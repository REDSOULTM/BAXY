"""M141 (2026-10-03, DEV-G v4o, D58): what the decider wrote reaches the PLANS and the follow-ups too.

DEV-G (iterable) rows of ``window/v4o-devG`` where the decider of the App wrote the data and the turn asked for it:
- G-s040 «open Notepad and put it on the left half of the screen please» → plan app.open + window.snap with the
  decider's {"app": "Notepad", "side": "left"} → «¿Cuál es el nombre o título exacto de la aplicación…?»;
- G-s116 «abrí spotify y ponime algo de jazz tranqui…» → plan app.open + media.play.query with {"app.open":
  "Spotify", "media.play.query": "jazz tranquilo"} → «¿Qué aplicación de jazz tranquilo quieres que abra?».
  M136 carried those values into one operation's fields (``_direct_arguments_result``); a plan's steps were written by
  the planner's own extraction call alone. Now a step takes the decider's values first, and after a failed extraction
  its values are completed with the decider's (a ``window.resolve`` before the decided ``window.snap`` too);
- G-w06-t3 «guárdalo en un archivo que se llame suma.py» after BAXY's ```python block → the decider's ``text`` is that
  code with its line break at the end, which read as code cut open (M118) → «¿Cuál es el código…?»: the decider's
  free text that is BAXY's previous reply in the same words is that reply verbatim.

Diagnosed, not changed here: G-w12-t2 (``note.update`` asks its ``noteId`` on every run since v3d: no read of the note
feeds it — a missing dependency, not a lost value) and G-w05-t3 (the lived history held no result of the match: BAXY
had said it found none, and the decider's text «El partido de River terminó con el resultado.» tells nothing).
"""

from __future__ import annotations

from typing import Any

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind.semantic import dialogue as dialogue_slot

APP_OPEN = {"type": "object", "properties": {"appId": {"type": "string", "x-maxUtf8Bytes": 512}},
            "required": ["appId"], "additionalProperties": False}
SNAP = {"type": "object", "properties": {"side": {"type": "string", "enum": ["left", "right"]},
                                         "windowId": {"type": "string", "maxLength": 36}},
        "required": ["side", "windowId"], "additionalProperties": False}
RESOLVE = {"type": "object", "properties": {
    "applicationName": {"type": "string", "x-maxUtf8Bytes": 256}, "byTitle": {"type": "boolean"},
    "limit": {"type": "integer", "minimum": 1, "maximum": 50}, "offset": {"type": "integer", "minimum": 0},
    "process": {"type": "string", "maxLength": 260}}, "required": [], "additionalProperties": False}
PLAY_QUERY = {"type": "object", "properties": {"provider": {"type": "string", "enum": ["spotify"]},
                                               "query": {"type": "string", "x-maxUtf8Bytes": 1024}},
              "required": ["provider", "query"], "additionalProperties": False}
WRITE_TEXT = {"type": "object", "properties": {
    "expectedSha256": {"type": ["string", "null"], "maxLength": 64},
    "folder": {"type": "string", "enum": ["desktop", "documents", "downloads"]},
    "relativePath": {"type": "string", "x-maxUtf8Bytes": 1024},
    "text": {"type": "string", "x-maxUtf8Bytes": 1048576}}, "required": ["relativePath", "text"],
    "additionalProperties": False}


def _tool(operation: str, schema: dict[str, Any]) -> dict[str, Any]:
    return {"type": "function", "function": {"name": operation.replace(".", "_"), "canonical_name": operation,
                                             "description": f"Leaf {operation}.", "parameters": schema}}


TOOLS = {"app.open": _tool("app.open", APP_OPEN), "window.snap": _tool("window.snap", SNAP),
         "window.resolve": _tool("window.resolve", RESOLVE), "media.play.query": _tool("media.play.query", PLAY_QUERY),
         "filesystem.write.text": _tool("filesystem.write.text", WRITE_TEXT)}


