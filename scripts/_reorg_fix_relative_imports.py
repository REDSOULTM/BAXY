"""Tras matar shims, los subpaquetes pre-existentes (domain_tools, voice,
computer_use_caps, etc.) tienen `from ..X import Y` donde X era un shim
top-level que ya no existe. Hay que reescribir esos imports a
`from ..<subpkg>.X import Y` segun el mapa stem->subpkg.

Tambien aplica a archivos DENTRO de los subpkgs nuevos cuando algun import
relativo intra-pkg (from .X) apunta a un stem que NO esta en su subpkg
(ej. agent_core/agent.py importa `from .state` queriendo decir memory_pkg.state).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
PKG = REPO / "gemma4_agent"

NEW_SUBPKGS = (
    "agent_core", "computer_use_pkg", "routing", "infra",
    "safety_pkg", "memory_pkg", "tools_pkg", "mission", "support",
)


def build_stem_to_subpkg_map() -> dict[str, str]:
    out: dict[str, str] = {}
    for subpkg in NEW_SUBPKGS:
        d = PKG / subpkg
        if not d.is_dir():
            continue
        for f in d.glob("*.py"):
            if f.stem == "__init__":
                continue
            out.setdefault(f.stem, subpkg)
    return out


def rewrite(path: Path, stem_map: dict[str, str]) -> int:
    """Reescribe `from ..<stem> import` y `from .<stem> import` cuando stem
    esta en stem_map y NO es del subpkg en el que vive path.

    Tambien `from gemma4_agent.<stem>` -> `from gemma4_agent.<subpkg>.<stem>`.
    """
    try:
        src = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 0
    original = src

    # Determinar el subpkg de este archivo (vacio si esta en raiz del pkg)
    rel = path.relative_to(PKG)
    own_subpkg = rel.parts[0] if len(rel.parts) > 1 else ""

    # `from ..<stem>(.X.Y)? import ...`  -> si stem in map y stem in distinto subpkg,
    # cambiar a `from ..<map_subpkg>.<stem>... import ...`. Si stem NO esta en map,
    # dejarlo (apunta a algo que no se movio: voice/, ui/, etc.).
    def repl_ddot(m: re.Match) -> str:
        prefix, stem, suffix = m.group(1), m.group(2), m.group(3)
        if stem in stem_map:
            sub = stem_map[stem]
            if sub != own_subpkg:
                return f"{prefix}..{sub}.{stem}{suffix}"
        return m.group(0)

    src = re.sub(
        r"(\bfrom\s+)\.\.(\w+)((?:\.\w+)*\s+import\b)",
        repl_ddot, src,
    )

    # `from .<stem>(.X.Y)? import` dentro de un subpkg: si stem in map pero
    # otro subpkg, debe ser `from ..<map_subpkg>.<stem>`.
    def repl_sdot(m: re.Match) -> str:
        prefix, stem, suffix = m.group(1), m.group(2), m.group(3)
        if stem in stem_map and stem_map[stem] != own_subpkg:
            return f"{prefix}..{stem_map[stem]}.{stem}{suffix}"
        return m.group(0)

    src = re.sub(
        r"(\bfrom\s+)\.(\w+)((?:\.\w+)*\s+import\b)",
        repl_sdot, src,
    )

    # `from gemma4_agent.<stem>(.X.Y)? import` absoluto: igual al script
    # anterior, pero garantizando que esta vez NO se nos pase.
    def repl_abs(m: re.Match) -> str:
        prefix, stem, suffix = m.group(1), m.group(2), m.group(3)
        if stem in stem_map:
            return f"{prefix}gemma4_agent.{stem_map[stem]}.{stem}{suffix}"
        return m.group(0)

    src = re.sub(
        r"(\bfrom\s+)gemma4_agent\.(\w+)((?:\.\w+)*\s+import\b)",
        repl_abs, src,
    )

    if src != original:
        path.write_text(src, encoding="utf-8")
        return sum(1 for a, b in zip(original.splitlines(), src.splitlines())
                   if a != b)
    return 0


def main() -> int:
    stem_map = build_stem_to_subpkg_map()
    print(f"Stem map: {len(stem_map)} entries")

    total_files = 0
    total_lines = 0
    for f in PKG.rglob("*.py"):
        if "__pycache__" in f.parts:
            continue
        if f.name == "_reorg_fix_relative_imports.py":
            continue
        # Saltar domain_tools_<X>.py shims pre-existentes R2 (no tocar)
        if f.parent == PKG and f.name.startswith("domain_tools_"):
            continue
        n = rewrite(f, stem_map)
        if n > 0:
            total_files += 1
            total_lines += n
    print(f"Rewrote {total_lines} import lines in {total_files} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
