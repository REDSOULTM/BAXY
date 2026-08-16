"""Reproduce la ruta conversacional exacta que usa el escritorio."""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from baxy_mind.llm import LlmRuntime


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    os.environ["BAXY_MIND_LLM_ENDPOINT"] = args.endpoint
    os.environ["BAXY_MIND_LLM_REQUEST_TIMEOUT"] = "4"
    runtime = LlmRuntime()
    rows = []
    for attempt in (1, 2, 3):
        started = time.perf_counter()
        reply, _ = runtime.chat(
            "Hola",
            history=[],
            tools=None,
            temperature=0.0,
            conversation_kind="social",
            response_language="es",
        )
        rows.append(
            {
                "attempt": attempt,
                "reply": reply,
                "elapsed_seconds": round(time.perf_counter() - started, 3),
            }
        )
    contextual_rows = []
    for attempt in (1, 2, 3):
        started = time.perf_counter()
        reply = runtime._resolve_contextual_answer(
            anchor="Hola. Estoy lista para ayudarte con este equipo.",
            current="Hola",
        )
        contextual_rows.append(
            {
                "attempt": attempt,
                "reply": reply,
                "elapsed_seconds": round(time.perf_counter() - started, 3),
            }
        )
    report = {
        "schema": "baxy-night-audit-social-greeting-repro-v1",
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "route": {
            "conversation_kind": "social",
            "response_language": "es",
            "temperature": 0.0,
        },
        "direct_social_runs": rows,
        "contextual_welcome_runs": contextual_rows,
    }
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
