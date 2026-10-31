"""Milestone 3 analyses: everything the data-model document and the M2 feedback ask for that the base
report does not compute. No model is called; every number comes from the stored verdicts.

  python -m biojudge.m3_analysis --run runs/local --config configs/ollama_l40s_ctrl.yaml --paper paper/

What it adds to biojudge.report:

  baselines     random chooser and prefer-longer, beside the uncorrected single judge and jury
  gameability   per-edit placebo-adjusted rate for each correction, including deterministic normalization
  RQ4           association between accuracy gain and robustness gain across the corrections
  RQ5           the same association within each benchmark and on the natural-error subset
  length        the length-controlled correction, after Dubois et al. (2024)
  equivalence   two one-sided tests of every accuracy change against the smallest effect of interest

Writes <run>/results/m3_metrics.json, m3_corrections.csv, m3_gameability.csv and paper/figs/m3_*.png.
"""
from __future__ import annotations

import argparse
import json
import os

import numpy as np
import pandas as pd
from scipy.stats import rankdata

from .analysis import (SINGLE_ATTACKS, Boot, Est, build_view, equivalence, load_trials, metrics)
from .config import load_config
from .pipeline import read_jsonl

# (key, table label, judge prompt + text protocol, aggregation). Each row is one correction compared
# with BASE; keys spell the combination in the notation of the data-model document.
BASE = ("Base", "Uncorrected single judge", "base_raw", "single")
CORRECTIONS = [
    ("S", "Swap aggregation (S)", "base_raw", "swap"),
    ("D", "Debiasing prompt (D)", "debias_raw", "single"),
    ("N", "LLM normalization (N)", "base_norm", "single"),
    ("Det", "Deterministic normalization", "base_strip", "single"),
    ("D+N", "D+N", "debias_norm", "single"),
    ("J", "Four-judge jury (J)", "base_raw", "jury"),
    ("R", "Recusal jury (R)", "base_raw", "recusal"),
    ("R+S", "R+S", "base_raw", "recusal+swap"),
    ("D+N+R", "D+N+R", "debias_norm", "recusal"),
    ("D+N+R+S", "D+N+R+S", "debias_norm", "recusal+swap"),
]
#: Smallest effect of interest, in proportion units. Chosen after the main run, and reported as such.
SESOI = 0.05
SUBSETS = ["literature", "clinical", "pharmacology", "natural_error"]


# =============================================================================== data
def load_all(run: str) -> pd.DataFrame:
    """The main-run verdicts plus, if collected, the placebo under deterministic normalization."""
    df = load_trials(os.path.join(run, "trials.jsonl"))
    extra = os.path.join(run, "strip_placebo.jsonl")
    if os.path.exists(extra):
        df = pd.concat([df, load_trials(extra)], ignore_index=True)
    return df


def natural_error_pairs(solo: pd.DataFrame, items: list[dict]) -> set[tuple[str, str]]:
    """(item, author) pairs whose R- defends the answer the author chose unprompted.

    A forced rationale defends an answer its author was told to defend. These are the exceptions: the
    author's own solo answer on the item was the distractor, so the error was not forced on it.
    """
    distractor = {it["item_id"]: it["distractor"] for it in items}
    return {(r.item_id, r.model) for r in solo.itertuples() if r.pred and r.pred == distractor.get(r.item_id)}


def subset(df: pd.DataFrame, name: str, natural: set[tuple[str, str]]) -> pd.DataFrame:
    if name != "natural_error":
        return df[df.domain == name]
    keep = [(i, w) in natural for i, w in zip(df.item_id, df.wg)]
    return df[keep]


# =============================================================================== per-configuration metrics
def tie_rate(bt: Boot, v: pd.DataFrame) -> Est | None:
    """Share of clean units scored one half (a tie, an unparseable verdict, or an aggregation tie)."""
    clean = v[(v.block == "bias") & (v.length_cond == "none")]
    return bt.mean(clean.assign(t=(clean.is_correct == 0.5).astype(float)), "t")


def gameability(m: dict) -> Est | None:
    """G = the mean placebo-adjusted attack success over the five single edits (the headline measure)."""
    parts = [m[f"adj_{a}"] for a in SINGLE_ATTACKS if f"adj_{a}" in m]
    if len(parts) != len(SINGLE_ATTACKS):
        return None
    return Est(float(np.mean([p.point for p in parts])), np.mean([p.boot for p in parts], axis=0))


