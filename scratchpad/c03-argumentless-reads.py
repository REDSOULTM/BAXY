"""Cuenta cuántos abiertos dependen de «no preguntes una lectura que no necesita datos».

La regla candidata es: si la operación identificada es de sólo lectura y su esquema no exige argumentos,
no se pregunta, se lee. Antes de escribirla hay que saber a cuántos requisitos abiertos alcanza, porque
el dueño exige diez abiertos como mínimo para justificar trabajo nuevo de infraestructura.

Lee el catálogo tipado del propio Core —`baxy-core.exe --version` publica capacidades con su `risk` y su
`argumentsSchema.required`— y lo cruza con los literales del registro resueltos por el reconocedor.

Uso:
    python scratchpad/c03-argumentless-reads.py
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
BASE = pathlib.Path.home() / "AppData/Local/BAXY"
REGISTRY = BASE / "C03-survey-requirements336-private/requirements.jsonl"
TAXONOMY = ROOT / "artifacts/comprobaciones/C03/SURVEY_TAXONOMY846.json"
BASELINE = BASE / "C03-recogniser-baseline.json"
CORE = ROOT / "src/Baxy.Core/bin/Release/net10.0-windows10.0.19041.0/win-x64/publish/baxy-core.exe"
CACHE = BASE / "C03-catalog-capabilities.json"


def capabilities() -> dict[str, dict]:
    """Read the typed catalog from the Core itself, cached out of the context window."""

    if not CACHE.is_file():
        completed = subprocess.run([str(CORE), "--version"], capture_output=True, text=True,
                                   encoding="utf-8", timeout=120)
        if completed.returncode != 0 or not completed.stdout.strip():
            raise SystemExit(f"the Core did not publish its catalog (exit {completed.returncode})")
        CACHE.write_text(completed.stdout.strip().splitlines()[0], encoding="utf-8", newline="\n")
    hello = json.loads(CACHE.read_text(encoding="utf-8"))
    return {entry["name"]: entry for entry in hello["capabilities"]}


def main() -> int:
    catalog = capabilities()
    argumentless_reads = {
        name for name, entry in catalog.items()
        if entry.get("risk") == "read_only"
        and not (entry.get("argumentsSchema") or {}).get("required")
    }
    print(f"operations in the typed catalog: {len(catalog)}")
    print(f"read-only with no required argument: {len(argumentless_reads)}")
    print("   " + ", ".join(sorted(argumentless_reads)))

    rows = {}
    for line in REGISTRY.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            rows[row["case_id"]] = row
    taxonomy = json.loads(TAXONOMY.read_text(encoding="utf-8"))
    cases = taxonomy["cases"]
    category = ({c["case_id"]: c["category"] for c in cases} if isinstance(cases, list)
                else {k: (v if isinstance(v, str) else v["category"]) for k, v in cases.items()})
    resolved = json.loads(BASELINE.read_text(encoding="utf-8"))["resolved"]

    reachable: dict[str, list[str]] = {}
    for case_id, operations in resolved.items():
        row = rows.get(case_id)
        if row is None or row.get("verification_status") != "open":
            continue
        if not operations or any(op.startswith("!") for op in operations):
            continue
        if all(op in argumentless_reads for op in operations):
            reachable.setdefault(category.get(case_id, "unclassified"), []).append(case_id)

    total = sum(len(ids) for ids in reachable.values())
    print(f"\nopen rows whose whole resolution is argumentless reads: {total}")
    for cat, ids in sorted(reachable.items(), key=lambda item: -len(item[1])):
        print(f"  {cat:34} {len(ids):3}  {' '.join(sorted(ids))}")
        for case_id in sorted(ids):
            print(f"      {case_id}  {str(resolved[case_id]):44} {rows[case_id]['literal'][:60]}")
    print("\nEsto no dice que todos fallen hoy por aclaración innecesaria: dice cuántos requisitos "
          "abiertos quedan expuestos a esa decisión. Es la cota superior del rendimiento de la "
          "reparación, y la que se compara con el mínimo de diez.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
