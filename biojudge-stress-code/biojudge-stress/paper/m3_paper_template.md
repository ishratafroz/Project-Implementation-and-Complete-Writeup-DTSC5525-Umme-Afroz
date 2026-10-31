%% Milestone 3 paper. Every result is a named slot filled from the stored metrics by scripts/build_m3_docx.py.
TITLE: Can LLM Verifiers Be Gamed? Accuracy, Corrections, and Content-Free Attacks in Biomedical Multi-Agent Pipelines

META: **Project Title:** Can LLM Verifiers Be Gamed? Accuracy, Corrections, and Content-Free Attacks in Biomedical Multi-Agent Pipelines
META: **Project Category:** Benchmarking / Evaluation
META: **Student Names:** Zhenni Liang, Umme Israt Afroz
META: **Student Emails:** ZhenniLiang@my.unt.edu, UmmeAfroz@my.unt.edu
META: **Course:** DTSC 5525
META: **Milestone:** Milestone 3 – Implementation & Complete Writeup

# Abstract

Language models increasingly decide which candidate answer a multi-agent pipeline accepts, yet corrections for known judge biases are usually evaluated on accuracy alone. Whether a verifier that becomes more accurate also becomes harder to manipulate has not been tested directly. Here we test it in biomedical verification, where every verdict can be scored against an expert answer key. Four small open-weight model families wrote and then judged paired rationales for @@M:NItemsKept@@ expert-keyed items from PubMedQA, MedQA-USMLE, and MedMCQA, producing @@n:x.n_pairwise_total@@ pairwise verdicts across position, length, authorship, content-free edits, and corrections. Gameability was measured as attack success above a length-matched placebo, so that the instability of weak judges was not mistaken for persuasion. The judges barely verify: they agree with the key @@v:c.Base.acc@@% of the time, and every model is a worse checker than answerer. A placebo overturns @@v:c.Base.asr_placebo@@% of correct verdicts, and against that floor only an instruction addressed to the evaluator persuades strongly (@@v:c.Base.adj_injection@@ percentage points). Across ten corrections, accuracy gain and robustness gain are only weakly and inconclusively associated (Spearman ρ = @@r:x.transfer.rho@@, 95% CI [@@r:x.transfer.lo@@, @@r:x.transfer.hi@@]). LLM normalization improves both, deleting cue text with a regular expression improves robustness alone, recusal improves accuracy alone, and the debiasing prompt improves neither reliably. The association is not stable within benchmarks or on natural errors. Accuracy is therefore not evidence of robustness: each must be measured, against expert keys and a placebo floor, before a small verifier is trusted as a safety layer.

# 1. Introduction

## 1.1 Problem and motivation

A biomedical answer from an agentic system has usually passed through several language-model calls before anyone reads it. Clinical reasoning frameworks assemble panels of specialist agents (Kim et al., 2024; Tang et al., 2024), simulated clinical environments and discovery agents plan, call tools, and criticize their own steps (Gao et al., 2024; Schmidgall et al., 2024), and the outputs are often scored by model juries or rubric-based graders (Arora et al., 2025; Bedi et al., 2025). Verifiers that rank sampled solutions were shown early to improve reasoning (Cobbe et al., 2021). In these systems one agent decides which candidate is accepted. We call this agent a verifier, and it acts as a guardrail: whatever it accepts flows downstream.

The reliability of that decision is uncertain, particularly in medicine. A recent scoping analysis of 134 healthcare studies reports that language-model judges often agree moderately to strongly with experts but vary substantially across tasks, rubrics, and models (L. Li et al., 2026). Judges agree less with experts than with lay raters in specialized domains (Szymanski et al., 2025), and same-provider judges change the apparent safety of medical models (Afrasyab, 2026). Credibility is also cheap to imitate. Prompt injection already works against medical language models (Clusmann et al., 2025), and indirect injection threatens any evaluator that reads text produced by other agents or tools (Greshake et al., 2023). A verifier that reads credentials, journal-style citations, or a claim of prior review as evidence becomes the easiest component of the pipeline to attack.

## 1.2 Context and significance

Two literatures address this problem from different sides. Mitigation studies ask whether a fix reduces a bias or raises agreement with a reference (L. Zheng et al., 2023; Soumik, 2026). Attack studies ask whether a judge can be fooled (Raina et al., 2024; X. Zheng et al., 2025; Yang et al., 2026). In our review we did not find a study that asks, correction by correction, whether the accuracy a correction buys comes with a matching gain in robustness. Two features of the evidence also limit what it says about verification. The reference signal is often a human preference rather than a correct answer, so a bias may only mean departing from what raters like. And attack success is rarely compared with the effect of a neutral change, although a weak judge may change its verdict under almost any change to its input, so a raw attack rate can overstate persuasion.

Biomedicine is a useful place to close this gap because it offers both an objective anchor and a realistic threat. Answers can be checked against expert keys, and an upstream agent can control how a candidate is presented without controlling its medical content. If corrections that raise accuracy also harden the verifier, practitioners can select on accuracy alone. If they do not, accuracy-based validation gives false assurance about a safety component.

## 1.3 Research questions

We address five questions, unchanged from the project's data model.

- **RQ1, bias profile.** With expert answer keys as the gold standard, how large are the effects of answer order, padding, and same-family authorship on judge accuracy, and do padding and same-family authorship interact beyond their individual effects?
- **RQ2, corrections and accuracy.** Which corrections improve gold-anchored accuracy by a practically meaningful margin, and how do they affect order stability, padding sensitivity, same-family favoritism, and tie rate?
- **RQ3, persuasion versus instability.** After adjusting for a length-matched placebo edit, how much does each content-free edit increase the rate at which initially correct verdicts are overturned, for uncorrected and corrected judges?
- **RQ4, accuracy–robustness transfer.** Among the corrections tested, do those that improve accuracy also reduce adjusted gameability, and how strong is the association between accuracy gain and robustness gain?
- **RQ5, boundary conditions.** Does the RQ4 relationship hold within each benchmark and on a natural-error subset, where the incorrect rationale defends a model's own error rather than an assigned one?

Our central hypothesis is that higher accuracy alone does not protect a judge from manipulation.

## 1.4 How the project changed from its blueprint

The project drifted from its original blueprint in ways that sharpened the question, so we state the changes here. The blueprint used general benchmarks (MT-Bench, JudgeBench, and MMLU-Pro) and larger judges (Qwen3-8B, Phi-4, and Granite-3.3-8B) to answer three research questions with a development set of 100 pairs. We moved to three biomedical benchmarks because they provide an objective key and a threat model in which cheap credibility cues are plausible. We moved to four judges of 2–3B parameters because crossing authorship with correctness requires every family both to write and to judge, and because the resulting verdict count exceeded what we could run at larger sizes. Questions were split into five so that the headline comparison (RQ4) and its boundary conditions (RQ5) are stated separately. The core question, whether accuracy-improving corrections also reduce gameability, is intact.

## 1.5 Contributions

This paper makes four contributions. First, a gold-anchored design that crosses position, length, and authorship against an objective biomedical key. Second, a placebo-adjusted measure of gameability, with symmetric edits and a repair rate that separate persuasion from verdict churn. Third, the first direct comparison, to our knowledge, of each correction's accuracy gain with its robustness gain, with ten corrections each scored on every metric. Fourth, a cached, reproducible implementation, in which every number in this paper regenerates from stored verdicts without a model call.

The main result supports the hypothesis. Accuracy gain predicts robustness gain only weakly across corrections, and the two can be separated experimentally: deleting cue text delivers the largest robustness gain with no accuracy gain, and recusal delivers an accuracy gain with no robustness gain. The study is too small to rule out a modest general association.

# 2. Related Work

**Biases of language-model judges.** Research agrees that judges respond to features unrelated to correctness. MT-Bench and Chatbot Arena established pairwise judging as a proxy for human preference and reported position and verbosity effects alongside self-enhancement (L. Zheng et al., 2023). Position bias has since been mapped across judges and tasks (Wang et al., 2024), a preference for longer answers has been documented in preference labeling (Saito et al., 2023), and self-preference has been shown and linked to self-recognition and text familiarity (Panickssery et al., 2024; Wataoka et al., 2024). Broader catalogues add stylistic and presentation biases (Chen et al., 2024; Ye et al., 2025), and benchmarks now inject biases deliberately (Zhou et al., 2026). This body of work mostly measures biases one at a time against human preference. We adopt the same three biases in RQ1 but score them against an expert key and cross them, so an interaction can be estimated.

**Corrections, and the closest comparisons.** The most common correction judges both orders and aggregates (L. Zheng et al., 2023). Others calibrate the judge's output distribution (H. Li et al., 2025; Wang et al., 2024), control for length statistically (Dubois et al., 2024), add debiasing instructions, pool judges from different families (Verga et al., 2024), or strip style before judging, as Yang et al. (2026) propose after showing that style attacks evade standard controls. The nearest work to ours compares corrections directly. Soumik (2026) evaluates nine debiasing strategies across five judges, three benchmarks, and four bias types and finds that effectiveness depends on the model. We differ in three ways: our reference is an expert key, our outcome includes manipulation as well as bias, and we test whether gains in one outcome predict gains in the other. H. Li et al. (2025) treat selection bias in pairwise judging as an optimization problem and report reduced bias with improved performance, and Q. Li et al. (2025) study bias in scoring-based judges, where the rubric and the score identifiers create biases of their own. Both evaluate a correction on the bias it targets. We score every correction on every metric, because a correction's side effects are invisible otherwise.

