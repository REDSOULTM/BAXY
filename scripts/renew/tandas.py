"""Batches for the banks whose runner reads a whole cases file (bench_decision, bench_escenas): no measuring step may
last more than 5 minutes, so a bank is split into files of at most --por cases, each run under its own label, and the
runs are joined back into one jsonl that summarize.py and pareado.py read as if it were a single run.

    py scripts/renew/tandas.py partir <cases.json> --por 40 --out <dir>
    py scripts/renew/tandas.py juntar <out.jsonl> <run1.jsonl> <run2.jsonl> ...

juntar refuses runs measured with something else (their summaries' "run" records differ: another mind, judge, model,
catalog or settings) and a case id seen twice, so a joined run is never a mix that no single run could have been."""
import argparse
import json
import statistics
from pathlib import Path


def partir(cases_path: Path, por: int, out: Path) -> list[Path]:
    cases = json.loads(cases_path.read_text(encoding="utf-8"))
    if not isinstance(cases, list) or not cases:
        raise SystemExit(f"{cases_path}: not a non-empty list of cases")
    if por < 1:
        raise SystemExit("--por must be at least 1")
    ids = [str(case["id"]) for case in cases]
    repeated = sorted({i for i in ids if ids.count(i) > 1})
    if repeated:
        raise SystemExit(f"{cases_path}: repeated ids {repeated}")
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for number, start in enumerate(range(0, len(cases), por), 1):
        target = out / f"{cases_path.stem}.t{number:02d}.json"
        target.write_text(json.dumps(cases[start:start + por], ensure_ascii=False, indent=1), encoding="utf-8")
        written.append(target)
    return written


def _read(run: Path) -> tuple[dict, list[dict]]:
    lines = [json.loads(line) for line in run.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines or "summary" not in lines[0]:
        raise SystemExit(f"{run}: its first line is not a run summary")
    return lines[0]["summary"], lines[1:]


def juntar(runs: list[Path]) -> dict:
    summaries, rows = [], []
    for run in runs:
        summary, its_rows = _read(run)
        summaries.append(summary)
        rows.extend(its_rows)
    records = [summary.get("run") for summary in summaries]
    if any(record != records[0] for record in records[1:]):
        differ = sorted({key for record in records[1:] for key in set(record or {}) | set(records[0] or {})
                         if (record or {}).get(key) != (records[0] or {}).get(key)})
        raise SystemExit(f"the runs were measured with something else: {differ}")
    ids = [str(row["id"]) for row in rows]
    repeated = sorted({i for i in ids if ids.count(i) > 1})
    if repeated:
        raise SystemExit(f"a case in more than one run: {repeated}")
    counted = [row for row in rows if not row.get("excluded")]
    families: dict[str, list[int]] = {}
    for row in counted:
        if "family" in row:
            family = families.setdefault(str(row["family"] or "-"), [0, 0])
            family[0] += bool(row["ok"])
            family[1] += 1
    latencies = [row["latency_s"] for row in rows if row.get("latency_s") is not None]
    ok = sum(bool(row["ok"]) for row in counted)
    return {"label": "+".join(str(summary.get("label")) for summary in summaries), "ok": ok, "n": len(counted),
            "accuracy": round(ok / max(1, len(counted)), 4),
            "excluded_retired": [row["id"] for row in rows if row.get("excluded")],
            "errors": sum(1 for row in rows if row.get("error")),
            "error_ids": [row["id"] for row in rows if row.get("error")],
            "p50": round(statistics.median(latencies), 3) if latencies else None,
            "p90": round(statistics.quantiles(latencies, n=10)[8], 3) if len(latencies) > 2 else None,
            "families": families or None, "run": records[0],
            # Whatever a runner adds to its summary (resources, warm_s, System One, annoying…) stays, per batch.
            "tandas": summaries, "rows": rows}


def main() -> None:
    parser = argparse.ArgumentParser(description="split a bank into batches and join their runs")
    commands = parser.add_subparsers(dest="command", required=True)
    split = commands.add_parser("partir")
    split.add_argument("cases", type=Path)
    split.add_argument("--por", type=int, required=True, help="cases per batch")
    split.add_argument("--out", type=Path, required=True)
    join = commands.add_parser("juntar")
    join.add_argument("out", type=Path)
    join.add_argument("runs", type=Path, nargs="+")
    args = parser.parse_args()
    if args.command == "partir":
        for path in partir(args.cases, args.por, args.out):
            print(path)
        return
    joined = juntar(args.runs)
    rows = joined.pop("rows")
    with open(args.out, "w", encoding="utf-8") as out:
        out.write(json.dumps({"summary": joined}, ensure_ascii=False) + "\n")
        for row in rows:
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps({key: joined[key] for key in ("label", "ok", "n", "accuracy", "errors")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
