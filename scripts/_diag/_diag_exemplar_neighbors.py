"""Show the top exemplar neighbors + their labels + the abstain-vs-tool vote for
a query. Throwaway diagnostic for the exemplar abstain decision."""
from __future__ import annotations
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import numpy as np
from gemma4_agent.routing import exemplar_router as ex
from gemma4_agent.routing.semantic_router import embed

idx = ex._load()
print(f"store: {len(idx.queries)} exemplars  MIN_SCORE={ex._MIN_SCORE} MARGIN={ex._ABSTAIN_MARGIN} TOP_K={ex._TOP_K}")

QUERIES = [
    "que recuerdas de mi",
    "que sabes de mi",
    "que recordas de mi",
    "abre el navegador",  # control: now fixed
]

for q in QUERIES:
    qv = np.asarray(embed(q), dtype=np.float32)
    scores = idx.embeddings @ qv
    top = np.argsort(-scores)[:8]
    print("=" * 70)
    print(f"Q: {q!r}")
    votes = {}
    abstain_vote = 0.0
    for rank, raw_i in enumerate(top):
        i = int(raw_i)
        s = float(scores[i])
        lab = idx.labels[i]
        used = s >= ex._MIN_SCORE
        w = s * s if used else 0.0
        if used:
            if not lab:
                abstain_vote += w
            else:
                for t in lab:
                    votes[t] = votes.get(t, 0.0) + w
        flag = "" if used else "  (below MIN_SCORE, ignored)"
        print(f"  #{rank} score={s:.4f} label={list(lab)} q={idx.queries[i]!r}{flag}")
    best_tool = max(votes.values(), default=0.0)
    print(f"  --> abstain_vote={abstain_vote:.4f}  best_tool_vote={best_tool:.4f}  "
          f"threshold(abstain wins if > best*{1+ex._ABSTAIN_MARGIN:.2f})={best_tool*(1+ex._ABSTAIN_MARGIN):.4f}")
    print(f"  --> votes={ {k: round(v,4) for k,v in votes.items()} }")
    decision = "ABSTAIN" if abstain_vote > best_tool * (1.0 + ex._ABSTAIN_MARGIN) else "TOOLS"
    print(f"  --> DECISION: {decision}")