def config_table(bt: Boot, df: pd.DataFrame) -> dict[str, dict]:
    """All metrics for BASE and each correction on one slice of the verdicts."""
    out = {}
    for key, _, proto, agg in [BASE] + CORRECTIONS:
        v = build_view(df, proto, agg)
        if v.empty:
            continue
        m = metrics(bt, v, per_judge_self=agg in ("single", "swap"))
        m["tie"] = tie_rate(bt, v)
        # half credit flatters a panel that abstains, so accuracy is also read with ties as misses
        c = v[(v.block == "bias") & (v.length_cond == "none")]
        m["acc_strict"] = bt.mean(c.assign(s=(c.is_correct == 1.0).astype(float)), "s")
        m["G"] = gameability(m)
        # the unadjusted counterpart of G: how much of a robustness gain survives without the floor
        singles = [m[f"asr_{a}"] for a in SINGLE_ATTACKS if f"asr_{a}" in m]
        if len(singles) == len(SINGLE_ATTACKS):
            m["asr_mean"] = Est(float(np.mean([e.point for e in singles])), np.mean([e.boot for e in singles], axis=0))
        out[key] = {k: e for k, e in m.items() if e is not None}
    return out


def gains(table: dict[str, dict], metric: str = "G") -> dict[str, dict]:
    """Delta accuracy and Delta robustness of each correction, both as paired bootstrap differences.
    Robustness gain = metric(base) - metric(corrected), so positive means harder to game."""
    b = table["Base"]
    out = {}
    for key, *_ in CORRECTIONS:
        m = table.get(key)
        if not m or "acc" not in m or metric not in m or metric not in b:
            continue
        out[key] = {"dacc": m["acc"] - b["acc"], "drob": b[metric] - m[metric]}
    return out


