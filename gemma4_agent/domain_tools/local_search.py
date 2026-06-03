"""Local filesystem search — extracted from domain_tools.py.

Búsqueda recursiva sobre el filesystem local con:
  - budget temporal (default 10s)
  - max_visited (default 50k archivos) — protección contra rglob a Home con
    500k archivos
  - binary guard (lee 512 bytes, detecta NUL antes de tratar como texto)
  - skipped_io counter para reportar archivos sin permiso

Funciones extraídas (1):
  local_search_tool              (entry, 3 acciones: status, search, recent)

Auto-contenido (shutil, pathlib, time, datetime; nada de domain_tools)."""
from __future__ import annotations

import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from .._shared import _err, _ok


__all__ = ["local_search_tool"]


def local_search_tool(args: dict[str, Any]) -> dict[str, Any]:
    action = str(args.get("action") or "search").casefold()
    if action == "status":
        return _ok(everything_cli=bool(shutil.which("es.exe")), backend="python_rglob")
    if action == "search":
        root = Path(str(args.get("root") or Path.home())).expanduser()
        if not root.exists():
            return _err("root not found", root=str(root), status="needs_user")
        if not root.is_dir():
            return _err("root is not a directory", root=str(root), status="needs_user")
        query = str(args.get("query") or "").casefold()
        pattern = str(args.get("pattern") or "*")
        try:
            limit = max(1, min(int(args.get("limit", 50)), 500))
        except (TypeError, ValueError):
            limit = 50
        include_content = bool(args.get("include_content", False))
        # BUDGET: rglob sin limite sobre Home puede caminar 500K archivos.
        try:
            budget_s = float(args.get("budget_s", 10.0))
        except (TypeError, ValueError):
            budget_s = 10.0
        budget_s = max(1.0, min(budget_s, 60.0))
        deadline = time.time() + budget_s
        max_visited = int(args.get("max_visited", 50000))
        results = []
        visited = 0
        skipped_io = 0
        try:
            iterator = root.rglob(pattern) if bool(args.get("recursive", True)) else root.glob(pattern)
            for path in iterator:
                visited += 1
                if len(results) >= limit or visited > max_visited:
                    break
                if time.time() > deadline:
                    break
                try:
                    name_hit = query in path.name.casefold() if query else True
                    content_hit = False
                    snippet = ""
                    is_file = path.is_file()
                    file_size = path.stat().st_size if is_file else None
                    # BINARY GUARD: si include_content + archivo > max_bytes
                    # ya lo salta. Ademas guard contra binarios reales:
                    # leemos primero los 512 bytes para detectar NUL.
                    if include_content and is_file and file_size is not None and file_size < int(args.get("max_bytes", 2_000_000)):
                        try:
                            with path.open("rb") as fh:
                                head = fh.read(512)
                            if b"\x00" not in head:
                                text = path.read_text(encoding="utf-8", errors="replace")
                                idx = text.casefold().find(query)
                                content_hit = idx >= 0
                                snippet = text[max(0, idx - 80): idx + 180] if content_hit else ""
                        except (PermissionError, OSError):
                            skipped_io += 1
                    if name_hit or content_hit:
                        results.append({
                            "path": str(path), "is_file": is_file,
                            "size": file_size, "snippet": snippet,
                        })
                except (PermissionError, OSError):
                    skipped_io += 1
                    continue
        except OSError as exc:
            return _err(f"search failed: {exc}", root=str(root))
        truncated = (
            len(results) >= limit
            or visited > max_visited
            or time.time() > deadline
        )
        return _ok(
            results=results, count=len(results), root=str(root),
            truncated=truncated, visited=visited, skipped_io=skipped_io,
        )
    if action == "recent":
        root = Path(str(args.get("root") or Path.home())).expanduser()
        if not root.exists() or not root.is_dir():
            return _err("root not found or not a directory", root=str(root), status="needs_user")
        try:
            limit = max(1, min(int(args.get("limit", 20)), 200))
        except (TypeError, ValueError):
            limit = 20
        # BUDGET: rglob igual que en search.
        try:
            budget_s = float(args.get("budget_s", 10.0))
        except (TypeError, ValueError):
            budget_s = 10.0
        deadline = time.time() + max(1.0, min(budget_s, 60.0))
        max_visited = int(args.get("max_visited", 50000))
        files: list[tuple[float, Path]] = []
        visited = 0
        for path in root.rglob(str(args.get("pattern") or "*")):
            visited += 1
            if visited > max_visited or time.time() > deadline:
                break
            if path.is_file():
                try:
                    files.append((path.stat().st_mtime, path))
                except OSError:
                    pass
            if len(files) > 5000:
                break
        files.sort(reverse=True)
        return _ok(
            files=[{"path": str(p), "modified": datetime.fromtimestamp(ts).isoformat()} for ts, p in files[:limit]],
            visited=visited,
            truncated=visited > max_visited or time.time() > deadline,
        )
    return _err(
        "unknown local_search action", action=action,
        valid_actions=["status", "search", "recent"], status="needs_user",
    )
