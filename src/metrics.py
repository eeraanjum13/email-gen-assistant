"""Three custom email-quality metrics: Fact Recall, Tone Accuracy, Conciseness & Clarity."""
import json
import re
import sys
from typing import Union

import anthropic

from src import config

FILLER_PHRASES = [
    "i hope this email finds you well",
    "i hope this message finds you well",
    "i hope you are doing well",
    "do not hesitate to",
    "please do not hesitate to",
    "please feel free to",
    "at your earliest convenience",
    "i am writing to",
    "i wanted to reach out",
    "i am reaching out to",
    "as per our conversation",
    "as discussed previously",
    "going forward",
    "thank you for your time and consideration",
    "should you have any questions",
    "if you have any questions or concerns",
]

_FACT_RECALL_PROMPT = """\
You are a fact-checking assistant. Given an email and a list of key facts, \
determine whether each fact appears in the email accurately.

Key facts:
{facts}

Email:
{email}

Return a JSON array with one object per fact:
[{{"fact": "...", "present": true/false, "accurate": true/false, "note": "..."}}]

Return only the JSON array, no other text."""

_TONE_ACCURACY_PROMPT = """\
You are an expert email reviewer assessing tone.

Requested tone: {tone}
Reference email (exemplary, score=5 baseline):
{reference}

Email to score:
{email}

Score the email's tone on a 1–5 rubric:
5 — Tone is consistently and naturally {tone} throughout.
4 — Mostly {tone}; minor lapses that don't undermine the message.
3 — Somewhat {tone} but inconsistent or mixed signals.
2 — Rarely {tone}; mostly a different register.
1 — Not {tone} at all; tone actively conflicts with intent.

Return JSON only: {{"rubric_score": <1-5>, "rationale": "<one sentence>"}}"""

_CLARITY_PROMPT = """\
You are assessing email clarity. Does the email communicate its purpose clearly and directly?

Email:
{email}

Return JSON only: {{"clarity_score": <0.0-1.0>, "rationale": "<one sentence>"}}"""


