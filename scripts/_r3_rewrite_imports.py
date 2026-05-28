"""R3 sprint 2026-05-28: rewrite lazy `from .domain_tools import <helper>` to
top-level-ready `from .domain_tools_helpers import <helper>` across the 19
sibling modules.

The rewrite is conservative — it only touches lines whose import EXACTLY
matches one of the 13 helpers extracted to domain_tools_helpers.py, so
unrelated lazy imports (e.g. `from .domain_tools import _resolve_streaming_provider`)
are left untouched.

Idempotent: running twice is a no-op.
"""
from __future__ import annotations

import re
from pathlib import Path

HELPERS = {
    "_existing_path",
    "_find_resource",
    "_find_routine",
    "_find_soundvolumeview",
    "_json_or_none",
    "_parse_due_iso",
    "_pid_alive",
    "_pid_owned_by",
    "_powershell_json",
    "_ps_quote",
    "_resources_by_kind",
    "_safe_name",
    "_update_resource_metadata",
}

FILES = [
    "gemma4_agent/domain_tools_accessibility.py",
    "gemma4_agent/domain_tools_backup_sync.py",
    "gemma4_agent/domain_tools_calendar.py",
    "gemma4_agent/domain_tools_contacts.py",
    "gemma4_agent/domain_tools_dependency.py",
    "gemma4_agent/domain_tools_desktop_layout.py",
    "gemma4_agent/domain_tools_developer.py",
    "gemma4_agent/domain_tools_document.py",
    "gemma4_agent/domain_tools_job_manager.py",
    "gemma4_agent/domain_tools_maintenance.py",
    "gemma4_agent/domain_tools_media_edit.py",
    "gemma4_agent/domain_tools_network.py",
    "gemma4_agent/domain_tools_notifications.py",
    "gemma4_agent/domain_tools_office.py",
    "gemma4_agent/domain_tools_peripheral.py",
    "gemma4_agent/domain_tools_printer_scanner.py",
    "gemma4_agent/domain_tools_routine.py",
    "gemma4_agent/domain_tools_source_manager.py",
    "gemma4_agent/domain_tools_watcher.py",
]

# Match: an import line whose symbols are ALL in HELPERS (possibly with
# trailing comment). Lines mixing helpers with non-helpers stay lazy and
# require manual review (R3 follow-up).
IMPORT_RE = re.compile(
    r"^(?P<indent>\s*)from \.domain_tools import (?P<symbols>[^#\n]+?)(?P<trailing>\s*#.*)?$"
)


def split_symbols(raw: str) -> list[str]:
    return [s.strip() for s in raw.split(",") if s.strip()]


def main() -> int:
    total_rewritten = 0
    skipped_mixed = 0
    for relpath in FILES:
        path = Path(relpath)
        src = path.read_text(encoding="utf-8")
        new_lines: list[str] = []
        file_changes = 0
        for line in src.splitlines(keepends=True):
            m = IMPORT_RE.match(line.rstrip("\n").rstrip("\r"))
            if not m:
                new_lines.append(line)
                continue
            symbols = split_symbols(m.group("symbols"))
            if not symbols:
                new_lines.append(line)
                continue
            if all(s in HELPERS for s in symbols):
                trailing = m.group("trailing") or ""
                rewritten = (
                    f"{m.group('indent')}from .domain_tools_helpers import "
                    f"{', '.join(symbols)}{trailing}"
                )
                # preserve original line ending
                eol = ""
                if line.endswith("\r\n"):
                    eol = "\r\n"
                elif line.endswith("\n"):
                    eol = "\n"
                new_lines.append(rewritten + eol)
                file_changes += 1
            else:
                # Mixed import (some helpers, some not). Leave alone for
                # manual handling; print so we can audit.
                non_helpers = [s for s in symbols if s not in HELPERS]
                print(f"  MIXED {relpath}:{line.strip()!r} non_helpers={non_helpers}")
                skipped_mixed += 1
                new_lines.append(line)
        if file_changes:
            path.write_text("".join(new_lines), encoding="utf-8")
            print(f"OK   {relpath}  ({file_changes} imports rewritten)")
            total_rewritten += file_changes
        else:
            print(f"--   {relpath}  (nothing to do)")
    print()
    print(f"TOTAL rewritten: {total_rewritten}")
    print(f"MIXED skipped:   {skipped_mixed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
