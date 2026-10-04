"""M152 (2026-10-04, App runs v4s-devF, v4s-devG, v4s-devH): the notice at a length from a moment the conversation said,
or at a length from now.

The window runs a conversation in one session, so its history is what BAXY really published in that run, not the
written one. Row by row, where the hour was lost:

* F-w33-t2, H-w44-t2, F-w05-t3, F-w18-t3, F-w34-t4: the moment never reached the conversation (the search found no
  kick-off time, Outlook was not set up, the council tax file was not found, the recipe found had no minutes for
  «pochar»). Asking is right; nothing is fixed here, and the tests below hold that no moment is invented. With the
  conversation as written, the readers of M84/M110/M113 already count the moment (also held below).
* G-w42-t2: the search answered another game («Wednesday, October 21 at 10:00 PM ET»); half an hour before it, as said,
  is what was set. Nothing to fix here.
* H-w39-t4 «ah ya. oye, pon un recordatorio para cargarla en una hora», restated «Pon un recordatorio en una hora para
  cargarla.» → «¿Cuándo quieres que se ejecute este recordatorio?»: the reader of a reminder with its delay first and
  then what it is for read only «ponme» and «set»; the extraction model asked. Fixed: it reads every order the
  shape with what it is for first reads.
* G-w19-t4 «pues salgo sobre las 6 de la tarde, así que calcula desde ahí» → set at 21:20: lost one turn before.
  G-w19-t3 «vale, pues recuérdamelo veinte minutos antes de salir» was restated «Recuérdame en 20 minutos que tengo que ir al
  aeropuerto.» and set 20 minutes from then, so t4 answered no question and M148 never ran. Fixed: M110's guard (a time
  nobody said is asked) also covers a length counted from an unplaced moment that the restatement made a delay from now.
* F-w55-t2: the turn before was set by ``reminder.create`` (not ``notification.schedule``), which the dialogue state
  does not keep for M113's move; reported, not fixed here.

Every phrasing beyond the rows is our own.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind.semantic import temporal
from baxy_mind.semantic.arguments import _canonical_due_utc, _explicit_relative_reminder_arguments
from baxy_mind.semantic.decider import ContextDecision
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic.dialogue import DialogueState
from test_c03_m148_avisos_eso_y_cuentas import (
    NOW, OPERATIONS, REMINDER, SCHEDULE, W19, _arguments, _Decider, _history, _local, _tool,
)


class _Asking(_Decider):
    """The decider of a whole turn whose clarification, when the code turns it into one, is written by the model."""

    def clarify_after_turn_failure(self, *_a, **_k):
        return "¿A qué hora sales?"


def _turn(said: list[str], decision: ContextDecision) -> dict:
    tools = {name: _tool(name) for name in OPERATIONS}
    return sidecar._prepare_turn_result(
        {"id": "m152", "text": said[-1], "history": _history(said)},
        llm=_Asking(decision), planner_catalog=PlannerCatalog(list(tools.values())), encoder=lambda _t: (),
        tool_by_name=tools, dialogue_state=DialogueState(),
    )


def _delay(literal: str) -> timedelta:
    """How long from the fixed clock the reader's literal rings."""

    due = _canonical_due_utc(literal, literal, now_utc=NOW)
    assert due is not None
    return _local(due) - NOW


# ------------------------------------------------------------------ 1. a reminder at a length from now (H-w39-t4)

H39 = [
    "oye cuanta pila le queda a la computadora",
    "La batería tiene el 99% de carga y no está cargando porque el equipo está conectado a la corriente.",
    "y cuanto espacio en disco",
    "Tienes 31.84 GB de espacio libre en el disco.",
    "ah y ya quedo conectado el internet?",
    "Sí, el PC está conectado a internet.",
    "ah ya. oye, pon un recordatorio para cargarla en una hora",
]


def test_h_w39_t4_a_reminder_in_one_hour_is_read_not_asked() -> None:
    restated = "Pon un recordatorio en una hora para cargarla."
    result = _turn(H39, ContextDecision(restated, "action", ("notification.schedule",), ""))
    assert result["kind"] == "action" and result["objective"] == restated
    arguments_, question = _arguments("notification.schedule", restated, H39)
    assert question == "" and arguments_["title"] == "cargarla" and arguments_["kind"] == "reminder"
    assert _explicit_relative_reminder_arguments(restated)["dueUtc"] == "en una hora"


@pytest.mark.parametrize(
    ("objective", "due", "title", "minutes"),
    [
        ("Pon un recordatorio en una hora para cargarla.", "en una hora", "cargarla", 60),
        ("crea un recordatorio en media hora para sacar la ropa", "en media hora", "sacar la ropa", 30),
        ("programa un recordatorio en 20 minutos para llamar a mamá", "en 20 minutos", "llamar a mamá", 20),
        ("create a reminder in 10 minutes to check the oven", "in 10 minutes", "check the oven", 10),
    ],
)
def test_a_reminder_asked_for_with_its_delay_first(objective: str, due: str, title: str, minutes: int) -> None:
    assert _explicit_relative_reminder_arguments(objective) == {"dueUtc": due, "title": title}
    assert _delay(due) == timedelta(minutes=minutes)
    arguments_, question = _arguments("reminder.create", objective, [objective], schema=REMINDER)
    assert question == "" and arguments_["title"] == title


