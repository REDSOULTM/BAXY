"""Cleanup of a model draft before it is judged: think tags, prompt labels, and a proper name glued to the
next word.
"""

from __future__ import annotations

import re

from .reply_language_checks import _THINK_BLOCK


def _strip_think_tags(text: str) -> str:
    return (
        _THINK_BLOCK.sub("", text)
        .replace("</think>", "")
        .replace("<think>", "")
        .strip()
    )


def _strip_prompt_labels(text: str) -> str:
    cleaned = _strip_think_tags(text)
    # MUSIC1777: a draft that quotes a title carrying its own quotation marks
    # («Op. 125 "Choral"») escaped them as backslash-quote; in prose the
    # backslash is never meant.
    cleaned = re.sub(r"\\+(?=[\"\'\u00ab\u00bb\u201c\u201d\u2018\u2019])", "", cleaned)
    cleaned = re.sub(r"^#+\s*", "", cleaned).strip()
    # SCREEN1807: the whole reply wrapped in one pair of quotation marks
    # («"The screen shows … lines are: '…'."») is the reply, not a quotation.
    for opening, closing in (("\"", "\""), ("\u201c", "\u201d"), ("\u00ab", "\u00bb")):
        if (
            len(cleaned) > 2
            and cleaned.startswith(opening)
            and cleaned.endswith(closing)
            and opening not in cleaned[1:-1]
            and closing not in cleaned[1:-1]
        ):
            cleaned = cleaned[1:-1].strip()
            break
    cleaned = re.sub(
        r"^(?:el )?estado observable(?: es)?:\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()
    return re.sub(
        r"^(?:el )?estado es:?\s*|^the state is:?\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()


def _glued_proper_name(text: str, situation: dict, user_text: str) -> bool:
    names: list[str] = []
    for value in (
        situation.get("target"),
        (situation.get("observed") or {}).get("app")
        if isinstance(situation.get("observed"), dict)
        else None,
        (situation.get("observed") or {}).get("title")
        if isinstance(situation.get("observed"), dict)
        else None,
    ):
        if isinstance(value, str) and len(value) >= 4:
            names.append(value)
    # A capitalized request verb is not a proper name: Find -> finding and
    # Revisa -> revisando are legitimate activity descriptions. Only typed
    # targets and observations identify names for this check.
    folded_tokens = re.findall(r"[a-z0-9]+", text.casefold())
    for name in names:
        stem = name.casefold()
        if any(
            token.startswith(stem) and len(token) > len(stem) + 1
            for token in folded_tokens
        ):
            return True
    return False
