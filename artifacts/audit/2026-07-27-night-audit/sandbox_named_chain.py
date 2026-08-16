"""Exercise named sandbox file operations through the installed BAXY core."""

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


def read_line(pipe: Any, timeout: float = 20.0) -> str:
    values: queue.Queue[str] = queue.Queue(maxsize=1)
    threading.Thread(target=lambda: values.put(pipe.readline()), daemon=True).start()
    try:
        line = values.get(timeout=timeout)
    except queue.Empty as exception:
        raise TimeoutError("sandbox operation timed out") from exception
    if not line:
        raise RuntimeError("core closed before sandbox response")
    return line


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    core = args.core.resolve(strict=True)
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    data_root = (
        Path(os.environ["LOCALAPPDATA"])
        / "BAXY"
        / ("audit-named-sandbox-" + uuid.uuid4().hex)
    )
    sandbox = data_root / "filesystem-sandbox"
    (sandbox / "a").mkdir(parents=True)
    (sandbox / "b").mkdir(parents=True)
    (sandbox / "README.md").write_text("one\ntwo\n", encoding="utf-8")
    (sandbox / "README.backup.md").write_text("one\nthree\n", encoding="utf-8")
    (sandbox / "a" / "dup.txt").write_text("a", encoding="utf-8")
    (sandbox / "b" / "dup.txt").write_text("b", encoding="utf-8")

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
    cases: list[dict[str, Any]] = []
    error: str | None = None

    def invoke(
        operation: str,
        arguments: dict[str, Any],
        *,
        expected_error: str | None = None,
    ) -> dict[str, Any]:
        mission_id = str(uuid.uuid4())
        invocation_id = str(uuid.uuid4())

        def send(token: str | None = None) -> dict[str, Any]:
            request: dict[str, Any] = {
                "type": "operation.request",
                "requestId": str(uuid.uuid4()),
                "missionId": mission_id,
                "invocationId": invocation_id,
                "operation": operation,
                "arguments": arguments,
            }
            if token is not None:
                request["confirmationToken"] = token
            process.stdin.write(json.dumps(request, separators=(",", ":")) + "\n")
            process.stdin.flush()
            return json.loads(read_line(process.stdout))

        started = time.perf_counter()
        responses = [send()]
        if responses[-1].get("errorCode") == "confirmation_required":
            responses.append(send(responses[-1]["result"]["token"]))
        terminal = responses[-1]
        cases.append(
            {
                "operation": operation,
                "arguments": arguments,
                "expected_error": expected_error,
                "responses": responses,
                "elapsed_seconds": time.perf_counter() - started,
            }
        )
        if expected_error is not None:
            if (
                terminal.get("status") != "failed"
                or terminal.get("verified") is not False
                or terminal.get("errorCode") != expected_error
                or terminal.get("effectMayHaveOccurred") is True
            ):
                raise RuntimeError(
                    f"{operation} did not fail closed as {expected_error}"
                )
            return terminal
        if terminal.get("status") != "completed" or terminal.get("verified") is not True:
            raise RuntimeError(
                f"{operation} failed: "
                f"{terminal.get('errorCode') or terminal.get('status')}"
            )
        return terminal["result"]

    started = time.perf_counter()
    try:
        appended = invoke(
            "filesystem.sandbox.append.named",
            {"fileName": "README.md", "text": "four\n"},
        )
        if appended.get("appendedBytes") != 5:
            raise RuntimeError("append byte count mismatch")
        diff = invoke(
            "filesystem.sandbox.diff.named",
            {"leftQuery": "README.md", "rightQuery": "backup"},
        )
        if diff.get("changedLineCount", 0) < 1:
            raise RuntimeError("diff did not detect synthetic changes")
        moved = invoke(
            "filesystem.sandbox.move.named",
            {
                "sourceFileName": "README.backup.md",
                "destinationRelativePath": "archive/README.backup.md",
            },
        )
        if moved.get("sourceAbsent") is not True:
            raise RuntimeError("move did not verify source absence")
        invoke(
            "filesystem.sandbox.append.named",
            {"fileName": "README.backup.md", "text": "after move\n"},
        )
        invoke(
            "filesystem.sandbox.move.named",
            {
                "sourceFileName": "README.md",
                "destinationRelativePath": "../escape.txt",
            },
            expected_error="sandbox_move_destination_invalid",
        )
        invoke(
            "filesystem.sandbox.append.named",
            {"fileName": "dup.txt", "text": "ambiguous"},
            expected_error="sandbox_named_file_ambiguous",
        )
        invoke("filesystem.list", {"relativeDirectory": "", "limit": 20})
    except Exception as exception:
        error = f"{type(exception).__name__}: {exception}"
    finally:
        process.stdin.close()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.terminate()
            process.wait(timeout=5)
        stderr = process.stderr.read()

    report = {
        "schema": "baxy.audit.sandbox-named-chain.v1",
        "core": str(core),
        "core_version": hello.get("coreVersion"),
        "catalog_count": len(hello.get("capabilities") or []),
        "catalog_utf8_bytes": len(hello_line.encode("utf-8")),
        "elapsed_seconds": time.perf_counter() - started,
        "total": len(cases),
        "expected_successes": sum(case["expected_error"] is None for case in cases),
        "verified_successes": sum(
            case["expected_error"] is None
            and case["responses"][-1].get("verified") is True
            for case in cases
        ),
        "expected_failures": sum(case["expected_error"] is not None for case in cases),
        "safe_expected_failures": sum(
            case["expected_error"] is not None
            and case["responses"][-1].get("errorCode") == case["expected_error"]
            and case["responses"][-1].get("effectMayHaveOccurred") is not True
            for case in cases
        ),
        "cases": cases,
        "error": error,
        "process_exit_code": process.returncode,
        "stderr": stderr[-2048:],
    }
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    shutil.rmtree(data_root, ignore_errors=True)
    print(
        json.dumps(
            {
                "total": report["total"],
                "verified_successes": report["verified_successes"],
                "safe_expected_failures": report["safe_expected_failures"],
                "error": error,
            },
            ensure_ascii=False,
        )
    )
    return 0 if error is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
