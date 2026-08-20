"""Rebuild the exact inherited FunctionGemma R2 training population.

The previous BAXY preserved the post-R3 corpus.  R3 added 112 rows whose
``source`` is ``core-contract-authored-contrastive-v3``.  Removing only those
rows recreates the winning 1,821-row R2 corpus byte-for-byte.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

EXPECTED_ROWS = 1_821
EXPECTED_SHA256 = "325a287fcb8797893f78aa6bf2209fcf238cdb8c56c2f1dd7001a09d8f095530"
EXCLUDED_SOURCE = "core-contract-authored-contrastive-v3"


def rebuild(source: Path, output: Path) -> None:
    kept: list[str] = []
    excluded = 0
    for line in source.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("source") == EXCLUDED_SOURCE:
            excluded += 1
        else:
            kept.append(line)
    payload = ("\n".join(kept) + "\n").encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    if len(kept) != EXPECTED_ROWS or excluded != 112 or digest != EXPECTED_SHA256:
        raise ValueError(
            f"R2 identity mismatch: kept={len(kept)}, excluded={excluded}, sha256={digest}"
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(payload)
    print(json.dumps({"rows": len(kept), "excluded": excluded, "sha256": digest}))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    rebuild(args.source.resolve(strict=True), args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