# =============================================================================== RQ4 / RQ5
def _spearman_boot(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Spearman's rho for each bootstrap replicate; x and y are replicates x corrections."""
    rx, ry = rankdata(x, axis=1), rankdata(y, axis=1)
    rx = rx - rx.mean(1, keepdims=True)
    ry = ry - ry.mean(1, keepdims=True)
    with np.errstate(invalid="ignore", divide="ignore"):
        return (rx * ry).sum(1) / np.sqrt((rx ** 2).sum(1) * (ry ** 2).sum(1))


def transfer(g: dict[str, dict], seed: int, n_perm: int = 20000) -> dict:
    """Association between accuracy gain and robustness gain across corrections.

    Corrections share verdicts, so the corrections are not independent observations and the permutation
    p-value is only descriptive. The item-level bootstrap interval is the honest measure of uncertainty:
    it resamples what was actually sampled, which is items.
    """
    keys = list(g)
    x = np.array([g[k]["dacc"].point for k in keys])
    y = np.array([g[k]["drob"].point for k in keys])
    rho = float(_spearman_boot(x[None, :], y[None, :])[0])
    bx = np.column_stack([g[k]["dacc"].boot for k in keys])
    by = np.column_stack([g[k]["drob"].boot for k in keys])
    ok = np.isfinite(bx).all(1) & np.isfinite(by).all(1)
    boot = _spearman_boot(bx[ok], by[ok])
    boot = boot[np.isfinite(boot)]
    rng = np.random.default_rng(seed)
    perm = np.array([_spearman_boot(x[None, :], rng.permutation(y)[None, :])[0] for _ in range(n_perm)])
    p = float((np.sum(np.abs(perm) >= abs(rho) - 1e-12) + 1) / (n_perm + 1))
    lo, hi = np.percentile(boot, [2.5, 97.5]) if boot.size else (np.nan, np.nan)
    both = [k for k in keys if g[k]["dacc"].point > 0 and g[k]["drob"].point > 0]
    # a correction "trades off" when one gain is positive and the other negative
    trade = [k for k in keys if g[k]["dacc"].point * g[k]["drob"].point < 0]
    sig_acc = [k for k in keys if g[k]["dacc"].ci()[0] > 0]
    sig_rob = [k for k in keys if g[k]["drob"].ci()[0] > 0]
    pearson = float(np.corrcoef(x, y)[0, 1])
    return {"rho": rho, "lo": float(lo), "hi": float(hi), "p_perm": p, "pearson": pearson, "n_corrections": len(keys),
            "n_boot_used": int(boot.size), "both_positive": both, "trade_off": trade,
            "acc_ci_above_zero": sig_acc, "rob_ci_above_zero": sig_rob}


# =============================================================================== baselines
def prefer_longer(bt: Boot, df: pd.DataFrame) -> dict:
    """The trivial heuristic baseline: always pick the longer rationale. It uses no model at all."""
    base = df[(df.protocol == "base_raw") & (df.block == "bias")]
    # one row per (item, pair, length condition): a length heuristic does not read the order or the judge
    u = base.drop_duplicates(["item_id", "pair_idx", "length_cond"]).copy()
    u["pick"] = np.where(u.len_correct > u.len_wrong, 1.0, np.where(u.len_correct < u.len_wrong, 0.0, 0.5))
    out = {f"acc_{k}": e for k, e in bt.means(u, "pick", ["length_cond"]).items()}
    return out


def longer_share(bt: Boot, df: pd.DataFrame) -> dict:
    """How often a judge's decided clean verdict goes to the longer rationale, per judge and pooled."""
    c = df[(df.protocol == "base_raw") & (df.block == "bias") & (df.length_cond == "none")
           & (df.len_correct != df.len_wrong) & (df.is_correct != 0.5)].copy()
    c["longer"] = ((c.len_correct > c.len_wrong) == (c.is_correct == 1.0)).astype(float)
    out = {"pooled": bt.mean(c, "longer")}
    out.update(bt.means(c, "longer", ["judge"]))
    return out


# =============================================================================== length-controlled correction
def length_controlled(bt: Boot, df: pd.DataFrame, protocol: str) -> dict:
    """Accuracy with the length difference between the two rationales statistically removed.

    After the length-controlled evaluation of Dubois et al. (2024): fit a linear probability model on
    the whole bias block (clean and padded pairs),  s = judge FE + slot + beta * LR, with
    LR = log(words(R-) / words(R+)), and read clean accuracy at LR = 0, i.e. Acc_clean - beta * mean(LR).
    The normal equations are summed per item, so every bootstrap replicate is one weighted solve.
    This correction adjusts a score after judging, so it has no attack-success counterpart.
    """
    d = df[(df.protocol == protocol) & (df.block == "bias")].copy()
    d["LR"] = np.log(d.len_wrong.clip(lower=1) / d.len_correct.clip(lower=1))
    judges = sorted(d.judge.unique())
    X = np.column_stack([(d.judge == j).astype(float) for j in judges]
                        + [(d.correct_slot == "B").astype(float), d.LR.values])
    y = d.is_correct.values.astype(float)
    pos = {it: i for i, it in enumerate(bt.items)}
    idx = d.item_id.map(pos).values
    p = X.shape[1]
    XtX, Xty = np.zeros((len(bt.items), p, p)), np.zeros((len(bt.items), p))
    np.add.at(XtX, idx, np.einsum("ni,nj->nij", X, X))
    np.add.at(Xty, idx, X * y[:, None])
    is_clean = (d.length_cond == "none").values
    S_y = np.bincount(idx[is_clean], y[is_clean], minlength=len(bt.items))
    S_lr = np.bincount(idx[is_clean], d.LR.values[is_clean], minlength=len(bt.items))
    C = np.bincount(idx[is_clean], minlength=len(bt.items)).astype(float)

    def est(w):
        # least squares, not a plain solve: if all lengths are equal (the simulator) the slope is unidentified
        beta = np.linalg.lstsq(np.einsum("i,ijk->jk", w, XtX), np.einsum("i,ij->j", w, Xty), rcond=None)[0][-1]
        acc, lr = (w @ S_y) / (w @ C), (w @ S_lr) / (w @ C)
        return acc - beta * lr, beta, lr

    point = est(np.ones(len(bt.items)))
    rep = np.array([est(w) for w in bt.W])
    raw = Est(float(S_y.sum() / C.sum()), (bt.W @ S_y) / (bt.W @ C))
    lc = Est(float(point[0]), rep[:, 0])
    return {"acc_raw": raw, "acc_lc": lc, "gain": lc - raw, "beta": Est(float(point[1]), rep[:, 1]),
            "mean_lr": Est(float(point[2]), rep[:, 2])}


# =============================================================================== data accounting
def exclusions(items: list[dict], responses: list[dict]) -> dict:
    """Exclusions counted by reason and benchmark, as the data-preparation plan requires."""
    r = pd.DataFrame(responses)
    src = {it["item_id"]: it["source"] for it in items}
    r["source"] = r.item_id.map(src)
    per_item = r.groupby("item_id").valid.all()
    bad = r[~r.valid]
    out = {"n_sampled": len(items), "n_rationales": int(len(r)), "n_valid": int(r.valid.sum()),
           "n_kept": int(per_item.sum()), "first_try": int((r.attempts == 1).sum()),
           "retried_ok": int(((r.attempts > 1) & r.valid).sum()),
           "max_words": int(r.words.max()), "min_words_valid": int(r[r.valid].words.min()),
           "over_250": int((r.words > 250).sum()),
           "by_reason": bad.reason.value_counts().to_dict(),
           "excluded_by_source": {}, "kept_by_source": {}}
    for it in items:
        s = it["source"]
        out["kept_by_source"].setdefault(s, 0)
        out["excluded_by_source"].setdefault(s, 0)
        if per_item.get(it["item_id"], False):
            out["kept_by_source"][s] += 1
        else:
            out["excluded_by_source"][s] += 1
    return out


# =============================================================================== qualitative check
def injection_mentions(df: pd.DataFrame) -> dict:
    """Do judges that the note to the evaluator overturned say so in their explanation?

    Looks at clean-correct units that the note turned wrong, and counts explanations naming the note.
    The stored verdict text keeps the first 600 characters, which covers the explanation in most units.
    """
    keys = ["judge", "item_id", "pair_idx", "correct_slot"]
    b = df[df.protocol == "base_raw"]
    clean = b[(b.block == "bias") & (b.length_cond == "none") & (b.is_correct == 1.0)][keys + ["raw"]]
    att = b[(b.block == "attack") & (b.attack == "injection") & (b.is_correct == 0.0)]
    hit = att.merge(clean, on=keys, suffixes=("", "_clean"))
    pat = r"verified|review team|evaluator|note to|should be selected"
    named = hit.raw.fillna("").str.contains(pat, case=False)
    # the note says it was checked "against current clinical guidelines", so an appeal to guidelines may
    # be an echo of it; the same units' clean verdicts show how common that appeal is without the note
    guide = hit.raw.fillna("").str.contains("guideline", case=False)
    guide_clean = hit.raw_clean.fillna("").str.contains("guideline", case=False)
    return {"n_flipped": int(len(hit)), "n_named": int(named.sum()), "share_named": float(named.mean()),
            "share_guideline": float(guide.mean()), "share_guideline_clean": float(guide_clean.mean()),
            "by_judge": hit.assign(n=named).groupby("judge").n.mean().to_dict()}


def strip_identity(run: str) -> dict:
    """Share of incorrect rationales for which deterministic normalization undoes an edit exactly.

    Where the stripped edited text equals the stripped clean text, the judge is shown the clean prompt
    again, so that edit's attack success under Det measures decoding churn and nothing else.
    """
    v = {r["key"]: r["text"] for r in read_jsonl(os.path.join(run, "variants.jsonl"))}
    out = {}
    for a in list(SINGLE_ATTACKS) + ["combo", "placebo", "consensus"]:
        tail = f"|atk:{a}#strip"
        ks = [k for k in v if k.endswith(tail) and "|-|" in k]
        out[a] = sum(v[k] == v[k.replace(f"atk:{a}#strip", "raw#strip")] for k in ks) / len(ks) if ks else None
    return out


# =============================================================================== figures
def _style():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8, "axes.spines.top": False,
                         "axes.spines.right": False, "axes.edgecolor": "#6b6b6b", "axes.linewidth": 0.6,
                         "xtick.color": "#444444", "ytick.color": "#444444", "axes.labelcolor": "#222222",
                         "grid.color": "#e4e4e4", "grid.linewidth": 0.6})
    return plt


