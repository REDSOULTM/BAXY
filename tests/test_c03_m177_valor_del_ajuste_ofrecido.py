"""M177 (2026-10-06, App runs v5a–v5d): a value or a yes that answers what BAXY just offered or asked about a level is
that change of that setting, and a question is never sent with effects.

- F-w04-t2 «yeah drop it to 40» after «Want me to dim the screen to save battery?», F-w32-t2 «ya po, dale» after «¿Bajo
  el brillo al 40 para que dure más?», F-w52-t2 «sí, dale, bájalo a 30» after «¿Te bajo el brillo para que aguante
  más?» (written histories): the decider read a battery drained to 40 («I do not drop the laptop's battery to 40%»),
  a download («No descargo archivos a 30.») or nothing («Entendido, estoy listo…»). The offer was BAXY's own; the yes,
  or the level said, sets the brightness (``levels.accepted_level_offer``), with the person's level, else the offer's.
  In the App runs BAXY offered nothing («The battery is at 96%…»): there those turns stay the decider's (M112).
- D-w18-t2 «can you bajarle un poco» (v5b–v5d) and G-w21-t2 «súbele un poco a esa» (v5d): M167 asked the volume amount
  with ``audio.volume.adjust`` among the effects, and the shell, whose contract refuses a clarification with effects,
  took it for no decision («No puedo bajarle nada porque mi mente no está disponible.»); D-w18-t3 «like 15» then
  answered that failure and was a seek. A question carries its operations as intent only.
- I-w34-t2 «25» after «How much should I lower it?» (v5b–v5d): lowered by 25 as BAXY asked (the gold's «down to what
  level?» is the written history's question), but worded in Spanish: M167's canonical request was Spanish and the
  result is worded against it. The request is now said in the person's language.

Rows are quoted with their real text and history; every other phrasing is our own. The clock is fixed.
"""

from __future__ import annotations

import datetime as _dt
import json
import pathlib
from typing import Any

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind import effect_intent
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic import arguments as semantic_arguments
from baxy_mind.semantic import levels
from baxy_mind.semantic import temporal as semantic_temporal
from baxy_mind.semantic.decider import ContextDecision
from baxy_mind.semantic.dialogue import DialogueState

OPERATIONS = tuple(
    json.loads(
        (pathlib.Path(sidecar.__file__).parent / "data" / "decider_catalog.es.v1.json").read_text(encoding="utf-8")
    )["operations"]
)
APPLICATIONS = ("Steam", "Spotify", "Google Chrome", "Discord", "Calculadora", "Bloc de notas")


class _FixedDatetime(_dt.datetime):
    """Tuesday 6 October 2026, 10:00 in Chile (UTC-3)."""

    @classmethod
    def now(cls, tz=None):  # noqa: ANN001, ANN206
        fixed = _dt.datetime(2026, 10, 6, 13, 0, 0, tzinfo=_dt.timezone.utc)
        return fixed.astimezone(tz) if tz is not None else fixed.astimezone(_dt.timezone(_dt.timedelta(hours=-3))).replace(
            tzinfo=None
        )


@pytest.fixture(autouse=True)
def _fixed_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    for module in (sidecar, semantic_arguments, semantic_temporal):
        if getattr(module, "datetime", None) is _dt.datetime:
            monkeypatch.setattr(module, "datetime", _FixedDatetime)


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
        self.formulated.append((objective, tuple(operations), tuple(missing_fields)))
        return self.question

    def clarify_after_turn_failure(self, *_a, **_k):
        return self.question

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
          question: str = "¿Cuánto le bajo al brillo?") -> tuple[dict, _Decider]:
    tools = {name: _tool(name) for name in OPERATIONS}
    model = _Decider(decision, question)
    result = sidecar._prepare_turn_result(
        {"id": "m177", "text": text, "history": [*before, {"role": "user", "content": text}]},
        llm=model, planner_catalog=PlannerCatalog(list(tools.values())), encoder=lambda _t: (),
        tool_by_name=tools, application_names=APPLICATIONS, dialogue_state=DialogueState(),
    )
    return result, model


def _decided(request: str, decision: str = "action", *operations: str) -> ContextDecision:
    return ContextDecision(request, decision, operations, "", ())


def _read(objective: str) -> tuple[str, ...]:
    read = effect_intent.resolve_explicit_effects(objective, OPERATIONS)
    assert read is not None, objective
    return read.operations


