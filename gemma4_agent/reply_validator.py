"""Post-reply structural validators.

These run after the LLM emits its turn's final reply. If a
structural anti-pattern is detected, the agent injects a
corrective system message into self.history so the NEXT turn's
LLM sees both its previous mistake and the correction note in
the same context window — the deferred-correction path
(Gemma4Agent has no _regen_reply method, building one is out of
scope for this hotfix).

The validators NEVER match user text — only the shape of the
LLM's own reply and the structural tool_call activity this turn.

Hotfix I 2026-05-17.
"""
from __future__ import annotations

import re
from typing import Any


# 'Listo' is the Spanish marker the fast_action prompt teaches
# the LLM to use as a POST-TOOL ack template. The structural
# anti-pattern is "ack template emitted on a turn where no tool
# ran" — the model defaulted to the template even though it
# shouldn't have. We detect the specific phrase the prompt
# teaches, NOT a generic ack across all languages.
_LISTO_PATTERN = re.compile(
    r"^\s*listo(\b|[,.!])",
    re.IGNORECASE,
)


def _result_of(call: Any) -> dict[str, Any]:
    """Read .result from a ToolEvent or a dict — tests use dicts,
    production code uses dataclasses."""
    if isinstance(call, dict):
        return call.get("result") or {}
    r = getattr(call, "result", None)
    return r if isinstance(r, dict) else {}


def _is_successful_call(call: Any) -> bool:
    """Mirror of agent._is_unverified_result inverted; duplicated
    here so reply_validator can stay decoupled from agent.py."""
    r = _result_of(call)
    if r.get("ok") is False:
        return False
    if r.get("verified") is False:
        return False
    status = str(r.get("status") or "").casefold()
    if status in {"failed", "needs_verification", "attempted", "needs_confirmation"}:
        return False
    return True


def is_listo_on_no_tool_turn(
    reply_text: str,
    tool_calls_this_turn: list[Any],
) -> bool:
    """True iff the reply starts with 'Listo' AND no tool ran
    successfully this turn.

    'Listo' is the template the fast_action prompt teaches for
    POST-TOOL acks. Emitting it without a tool is the anti-pattern
    Bug B caught. The fix in B was prompt-level; this is the
    structural backstop.
    """
    if not reply_text or not _LISTO_PATTERN.match(reply_text):
        return False
    successful = [c for c in tool_calls_this_turn if _is_successful_call(c)]
    return not successful


LISTO_REGEN_HINT = (
    "Your previous reply started with 'Listo' but no tool ran "
    "in this turn. 'Listo' is reserved for post-tool acks. "
    "Rewrite your reply naturally — for social acks like a "
    "thank-you, use 'de nada', 'no hay de qué', or the equivalent "
    "in the user's language."
)
