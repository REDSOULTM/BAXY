"""Re-judge decision runs of one practice bank against a newer one, from the arguments each run stored.

usage: py -3.12 -X utf8 scripts/renew/compare_banks.py RUN.jsonl... [--old decision2.json] [--new decision3.json] [--write]
       [--catalog FILE]
A run of bench_decision.py keeps, per case, the decision (kind, operation, arguments, reply): no model runs again. Each
row is judged with today's judge (bench_decision.judge, catalog_equivalence) against the old bank and against the new
one, where a relabelled case (new id, «relabel_of» the old one) takes its new expectation and a retired case (in the old
bank, in neither form in the new one) is left out. Prints, per run, the score it wrote, the old bank re-judged and the
new bank, with the cases whose verdict the new labels flip; --write keeps <run>.<new bank>.jsonl beside each run, its
rows under the new ids. Run patterns are expanded (PowerShell does not expand them). With --catalog (the runs' catalog), an
argument of a code list is judged exactly (bench_decision.enums_of); the same bank as --old and --new re-judges runs
with today's judge (holdout: one judge for every configuration).
"""
import argparse
import glob
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bench_decision import enums_of, judge  # noqa: E402

# Where the other scripts find the banks (BAXY_RENEW_BANKS, D: on the notebook): it was F: whatever that said.
PRACTICE = Path(os.environ.get("BAXY_RENEW_BANKS", r"F:\BAXYeval\renew_v1")) / "practica"


def load_bank(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def mapping(old: list[dict], new: list[dict]) -> tuple[dict, list[str]]:
    """Old id → the new bank's case for it (itself, or the case relabelled from it), and the old ids retired."""
    by_id = {c["id"]: c for c in new}
    relabelled = {c["relabel_of"]: c for c in new if c.get("relabel_of")}
    found, retired = {}, []
    for case in old:
        target = relabelled.get(case["id"]) or by_id.get(case["id"])
        if target is None:
            retired.append(case["id"])
        else:
            found[case["id"]] = target
    for case in new:  # a run on the new bank itself names the new ids
        found.setdefault(case["id"], case)
    return found, retired


def verdict(case: dict, row: dict, enums: dict | None = None):
    """True, False, or None when the case is not counted (an operation retired with nothing in its place)."""
    if row.get("error"):
        return False
    return judge(case["expect"], row, row.get("arguments"), enums)


def score(verdicts: list) -> tuple[int, int]:
    counted = [v for v in verdicts if v is not None]
    return sum(bool(v) for v in counted), len(counted)


def rejudge(rows: list[dict], old_by_id: dict, new_by_old: dict, enums: dict | None = None) -> dict:
    old_v, new_v, flips, rows_new, unknown = [], [], [], [], []
    for row in rows:
        old_case, new_case = old_by_id.get(row["id"]), new_by_old.get(row["id"])
        if old_case is None and new_case is None:
            unknown.append(row["id"])
            continue
        before = verdict(old_case, row, enums) if old_case is not None else None
        after = verdict(new_case, row, enums) if new_case is not None else None
        old_v.append(before)
        new_v.append(after)
        if new_case is not None:
            if old_case is not None and before is not None and after is not None and bool(before) != bool(after):
                flips.append(f"{row['id']}→{new_case['id']} {'ok' if after else 'BAD'}")
            rows_new.append({**row, "id": new_case["id"], "relabel_of": new_case.get("relabel_of"),
                             "ok_old_bank": None if before is None else bool(before),
                             "ok": after is not None and bool(after), "excluded": after is None})
    return {"old": score(old_v), "new": score(new_v), "flips": flips, "rows": rows_new, "unknown": unknown}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("runs", nargs="+")
    parser.add_argument("--old", default=str(PRACTICE / "decision2.json"))
    parser.add_argument("--new", default=str(PRACTICE / "decision3.json"))
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--catalog", default="", help="the runs' catalog: code-list arguments judged exactly")
    args = parser.parse_args()
    enums = enums_of(json.loads(Path(args.catalog).read_text(encoding="utf-8"))) if args.catalog else None
    old, new = load_bank(Path(args.old)), load_bank(Path(args.new))
    old_by_id = {c["id"]: c for c in old}
    new_by_old, retired = mapping(old, new)
    print(f"{Path(args.old).name} {len(old)} → {Path(args.new).name} {len(new)}: "
          f"{sum(1 for c in new if c.get('relabel_of'))} relabelled, retired {retired}")
    paths = sorted({p for pattern in args.runs for p in (glob.glob(pattern) or [pattern])})
    bank_names = {Path(args.old).name, Path(args.new).name}
    for path in map(Path, paths):
        if path.name.endswith((".trace.jsonl", ".comun.jsonl")) or path.stem.endswith(Path(args.new).stem):
            continue
        lines = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if not lines or "summary" not in lines[0]:
            print(f"{path.name}: no summary line, skipped")
            continue
        summary, rows = lines[0]["summary"], lines[1:]
        if Path(str(summary.get("cases", ""))).name not in bank_names:
            print(f"{path.name}: a run of {summary.get('cases')}, skipped")
            continue
        result = rejudge(rows, old_by_id, new_by_old, enums)
        (ok_old, n_old), (ok_new, n_new) = result["old"], result["new"]
        print(f"{summary.get('label', path.stem):28} written {summary.get('ok')}/{summary.get('n')}  "
              f"{Path(args.old).stem} {ok_old}/{n_old}  {Path(args.new).stem} {ok_new}/{n_new}  "
              f"flips {' '.join(result['flips']) or '-'}" + (f"  unknown {result['unknown']}" if result["unknown"] else ""))
        if args.write:
            head = {**summary, "cases": args.new, "rejudged_from": str(path), "ok_written": summary.get("ok"),
                    "n_written": summary.get("n"), "ok": ok_new, "n": n_new, "judge_catalog": args.catalog or None,
                    "accuracy": round(ok_new / max(1, n_new), 4), "retired": retired,
                    "excluded_retired": [r["id"] for r in result["rows"] if r["excluded"]]}
            out = path.with_name(f"{path.stem}.{Path(args.new).stem}.jsonl")
            out.write_text("\n".join([json.dumps({"summary": head}, ensure_ascii=False)]
                                     + [json.dumps(r, ensure_ascii=False) for r in result["rows"]]) + "\n",
                           encoding="utf-8")


if __name__ == "__main__":
    main()
