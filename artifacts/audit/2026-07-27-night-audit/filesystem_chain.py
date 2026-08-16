"""Exercise the complete sandbox filesystem and backup lifecycle."""

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
        raise TimeoutError("filesystem operation timed out") from exception
    if not line:
        raise RuntimeError("core closed before filesystem response")
    return line


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--skip-known-broken-hash",
        action="store_true",
        help="Continue with later lifecycle steps after AUD-019 was isolated.",
    )
    args = parser.parse_args()
    core = args.core.resolve(strict=True)
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    data_root = (
        Path(os.environ["LOCALAPPDATA"])
        / "BAXY"
        / ("audit-filesystem-" + uuid.uuid4().hex)
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
        first = send()
        responses = [first]
        if first.get("errorCode") == "confirmation_required":
            responses.append(send(first["result"]["token"]))
        case = {
            "operation": operation,
            "arguments": arguments,
            "responses": responses,
            "elapsed_seconds": time.perf_counter() - started,
        }
        cases.append(case)
        terminal = responses[-1]
        if terminal.get("status") != "completed" or terminal.get("verified") is not True:
            raise RuntimeError(
                f"{operation} failed: {terminal.get('errorCode') or terminal.get('status')}"
            )
        return terminal["result"]

    def find_entry(result: dict[str, Any], name: str) -> dict[str, Any]:
        matches = [entry for entry in result["entries"] if entry["name"] == name]
        if len(matches) != 1:
            raise RuntimeError(f"expected one entry named {name}, got {len(matches)}")
        return matches[0]

    started = time.perf_counter()
    try:
        invoke("filesystem.create.directory", {"relativePath": "documents"})
        invoke("filesystem.create.directory", {"relativePath": "moved"})
        written = invoke(
            "filesystem.write.text",
            {
                "relativePath": "documents/source.txt",
                "text": "BAXY synthetic filesystem audit: alpha\n",
                "expectedSha256": None,
            },
        )
        source_id = written["resourceId"]
        source_hash = written["sha256"]
        read = invoke(
            "filesystem.read.text",
            {"resourceId": source_id, "maximumBytes": 4096},
        )
        if read["sha256"] != source_hash or "alpha" not in read["text"]:
            raise RuntimeError("filesystem.read.text did not preserve content and hash")
        if not args.skip_known_broken_hash:
            hashed = invoke("filesystem.hash", {"resourceId": source_id})
            if hashed["sha256"] != source_hash:
                raise RuntimeError("filesystem.hash disagreed with write receipt")

        written = invoke(
            "filesystem.write.text",
            {
                "relativePath": "documents/source.txt",
                "text": "BAXY synthetic filesystem audit: beta\n",
                "expectedSha256": source_hash,
            },
        )
        source_id = written["resourceId"]
        source_hash = written["sha256"]
        listed = invoke(
            "filesystem.list",
            {"relativeDirectory": "documents", "limit": 20},
        )
        listed_source = find_entry(listed, "source.txt")
        if listed_source["size"] != written["size"]:
            raise RuntimeError("filesystem.list disagreed with replaced file size")
        searched = invoke("filesystem.search", {"query": "source", "limit": 20})
        searched_source = find_entry(searched, "source.txt")
        if searched_source["size"] != written["size"]:
            raise RuntimeError("filesystem.search disagreed with replaced file size")
        source_id = searched_source["resourceId"]

        copied = invoke(
            "filesystem.copy",
            {
                "resourceId": source_id,
                "destinationRelativePath": "documents/copy.txt",
                "expectedSha256": source_hash,
            },
        )
        listed = invoke(
            "filesystem.list",
            {"relativeDirectory": "documents", "limit": 20},
        )
        listed_copy = find_entry(listed, "copy.txt")
        if listed_copy["size"] != copied["size"]:
            raise RuntimeError("filesystem.list disagreed with copied file size")
        copied["resourceId"] = listed_copy["resourceId"]
        backup = invoke(
            "backup.create",
            {"resourceId": copied["resourceId"], "expectedSha256": copied["sha256"]},
        )
        verified_backup = invoke("backup.verify", {"backupId": backup["backupId"]})
        if verified_backup["sha256"] != copied["sha256"]:
            raise RuntimeError("backup hash disagreed with copied file")
        invoke("backup.list", {"limit": 20})
        restored = invoke(
            "backup.restore",
            {
                "backupId": backup["backupId"],
                "destinationRelativePath": "documents/restored.txt",
            },
        )
        if restored["sha256"] != copied["sha256"]:
            raise RuntimeError("restored backup hash disagreed with source")

        invoke(
            "filesystem.move",
            {
                "resourceId": source_id,
                "destinationRelativePath": "moved/source-moved.txt",
                "expectedSha256": source_hash,
            },
        )
        moved_list = invoke(
            "filesystem.list",
            {"relativeDirectory": "moved", "limit": 20},
        )
        moved_entry = find_entry(moved_list, "source-moved.txt")
        moved_read = invoke(
            "filesystem.read.text",
            {"resourceId": moved_entry["resourceId"], "maximumBytes": 4096},
        )
        if moved_read["sha256"] != source_hash:
            raise RuntimeError("moved file hash disagreed with source")

        listed = invoke(
            "filesystem.list",
            {"relativeDirectory": "documents", "limit": 20},
        )
        copied["resourceId"] = find_entry(listed, "copy.txt")["resourceId"]
        preparation = invoke(
            "filesystem.trash.prepare",
            {"resourceId": copied["resourceId"]},
        )
        trashed = invoke(
            "filesystem.trash.commit",
            {
                "trashId": preparation["trashId"],
                "reviewLabel": preparation["reviewLabel"],
            },
        )
        invoke(
            "filesystem.trash.restore",
            {"restoreId": trashed["restoreId"]},
        )
        final_list = invoke(
            "filesystem.list",
            {"relativeDirectory": "documents", "limit": 20},
        )
        final_copy = find_entry(final_list, "copy.txt")
        final_read = invoke(
            "filesystem.read.text",
            {"resourceId": final_copy["resourceId"], "maximumBytes": 4096},
        )
        if final_read["sha256"] != copied["sha256"]:
            raise RuntimeError("trash restore did not preserve copied file")
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
        "schema": "baxy.audit.filesystem-chain.v1",
        "core": str(core),
        "core_version": hello.get("coreVersion"),
        "catalog_count": len(hello.get("capabilities") or []),
        "catalog_utf8_bytes": len(hello_line.encode("utf-8")),
        "elapsed_seconds": time.perf_counter() - started,
        "total": len(cases),
        "verified": sum(
            case["responses"][-1].get("verified") is True for case in cases
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
                "verified": report["verified"],
                "error": error,
            },
            ensure_ascii=False,
        )
    )
    return 0 if error is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
