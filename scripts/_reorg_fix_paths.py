"""Tras mover tests a gemma4_agent/tests/, ajustar Path(__file__).resolve().parent
chains que asumian que el test vivia en gemma4_agent/ directamente.

Reglas (orden importa — los mas-anchored primero para no doblar):
  - `Path(__file__).resolve().parent.parent / "scripts"` -> `.parent.parent.parent / "scripts"`
    (apuntaba a repo root, ahora hay un nivel mas)
  - `Path(__file__).resolve().parent.parent` (sola, sin / "scripts") -> `.parent.parent.parent`
    (apuntaba a repo root)
  - `Path(__file__).resolve().parent` (sola) -> `.parent.parent` (apuntaba a gemma4_agent/)

Solo en archivos que la grep marca explicitamente (lista hardcodeada).
"""
from __future__ import annotations

import re
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
TESTS = REPO / "gemma4_agent" / "tests"

# Archivos identificados via grep que tienen Path(__file__).resolve().parent chains
# que NO fueron arreglados ya manualmente.
TARGETS = [
    "test_no_bare_except.py",
    "test_no_eval_exec.py",
    "test_no_print_in_runtime.py",
    "test_r4_all_handlers_smoke.py",
    "test_scripts_inventory.py",
    "test_schema_handler_contract.py",
    "test_vram_calculator.py",
]


def patch(file: Path) -> int:
    """Devuelve numero de sustituciones aplicadas. NO toca chains que ya
    fueron arregladas manualmente (idempotente por la firma)."""
    src = file.read_text(encoding="utf-8")
    original = src
    # 1) parent.parent / "scripts"  ->  parent.parent.parent / "scripts"
    src = re.sub(
        r'(Path\(__file__\)\.resolve\(\))\.parent\.parent(\s*/\s*[\'"]scripts)',
        r'\1.parent.parent.parent\2', src,
    )
    # 2) parent.parent (sin /scripts despues) -> parent.parent.parent
    #    Cuidado: NO tocar el que YA arreglamos (que es parent.parent.parent).
    src = re.sub(
        r'(Path\(__file__\)\.resolve\(\))\.parent\.parent(?!\.parent)(?!\s*/\s*[\'"]scripts)',
        r'\1.parent.parent.parent', src,
    )
    # 3) parent (solo) -> parent.parent. Solo si NO le sigue otro .parent ya.
    src = re.sub(
        r'(Path\(__file__\)\.resolve\(\))\.parent(?!\.parent)',
        r'\1.parent.parent', src,
    )

    if src != original:
        file.write_text(src, encoding="utf-8")
        # Contar cuantas lineas cambiaron
        return sum(1 for a, b in zip(original.splitlines(), src.splitlines()) if a != b)
    return 0


def main() -> int:
    total = 0
    for name in TARGETS:
        f = TESTS / name
        if not f.exists():
            print(f"SKIP: {name} not found")
            continue
        n = patch(f)
        print(f"{name}: {n} lines changed")
        total += n
    print(f"TOTAL: {total} substitutions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
