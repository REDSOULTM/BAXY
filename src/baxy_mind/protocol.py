"""Protocolo JSONL del sidecar mente (baxy.mind.v1).

Espejo disciplinado de baxy.local.v1: una línea = un mensaje JSON UTF-8
estricto, tope de 1 MiB por línea en ambas direcciones, fail-closed ante
malformación. stdin recibe solicitudes del shell; stdout emite hello,
resultados y eventos (transcripciones de voz).
"""

from __future__ import annotations

import json
import sys
import threading
from dataclasses import dataclass
from typing import Any

MAX_LINE_BYTES = 1024 * 1024
PROTOCOL = "baxy.mind.v1"
# The voice thread writes transcripts and events beside the request loop's replies: one line at a time.
_WRITE_LOCK = threading.Lock()


@dataclass
class ProtocolViolation(Exception):
    code: str
    detail: str


def _decode_message(line: bytes) -> dict[str, Any]:
    if len(line) > MAX_LINE_BYTES:
        raise ProtocolViolation("line_too_large", f"{len(line)} bytes")
    try:
        text = line.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise ProtocolViolation("malformed_utf8", str(error)) from error
    text = text.strip()
    if not text:
        return {}
    try:
        message = json.loads(text)
    except json.JSONDecodeError as error:
        raise ProtocolViolation("malformed_json", str(error)) from error
    if not isinstance(message, dict) or not isinstance(message.get("type"), str):
        raise ProtocolViolation("missing_type", "el mensaje no declara type")
    return message


def read_message() -> dict[str, Any] | None:
    """Lee una solicitud; None en EOF. Fail-closed ante línea inválida."""

    stream = sys.stdin.buffer
    # Request one byte beyond the contract so an unterminated or hostile line
    # is rejected before the stream allocates arbitrary input.
    line = stream.readline(MAX_LINE_BYTES + 1)
    if not line:
        return None
    return _decode_message(line)


def write_message(message: dict[str, Any]) -> None:
    stream = sys.stdout.buffer
    payload = json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )
    if len(payload) > MAX_LINE_BYTES:
        raise ProtocolViolation("reply_too_large", f"{len(payload)} bytes")
    with _WRITE_LOCK:
        stream.write(payload + b"\n")
        stream.flush()


def error_reply(request_id: str | None, code: str, message: str) -> dict[str, Any]:
    return {
        "type": "error",
        "id": request_id,
        "code": code,
        "message": message,
    }
