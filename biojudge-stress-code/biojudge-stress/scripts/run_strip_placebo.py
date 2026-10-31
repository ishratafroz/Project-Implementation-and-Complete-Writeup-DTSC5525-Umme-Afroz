"""Collect the one verdict set the main run did not: the placebo edit under deterministic normalization.

The placebo floor was judged under the four main protocols only, so the strip-only correction had no
floor of its own and its placebo-adjusted gameability could not be computed. This script judges
(placebo on R-, base prompt, strip-only text) for every kept item, attack pair and order, and nothing else.

It writes to its own files, runs/<run>/strip_placebo.jsonl and strip_placebo_cache.sqlite, so that the
main run's trials.jsonl and cache.sqlite stay byte-identical. biojudge.m3_analysis merges the rows.

  bash /d/ollama_models/serve.sh 4        # any Ollama server holding the five models
  python scripts/run_strip_placebo.py --config configs/ollama_laptop_strip_placebo.yaml
"""
from __future__ import annotations

import argparse
import asyncio
import copy
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from biojudge.config import load_config, run_dir  # noqa: E402
from biojudge.data import load_items  # noqa: E402
from biojudge.llm import LLMClient  # noqa: E402
from biojudge.pipeline import read_jsonl, run_pairwise, valid_item_ids, write_jsonl  # noqa: E402


async def main_async(cfg: dict, protocol: str, tag: str) -> None:
    """Judge the placebo under one protocol. `tag` names the output files: with --host-check the same
    base_raw prompts the main run judged on the L40S host are judged again here, which measures how far
    verdicts move between hosts, so the floor collected on this host can be read with that in mind."""
    rd = run_dir(cfg)
    items = load_items(os.path.join(rd, "items.jsonl"))
    resp = read_jsonl(os.path.join(rd, "responses.jsonl"))
    variants = {r.pop("key"): r for r in read_jsonl(os.path.join(rd, "variants.jsonl"))}
    keep = valid_item_ids(cfg, resp)

    # Narrow the design to one protocol and one edit. Everything else about a call (prompt template,
    # max_tokens, temperature, parser, scoring) is the code path the main run used.
    c = copy.deepcopy(cfg)
    c["experiment"].update(protocols=[protocol], control_protocols=[protocol],
                           attacks=[], attacks_control=["placebo"], attacks_sym=[])
    client = LLMClient(c, os.path.join(rd, f"{tag}_cache.sqlite"))
    t0 = time.time()
    rows = await run_pairwise(c, client, items, variants, keep,
                              spec_filter=lambda s: s["block"] == "attack" and s["attack"] == "placebo")
    client.close()
    write_jsonl(rows, os.path.join(rd, f"{tag}.jsonl"))
    secs = time.time() - t0
    with open(os.path.join(rd, f"{tag}_meta.json"), "w") as f:
        json.dump({"seconds": secs, "n": len(rows), "llm_stats": dict(client.stats),
                   "provenance": c.get("provenance")}, f, indent=2, default=str)
    fails = sum(r["parse_fail"] for r in rows)
    print(f"[{tag}] {len(rows)} verdicts, {fails} parse failures, {secs:.0f}s")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--host-check", action="store_true",
                    help="re-judge the base_raw placebo, already judged on the main host, on this host")
    a = ap.parse_args()
    protocol, tag = ("base_raw", "host_check") if a.host_check else ("base_strip", "strip_placebo")
    asyncio.run(main_async(load_config(a.config), protocol, tag))


if __name__ == "__main__":
    main()
