"""M167 (2026-10-05, App runs v4y): the answer to the amount BAXY just asked completes that same request, and raising or
lowering what plays is its volume.

- I-w15-t3 «unos 15 nomás» right after BAXY asked «¿Cuánto le subo?» → the decider moved the song 15 seconds on
  (``media.seek.relative``). BAXY asked about the volume; the amount answers it (``levels.answered_level_request``,
  read before the decider as M110 reads the length that answers «how long?»). An exception to D58: the question was
  BAXY's own.
- G-w21-t2 «súbele un poco a esa» (the salsa playlist playing) → restated «Adelanta un poco la canción.» and asked
  «¿Cuántos segundos la adelanto?». «súbele … a esa» is the volume (``levels.read`` now reads what plays as the dative
  of «súbele»/«bájale»); with no amount only the amount is asked (owner rule H0027, no default step).
- G-w21-t3 «subile 10, con eso ya me sirve» after that question → seek. «subir/bajar» is the level, never the
  position: with the decider's seek and the person's words a level change, the change is the level's.
- D-w18-t2 «can you bajarle un poco» → «¿Cuántos segundos retrocedo?» (the same misreading), so D-w18-t3 «like 15»
  answered a question about seconds and was a seek. With t2 asking the volume, «like 15» is the volume lowered by 15;
  a bare amount that answers a question about seconds stays a seek.
- I-w34-t2 «25» after «How much should I lower it?» → lowered by 25, as the existing Tanda 8 rule reads it
  (``levels.answers_with_amount``: «how much» asks an amount, «to what level» a level). No owner decision makes it a
  level; the written history's «down to what level?» sets it at 25.

Rows are quoted with their real text and history; every other phrasing is our own.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind import effect_intent
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
        return "¿Cuántos segundos la adelanto?"

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
        {"id": "m167", "text": text, "history": [*before, {"role": "user", "content": text}]},
        llm=model, planner_catalog=PlannerCatalog(list(tools.values())), encoder=lambda _t: (),
        tool_by_name=tools, application_names=APPLICATIONS, dialogue_state=DialogueState(),
    )
    return result, model


def _decided(request: str, decision: str = "action", *operations: str) -> ContextDecision:
    return ContextDecision(request, decision, operations, "", ())


def _evidence(objective: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    read = effect_intent.resolve_explicit_effects(objective, OPERATIONS)
    assert read is not None, objective
    return read.operations, read.evidence


SEEK = "media.seek.relative"
ROCK = ("oye baxy, pues, ponme la playlist de rock de los ochenta en spotify",
        "El último tema reproduciéndose es \"Welcome To My Crib\" de Randy Nota Loca.")
SALSA = ("pon la playlist de salsa que tengo en spotify",
         "He encontrado la canción \"Virgen\" de Adolescent's Orquesta que está reproduciéndose en tu lista de "
         "reproducción de salsa en Spotify.")
LOFI = ("ok so like ponme la playlist de lofi para estudiar en spotify",
        "La pista «Moonloop - A Place to Stay» se está reproduciendo en Spotify.")
TELLY = "the telly's blaring in the next room as it is, bring the volume down on here"
JAZZ = ("play some jazz on spotify", "Now playing «Take Five» by The Dave Brubeck Quartet on Spotify.")


# ------------------------------------------------------------------ the answer to BAXY's «¿cuánto le subo?»


@pytest.mark.parametrize(
    ("before", "text", "decision", "objective", "evidence"),
    [
        # The row (DEV-I v4y I-w15-t3), lived history and the App's decision.
        (_said(*ROCK, "súbele un poco más, porfa", "¿Cuánto le subo?"), "unos 15 nomás",
         _decided("Adelanta 15 segundos la canción.", "action", SEEK), "sube el volumen en 15", "volumen en 15"),
        # The same row with its written history.
        (_said(ROCK[0], "Va, puse rock de los 80 en Spotify.", "súbele un poco más, porfa",
               "¿Cuánto quieres que le suba?"), "unos 15 nomás",
         _decided("Adelanta 15 segundos la canción.", "action", SEEK), "sube el volumen en 15", "volumen en 15"),
        # DEV-G v4y G-w21-t3 and DEV-D v4y D-w18-t3 with the question their written history asks.
        (_said(*SALSA, "súbele un poco a esa", "¿Cuánto le subo?"), "subile 10, con eso ya me sirve",
         _decided("Adelanta 10 segundos la canción.", "action", SEEK), "sube el volumen en 10", "volumen en 10"),
        (_said(*LOFI, "can you bajarle un poco", "¿Cuánto le bajo?"), "like 15",
         _decided("Retrocede 15 segundos la canción.", "action", SEEK), "baja el volumen en 15", "volumen en 15"),
        # Our own words: another hedge, the other language.
        (_said(*SALSA, "bájale un toque", "¿Cuánto le bajo?"), "unos 20 más o menos",
         _decided("Retrocede 20 segundos la canción.", "action", SEEK), "baja el volumen en 20", "volumen en 20"),
        (_said(*JAZZ, "turn it up a bit", "How much should I turn it up?"), "like 10, that'll do",
         _decided("Skip ahead 10 seconds in the song.", "action", SEEK), "sube el volumen en 10", "volumen en 10"),
    ],
)
def test_the_amount_that_answers_how_much_is_that_volume_change(
    before, text: str, decision: ContextDecision, objective: str, evidence: str,
) -> None:
    result, model = _turn(before, text, decision)
    assert (result["kind"], result["effectOperations"]) == ("action", ["audio.volume.adjust"]), result
    assert result["objective"] == objective
    assert _evidence(objective) == (("audio.volume.adjust",), (evidence,))
    assert model.asked == 0


@pytest.mark.parametrize(
    ("question", "operation", "objective"),
    [
        # The row (DEV-I v4y I-w34-t2): «how much» asks an amount (Tanda 8), as the App did.
        ("How much should I lower it?", "audio.volume.adjust", "baja el volumen en 25"),
        # Its written history asks a level: where it ends.
        ("Sure, down to what level?", "audio.volume", "pon el volumen al 25"),
        ("¿A cuánto lo bajo?", "audio.volume", "pon el volumen al 25"),
    ],
)
def test_the_question_says_whether_the_number_is_an_amount_or_a_level(
    question: str, operation: str, objective: str,
) -> None:
    result, model = _turn(_said(TELLY, question), "25", _decided("Lower the volume by 25.", "action",
                                                                 "audio.volume.adjust"))
    assert (result["kind"], result["effectOperations"], result["objective"]) == ("action", [operation], objective)
    assert model.asked == 0


def test_the_brightness_asked_about_keeps_its_setting() -> None:
    before = _said("¿qué brillo tiene la pantalla?", "El brillo está en 70.", "bájale un poco", "¿Cuánto le bajo?")
    result, _ = _turn(before, "20", _decided("Retrocede 20 segundos.", "action", SEEK))
    assert (result["kind"], result["effectOperations"]) == ("action", ["system.settings.adjust"]), result
    assert result["objective"] == "baja el brillo en 20"


# ------------------------------------------------------------------ «súbele un poco a esa» is the volume


@pytest.mark.parametrize(
    ("before", "text", "decision", "question"),
    [
        # The row (DEV-G v4y G-w21-t2), lived history and the App's decision.
        (_said(*SALSA), "súbele un poco a esa", _decided("Adelanta un poco la canción.", "clarify"),
         "¿Cuánto le subo?"),
        # DEV-D v4y D-w18-t2.
        (_said(*LOFI), "can you bajarle un poco", _decided("Retrocede la canción.", "clarify"), "¿Cuánto le bajo?"),
        # Our own words, both languages.
        (_said(*SALSA), "bájale un poquito a la canción", _decided("Retrocede un poco la canción.", "clarify"),
         "¿Cuánto le bajo?"),
        (_said(*JAZZ), "turn this song up a bit", _decided("Skip ahead a bit in the song.", "clarify"),
         "How much should I turn it up?"),
        (_said(*JAZZ), "turn this song up a bit", _decided("Skip ahead in the song.", "action", SEEK),
         "How much should I turn it up?"),
    ],
)
def test_raising_what_plays_without_an_amount_asks_the_volume_amount(
    before, text: str, decision: ContextDecision, question: str,
) -> None:
    result, model = _turn(before, text, decision, question)
    assert result["kind"] == "clarify", result
    assert result["intentOperations"] == ["audio.volume.adjust"]
    assert result["question"] == question
    assert model.formulated == [(text, ("audio.volume.adjust",), ("amount",))]


@pytest.mark.parametrize(
    ("before", "text", "decision", "objective"),
    [
        # The row (DEV-G v4y G-w21-t3) as lived: BAXY had asked about seconds; «subile 10» is still the volume.
        (_said(*SALSA, "súbele un poco a esa", "¿Cuántos segundos la adelanto?"), "subile 10, con eso ya me sirve",
         _decided("Adelanta 10 segundos la canción.", "action", SEEK), "sube el volumen en 10"),
        # Our own words, both languages.
        (_said(*SALSA), "bájale 10 a esta rola", _decided("Retrocede 10 segundos la canción.", "action", SEEK),
         "baja el volumen en 10"),
        (_said(*JAZZ), "turn the track down 10", _decided("Rewind the track 10 seconds.", "action", SEEK),
         "baja el volumen en 10"),
    ],
)
def test_raising_or_lowering_with_an_amount_is_the_volume_not_the_position(
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
        # Moving what plays is the position.
        (_said(*SALSA), "adelántala 15", _decided("Adelanta 15 segundos la canción.", "action", SEEK)),
        (_said(*JAZZ), "skip ahead 15 seconds", _decided("Skip ahead 15 seconds.", "action", SEEK)),
        # A bare amount that answers BAXY's question about seconds is the seek it asked (DEV-D v4y D-w18-t3 as lived).
        (_said(*SALSA, "adelántala un poco", "¿Cuántos segundos la adelanto?"), "15",
         _decided("Adelanta 15 segundos la canción.", "action", SEEK)),
        (_said(*LOFI, "can you bajarle un poco", "¿Cuántos segundos retrocedo?"), "like 15",
         _decided("Retrocede 15 segundos la canción.", "action", SEEK)),
        # «súbele 10 segundos» says the position.
        (_said(*SALSA), "súbele 10 segundos", _decided("Adelanta 10 segundos la canción.", "action", SEEK)),
    ],
)
def test_the_position_stays_the_deciders(before, text: str, decision: ContextDecision) -> None:
    result, model = _turn(before, text, decision)
    assert (result["kind"], result["effectOperations"]) == ("action", [SEEK]), result
    assert model.asked == 1


@pytest.mark.parametrize(
    ("before", "text", "decision"),
    [
        # «unos 15» with no question of BAXY's before it is the decider's, as today.
        (_said(*SALSA), "unos 15 nomás", _decided("Adelanta 15 segundos la canción.", "action", SEEK)),
        (_said(*SALSA), "unos 15", _decided("", "talk")),
        # The volume of one application keeps its own completion and the decider (AUDIO1787).
        (_said("súbele a spotify", "¿Cuánto le subo?"), "20",
         _decided("Sube el volumen de Spotify en 20.", "action", "audio.app.volume.adjust")),
        # M112 (DEV-F v4d w52-t2): «bájalo a 30» after the battery was read is the decider's limit.
        (_said("oiga baxy, ¿cuánta pila le queda a este computador?",
               "El computador tiene el 100% de carga en la batería y no está cargando."),
         "sí, dale, bájalo a 30", _decided("Baja el nivel de la batería al 30.", "limit")),
    ],
)
def test_what_no_question_of_baxys_asked_stays_the_deciders(before, text: str, decision: ContextDecision) -> None:
    result, model = _turn(before, text, decision)
    assert model.asked == 1
    if decision.decision == "action":
        assert result["effectOperations"] == list(decision.operations), result
    else:
        assert "audio.volume" not in (result.get("effectOperations") or []), result
        assert "audio.volume.adjust" not in (result.get("effectOperations") or []), result


def test_an_answer_about_minutes_stays_the_timer() -> None:
    # BAXY's question is not about raising or lowering a level: the length that answers «how long?» is M110's timer.
    result, _ = _turn(_said("ponme un temporizador", "¿Cuántos minutos?"), "unos 15",
                      _decided("Pon un temporizador de 15 minutos.", "action", "notification.schedule"))
    assert result["effectOperations"] == ["notification.schedule"], result


def test_the_deciders_own_volume_question_stands() -> None:
    # DEV-I v4y I-w15-t2: the decider already asked the volume; nothing replaces its question.
    decision = ContextDecision("Súbele más el volumen.", "clarify", (), "¿Cuánto le subo?", ())
    result, model = _turn(_said(*ROCK), "súbele un poco más, porfa", decision, "¿Otra pregunta?")
    assert (result["kind"], result["question"]) == ("clarify", "¿Cuánto le subo?"), result
    assert model.formulated == []


def test_a_relative_volume_without_amount_still_asks_on_a_first_message() -> None:
    # Owner rule H0027: «sube el volumen» asks the amount, no default step.
    result, _ = _turn([], "sube el volumen", _decided("", "talk"))
    assert (result["kind"], result["intentOperations"]) == ("clarify", ["audio.volume.adjust"]), result


# ------------------------------------------------------------------ the readers


@pytest.mark.parametrize(
    ("text", "level"),
    [
        ("súbele un poco a esa", levels.Level(levels.VOLUME, "up", None, None)),
        ("bájale un poquito a la canción", levels.Level(levels.VOLUME, "down", None, None)),
        ("súbele a ese tema", levels.Level(levels.VOLUME, "up", None, None)),
        ("bájale 10 a esta rola", levels.Level(levels.VOLUME, "down", 10, None)),
        ("turn this song up a bit", levels.Level(levels.VOLUME, "up", None, None)),
        ("subile 10, con eso ya me sirve", levels.Level(None, "up", 10, None)),
        ("súbele 10 y ya", levels.Level(None, "up", 10, None)),
        # Not the level: uploading, a rating, the position, a manner.
        ("sube la canción", None),
        ("sube la canción a drive", None),
        ("ponle 10 a esa", None),
        ("adelántala 15", None),
        ("súbele así", None),
        ("sube esa canción a youtube", None),
    ],
)
def test_the_level_reader(text: str, level: levels.Level | None) -> None:
    assert levels.read(text) == level


@pytest.mark.parametrize(
    ("text", "reply", "pending", "completed"),
    [
        ("unos 15 nomás", "¿Cuánto le subo?", "súbele un poco más, porfa", "sube el volumen en 15"),
        ("like 15", "¿Cuánto le bajo?", "can you bajarle un poco", "baja el volumen en 15"),
        ("25", "How much should I lower it?", TELLY, "baja el volumen en 25"),
        ("25", "Sure, down to what level?", TELLY, "pon el volumen al 25"),
        ("a 40", "¿Cuánto le subo?", "súbele", "pon el volumen al 40"),
        # Not this question: seconds, minutes, moving forward, no question, a statement.
        ("15", "¿Cuántos segundos la adelanto?", "adelántala un poco", None),
        ("like 15", "¿Cuántos segundos retrocedo?", "can you bajarle un poco", None),
        ("15", "¿Cuántos minutos?", "ponme un temporizador", None),
        ("15", "Listo, bajé 15.", "bájale un poco", None),
        ("15", "¿Cuánto la adelanto?", "adelántala", None),
        # Not an amount, or the request asked about was no level.
        ("la de queen", "¿Cuánto le subo?", "súbele un poco", None),
        ("15", "¿Cuánto le subo?", "pon la playlist de salsa", None),
    ],
)
def test_the_answer_reader(text: str, reply: str, pending: str, completed: str | None) -> None:
    assert levels.answered_level_request(text, reply, pending) == completed