@pytest.mark.parametrize(
    ("objective", "expected"),
    [
        # Unchanged: «ponme» and «set» were read before.
        ("Ponme un recordatorio en una hora para cargarla.", {"dueUtc": "en una hora", "title": "cargarla"}),
        ("Set a reminder in 20 minutes to charge it.", {"dueUtc": "in 20 minutes", "title": "charge it"}),
        # No moment: nothing to read.
        ("pon un recordatorio para cargarla", None),
        ("crea un recordatorio para la reunión", None),
    ],
)
def test_the_same_order_without_a_new_shape_is_unchanged(objective: str, expected: dict | None) -> None:
    assert _explicit_relative_reminder_arguments(objective) == expected


def test_a_clock_first_reminder_reads_as_before() -> None:
    arguments_, question = _arguments(
        "reminder.create", "pon un recordatorio a las 9 para la reunión",
        ["pon un recordatorio a las 9 para la reunión"],
        schema=REMINDER,
    )
    assert question == "" and arguments_["title"] == "la reunión" and _local(arguments_["dueUtc"]).hour == 9


# ------------------------------------------------------------------ 2. a length before a moment nobody placed (G-w19)

def test_g_w19_t3_twenty_minutes_before_leaving_is_not_twenty_minutes_from_now() -> None:
    restated = "Recuérdame en 20 minutos que tengo que ir al aeropuerto."  # the App's v4s
    result = _turn(W19[:5], ContextDecision(restated, "action", ("notification.schedule",), ""))
    assert result["kind"] == "clarify" and result["question"] == "¿A qué hora sales?"


def test_g_w19_t4_then_counts_from_the_answered_moment() -> None:
    said = [*W19[:5], "¿A qué hora sales?", W19[-1]]
    restated = "Recuérdame a las 21:20 para ir al aeropuerto."  # the App's v4s restatement of t4
    result = _turn(said, ContextDecision(restated, "action", ("notification.schedule",), ""))
    assert result["kind"] == "action" and result["objective"] == "recuérdame salir a las 17:40"
    schema = SCHEDULE if result["operation"] == "notification.schedule" else REMINDER
    arguments_, question = _arguments(result["operation"], result["objective"], said, schema=schema)
    assert question == "" and (_local(arguments_["dueUtc"]).hour, _local(arguments_["dueUtc"]).minute) == (17, 40)


@pytest.mark.parametrize(
    ("text", "restated"),
    [
        ("vale, pues recuérdamelo veinte minutos antes de salir",
         "Recuérdame en 20 minutos que tengo que ir al aeropuerto."),
        ("remind me half an hour before I leave", "Remind me in 30 minutes to leave."),
        ("avísame una hora antes de que empiece el partido", "Avísame en una hora que empieza el partido."),
        ("ponme una alarma 15 minutos antes de irme al gym", "Pon una alarma en 15 minutos para ir al gimnasio."),
        ("set a reminder for ten minutes after the meeting ends", "Set a reminder in 10 minutes."),
    ],
)
def test_a_length_from_an_unplaced_moment_restated_as_a_delay(text: str, restated: str) -> None:
    assert temporal.advance_restated_as_delay(text, restated)


@pytest.mark.parametrize(
    ("text", "restated"),
    [
        # The message says the moment: M137 counts from it.
        ("recuérdamelo veinte minutos antes de salir, salgo a las 6", "Recuérdame en 20 minutos que salgo."),
        # The message's own delay from now.
        ("recuérdame en 20 minutos sacar la ropa", "Recuérdame en 20 minutos sacar la ropa."),
        # The decider wrote a clock (D58: it may have counted it from the conversation).
        ("vale, pues recuérdamelo veinte minutos antes de salir", "Recuérdame a las 17:40 para ir al aeropuerto."),
        # Another length: not the advance read as a delay.
        ("vale, pues recuérdamelo veinte minutos antes de salir", "Recuérdame en 40 minutos que tengo que salir."),
        # The restatement keeps the count.
        ("vale, pues recuérdamelo veinte minutos antes de salir", "Recuérdame 20 minutos antes de salir."),
        # «después» alone counts from nothing said: it may be from now.
        ("avísame media hora después", "Avísame en media hora."),
        ("remind me 20 minutes later", "Remind me in 20 minutes."),
        # No count at all.
        ("pon un recordatorio antes de que se me vaya de la cabeza", "Pon un recordatorio en 5 minutos."),
    ],
)
def test_no_advance_restated_as_a_delay(text: str, restated: str) -> None:
    assert not temporal.advance_restated_as_delay(text, restated)