def _judge_json(
    prompt: str,
    client: anthropic.Anthropic,
    schema_keys: list[str],
    max_retries: int = 3,
) -> Union[dict, list]:
    """Call Claude as a judge and return parsed JSON, retrying on failure."""
    last_error: Exception | None = None
    for attempt in range(max_retries):
        response = client.messages.create(
            model=config.MODEL,
            max_tokens=512,
            temperature=config.JUDGE_TEMPERATURE,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        # Strip markdown fences
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        try:
            parsed = json.loads(raw)
            # For dict responses, validate required keys
            if isinstance(parsed, dict):
                missing = [k for k in schema_keys if k not in parsed]
                if missing:
                    raise ValueError(f"Missing keys: {missing}")
            return parsed
        except (json.JSONDecodeError, ValueError) as e:
            last_error = e
    raise RuntimeError(
        f"Judge failed to return valid JSON after {max_retries} attempts. Last error: {last_error}"
    )


def _programmatic_signals(email: str, reference: str) -> dict:
    """Compute length ratio, sentence length, and filler density without an API call."""
    def word_count(text: str) -> int:
        return len(text.split())

    def sentences(text: str) -> list[str]:
        return [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]

    email_words = max(1, word_count(email))
    ref_words = max(1, word_count(reference))

    # Length: penalise if email is longer than reference
    if email_words > ref_words:
        length_component = min(1.0, ref_words / email_words)
    else:
        length_component = 1.0

    # Sentence length: optimal ≤20 words; drops linearly to 0 at 40
    email_sentences = sentences(email)
    if email_sentences:
        mean_words = sum(len(s.split()) for s in email_sentences) / len(email_sentences)
    else:
        mean_words = 0
    sentence_component = max(0.0, 1.0 - (mean_words - 20) / 20)

    # Filler density
    email_lower = email.lower()
    filler_count = sum(1 for phrase in FILLER_PHRASES if phrase in email_lower)
    filler_component = max(0.0, 1.0 - filler_count / 5)

    return {
        "length_component": round(length_component, 4),
        "sentence_component": round(min(1.0, sentence_component), 4),
        "filler_component": round(filler_component, 4),
        "email_words": email_words,
        "ref_words": ref_words,
        "mean_sentence_words": round(mean_words, 1),
        "filler_count": filler_count,
    }


def fact_recall(email: str, key_facts: list[str], client: anthropic.Anthropic) -> dict:
    """Score fraction of key facts present and accurate in the email (0–1)."""
    facts_str = "\n".join(f"{i + 1}. {f}" for i, f in enumerate(key_facts))
    prompt = _FACT_RECALL_PROMPT.format(facts=facts_str, email=email)
    per_fact = _judge_json(prompt, client, schema_keys=[], max_retries=3)
    if not isinstance(per_fact, list):
        raise RuntimeError("fact_recall judge did not return a JSON array")
    included = sum(1 for f in per_fact if f.get("present") and f.get("accurate"))
    score = included / max(1, len(key_facts))
    return {
        "score": round(score, 4),
        "included": included,
        "total": len(key_facts),
        "per_fact": per_fact,
    }


def tone_accuracy(
    email: str, tone: str, reference: str, client: anthropic.Anthropic
) -> dict:
    """Score how well the email matches the requested tone (0–1)."""
    prompt = _TONE_ACCURACY_PROMPT.format(tone=tone, reference=reference, email=email)
    result = _judge_json(prompt, client, schema_keys=["rubric_score", "rationale"])
    rubric = int(result["rubric_score"])
    score = (rubric - 1) / 4
    return {
        "score": round(score, 4),
        "rubric_score": rubric,
        "rationale": result.get("rationale", ""),
    }


def conciseness_clarity(
    email: str, reference: str, client: anthropic.Anthropic
) -> dict:
    """Score conciseness and clarity as a weighted blend of programmatic + LLM signals (0–1)."""
    signals = _programmatic_signals(email, reference)
    prompt = _CLARITY_PROMPT.format(email=email)
    clarity_result = _judge_json(prompt, client, schema_keys=["clarity_score"])
    clarity_score = float(clarity_result["clarity_score"])

    w = config.METRIC_WEIGHTS
    score = (
        w["length_ratio"] * signals["length_component"]
        + w["sentence_length"] * signals["sentence_component"]
        + w["filler_density"] * signals["filler_component"]
        + w["clarity"] * clarity_score
    )
    return {
        "score": round(min(1.0, score), 4),
        "components": {
            **signals,
            "clarity_score": round(clarity_score, 4),
            "clarity_rationale": clarity_result.get("rationale", ""),
        },
    }


def run_validity_checks(client: anthropic.Anthropic) -> None:
    """Assert each metric scores a known-good email higher than a known-bad email."""
    key_facts = ["Project Alpha", "deadline is August 31", "budget is $50,000", "lead is Jordan Mills"]
    reference = (
        "Hi team,\n\nProject Alpha kicks off this Monday. Jordan Mills will lead the effort. "
        "Our deadline is 31 August and the approved budget is $50,000. "
        "Please review the brief before our 9 AM meeting.\n\nBest,\nSam"
    )
    good_email = (
        "Hi team,\n\nProject Alpha is officially underway. Jordan Mills is leading the project "
        "with a deadline of 31 August and a $50,000 budget. "
        "Please review the attached brief ahead of Monday's kickoff.\n\nBest,\nSam"
    )
    bad_email_facts = (
        "Hi team,\n\nJust a quick note to say we have a new project starting soon. "
        "Details to follow — stay tuned!\n\nThanks"
    )
    bad_email_tone = (
        "YO TEAM!!! we got a project lol its called alpha or something idk just show up monday ok?? "
        "budget is like a lot of money. JORDAN is the boss ig"
    )
    bad_email_clarity = (
        "I am writing to inform you that, going forward, as per our previous discussions and "
        "in alignment with the strategic objectives we have been working towards, "
        "there is a project which, at your earliest convenience, we hope you will be able to "
        "engage with and contribute to in a meaningful and impactful way. "
        "Do not hesitate to reach out should you have any questions or concerns at all. "
        "I hope this email finds you well."
    )

    results = []

    # Fact Recall
    good_fr = fact_recall(good_email, key_facts, client)["score"]
    bad_fr = fact_recall(bad_email_facts, key_facts, client)["score"]
    passed = good_fr > bad_fr
    results.append(("Fact Recall", passed, good_fr, bad_fr))

    # Tone Accuracy
    good_ta = tone_accuracy(good_email, "professional", reference, client)["score"]
    bad_ta = tone_accuracy(bad_email_tone, "professional", reference, client)["score"]
    passed = good_ta > bad_ta
    results.append(("Tone Accuracy", passed, good_ta, bad_ta))

    # Conciseness & Clarity
    good_cc = conciseness_clarity(good_email, reference, client)["score"]
    bad_cc = conciseness_clarity(bad_email_clarity, reference, client)["score"]
    passed = good_cc > bad_cc
    results.append(("Conciseness & Clarity", passed, good_cc, bad_cc))

    all_passed = True
    for name, passed, good_score, bad_score in results:
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_passed = False
        print(f"{status}  {name}: good={good_score:.3f}  bad={bad_score:.3f}")

    if not all_passed:
        raise AssertionError("One or more validity checks failed.")


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    load_dotenv()
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY not set.", file=sys.stderr)
        sys.exit(1)
    client = anthropic.Anthropic(api_key=api_key)
    run_validity_checks(client)
