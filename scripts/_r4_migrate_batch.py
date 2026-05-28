"""R4 sprint 2026-05-28: batch-migrate handlers to ToolResult.to_dict().

Conservative migration: rewrite `_ok(...)`/`_err(...)` to `_ok_tr(...)`/
`_err_tr(...)` aliases that wrap the legacy dict via ToolResult. Same
byte-output, but the handler now flows through the typed dataclass for
free Pylance/mypy validation.

Usage:
    python scripts/_r4_migrate_batch.py <area1> <area2> ...
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


def migrate(name: str) -> str:
    """Migrate a single sibling. Returns one-line status."""
    p = Path(f"gemma4_agent/domain_tools_{name}.py")
    if not p.exists():
        return f"{name}: NOT FOUND"
    src = p.read_text(encoding="utf-8")
    if "from .tool_result import ToolResult" in src:
        return f"{name}: already migrated"
    if "from ._shared import _err, _ok" not in src:
        return f"{name}: skip (no _err/_ok import)"
    src = re.sub(
        r"(from \._shared import _err, _ok\n)",
        r"\1from .tool_result import ToolResult\n",
        src, count=1,
    )
    if "_ok_tr" not in src:
        helpers = (
            "\n\n# R4 sprint 2026-05-28: handler migrado a ToolResult con .to_dict().\n"
            "def _ok_tr(**kw):\n    return ToolResult.ok_result(**kw).to_dict()\n\n\n"
            "def _err_tr(msg, **kw):\n    return ToolResult.err(msg, **kw).to_dict()\n"
        )
        src = re.sub(
            r"(__all__ = \[[^\]]*\]\n)",
            r"\1" + helpers,
            src, count=1,
        )
    src = re.sub(r"\b_ok\(", "_ok_tr(", src)
    src = re.sub(r"\b_err\(", "_err_tr(", src)
    p.write_text(src, encoding="utf-8")
    return f"{name}: OK"


def main(argv: list[str]) -> int:
    targets = argv or [
        "data_analysis", "media_edit", "study", "printer_scanner",
        "backup_sync", "maintenance", "photo_library", "game_launcher",
        "job_manager", "watcher", "accessibility", "document", "network",
    ]
    for name in targets:
        print(migrate(name))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
