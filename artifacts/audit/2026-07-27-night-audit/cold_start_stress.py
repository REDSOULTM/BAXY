"""Repeatedly start and cleanly stop the installed BAXY core.

Audit harness only. Each process receives a unique empty data root and no
operation requests. The root is removed after the process exits.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import queue
import shutil
import statistics
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Any


def read_line(pipe: Any, timeout: float) -> str:
    values: queue.Queue[str] = queue.Queue(maxsize=1)
    threading.Thread(target=lambda: values.put(pipe.readline()), daemon=True).start()
    try:
        line = values.get(timeout=timeout)
    except queue.Empty as exception:
        raise TimeoutError("hello timed out") from exception
    if not line:
        raise RuntimeError("core closed before hello")
    return line


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(len(ordered) * fraction)))
    return ordered[index]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cycles", type=int, default=100)
    args = parser.parse_args()
    if args.cycles < 1:
        raise SystemExit("--cycles must be positive")

    core = args.core.resolve(strict=True)
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    durations: list[float] = []
    errors: list[dict[str, Any]] = []
    normalized_hashes: set[str] = set()
    catalog_counts: set[int] = set()
    versions: set[str] = set()
    hello_sizes: set[int] = set()

    for cycle in range(1, args.cycles + 1):
        data_root = (
            Path(os.environ["LOCALAPPDATA"])
            / "BAXY"
            / ("audit-cold-start-" + uuid.uuid4().hex)
        )
        data_root.mkdir(parents=True, exist_ok=False)
        process: subprocess.Popen[str] | None = None
        started = time.perf_counter()
        cycle_errors: list[str] = []
        stderr = ""
        try:
            process = subprocess.Popen(
                [str(core)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                env={**os.environ, "BAXY_DATA_DIR": str(data_root)},
            )
            hello_line = read_line(process.stdout, 10)
            hello = json.loads(hello_line)
            capabilities = hello.get("capabilities") or []
            catalog_counts.add(len(capabilities))
            versions.add(str(hello.get("coreVersion")))
            hello_sizes.add(len(hello_line.encode("utf-8")))
            normalized = dict(hello)
            normalized.pop("pid", None)
            normalized_hashes.add(
                hashlib.sha256(
                    json.dumps(
                        normalized,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode("utf-8")
                ).hexdigest()
            )
            if len(capabilities) != 168:
                cycle_errors.append(f"catalog_count:{len(capabilities)}")
            if hello.get("coreVersion") != "1.0.8":
                cycle_errors.append(f"core_version:{hello.get('coreVersion')}")
        except Exception as exception:
            cycle_errors.append(f"{type(exception).__name__}:{exception}")
        finally:
            if process is not None:
                if process.stdin is not None:
                    process.stdin.close()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    cycle_errors.append("exit_timeout")
                    process.terminate()
                    process.wait(timeout=5)
                stderr = process.stderr.read() if process.stderr is not None else ""
                if process.returncode != 0:
                    cycle_errors.append(f"exit_code:{process.returncode}")
            shutil.rmtree(data_root, ignore_errors=True)

        duration = time.perf_counter() - started
        durations.append(duration)
        if cycle_errors or stderr:
            errors.append(
                {
                    "cycle": cycle,
                    "duration_seconds": round(duration, 4),
                    "errors": cycle_errors,
                    "stderr": stderr[-1024:],
                }
            )

    if len(normalized_hashes) != 1:
        errors.append(
            {
                "cycle": None,
                "errors": [
                    f"normalized_hello_hash_count:{len(normalized_hashes)}"
                ],
            }
        )

    report = {
        "schema": "baxy.audit.cold-start-stress.v1",
        "core": str(core),
        "cycles": args.cycles,
        "successful_cycles": args.cycles - sum(
            item.get("cycle") is not None for item in errors
        ),
        "catalog_counts": sorted(catalog_counts),
        "core_versions": sorted(versions),
        "hello_utf8_sizes": sorted(hello_sizes),
        "normalized_hello_hash_count": len(normalized_hashes),
        "timing_seconds": {
            "minimum": min(durations),
            "median": statistics.median(durations),
            "p95": percentile(durations, 0.95),
            "maximum": max(durations),
            "mean": statistics.fmean(durations),
        },
        "errors": errors,
    }
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "cycles": report["cycles"],
                "successful_cycles": report["successful_cycles"],
                "catalog_counts": report["catalog_counts"],
                "core_versions": report["core_versions"],
                "normalized_hello_hash_count": report[
                    "normalized_hello_hash_count"
                ],
                "p95_seconds": report["timing_seconds"]["p95"],
                "maximum_seconds": report["timing_seconds"]["maximum"],
                "error_count": len(errors),
            },
            ensure_ascii=False,
        )
    )
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
