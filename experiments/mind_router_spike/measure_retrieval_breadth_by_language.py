"""Measure how many candidates retrieval hands the decision, matched by language.

R134 saw "explicame en dos frases que es la fotosintesis" arrive at the decision
with 28 candidate operations while "tell me in two sentences what a taskbar is"
arrived with 2, and the three Spanish requests of that sample carried 28, 28 and
11 against 2, 9 and 2 for the English ones. Eight turns cannot tell whether that
is the language or the content, so it was recorded as a suspicion.

This separates the two the only way that works: **matched sets**. Every group
below is the same request written in Spanish, English and where natural
spanglish, so any difference in breadth inside a group is attributable to the
language and not to what was asked.

Breadth matters twice over. It is more than a second of latency on the call that
already blocks the first signal, and it is the number of chances the model gets
to choose wrong -- the failure R124 left with no gate able to repair it. A
request the catalogue cannot serve at all should arrive with none.

The sidecar runs unmodified behind the recording proxy of
``measure_turn_call_decomposition``. Read-only: it decides turns and dispatches
no operation. Nothing here authorises shortening the shortlist; that needs its
own measurement against the accuracy cuts, because a shortlist shortened by eye
drops the correct operation, which is how R103 failed.
"""

from __future__ import annotations

import argparse
import http.server
import json
import statistics
import sys
import threading
import time
from datetime import datetime, timezone
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

from experiments.mind_router_spike import (  # noqa: E402
    measure_turn_call_decomposition as decomposition,
)
from experiments.mind_router_spike.probe_native_tool_contract_ceiling import (  # noqa: E402
    _start_server,
    _stop_server,
)

DEFAULT_OUTPUT = (
    REPO / "artifacts/development/retrieval_breadth_by_language_20260813.json"
)

# Matched groups: same request, different language. "kind" records what the
# catalogue can honestly do with it, which is what makes a breadth number
# interpretable -- for pure knowledge the right breadth is zero.
GROUPS: tuple[tuple[str, str, tuple[tuple[str, str], ...]], ...] = (
    (
        "knowledge-photosynthesis",
        "knowledge",
        (
            ("es", "Explicame en dos frases que es la fotosintesis."),
            ("en", "Explain in two sentences what photosynthesis is."),
            ("spanglish", "Explicame in two sentences que es la photosynthesis."),
        ),
    ),
    (
        "knowledge-taskbar",
        "knowledge",
        (
            ("es", "Explicame en dos frases que es una barra de tareas."),
            ("en", "Tell me in two sentences what a taskbar is."),
        ),
    ),
    (
        "knowledge-thunder",
        "knowledge",
        (
            ("es", "Por que suena el trueno despues del relampago?"),
            ("en", "Why does thunder sound after the lightning?"),
        ),
    ),
    (
        "social-tired",
        "social",
        (
            ("es", "Estoy bastante cansado hoy."),
            ("en", "I am pretty tired today."),
        ),
    ),
    (
        "social-opinion",
        "social",
        (
            ("es", "Que opinas del pan recien hecho?"),
            ("en", "What do you think about freshly baked bread?"),
        ),
    ),
    (
        "outside-water-plants",
        "outside_catalogue",
        (
            ("es", "Riega las plantas del balcon."),
            ("en", "Water the plants on the balcony."),
            ("spanglish", "Riega las plants del balcon."),
        ),
    ),
    (
        "outside-taxi",
        "outside_catalogue",
        (
            ("es", "Pide un taxi para las ocho."),
            ("en", "Book a taxi for eight o'clock."),
        ),
    ),
    (
        "served-volume-down",
        "served",
        (
            ("es", "Baja el volumen a la mitad."),
            ("en", "Turn the volume down to half."),
            ("spanglish", "Baja el volume a la mitad."),
        ),
    ),
    (
        "served-battery",
        "served",
        (
            ("es", "Cuanta bateria le queda al equipo?"),
            ("en", "How much battery is left on the computer?"),
        ),
    ),
    (
        "served-notes",
        "served",
        (
            ("es", "Que notas tengo guardadas?"),
            ("en", "What notes do I have saved?"),
        ),
    ),
)