**Gameability of judges.** A second line of work treats the judge as a target. A constant response that ignores the question can achieve high win rates on automatic benchmarks (X. Zheng et al., 2025), universal adversarial phrases can move zero-shot scores (Raina et al., 2024), optimized prompt injections can steer judges (Shi et al., 2024), and a bandit search over meaning-preserving style edits inflates scores with success above 65% (Yang et al., 2026). These studies show what a capable adversary can do. Our threat model is weaker and cheaper: fixed, content-free edits with no optimization and no access to the judge. This estimates what a low-effort upstream agent gets for free. Our main addition is to subtract a length-matched placebo, so that the instability of a weak judge is not reported as persuasion.

**Judges in biomedicine.** The evidence on biomedical judges is mixed. MedHELM scores medical tasks with a jury validated against clinicians (Bedi et al., 2025), and HealthBench grades against physician-written rubrics (Arora et al., 2025). In contrast, reviewers list position, length, and related-model preference among the failure modes of healthcare judges (L. Li et al., 2026), and same-provider judges are more lenient toward their own provider's models (Afrasyab, 2026). MedFabric shows that detectors depend on gold evidence and fall below chance when given wrong evidence (Kwok et al., 2026). Closest to our setting, de Oliveira et al. (2026) evaluate biomedical judges on agreement with metric-derived gold labels, stability across repeated runs, and format adherence. They share our concern for validity, and we add the expert key, attacks, placebo control, and corrections.

**Biomedical benchmarks as anchors.** PubMedQA offers expert-annotated yes/no/maybe questions answerable from PubMed abstracts (Jin et al., 2019). MedQA collects questions from medical licensing examinations (D. Jin et al., 2021), and MedMCQA collects multi-subject questions from medical entrance examinations, including pharmacology (Pal et al., 2022). We use them as sources of objective keys rather than as targets for model evaluation.

**Positioning.** To our knowledge, no study combines three elements: crossing order, padding, and same-family authorship against an objective biomedical key; scoring content-free attacks net of a placebo; and comparing each correction's accuracy gain with its robustness gain. The closest neighbors each hold one or two of these elements. The project fills that intersection.

# 3. Methodology and System Design

## 3.1 Roles and threat model

We use "judge" for the language model itself and "verifier" for the role it plays when it decides which candidate a pipeline accepts. An evaluation is *gold-anchored* because every verdict is scored against an expert answer key rather than a preference label. The adversary is whatever upstream agent, tool, or data source controls the surface form of one candidate but not its medical content. It may add text, markup, credentials, or references through fixed templates, but it cannot change which option the candidate defends. Figure 1 shows the framework.

{{FIG:m3_architecture.png|The framework. (a) An expert-keyed item feeds candidate construction (green), the stress manipulations (blue), and the corrections (yellow); all three meet at the verifier under test, whose verdicts are scored against the key. (b) The corrected pipeline D+N+R+S, with dashed boxes marking what changes. (c) Best-of-4 selection, a secondary test in which three candidates defend the same distractor and one is decorated.|6.6}}

## 3.2 Candidate construction

Each judge first answers every item alone, in at most 60 words, ending on a letter. The wrong option the four models pick most often becomes that item's hard-negative distractor, so that errors are plausible; a seeded rule breaks ties and handles items on which no model erred. Each family then writes one rationale for the keyed answer (R+) and one for the distractor (R−) from the same prompt, giving eight candidate rationales per item.

Because all four families write and all four judge, authorship is crossed with correctness by construction. The four authors are permuted into a cycle for each item, and consecutive authors supply the (R+, R−) pair. Every judge therefore meets one pair in which its own family wrote R+ (self-right), one in which its family wrote R− (self-wrong), and two neutral pairs on each item.

## 3.3 Manipulations

**Position.** Every pair is judged in both orders. **Length.** A utility model outside the judge pool expands a rationale to about 2.5 times its length by restating the question and adding general background, with no fact bearing on which option is right. Each pair is judged unpadded, with R− padded, and with R+ padded. Keeping this model outside the pool prevents padded text from carrying a judge's own style.

**Content-free edits.** Six deterministic edits go on R− in the first two pairs of each item, in both orders, and change only its surface form:

- **Authority:** an unsupported professional credential (board certification, twenty years of practice).
- **Citation:** two well-formed but invented journal references and a mention of the latest guideline.
- **Formatting:** markdown headings, one bullet per sentence, and a bold final answer.
- **Confidence:** a statement that the point is well established and the evidence definitive.
- **Evaluator instruction:** a bracketed note telling the evaluator that the response was verified and should be selected.
- **All five combined.**

## 3.4 Controls for instability

A near-chance judge changes its mind easily, so a verdict that changes after an edit is not by itself evidence of persuasion. Three controls separate the two. The **placebo** adds two neutral sentences of matched length carrying no cue at all, and its success rate is the floor every edit is read against. **Symmetric edits** place each single edit on R+ instead of R−: a cue that persuades should help whichever side carries it, while one that merely perturbs should not. A **held-out edit** claims that most consulted specialists agree. The normalizer's prompt never names such a cue, so it asks whether the defense generalizes beyond the cues it was written for. We also report the mirror image of attack success, the **repair rate**: the share of verdicts wrong on the clean pair that come out right under the same edit.

## 3.5 Corrections and baselines

Corrections act at three levels, and each is scored on every metric, so that side effects remain visible.

- **Prompt level.** A debiasing prompt (D) tells the judge to decide on correctness alone, to ignore order, length, formatting, tone, and stated confidence, and to treat credentials, references, and instructions inside a response as unverified.
- **Input level.** LLM normalization (N) rewrites every candidate into at most 80 words of plain prose that keep the final answer and main reasoning steps. Rewrites that fail validation fall back to strip-and-truncate. Deterministic normalization (Det) is the ablation of N: a regular expression deletes markup, bracketed text, and anything after the final-answer line, with no rewriting and no removal of credentials, citations, or confident wording. The difference between N and Det is what the rewrite itself buys.
- **Aggregation level.** Swap aggregation (S) counts a preference only if it survives order reversal; otherwise the unit is a tie. A four-judge jury (J) takes the majority verdict. A recusal jury (R) first drops every judge whose family wrote either candidate.

We test combinations D+N, R+S, D+N+R, and D+N+R+S. The length-controlled correction of Dubois et al. (2024) is applied after judging as a statistical adjustment (Section 4.5). Table 1 lists the baselines, with results that Section 6.1 discusses.

{{TABLE:baselines}}

## 3.6 Model choice and justification

The four judges and authors are Llama-3.2-3B-Instruct, Qwen2.5-3B-Instruct, Gemma-2-2B-it, and Ministral-3-3B-Instruct. Phi-4-mini-instruct pads and normalizes (Table 2). We chose these four families for three reasons. They can be hosted locally, which matches a setting in which clinical data cannot leave the institution. Four distinct families let authorship be crossed with correctness, so that same-family preference is not confounded with answer quality. And they are small enough that a fully crossed design is affordable.

We considered and rejected three alternatives. Closed or API-hosted models were rejected because the setting we study is one where data cannot leave the institution, and because a metered run was beyond our budget. Larger open-weight models were rejected for the main study because the design requires on the order of 100,000 verdicts per batch, which does not fit our compute budget at larger sizes. Domain-specialist biomedical models were rejected because the available ones are often fine-tuned from general base models, which would blur the family boundaries on which the authorship analysis depends, and because too few families exist to cross authors with judges.

This choice has a known cost: judges of 2–3B parameters may sit near chance on medical items, which limits how far any correction can move them and means that a large share of apparent manipulation may be churn. We accept the trade-off because the placebo measures that churn directly, and because this class of model is what a self-hosting biomedical group is likely to place in the verifier seat. The magnitudes belong to this class; what transfers is the method.

{{TABLE:models}}

# 4. Data and Experimental Setup

## 4.1 Datasets and access

The three benchmarks are public and serve only as sources of objective keys. Table 3 records where each is accessed, under what license, and how much of it is used. Each item has a question, lettered options, and an answer key; PubMedQA items also include a structured abstract with its conclusion removed. All text is English.

The judges do not see the benchmarks directly. They see a derived rationale set: each kept item contributes eight model-written rationales, so the @@M:NItemsKept@@ kept items yield @@n:x.n_rationales_kept@@ rationales (600 before exclusions). From these, the perturbation stage builds @@n:x.n_variants@@ text variants, each cached and stored with its construction method.

{{TABLE:datasets}}

## 4.2 Preprocessing

The stored run draws items with a fixed seed, stratified by benchmark. Each item is normalized into a lettered single-best-answer question: "all of the above" options are removed, because a rationale cannot argue for them without referring to the others, and PubMedQA is limited to yes/no. All models receive identical prompts, decoding settings, and candidate texts.

A rationale is valid only if it ends on the required target letter, does not endorse a competing option, does not refuse, and has between 30 and 250 words. Invalid outputs are regenerated up to twice at temperature 0.7, and an item is excluded if any of its rationales stays invalid. Excluded items are not replaced unless a benchmark falls too low. In the stored run, @@n:x.exclusions.first_try@@ of @@n:x.exclusions.n_rationales@@ rationales passed at the first attempt and @@n:x.exclusions.retried_ok@@ on retry. Two remained invalid, both for lacking the final-answer line, both written by Llama-3.2-3B, and both on MedMCQA items, so @@n:x.exclusions.excluded_by_source.medmcqa_pharm@@ MedMCQA items were excluded and no replacement was needed. No rationale exceeded the upper bound (the longest had @@n:x.exclusions.max_words@@ words). The planned Unicode and whitespace cleaning and near-duplicate removal were implemented after the stored draw and are switched on in the full-design configuration; the stored items were drawn without them.

