"""Source Manager domain tool — extracted from domain_tools.py (R2 sprint
2026-05-28).

Bibliografía y snapshots de texto local persistidos en state.json como
resources kind=source. Cada source guarda title/url/source/text/saved_at.

Funciones extraídas (1):
  source_manager_tool             (entry, 7 acciones: status/list/save/
                                   snapshot_file/search/read/delete)

Helpers desde domain_tools (lazy):
  _resources_by_kind, _find_resource, _existing_path."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from ._shared import _err, _ok
from .state import AgentState
from .tool_result import ToolResult


__all__ = ["source_manager_tool"]


# R4 sprint 2026-05-28: handler migrado a ToolResult (con .to_dict() para
# back-compat).
def source_manager_tool(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    from .domain_tools_helpers import _existing_path, _find_resource, _resources_by_kind
    action = str(args.get("action") or "list").casefold()
    if action == "status":
        return ToolResult.ok_result(local_state=True, source_count=len(_resources_by_kind(state, "source"))).to_dict()
    if action in {"list", "sources"}:
        return ToolResult.ok_result(sources=_resources_by_kind(state, "source", include_closed=bool(args.get("include_closed", False)))).to_dict()
    if action in {"save", "add"}:
        title = str(args.get("title") or args.get("url") or args.get("source") or "source").strip()
        text = str(args.get("text") or args.get("content") or "").strip()
        url = str(args.get("url") or "").strip()
        resource = state.register_resource(
            "source",
            title,
            metadata={"title": title, "url": url, "source": args.get("source"), "text": text, "saved_at": datetime.now().isoformat()},
        )
        return ToolResult.ok_result(source=resource.get("resource")).to_dict()
    if action == "snapshot_file":
        path = _existing_path(args)
        if not path:
            return ToolResult.err("missing or invalid path").to_dict()
        max_chars = int(args.get("max_chars", 12000))
        text = path.read_text(encoding="utf-8", errors="replace")[:max_chars]
        resource = state.register_resource("source", path.name, metadata={"title": path.name, "path": str(path), "text": text, "saved_at": datetime.now().isoformat()})
        return ToolResult.ok_result(source=resource.get("resource"), chars=len(text)).to_dict()
    if action == "search":
        query = str(args.get("query") or "").casefold()
        if not query:
            return ToolResult.err("missing query").to_dict()
        matches = []
        for source in _resources_by_kind(state, "source", include_closed=bool(args.get("include_closed", False))):
            haystack = json.dumps(source.get("metadata", {}), ensure_ascii=False).casefold() + " " + str(source.get("label", "")).casefold()
            if query in haystack:
                matches.append(source)
        return ToolResult.ok_result(matches=matches[: int(args.get("limit", 10))], count=len(matches)).to_dict()
    if action in {"read", "get"}:
        source = _find_resource(args, state, "source")
        return ToolResult.ok_result(source=source).to_dict() if source else ToolResult.err("source not found").to_dict()
    if action == "delete":
        source = _find_resource(args, state, "source")
        return state.mark_cleaned(str(source["id"]), {"deleted": True}) if source else ToolResult.err("source not found").to_dict()
    return ToolResult.err(
        "unknown source_manager action", action=action,
        valid_actions=[
            "status", "save", "add", "list", "source_get", "source_delete",
            "bibtex_export",
        ],
        status="needs_user",
    ).to_dict()
