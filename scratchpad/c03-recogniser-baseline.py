"""Baseline y diff del reconocedor determinista sobre los 742 literales de la encuesta.

Instrumento de reparación sin GPU. `resolve_explicit_effects` es una función pura, así que la
cobertura del reconocedor se puede medir y comparar en segundos, sin producto, sin modelo y sin tanda.
Su razón de ser está medida: en SYSTEM1028 los casos que llegaron al reconocedor pasaron 9 de 14,
y los que cayeron al modelo pasaron 3 de 15. Ampliar el reconocedor es la palanca, y este script es
el que dice si una ampliación rompió algo.

Uso:
    python scratchpad/c03-recogniser-baseline.py write  <salida.json>
    python scratchpad/c03-recogniser-baseline.py compare <baseline.json>

`write` con la fuente sin tocar; `compare` después de editar `effect_intent.py`. El diff enumera cada
literal cuyas operaciones resueltas cambiaron. Un cambio fuera del conjunto que la reparación
declaraba es una regresión, y se ve aquí antes de gastar una tanda en descubrirlo.

No adjudica, no escribe en el registro y no acredita cobertura: resolver una operación no es lo mismo
que responder con verdad. Sólo mide qué llega al camino determinista.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

REGISTRY = (pathlib.Path.home() / "AppData/Local/BAXY"
            / "C03-survey-requirements336-private" / "requirements.jsonl")
CATALOG = ROOT / "src" / "Baxy.Kernel" / "Operations" / "ProductCatalog.cs"


def public_operations() -> frozenset[str]:
    """Read the operation names the typed catalog declares, not an invented list."""

    source = CATALOG.read_text(encoding="utf-8", errors="replace")
    names = re.findall(r'Descriptor\(\s*"([a-z][a-z0-9.]*)"', source)
    if not names:
        raise SystemExit("no operation names found in the typed catalog")
    return frozenset(names)


def literals() -> list[tuple[str, str]]:
    if not REGISTRY.is_file():
        raise SystemExit(f"private registry absent: {REGISTRY}")
    rows = [json.loads(line) for line in REGISTRY.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [(row["case_id"], row["literal"]) for row in rows]


def resolve_all() -> dict[str, object]:
    from baxy_mind import effect_intent as ei

    available = public_operations()
    games = ei.build_game_catalog_index(())
    resolved: dict[str, list[str] | None] = {}
    for case_id, literal in literals():
        try:
            intent = ei.resolve_explicit_effects(literal, available, (), games)
        except Exception as error:  # a raise is itself a result worth diffing
            resolved[case_id] = ["!" + type(error).__name__]
            continue
        resolved[case_id] = list(intent.operations) if intent is not None else None
    covered = sum(1 for value in resolved.values() if value)
    return {
        "schema": "c03-recogniser-baseline-v1",
        "operations_in_catalog": len(available),
        "literals": len(resolved),
        "deterministically_resolved": covered,
        "unresolved": len(resolved) - covered,
        "resolved": resolved,
    }


def main(argv: list[str]) -> int:
    if len(argv) != 3 or argv[1] not in {"write", "compare"}:
        print(__doc__)
        return 2
    mode, target = argv[1], pathlib.Path(argv[2])
    current = resolve_all()
    if mode == "write":
        target.write_text(json.dumps(current, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(json.dumps({k: current[k] for k in
                          ("operations_in_catalog", "literals",
                           "deterministically_resolved", "unresolved")}, indent=1))
        return 0

    baseline = json.loads(target.read_text(encoding="utf-8"))
    before, after = baseline["resolved"], current["resolved"]
    changed = [case for case in after if before.get(case) != after[case]]
    print(json.dumps({
        "baseline_resolved": baseline["deterministically_resolved"],
        "current_resolved": current["deterministically_resolved"],
        "delta": current["deterministically_resolved"] - baseline["deterministically_resolved"],
        "changed_literals": len(changed),
    }, indent=1))
    by_literal = dict(literals())
    for case in sorted(changed):
        print(f"  {case}: {before.get(case)} -> {after[case]}   :: {by_literal.get(case, '')[:64]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