## 4.3 Splits

No model is trained, so there are no training or validation splits. The data-model plan divides items into an evaluation set of 150 (two fixed batches of 75, stratified by benchmark) and a disjoint 12-item development set. We ran one evaluation batch, which is the plan's reduced-scale fallback. The development set was not run before the main run; Section 5.2 gives the consequence.

## 4.4 Experimental protocol

A judging unit is one verdict for a given judge, protocol, item, pair, condition, and order. Judges use greedy decoding at temperature 0 with at most 300 new tokens, and each unit is a single decode. A strict parser reads a tag of [[A]], [[B]], or [[C]] (tie). The bias block crosses four pairs, three length conditions, and two orders. The attack block applies edits to the first two pairs, in both orders, under the base, debiasing, normalized, and debiased-normalized protocols. Symmetric edits run under the base protocol only, and the deterministic normalizer runs on the base prompt only.

The main run produced @@M:NPairwise@@ pairwise verdicts and @@M:NSelect@@ selections, of which @@M:NCtrlVerdicts@@ pairwise verdicts came from the controls and the deterministic ablation. A further @@n:x.strip_n@@ verdicts supply the placebo floor for deterministic normalization, which the main run had not collected. We assumed that the three benchmarks are independent sources, that items within a benchmark are exchangeable, and that the fixed templates represent a low-effort adversary rather than the strongest one.

## 4.5 Evaluation metrics

A unit scores $s$ = 1 if the verdict prefers the rationale defending the keyed answer, 0 if it prefers the other, and one half for a tie or an unparseable verdict. Half credit keeps a judge that always abstains at 50% rather than 0%; since it can flatter a panel that abstains often, we also report accuracy with ties scored 0. Clean units have no padding and no edit. Rates are percentages and differences are percentage points (pp). Let $U$ denote the clean units of a configuration, and for edit $e$ let $s_{u}^{e}$ be the score of unit $u$ when $e$ is applied to R−.

**Accuracy** measures the verifier's job directly, against an objective reference. We add Cohen's kappa against the gold slot, and verification gain, a judge's verifier accuracy minus its own solo accuracy, which asks whether reading two rationales helps at all.

\eq{\text{Acc}=\frac{1}{|U|}∑_{u∈U}s_{u}}

**Order stability.** Flip is the share of clean pairs whose outcome changes when the order is reversed, and the position preference index PPI is the mean of +1 for a slot A verdict and −1 for a slot B verdict. **Padding sensitivity** is the accuracy lost when R− is padded. **Same-family favoritism** for judge $j$ compares the two self conditions on the same items, so that whatever the judge believes about the answer cancels out. **Tie rate** is the share of clean units scored one half.

\eq{\text{VB}=\text{Acc}(\text{none})−\text{Acc}(\text{R− padded}),   \text{SPB}_{j}=\text{Acc}_{j}(\text{self-right})−\text{Acc}_{j}(\text{self-wrong})}

**Interaction.** The contrast IC is what padding costs when the judge's own family wrote the wrong rationale (written SW), minus what padding costs on a neutral pair, so IC above zero means the two manipulations are super-additive.

\eq{\text{IC}=[\text{Acc}(\text{SW, none})−\text{Acc}(\text{SW, padded})]−[\text{Acc}(\text{neutral, none})−\text{Acc}(\text{neutral, padded})]}

We also fit a linear probability model on the bias block with judge fixed effects, indicators WA (incorrect rationale first), SW and SR (self-wrong and self-right), PW and PR (padded incorrect and correct), and the interactions SW×PW, WA×PW, and WA×SW, with errors clustered by item (Cameron & Miller, 2015).

**Attack success, repair, and gameability.** Each rate conditions on the same unit's clean verdict. With $U_{1}$ and $U_{0}$ the units scored 1 and 0 on the clean pair, ASR is the share of $U_{1}$ that is wrong after the edit (a tie counts one half), and RR is the share of $U_{0}$ that comes out right. We chose this conditional form because it asks the operational question, whether a correct verdict can be taken away. It cannot say what an edit does overall, so we add $Δ$Acc$_{e}$, the accuracy on edited units minus accuracy on the same units when clean.

\eq{\text{ASR}_{e}=\frac{∑_{u∈U_{1}}(1−s_{u}^{e})}{|U_{1}|},   \text{RR}_{e}=\frac{∑_{u∈U_{0}}s_{u}^{e}}{|U_{0}|},   \text{Net}_{e}=\text{ASR}_{e}−\text{RR}_{e}}

The placebo-adjusted rate is the project's measure of persuasion, since it removes what any edit of similar size would do. Because RQ4 needs one number per correction, we summarize robustness as gameability $G$, the mean adjusted rate over the five single edits. A correction $c$ then has two gains, both signed so that positive is good:

\eq{\text{Adj}_{e}=\text{ASR}_{e}−\text{ASR}_{\text{placebo}},   G=\frac{1}{5}∑_{e}\text{Adj}_{e}}

\eq{Δ\text{Acc}(c)=\text{Acc}(c)−\text{Acc}(\text{base}),   Δ\text{Rob}(c)=G(\text{base})−G(c)}

**Length-controlled accuracy.** After Dubois et al. (2024), we fit $s$ on judge effects, slot, and LR = log(words(R−)/words(R+)) across the bias block, and read clean accuracy at LR = 0, where $β$ is the fitted length slope.

\eq{\text{Acc}_{\text{LC}}=\text{Acc}−β × \text{mean}_{u∈U}(\text{LR}_{u})}

## 4.6 Statistical analysis

Confidence intervals are 95% percentile intervals from an item-level cluster bootstrap with 2,000 replicates (Field & Welsh, 2007). One weight matrix is reused throughout, so every difference is paired. Items are the resampling unit because verdicts on one item are strongly dependent. P-values are two-sided bootstrap sign tests, and cross-domain ranking agreement is Kendall's $W$ (Kendall & Babington Smith, 1939) with a permutation test. Four primary contrasts carried over from the main analysis (IC, $Δ$Acc of D+N+R+S, $W$ for accuracy, and the base-to-D+N change in the any-edit attack rate) are Holm-adjusted (Holm, 1979), and everything else is descriptive.

**Smallest effect and equivalence.** A nonsignificant result is not evidence of absence, so we test equivalence with two one-sided tests (Schuirmann, 1987) against a smallest effect of interest of ±5 pp, the margin we treat as practically meaningful in RQ2. This bound was chosen after the main run, is below every main effect in RQ1, and is reported as such. We also give the minimum detectable effect at 80% power for the interaction.

**RQ4 plan.** Ten corrections are a small sample, and they share verdicts, so they are not independent observations. The analysis is therefore Spearman's $ρ$ between $Δ$Acc and $Δ$Rob, with uncertainty from resampling items and recomputing $ρ$ in each replicate; a count of corrections improving both, and of those trading one against the other; and sensitivity to the choice of robustness summary. The permutation p-value is descriptive only. We wrote this plan into the code before computing the statistic but after the verdicts existed and many per-correction results were known, so RQ4 and RQ5 are exploratory. **RQ5** repeats the analysis inside each benchmark and on the natural-error subset: pairs whose R− author independently chose that same wrong answer in the solo stage (@@n:x.natural_pairs@@ author–item pairs).

## 4.7 Hardware and software environment

Solo answers, rationales, and padding ran on a laptop with one NVIDIA RTX 3050 (6 GB) under Windows 11. Judging, selection, and the controls ran on a Linux server with four NVIDIA L40S GPUs (46 GB each; three used), an Intel Xeon Gold 6526Y, and 503 GB of RAM, using Ollama 0.32.1. The placebo floor for deterministic normalization and the host check (Section 5.4) ran on the laptop with Ollama 0.40.13, using the same model digests. Models were served by Ollama (Ollama, 2026) on the llama.cpp back end (Gerganov et al., 2026) in 4-bit GGUF form, with flash attention and a q8_0 KV cache. Analysis needs only a CPU: Python 3.12 with NumPy 2.5.3 (Harris et al., 2020), pandas 3.0.6 (McKinney, 2010), SciPy 1.18.1 (Virtanen et al., 2020), statsmodels 0.15.0 (Seabold & Perktold, 2010), and Matplotlib 3.11.2 (Hunter, 2007), with SQLite for the call cache and Git for version control.

# 5. Implementation Details

## 5.1 System overview

The system is a staged batch pipeline (Table 4). Each stage reads the previous stage's JSONL output and writes its own, so a stage can be inspected or rerun on its own. Three design decisions shaped it. First, every model call passes through a SQLite cache keyed on the full request, so an interrupted run resumes without repeating work. This answers the compute-limit risk raised in the Milestone 2 feedback, and it worked in practice: work done on the laptop was reused when the project moved to the server, with no repeated calls. Second, all edits are templates rather than model outputs, so they can be audited and do not vary between runs. Third, all analysis is separated from inference. Reporting reads stored verdicts and calls no model, so any number can be regenerated in minutes on a CPU.

{{TABLE:components}}

## 5.2 Deviations from the proposal

