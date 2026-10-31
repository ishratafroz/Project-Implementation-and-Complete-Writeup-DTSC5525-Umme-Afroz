"""Regenerate every number, table and figure of the Milestone 3 paper from the stored verdicts.

No model is called and no GPU is needed. Run from the project folder, with the environment active:

  python scripts/reproduce_m3.py            # analysis, figures and the Word document (about 4 minutes)
  python scripts/reproduce_m3.py --tests    # the same, after running the offline test suite (about 2 minutes more)
"""
import argparse
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RUN, CONFIG = os.path.join("runs", "local"), os.path.join("configs", "ollama_l40s_ctrl.yaml")
OUT = "Project-Implementation and Complete Writeup-DTSC5525-Umme Afroz.docx"


def step(*args: str) -> None:
    """Run one module or script with this interpreter, stopping the whole sequence if it fails."""
    print("\n>>>", " ".join(args), flush=True)
    subprocess.run([sys.executable, *args], cwd=ROOT, check=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tests", action="store_true", help="run the offline test suite first")
    ap.add_argument("--out", default=OUT, help="where to write the Word document")
    a = ap.parse_args()
    if a.tests:
        step("-m", "pytest", "tests", "-q")
    step("-m", "biojudge.report", "--run", RUN, "--config", CONFIG, "--paper", "paper")   # base metrics, tables
    step("-m", "biojudge.m3_analysis", "--run", RUN, "--config", CONFIG, "--paper", "paper")  # RQ4, RQ5, baselines
    step(os.path.join("scripts", "build_m3_docx.py"), "--out", a.out)


if __name__ == "__main__":
    main()
