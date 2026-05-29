"""Repara imports + escribe shims en un subpkg que ya tiene archivos movidos.

Caso de uso: el move por `git mv` se hizo parcialmente (algunos archivos
movidos a `gemma4_agent/<subpkg>/`, otros no). Este script:
  1) Detecta los archivos ya presentes en el subpkg (sin __init__.py).
  2) Reescribe sus imports relativos `from .X` segun X este en el subpkg o no.
  3) Crea los shims back-compat en `gemma4_agent/X.py` para cada movido.

NO toca los archivos NO movidos (en la raiz del paquete).

Uso:
    python scripts/_reorg_finalize_subpkg.py <subpkg>
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
PKG = REPO / "gemma4_agent"

SHIM_TEMPLATE = '''"""Back-compat shim (reorg 2026-05-28): este modulo fue movido
a `gemma4_agent.{subpkg}.{stem}`. El shim re-exporta TODO via re-aliasing en
sys.modules para que `import gemma4_agent.{stem}` y `import gemma4_agent.{subpkg}.{stem}`
resuelvan al MISMO objeto-modulo.

Patron validado en Sprint R2 (memoria project_r2_sprint1_domain_tools_split_2026_05_28)."""
import sys as _sys
from .{subpkg} import {stem} as _real_module

_sys.modules[__name__] = _real_module
'''


def rewrite_imports(moved: Path, subpkg_members: set[str]) -> int:
    text = moved.read_text(encoding="utf-8", errors="replace")
    original = text
    out_lines = []
    for line in text.splitlines(keepends=True):
        # `from .X[.Y.Z] import ...`  — captura el primer segmento X
        m = re.match(r'^(\s*)from \.(\w+)((?:\.\w+)*\s+import\b.*)$', line)
        if m:
            indent, name, rest = m.group(1), m.group(2), m.group(3)
            if name in subpkg_members:
                out_lines.append(line)
            else:
                ending = "\n" if line.endswith("\n") else ""
                out_lines.append(f"{indent}from ..{name}{rest}{ending}")
            continue
        m2 = re.match(r'^(\s*)from \. import (.*)$', line)
        if m2:
            indent, items_raw = m2.group(1), m2.group(2).rstrip()
            items = [it.strip() for it in items_raw.split(",")]
            same = [it for it in items
                    if it.split(" as ")[0].strip() in subpkg_members]
            parent = [it for it in items
                      if it.split(" as ")[0].strip() not in subpkg_members]
            new = []
            if same:
                new.append(f"{indent}from . import {', '.join(same)}")
            if parent:
                new.append(f"{indent}from .. import {', '.join(parent)}")
            ending = "\n" if line.endswith("\n") else ""
            out_lines.append("\n".join(new) + ending)
            continue
        out_lines.append(line)
    new_text = "".join(out_lines)
    if new_text != original:
        moved.write_text(new_text, encoding="utf-8")
    return sum(1 for a, b in zip(original.splitlines(), new_text.splitlines())
               if a != b)


def write_shim(subpkg: str, stem: str) -> None:
    shim_path = PKG / f"{stem}.py"
    if shim_path.exists():
        # Si la raiz aun tiene un archivo no-shim aqui, no sobreescribir
        # (el move parcial pudo dejar la version vieja como huerfano).
        existing = shim_path.read_text(encoding="utf-8", errors="replace")
        if "Back-compat shim" not in existing:
            print(f"  SKIP shim (raiz aun tiene {stem}.py no-shim)",
                  file=sys.stderr)
            return
    shim_path.write_text(
        SHIM_TEMPLATE.format(subpkg=subpkg, stem=stem),
        encoding="utf-8",
    )
    rel = str(shim_path.relative_to(REPO)).replace("\\", "/")
    subprocess.run(["git", "add", rel], cwd=REPO, check=False)


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 1
    subpkg = sys.argv[1]
    subpkg_dir = PKG / subpkg
    if not subpkg_dir.is_dir():
        print(f"ABORT: {subpkg_dir} not a directory", file=sys.stderr)
        return 1
    moved = sorted(p for p in subpkg_dir.glob("*.py") if p.stem != "__init__")
    if not moved:
        print(f"No modules in {subpkg}/ to finalize")
        return 0
    members = {p.stem for p in moved}
    print(f"Finalizing {len(moved)} modules in {subpkg}/")
    total = 0
    for f in moved:
        n = rewrite_imports(f, members)
        total += n
    print(f"Rewrote {total} import lines")
    for f in moved:
        write_shim(subpkg, f.stem)
    print(f"Shims written for {len(moved)} modules")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
