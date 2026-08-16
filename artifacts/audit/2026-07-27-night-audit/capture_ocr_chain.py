"""Capture the desktop and run local OCR without retaining image or OCR text."""

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


def read_line(pipe: Any, timeout: float = 45.0) -> str:
    values: queue.Queue[str] = queue.Queue(maxsize=1)
    threading.Thread(target=lambda: values.put(pipe.readline()), daemon=True).start()
    try:
        line = values.get(timeout=timeout)
    except queue.Empty as exception:
        raise TimeoutError("capture/OCR response timed out") from exception
    if not line:
        raise RuntimeError("core closed before response")
    return line


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--vision", action="store_true")
    args = parser.parse_args()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    data_root = (
        Path(os.environ["LOCALAPPDATA"])
        / "BAXY"
        / ("audit-capture-ocr-" + uuid.uuid4().hex)
    )
    data_root.mkdir(parents=True)
    process = subprocess.Popen(
        [str(args.core.resolve(strict=True))],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env={**os.environ, "BAXY_DATA_DIR": str(data_root)},
    )
    hello = json.loads(read_line(process.stdout, 10))

    def invoke(operation: str, arguments: dict[str, Any]) -> list[dict[str, Any]]:
        mission_id = str(uuid.uuid4())
        invocation_id = str(uuid.uuid4())

        def send(token: str | None = None) -> dict[str, Any]:
            value: dict[str, Any] = {
                "type": "operation.request",
                "requestId": str(uuid.uuid4()),
                "missionId": mission_id,
                "invocationId": invocation_id,
                "operation": operation,
                "arguments": arguments,
            }
            if token:
                value["confirmationToken"] = token
            process.stdin.write(json.dumps(value, separators=(",", ":")) + "\n")
            process.stdin.flush()
            return json.loads(read_line(process.stdout))

        first = send()
        responses = [first]
        if first.get("errorCode") == "confirmation_required":
            responses.append(send(first["result"]["token"]))
        return responses

    started = time.perf_counter()
    capture_responses = invoke("capture.screenshot", {})
    capture_terminal = capture_responses[-1]
    capture_id = (capture_terminal.get("result") or {}).get("captureId")
    ocr_responses: list[dict[str, Any]] = []
    vision_responses: list[dict[str, Any]] = []
    if capture_terminal.get("verified") is True and capture_id:
        ocr_responses = invoke("ocr.read", {"captureId": capture_id, "language": None})
        if args.vision:
            vision_responses = invoke(
                "vision.describe",
                {
                    "captureId": capture_id,
                    "prompt": "Describe objetivamente la superficie de auditoría.",
                },
            )

    sanitized_ocr = json.loads(json.dumps(ocr_responses))
    for response in sanitized_ocr:
        result = response.get("result")
        if isinstance(result, dict) and isinstance(result.get("text"), str):
            text = result.pop("text")
            result["textCharacterCount"] = len(text)
            result["textSha256"] = hashlib.sha256(text.encode("utf-8")).hexdigest()

    sanitized_vision = json.loads(json.dumps(vision_responses))
    for response in sanitized_vision:
        result = response.get("result")
        if isinstance(result, dict) and isinstance(result.get("description"), str):
            description = result.pop("description")
            result["descriptionCharacterCount"] = len(description)
            result["descriptionSha256"] = hashlib.sha256(
                description.encode("utf-8")
            ).hexdigest()

    process.stdin.close()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.terminate()
        process.wait(timeout=5)
    report = {
        "schema": "baxy.audit.capture-ocr.v1",
        "core_version": hello.get("coreVersion"),
        "catalog_count": len(hello.get("capabilities") or []),
        "elapsed_seconds": time.perf_counter() - started,
        "capture_responses": capture_responses,
        "ocr_responses_sanitized": sanitized_ocr,
        "vision_responses_sanitized": sanitized_vision,
        "private_capture_deleted_with_data_root": True,
        "process_exit_code": process.returncode,
        "stderr": process.stderr.read()[-2048:],
    }
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    shutil.rmtree(data_root, ignore_errors=True)
    print(
        json.dumps(
            {
                "capture_verified": capture_terminal.get("verified"),
                "ocr_verified": (
                    ocr_responses[-1].get("verified") if ocr_responses else None
                ),
                "vision_status": (
                    vision_responses[-1].get("status")
                    if vision_responses
                    else None
                ),
                "vision_error": (
                    vision_responses[-1].get("errorCode")
                    if vision_responses
                    else None
                ),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
