"""R3 deep cleanup 2026-05-28: eliminar lazies redundantes que importan
EXACTAMENTE lo mismo que ya está en top-level del MISMO archivo.

Estos lazies no aportan nada — son ruido que el audit cuenta como
"imports-inside-function". El nombre ya está disponible en el module
scope vía el import top-level.

Conservador: SOLO elimino líneas que matcheen exactamente. Si la lazy
usa `as` para alias diferente, NO la toco (puede ser intencional).
Si la lazy importa MÁS nombres que el top-level, NO la toco.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


def process_file(path: Path) -> int:
    """Devuelve cuántas líneas se eliminaron."""
    src = path.read_text(encoding="utf-8")
    lines = src.split("\n")

    # Top-level imports: (module, name) pairs
    top_set: set[tuple[str, str]] = set()
    for m in re.finditer(r"^from \.(\S+) import (.+)$", src, re.M):
        mod = m.group(1)
        for n in re.findall(r"\b[a-zA-Z_]\w*\b", m.group(2)):
            top_set.add((mod, n))

    # Find lazy lines that exactly duplicate top-level (single-name imports only).
    new_lines: list[str] = []
    removed = 0
    for line in lines:
        # Lazy single-import (no `as`, no parens, no commas)
        m = re.match(r"^(\s+)from \.([a-zA-Z_]\w*) import ([a-zA-Z_]\w*)\s*(?:#.*)?$", line)
        if m and "," not in line and " as " not in line:
            mod, name = m.group(2), m.group(3)
            if (mod, name) in top_set:
                removed += 1
                continue
        new_lines.append(line)

    if removed:
        path.write_text("\n".join(new_lines), encoding="utf-8")
    return removed


def main() -> int:
    pkg = Path("gemma4_agent")
    total = 0
    files = 0
    for p in sorted(pkg.rglob("*.py")):
        if p.name.startswith("test_"):
            continue
        if "node_modules" in p.parts:
            continue
        n = process_file(p)
        if n:
            print(f"  {n:>3}  {p.relative_to('gemma4_agent')}")
            total += n
            files += 1
    print(f"TOTAL: {total} lazies removed from {files} files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