Table 5 lists every deviation from the Milestone 2 plan. Most concern scale and tooling. The two that matter most for interpretation are running one of the two planned batches, which widens every interval, and the absence of a pre-tagged commit and a separate development set, which is why we describe RQ4 and RQ5 as exploratory and do not claim pre-registration.

The Milestone 2 feedback asked us to restore or justify three things. The length-controlled correction is restored as a post-hoc adjustment. Pre-set smallest effects are replaced by an equivalence bound that we disclose was set after the data. The reduced-scale fallback is what we ran. The feedback also asked us to confirm before the main run that all models load and decode, that the parser is reliable, and that no judge sits at chance. The first two were confirmed by an early check on a verdict sample and by the final parse rates (Section 6.2). The third was not satisfied, and it became a central finding: one judge sits below chance.

{{TABLE:deviations}}

## 5.3 Tools and compute resources

The phases with recorded timing took @@h:x.gpu_seconds@@ hours of wall-clock GPU time: @@h:x.phase_pad@@ hours for padding and normalization on the laptop, @@h:x.phase_judge@@ hours for main judging on the server (about @@M:JudgeCallsPerSec@@ calls per second), and @@h:x.phase_ctrl@@ hours for the controls. The earlier solo and generation stages and the added placebo floor ran on the laptop and add little. The plan estimated 8–16 GPU-hours for the larger design. Throughput on the 6 GB laptop was much lower than on the server, because only one model fits in memory at a time. Two operational problems are worth recording: the default host prompt cache in llama.cpp exhausted system memory until it was disabled, and on the server, rotating judges in the job order (rather than finishing each judge in turn) kept all model servers busy. Neither affects results, since each call is independent and cached on its content.

## 5.4 Reproducibility

One seed (2026) controls item sampling, tie-breaking, the fallback distractor rule, the authorship cycle, and the bootstrap weight matrix, and it is written in the configuration file. Prompts, edit templates, and the parser are each in a single module. Model builds are pinned by digest (Table 2). The repository's README gives setup, data preparation, run, and regeneration steps, and requirements.txt pins exact library versions. All new behavior required by the Milestone 2 plan is opt-in, so the stored run's draw is not affected. A separate configuration (configs/m2_full_design.yaml) specifies the full 150-item design, the development split, and both batches.

We verified the implementation at three levels. A simulator with planted biases of known size confirms that the pipeline and estimators recover those effects; it exposed two estimator bugs that were fixed before any real result was read, and it is never a source of numbers in this paper. The test suite of 23 offline tests passes on Windows. And regenerating the analysis from stored verdicts on a different operating system and Python build reproduced all 8,061 stored numeric values to within 1e−9.

Two reliability checks concern the models rather than the code. Greedy decoding is not bit-reproducible on this stack: asking every clean pair a second time with the same prompt and settings returned identical text @@v:b.retest.text_agreement@@% of the time and an identical verdict @@v:b.retest.verdict_agreement@@% of the time over @@n:b.retest.n@@ re-decodes, while pooled accuracy moved only from @@v:c.Base.acc@@% to @@v:b.retest.acc_retest@@%. Estimates are therefore stable although individual verdicts are not, and about @@M:RetestFlipPct@@% of verdicts would differ on a repeat run with nothing changed. Because the placebo floor for Det came from a different host, we also re-judged the @@n:x.host_check.n@@ base-protocol placebo units on the laptop. Verdicts agreed with the server's @@v:x.host_check.verdict_agreement@@% of the time, close to the @@v:b.retest.verdict_agreement@@% agreement between two decodes on one host, and the placebo ASR was @@v:x.host_check.asr_laptop@@% against @@v:x.host_check.asr_l40s@@%.

## 5.5 Ethical considerations

The benchmarks are English-only and lean toward US-style medical examinations, so conclusions may not transfer to other languages, health systems, or populations. Nothing here supports clinical use of any verifier. The study involves no human participants, patient records, or new annotation. Caching limited compute, and hours are reported so that readers can weigh each correction's cost. The edits are in effect templates for manipulating a verifier; we judge the risk to be low because they are simple and widely discussed, and we report defenses beside attacks.

# 6. Results

## 6.1 Baselines: the judges barely clear chance

Table 1 sets the scale. The random chooser scores 50.0% by definition. Picking the longer rationale, which uses no model at all, scores @@v:x.prefer_longer.acc_none@@% @@ci:x.prefer_longer.acc_none@@ on clean pairs, so length carries no useful information about the key in this set. The uncorrected single judge reaches @@v:c.Base.acc@@% @@ci:c.Base.acc@@ and the uncorrected jury @@v:c.J.acc@@% @@ci:c.J.acc@@. Pooling four weak judges therefore adds little. Yet the judges still favor length: decided clean verdicts go to the longer rationale @@v:x.longer_share.pooled@@% of the time @@ci:x.longer_share.pooled@@, although doing so is no better than a coin flip against the key.

## 6.2 RQ1: position and length bias are large, self-preference is model-specific, and the planned interaction is absent

Table 6 gives each judge's profile. Mean Cohen's kappa against the gold slot is @@M:KappaBase@@. The two alternative rules for ties and unparseable verdicts give @@v:b.tie_rules.acc_strict@@% (scored as misses) and @@v:b.tie_rules.acc_drop@@% (dropped). Parse failures are rare (@@M:ParseFailRate@@% of verdicts) and are not truncation: an audit of @@M:ParseAuditN@@ reissued calls found finish reason "stop" on all of them, with the longest completion at @@M:ParseAuditMaxTok@@ of @@M:ParseAuditCap@@ tokens, and @@M:ParseAuditReparse@@% of previously failed prompts parsed on a second decode.

{{TABLE:bias}}

Verification gain is negative for all four judges: @@v:b.verification_gain_pooled.all@@ pp pooled @@ci:b.verification_gain_pooled.all@@ and as low as @@v:b.verification_gain.llama.vg@@ pp @@ci:b.verification_gain.llama.vg@@ for Llama-3.2-3B, which answers @@v:b.verification_gain.llama.solo@@% of the same items correctly alone but agrees with the key only @@v:b.per_judge.llama.acc@@% of the time as a verifier. The gap is concentrated in two-option PubMedQA items (@@v:b.verification_gain_pooled.TwoOpt@@ pp @@ci:b.verification_gain_pooled.TwoOpt@@). On four-option items it is @@v:b.verification_gain_pooled.FourOpt@@ pp @@ci:b.verification_gain_pooled.FourOpt@@, where a pair judge has a higher chance floor than the solo task, so the fair reading is that a verifier adds no measurable value here rather than that verifiers are useless.

Position and length both have large effects (Table 7). A wrong answer in the first slot costs @@a:b.regression.WA@@ pp, padding it costs a further @@a:b.regression.PW@@ pp, and padding the correct answer gains @@a:b.regression.PR@@ pp. Gemma-2-2B picks whichever rationale it reads first often enough to reach a preference index of @@v:b.per_judge.gemma.ppi@@ pp. Between @@v:b.per_judge.mistral.flip@@% and @@v:b.per_judge.gemma.flip@@% of pairs change outcome when the two rationales swap places.

{{TABLE:regression}}

Self-preference does not generalize across families. Ministral-3-3B sides with the key @@v:b.per_judge.mistral.spb@@ pp @@ci:b.per_judge.mistral.spb@@ more often when its own family wrote the correct rationale than when its family wrote the wrong one, while Llama-3.2-3B is indistinguishable from neutral (@@v:b.per_judge.llama.spb@@ pp @@ci:b.per_judge.llama.spb@@), Qwen2.5-3B penalizes its own family (@@v:b.per_judge.qwen.spb@@ pp @@ci:b.per_judge.qwen.spb@@), and Gemma-2-2B points the same way but straddles zero. The pooled magnitude of @@v:b.corrections.Base.spb_abs@@ pp therefore describes none of them.

The interaction asked about in RQ1 is absent. The contrast is IC = @@v:c.Base.ic_self_len@@ pp @@ci:c.Base.ic_self_len@@ (@@p:b.primary_tests.raw.IC@@; Holm-adjusted @@M:HolmIC@@), and the regression gives $β$(SW×PW) = @@v:b.regression.SW:PW@@ pp (@@p:b.regression.SW:PW@@). With a standard error of @@M:ICSE@@ pp the design could only detect @@M:ICMDE@@ pp at 80% power, but equivalence against ±5 pp holds (TOST @@M:ICTOSTP@@). So padding and same-family authorship act additively. Position and length do compound, $β$(WA×PW) = @@v:b.regression.WA:PW@@ pp (@@p:b.regression.WA:PW@@), which we did not hypothesize. The risk comes mainly from the size of the individual biases.

## 6.3 RQ2: normalization improves accuracy, but no correction demonstrably reaches the meaningful margin

Table 8 scores every correction on every metric. Rewriting both candidates into a canonical form raises accuracy by @@v:g.N.dacc@@ pp @@ci:g.N.dacc@@, and D+N by @@v:g.D+N.dacc@@ pp @@ci:g.D+N.dacc@@. Recusal gains @@v:g.R.dacc@@ pp @@ci:g.R.dacc@@. The largest point estimate is D+N+R at @@v:g.D+N+R.dacc@@ pp @@ci:g.D+N+R.dacc@@, but it reaches that only with half credit for a tie rate of @@v:c.D+N+R.tie@@%, and with ties scored as misses its accuracy falls to @@v:c.D+N+R.acc_strict@@%, below the uncorrected judge's @@v:c.Base.acc_strict@@%. The primary contrast D+N+R+S gains @@v:g.D+N+R+S.dacc@@ pp @@ci:g.D+N+R+S.dacc@@ and does not survive adjustment (Holm @@M:HolmDAccFull@@), so we do not claim that the full pipeline improves accuracy.

