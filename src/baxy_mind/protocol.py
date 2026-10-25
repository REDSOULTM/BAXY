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
    # The cap is the message's, without its line end: the App's (MindSidecarClient.MaximumLineBytes) and write_message's.
    body = line[:-1] if line.endswith(b"\n") else line
    body = body[:-1] if body.endswith(b"\r") else body
    if len(body) > MAX_LINE_BYTES:
        raise ProtocolViolation("line_too_large", f"{len(body)} bytes")
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
    # Request the contract, its line end («\r\n» at most) and nothing more, so an unterminated or hostile line
    # is rejected before the stream allocates arbitrary input.
    line = stream.readline(MAX_LINE_BYTES + 2)
    if not line:
        return None
    return _decode_message(line)


def whole_code_points(text: str) -> str:
    """El texto sin sustitutos UTF-16 sueltos (json.loads acepta el escape de una mitad sin su par): cada uno pasa a
    U+FFFD, como los escribe System.Text.Json en la App. Sueltos, codificarlos en UTF-8 lanzaba UnicodeEncodeError, que
    hacía fallar la respuesta o la traza."""
    try:
        text.encode("utf-8")
        return text
    except UnicodeEncodeError:
        return text.encode("utf-16-le", "surrogatepass").decode("utf-16-le", "replace")


def write_message(message: dict[str, Any]) -> None:
    stream = sys.stdout.buffer
    payload = whole_code_points(json.dumps(message, ensure_ascii=False, separators=(",", ":"))).encode("utf-8")
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