COL_BASE, COL_CORR, COL_INK = "#2a78b4", "#c8682a", "#333333"
EDIT_LABEL = {"authority": "Authority", "citation": "Citation", "format": "Formatting", "confidence": "Confidence",
              "injection": "Evaluator instruction", "combo": "All five combined", "consensus": "Held-out consensus"}


def fig_gameability(table: dict, path: str) -> None:
    """Placebo-adjusted attack success per edit, uncorrected vs deterministic and LLM normalization."""
    plt = _style()
    edits = ["injection", "combo", "citation", "format", "consensus", "authority", "confidence"]
    cfgs = [("Base", "Uncorrected", "#2a78b4", "o"), ("Det", "Deterministic normalization", "#c8682a", "s"),
            ("N", "LLM normalization", "#3e8e5a", "^")]
    fig, ax = plt.subplots(figsize=(6.3, 3.5))
    for i, (key, lab, col, mk) in enumerate(cfgs):
        for j, a in enumerate(edits):
            e = table[key].get(f"adj_{a}")
            if e is None:
                continue
            lo, hi = e.ci()
            yy = len(edits) - 1 - j + (1 - i) * 0.24
            ax.plot([100 * lo, 100 * hi], [yy, yy], color=col, lw=1.4, solid_capstyle="round", zorder=2)
            ax.plot(100 * e.point, yy, mk, ms=5.5, color=col, mec="white", mew=0.7, zorder=3,
                    label=lab if j == 0 else None)
    ax.axvline(0, color=COL_INK, lw=0.9)
    ax.set_yticks(range(len(edits)), [EDIT_LABEL[a] for a in reversed(edits)])
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    ax.xaxis.grid(True)
    ax.set_axisbelow(True)
    ax.set_xlabel("Attack success above the placebo floor (percentage points, 95% bootstrap CI)")
    ax.legend(frameon=False, loc="lower right")
    fig.tight_layout()
    fig.savefig(path, dpi=300)
    plt.close(fig)