def run(output: Path, args: Any) -> dict[str, Any]:
    runtime = resolve_runtime_from_args(args)
    capabilities = current_core_capabilities(discover_core(args.core))
    limits = PROFILE_LIMITS["gpu"]

    server, upstream_port = _start_server(runtime, runtime.gguf)
    proxy_port = decomposition._free_port()
    proxy = http.server.ThreadingHTTPServer(
        ("127.0.0.1", proxy_port),
        decomposition._make_handler(f"http://127.0.0.1:{upstream_port}"),
    )
    threading.Thread(target=proxy.serve_forever, daemon=True).start()

    environment = sidecar_environment(
        runtime,
        gpu_layers=runtime.gpu_layers,
        llm_http_timeout=limits["llm_http"],
    )
    environment["BAXY_MIND_LLM_ENDPOINT"] = f"http://127.0.0.1:{proxy_port}"
    client = JsonLineProcess(
        [str(runtime.python), "-u", "-X", "utf8", "-m", "baxy_mind"],
        environment=environment,
        cwd=REPO,
    )
    rows: list[dict[str, Any]] = []
    try:
        hello = client.next_message(limits["handshake"])
        if hello.get("type") != "hello":
            raise RuntimeError("sidecar did not greet")
        ready = client.request(
            {
                "type": "catalog.configure",
                "id": "catalog-breadth",
                "capabilities": capabilities,
            },
            limits["handshake"],
        )
        if ready.get("type") != "catalog.ready":
            raise RuntimeError("catalogue rejected")
        for group, kind, cases in GROUPS:
            for language, text in cases:
                case_id = f"{group}:{language}"
                with decomposition._CALLS_LOCK:
                    decomposition._CALLS.clear()
                started = time.perf_counter()
                reply = client.request(
                    {
                        "type": "turn.decide",
                        "id": f"breadth-{case_id}",
                        "text": text,
                        "history": [],
                    },
                    limits["turn.decide"],
                )
                total = time.perf_counter() - started
                with decomposition._CALLS_LOCK:
                    calls = list(decomposition._CALLS)
                policy = [
                    call
                    for call in calls
                    if call["call"] == "turn_policy_native_tools"
                ]
                rows.append(
                    {
                        "group": group,
                        "kind": kind,
                        "language": language,
                        "text": text,
                        "turn_kind": reply.get("kind"),
                        "effect_operations": list(reply.get("effectOperations") or []),
                        # Zero means the deterministic recogniser resolved it or
                        # a deterministic conversation branch closed it, so the
                        # policy call never happened at all.
                        "candidates": policy[0]["tool_count"] if policy else 0,
                        "policy_seconds": policy[0]["seconds"] if policy else 0.0,
                        "policy_prompt_bytes": policy[0]["prompt_bytes"]
                        if policy
                        else 0,
                        "seconds_total": round(total, 4),
                        "model_calls": len(calls),
                    }
                )
                print(
                    f"{case_id:<40} cand={rows[-1]['candidates']:<4} "
                    f"policy={rows[-1]['policy_seconds']:<8} "
                    f"kind={rows[-1]['turn_kind']}",
                    flush=True,
                )
    finally:
        client.close(graceful_message=None, timeout=15.0)
        proxy.shutdown()
        proxy.server_close()
        _stop_server(server)

    report = {
        "schema": "baxy.retrieval-breadth-by-language.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "authority": (
            "development diagnostic; the sidecar runs unmodified behind a "
            "recording proxy. It decides turns and dispatches no operation, and "
            "it authorises no change to the shortlist."
        ),
        "effects_executed": 0,
        "summary": _summarise(rows),
        "rows": rows,
    }
    write_json_atomic(output, report)
    return report


def _summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_language: dict[str, list[int]] = {}
    by_kind: dict[str, list[int]] = {}
    for row in rows:
        by_language.setdefault(row["language"], []).append(row["candidates"])
        by_kind.setdefault(row["kind"], []).append(row["candidates"])

    gaps = []
    for group in {row["group"] for row in rows}:
        members = [row for row in rows if row["group"] == group]
        if len(members) < 2:
            continue
        widest = max(members, key=lambda row: row["candidates"])
        narrowest = min(members, key=lambda row: row["candidates"])
        gaps.append(
            {
                "group": group,
                "kind": members[0]["kind"],
                "widest": {
                    "language": widest["language"],
                    "candidates": widest["candidates"],
                },
                "narrowest": {
                    "language": narrowest["language"],
                    "candidates": narrowest["candidates"],
                },
                "gap": widest["candidates"] - narrowest["candidates"],
            }
        )

    def stats(values: list[int]) -> dict[str, Any]:
        return {
            "n": len(values),
            "median": statistics.median(values) if values else None,
            "max": max(values) if values else None,
            "zero": sum(1 for value in values if value == 0),
        }

    return {
        "turns": len(rows),
        "by_language": {name: stats(values) for name, values in sorted(by_language.items())},
        "by_kind": {name: stats(values) for name, values in sorted(by_kind.items())},
        "matched_gaps": sorted(gaps, key=lambda entry: -entry["gap"]),
        "knowledge_and_social_should_be_zero": (
            "A photosynthesis question and 'I am pretty tired today' cannot be "
            "served by any catalogue operation. Every candidate handed to the "
            "decision there is pure cost: latency on the call that blocks the "
            "first signal, and one more chance to choose wrong."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    add_runtime_arguments(parser)
    parser.add_argument("--core", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = run(args.output, args)
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
