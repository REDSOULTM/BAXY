"""Re-audit un JSON existente con el auditor actual (sin re-correr el modelo).
Util para validar fixes del auditor antes de gastar GPU.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from auditor import audit_case  # noqa
from collections import namedtuple

CaseStub = namedtuple("CaseStub", ["cid", "category", "expected_tools"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    args = ap.parse_args()
    d = json.loads(Path(args.input).read_text(encoding="utf-8"))

    new_pass = 0
    new_partial = 0
    new_fail = 0
    changed = []
    for r in d["results"]:
        case = CaseStub(cid=r["cid"], category=r["category"], expected_tools=r["expected_tools"])
        # For consolidated runs, prefer tools_legacy (translated for auditor compatibility)
        # For individual runs, just use tools.
        tool_names_for_audit = r.get("tools_legacy") or r.get("tools", [])
        tool_calls = [{"name": n} for n in tool_names_for_audit]
        new_audit = audit_case(case, r.get("reply", ""), tool_calls, r.get("latency_ms", 0))
        old_status = r.get("status")
        new_status = new_audit["status"]
        if new_status == "PASS":
            new_pass += 1
        elif new_status == "PARTIAL":
            new_partial += 1
        else:
            new_fail += 1
        if old_status != new_status:
            changed.append((r["cid"], old_status, new_status, new_audit["reasons"]))

    total = len(d["results"])
    print(f"\nReaudit con auditor actual sobre {Path(args.input).name}:")
    print(f"  PASS: {new_pass}  PARTIAL: {new_partial}  FAIL: {new_fail}")
    print(f"  Pass rate: {new_pass/total*100:.2f}%")
    print(f"\nCambios ({len(changed)}):")
    for cid, old, new, reasons in changed[:20]:
        arrow = "->" if new == "PASS" else "x>"
        print(f"  {cid}: {old} {arrow} {new}  {reasons}")


if __name__ == "__main__":
    main()
