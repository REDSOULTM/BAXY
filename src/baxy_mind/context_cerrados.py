"""H-ctx «cerrados» (nb-h-ctx-cerrados, 2026-10-25): once a turn is closed, the bodies of its results that can no
longer be used as they are reach the model in short, before the next turn reads them.

Measured on the e2e traces of c3-* and ho6-* (45 runs, 3,088 results): web_fetch (4.2k chars, ~1.4k tokens a page) and
input_visible_controls (2.7k chars, ~1k tokens) are 56 % of every result's characters, and they stay whole in every
later turn until the trim (8 turns, 24k characters or the tokens the prefix leaves) cuts them all at once. A closed
turn's view lists control numbers of a window as it was (the trim's own note says they no longer hold), and the long
text of a page or file was already told in BAXY's words; the person's next turn reads them again (h2 V5E061 «cámbialo,
era el miércoles»: the Notepad's views of turn 1 beside the new ones, 18/18 failed).

What changes, in tool messages of closed turns only: a view («view») keeps its window and focus lines and loses its
controls, with a note of how many; a text longer than TEXT_CAP characters keeps its start and says how many more were
left out («[recortado: N caracteres más…]»); a list longer than LIST_CAP keeps its first items and says how many more.
Never a field that says whether it ran, how it failed or how it was verified (ESSENTIAL), never the facts line that
ends each result, never the person's words nor BAXY's. Once in short a result is not changed again, so a closed turn
changes once: when the turn has just closed, before the history is read into the slot (prefill, where nobody waits),
or at the next turn's start. The fixed prefix (system prompt and tools) is never touched.

Off unless BAXY_RENEW_CTX_MODE names «cerrados» (comma-separated): the mind reads as it did before."""
from __future__ import annotations

import json
import os
from typing import Any

CTX_ENV = "BAXY_RENEW_CTX_MODE"
CLOSED = "cerrados"
CLOSED_VIEW = ("[Vista de un turno anterior: {n} líneas de controles omitidas; sus números ya no valen, mira de nuevo "
               "si hace falta]")
CUT_TEXT = "… [recortado: {n} caracteres más de un turno anterior; se puede volver a leer]"
CUT_LIST = "[recortado: {n} elementos más de un turno anterior]"
TEXT_CAP = 1200
LIST_CAP = 6
ESSENTIAL = ("status", "error", "cause", "reason", "failure", "verification", "effectUncertain", "notVerified")
_MARKS = (CLOSED_VIEW[:24], CUT_TEXT[:14], CUT_LIST[:11])


def on(env: dict[str, str] | None = None) -> bool:
    setting = (env if env is not None else os.environ).get(CTX_ENV, "")
    return CLOSED in {part.strip().lower() for part in setting.split(",")}


def _view(view: str) -> str:
    if CLOSED_VIEW[:24] in view:
        return view
    lines = view.split("\n")
    head = next((i for i, line in enumerate(lines) if line.startswith("Controles")), None)
    if head is None:
        return view
    return "\n".join([*lines[:head], CLOSED_VIEW.format(n=len(lines) - head)])


def _short(node: Any, key: str = "") -> Any:
    if key in ESSENTIAL:
        return node
    if isinstance(node, dict):
        return {k: (_view(v) if k == "view" and isinstance(v, str) else _short(v, k)) for k, v in node.items()}
    if isinstance(node, list):
        if len(node) > LIST_CAP and not (node and isinstance(node[-1], str) and node[-1].startswith(CUT_LIST[:11])):
            return [_short(v) for v in node[:LIST_CAP]] + [CUT_LIST.format(n=len(node) - LIST_CAP)]
        return [_short(v) for v in node]
    if isinstance(node, str) and len(node) > TEXT_CAP and CUT_TEXT[:14] not in node:
        return node[:TEXT_CAP] + CUT_TEXT.format(n=len(node) - TEXT_CAP)
    return node


def clean_closed(conv: list[dict[str, Any]], end: int, facts_mark: str) -> int:
    """The tool messages of ``conv[:end]`` (closed turns) in short, in place. How many changed."""
    changed = 0
    for message in conv[:end]:
        if message.get("role") != "tool":
            continue
        content = str(message.get("content") or "")
        at = content.find(facts_mark)
        body, rest = (content, "") if at < 0 else (content[:at], content[at:])
        try:
            facts = json.loads(body)
        except (json.JSONDecodeError, ValueError):
            continue
        if not isinstance(facts, (dict, list)):
            continue
        shown = _short(facts)
        if shown != facts:
            message["content"] = json.dumps(shown, ensure_ascii=False, separators=(",", ":")) + rest
            changed += 1
    return changed
