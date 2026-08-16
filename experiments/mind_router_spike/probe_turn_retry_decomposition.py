"""Per-inference decomposition of long retry turns in the frozen GPU workload.

Driver mode spawns the real product sidecar with ``--sidecar-trace``: that
child monkeypatches ``LlmRuntime._post`` to append one JSON line per wire
call (label, monotonic start/end, server timings, finish_reason, content
emptiness) without changing payloads, sampling, contracts or decisions.  The
driver correlates trace lines with each case's wall-clock window and reports
where the seconds of a retry turn physically go: first P attempts, thinking
drain, retry P, validators and reply generation.  No Core operation is
dispatched; no registered asset changes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
SRC = REPO / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from scripts.baxy_runtime_config import (  # noqa: E402
    DEFAULT_RUNTIME_MANIFEST,
    public_runtime_identity,
    resolve_runtime,
)
from scripts.measure_mind_budget import (  # noqa: E402
    DEFAULT_CORE_CANDIDATES,
    JsonLineProcess,
    PROFILE_LIMITS,
    build_workload,
    current_core_capabilities,
    discover_core,
    sidecar_environment,
    validate_reply,
    write_json_atomic,
)

DEFAULT_OUTPUT = (
    REPO / "artifacts" / "fixes" / "turn_retry_decomposition_20260730.json"
)
DEFAULT_CASES = ("turn-23", "turn-06", "turn-00", "turn-13")


def _wire_label(payload: dict[str, Any]) -> str:
    response_format = payload.get("response_format")
    if isinstance(response_format, dict):
        envelope = response_format.get("json_schema")
        if isinstance(envelope, dict):
            name = envelope.get("name")
            if isinstance(name, str) and name:
                return name
    grammar = payload.get("grammar")
    if isinstance(grammar, str) and grammar:
        digest = hashlib.sha256(grammar.encode("utf-8")).hexdigest()[:8]
        return f"gbnf:{digest}"
    return "chat"


def _run_trace_sidecar(trace_path: Path) -> int:
    from baxy_mind import __main__ as sidecar_module
    from baxy_mind.llm import LlmRuntime

    original_post = LlmRuntime._post
    lock_path = trace_path.with_suffix(".lock")
    del lock_path  # single-process writer; kept simple on purpose

    retry_expanded_raw = os.environ.get("BAXY_PROBE_RETRY_P_MAXTOK", "").strip()
    retry_expanded = int(retry_expanded_raw) if retry_expanded_raw else None
    dump_dir_raw = os.environ.get("BAXY_PROBE_DUMP_P_DIR", "").strip()
    dump_dir = Path(dump_dir_raw) if dump_dir_raw else None

    def tracing_post(
        self: LlmRuntime,
        payload: dict[str, Any],
        timeout: float | None = None,
        *,
        max_attempts: int = 2,
        cancellation: Any = None,
    ) -> dict[str, Any]:
        if (
            retry_expanded is not None
            and _wire_label(payload) == "baxy_turn_decision"
            and max(0, int(getattr(self, "_request_attempt", 0))) > 0
        ):
            payload = dict(payload)
            payload["max_tokens"] = retry_expanded
        if dump_dir is not None and _wire_label(payload) == "baxy_turn_decision":
            try:
                dump_dir.mkdir(parents=True, exist_ok=True)
                target = dump_dir / "p_payload.json"
                if not target.exists():
                    target.write_text(
                        json.dumps(payload, ensure_ascii=False, indent=1),
                        encoding="utf-8",
                    )
            except OSError:
                pass
        started_unix = time.time()
        started = time.perf_counter()
        error_text = None
        response: dict[str, Any] | None = None
        try:
            response = original_post(
                self,
                payload,
                timeout,
                max_attempts=max_attempts,
                cancellation=cancellation,
            )
            return response
        except BaseException as error:
            error_text = f"{type(error).__name__}"
            raise
        finally:
            elapsed = time.perf_counter() - started
            messages_blob = json.dumps(
                payload.get("messages"), ensure_ascii=False, sort_keys=True
            )
            record: dict[str, Any] = {
                "label": _wire_label(payload),
                "unix_start": started_unix,
                "elapsed_seconds": round(elapsed, 4),
                "messages_chars": len(messages_blob),
                "messages_sha256": hashlib.sha256(
                    messages_blob.encode("utf-8")
                ).hexdigest()[:16],
                "max_tokens": payload.get("max_tokens"),
                "temperature": payload.get("temperature"),
                "seed": payload.get("seed"),
                "error": error_text,
            }
            if isinstance(response, dict):
                timings = response.get("timings")
                if isinstance(timings, dict):
                    for key in (
                        "prompt_n",
                        "prompt_ms",
                        "predicted_n",
                        "predicted_ms",
                        "cache_n",
                    ):
                        record[key] = timings.get(key)
                choices = response.get("choices")
                if isinstance(choices, list) and choices:
                    choice = choices[0]
                    if isinstance(choice, dict):
                        record["finish_reason"] = choice.get("finish_reason")
                        message = choice.get("message")
                        if isinstance(message, dict):
                            content = message.get("content")
                            record["content_chars"] = (
                                len(content) if isinstance(content, str) else None
                            )
            try:
                with trace_path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            except OSError:
                pass

    LlmRuntime._post = tracing_post  # type: ignore[method-assign]
    try:
        return sidecar_module.main()
    finally:
        LlmRuntime._post = original_post  # type: ignore[method-assign]


def run(
    output: Path,
    case_ids: tuple[str, ...],
    settle_seconds: float = 0.0,
    retry_p_maxtok: int | None = None,
) -> dict[str, Any]:
    runtime = resolve_runtime(manifest_path=DEFAULT_RUNTIME_MANIFEST)
    capabilities = current_core_capabilities(
        discover_core(None, candidates=reversed(DEFAULT_CORE_CANDIDATES))
    )
    limits = PROFILE_LIMITS["gpu"]
    trace_path = output.with_suffix(".trace.jsonl")
    if trace_path.exists():
        trace_path.unlink()
    environment = sidecar_environment(
        runtime,
        gpu_layers=runtime.gpu_layers,
        llm_http_timeout=limits["llm_http"],
    )
    if retry_p_maxtok is not None:
        environment["BAXY_PROBE_RETRY_P_MAXTOK"] = str(retry_p_maxtok)
    dump_dir = os.environ.get("BAXY_PROBE_DUMP_P_DIR", "").strip()
    if dump_dir:
        environment["BAXY_PROBE_DUMP_P_DIR"] = dump_dir
    command = [
        str(runtime.python),
        "-u",
        "-X",
        "utf8",
        str(Path(__file__).resolve()),
        "--sidecar-trace",
        str(trace_path),
    ]
    spawn_started = time.perf_counter()
    client = JsonLineProcess(command, environment=environment, cwd=REPO)
    cases: list[dict[str, Any]] = []
    startup: dict[str, float] = {}
    try:
        hello = client.next_message(limits["handshake"])
        startup["spawn_to_hello_seconds"] = round(
            time.perf_counter() - spawn_started, 4
        )
        if hello.get("type") != "hello":
            raise RuntimeError("sidecar hello rejected")
        catalog_started = time.perf_counter()
        catalog = client.request(
            {
                "type": "catalog.configure",
                "id": "catalog-retry-decomposition",
                "capabilities": capabilities,
            },
            limits["handshake"],
        )
        startup["catalog_configure_seconds"] = round(
            time.perf_counter() - catalog_started, 4
        )
        if catalog.get("type") != "catalog.ready":
            raise RuntimeError("catalog handshake rejected")
        if settle_seconds > 0.0:
            time.sleep(settle_seconds)
        for item in build_workload():
            if item.request_type != "turn.decide" or item.case_id not in case_ids:
                continue
            window_start = time.time()
            begin = time.perf_counter()
            reply = client.request(item.message, limits["turn.decide"])
            elapsed = time.perf_counter() - begin
            cases.append(
                {
                    "case_id": item.case_id,
                    "window_unix_start": window_start,
                    "window_unix_end": time.time(),
                    "elapsed_seconds": round(elapsed, 4),
                    "kind": reply.get("kind"),
                    "turn_attempts": reply.get("turn_attempts"),
                    "validation_error": validate_reply(item, reply) or None,
                }
            )
    finally:
        client.close(
            graceful_message={"type": "shutdown", "id": "shutdown-retry-probe"},
            timeout=limits["shutdown"],
        )

    trace: list[dict[str, Any]] = []
    if trace_path.exists():
        with trace_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line:
                    trace.append(json.loads(line))

    for case in cases:
        start = case["window_unix_start"] - 0.05
        end = case["window_unix_end"] + 0.05
        rows = [
            row
            for row in trace
            if start <= row["unix_start"] <= end
        ]
        inference_total = sum(float(row["elapsed_seconds"]) for row in rows)
        case["inferences"] = [
            {
                key: row.get(key)
                for key in (
                    "label",
                    "messages_chars",
                    "messages_sha256",
                    "elapsed_seconds",
                    "prompt_n",
                    "cache_n",
                    "predicted_n",
                    "predicted_ms",
                    "prompt_ms",
                    "finish_reason",
                    "content_chars",
                    "temperature",
                    "seed",
                    "max_tokens",
                    "error",
                )
            }
            | {"offset_seconds": round(row["unix_start"] - case["window_unix_start"], 4)}
            for row in sorted(rows, key=lambda item: item["unix_start"])
        ]
        case["wire_calls"] = len(rows)
        case["sum_inference_seconds"] = round(inference_total, 4)
        case["non_overlapped_gap_estimate_seconds"] = None

    report = {
        "schema": "baxy.turn-retry-decomposition.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "runtime": public_runtime_identity(runtime),
        "startup": startup,
        "cases": cases,
        "trace_rows": len(trace),
    }
    write_json_atomic(output, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--case", action="append", dest="case_ids")
    parser.add_argument("--sidecar-trace", type=Path, default=None)
    parser.add_argument("--settle-seconds", type=float, default=0.0)
    parser.add_argument("--retry-p-maxtok", type=int, default=None)
    args = parser.parse_args()
    if args.sidecar_trace is not None:
        return _run_trace_sidecar(args.sidecar_trace)
    case_ids = tuple(args.case_ids) if args.case_ids else DEFAULT_CASES
    report = run(
        args.output,
        case_ids,
        settle_seconds=args.settle_seconds,
        retry_p_maxtok=args.retry_p_maxtok,
    )
    digest = [
        {
            "case_id": case["case_id"],
            "elapsed": case["elapsed_seconds"],
            "kind": case["kind"],
            "attempts": case["turn_attempts"],
            "wire_calls": case["wire_calls"],
            "sum_inference_seconds": case["sum_inference_seconds"],
        }
        for case in report["cases"]
    ]
    print(json.dumps(digest, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
