"""R4 cleanup sprint 2026-05-28: revertir el alias `_ok_tr/_err_tr` a
`_ok/_err` directos. El alias era para "back-compat byte-a-byte via
ToolResult", pero `_ok(...)` y `ToolResult.ok_result(...).to_dict()`
producen el mismo dict — el alias es ruido. El dataclass queda
disponible en `tool_result.py` para una migración REAL handler-por-
handler en sprint futuro.

Reescribe: `_ok_tr(` → `_ok(`, `_err_tr(` → `_err(`.
Borra las defs de `_ok_tr` / `_err_tr` cuando ya no se usan.
Borra el `from .tool_result import ToolResult` si queda no-usado.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


def process_file(path: Path) -> bool:
    """Returns True if file was modified."""
    src = path.read_text(encoding="utf-8")
    original = src
    # Step 1: replace call sites
    src = re.sub(r"\b_ok_tr\(", "_ok(", src)
    src = re.sub(r"\b_err_tr\(", "_err(", src)
    # Step 2: remove the alias defs (only if no remaining usage)
    # The injected block looks like:
    #
    # # R4 sprint 2026-05-28: handler migrado a ToolResult con .to_dict().
    # def _ok_tr(**kw):
    #     return ToolResult.ok_result(**kw).to_dict()
    #
    #
    # def _err_tr(msg, **kw):
    #     return ToolResult.err(msg, **kw).to_dict()
    src = re.sub(
        r"\n\n# R4 sprint 2026-05-28: handler migrado a ToolResult con \.to_dict\(\)\.\n"
        r"def _ok_tr\(\*\*kw\):\n"
        r"    return ToolResult\.ok_result\(\*\*kw\)\.to_dict\(\)\n\n\n"
        r"def _err_tr\(msg, \*\*kw\):\n"
        r"    return ToolResult\.err\(msg, \*\*kw\)\.to_dict\(\)\n",
        "",
        src,
    )
    # Also the variant in domain_tools/__init__.py (different comment)
    src = re.sub(
        r"\n\n# R4 sprint 2026-05-28: alias para migración _ok/_err -> ToolResult\.to_dict\(\)\.\n"
        r"# Mantiene back-compat byte-a-byte con consumers viejos\.\n"
        r"def _ok_tr\(\*\*kw\):\n"
        r"    return ToolResult\.ok_result\(\*\*kw\)\.to_dict\(\)\n\n\n"
        r"def _err_tr\(msg, \*\*kw\):\n"
        r"    return ToolResult\.err\(msg, \*\*kw\)\.to_dict\(\)\n",
        "",
        src,
    )
    # Variant present in local_search.py and notes.py (inline form)
    src = re.sub(
        r"# R4 sprint 2026-05-28: handler migrado a ToolResult con \.to_dict\(\)\.\n"
        r"def _ok_tr\(\*\*kw\):  # local alias to keep the rest of the file readable\n"
        r"    return ToolResult\.ok_result\(\*\*kw\)\.to_dict\(\)\n\n\n"
        r"def _err_tr\(msg, \*\*kw\):\n"
        r"    return ToolResult\.err\(msg, \*\*kw\)\.to_dict\(\)\n\n\n",
        "",
        src,
    )
    # Step 3: remove the now-unused `from ..tool_result import ToolResult`
    # only if ToolResult is no longer referenced.
    if "ToolResult" not in re.sub(r"from .+?ToolResult.*\n", "", src):
        src = re.sub(r"^from \.+tool_result import ToolResult\n", "", src, flags=re.M)
    return original != src and (path.write_text(src, encoding="utf-8") or True)


def main() -> int:
    pkg = Path("gemma4_agent")
    # Affected files: anything that has `_ok_tr(` or `_err_tr(`.
    targets = []
    for p in list(pkg.rglob("*.py")):
        if "_ok_tr(" in p.read_text(encoding="utf-8") or "_err_tr(" in p.read_text(encoding="utf-8"):
            targets.append(p)
    print(f"Found {len(targets)} files with _ok_tr/_err_tr.")
    n_modified = 0
    for p in targets:
        if process_file(p):
            print(f"  cleaned: {p.relative_to(Path('.'))}")
            n_modified += 1
    print(f"Modified: {n_modified} files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
