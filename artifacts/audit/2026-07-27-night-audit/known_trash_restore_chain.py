"""Trash one synthetic Downloads file through BAXY, then restore it exactly."""

from __future__ import annotations

import argparse
import hashlib
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


FILE_NAME = "baxy-audit-known-trash-20260727.txt"


def read_line(pipe: Any, timeout: float = 20) -> str:
    values: queue.Queue[str] = queue.Queue(maxsize=1)
    threading.Thread(target=lambda: values.put(pipe.readline()), daemon=True).start()
    try:
        line = values.get(timeout=timeout)
    except queue.Empty as exception:
        raise TimeoutError("operation timed out") from exception
    if not line:
        raise RuntimeError("core closed before response")
    return line


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    args = parser.parse_args()
    core = args.core.resolve(strict=True)
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    target = args.target.resolve(strict=True)
    if target.name != FILE_NAME:
        raise SystemExit("unexpected target identity")
    baseline_hash = sha256(target)
    data_root = (
        Path(os.environ["LOCALAPPDATA"])
        / "BAXY"
        / ("audit-known-trash-" + uuid.uuid4().hex)
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
    mission_id = str(uuid.uuid4())
    invocation_id = str(uuid.uuid4())

    def send(token: str | None = None) -> dict[str, Any]:
        request: dict[str, Any] = {
            "type": "operation.request",
            "requestId": str(uuid.uuid4()),
            "missionId": mission_id,
            "invocationId": invocation_id,
            "operation": "filesystem.known.trash.named",
            "arguments": {"fileName": FILE_NAME, "folder": "downloads"},
        }
        if token is not None:
            request["confirmationToken"] = token
        process.stdin.write(json.dumps(request, separators=(",", ":")) + "\n")
        process.stdin.flush()
        return json.loads(read_line(process.stdout))

    started = time.perf_counter()
    responses: list[dict[str, Any]] = []
    errors: list[str] = []
    source_absent_after_trash = False
    restored = False
    restored_hash_matches = False
    private_trash_absent_after_restore = False
    private_item: Path | None = None
    try:
        responses.append(send())
        if responses[-1].get("errorCode") == "confirmation_required":
            responses.append(send(responses[-1]["result"]["token"]))
        terminal = responses[-1]
        if terminal.get("status") != "completed" or terminal.get("verified") is not True:
            errors.append(
                "trash:"
                + str(terminal.get("errorCode") or terminal.get("status"))
            )
        else:
            source_absent_after_trash = not target.exists()
            result = terminal["result"]
            restore_id = str(result["restoreId"])
            private_item = (
                data_root / "known-file-trash" / f"{restore_id}_{FILE_NAME}"
            )
            if not source_absent_after_trash:
                errors.append("source_not_absent_after_trash")
            if not private_item.is_file():
                errors.append("private_trash_item_missing")
            elif sha256(private_item) != baseline_hash:
                errors.append("private_trash_hash_mismatch")
            elif str(result.get("sha256")) != baseline_hash:
                errors.append("receipt_hash_mismatch")
            else:
                private_item.replace(target)
                restored = target.is_file()
                restored_hash_matches = restored and sha256(target) == baseline_hash
                private_trash_absent_after_restore = not private_item.exists()
                if not restored_hash_matches:
                    errors.append("restored_hash_mismatch")
                if not private_trash_absent_after_restore:
                    errors.append("private_item_remained_after_restore")
    except Exception as exception:
        errors.append(f"{type(exception).__name__}:{exception}")
    finally:
        process.stdin.close()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.terminate()
            process.wait(timeout=5)
        stderr = process.stderr.read()
        shutil.rmtree(data_root, ignore_errors=True)

    if not target.exists() and private_item is not None and private_item.exists():
        private_item.replace(target)
    final_target_present = target.is_file()
    final_hash_matches = final_target_present and sha256(target) == baseline_hash
    if not final_hash_matches:
        errors.append("final_target_not_restored")
    report = {
        "schema": "baxy.audit.known-trash-restore-chain.v1",
        "core": str(core),
        "core_version": hello.get("coreVersion"),
        "catalog_count": len(hello.get("capabilities") or []),
        "operation": "filesystem.known.trash.named",
        "file_name": FILE_NAME,
        "responses": responses,
        "source_absent_after_trash": source_absent_after_trash,
        "restored": restored,
        "restored_hash_matches": restored_hash_matches,
        "private_trash_absent_after_restore": private_trash_absent_after_restore,
        "final_target_present": final_target_present,
        "final_hash_matches": final_hash_matches,
        "elapsed_seconds": time.perf_counter() - started,
        "errors": errors,
        "process_exit_code": process.returncode,
        "stderr": stderr[-2048:],
    }
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "verified": bool(responses)
                and responses[-1].get("verified") is True,
                "source_absent_after_trash": source_absent_after_trash,
                "restored": restored,
                "restored_hash_matches": restored_hash_matches,
                "final_target_present": final_target_present,
                "errors": errors,
            },
            ensure_ascii=False,
        )
    )
    return 0 if not errors and not stderr else 1


if __name__ == "__main__":
    raise SystemExit(main())
