"""Private encoder-only subprocess for the pinned E5 model."""

from __future__ import annotations

import json
import sys

from .router import (
    MAX_ENCODER_BATCH_SIZE,
    MAX_ENCODER_TEXT_CHARS,
    SemanticEncoder,
)


def _write(value: dict) -> None:
    sys.stdout.write(json.dumps(value, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _valid_request_id(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 1


def _write_error(request_id: object, code: str) -> None:
    _write(
        {
            "type": "error",
            "id": request_id if _valid_request_id(request_id) else None,
            "code": code,
        }
    )


def main() -> int:
    encoder = SemanticEncoder()
    _write({"type": "ready"})
    for line in sys.stdin:
        request_id: object = None
        try:
            request = json.loads(line)
            if not isinstance(request, dict):
                _write_error(None, "invalid_request")
                continue
            request_id = request.get("id")
            kind = request.get("type")
            if kind == "shutdown":
                if (
                    set(request) != {"type", "id"}
                    or not _valid_request_id(request_id)
                ):
                    _write_error(request_id, "invalid_request")
                    continue
                return 0
            if kind == "encode":
                texts = request.get("texts")
                if (
                    set(request) != {"type", "id", "texts"}
                    or not _valid_request_id(request_id)
                    or not isinstance(texts, list)
                    or not 1 <= len(texts) <= MAX_ENCODER_BATCH_SIZE
                    or any(
                        not isinstance(text, str)
                        or not text
                        or len(text) > MAX_ENCODER_TEXT_CHARS
                        for text in texts
                    )
                ):
                    _write_error(request_id, "invalid_request")
                    continue
                rows = encoder.encode(tuple(texts))
                _write(
                    {
                        "type": "encode.result",
                        "id": request_id,
                        "rows": rows.tolist(),
                    }
                )
            else:
                _write_error(request_id, "unknown_request")
        except Exception:
            _write_error(request_id, "request_failed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
