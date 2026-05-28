"""R2 sprint 2026-05-28: arregla los imports relativos dentro del nuevo
sub-paquete `gemma4_agent/domain_tools/`.

Dentro del sub-paquete, un `from .X import ...` apunta a un submódulo
HERMANO del paquete (domain_tools/X.py). Pero el código original (que
fue movido desde gemma4_agent/domain_tools.py al nuevo __init__.py o
desde gemma4_agent/domain_tools_X.py al nuevo domain_tools/X.py) usaba
`from .X` para apuntar a archivos en gemma4_agent/ (un nivel arriba).

Esa diferencia rompe los imports. Este script lista los nombres que son
submódulos del propio paquete (sus archivos hermanos) y los preserva;
todo lo demás se reescribe como `from ..X import ...` (subir un nivel).

Idempotente — re-correrlo no hace nada si los imports ya están bien.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


PKG_DIR = Path("gemma4_agent/domain_tools")


def main() -> int:
    if not PKG_DIR.exists():
        print(f"ABORT: {PKG_DIR} missing.")
        return 1

    submodules = {p.stem for p in PKG_DIR.glob("*.py") if p.stem != "__init__"}
    print(f"Submodules: {len(submodules)}")

    pattern = re.compile(r"^(\s*from )\.([a-zA-Z_][a-zA-Z0-9_]*)(\.|\b)", re.M)

    def rewrite(text: str) -> tuple[str, int]:
        count = 0
        def repl(m):
            nonlocal count
            prefix, name, tail = m.group(1), m.group(2), m.group(3)
            if name in submodules:
                return m.group(0)  # keep
            count += 1
            return f"{prefix}..{name}{tail}"
        new = pattern.sub(repl, text)
        return new, count

    total = 0
    for p in sorted(PKG_DIR.glob("*.py")):
        src = p.read_text(encoding="utf-8")
        new, n = rewrite(src)
        if n:
            p.write_text(new, encoding="utf-8")
            print(f"  {p.name}: rewrote {n} imports")
            total += n
    print(f"TOTAL: {total} imports rewritten across the package.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
