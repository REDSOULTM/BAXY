"""Uso real 2026-09-23 (MASSIVE es/en replay, family calendar/alarms/reminders): the person's agenda
went to a clarification, a web search, a knowledge reply or «eso no lo hago».

- What the person has planned is their own data: «qué tengo por venir», «tengo algo programado para el
  cuatro de julio de este año», «cuál es mi horario para el día», «cuándo es mi brunch con Jennifer»
  are read from the calendar over the window said, or the next thirty days when none is said.
- An event is put on the agenda with what was said (a start without an end lasts an hour, a marked day
  takes the whole day); only a time never said, am/pm, or a repetition the calendar cannot hold is asked.
  A daily repetition is a repeating reminder.
- «pon alerta …», «activa alarma …», «despiértame … para …» schedule the alarm; «establece un
  recordatorio sobre …», «tengo una reunión … envíame un recordatorio» schedule the reminder; «no dejes
  que me olvide de …», «please alert me», «no me despiertes mañana» ask what is missing; removing an
  event from the calendar is a plain limit.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic.normalize import fold
from baxy_mind.semantic.notes import agenda_event_request, agenda_read_request, stated_event_reminder
from baxy_mind.semantic.patterns import (
    known_unsupported_effect_request,
    operation_domain_is_grounded,
    resolve_explicit_clarification_intent,
    resolve_explicit_effects,
)
from baxy_mind.semantic.temporal import UPCOMING_DAYS, agenda_window, spoken_date, spoken_window
from test_c03_pointless_questions import _NoEvidence, _tool
from test_c03_unknown_looked_up import _KnowledgeLlm

OPERATIONS = (
    "calendar.event.list", "calendar.event.create", "reminder.create", "reminder.list", "notification.schedule",
    "notification.list", "notification.cancel.at", "notification.cancel.latest", "task.create", "task.list",
    "note.create", "web.search", "media.play.youtube", "media.play.query", "system.time",
)
# Chile's civil offset on the day of the replay: every window and instant is local civil time.
LOCAL = timezone(timedelta(hours=-3))
NOW = datetime(2026, 9, 23, 22, 15, tzinfo=LOCAL)  # a Wednesday evening
NAIVE_NOW = NOW.replace(tzinfo=None)


def _utc(local: str) -> str:
    """«2026-09-24 09:00» local → its UTC wire string."""

    return datetime.fromisoformat(local).replace(tzinfo=LOCAL).astimezone(timezone.utc).isoformat().replace(
        "+00:00", "Z",
    )


# ------------------------------------------------------------------ the agenda, read


@pytest.mark.parametrize(
    ("text", "start", "end"),
    [
        ("tengo algo programado para el cuatro de julio de este año", "2026-07-04 00:00", "2026-07-05 00:00"),
        ("que tengo que hacer esta semana", "2026-09-21 00:00", "2026-09-28 00:00"),
        ("que tengo yo planeado para esta semana", "2026-09-21 00:00", "2026-09-28 00:00"),
        ("cuánto tiempo durará mi reunión para comer el martes", "2026-09-29 00:00", "2026-09-30 00:00"),
        ("cuál es mi horario para el día", "2026-09-23 00:00", "2026-09-24 00:00"),
        ("tengo algo planeado para el veintiuno", "2026-10-21 00:00", "2026-10-22 00:00"),
        ("mi horario para el siete de julio está completamente abierto", "2027-07-07 00:00", "2027-07-08 00:00"),
        ("que reunión está programada para hoy", "2026-09-23 00:00", "2026-09-24 00:00"),
        ("cómo será mi próxima semana", "2026-09-28 00:00", "2026-10-05 00:00"),
        ("hay algún evento planeado para los próximos tres meses", "2026-09-23 22:15", "2026-12-23 22:15"),
        ("dime mi horario para esta tarde", "2026-09-23 12:00", "2026-09-23 20:00"),
        ("que eventos hay la semana que viene", "2026-09-28 00:00", "2026-10-05 00:00"),
        ("cuales son mis planes para el mes de mayo", "2027-05-01 00:00", "2027-06-01 00:00"),
        ("cual es el plan hoy", "2026-09-23 00:00", "2026-09-24 00:00"),
        ("que hay hoy", "2026-09-23 00:00", "2026-09-24 00:00"),
        ("do i have anything set for the fourth of july this year", "2026-07-04 00:00", "2026-07-05 00:00"),
        ("what do i have to do this week", "2026-09-21 00:00", "2026-09-28 00:00"),
        ("what are my plans for the month of may", "2027-05-01 00:00", "2027-06-01 00:00"),
        ("tell me my schedule for later this afternoon", "2026-09-23 12:00", "2026-09-23 20:00"),
        ("what's my schedule like today", "2026-09-23 00:00", "2026-09-24 00:00"),
        ("do i have appointments today", "2026-09-23 00:00", "2026-09-24 00:00"),
    ],
)
def test_the_persons_agenda_is_read_over_the_window_said(text: str, start: str, end: str) -> None:
    effects = resolve_explicit_effects(text, OPERATIONS)

    assert effects is not None and effects.operations == ("calendar.event.list",)
    assert resolve_explicit_clarification_intent(text, OPERATIONS) is None
    assert operation_domain_is_grounded(text, "calendar.event.list") is True
    assert operation_domain_is_grounded(text, "calendar.event.create") is False
    assert sidecar._explicit_calendar_range_arguments(effects.evidence[0], now_utc=NOW) == {
        "startUtc": _utc(start), "endUtc": _utc(end),
    }


@pytest.mark.parametrize(
    "text",
    [
        "que tengo por venir",
        "tengo algo planeado",
        "cuándo es mi brunch con jennifer",
        "cuándo es mi próxima cita con el doctor janeiro",
        "cuáles son mis próximos tres eventos",
        "Lista mis próximos eventos del calendario",
        "próximos eventos en calendario",
    ],
)
def test_an_agenda_read_with_no_window_reads_what_is_coming(text: str) -> None:
    effects = resolve_explicit_effects(text, OPERATIONS)

    assert effects is not None and effects.operations == ("calendar.event.list",)
    # Nothing is missing: what is coming is the next thirty days (the date range was asked before).
    assert resolve_explicit_clarification_intent(text, OPERATIONS) is None
    upcoming = NOW + timedelta(days=UPCOMING_DAYS)
    assert sidecar._explicit_calendar_range_arguments(effects.evidence[0], now_utc=NOW) == {
        "startUtc": _utc("2026-09-23 22:15"), "endUtc": _utc(upcoming.strftime("%Y-%m-%d %H:%M")),
    }


@pytest.mark.parametrize(
    "text",
    [
        "tengo una cita mañana recuérdame",
        "do i have time today",
        "yo tengo una cita hoy",
        "can you give me the movie schedule",
        "habrá algún evento en el centro este fin de semana",
        "qué hay de comer hoy",
        "mi horario de trabajo es de 9 a 5",
        "dame un recordatorio veinticuatro horas antes de mi reunión del viernes con edg",
        "no tengo nada planeado",
        "añade una reunión con tom a mi calendario para las nueve de la mañana",
        "tengo algo que decirte",
    ],
)
def test_a_statement_a_public_schedule_or_a_change_is_not_an_agenda_read(text: str) -> None:
    assert agenda_read_request(text) is False
    effects = resolve_explicit_effects(text, OPERATIONS)
    assert effects is None or effects.operations != ("calendar.event.list",)


def test_what_baxy_scheduled_for_today_stays_its_own_alarm_listing() -> None:
    # AGENDA1669 H0660: «qué tengo agendado para hoy» lists the alarms and reminders BAXY scheduled.
    assert agenda_read_request("qué tengo agendado para hoy") is False
    effects = resolve_explicit_effects("qué tengo agendado para hoy", OPERATIONS)
    assert effects is not None and effects.operations == ("notification.list",)


# ------------------------------------------------------------------ dates and windows


@pytest.mark.parametrize(
    ("text", "day", "month", "year", "this_year"),
    [
        ("el cuatro de julio de este año", 4, 7, None, True),
        ("the fourth of july", 4, 7, None, False),
        ("march seven", 7, 3, None, False),
        ("april twenty", 20, 4, None, False),
        ("el 21", 21, None, None, False),
        ("el veintiuno", 21, None, None, False),
        ("on the 21st", 21, None, None, False),
        ("twenty-first of may", 21, 5, None, False),
        ("el primero de mayo de 2027", 1, 5, 2027, False),
    ],
)
def test_a_date_is_read_in_digits_or_words(text, day, month, year, this_year) -> None:
    said = spoken_date(fold(text))
    assert said is not None
    assert (said.day, said.month, said.year, said.this_year) == (day, month, year, this_year)


@pytest.mark.parametrize(
    "text",
    ["a las dos de la tarde", "el dos por ciento", "el cinco de la tarde", "dos horas", "el martes"],
)
def test_a_clock_a_quantity_or_a_weekday_is_not_a_date(text: str) -> None:
    assert spoken_date(fold(text)) is None


def test_a_date_without_its_year_is_the_next_one_and_with_it_that_one() -> None:
    today = NAIVE_NOW.date()
    assert spoken_date("el siete de julio").on_or_after(today).isoformat() == "2027-07-07"
    assert spoken_date("el siete de julio de este ano").on_or_after(today).isoformat() == "2026-07-07"
    assert spoken_date("el veintiuno").on_or_after(today).isoformat() == "2026-10-21"
    assert spoken_date("el 31").on_or_after(today).isoformat() == "2026-10-31"


def test_two_windows_are_not_one_and_no_window_is_what_is_coming() -> None:
    assert agenda_window("show events today and tomorrow", NAIVE_NOW) is None
    assert agenda_window("el lunes y el martes", NAIVE_NOW) is None
    assert spoken_window("que tengo por venir", NAIVE_NOW) is None
    assert agenda_window("que tengo por venir", NAIVE_NOW) == (NAIVE_NOW, NAIVE_NOW + timedelta(days=UPCOMING_DAYS))
    assert spoken_window("en los ultimos tres meses", NAIVE_NOW) == (datetime(2026, 6, 23, 22, 15), NAIVE_NOW)
    assert spoken_window("el fin de semana que viene", NAIVE_NOW) == (datetime(2026, 10, 3), datetime(2026, 10, 5))
    assert spoken_window("la primera semana de junio", NAIVE_NOW) == (datetime(2027, 6, 1), datetime(2027, 6, 8))


# ------------------------------------------------------------------ an event put on the agenda


@pytest.mark.parametrize(
    ("text", "title", "start", "end"),
    [
        ("añade una reunión con tom a mi calendario para las nueve de la mañana",
         "reunión con tom", "2026-09-24 09:00", "2026-09-24 10:00"),
        ("programa una reunión para el martes que viene a las once de la mañana con joan",
         "reunión con joan", "2026-09-29 11:00", "2026-09-29 12:00"),
        ("establecer una reunión con joan el sábado a las cuatro de la tarde",
         "reunión con joan", "2026-09-26 16:00", "2026-09-26 17:00"),
        ("programar una reunión con matt a las once de la mañana el jueves",
         "reunión con matt", "2026-09-24 11:00", "2026-09-24 12:00"),
        ("por favor añade práctica el cuatro de febrero en el parque del retiro a las dos de la tarde",
         "práctica en el parque del retiro", "2027-02-04 14:00", "2027-02-04 15:00"),
        ("set me a meeting next tuesday at eleven am with jesse",
         "meeting with jesse", "2026-09-29 11:00", "2026-09-29 12:00"),
        ("add a meeting at the office with brian for three p. m. on tuesday",
         "meeting at the office with brian", "2026-09-29 15:00", "2026-09-29 16:00"),
        ("pon una reunión de dos horas mañana a las 10 de la mañana", "reunión", "2026-09-24 10:00", "2026-09-24 12:00"),
        ("añade una cita de cuatro a seis de la tarde mañana", "cita", "2026-09-24 16:00", "2026-09-24 18:00"),
        ("Crea un evento llamado Revisión el domingo a las 9 de la mañana", "Revisión", "2026-09-27 09:00",
         "2026-09-27 10:00"),
    ],
)
def test_an_event_is_created_as_said_and_a_start_alone_lasts_an_hour(text, title, start, end) -> None:
    effects = resolve_explicit_effects(text, OPERATIONS)

    assert effects is not None and effects.operations == ("calendar.event.create",)
    assert resolve_explicit_clarification_intent(text, OPERATIONS) is None
    assert operation_domain_is_grounded(text, "calendar.event.create") is True
    assert operation_domain_is_grounded(text, "calendar.event.list") is False
    assert sidecar._explicit_calendar_event_arguments(effects.evidence[0], now_utc=NOW) == {
        "title": title, "startUtc": _utc(start), "endUtc": _utc(end),
    }


@pytest.mark.parametrize(
    ("text", "title", "start", "end"),
    [
        ("mark april twenty as my brother's birthday", "brother's birthday", "2027-04-20 00:00", "2027-04-21 00:00"),
        ("marca el trece de junio como el cumpleaños de mi hermano", "cumpleaños de mi hermano",
         "2027-06-13 00:00", "2027-06-14 00:00"),
        ("poner la primera semana de junio como vacaciones en mi calendario", "vacaciones",
         "2027-06-01 00:00", "2027-06-08 00:00"),
    ],
)
def test_a_marked_day_or_span_takes_the_whole_day(text, title, start, end) -> None:
    event = agenda_event_request(text)
    assert event is not None and event.whole_day and not event.missing
    assert sidecar._explicit_calendar_event_arguments(text, now_utc=NOW) == {
        "title": title, "startUtc": _utc(start), "endUtc": _utc(end),
    }


@pytest.mark.parametrize(
    ("text", "missing"),
    [
        ("añadir la comida con david", ("event_date_and_time",)),
        ("necesito programar una reunión con esta persona", ("event_date_and_time",)),
        ("crea un evento para el viernes", ("start_time",)),
        ("quiero una reunión hasta las tres en punto", ("start_time",)),
        ("reunirme con pablo mañana a las tres", ("am_pm_or_part_of_day_for_supplied_hour",)),
        ("pon reunión de almuerzo a las doce del mediodía cada miércoles de marzo",
         ("repetition_the_calendar_cannot_hold",)),
    ],
)
def test_an_event_asks_only_what_was_never_said(text: str, missing: tuple[str, ...]) -> None:
    clarification = resolve_explicit_clarification_intent(text, OPERATIONS)

    assert clarification is not None
    assert clarification.operations == ("calendar.event.create",)
    assert clarification.missing_fields == missing
    effects = resolve_explicit_effects(text, OPERATIONS)
    assert effects is None or "calendar.event.create" not in effects.operations


@pytest.mark.parametrize(
    "text",
    ["pon la mesa para la cena", "pon música para la cena", "pon una alarma para la reunión de mañana a las 7 de la mañana",
     "añade leche a mi lista de la compra", "anota que tengo reunión mañana", "haz la cena",
     "haz una llamada a mamá", "pon la comida"],
)
def test_an_order_about_something_else_is_not_an_event(text: str) -> None:
    assert agenda_event_request(text) is None


def test_doing_it_with_someone_or_at_a_time_is_an_event() -> None:
    appointment = agenda_event_request("Haz un appointment con el doctor.")
    assert appointment is not None and appointment.missing == ("event_date_and_time",)
    call = agenda_event_request("haz una llamada con Ana mañana a las 5 de la tarde")
    assert call is not None and not call.missing and call.title == "llamada con Ana"


def test_a_daily_repetition_is_a_repeating_reminder() -> None:
    text = "poner el almuerzo todos los días a la una de la tarde"
    effects = resolve_explicit_effects(text, OPERATIONS)

    assert effects is not None and effects.operations == ("notification.schedule",)
    assert operation_domain_is_grounded(text, "notification.schedule") is True
    schema = {
        "type": "object",
        "properties": {
            "dueUtc": {"type": "string", "maxLength": 64, "x-nonWhitespace": True},
            "kind": {"type": "string", "enum": ["alarm", "reminder"]},
            "recurrence": {"type": "string", "enum": ["daily", "hourly"]},
            "title": {"type": "string", "x-maxUtf8Bytes": 1024, "x-nonWhitespace": True},
        },
        "required": ["dueUtc", "kind", "title"], "additionalProperties": False,
    }
    arguments = sidecar._ground_explicit_arguments("notification.schedule", effects.evidence[0], schema)
    assert arguments is not None
    assert {key: arguments[key] for key in ("kind", "recurrence", "title")} == {
        "kind": "reminder", "recurrence": "daily", "title": "almuerzo",
    }
    assert datetime.fromisoformat(arguments["dueUtc"].replace("Z", "+00:00")).astimezone().strftime("%H:%M") == "13:00"
    # Every other day is not daily: the question says what cannot be held.
    other = agenda_event_request("pon el almuerzo cada dos días a la una de la tarde")
    assert other is not None and other.repeat is None
    assert other.missing == ("repetition_the_calendar_cannot_hold",)


# ------------------------------------------------------------------ alarms and reminders


@pytest.mark.parametrize(
    ("text", "hour"),
    [
        ("pon alerta para las dos de la tarde", 14),
        ("activa alarma a las tres y media de la tarde hoy", 15),
        ("despiértame a las seis de la mañana del jueves para tener yo tiempo para la reunión", 6),
    ],
)
def test_an_alert_an_activated_alarm_and_a_wake_up_with_its_purpose_are_scheduled(text: str, hour: int) -> None:
    effects = resolve_explicit_effects(text, OPERATIONS)

    assert effects is not None and effects.operations == ("notification.schedule",)
    arguments = sidecar._explicit_arguments_from_evidence("notification.schedule", effects.evidence[0])
    assert arguments is not None and arguments["kind"] == "alarm"
    due = sidecar._canonical_due_utc(arguments["dueUtc"], effects.evidence[0], now_utc=NOW.replace(hour=1))
    assert due is not None
    assert datetime.fromisoformat(due.replace("Z", "+00:00")).astimezone(LOCAL).hour == hour


@pytest.mark.parametrize(
    ("text", "title", "due_literal"),
    [
        ("establece un recordatorio sobre la reunión de mañana a las nueve de la mañana",
         "la reunión de mañana", "a las nueve de la mañana"),
        ("add conference call at four p. m. to my reminders for today", "conference call", "at four p. m."),
    ],
)
def test_a_reminder_set_or_added_is_created_with_its_moment(text: str, title: str, due_literal: str) -> None:
    effects = resolve_explicit_effects(text, OPERATIONS)

    assert effects is not None and effects.operations == ("reminder.create",)
    assert sidecar._explicit_arguments_from_evidence("reminder.create", text) == {"dueUtc": due_literal, "title": title}


def test_an_event_stated_then_asked_to_be_reminded_of_is_the_reminder() -> None:
    text = "tengo una reunión el miércoles a las nueve de la mañana enviáme un recordatorio"
    assert stated_event_reminder(text) == ("una reunión el miércoles", "a las nueve de la mañana")
    effects = resolve_explicit_effects(text, OPERATIONS)
    assert effects is not None and effects.operations == ("reminder.create",)
    arguments = sidecar._explicit_arguments_from_evidence("reminder.create", effects.evidence[0])
    due = sidecar._canonical_due_utc(arguments["dueUtc"], text, now_utc=NOW)
    assert due == _utc("2026-09-30 09:00")
    assert stated_event_reminder("tengo una reunión el miércoles a las nueve") is None


@pytest.mark.parametrize(
    ("text", "operation", "missing"),
    [
        ("no dejes que me olvide de comprarle un regalo a mi hermana", "reminder.create", ("due_time",)),
        ("notificarme sobre el evento en mi calendario", "reminder.create", ("due_time",)),
        ("alert me at the time of the event", "reminder.create", ("due_time",)),
        ("please alert me", "reminder.create", ("what_to_remind_or_notify_about", "due_time")),
        ("remind me at", "reminder.create", ("what_to_remind_or_notify_about", "due_time")),
        ("dame un recordatorio veinticuatro horas antes de mi reunión del viernes con edg", "reminder.create",
         ("due_time",)),
        ("no me despiertes mañana", "notification.cancel.at", ("which_alarm",)),
    ],
)
def test_a_reminder_or_a_cancellation_asks_only_what_is_missing(text, operation, missing) -> None:
    clarification = resolve_explicit_clarification_intent(text, OPERATIONS)

    assert clarification is not None
    assert clarification.operations == (operation,)
    assert clarification.missing_fields == missing


def test_a_reminder_of_a_spoken_date_falls_on_that_date() -> None:
    due = sidecar._canonical_due_utc(
        "a las dos de la tarde", "recuérdame pagar el cuatro de febrero a las dos de la tarde", now_utc=NOW,
    )
    assert due == _utc("2027-02-04 14:00")
    # A date said with a day word that disagrees has no one day.
    assert sidecar._canonical_due_utc("a las dos de la tarde", "mañana el cuatro de febrero", now_utc=NOW) is None


@pytest.mark.parametrize(
    "text",
    ["erase my appointment for march seven", "clear my next activity", "cancela la reunión de mañana",
     "borra mi cita del martes"],
)
def test_removing_an_event_from_the_calendar_is_a_plain_limit(text: str) -> None:
    assert known_unsupported_effect_request(text, OPERATIONS) is True
    assert sidecar.effect_request_is_authoritative(text) is True


@pytest.mark.parametrize("text", ["cancela la alarma de las 7", "borra el recordatorio de pagar la luz"])
def test_baxys_own_alarms_and_reminders_keep_their_cancellation(text: str) -> None:
    assert known_unsupported_effect_request(text, OPERATIONS) is False


# ------------------------------------------------------------------ the whole turn


class _TalkingLlm(_KnowledgeLlm):
    """The real run answered these as talk, a web search or «eso no lo hago»."""

    @staticmethod
    def formulate_explicit_clarification_question(*_args: object, **_kwargs: object) -> str:
        return "¿A qué hora?"


def _turn(text: str) -> dict[str, object]:
    tools = {
        name: _tool(name, required=required)
        for name, required in (
            ("calendar.event.list", ("startUtc", "endUtc")),
            ("calendar.event.create", ("startUtc", "endUtc", "title")),
            ("reminder.create", ("dueUtc", "title")),
            ("notification.schedule", ("dueUtc", "kind", "title")),
            ("notification.cancel.at", ("hour", "kind")),
            ("web.search", ("query",)),
        )
    }
    return sidecar._prepare_turn_result(
        {"id": "turn-agenda", "text": text},
        llm=_TalkingLlm("x"),
        planner_catalog=PlannerCatalog(list(tools.values())),
        turn_evidence=_NoEvidence(),
        encoder=lambda _texts: (),
        tool_by_name=tools,
    )


@pytest.mark.parametrize(
    ("text", "operation"),
    [
        ("que tengo por venir", "calendar.event.list"),
        ("tengo algo programado para el cuatro de julio de este año", "calendar.event.list"),
        ("cuándo es mi brunch con jennifer", "calendar.event.list"),
        ("what's my schedule like today", "calendar.event.list"),
        ("añade una reunión con tom a mi calendario para las nueve de la mañana", "calendar.event.create"),
        # Fifteen words with no listed order verb: a request the readers prove is not overheard speech.
        ("por favor añade práctica el cuatro de febrero en el parque del retiro a las dos de la tarde",
         "calendar.event.create"),
        ("dame una notificación de recordatorio para la reunión de mañana a las diez a. m.", "reminder.create"),
        ("pon alerta para las dos de la tarde", "notification.schedule"),
    ],
)
def test_the_turn_acts_on_the_agenda_request(text: str, operation: str) -> None:
    result = _turn(text)

    assert result["kind"] == "action"
    assert result["operation"] == operation


@pytest.mark.parametrize(
    "text",
    ["añadir la comida con david", "no me despiertes mañana", "no dejes que me olvide de comprarle un regalo a mi hermana"],
)
def test_the_turn_asks_what_the_agenda_request_misses(text: str) -> None:
    result = _turn(text)

    assert result["kind"] == "clarify"
    assert result["question"] == "¿A qué hora?"
