"""Durable replacement for generated tooling outputs."""

from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path

REPLACE_RETRY_SECONDS = 1.0
REPLACE_RETRY_INITIAL_SECONDS = 0.005
REPLACE_RETRY_MAX_SECONDS = 0.05


def _replace_with_bounded_retry(source: Path, destination: Path) -> None:
    """Retry transient Windows sharing violations without hiding hard failures."""

    deadline = time.monotonic() + REPLACE_RETRY_SECONDS
    delay = REPLACE_RETRY_INITIAL_SECONDS
    while True:
        try:
            os.replace(source, destination)
            return
        except PermissionError:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise
            time.sleep(min(delay, remaining))
            delay = min(delay * 2, REPLACE_RETRY_MAX_SECONDS)


def replace_bytes_atomically(path: Path, payload: bytes) -> None:
    """Write complete bytes beside ``path`` and atomically replace it."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        _replace_with_bounded_retry(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
