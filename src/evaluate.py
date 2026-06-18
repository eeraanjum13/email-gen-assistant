"""Evaluation runner: 10 scenarios × 2 strategies × 3 metrics → CSV + JSON results."""
import csv
import json
import os
import sys
from collections import defaultdict

import anthropic
from typing import Union

from src import config
from src.generate import EmailAssistant
from src.metrics import fact_recall, tone_accuracy, conciseness_clarity

METRIC_DEFINITIONS = {
    "fact_recall": {
        "name": "Fact Recall",
        "formula": "included_facts / total_facts",
        "logic": (
            "LLM-as-judge checks each key fact for presence and accuracy. "
            "A fact counts only if both present=true and accurate=true. "
            "Penalises omitted and distorted facts equally."
        ),
    },
    "tone_accuracy": {
        "name": "Tone Accuracy",
        "formula": "(rubric_score - 1) / 4",
        "logic": (
            "LLM-as-judge scores the email 1–5 against a rubric with explicit anchors "
            "for the requested tone. The reference email is supplied as a calibration anchor. "
            "Score normalised to 0–1."
        ),
    },
    "conciseness_clarity": {
        "name": "Conciseness & Clarity",
        "formula": "0.30*length_ratio + 0.20*sentence_length + 0.20*filler_density + 0.30*clarity",
        "logic": (
            "Blend of programmatic signals (length ratio vs reference, mean sentence length, "
            "filler-phrase density) and an LLM clarity rating (0–1). "
            "Weights from config.METRIC_WEIGHTS."
        ),
    },
}


def _load_scenarios() -> list[dict]:
    """Load and validate scenarios from data/scenarios.json."""
    path = config.SCENARIOS_PATH
    if not path.exists():
        raise FileNotFoundError(f"Scenarios file not found: {path}")
    with path.open() as f:
        scenarios = json.load(f)
    required_keys = {"id", "intent", "key_facts", "tone", "reference_email"}
    for s in scenarios:
        missing = required_keys - s.keys()
        if missing:
            raise ValueError(f"Scenario {s.get('id')} missing keys: {missing}")
    return scenarios


def _find_existing_log(scenario_id: int, strategy: str) -> Union[str, None]:
    """Return parsed_email from an existing log file for this scenario+strategy, or None."""
    if not config.OUTPUTS_DIR.exists():
        return None
    tag = f"scenario{scenario_id}-{strategy}"
    for path in config.OUTPUTS_DIR.glob(f"*-{strategy}.json"):
        try:
            data = json.loads(path.read_text())
            # Check if this log was tagged for this scenario
            prompt_used = data.get("prompt_used", {})
            messages = prompt_used.get("messages", [])
            if messages:
                content = messages[0].get("content", "")
                # Look for scenario id marker in the prompt
                if f"[scenario_id:{scenario_id}]" in content:
                    return data.get("parsed_email")
        except (json.JSONDecodeError, KeyError):
            continue
    return None


def _write_csv(rows: list[dict]) -> None:
    """Write eval results to results/eval_results.csv."""
    config.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = config.RESULTS_DIR / "eval_results.csv"
    fieldnames = ["scenario_id", "strategy", "metric", "score", "detail"]
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {path}")


def _write_json(rows: list[dict], scenarios: list[dict]) -> None:
    """Write self-describing results JSON to results/eval_results.json."""
    config.RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    # Build per-scenario scores
    per_scenario: dict = defaultdict(lambda: defaultdict(dict))
    for row in rows:
        sid = row["scenario_id"]
        strat = row["strategy"]
        metric = row["metric"]
        per_scenario[sid][strat][metric] = {"score": row["score"], "detail": row["detail"]}

    # Compute averages by strategy
    metric_names = ["fact_recall", "tone_accuracy", "conciseness_clarity"]
    strategies = ["advanced", "naive"]
    averages: dict = {}
    for strat in strategies:
        strat_rows = [r for r in rows if r["strategy"] == strat]
        averages[strat] = {}
        for metric in metric_names:
            metric_scores = [r["score"] for r in strat_rows if r["metric"] == metric]
            averages[strat][metric] = round(sum(metric_scores) / len(metric_scores), 4) if metric_scores else 0.0
        all_scores = [r["score"] for r in strat_rows]
        averages[strat]["overall"] = round(sum(all_scores) / len(all_scores), 4) if all_scores else 0.0

    output = {
        "metric_definitions": METRIC_DEFINITIONS,
        "per_scenario_scores": dict(per_scenario),
        "averages_by_strategy": averages,
    }
    path = config.RESULTS_DIR / "eval_results.json"
    path.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    print(f"Wrote results to {path}")


def run(client: anthropic.Anthropic) -> None:
    """Run 10 × 2 evaluation matrix and write results."""
    scenarios = _load_scenarios()
    assistant = EmailAssistant(client)
    rows: list[dict] = []

    for scenario in scenarios:
        sid = scenario["id"]
        intent = scenario["intent"]
        key_facts = scenario["key_facts"]
        tone = scenario["tone"]
        reference = scenario["reference_email"]

        for strategy in ["advanced", "naive"]:
            print(f"  Scenario {sid} / {strategy} ...", end=" ", flush=True)

            # Try to reuse existing generation
            email = _find_existing_log(sid, strategy)
            if email:
                print("(reused log)", end=" ", flush=True)
            else:
                # Tag the prompt so we can match it later
                tagged_intent = f"[scenario_id:{sid}] {intent}"
                email = assistant.generate(tagged_intent, key_facts, tone, strategy)

            # Score all 3 metrics
            fr = fact_recall(email, key_facts, client)
            ta = tone_accuracy(email, tone, reference, client)
            cc = conciseness_clarity(email, reference, client)

            rows.append({"scenario_id": sid, "strategy": strategy, "metric": "fact_recall",
                          "score": fr["score"], "detail": json.dumps({"included": fr["included"], "total": fr["total"]})})
            rows.append({"scenario_id": sid, "strategy": strategy, "metric": "tone_accuracy",
                          "score": ta["score"], "detail": json.dumps({"rubric_score": ta["rubric_score"], "rationale": ta["rationale"]})})
            rows.append({"scenario_id": sid, "strategy": strategy, "metric": "conciseness_clarity",
                          "score": cc["score"], "detail": json.dumps(cc["components"])})

            print(f"FR={fr['score']:.2f} TA={ta['score']:.2f} CC={cc['score']:.2f}")

    if len(rows) != 60:
        raise AssertionError(f"Expected 60 rows, got {len(rows)}")

    _write_csv(rows)
    _write_json(rows, scenarios)
    print("\nEvaluation complete.")


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY not set.", file=sys.stderr)
        sys.exit(1)
    client = anthropic.Anthropic(api_key=api_key)
    run(client)