def _the_shell_accepts(result: dict) -> bool:
    """``MindSidecarClient.DecideTurnAsync``: a clarification has no operation and no effects, and one question."""

    if result["kind"] != "clarify":
        return True
    return not result.get("effectOperations") and result.get("operation") is None and bool(result.get("question"))


SET = "system.settings.set"
ADJUST = "system.settings.adjust"
F04 = ("laptop's been unplugged since lunch, battery at what?",
       "You're at 23%, about 1 hour 10 minutes left. Want me to dim the screen to save battery?")
F32 = ("oye cuánta batería me queda? se me quedó el cargador en la pega",
       "Te queda 23 %, más o menos 1 hora y 10 minutos. ¿Bajo el brillo al 40 para que dure más?")
F52 = ("oiga baxy, ¿cuánta pila le queda a este computador?",
       "Le queda 18 % y no está cargando. ¿Te bajo el brillo para que aguante más?")
LOFI = ("ok so like ponme la playlist de lofi para estudiar en spotify",
        "La pista «Moonloop - A Place to Stay» se está reproduciendo en Spotify.")
SALSA = ("pon la playlist de salsa que tengo en spotify",
         "He encontrado la canción \"Virgen\" de Adolescent's Orquesta que está reproduciéndose en tu lista de "
         "reproducción de salsa en Spotify.")


# ------------------------------------------------------------------ the yes or the level to BAXY's offer


@pytest.mark.parametrize(
    ("before", "text", "decision", "operation", "objective"),
    [
        # The rows (DEV-F, written histories) with what the App's decider decided in v5d.
        (_said(*F04), "yeah drop it to 40", _decided("Drop the battery to 40%.", "limit"), SET,
         "set the brightness to 40"),
        (_said(*F32), "ya po, dale", _decided("ya po, dale", "talk"), SET, "pon el brillo al 40"),
        (_said(*F52), "sí, dale, bájalo a 30", _decided("Baja la carga de la batería a 30.", "limit"), SET,
         "pon el brillo al 30"),
        # Our own words, both languages: the volume, an amount, the offer's own level, a level of the person's.
        (_said("está muy fuerte esto", "Está al 80. ¿Quieres que te baje el volumen?"), "sí porfa, a 20",
         _decided("Pon el volumen al 20.", "action", "audio.volume"), "audio.volume", "pon el volumen al 20"),
        (_said("play some jazz", "Now playing «Take Five». Should I turn the volume up to 60?"), "yes please",
         _decided("Yes please.", "talk"), "audio.volume", "set the volume to 60"),
        (_said("no veo nada", "El brillo está en 10. ¿Te subo el brillo?"), "dale, súbele 30",
         _decided("Adelanta 30 segundos.", "action", "media.seek.relative"), ADJUST, "sube el brillo en 30"),
        (_said("my eyes hurt", "Brightness is at 90. Want me to dim the screen?"), "sure, take it down to 50",
         _decided("Take it down to 50.", "clarify"), SET, "set the brightness to 50"),
    ],
)
def test_the_yes_to_baxys_offer_is_that_setting_changed(
    before, text: str, decision: ContextDecision, operation: str, objective: str,
) -> None:
    result, model = _turn(before, text, decision)
    assert (result["kind"], result["effectOperations"], result["objective"]) == ("action", [operation], objective), result
    assert _read(objective) == (operation,)
    assert model.asked == 0


@pytest.mark.parametrize(
    ("before", "text", "operation", "restated"),
    [
        (_said(*F52), "dale", ADJUST, "baja el brillo"),
        (_said(*F52), "sí, bájalo", ADJUST, "baja el brillo"),
        (_said("play some jazz", "Now playing «Take Five». Want me to turn the volume up?"), "yeah",
         "audio.volume.adjust", "turn the volume up"),
    ],
)
def test_a_yes_with_no_amount_to_an_offer_of_none_asks_only_the_amount(
    before, text: str, operation: str, restated: str,
) -> None:
    # Owner rule H0027: a relative change without an amount asks it; no default step.
    result, model = _turn(before, text, _decided(text, "talk"))
    assert (result["kind"], result["intentOperations"], result["effectOperations"]) == ("clarify", [operation], [])
    assert model.formulated == [(restated, (operation,), ("amount",))]
    assert model.asked == 0


