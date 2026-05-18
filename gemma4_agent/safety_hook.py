"""Pre-dispatch safety hook for purchase / paid-action attempts.

When safety_enabled, this hook intercepts tool_calls whose args
contain checkout-pattern URLs or paid-action keywords. The hook
returns {"block": True, ...} (the dispatcher refuses the call and
returns a synthetic needs_confirmation result) or {"block": False}
(the call proceeds).

When safety is OFF, the dispatcher still calls the hook and emits
a 'safety_hook_match' trace event with enforced=False so
operators can see when paid-pattern args slipped through. The
call itself proceeds in that case.

Structural detection — operates on args (URLs, action names) but
NEVER on user text or LLM reply text.

Hotfix I 2026-05-17.
"""
from __future__ import annotations

import re
from typing import Any


# URL patterns observed in real checkout / payment flows. Each
# pattern is anchored to the URL structure (host + path
# segment), not free text. Adding a pattern requires a real
# checkout URL example as backing — do NOT speculate.
_CHECKOUT_URL_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"://(www\.)?steampowered\.com/checkout", re.IGNORECASE),
    re.compile(r"://store\.steampowered\.com/checkout", re.IGNORECASE),
    re.compile(r"://(www\.)?epicgames\.com/store/.*/checkout", re.IGNORECASE),
    re.compile(r"://(www\.)?gog\.com/checkout", re.IGNORECASE),
    re.compile(r"://(www\.)?microsoft\.com/.*/checkout", re.IGNORECASE),
    re.compile(r"://(www\.)?paypal\.com/checkoutnow", re.IGNORECASE),
    re.compile(r"://checkout\.stripe\.com/", re.IGNORECASE),
    re.compile(r"://(www\.)?amazon\.com/gp/buy", re.IGNORECASE),
    re.compile(r"://(www\.)?amazon\.[a-z.]+/gp/buy", re.IGNORECASE),
)


# (tool_name, action) pairs that imply money movement regardless
# of args. These come from the schema definitions, NOT user text.
_PAID_ACTION_NAMES: frozenset[tuple[str, str]] = frozenset({
    ("steam", "purchase"),
    ("steam", "buy"),
    ("game_launcher", "purchase"),
    ("browser", "checkout"),
    # browser(action='open', url='...checkout...') is caught by
    # the URL pattern check above, not by action name.
})


def evaluate_tool_call(
    tool_name: str,
    action: str,
    args: dict[str, Any],
) -> dict[str, Any]:
    """Inspect a planned tool_call.

    Returns one of:
      {"block": False}
        The call is safe to dispatch.

      {"block": True, "reason": str, "pattern": str}
        A checkout-pattern URL or paid action was detected. The
        caller decides whether to hard-block (safety_enabled) or
        just warn-and-proceed.
    """
    url = args.get("url") or args.get("href") or ""
    if isinstance(url, str) and url:
        for pat in _CHECKOUT_URL_PATTERNS:
            if pat.search(url):
                return {
                    "block": True,
                    "reason": (
                        "URL matches a known checkout pattern. "
                        "Confirm with user before proceeding."
                    ),
                    "pattern": pat.pattern,
                }

    key = (tool_name, action)
    if key in _PAID_ACTION_NAMES:
        return {
            "block": True,
            "reason": (
                f"{tool_name}.{action} is a paid action. "
                "Confirm with user before proceeding."
            ),
            "pattern": f"action:{tool_name}.{action}",
        }

    return {"block": False}
