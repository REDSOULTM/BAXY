"""M148 (2026-10-03, App runs v4q-devF, v4q-devD, v4r-devG): reminders in a conversation, «eso» and the counts.

Rows where the decision was right and the arguments wrong:

1. F-w48-t4 «órale, pues recuérdame eso el domingo a las 3 de la tarde» after «…; mejor lleva paraguas.» → titled «Voy a
   estar en Zapopan el domingo.» (another thing the person said). A reminder that is all «eso» is the one thing BAXY's
   last reply advised doing.
2. D-w07-t4 «va, ahorita ponle un recordatorio el viernes a las 5 de la tarde que le devuelva eso a mi carnal» after
   «Redondeado hacia arriba, 265.» → «Devolverle eso a mi amigo.». «eso» as what something is done with is the one figure
   BAXY's last short reply gave.
3. G-w19-t4 «pues salgo sobre las 6 de la tarde, así que calcula desde ahí» after «vale, pues recuérdamelo veinte minutos
   antes de salir» → «¿A qué hora tienes pensado salir?» → set at 18:00. The moment the answer gives, less the advance
   the request asked, is when it rings (17:40).
4. F-w45-t3 «go with 12, the bag says 10 to 12 but my oven runs cold»: in the App the turn before had set a 25-minute
   countdown for the garlic knots (where the written conversation asked «How long…?», which the M110 reader already
   completes), the decider planned «Change the garlic knots countdown to 12 minutes.» and the plan asked «¿Qué tipo de
   alarma o recordatorio necesitas cancelar?». A countdown is a timer, and a timer moved to a new length rings that long
   from now.

Every phrasing beyond the rows is our own; clocks are fixed where the result depends on them.
"""

from __future__ import annotations

import json
import pathlib
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic import dialogue, temporal
from baxy_mind.semantic.decider import ContextDecision
from baxy_mind.semantic.dialogue import DialogueState

LOCAL = timezone(timedelta(hours=-3))
# Saturday 3 October 2026, 15:00 in Chile (UTC-3).
NOW = datetime(2026, 10, 3, 15, 0, tzinfo=LOCAL)

OPERATIONS = tuple(
    json.loads(
        (pathlib.Path(sidecar.__file__).parent / "data" / "decider_catalog.es.v1.json").read_text(encoding="utf-8")
    )["operations"]
)
SCHEDULE = {"type": "object", "properties": {
    "dueUtc": {"type": "string", "maxLength": 64, "x-nonWhitespace": True},
    "kind": {"type": "string", "enum": ["alarm", "reminder"]},
    "recurrence": {"type": "string", "enum": ["daily", "hourly"]},
    "title": {"type": "string", "x-maxUtf8Bytes": 1024, "x-nonWhitespace": True}},
    "required": ["dueUtc", "kind", "title"], "additionalProperties": False}
REMINDER = {"type": "object", "properties": {
    "details": {"type": "string", "x-maxUtf8Bytes": 65536},
    "dueUtc": {"type": "string", "maxLength": 64, "x-nonWhitespace": True},
    "title": {"type": "string", "x-maxUtf8Bytes": 1024, "x-nonWhitespace": True}},
    "required": ["dueUtc", "title"], "additionalProperties": False}
CANCEL_LATEST = {"type": "object", "properties": {"kind": {"type": "string", "enum": ["alarm", "reminder"]}},
                 "required": ["kind"], "additionalProperties": False}


def _tool(operation: str, schema: dict[str, Any] | None = None) -> dict[str, Any]:
    schema = schema or {"type": "object", "properties": {}, "required": [], "additionalProperties": False}
    return {"type": "function", "function": {"name": operation.replace(".", "_"), "canonical_name": operation,
                                             "description": operation, "risk": "read_only", "parameters": schema}}


class _Decider:
    """The model of a whole turn: the decider answers what it is given; every other call is neutral."""

    _native_tool_policy_enabled = False

    def __init__(self, decision: ContextDecision) -> None:
        self.decision = decision

    def decide_in_context(self, *_a, **_k):
        return self.decision

    def prepare_decision(self, *_a, **_k):
        return None

    def formulate_explicit_clarification_question(self, *_a, **_k):
        return "¿A qué hora?"

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


