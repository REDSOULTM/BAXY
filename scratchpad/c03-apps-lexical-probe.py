"""Sonda léxica del reconocedor sobre los abiertos de apps que no llegan a él.

Compara literales que sí resuelven con los que no, para localizar exactamente qué parte de la frase
desarma el reconocimiento: la cabeza verbal, el determinante o la cola. Función pura, sin GPU.

Uso:
    python scratchpad/c03-apps-lexical-probe.py
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
CATALOG = ROOT / "src/Baxy.Kernel/Operations/ProductCatalog.cs"

WORKS = [
    "abrí la calculadora",
    "abre la calculadora",
    "abre steam",
    "abrí discord",
    "abrí la configuración de windows",
]

FAILS = [
    "avrí la calculadora",
    "abrime la calculadora dale",
    "me abrís la calculadora",
    "abre a calculadora",
    "abres team",
    "Abre stea,",
    "Abre steam pls",
    "abre Steel.",
    "open the file explorer",
    "abrí el explorador de archivos",
    "abrime el photoshop",
    "son las tres abrí la calculadora",
    # Aislar cabeza y cola: qué parte desarma el reconocimiento.
    "abrime la calculadora",
    "abrime la calculadora por favor",
    "abre steam por favor",
    "abre steam please",
    "abrís la calculadora",
    "abres la calculadora",
    "me abres la calculadora",
    "me abrirías la calculadora",
]


def main() -> int:
    from baxy_mind import effect_intent as ei

    source = CATALOG.read_text(encoding="utf-8", errors="replace")
    operations = frozenset(re.findall(r'Descriptor\(\s*"([a-z][a-z0-9.]*)"', source))
    games = ei.build_game_catalog_index(())

    def resolve(text: str):
        intent = ei.resolve_explicit_effects(text, operations, (), games)
        return list(intent.operations) if intent is not None else None

    print(f"catalog operations: {len(operations)}")
    print("== resuelven hoy")
    for text in WORKS:
        print(f"  {text!r:38} -> {resolve(text)}")
    print("== no resuelven")
    for text in FAILS:
        print(f"  {text!r:38} -> {resolve(text)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
