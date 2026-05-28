"""R2 sprint 2026-05-28 (finalización): convertir los 36 hermanos
`gemma4_agent/domain_tools_<area>.py` en un sub-paquete real
`gemma4_agent/domain_tools/` con `<area>.py` adentro.

CONFLICTO: en Python no pueden coexistir `domain_tools.py` (módulo) y
`domain_tools/` (paquete). Solución:
  - El contenido del archivo `domain_tools.py` se mueve a
    `domain_tools/__init__.py`.
  - Los siblings `domain_tools_X.py` se mueven a `domain_tools/X.py`.
  - Re-escribimos imports internos `from .domain_tools_X` → `from .X`
    DENTRO del nuevo paquete.
  - Re-escribimos `from .domain_tools_helpers import` → `from .helpers import`.
  - Los archivos `domain_tools_X.py` originales quedan como SHIMS que
    re-exportan desde el paquete, por si algún consumer externo todavía
    los importa por path viejo.
  - El antiguo `domain_tools.py` se BORRA — su contenido ahora vive en
    `__init__.py`.

Idempotente: aborta si `domain_tools/` ya existe.
"""
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path


PKG = Path("gemma4_agent")
OLD_FILE = PKG / "domain_tools.py"
NEW_PKG = PKG / "domain_tools"


def main() -> int:
    if NEW_PKG.exists():
        print(f"ABORT: {NEW_PKG} already exists.")
        return 1
    if not OLD_FILE.exists():
        print(f"ABORT: {OLD_FILE} missing — already converted?")
        return 1

    # Step 0: list siblings (sorted for reproducibility)
    siblings = sorted(p for p in PKG.glob("domain_tools_*.py"))
    print(f"Found {len(siblings)} siblings.")

    # Step 1: create package + __init__.py from old domain_tools.py.
    NEW_PKG.mkdir()
    init_path = NEW_PKG / "__init__.py"
    init_body = OLD_FILE.read_text(encoding="utf-8")
    # Rewrite imports inside __init__.py:
    #   from .domain_tools_X import ...  →  from .X import ...
    #   from .domain_tools_helpers import → from .helpers import
    init_body = re.sub(
        r"from \.domain_tools_helpers import",
        "from .helpers import",
        init_body,
    )
    init_body = re.sub(
        r"from \.domain_tools_([a-z_]+) import",
        r"from .\1 import",
        init_body,
    )
    init_path.write_text(init_body, encoding="utf-8")
    print(f"Created {init_path}")

    # Step 2: move each sibling into the package as <area>.py, rewriting
    # its internal imports.
    for sib in siblings:
        area = sib.stem.replace("domain_tools_", "")
        target = NEW_PKG / f"{area}.py"
        body = sib.read_text(encoding="utf-8")
        body = re.sub(
            r"from \.domain_tools_helpers import",
            "from .helpers import",
            body,
        )
        body = re.sub(
            r"from \.domain_tools_([a-z_]+) import",
            r"from .\1 import",
            body,
        )
        # Cross-package import: when INSIDE domain_tools/, "from .domain_tools
        # import X" would mean a non-existent nested module. Use "from . import X"
        # (the package itself).
        body = re.sub(r"from \.domain_tools import ", "from . import ", body)
        target.write_text(body, encoding="utf-8")
    print(f"Moved {len(siblings)} siblings into {NEW_PKG}/")

    # Step 3: turn the original sibling files into thin re-export shims so
    # external `from gemma4_agent.domain_tools_<area>` keeps working.
    for sib in siblings:
        area = sib.stem.replace("domain_tools_", "")
        shim_body = (
            f'"""Back-compat shim — re-exporta `gemma4_agent.domain_tools.{area}`\n'
            f'para callers que todavía importan `gemma4_agent.domain_tools_{area}`.\n'
            f"R2-finalize sprint 2026-05-28.\n"
            f'"""\n'
            f"from .domain_tools.{area} import *  # noqa: F401,F403\n"
        )
        sib.write_text(shim_body, encoding="utf-8")
    print(f"Rewrote {len(siblings)} sibling files as back-compat shims.")

    # Step 4: delete the old `domain_tools.py` (its body lives in __init__.py).
    OLD_FILE.unlink()
    print(f"Deleted old {OLD_FILE}.")

    print()
    print("Done. New layout:")
    for f in sorted(NEW_PKG.iterdir()):
        print(f"  domain_tools/{f.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
