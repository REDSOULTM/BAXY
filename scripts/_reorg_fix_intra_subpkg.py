"""Tras matar shims, `from ..X` dentro de un subpkg que apunta a X tambien
en el mismo subpkg deberia ser `from .X`. Este script arregla eso.
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


def fix(path: Path, stem_map: dict[str, str]) -> int:
    rel = path.relative_to(PKG)
    own_subpkg = rel.parts[0] if len(rel.parts) > 1 else ""
    if not own_subpkg:
        return 0
    try:
        src = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 0
    original = src

    def repl(m: re.Match) -> str:
        prefix, stem, suffix = m.group(1), m.group(2), m.group(3)
        if stem in stem_map and stem_map[stem] == own_subpkg:
            return f"{prefix}.{stem}{suffix}"
        return m.group(0)

    src = re.sub(
        r"(\bfrom\s+)\.\.(\w+)((?:\.\w+)*\s+import\b)",
        repl, src,
    )

    if src != original:
        path.write_text(src, encoding="utf-8")
        return sum(1 for a, b in zip(original.splitlines(), src.splitlines())
                   if a != b)
    return 0


def main() -> int:
    stem_map = build_stem_to_subpkg_map()
    total = 0
    files = 0
    for f in PKG.rglob("*.py"):
        if "__pycache__" in f.parts:
            continue
        n = fix(f, stem_map)
        if n > 0:
            total += n
            files += 1
    print(f"Fixed {total} lines in {files} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
