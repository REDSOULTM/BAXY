"""M165 (2026-10-05, App runs v4y-devF, v4y-devG, v4y-devH, v4y-devI): the reminders whose decision was right and whose
data was lost.

The window runs a conversation in one session, so its history is what BAXY really published in that run. Row by row:

* H-s047 «¿me podrías poner una alarma una hora antes de las 9?» → «¿A qué hora específica…?». ``said_advance`` (M143)
  reads it; the turn ran at 20:52, when the next 9 (D61) is 21:00 and an hour before it had passed, so the moment was
  asked back. Fixed: an hour said without its part of the day nor a day is the next time it comes whose advance is still
  ahead (at 20:52 the 9 of tomorrow morning, rung at 8).
* I-w20-t3 «tambien tengo una reunion a las 9, recuerdamelo 15 minutos antes de eso» (the neighbour M152 reported):
  ``anchored_offset_request`` counted «eso» from BAXY's last answer (08:00 → 07:45), not from the 9 the message said.
  Fixed: a message whose own clock ``said_advance`` reads counts from it.
* I-s008 «set an alarm for 6 to get up for my run, cheers» → «When would you like the alarm to go off…?». M155's reader
  reads «at 6» (the M155 + M156 merge is intact), but the literal check of the arguments dropped a clock the person
  never spelled «at 6», and the extraction asked. Fixed: the hour reader's clock is the reader's, like a repetition's.
* G-w19-t4 «pues salgo sobre las 6 de la tarde, así que calcula desde ahí» → 18:00, titled with the answer. The decider
  got 17:40 («Recuérdame en 5:40 de la tarde.»), but that request says nothing it is for and no reader reads «en 5:40»,
  so the readers fell back on the person's message, whose clock is the departure. In the lived run t3 asked «¿Te
  gustaría que te lo recuerde en ese momento?», not when, so M148's count did not run either. Fixed: a question about
  the request that offers no clock of its own is answered like one asking when, and a decided request that says only
  the order and its moment does not stand over the count (same moment, which says what it is for).
* F-w48-t4 «órale, pues recuérdame eso el domingo a las 3 de la tarde» → titled «Recuérdame el domingo a las 3 de la
  tarde.». In v4y the weather service failed on every turn, so no reply advised the umbrella M148 points at (with the
  conversation as written it still does). Fixed: with nothing pointed at, the order repeated is no title; what to remind
  is asked.

Every phrasing beyond the rows is our own; clocks are fixed where the result depends on them.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind.semantic import dialogue, temporal
from baxy_mind.semantic.arguments import _canonical_due_utc
from baxy_mind.semantic.catalog import GameCatalogIndex
from baxy_mind.semantic.decider import ContextDecision
from baxy_mind.semantic.dialogue import DialogueState
from test_c03_m148_avisos_eso_y_cuentas import (
    REMINDER, SCHEDULE, W19, W48, _arguments, _history, _local, _tool, _turn,
)

LOCAL = timezone(timedelta(hours=-3))
# Sunday 4 October 2026, 20:52 in Chile: when v4y ran H-s047.
RUN = datetime(2026, 10, 4, 20, 52, tzinfo=LOCAL)


def _normalized(text: str, due: str | None = None, *, now: datetime = RUN) -> dict | None:
    """The alarm the readers read from ``text`` (or with ``due`` as its moment), normalized at ``now``."""

    raw = sidecar._explicit_arguments_from_evidence("notification.schedule", text, (), GameCatalogIndex())
    assert raw is not None
    raw = raw if due is None else {**raw, "dueUtc": due}
    return sidecar._normalize_grounded_operation_arguments("notification.schedule", raw, text, now_utc=now, said=text)


def _rings(text: str, due: str | None = None, *, now: datetime = RUN) -> datetime | None:
    normalized = _normalized(text, due, now=now)
    return None if normalized is None else _local(normalized["dueUtc"])


class _AskOnly:
    """The arguments step with no extraction: only the question for what is missing is the model's."""

    def __init__(self) -> None:
        self.asked: list[tuple[str, ...]] = []

    def extract_direct_arguments(self, *_a, **_k):
        raise AssertionError("the readers had the arguments")

    def formulate_missing_argument_question(self, _objective, _context, _tool, fields, **_k):
        self.asked.append(tuple(fields))
        return "¿Qué quieres que te recuerde?"


