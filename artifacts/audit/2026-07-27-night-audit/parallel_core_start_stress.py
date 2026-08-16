"""Start many installed BAXY cores concurrently using isolated data roots."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import shutil
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any


def run_one(core: Path, round_index: int, slot: int) -> dict[str, Any]:
    data_root = (
        Path(os.environ["LOCALAPPDATA"])
        / "BAXY"
        / ("audit-parallel-core-" + uuid.uuid4().hex)
    )
    data_root.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    process: subprocess.Popen[str] | None = None
    result: dict[str, Any] = {
        "round": round_index,
        "slot": slot,
        "data_root": str(data_root),
        "errors": [],
    }
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
        assert process.stdin is not None
        assert process.stdout is not None
        assert process.stderr is not None
        hello = json.loads(process.stdout.readline())
        result["pid"] = process.pid
        result["hello_seconds"] = time.perf_counter() - started
        result["core_version"] = hello.get("coreVersion")
        result["catalog_count"] = len(hello.get("capabilities") or [])
        if hello.get("type") != "hello":
            result["errors"].append("hello_type")
        if result["catalog_count"] != 168:
            result["errors"].append("catalog_count")

        request_id = str(uuid.uuid4())
        mission_id = str(uuid.uuid4())
        invocation_id = str(uuid.uuid4())
        process.stdin.write(
            json.dumps(
                {
                    "type": "operation.request",
                    "requestId": request_id,
                    "missionId": mission_id,
                    "invocationId": invocation_id,
                    "operation": "system.time",
                    "arguments": {},
                },
                separators=(",", ":"),
            )
            + "\n"
        )
        process.stdin.flush()
        response = json.loads(process.stdout.readline())
        result["response_seconds"] = time.perf_counter() - started
        for field, expected in (
            ("requestId", request_id),
            ("missionId", mission_id),
            ("invocationId", invocation_id),
            ("status", "completed"),
            ("verified", True),
        ):
            if response.get(field) != expected:
                result["errors"].append(f"response_{field}")

        process.stdin.close()
        result["exit_code"] = process.wait(timeout=15)
        result["stderr"] = process.stderr.read()[-2048:]
        if result["exit_code"] != 0:
            result["errors"].append("exit_code")
        if result["stderr"]:
            result["errors"].append("stderr")
    except Exception as exception:
        result["errors"].append(f"{type(exception).__name__}:{exception}")
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
    finally:
        try:
            shutil.rmtree(data_root)
            result["data_root_removed"] = True
        except OSError as exception:
            result["data_root_removed"] = False
            result["errors"].append(
                f"data_root_cleanup:{type(exception).__name__}"
            )
    result["elapsed_seconds"] = time.perf_counter() - started
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--parallel", type=int, default=12)
    parser.add_argument("--rounds", type=int, default=3)
    args = parser.parse_args()
    if args.parallel < 1 or args.rounds < 1:
        raise SystemExit("--parallel and --rounds must be positive")

    core = args.core.resolve(strict=True)
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    for round_index in range(1, args.rounds + 1):
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=args.parallel
        ) as executor:
            futures = [
                executor.submit(run_one, core, round_index, slot)
                for slot in range(1, args.parallel + 1)
            ]
            results.extend(future.result() for future in futures)

    hello_times = [float(item["hello_seconds"]) for item in results]
    response_times = [float(item["response_seconds"]) for item in results]
    errors = [
        {
            "round": item["round"],
            "slot": item["slot"],
            "errors": item["errors"],
        }
        for item in results
        if item["errors"]
    ]
    report = {
        "schema": "baxy.audit.parallel-core-start-stress.v1",
        "core": str(core),
        "parallel": args.parallel,
        "rounds": args.rounds,
        "instances": len(results),
        "successful_instances": len(results) - len(errors),
        "hello_seconds": {
            "minimum": min(hello_times),
            "mean": sum(hello_times) / len(hello_times),
            "maximum": max(hello_times),
        },
        "response_seconds": {
            "minimum": min(response_times),
            "mean": sum(response_times) / len(response_times),
            "maximum": max(response_times),
        },
        "errors": errors,
        "results": results,
    }
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                key: report[key]
                for key in (
                    "instances",
                    "successful_instances",
                    "hello_seconds",
                    "response_seconds",
                    "errors",
                )
            },
            ensure_ascii=False,
        )
    )
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
