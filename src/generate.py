"""Email generation engine and CLI entry point."""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone

import anthropic

from src import config
from src.prompts import ADVANCED_SYSTEM, ADVANCED_USER_TEMPLATE, NAIVE_TEMPLATE, format_facts


class EmailAssistant:
    """Generates professional emails via Claude using advanced or naive prompting."""

    def __init__(self, client: anthropic.Anthropic, model: str = config.MODEL) -> None:
        self.client = client
        self.model = model

    def generate(
        self,
        intent: str,
        key_facts: list[str],
        tone: str,
        strategy: str = "advanced",
    ) -> str:
        """Generate an email and return the final body only."""
        if strategy == "advanced":
            temperature = config.GEN_TEMPERATURE
            user_content = ADVANCED_USER_TEMPLATE.format(
                intent=intent,
                key_facts=format_facts(key_facts),
                tone=tone,
            )
            request: dict = {
                "model": self.model,
                "max_tokens": config.MAX_TOKENS,
                "temperature": temperature,
                "system": ADVANCED_SYSTEM,
                "messages": [{"role": "user", "content": user_content}],
            }
        elif strategy == "naive":
            temperature = config.GEN_TEMPERATURE
            user_content = NAIVE_TEMPLATE.format(
                intent=intent,
                key_facts=", ".join(key_facts),
                tone=tone,
            )
            request = {
                "model": self.model,
                "max_tokens": config.MAX_TOKENS,
                "temperature": temperature,
                "messages": [{"role": "user", "content": user_content}],
            }
        else:
            raise ValueError(f"Unknown strategy: {strategy!r}. Use 'advanced' or 'naive'.")

        response = self.client.messages.create(**request)
        raw = response.content[0].text
        parsed = self._parse_email(raw, strategy)
        self._log(strategy, request, raw, parsed)
        return parsed

    def _parse_email(self, raw: str, strategy: str = "advanced") -> str:
        """Extract email body; strip thinking block for advanced strategy."""
        if strategy == "advanced":
            text = re.sub(r"<thinking>.*?</thinking>", "", raw, flags=re.DOTALL)
            match = re.search(r"<email>(.*?)</email>", text, flags=re.DOTALL)
            if not match:
                raise ValueError(
                    "Advanced response missing <email> tag. Raw output not returned to prevent leaking reasoning."
                )
            return match.group(1).strip()
        # naive — return raw text as-is
        return raw.strip()

    def _log(
        self,
        strategy: str,
        request_payload: dict,
        raw_response: str,
        parsed_email: str,
    ) -> None:
        """Write raw I/O to data/outputs/ — never includes the API key."""
        config.OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).isoformat()
        filename = f"{timestamp.replace(':', '-').replace('+', 'Z')}-{strategy}.json"
        # Strip any accidental key from payload copy
        safe_payload = {k: v for k, v in request_payload.items() if k != "api_key"}
        log_entry = {
            "timestamp": timestamp,
            "strategy": strategy,
            "model": self.model,
            "temperature": safe_payload.get("temperature"),
            "prompt_used": safe_payload,
            "raw_response": raw_response,
            "parsed_email": parsed_email,
        }
        path = config.OUTPUTS_DIR / filename
        path.write_text(json.dumps(log_entry, indent=2, ensure_ascii=False))


def main() -> None:
    """CLI: generate a single email and print to stdout."""
    parser = argparse.ArgumentParser(description="Generate a professional email via Claude.")
    parser.add_argument("--intent", required=True, help="Purpose of the email.")
    parser.add_argument("--facts", nargs="+", required=True, metavar="FACT", help="Key facts to include.")
    parser.add_argument("--tone", required=True, help="Desired tone (e.g. formal, empathetic).")
    parser.add_argument(
        "--strategy",
        default="advanced",
        choices=["advanced", "naive"],
        help="Prompting strategy (default: advanced).",
    )
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY is not set.", file=sys.stderr)
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)
    assistant = EmailAssistant(client)
    email = assistant.generate(args.intent, args.facts, args.tone, args.strategy)
    print(email)


if __name__ == "__main__":
    main()
