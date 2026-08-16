"""Decompose one turn into the model calls it actually makes, and time each.

R132 measured that the model finishes writing a conversational reply in 0.918 s
at p95 on this machine while the product takes 2.668 s to its first signal, so
roughly 1.75 s is spent by the turn machinery rather than by writing. It named
the next measurement: which call costs what.

The instrument is a **local proxy** between the sidecar and llama-server. The
sidecar is driven exactly as it runs in production -- same process, same
prompts, same order, no runtime code changed -- and every chat completion it
issues is forwarded verbatim while its duration and its system prompt are
recorded. The system prompt is what names the call: the turn policy, the
semantic effect guard, the effect counter, the language detector, the operation
compatibility verifier and the conversation reply each carry their own.

Read-only. It decides turns and never dispatches an operation.
"""

from __future__ import annotations

import argparse
import http.server
import json
import socket
import statistics
import sys
import threading
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

from experiments.mind_router_spike.probe_native_tool_contract_ceiling import (  # noqa: E402
    _start_server,
    _stop_server,
)

DEFAULT_OUTPUT = (
    REPO / "artifacts/development/turn_call_decomposition_20260812.json"
)

# The shapes that miss the first-signal bar: everything the deterministic
# recogniser does not resolve, so the model has to decide and then write.
REQUESTS: tuple[tuple[str, str], ...] = (
    ("es-knowledge", "Explicame en dos frases que es la fotosintesis."),
    ("es-opinion", "Que te parece el pan recien hecho por la manana?"),
    ("es-unsupported", "Riega los geranios del balcon."),
    ("es-checkin", "Estoy bastante cansado hoy."),
    ("en-knowledge", "Tell me in two sentences what a taskbar is."),
    ("en-unsupported", "Book an uber to the airport."),
    ("en-curious", "Tell me something odd about walnut trees."),
    ("spanglish-mixed", "Cuentame algo curioso about los rose bushes."),
)

# Each call is named by the opening of its system prompt. Anything unmatched is
# reported verbatim rather than bucketed, so a call cannot hide in "other".
_CALL_NAMES: tuple[tuple[str, str], ...] = (
    ("Selecciona una operacion candidata", "single_effect_selector"),
    ("Verifica estrictamente si la unica operacion", "operation_compatibility"),
    ("La entrada es una sola clausula positiva", "compound_clause_compatibility"),
    ("Cuenta solo los efectos atomicos", "effect_count_verifier"),
    ("Clasifica solamente el idioma", "response_language"),
    ("Identify only the language", "response_language"),
)

_CALLS: list[dict[str, Any]] = []
_CALLS_LOCK = threading.Lock()


def _fold(value: str) -> str:
    import unicodedata

    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )


def _name_call(payload: dict[str, Any]) -> str:
    messages = payload.get("messages") or []
    system = ""
    for message in messages:
        if message.get("role") == "system":
            system = str(message.get("content") or "")
            break
    folded = _fold(system)
    for prefix, name in _CALL_NAMES:
        if folded.startswith(prefix):
            return name
    if payload.get("tools"):
        return "turn_policy_native_tools"
    if not system:
        return "no_system_prompt"
    return f"unnamed:{folded[:48]}"


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _make_handler(upstream: str) -> type[http.server.BaseHTTPRequestHandler]:
    class Handler(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *_: Any) -> None:  # noqa: D102 - silence the proxy
            return

        def do_GET(self) -> None:  # noqa: N802 - http.server contract
            """Pass health and model probes straight through, untimed.

            The sidecar's startup does more than chat completions; a proxy that
            only forwards POST turns the handshake into a 501 and the catalogue
            never becomes ready.
            """

            try:
                with urllib.request.urlopen(
                    f"{upstream}{self.path}", timeout=120.0
                ) as response:
                    answer = response.read()
                    status = response.status
            except Exception as error:  # noqa: BLE001 - proxy boundary
                answer = json.dumps({"error": str(error)}).encode("utf-8")
                status = 502
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(answer)))
            self.end_headers()
            self.wfile.write(answer)

        def do_POST(self) -> None:  # noqa: N802 - http.server contract
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length)
            try:
                payload = json.loads(body.decode("utf-8"))
            except ValueError:
                payload = {}
            name = _name_call(payload) if isinstance(payload, dict) else "unparsed"
            started = time.perf_counter()
            request = urllib.request.Request(
                f"{upstream}{self.path}",
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(request, timeout=120.0) as response:
                    answer = response.read()
                    status = response.status
            except Exception as error:  # noqa: BLE001 - proxy boundary
                answer = json.dumps({"error": str(error)}).encode("utf-8")
                status = 502
            seconds = time.perf_counter() - started
            with _CALLS_LOCK:
                _CALLS.append(
                    {
                        "call": name,
                        "seconds": round(seconds, 4),
                        "max_tokens": payload.get("max_tokens")
                        if isinstance(payload, dict)
                        else None,
                        "structured": bool(
                            isinstance(payload, dict)
                            and payload.get("response_format")
                        ),
                        # What the call has to read before it can write. If the
                        # primary decision is dominated by prompt processing
                        # rather than generation, a shorter shortlist cuts it
                        # directly and nothing else has to change.
                        "prompt_bytes": len(body),
                        "tool_count": len(payload.get("tools") or [])
                        if isinstance(payload, dict)
                        else 0,
                        "max_tokens_requested": payload.get("max_tokens")
                        if isinstance(payload, dict)
                        else None,
                        "finished_at": time.perf_counter(),
                    }
                )
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(answer)))
            self.end_headers()
            self.wfile.write(answer)

    return Handler