class _NoExtraction:
    """The arguments step must not need the model."""

    def extract_direct_arguments(self, *_a, **_k):
        raise AssertionError("the readers had the arguments")

    def formulate_missing_argument_question(self, *_a, **_k):
        raise AssertionError("nothing is to be asked")


def _history(said: list[str]) -> list[dict[str, str]]:
    return [{"role": "user" if index % 2 == 0 else "assistant", "content": line} for index, line in enumerate(said)]


def _turn(said: list[str], decision: ContextDecision) -> dict:
    """``said``: the conversation, user first and alternating, ending in the person's message."""

    tools = {name: _tool(name) for name in OPERATIONS}
    return sidecar._prepare_turn_result(
        {"id": "m148", "text": said[-1], "history": _history(said)},
        llm=_Decider(decision), planner_catalog=PlannerCatalog(list(tools.values())), encoder=lambda _t: (),
        tool_by_name=tools, dialogue_state=DialogueState(),
    )


def _arguments(operation: str, objective: str, said: list[str], decided: dict[str, Any] | None = None,
               schema: dict[str, Any] = SCHEDULE) -> tuple[dict | None, str]:
    if decided is not None:
        sidecar._remember_decided_arguments(objective, (operation,), tuple(decided.items()))
    return sidecar._direct_arguments_result(
        {"operation": operation, "text": objective, "history": _history(said)},
        llm=_NoExtraction(), tool=_tool(operation, schema), dialogue_state=DialogueState(),
    )


def _local(due: str) -> datetime:
    return datetime.fromisoformat(due.replace("Z", "+00:00")).astimezone()


# ------------------------------------------------------------------ 1. «recuérdame eso» after advice

W48 = [
    "oye baxy, ¿qué onda con el clima en Guadalajara hoy? es que voy a salir al rato",
    "En Guadalajara hay 27 °C y está despejado; en la tarde puede caer tormenta.",
    "¿y pa'l domingo cómo pinta?",
    "El domingo en Guadalajara: 24 °C, con lluvia por la tarde.",
    "ah no, perdón, me equivoqué, el domingo voy a estar en Zapopan, no en Guadalajara",
    "El domingo en Zapopan: 23 °C, nublado y 60 % de probabilidad de lluvia en la tarde; mejor lleva paraguas.",
    "órale, pues recuérdame eso el domingo a las 3 de la tarde",
]


def test_f_w48_t4_the_reminder_of_eso_is_the_umbrella() -> None:
    restated = "Recuérdame el domingo a las 3 de la tarde que voy a estar en Zapopan."
    arguments_, question = _arguments(
        "notification.schedule", restated, W48,
        decided={"dueUtc": "2026-10-04T15:00:00-06:00", "kind": "reminder",
                 "title": "Voy a estar en Zapopan el domingo a las 3 de la tarde."},
    )
    assert question == "" and arguments_["title"] == "lleva paraguas"
    assert (_local(arguments_["dueUtc"]).hour, _local(arguments_["dueUtc"]).minute) == (15, 0)


@pytest.mark.parametrize(
    ("text", "reply", "title", "pointed"),
    [
        ("recuérdamelo mañana a las 8", "Mañana amanece con 2 °C; te conviene sacar la chaqueta gruesa.",
         "Mañana a las 8", "sacar la chaqueta gruesa"),
        ("ok remind me about that tomorrow at 7", "Tomorrow will be windy and wet, so you might want to bring a "
         "raincoat.", "tomorrow at 7", "bring a raincoat"),
        ("dale, ponme un recordatorio de eso para el lunes a las 9", "El trámite vence el martes; no olvides llevar "
         "el carnet.", "trámite", "llevar el carnet"),
    ],
)
def test_a_reminder_that_is_all_eso_is_what_baxy_advised(text: str, reply: str, title: str, pointed: str) -> None:
    assert dialogue.pointed_reminder_title(text, reply, title) == pointed


