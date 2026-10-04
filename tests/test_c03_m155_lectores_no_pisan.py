"""M155 (D58, 2026-10-04): first-turn readers and guards that overrode the isolated decider on DEV-I (window v4u-devI).

Five messages a reader or a guard decided (explicit_effects / explicit_clarification / explicit_conversation) where the
isolated decider full3 was right. Each reader is narrowed to what it really reads; nothing waits on a new layer, and a
message no reader proves any more is the contextual decider's:

1. «media hora» is half an hour, not media (I-s022: the battery was read as what this PC plays).
2. An exclamation of praise («qué buena esa respuesta…», «what a great answer…») is no question to observe a domain
   (I-s043: «la tarea» was read as the task list).
3. Safety: a message the person keeps for themselves to send («leave it for me to send», «pero lo mando yo») is never
   read as sent, by the readers or after the decider (I-s061: sent where the gold and the decider left it written).
4. «¿qué horas son?» is Latin American Spanish, not Portuguese (I-w44-t3: «repita su pedido en español o inglés»).
5. D61: an alarm «for 6 to get up…» has its hour; what it is for follows it (I-s008: asked am or pm).

Left as it is, by owner decision: «buscame en youtube X» opens YouTube's results (reviewed literal H0728, WEB1481), and
«escribe/write X to Y on WhatsApp» with no order not to send is a send, confirmed in normal mode (reviewed literals
H0369, H0395, H0533; owner 2026-09-21; D59.1).

Every variant phrasing here is our own; the DEV-I texts are the rows themselves.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic.arguments import _explicit_arguments_from_evidence
from baxy_mind.semantic.decider import ContextDecision
from baxy_mind.semantic.dialogue import DialogueState
from baxy_mind.semantic.grammar import _fold
from baxy_mind.semantic.messaging import asks_not_to_send, message_left_written_request
from baxy_mind.semantic.patterns import (
    confident_non_target_language,
    resolve_explicit_clarification_intent,
    resolve_explicit_effects,
)
from baxy_mind.semantic.temporal import alarm_for_hour

OPERATIONS = tuple(
    json.loads(
        (pathlib.Path(sidecar.__file__).parent / "data" / "decider_catalog.es.v1.json").read_text(encoding="utf-8")
    )["operations"]
)


class _Decider:
    """The model of a whole turn: the decider answers what it is given; every other call is neutral."""

    _native_tool_policy_enabled = False

    def __init__(self, decision: ContextDecision | None = None) -> None:
        self.decision = decision
        self.decisions = 0

    def decide_in_context(self, *_a, **_k):
        self.decisions += 1
        if self.decision is None:
            raise AssertionError("the decider was not to be asked")
        return self.decision

    def formulate_explicit_clarification_question(self, *_a, **_k):
        return "¿A qué hora?"

    def clarify_after_turn_failure(self, *_a, **_k):
        return "¿Qué necesitas?"

    def public_lookup_requested(self, _text):
        return False

    def operation_is_the_requested_effect(self, *_a, **_k):
        return True

    def _verify_semantic_effect_shape(self, _text):
        return "no_effect", "zero"

    def chat(self, *_a, **_k):
        return "Respuesta.", []

    def prepare_chat(self, *_a, **_k):
        return None

    def prepare_decision(self, *_a, **_k):
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


def _tool(name: str) -> dict:
    schema = {"type": "object", "properties": {}, "required": [], "additionalProperties": False}
    return {"type": "function", "function": {"name": name.replace(".", "_"), "canonical_name": name,
                                             "description": name, "risk": "read_only", "parameters": schema}}


def _turn(text: str, model: _Decider, history: list[dict] | None = None) -> dict:
    tools = {name: _tool(name) for name in OPERATIONS}
    return sidecar._prepare_turn_result(
        {"id": "m155", "text": text, "history": [*(history or []), {"role": "user", "content": text}]},
        llm=model, planner_catalog=PlannerCatalog(list(tools.values())), encoder=lambda _t: (), tool_by_name=tools,
        dialogue_state=DialogueState(),
    )


def _read(text: str) -> tuple[str, ...] | None:
    found = resolve_explicit_effects(text, OPERATIONS)
    return None if found is None else tuple(found.operations)


def _asked(text: str) -> tuple[str, ...] | None:
    found = resolve_explicit_clarification_intent(text, OPERATIONS)
    return None if found is None else tuple(found.missing_fields)


def _action(request: str, *operations: str) -> ContextDecision:
    return ContextDecision(request=request, decision="action", operations=operations, question="")


# ------------------------------------------------------------------ 1. «media hora» is no media


def test_the_battery_before_half_an_hour_is_the_deciders() -> None:
    # DEV-I I-s022: the isolated decider read the battery.
    text = "oye, dime cuánto de batería le queda a la laptop, que salgo en media hora"
    model = _Decider(_action("¿Cuánta batería le queda a la laptop?", "system.status"))

    result = _turn(text, model)

    assert model.decisions == 1
    assert result["operation"] == "system.status"


@pytest.mark.parametrize(
    "text",
    [
        "revisa el sistema, que en media hora tengo clase",
        "ponme al día con las noticias, que en media hora salgo",
        "dime cuánta memoria tiene el equipo, que a media mañana tengo una reunión",
    ],
)
def test_half_an_hour_reads_no_media(text: str) -> None:
    assert "media.status" not in (_read(text) or ())


@pytest.mark.parametrize(
    "text",
    ["qué está sonando", "dime qué está sonando", "¿qué se está reproduciendo?", "what's playing right now?"],
)
def test_what_plays_is_still_what_plays(text: str) -> None:
    assert _read(text) == ("media.status",)


def test_the_battery_alone_is_still_read() -> None:
    assert _read("dime cuánta batería le queda") == ("system.status",)
    assert _read("check the battery, I'm leaving in half an hour") == ("system.status",)


# ------------------------------------------------------------------ 2. praise is no request


def test_praise_for_help_with_homework_is_the_deciders_talk() -> None:
    # DEV-I I-s043: the isolated decider talked.
    text = "qué buena esa respuesta baxy, en serio me salvaste con la tarea"
    model = _Decider(ContextDecision(request=text, decision="talk", operations=(), question=""))

    result = _turn(text, model)

    assert model.decisions == 1
    assert result["kind"] == "conversation"
    assert not result.get("effectOperations")


@pytest.mark.parametrize(
    "text",
    [
        "qué buena esa respuesta baxy, en serio me salvaste con la tarea",
        "what a great answer baxy, you totally saved me with the homework",
        "qué bien, me salvaste con la tarea de mate",
        "que bueno que me ayudaste con la tarea",
    ],
)
def test_praise_reads_no_task_list(text: str) -> None:
    assert _read(text) is None


@pytest.mark.parametrize("text", ["muéstrame mis tareas", "¿qué tareas tengo?", "show my tasks"])
def test_the_task_list_is_still_read(text: str) -> None:
    assert _read(text) == ("task.list",)


def test_a_request_after_the_praise_is_still_read() -> None:
    assert _read("qué bien, qué está sonando") == ("media.status",)


# ------------------------------------------------------------------ 3. safety: kept to send is never sent


def test_a_message_left_for_the_person_to_send_is_drafted() -> None:
    # DEV-I I-s061: the gold and the isolated decider left it written.
    text = ("write a WhatsApp to Callum saying I'm stuck on the Northern line and I'll be about twenty minutes late, "
            "but leave it for me to send")

    result = _turn(text, _Decider())

    assert result["effectOperations"] == ["message.draft"]
    assert _explicit_arguments_from_evidence("message.draft", text) == {
        "channel": "whatsapp", "recipient": "Callum",
        "text": "I'm stuck on the Northern line and I'll be about twenty minutes late",
    }


@pytest.mark.parametrize(
    ("text", "recipient", "body"),
    [
        ("escríbele un whatsapp a Callum diciendo que llego tarde, pero déjamelo para que lo mande yo", "Callum",
         "llego tarde"),
        ("mándale a Lucas por whatsapp que llego tarde, pero lo mando yo", "Lucas", "llego tarde"),
        ("send a whatsapp to Priya saying the meeting moved to 4, I'll send it myself", "Priya",
         "the meeting moved to 4"),
        ("write a discord message to Tyler saying the raid starts at 9, let me hit send on it", "Tyler",
         "the raid starts at 9"),
    ],
)
def test_kept_to_send_is_a_draft(text: str, recipient: str, body: str) -> None:
    assert asks_not_to_send(text)
    assert _read(text) == ("message.draft",)
    assert message_left_written_request(text)[1:] == (recipient, body)


@pytest.mark.parametrize(
    "text",
    [
        "text Callum saying I'm late, don't send it yet",
        "escríbele a Ana que llego tarde pero no se lo mandes",
        "message Priya that I'm on my way, but leave it for me to send",
    ],
)
def test_an_order_not_to_send_with_no_client_is_never_read_as_sent(text: str) -> None:
    assert _read(text) is None


def test_the_deciders_send_is_held_when_the_person_keeps_the_sending() -> None:
    text = "text Callum saying I'm late, don't send it yet"
    model = _Decider(_action("Text Callum saying I'm late.", "message.recipient.resolve", "message.send"))

    result = _turn(text, model)

    assert model.decisions == 1
    assert result["effectOperations"] == ["message.draft"]


@pytest.mark.parametrize(
    "text",
    [
        # the owner's reviewed sends: a message said to someone in a client is sent, confirmed in normal mode
        "escríbele un whatsapp a Callum diciendo que llego tarde",
        "envíale un whatsapp a Callum diciendo que llego en veinte",
        "write a WhatsApp to Callum saying I'm running late",
        "Escribe hola a musica en whatsapp",
        # «yo lo mando» inside the words of the message is what is said
        "dile a Ana por whatsapp que yo lo mando mañana",
    ],
)
def test_a_message_to_send_is_still_sent(text: str) -> None:
    assert not asks_not_to_send(text)
    assert _read(text) == ("message.recipient.resolve", "message.send")


def test_the_deciders_send_still_sends_without_the_order() -> None:
    text = "text Callum saying I'm late"
    model = _Decider(_action("Text Callum saying I'm late.", "message.recipient.resolve", "message.send"))

    result = _turn(text, model)

    assert result["effectOperations"] == ["message.recipient.resolve", "message.send"]


# ------------------------------------------------------------------ 4. «qué horas son» is Spanish


def test_the_clock_of_another_town_asked_in_spanish_is_the_deciders() -> None:
    # DEV-I I-w44-t3, with its conversation: the isolated decider read Orlando's clock.
    history = [
        {"role": "user", "content": "oiga baxy, cómo está el clima en Miami, que viajo el jueves"},
        {"role": "assistant", "content": "En Miami hay 29 °C, nublado y con chance de lluvia por la tarde."},
        {"role": "user", "content": "¿y en Orlando?"},
        {"role": "assistant", "content": "En Orlando, 31 °C y sol; mañana parecido."},
    ]
    text = "oiga y allá en orlando qué horas serán, para llamar a mi prima sin despertarla"
    model = _Decider(_action("¿Qué hora es en Orlando?", "system.time"))

    result = _turn(text, model, history)

    assert model.decisions == 1
    assert result["operation"] == "system.time"


@pytest.mark.parametrize(
    "text",
    [
        "oiga y allá en orlando qué horas serán, para llamar a mi prima sin despertarla",
        "¿qué horas son en Bogotá?",
        "mijo, ¿qué horas tiene?",
    ],
)
def test_que_horas_is_spanish(text: str) -> None:
    assert confident_non_target_language(text) is None


@pytest.mark.parametrize(("text", "language"), [("que horas são", "pt"), ("Que horas são agora?", "pt"),
                                                ("aumenta o volume", "pt")])
def test_portuguese_is_still_portuguese(text: str, language: str) -> None:
    assert confident_non_target_language(text) == language


# ------------------------------------------------------------------ 5. D61: the alarm's hour before what it is for


def test_an_alarm_for_six_to_get_up_rings_at_the_next_six() -> None:
    # DEV-I I-s008: the isolated decider set it.
    text = "set an alarm for 6 to get up for my run, cheers"

    result = _turn(text, _Decider())

    assert result["effectOperations"] == ["notification.schedule"]
    assert _explicit_arguments_from_evidence("notification.schedule", text)["dueUtc"] == "at 6"


@pytest.mark.parametrize(
    ("text", "due"),
    [
        ("pon una alarma para 7 para ir al gimnasio", "a las 7"),
        ("set an alarm for 5 so I can catch the early train", "at 5"),
        ("ponme una alarma para 6 pa levantarme temprano", "a las 6"),
    ],
)
def test_what_the_alarm_is_for_follows_its_hour(text: str, due: str) -> None:
    assert _asked(text) is None
    assert _read(text) == ("notification.schedule",)
    assert _explicit_arguments_from_evidence("notification.schedule", text)["dueUtc"] == due


@pytest.mark.parametrize(
    ("text", "asked"),
    [
        # a range or a clock said in words is not what the alarm is for
        ("set an alarm for 6 to 7", ("am_pm_or_part_of_day_for_supplied_hour",)),
        # what the alarm is for, with no hour, still asks it
        ("pon una alarma para una reunión", ("alarm_time",)),
        # a purpose that names the day is asked as before (D61b would read the 6 of a named day as the afternoon)
        ("set an alarm for 6 to get up tomorrow", ("am_pm_or_part_of_day_for_supplied_hour",)),
        ("pon una alarma para 6 para levantarme mañana", ("am_pm_or_part_of_day_for_supplied_hour",)),
    ],
)
def test_no_hour_with_a_purpose_is_read_from_a_number(text: str, asked: tuple[str, ...]) -> None:
    assert _asked(text) == asked
    assert alarm_for_hour(_fold(text)) is None


def test_the_length_and_the_reason_keep_their_reading() -> None:
    assert alarm_for_hour("set an alarm for ten to seven") is None
    assert alarm_for_hour("set an alarm for 8 minutes") is None
    # «que/porque» gives the reason, not what the alarm is for: left to the readers as before
    assert alarm_for_hour("ponme una alarma para 6 que mañana madrugo") is None


# ------------------------------------------------------------------ left as the owner decided


def test_a_search_on_youtube_still_opens_its_results() -> None:
    # DEV-I I-s111 (gold: play) against the reviewed literal H0728 «buscá videos de gatos en youtube» (WEB1481): a
    # search on YouTube opens YouTube's results page, nothing plays. Not changed here; reported.
    assert _read("buscame en youtube el resumen de la final de la libertadores 2024") == ("browser.navigate",)
    assert _read("buscá videos de gatos en youtube") == ("browser.navigate",)
