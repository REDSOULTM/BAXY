"""Exercise installed BAXY Office create/read adapters and clean exact outputs."""

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
        raise TimeoutError("office operation timed out") from exception
    if not line:
        raise RuntimeError("core closed before office response")
    return line


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--documents-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    core = args.core.resolve(strict=True)
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    documents_root = args.documents_root.resolve(strict=True)
    office_root = documents_root / "BAXY"
    before = set(office_root.glob("*")) if office_root.exists() else set()
    run_id = uuid.uuid4().hex[:12]
    title_prefix = f"BAXY Night Audit {run_id}"
    data_root = (
        Path(os.environ["LOCALAPPDATA"])
        / "BAXY"
        / ("audit-office-" + uuid.uuid4().hex)
    )
    data_root.mkdir(parents=True, exist_ok=False)
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

    def invoke(operation: str, arguments: dict[str, Any]) -> dict[str, Any]:
        mission_id = str(uuid.uuid4())
        invocation_id = str(uuid.uuid4())
        request = {
            "type": "operation.request",
            "requestId": str(uuid.uuid4()),
            "missionId": mission_id,
            "invocationId": invocation_id,
            "operation": operation,
            "arguments": arguments,
        }
        started = time.perf_counter()
        process.stdin.write(json.dumps(request, separators=(",", ":")) + "\n")
        process.stdin.flush()
        response = json.loads(read_line(process.stdout, 70))
        cases.append(
            {
                "operation": operation,
                "arguments": arguments,
                "response": response,
                "elapsed_seconds": time.perf_counter() - started,
            }
        )
        if response.get("status") != "completed" or response.get("verified") is not True:
            raise RuntimeError(
                f"{operation} failed: "
                f"{response.get('errorCode') or response.get('status')}"
            )
        return response["result"]

    started = time.perf_counter()
    created_paths: list[Path] = []
    try:
        for format_name in ("docx", "xlsx"):
            title = f"{title_prefix} {format_name.upper()}"
            created = invoke(
                "office.document.create",
                {"format": format_name, "title": title},
            )
            if created.get("format") != format_name or created.get("title") != title:
                raise RuntimeError("office create result did not preserve format/title")
            read = invoke(
                "office.document.read",
                {"documentId": created["documentId"]},
            )
            if (
                read.get("documentId") != created["documentId"]
                or read.get("format") != format_name
                or title not in read.get("text", "")
            ):
                raise RuntimeError("office read did not bind to the created document")

        after = set(office_root.glob("*"))
        created_paths = sorted(after - before)
        expected_paths = [
            path
            for path in created_paths
            if path.name.startswith(title_prefix)
            and path.suffix.lower() in {".docx", ".xlsx"}
        ]
        if len(created_paths) != 2 or len(expected_paths) != 2:
            raise RuntimeError(
                f"unexpected Office output set: "
                f"{[path.name for path in created_paths]}"
            )
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

    cleanup: list[dict[str, Any]] = []
    for path in created_paths:
        resolved = path.resolve(strict=True)
        if (
            resolved.parent != office_root.resolve(strict=True)
            or not resolved.name.startswith(title_prefix)
            or resolved.suffix.lower() not in {".docx", ".xlsx"}
        ):
            cleanup.append({"path": str(resolved), "deleted": False, "safe": False})
            if error is None:
                error = "cleanup target validation failed"
            continue
        resolved.unlink()
        cleanup.append({"path": str(resolved), "deleted": not resolved.exists(), "safe": True})

    report = {
        "schema": "baxy.audit.office-document-chain.v1",
        "core": str(core),
        "core_version": hello.get("coreVersion"),
        "catalog_count": len(hello.get("capabilities") or []),
        "catalog_utf8_bytes": len(hello_line.encode("utf-8")),
        "documents_root": str(documents_root),
        "title_prefix": title_prefix,
        "elapsed_seconds": time.perf_counter() - started,
        "total": len(cases),
        "verified": sum(case["response"].get("verified") is True for case in cases),
        "cases": cases,
        "cleanup": cleanup,
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
                "verified": report["verified"],
                "cleaned": sum(item["deleted"] for item in cleanup),
                "error": error,
            },
            ensure_ascii=False,
        )
    )
    return 0 if error is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
