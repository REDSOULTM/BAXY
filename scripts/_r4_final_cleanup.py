"""R4 final cleanup sprint 2026-05-28: borrar las defs duplicadas de
`_ok`/`_err` que el cleanup anterior dejó por el rename `_ok_tr`→`_ok`.

Patrón a borrar (con o sin comentario header):

    def _ok(**kw):
        return ToolResult.ok_result(**kw).to_dict()


    def _err(msg, **kw):
        return ToolResult.err(msg, **kw).to_dict()

Si `ToolResult` ya no se usa en otra parte del archivo, también se
borra el `from ..tool_result import ToolResult`.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


def process_file(path: Path) -> bool:
    """Returns True if file was modified."""
    src = path.read_text(encoding="utf-8")
    original = src

    # Patrón 1: par completo con o sin header comment
    patterns_to_remove = [
        # Con header comment
        r"\n*# R4 sprint 2026-05-28: handler migrado a ToolResult con \.to_dict\(\)\.\n"
        r"def _ok\(\*\*kw\):\n"
        r"    return ToolResult\.ok_result\(\*\*kw\)\.to_dict\(\)\n+"
        r"def _err\(msg, \*\*kw\):\n"
        r"    return ToolResult\.err\(msg, \*\*kw\)\.to_dict\(\)\n",
        # Con header alternativo (formato del __init__.py)
        r"\n*# R4 sprint 2026-05-28: alias para migración _ok/_err -> ToolResult\.to_dict\(\)\.\n"
        r"# Mantiene back-compat byte-a-byte con consumers viejos\.\n"
        r"def _ok\(\*\*kw\):\n"
        r"    return ToolResult\.ok_result\(\*\*kw\)\.to_dict\(\)\n+"
        r"def _err\(msg, \*\*kw\):\n"
        r"    return ToolResult\.err\(msg, \*\*kw\)\.to_dict\(\)\n",
        # Variante inline de local_search
        r"\n*# R4 sprint 2026-05-28: handler migrado a ToolResult con \.to_dict\(\)\.\n"
        r"def _ok\(\*\*kw\):  # local alias to keep the rest of the file readable\n"
        r"    return ToolResult\.ok_result\(\*\*kw\)\.to_dict\(\)\n+"
        r"def _err\(msg, \*\*kw\):\n"
        r"    return ToolResult\.err\(msg, \*\*kw\)\.to_dict\(\)\n",
    ]
    for pat in patterns_to_remove:
        src = re.sub(pat, "\n", src)

    # Si ToolResult ya no se usa, borrar el import.
    body_without_import_line = re.sub(r"^from \.+tool_result import ToolResult\n", "", src, flags=re.M)
    if "ToolResult" not in body_without_import_line:
        src = body_without_import_line

    if src != original:
        path.write_text(src, encoding="utf-8")
        return True
    return False


def main() -> int:
    pkg = Path("gemma4_agent")
    targets = []
    for p in pkg.rglob("*.py"):
        src = p.read_text(encoding="utf-8")
        if "def _ok(**kw):" in src and "ToolResult.ok_result" in src:
            targets.append(p)
    print(f"Found {len(targets)} files with duplicate _ok/_err defs.")
    n = 0
    for p in targets:
        if process_file(p):
            print(f"  cleaned: {p.relative_to(Path('.'))}")
            n += 1
    print(f"Modified: {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