def _asked(operation: str, objective: str, said: list[str], decided: dict[str, Any] | None = None,
           schema: dict[str, Any] = SCHEDULE) -> tuple[dict | None, str, list[tuple[str, ...]]]:
    if decided is not None:
        sidecar._remember_decided_arguments(objective, (operation,), tuple(decided.items()))
    model = _AskOnly()
    arguments_, question = sidecar._direct_arguments_result(
        {"operation": operation, "text": objective, "history": _history(said)},
        llm=model, tool=_tool(operation, schema), dialogue_state=DialogueState(),
    )
    return arguments_, question, model.asked


# ------------------------------------------------------------------ 1. an hour before the 9 said (H-s047)

H047 = "¿me podrías poner una alarma una hora antes de las 9?"


def test_h_s047_an_hour_before_the_next_nine_whose_hour_is_still_ahead() -> None:
    # At 20:52 the 21:00 alarm's hour has passed: the 9 of tomorrow morning, at 8.
    assert _rings(H047) == datetime(2026, 10, 5, 8, 0, tzinfo=LOCAL)
    # At noon, tonight's 9: at 20:00; at 7:00, this morning's: at 8:00; at 8:30, tonight's again.
    assert _rings(H047, now=RUN.replace(hour=12, minute=0)) == RUN.replace(hour=20, minute=0)
    assert _rings(H047, now=RUN.replace(hour=7, minute=0)) == RUN.replace(hour=8, minute=0)
    assert _rings(H047, now=RUN.replace(hour=8, minute=30)) == RUN.replace(hour=20, minute=0)


def test_h_s047_the_readers_have_it_at_any_hour() -> None:
    arguments_, question = _arguments("notification.schedule", H047, [H047])
    due = _local(arguments_["dueUtc"])
    assert question == "" and (due.hour, due.minute) in {(8, 0), (20, 0)}


@pytest.mark.parametrize(
    ("text", "now", "rings"),
    [
        ("set an alarm an hour before 7", RUN.replace(hour=18, minute=30), datetime(2026, 10, 5, 6, 0, tzinfo=LOCAL)),
        ("ponme una alarma media hora antes de las 10", RUN.replace(hour=9, minute=45), RUN.replace(hour=21, minute=30)),
    ],
)
def test_the_next_moment_whose_advance_is_ahead(text: str, now: datetime, rings: datetime) -> None:
    assert _rings(text, now=now) == rings


@pytest.mark.parametrize(
    "text",
    [
        # Its part of the day said: that moment is the one the person placed; it has passed and is asked.
        "ponme una alarma una hora antes de las 9 de la noche",
        # A day said: the same.
        "ponme una alarma hoy una hora antes de las 9",
    ],
)
def test_a_placed_moment_whose_advance_passed_is_still_asked(text: str) -> None:
    assert temporal.said_advance(text) is not None
    assert _normalized(text) is None


def test_an_alarm_at_nine_is_still_the_next_nine() -> None:
    # D61: at 20:52 the next 9 is 21:00.
    due = _canonical_due_utc("a las 9", "pon una alarma a las 9", now_utc=RUN)
    assert _local(due) == RUN.replace(hour=21, minute=0)


@pytest.mark.parametrize("text", ["ponme una alarma una hora antes", "remind me half an hour before"])
def test_an_advance_from_no_moment_is_still_asked(text: str) -> None:
    assert temporal.said_advance(text) is None
    assert temporal.anchored_offset_request(text, None, []) is None
    with pytest.raises(AssertionError):
        _arguments("notification.schedule", text, [text])


# ------------------------------------------------------------------ 2. «antes de eso» of the clock the message said

I20 = [
    "ponme una alrama pa manana a las 7 que tengo que levantarme tenprano",
    "He programado la alarma para mañana a las 07:00.",
    "no, mejro a las 8",
    "He cambiado la alarma de mañana a las 08:00.",
    "tambien tengo una reunion a las 9, recuerdamelo 15 minutos antes de eso",
]


@pytest.mark.parametrize(
    ("text", "reply"),
    [
        (I20[-1], I20[-2]),
        ("tengo dentista a las 4, avísame media hora antes de eso", "Listo, alarma a las 7:00."),
        ("I have a call at 3pm, remind me ten minutes before that", "Done, your alarm is set for 7:00."),
    ],
)
def test_eso_is_the_clock_the_message_said(text: str, reply: str) -> None:
    assert temporal.said_advance(text) is not None
    assert temporal.anchored_offset_request(text, reply, [reply]) is None