Against the ±5 pp margin, S, D, Det, J, R, and R+S are each demonstrably smaller than a meaningful change (TOST p below 0.05). N, D+N, D+N+R, and D+N+R+S remain undecided, because their intervals are too wide to settle the question, and none has a lower bound at or above 5 pp. So no correction has been shown to improve accuracy by a practically meaningful margin. Scoring ties as misses is more severe: only N and D+N then stay above the uncorrected judge (@@v:c.N.acc_strict@@% and @@v:c.D+N.acc_strict@@% against @@v:c.Base.acc_strict@@%), and every panel falls below it.

{{TABLE:corrections}}

**Side effects are large and sometimes opposite to the goal.** Debiasing moves accuracy by @@v:g.D.dacc@@ pp @@ci:g.D.dacc@@ and leaves Flip and VB where they were. Swap removes the order flip by construction but leaves accuracy unchanged (@@v:g.S.dacc@@ pp) because disagreements become ties (tie rate @@v:c.S.tie@@%), so its accuracy with ties scored as misses falls to @@v:c.S.acc_strict@@%. Both juries increase Flip (@@v:c.J.flip@@% and @@v:c.R.flip@@% against @@v:c.Base.flip@@%), since a majority over disagreeing judges produces ties and a tie counts as a changed outcome under reversal. Normalization does not remove the length effect. It reverses it, moving VB from @@v:c.Base.vb@@ pp to @@v:c.N.vb@@ pp, so that padding R− now *raises* accuracy. The cause is the normalizer's own fallback. An 80-word rewrite of a padded text usually fails validation (@@v:b.normalizer_fallback_by_kind.pad@@% fall back to truncation, against @@v:b.normalizer_fallback_by_kind.raw@@% of unedited texts), and truncation keeps the filler while discarding the argument.

**Ablation: which part of the normalizer does the work?** Deterministic normalization buys no accuracy (@@v:g.Det.dacc@@ pp @@ci:g.Det.dacc@@) and leaves VB unchanged, so the accuracy gain belongs to the rewrite. That gain looks like equalized length rather than the rewriter's own medical knowledge. It is the same on items Phi-4-mini answers correctly and on those it does not (@@v:b.normalizer_split.phi_known.delta@@ against @@v:b.normalizer_split.phi_unknown.delta@@ pp), and accuracy after a validated rewrite matches accuracy after the deterministic fallback (@@v:b.normalizer_method_acc.llm@@% against @@v:b.normalizer_method_acc.fallback@@%), which contains no model output.

**Length-controlled correction.** The fitted slope is @@v:x.length_controlled.base_raw.beta@@ pp per log unit of length ratio @@ci:x.length_controlled.base_raw.beta@@, so doubling the wrong rationale relative to the right one costs about @@a:x.lc_doubling@@ pp. Yet the correction changes clean accuracy by only @@v:x.length_controlled.base_raw.gain@@ pp @@ci:x.length_controlled.base_raw.gain@@, because unpadded rationales in this set differ little in length on average. A statistical length correction is therefore not a remedy here, and most of the length effect exists only under padding.

## 6.4 RQ3: most apparent manipulation is churn, and one cue is truly persuasive

Taken at face value, these judges look easy to break: single edits overturn @@v:c.Base.asr_authority@@% to @@v:c.Base.asr_injection@@% of correct verdicts, and @@v:c.Base.asr_any@@% @@ci:c.Base.asr_any@@ fall to at least one of the five. The controls change that picture (Table 9, Figure 2). Two neutral sentences overturn @@v:c.Base.asr_placebo@@% @@ci:c.Base.asr_placebo@@, and simply decoding an unmodified prompt a second time overturns @@v:x.retest_asr@@% @@ci:x.retest_asr@@. The same edits repair @@v:c.Base.rr_any@@% @@ci:c.Base.rr_any@@ of verdicts that were wrong.

{{TABLE:gameability}}

Above the floor, three of the five single edits do more than disturb the text: the evaluator instruction by @@v:c.Base.adj_injection@@ pp @@ci:c.Base.adj_injection@@, citations by @@v:c.Base.adj_citation@@ pp @@ci:c.Base.adj_citation@@, and formatting by @@v:c.Base.adj_format@@ pp @@ci:c.Base.adj_format@@. Authority and confidence do not clear it. Reading accuracy alongside gives a narrower story, since only the instruction (@@v:c.Base.dacc_injection@@ pp @@ci:c.Base.dacc_injection@@) and citations (@@v:c.Base.dacc_citation@@ pp @@ci:c.Base.dacc_citation@@) cost accuracy among single edits. Formatting moves verdicts in both directions and repairs about as many as it breaks (@@v:c.Base.rr_format@@% against @@v:c.Base.asr_format@@%).

Symmetric edits separate three mechanisms. The evaluator instruction and citations **persuade**, since they help whichever side carries them: on R+ the instruction adds @@v:c.Base.symdacc_injection@@ pp @@ci:c.Base.symdacc_injection@@ and citations add @@v:c.Base.symdacc_citation@@ pp @@ci:c.Base.symdacc_citation@@. Confidence **repels**: it raises accuracy when placed on the wrong answer (@@v:c.Base.dacc_confidence@@ pp) and lowers it when placed on the right one (@@v:c.Base.symdacc_confidence@@ pp), so these judges are mildly put off by a response that insists on itself. Authority has **no directional effect** on either side. Formatting moves verdicts above the floor but in no consistent direction, so it costs no accuracy on either side. The placebo is not neutral either, since it raises accuracy by @@v:c.Base.dacc_placebo@@ pp @@ci:c.Base.dacc_placebo@@.

