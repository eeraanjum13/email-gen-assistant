# BUILD_PLAN.md — Email Generation Assistant

Engineering plan and architecture. Read with `PRD.md` (requirements) and `CLAUDE.md` (rules).

**Stack:** Python 3.10+ · Anthropic Claude API (SDK only) · local files, no UI/DB/SMTP.
**A/B axis:** one model, two prompts — *advanced* (role + few-shot + chain-of-thought) vs.
*naive* baseline. Isolates the impact of prompt engineering, which is the Section 3 story.

---

## 1. Repository layout

```
email-gen-assistant/
├── README.md                  # setup + run (deliverable)
├── requirements.txt           # pinned deps
├── .env.example               # ANTHROPIC_API_KEY=your-key-here
├── .gitignore                 # .env, __pycache__, data/outputs/*
├── CLAUDE.md  PRD.md  BUILD_PLAN.md
├── src/
│   ├── __init__.py
│   ├── config.py              # model, temps, paths, weights, constants
│   ├── prompts.py             # ADVANCED_* + NAIVE_* templates, judge prompts
│   ├── generate.py            # EmailAssistant + CLI
│   ├── metrics.py             # 3 metrics + validity unit checks
│   ├── evaluate.py            # 10×2 matrix runner -> results/
│   └── analyze.py             # aggregation, winner, failure mode, summary.md
├── data/
│   ├── scenarios.json         # 10 scenarios + reference emails
│   └── outputs/               # raw generation logs (audit trail)
├── results/
│   ├── eval_results.csv  eval_results.json  summary.md
├── report/
│   └── final_report.pdf
└── .claude/
    ├── commands/create-spec.md
    └── specs/                 # 01-…, 02-…, 03-… per part
```

---

## 2. Shared foundation (build first)

**`config.py`** — single source of truth, no scattered literals:
```python
MODEL = "claude-…"            # pinned version string
GEN_TEMPERATURE = 0.3         # generation (slight variety, still stable)
JUDGE_TEMPERATURE = 0.0       # deterministic judging
MAX_TOKENS = 1024
DATA_DIR / OUTPUTS_DIR / RESULTS_DIR / SCENARIOS_PATH   # pathlib paths
METRIC_WEIGHTS = {...}        # for Conciseness & Clarity blend
```
API key is read from env via `os.environ["ANTHROPIC_API_KEY"]` (or `.env` through
`python-dotenv`). Never hardcoded; never logged.

**`requirements.txt`** (pinned): `anthropic`, `python-dotenv`, plus report tooling
(`reportlab` or `markdown`+`weasyprint`) and optional `matplotlib` for charts.

---

## 3. Part 1 — Email Generation Assistant

**Covers PRD F1–F7.**

`prompts.py`
- `ADVANCED_SYSTEM` — role: senior executive-communications assistant.
- `ADVANCED_USER_TEMPLATE` — few-shot (2 input→email exemplars across tones) +
  chain-of-thought instruction: plan privately in `<thinking>`, emit final in `<email>`.
- `NAIVE_TEMPLATE` — one bare line: intent / facts / tone, no scaffold. The control;
  do not improve it.
- `format_facts(facts: list[str]) -> str` helper.

`generate.py`
```python
class EmailAssistant:
    def __init__(self, client, model=config.MODEL): ...
    def generate(self, intent: str, key_facts: list[str], tone: str,
                 strategy: str = "advanced") -> str:
        """Build prompt for `strategy`, call Claude, parse out <email>, log raw, return body."""
```
- `_parse_email(raw) -> str` strips `<thinking>` and returns only `<email>` contents.
- Every call appends raw request/response to `data/outputs/<timestamp>-<strategy>.json`
  (no API key in the log).
- CLI: `python -m src.generate --intent ... --facts ... --tone ... --strategy advanced`.

**Smoke test:** generate one email each strategy; confirm advanced output has no leaked
`<thinking>` and includes all facts.

---

## 4. Part 2 — Evaluation with 3 custom metrics

**Covers PRD E1–E7.**

