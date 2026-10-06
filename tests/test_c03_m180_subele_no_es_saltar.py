"""M180 (2026-10-06, App runs v5b/v5c/v5f): raising or lowering what plays is its volume, never the next song.

- G-w21-t2 «súbele un poco a esa» (the salsa playlist BAXY had just put on) → the decider restated «Pasa a la siguiente
  canción.» → ``media.control`` skipped the song and BAXY said «Está sonando «Me Hace Daño Verte»…» (v5b, v5c, v5f).
- H-w21-t3 «subile un toque» (Charly García playing) → the same «Pasa a la siguiente canción.» skipped it (v5f).

M167 already turned the decider's seek into the level when the level reader reads the whole message; the transport
(``media.control``: play, pause, next, previous) was not covered, so nothing corrected it. The owner's rule (H0027,
M167): «súbele», «bájale», «turn it up» with «un poco», «un toque», «a bit» or nothing asks how much (no default
step); with the amount it is that change. Skipping is only what the person says: «pasa a la siguiente», «ponle
otra», «skip this one».

Rows are quoted with their real text and the history the App lived; every other phrasing is our own.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic import levels
from baxy_mind.semantic.decider import ContextDecision
from baxy_mind.semantic.dialogue import DialogueState

OPERATIONS = tuple(
    json.loads(
        (pathlib.Path(sidecar.__file__).parent / "data" / "decider_catalog.es.v1.json").read_text(encoding="utf-8")
    )["operations"]
)
APPLICATIONS = ("Steam", "Spotify", "Google Chrome", "Discord", "Calculadora", "Bloc de notas")
CONTROL = "media.control"


def _tool(operation: str) -> dict[str, Any]:
    schema = {"type": "object", "properties": {}, "required": [], "additionalProperties": False}
    return {"type": "function", "function": {"name": operation.replace(".", "_"), "canonical_name": operation,
                                             "description": operation, "risk": "read_only", "parameters": schema}}


class _Decider:
    """The model of a whole turn: the decider answers what it is given; every other call is neutral."""

    _native_tool_policy_enabled = False

    def __init__(self, decision: ContextDecision, question: str) -> None:
        self.decision = decision
        self.question = question
        self.asked = 0
        self.formulated: list[tuple[str, tuple[str, ...], tuple[str, ...]]] = []

    def decide_in_context(self, *_a, **_k):
        self.asked += 1
        return self.decision

    def prepare_decision(self, *_a, **_k):
        return None

    def formulate_explicit_clarification_question(self, objective, operations, missing_fields):
        self.formulated.append((objective, operations, missing_fields))
        return self.question

    def clarify_after_turn_failure(self, *_a, **_k):
        return "¿Qué necesitas?"

    def clarify_unresolved_input(self, *_a, **_k):
        return "¿Qué quieres decir?"

    def clarify_missing_referent(self, *_a, **_k):
        return "¿Qué cosa?"

    def public_lookup_requested(self, _text):
        return False

    def operation_is_the_requested_effect(self, *_a, **_k):
        return True

    def _verify_semantic_effect_shape(self, _text):
        return "complete", "one"

    def chat(self, *_a, **_k):
        return "Respuesta.", []

    def compose_user_message(self, *_a, **_k):
        return "Listo."

    def prepare_chat(self, *_a, **_k):
        return None

    def detect_response_language(self, _text):
        return "es"

    def consume_deferred_response_language(self, _text):
        return True, None

    def retire_deferred_response_language(self, _text):
        return None

    def __getattr__(self, name):
        def missing(*_a, **_k):
            raise RuntimeError(f"no {name} here")
        return missing


def _said(*lines: str) -> list[dict[str, str]]:
    """The conversation before the message, user first and alternating."""

    return [{"role": "user" if index % 2 == 0 else "assistant", "content": line} for index, line in enumerate(lines)]


def _turn(before: list[dict[str, str]], text: str, decision: ContextDecision,
          question: str = "¿Cuánto le subo?") -> tuple[dict, _Decider]:
    tools = {name: _tool(name) for name in OPERATIONS}
    model = _Decider(decision, question)
    result = sidecar._prepare_turn_result(
        {"id": "m180", "text": text, "history": [*before, {"role": "user", "content": text}]},
        llm=model, planner_catalog=PlannerCatalog(list(tools.values())), encoder=lambda _t: (),
        tool_by_name=tools, application_names=APPLICATIONS, dialogue_state=DialogueState(),
    )
    return result, model


def _decided(request: str, decision: str = "action", *operations: str) -> ContextDecision:
    return ContextDecision(request, decision, operations, "", ())


NEXT_ES = _decided("Pasa a la siguiente canción.", "action", CONTROL)
NEXT_EN = _decided("Skip to the next song.", "action", CONTROL)
# DEV-G v5f G-w21 as lived.
SALSA = ("pon la playlist de salsa que tengo en spotify",
         "El tema que tiene reproduciendo ahora es Neutro Shorty - Un Consejo.")
# DEV-H v5f H-w21 as lived.
CHARLY = ("che baxy, tirá algún tema de charly garcia de los ochenta, el que sea",
          "Estás escuchando \"Demoliendo Hoteles\" de Charly García, un tema de los ochenta que está sonando ahora "
          "mismo en Spotify.",
          "no no pasalo en youtube que quiero ver el video",
          "No se pudo encontrar el video de «Demoliendo Hoteles» de Charly García en YouTube.")
JAZZ = ("play some jazz on spotify", "Now playing «Take Five» by The Dave Brubeck Quartet on Spotify.")


# ------------------------------------------------------------------ raising or lowering without an amount asks it


@pytest.mark.parametrize(
    ("before", "text", "decision", "question"),
    [
        # The row (DEV-G v5f G-w21-t2), lived history and the App's decision (also v5b, v5c).
        (_said(*SALSA), "súbele un poco a esa", NEXT_ES, "¿Cuánto le subo?"),
        # The same row with its written history.
        (_said(SALSA[0], "Listo, sonando tu playlist de salsa en Spotify."), "súbele un poco a esa", NEXT_ES,
         "¿Cuánto le subo?"),
        # The row (DEV-H v5f H-w21-t3), lived history and the App's decision.
        (_said(*CHARLY), "subile un toque", NEXT_ES, "¿Cuánto le subo?"),
        # Our own words, both languages and both ways.
        (_said(*SALSA), "bájale un toque", NEXT_ES, "¿Cuánto le bajo?"),
        (_said(*SALSA), "súbele un tris", NEXT_ES, "¿Cuánto le subo?"),
        (_said(*JAZZ), "turn it up a bit", NEXT_EN, "How much should I turn it up?"),
        (_said(*JAZZ), "turn this song down a little", NEXT_EN, "How much should I turn it down?"),
        # The decider's «pausa» for «bájale» is no better than its «siguiente».
        (_said(*SALSA), "bájale a esa", _decided("Pausa la canción.", "action", CONTROL), "¿Cuánto le bajo?"),
    ],
)
def test_raising_or_lowering_what_plays_never_skips_it_and_asks_the_amount(
    before, text: str, decision: ContextDecision, question: str,
) -> None:
    result, model = _turn(before, text, decision, question)
    assert result["kind"] == "clarify", result
    assert CONTROL not in (result.get("effectOperations") or []), result
    assert result["intentOperations"] == ["audio.volume.adjust"]
    assert result["question"] == question
    assert model.formulated == [(text, ("audio.volume.adjust",), ("amount",))]


@pytest.mark.parametrize(
    ("before", "text", "decision", "objective"),
    [
        (_said(*SALSA), "súbele 10", NEXT_ES, "sube el volumen en 10"),
        (_said(*CHARLY), "bajale 20 a ese tema", NEXT_ES, "baja el volumen en 20"),
        (_said(*JAZZ), "turn it up by 10", NEXT_EN, "turn the volume up by 10"),
    ],
)
def test_raising_or_lowering_with_an_amount_is_that_volume_change(
    before, text: str, decision: ContextDecision, objective: str,
) -> None:
    result, model = _turn(before, text, decision)
    assert (result["kind"], result["effectOperations"], result["objective"]) == (
        "action", ["audio.volume.adjust"], objective,
    ), result
    assert model.asked == 1


# ------------------------------------------------------------------ what must not change


@pytest.mark.parametrize(
    ("before", "text", "decision"),
    [
        # Skipping said by the person stays the decider's skip.
        (_said(*SALSA), "pasa a la siguiente", NEXT_ES),
        (_said(*SALSA), "ponle otra", NEXT_ES),
        (_said(*CHARLY), "pasá esa, no me gusta", NEXT_ES),
        # DEV-H H-s063, as the App decided it (no conversation before).
        ([], "skip this one, it's rubbish", NEXT_EN),
        (_said(*JAZZ), "next one please", NEXT_EN),
        # The same transport for pausing and resuming (DEV-G G-s035, G-w03-t5).
        ([], "dale pausa a la musica un momentico", _decided("Pausa la música.", "action", CONTROL)),
        (_said(*SALSA), "ya, dale play again", _decided("Reanuda la canción.", "action", CONTROL)),
        # «súbele 10 segundos» says the position, and «sube la canción» may be uploading it: no level read.
        (_said(*SALSA), "súbele 10 segundos", NEXT_ES),
        (_said(*SALSA), "sube la canción", NEXT_ES),
    ],
)
def test_the_transport_said_stays_the_deciders(before, text: str, decision: ContextDecision) -> None:
    result, model = _turn(before, text, decision)
    assert (result["kind"], result["effectOperations"]) == ("action", [CONTROL]), result
    assert model.asked == 1


def test_the_answer_to_baxys_how_much_is_still_the_volume() -> None:
    # M167: «unos 15 nomás» right after «¿Cuánto le subo?» completes that request before the decider is asked.
    before = _said(*SALSA, "súbele un poco a esa", "¿Cuánto le subo?")
    result, model = _turn(before, "unos 15 nomás", NEXT_ES)
    assert (result["kind"], result["effectOperations"], result["objective"]) == (
        "action", ["audio.volume.adjust"], "sube el volumen en 15",
    ), result
    assert model.asked == 0


def test_the_yes_to_baxys_offer_is_still_that_change() -> None:
    # M177: the yes to BAXY's own offer to lower the volume is that change, whatever the decider said.
    before = _said(*SALSA, "está muy fuerte", "¿Te bajo el volumen al 30?")
    result, _ = _turn(before, "sí, dale", NEXT_ES)
    assert result["kind"] == "action", result
    assert CONTROL not in result["effectOperations"], result


def test_the_deciders_volume_question_stands() -> None:
    # DEV-H v5a–v5d H-w21-t3: the decider already asked the volume; nothing replaces its question.
    decision = ContextDecision("Subí un poco el volumen.", "clarify", (), "¿Cuánto le subo?", ())
    result, model = _turn(_said(*CHARLY), "subile un toque", decision, "¿Otra pregunta?")
    assert (result["kind"], result["question"]) == ("clarify", "¿Cuánto le subo?"), result
    assert model.formulated == []


@pytest.mark.parametrize(
    ("text", "level"),
    [
        ("súbele un tris", levels.Level(None, "up", None, None)),
        ("bájale un tris a esa", levels.Level(levels.VOLUME, "down", None, None)),
        ("un tris más", None),
    ],
)
def test_un_tris_is_a_small_amount_said_with_no_number(text: str, level: levels.Level | None) -> None:
    assert levels.read(text) == level
