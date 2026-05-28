"""Local calendar (ICS) domain tool — extracted from domain_tools.py (R2 sprint
2026-05-27).

Calendario LOCAL — eventos persistidos como resources en state.json. Import/
export ICS (RFC 5545: line-folding, DATE-TIME floating/UTC/TZID). No habla con
ningún Google Calendar ni Outlook (offline-first + privacidad).

Funciones extraídas (9):
  local_calendar_tool                (entry, 7 acciones)
  _calendar_event_update
  _calendar_ics_import
  _ics_parse_events                  (line-folding compatible)
  _ics_unescape
  _ics_normalize_datetime
  _calendar_export_path
  _events_to_ics                     (genera ICS válido con escapes)
  _ics_time / _ics_escape

Helpers desde domain_tools (lazy):
  _resources_by_kind, _find_resource, _update_resource_metadata, _parse_due_iso

Mock-friendly: state.* y filesystem (Path.write_text) son los puntos de patch."""
from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ._shared import _err, _ok
from .tool_result import ToolResult
from .state import AgentState


__all__ = [
    "local_calendar_tool",
    "_calendar_event_update",
    "_calendar_ics_import",
    "_ics_parse_events",
    "_ics_unescape",
    "_ics_normalize_datetime",
    "_calendar_export_path",
    "_events_to_ics",
    "_ics_time",
    "_ics_escape",
]


# R4 sprint 2026-05-28: handler migrado a ToolResult con .to_dict().
def _ok_tr(**kw):
    return ToolResult.ok_result(**kw).to_dict()


def _err_tr(msg, **kw):
    return ToolResult.err(msg, **kw).to_dict()


