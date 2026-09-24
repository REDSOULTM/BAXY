"""Uso real 2026-09-24 (MASSIVE es/en, second development set of the calendar/alarms/reminders family):
own agenda questions went to the web, orders said with «usted» or as an infinitive were heard as nobody's
talk, a repeated wake-up was scheduled once, and a meeting was «eso no lo hago» or a web search.

- An order said with «usted», as a bare infinitive or with its clitic split off by the transcription
  («envíeme…», «establecer…», «recuérda me…») is the order the readers read in the tú imperative.
- The person's own event, named without «mi» («la reunión que tengo con…», «cuándo está programada la
  boda», «la cena de esta noche», «am I busy this weekend»), is read from the calendar over the window
  said (yesterday, a run of days «entre hoy y el veintiuno», the hours «entre las ocho y las cinco»).
- An event of the person's agenda never leaves as a web search.
- A daily or hourly repetition is scheduled as a repeating alarm or reminder; any other one, or one
  bounded by a date, is asked. Cleaning the agenda or editing an event is a plain limit; several alarms
  to cancel ask which one; a time counted from an event whose hour is unknown asks when.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic.grammar import imperative_rewrites
from baxy_mind.semantic.guards import _overheard_speech
from baxy_mind.semantic.normalize import fold
from baxy_mind.semantic.notes import agenda_read_request, reminder_inventory_question, said_repetition
from baxy_mind.semantic.patterns import (
    effect_request_is_authoritative,
    known_unsupported_effect_request,
    resolve_explicit_clarification_intent,
    resolve_explicit_effects,
)
from baxy_mind.semantic.reading import read
from baxy_mind.semantic.temporal import agenda_window, spoken_clock
from baxy_mind.semantic.web import names_own_data
from test_c03_pointless_questions import _NoEvidence, _tool
from test_c03_unknown_looked_up import _KnowledgeLlm

OPERATIONS = (
    "calendar.event.list", "calendar.event.create", "reminder.create", "reminder.list", "notification.schedule",
    "notification.list", "notification.cancel.at", "notification.cancel.latest", "task.create", "task.list",
    "note.create", "web.search", "media.play.youtube", "media.play.query", "system.time", "app.open",
    "audio.volume.adjust",
)
LOCAL = timezone(timedelta(hours=-3))
NOW = datetime(2026, 9, 24, 6, 30, tzinfo=LOCAL)  # a Thursday morning
NAIVE_NOW = NOW.replace(tzinfo=None)
NOTIFICATION_SCHEMA = {
    "type": "object",
    "properties": {
        "dueUtc": {"type": "string", "maxLength": 64, "x-nonWhitespace": True},
        "kind": {"type": "string", "enum": ["alarm", "reminder"]},
        "recurrence": {"type": "string", "enum": ["daily", "hourly"]},
        "title": {"type": "string", "x-maxUtf8Bytes": 1024, "x-nonWhitespace": True},
    },
    "required": ["dueUtc", "kind", "title"], "additionalProperties": False,
}


def _local(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%d %H:%M")


# ------------------------------------------------------------------ an order said another way


@pytest.mark.parametrize(
    ("text", "rewrite"),
    [
        ("Envíeme un recordatorio", "enviame un recordatorio"),
        ("póngame una alarma", "ponme una alarma"),
        ("agregue la cena", "agrega la cena"),
        ("cancele el evento", "cancela el evento"),
        ("establecer un recordatorio", "establece un recordatorio"),
        ("recordarme que", "recordame que"),
        ("recuérda me la cita", "recuerdame la cita"),
        ("cuénta me todo", "cuentame todo"),
        ("dígame la hora", "dime la hora"),
        ("solo recuérdame algo", "recuerdame algo"),
    ],
)
def test_an_usted_infinitive_or_split_order_is_rewritten_as_the_tu_imperative(text: str, rewrite: str) -> None:
    assert fold(imperative_rewrites(text)[0]) == rewrite


@pytest.mark.parametrize("text", ["limpia mi agenda", "programa una reunión", "sube el volumen", "horario"])
def test_a_tu_imperative_or_a_noun_is_never_read_backwards_into_another_verb(text: str) -> None:
    # «limpia» → «limpie», «programa» → «programe» are no order the readers know.
    assert not any(fold(rewrite).split()[0] in {"limpie", "programe", "suba"} for rewrite in imperative_rewrites(text))
    assert imperative_rewrites("horario") == ()
    # A noun that looks like an «usted» form is followed by its complement; English has no such forms.
    assert imperative_rewrites("Cierre de Word podía perder trabajo") == ()
    assert imperative_rewrites("Lower nine points the volume") == ()


@pytest.mark.parametrize(
    ("text", "operation"),
    [
        ("Agende una cita con el dentista el martes a las cuatro de la tarde", "calendar.event.create"),
        ("Programe una alarma a las seis y media de la mañana", "notification.schedule"),
        ("Recuérdeme llamar a mi madre mañana a las ocho de la noche", "reminder.create"),
        ("Mándeme un recordatorio para pagar el arriendo el viernes a las diez de la mañana", "reminder.create"),
        ("Cree una reunión con Ana el viernes a las once de la mañana", "calendar.event.create"),
        ("Establecer un recordatorio para la cita con el médico a las cinco de la tarde", "reminder.create"),
        ("recordarme sacar la basura a las nueve de la noche", "reminder.create"),
        ("abra el bloc de notas", "app.open"),
    ],
)
def test_the_reading_reads_the_order_said_another_way(text: str, operation: str) -> None:
    reading = read(text, available_operations=OPERATIONS)

    assert reading.source == "imperative_rewrite"
    assert reading.effects is not None and reading.effects.operations == (operation,)


def test_what_the_rewritten_order_misses_is_asked_as_for_the_tu_order() -> None:
    clarification = resolve_explicit_clarification_intent("Establecer una alarma para las siete", OPERATIONS)

    assert clarification is not None
    assert clarification.missing_fields == ("am_pm_or_part_of_day_for_supplied_hour",)


def test_a_long_order_said_with_usted_is_said_to_baxy_not_overheard() -> None:
    text = fold("envíeme un recordatorio para retirar el auto del taller mecánico a las seis y media de la tarde")
    assert len(text.split()) >= 15
    assert _overheard_speech(text) is False


@pytest.mark.parametrize(
    ("text", "title", "hour"),
    [
        ("Mándeme un recordatorio para pagar el arriendo a las diez de la mañana", "pagar el arriendo", 10),
        ("envíame un recordatorio para sacar la basura a las nueve por la noche", "sacar la basura", 21),
        ("send me a reminder to water the plants at 6 pm", "water the plants", 18),
        ("establece un recordatorio para la entrevista a las cuatro de la tarde mañana", "la entrevista", 16),
    ],
)
def test_a_reminder_sent_or_set_keeps_its_subject_and_moment(text: str, title: str, hour: int) -> None:
    effects = read(text, available_operations=OPERATIONS).effects
    assert effects is not None and effects.operations == ("reminder.create",)

    arguments = sidecar._explicit_arguments_from_evidence("reminder.create", effects.evidence[0])
    assert arguments is not None and fold(arguments["title"]) == fold(title)
    due = sidecar._canonical_due_utc(arguments["dueUtc"], text, now_utc=NOW)
    assert due is not None
    assert datetime.fromisoformat(due.replace("Z", "+00:00")).astimezone(LOCAL).hour == hour


def test_set_a_reminder_to_and_send_a_reminder_to_read_the_same_arguments() -> None:
    expected = {"dueUtc": "at 7 pm", "title": "call the vet"}
    assert sidecar._explicit_arguments_from_evidence("reminder.create", "set a reminder to call the vet at 7 pm") == expected
    assert sidecar._explicit_arguments_from_evidence("reminder.create", "send me a reminder to call the vet at 7 pm") == expected


# ------------------------------------------------------------------ the person's own agenda, read


@pytest.mark.parametrize(
    ("text", "start", "end"),
    [
        ("¿a qué hora empieza la reunión que tengo con Marta?", None, None),
        ("when is the dinner scheduled", None, None),
        ("cuándo está agendada la entrevista", None, None),
        ("qué tal estuvo la cita de anoche", "2026-09-23 00:00", "2026-09-24 00:00"),
        ("quién viene a la reunión de mañana", "2026-09-25 00:00", "2026-09-26 00:00"),
        ("a qué hora es la comida con mis suegros esta noche", "2026-09-24 18:00", "2026-09-25 00:00"),
        ("am I busy on saturday", "2026-09-26 00:00", "2026-09-27 00:00"),
        ("estoy libre el sábado", "2026-09-26 00:00", "2026-09-27 00:00"),
        ("any appointments next week", "2026-09-28 00:00", "2026-10-05 00:00"),
        ("cómo tengo la agenda del viernes", "2026-09-25 00:00", "2026-09-26 00:00"),
        ("mi agenda", None, None),
        ("my class schedule", None, None),
        ("tengo que ir a algún lado mañana por la tarde", "2026-09-25 12:00", "2026-09-25 20:00"),
        ("do I need to be anywhere on friday", "2026-09-25 00:00", "2026-09-26 00:00"),
        ("qué eventos tengo entre el lunes y el miércoles", "2026-09-28 00:00", "2026-10-01 00:00"),
        ("dime todas las citas hasta el domingo", "2026-09-24 00:00", "2026-09-28 00:00"),
        ("qué tengo que hacer yo mañana", "2026-09-25 00:00", "2026-09-26 00:00"),
        ("qué tengo hoy entre las nueve de la mañana y las dos de la tarde", "2026-09-24 09:00", "2026-09-24 14:00"),
        ("have you put a meeting with Luis on my calendar for friday", "2026-09-25 00:00", "2026-09-26 00:00"),
        ("up coming appointments", None, None),
    ],
)
def test_the_persons_own_event_is_read_from_the_agenda(text: str, start: str | None, end: str | None) -> None:
    assert agenda_read_request(text) is True
    effects = resolve_explicit_effects(text, OPERATIONS)
    assert effects is not None and effects.operations == ("calendar.event.list",)

    window = agenda_window(fold(effects.evidence[0]), NAIVE_NOW)
    assert window is not None
    if start is None:
        # Nothing said: what is coming.
        assert window[0] == NAIVE_NOW and window[1] > NAIVE_NOW + timedelta(days=7)
    else:
        assert (_local(window[0]), _local(window[1])) == (start, end)


@pytest.mark.parametrize(
    "text",
    [
        "cuándo es el concierto de Coldplay en Santiago",
        "cuándo es la reunión del G20",
        "qué es una reunión de directorio",
        "cómo preparo una reunión efectiva",
        "necesito que me recuerden las reuniones del lunes",
        "limpia mi agenda para mañana",
        "estoy cansado",
        "eventos deportivos este fin de semana",
        # How the day is, is the weather.
        "cómo está el día hoy",
    ],
)
def test_a_public_event_a_question_about_meetings_or_a_change_is_not_an_agenda_read(text: str) -> None:
    assert agenda_read_request(text) is False


@pytest.mark.parametrize(
    "text",
    [
        "necesito prepararme para una reunión importante",
        "tengo un vuelo el jueves",
        "i have a dentist appointment on monday",
        "quiero ir a la fiesta de Carla el sábado",
        "qué pasó en la reunión de ayer",
        "cuándo está programada la boda",
    ],
)
def test_an_event_of_the_persons_agenda_is_their_own_data(text: str) -> None:
    assert names_own_data(text) is True


@pytest.mark.parametrize(
    "text",
    ["cuándo es el concierto de Coldplay en Santiago", "cuándo es la reunión del G20", "when is the next apple event"],
)
def test_a_public_event_is_not_the_persons_data(text: str) -> None:
    assert names_own_data(text) is False


@pytest.mark.parametrize(
    ("text", "operation"),
    [
        ("tengo recordatorios pendientes", "reminder.list"),
        ("do I have any reminders for tomorrow", "reminder.list"),
        ("are there any alarms set for tomorrow", "notification.list"),
        ("hay alarmas puestas", "notification.list"),
    ],
)
def test_whether_baxy_holds_reminders_or_alarms_is_a_read_of_them(text: str, operation: str) -> None:
    assert reminder_inventory_question(text) == operation
    effects = resolve_explicit_effects(text, OPERATIONS)
    assert effects is not None and effects.operations == (operation,)


# ------------------------------------------------------------------ repetitions


@pytest.mark.parametrize(
    ("text", "repetition"),
    [
        ("recuérdame regar las plantas cada día a las ocho de la mañana", "daily"),
        ("todas las mañanas", "daily"),
        ("every hour", "hourly"),
        ("cada domingo a las nueve", "unsupported"),
        ("every month", "unsupported"),
        ("mañana a las nueve", None),
    ],
)
def test_the_repetition_said_is_one_the_catalog_holds_or_not(text: str, repetition: str | None) -> None:
    assert said_repetition(text) == repetition


@pytest.mark.parametrize(
    ("text", "kind", "title", "hour"),
    [
        ("recuérdame regar las plantas cada día a las ocho de la mañana", "reminder", "regar las plantas", 8),
        ("recordarme que tengo que tomar la pastilla a las diez de la noche todos los días", "reminder",
         "tengo que tomar la pastilla", 22),
        ("despiértame todos los días a las seis y media de la mañana", "alarm", None, 6),
        ("set an alarm every day at 7 am", "alarm", None, 7),
    ],
)
def test_a_daily_alarm_or_reminder_repeats_daily(text: str, kind: str, title: str | None, hour: int) -> None:
    effects = read(text, available_operations=OPERATIONS).effects
    assert effects is not None and effects.operations == ("notification.schedule",)

    arguments = sidecar._ground_explicit_arguments("notification.schedule", effects.evidence[0], NOTIFICATION_SCHEMA)
    assert arguments is not None
    assert arguments["kind"] == kind and arguments["recurrence"] == "daily"
    if title is not None:
        assert fold(arguments["title"]) == fold(title)
    assert datetime.fromisoformat(arguments["dueUtc"].replace("Z", "+00:00")).astimezone().hour == (
        datetime(2026, 1, 1, hour, tzinfo=LOCAL).astimezone().hour
    )


@pytest.mark.parametrize(
    ("text", "operation"),
    [
        ("pon una alarma cada domingo a las nueve de la mañana", "notification.schedule"),
        ("recuérdame sacar la basura cada martes a las ocho de la noche", "notification.schedule"),
        ("recuérdame pagar la tarjeta cada mes", "notification.schedule"),
        ("agenda la clase de yoga todos los días hasta el viernes a las siete de la tarde", "notification.schedule"),
        ("programa una meditación al mediodía todos los lunes", "calendar.event.create"),
    ],
)
def test_a_repetition_no_alarm_or_reminder_holds_is_asked(text: str, operation: str) -> None:
    clarification = resolve_explicit_clarification_intent(text, OPERATIONS)

    assert clarification is not None
    assert clarification.operations == (operation,)
    assert clarification.missing_fields == ("repetition_the_calendar_cannot_hold",)
    # Nothing is scheduled once in its place.
    assert sidecar._explicit_arguments_from_evidence("notification.schedule", text) is None


# ------------------------------------------------------------------ what is asked, what is a limit


@pytest.mark.parametrize(
    ("text", "operation", "missing"),
    [
        ("avísame media hora antes de la cena", "reminder.create", ("due_time",)),
        ("remind me two hours before the interview", "reminder.create", ("due_time",)),
        ("no te olvides de recordarme la reunión con el contador", "reminder.create", ("due_time",)),
        ("acuérdate de recordarme esto", "reminder.create", ("due_time",)),
        ("necesito que me recuerden el pago del gimnasio", "reminder.create", ("due_time",)),
        ("el sábado es el cumpleaños de mi sobrina, recuérdamelo", "reminder.create", ("due_time",)),
        ("remind me to call the bank at three o'clock", "reminder.create",
         ("am_pm_or_part_of_day_for_supplied_hour",)),
        ("wake me up at seven o'clock tomorrow", "notification.schedule",
         ("am_pm_or_part_of_day_for_supplied_hour",)),
        ("establecer un recordatorio para el domingo ir al mercado a las nueve", "reminder.create",
         ("am_pm_or_part_of_day_for_supplied_hour",)),
        ("quita todas mis alarmas", "notification.cancel.at", ("which_alarm",)),
        ("delete my alarms for tomorrow", "notification.cancel.at", ("which_alarm",)),
        ("anota esta reunión en mi agenda", "calendar.event.create", ("event_title", "event_date_and_time")),
    ],
)
def test_only_what_is_missing_is_asked(text: str, operation: str, missing: tuple[str, ...]) -> None:
    clarification = resolve_explicit_clarification_intent(text, OPERATIONS)

    assert clarification is not None
    assert clarification.operations == (operation,)
    assert clarification.missing_fields == missing


def test_a_time_counted_from_now_is_still_a_moment() -> None:
    effects = resolve_explicit_effects("recuérdame sacar la ropa en dos horas", OPERATIONS)
    assert effects is not None and effects.operations == ("reminder.create",)
    assert resolve_explicit_clarification_intent("recuérdame sacar la ropa en dos horas", OPERATIONS) is None


def test_o_clock_is_a_clock_time_and_not_an_alternative() -> None:
    clock = spoken_clock("an appointment twelve o'clock on saturday")
    assert clock is not None and clock.hour == 12 and clock.resolved is False
    assert spoken_clock("a las cinco en punto de la tarde").hour == 17


@pytest.mark.parametrize(
    "text",
    [
        "limpie mi calendario de mañana",
        "clear my schedule for friday",
        "cancele la cita del dentista",
        "cambia la cita del lunes para el martes",
        "modify the lunch event to start at one",
    ],
)
def test_cleaning_the_agenda_or_editing_an_event_is_a_plain_limit(text: str) -> None:
    assert known_unsupported_effect_request(text, OPERATIONS) is True
    assert effect_request_is_authoritative(text) is True


@pytest.mark.parametrize("text", ["cambia la alarma de las siete", "mueve la ventana a la izquierda"])
def test_an_alarm_or_a_window_is_not_an_event_edit(text: str) -> None:
    assert known_unsupported_effect_request(text, OPERATIONS) is False


# ------------------------------------------------------------------ the whole turn


class _PublicLookupLlm(_KnowledgeLlm):
    """The model talks and the public-lookup guard reads everything as public: only the own-data rule keeps
    the person's agenda on the PC."""

    @staticmethod
    def public_lookup_requested(_text: str) -> bool:
        return True

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
        {"id": "turn-agenda-2", "text": text},
        llm=_PublicLookupLlm("No lo sé."),
        planner_catalog=PlannerCatalog(list(tools.values())),
        turn_evidence=_NoEvidence(),
        encoder=lambda _texts: (),
        tool_by_name=tools,
    )


