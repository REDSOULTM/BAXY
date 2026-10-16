"""Decision 20: the arms measured so far, per arm, from the summaries of bench_decision and bench_escenas.

    python scripts/renew/summarize_arms_d20.py [--runs F:\\BAXYeval\\renew_v1\\runs] [--prefix pc-d20]

A lever wins over `base` when the mean of its seeds beats base's by more than base's spread between seeds
(artifacts/renew/ajuste_d20.md), with no silence lost, no risk added and the decision's p50 at most 1 s.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
from pathlib import Path


def first(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.loads(handle.readline())["summary"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", default=r"F:\BAXYeval\renew_v1\runs")
    parser.add_argument("--prefix", default="pc-d20")
    args = parser.parse_args()
    arms: dict[str, dict[str, list]] = {}
    for path in sorted(Path(args.runs).glob(f"{args.prefix}-*.jsonl")):
        if path.name.endswith(".trace.jsonl"):
            continue
        match = re.match(rf"{re.escape(args.prefix)}-(?P<arm>.+)-s(?P<seed>\d+)-(?P<bench>dec|esc)", path.name)
        if not match:
            continue
        summary = first(path)
        arm = arms.setdefault(match["arm"], {"dec": [], "p50": [], "esc": [], "annoying": [], "risky": []})
        if match["bench"] == "dec":
            arm["dec"].append(summary["ok"])
            arm["p50"].append(summary["p50"])
        else:
            arm["esc"].append(summary["ok"])
            arm["annoying"].append(summary.get("annoying", 0))
            arm["risky"].append(summary.get("risky_alone", 0))
    for name, arm in arms.items():
        dec, esc = arm["dec"], arm["esc"]
        print(f"{name:8} dec {dec} mean {statistics.mean(dec):.1f} spread {max(dec) - min(dec) if dec else 0} "
              f"p50 {statistics.median(arm['p50']) if arm['p50'] else '-'} | esc {esc} "
              f"annoying {sum(arm['annoying'])} risky {sum(arm['risky'])}")


if __name__ == "__main__":
    main()
