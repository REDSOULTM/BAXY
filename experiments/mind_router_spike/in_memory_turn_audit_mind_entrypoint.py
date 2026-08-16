"""Expose bounded turn diagnostics in-memory on the requesting response.

This measurement-only entrypoint never writes the audit stream.  It preserves
the production decision path and appends diagnostics to the matching JSONL
response only after the production turn has finished.
"""

from __future__ import annotations

import json
import os
import threading
from typing import Any

import baxy_mind.__main__ as mind


_AUDITS: dict[str, list[dict[str, Any]]] = {}
_LOCK = threading.Lock()
_REAL_WRITE = mind._write


def _capture(record: dict[str, Any]) -> None:
    request_id = record.get("request_id")
    if not isinstance(request_id, str) or not request_id:
        return
    try:
        copied = json.loads(json.dumps(record, ensure_ascii=False))
    except (TypeError, ValueError):
        return
    with _LOCK:
        _AUDITS.setdefault(request_id, []).append(copied)


def _write_with_audit(message: dict[str, Any]) -> None:
    outgoing = message
    request_id = message.get("id")
    if message.get("type") == "turn.result" and isinstance(request_id, str):
        with _LOCK:
            records = _AUDITS.pop(request_id, [])
        outgoing = dict(message)
        outgoing["_aggregateAudit"] = records
    _REAL_WRITE(outgoing)


os.environ.pop(mind.TURN_AUDIT_ENV, None)
mind._append_turn_audit = _capture
mind._write = _write_with_audit


if __name__ == "__main__":
    raise SystemExit(mind.main())