def _plan(said: str, objective: str, effects: tuple[str, ...], decided: dict[str, Any], *, after: bool = False,
          extracted: dict[str, Any] | None = None, history: list[dict[str, str]] | None = None) -> dict[str, Any]:
    """Each literal step of the plan the App asks for, materialized as the plan request does before (or, with
    ``after``, once) the extraction ran."""

    sidecar._remember_decided_arguments(objective, effects, tuple(decided.items()))
    skeleton = sidecar._explicit_plan_skeleton(effects)
    operations = tuple(step["operation"] for step in skeleton["steps"])
    conversation = (history or []) + [{"role": "user", "content": said}]
    got = {}
    for step in skeleton["steps"]:
        if step["argumentsMode"] != "literal":
            continue
        got[step["operation"]] = sidecar._plan_step_decided_arguments(
            step["operation"], operations, objective, TOOLS[step["operation"]], conversation,
            extracted=extracted, after_extraction=after,
        )
    return got


# ------------------------------------------------------------------ 1. plans


def test_g_s040_open_and_snap_takes_the_decider_s_application() -> None:
    said = "open Notepad and put it on the left half of the screen please"
    objective = "Open Notepad and snap it to the left half of the screen."
    got = _plan(said, objective, ("app.open", "window.snap"), {"app": "Notepad", "side": "left"})
    # The opening is the decider's; the window to snap is read by the extraction first (it is no decided effect).
    assert got == {"app.open": {"appId": "Notepad"}, "window.resolve": None}
    # When the extraction could not read it, the window of the snap is the decided application's.
    got = _plan(said, objective, ("app.open", "window.snap"), {"app": "Notepad", "side": "left"}, after=True)
    assert got == {"app.open": {"appId": "Notepad"}, "window.resolve": {"applicationName": "Notepad"}}


def test_g_s116_open_and_play_takes_the_values_keyed_by_operation() -> None:
    said = "abrí spotify y ponime algo de jazz tranqui, que estoy laburando y necesito algo de fondo"
    objective = "Abrí Spotify y pon algo de jazz tranquilo."
    got = _plan(said, objective, ("app.open", "media.play.query"),
                {"app.open": "Spotify", "media.play.query": "jazz tranquilo"})
    assert got == {"app.open": {"appId": "Spotify"},
                   "media.play.query": {"provider": "spotify", "query": "jazz tranquilo"}}


@pytest.mark.parametrize(
    ("said", "objective", "effects", "decided", "expected"),
    [
        # Other words, other language.
        ("abre la calculadora y tirala a la derecha", "Abre Calculadora y colócala en la mitad derecha.",
         ("app.open", "window.snap"), {"appId": "Calculadora", "side": "right"},
         {"app.open": {"appId": "Calculadora"}, "window.resolve": None}),
        ("open spotify and play some lo-fi beats", "Open Spotify and play some lo-fi beats.",
         ("app.open", "media.play.query"), {"app": "Spotify", "query": "lo-fi beats"},
         {"app.open": {"appId": "Spotify"}, "media.play.query": {"provider": "spotify", "query": "lo-fi beats"}}),
    ],
)
def test_variants_of_a_plan_take_the_decider_s_values(said: str, objective: str, effects: tuple[str, ...],
                                                       decided: dict[str, Any], expected: dict[str, Any]) -> None:
    assert _plan(said, objective, effects, decided) == expected


def test_a_plan_never_takes_what_nobody_said_or_what_it_cannot_place() -> None:
    # A name the decider brought that nobody said grounds nothing; the extraction reads the step (and may ask).
    got = _plan("ábrelo y ponlo a la izquierda", "Abre la aplicación y colócala a la izquierda.",
                ("app.open", "window.snap"), {"app": "Notepad", "side": "left"}, after=True)
    assert got == {"app.open": None, "window.resolve": None}
    # Two openings: the decider's values cannot say which step is whose.
    objective = "Abre Spotify y Discord."
    sidecar._remember_decided_arguments(objective, ("app.open", "app.open"), (("app", ["Spotify", "Discord"]),))
    for step in ("app.open",):
        assert sidecar._plan_step_decided_arguments(
            step, ("app.open", "app.open"), objective, TOOLS[step], [{"role": "user", "content": objective}],
        ) is None
    # A list is never one text, whatever its words.
    assert sidecar._decided_value(["Spotify", "Discord"], {"type": "string"}) is None


