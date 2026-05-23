"""Merges chunked bench JSONs into single results/{tag}_full.json with full stats."""
import argparse
import json
from collections import defaultdict
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--quant", required=True)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    root = Path(__file__).parent / "results"
    pattern = f"{args.tag}_{args.quant}_*.json"
    files = sorted(root.glob(pattern))
    if not files:
        print(f"No files match {pattern}")
        return

    all_results = []
    by_cat = defaultdict(lambda: {"pass": 0, "partial": 0, "fail": 0})
    p = part = f = 0
    for fp in files:
        d = json.loads(fp.read_text(encoding="utf-8"))
        for r in d.get("results", []):
            all_results.append(r)
            cat = r.get("category", -1)
            st = r.get("status", "FAIL")
            if st == "PASS":
                p += 1; by_cat[cat]["pass"] += 1
            elif st == "PARTIAL":
                part += 1; by_cat[cat]["partial"] += 1
            else:
                f += 1; by_cat[cat]["fail"] += 1

    total = len(all_results)
    summary = {
        "completed": total, "total": total,
        "pass": p, "partial": part, "fail": f,
        "pass_rate": round(p / total * 100, 2) if total else 0,
        "partial_or_pass_rate": round((p + part) / total * 100, 2) if total else 0,
        "model": args.quant,
        "by_category": dict(by_cat),
    }

    out_path = Path(args.out) if args.out else (root / f"{args.tag}_{args.quant}_FULL.json")
    out_path.write_text(json.dumps({"summary": summary, "results": all_results},
                                    ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Merged {len(files)} chunks -> {out_path}")
    print(f"\nTOTAL {total}  PASS {p}  PARTIAL {part}  FAIL {f}")
    print(f"Pass rate: {summary['pass_rate']}%  (with PARTIAL: {summary['partial_or_pass_rate']}%)")
    print("\nBy category:")
    for cat in sorted(by_cat.keys()):
        s = by_cat[cat]
        tot = sum(s.values())
        rate = round(s["pass"] / tot * 100, 1) if tot else 0
        print(f"  C{cat:02d}  {s['pass']:>3}/{tot}  ({rate}%)  fail={s['fail']}")


if __name__ == "__main__":
    main()
