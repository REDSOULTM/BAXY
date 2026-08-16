"""Build the frozen semantic vectors used during BAXY startup.

The generated files are versioned with the intent bank. Production validates
the bank SHA-256 and falls back to recomputing the vectors if either artifact
is missing or stale.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "src"))

from baxy_mind.router import (  # noqa: E402
    BANK_PATH,
    MODEL_NAME,
    POOL_METADATA_PATH,
    POOL_PATH,
    QUERY_PREFIX,
)


def main() -> None:
    from sentence_transformers import SentenceTransformer

    bank_bytes = BANK_PATH.read_bytes()
    rows = [json.loads(line) for line in bank_bytes.decode("utf-8").splitlines()]
    if not rows:
        raise ValueError("intent bank is empty")

    model = SentenceTransformer(MODEL_NAME, device="cpu")
    pool = model.encode(
        [QUERY_PREFIX + str(row["text"]) for row in rows],
        normalize_embeddings=True,
        show_progress_bar=False,
    ).astype(np.float32, copy=False)

    POOL_PATH.parent.mkdir(parents=True, exist_ok=True)
    np.save(POOL_PATH, pool, allow_pickle=False)
    metadata = {
        "schema": "baxy-intent-pool-v1",
        "model": MODEL_NAME,
        "bank_sha256": hashlib.sha256(bank_bytes).hexdigest(),
        "pool_sha256": hashlib.sha256(POOL_PATH.read_bytes()).hexdigest(),
        "rows": len(rows),
        "dimensions": int(pool.shape[1]),
        "normalized": True,
    }
    POOL_METADATA_PATH.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        f"router pool: {pool.shape[0]}x{pool.shape[1]} -> "
        f"{POOL_PATH} ({POOL_PATH.stat().st_size} bytes)"
    )


if __name__ == "__main__":
    main()