@pytest.mark.parametrize(
    ("text", "reply", "title"),
    [
        # The App's run v4q: the forecast came with no advice; nothing to point at is invented.
        ("órale, pues recuérdame eso el domingo a las 3 de la tarde", "El domingo en Zapopan hará 26.6 °C de máxima y "
         "17 °C de mínima con un 100 % de probabilidad de lluvia.", "Voy a estar en Zapopan el domingo."),
        # The title already says it.
        ("órale, pues recuérdame eso el domingo a las 3 de la tarde", W48[-2], "Llevar paraguas"),
        # The reminder says what it is for.
        ("recuérdame mañana a las 9 llamar a mamá", "Mejor lleva paraguas.", "llamar a mamá"),
        # «recuérdamelo … antes de salir» is about leaving, and the reply advised nothing.
        ("vale, pues recuérdamelo veinte minutos antes de salir", "En una hora debería estar algo más fluido, unos 25 "
         "minutos.", "salir"),
        # Two pieces of advice: which one is not told.
        ("recuérdamelo a las 7", "Mejor lleva paraguas. Y te conviene salir temprano.", "a las 7"),
    ],
)
def test_nothing_else_is_retitled(text: str, reply: str, title: str) -> None:
    assert dialogue.pointed_reminder_title(text, reply, title) is None


# ------------------------------------------------------------------ 2. «que le devuelva eso» after a figure

W07 = [
    "oye güey ábreme la calcu porfa",
    "Listo, abrí la Calculadora.",
    "órale, y divídeme ahí 1850 entre 7",
    "1850 entre 7 da 264.29.",
    "este... y redondeado para arriba",
    "Redondeado hacia arriba, 265.",
    "va, ahorita ponle un recordatorio el viernes a las 5 de la tarde que le devuelva eso a mi carnal",
]


@pytest.mark.parametrize("decided_title", ["Devolverle eso a mi amigo.", "Devolverle algo a mi amigo"])
def test_d_w07_t4_eso_is_the_265_just_given(decided_title: str) -> None:
    restated = "Pon un recordatorio el viernes a las 5 de la tarde para devolverle eso a mi amigo."
    arguments_, question = _arguments(
        "notification.schedule", restated, W07,
        decided={"dueUtc": "2026-10-09T17:00:00", "kind": "reminder", "title": decided_title},
    )
    assert question == "" and "265" in arguments_["title"] and "eso" not in arguments_["title"]


@pytest.mark.parametrize(
    ("text", "reply", "before", "title", "pointed"),
    [
        # The App's run v4q answered «265.» alone.
        (W07[-1], "265.", W07[0:-1:2], "Devolverle eso a mi amigo.", "Devolverle 265 a mi amigo."),
        ("set a reminder for friday at 6pm to pay my sister that back", "Split three ways, each of you owes 42.50 "
         "dollars.", ["dinner was 127.50, split it three ways"], "pay my sister that back",
         "pay my sister 42.50 dollars back"),
        ("recuérdame mañana a las 9 que le pase eso a Juan", "Te toca pagar 18 mil pesos.", [],
         "que le pase eso a Juan", "que le pase 18 mil pesos a Juan"),
    ],
)
def test_eso_done_with_something_is_the_figure_baxy_gave(
    text: str, reply: str, before: list[str], title: str, pointed: str,
) -> None:
    assert dialogue.pointed_reminder_title(text, reply, title, before) == pointed


@pytest.mark.parametrize(
    ("text", "reply", "title"),
    [
        # A reply with a clock and a room number gives no one figure.
        ("recuérdame mañana a las 9 que le pase eso a Juan", "La reunión es a las 10 en la sala 3.",
         "que le pase eso a Juan"),
        # «that» opening a clause points at nothing.
        ("remind me tomorrow that the meeting moved", "It moved to room 4.", "that the meeting moved"),
        # The figure is already in the title.
        (W07[-1], "Redondeado hacia arriba, 265.", "Devolverle 265 a mi carnal"),
        # Only numbers the person said: nothing new to point at.
        ("recuérdame mañana devolverle eso a Ana", "Le debes 20, como dijiste.", "devolverle eso a Ana"),
    ],
)
def test_no_figure_no_change(text: str, reply: str, title: str) -> None:
    before = ["le debo 20 a Ana"] if "Ana" in text else []
    assert dialogue.pointed_reminder_title(text, reply, title, before) is None


