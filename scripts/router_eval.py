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
    # prev is the PREVIOUS USER TURN (corpus `prev` field), passed as
    # prev_user_text so deictic continuations can resolve their referent —
    # this is what the planner sees at runtime when context is available.
    from gemma4_agent.planner import select_tool_names, plan_mission
    return set(select_tool_names(
        q, plan_mission(q), safety_enabled=True,
        prev_user_text=prev,
    ))


# ---- runtime inherit_tools simulation -------------------------------------
# The harness above measures the router IN ISOLATION. Production does more:
# when the router returns no domain tool AND the turn is a short continuation
# ("ciérralo", "mutea"), agent.py inherits the tools the PRIOR turn actually
# executed (NOT the prior text — the deictic's referent lives in the executed
# tool). --inherit reproduces that so we see the real production recall.
# We mirror agent.py's rules: <=6 words, and never inherit dangerous tools.
try:
    from gemma4_agent.agent import DANGEROUS_TOOLS_NEVER_INHERIT as _DANGEROUS
except Exception:
    _DANGEROUS = frozenset({
        "whatsapp", "whatsapp_send", "file_delete", "file_write",
        "system_shutdown", "system_logoff", "system_restart",
        "subprocess", "shell",
    })


def _build_executed_map(rows: list[dict]) -> dict[str, list[str]]:
    """Approximate 'what tool ran on turn T' by T's curated expected tools.
    This is the signal agent.py inherits from real tool-call history; on the
    corpus the closest proxy is the prior turn's ground-truth label."""
    return {r["q"].strip().lower(): list(r.get("expected") or []) for r in rows}


def _inherit_from_prev(q: str, prev: str | None,
                       executed: dict[str, list[str]]) -> set[str]:
    """Mirror agent.py inherit_tools: for a short continuation with a known
    prior turn, inherit that turn's executed (non-dangerous) tools."""
    if not prev:
        return set()
    if len(q.split()) > 6:           # same <=6-word gate as runtime
        return set()
    prior = executed.get(prev.strip().lower())
    if not prior:
        return set()
    return {t for t in prior if t not in _DANGEROUS}


def _evaluate(rows: list[dict], use_prev: bool = False,
              inherit: bool = False, all_rows: list[dict] | None = None):
    recall_total = recall_ok = 0
    notool_total = notool_ok = 0
    recall_fails: list[tuple[str, list[str], list[str]]] = []
    notool_fails: list[tuple[str, list[str]]] = []
    per_tool = collections.defaultdict(lambda: [0, 0])
    # executed-tool map for the inherit simulation (built from the WHOLE
    # corpus, not just this split, because a continuation's prior turn may
    # live in the other split).
    executed = _build_executed_map(all_rows if all_rows is not None else rows) if inherit else {}

    for r in rows:
        q = r["q"]
        expected = r.get("expected") or []
        # --use-prev measures the realistic production case: the planner
        # gets the previous user turn (corpus `prev`) so deictic
        # continuations can resolve. Default (no prev) is the honest
        # isolated number — how the router does with zero context.
        prev = (r.get("prev") if (use_prev or inherit) else None)
        subset = run_router(q, prev)
        # --inherit: reproduce agent.py's continuation inheritance. Like the
        # runtime, only kicks in when the router pulled NO domain tool.
        if inherit and not (subset - _NON_DOMAIN):
            subset |= _inherit_from_prev(q, prev, executed)
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
    ap.add_argument("--use-prev", action="store_true",
                    help="pass the previous user turn (realistic production "
                         "context) so deictic continuations can resolve")
    ap.add_argument("--inherit", action="store_true",
                    help="simulate agent.py inherit_tools: short continuations "
                         "with no router tool inherit the prior turn's executed "
                         "tools. This is the REAL production recall (the router "
                         "alone under-measures it).")
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

    if args.use_prev:
        print("  (context mode: passing previous user turn — production-like)")
    if args.inherit:
        print("  (inherit mode: simulating agent.py continuation inheritance "
              "— REAL production recall)")
    last = None
    for name, subset_rows in targets:
        m = _evaluate(subset_rows, use_prev=args.use_prev,
                      inherit=args.inherit, all_rows=rows)
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
