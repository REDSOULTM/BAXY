# -*- coding: utf-8 -*-
"""Eval del CAMINO FG (lo que el runtime con GEMMA4_FG_ROUTER=1 realmente usa).

router_eval.py mide la PLANNER path (select_tool_names + exemplar memory), pero el
runtime FG rutea por fg_router.fg_emit -> sr.suggest_tools_scored (encoder + tool2vec
centroids) + KVA gate + act-gate, SIN exemplar ni planner. Por eso router_eval no
mide lo que Baxy hace, y su número no sirve para juzgar un reentreno del encoder.

Este eval reproduce la decisión PRE-FunctionGemma de fg_emit (encoder + gates; NO
llama a FunctionGemma, que elige la tool DENTRO del subset y no se reentrena acá) y
mide, sobre el MISMO corpus/split que router_eval:

  - TOOL recall   : de las queries con tool, ¿el act-gate dispara (no KVA-knowledge)
                    Y la familia esperada cae en el subset top-fam_k?  (lo que define
                    si FunctionGemma siquiera puede elegir bien)
  - top-1 familia : ¿la familia esperada es el top-1 del encoder?
  - NO-TOOL keep  : de las queries de chitchat, ¿NO rutea (KVA-knowledge o act-gate
                    no dispara)?  -> mide la abstención del camino FG

HONESTO por construcción: suggest_tools_scored usa encoder + centroids (sintéticos),
NO el eval corpus, así que NO hay auto-match/contaminación (a diferencia del exemplar).

Uso:   python scripts/router_eval_fg.py [--split both|dev|holdout] [--show-fails]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

CORPUS = ROOT / "gemma4_agent" / "data" / "router_eval_corpus.curated.jsonl"
_HOLDOUT_SALT = "router-eval-2026-05-20"


def _split_of(q: str) -> str:
    h = hashlib.sha256((_HOLDOUT_SALT + q).encode("utf-8")).hexdigest()
    return "holdout" if (int(h[:8], 16) % 5 == 0) else "dev"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["dev", "holdout", "both"], default="both")
    ap.add_argument("--fam-k", type=int, default=3, help="familias en el subset (igual que fg_emit)")
    ap.add_argument("--show-fails", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    import numpy as np
    from gemma4_agent.routing import fg_router as fg
    from gemma4_agent.routing.fg_router import (
        _FGRouter, _is_interrogative, _norm, FG_ACT_PEAK, FG_ACT_FLOOR,
    )

    if fg._R is None:
        fg._R = _FGRouter()
    R = fg._R

    rows = [json.loads(l) for l in CORPUS.read_text(encoding="utf-8").splitlines() if l.strip()]
    if args.limit:
        rows = rows[: args.limit]

    def fg_decision(q: str):
        """Reproduce la decisión pre-FunctionGemma de fg_emit. Devuelve (route, top_fams,
        top1_fam, top1_score)."""
        scored = R.sr.suggest_tools_scored(q, k=12)
        if not scored:
            return False, [], None, 0.0
        top1_fam, top1 = scored[0]
        top_fams = [f for f, _ in scored[: args.fam_k]]
        # KVA gate (conocimiento -> no_tool), igual que fg_emit
        is_know = False
        if R.kva is not None:
            try:
                emb = _norm(np.asarray(R.sr.embed(q), dtype=np.float32))
                is_know = bool(R.kva.is_knowledge(emb))
            except Exception:
                is_know = False
        # act-gate: top1>=PEAK o (interrogativa y top1>=FLOOR). (e2b_emitted=False acá.)
        actionable = (top1 >= FG_ACT_PEAK) or (_is_interrogative(q) and top1 >= FG_ACT_FLOOR)
        route = (not is_know) and actionable
        return route, top_fams, top1_fam, top1

    print("=" * 70)
    print(f"FG-path eval — {CORPUS.name}  (camino del runtime: encoder+centroids+gates)")
    print("=" * 70)

    targets = []
    dev = [r for r in rows if _split_of(r["q"]) == "dev"]
    hold = [r for r in rows if _split_of(r["q"]) == "holdout"]
    if args.split in ("dev", "both"):
        targets.append(("dev", dev))
    if args.split in ("holdout", "both"):
        targets.append(("holdout", hold))

    for name, subset_rows in targets:
        tool_rows = [r for r in subset_rows if (r.get("expected") or [])]
        notool_rows = [r for r in subset_rows if not (r.get("expected") or [])]
        t_recall = t_top1 = 0
        nk = 0
        fails = []
        for r in tool_rows:
            exp = set(r.get("expected") or []) | set(r.get("expected_equiv") or [])
            route, top_fams, top1_fam, top1 = fg_decision(r["q"])
            in_subset = bool(exp & set(top_fams))
            if route and in_subset:
                t_recall += 1
            elif args.show_fails:
                fails.append((r["q"], sorted(exp), top_fams, round(top1, 3), route))
            if top1_fam in exp:
                t_top1 += 1
        for r in notool_rows:
            route, *_ = fg_decision(r["q"])
            if not route:
                nk += 1
        nt = max(1, len(tool_rows))
        nn = max(1, len(notool_rows))
        print(f"\n  [{name}]  TOOL recall {t_recall}/{len(tool_rows)}={t_recall/nt:.4f}   "
              f"top-1 fam {t_top1}/{len(tool_rows)}={t_top1/nt:.4f}   "
              f"NO-TOOL keep {nk}/{len(notool_rows)}={nk/nn:.4f}")
        if args.show_fails and fails:
            print(f"    -- {len(fails)} recall-fails (muestra) --")
            for q, exp, fams, sc, route in fails[:25]:
                print(f"      {q[:42]!r:44} exp={exp} top={fams} s={sc} route={route}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
