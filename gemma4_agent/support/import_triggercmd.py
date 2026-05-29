"""CLI: import TriggerCMD commands.json into Gemma4 on_phrase routines.

Usage:
    python -m gemma4_agent.support.import_triggercmd <ruta-al-commands.json>
    python -m gemma4_agent.support.import_triggercmd <ruta-al-commands.json> --overwrite
    python -m gemma4_agent.support.import_triggercmd <ruta-al-commands.json> --dry-run

dry-run reads the file and shows what would happen WITHOUT creating routines.
overwrite allows re-using a phrase that already exists (replaces would be
unsafe; instead we skip dupes by default and warn).

The CLI is a thin wrapper over `routine_tool(action='import')` so it shares
all validation, idempotency and storage with the in-chat tool. After import,
run `python -m gemma4_agent.support.chat` and the routines are immediately active.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gemma4_agent.import_triggercmd",
                                     description="Import TriggerCMD commands.json as Gemma4 on_phrase routines.")
    parser.add_argument("json_path", help="Path to your TriggerCMD commands.json export")
    parser.add_argument("--overwrite", action="store_true",
                        help="Allow reusing phrases that already exist (default: skip duplicates).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would happen without creating routines.")
    args = parser.parse_args(argv)

    path = Path(args.json_path).expanduser()
    if not path.is_file():
        print(f"error: file not found: {path}", file=sys.stderr)
        return 2
    try:
        entries = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"error: invalid JSON at {path}: {exc}", file=sys.stderr)
        return 2
    if not isinstance(entries, list):
        print(f"error: expected a JSON array at top level, got {type(entries).__name__}", file=sys.stderr)
        return 2

    if args.dry_run:
        return _dry_run(entries)

    # Defer imports of the heavy bits until we know we'll actually create stuff.
    from ..infra.config import AgentConfig
    from ..domain_tools import import_triggercmd_entries
    from ..memory_pkg.state import AgentState

    config = AgentConfig.from_env()
    state = AgentState(config.state_path)
    result = import_triggercmd_entries(entries, state, overwrite_same_phrase=args.overwrite)

    imported = result.get("imported", [])
    skipped = result.get("skipped", [])
    total = result.get("total_input", len(entries))

    print(f"\nTotal input entries: {total}")
    print(f"Imported routines:   {len(imported)}")
    print(f"Skipped:             {len(skipped)}\n")

    if imported:
        print("--- Imported ---")
        for item in imported:
            tag = item.get("trigger") or item.get("phrase")
            line = f"  + {tag!r:40s} phrase='{item.get('phrase')}'"
            if item.get("off_phrase"):
                line += f" + off='{item['off_phrase']}'"
            elif item.get("off_skipped"):
                line += f" (off skipped: {item['off_skipped']})"
            print(line)

    if skipped:
        print("\n--- Skipped ---")
        for item in skipped:
            tag = item.get("trigger") or item.get("voice") or f"#{item.get('index')}"
            reason = item.get("reason", "unknown")
            extra = f"  err={item.get('error')}" if item.get("error") else ""
            print(f"  - {tag!r:40s} reason={reason}{extra}")

    # The note is the same the in-chat tool returns; surface once.
    if note := result.get("note"):
        print(f"\nNote: {note}")
    return 0 if imported or not skipped else 1


def _dry_run(entries: list[dict]) -> int:
    would_import: list[str] = []
    would_skip: list[tuple[str, str]] = []
    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            would_skip.append((f"#{i}", "not_an_object"))
            continue
        voice = str(entry.get("voice") or "").strip()
        command = str(entry.get("command") or "").strip()
        trigger = str(entry.get("trigger") or "").strip()
        allow_params = str(entry.get("allowParams") or "").strip().casefold() in {"true", "1", "yes"}
        label = trigger or f"triggercmd_{i}"
        if not command:
            would_skip.append((label, "empty_command"))
            continue
        if not voice:
            would_skip.append((label, "empty_voice"))
            continue
        if len(voice) < 3:
            would_skip.append((label, "voice_too_short"))
            continue
        if allow_params:
            would_skip.append((label, "allowParams_true_needs_manual_setup"))
            continue
        suffix = " + off-routine" if entry.get("offCommand") else ""
        would_import.append(f"{label!r:40s} phrase='{voice}'{suffix}")
    print(f"\n[dry-run] No changes written.\n")
    print(f"Would import: {len(would_import)}")
    print(f"Would skip:   {len(would_skip)}\n")
    for line in would_import:
        print(f"  + {line}")
    if would_skip:
        print("\n  Skips:")
        for label, reason in would_skip:
            print(f"  - {label!r:40s} reason={reason}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
