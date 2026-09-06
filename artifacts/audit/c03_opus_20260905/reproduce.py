"""Read-only probes of C03 helpers; no model requests or Windows effects."""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from baxy_mind import llm  # noqa: E402


def main() -> None:
    rows = []
    for text in (
        "Good afternoon", "Good morning", "define DNS in one sentence",
        "Hi again", "hey, close Paint", "hey, what can you do",
    ):
        language = llm._message_response_language(text)
        situation = {"kind": "welcome", "polarity": "success"}
        payload = llm._compose_situation_payload(situation, language, text)
        rows.append({
            "request": text,
            "language_selected": language,
            "greeting_selected": llm._looks_like_greeting_ask(text),
            "payload": payload,
            "user_content": llm._compose_user_content(
                text, {"situation": payload}, "LANG=" + language
            ),
        })
    rows.append({
        "case": "no observed close effect",
        "payload": llm._compose_situation_payload(
            {"kind": "conversation", "polarity": "success"}, "en", "close that"
        ),
    })
    rows.append({
        "case": "network observation missing online/connected",
        "payload": llm._compose_situation_payload(
            {
                "kind": "result", "polarity": "success",
                "operation": "network.status", "observed": {"interfaceCount": 2},
            },
            "en", "are you connected?",
        ),
    })
    print(json.dumps(rows, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
