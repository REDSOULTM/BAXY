"""Long-running, read-only BAXY core soak with periodic checkpoints."""

from __future__ import annotations

import argparse
import json
import math
import os
import queue
import shutil
import subprocess
import threading
import time
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psutil


FAST_CASES: list[tuple[str, dict[str, Any]]] = [
    ("system.time", {}),
    ("system.status", {"scope": "summary"}),
    ("audio.status", {}),
    ("network.status", {}),
    ("system.process.list", {"limit": 10, "sort": "memory"}),
    ("network.port.list", {"limit": 10}),
    ("input.keyboard.status", {}),
    ("notification.diagnose", {}),
    ("backup.list", {"limit": 10}),
    ("note.list", {"scope": "all", "limit": 10, "offset": 0}),
    ("task.list", {"status": "all", "includeDeleted": True, "limit": 10}),
    ("reminder.list", {"limit": 10}),
    ("routine.list", {"includeDeleted": True, "limit": 10}),
    ("filesystem.list", {"relativeDirectory": "", "limit": 10}),
    ("game.catalog.list", {"query": "", "limit": 10}),
    ("window.active", {}),
    ("app.installed", {"name": "Bloc de notas"}),
    ("media.status", {}),
]

HOURLY_CASES: list[tuple[str, dict[str, Any]]] = [
    ("system.application.crash.diagnose", {"hours": 2, "limit": 10}),
    (
        "filesystem.known.search",
        {
            "folder": "downloads",
            "query": "baxy-audit-no-match",
            "limit": 1,
        },
    ),
    ("filesystem.known.duplicates", {"folder": "downloads", "limit": 10}),
    ("peripheral.list", {"kind": "all"}),
    ("wifi.profile.list", {}),
    (
        "calendar.event.list",
        {
            "startUtc": "2026-07-27T00:00:00Z",
            "endUtc": "2026-07-28T00:00:00Z",
        },
    ),
    ("web.search", {"query": "Windows 11 calculator", "limit": 3}),
    ("network.ping", {"host": "127.0.0.1"}),
]


def read_line(pipe: Any, timeout: float) -> str:
    values: queue.Queue[str] = queue.Queue(maxsize=1)
    threading.Thread(target=lambda: values.put(pipe.readline()), daemon=True).start()
    try:
        line = values.get(timeout=timeout)
    except queue.Empty as exception:
        raise TimeoutError("core response timed out") from exception
    if not line:
        raise RuntimeError("core closed before response")
    return line


def percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, math.ceil(quantile * len(ordered)) - 1))
    return round(ordered[index], 4)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--until", required=True, help="ISO-8601 timestamp with offset")
    parser.add_argument("--interval-seconds", type=float, default=5.0)
    parser.add_argument("--segment-minutes", type=float, default=120.0)
    parser.add_argument("--checkpoint-seconds", type=float, default=60.0)
    args = parser.parse_args()
    core = args.core.resolve(strict=True)
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    deadline = datetime.fromisoformat(args.until)
    if deadline.tzinfo is None:
        raise SystemExit("--until must include a UTC offset")
    deadline_epoch = deadline.timestamp()
    data_root = (
        Path(os.environ["LOCALAPPDATA"])
        / "BAXY"
        / ("audit-soak-" + uuid.uuid4().hex)
    )
    data_root.mkdir(parents=True, exist_ok=False)

    process: subprocess.Popen[str] | None = None
    process_started = 0.0
    segment_index = 0
    catalog_count: int | None = None
    core_version: str | None = None
    calls = 0
    latencies: dict[str, list[float]] = defaultdict(list)
    statuses: dict[str, Counter[str]] = defaultdict(Counter)
    error_codes: dict[str, Counter[str]] = defaultdict(Counter)
    anomalies: list[dict[str, Any]] = []
    resource_samples: list[dict[str, Any]] = []
    segments: list[dict[str, Any]] = []
    started_utc = datetime.now(timezone.utc)
    started_perf = time.perf_counter()
    next_checkpoint = time.monotonic()
    next_resource = time.monotonic()
    next_hourly = time.monotonic()
    case_index = 0
    final_error: str | None = None

    def start_core() -> None:
        nonlocal process, process_started, segment_index, catalog_count, core_version
        segment_index += 1
        process = subprocess.Popen(
            [str(core)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            env={**os.environ, "BAXY_DATA_DIR": str(data_root)},
        )
        process_started = time.monotonic()
        hello_line = read_line(process.stdout, 15)
        hello = json.loads(hello_line)
        catalog_count = len(hello.get("capabilities") or [])
        core_version = hello.get("coreVersion")
        segments.append(
            {
                "index": segment_index,
                "pid": process.pid,
                "startedUtc": datetime.now(timezone.utc).isoformat(),
                "helloUtf8Bytes": len(hello_line.encode("utf-8")),
                "catalogCount": catalog_count,
                "exitCode": None,
                "stderrTail": "",
            }
        )

    def stop_core() -> None:
        nonlocal process
        if process is None:
            return
        if process.stdin is not None:
            process.stdin.close()
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.terminate()
            process.wait(timeout=5)
        stderr = process.stderr.read() if process.stderr is not None else ""
        segments[-1]["exitCode"] = process.returncode
        segments[-1]["stderrTail"] = stderr[-1024:]
        segments[-1]["endedUtc"] = datetime.now(timezone.utc).isoformat()
        process = None

    def call(operation: str, arguments: dict[str, Any]) -> None:
        nonlocal calls
        if process is None or process.stdin is None or process.stdout is None:
            raise RuntimeError("core is not running")
        request = {
            "type": "operation.request",
            "requestId": str(uuid.uuid4()),
            "missionId": str(uuid.uuid4()),
            "invocationId": str(uuid.uuid4()),
            "operation": operation,
            "arguments": arguments,
        }
        before = time.perf_counter()
        process.stdin.write(json.dumps(request, separators=(",", ":")) + "\n")
        process.stdin.flush()
        response = json.loads(read_line(process.stdout, 20))
        elapsed = time.perf_counter() - before
        calls += 1
        latencies[operation].append(elapsed)
        status = str(response.get("status"))
        statuses[operation][status] += 1
        error = response.get("errorCode")
        if error:
            error_codes[operation][str(error)] += 1
        if (
            response.get("type") != "operation.response"
            or status not in {"completed", "failed"}
            or response.get("effectMayHaveOccurred", False) is True
        ):
            anomalies.append(
                {
                    "atUtc": datetime.now(timezone.utc).isoformat(),
                    "operation": operation,
                    "kind": "unexpected_terminal_semantics",
                    "status": status,
                    "errorCode": error,
                    "effectMayHaveOccurred": response.get(
                        "effectMayHaveOccurred", False
                    ),
                }
            )

    def sample_resources() -> None:
        if process is None or process.poll() is not None:
            return
        observed = psutil.Process(process.pid)
        memory = observed.memory_info()
        resource_samples.append(
            {
                "atUtc": datetime.now(timezone.utc).isoformat(),
                "segment": segment_index,
                "pid": process.pid,
                "rssBytes": memory.rss,
                "privateBytes": getattr(memory, "private", None),
                "handles": observed.num_handles(),
                "threads": observed.num_threads(),
                "cpuSeconds": round(sum(observed.cpu_times()[:2]), 3),
            }
        )

    def report_value(running: bool) -> dict[str, Any]:
        aggregate: dict[str, Any] = {}
        for operation in sorted(set(latencies) | set(statuses)):
            values = latencies[operation]
            aggregate[operation] = {
                "calls": len(values),
                "statuses": dict(statuses[operation]),
                "errors": dict(error_codes[operation]),
                "minSeconds": round(min(values), 4) if values else None,
                "meanSeconds": (
                    round(sum(values) / len(values), 4) if values else None
                ),
                "p95Seconds": percentile(values, 0.95),
                "maxSeconds": round(max(values), 4) if values else None,
            }
        return {
            "schema": "baxy.audit.overnight-soak.v1",
            "running": running,
            "startedUtc": started_utc.isoformat(),
            "checkpointUtc": datetime.now(timezone.utc).isoformat(),
            "deadline": deadline.isoformat(),
            "elapsedSeconds": round(time.perf_counter() - started_perf, 3),
            "core": str(core),
            "coreVersion": core_version,
            "catalogCount": catalog_count,
            "calls": calls,
            "aggregate": aggregate,
            "anomalies": anomalies,
            "resourceSamples": resource_samples,
            "segments": segments,
            "finalError": final_error,
        }

    def write_checkpoint(running: bool) -> None:
        temporary = output.with_suffix(output.suffix + ".tmp")
        temporary.write_text(
            json.dumps(report_value(running), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, output)

    try:
        start_core()
        while time.time() < deadline_epoch:
            now = time.monotonic()
            if (
                process is None
                or process.poll() is not None
                or now - process_started >= args.segment_minutes * 60
            ):
                if process is not None and process.poll() is not None:
                    anomalies.append(
                        {
                            "atUtc": datetime.now(timezone.utc).isoformat(),
                            "kind": "unexpected_core_exit",
                            "exitCode": process.returncode,
                            "segment": segment_index,
                        }
                    )
                stop_core()
                start_core()

            operation, arguments = FAST_CASES[case_index % len(FAST_CASES)]
            case_index += 1
            try:
                call(operation, arguments)
            except Exception as exception:
                anomalies.append(
                    {
                        "atUtc": datetime.now(timezone.utc).isoformat(),
                        "operation": operation,
                        "kind": "call_exception",
                        "exception": f"{type(exception).__name__}: {exception}",
                    }
                )
                stop_core()
                start_core()

            now = time.monotonic()
            if now >= next_hourly:
                for hourly_operation, hourly_arguments in HOURLY_CASES:
                    try:
                        call(hourly_operation, hourly_arguments)
                    except Exception as exception:
                        anomalies.append(
                            {
                                "atUtc": datetime.now(timezone.utc).isoformat(),
                                "operation": hourly_operation,
                                "kind": "hourly_call_exception",
                                "exception": (
                                    f"{type(exception).__name__}: {exception}"
                                ),
                            }
                        )
                        stop_core()
                        start_core()
                next_hourly = now + 3600

            if now >= next_resource:
                sample_resources()
                next_resource = now + 60
            if now >= next_checkpoint:
                write_checkpoint(running=True)
                next_checkpoint = now + args.checkpoint_seconds

            remaining = deadline_epoch - time.time()
            if remaining <= 0:
                break
            time.sleep(min(args.interval_seconds, remaining))
    except Exception as exception:
        final_error = f"{type(exception).__name__}: {exception}"
        anomalies.append(
            {
                "atUtc": datetime.now(timezone.utc).isoformat(),
                "kind": "soak_fatal",
                "exception": final_error,
            }
        )
    finally:
        stop_core()
        write_checkpoint(running=False)
        shutil.rmtree(data_root, ignore_errors=True)
        print(
            json.dumps(
                {
                    "calls": calls,
                    "segments": len(segments),
                    "anomalies": len(anomalies),
                    "finalError": final_error,
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
    return 0 if final_error is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
