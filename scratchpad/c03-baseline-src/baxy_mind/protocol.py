"""Protocolo JSONL del sidecar mente (baxy.mind.v1).

Espejo disciplinado de baxy.local.v1: una línea = un mensaje JSON UTF-8
estricto, tope de 1 MiB por línea en ambas direcciones, fail-closed ante
malformación. stdin recibe solicitudes del shell; stdout emite hello,
resultados y eventos (transcripciones de voz).
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from typing import Any, Callable

MAX_LINE_BYTES = 1024 * 1024
_READ_CHUNK_BYTES = 64 * 1024
PROTOCOL = "baxy.mind.v1"


@dataclass
class ProtocolViolation(Exception):
    code: str
    detail: str


def _decode_message(line: bytes) -> dict[str, Any]:
    if not line:
        raise ValueError("an empty byte sequence is EOF, not a message")
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


class _BoundedFileDescriptorLineReader:
    """Read bounded lines without acquiring CPython's buffered-stream lock."""

    def __init__(
        self,
        descriptor: int,
        *,
        read: Callable[[int, int], bytes] = os.read,
        chunk_bytes: int = _READ_CHUNK_BYTES,
    ) -> None:
        if descriptor < 0:
            raise ValueError("descriptor must be non-negative")
        if chunk_bytes <= 0:
            raise ValueError("chunk_bytes must be positive")
        self._descriptor = descriptor
        self._read = read
        self._chunk_bytes = chunk_bytes
        self._buffer = bytearray()
        self._eof = False

    def readline(self, limit: int = -1) -> bytes:
        if limit <= 0:
            raise ValueError("a positive line limit is required")

        while True:
            newline = self._buffer.find(b"\n")
            if 0 <= newline < limit:
                line_end = newline + 1
                line = bytes(self._buffer[:line_end])
                del self._buffer[:line_end]
                return line
            if len(self._buffer) >= limit:
                line = bytes(self._buffer[:limit])
                del self._buffer[:limit]
                return line
            if self._eof:
                if not self._buffer:
                    return b""
                line = bytes(self._buffer)
                self._buffer.clear()
                return line

            maximum_read = min(self._chunk_bytes, limit - len(self._buffer))
            try:
                chunk = self._read(self._descriptor, maximum_read)
            except InterruptedError:
                continue
            if chunk:
                if len(chunk) > maximum_read:
                    raise ValueError("read returned more bytes than requested")
                self._buffer.extend(chunk)
            else:
                self._eof = True


def read_message(stream=None) -> dict[str, Any] | None:
    """Lee una solicitud; None en EOF. Fail-closed ante línea inválida."""

    stream = stream or sys.stdin.buffer
    # Request one byte beyond the contract so an unterminated or hostile line
    # is rejected before the stream allocates arbitrary input.
    line = stream.readline(MAX_LINE_BYTES + 1)
    if not line:
        return None
    return _decode_message(line)


def write_message(message: dict[str, Any], stream=None) -> None:
    stream = stream or sys.stdout.buffer
    payload = json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )
    if len(payload) > MAX_LINE_BYTES:
        raise ProtocolViolation("reply_too_large", f"{len(payload)} bytes")
    stream.write(payload + b"\n")
    stream.flush()


def hello(models: dict[str, str]) -> dict[str, Any]:
    return {
        "type": "hello",
        "protocol": PROTOCOL,
        "mindVersion": "1.0.0",
        "models": models,
        "requests": [
            "catalog.configure",
            "turn.decide",
            "plan",
            "plan.ground",
            "narrate",
            "voice.start",
            "voice.stop",
            "voice.status",
            "voice.speak",
            "voice.cancel",
            "shutdown",
        ],
    }


def error_reply(request_id: str | None, code: str, message: str) -> dict[str, Any]:
    return {
        "type": "error",
        "id": request_id,
        "code": code,
        "message": message,
    }
