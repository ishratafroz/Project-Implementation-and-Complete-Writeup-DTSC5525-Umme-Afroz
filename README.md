# Can LLM Verifiers Be Gamed?

Code, data and stored results for *Can LLM Verifiers Be Gamed? Accuracy, Corrections, and Content-Free Attacks in Biomedical Multi-Agent Pipelines.

The project scores small open-weight language models acting as verifiers against expert answer keys
(PubMedQA, MedQA-USMLE, MedMCQA) under position, length, authorship and content-free manipulations, and
asks whether corrections that raise accuracy also make a verifier harder to manipulate.

## 1. Environment setup

| | |
|---|---|
| Operating system | Windows 11  |
| Python | 3.12 (results produced on 3.12.13 and re-verified on 3.12.7) |
| Libraries | exact versions pinned in `requirements.txt` |
| IDE | none required; VS Code is what we used |
| GPU | none for analysis; see section 5 for new model runs |

With [uv](https://docs.astral.sh/uv/) (recommended):

```bash
uv venv --python 3.12 .venv
# Windows:      .venv\Scripts\activate
# Linux/macOS:  source .venv/bin/activate
uv pip install -r requirements.txt
```

With plain pip: create a Python 3.12 virtual environment, activate it, and run `pip install -r requirements.txt`.

## 2. Quick start: regenerate everything (no GPU, about 4 minutes)

```bash
python scripts/reproduce_m3.py          # add --tests to run the offline test suite first (about 2 minutes)
```

This runs three steps, each of which can also be run alone:

```bash
python -m biojudge.report      --run runs/local --config configs/ollama_l40s_ctrl.yaml --paper paper   # base metrics, tables, figures
python -m biojudge.m3_analysis --run runs/local --config configs/ollama_l40s_ctrl.yaml --paper paper   # baselines, G, RQ4, RQ5, length control, TOST
python scripts/build_m3_docx.py --out "Project-Implementation and Complete Writeup-DTSC5525-Umme Afroz.docx"
```

Outputs appear in `runs/local/results/` (`metrics.json`, `m3_metrics.json`, CSV files) and `paper/figs/`.
`build_m3_docx.py` fills the paper from those files and stops without writing if any number cannot be resolved.

To see the whole pipeline run end to end with no GPU, use the simulator (about 1 minute). Its numbers are
**never** results; it exists to confirm that the estimators recover biases of known size:

```bash
python -m biojudge.run --config configs/mock.yaml --stages items,solo,generate,perturb,judge,select
python -m biojudge.report --run runs/mock --config configs/mock.yaml --paper runs/mock/paper
python -m biojudge.m3_analysis --run runs/mock --config configs/mock.yaml --paper runs/mock/paper
```

## 3. Project structure

```
biojudge/                 the package
  config.py               YAML configuration and validation
  data.py                 benchmark loaders, cleaning, de-duplication, development split, batches
  prompts.py              every prompt template
  textutil.py             answer extraction, rationale validation, verdict parser
  perturb.py              content-free edits, placebo, held-out cue, padding, deterministic normalizer
  llm.py                  asynchronous client with SQLite cache and retries
  pipeline.py             stages: solo -> distractors -> generate -> perturb -> judge -> select
  analysis.py             metrics, aggregation views, cluster bootstrap, regression
  report.py               base tables, figures and metrics.json
  m3_analysis.py          baselines, gameability, RQ4, RQ5, length-controlled correction, equivalence tests
  mock.py                 simulator with planted biases (validation only)
  run.py                  command-line entry point
configs/
  ollama_l40s_ctrl.yaml   the configuration of record for the stored run (75 items)
  ollama_laptop_strip_placebo.yaml   the added control: placebo under deterministic normalization
  m2_full_design.yaml     the full Milestone 2 design (150 items, dev set, two batches); not yet run
  mock.yaml               offline simulator
data_cache/ori_pqal.json  PubMedQA labeled subset (included; MIT license)
runs/local/               stored items, rationales, text variants, verdicts, selections and the call cache
paper/                    Word paper template, figures, tables
scripts/                  reproduce_m3.py, build_m3_docx.py, run_strip_placebo.py, redecode.py,
                          audit_parse_failures.py, solo_utility.py, and helpers for the earlier LaTeX draft
tests/test_pipeline.py    offline tests, including an end-to-end simulator run
```

Files in `runs/local/`: `items.jsonl` (75 sampled items), `solo.jsonl` (each model's own answers),
`responses.jsonl` (600 rationales), `variants.jsonl` (14,892 text variants), `trials.jsonl` (85,264 pairwise
verdicts), `select.jsonl` (7,008 selections), `strip_placebo.jsonl` (1,168 added verdicts), `host_check.jsonl`
(1,168 re-judged verdicts, used only to compare hosts), `retest.jsonl` (repeat decodes), `model_tags.json`
(pinned digests), `cache.sqlite` (every call).

## 4. Data preparation

No step is needed to regenerate results: the sampled items are stored in `runs/local/items.jsonl`.

To draw items afresh, the loaders fetch the data on first use:

| Benchmark | Source | License | How it is obtained |
|---|---|---|---|
| PubMedQA, PQA-L | `github.com/pubmedqa/pubmedqa`, `data/ori_pqal.json` | MIT | included as `data_cache/ori_pqal.json`; downloaded if missing |
| MedQA-USMLE, 4 options | Hugging Face `GBaker/MedQA-USMLE-4-options`, test split | CC BY 4.0 | `datasets` library, on first use |
| MedMCQA | Hugging Face `openlifescienceai/medmcqa`, validation split, Pharmacology | Apache-2.0 | `datasets` library, on first use |

Each item is converted to a lettered single-best-answer question in `biojudge/data.py`. `data.preprocess: true`
(in `m2_full_design.yaml`) adds Unicode and whitespace cleaning, near-duplicate removal, and a disjoint
development split. The stored run predates that option and does not use it.

There is no training step: no model is trained or fine-tuned.

## 5. Running models again (optional; needs a GPU)

1. Install [Ollama](https://ollama.com) and pull the models. Digests are in `runs/local/model_tags.json`:

   ```bash
   ollama pull llama3.2:3b && ollama pull qwen2.5:3b && ollama pull gemma2:2b
   ollama pull ministral-3:3b && ollama pull phi4-mini
   ```

2. Set `base_url` in the configuration to your server. The cache key excludes the host, so calls already in
   `cache.sqlite` are not repeated. The stored run needs only its missing calls.

   ```bash
   export OLLAMA_API_KEY=EMPTY    # Windows PowerShell: $env:OLLAMA_API_KEY = "EMPTY"
   python -m biojudge.run --config configs/ollama_l40s_ctrl.yaml --estimate
   python -m biojudge.run --config configs/ollama_l40s_ctrl.yaml --stages solo,generate,perturb,judge,select
   ```

3. The added control: `python scripts/run_strip_placebo.py --config configs/ollama_laptop_strip_placebo.yaml`.
   `--host-check` re-judges the base-protocol placebo for comparison between machines.

4. The full design has not been run on real models. Use `--split dev` for the pilot, then `--batch 1` and
   `--batch 2`; the commands are at the top of `configs/m2_full_design.yaml`.

Every call is cached, so re-running a stopped command loses nothing. Greedy decoding is not bit-reproducible on
this stack, so uncached calls will differ slightly even with the same seed. Reproducibility of the reported
numbers comes from the stored verdicts.

### Approximate runtimes

| Task | Hardware | Time |
|---|---|---|
| Regenerate all analysis and the paper | any CPU | about 4 minutes |
| Offline tests (23) | any CPU | about 2 minutes |
| Padding and normalization, 75 items | RTX 3050, 6 GB | about 2.4 hours |
| Main judging and selection (about 61,500 calls) | 3 x NVIDIA L40S | about 1.7 hours (10 calls per second) |
| Controls (about 30,800 calls) | 3 x NVIDIA L40S | about 1 hour |
| Added placebo, and the host check (1,168 calls each) | RTX 3050, 6 GB | about 20 minutes each (1 call per second) |
| Full 150-item design (about 207,600 calls) | 3 x NVIDIA L40S | about 6 hours; a 6 GB laptop would take days |

## 6. Reproducibility

- Seed 2026 fixes item sampling, tie-breaking, the fallback distractor rule, the authorship cycle and the bootstrap.
- Each configuration file specifies a run completely.
- Re-running the analysis from stored verdicts on a different operating system reproduced all 8,061 stored numeric values to within 1e-9.

## 7. Older material

`paper/biojudge_stress_template.tex`, `scripts/fill_paper.py` and related scripts build an earlier IEEE LaTeX
version of this work, organized around different research questions. They are not needed for Milestone 3.
`configs/openrouter.yaml`, `pilot.yaml`, `vllm_local.yaml`, `ollama_local*.yaml`, and `scripts/run_local.sh` record
earlier hosting options and were not used for the configuration of record.
