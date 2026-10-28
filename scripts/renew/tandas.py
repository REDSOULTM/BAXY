"""Batches for the banks whose runner reads a whole cases file (bench_decision, bench_escenas): no measuring step may
last more than 5 minutes, so a bank is split into files of at most --por cases, each run under its own label, and
bench_decision's runs are joined back into one jsonl that summarize.py and pareado.py read as if it were a single run.

    py scripts/renew/tandas.py partir <cases.json> --por 40 --out <dir>
    py scripts/renew/tandas.py juntar --casos <cases.json> --out <label>-decision.jsonl <run1.jsonl> <run2.jsonl> ...

juntar refuses a run with no "run" record (bench_escenas writes none), runs measured with something else (another
mind, judge, model, catalog or setting; the machine and the folders may differ), a case run twice and a case of the
bank that no run has, so a joined run is never a mix, nor a smaller bank, that no single run could have been."""
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
    old = sorted(out.glob(f"{cases_path.stem}.t*.json"))
    if old:  # batches of an earlier split would be run with these and repeat cases
        raise SystemExit(f"{out} already has batches of {cases_path.stem}: {[p.name for p in old]}")
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


def _measured_with(record: dict) -> dict:
    """A run record (run_meta) without where the run happened: the machine, the folders, a file's path (its bytes and
    sha256 stay) and the BAXY_* values that are paths (BAXY_DATA_DIR is one per label)."""
    same = {}
    for key, value in record.items():
        if key in ("machine", "src"):
            continue
        if isinstance(value, dict) and "path" in value:
            value = {k: v for k, v in value.items() if k != "path"}
        if key == "env":
            value = {k: v for k, v in value.items() if not ("/" in v or "\\" in v)}
        same[key] = value
    return same


def juntar(runs: list[Path], cases_path: Path) -> dict:
    summaries, rows = [], []
    for run in runs:
        summary, its_rows = _read(run)
        if not isinstance(summary.get("run"), dict):
            raise SystemExit(f"{run}: no run record to tell what it was measured with")
        summaries.append(summary)
        rows.extend(its_rows)
    records = [_measured_with(summary["run"]) for summary in summaries]
    differ = sorted({key for record in records[1:] for key in set(record) | set(records[0])
                     if record.get(key) != records[0].get(key)})
    if differ:
        raise SystemExit(f"the runs were measured with something else: {differ}")
    ids = [str(row["id"]) for row in rows]
    repeated = sorted({i for i in ids if ids.count(i) > 1})
    if repeated:
        raise SystemExit(f"a case in more than one run: {repeated}")
    bank = [str(case["id"]) for case in json.loads(cases_path.read_text(encoding="utf-8"))]
    missing, foreign = sorted(set(bank) - set(ids)), sorted(set(ids) - set(bank))
    if missing or foreign:  # a batch left out would give a smaller bank with nothing said
        raise SystemExit(f"the runs are not {cases_path.name}: missing {missing}, not in it {foreign}")
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
            "families": families or None, "run": summaries[0]["run"],
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
    join.add_argument("--casos", type=Path, required=True, help="the whole bank the batches came from")
    join.add_argument("--out", type=Path, required=True)
    join.add_argument("runs", type=Path, nargs="+")
    args = parser.parse_args()
    if args.command == "partir":
        for path in partir(args.cases, args.por, args.out):
            print(path)
        return
    if args.out.exists():  # never over a run, nor over a joined run kept from before
        raise SystemExit(f"{args.out} already exists")
    joined = juntar(args.runs, args.casos)
    rows = joined.pop("rows")
    with open(args.out, "w", encoding="utf-8") as out:
        out.write(json.dumps({"summary": joined}, ensure_ascii=False) + "\n")
        for row in rows:
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps({key: joined[key] for key in ("label", "ok", "n", "accuracy", "errors")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
