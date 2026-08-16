"""Measure the clock the product is judged by, not the transport clock.

`goal.md` section 3 sets the bar on what the person perceives: an
acknowledgement or the start of visible action at p50 <= 1.0 s and p95 <= 2.0 s,
and a simple action complete and verified at p50 <= 2.5 s. The existing budget
gate measures transport deadlines per request type, which is a different clock:
it never asks how long a person waits before BAXY says or does anything.

This measures the first signal end to end over the real sidecar: from handing a
request to the mind until the first user-visible content exists for that turn --
a reply, a clarifying question, or a decided action ready to dispatch.

Read-only. It decides turns and never dispatches an operation, so no effect is
executed on the machine.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
for path in (REPO, REPO / "src", REPO / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from scripts.baxy_runtime_config import (  # noqa: E402
    add_runtime_arguments,
    resolve_runtime_from_args,
)
from scripts.measure_mind_budget import (  # noqa: E402
    JsonLineProcess,
    PROFILE_LIMITS,
    current_core_capabilities,
    discover_core,
    sidecar_environment,
    write_json_atomic,
)

DEFAULT_OUTPUT = REPO / "artifacts/product/first_signal_latency.json"

# Section 3 targets, in seconds.
FIRST_SIGNAL_P50_TARGET = 1.0
FIRST_SIGNAL_P95_TARGET = 2.0

# A spread of everyday requests across the three languages and across the
# shapes a person actually produces: a direct action, a read, a question, small
# talk and something outside the catalogue.
REQUESTS: tuple[tuple[str, str, str], ...] = (
    ("act-es-01", "es", "Sube el volumen al cuarenta por ciento."),
    ("act-es-02", "es", "Silencia el audio del computador."),
    ("act-es-03", "es", "Crea una nota Faro con contenido luz."),
    ("act-es-04", "es", "Baja el brillo de la pantalla."),
    ("read-es-01", "es", "Cuanta bateria le queda al equipo?"),
    ("read-es-02", "es", "Como esta la conexion de red?"),
    ("read-es-03", "es", "Que hora es ahora?"),
    ("act-en-01", "en", "Mute the computer audio."),
    ("act-en-02", "en", "Set the volume to seventy percent."),
    ("read-en-01", "en", "How much free disk space is left?"),
    ("read-en-02", "en", "What is the current CPU load?"),
    ("chat-es-01", "es", "Cuentame un chiste corto."),
    ("chat-en-01", "en", "What do you think about pineapple on pizza?"),
    ("sp-01", "spanglish", "Pon el volumen del speaker al treinta."),
    ("sp-02", "spanglish", "Check el estado del wifi."),
    ("out-es-01", "es", "Riega las plantas del balcon."),
    ("out-en-01", "en", "Walk the dog around the block."),
)


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return round(ordered[0], 3)
    position = fraction * (len(ordered) - 1)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return round(ordered[lower] * (1 - weight) + ordered[upper] * weight, 3)


def measure(runtime: Any, capabilities: list[dict[str, Any]]) -> dict[str, Any]:
    limits = PROFILE_LIMITS["gpu"]
    start = time.perf_counter()
    client = JsonLineProcess(
        [str(runtime.python), "-u", "-X", "utf8", "-m", "baxy_mind"],
        environment=sidecar_environment(
            runtime,
            gpu_layers=runtime.gpu_layers,
            llm_http_timeout=limits["llm_http"],
        ),
        cwd=REPO,
    )
    records: list[dict[str, Any]] = []
    try:
        hello = client.next_message(limits["handshake"])
        if hello.get("type") != "hello":
            raise RuntimeError("sidecar did not greet")
        ready = client.request(
            {
                "type": "catalog.configure",
                "id": "catalog-first-signal",
                "capabilities": capabilities,
            },
            limits["handshake"],
        )
        if ready.get("type") != "catalog.ready":
            raise RuntimeError("catalogue rejected")
        cold_start = round(time.perf_counter() - start, 3)

        for case_id, language, text in REQUESTS:
            begin = time.perf_counter()
            reply = client.request(
                {
                    "type": "turn.decide",
                    "id": f"first-signal-{case_id}",
                    "text": text,
                    "history": [],
                },
                limits["turn.decide"],
            )
            seconds = time.perf_counter() - begin
            visible = bool(
                str(reply.get("reply") or "").strip()
                or str(reply.get("question") or "").strip()
                or reply.get("operation")
                or reply.get("effectOperations")
            )
            records.append(
                {
                    "case_id": case_id,
                    "language": language,
                    "kind": reply.get("kind"),
                    "first_signal_seconds": round(seconds, 3),
                    "has_visible_signal": visible,
                }
            )
    finally:
        client.close(graceful_message=None, timeout=15.0)

    latencies = [record["first_signal_seconds"] for record in records]
    p50 = _percentile(latencies, 0.5)
    p95 = _percentile(latencies, 0.95)
    return {
        "cold_start_seconds": cold_start,
        "requests": len(records),
        "silent_turns": sum(1 for r in records if not r["has_visible_signal"]),
        "first_signal_seconds": {
            "p50": p50,
            "p95": p95,
            "max": round(max(latencies), 3) if latencies else 0.0,
            "mean": round(statistics.fmean(latencies), 3) if latencies else 0.0,
        },
        "targets": {
            "p50_maximum": FIRST_SIGNAL_P50_TARGET,
            "p95_maximum": FIRST_SIGNAL_P95_TARGET,
        },
        "meets_p50_target": p50 <= FIRST_SIGNAL_P50_TARGET,
        "meets_p95_target": p95 <= FIRST_SIGNAL_P95_TARGET,
        "records": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    add_runtime_arguments(parser)
    parser.add_argument("--core", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    runtime = resolve_runtime_from_args(args)
    capabilities = current_core_capabilities(discover_core(args.core))
    result = measure(runtime, capabilities)
    report = {
        "schema": "baxy.first-signal-latency.v1",
        "clock": (
            "from handing the request to the mind until the first user-visible "
            "content exists for that turn"
        ),
        "authority": "read-only turn decisions; no operation dispatched",
        **result,
    }
    write_json_atomic(args.output, report)
    summary = {k: v for k, v in report.items() if k not in {"records"}}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if result["meets_p50_target"] and result["meets_p95_target"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
