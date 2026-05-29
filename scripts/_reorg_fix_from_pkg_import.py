"""Reescribe `from gemma4_agent import X as Y` / `from gemma4_agent import X`
para X que ahora vive en un subpkg.

Patron destinatario:
    from gemma4_agent import X as Y
    ->
    from gemma4_agent.<subpkg> import X as Y

    from gemma4_agent import X
    ->
    from gemma4_agent.<subpkg> import X

Soporta multiple imports en una linea: `from gemma4_agent import a, b as B, c`.
Si NO todos los names estan en el stem_map, deja la linea sin tocar (caso
mixto raro).
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


def rewrite_file(path: Path, stem_map: dict[str, str]) -> int:
    try:
        src = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 0
    original = src
    out_lines = []
    changed = 0
    for line in src.splitlines(keepends=True):
        m = re.match(r"^(\s*)from\s+gemma4_agent\s+import\s+(.+?)(\s*(?:#.*)?)$", line)
        if not m:
            out_lines.append(line)
            continue
        indent, names_raw, trailing = m.group(1), m.group(2).strip(), m.group(3) or ""
        # `a as A, b, c as C` -> [("a","A"), ("b","b"), ("c","C")]
        items: list[tuple[str, str]] = []
        for piece in names_raw.split(","):
            piece = piece.strip()
            if not piece:
                continue
            parts = re.split(r"\s+as\s+", piece, maxsplit=1)
            if len(parts) == 2:
                items.append((parts[0].strip(), parts[1].strip()))
            else:
                items.append((parts[0].strip(), parts[0].strip()))

        # Agrupar por subpkg
        by_sub: dict[str, list[tuple[str, str]]] = {}
        unmapped: list[tuple[str, str]] = []
        for name, alias in items:
            if name in stem_map:
                by_sub.setdefault(stem_map[name], []).append((name, alias))
            else:
                unmapped.append((name, alias))

        if not by_sub:
            # Nada migrable, dejar
            out_lines.append(line)
            continue

        # Construir las lineas nuevas
        new_lines: list[str] = []
        ending = "\n" if line.endswith("\n") else ""
        line_no_nl = line.rstrip("\n")

        for sub, sub_items in sorted(by_sub.items()):
            parts = []
            for name, alias in sub_items:
                if name == alias:
                    parts.append(name)
                else:
                    parts.append(f"{name} as {alias}")
            new_lines.append(f"{indent}from gemma4_agent.{sub} import {', '.join(parts)}{trailing}")

        if unmapped:
            parts = []
            for name, alias in unmapped:
                if name == alias:
                    parts.append(name)
                else:
                    parts.append(f"{name} as {alias}")
            new_lines.append(f"{indent}from gemma4_agent import {', '.join(parts)}{trailing}")

        replacement = "\n".join(new_lines) + ending
        if replacement != line:
            changed += 1
        out_lines.append(replacement)

    new_src = "".join(out_lines)
    if new_src != original:
        path.write_text(new_src, encoding="utf-8")
    return changed


def main() -> int:
    stem_map = build_stem_to_subpkg_map()
    print(f"Stem map: {len(stem_map)} entries")
    total_files = 0
    total_lines = 0
    for root in (REPO / "scripts", PKG):
        for f in root.rglob("*.py"):
            if "__pycache__" in f.parts:
                continue
            if f.name.startswith("_reorg_"):
                continue
            n = rewrite_file(f, stem_map)
            if n > 0:
                total_files += 1
                total_lines += n
    print(f"Rewrote {total_lines} from-import lines in {total_files} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
