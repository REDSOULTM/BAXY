"""Build the semantic exemplar router artifact from curated router labels.

The artifact is a compact NPZ with:
  - query texts
  - reviewed expected tool labels
  - normalized multilingual embeddings

Runtime code uses this as a high-confidence semantic memory, not as regex or a
tool-specific phrase table.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DEFAULT_CORPUS = ROOT / "gemma4_agent" / "data" / "router_eval_corpus.curated.jsonl"
DEFAULT_OUT = ROOT / "gemma4_agent" / "data" / "router_exemplars.npz"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()

    if not args.corpus.exists():
        print(f"missing corpus: {args.corpus}")
        return 1

    import numpy as np
    from gemma4_agent.semantic_router import TOOL_DESCRIPTIONS, embed

    known = set(TOOL_DESCRIPTIONS)
    rows = [
        json.loads(line)
        for line in args.corpus.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    queries: list[str] = []
    labels: list[str] = []
    vectors: list[np.ndarray] = []
    skipped = 0
    unknown_labels: set[str] = set()
    for i, row in enumerate(rows, start=1):
        q = str(row.get("q") or "").strip()
        if not q:
            skipped += 1
            continue
        expected = []
        for tool in row.get("expected") or []:
            tool = str(tool)
            if tool in known:
                expected.append(tool)
            else:
                unknown_labels.add(tool)
        v = embed(q)
        if v is None:
            skipped += 1
            continue
        queries.append(q)
        labels.append(json.dumps(list(dict.fromkeys(expected)), ensure_ascii=False))
        vectors.append(np.asarray(v, dtype=np.float32))
        if i % 250 == 0:
            print(f"embedded {i}/{len(rows)}")

    if not vectors:
        print("no embeddings produced")
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        args.out,
        queries=np.asarray(queries, dtype="U"),
        labels=np.asarray(labels, dtype="U"),
        embeddings=np.vstack(vectors).astype(np.float32),
        meta=json.dumps(
            {
                "source": str(args.corpus.relative_to(ROOT)),
                "rows": len(rows),
                "embedded": len(vectors),
                "skipped": skipped,
                "unknown_labels": sorted(unknown_labels),
            },
            ensure_ascii=False,
        ),
    )
    print(f"wrote {args.out} ({len(vectors)} exemplars, skipped={skipped})")
    if unknown_labels:
        print(f"unknown labels ignored: {sorted(unknown_labels)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
