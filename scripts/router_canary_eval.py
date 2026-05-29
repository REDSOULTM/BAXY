"""Canary regression for the router — hand-labeled real-failure + known-good
cases (oracle = manual). A query PASSES when:
  - expect_empty:    the domain subset is empty (correct abstention), OR
  - expect_any:      at least one acceptable tool is present, AND
  - forbid:          no forbidden tool is present.

This is the measurable target toward "100%": the failures found auditing the
337 real trace queries, plus anchors that must not regress. Run after any
router change.

Run:  python scripts/router_canary_eval.py [--show]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
CANARIES = ROOT / "gemma4_agent" / "data" / "router_canaries.jsonl"
_UTIL = {"session", "safety", "state", "verify"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", action="store_true", help="print every case")
    args = ap.parse_args()

    import warnings
    warnings.filterwarnings("ignore")
    from gemma4_agent.routing.planner import select_tool_names, plan_mission

    rows = [json.loads(l) for l in CANARIES.read_text(encoding="utf-8").splitlines() if l.strip()]
    passed = 0
    fails = []
    for r in rows:
        q = r["q"]
        t = select_tool_names(q, plan_mission(q), safety_enabled=True)
        dom = [x for x in t if x not in _UTIL]
        domset = set(dom)
        ok = True
        why = ""
        if r.get("expect_empty"):
            if dom:
                ok = False; why = f"expected EMPTY, got {dom}"
        else:
            if not (set(r.get("expect_any", [])) & domset):
                ok = False; why = f"missing any of {r['expect_any']}, got {dom}"
        forb = set(r.get("forbid", [])) & domset
        if forb:
            ok = False; why = (why + " | " if why else "") + f"forbidden present {sorted(forb)}"
        if ok:
            passed += 1
        else:
            fails.append((q, dom, why))
        if args.show:
            mark = "ok " if ok else "FAIL"
            print(f"  [{mark}] {q[:38]!r:41s} {dom}")

    n = len(rows)
    print(f"\nCANARY PASS: {passed}/{n} = {passed/n:.1%}")
    if fails:
        print(f"\n--- {len(fails)} FAILURES ---")
        for q, dom, why in fails:
            print(f"  {q[:42]!r:45s} {dom}\n      {why}")
    return 0 if passed == n else 1


if __name__ == "__main__":
    sys.exit(main())