# ------------------------------------------------------------------ 3. the advance counted from the answered moment

W19 = [
    "qué tal está el tráfico para ir al aeropuerto",
    "Ahora mismo hay bastante tráfico, se tarda unos 40 minutos al aeropuerto.",
    "¿y en una hora estará mejor?",
    "En una hora debería estar algo más fluido, unos 25 minutos.",
    "vale, pues recuérdamelo veinte minutos antes de salir",
    "¿A qué hora tienes pensado salir?",
    "pues salgo sobre las 6 de la tarde, así que calcula desde ahí",
]


@pytest.mark.parametrize(
    "restated",
    [
        "Recuérdame en 4:40 de la tarde.",  # the isolated decider
        "Recuérdame en 20 minutos que la alarma para el tráfico del aeropuerto sonará a las 17:55.",  # the App's
    ],
)
def test_g_w19_t4_twenty_minutes_before_six_is_17_40(restated: str) -> None:
    result = _turn(W19, ContextDecision(restated, "action", ("notification.schedule",), ""))
    assert result["kind"] == "action" and result["objective"] == "recuérdame salir a las 17:40"
    schema = SCHEDULE if result["operation"] == "notification.schedule" else REMINDER
    arguments_, question = _arguments(result["operation"], result["objective"], W19, schema=schema)
    assert question == "" and arguments_["title"] == "salir"
    assert (_local(arguments_["dueUtc"]).hour, _local(arguments_["dueUtc"]).minute) == (17, 40)


def test_the_decider_that_already_counted_it_stands() -> None:
    restated = "Recuérdame salir a las 17:40 para ir al aeropuerto."
    result = _turn(W19, ContextDecision(restated, "action", ("notification.schedule",), ""))
    assert result["objective"] == restated


@pytest.mark.parametrize(
    ("text", "pending", "reply", "rewritten"),
    [
        ("I'm heading out at 7pm", "remind me half an hour before I leave", "What time are you leaving?",
         "remind me at 18:30 before I leave"),
        # A clock without its part of the day is the next time it comes (D61): at 15:00, 20:00.
        ("como a las 8, más o menos", "avísame 15 minutos antes de irme al gimnasio", "¿A qué hora te vas?",
         "recuérdame irme al gimnasio a las 19:45"),
        ("mañana salgo a las 7 de la mañana", "ponme una alarma media hora antes de salir", "¿A qué hora sales?",
         "pon una alarma mañana a las 06:30 para salir"),
        ("empieza a las 9 de la noche", "recuérdame una hora antes de que empiece el partido",
         "¿A qué hora empieza el partido?", "recuérdame a las 20:00 antes de que empiece el partido"),
    ],
)
def test_the_answered_moment_less_the_advance(text: str, pending: str, reply: str, rewritten: str) -> None:
    assert temporal.answered_advance_request(text, pending, reply, now=NOW) == rewritten


@pytest.mark.parametrize(
    ("text", "pending", "reply"),
    [
        # An order with its own clock: that is when it rings.
        ("avísame a las 5:30", "recuérdamelo veinte minutos antes de salir", "¿A qué hora tienes pensado salir?"),
        # BAXY asked nothing.
        ("salgo a las 6", "recuérdamelo veinte minutos antes de salir", "Vale, lo anoto."),
        # The request counted nothing.
        ("salgo a las 6", "recuérdame comprar pan", "¿A qué hora?"),
        # «antes de eso» is the moment BAXY gave (``anchored_offset_request``).
        ("a las 6", "recuérdamelo veinte minutos antes de eso", "¿A qué hora es eso?"),
        # A new count in the answer is read by ``said_advance`` with its own clock.
        ("salgo a las 6, pero avísame 10 minutos antes", "recuérdamelo veinte minutos antes de salir",
         "¿A qué hora sales?"),
        # Two clocks: which one is not told.
        ("entre las 6 y las 7", "recuérdamelo veinte minutos antes de salir", "¿A qué hora sales?"),
        # A day and a clock without its part of the day are left to the decider.
        ("el viernes a las 6", "recuérdamelo veinte minutos antes de salir", "¿A qué hora sales?"),
    ],
)
def test_no_answered_advance(text: str, pending: str, reply: str) -> None:
    assert temporal.answered_advance_request(text, pending, reply, now=NOW) is None


