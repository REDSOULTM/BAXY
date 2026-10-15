"""What a person asks of a chat client that no typed operation serves: reading the last thing written to them, and
leaving the voice call they are in.

Estabilización, imprescindibles de mensajería (dueño 2026-10-10, decisión 4). Both are a mission on the application the
person names (``semantic.missions``): the chat is gone to and read from its view, the call is left by pressing the
control that leaves it. The words are data (data/conversation_acts.v1.json); no application is named here, so another
chat client is served by the same reading.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .normalize import fold

_DATA = Path(__file__).resolve().parent.parent / "data" / "conversation_acts.v1.json"
_EDGES = " .,;:!?¿¡«»\"'“”‘’"


@lru_cache(maxsize=1)
def data() -> dict:
    return json.loads(_DATA.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _last_written_patterns() -> tuple[re.Pattern[str], ...]:
    return tuple(re.compile(pattern) for pattern in data()["lastWritten"]["patterns"])


@lru_cache(maxsize=1)
def _leave_call_patterns() -> tuple[re.Pattern[str], ...]:
    return tuple(re.compile(pattern) for pattern in data()["leaveCall"]["patterns"])


@dataclass(frozen=True)
class LastWritten:
    """The chat a last-written question goes to and, when the question says it, who wrote (folded words)."""

    chat: str
    author: str | None


def last_written(clause: object) -> LastWritten | None:
    """«qué me escribió Ron92» → chat and author «ron92»; «lo último que me escribieron en Música» → chat «musica», no
    author; None for anything else (a message to send, «el PDF que me mandó el banco»)."""

    said = fold(clause).strip(_EDGES)
    for pattern in _last_written_patterns():
        found = pattern.match(said)
        if found is None:
            continue
        groups = found.groupdict()
        author = (groups.get("author") or "").strip(_EDGES) or None
        chat = (groups.get("chat") or "").strip(_EDGES) or author
        if chat:
            return LastWritten(chat, author)
    return None


def leaves_the_call(clause: object) -> bool:
    """«salí del canal de voz», «colgá», «leave the voice channel»: the person leaves the call they are in."""

    said = fold(clause).strip(_EDGES)
    return any(pattern.match(said) is not None for pattern in _leave_call_patterns())


def leave_call_labels() -> tuple[str, ...]:
    """The names an application gives the control that leaves a call, the goal's first."""

    return tuple(data()["leaveCall"]["labels"])


def leave_call_goal() -> str:
    """The sub-goal of leaving the call, as semantic.missions writes it: a click on the goal's label (folded)."""

    return f"hacer clic en {fold(leave_call_labels()[0])}"


def last_written_by(author: str, entries: list[str]) -> tuple[str, str] | None:
    """The last entry of a conversation, in the order the window shows them, written by ``author``: an entry that
    names its author first and then what was written («Ron92 , hola , 12:40 p. m.», the way a chat's accessible tree
    names a message), as (text, time); time is "" when the entry gives none. None when no entry is so."""

    separator = re.compile(data()["lastWritten"]["authorSeparator"])
    wanted = fold(author)
    found: tuple[str, str] | None = None
    for entry in entries:
        parts = [part.strip() for part in separator.split(str(entry or ""))]
        if len(parts) < 2 or not parts[1]:
            continue
        head = fold(parts[0])
        # The author may carry a tag after the name («Ron92 Etiqueta del servidor: DEMO»), never another name first.
        if head != wanted and not head.startswith(wanted + " "):
            continue
        text = " , ".join(parts[1:-1]) if len(parts) > 2 else parts[1]
        found = (text, parts[-1] if len(parts) > 2 else "")
    return found


def has_written_entries(entries: list[str]) -> bool:
    """Some entry names an author and what was written (the window showed a conversation at all)."""

    separator = re.compile(data()["lastWritten"]["authorSeparator"])
    return any(len(separator.split(str(entry or ""))) >= 3 for entry in entries)