@pytest.mark.parametrize(
    ("text", "operation"),
    [
        ("¿a qué hora empieza la reunión que tengo con Marta?", "calendar.event.list"),
        ("when is the dinner scheduled", "calendar.event.list"),
        ("any appointments next week", "calendar.event.list"),
        ("qué tal estuvo la cita de anoche", "calendar.event.list"),
        # Sixteen words with no listed order verb at a clause start: said to BAXY.
        ("envíeme un recordatorio para retirar el auto del taller mecánico a las seis y media de la tarde",
         "reminder.create"),
        ("despiértame todos los días a las seis y media de la mañana", "notification.schedule"),
    ],
)
def test_the_turn_reads_or_schedules_what_was_asked(text: str, operation: str) -> None:
    result = _turn(text)

    assert result["kind"] == "action"
    assert result["operation"] == operation


@pytest.mark.parametrize(
    "text",
    ["necesito prepararme para una reunión importante", "tengo un vuelo el jueves", "call person b for the meeting"],
)
def test_the_persons_event_never_leaves_as_a_web_search(text: str) -> None:
    result = _turn(text)

    assert result["kind"] == "conversation"
    assert result["operation"] is None


def test_a_public_event_is_still_looked_up() -> None:
    result = _turn("cuándo es el concierto de Coldplay en Santiago")

    assert result["kind"] == "action"
    assert result["operation"] == "web.search"


@pytest.mark.parametrize("text", ["cancele el próximo evento del calendario", "alter the lunch event to repeat every friday"])
def test_the_turn_says_the_limit_of_the_agenda(text: str) -> None:
    result = _turn(text)

    assert result["kind"] == "conversation"
    assert result["conversationKind"] == "unsupported"


@pytest.mark.parametrize(
    "text",
    ["apaga mis alarmas del fin de semana", "i want to go to the street fair on sunday remind me",
     "por favor recuérdame una hora antes de la reunión que tengo mañana"],
)
def test_the_turn_asks_what_the_request_misses(text: str) -> None:
    result = _turn(text)

    assert result["kind"] == "clarify"
    assert result["question"] == "¿A qué hora?"