def run(output: Path, args: Any) -> dict[str, Any]:
    runtime = resolve_runtime_from_args(args)
    capabilities = current_core_capabilities(discover_core(args.core))
    limits = PROFILE_LIMITS["gpu"]

    server, upstream_port = _start_server(runtime, runtime.gguf)
    proxy_port = _free_port()
    proxy = http.server.ThreadingHTTPServer(
        ("127.0.0.1", proxy_port),
        _make_handler(f"http://127.0.0.1:{upstream_port}"),
    )
    thread = threading.Thread(target=proxy.serve_forever, daemon=True)
    thread.start()

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
                "id": "catalog-decomposition",
                "capabilities": capabilities,
            },
            limits["handshake"],
        )
        if ready.get("type") != "catalog.ready":
            raise RuntimeError(
                f"catalogue rejected: {json.dumps(ready, ensure_ascii=False)[:400]}"
            )
        # The handshake warms the model. Discard everything it spent so the
        # per-turn decomposition is not credited with startup work.
        with _CALLS_LOCK:
            _CALLS.clear()
        for case_id, text in REQUESTS:
            with _CALLS_LOCK:
                _CALLS.clear()
            started = time.perf_counter()
            reply = client.request(
                {
                    "type": "turn.decide",
                    "id": f"decomposition-{case_id}",
                    "text": text,
                    "history": [],
                },
                limits["turn.decide"],
            )
            total = time.perf_counter() - started
            with _CALLS_LOCK:
                calls = [
                    {key: value for key, value in call.items() if key != "finished_at"}
                    for call in _CALLS
                ]
            rows.append(
                {
                    "case_id": case_id,
                    "text": text,
                    "kind": reply.get("kind"),
                    "seconds_total": round(total, 4),
                    "seconds_in_model_calls": round(
                        sum(call["seconds"] for call in calls), 4
                    ),
                    "model_calls": len(calls),
                    "calls": calls,
                }
            )
            print(
                f"{case_id:<18} total={rows[-1]['seconds_total']:<7} "
                f"calls={len(calls)} "
                f"in_model={rows[-1]['seconds_in_model_calls']}",
                flush=True,
            )
    finally:
        client.close(graceful_message=None, timeout=15.0)
        proxy.shutdown()
        proxy.server_close()
        _stop_server(server)

    report = {
        "schema": "baxy.turn-call-decomposition.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "authority": (
            "development diagnostic; the sidecar runs unmodified behind a "
            "recording proxy. It decides turns and dispatches no operation."
        ),
        "effects_executed": 0,
        "summary": _summarise(rows),
        "rows": rows,
    }
    write_json_atomic(output, report)
    return report


def _median_field(rows: list[dict[str, Any]], name: str, field: str) -> Any:
    values = [
        call[field]
        for row in rows
        for call in row["calls"]
        if call["call"] == name and call.get(field) is not None
    ]
    return round(statistics.median(values), 1) if values else None


def _summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_call: dict[str, list[float]] = {}
    for row in rows:
        for call in row["calls"]:
            by_call.setdefault(call["call"], []).append(call["seconds"])
    totals = [row["seconds_total"] for row in rows]
    in_model = [row["seconds_in_model_calls"] for row in rows]
    return {
        "turns": len(rows),
        "seconds_total_p50": round(statistics.median(totals), 4) if totals else None,
        "seconds_total_max": round(max(totals), 4) if totals else None,
        "seconds_in_model_calls_p50": (
            round(statistics.median(in_model), 4) if in_model else None
        ),
        "model_calls_per_turn": {
            "min": min((row["model_calls"] for row in rows), default=0),
            "max": max((row["model_calls"] for row in rows), default=0),
        },
        "by_call": {
            name: {
                "count": len(values),
                "total_seconds": round(sum(values), 4),
                "median_seconds": round(statistics.median(values), 4),
                "max_seconds": round(max(values), 4),
                "median_prompt_bytes": _median_field(rows, name, "prompt_bytes"),
                "median_tool_count": _median_field(rows, name, "tool_count"),
            }
            for name, values in sorted(
                by_call.items(), key=lambda item: -sum(item[1])
            )
        },
        "note": (
            "seconds_total is the sidecar round trip; seconds_in_model_calls is "
            "the sum of the completions it issued. Calls that run concurrently "
            "make the sum exceed the wall clock, which is itself informative: "
            "it says the turn is already overlapping work."
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
