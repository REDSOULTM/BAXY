"""Diagnostic: attribute router misses/over-offers to their pipeline source.

For each corpus row, decompose the subset into the contribution of each
stage so we know WHERE to intervene:
  - kw      : _suggest_tools (keyword regex)
  - sem     : semantic_router.suggest_tools_semantic (embedding similarity)
  - intent  : intent_router.wants_knowledge (web/knowledge)

This is a read-only audit; it does not change routing. Run on dev only
(holdout stays blind for tuning decisions).

    python scripts/router_diag.py --split dev
    python scripts/router_diag.py --split dev --notool   # over-offer sources
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.router_eval import CURATED, _split_of, _NON_DOMAIN  # noqa: E402


def _stage_sources(q: str) -> dict[str, set[str]]:
    """Return tools contributed by each stage (best-effort decomposition)."""
    from gemma4_agent.planner import _suggest_tools, _fold_text
    out: dict[str, set[str]] = {}
    out["kw"] = set(_suggest_tools(q))
    try:
        from gemma4_agent.semantic_router import suggest_tools_semantic
        out["sem"] = set(suggest_tools_semantic(q, k=12)) if q.strip() else set()
    except Exception:
        out["sem"] = set()
    try:
        from gemma4_agent.intent_router import wants_knowledge
        out["intent"] = {"web", "knowledge"} if wants_knowledge(q) else set()
    except Exception:
        out["intent"] = set()
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="dev")
    ap.add_argument("--notool", action="store_true",
                    help="audit over-offers on expected==[] rows")
    ap.add_argument("--recall", action="store_true",
                    help="audit recall misses on expected!=[] rows")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    rows = [json.loads(l) for l in CURATED.read_text(encoding="utf-8").splitlines() if l.strip()]
    rows = [r for r in rows if _split_of(r["q"]) == args.split]
    if args.limit:
        rows = rows[: args.limit]

    from scripts.router_eval import run_router

    if args.notool:
        rows = [r for r in rows if not (r.get("expected") or [])]
        # Which stage introduced the domain tool that broke no-tool keep?
        blame = collections.Counter()
        examples = collections.defaultdict(list)
        bad = 0
        for r in rows:
            q = r["q"]
            subset = run_router(q, None) - _NON_DOMAIN
            if not subset:
                continue
            bad += 1
            src = _stage_sources(q)
            for t in subset:
                tags = [name for name in ("kw", "sem", "intent") if t in src[name]]
                tag = "+".join(tags) if tags else "?"
                blame[tag] += 1
                if len(examples[tag]) < 6:
                    examples[tag].append((q[:40], t))
        print(f"[{args.split}] over-offering rows: {bad}/{len(rows)}")
        print("blame by stage (tool-instances):")
        for tag, n in blame.most_common():
            print(f"  {tag:14s} {n}")
        print("\nexamples:")
        for tag, ex in sorted(examples.items()):
            print(f"  [{tag}]")
            for q, t in ex:
                print(f"      {t:14s} <- {q!r}")
        return 0

    if args.recall:
        rows = [r for r in rows if (r.get("expected") or [])]
        # For each miss, did ANY stage have the right tool?
        recoverable = collections.Counter()
        miss = 0
        examples = collections.defaultdict(list)
        for r in rows:
            q = r["q"]
            exp = set(r["expected"])
            subset = run_router(q, None)
            if subset & exp:
                continue
            miss += 1
            src = _stage_sources(q)
            present = [name for name in ("kw", "sem", "intent")
                       if src[name] & exp]
            tag = "+".join(present) if present else "none-had-it"
            recoverable[tag] += 1
            if len(examples[tag]) < 8:
                examples[tag].append((q[:45], sorted(exp)))
        print(f"[{args.split}] recall misses: {miss}/{len(rows)}")
        print("which stage HAD the right tool (but it got dropped/capped):")
        for tag, n in recoverable.most_common():
            print(f"  {tag:14s} {n}")
        print("\nexamples:")
        for tag, ex in sorted(examples.items()):
            print(f"  [{tag}]")
            for q, exp in ex:
                print(f"      expected={exp}  <- {q!r}")
        return 0

    print("pass --notool or --recall")
    return 1


if __name__ == "__main__":
    sys.exit(main())