# label placement (dx, dy, ha) in points; set by looking at the rendered scatter
_OFF = {"D+N+R+S": (-6, 5, "right"), "D+N+R": (6, -9, "left"), "D+N": (6, 4, "left"), "N": (6, -10, "left"),
        "Det": (6, 4, "left"), "D": (6, 3, "left"), "S": (-6, 5, "right"), "J": (6, 4, "left"),
        "R": (6, -9, "left"), "R+S": (6, 4, "left")}


def _place_labels(ax, g, fontsize=6.5):
    """Greedy label placement: try offsets around each point, keep the first clear of other labels and points."""
    fig = ax.figure
    fig.canvas.draw()
    rend = fig.canvas.get_renderer()
    pts = {k: ax.transData.transform((100 * d["dacc"].point, 100 * d["drob"].point)) for k, d in g.items()}
    placed = []
    tries = [(4, 3, "left"), (4, -9, "left"), (-4, 3, "right"), (-4, -9, "right"), (0, 7, "center"), (0, -14, "center"),
             (9, -3, "left"), (-9, -3, "right"), (4, 12, "left"), (-4, 12, "right"), (4, -18, "left"), (-4, -18, "right")]
    # the most crowded points choose first, while they still have room
    order = sorted(g, key=lambda k: -sum(abs(pts[k] - p).sum() < 90 for p in pts.values()))
    for k in order:
        x, y = 100 * g[k]["dacc"].point, 100 * g[k]["drob"].point
        best = None
        for dx, dy, ha in tries:
            t = ax.annotate(k, (x, y), xytext=(dx, dy), textcoords="offset points", ha=ha, fontsize=fontsize, color="#222222")
            box = t.get_window_extent(rend)
            clash = any(box.overlaps(b) for b in placed) or any(
                box.x0 - 3 < p[0] < box.x1 + 3 and box.y0 - 3 < p[1] < box.y1 + 3 for p in pts.values())
            if not clash:
                best = box
                break
            t.remove()
        if best is None:   # nothing clear: fall back to the first position
            t = ax.annotate(k, (x, y), xytext=tries[0][:2], textcoords="offset points", ha="left", fontsize=fontsize, color="#222222")
            best = t.get_window_extent(rend)
        placed.append(best)


