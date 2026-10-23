"""Paired comparison of bench runs on the same items: decision2, scenes or e2e (Renew al máximo, palancas 12.2 y 12.5).

usage: py -3.12 scripts/renew/pareado.py A[,A2,...] B[,B2,...] [C[,C2,...] ...] [--exclude P045,P047,...]
       [--cases CASES.json] [--metric ok|wrong_action]

Each argument is one arm: its replicas (seeds or neutral edits of the prompt) joined by commas. A replica is a bench's
jsonl (bench_decision, bench_escenas) or an e2e run directory (its results.jsonl). The first arm is the reference.
For every other arm, on the items every replica of both arms holds (excluded and retired items left out):
- the mean of correct items per replica and Δ against the reference, with its 95 % interval by a paired bootstrap over
  items (each item's score is its mean over its replicas): the difficulty of each item cancels (Miller 2024, «Adding
  Error Bars to Evals», doi.org/10.48550/arXiv.2411.00640);
- the items that went up and down, and exact McNemar on each item's majority (a tie is neither);
- pass^k (every replica right) when the arm has k > 1 replicas (τ-bench, doi.org/10.48550/arXiv.2406.12045);
- with two or more arms against the reference, Holm's adjustment of the McNemar p-values.
Audit w8-medir (2026-10-23), what the plan of the holdout pre-registered and this did not do:
- an e2e case whose setup failed, a VOID one and one the locked session never ran (status setup_fallido, void,
  sesion_bloqueada) are not the product's failures: they are left out (CIERRE_PLAN: «setup_fallido es VOID»);
- --cases: the bank's cases; a dictation twin (field «twin», the id of its clean case, same expectation) and its clean
  case are one cluster, and Δ gets its error and interval clustered by pair (delta_se_twins: the sum's cluster-robust
  standard error; delta_ci95_twins: the bootstrap over clusters), since the two items of a pair are not independent;
- --metric wrong_action: the item counts when the model's decision was an action and was wrong (the pre-registered
  secondary metric: wrong actions proposed; in the decision bench nothing runs, so the kernel never had its say);
- a replica with rows the model server failed («error») is named: it counts them as wrong and is not a clean replica.
"""
import json
import random
import sys
from math import comb, sqrt
from pathlib import Path

VOID_STATUSES = {"setup_fallido", "void", "sesion_bloqueada"}
METRICS = ("ok", "wrong_action")


def scored(row: dict, metric: str = "ok") -> bool | None:
    """The row's value for the metric, or None when it is not counted."""
    if "id" not in row or row.get("excluded") or row.get("status") in VOID_STATUSES:
        return None
    if metric == "wrong_action":
        return row.get("kind") == "action" and not row.get("ok")
    return bool(row.get("ok"))


def rows(path: Path, metric: str = "ok", errors: dict | None = None) -> dict[str, bool]:
    if path.is_dir():
        path = path / "results.jsonl"
    found = {}
    for line in path.open(encoding="utf-8"):
        row = json.loads(line)
        value = scored(row, metric)
        if value is None:
            continue
        found[str(row["id"])] = value
        if row.get("error") and errors is not None:
            errors[str(path)] = errors.get(str(path), 0) + 1
    return found


def clusters(cases: list[dict]) -> dict[str, str]:
    """Each case's cluster: its twin's id for a dictation twin, its own id otherwise."""
    return {str(case["id"]): str(case.get("twin") or case["id"]) for case in cases}


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


def grouped(deltas: dict[str, float], cluster_of: dict[str, str]) -> list[float]:
    """The items' deltas summed by cluster (an item the cases do not name is its own)."""
    sums: dict[str, float] = {}
    for item, delta in deltas.items():
        key = cluster_of.get(item, item)
        sums[key] = sums.get(key, 0.0) + delta
    return list(sums.values())


def cluster_se(sums: list[float]) -> float:
    """The cluster-robust standard error of Σ deltas: sqrt(K/(K-1) · Σ_k (D_k − D̄)²)."""
    k = len(sums)
    if k < 2:
        return 0.0
    mean = sum(sums) / k
    return sqrt(k / (k - 1) * sum((d - mean) ** 2 for d in sums))


def holm(p_values: list[float]) -> list[float]:
    order = sorted(range(len(p_values)), key=lambda i: p_values[i])
    adjusted, running = [0.0] * len(p_values), 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (len(p_values) - rank) * p_values[i]))
        adjusted[i] = running
    return adjusted


def compare(reference: list[dict], arm: list[dict], exclude: set, cluster_of: dict[str, str] | None = None) -> dict:
    items = sorted(set.intersection(*[set(replica) for replica in reference + arm]) - exclude)
    a = {item: sum(r[item] for r in reference) / len(reference) for item in items}
    b = {item: sum(r[item] for r in arm) / len(arm) for item in items}
    up = [item for item in items if majority(b[item]) is True and majority(a[item]) is False]
    down = [item for item in items if majority(a[item]) is True and majority(b[item]) is False]
    deltas = {item: b[item] - a[item] for item in items}
    low, high = interval(list(deltas.values()))
    result = {
        "items": len(items),
        "reference_mean": round(sum(a.values()), 2), "arm_mean": round(sum(b.values()), 2),
        "delta": round(sum(deltas.values()), 2), "delta_ci95": [round(low, 2), round(high, 2)],
        "up": up, "down": down, "mcnemar_p": round(mcnemar(len(up), len(down)), 4),
        "changed_any_replica": sum(1 for item in items if a[item] != b[item]),
    }
    if cluster_of and any(cluster_of.get(item, item) != item for item in items):
        sums = grouped(deltas, cluster_of)
        low, high = interval(sums)
        result.update(clusters=len(sums), delta_se_twins=round(cluster_se(sums), 2),
                      delta_ci95_twins=[round(low, 2), round(high, 2)])
    for name, group in (("reference", reference), ("arm", arm)):
        if len(group) > 1:
            result[f"{name}_pass^{len(group)}"] = sum(all(r[item] for r in group) for item in items)
    return result


def _take(args: list[str], flag: str) -> tuple[list[str], str | None]:
    if flag not in args:
        return args, None
    at = args.index(flag)
    return args[:at] + args[at + 2:], args[at + 1]


def main() -> None:
    args = sys.argv[1:]
    args, excluded = _take(args, "--exclude")
    args, cases_file = _take(args, "--cases")
    args, metric = _take(args, "--metric")
    metric = metric or "ok"
    if len(args) < 2 or metric not in METRICS:
        sys.exit(__doc__)
    exclude = {item for item in (excluded or "").split(",") if item}
    cluster_of = clusters(json.loads(Path(cases_file).read_text(encoding="utf-8"))) if cases_file else None
    errors: dict[str, int] = {}
    arms = [[rows(Path(part), metric, errors) for part in arg.split(",")] for arg in args]
    reference = arms[0]
    results = [{"arm": args[number], **compare(reference, arm, exclude, cluster_of)}
               for number, arm in enumerate(arms[1:], start=1)]
    if len(results) > 1:
        for result, adjusted in zip(results, holm([r["mcnemar_p"] for r in results])):
            result["mcnemar_p_holm"] = round(adjusted, 4)
    print(f"reference: {args[0]} ({len(reference)} replica(s)); metric {metric}; excluded ids: {len(exclude)}")
    for replica, count in sorted(errors.items()):
        print(f"WARNING: {replica} has {count} row(s) the model server failed (counted wrong): not a clean replica")
    for result in results:
        print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