def test_a_delay_the_person_said_is_still_set() -> None:
    said = ["qué tal el tráfico", "Hay bastante tráfico.", "recuérdame en 20 minutos salir para el aeropuerto"]
    restated = "Recuérdame en 20 minutos salir para el aeropuerto."
    result = _turn(said, ContextDecision(restated, "action", ("notification.schedule",), ""))
    assert result["kind"] == "action" and result["objective"] == restated


def test_before_that_with_the_moment_in_the_reply_is_counted_from_it() -> None:
    said = [
        "a que hora juega chile el martes",
        "Chile juega el martes a las 21:00 contra Perú en el Estadio Nacional.",
        "recuerdame una hora antes de eso",
    ]
    result = _turn(said, ContextDecision("Recuérdame en una hora.", "action", ("notification.schedule",), ""))
    assert result["kind"] == "action" and result["objective"] == "recuerdame el martes a las 20:00"


# ------------------------------------------------------------------ 3. no moment in the conversation, none invented

# The conversations as the App lived them in v4s (BAXY's own published answers).
LIVED = {
    "F-w33-t2": [
        "What time's the Arsenal match on Saturday, do you know?",
        "Arsenal's match on Saturday, December 12, is set to move to the preceding Thursday due to Bournemouth's "
        "Europa League fixture. I could not find the specific new time for the relocated game.",
        "Set an alarm for half an hour before kick-off, then",
    ],
    "H-w44-t2": [
        "what time does the arsenal match kick off tonight",
        "I could not find the kick-off time for tonight's Arsenal match.",
        "remind me twenty minutes before that",
    ],
    "F-w05-t3": [
        "baxy leeme el ultimo correo porfa",
        "No puedo leer el correo porque Outlook no está configurado en este equipo.",
        "dejale escrito un wsp a la paula que voy pero llego tipo 7 y media, no lo mandes eso si",
        "Se escribió el mensaje en WhatsApp a Paula diciendo que llegas a las siete y media, pero no se confirmó si se "
        "envió o no.",
        "y ponme un recordatorio una hora antes de la junta",
    ],
}


@pytest.mark.parametrize("row", sorted(LIVED))
def test_with_no_moment_lived_the_question_stands(row: str) -> None:
    said = LIVED[row]
    result = _turn(said, ContextDecision(said[-1], "clarify", (), ""))
    assert result["kind"] == "clarify"


# The conversations as written: the moment is there, and the readers already count it.
WRITTEN = [
    (["What time's the Arsenal match on Saturday, do you know?",
      "Arsenal host Brentford on Saturday, kick-off 15:00 at the Emirates.",
      "Set an alarm for half an hour before kick-off, then"], (14, 30)),
    (["what time does the arsenal match kick off tonight", "Kick-off is at 8pm.",
      "remind me twenty minutes before that"], (19, 40)),
    (["baxy leeme el ultimo correo porfa",
      "Es de Paula Rojas, «Junta trabajo»: propone juntarse el jueves a las 19:00 en el café de Plaza Vergara para "
      "terminar la presentación.",
      "dejale escrito un wsp a la paula que voy pero llego tipo 7 y media, no lo mandes eso si",
      "Listo, le dejé escrito a Paula: «Voy, pero llego tipo 7 y media». No lo envié.",
      "y ponme un recordatorio una hora antes de la junta"], (18, 0)),
]


@pytest.mark.parametrize(("said", "clock"), WRITTEN)
def test_with_the_moment_written_it_is_counted(said: list[str], clock: tuple[int, int]) -> None:
    result = _turn(said, ContextDecision(said[-1], "clarify", (), ""))
    assert result["kind"] == "action"
    schema = SCHEDULE if result["operation"] == "notification.schedule" else REMINDER
    arguments_, question = _arguments(result["operation"], result["objective"], said, schema=schema)
    assert question == "" and (_local(arguments_["dueUtc"]).hour, _local(arguments_["dueUtc"]).minute) == clock


def test_the_count_without_conversation_still_asks() -> None:
    result = _turn(
        ["remind me twenty minutes before that"],
        ContextDecision("remind me twenty minutes before that", "clarify", (), ""),
    )
    assert result["kind"] == "clarify"



@pytest.mark.parametrize(
    ("text", "restated", "kind"),
    [
        # The same phrases alone, as a first message: the readers decide them as before.
        ("recuérdame veinte minutos antes de salir", "Recuérdame en 20 minutos que tengo que salir.", "clarify"),
        ("pon un recordatorio en una hora para cargar el celular",
         "Pon un recordatorio en una hora para cargar el celular.", "action"),
    ],
)
def test_the_same_phrase_without_conversation_is_unchanged(text: str, restated: str, kind: str) -> None:
    result = _turn([text], ContextDecision(restated, "action", ("notification.schedule",), ""))
    assert result["kind"] == kind
