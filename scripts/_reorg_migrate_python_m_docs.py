"""Migra `python -m gemma4_agent.<runnable>` -> `python -m gemma4_agent.<subpkg>.<runnable>`
en docstrings y READMEs activos. No toca docs/sprints/ ni docs/_archive/ (historia).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
PKG = REPO / "gemma4_agent"

# Mapa runnable -> subpkg
RUNNABLES = {
    "launcher": "infra",
    "server": "infra",
    "voice_runner": "infra",
    "watcher_runner": "infra",
    "task_runner": "infra",
    "routine_runner": "infra",
    "microagents": "memory_pkg",
    "mcp_server": "tools_pkg",
    "skills_registry": "tools_pkg",
    "chat": "support",
    "eval_smoke": "support",
    "import_triggercmd": "support",
}

# NO tocar (historia, NO actualizar):
SKIP_DIRS = {
    "docs/sprints",
    "docs/_archive",
    "docs/architecture/_baseline_audit",
}


def should_skip(p: Path) -> bool:
    rel = str(p.relative_to(PKG)).replace("\\", "/")
    return any(rel.startswith(s) for s in SKIP_DIRS)


def migrate_file(p: Path) -> int:
    try:
        src = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 0
    original = src

    for runnable, subpkg in RUNNABLES.items():
        # `python -m gemma4_agent.<runnable>` -> `python -m gemma4_agent.<subpkg>.<runnable>`
        # No tocar si ya tiene un dot intermedio (ya migrado).
        pat = re.compile(
            r"python -m gemma4_agent\." + runnable + r"(?![.\w])"
        )
        src = pat.sub(f"python -m gemma4_agent.{subpkg}.{runnable}", src)

    if src != original:
        p.write_text(src, encoding="utf-8")
        return sum(1 for a, b in zip(original.splitlines(), src.splitlines())
                   if a != b)
    return 0


def main() -> int:
    total_files = 0
    total_lines = 0
    targets = []
    # Docs activos
    for d in (PKG, PKG / "docs", REPO / "documentacion"):
        if not d.is_dir():
            continue
        for f in d.rglob("*.md"):
            if d == PKG / "docs" and should_skip(f):
                continue
            targets.append(f)
    # Codigo productivo (docstrings, comentarios)
    for f in PKG.rglob("*.py"):
        if "__pycache__" in f.parts:
            continue
        if f.name.startswith("_reorg_"):
            continue
        targets.append(f)
    # .gitignore puntual
    for f in PKG.rglob(".gitignore"):
        targets.append(f)

    for f in targets:
        n = migrate_file(f)
        if n > 0:
            total_files += 1
            total_lines += n
            rel = f.relative_to(REPO)
            print(f"  {rel}: {n} lines")

    print(f"\nMigrated {total_lines} lines in {total_files} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
