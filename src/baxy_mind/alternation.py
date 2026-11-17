"""MODX2: a chat template that wants the person's and the model's messages to alternate, read from the template itself.

MOD2 (§4): Ministral-3-8B answered every turn 500 «After the optional system message, conversation roles must alternate
user and assistant roles except for tool calls and results» (the check of its own tokenizer.chat_template), because the
mind writes its notes (a doubt, a check, a server error) as messages of the person: after the person's own, or after a
call's results. Such a template counts the person's messages and the model's replies in words (a reply that calls a tool
and the tool's results are not counted) and raises when two of one side follow each other.

What the template refuses is read from it, never from the model's name: two messages of the person in a row are rendered
(/apply-template), and only if the template refuses them and renders them joined is the conversation joined for it
(``required``). Joined as Mistral's own tokenizer joins them (mistral-common, protocol/instruct/normalize.py,
InstructRequestNormalizer._aggregate_messages: neighbouring messages of one role become one, their texts joined with
«\\n\\n»; consulted 16-11-2026): a message of one side right after another of the same side is added to it; one of the
person after a call's results, where the template wants the model's reply, is added to the last result, so it is read in
the same place and the same order (mistral-common's own order check, validator.py _validate_message_order, lets the person
speak right after a tool's result; only the template forbids it). No word is changed, removed or added.
"""
from __future__ import annotations

from typing import Any, Callable

from .call_format import _refused

JOIN = "\n\n"
SYSTEM = "PROBE-S-7f3a"
FIRST = "PROBE-U-7f3a"
SECOND = "PROBE-W-7f3a"

Render = Callable[[list[dict[str, Any]], list[dict[str, Any]], bool], str]


def _counted(message: dict[str, Any]) -> bool:
    """A message such a template counts: the person's, or the model's in words (not a call, not a result)."""
    role = message.get("role")
    return role == "user" or (role == "assistant" and not message.get("tool_calls"))


def _joined(first: Any, second: Any) -> str:
    return f"{first or ''}{JOIN}{second or ''}" if first and second else str(first or second or "")


def fold(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The conversation with no two counted messages of one side in a row (``_counted``): each such message added to the
    one before it of its side, or, the person's after a call's results, to the last result. The messages given are
    never changed: the joined ones are copies."""
    out: list[dict[str, Any]] = []
    side: str | None = None  # the role of the last counted message
    for message in messages:
        if not isinstance(message, dict) or message.get("role") == "system" or not _counted(message):
            out.append(message)
            continue
        role = message["role"]
        if side == role and isinstance(message.get("content"), str):
            last = out[-1]
            if _counted(last) and last.get("role") == role and isinstance(last.get("content"), str):
                out[-1] = {**last, "content": _joined(last["content"], message["content"])}
                continue
            if role == "user" and last.get("role") == "tool" and isinstance(last.get("content"), str):
                out[-1] = {**last, "content": _joined(last["content"], message["content"])}
                continue
        out.append(message)
        side = role
    return out


def required(render: Render) -> bool:
    """Whether this model's template refuses two messages of the person in a row and renders them joined (``fold``).
    False when it renders them as they are, or refuses both ways (that template wants something else, and the mind keeps
    sending what it sent). What ``render`` raises when the server cannot be reached is raised."""
    two = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": FIRST},
           {"role": "user", "content": SECOND}]
    try:
        render(two, [], True)
        return False
    except Exception as error:  # noqa: BLE001 - a template that raises on it, or a server that refuses it
        if not _refused(error):
            raise
    try:
        joined = render(fold(two), [], True)
    except Exception as error:  # noqa: BLE001 - refused joined as well: not what this template wants
        if not _refused(error):
            raise
        return False
    return FIRST in joined and SECOND in joined