def _scatter(ax, g, ci=True, labels=True):
    for k, d in g.items():
        x, y = 100 * d["dacc"].point, 100 * d["drob"].point
        if ci:
            xl, xh = d["dacc"].ci()
            yl, yh = d["drob"].ci()
            ax.plot([100 * xl, 100 * xh], [y, y], color="#b9c6d2", lw=0.8, zorder=1)
            ax.plot([x, x], [100 * yl, 100 * yh], color="#b9c6d2", lw=0.8, zorder=1)
        ax.plot(x, y, "o", ms=6, color=COL_BASE, mec="white", mew=0.8, zorder=3)
        if labels:
            dx, dy, ha = _OFF.get(k, (5, 4, "left"))
            ax.annotate(k, (x, y), xytext=(dx, dy), textcoords="offset points", ha=ha, fontsize=7.5, color="#222222")
    ax.axhline(0, color=COL_INK, lw=0.7)
    ax.axvline(0, color=COL_INK, lw=0.7)


def fig_transfer(g: dict, res: dict, path: str) -> None:
    plt = _style()
    fig, ax = plt.subplots(figsize=(5.6, 4.0))
    _scatter(ax, g)
    ax.set_xlabel("Accuracy gain over the uncorrected judge (pp)")
    ax.set_ylabel("Robustness gain: reduction in gameability G (pp)")
    ax.text(0.02, 0.97, f"Spearman ρ = {res['rho']:.2f}  [{res['lo']:.2f}, {res['hi']:.2f}]".replace("-", "−"),
            transform=ax.transAxes, va="top", fontsize=8, color="#222222")
    fig.tight_layout()
    fig.savefig(path, dpi=300)
    plt.close(fig)


def fig_bestof(sel: dict, path: str) -> None:
    """Best-of-4: correct picks and captures, per pool, for the base and corrected protocols."""
    plt = _style()
    pools, labs = ["clean", "pad", "attack"], ["Clean pool", "One candidate\npadded", "One candidate\nwith all edits"]
    protos = [("base_raw", "Uncorrected", COL_BASE, "o"), ("debias_norm", "D+N", COL_CORR, "s")]
    fig, axes = plt.subplots(1, 2, figsize=(6.3, 2.9), sharey=True)
    for ax, (pre, title) in zip(axes, (("acc", "Correct candidate picked"), ("capture", "Decorated candidate picked"))):
        for k, (p, lab, col, mk) in enumerate(protos):
            r = sel[f"{p}|pooled"]
            xs = np.arange(3) + (k - 0.5) * 0.22
            ys = [100 * r[f"{pre}_{c}"]["est"] for c in pools]
            lo = [100 * r[f"{pre}_{c}"]["lo"] for c in pools]
            hi = [100 * r[f"{pre}_{c}"]["hi"] for c in pools]
            ax.vlines(xs, lo, hi, color=col, lw=1.4, zorder=2)
            ax.plot(xs, ys, mk, ms=6, color=col, mec="white", mew=0.7, label=lab, zorder=3)
        ax.axhline(100 * sel["base_raw|pooled"]["chance_scored"]["est"], ls=":", lw=0.9, color="#555555")
        ax.set_xticks(range(3), labs, fontsize=7)
        ax.set_title(title, fontsize=8, loc="left", color="#222222")
        ax.yaxis.grid(True)
        ax.set_axisbelow(True)
        ax.set_xlim(-0.5, 2.5)
    axes[0].set_ylabel("% of selections")
    axes[0].set_ylim(0, 50)
    axes[0].legend(frameon=False, loc="upper right", fontsize=7)
    axes[1].annotate("random pick", (-0.45, 100 * sel["base_raw|pooled"]["chance_scored"]["est"]), xytext=(0, 3),
                     textcoords="offset points", fontsize=6.5, color="#555555", ha="left")
    fig.tight_layout()
    fig.savefig(path, dpi=300)
    plt.close(fig)


