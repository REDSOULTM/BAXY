"""Mueve N modulos de gemma4_agent/ a gemma4_agent/<subpkg>/ con shims
aliased back-compat (patron R2).

Por archivo X.py movido a <subpkg>/X.py:
  1) git mv (o fallback rename + git add)
  2) En el archivo movido, reescribir `from .Y` -> `from ..Y` para Y que NO
     pertenece al mismo subpaquete; deja `from .Y` si Y SI pertenece al mismo
     subpaquete.
  3) Crear shim `gemma4_agent/X.py` con:
         import sys
         from .<subpkg>.X import *  # noqa: F401,F403
         from .<subpkg> import X as _real
         sys.modules[__name__] = _real
     Esto hace `from gemma4_agent.X import foo` y `from gemma4_agent.<subpkg>.X
     import foo` retornar el MISMO modulo (mismas identidades, no copias),
     que es lo que R2 valido como correcto para back-compat completa.

Uso:
    python scripts/_reorg_pkg_subpackage.py <subpkg> file1.py file2.py ...

Ej:
    python scripts/_reorg_pkg_subpackage.py agent_core agent.py agent_runner.py
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
resuelvan al MISMO objeto-modulo (mismas identidades de clases, no copias).

Patron validado en Sprint R2 (memoria project_r2_sprint1_domain_tools_split_2026_05_28)."""
import sys as _sys
from .{subpkg} import {stem} as _real_module

_sys.modules[__name__] = _real_module
'''


def git_mv(src: Path, dst: Path) -> bool:
    """Intenta git mv; si falla (untracked), rename + git add."""
    src_rel = str(src.relative_to(REPO)).replace("\\", "/")
    dst_rel = str(dst.relative_to(REPO)).replace("\\", "/")
    r = subprocess.run(["git", "mv", src_rel, dst_rel], cwd=REPO,
                       capture_output=True, text=True)
    if r.returncode == 0:
        return True
    # Fallback: untracked
    if src.exists() and not dst.exists():
        src.replace(dst)
        subprocess.run(["git", "add", dst_rel], cwd=REPO, check=False)
        return True
    print(f"  WARN: {src.name}: {r.stderr.strip()}", file=sys.stderr)
    return False


def rewrite_imports_in_moved(moved: Path, subpkg: str,
                             subpkg_members: set[str]) -> int:
    """En el archivo movido a subpkg/, reescribir imports:
      - `from .Y` donde Y in subpkg_members -> dejar `from .Y` (sigue siendo
        sibling, ahora dentro del subpkg)
      - `from .Y` donde Y NOT in subpkg_members -> `from ..Y` (sube un nivel
        al paquete padre, donde el shim vive)
      - `from . import Y` -> mismo principio.

    Devuelve N cambios.
    """
    text = moved.read_text(encoding="utf-8", errors="replace")
    original = text
    out_lines = []
    for line in text.splitlines(keepends=True):
        m = re.match(r'^(\s*)from \.(\w+)( import\b.*)$', line)
        if m:
            indent, name, rest = m.group(1), m.group(2), m.group(3)
            # Solo subir si NO es del mismo subpaquete
            if name in subpkg_members:
                out_lines.append(line)
            else:
                out_lines.append(f"{indent}from ..{name}{rest}\n"
                                 if line.endswith("\n") else
                                 f"{indent}from ..{name}{rest}")
            continue
        # `from . import Y, Z`
        m2 = re.match(r'^(\s*)from \. import (.*)$', line)
        if m2:
            indent, items_raw = m2.group(1), m2.group(2).rstrip()
            items = [it.strip() for it in items_raw.split(",")]
            same_pkg = [it for it in items
                        if it.split(" as ")[0].strip() in subpkg_members]
            parent_pkg = [it for it in items
                          if it.split(" as ")[0].strip() not in subpkg_members]
            new_lines = []
            if same_pkg:
                new_lines.append(f"{indent}from . import {', '.join(same_pkg)}")
            if parent_pkg:
                new_lines.append(f"{indent}from .. import {', '.join(parent_pkg)}")
            replacement = "\n".join(new_lines)
            if line.endswith("\n"):
                replacement += "\n"
            out_lines.append(replacement)
            continue
        out_lines.append(line)
    new_text = "".join(out_lines)
    if new_text != original:
        moved.write_text(new_text, encoding="utf-8")
    return sum(1 for a, b in zip(original.splitlines(), new_text.splitlines())
               if a != b)


def write_shim(subpkg: str, stem: str) -> None:
    shim_path = PKG / f"{stem}.py"
    shim_path.write_text(
        SHIM_TEMPLATE.format(subpkg=subpkg, stem=stem),
        encoding="utf-8",
    )
    subprocess.run(["git", "add", str(shim_path.relative_to(REPO)).replace("\\", "/")],
                   cwd=REPO, check=False)


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    subpkg = sys.argv[1]
    files = sys.argv[2:]
    subpkg_dir = PKG / subpkg
    subpkg_dir.mkdir(exist_ok=True)
    init = subpkg_dir / "__init__.py"
    if not init.exists():
        init.write_text(
            f'"""gemma4_agent.{subpkg} subpackage (reorg 2026-05-28)."""\n',
            encoding="utf-8",
        )
        subprocess.run(["git", "add", str(init.relative_to(REPO)).replace("\\", "/")],
                       cwd=REPO, check=False)

    # Set de stems pertenecientes al subpkg (sin .py)
    subpkg_members = {Path(f).stem for f in files}

    moved: list[Path] = []
    for fname in files:
        src = PKG / fname
        dst = subpkg_dir / fname
        if not src.exists():
            print(f"SKIP missing: {fname}", file=sys.stderr)
            continue
        if dst.exists():
            print(f"SKIP already moved: {fname}", file=sys.stderr)
            continue
        if not git_mv(src, dst):
            continue
        moved.append(dst)

    print(f"Moved {len(moved)} files to {subpkg}/")

    # Reescribir imports en cada movido
    total_rewrites = 0
    for f in moved:
        n = rewrite_imports_in_moved(f, subpkg, subpkg_members)
        total_rewrites += n

    print(f"Rewrote {total_rewrites} import lines in moved files")

    # Crear shims
    for f in moved:
        write_shim(subpkg, f.stem)
    print(f"Wrote {len(moved)} back-compat shims at package root")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
