"""Paired comparison of bench runs on the same items: decision2, scenes or e2e (Renew al máximo, palancas 12.2 y 12.5).

usage: py -3.12 scripts/renew/pareado.py A[,A2,...] B[,B2,...] [C[,C2,...] ...] [--exclude P045,P047,...]

Each argument is one arm: its replicas (seeds or neutral edits of the prompt) joined by commas. A replica is a bench's
jsonl (bench_decision, bench_escenas) or an e2e run directory (its results.jsonl). The first arm is the reference.
For every other arm, on the items every replica of both arms holds (excluded and retired items left out):
- the mean of correct items per replica and Δ against the reference, with its 95 % interval by a paired bootstrap over
  items (each item's score is its mean over its replicas): the difficulty of each item cancels (Miller 2024, «Adding
  Error Bars to Evals», doi.org/10.48550/arXiv.2411.00640);
- the items that went up and down, and exact McNemar on each item's majority (a tie is neither);
- pass^k (every replica right) when the arm has k > 1 replicas (τ-bench, doi.org/10.48550/arXiv.2406.12045);
- with two or more arms against the reference, Holm's adjustment of the McNemar p-values.
"""
import json
import random
import sys
from math import comb
from pathlib import Path


def rows(path: Path) -> dict[str, bool]:
    if path.is_dir():
        path = path / "results.jsonl"
    found = {}
    for line in path.open(encoding="utf-8"):
        row = json.loads(line)
        if "id" not in row or row.get("excluded"):
            continue
        found[str(row["id"])] = bool(row.get("ok"))
    return found


def majority(score: float) -> bool | None:
    """An item's majority over its replicas: right, wrong, or a tie (None)."""
    return None if score == .5 else score > .5


def mcnemar(up: int, down: int) -> float:
    n = up + down
    return 1.0 if n == 0 else min(1.0, 2 * sum(comb(n, i) for i in range(min(up, down) + 1)) / 2 ** n)


def interval(deltas: list[float], draws: int = 10000) -> tuple[float, float]:
    rng = random.Random(0)
    totals = sorted(sum(rng.choice(deltas) for _ in deltas) for _ in range(draws))
    return totals[int(.025 * draws)], totals[int(.975 * draws)]


def holm(p_values: list[float]) -> list[float]:
    order = sorted(range(len(p_values)), key=lambda i: p_values[i])
    adjusted, running = [0.0] * len(p_values), 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (len(p_values) - rank) * p_values[i]))
        adjusted[i] = running
    return adjusted


def main() -> None:
    args, exclude = sys.argv[1:], set()
    if "--exclude" in args:
        at = args.index("--exclude")
        exclude = {item for item in args[at + 1].split(",") if item}
        args = args[:at] + args[at + 2:]
    if len(args) < 2:
        sys.exit(__doc__)
    arms = [[rows(Path(part)) for part in arg.split(",")] for arg in args]
    reference = arms[0]
    results = []
    for number, arm in enumerate(arms[1:], start=1):
        items = sorted(set.intersection(*[set(replica) for replica in reference + arm]) - exclude)
        a = {item: sum(r[item] for r in reference) / len(reference) for item in items}
        b = {item: sum(r[item] for r in arm) / len(arm) for item in items}
        up = [item for item in items if majority(b[item]) is True and majority(a[item]) is False]
        down = [item for item in items if majority(a[item]) is True and majority(b[item]) is False]
        deltas = [b[item] - a[item] for item in items]
        low, high = interval(deltas)
        result = {
            "arm": args[number], "items": len(items),
            "reference_mean": round(sum(a.values()), 2), "arm_mean": round(sum(b.values()), 2),
            "delta": round(sum(deltas), 2), "delta_ci95": [round(low, 2), round(high, 2)],
            "up": up, "down": down, "mcnemar_p": round(mcnemar(len(up), len(down)), 4),
            "changed_any_replica": sum(1 for item in items if a[item] != b[item]),
        }
        for name, group in (("reference", reference), ("arm", arm)):
            if len(group) > 1:
                result[f"{name}_pass^{len(group)}"] = sum(all(r[item] for r in group) for item in items)
        results.append(result)
    if len(results) > 1:
        for result, adjusted in zip(results, holm([r["mcnemar_p"] for r in results])):
            result["mcnemar_p_holm"] = round(adjusted, 4)
    print(f"reference: {args[0]} ({len(reference)} replica(s)); excluded ids: {len(exclude)}")
    for result in results:
        print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
