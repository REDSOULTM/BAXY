"""Router evaluation against the hand-curated ground-truth corpus.

Sprint 8 (2026-05-20): a second agent curated the full historical corpus
(this project's logs + Carter v1–v5) into a clean ground truth, every row
labeled by hand/guide (no automatic oracle — that corrupted labels):

    gemma4_agent/data/router_eval_corpus.curated.jsonl   (1733 rows)

Each row: {"q", "expected": ["tool", ...] | [], "source", "label_origin"}
  - expected non-empty → RECALL: at least one acceptable tool must be in
    the router's subset (any one of the listed tools counts as a hit).
  - expected == []     → NO-TOOL: the router must NOT pull a domain tool
    (smalltalk, knowledge the LLM answers itself, behavior directives).

The tools are already in the current 65-compound vocabulary, so no legacy
mapping is needed. We route each query through the REAL planner, passing
the previous user turn as context when available so continuation prompts
get what the planner sees at runtime.

Run:
    python scripts/router_eval.py
    python scripts/router_eval.py --show-fails
    python scripts/router_eval.py --by-tool        # per-tool recall table
    python scripts/router_eval.py --corpus <path>  # eval a different file
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

CURATED = ROOT / "gemma4_agent" / "data" / "router_eval_corpus.curated.jsonl"
# Map query → previous user turn, reconstructed from the ordered logs
# (the curated corpus dropped temporal order). Lets continuation prompts
# ("ciérralo", "haz lo mismo") be routed with the context the planner has
# at runtime. Built by the snippet in this sprint; regenerate if logs grow.
_PREV_MAP_PATH = ROOT / "gemma4_agent" / "data" / "router_prev_map.json"
try:
    _PREV_MAP = json.loads(_PREV_MAP_PATH.read_text(encoding="utf-8")) \
        if _PREV_MAP_PATH.exists() else {}
except Exception:
    _PREV_MAP = {}

# Anti-overfit holdout. Each row is assigned to dev (80%) or holdout (20%)
# by a STABLE hash of its query text — independent of file order, fixed
# across runs, and not derivable from the planner. We develop/tune against
# dev ONLY and report the holdout as the honest, never-seen-in-dev number.
_HOLDOUT_SALT = "router-eval-2026-05-20"


def _split_of(q: str) -> str:
    h = hashlib.sha256((_HOLDOUT_SALT + q).encode("utf-8")).hexdigest()
    return "holdout" if (int(h[:8], 16) % 5 == 0) else "dev"

# Utility tools that are always reachable / harmless; their presence does
# NOT count as "the router pulled a domain tool" for the no-tool metric.
_NON_DOMAIN = {"session", "safety", "state", "verify"}


def run_router(q: str, prev: str | None = None) -> set[str]:
    # safety_enabled=True mirrors production: the planner appends `safety`
    # so risky actions ("formatea el pendrive", "edita el registry") can be
    # gated. Running with it off hid the safety tool from the subset.
    from gemma4_agent.planner import select_tool_names, plan_mission
    return set(select_tool_names(
        q, plan_mission(q), safety_enabled=True,
        last_assistant_text=prev,
    ))


def _evaluate(rows: list[dict]):
    recall_total = recall_ok = 0
    notool_total = notool_ok = 0
    recall_fails: list[tuple[str, list[str], list[str]]] = []
    notool_fails: list[tuple[str, list[str]]] = []
    per_tool = collections.defaultdict(lambda: [0, 0])

    for r in rows:
        q = r["q"]
        expected = r.get("expected") or []
        # The planner does not inherit from prior user text (measured
        # net-negative; the agent does it from real history). So we route
        # each query as the planner sees it on a fresh turn. prev is kept
        # available for analysis but not passed.
        subset = run_router(q, None)
        if expected:
            recall_total += 1
            hit = bool(subset & set(expected))
            if hit:
                recall_ok += 1
            else:
                recall_fails.append((q, expected, sorted(subset)))
            for t in expected:
                per_tool[t][1] += 1
                if hit:
                    per_tool[t][0] += 1
        else:
            notool_total += 1
            if not (subset - _NON_DOMAIN):
                notool_ok += 1
            else:
                notool_fails.append((q, sorted(subset - _NON_DOMAIN)))
    return {
        "recall_ok": recall_ok, "recall_total": recall_total,
        "notool_ok": notool_ok, "notool_total": notool_total,
        "recall_fails": recall_fails, "notool_fails": notool_fails,
        "per_tool": per_tool,
    }


def _print_block(name: str, m: dict) -> None:
    rt, ro = m["recall_total"], m["recall_ok"]
    nt, no = m["notool_total"], m["notool_ok"]
    print(f"  [{name}]  TOOL RECALL {ro}/{rt}={ro/max(1,rt):.4f}   "
          f"NO-TOOL keep {no}/{nt}={no/max(1,nt):.4f}   "
          f"(recall misses {len(m['recall_fails'])}, "
          f"over-offers {len(m['notool_fails'])})")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--show-fails", action="store_true")
    ap.add_argument("--by-tool", action="store_true")
    ap.add_argument("--corpus", type=Path, default=CURATED)
    ap.add_argument("--split", choices=["dev", "holdout", "all", "both"],
                    default="both")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    if not args.corpus.exists():
        print(f"corpus missing: {args.corpus}")
        return 1
    rows = [json.loads(l) for l in args.corpus.read_text(encoding="utf-8").splitlines() if l.strip()]
    if args.limit:
        rows = rows[: args.limit]

    dev = [r for r in rows if _split_of(r["q"]) == "dev"]
    hold = [r for r in rows if _split_of(r["q"]) == "holdout"]

    print("=" * 70)
    print(f"Router eval — {args.corpus.name}  ({len(rows)} rows; "
          f"dev={len(dev)} holdout={len(hold)})")
    print("=" * 70)

    targets = []
    if args.split in ("dev", "both"):
        targets.append(("dev", dev))
    if args.split in ("holdout", "both"):
        targets.append(("holdout", hold))
    if args.split == "all":
        targets.append(("all", rows))

    last = None
    for name, subset_rows in targets:
        m = _evaluate(subset_rows)
        _print_block(name, m)
        last = (name, m)

    # detail uses the LAST evaluated split (so --split holdout --show-fails
    # shows holdout fails; default 'both' shows holdout detail).
    if last and (args.by_tool or args.show_fails):
        name, m = last
        if args.by_tool:
            print(f"\n  per-tool recall on [{name}] (hit/total):")
            for t, (h, n) in sorted(m["per_tool"].items(), key=lambda x: -x[1][1]):
                flag = "" if h == n else "  <-- misses"
                print(f"    {t:16s} {h:4d}/{n:<4d} = {h/max(1,n):.3f}{flag}")
        if args.show_fails:
            print(f"\n--- RECALL misses on [{name}] ---")
            for q, exp, sub in m["recall_fails"][:120]:
                print(f"  {q[:60]!r}\n     expected={exp}  subset={sub}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