@pytest.mark.parametrize(
    ("before", "text", "decision"),
    [
        # The rows as the App lived them: BAXY read the battery and offered nothing (M112: the decider's limit).
        (_said(F04[0], "The battery is at 96% and is not charging."), "yeah drop it to 40",
         _decided("Drop the battery to 40%.", "limit")),
        (_said(F52[0], "Le queda el 96% de carga en la batería, aunque está conectado a la corriente."),
         "sí, dale, bájalo a 30", _decided("Baja la carga de la batería a 30.", "limit")),
        (_said(F32[0], "Tienes el 96% de batería y el cargador está conectado."), "ya po, dale",
         _decided("ya po, dale", "talk")),
        # «bájalo a 30» with a song playing and nothing offered is the decider's.
        (_said(*SALSA), "bájalo a 30", _decided("Baja el volumen al 30.", "action", "audio.volume")),
        (_said("pon la película en netflix", "Se está reproduciendo «Dune» en Netflix."), "bájale a 30",
         _decided("Baja el volumen de Netflix al 30.", "action", "audio.app.volume.adjust")),
        # A no, something else asked, another setting, music offered, an application's volume offered.
        (_said(*F32), "no gracias, así está bien", _decided("No gracias.", "talk")),
        (_said(*F32), "mejor pon música", _decided("Pon música.", "action", "media.play.query")),
        (_said(*F32), "sí, y sube el volumen a 50", _decided("Sube el volumen a 50.", "action", "audio.volume")),
        (_said("estoy aburrido", "¿Pongo música?"), "dale", _decided("Pon música.", "action", "media.play.query")),
        (_said(*LOFI[:1], "Suena en Spotify. ¿Le bajo el volumen a Spotify?"), "dale, a 20",
         _decided("Baja el volumen de Spotify a 20.", "action", "audio.app.volume.adjust")),
    ],
)
def test_what_baxy_did_not_offer_stays_the_deciders(before, text: str, decision: ContextDecision) -> None:
    result, model = _turn(before, text, decision)
    assert model.asked == 1
    if decision.decision == "action":
        assert result["effectOperations"] == list(decision.operations), result
    else:
        assert not set(result.get("effectOperations") or ()) & {SET, ADJUST, "audio.volume", "audio.volume.adjust"}


def test_a_bare_number_with_nothing_before_it_is_still_asked() -> None:
    # No conversation, no offer: «40» stays the question it was (``unresolved_input_clarification``), no level.
    result, _ = _turn([], "40", _decided("40", "talk"))
    assert result["kind"] == "clarify" and not result.get("effectOperations"), result


def test_the_answer_to_how_much_stays_m167s() -> None:
    # M167: «¿cuánto le subo?» asks an amount, not a yes; its answer is still the change it asked.
    result, model = _turn(_said(*SALSA, "súbele un poco", "¿Cuánto le subo?"), "20",
                          _decided("Adelanta 20 segundos.", "action", "media.seek.relative"))
    assert (result["kind"], result["effectOperations"], result["objective"]) == (
        "action", ["audio.volume.adjust"], "sube el volumen en 20",
    ), result
    assert model.asked == 0


# ------------------------------------------------------------------ a question is never sent with effects


@pytest.mark.parametrize(
    ("before", "text", "decision", "intent"),
    [
        # The rows (DEV-D v5d D-w18-t2, DEV-G v5d G-w21-t2) with the App's decision.
        (_said(*LOFI), "can you bajarle un poco", _decided("Retrocede un poco la canción.", "clarify"),
         ["audio.volume.adjust"]),
        (_said(*SALSA), "súbele un poco a esa", _decided("Adelanta un poco la canción.", "clarify"),
         ["audio.volume.adjust"]),
        # Our own words, the other language and the brightness.
        (_said("play some jazz on spotify", "Now playing «Take Five» on Spotify."), "turn this song down a bit",
         _decided("Rewind the song a bit.", "clarify"), ["audio.volume.adjust"]),
        (_said("¿qué brillo tiene la pantalla?", "El brillo está en 70."), "bájale un poco al brillo",
         _decided("Retrocede un poco.", "clarify"), ["system.settings.adjust"]),
    ],
)
def test_a_question_carries_its_operations_as_intent_only(
    before, text: str, decision: ContextDecision, intent: list[str],
) -> None:
    result, _ = _turn(before, text, decision, "¿Cuánto le bajo?")
    assert (result["kind"], result["intentOperations"], result["effectOperations"]) == ("clarify", intent, []), result
    assert _the_shell_accepts(result)