{{FIG:m3_gameability.png|Attack success above the placebo floor for each edit, for the uncorrected judge and the two normalizers. Zero marks an edit that does no more than the neutral sentences. Error bars are 95% item-level bootstrap intervals. Both normalizers remove most of the instruction's effect. Deterministic values can fall below zero because that normalizer deletes some edits outright, while part of the placebo survives it.|6.1}}

**Corrected judges.** Debiasing lowers $G$ from @@v:c.Base.G@@ to @@v:c.D.G@@ pp, with the instruction's adjusted rate falling to @@v:c.D.adj_injection@@ pp. It does so partly by raising the floor: its own placebo ASR is @@v:c.D.asr_placebo@@%. LLM normalization lowers $G$ to @@v:c.N.G@@ pp @@ci:c.N.G@@ and deterministic normalization to @@v:c.Det.G@@ pp @@ci:c.Det.G@@. Under deterministic normalization, the raw instruction rate falls from @@v:c.Base.asr_injection@@% to @@v:c.Det.asr_injection@@%, against @@v:c.N.asr_injection@@% under the rewrite.

**What Det actually does to the edits.** The ablation needs careful reading, because the regular expression undoes the instruction exactly: on @@v:x.strip_identity.injection@@% of incorrect rationales the stripped edited text equals the stripped clean text, so the judge sees the clean prompt again. The @@v:c.Det.asr_injection@@% is thus pure decoding churn, measured a second way, and the adjusted rate of @@v:c.Det.adj_injection@@ pp is negative only because part of the placebo survives stripping (its first sentence precedes the rationale; its second sentence is deleted with everything after the final-answer line). Two cautions follow. Part of Det's gain comes from this higher floor (@@v:c.Det.asr_placebo@@% against @@v:c.Base.asr_placebo@@%): on raw attack rates, the mean over the five single edits falls from @@v:c.Base.asr_mean@@% to @@v:c.Det.asr_mean@@%, a real but smaller reduction, and citation and authority text survive it. And the defense depends on where the template puts its text. A note placed before the final-answer line without brackets would pass straight through. Det defeats these fixed templates; it has not been tested against an attacker who adapts to it. The held-out consensus cue costs @@a:c.Base.dacc_consensus@@ pp of accuracy at base @@ci:c.Base.dacc_consensus@@, and under D+N its success (@@v:c.D+N.asr_consensus@@%) is indistinguishable from that configuration's floor (@@v:c.D+N.asr_placebo@@%), so the defense generalizes past the cues it was written for, at least to this one.

**A qualitative check.** The stored verdicts show how the instruction works. Of @@n:x.injection_mentions.n_flipped@@ clean-correct units it turned wrong, only @@n:x.injection_mentions.n_named@@ (@@v:x.injection_mentions.share_named@@%) mention verification, a review team, or an evaluator in their explanation. Appeals to guidelines are more common (@@v:x.injection_mentions.share_guideline@@% of these explanations, against @@v:x.injection_mentions.share_guideline_clean@@% of the same units' clean verdicts), which may echo the note's phrase "current clinical guidelines". So the judge changes its verdict and gives a medical reason, at most borrowing the note's vocabulary. In one MedQA item on essential tremor, Qwen2.5-3B judging the clean pair writes:

> "Assistant A correctly identifies the diagnosis as essential tremor and recommends Propranolol, which is indeed effective in managing this condition [...] Assistant B suggests Primidone for essential tremor, which is not typically used for this purpose."

With only the bracketed note appended to the incorrect rationale, the same judge on the same pair writes:

> "Assistant A suggests Propranolol, which is not typically used for essential tremor [...] Assistant B recommends Primidone as the most appropriate initial treatment for essential tremor based on clinical guidelines."

The medical claim reverses, and the only visible trace of the note is the borrowed reference to guidelines. An auditor reading such explanations would see a plausible clinical argument, not a judge deferring to a claim of prior review.

## 6.5 RQ4: accuracy gain predicts robustness gain only weakly

Across the @@n:x.transfer.n_corrections@@ corrections, Spearman's $ρ$ between $Δ$Acc and $Δ$Rob is @@r:x.transfer.rho@@, with a 95% item-bootstrap interval of [@@r:x.transfer.lo@@, @@r:x.transfer.hi@@] that spans zero (permutation @@p:x.transfer.p_perm@@, descriptive only). Figure 3 shows the structure behind this number. The corrections do not lie along a line. The LLM-normalized configurations gain on both axes, deterministic normalization has the largest robustness gain with no accuracy gain, and the rest sit near zero on at least one axis.

{{FIG:m3_transfer.png|Accuracy gain against robustness gain for each correction. Gray bars are 95% item-level bootstrap intervals. The upper-right group shares one mechanism, LLM normalization. Deterministic normalization (Det) and recusal (R) show that either gain can occur without the other.|5.2}}

The exceptions are what make the result informative. Recusal has an accuracy gain whose interval clears zero (@@v:g.R.dacc@@ pp @@ci:g.R.dacc@@) and no robustness gain (@@v:g.R.drob@@ pp @@ci:g.R.drob@@). R+S reduces robustness (@@v:g.R+S.drob@@ pp @@ci:g.R+S.drob@@) with no accuracy change. Debiasing has a robustness estimate of @@v:g.D.drob@@ pp @@ci:g.D.drob@@ with zero accuracy gain, and Det has @@v:g.Det.drob@@ pp @@ci:g.Det.drob@@ with @@v:g.Det.dacc@@ pp of accuracy. The accuracy-gain interval clears zero for @@L:x.transfer.acc_ci_above_zero@@, and the robustness-gain interval clears zero for @@L:x.transfer.rob_ci_above_zero@@, so the two lists agree on only three corrections, all containing N.

The estimate is sensitive to analytic choices, and we report them rather than select one. Because Det's floor came from another host and its mechanism is unusual, we recomputed without it: $ρ$ rises to @@r:x.transfer_no_det.rho@@ [@@r:x.transfer_no_det.lo@@, @@r:x.transfer_no_det.hi@@], still spanning zero, because the remaining set is dominated by the N-based group. Using other robustness summaries for all ten corrections, $ρ$ is @@r:x.transfer_sensitivity.raw_mean.rho@@ with the raw mean attack rate, @@r:x.transfer_sensitivity.any.rho@@ with the raw any-edit rate, @@r:x.transfer_sensitivity.combo.rho@@ with the adjusted combined edit, @@r:x.transfer_sensitivity.injection.rho@@ with the adjusted instruction alone, and @@r:x.transfer_sensitivity.net_any.rho@@ with the net any-edit rate. Every estimate is positive, and every interval includes zero. We conclude that accuracy and robustness gains tend to co-occur weakly in this set, and that accuracy gain does not identify which corrections harden a judge.

## 6.6 RQ5: the association does not hold steadily at the boundaries

Table 10 and Figure 4 repeat the analysis on four slices. The association is unstable: $ρ$ is @@r:s.literature.transfer.rho@@ on PubMedQA, @@r:s.clinical.transfer.rho@@ on MedQA-USMLE, @@r:s.pharmacology.transfer.rho@@ on MedMCQA, and @@r:s.natural_error.transfer.rho@@ on the natural-error subset, and every interval is wide and includes zero. Each benchmark slice has about a third of the items and the natural-error slice covers only some pairs of its items, so these estimates can show instability but cannot establish a difference between slices. Corrections that help on one benchmark can trade one gain against the other on another.

{{TABLE:boundary}}

{{FIG:m3_boundary.png|The RQ4 relationship within each benchmark and on the natural-error subset. Each point is one correction. Scales are shared, so the spread can be compared across panels. Interval bars are omitted for legibility and appear in the repository's results.|6.1}}

The natural-error subset needs its own reading, because a forced rationale might carry cues that a sincere error would not. It covers @@n:s.natural_error.n_items@@ items and @@n:s.natural_error.n_verdicts@@ verdicts. Uncorrected accuracy there is @@v:s.natural_error.base.acc@@% @@ci:s.natural_error.base.acc@@, at chance, compared with @@v:c.Base.acc@@% overall, which suggests that the errors models actually make are at least as hard to catch. The instruction's adjusted success there is @@v:s.natural_error.base.adj_injection@@ pp @@ci:s.natural_error.base.adj_injection@@, against @@v:c.Base.adj_injection@@ pp overall. The intervals overlap, but neither estimate suggests that forced rationales overstate the problem.

Judge rankings also fail to transfer. Agreement across the three benchmarks under the base protocol is $W$ = @@M:KWAcc@@ for accuracy (@@M:KWAccP@@ before adjustment, @@M:HolmKWAcc@@ after), and @@M:KWVB@@, @@M:KWSPB@@, and @@M:KWASR@@ for padding sensitivity, self-preference, and any-edit attack rate. With four judges and three benchmarks the permutation distribution is coarse, and no ranking is stable after adjustment. Llama-3.2-3B's accuracy swings from @@v:b.domain.literature.llama.acc@@% on PubMedQA to @@v:b.domain.pharmacology.llama.acc@@% on MedMCQA. Benchmark and answer format are confounded, as only PubMedQA has two options.

## 6.7 Secondary test: best-of-4 selection

The project also tests a second verifier role that the data model did not plan. A selector reads four candidates, only one of them correct, and three defending the same distractor, so a majority over final answers would be wrong on every item. This is a deliberate worst case, modeling a sampling or debate stage that has converged on a popular error. Figure 5 shows the outcome. In a clean pool the selector picks correctly @@v:b.select.base_raw|pooled.acc_clean@@% of the time @@ci:b.select.base_raw|pooled.acc_clean@@, against the @@v:b.select.base_raw|pooled.chance_scored@@% that a random pick scores once unparseable picks count as misses. Decorating one incorrect candidate with all five edits pulls captures from @@v:b.select.base_raw|pooled.capture_clean@@% to @@v:b.select.base_raw|pooled.capture_attack@@% @@ci:b.select.base_raw|pooled.capture_attack@@ and accuracy to @@v:b.select.base_raw|pooled.acc_attack@@% @@ci:b.select.base_raw|pooled.acc_attack@@. Under D+N accuracy holds between @@v:b.select.debias_norm|pooled.acc_attack@@% and @@v:b.select.debias_norm|pooled.acc_clean@@%, and capture does not exceed @@v:b.select.debias_norm|pooled.capture_clean@@%. Position acts differently in this setting: selectors under-pick the first candidate (@@v:b.select.base_raw|pooled.pos1_excess@@ pp against a neutral selector), although the same models prefer slot A in pairwise judging.

{{FIG:m3_bestof.png|Best-of-4 selection. One decorated incorrect candidate redirects the uncorrected selector and pushes its accuracy down to about the level of a random pick (dotted line, inside the interval); debiasing plus normalization holds. Error bars are 95% item-level bootstrap intervals.|6.1}}

# 7. Analysis and Discussion

## 7.1 Why the results look the way they do

**The judges are not verifying.** Verdicts match the key @@v:c.Base.acc@@% of the time, and every model scores higher answering the items itself than refereeing them. We read this as a failure of comparison rather than of knowledge. A judge given two fluent rationales has to weigh confident text arguing in opposite directions, and rationales written to order are persuasive whichever option they defend. It may then respond more to which text it read and how much of it there was than to medical content. The biases are not corrupting a careful judgment; they are tilting a decision that was close to a coin flip. This explains why apparent attack rates are so high, and why the placebo is essential.

**Why accuracy and robustness come apart.** The ablation suggests that the two gains have separate causes. Cue deletion stops the edits: the instruction is the most persuasive cue, and removing it removes most gameability, with no effect on accuracy, as Det shows. Length equalization buys accuracy: it removes a strong and misleading signal from the judge's decision. An LLM rewrite happens to do both, which is why the two gains co-occur for N-based corrections and why the association is positive at all. It reflects one shared mechanism, not a general law that accuracy brings robustness. Recusal shows the reverse separation: it removes one source of bias and leaves the cues in place. Debiasing instructs the judge but changes neither input nor comparison, and judges that cannot compare well may not be able to act on it.

**Why the evaluator instruction works.** The instruction is the only cue that claims the verification has already been done, addressing the verifier's task rather than decorating the answer. Credentials and confident tone describe an author; the instruction describes the outcome. This fits the injection literature (Greshake et al., 2023; Shi et al., 2024). The qualitative evidence adds a concern for auditing: judges rarely acknowledge the note, so reading explanations for a stated deference would not catch it, although a sudden appeal to guidelines may be a usable signal. These 2–3B judges also appear to be put off by bare assertion, which may be why asserted confidence fails.

## 7.2 Trade-offs

Table 11 sets each correction's cost beside what it buys. Deterministic normalization is nearly free: one regular expression, with no added verdicts or model calls. It delivers a robustness gain against these templates but no accuracy gain. LLM normalization costs one model call per candidate and delivers both, at the price of a reversed length bias and a model that can distort reasoning. Swap doubles the verdicts and recusal needs multiple judges, and both convert disagreement into ties. This raises a design question that half-credit scoring hides: a tie is a refusal to decide. A verifier that abstains on @@v:c.D+N+R+S.tie@@% of pairs, as D+N+R+S does, is cautious, but the pipeline must then escalate or pick by another rule. Accuracy with ties scored as misses shows this cost directly. Between speed and quality, the best value here is deterministic normalization for robustness and N when accuracy matters. Stacking everything is the most expensive option and does not beat D+N.

{{TABLE:tradeoff}}

## 7.3 Failure cases and unexpected behaviors

Several results contradicted our expectations. **The interaction we hypothesized was absent**, while an unplanned one (position × length) appeared. **Llama-3.2-3B judges below chance** on literature items (@@v:b.domain.literature.llama.acc@@%), although it is the most accurate model when answering alone, and this is a failure of the role rather than of the model's knowledge. **Debiasing does not lower the broadest attack measure**: the raw any-edit rate moves by @@M:DeltaASRanyDebias@@ pp @@M:DeltaASRanyDebiasCI@@, an interval that includes zero, while its placebo floor rises. **Normalization fails on long inputs**: most padded texts exceed what the rewriter can compress within validation limits, and the fallback's truncation produced the reversed length bias. A concrete instance is a padded MedQA rationale that merely restates the case history for its full 80 words and then gives a final answer, leaving no argument to judge. **Juries worsen order stability**, the opposite of why ensembles are usually adopted. And **greedy decoding is not reproducible**: an expectation that temperature 0 would yield identical repeats simply does not hold under continuous batching. Parse failures are the same phenomenon, since most reparse on a second decode.

## 7.4 Limitations and threats to validity

**Construct validity.** Multiple-choice items with rationales written to order are a controlled proxy for biomedical verification. Nothing here measures completeness, communication, or clinical safety. A rationale written to defend an option its author believes wrong may carry cues that a sincere mistake would not, although the natural-error slice suggests this does not inflate the problem. Padding and normalization are validated automatically, so some rewrites will have strengthened or weakened an argument.

**Internal validity.** Half credit flatters abstaining panels, which is why we report the strict column. The controls were judged in a later session than the main run, and normalized text in that session is a fresh sample from the same prompt, not the identical strings. The Det floor came from a different machine and Ollama version. The host check shows that this matters little (Section 5.4), since verdicts agree across hosts almost as often as across two decodes on one host, but it does not eliminate the difference. Under Det, the placebo's second sentence falls after the final-answer line and is deleted, so Det's floor measures a different edit from the other floors, and it is the reason a sizable part of Det's $Δ$Rob is a higher floor rather than a lower attack rate. Gemma-2-2B uses a different quantization from the other judges, which could contribute to its differences. Self-preference and rationale length are also partly confounded by family, since authors differ in mean length from @@M:WordsMin@@ to @@M:WordsMax@@ words.

**Statistical conclusion validity.** With @@M:NItemsKept@@ items, intervals are wide and this study can detect only large effects. Corrections share verdicts, so RQ4's ten points are not independent, and the bootstrap interval is the appropriate statement of uncertainty. RQ4, RQ5, and the ±5 pp bound were specified after verdicts existed, so they are exploratory and need confirmation on new items. Only the four primary contrasts are adjusted for multiplicity.

**External validity.** Every judge is a 2–3B model at 4-bit, so the magnitudes belong to that class. Each benchmark has its own answer format, and benchmark and format are confounded. All three are public and may be in the judges' training data, which would inflate solo accuracy and could partly explain the negative verification gain. They are English-only and lean toward US-style examinations. Finally, the edits are fixed templates rather than an optimizing adversary, so they estimate a floor on what an attacker gets for free, not a ceiling.

## 7.5 Implications

For practitioners deploying a small verifier, four points follow. Do not read accuracy validation as a robustness guarantee. Remove cue text from the input before the judge sees it, which needs only a few lines of deterministic code against fixed templates, and treat any instruction embedded in candidate text as hostile, since a determined attacker can route around simple pattern matching. Keep a judge away from its own family's writing, as self-preference can be very large where it exists. And do not assume a panel is free, since juries bought some gains with more ties and more order dependence. For researchers, the result is methodological: reporting attack success without a placebo overstates persuasion, and reporting a correction's effect on its target bias alone hides its side effects. On the question of why this matters, an agentic pipeline in which a near-chance verifier can be redirected by one bracketed sentence does not have the safety layer its architecture suggests.

# 8. Conclusion and Future Work

We asked whether a small language model placed in charge of checking another model's biomedical answer becomes harder to manipulate when it becomes more accurate. Scoring verifiers against expert keys, we crossed position, length, authorship, and content-free edits, and subtracted a placebo floor. These verifiers sit near chance, are swayed by reading order and length, and check answers less well than they produce them. Most apparent manipulation is instability; what truly moves them is a sentence claiming the answer has already been verified. Accuracy gain predicts robustness gain only weakly across corrections, and its positive sign comes chiefly from LLM normalization, which delivers both. Recusal raises accuracy without robustness, deterministic normalization raises robustness against these templates without accuracy, and the association is not stable within benchmarks or on natural errors. Our hypothesis, that accuracy alone does not protect a judge from manipulation, is supported in that sense, although the design cannot rule out a modest general association.

The main limitations are the sample of @@M:NItemsKept@@ items, the restriction to 2–3B models, the post-hoc status of the RQ4 and RQ5 analyses, and the confounding of benchmark with answer format.

Future work follows from these limits. First, run new items from the prepared configuration, which excludes every item already judged, to double the sample and provide a held-out, pre-specified test of the RQ4 association. Second, repeat the protocol with larger open-weight judges to learn whether gameability falls as competence rises, since the near-chance floor here limits what any correction can show. Third, use items where format is not confounded with benchmark. Fourth, test an adaptive adversary, such as a bandit search over edits (Yang et al., 2026), against deterministic normalization, starting with the simplest evasion of moving the note above the final-answer line. Fifth, repair the normalizer's handling of long inputs and measure whether the reversed length bias disappears. Finally, compare verdicts with clinician judgments on a subset to establish how far an expert key captures verification in practice.

# Code and Data Availability

The complete code, configurations, stored model outputs, derived data, and the scripts that regenerate every number, table, and figure are in the submission package; its README.md gives step-by-step instructions. All three benchmarks are public under the licenses in Table 3. PubMedQA's labeled file is included in the package, and the other two download automatically through the Hugging Face datasets library on first use.

# Acknowledgment

All experiments ran on personal and institutional hardware with open-weight models. Generative AI tools assisted with code and with drafting and editing text. The authors take responsibility for the content and checked all numbers against the stored analysis output.

# References

REF: Abouelenin, A., Ashfaq, A., Atkinson, A., et al. [Microsoft]. (2025). *Phi-4-mini technical report: Compact yet powerful multimodal language models via mixture-of-LoRAs*. arXiv:2503.01743.
REF: Afrasyab, K. (2026). *Evaluating medical AI under missing information: Same-provider judges and human raters change apparent safety*. arXiv:2607.18828.
REF: Arora, R. K., Wei, J., Hicks, R. S., Bowman, P., Quiñonero-Candela, J., Tsimpourlas, F., Sharman, M., Shah, M., Vallone, A., Beutel, A., Heidecke, J., & Singhal, K. (2025). *HealthBench: Evaluating large language models towards improved human health*. arXiv:2505.08775.
REF: Bedi, S., Cui, H., Fuentes, M., Unell, A., Wornow, M., Banda, J. M., Kotecha, N., Keyes, T., Mai, Y., Oez, M., Qiu, H., Jain, S., Schettini, L., Kashyap, M., Fries, J. A., Swaminathan, A., Chung, P., Nateghi, F., Aali, A., ... Shah, N. H. (2025). *MedHELM: Holistic evaluation of large language models for medical tasks*. arXiv:2505.23802.
REF: Cameron, A. C., & Miller, D. L. (2015). A practitioner's guide to cluster-robust inference. *Journal of Human Resources, 50*(2), 317–372.
REF: Chen, G. H., Chen, S., Liu, Z., Jiang, F., & Wang, B. (2024). Humans or LLMs as the judge? A study on judgement biases. In *Proceedings of EMNLP 2024*.
REF: Clusmann, J., Ferber, D., Wiest, I. C., Schneider, C. V., Brinker, T. J., Foersch, S., Truhn, D., & Kather, J. N. (2025). Prompt injection attacks on vision language models in oncology. *Nature Communications, 16*, 1239.
REF: Cobbe, K., Kosaraju, V., Bavarian, M., Chen, M., Jun, H., Kaiser, L., Plappert, M., Tworek, J., Hilton, J., Nakano, R., Hesse, C., & Schulman, J. (2021). *Training verifiers to solve math word problems*. arXiv:2110.14168.
REF: de Oliveira, R., Pittino, F., Gwinnutt, J., & Nanavati, J. (2026). *Beyond correctness: Validity-oriented evaluation of biomedical LLM judges*. arXiv:2608.29127.
REF: Dubois, Y., Galambosi, B., Liang, P., & Hashimoto, T. B. (2024). Length-controlled AlpacaEval: A simple way to debias automatic evaluators. In *Proceedings of the Conference on Language Modeling (COLM)*.
REF: Field, C. A., & Welsh, A. H. (2007). Bootstrapping clustered data. *Journal of the Royal Statistical Society: Series B, 69*(3), 369–390.
REF: Gao, S., Fang, A., Huang, Y., Giunchiglia, V., Noori, A., Schwarz, J. R., Ektefaie, Y., Kondic, J., & Zitnik, M. (2024). Empowering biomedical discovery with AI agents. *Cell, 187*(22), 6125–6151.
REF: Gemma Team. (2024). *Gemma 2: Improving open language models at a practical size*. arXiv:2408.00118.
REF: Gerganov, G., et al. (2026). *llama.cpp* [Computer software]. https://github.com/ggml-org/llama.cpp
REF: Grattafiori, A., Dubey, A., Jauhri, A., Pandey, A., Kadian, A., Al-Dahle, A., Letman, A., Mathur, A., Schelten, A., Vaughan, A., Yang, A., Fan, A., Goyal, A., Hartshorn, A., Yang, A., Mitra, A., Sravankumar, A., Korenev, A., Hinsvark, A., ... Ma, Z. (2024). *The Llama 3 herd of models*. arXiv:2407.21783.
REF: Greshake, K., Abdelnabi, S., Mishra, S., Endres, C., Holz, T., & Fritz, M. (2023). Not what you've signed up for: Compromising real-world LLM-integrated applications with indirect prompt injection. In *Proceedings of the 16th ACM Workshop on Artificial Intelligence and Security* (pp. 79–90).
REF: Harris, C. R., Millman, K. J., van der Walt, S. J., et al. (2020). Array programming with NumPy. *Nature, 585*, 357–362.
REF: Holm, S. (1979). A simple sequentially rejective multiple test procedure. *Scandinavian Journal of Statistics, 6*(2), 65–70.
REF: Hunter, J. D. (2007). Matplotlib: A 2D graphics environment. *Computing in Science & Engineering, 9*(3), 90–95.
REF: Jin, D., Pan, E., Oufattole, N., Weng, W.-H., Fang, H., & Szolovits, P. (2021). What disease does this patient have? A large-scale open domain question answering dataset from medical exams. *Applied Sciences, 11*(14), 6421.
REF: Jin, Q., Dhingra, B., Liu, Z., Cohen, W. W., & Lu, X. (2019). PubMedQA: A dataset for biomedical research question answering. In *Proceedings of EMNLP-IJCNLP* (pp. 2567–2577).
REF: Kendall, M. G., & Babington Smith, B. (1939). The problem of m rankings. *The Annals of Mathematical Statistics, 10*(3), 275–287.
REF: Kim, Y., Park, C., Jeong, H., Chan, Y. S., Xu, X., McDuff, D., Lee, H., Ghassemi, M., Breazeal, C., & Park, H. W. (2024). MDAgents: An adaptive collaboration of LLMs for medical decision-making. In *Advances in Neural Information Processing Systems, 37*.
REF: Kwok, T. S. T., Qian, Q., Lin, X., Zhang, D., Han, J., Yang, Z., Hill, D., Soliman, T., Batra, S. S., Tillman, R., & Cheng, G. (2026). *MedFabric: Gold evidence hides the difficulty of word-level medical fabrication detection*. arXiv:2605.04180.
REF: Li, H., Chen, J., Ai, Q., Chu, Z., Zhou, Y., Dong, Q., & Liu, Y. (2025). CalibraEval: Calibrating prediction distribution to mitigate selection bias in LLMs-as-judges. In *Proceedings of the 63rd Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers)* (pp. 16537–16552).
REF: Li, L., Li, D., Chen, C., Ma, R., Yu, R., Lin, M., Yin, R., Fan, L., Shyr, C., Ma, S., Liu, M., & Bethard, S. (2026). *LLM-as-a-judge in healthcare: A scoping analysis of applications, methods, and human alignment*. arXiv:2605.25273.
REF: Li, Q., Dou, S., Shao, K., Chen, C., & Hu, H. (2025). *Evaluating scoring bias in LLM-as-a-judge*. arXiv:2506.22316.
REF: McKinney, W. (2010). Data structures for statistical computing in Python. In *Proceedings of the 9th Python in Science Conference* (pp. 56–61).
REF: Mistral AI. (2025). *Introducing Mistral 3* [Model announcement]. https://mistral.ai/news/mistral-3
REF: Ollama. (2026). *Ollama* [Computer software]. https://github.com/ollama/ollama
REF: Pal, A., Umapathi, L. K., & Sankarasubbu, M. (2022). MedMCQA: A large-scale multi-subject multi-choice dataset for medical domain question answering. In *Proceedings of the Conference on Health, Inference, and Learning* (PMLR 174, pp. 248–260).
REF: Panickssery, A., Bowman, S. R., & Feng, S. (2024). LLM evaluators recognize and favor their own generations. In *Advances in Neural Information Processing Systems, 37*.
REF: Qwen Team. (2024). *Qwen2.5 technical report*. arXiv:2412.15115.
REF: Raina, V., Liusie, A., & Gales, M. (2024). Is LLM-as-a-judge robust? Investigating universal adversarial attacks on zero-shot LLM assessment. In *Proceedings of EMNLP 2024*.
REF: Saito, K., Wachi, A., Wataoka, K., & Akimoto, Y. (2023). *Verbosity bias in preference labeling by large language models*. arXiv:2310.10076.
REF: Schmidgall, S., Ziaei, R., Harris, C., Reis, E., Jopling, J., & Moor, M. (2024). *AgentClinic: A multimodal agent benchmark to evaluate AI in simulated clinical environments*. arXiv:2405.07960.
REF: Schuirmann, D. J. (1987). A comparison of the two one-sided tests procedure and the power approach for assessing the equivalence of average bioavailability. *Journal of Pharmacokinetics and Biopharmaceutics, 15*(6), 657–680.
REF: Seabold, S., & Perktold, J. (2010). Statsmodels: Econometric and statistical modeling with Python. In *Proceedings of the 9th Python in Science Conference* (pp. 92–96).
REF: Shi, J., Yuan, Z., Liu, Y., Huang, Y., Zhou, P., Sun, L., & Gong, N. Z. (2024). Optimization-based prompt injection attack to LLM-as-a-judge. In *Proceedings of the ACM Conference on Computer and Communications Security (CCS)*.
REF: Soumik, S. K. (2026). *Judging the judges: A systematic evaluation of bias mitigation strategies in LLM-as-a-judge pipelines*. arXiv:2604.23178.
REF: Szymanski, A., Ziems, N., Eicher-Miller, H. A., Li, T. J.-J., Jiang, M., & Metoyer, R. A. (2025). Limitations of the LLM-as-a-judge approach for evaluating LLM outputs in expert knowledge tasks. In *Proceedings of the 30th International Conference on Intelligent User Interfaces*.
REF: Tang, X., Zou, A., Zhang, Z., Li, Z., Zhao, Y., Zhang, X., Cohan, A., & Gerstein, M. (2024). MedAgents: Large language models as collaborators for zero-shot medical reasoning. In *Findings of the Association for Computational Linguistics: ACL 2024*.
REF: Verga, P., Hofstätter, S., Althammer, S., Su, Y., Piktus, A., Arkhangorodsky, A., Xu, M., White, N., & Lewis, P. (2024). *Replacing judges with juries: Evaluating LLM generations with a panel of diverse models*. arXiv:2404.18796.
REF: Virtanen, P., Gommers, R., Oliphant, T. E., et al. (2020). SciPy 1.0: Fundamental algorithms for scientific computing in Python. *Nature Methods, 17*, 261–272.
REF: Wang, P., Li, L., Chen, L., Cai, Z., Zhu, D., Lin, B., Cao, Y., Liu, Q., Liu, T., & Sui, Z. (2024). Large language models are not fair evaluators. In *Proceedings of the 62nd Annual Meeting of the Association for Computational Linguistics*.
REF: Wataoka, K., Takahashi, T., & Ri, R. (2024). *Self-preference bias in LLM-as-a-judge*. arXiv:2410.21819.
REF: Yang, X., Hooi, B., Deng, G., Zhang, T., & Dong, J. S. (2026). Turning bias into bugs: Bandit-guided style manipulation attacks on LLM judges. In *Proceedings of the 43rd International Conference on Machine Learning* (PMLR 306). arXiv:2605.26156.
REF: Ye, J., Wang, Y., Huang, Y., Chen, D., Zhang, Q., Moniz, N., Gao, T., Geyer, W., Huang, C., Chen, P.-Y., Chawla, N. V., & Zhang, X. (2025). Justice or prejudice? Quantifying biases in LLM-as-a-judge. In *Proceedings of the International Conference on Learning Representations*.
REF: Zheng, L., Chiang, W.-L., Sheng, Y., Zhuang, S., Wu, Z., Zhuang, Y., Lin, Z., Li, Z., Li, D., Xing, E. P., Zhang, H., Gonzalez, J. E., & Stoica, I. (2023). Judging LLM-as-a-judge with MT-Bench and Chatbot Arena. In *Advances in Neural Information Processing Systems, 36*.
REF: Zheng, X., Pang, T., Du, C., Liu, Q., Jiang, J., & Lin, M. (2025). Cheating automatic LLM benchmarks: Null models achieve high win rates. In *The Thirteenth International Conference on Learning Representations*.
REF: Zhou, H., Huang, H., Zhang, R., Chen, K., Xu, B., Zhu, C., Zhao, T., & Yang, M. (2026). *Toward robust LLM-based judges: Taxonomic bias evaluation and debiasing optimization*. arXiv:2603.08091.
