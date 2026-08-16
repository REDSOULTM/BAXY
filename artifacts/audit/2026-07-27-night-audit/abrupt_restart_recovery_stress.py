"""Audit installed-core recovery after an abrupt stop with queued requests."""

from __future__ import annotations

import argparse
import json
import os
import queue
import shutil
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Any


def read_line(pipe: Any, timeout: float = 15.0) -> str:
    values: queue.Queue[str] = queue.Queue(maxsize=1)
    threading.Thread(target=lambda: values.put(pipe.readline()), daemon=True).start()
    try:
        line = values.get(timeout=timeout)
    except queue.Empty as exception:
        raise TimeoutError("core response timed out") from exception
    if not line:
        raise RuntimeError("core closed before response")
    return line


def request(
    operation: str,
    *,
    mission_id: str | None = None,
    invocation_id: str | None = None,
) -> dict[str, Any]:
    return {
        "type": "operation.request",
        "requestId": str(uuid.uuid4()),
        "missionId": mission_id or str(uuid.uuid4()),
        "invocationId": invocation_id or str(uuid.uuid4()),
        "operation": operation,
        "arguments": {},
    }


def start_core(
    core: Path, environment: dict[str, str]
) -> tuple[subprocess.Popen[str], dict[str, Any]]:
    process = subprocess.Popen(
        [str(core)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env=environment,
    )
    assert process.stdin is not None
    assert process.stdout is not None
    assert process.stderr is not None
    hello = json.loads(read_line(process.stdout))
    return process, hello


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cycles", type=int, default=20)
    parser.add_argument("--queued", type=int, default=100)
    args = parser.parse_args()
    if args.cycles < 1 or args.queued < 1:
        raise SystemExit("--cycles and --queued must be positive")

    core = args.core.resolve(strict=True)
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []

    for cycle in range(1, args.cycles + 1):
        data_root = (
            Path(os.environ["LOCALAPPDATA"])
            / "BAXY"
            / ("audit-abrupt-restart-" + uuid.uuid4().hex)
        )
        data_root.mkdir(parents=True, exist_ok=False)
        environment = {**os.environ, "BAXY_DATA_DIR": str(data_root)}
        mission_id = str(uuid.uuid4())
        invocation_id = str(uuid.uuid4())
        cycle_result: dict[str, Any] = {"cycle": cycle, "errors": []}
        first: subprocess.Popen[str] | None = None
        second: subprocess.Popen[str] | None = None
        started = time.perf_counter()
        try:
            first, first_hello = start_core(core, environment)
            marker = request(
                "system.time",
                mission_id=mission_id,
                invocation_id=invocation_id,
            )
            first.stdin.write(json.dumps(marker, separators=(",", ":")) + "\n")
            first.stdin.flush()
            marker_response = json.loads(read_line(first.stdout))
            if (
                marker_response.get("status") != "completed"
                or marker_response.get("verified") is not True
                or marker_response.get("replayed") is not False
            ):
                cycle_result["errors"].append("marker_not_committed")

            drained_responses: list[str] = []

            def drain_stdout() -> None:
                assert first is not None
                assert first.stdout is not None
                while True:
                    line = first.stdout.readline()
                    if not line:
                        return
                    drained_responses.append(line)

            drainer = threading.Thread(target=drain_stdout, daemon=True)
            drainer.start()
            queued_requests = [
                request(
                    (
                        "system.status"
                        if (index + cycle) % 2
                        else "network.status"
                    )
                )
                for index in range(args.queued)
            ]
            writes_completed = 0

            def write_queue() -> None:
                nonlocal writes_completed
                assert first is not None
                assert first.stdin is not None
                try:
                    for queued in queued_requests:
                        first.stdin.write(
                            json.dumps(queued, separators=(",", ":")) + "\n"
                        )
                        first.stdin.flush()
                        writes_completed += 1
                except (BrokenPipeError, OSError, ValueError):
                    return

            writer = threading.Thread(target=write_queue, daemon=True)
            writer.start()
            time.sleep(0.02 + (cycle % 5) * 0.01)
            first.kill()
            first.wait(timeout=10)
            writer.join(timeout=5)
            drainer.join(timeout=5)
            cycle_result["writes_before_kill"] = writes_completed
            cycle_result["responses_before_kill"] = len(drained_responses)
            cycle_result["killed_exit_code"] = first.returncode
            cycle_result["first_stderr"] = first.stderr.read()[-1024:]

            second, second_hello = start_core(core, environment)
            replay = request(
                "system.time",
                mission_id=mission_id,
                invocation_id=invocation_id,
            )
            second.stdin.write(json.dumps(replay, separators=(",", ":")) + "\n")
            second.stdin.flush()
            replay_response = json.loads(read_line(second.stdout))
            if (
                replay_response.get("status") != "completed"
                or replay_response.get("verified") is not True
                or replay_response.get("replayed") is not True
            ):
                cycle_result["errors"].append("committed_marker_not_replayed")

            probe = request("system.status")
            second.stdin.write(json.dumps(probe, separators=(",", ":")) + "\n")
            second.stdin.flush()
            probe_response = json.loads(read_line(second.stdout))
            if (
                probe_response.get("status") != "completed"
                or probe_response.get("verified") is not True
            ):
                cycle_result["errors"].append("post_recovery_probe_failed")
            second.stdin.close()
            cycle_result["second_exit_code"] = second.wait(timeout=15)
            cycle_result["second_stderr"] = second.stderr.read()[-1024:]
            if cycle_result["second_exit_code"] != 0:
                cycle_result["errors"].append("recovered_exit_code")
            if cycle_result["second_stderr"]:
                cycle_result["errors"].append("recovered_stderr")
            cycle_result["catalog_counts"] = [
                len(first_hello.get("capabilities") or []),
                len(second_hello.get("capabilities") or []),
            ]
            if cycle_result["catalog_counts"] != [168, 168]:
                cycle_result["errors"].append("catalog_count")
        except Exception as exception:
            cycle_result["errors"].append(
                f"{type(exception).__name__}:{exception}"
            )
        finally:
            for process in (first, second):
                if process is not None and process.poll() is None:
                    process.kill()
                    process.wait(timeout=5)
            try:
                shutil.rmtree(data_root)
                cycle_result["data_root_removed"] = True
            except OSError as exception:
                cycle_result["data_root_removed"] = False
                cycle_result["errors"].append(
                    f"data_root_cleanup:{type(exception).__name__}"
                )
        cycle_result["elapsed_seconds"] = time.perf_counter() - started
        results.append(cycle_result)

    errors = [
        {"cycle": item["cycle"], "errors": item["errors"]}
        for item in results
        if item["errors"]
    ]
    report = {
        "schema": "baxy.audit.abrupt-restart-recovery-stress.v1",
        "core": str(core),
        "cycles": args.cycles,
        "queuedRequestsBeforeKill": args.queued,
        "successfulCycles": args.cycles - len(errors),
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
                "cycles": report["cycles"],
                "successfulCycles": report["successfulCycles"],
                "errors": report["errors"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