def test_the_amount_after_the_question_is_the_volume() -> None:
    # D-w18-t3 «like 15» once t2 asked: the volume lowered by 15 (M167), in the person's language.
    before = _said(*LOFI, "can you bajarle un poco", "¿Cuánto le bajo?")
    result, _ = _turn(before, "like 15", _decided("Retrocede 15 segundos la canción.", "action", "media.seek.relative"))
    assert (result["kind"], result["effectOperations"]) == ("action", ["audio.volume.adjust"]), result


@pytest.mark.parametrize(
    ("before", "text", "objective"),
    [
        # I-w34-t2: the English request it answers keeps the English form.
        (_said("the telly's blaring in the next room as it is, bring the volume down on here",
               "How much should I lower it?"), "25", "turn the volume down by 25"),
        # A Spanish conversation keeps the Spanish form.
        (_said("bájale al volumen", "¿Cuánto le bajo?"), "25", "baja el volumen en 25"),
        (_said("turn the brightness down", "How much should I lower the brightness?"), "20",
         "turn the brightness down by 20"),
    ],
)
def test_the_level_request_is_said_in_the_persons_language(before, text: str, objective: str) -> None:
    result, _ = _turn(before, text, _decided("Baja 25.", "action", "media.seek.relative"))
    assert result["objective"] == objective, result
    assert result["effectOperations"] == list(_read(objective))


# ------------------------------------------------------------------ the reader


@pytest.mark.parametrize(
    ("reply", "text", "level"),
    [
        (F04[1], "yeah drop it to 40", levels.Level(levels.BRIGHTNESS, "down", None, 40)),
        (F32[1], "ya po, dale", levels.Level(levels.BRIGHTNESS, "down", None, 40)),
        (F52[1], "sí, dale, bájalo a 30", levels.Level(levels.BRIGHTNESS, "down", None, 30)),
        (F04[1], "40", levels.Level(levels.BRIGHTNESS, "down", None, 40)),
        (F04[1], "yeah drop it by 10", levels.Level(levels.BRIGHTNESS, "down", 10, None)),
        (F52[1], "dale, al mínimo", levels.Level(levels.BRIGHTNESS, "down", None, 0)),
        (F52[1], "bájale 10", levels.Level(levels.BRIGHTNESS, "down", 10, None)),
        ("Should I turn the volume up to 60?", "make it 70", levels.Level(levels.VOLUME, "up", None, 70)),
        # Not an offer of a level, or not a yes to it.
        (F32[1], "no gracias", None),
        (F32[1], "dale, pero al 20", None),
        (F52[1], "sí, y sube el volumen a 50", None),
        (F04[1], "what time is it", None),
        ("¿Cuánto le bajo?", "20", None),
        ("The battery is at 96%.", "yeah drop it to 40", None),
        ("¿Pongo música?", "dale", None),
        ("¿Pongo el volumen?", "dale", None),
        ("¿Te bajo el brillo para que dure 2 horas más?", "dale", None),
        ("¿Subo el volumen o lo bajo?", "dale", None),
        ("Listo, brillo al 40.", "dale", None),
        # One application's volume is its own operation (AUDIO1787).
        ("Suena en Spotify. ¿Le bajo el volumen a Spotify?", "dale, a 20", None),
        ("Want me to turn Chrome's volume down?", "yes", None),
        ("¿Te bajo el volumen de la música?", "dale, a 20", levels.Level(levels.VOLUME, "down", None, 20)),
    ],
)
def test_the_offer_reader(reply: str, text: str, level: levels.Level | None) -> None:
    assert levels.accepted_level_offer(text, reply) == level


@pytest.mark.parametrize(
    ("level", "setting", "spanish", "english"),
    [
        (levels.Level(None, None, None, 40), levels.BRIGHTNESS, "pon el brillo al 40", "set the brightness to 40"),
        (levels.Level(None, "down", 25, None), levels.VOLUME, "baja el volumen en 25", "turn the volume down by 25"),
        (levels.Level(None, "up", None, None), levels.VOLUME, "sube el volumen", "turn the volume up"),
    ],
)
def test_the_canonical_request_in_both_languages(level: levels.Level, setting: str, spanish: str, english: str) -> None:
    assert (level.request(setting), level.request(setting, english=True)) == (spanish, english)
    if level.amount is not None or level.target is not None:
        assert _read(spanish) == _read(english)
    else:
        # Without an amount both forms are the same question for it (owner rule H0027).
        asked = [effect_intent.resolve_explicit_clarification_intent(said, OPERATIONS) for said in (spanish, english)]
        assert asked[0] is not None and asked[1] is not None
        assert (asked[0].operations, asked[0].missing_fields) == (asked[1].operations, asked[1].missing_fields)