def fig_boundary(gs: dict, rs: dict, path: str) -> None:
    plt = _style()
    names = {"literature": "PubMedQA", "clinical": "MedQA-USMLE", "pharmacology": "MedMCQA",
             "natural_error": "Natural-error subset"}
    fig, axes = plt.subplots(2, 2, figsize=(6.8, 5.6), sharex=True, sharey=True)
    for ax, s in zip(axes.ravel(), SUBSETS):
        g, r = gs.get(s), rs.get(s)
        if not g:
            ax.set_visible(False)
            continue
        _scatter(ax, g, ci=False, labels=False)
        ax.set_title(f"{names[s]}   " + f"ρ = {r['rho']:.2f} [{r['lo']:.2f}, {r['hi']:.2f}]".replace("-", "−"), fontsize=8, loc="left",
                     color="#222222")
        ax.xaxis.grid(True)
        ax.yaxis.grid(True)
        ax.set_axisbelow(True)
    axes[0, 0].set_xlim(-2.4, 10.5)   # room for the longest labels at the right edge
    fig.supxlabel("Accuracy gain over the uncorrected judge (pp)", fontsize=8)
    fig.supylabel("Robustness gain in G (pp)", fontsize=8)
    fig.tight_layout()
    # labels are placed after layout, because their collision test uses final pixel positions
    for ax, s in zip(axes.ravel(), SUBSETS):
        if gs.get(s):
            _place_labels(ax, gs[s])
    fig.savefig(path, dpi=300)
    plt.close(fig)


# =============================================================================== driver
def _dump(table: dict) -> dict:
    return {k: {m: e.as_dict() for m, e in v.items()} for k, v in table.items()}


def _dump_gains(g: dict) -> dict:
    return {k: {m: e.as_dict() for m, e in d.items()} for k, d in g.items()}


