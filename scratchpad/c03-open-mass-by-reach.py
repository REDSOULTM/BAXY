"""Cruza masa abierta con alcance del reconocedor determinista, por categoría.

Responde la pregunta que ordena el trabajo: de los abiertos de cada categoría, cuántos ya llegan
al camino determinista —que en SYSTEM1028 pasó 9 de 14— y cuántos caen al modelo, que pasó 3 de 15.
Un abierto que ya resuelve está listo para tanda; uno que no resuelve necesita reparación léxica
antes, y su reparación se verifica con `c03-recogniser-baseline.py compare`.

No adjudica, no escribe registro y no acredita cobertura.

Uso:
    python scratchpad/c03-open-mass-by-reach.py                 # tabla por categoría
    python scratchpad/c03-open-mass-by-reach.py <categoria>      # literales de una categoría
"""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
REGISTRY = (pathlib.Path.home() / "AppData/Local/BAXY"
            / "C03-survey-requirements336-private" / "requirements.jsonl")
TAXONOMY = ROOT / "artifacts" / "comprobaciones" / "C03" / "SURVEY_TAXONOMY846.json"
BASELINE = pathlib.Path.home() / "AppData/Local/BAXY" / "C03-recogniser-baseline.json"


def load():
    rows = {}
    for line in REGISTRY.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            rows[row["case_id"]] = row
    taxonomy = json.loads(TAXONOMY.read_text(encoding="utf-8"))
    cases = taxonomy["cases"]
    if isinstance(cases, list):
        category = {c["case_id"]: c["category"] for c in cases}
    else:
        category = {k: (v if isinstance(v, str) else v["category"]) for k, v in cases.items()}
    labels = {c["category"]: c["label"] for c in taxonomy["categories"]}
    resolved = json.loads(BASELINE.read_text(encoding="utf-8"))["resolved"]
    return rows, category, resolved, labels


def main(argv):
    rows, category, resolved, labels = load()
    buckets = {}
    for case_id, row in rows.items():
        cat = category.get(case_id, "unclassified")
        bucket = buckets.setdefault(cat, {"open_reached": [], "open_unreached": [], "covered": []})
        if row.get("verification_status") == "covered":
            bucket["covered"].append(case_id)
        elif row.get("verification_status") == "open":
            key = "open_reached" if resolved.get(case_id) else "open_unreached"
            bucket[key].append(case_id)

    if len(argv) == 2:
        want = argv[1]
        bucket = buckets.get(want)
        if bucket is None:
            print(f"unknown category: {want}")
            print(sorted(buckets))
            return 2
        for key in ("open_reached", "open_unreached"):
            print(f"== {key} ({len(bucket[key])})")
            for case_id in sorted(bucket[key]):
                ops = resolved.get(case_id)
                print(f"  {case_id}  {str(ops):46}  {rows[case_id]['literal'][:78]}")
        return 0

    order = sorted(buckets.items(),
                   key=lambda kv: -(len(kv[1]["open_reached"]) + len(kv[1]["open_unreached"])))
    print(f"{'categoria':34} {'abiertos':>8} {'llegan':>7} {'caen':>6} {'cubiertos':>10}")
    for cat, bucket in order:
        total_open = len(bucket["open_reached"]) + len(bucket["open_unreached"])
        print(f"{cat[:34]:34} {total_open:8} {len(bucket['open_reached']):7} "
              f"{len(bucket['open_unreached']):6} {len(bucket['covered']):10}")
    reached = sum(len(b["open_reached"]) for b in buckets.values())
    unreached = sum(len(b["open_unreached"]) for b in buckets.values())
    print(f"\ntotal abiertos que ya llegan al reconocedor: {reached}; que caen al modelo: {unreached}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
