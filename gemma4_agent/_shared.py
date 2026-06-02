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
                # Keep None / "" so logs distinguish "absent" from "redacted".
                # Use `is`/explicit compare instead of `v not in (None, "")`:
                # that membership check raises ValueError on a numpy array value
                # ("truth value ambiguous"), which would crash this safety-path
                # helper (called from hard_gate / confirmation prompts).
                keep_as_is = v is None or (isinstance(v, str) and v == "")
                out[k] = v if keep_as_is else "***REDACTED***"
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
    # Coerción honesta de `confirmed`: si llega como STRING ("false"/"no"/"0"),
    # `bool("false")` daba True (string no-vacío) y abría el gate sin confirmar.
    # Defensa en profundidad: el dispatcher ya coerce, pero los callers directos
    # de domain_tools podrían pasar el raw. (Auditoría 2026-06-01, mismo bug-class
    # que el `state` del mute y el `confirmed` del dispatcher.)
    _conf = args.get("confirmed")
    if isinstance(_conf, str):
        _conf = _conf.strip().lower() not in {"false", "no", "0", "off", ""}
    if bool(_conf):
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


from dataclasses import dataclass


@dataclass
class TurnRequest:
    """In-flight user turn enqueued by either worker (UI or HTTP).

    Was duplicated as ``_TurnRequest`` in :mod:`agent_runner` and
    :mod:`ui.agent_thread` (audit §2.1). The two workers diverge in
    everything ELSE (threading model, output channel, build steps) so
    Sprint 4 only unifies what was byte-identical. Full ``AgentSerialWorker``
    extraction is deferred to Sprint 5.
    """
    text: str
    images: list[str]
    audios: list[str]


def fmt_tool_args(args: Any, max_chars: int = 120) -> str:
    """One-line preview of a tool's args dict, capped at ``max_chars``.

    Identical helper used by both worker `_progress_forwarder` paths.
    """
    import json
    try:
        s = json.dumps(args, ensure_ascii=False)
    except (TypeError, ValueError):
        s = str(args)
    if len(s) > max_chars:
        s = s[: max_chars - 3] + "..."
    return s


# Tool-result builders — by far the most repeated helpers in the codebase.
# Were triplicated as private copies in domain_tools/ops_tools/tools (each
# with the SAME body byte-for-byte). Consolidated here per audit R3 + R4
# foundation: every tool handler in the repo returns dicts shaped like
# ``{"ok": True/False, ...}`` so two single-source-of-truth constructors
# avoid drift if/when a shape detail evolves (e.g. when ToolResult dataclass
# from audit R4 is introduced, only THIS file needs to update).
def _ok(**kwargs: Any) -> dict[str, Any]:
    """Successful tool-result dict: ``{"ok": True, **kwargs}``."""
    return {"ok": True, **kwargs}


def _err(message: str, **kwargs: Any) -> dict[str, Any]:
    """Failed tool-result dict: ``{"ok": False, "error": message, **kwargs}``."""
    return {"ok": False, "error": message, **kwargs}


__all__ = [
    "redact_sensitive", "hard_gate", "TurnRequest", "fmt_tool_args",
    "_ok", "_err",
]
