"""Reorganiza tests: gemma4_agent/test_*.py -> gemma4_agent/tests/test_*.py.

Pasos:
  1) git mv todos los test_*.py al sub-directorio tests/
  2) En cada test movido, reescribir `from .X` -> `from ..X` (un nivel mas profundo)
  3) Parchar test_audit_8r_verification.py: `PKG / "test_schema_handler_contract.py"`
     -> `PKG / "tests" / "test_schema_handler_contract.py"`
  4) Actualizar docstrings "pytest gemma4_agent/test_X.py" -> "tests/test_X.py"
  5) Crear gemma4_agent/tests/__init__.py para hacer sub-paquete

NO toca domain_tools_*.py (shims back-compat R2, son codigo de produccion).
NO toca rutas PKG.rglob (encuentran tests donde sea).
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
PKG = REPO / "gemma4_agent"
TESTS_DIR = PKG / "tests"


def main() -> int:
    # 1) Crear sub-paquete tests/
    TESTS_DIR.mkdir(exist_ok=True)
    init = TESTS_DIR / "__init__.py"
    if not init.exists():
        init.write_text(
            '"""gemma4_agent test subpackage (reorg 2026-05-28).\n'
            '\n'
            'Tests viven aca para no contaminar el espacio del paquete\n'
            'productivo. Imports relativos a un nivel mas (from ..X).\n'
            '"""\n',
            encoding="utf-8",
        )
        subprocess.run(["git", "add", str(init)], cwd=REPO, check=False)

    # 2) Identificar tests
    tests = sorted(PKG.glob("test_*.py"))
    print(f"Moving {len(tests)} test files")
    moved: list[Path] = []
    for src in tests:
        dst = TESTS_DIR / src.name
        result = subprocess.run(
            ["git", "mv", str(src.relative_to(REPO)).replace("\\", "/"),
             str(dst.relative_to(REPO)).replace("\\", "/")],
            cwd=REPO, capture_output=True, text=True,
        )
        if result.returncode != 0:
            # Fallback: file probablemente untracked
            if src.exists() and not dst.exists():
                src.replace(dst)
                subprocess.run(["git", "add", str(dst.relative_to(REPO))],
                               cwd=REPO, check=False)
            else:
                print(f"  WARN: {src.name}: {result.stderr.strip()}", file=sys.stderr)
                continue
        moved.append(dst)

    print(f"Moved {len(moved)} tests")

    # 3) Reescribir imports relativos un nivel adicional + ajustar docstrings
    rewritten = 0
    for test_file in moved:
        text = test_file.read_text(encoding="utf-8", errors="replace")
        original = text

        # `from .X import Y`  ->  `from ..X import Y`
        # `from . import X`   ->  `from .. import X`
        # NO toca `from ..X` o `from gemma4_agent.X` (absolutos)
        text = re.sub(r'^(\s*from )\.(?!\.)', r'\1..', text, flags=re.M)

        # Docstring cosmetic: pytest gemma4_agent/test_X.py -> gemma4_agent/tests/test_X.py
        text = re.sub(
            r'pytest gemma4_agent/(test_[\w]+\.py)',
            r'pytest gemma4_agent/tests/\1',
            text,
        )

        if text != original:
            test_file.write_text(text, encoding="utf-8")
            rewritten += 1

    print(f"Rewrote imports/docs in {rewritten} files")

    # 4) Patch test_audit_8r_verification.py: ruta a test_schema_handler_contract.py
    audit = TESTS_DIR / "test_audit_8r_verification.py"
    if audit.exists():
        s = audit.read_text(encoding="utf-8")
        new = s.replace(
            'PKG / "test_schema_handler_contract.py"',
            'PKG / "tests" / "test_schema_handler_contract.py"',
        )
        if new != s:
            audit.write_text(new, encoding="utf-8")
            print("Patched test_audit_8r_verification.py R5 contract path")

    return 0


if __name__ == "__main__":
    sys.exit(main())
