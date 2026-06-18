# Email Generation Assistant

A candidate-assessment prototype that generates professional emails from structured inputs using the Anthropic Claude API, with a full evaluation harness and comparative analysis of two prompting strategies.

## What this project does

1. **Part 1 — Email Generation:** Generates professional emails from `intent`, `key_facts`, and `tone` using an advanced prompt (role-play + few-shot + chain-of-thought) and a naive baseline.
2. **Part 2 — Evaluation:** Scores 10 fictional scenarios under both strategies across 3 custom metrics: Fact Recall, Tone Accuracy, and Conciseness & Clarity.
3. **Part 3 — Analysis:** Compares strategies, identifies the naive baseline's failure modes, and produces a production recommendation in `results/summary.md` and `report/final_report.pdf`.

---

## Prerequisites

- Python 3.10+
- An Anthropic API key ([console.anthropic.com](https://console.anthropic.com))

---

## Setup

```bash
# 1. Clone the repo
git clone https://github.com/eeraanjum13/email-gen-assistant.git
cd email-gen-assistant

# 2. Create and activate a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set your API key
# Edit .env and replace "your-key-here" with your actual key
```

---

## Running the project

### Generate a single email (manual test)

```bash
python -m src.generate \
  --intent "Follow up on a job application" \
  --facts "Applied for Senior Engineer role" "Interview was last Tuesday" "Still waiting to hear back" \
  --tone formal \
  --strategy advanced
```

Switch `--strategy` to `naive` to compare the baseline output. Raw logs are written to `data/outputs/`.

### Run the full evaluation (Part 2)

Scores all 10 scenarios under both strategies across 3 metrics. Produces `results/eval_results.csv` and `results/eval_results.json`.

```bash
python -m src.evaluate
```

Expected output: 60 rows (10 scenarios × 2 strategies × 3 metrics).

### Run metric validity checks

Verifies each metric discriminates known-good from known-bad emails.

```bash
python -m src.metrics
```

Expected output: `PASS` for all 3 checks.

### Run the comparative analysis (Part 3)

Reads eval results, writes `results/summary.md` and `report/final_report.pdf`.

```bash
python -m src.analyze
```

### Full pipeline (all three steps in order)

```bash
python -m src.evaluate   # generates + scores
python -m src.analyze    # analysis + report
```

---

## Output files

| File | Description |
|------|-------------|
| `data/outputs/*.json` | Raw generation logs (one per call) |
| `results/eval_results.csv` | 60-row scored results matrix |
| `results/eval_results.json` | Self-describing results with metric definitions and averages |
| `results/summary.md` | One-page comparative analysis and production recommendation |
| `report/final_report.pdf` | Full report: prompt templates, metric definitions, raw data, analysis |

---

## Key results

| Metric | Advanced | Naive | Delta |
|--------|----------|-------|-------|
| Fact Recall | 0.955 | 0.975 | -0.020 |
| Tone Accuracy | 0.950 | 0.750 | +0.200 |
| Conciseness & Clarity | 0.782 | 0.659 | +0.123 |
| **Overall** | **0.896** | **0.795** | **+0.101** |

The advanced strategy wins overall. Its largest advantage is Tone Accuracy (+0.200), where the naive baseline defaults to a generic formal register regardless of the requested tone.

---

## Known limitations

- **Self-evaluation bias:** The same model family (Claude) both generates emails and acts as judge. Results are directionally correct but not ground truth.
- **No UI or email sending:** This project drafts emails only — nothing is delivered.
- **Fictional data only:** All scenarios use made-up names, companies, and addresses.

---

## Project structure

```
src/
  config.py      # model, temperatures, paths, metric weights
  prompts.py     # ADVANCED_* and NAIVE_* templates
  generate.py    # EmailAssistant class + CLI
  metrics.py     # 3 metrics + validity checks
  evaluate.py    # 10×2 evaluation runner
  analyze.py     # comparative analysis + PDF report
data/
  scenarios.json       # 10 evaluation scenarios
  outputs/             # raw generation logs
results/
  eval_results.csv
  eval_results.json
  summary.md
report/
  final_report.pdf
```
