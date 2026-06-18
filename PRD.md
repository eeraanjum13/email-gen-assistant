# PRD — Email Generation Assistant

**Owner:** Eera (Sadia Anjum) · **Status:** Draft · **Date:** 2026-06-18
**Context:** AI Engineer candidate assessment. Deliver a working prototype + an evaluation system + a comparative analysis.

---

## 1. Summary

Build a prototype assistant that turns three structured inputs — **intent**, **key facts**, **tone** — into a polished professional email using Claude, driven by an advanced, documented prompt. Then build an evaluation harness with three custom, email-specific metrics, run it across 10 scenarios under two prompting strategies, and produce a comparative analysis recommending one for production.

## 2. Problem & motivation

Drafting professional emails is repetitive and quality is inconsistent. A naive "write me an email" prompt drops facts, drifts on tone, and pads with filler. The goal is to show that disciplined prompt engineering measurably improves output, and to prove it with metrics rather than vibes.

## 3. Goals / Non-goals

**Goals**
- Generate professional emails from (intent, key facts, tone) reliably.
- Define and implement 3 custom, automated metrics tailored to email quality.
- Quantify the impact of advanced prompting vs. a naive baseline on identical inputs.
- Ship a reproducible repo + report any reviewer can run.

**Non-goals**
- No UI/frontend, no email sending/SMTP, no auth, no persistence beyond local files.
- No multi-provider abstraction (Anthropic only).
- No fine-tuning or RAG.

## 4. Users & use case

Primary user is the assessment reviewer running the repo. Conceptual end user is a professional who supplies intent + facts + tone and wants a send-ready draft.

## 5. Functional requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| F1 | Accept `intent` (string), `key_facts` (list of strings), `tone` (string) as input. | Must |
| F2 | Produce a complete, professional email body via Claude. | Must |
| F3 | Support two strategies: `advanced` (role + few-shot + chain-of-thought) and `naive` (bare instruction). | Must |
| F4 | Advanced prompt hides reasoning; only the final email is returned. | Must |
| F5 | CLI entry point to generate a single email for manual testing. | Should |
| F6 | Log every raw generation to `data/outputs/` for auditability. | Should |
| F7 | Deterministic-ish output (pinned model + low temperature). | Must |

## 6. Evaluation requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| E1 | 10 unique scenarios (intent/facts/tone) + a human reference email each, in `scenarios.json`. | Must |
| E2 | **Metric 1 — Fact Recall:** fraction of key facts present & accurate (LLM-judged per fact). | Must |
| E3 | **Metric 2 — Tone Accuracy:** rubric LLM-as-judge (1–5 → 0–1), reference email as calibration anchor. | Must |
| E4 | **Metric 3 — Conciseness & Clarity:** programmatic signals (length vs. ref, sentence length, filler count) + LLM clarity rating. | Must |
| E5 | Run all 10 scenarios under both strategies and score all 3 metrics. | Must |
| E6 | Emit `eval_results.csv` (raw per scenario×strategy×metric) and `eval_results.json` (metric definitions/logic + raw scores + averages). | Must |
| E7 | Judge calls use temperature 0, strict JSON output, retry on parse failure. | Should |

## 7. Analysis requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| A1 | Compute per-metric and overall averages for each strategy + deltas. | Must |
| A2 | One-page `summary.md`: which strategy won; biggest failure mode of the loser (data-backed); production recommendation justified by metrics. | Must |
| A3 | Include a comparison table; optional per-metric bar chart. | Should |

## 8. Deliverables

- GitHub repo with all code + README (setup + run instructions).
- Final report PDF containing: the exact prompt template, the 3 metric definitions/logic, the raw eval data, and the Section 3 comparative summary.

## 9. Architecture (brief)

`prompts.py` (templates) → `generate.py` (`EmailAssistant`) → `evaluate.py` (drives 10×2 matrix, calls `metrics.py`) → writes `results/` → `analyze.py` → `summary.md` → assembled into PDF. Anthropic Python SDK; config (model, temps, paths) centralized in `config.py`.

## 10. Metric definitions (detail)

- **Fact Recall** = included_facts / total_facts. Per fact, a judge returns present∈{true,false} with accuracy check (penalize hallucinated/distorted facts). Most heavily weighted in interpretation since dropped facts are the worst failure.
- **Tone Accuracy** = (rubric_score − 1) / 4. Rubric anchors define what 1 vs. 5 looks like for the requested tone; reference email supplied for calibration.
- **Conciseness & Clarity** = weighted blend of: length ratio to reference (penalty for >1.5×), mean sentence length, filler-phrase density, and a 0–1 LLM clarity rating. Tuned so dropping facts to shorten does not win.

## 11. Success criteria

- Harness runs end-to-end on a clean clone with only an API key.
- Metrics demonstrably separate known-good from known-bad emails (validity check).
- Advanced strategy scores higher on aggregate; report explains why and where naive fails.

## 12. Risks & mitigations

| Risk | Mitigation |
|------|-----------|
| LLM-judge noise | Rubrics, temp 0, reference anchoring, optional 2-run averaging. |
| Self-evaluation bias (same model judges its own family) | Acceptable for scope; stated as a limitation in the report. |
| Cost/latency of longer advanced prompt | Acknowledge tradeoff in recommendation despite same base model. |
| JSON parse failures from judge | Retry + schema validation. |
| Non-reproducibility | Pin model version + temperature; log raw outputs. |

## 13. Out of scope / future

Multi-provider comparison, real model-vs-model axis, human eval correlation study, web UI, sending integration.

## 14. Milestones

1. Repo scaffold + prompts.
2. Generator + smoke test.
3. 10 scenarios + references.
4. 3 metrics + unit checks.
5. Eval run → CSV/JSON.
6. Analysis + summary.
7. README + PDF report.
8. Verification pass (metric validity, judge spot-check, averages math).