"""Measure whether streaming could close the first-signal p95, before building it.

The first-signal clock misses its bar at p95 2.668 s against 2.0 s, and the
cause is already isolated: 9 of 17 turns resolve deterministically at or under
0.071 s, while the 8 that need model-authored prose take 0.698 s to 2.957 s
because the turn waits for the prose to be complete before emitting anything.

Invariant 6 forbids a fixed visible reply, so an early acknowledgement cannot be
a constant -- "un momento..." is exactly the defect the invariant names. That
leaves streaming the model's own words. But BAXY's honesty guards run on the
complete text: R128 and R131 reject an invented reading, an assertion about a
machine never read, and a first-person claim of perception. Streaming raw tokens
would put a sentence on screen *before* those guards can reject it, which trades
a latency defect for a honesty defect and is not acceptable.

The only shape that keeps both is **sentence-level streaming**: emit a sentence
once it is complete and once it has passed the same guards. So the number that
decides the whole line is not time-to-first-token, it is **time to the first
complete sentence**, and whether that sentence can be judged on its own.

This measures all three clocks over the real llama-server on this machine, with
the same model and the same prompts the product uses. It changes nothing: no
runtime code is touched and no operation is executed.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
for path in (REPO, REPO / "src", REPO / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from scripts.baxy_runtime_config import (  # noqa: E402
    DEFAULT_RUNTIME_MANIFEST,
    resolve_runtime,
)
from scripts.measure_mind_budget import (  # noqa: E402
    PROFILE_LIMITS,
    sidecar_environment,
    write_json_atomic,
)

from experiments.mind_router_spike.probe_native_tool_contract_ceiling import (  # noqa: E402
    _start_server,
    _stop_server,
)


DEFAULT_OUTPUT = (
    REPO / "artifacts/development/streaming_first_signal_ceiling_20260812.json"
)

FIRST_SIGNAL_P95_TARGET = 2.0

# The conversation shapes that miss the bar: everything the deterministic
# recogniser does not resolve, which is where the model has to write prose.
PROMPTS: tuple[tuple[str, str], ...] = (
    ("es-knowledge", "Explicame en dos frases que es la fotosintesis."),
    ("es-opinion", "Que te parece el pan recien hecho por la manana?"),
    ("es-unsupported", "Riega los geranios del balcon."),
    ("es-checkin", "Estoy bastante cansado hoy."),
    ("en-knowledge", "Tell me in two sentences what a taskbar is."),
    ("en-opinion", "What do you think about pineapple on pizza?"),
    ("en-unsupported", "Book an uber to the airport."),
    ("en-curious", "Tell me something odd about walnut trees."),
    ("spanglish-mixed", "Cuentame algo curioso about los rose bushes."),
    ("es-counterfactual", "Que ocurriria si otra computadora perdiera su Wi-Fi?"),
)

# A sentence ends at a terminator followed by whitespace or end of text. This is
# deliberately conservative: an abbreviation would only delay the first signal,
# never emit an incomplete sentence.
_SENTENCE_END = re.compile(r"[.!?…](?=\s|$)|[\n\r]")


def _first_sentence_end(text: str) -> int | None:
    found = _SENTENCE_END.search(text)
    return found.end() if found is not None else None


def _stream_once(endpoint: str, prompt: str, timeout: float) -> dict[str, Any]:
    """One streaming completion, timing the three clocks that matter."""

    payload = {
        "messages": [
            {
                "role": "system",
                "content": (
                    "Responde de forma breve y natural en el idioma del mensaje."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.0,
        "seed": 0,
        "max_tokens": 160,
        "chat_template_kwargs": {"enable_thinking": False},
        "stream": True,
    }
    request = urllib.request.Request(
        f"{endpoint}/v1/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    first_token: float | None = None
    first_sentence: float | None = None
    text = ""
    with urllib.request.urlopen(request, timeout=timeout) as response:
        for raw in response:
            line = raw.decode("utf-8", errors="replace").strip()
            if not line.startswith("data:"):
                continue
            body = line[5:].strip()
            if body == "[DONE]":
                break
            try:
                chunk = json.loads(body)
            except ValueError:
                continue
            choices = chunk.get("choices") or []
            if not choices:
                continue
            piece = (choices[0].get("delta") or {}).get("content") or ""
            if not piece:
                continue
            if first_token is None:
                first_token = time.perf_counter() - started
            text += piece
            if first_sentence is None and _first_sentence_end(text) is not None:
                first_sentence = time.perf_counter() - started
    complete = time.perf_counter() - started
    end = _first_sentence_end(text)
    return {
        "seconds_to_first_token": round(first_token, 4) if first_token else None,
        "seconds_to_first_sentence": (
            round(first_sentence, 4) if first_sentence else None
        ),
        "seconds_to_complete": round(complete, 4),
        "first_sentence": text[:end].strip() if end is not None else "",
        "complete_text": text.strip(),
        "sentences": len(
            [part for part in _SENTENCE_END.split(text) if part.strip()]
        ),
    }


def run(output: Path) -> dict[str, Any]:
    runtime = resolve_runtime(manifest_path=DEFAULT_RUNTIME_MANIFEST)
    os.environ.update(
        sidecar_environment(
            runtime,
            gpu_layers=runtime.gpu_layers,
            llm_http_timeout=PROFILE_LIMITS["gpu"]["llm_http"],
        )
    )
    process, port = _start_server(runtime, runtime.gguf)
    endpoint = f"http://127.0.0.1:{port}"
    rows: list[dict[str, Any]] = []
    try:
        for case_id, prompt in PROMPTS:
            measured = {"case_id": case_id, "prompt": prompt}
            try:
                measured.update(_stream_once(endpoint, prompt, 60.0))
                measured["error"] = ""
            except Exception as exc:  # noqa: BLE001 - measurement boundary
                measured["error"] = f"{type(exc).__name__}: {exc}"[:300]
            rows.append(measured)
            print(
                f"{case_id:<20} token={measured.get('seconds_to_first_token')} "
                f"sentence={measured.get('seconds_to_first_sentence')} "
                f"complete={measured.get('seconds_to_complete')}",
                flush=True,
            )
    finally:
        _stop_server(process)

    report = {
        "schema": "baxy.streaming-first-signal-ceiling.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "authority": (
            "development diagnostic on this machine; changes no runtime code "
            "and executes no operation. It measures whether sentence-level "
            "streaming could close the first-signal p95, before anything is "
            "built for it."
        ),
        "effects_executed": 0,
        "summary": _summarise(rows),
        "rows": rows,
    }
    write_json_atomic(output, report)
    return report


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(len(ordered) * fraction)))
    return round(ordered[index], 4)


def _summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    def clock(key: str) -> dict[str, Any]:
        values = [row[key] for row in rows if not row["error"] and row.get(key)]
        return {
            "samples": len(values),
            "p50": round(statistics.median(values), 4) if values else None,
            "p95": _percentile(values, 0.95),
            "max": round(max(values), 4) if values else None,
            "meets_p95_target": (
                _percentile(values, 0.95) is not None
                and _percentile(values, 0.95) <= FIRST_SIGNAL_P95_TARGET
            ),
        }

    return {
        "prompts": len(rows),
        "errors": sum(1 for row in rows if row["error"]),
        "first_token": clock("seconds_to_first_token"),
        "first_sentence": clock("seconds_to_first_sentence"),
        "complete_prose": clock("seconds_to_complete"),
        "single_sentence_replies": sum(
            1 for row in rows if not row["error"] and row.get("sentences", 0) <= 1
        ),
        "why_single_sentence_matters": (
            "A reply that is one sentence long gains nothing from sentence-level "
            "streaming: its first sentence IS the complete prose. The gain is "
            "bounded by how many replies have a second sentence."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = run(args.output)
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