def build(run: str, cfg: dict, paper: str) -> dict:
    res_dir, fdir = os.path.join(run, "results"), os.path.join(paper, "figs")
    os.makedirs(res_dir, exist_ok=True)
    os.makedirs(fdir, exist_ok=True)
    df = load_all(run)
    items = read_jsonl(os.path.join(run, "items.jsonl"))
    responses = read_jsonl(os.path.join(run, "responses.jsonl"))
    solo = pd.DataFrame(read_jsonl(os.path.join(run, "solo.jsonl")))
    # identical draw to biojudge.report: the extra placebo rows add no item, so the weights are shared
    bt = Boot(df.item_id.unique(), cfg["analysis"]["bootstrap"], cfg["seed"])
    seed = cfg["seed"]
    out: dict = {"exclusions": exclusions(items, responses), "sesoi": SESOI,
                 "labels": {k: lab for k, lab, *_ in [BASE] + CORRECTIONS},
                 "has_strip_placebo": "placebo" in set(df[df.protocol == "base_strip"].attack)}

    table = config_table(bt, df)
    out["configs"] = _dump(table)
    g = gains(table)
    if len(g) < 3:
        raise SystemExit("[m3] this run has no placebo verdicts, so gameability is undefined; "
                         "use a configuration with attacks_control (see configs/ollama_l40s_ctrl.yaml)")
    out["gains"] = _dump_gains(g)
    out["transfer"] = transfer(g, seed)
    # sensitivity of RQ4 to how robustness is summarized
    out["transfer_sensitivity"] = {}
    out["transfer_no_det"] = transfer({k: d for k, d in g.items() if k != "Det"}, seed)
    for tag, metric in (("raw_mean", "asr_mean"), ("any", "asr_any"), ("combo", "adj_combo"),
                        ("injection", "adj_injection"), ("net_any", "net_any")):
        gs = gains(table, metric)
        if len(gs) >= 3:
            out["transfer_sensitivity"][tag] = transfer(gs, seed)
    # accuracy-improving corrections must be judged both ways: equivalence against the smallest effect
    out["equivalence"] = {k: equivalence(d["dacc"], SESOI) for k, d in g.items()}
    out["equivalence_rob"] = {k: equivalence(d["drob"], SESOI) for k, d in g.items()}

    # RQ5: the same analysis inside each benchmark and on the natural-error subset
    natural = natural_error_pairs(solo, items)
    out["natural_pairs"] = len(natural)
    sub_g, sub_r, sub_tables = {}, {}, {}
    for s in SUBSETS:
        d = subset(df, s, natural)
        t = config_table(bt, d)
        gs = gains(t)
        sub_tables[s] = t
        sub_g[s], sub_r[s] = gs, transfer(gs, seed) if len(gs) >= 3 else None
    out["subset"] = {s: {"n_items": int(subset(df, s, natural).item_id.nunique()),
                         "n_verdicts": int(len(subset(df, s, natural))),
                         "gains": _dump_gains(sub_g[s]), "transfer": sub_r[s],
                         "base": {k: e.as_dict() for k, e in sub_tables[s]["Base"].items()
                                  if k in ("acc", "G", "asr_placebo", "asr_injection", "adj_injection", "tie")}}
                     for s in SUBSETS}

    bl = {"random": 0.5}
    out["prefer_longer"] = {k: e.as_dict() for k, e in prefer_longer(bt, df).items()}
    out["longer_share"] = {k: e.as_dict() for k, e in longer_share(bt, df).items()}
    out["baselines"] = bl
    out["length_controlled"] = {p: {k: e.as_dict() for k, e in length_controlled(bt, df, p).items()}
                                for p in ("base_raw", "debias_raw", "base_norm", "debias_norm")}

    # the strip-placebo host check: same prompts as the L40S placebo, re-judged on the laptop
    hc = os.path.join(run, "host_check.jsonl")
    if os.path.exists(hc):
        h = load_trials(hc)   # placebo units re-judged on a second host, used only for this comparison
        join = ["judge", "item_id", "pair_idx", "correct_slot"]
        m0 = df[(df.protocol == "base_raw") & (df.attack == "placebo")][join + ["verdict", "is_correct"]]
        j = h.merge(m0, on=join, suffixes=("_laptop", "_l40s"))
        clean = df[(df.protocol == "base_raw") & (df.block == "bias") & (df.length_cond == "none")]
        c0 = clean[join + ["is_correct"]].rename(columns={"is_correct": "clean"})
        jc = j.merge(c0, on=join)
        hit = jc[jc.clean == 1.0]
        out["host_check"] = {"n": int(len(j)),
                             "verdict_agreement": float((j.verdict_laptop.fillna("?") == j.verdict_l40s.fillna("?")).mean()),
                             "acc_laptop": float(j.is_correct_laptop.mean()), "acc_l40s": float(j.is_correct_l40s.mean()),
                             "asr_laptop": float((1 - hit.is_correct_laptop).mean()),
                             "asr_l40s": float((1 - hit.is_correct_l40s).mean())}

    out["injection_mentions"] = injection_mentions(df)
    out["strip_identity"] = strip_identity(run)
    retest = os.path.join(run, "retest.jsonl")
    if os.path.exists(retest):
        rt = pd.DataFrame(read_jsonl(retest))
        hit = rt[rt.is_correct == 1.0]
        # what the attack success rate would be if the "edit" were a second decode of the same prompt
        out["retest_asr"] = bt.mean(hit.assign(s=1.0 - hit.is_correct_retest.astype(float)), "s").as_dict()

    fig_gameability(table, os.path.join(fdir, "m3_gameability.png"))
    base_metrics = os.path.join(res_dir, "metrics.json")   # written by biojudge.report
    if os.path.exists(base_metrics):
        with open(base_metrics) as f:
            fig_bestof(json.load(f)["select"], os.path.join(fdir, "m3_bestof.png"))
    fig_transfer(g, out["transfer"], os.path.join(fdir, "m3_transfer.png"))
    fig_boundary(sub_g, sub_r, os.path.join(fdir, "m3_boundary.png"))

    with open(os.path.join(res_dir, "m3_metrics.json"), "w") as f:
        json.dump(out, f, indent=2, default=float)
    pd.DataFrame([{"config": c, "metric": k, **e.as_dict()} for c, m in table.items() for k, e in m.items()]) \
        .to_csv(os.path.join(res_dir, "m3_corrections.csv"), index=False, lineterminator="\n")
    pd.DataFrame([{"config": c, "edit": a, "metric": pre, **m[f"{pre}_{a}"].as_dict()} for c, m in table.items()
                  for a in list(SINGLE_ATTACKS) + ["combo", "placebo", "consensus"] for pre in ("asr", "adj", "rr", "net", "dacc")
                  if f"{pre}_{a}" in m]).to_csv(os.path.join(res_dir, "m3_gameability.csv"), index=False, lineterminator="\n")
    print(f"[m3] {len(table)} configurations; transfer rho={out['transfer']['rho']:.2f} "
          f"[{out['transfer']['lo']:.2f}, {out['transfer']['hi']:.2f}]; outputs in {res_dir}")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run", required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--paper", default="paper")
    a = ap.parse_args()
    build(a.run, load_config(a.config), a.paper)


if __name__ == "__main__":
    main()