def test_the_extraction_s_values_are_kept_and_completed() -> None:
    said = "abrí spotify y ponime algo de jazz tranqui"
    objective = "Abrí Spotify y pon algo de jazz tranquilo."
    sidecar._remember_decided_arguments(objective, ("app.open", "media.play.query"),
                                        (("app.open", "Spotify"), ("media.play.query", "jazz tranquilo")))

    def completed(extracted: dict[str, Any]) -> dict[str, Any] | None:
        return sidecar._plan_step_decided_arguments(
            "media.play.query", ("app.open", "media.play.query"), objective, TOOLS["media.play.query"],
            [{"role": "user", "content": said}], extracted=extracted, after_extraction=True,
        )

    # What the extraction left out is the decider's; what it read and grounds stays.
    assert completed({"provider": "spotify"}) == {"provider": "spotify", "query": "jazz tranquilo"}
    assert completed({"query": "algo de jazz"}) == {"provider": "spotify", "query": "algo de jazz"}
    # What it brought that nobody said is the decider's said value instead.
    assert completed({"provider": "spotify", "query": "smooth jazz classics"}) == {
        "provider": "spotify", "query": "jazz tranquilo"}


# ------------------------------------------------------------------ 2. a follow-up that writes BAXY's reply


class _Model:
    """The extraction must never be needed: the decider wrote the content."""

    def extract_direct_arguments(self, *_args: object, **_kwargs: object) -> object:
        raise AssertionError("the decider had the arguments")


def _write(said: str, objective: str, reply: str, decided: dict[str, Any]) -> tuple[dict | None, str]:
    sidecar._remember_decided_arguments(objective, ("filesystem.write.text",), tuple(decided.items()))
    history = [{"role": "user", "content": "ahora hazlo en python"}, {"role": "assistant", "content": reply},
               {"role": "user", "content": said}]
    return sidecar._direct_arguments_result(
        {"operation": "filesystem.write.text", "text": objective, "history": history},
        llm=_Model(), tool=TOOLS["filesystem.write.text"], dialogue_state=dialogue_slot.DialogueState(),
    )


CODE = "def sumar(a, b):\n    return a + b"


def test_g_w06_t3_the_code_baxy_wrote_is_saved_verbatim() -> None:
    arguments, question = _write(
        "guárdalo en un archivo que se llame suma.py",
        "Escribe el código de Python de sumar dos números en un archivo suma.py.",
        f"```python\n{CODE}\n```",
        {"expectedSha256": "no known", "folder": "carpeta de trabajo de BAXY", "relativePath": "suma.py",
         "text": CODE + "\n"},
    )
    assert question == "" and arguments == {"relativePath": "suma.py", "text": CODE}


@pytest.mark.parametrize(
    ("said", "objective", "reply", "decided_text", "path", "expected"),
    [
        ("save that to a file called add.js", "Write the JavaScript code in a file add.js.",
         "Sure:\n```javascript\nfunction add(a, b) {\n  return a + b;\n}\n```",
         "function add(a, b) {\n  return a + b;\n}\n", "add.js", "function add(a, b) {\n  return a + b;\n}"),
        # A reply with no code block is the content whole.
        ("pásalo a un archivo lista.txt", "Guarda la lista en un archivo lista.txt.",
         "- pan\n- leche\n- huevos", "- pan\n- leche\n- huevos", "lista.txt", "- pan\n- leche\n- huevos"),
    ],
)
def test_variants_of_writing_baxy_s_reply(said: str, objective: str, reply: str, decided_text: str, path: str,
                                          expected: str) -> None:
    arguments, question = _write(said, objective, reply, {"relativePath": path, "text": decided_text})
    assert question == "" and arguments == {"relativePath": path, "text": expected}


def test_a_text_that_is_not_baxy_s_reply_is_not_replaced() -> None:
    reply = f"```python\n{CODE}\n```"
    assert sidecar._reply_the_decider_wrote("def restar(a, b):\n    return a - b\n", reply) is None
    assert sidecar._reply_the_decider_wrote(CODE + "\n", reply) == CODE
    # M118 (DEV-F F-w42-t3): a line left open at the end is still a cut value.
    assert sidecar._decided_value("def f(x):\n    if \n", {"type": "string"}) is None
    assert sidecar._decided_value(CODE + "\n", {"type": "string"}) == "def sumar(a, b): return a + b"