def local_calendar_tool(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    from .domain_tools_helpers import (
        _find_resource,
        _parse_due_iso,
        _resources_by_kind,
    )
    action = str(args.get("action") or "list").casefold()
    if action == "status":
        return _ok_tr(local_state=True, event_count=len(_resources_by_kind(state, "calendar_event")))
    if action in {"event_list", "list"}:
        return _ok_tr(events=_resources_by_kind(state, "calendar_event", include_closed=bool(args.get("include_closed", False))))
    if action == "event_create":
        title = str(args.get("title") or "").strip()
        if not title:
            return _err_tr("event_create requires title", status="needs_user")
        # VALIDACION start/end como ISO. Antes acepta cualquier string lo que
        # rompe ics_export y comparaciones temporales downstream.
        start_raw = args.get("start") or args.get("due")
        if start_raw is None:
            start_iso = datetime.now().isoformat(timespec="seconds")
        else:
            start_iso, err = _parse_due_iso(start_raw)
            if err:
                return _err_tr(err, field="start", value=start_raw, status="needs_user")
            if start_iso is None:
                start_iso = datetime.now().isoformat(timespec="seconds")
        end_raw = args.get("end")
        end_iso: str | None
        if end_raw:
            end_iso, err = _parse_due_iso(end_raw)
            if err:
                return _err_tr(err, field="end", value=end_raw, status="needs_user")
        else:
            end_iso = None
        # SANITY: end debe ser >= start si ambos estan presentes.
        if end_iso:
            try:
                if datetime.fromisoformat(end_iso) < datetime.fromisoformat(start_iso):
                    return _err_tr(
                        "event end is before start",
                        start=start_iso, end=end_iso, status="needs_user",
                    )
            except ValueError:
                pass
        resource = state.register_resource(
            "calendar_event", title,
            metadata={
                "title": title, "start": start_iso, "end": end_iso,
                "location": args.get("location"), "notes": args.get("notes"),
                "created_at": datetime.now().isoformat(timespec="seconds"),
            },
        )
        return _ok_tr(event=resource.get("resource"))
    if action in {"event_delete", "delete"}:
        event = _find_resource(args, state, "calendar_event")
        if not event:
            return _err_tr("event not found", status="needs_user")
        return state.mark_cleaned(str(event["id"]), {"deleted": True})
    if action == "ics_export":
        events = _resources_by_kind(state, "calendar_event")
        if not events:
            return _err_tr("no events to export", status="needs_user")
        path = _calendar_export_path(args, state)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return _err_tr("cannot create export directory", path=str(path.parent), reason=str(exc))
        body = _events_to_ics(events)
        try:
            path.write_text(body, encoding="utf-8")
        except (PermissionError, OSError) as exc:
            return _err_tr("ics write failed", path=str(path), reason=str(exc),
                        status="needs_user" if isinstance(exc, PermissionError) else "failed")
        try:
            size = path.stat().st_size
        except OSError:
            size = -1
        return _ok_tr(path=str(path.resolve()), events=len(events), bytes=size, verified=size > 0)
    if action == "event_update":
        return _calendar_event_update(args, state)
    if action == "ics_import":
        return _calendar_ics_import(args, state)
    return _err_tr(
        "unknown local_calendar action", action=action,
        valid_actions=[
            "status", "event_list", "event_create", "event_delete",
            "event_update", "ics_export", "ics_import",
        ],
        status="needs_user",
    )


def _calendar_event_update(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    from .domain_tools_helpers import _find_resource, _update_resource_metadata
    event = _find_resource(args, state, "calendar_event")
    if not event:
        return _err_tr("event not found")
    updates: dict[str, Any] = {}
    for key in ("title", "start", "end", "location", "notes"):
        if key in args and args[key] is not None:
            updates[key] = args[key]
    if not updates:
        return _err_tr("no updatable fields provided", supported=["title", "start", "end", "location", "notes"])
    if "title" in updates:
        # CC-102: label patch atómico.
        state.update_resource(str(event["id"]), label=str(updates["title"]))
    return _update_resource_metadata(state, str(event["id"]), updates)


def _calendar_ics_import(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    path_raw = str(args.get("path") or args.get("file") or "").strip()
    text = str(args.get("content") or args.get("ics") or "")
    if path_raw:
        p = Path(path_raw).expanduser()
        if not p.is_file():
            return _err_tr("ICS file not found", path=str(p))
        text = p.read_text(encoding="utf-8", errors="replace")
    if not text.strip():
        return _err_tr("no ICS content provided (pass path or content)")
    events_parsed = _ics_parse_events(text)
    if not events_parsed:
        return _err_tr("no VEVENT blocks found in input")
    created = []
    for evt in events_parsed:
        title = evt.get("summary") or "Evento"
        resource = state.register_resource(
            "calendar_event",
            title,
            metadata={
                "title": title,
                "start": evt.get("dtstart") or "",
                "end": evt.get("dtend") or evt.get("dtstart") or "",
                "location": evt.get("location"),
                "notes": evt.get("description"),
                "uid": evt.get("uid"),
                "imported_from": path_raw or "<inline>",
            },
        )
        created.append(resource.get("resource"))
    return _ok_tr(imported=len(created), events=created[:50], total_parsed=len(events_parsed))


def _ics_parse_events(text: str) -> list[dict[str, Any]]:
    """Parse ICS into a flat list of {uid, summary, dtstart, dtend, location, description}.

    Handles line folding (CRLF + space/tab continues the previous line) and the three
    DATE-TIME forms in RFC 5545: floating, UTC (Z suffix), and TZID-prefixed.
    Property parameters (between ; and :) are dropped except for TZID which is
    preserved as a separate hint.
    """
    # Step 1: unfold continuation lines.
    raw_lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    unfolded: list[str] = []
    for line in raw_lines:
        if unfolded and (line.startswith(" ") or line.startswith("\t")):
            unfolded[-1] += line[1:]
        else:
            unfolded.append(line)

    events: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in unfolded:
        stripped = line.strip()
        if not stripped:
            continue
        upper = stripped.upper()
        if upper == "BEGIN:VEVENT":
            current = {}
            continue
        if upper == "END:VEVENT":
            if current is not None:
                events.append(current)
            current = None
            continue
        if current is None:
            continue
        # Property name is everything before the first ':' or ';' (params).
        # Examples:
        #  DTSTART:20251231T230000Z
        #  DTSTART;TZID=America/New_York:20251231T180000
        #  SUMMARY:Some text with \\n escapes
        sep = stripped.find(":")
        if sep < 0:
            continue
        head, value = stripped[:sep], stripped[sep + 1:]
        name = head.split(";", 1)[0].upper()
        value = _ics_unescape(value)
        if name == "UID":
            current["uid"] = value
        elif name == "SUMMARY":
            current["summary"] = value
        elif name == "DESCRIPTION":
            current["description"] = value
        elif name == "LOCATION":
            current["location"] = value
        elif name == "DTSTART":
            current["dtstart"] = _ics_normalize_datetime(value)
        elif name == "DTEND":
            current["dtend"] = _ics_normalize_datetime(value)
        elif name == "DTSTAMP":
            current["dtstamp"] = _ics_normalize_datetime(value)
    return events


def _ics_unescape(text: str) -> str:
    return text.replace("\\,", ",").replace("\\;", ";").replace("\\n", "\n").replace("\\N", "\n").replace("\\\\", "\\")


def _ics_normalize_datetime(value: str) -> str:
    """Convert an ICS DATE-TIME to an ISO-8601 string when possible.

    - 20251231T230000Z  -> 2025-12-31T23:00:00+00:00
    - 20251231T230000   -> 2025-12-31T23:00:00 (floating)
    - 20251231          -> 2025-12-31
    """
    v = value.strip()
    if not v:
        return ""
    # YYYYMMDDTHHMMSSZ -> ISO UTC.
    if len(v) == 16 and v.endswith("Z") and v[8] == "T":
        try:
            dt = datetime.strptime(v[:-1], "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)
            return dt.isoformat()
        except ValueError:
            return v
    # YYYYMMDDTHHMMSS -> ISO floating.
    if len(v) == 15 and v[8] == "T":
        try:
            return datetime.strptime(v, "%Y%m%dT%H%M%S").isoformat()
        except ValueError:
            return v
    # YYYYMMDD -> ISO date.
    if len(v) == 8 and v.isdigit():
        try:
            return datetime.strptime(v, "%Y%m%d").date().isoformat()
        except ValueError:
            return v
    return v


def _calendar_export_path(args: dict[str, Any], state: AgentState) -> Path:
    raw = str(args.get("path") or "").strip()
    if raw:
        path = Path(raw).expanduser()
    else:
        path = state.path.parent / "generated" / f"calendar_{time.strftime('%Y%m%d_%H%M%S')}.ics"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _events_to_ics(events: list[dict[str, Any]]) -> str:
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Gemma4Agent//Local Calendar//ES"]
    for event in events:
        meta = event.get("metadata", {})
        uid = event.get("id", f"evt_{time.time()}")
        title = str(meta.get("title") or event.get("label") or "Evento")
        start = _ics_time(str(meta.get("start") or datetime.now().isoformat()))
        end = _ics_time(str(meta.get("end") or meta.get("start") or datetime.now().isoformat()))
        lines.extend([
            "BEGIN:VEVENT",
            f"UID:{uid}@gemma4-agent",
            f"DTSTAMP:{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
            f"DTSTART:{start}",
            f"DTEND:{end}",
            f"SUMMARY:{_ics_escape(title)}",
        ])
        if meta.get("location"):
            lines.append(f"LOCATION:{_ics_escape(str(meta['location']))}")
        if meta.get("notes"):
            lines.append(f"DESCRIPTION:{_ics_escape(str(meta['notes']))}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def _ics_time(raw: str) -> str:
    try:
        value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        value = datetime.now()
    return value.strftime("%Y%m%dT%H%M%S")


def _ics_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")
