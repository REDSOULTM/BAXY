"""Notes / Tasks domain tool — extracted from domain_tools.py (R2 sprint
2026-05-27).

Notas y tareas pendientes locales, persistidas como recursos del state. NO toca
ninguna app externa (ni MS Tasks ni Notion); todo vive en state.json. Esa es
la decisión deliberada del proyecto: privacidad + offline-first.

Funciones extraídas (1, con 13 acciones internas):
  notes_tasks_tool

Acciones: status, note_create, task_create, note_list, task_list, note_search,
task_search, search, task_complete, note_delete, task_delete, note_update,
task_update.

Helpers importados desde domain_tools (lazy, dentro de la función):
  _resources_by_kind, _find_resource, _update_resource_metadata, _parse_due_iso

Mock-friendly: solo lee/escribe state. Tests futuros pueden mockear AgentState
methods directamente."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from .._shared import _err, _ok
from ..state import AgentState
from ..tool_result import ToolResult


__all__ = ["notes_tasks_tool"]


# R4 sprint 2026-05-28: handler migrado a ToolResult con .to_dict().
def _ok_tr(**kw):
    return ToolResult.ok_result(**kw).to_dict()


def _err_tr(msg, **kw):
    return ToolResult.err(msg, **kw).to_dict()


def notes_tasks_tool(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    # Imports diferidos para evitar ciclo en import time (notes -> domain_tools
    # -> notes via re-export). En runtime el módulo ya está cargado.
    from .helpers import (
        _find_resource,
        _parse_due_iso,
        _resources_by_kind,
        _update_resource_metadata,
    )
    action = str(args.get("action") or "list").casefold()
    if action == "status":
        return _ok_tr(notes=len(_resources_by_kind(state, "note")), tasks=len(_resources_by_kind(state, "task")))
    if action in {"note_create", "create_note"}:
        title = str(args.get("title") or "").strip() or "Nota"
        text = str(args.get("text") or args.get("content") or "").strip()
        # WARNING (no error) si la nota es vacia. La nota se crea igual pero
        # el LLM ve que algo raro pasa y puede corregir en el siguiente turn.
        if not text and title == "Nota":
            return _err_tr(
                "note_create needs at least title or text",
                hint="pass title='...' or text='...'", status="needs_user",
            )
        resource = state.register_resource("note", title, metadata={"title": title, "text": text, "tags": args.get("tags"), "created_at": datetime.now().isoformat()})
        out = _ok_tr(note=resource.get("resource"))
        if not text:
            out["warning"] = "note created with empty text"
        return out
    if action in {"task_create", "create_task"}:
        title = str(args.get("title") or args.get("text") or "").strip()
        if not title:
            return _err_tr(
                "task_create requires title or text", status="needs_user",
            )
        due_raw = args.get("due")
        due_iso, due_err = _parse_due_iso(due_raw)
        if due_err:
            return _err_tr(due_err, value=due_raw, status="needs_user")
        resource = state.register_resource(
            "task", title,
            metadata={
                "title": title, "text": args.get("text"),
                "due": due_iso, "status": "open",
                "created_at": datetime.now().isoformat(),
            },
        )
        return _ok_tr(task=resource.get("resource"))
    if action in {"note_list", "notes", "list"}:
        return _ok_tr(notes=_resources_by_kind(state, "note", include_closed=bool(args.get("include_closed", False))))
    if action in {"task_list", "tasks"}:
        return _ok_tr(tasks=_resources_by_kind(state, "task", include_closed=bool(args.get("include_closed", False))))
    if action in {"note_search", "task_search", "search"}:
        kinds = ["note", "task"] if action == "search" else ["note"] if action.startswith("note") else ["task"]
        query = str(args.get("query") or "").strip().casefold()
        if not query:
            return _err_tr("missing query", status="needs_user")
        try:
            limit = max(1, min(int(args.get("limit", 10)), 100))
        except (TypeError, ValueError):
            limit = 10
        # MATCHING ESTRUCTURADO en campos relevantes (title/text/tags), no
        # sobre el JSON entero (que incluye ids, timestamps).
        matches: list[dict[str, Any]] = []
        for r in _resources_by_kind(state, kinds, include_closed=True):
            meta = r.get("metadata") or {}
            haystacks = [
                str(meta.get("title") or ""),
                str(meta.get("text") or ""),
                str(meta.get("tags") or ""),
                str(r.get("label") or ""),
            ]
            if any(query in h.casefold() for h in haystacks):
                matches.append(r)
        return _ok_tr(matches=matches[:limit], count=len(matches), query=query)
    if action == "task_complete":
        task = _find_resource(args, state, "task")
        if not task:
            return _err_tr("task not found", status="needs_user")
        return _update_resource_metadata(state, str(task["id"]), {"status": "completed", "completed_at": datetime.now().isoformat()})
    if action in {"note_delete", "task_delete", "delete"}:
        resource = _find_resource(args, state, ["note", "task"])
        if not resource:
            return _err_tr("note/task not found", status="needs_user")
        return state.mark_cleaned(str(resource["id"]), {"deleted": True})
    if action in {"note_update", "task_update"}:
        resource = _find_resource(args, state, "note" if action.startswith("note") else "task")
        if not resource:
            return _err_tr("note/task not found", status="needs_user")
        updates = {k: args[k] for k in ("title", "text", "content", "due", "tags") if k in args}
        if "content" in updates and "text" not in updates:
            updates["text"] = updates.pop("content")
        # Validar due si vino en el update.
        if "due" in updates:
            due_iso, due_err = _parse_due_iso(updates["due"])
            if due_err:
                return _err_tr(due_err, value=updates["due"], status="needs_user")
            updates["due"] = due_iso
        if not updates:
            return _err_tr("no updatable fields provided", status="needs_user",
                        supported=["title", "text", "content", "due", "tags"])
        return _update_resource_metadata(state, str(resource["id"]), updates)
    return _err_tr(
        "unknown notes_tasks action", action=action,
        valid_actions=[
            "status", "note_create", "task_create", "note_list", "task_list",
            "note_search", "task_search", "search", "task_complete",
            "note_delete", "task_delete", "note_update", "task_update",
        ],
        status="needs_user",
    )
