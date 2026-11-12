"""RUT1 (owner, 2026-11-10; documentacion/RUTINAS.md): the person's routines as the mind sees them.

A routine is kept by the App's baxy.routines (RoutinesHandler): a phrase of the person and steps that are calls of the
catalog or a text to say. Here only form is compared, on the person's own data:

- (RUT7: the turn's note with the routines is gone, as the model's run by name: a routine runs by its whole phrase,
  below, and the fixed orders about the routines are routine_guide's.)
- ``fired``: the person's own shortcut (§5 b, the owner's exception, written as the alarm's acknowledgement is): the whole
  turn, folded and without BAXY's name in front, is exactly the phrase of one active routine. Never part of a longer
  sentence: «¿qué tiempo hace?» with a routine «tiempo» is not it.
- ``steps``: the steps a run receipt gave back, as the calls the mind proposes one by one (each authorized by the kernel
  as any other, its «sí» included) and the texts BAXY says when they all completed.
- ``ordered`` (RUT6, §5 c): a routine kept as an order, the words the person asked with when they saved it. The same
  whole-turn comparison; the turn then is that order, as if the person had just said it: the model reads it and decides
  with its tools, its brakes and its «sí» as for any other request.
"""
from __future__ import annotations

import json
import re
import unicodedata
from typing import Any

# BAXY's name as the ear writes it in front of a request (ring_answer.SAID has the same two).
NAMES = ("baxy", "baxi")

def fold(text: Any) -> str:
    """As LocalRoutineStore.Folded: lower case, no accents, no punctuation, single spaces. RUT9 (REV9 H12): the same
    forms as the store's (NFD and lower case; NFKD and casefold made «Straße» and «strasse» one phrase here and two
    there, and with both kept neither fired)."""
    folded = unicodedata.normalize("NFD", str(text or "")).lower()
    plain = "".join(ch for ch in folded if not unicodedata.combining(ch))
    return unicodedata.normalize("NFC", " ".join(re.findall(r"[^\W_]+", plain)))


def unnamed(text: Any) -> str:
    """The words folded without BAXY's name in front: how a turn and a routine's phrase are compared (RUT9, REV9 H2:
    a phrase kept as «baxy buenas noches» never fired, as the name was taken off the turn only)."""
    words = fold(text).split()
    while words and words[0] in NAMES:
        words = words[1:]
    return " ".join(words)


def _phrase(routine: Any) -> str:
    trigger = routine.get("trigger") if isinstance(routine, dict) else None
    return str(trigger.get("phrase") or "") if isinstance(trigger, dict) else ""


def active(routines: Any) -> list[dict[str, Any]]:
    """The routines a phrase fires: active, with a phrase and a name."""
    return [r for r in routines if isinstance(r, dict) and r.get("active") is True and fold(_phrase(r))
            and str(r.get("name") or "").strip()] if isinstance(routines, list) else []


def _whole(text: str, routines: Any) -> dict[str, Any] | None:
    """The one active routine whose phrase is the whole turn (BAXY's name in front aside), or None. REV11 B-3: a turn
    with «?» or «¿» is a question, not the phrase said («¿Buenas noches?»), as for the fixed orders (RUTINAS.md §5 d),
    unless the phrase kept has it too."""
    said = unnamed(text)
    if not said:
        return None
    asks = "?" in str(text) or "¿" in str(text)
    found = [r for r in active(routines) if unnamed(_phrase(r)) == said
             and (not asks or "?" in _phrase(r) or "¿" in _phrase(r))]
    return found[0] if len(found) == 1 else None


def _order(routine: dict[str, Any]) -> str:
    return str(routine.get("order") or "").strip() if isinstance(routine.get("order"), str) else ""


def fired(text: str, routines: Any) -> str | None:
    """The name of the active routine of steps whose phrase is the whole turn, or None."""
    found = _whole(text, routines)
    return str(found["name"]).strip() if found is not None and not _order(found) else None


def ordered(text: str, routines: Any) -> tuple[str, str, str] | None:
    """(name, phrase, order) of the active routine kept as an order whose phrase is the whole turn, or None."""
    found = _whole(text, routines)
    if found is None or not _order(found):
        return None
    return str(found["name"]).strip(), _phrase(found).strip(), _order(found)


# An object key written without quotes, after «{» or «,» (JavaScript's form): RUT1 held-out cp06.
_BARE_KEY = re.compile(r"([{,]\s*)([A-Za-z_][A-Za-z0-9_]*)\s*:")
# RUT4 (the owner's «pantalla», seed 0 in both profiles): a value written as a bare word, «{active: false, monitor: left}».
# After a quoted key, a word that is not JSON's own (true, false, null) nor a number is that word as a string. Form
# only, and only when the step is not JSON as written.
_BARE_VALUE = re.compile(r'("\s*:\s*)(?!(?:true|false|null)\s*[,}])([A-Za-z_][A-Za-z0-9_.-]*)(\s*[,}])')


def named_steps(arguments: dict[str, Any], wire_to_op: dict[str, str]) -> dict[str, Any]:
    """The model writes a step with the tool's name it calls; the store keeps the catalog's operation. ``wire_to_op``
    holds the tools off in the profile too: the App refuses such a step as that tool's call would be refused."""
    steps = arguments.get("steps")
    if not isinstance(steps, list):
        return arguments
    named = []
    for step in steps:
        text = str(step).strip()
        head = re.match(r"[^\s{]+", text)
        if head and head.group(0) in wire_to_op:
            text = wire_to_op[head.group(0)] + text[head.end():]
        head = re.match(r"[^\s{]+", text)
        rest = text[head.end():].strip() if head else ""
        if head and rest.startswith("{") and not text.casefold().startswith("say:"):
            try:
                json.loads(rest)
            except json.JSONDecodeError:
                quoted = _BARE_KEY.sub(r'\1"\2":', rest)
                for candidate in (quoted, _BARE_VALUE.sub(r'\1"\2"\3', quoted)):
                    try:
                        text = head.group(0) + " " + json.dumps(json.loads(candidate), ensure_ascii=False)
                        break
                    except json.JSONDecodeError:
                        continue
        named.append(text)
    return {**arguments, "steps": named}


def steps(received: str) -> tuple[list[tuple[str, dict[str, Any]]], list[str]] | None:
    """The calls (operation, arguments) and the texts to say of a completed run receipt; None when it is not one."""
    try:
        facts = json.loads(received)
    except (json.JSONDecodeError, TypeError):
        return None
    observed = facts.get("observed") if isinstance(facts, dict) else None
    run = observed.get("run") if isinstance(observed, dict) else None
    given = run.get("steps") if isinstance(run, dict) else None
    if not isinstance(given, list):
        return None
    calls, says = [], []
    for step in given:
        if not isinstance(step, dict):
            return None
        if isinstance(step.get("say"), str):
            says.append(step["say"])
        elif isinstance(step.get("op"), str) and isinstance(step.get("arguments"), dict):
            calls.append((step["op"], step["arguments"]))
        else:
            return None
    return calls, says
