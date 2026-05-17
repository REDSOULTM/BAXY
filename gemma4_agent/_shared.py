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


__all__ = ["redact_sensitive"]
