"""Habit Tracker domain tool — extracted from domain_tools.py (R2 sprint
2026-05-28).

Hábitos persistidos como resources en state.json. Frecuencias: daily / weekly
/ monthly / weekdays / custom. Streak basico para 'daily' contando días
consecutivos hacia atrás desde el log más reciente.

Funciones extraídas (1) + 1 constante:
  habit_tracker_tool             (entry, 6 acciones)
  _VALID_HABIT_FREQUENCIES

Helpers desde domain_tools (lazy):
  _resources_by_kind, _find_resource, _update_resource_metadata, _parse_due_iso"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from ._shared import _err, _ok
from .state import AgentState


__all__ = ["habit_tracker_tool", "_VALID_HABIT_FREQUENCIES"]


_VALID_HABIT_FREQUENCIES = {"daily", "weekly", "monthly", "weekdays", "custom"}


def habit_tracker_tool(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    from .domain_tools import (
        _find_resource,
        _parse_due_iso,
        _resources_by_kind,
        _update_resource_metadata,
    )
    action = str(args.get("action") or "list").casefold()
    if action == "status":
        return _ok(habits=len(_resources_by_kind(state, "habit")))
    if action == "list":
        return _ok(habits=_resources_by_kind(state, "habit", include_closed=bool(args.get("include_closed", False))))
    if action == "create":
        name = str(args.get("name") or args.get("title") or "").strip()
        if not name:
            return _err("missing habit name", status="needs_user")
        frequency = str(args.get("frequency") or "daily").lower()
        if frequency not in _VALID_HABIT_FREQUENCIES:
            return _err(
                f"invalid frequency: {frequency!r}",
                valid=sorted(_VALID_HABIT_FREQUENCIES), status="needs_user",
            )
        resource = state.register_resource(
            "habit", name,
            metadata={
                "name": name, "frequency": frequency, "logs": [],
                "created_at": datetime.now().isoformat(timespec="seconds"),
            },
        )
        return _ok(habit=resource.get("resource"))
    if action == "log":
        habit = _find_resource(args, state, "habit")
        if not habit:
            return _err("habit not found", status="needs_user")
        # VALIDACION del campo `at` como ISO antes de persistir; si el LLM
        # pasa "hoy" como string, _parse_due_iso lo rechaza con un mensaje
        # claro en vez de guardarlo y romper stats downstream.
        at_raw = args.get("at")
        if at_raw is None:
            at_iso = datetime.now().isoformat(timespec="seconds")
        else:
            at_iso, err = _parse_due_iso(at_raw)
            if err:
                return _err(err, field="at", value=at_raw, status="needs_user")
            if at_iso is None:
                at_iso = datetime.now().isoformat(timespec="seconds")
        logs = list(habit.setdefault("metadata", {}).get("logs") or [])
        logs.append({
            "at": at_iso,
            "value": args.get("value", True),
            "note": args.get("note"),
        })
        return _update_resource_metadata(state, str(habit["id"]), {"logs": logs})
    if action == "stats":
        habit = _find_resource(args, state, "habit")
        if not habit:
            return _err("habit not found", status="needs_user")
        meta = habit.get("metadata", {}) or {}
        logs = meta.get("logs") or []
        # Calculo de streak basico para "daily": dias consecutivos contando
        # desde la fecha mas reciente hacia atras. Para otras frecuencias no
        # calculamos streak (semantica ambigua).
        streak = 0
        if logs and meta.get("frequency") == "daily":
            try:
                seen_dates: set[str] = set()
                for entry in logs:
                    at_val = str(entry.get("at") or "")
                    if at_val:
                        seen_dates.add(at_val[:10])  # YYYY-MM-DD
                if seen_dates:
                    sorted_dates = sorted(seen_dates, reverse=True)
                    most_recent = sorted_dates[0]
                    today = datetime.now().date().isoformat()
                    cur = datetime.fromisoformat(most_recent).date()
                    today_d = datetime.fromisoformat(today).date()
                    # streak empieza solo si el log mas reciente es de hoy o ayer
                    if (today_d - cur).days <= 1:
                        streak = 1
                        for i in range(1, len(sorted_dates)):
                            next_d = datetime.fromisoformat(sorted_dates[i]).date()
                            if (cur - next_d).days == 1:
                                streak += 1
                                cur = next_d
                            else:
                                break
            except (ValueError, TypeError):
                streak = 0
        return _ok(
            habit=habit, log_count=len(logs),
            last=logs[-1] if logs else None,
            current_streak=streak, frequency=meta.get("frequency"),
        )
    if action == "delete":
        habit = _find_resource(args, state, "habit")
        if not habit:
            return _err("habit not found", status="needs_user")
        return state.mark_cleaned(str(habit["id"]), {"deleted": True})
    return _err(
        "unknown habit_tracker action", action=action,
        valid_actions=["status", "list", "create", "log", "stats", "delete"],
        status="needs_user",
    )
