"""Deriva el sellador de REPAIR1031 del de REPAIR1030.

Mismo subconjunto exacto —los siete literales que la primera reparación dejó veraces pero con frase
fija— y mismos controles cubiertos. Lo que cambia es el candidato: la instrucción de reintento ya no
es una oración publicable y el chequeo rechaza además el relanzamiento afirmado.
"""
from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scratchpad/c03-repair1030-seal.py"
TARGET = ROOT / "scratchpad/c03-repair1031-seal.py"

OLD_PRIOR = 'PRIOR = ROOT / "artifacts/comprobaciones/C03/APPS1029/ROOT_ADJUDICATION.json"'
NEW_PRIOR = 'PRIOR = ROOT / "artifacts/comprobaciones/C03/REPAIR1030/ROOT_ADJUDICATION.json"'

OLD_REPAIR = '''    "repair_under_measurement": {
            "commit": "27a1f2314c4518c395353b426222c6e75363aeb0",
            "file": "src/baxy_mind/llm.py",
            "defect_code": "unstated_already_running",
            "pure_probe": "scratchpad/c03-already-running-probe.py: 14 real drafts, 8 rejected, "
                          "6 clean, 0 mismatches",
        },'''
NEW_REPAIR = '''    "repair_under_measurement": {
            "commit": "REPAIR1031_HEAD",
            "file": "src/baxy_mind/llm.py",
            "defect_code": "unstated_already_running",
            "change": "The retry instruction is a short imperative instead of a publishable "
                      "declarative sentence, and an asserted relaunch over a reused process is "
                      "rejected too.",
            "pure_probe": "scratchpad/c03-already-running-check.py: 28 real drafts across APPS1029 "
                          "and REPAIR1030, 0 mismatches",
        },'''


def main() -> int:
    text = SOURCE.read_text(encoding="utf-8")
    if OLD_PRIOR not in text or OLD_REPAIR not in text:
        raise SystemExit("the 1030 sealer no longer has the expected anchors")
    text = text.replace(OLD_REPAIR, NEW_REPAIR).replace(OLD_PRIOR, NEW_PRIOR)
    text = text.replace("repair1030", "repair1031").replace("REPAIR1030", "REPAIR1031")
    # El puntero de evidencia previa sí apunta a la tanda anterior, no a la propia.
    text = text.replace('"artifacts/comprobaciones/C03/REPAIR1031/ROOT_ADJUDICATION.json"',
                        '"artifacts/comprobaciones/C03/REPAIR1030/ROOT_ADJUDICATION.json"')
    TARGET.write_text(text, encoding="utf-8", newline="\n")
    print(f"written {TARGET} ({len(text.splitlines())} lines)")
    for line in text.splitlines():
        if line.startswith("PRIOR") or "REPAIR1031_HEAD" in line:
            print("  ", line.strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