`data/scenarios.json` — 10 scenarios, fictional entities only. Each:
```json
{ "id": 1, "intent": "...", "key_facts": ["...","..."], "tone": "formal",
  "reference_email": "..." }
```
Spread across tones (formal, casual, urgent, empathetic, apologetic, persuasive…) and
intents (follow-up, RFP request, decline, intro, escalation, reminder…).

`metrics.py` — each returns a 0–1 score + supporting detail; formulas match PRD:
1. **`fact_recall(email, key_facts, client)`** — per-fact LLM judge "present & accurate?";
   score = included / total. Penalizes dropped *and* distorted facts.
2. **`tone_accuracy(email, tone, reference, client)`** — rubric judge 1–5 with explicit
   anchors, reference passed for calibration; normalized `(score-1)/4`.
3. **`conciseness_clarity(email, reference, client)`** — blend of length ratio vs.
   reference (penalty >1.5×), mean sentence length, filler-phrase density, and a 0–1 LLM
   clarity rating, weighted by `config.METRIC_WEIGHTS`.
- All judge calls: temp 0, strict JSON, `_judge_json(prompt)` wrapper with retry +
  schema validation on parse failure.
- **Validity unit checks** (`test_metrics`): each metric must score a known-good email
  higher than a known-bad one — this proves the metric discriminates.

`evaluate.py`
```python
def run() -> None:
    """For each scenario × {advanced, naive}: generate, score 3 metrics, collect rows.
       Write results/eval_results.csv and results/eval_results.json."""
```
- CSV: one row per scenario×strategy×metric (60 rows = 10×2×3).
- JSON: `{metric_definitions, per_scenario_scores, averages_by_strategy}` — the raw-data
  deliverable; metric definitions/logic embedded so the file is self-describing.
- Reuse logged generations where possible to limit API spend.

---

## 5. Part 3 — Comparison & analysis

**Covers PRD A1–A3.**

`analyze.py`
```python
def analyze() -> None:
    """Load results, compute per-metric + overall averages and deltas for both strategies,
       identify the loser's worst metric/scenario, write results/summary.md."""
```
`summary.md` (one page) answers the three required questions:
1. Which strategy won — by metric and overall (table + optional bar chart).
2. Biggest failure mode of the loser — data-backed (expect naive to drop/garble facts and
   drift on tone; cite the specific low-scoring scenarios).
3. Production recommendation, justified with the metric numbers; note cost/latency caveat
   since both use the same base model.

---

## 6. README + final report

- **README:** prereqs, `pip install -r requirements.txt`, set `ANTHROPIC_API_KEY` (or `.env`),
  run order (generate → evaluate → analyze), where outputs land, known limitations.
- **`report/final_report.pdf`** assembles: the exact prompt template (verbatim from
  `prompts.py`), the 3 metric definitions + logic, the raw eval data (CSV/JSON excerpt),
  and the Section 3 summary.

---

## 7. Build order & milestones

1. Scaffold repo, `.gitignore`, `.env.example`, `config.py`, `requirements.txt`.
2. `prompts.py` (advanced + naive) → `generate.py` → smoke test on 1 scenario.
3. Author 10 scenarios + reference emails in `scenarios.json`.
4. `metrics.py` (3 metrics) + validity unit checks (good > bad).
5. `evaluate.py` → run full 10×2 matrix → `eval_results.{csv,json}`.
6. `analyze.py` → `summary.md`.
7. README + assemble `final_report.pdf`.
8. **Verification pass:** metric validity holds, hand-check 2–3 judge calls, confirm
   averages math, confirm clean-clone run with only the API key set.

Each part is scaffolded via `/create-spec <n> <slug>` on a `feature/<slug>` branch.

---

## 8. Risks & mitigations

| Risk | Mitigation |
|------|-----------|
| LLM-judge noise | Rubrics, temp 0, reference anchoring, optional 2-run averaging. |
| Self-evaluation bias | Same model judges its family — stated as a report limitation. |
| Cost/latency of longer advanced prompt | Acknowledge tradeoff in recommendation. |
| Judge JSON parse failures | Retry + schema validation in `_judge_json`. |
| Non-reproducibility | Pin model + temperature; log raw outputs to `data/outputs/`. |
| Secret leakage | Key from env only; never logged/committed; `.env` git-ignored. |