# ------------------------------------------------------------------ 4. a countdown moved to a new length


def _timer_state(title: str, due: datetime, request: str, kind: str = "alarm") -> DialogueState:
    state = DialogueState()
    state.expect(request, ["notification.schedule"])
    state.record({
        "kind": "operation", "operation": "notification.schedule", "polarity": "success", "verified": True,
        "succeeded": True,
        "observed": {"version": 1, "kind": kind, "title": title, "dueUtc": due.astimezone(timezone.utc).isoformat(),
                     "taskName": "BAXY-Reminder-m148"},
    })
    state.expect("…", ["notification.cancel.latest", "notification.schedule"])
    return state


@pytest.mark.parametrize(
    ("title", "setting", "said", "due"),
    [
        # DEV-F v4q F-w45-t3: the App had set «a 25-minute countdown for the garlic knots»; the plan's restatement.
        ("countdown for the garlic knots", "and one for the garlic knots",
         "Change the garlic knots countdown to 12 minutes.", "in 12 minutes"),
        ("temporizador de la pizza", "pon un temporizador de 20 minutos para la pizza",
         "Cambia el temporizador de la pizza a 8 minutos.", "en 8 minutos"),
        ("alarma", "ponme una alarma en media hora", "mejor que sea de 45 minutos", "en 45 minutos"),
    ],
)
def test_a_timer_moved_to_a_new_length_rings_that_long_from_now(title: str, setting: str, said: str, due: str) -> None:
    state = _timer_state(title, NOW + timedelta(minutes=25), setting)
    moved = state.retimed_notification(said, now=NOW, zone=LOCAL, moving=True)
    assert moved is not None and moved.schedule_arguments == {"dueUtc": due, "kind": "alarm", "title": title}
    assert sidecar._retimed_step_arguments("notification.cancel.latest", moved, CANCEL_LATEST) == {"kind": "alarm"}


@pytest.mark.parametrize(
    ("title", "setting", "said", "kind"),
    [
        # A length counted from another moment is a shift, not the new length.
        ("countdown for the pizza", "gimme a 25 minute countdown", "Move the pizza countdown 10 minutes later.",
         "alarm"),
        # An alarm set at a clock is no timer.
        ("alarma", "ponme una alarma a las 7", "cámbiala, que sean 20 minutos", "alarm"),
        # A reminder is not moved to a length here.
        ("tomar un descanso", "remind me en 45 minutes to take a break", "make the break reminder 20 minutes", "reminder"),
    ],
)
def test_no_new_length(title: str, setting: str, said: str, kind: str) -> None:
    state = _timer_state(title, NOW + timedelta(minutes=25), setting, kind)
    assert state.retimed_notification(said, now=NOW, zone=LOCAL, moving=True) is None


@pytest.mark.parametrize(
    ("said", "kind"),
    [
        ("Change the garlic knots countdown to 12 minutes.", {"kind": "alarm"}),
        ("cancela la cuenta regresiva", {"kind": "alarm"}),
        ("cancel the last timer", {"kind": "alarm"}),  # unchanged
        ("cancela el último recordatorio", {"kind": "reminder"}),  # unchanged
    ],
)
def test_a_countdown_is_a_timer_to_cancel(said: str, kind: dict) -> None:
    assert sidecar._ground_explicit_arguments("notification.cancel.latest", said, CANCEL_LATEST) == kind