def test_i_w20_t3_fifteen_minutes_before_the_meeting() -> None:
    # The decider's restatement stands and is read as it says.
    restated = "Recuérdame mañana a las 8:45 que tengo una reunión a las 9."
    result = _turn(I20, ContextDecision(restated, "action", ("notification.schedule",), ""))
    assert result["kind"] == "action" and result["objective"] == restated
    arguments_, question = _arguments("notification.schedule", restated, I20)
    assert question == "" and (_local(arguments_["dueUtc"]).hour, _local(arguments_["dueUtc"]).minute) == (8, 45)
    # Read from the message's own 9 at 20:52: the 9 of tomorrow morning, less 15 minutes.
    assert _rings("pon una alarma, tengo una reunion a las 9, 15 minutos antes", "a las 9") == datetime(
        2026, 10, 5, 8, 45, tzinfo=LOCAL)


def test_eso_after_a_moment_baxy_gave_is_still_counted_from_it() -> None:
    assert temporal.anchored_offset_request(
        "ponme una alarma media hora antes de eso", "En Madrid son las 10:00.", [],
    ) == "ponme una alarma a las 09:30"


# ------------------------------------------------------------------ 3. an alarm «for 6» with what it is for (I-s008)

S008 = "set an alarm for 6 to get up for my run, cheers"


@pytest.mark.parametrize(
    "text",
    [S008, "pon una alarma para 7 para ir al gimnasio", "set an alarm for 5 so I can catch the early train",
     "set an alarm for 8"],
)
def test_the_alarm_for_an_hour_reaches_the_operation(text: str) -> None:
    hour = int(temporal.alarm_for_hour(temporal._fold(text)).split()[-1])
    arguments_, question = _arguments("notification.schedule", text, [text])
    due = _local(arguments_["dueUtc"])
    assert question == "" and arguments_["kind"] == "alarm"
    # D61: the next time that hour comes, morning or evening — at 20:52, tomorrow morning's.
    assert due.hour % 12 == hour % 12 and due.minute == 0
    assert _rings(text) == datetime(2026, 10, 5, hour, 0, tzinfo=LOCAL)


@pytest.mark.parametrize("text", ["set an alarm for 6 to 7", "set an alarm for 6 to get up tomorrow"])
def test_no_hour_read_is_still_not_read(text: str) -> None:
    assert temporal.alarm_for_hour(temporal._fold(text)) is None
    with pytest.raises(AssertionError):
        _arguments("notification.schedule", text, [text])


# ------------------------------------------------------------------ 4. «salgo sobre las 6» after another question

W19_LIVED = [
    "qué tal está el tráfico para ir al aeropuerto",
    "No se pudo consultar el tráfico ahora mismo; puedo abrirlo en tu navegador.",
    "¿y en una hora estará mejor?",
    "No se pudo consultar ahora si el tráfico es mejor en una hora. Puedo abrirlo en tu navegador.",
    "vale, pues recuérdamelo veinte minutos antes de salir",
    "¿Te gustaría que te lo recuerde en ese momento?",
    "pues salgo sobre las 6 de la tarde, así que calcula desde ahí",
]


@pytest.mark.parametrize("said", [W19_LIVED, W19], ids=["lived-v4y", "written"])
def test_g_w19_t4_the_decided_moment_without_its_purpose_is_counted(said: list[str]) -> None:
    result = _turn(said, ContextDecision("Recuérdame en 5:40 de la tarde.", "action", ("notification.schedule",), ""))
    assert result["kind"] == "action" and result["objective"] == "recuérdame salir a las 17:40"
    schema = SCHEDULE if result["operation"] == "notification.schedule" else REMINDER
    arguments_, question = _arguments(result["operation"], result["objective"], said, schema=schema)
    assert question == "" and arguments_["title"] == "salir"
    assert (_local(arguments_["dueUtc"]).hour, _local(arguments_["dueUtc"]).minute) == (17, 40)


@pytest.mark.parametrize(
    ("text", "pending", "reply", "rewritten"),
    [
        ("I'm heading out at 7pm, so work it out from there", "ok, remind me ten minutes before I leave",
         "Do you want me to remind you then?", "remind me at 18:50 before I leave"),
        ("salgo a las 6 de la tarde", "avísame media hora antes de salir", "¿Quieres que te lo recuerde?",
         "recuérdame salir a las 17:30"),
    ],
)
def test_a_question_that_offers_no_clock_is_answered_by_the_moment(
    text: str, pending: str, reply: str, rewritten: str,
) -> None:
    assert temporal.answered_advance_request(text, pending, reply, now=RUN) == rewritten


