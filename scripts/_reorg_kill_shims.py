"""Migra imports externos y elimina shims back-compat.

Patron R2 con shims era "back-compat seguro". Ahora que la reorg esta
estable, los shims son cosmeticamente molestos. Este script:

  1) Escanea gemma4_agent/<subpkg>/ por subpkg para construir un mapa
     stem -> subpkg (ej. agent -> agent_core).
  2) Reescribe TODOS los imports externos al paquete:
       from gemma4_agent.<stem> import X
       -> from gemma4_agent.<subpkg>.<stem> import X
     en estos directorios: scripts/, gemma4_agent/tests/, raiz (si hay).
  3) Tambien reescribe `import gemma4_agent.<stem>` -> `import gemma4_agent.<subpkg>.<stem> as <stem>`.
  4) Reescribe imports INTERNOS del paquete que aun usen el shim path
     (from gemma4_agent.X -> from gemma4_agent.<subpkg>.X) en cualquier
     subpkg.
  5) Elimina los shims fisicamente (git rm) — los archivos top-level cuyo
     contenido es el template de shim.

NO toca:
  - domain_tools_*.py (shims pre-existentes del Sprint R2 — ya documentados como API publica)
  - __init__.py, _ps.py, _shared.py (privados, conservar)
  - docs/, prompts/, microagents/, skills/ (no son codigo)
"""
from __future__ import annotations

import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
PKG = REPO / "gemma4_agent"

# Subpaquetes creados por la reorg 2026-05-28
NEW_SUBPKGS = (
    "agent_core", "computer_use_pkg", "routing", "infra",
    "safety_pkg", "memory_pkg", "tools_pkg", "mission", "support",
)


def build_stem_to_subpkg_map() -> dict[str, str]:
    """Para cada subpkg nuevo, lista sus .py y devuelve {stem -> subpkg}."""
    out: dict[str, str] = {}
    for subpkg in NEW_SUBPKGS:
        d = PKG / subpkg
        if not d.is_dir():
            continue
        for f in d.glob("*.py"):
            if f.stem == "__init__":
                continue
            if f.stem in out:
                print(f"WARN: stem '{f.stem}' duplicado en {out[f.stem]} y {subpkg}",
                      file=sys.stderr)
                continue
            out[f.stem] = subpkg
    return out


def is_shim(path: Path) -> bool:
    """True si el archivo es un shim back-compat del patron R2 reorg."""
    if not path.is_file():
        return False
    try:
        src = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return ("Back-compat shim" in src
            and "sys.modules[__name__] = _real_module" in src
            and len(src.splitlines()) <= 20)


def rewrite_file_imports(path: Path, stem_map: dict[str, str]) -> int:
    """Reescribe imports `from gemma4_agent.<stem>` -> `from gemma4_agent.<subpkg>.<stem>`
    y `import gemma4_agent.<stem>` similarmente. Devuelve N substituciones.

    Limita el match a stems en stem_map para no tocar nombres no migrados
    (ej. `gemma4_agent.voice`, que ya es subpkg, no debe cambiarse).
    """
    try:
        src = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 0
    original = src

    def from_repl(m: re.Match) -> str:
        prefix, stem, suffix = m.group(1), m.group(2), m.group(3)
        if stem not in stem_map:
            return m.group(0)
        return f"{prefix}gemma4_agent.{stem_map[stem]}.{stem}{suffix}"

    # `from gemma4_agent.<stem>(.X.Y)? import ...`
    src = re.sub(
        r"(\bfrom\s+)gemma4_agent\.(\w+)((?:\.\w+)*\s+import\b)",
        from_repl, src,
    )

    # `import gemma4_agent.<stem>` (sin `from`)
    def imp_repl(m: re.Match) -> str:
        prefix, stem, suffix = m.group(1), m.group(2), m.group(3)
        if stem not in stem_map:
            return m.group(0)
        # `import gemma4_agent.X` -> `import gemma4_agent.<sub>.X as X` to keep
        # callers writing `gemma4_agent.X.Y` working.
        if suffix.strip().startswith("as "):
            return f"{prefix}gemma4_agent.{stem_map[stem]}.{stem}{suffix}"
        return f"{prefix}gemma4_agent.{stem_map[stem]}.{stem} as {stem}{suffix}"

    src = re.sub(
        r"(\bimport\s+)gemma4_agent\.(\w+)(\s+as\s+\w+|\s*$|\s*[\n;])",
        imp_repl, src, flags=re.MULTILINE,
    )

    if src != original:
        path.write_text(src, encoding="utf-8")
        return sum(1 for a, b in zip(original.splitlines(), src.splitlines())
                   if a != b)
    return 0


def main() -> int:
    stem_map = build_stem_to_subpkg_map()
    print(f"Stem map: {len(stem_map)} entries")
    # Mostrar mapa por subpkg
    by_sub: dict[str, list[str]] = defaultdict(list)
    for stem, sub in stem_map.items():
        by_sub[sub].append(stem)
    for sub in sorted(by_sub):
        print(f"  {sub}: {len(by_sub[sub])} modules")

    # Reescribir imports en:
    # - scripts/ (excepto el propio reorg)
    # - gemma4_agent/tests/
    # - cualquier .py dentro del paquete que no sea shim (subpkgs)
    scan_dirs = [
        REPO / "scripts",
        PKG / "tests",
    ]
    # tambien los .py dentro de subpkgs (algunos pueden tener imports
    # absolutos a gemma4_agent.X que apuntan a shim)
    for sub in NEW_SUBPKGS:
        scan_dirs.append(PKG / sub)
    # voice / domain_tools / ui / etc. sub-pkgs preexistentes tambien podrian
    # tener imports a shim:
    for d in PKG.iterdir():
        if d.is_dir() and d.name not in {"tests", "__pycache__", "docs",
                                          "captures", "data", "logs",
                                          "prompts", "skills", "microagents",
                                          "ui", "ui_field"} and d.name not in NEW_SUBPKGS:
            scan_dirs.append(d)

    total_files_touched = 0
    total_lines = 0
    for d in scan_dirs:
        if not d.is_dir():
            continue
        for f in d.rglob("*.py"):
            if "__pycache__" in f.parts:
                continue
            # No tocar este script
            if f.name == "_reorg_kill_shims.py":
                continue
            n = rewrite_file_imports(f, stem_map)
            if n > 0:
                total_files_touched += 1
                total_lines += n

    print(f"\nRewrote {total_lines} import lines across {total_files_touched} files")

    # Eliminar shims
    shim_paths = [p for p in PKG.glob("*.py")
                  if p.stem not in {"__init__", "_ps", "_shared"}
                  and not p.stem.startswith("domain_tools_")  # shims pre-existentes R2
                  and is_shim(p)]
    print(f"\nDeleting {len(shim_paths)} shim files...")
    for p in shim_paths:
        rel = str(p.relative_to(REPO)).replace("\\", "/")
        r = subprocess.run(["git", "rm", rel], cwd=REPO,
                           capture_output=True, text=True)
        if r.returncode != 0:
            # Fallback: rm fisico + git add (untracked)
            p.unlink(missing_ok=True)
    print(f"Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
