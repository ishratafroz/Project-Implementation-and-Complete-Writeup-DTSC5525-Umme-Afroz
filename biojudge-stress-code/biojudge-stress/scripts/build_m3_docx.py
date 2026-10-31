"""Build the Milestone 3 Word document from the paper template and the stored results.

  python scripts/build_m3_docx.py --out "../../Project-Implementation and Complete Writeup-DTSC5525-Umme Afroz.docx"

No result is typed into the paper by hand. paper/m3_paper_template.md carries named slots, and this script
replaces each one with the value in runs/local/results/{metrics.json,m3_metrics.json}. It stops without
writing anything if a slot does not resolve. Tables are generated here from the same two files.

Slot forms, where PATH walks the JSON (c = m3 configs, g = m3 gains, s = m3 subsets, x = m3 root, b = metrics.json):
  @@v:PATH@@   estimate in percent or pp, one decimal      @@a:PATH@@   its magnitude
  @@ci:PATH@@  95% interval "[lo, hi]" in the same units   @@p:PATH@@   p value
  @@r:PATH@@   plain number, two decimals                  @@n:PATH@@   integer with thousands separators
  @@M:Name@@   a macro from metrics.json["macros"]         @@h:PATH@@   seconds as hours, one decimal
  @@L:PATH@@   a list of names, as prose

Template markup: "# " and "## " headings, **bold**, *italic*, $inline math$ with _{sub} and ^{sup},
"\\eq{...}" for a numbered display equation, "{{TABLE:name}}", "{{FIG:file|caption|width in inches}}",
"> " for a quotation, "- " for a bullet, and "REF: " for a hanging-indent reference.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys

import docx
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn
from docx.shared import Inches, Pt, RGBColor

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
MINUS = "−"
FONT = "Times New Roman"
M_NS = 'xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math"'


# =============================================================================== slots
class Values:
    def __init__(self, run: str):
        with open(os.path.join(run, "results", "metrics.json")) as f:
            self.b = json.load(f)
        with open(os.path.join(run, "results", "m3_metrics.json")) as f:
            self.x = json.load(f)
        with open(os.path.join(run, "model_tags.json")) as f:
            self.tags = json.load(f)
        self.roots = {"b": self.b, "x": self.x, "c": self.x["configs"], "g": self.x["gains"], "s": self.x["subset"]}

    def get(self, path: str):
        root, *rest = path.split(".")
        node = self.roots[root]
        for k in rest:
            node = node[k]
        return node


def _sign(s: str) -> str:
    return s.replace("-", MINUS)


def _point(node) -> float:
    if isinstance(node, dict):
        return node["est"] if "est" in node else node["coef"]
    return float(node)


def resolve(form: str, path: str, V: Values) -> str:
    if form == "M":
        return (V.b["macros"][path].replace("{,}", ",").replace("$-$", MINUS).replace("$<$", "<")
                .replace("p=", "p = ").replace("p<", "p < "))
    node = V.get(path)
    if form == "L":
        return ", ".join(node[:-1]) + (" and " if len(node) > 1 else "") + node[-1] if node else "none"
    if form == "v":
        return _sign(f"{100 * _point(node):.1f}")
    if form == "a":
        return f"{abs(100 * _point(node)):.1f}"
    if form == "ci":
        return _sign(f"[{100 * node['lo']:.1f}, {100 * node['hi']:.1f}]")
    if form == "r":
        return _sign(f"{_point(node):.2f}")
    if form == "n":
        return f"{int(round(float(node))):,}"
    if form == "h":
        return f"{float(node) / 3600:.1f}"
    if form == "p":
        p = node["p"] if isinstance(node, dict) else float(node)
        return "p < 0.001" if p < 0.001 else f"p = {p:.3f}"
    raise KeyError(form)


SLOT = re.compile(r"@@(v|a|ci|r|n|h|p|M|L):([^@]+)@@")


def fill(text: str, V: Values, errors: list[str]) -> str:
    def rep(m):
        try:
            return resolve(m.group(1), m.group(2), V)
        except (KeyError, TypeError, ValueError) as e:
            errors.append(f"{m.group(0)}: {e!r}")
            return "??"
    return SLOT.sub(rep, text)


# =============================================================================== inline text
TOKEN = re.compile(r"(\*\*.+?\*\*|\*[^*]+?\*|\$[^$]+?\$)")
MATH_PART = re.compile(r"(_\{[^}]*\}|\^\{[^}]*\})")


def _run(par, text, bold=False, italic=False, sub=False, sup=False, size=None):
    r = par.add_run(text)
    r.bold, r.italic = bold or None, italic or None
    if sub:
        r.font.subscript = True
    if sup:
        r.font.superscript = True
    if size:
        r.font.size = Pt(size)
    return r


def add_inline(par, text, size=None, bold=False):
    for tok in TOKEN.split(text):
        if not tok:
            continue
        if tok.startswith("**"):
            add_inline(par, tok[2:-2], size, bold=True)
        elif tok.startswith("$"):
            for part in MATH_PART.split(tok[1:-1]):
                if part.startswith("_{"):
                    _run(par, part[2:-1], italic=True, sub=True, size=size, bold=bold)
                elif part.startswith("^{"):
                    _run(par, part[2:-1], italic=True, sup=True, size=size, bold=bold)
                elif part:
                    _run(par, part, italic=True, size=size, bold=bold)
        elif tok.startswith("*"):
            _run(par, tok[1:-1], italic=True, size=size, bold=bold)
        else:
            _run(par, tok, size=size, bold=bold)


# =============================================================================== display equations (OMML)
def _omml_text(s: str, normal: bool = False) -> str:
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    pr = "<m:rPr><m:nor/></m:rPr>" if normal else ""
    rfonts = '<w:rPr><w:rFonts w:ascii="Cambria Math" w:hAnsi="Cambria Math"/></w:rPr>'
    return f'<m:r>{pr}{rfonts}<m:t xml:space="preserve">{s}</m:t></m:r>'


def _group(src: str, i: int) -> tuple[str, int]:
    """Return the contents of the brace group opening at src[i] and the index just past it."""
    depth, j = 0, i
    while True:
        depth += {"{": 1, "}": -1}.get(src[j], 0)
        j += 1
        if depth == 0:
            return src[i + 1:j - 1], j


def _omml(src: str) -> str:
    """A small subset of LaTeX: \\frac{}{}, \\text{}, _{} and ^{} on the preceding atom, and Unicode."""
    atoms: list[str] = []
    i, buf = 0, ""

    def flush():
        nonlocal buf
        if buf:
            atoms.append(_omml_text(buf))
            buf = ""

    while i < len(src):
        c = src[i]
        if src.startswith("\\frac", i):
            flush()
            a, i = _group(src, i + 5)
            b, i = _group(src, i)
            atoms.append(f"<m:f><m:num>{_omml(a)}</m:num><m:den>{_omml(b)}</m:den></m:f>")
        elif src.startswith("\\text", i):
            flush()
            a, i = _group(src, i + 5)
            atoms.append(_omml_text(a, normal=True))
        elif c in "_^":
            flush()
            base = atoms.pop() if atoms else _omml_text(" ")
            a, i = _group(src, i + 1)
            if c == "_" and src[i:i + 1] == "^":
                b, i = _group(src, i + 1)
                atoms.append(f"<m:sSubSup><m:e>{base}</m:e><m:sub>{_omml(a)}</m:sub><m:sup>{_omml(b)}</m:sup></m:sSubSup>")
            elif c == "_":
                atoms.append(f"<m:sSub><m:e>{base}</m:e><m:sub>{_omml(a)}</m:sub></m:sSub>")
            else:
                atoms.append(f"<m:sSup><m:e>{base}</m:e><m:sup>{_omml(a)}</m:sup></m:sSup>")
        else:
            buf += c
            i += 1
            # keep multi-letter words together only until a script arrives on the last atom
            if i < len(src) and src[i] in "_^":
                flush()
    flush()
    return "".join(atoms)


def add_equation(doc, src: str, number: int, width_in: float):
    par = doc.add_paragraph()
    par.paragraph_format.space_before = Pt(4)
    par.paragraph_format.space_after = Pt(6)
    tabs = par.paragraph_format.tab_stops
    tabs.add_tab_stop(Inches(width_in / 2), WD_TAB_ALIGNMENT.CENTER)
    tabs.add_tab_stop(Inches(width_in), WD_TAB_ALIGNMENT.RIGHT)
    par.add_run("\t")
    math = parse_xml(f'<m:oMath {M_NS} {nsdecls("w")}>{_omml(src)}</m:oMath>')
    par._p.append(math)
    par.add_run(f"\t({number})")


# =============================================================================== tables
def _shade(cell, fill_hex: str):
    cell._tc.get_or_add_tcPr().append(parse_xml(f'<w:shd {nsdecls("w")} w:val="clear" w:color="auto" w:fill="{fill_hex}"/>'))


def _borders(cell, **edges):
    pr = cell._tc.get_or_add_tcPr()
    b = OxmlElement("w:tcBorders")
    for edge in ("top", "left", "bottom", "right"):
        el = OxmlElement(f"w:{edge}")
        val = edges.get(edge)
        el.set(qn("w:val"), "single" if val else "nil")
        if val:
            el.set(qn("w:sz"), str(val))
            el.set(qn("w:color"), "444444")
        b.append(el)
    pr.append(b)


def add_table(doc, counters, caption: str, header: list[str], rows: list[list[str]], widths: list[float],
              note: str | None = None, size: float = 8.5, align_num_from: int = 1, rules: tuple = ()):
    """Caption above, three-line rule style, header row repeats across pages, rows never split."""
    counters["table"] += 1
    cap = doc.add_paragraph(style="Caption")
    cap.paragraph_format.keep_with_next = True
    add_inline(cap, f"**Table {counters['table']}.** {caption}")
    t = doc.add_table(rows=1 + len(rows), cols=len(header))
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    # narrow cell margins, so that dense numeric columns do not wrap
    t._tbl.tblPr.append(parse_xml(f'<w:tblCellMar {nsdecls("w")}><w:left w:w="40" w:type="dxa"/><w:right w:w="40" w:type="dxa"/></w:tblCellMar>'))
    last = len(rows)
    for ri, row in enumerate([header] + rows):
        tr = t.rows[ri]._tr.get_or_add_trPr()
        tr.append(OxmlElement("w:cantSplit"))
        if ri == 0:
            tr.append(OxmlElement("w:tblHeader"))
        for ci, val in enumerate(row):
            c = t.cell(ri, ci)
            c.width = Inches(widths[ci])
            par = c.paragraphs[0]
            par.paragraph_format.space_after = Pt(1)
            par.paragraph_format.space_before = Pt(1)
            par.paragraph_format.line_spacing = 1.0
            if ci >= align_num_from:
                par.alignment = WD_ALIGN_PARAGRAPH.CENTER
            else:
                par.alignment = WD_ALIGN_PARAGRAPH.LEFT
            if ri < last:
                par.paragraph_format.keep_with_next = True
            add_inline(par, val, size=size, bold=ri == 0)
            top = 8 if ri == 0 else (4 if ri - 1 in rules else None)
            bottom = 4 if ri == 0 else (8 if ri == last else None)
            _borders(c, top=top, bottom=bottom)
            if ri == 0:
                _shade(c, "EDEDED")
    n = doc.add_paragraph()
    n.paragraph_format.space_before = Pt(3)
    n.paragraph_format.space_after = Pt(10)
    n.paragraph_format.line_spacing = 1.0
    if note:
        add_inline(n, note, size=8.5)


# =============================================================================== generated tables
JUDGES = [("llama", "Llama-3.2-3B"), ("qwen", "Qwen2.5-3B"), ("gemma", "Gemma-2-2B"), ("mistral", "Ministral-3-3B")]
EDITS = [("authority", "Authority"), ("citation", "Citation"), ("format", "Formatting"), ("confidence", "Confidence"),
         ("injection", "Evaluator instruction"), ("combo", "All five combined"), ("consensus", "Held-out consensus")]
CORR = ["S", "D", "N", "Det", "D+N", "J", "R", "R+S", "D+N+R", "D+N+R+S"]


def _v(e, bold_sig=False, abs_=False):
    if e is None:
        return "n/a"
    x = round(100 * e["est"], 1) + 0.0   # adding 0.0 turns a rounded -0.0 into 0.0
    s = _sign(f"{abs(x) if abs_ else x:.1f}")
    if bold_sig and (e["lo"] > 0 or e["hi"] < 0):
        s = f"**{s}**"
    return s


def _vci(e):
    return "n/a" if e is None else f"{_v(e)} {resolve('ci', 'x', _Holder(e))}"


class _Holder:
    """Lets resolve() format an interval that is already in hand."""
    def __init__(self, e):
        self.e = e

    def get(self, _):
        return self.e


def table_datasets(V):
    d = V.b["data_table"]
    ex = V.x["exclusions"]
    src = {"literature": ("PubMedQA, PQA-L (Jin et al., 2019)", "GitHub: pubmedqa/pubmedqa; MIT", "1,000 labeled questions; 890 yes/no after removing 110 maybe", "pubmedqa"),
           "clinical": ("MedQA-USMLE, 4 options (D. Jin et al., 2021)", "Hugging Face: GBaker/MedQA-USMLE-4-options; CC BY 4.0", "Test split, about 1,270 questions", "medqa"),
           "pharmacology": ("MedMCQA (Pal et al., 2022)", "Hugging Face: openlifescienceai/medmcqa; Apache-2.0", "Validation split, 4,183 questions; Pharmacology, single choice", "medmcqa_pharm")}
    rows = []
    for k in ("literature", "clinical", "pharmacology"):
        name, acc, sub, key = src[k]
        r = d[k]
        rows.append([name, acc, sub, str(r["n_options"]), str(r["drawn"]), str(ex["kept_by_source"][key]),
                     f"{ex['kept_by_source'][key] * 8}", f"{100 * r['hard']:.0f}", f"{r['words']:.0f}", f"{r['pad_ratio']:.2f}"])
    return dict(caption="Benchmarks and the derived rationale set the judges actually see.",
                header=["Benchmark", "Access; license", "Subset used", "Opts", "Drawn", "Kept", "Rationales", "Hard neg. (%)", "Mean words", "Pad ratio"],
                rows=rows, widths=[1.25, 1.4, 1.25, 0.32, 0.4, 0.34, 0.6, 0.45, 0.45, 0.4], align_num_from=3,
                note="Kept: all eight rationales valid. Hard neg.: share of drawn items whose distractor is the option the model "
                     "pool chose most often; the rest use a seeded random wrong option. Pad ratio: words after padding over words before.")


def table_models(V):
    t = V.tags
    rows = []
    vg = V.b["verification_gain"]
    for key, disp, tag in (("llama", "Llama-3.2-3B-Instruct (Meta; Grattafiori et al., 2024)", "llama3.2:3b"),
                           ("qwen", "Qwen2.5-3B-Instruct (Alibaba; Qwen Team, 2024)", "qwen2.5:3b"),
                           ("gemma", "Gemma-2-2B-it (Google; Gemma Team, 2024)", "gemma2:2b"),
                           ("mistral", "Ministral-3-3B-Instruct (Mistral AI, 2025)", "ministral-3:3b")):
        m = t[tag]
        rows.append([disp, "Author, judge", tag, f"{m['quantization'].replace('_', ' ')}, {m['parameter_size']}", m["digest"][:12],
                     f"{100 * vg[key]['solo']['est']:.1f}"])
    rows.append(["Phi-4-mini-instruct (Microsoft, 2025)", "Padding, normalizer", "phi4-mini", "Q4 K M, 3.8B",
                 V.b["provenance"]["utility_digest"].split("sha256:")[1][:12], f"{100 * V.b['solo_utility']['acc_kept']:.1f}"])
    return dict(caption="Models, roles, pinned builds, and each model's accuracy when answering the kept items alone.",
                header=["Model", "Role", "Ollama tag", "Quantization, params", "Digest (first 12)", "Solo acc. (%)"], rows=rows,
                widths=[2.3, 0.85, 0.85, 0.85, 0.85, 0.5], note="The utility model takes no part in the solo stage that picks each item's distractor; its solo accuracy was measured afterward.")


def table_baselines(V):
    pl, c = V.x["prefer_longer"], V.x["configs"]
    return dict(caption="Baselines and what each comparison shows, with measured clean accuracy.",
                header=["Baseline", "Definition", "Acc (%)", "What the comparison shows"],
                rows=[["Random chooser", "Picks either rationale with probability one half.", "50.0", "A floor. A judge near it provides little verification."],
                      ["Prefer-longer", "Always picks the longer rationale; uses no model.", f"{_vci(pl['acc_none'])}", "How far length alone predicts the key on clean pairs."],
                      ["Uncorrected single judge", "Each judge with the base prompt and raw rationales, one verdict per order.", f"{_vci(c['Base']['acc'])}", "The reference for every $Δ$Acc and $Δ$Rob."],
                      ["Uncorrected jury", "Majority vote of all four judges, with no recusal, swap, or normalization.", f"{_vci(c['J']['acc'])}", "The common practical choice; separates pooling from excluding authors' families."]],
                widths=[1.2, 2.3, 1.0, 2.2], align_num_from=2, note="Brackets: 95% item-level bootstrap interval. The random chooser has no sampling uncertainty.")


def table_bias(V):
    pj = V.b["per_judge"]
    rows = []
    for k, name in JUDGES:
        m = pj[k]
        rows.append([name, f"{_v(m['acc'])}", _sign(f"{m['kappa']['est']:.2f}"), _v(m["flip"]), _v(m["ppi"], True), _v(m["vb"], True),
                     _v(m["spb"], True), _v(m["tie_rate"]), f"{100 * V.b['parse_fail_by_judge'][name]:.1f}"])
    b = V.b["corrections"]["Base"]
    rows.append(["All four, pooled", _v(b["acc"]), _sign(f"{b['kappa']['est']:.2f}"), _v(b["flip"]), _v(b["ppi"], True), _v(b["vb"], True),
                 "n/a", _v(b["tie_rate"]), V.b["macros"]["ParseFailRate"]])
    return dict(caption="Bias profile of each uncorrected judge on the base prompt and raw rationales.",
                header=["Judge", "Acc (%)", "$κ$", "Flip (%)", "PPI (pp)", "VB (pp)", "SPB (pp)", "Tie (%)", "Unparsed (%)"],
                rows=rows, widths=[1.5, 0.6, 0.5, 0.6, 0.6, 0.6, 0.6, 0.55, 0.65], rules=(3,),
                note="Bold: the 95% cluster-bootstrap interval excludes zero. PPI above zero favors the first slot. SPB pools to no single meaning because its sign differs by judge. "
                     "Tie includes explicit ties and unparseable verdicts on clean units; Unparsed is over all verdicts of that judge.")


def table_regression(V):
    r = V.b["regression"]
    lab = {"WA": "Incorrect rationale in slot A (WA)", "SW": "Judge's family wrote R− (SW)", "SR": "Judge's family wrote R+ (SR)",
           "PW": "R− padded (PW)", "PR": "R+ padded (PR)", "SW:PW": "SW × PW", "WA:PW": "WA × PW", "WA:SW": "WA × SW"}
    rows = []
    for k, name in lab.items():
        e = r[k]
        p = "< 0.001" if e["p"] < 0.001 else f"{e['p']:.3f}"
        rows.append([name, _sign(f"{100 * e['coef']:.1f}"), _sign(f"[{100 * e['lo']:.1f}, {100 * e['hi']:.1f}]"), p])
    return dict(caption="Linear probability model of a correct verdict: bias block, base protocol, judge fixed effects, errors clustered by item.",
                header=["Term", "Coefficient (pp)", "95% CI", "p"], rows=rows, widths=[3.0, 1.1, 1.2, 0.7], rules=(4,),
                note="A negative interaction means the two manipulations together cost more accuracy than the sum of their separate costs.")


def table_corrections(V):
    c, g, eq, er = V.x["configs"], V.x["gains"], V.x["equivalence"], V.x["labels"]
    rows = [[er["Base"], _v(c["Base"]["acc"]), "", "", _v(c["Base"]["acc_strict"]), _v(c["Base"].get("flip")), _v(c["Base"]["tie"]),
             _v(c["Base"]["vb"]), _v(c["Base"]["G"]), ""]]
    for k in CORR:
        m, d = c[k], g.get(k, {})
        tost = eq.get(k, {}).get("p_tost")
        rows.append([er[k], _v(m["acc"]), _vci(d.get("dacc")), "n/a" if tost is None else ("< 0.001" if tost < 0.001 else f"{tost:.3f}"),
                     _v(m["acc_strict"]), _v(m.get("flip")), _v(m["tie"]), _v(m.get("vb"), True), _v(m.get("G")), _vci(d.get("drob"))])
    return dict(caption="Every correction scored on every metric, against the uncorrected single judge.",
                header=["Configuration", "Acc (%)", "$Δ$Acc (pp) [95% CI]", "TOST p", "Acc, ties = 0 (%)", "Flip (%)", "Tie (%)", "VB (pp)", "G (pp)", "$Δ$Rob (pp) [95% CI]"],
                rows=rows, widths=[1.3, 0.42, 0.95, 0.47, 0.5, 0.42, 0.4, 0.42, 0.42, 0.95], size=8, rules=(0, 5),
                note="Acc scores a tie one half; the \"Acc, ties = 0\" column scores it zero. TOST p: two one-sided tests of $Δ$Acc against ±5 pp, where a small value means the change is demonstrably "
                     "smaller than 5 pp. Flip is undefined once swap has aggregated the two orders. G: mean placebo-adjusted attack success over the five single edits. Bold VB: interval excludes zero.")


def table_gameability(V):
    c = V.x["configs"]
    rows = []
    for a, name in EDITS:
        b = c["Base"]
        rows.append([name, _v(b[f"asr_{a}"]), _vci(b.get(f"adj_{a}")), _v(b.get(f"rr_{a}")), _v(b.get(f"net_{a}")), _v(b.get(f"dacc_{a}"), True),
                     _v(b.get(f"symdacc_{a}"), True) if f"symdacc_{a}" in b else "n/a",
                     _v(c["D"].get(f"adj_{a}"), True), _v(c["N"].get(f"adj_{a}"), True), _v(c["Det"].get(f"adj_{a}"), True), _v(c["D+N"].get(f"adj_{a}"), True), _v(c["D+N+R+S"].get(f"adj_{a}"), True)])
    b = c["Base"]
    rows.append(["*Placebo floor (ASR)*", _v(b["asr_placebo"]), resolve("ci", "x", _Holder(b["asr_placebo"])), _v(b["rr_placebo"]), _v(b["net_placebo"]), _v(b["dacc_placebo"], True), "n/a",
                 _v(c["D"]["asr_placebo"]), _v(c["N"]["asr_placebo"]), _v(c["Det"].get("asr_placebo")), _v(c["D+N"]["asr_placebo"]), _v(c["D+N+R+S"]["asr_placebo"])])
    return dict(caption="Each content-free edit: raw and placebo-adjusted success, its mirror-image rates, and its adjusted success under corrections.",
                header=["Edit", "ASR", "Adjusted ASR [95% CI]", "RR", "Net", "$Δ$Acc", "$Δ$Acc on R+", "D", "N", "Det", "D+N", "D+N+R+S"],
                rows=rows, widths=[1.0, 0.4, 1.0, 0.38, 0.42, 0.42, 0.45, 0.4, 0.4, 0.4, 0.4, 0.55], size=8, rules=(4, 6),
                note="First seven columns: uncorrected judge. Last five: adjusted ASR under that correction, with the floor row showing that correction's own placebo ASR. All values in % or pp. "
                     "Bold: interval excludes zero. $Δ$Acc on R+: accuracy change when the same edit is placed on the correct rationale instead.")


def table_boundary(V):
    s = V.x["subset"]
    t = V.x["transfer"]
    name = {"literature": "PubMedQA", "clinical": "MedQA-USMLE", "pharmacology": "MedMCQA", "natural_error": "Natural-error subset"}
    def row(label, n, base, tr):
        rho = f"{tr['rho']:.2f} [{tr['lo']:.2f}, {tr['hi']:.2f}]".replace("-", MINUS)
        return [label, n, _v(base["acc"]), _v(base["asr_placebo"]), _v(base["adj_injection"]), _v(base["G"]), rho, f"{len(tr['both_positive'])} / {len(tr['trade_off'])}"]
    rows = [row("All items", str(V.b["macros"]["NItemsKept"]), {k: V.x["configs"]["Base"][k] for k in ("acc", "asr_placebo", "adj_injection", "G")}, t)]
    for k in ("literature", "clinical", "pharmacology", "natural_error"):
        rows.append(row(name[k], str(s[k]["n_items"]), s[k]["base"], s[k]["transfer"]))
    return dict(caption="Boundary conditions: the accuracy–robustness association inside each benchmark and on the natural-error subset.",
                header=["Slice", "Items", "Acc (%)", "Placebo ASR (%)", "Adj. instruction (pp)", "G (pp)", "Spearman $ρ$ [95% CI]", "Both gain / trade off"],
                rows=rows, widths=[1.45, 0.45, 0.55, 0.65, 0.8, 0.5, 1.3, 0.8], rules=(0,),
                note="Both gain: corrections with positive $Δ$Acc and $Δ$Rob. Trade off: one positive and one negative. Natural-error rows keep only pairs whose R− author chose that wrong answer unprompted, so an item can contribute some pairs and not others.")


def table_tradeoff(V):
    g, c = V.x["gains"], V.x["configs"]
    cost = {"S": ("2", "0"), "D": ("1", "0"), "N": ("1", "1 per candidate"), "Det": ("1", "0"), "D+N": ("1", "1 per candidate"), "J": ("4", "0"),
            "R": ("2", "0"), "R+S": ("4", "0"), "D+N+R": ("2", "1 per candidate"), "D+N+R+S": ("4", "1 per candidate")}
    rows = []
    for k in CORR:
        d = g.get(k)
        tie = 100 * (c[k]["tie"]["est"] - c["Base"]["tie"]["est"])
        rows.append([V.x["labels"][k], cost[k][0], cost[k][1], _v(d["dacc"]) if d else "n/a", _v(d["drob"]) if d else "n/a", _sign(f"{tie:+.1f}")])
    return dict(caption="What each correction costs and buys, per pair decision.",
                header=["Correction", "Verdicts", "LLM rewrites", "$Δ$Acc (pp)", "$Δ$Rob (pp)", "Added ties (pp)"],
                rows=rows, widths=[2.0, 0.7, 1.1, 0.8, 0.8, 0.9], note="Verdict and rewrite counts follow from the design. A recusal jury has exactly two eligible judges when both candidates come from different families.")


def table_deviations(V):
    x = V.x
    return dict(caption="Deviations from the Milestone 2 plan, and why each was made.",
                header=["Milestone 2 plan", "What was done", "Reason and consequence"],
                rows=[["150 items, 50 per benchmark, in two fixed batches of 75", f"One batch: 75 items, 25 per benchmark; {x['exclusions']['n_kept']} kept",
                       "The plan's reduced-scale fallback. Intervals are wider than planned, and each benchmark's rankings rest on about 25 items. The second batch is configured and not run (Section 8)."],
                      ["vLLM with bitsandbytes NF4 on a T4 in Google Colab", "Ollama (llama.cpp back end) with Q4 GGUF builds; RTX 3050 laptop and L40S server",
                       "A metered API run was unaffordable and local GPUs were available. Gemma-2 is Q4_0 and the others Q4_K_M, so precision is not identical across judges."],
                      ["Python 3.11", "Python 3.12.7 (Windows), 3.12.13 (Linux)", "The version installed at setup. Results reproduce across both (Section 5.4)."],
                      ["12-item development set used to tune prompts and the parser", "Not run before the main run; added to the code afterward",
                       "Prompts were fixed before judging. Parser and pipeline were checked on a simulator and an early verdict sample, which changed nothing. Evaluation items were therefore exposed to those checks, which the plan had meant to avoid."],
                      ["Replace excluded items if a benchmark falls too low", "Rule not implemented", "It never triggered: at most two items were lost from any benchmark."],
                      ["Commit tagged before the main run", "Not done; the repository was created after the main run",
                       "Model digests, configurations and seeds are recorded instead, and the stored verdicts regenerate every number. This proves reproducibility but not pre-registration."],
                      ["Thresholds fixed before the main run", "±5 pp smallest effect, and the RQ4 and RQ5 plan, set after verdicts existed",
                       "All of these analyses are reported as exploratory, not as confirmatory tests."],
                      ["Length-controlled correction (blueprint)", "Restored as a post-hoc statistical adjustment", "Needs no new verdicts, but it corrects a score, so it has no attack-success counterpart and stays outside RQ4."],
                      ["About 150,000 verdicts", f"{V.b['macros']['NPairwise'].replace('{,}', ',')} pairwise, {x['strip_n']:,} added for one control, {V.b['macros']['NSelect'].replace('{,}', ',')} selections", "Follows from running one batch."],
                      ["Six edits and a placebo", "Added a held-out cue, symmetric edits, and best-of-4 selection", "Additions, not substitutions. They separate persuasion from churn and test a second verifier role."]],
                widths=[2.0, 2.0, 2.7], align_num_from=9, size=8.5)


def table_components(V):
    return dict(caption="Implemented components.",
                header=["Module", "Responsibility", "Key design decision"],
                rows=[["biojudge/config.py", "Loads and validates one YAML file per run", "A run is fully specified by its configuration; authors must come from distinct families"],
                      ["biojudge/data.py", "Benchmark loaders, cleaning, de-duplication, splits", "Every item becomes a lettered single-best-answer question with a human key"],
                      ["biojudge/prompts.py", "Every prompt template", "One file, so nothing differs by accident between stages"],
                      ["biojudge/textutil.py", "Answer extraction, rationale validation, verdict parser", "Strict parser; anything unparseable scores one half and is reported"],
                      ["biojudge/perturb.py", "Edits, placebo, held-out cue, padding, strip-only normalizer", "Deterministic templates with no model and no optimization"],
                      ["biojudge/llm.py", "Asynchronous client, retries, SQLite cache", "The cache key is the full request and excludes the host, so work survives a change of machine"],
                      ["biojudge/pipeline.py", "Stages: solo, distractors, generate, perturb, judge, select", "Each stage reads the previous stage's JSONL and writes its own"],
                      ["biojudge/analysis.py", "Metrics, aggregation views, cluster bootstrap, regression", "One weight matrix for every estimate, so all differences are paired"],
                      ["biojudge/report.py", "Base tables, figures, metrics.json", "Regenerates everything from stored verdicts"],
                      ["biojudge/m3_analysis.py", "Baselines, G, RQ4, RQ5, length control, TOST", "Adds analyses without calling a model"],
                      ["biojudge/mock.py", "Simulator with planted biases", "Validates estimators against known effects; never a source of results"],
                      ["scripts/build_m3_docx.py", "This document", "Stops if any number cannot be resolved from the stored results"]],
                widths=[1.7, 2.5, 2.5], align_num_from=9, size=8.5)


TABLES = {"datasets": table_datasets, "models": table_models, "baselines": table_baselines, "bias": table_bias, "regression": table_regression,
          "corrections": table_corrections, "gameability": table_gameability, "boundary": table_boundary, "tradeoff": table_tradeoff,
          "deviations": table_deviations, "components": table_components}


# =============================================================================== document
def setup(doc):
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Inches(8.5), Inches(11)
    for side in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(sec, side, Inches(0.9))
    st = doc.styles["Normal"]
    st.font.name, st.font.size = FONT, Pt(11)
    st.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
    st.paragraph_format.space_after = Pt(7)
    st.paragraph_format.line_spacing = 1.12
    for name, size, before, after in (("Heading 1", 14, 14, 6), ("Heading 2", 12, 10, 4), ("Title", 18, 0, 8)):
        h = doc.styles[name]
        h.font.name, h.font.size, h.font.bold, h.font.italic = FONT, Pt(size), True, False
        h.font.color.rgb = RGBColor(0, 0, 0)
        rf = h.element.get_or_add_rPr().get_or_add_rFonts()
        for attr in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
            rf.set(qn(attr), FONT)
        for attr in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
            if rf.get(qn(attr)) is not None:
                del rf.attrib[qn(attr)]
        h.paragraph_format.space_before, h.paragraph_format.space_after = Pt(before), Pt(after)
        h.paragraph_format.keep_with_next = True
    bdr = doc.styles["Title"].element.find(qn("w:pPr")).find(qn("w:pBdr"))
    if bdr is not None:
        doc.styles["Title"].element.find(qn("w:pPr")).remove(bdr)
    c = doc.styles["Caption"]
    c.font.name, c.font.size, c.font.bold, c.font.italic = FONT, Pt(10), False, False
    c.font.color.rgb = RGBColor(0, 0, 0)
    c.paragraph_format.space_after = Pt(4)
    # page number field in the footer
    fp = sec.footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = fp.add_run()
    for kind, text in (("begin", None), (None, "PAGE"), ("end", None)):
        if kind:
            el = OxmlElement("w:fldChar")
            el.set(qn("w:fldCharType"), kind)
        else:
            el = OxmlElement("w:instrText")
            el.text = text
        r._r.append(el)
    return 8.5 - 1.8


def build(template: str, V: Values, out: str, figdir: str, title_props: dict) -> tuple[int, int]:
    errors: list[str] = []
    with open(template, encoding="utf-8") as f:
        lines = fill(f.read(), V, errors).split("\n")
    # tables contain no slots of their own, but they do read the JSON: a missing key must also stop the build
    built = {}
    for name, fn in TABLES.items():
        try:
            built[name] = fn(V)
        except (KeyError, TypeError) as e:
            errors.append(f"table {name}: {e!r}")
    if errors:
        print("Unresolved slots; nothing written:\n  " + "\n  ".join(errors))
        sys.exit(1)

    doc = docx.Document()
    width = setup(doc)
    counters = {"table": 0, "fig": 0, "eq": 0}
    numbering_bullet = doc.styles["List Bullet"]
    numbering_bullet.font.name = FONT
    words_body = 0
    in_refs = False
    for raw in lines:
        s = raw.strip()
        if not s or s.startswith("%%"):
            continue
        if s.startswith("TITLE: "):
            p = doc.add_paragraph(style="Title")
            p.add_run(s[7:])
        elif s.startswith("# "):
            doc.add_heading(s[2:], level=1)
            in_refs = s.lower().startswith("# references")
        elif s.startswith("## "):
            doc.add_heading(s[3:], level=2)
        elif s.startswith("\\eq{"):
            counters["eq"] += 1
            add_equation(doc, s[4:-1], counters["eq"], width)
        elif s.startswith("{{TABLE:"):
            add_table(doc, counters, **built[s[8:-2]])
        elif s.startswith("{{FIG:"):
            name, cap, w = s[6:-2].split("|")
            counters["fig"] += 1
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.keep_with_next = True
            p.paragraph_format.space_after = Pt(3)
            p.add_run().add_picture(os.path.join(figdir, name), width=Inches(float(w)))
            c = doc.add_paragraph(style="Caption")
            c.paragraph_format.space_after = Pt(10)
            add_inline(c, f"**Figure {counters['fig']}.** {cap}")
        elif s.startswith("REF: "):
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Inches(0.3)
            p.paragraph_format.first_line_indent = Inches(-0.3)
            p.paragraph_format.space_after = Pt(4)
            add_inline(p, s[5:], size=10)
        elif s.startswith("> "):
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Inches(0.35)
            p.paragraph_format.right_indent = Inches(0.35)
            add_inline(p, s[2:], size=10)
            words_body += len(s.split())
        elif s.startswith("- "):
            p = doc.add_paragraph(style="List Bullet")
            add_inline(p, s[2:])
            words_body += len(s.split())
        elif s.startswith("META: "):
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(2)
            add_inline(p, s[6:])
        else:
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            add_inline(p, s)
            if not in_refs:
                words_body += len(s.split())
    for k, v in title_props.items():
        setattr(doc.core_properties, k, v)
    doc.save(out)
    return words_body, counters["table"]


def make_architecture_png(figdir: str) -> None:
    """Render the framework figure for Word, relabeling its research-question range to the current five."""
    import pymupdf
    page = pymupdf.open(os.path.join(figdir, "fig_architecture.pdf"))[0]
    for rect in page.search_for("RQ1\u2013RQ4"):
        page.draw_rect(rect, color=(1, 1, 1), fill=(1, 1, 1))
        page.insert_text((rect.x0, rect.y1 - 1.5), "RQ1-RQ5", fontsize=rect.height * 0.8, fontname="hebo")
    page.get_pixmap(dpi=300).save(os.path.join(figdir, "m3_architecture.png"))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run", default=os.path.join(ROOT, "runs", "local"))
    ap.add_argument("--template", default=os.path.join(ROOT, "paper", "m3_paper_template.md"))
    ap.add_argument("--figs", default=os.path.join(ROOT, "paper", "figs"))
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    V = Values(a.run)
    # how many verdicts the added control contributed, for the deviations table
    with open(os.path.join(a.run, "strip_placebo.jsonl")) as f:
        V.x["strip_n"] = sum(1 for line in f if line.strip())
    with open(os.path.join(a.run, "strip_placebo_meta.json")) as f:
        V.x["strip_meta"] = json.load(f)
    # quantities derived from the stored results, named so that the template can use them as slots
    phases = V.b["phases"]
    sec = {k.split("/")[0]: v["seconds"] for k, v in phases.items() if "perturb" not in k}
    V.x["phase_pad"] = phases["local/run_meta_perturb.json"]["seconds"]
    V.x["phase_judge"] = sec["backup_20261014"]
    V.x["phase_ctrl"] = sec["local"]
    V.x["gpu_seconds"] = V.x["phase_pad"] + V.x["phase_judge"] + V.x["phase_ctrl"]
    V.x["n_pairwise_total"] = int(V.b["macros"]["NPairwise"].replace("{,}", "")) + V.x["strip_n"]
    V.x["n_rationales_kept"] = V.x["exclusions"]["n_kept"] * 8
    with open(os.path.join(a.run, "variants.jsonl")) as f:
        V.x["n_variants"] = sum(1 for line in f if line.strip())
    V.x["lc_doubling"] = V.x["length_controlled"]["base_raw"]["beta"]["est"] * 0.6931
    make_architecture_png(a.figs)
    words, tables = build(a.template, V, a.out, a.figs,
                          {"title": "Can LLM Verifiers Be Gamed? Accuracy, Corrections, and Content-Free Attacks in Biomedical Multi-Agent Pipelines",
                           "author": "Zhenni Liang; Umme Israt Afroz", "subject": "DTSC 5525 Milestone 3"})
    print(f"[m3-docx] {words:,} body words (no tables, figures, equations or references); {tables} tables; wrote {a.out}")


if __name__ == "__main__":
    main()
