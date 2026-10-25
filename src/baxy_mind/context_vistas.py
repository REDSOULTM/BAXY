"""H-ctx «vistas» (nb-h-ctx-vistas, 2026-10-25): inside the open turn, a look at a window that a newer look of the same
window replaced, and a result repeated identically later in the turn, reach the model once.

Measured on the e2e traces of c3-* and ho6-* (45 runs, 3,088 results): input_visible_controls is 26 % of every result's
characters (2.7k chars, ~1k tokens each, up to 7.6k tokens), and in the CU cases of the practice banks it is looked at
again and again in the same turn (h2 V5E029: 37 superseded looks and 21 identical results in 18 runs, failed 18/18; h2
V5E023 19 superseded, 18/18; E017 16, 8/19). Every older view stays whole until the trim, with control numbers that may
no longer hold, beside the newest one.

Only tool messages of the open turn change; the person's words, BAXY's words, the calls and every facts line («[En este
turno: …]») stay as they were. The fixed prefix (system prompt and tools) is never touched, so its cached slot stays;
the model re-reads only from the first older result changed on (a few hundred tokens: the call and result between two
looks). A result kept in short keeps every field but the view (its window line and focus stay), or, repeated, its
status, error and verification: a failure is never left out, and the newest copy is always whole.

Off unless BAXY_RENEW_CTX names «vistas» (comma-separated): the mind reads as it did before."""
from __future__ import annotations

import json
import os
import re
from typing import Any

CTX_ENV = "BAXY_RENEW_CTX"
VIEWS = "vistas"
# What a superseded view says in place of its controls.
SUPERSEDED_VIEW = ("[Vista sustituida por una más nueva de esta ventana, más abajo: {n} líneas de controles omitidas; "
                   "sus números pueden no valer ya]")
# What an identical result repeated later in the turn says in place of its body.
SAME_RESULT = "[Mismo resultado que el de {tool} más abajo: se muestra entero una sola vez]"
# Fields a result kept in short never loses: whether it ran, how it failed, how it was verified.
ESSENTIAL = ("status", "error", "cause", "reason", "failure", "verification", "effectUncertain", "notVerified")
LOOK_TOOL = "input_visible_controls"
SAME_MIN_CHARS = 200  # a short result repeated costs less than the note that would replace it
_WINDOW = re.compile(r"\bwindow (\d+)\)")


def on(env: dict[str, str] | None = None) -> bool:
    setting = (env if env is not None else os.environ).get(CTX_ENV, "")
    return VIEWS in {part.strip().lower() for part in setting.split(",")}


def _split(content: str, facts: str) -> tuple[str, str]:
    """A tool message as (its body, what follows it: the facts line and any notes)."""
    at = content.find(facts)
    return (content, "") if at < 0 else (content[:at], content[at:])


def _facts_of(body: str) -> dict[str, Any] | None:
    try:
        facts = json.loads(body)
    except (json.JSONDecodeError, ValueError):
        return None
    return facts if isinstance(facts, dict) else None


def _window(facts: dict[str, Any]) -> str | None:
    view = facts.get("view")
    if not isinstance(view, str) or SUPERSEDED_VIEW[:30] in view:
        return None
    found = _WINDOW.search(view.split("\n", 1)[0])
    return found.group(1) if found else None


def _superseded(facts: dict[str, Any]) -> dict[str, Any]:
    lines = str(facts["view"]).split("\n")
    head = next((i for i, line in enumerate(lines) if line.startswith("Controles")), len(lines))
    kept = dict(facts)
    kept["view"] = "\n".join([*lines[:head], SUPERSEDED_VIEW.format(n=len(lines) - head)])
    return kept


def _same(facts: dict[str, Any] | None, tool: str) -> str:
    essential = {k: facts[k] for k in ESSENTIAL if facts and k in facts}
    head = json.dumps(essential, ensure_ascii=False, separators=(",", ":")) + "\n" if essential else ""
    return head + SAME_RESULT.format(tool=tool)


def clean_turn(conv: list[dict[str, Any]], begin: int, facts_mark: str, same_key) -> int:
    """The open turn's earlier results (from ``begin``) that the newest one (``conv[-1]``, a tool message) supersedes or
    repeats, kept in short in place. ``same_key`` is the mind's _result_key (two results are the same without their
    timings and single-use handles). How many changed."""
    newest = conv[-1]
    if newest.get("role") != "tool":
        return 0
    names = {c.get("id"): str((c.get("function") or {}).get("name") or "?")
             for m in conv[begin:] for c in m.get("tool_calls") or []}
    tool = names.get(newest.get("tool_call_id"), "?")
    body, _ = _split(str(newest.get("content") or ""), facts_mark)
    facts = _facts_of(body)
    window = _window(facts) if facts and tool == LOOK_TOOL else None
    key = same_key(body) if len(body) >= SAME_MIN_CHARS else None
    changed = 0
    for message in conv[begin:-1]:
        if message.get("role") != "tool" or names.get(message.get("tool_call_id")) != tool:
            continue
        old_body, rest = _split(str(message.get("content") or ""), facts_mark)
        old = _facts_of(old_body)
        if key is not None and len(old_body) >= SAME_MIN_CHARS and same_key(old_body) == key:
            message["content"] = _same(old, tool) + rest
            changed += 1
        elif window is not None and old is not None and _window(old) == window:
            message["content"] = json.dumps(_superseded(old), ensure_ascii=False, separators=(",", ":")) + rest
            changed += 1
    return changed