@pytest.mark.parametrize(
    ("text", "pending", "reply"),
    [
        # BAXY offered a clock: the answer is the notification's own.
        ("no, a las 5:30", "recuérdamelo veinte minutos antes de salir", "¿Quieres que te avise a las 6?"),
        ("salgo a las 6 de la tarde", "avísame media hora antes de salir", "¿Te aviso a las 5?"),
        # BAXY asked nothing.
        ("salgo a las 6", "recuérdamelo veinte minutos antes de salir", "Vale, lo anoto."),
    ],
)
def test_no_answered_advance_still(text: str, pending: str, reply: str) -> None:
    assert temporal.answered_advance_request(text, pending, reply, now=RUN) is None


@pytest.mark.parametrize(
    ("request_", "only"),
    [
        ("Recuérdame en 5:40 de la tarde.", True),
        ("Recuérdame el domingo a las 3 de la tarde.", True),
        ("Remind me", True),
        ("Recuérdame salir a las 17:40 para ir al aeropuerto.", False),
        ("Remind me at 7:40pm tonight about the Arsenal match.", False),
        ("Voy a estar en Zapopan el domingo.", False),
    ],
)
def test_a_request_with_only_the_order_and_its_moment(request_: str, only: bool) -> None:
    assert dialogue.says_no_reminder_title(request_) is only


# ------------------------------------------------------------------ 5. «recuérdame eso» with nothing pointed at

W48_LIVED = [
    "oye baxy, ¿qué onda con el clima en Guadalajara hoy? es que voy a salir al rato",
    "No puedo decirte el clima porque el servicio no respondió y no se leyó ninguna predicción para Guadalajara hoy.",
    "¿y pa'l domingo cómo pinta?",
    "No pude obtener el pronóstico del clima para Guadalajara porque el servicio meteorológico no respondió.",
    "ah no, perdón, me equivoqué, el domingo voy a estar en Zapopan, no en Guadalajara",
    "No pude predecir el tiempo en Zapopan para el domingo porque el servicio meteorológico no respondió y no se leyó "
    "ninguna previsión.",
    "órale, pues recuérdame eso el domingo a las 3 de la tarde",
]


def test_f_w48_t4_with_nothing_pointed_at_what_to_remind_is_asked() -> None:
    restated = "Recuérdame el domingo a las 3 de la tarde."
    arguments_, question, asked = _asked(
        "notification.schedule", restated, W48_LIVED,
        decided={"dueUtc": "2026-10-11T15:00:00-06:00", "kind": "reminder", "title": restated},
    )
    assert arguments_ is None and question and asked == [("title",)]


def test_f_w48_t4_as_written_is_still_the_umbrella() -> None:
    restated = "Recuérdame el domingo a las 3 de la tarde."
    arguments_, question, asked = _asked(
        "notification.schedule", restated, W48,
        decided={"dueUtc": "2026-10-11T15:00:00-06:00", "kind": "reminder", "title": restated},
    )
    assert question == "" and asked == [] and arguments_["title"] == "lleva paraguas"


@pytest.mark.parametrize(
    ("text", "reply", "title"),
    [
        ("ok remind me about that tomorrow at 7", "I couldn't read the forecast; the weather service did not answer.",
         "Remind me tomorrow at 7"),
        ("recuérdamelo mañana a las 8", "No pude leer el pronóstico.", "Recordatorio"),
    ],
)
def test_the_order_repeated_is_no_title(text: str, reply: str, title: str) -> None:
    assert dialogue.pointed_reminder_unsaid(text, reply, title)


@pytest.mark.parametrize(
    ("text", "reply", "title"),
    [
        # A title that says something stays (M148: nothing pointed at is invented).
        (W48_LIVED[-1], W48_LIVED[-2], "Voy a estar en Zapopan el domingo."),
        # BAXY advised something: that is the title (M148).
        (W48[-1], W48[-2], "Recuérdame el domingo a las 3 de la tarde."),
        # The reminder says what it is for.
        ("recuérdame mañana a las 8 llamar a mamá", "No pude leer el pronóstico.", "Recuérdame"),
    ],
)
def test_a_title_said_or_pointed_is_not_asked(text: str, reply: str, title: str) -> None:
    assert not dialogue.pointed_reminder_unsaid(text, reply, title)
