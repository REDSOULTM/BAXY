"""Build per-tool Tool2Vec centroids from the synthetic queries (Step 4b).

Reads data/tool2vec_queries.jsonl (produced by router_tool2vec_generate.py),
embeds every query with the SAME runtime encoder the planner uses
(paraphrase-multilingual-MiniLM-L12-v2 via semantic_router.embed), and stores
the L2-normalized MEAN embedding per tool — the Tool2Vec representation.

Output: data/tool2vec_centroids.npz  (names[], centroids[N,384], meta)
This is a reproducible artifact: regenerate any time from the queries + the
fixed encoder. The runtime (semantic_router) blends this centroid with the
description embedding; the blend weight is tuned on dev in router_eval.

Run:  python scripts/router_tool2vec_build.py
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

QUERIES = ROOT / "gemma4_agent" / "data" / "tool2vec_queries.jsonl"
OUT = ROOT / "gemma4_agent" / "data" / "tool2vec_centroids.npz"


def main() -> int:
    import numpy as np
    from gemma4_agent.routing.semantic_router import embed, _MODEL_NAME_DEFAULT

    if not QUERIES.exists():
        print(f"missing {QUERIES} — run router_tool2vec_generate.py first")
        return 1

    by_tool: dict[str, list[str]] = defaultdict(list)
    for ln in QUERIES.read_text(encoding="utf-8").splitlines():
        if ln.strip():
            d = json.loads(ln)
            by_tool[d["tool"]].append(d["q"])
    print(f"tools with queries: {len(by_tool)}  "
          f"total queries: {sum(len(v) for v in by_tool.values())}")

    names = sorted(by_tool)
    centroids = []
    for name in names:
        vecs = []
        for q in by_tool[name]:
            v = embed(q)
            if v is not None:
                vecs.append(np.asarray(v, dtype="float32"))
        if not vecs:
            print(f"  {name}: NO embeddings (encoder unavailable?)")
            return 2
        mean = np.mean(np.stack(vecs), axis=0)
        norm = np.linalg.norm(mean)
        if norm > 0:
            mean = mean / norm
        centroids.append(mean)
        print(f"  {name}: {len(vecs)} queries -> centroid")
    centroids = np.stack(centroids).astype("float32")

    np.savez(OUT, names=np.array(names, dtype=object),
             centroids=centroids, encoder=_MODEL_NAME_DEFAULT)
    print(f"\nwrote {OUT}  shape={centroids.shape}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
