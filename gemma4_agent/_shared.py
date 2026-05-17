"""Cross-module helpers that have no gemma4_agent dependency.

This module exists to break import cycles between :mod:`tools` and
:mod:`domain_tools`. Each of them used to ship its own private copy of
``redact_sensitive`` (commented "CC-105: paralelo a …") because neither
could import from the other without a circular dep. The functions
collected here are pure stdlib + typing and safe to import from
anywhere.
"""
from __future__ import annotations

import re
from typing import Any

# Keys whose value should be replaced with ``***REDACTED***`` when a
# dict is logged or persisted. Case-insensitive substring match.
_SENSITIVE_KEY_RX = re.compile(
    r"(password|token|key|secret|api[_-]?key|auth)",
    re.IGNORECASE,
)


def redact_sensitive(value: Any, depth: int = 0) -> Any:
    """Recursively mask sensitive keys in dicts/lists.

    Any dict key matching :data:`_SENSITIVE_KEY_RX` has its value
    swapped for ``"***REDACTED***"`` (unless the value is ``None`` or
    ``""`` — those stay so logs can tell "absent" from "redacted").
    Lists are walked in place. Recursion is capped at depth 6 to keep
    pathological structures from blowing the stack.

    Used by both ``tools.ToolRegistry`` (for confirmation prompts +
    persisted tool args) and ``domain_tools._hard_gate`` (for the
    PowerShell-bound gate path).
    """
    if depth > 6:
        return value
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():
            if isinstance(k, str) and _SENSITIVE_KEY_RX.search(k):
                out[k] = "***REDACTED***" if v not in (None, "") else v
            else:
                out[k] = redact_sensitive(v, depth + 1)
        return out
    if isinstance(value, list):
        return [redact_sensitive(v, depth + 1) for v in value]
    return value


def hard_gate(
    state: Any,
    *,
    tool: str | None = None,
    action: str,
    args: dict[str, Any],
    reason: str,
    risk: str = "high",
    tool_name: str | None = None,
    routine_context: bool | None = None,
    confirmed_at_create: bool | None = None,
) -> dict[str, Any] | None:
    """Confirmation gate shared by :mod:`tools` and :mod:`domain_tools`.

    Returns ``None`` when the call is authorized, or an error-shaped
    dict (``{"ok": False, ...}``) when confirmation is still needed.

    Two historical call conventions are supported (CC-101 from the
    audit §2.2 unification):

    - ``tool=`` and explicit ``routine_context`` / ``confirmed_at_create``
      kwargs — the way :class:`ToolRegistry` always invoked its method
      version (the dispatcher peeled the flags off ``args`` first).
    - ``tool_name=`` alias for ``tool``; ``routine_context=None`` /
      ``confirmed_at_create=None`` triggering an in-body read from
      ``args`` — the convention used by
      :func:`domain_tools._hard_gate`.

    Either way, ``args`` always has its ``routine_context`` /
    ``confirmed_at_create`` keys stripped before the redacted payload
    is handed to ``state.create_confirmation``.
    """
    name = tool if tool is not None else tool_name
    if not name:
        raise TypeError("hard_gate requires `tool` (or legacy `tool_name`)")
    if bool(args.get("confirmed")):
        return None
    if routine_context is None:
        routine_context = bool(args.get("routine_context"))
    if confirmed_at_create is None:
        confirmed_at_create = bool(args.get("confirmed_at_create"))
    if routine_context:
        if confirmed_at_create:
            return None
        return {
            "ok": False,
            "error": f"{name}.{action} blocked: routine step missing confirmed_at_create",
            "status": "blocked_needs_confirmation",
            "tool": name,
            "action": action,
        }
    safe_args = redact_sensitive(
        {
            **{k: v for k, v in args.items()
              if k not in {"routine_context", "confirmed_at_create"}},
            "confirmed": True,
        }
    )
    pending = state.create_confirmation(name, safe_args, reason=reason, risk=risk)
    return {
        "ok": False,
        "error": f"{name}.{action} requires confirmation; call safety(confirm, id=...) or re-call with confirmed=true",
        "status": "needs_confirmation",
        "verified": False,
        "completion_status": "needs_user_confirmation",
        "confirmation": pending.get("confirmation"),
    }


__all__ = ["redact_sensitive", "hard_gate"]
