"""Tanda 5 and 4f (2026-09-24, official window): the date, the time, timers and numbers said in words.

A. «dime el mes actual» and «i need information on today's date» searched the web; «dime hora que es» asked back
   whether to read the clock. The month, the year, the day and the hour of this PC, asked however it is asked, are
   one clock read.
B. «¿estamos a mitad de semana?» searched the web, quoted dictionaries and died in the App's policy
   (internal_code: the snippet's «lo que significa que» was taken for a restated definition ask). Which part of the
   week today is, is the weekday of this PC's calendar, and the answer carries the weekday and the date.
C. «set 30 minute timer» died three times in missing_state: the receipt reached the narrator as UTC instants and
   the drafts said 14:27, 16:57 and 17:27 for a timer due at 13:57 local. The narrator gets the local time.
D. «cien mil doscientas veintitrés» was written 100.223, 102.230 and 10223 on four runs: a number said in words is
   read by the mind, with its thousands and millions, and the model is only handed the figures.
E. «configuré una alarma para despertarme por la mañana» → «¡Claro! ¿Quieres que te diga qué hora tienes
   configurada…?»: an alarm the person set is told, not asked for; it is acknowledged without an offer.

Every phrasing here is a paraphrase none of the fixes names, with its negative controls.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from baxy_mind import llm
from baxy_mind.__main__ import _explicit_stable_no_effect_turn_decision, _general_factoid_prompt, _prepare_turn_result
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic.grammar import spoken_cardinal, spoken_number_request
from baxy_mind.semantic.media import radio_station_query
from baxy_mind.semantic.network import asks_calendar_part, calendar_parts_asked
from baxy_mind.semantic.patterns import reported_own_schedule
from baxy_mind.semantic.reading import read
from test_c03_cpu_actor import Recorder
from test_c03_pointless_questions import _NoEvidence, _tool

_OPERATIONS = (
    "system.time", "web.search", "notification.schedule", "notification.list", "reminder.create",
    "calendar.event.list", "weather.current", "input.text.type", "audio.volume",
)


def _effects(text: str) -> tuple[str, ...] | None:
    effects = read(text, available_operations=_OPERATIONS).effects
    return None if effects is None else effects.operations


# ------------------------------------------------------------------ A. the calendar and the clock are one read


@pytest.mark.parametrize(
    "text",
    [
        "dime el mes actual",
        "cuál es el mes actual",
        "decime el año actual",
        "dime el día de hoy",
        "tell me the current month",
        "what's the current year?",
        "show me the current weekday",
        "dime el month actual",
        "i need information on today's date",
        "necesito información sobre la fecha de hoy",
        "i'd like some info about the current date",
        "dime hora que es",
        "dime la hora que es",
        "decime la fecha que es hoy",
        "dame la hora que tenemos",
    ],
)
def test_the_month_the_year_the_day_and_the_hour_are_the_clock_read(text: str) -> None:
    assert _effects(text) == ("system.time",)


@pytest.mark.parametrize(
    "text",
    [
        "i need information on the date of the concert",
        "necesito información sobre el mes de las flores",
        "dime el mes en que nació Messi",
        "información sobre la semana santa",
        "dime el año en que cayó el muro de Berlín",
    ],
)
def test_the_date_of_something_else_is_not_the_clock(text: str) -> None:
    assert _effects(text) != ("system.time",)


def test_a_month_asked_is_carried_alone_and_an_hour_asked_is_the_clock() -> None:
    situation = _time_situation()
    assert llm._compose_situation_payload(situation, "es", "decime el mes actual") == {
        "month": "septiembre", "operation": "system.time",
    }
    assert llm._compose_situation_payload(situation, "es", "dime hora que es") == {
        "clock": "13:25", "operation": "system.time",
    }


# ------------------------------------------------------------------ B. the part of the week is the weekday


def _time_situation() -> dict:
    # Thursday 2026-09-24 13:25 at UTC-3.
    return {
        "kind": "operation", "operation": "system.time", "polarity": "success", "verified": True, "succeeded": True,
        "observed": {"utc": "2026-09-24T16:25:30.1234567+00:00", "localUtcOffsetMinutes": -180},
    }


_WEEK_PERIOD_QUESTIONS = (
    "¿estamos a mitad de semana?",
    "ya es fin de semana?",
    "¿hoy es finde?",
    "estamos en el principio de la semana?",
    "is it the weekend yet?",
    "are we in the middle of the week?",
    "is today midweek",
    "sabes si ya estamos a mitad de semana",
    "is it el fin de semana yet",
)


@pytest.mark.parametrize("text", _WEEK_PERIOD_QUESTIONS)
def test_which_part_of_the_week_today_is_reads_the_clock(text: str) -> None:
    assert _effects(text) == ("system.time",)
    assert asks_calendar_part(text)
    # Tanda 6b (owner): the part of the week is answered by the weekday; the date is not required.
    assert calendar_parts_asked(text) == ("weekday",)


@pytest.mark.parametrize("text", _WEEK_PERIOD_QUESTIONS[:3])
def test_the_part_of_the_week_carries_the_weekday_not_the_clock(text: str) -> None:
    payload = llm._compose_situation_payload(_time_situation(), "es", text)
    assert payload == {"weekday": "jueves", "operation": "system.time"}


@pytest.mark.parametrize(
    ("reply", "defect"),
    [
        ("No del todo: hoy es jueves 24 de septiembre.", ""),
        ("Hoy es jueves 24 de septiembre, ya pasamos la mitad de la semana.", ""),
        ("Sí, estamos a mitad de semana.", "missing_name"),
        ("Hoy es miércoles 24 de septiembre.", "missing_name"),
    ],
)
def test_the_answer_names_the_observed_weekday_and_date(reply: str, defect: str) -> None:
    facts = {"situation": _time_situation()}
    assert llm.compose_visible_defect(reply, "status", "¿estamos a mitad de semana?", facts) == defect


@pytest.mark.parametrize(
    "text",
    [
        "¿es fin de semana largo en Chile?",
        "is the weekend forecast sunny",
        "qué planes hay para el fin de semana",
        "what should I do this weekend",
    ],
)
def test_the_weekend_as_a_topic_is_not_the_clock(text: str) -> None:
    assert _effects(text) != ("system.time",)


# ------------------------------------------------------------------ C. the timer is told in the person's clock


def _timer_situation(due: datetime) -> dict:
    stamp = due.isoformat()
    return {
        "kind": "operation", "operation": "notification.schedule", "polarity": "success", "verified": True,
        "succeeded": True,
        "observed": {
            "version": 1, "kind": "alarm", "title": "timer", "dueUtc": stamp, "taskName": "BAXY-Alarm-0123",
            "state": "Ready", "nextRunUtc": stamp.replace("+00:00", ".0000000+00:00"),
            "authority": "windows_task_scheduler_postread",
        },
    }


def _soon() -> datetime:
    return (datetime.now(timezone.utc) + timedelta(minutes=30)).replace(microsecond=0)


def test_the_narrator_gets_the_local_time_and_no_utc_instant() -> None:
    due = _soon()
    payload = llm._compose_situation_payload(_timer_situation(due), "en", "set 30 minute timer")
    seen = payload["seen"]
    assert seen["scheduledLocalTime"] == due.astimezone().strftime("%H:%M")
    assert not {"dueUtc", "nextRunUtc", "taskName", "authority"} & set(seen)
    if due.astimezone().date() == datetime.now().astimezone().date():
        assert "scheduledLocalDate" not in seen
    assert due.strftime("%H:%M") in json.dumps(_timer_situation(due))  # the checks keep the whole receipt


def test_a_timer_for_another_day_carries_its_local_date() -> None:
    due = (datetime.now(timezone.utc) + timedelta(days=2)).replace(microsecond=0)
    seen = llm._compose_situation_payload(_timer_situation(due), "es", "pon una alarma pasado mañana")["seen"]
    assert seen["scheduledLocalDate"] == due.astimezone().date().isoformat()


@pytest.mark.parametrize("language", ["en", "es"])
def test_the_scheduled_time_is_the_local_one(language: str) -> None:
    due = _soon()
    local = due.astimezone().strftime("%H:%M")
    facts = {"situation": _timer_situation(due)}
    text = "set 30 minute timer" if language == "en" else "pon un temporizador de media hora"
    good = f"The 30-minute timer is set for {local}." if language == "en" else f"Listo, el temporizador suena a las {local}."
    assert llm.compose_visible_defect(good, "status", text, facts) == ""
    wrong = (due + timedelta(hours=1)).astimezone().strftime("%H:%M")
    assert llm.compose_visible_defect(good.replace(local, wrong), "status", text, facts) == "missing_state"


def test_the_retry_hint_names_the_local_time() -> None:
    due = _soon()
    local = due.astimezone().strftime("%H:%M")
    wrong = f"The 30-minute timer is set for {due:%H:%M}." if due.strftime("%H:%M") != local else "It is set for 99:99."
    good = f"The 30-minute timer is set for {local}."
    client = Recorder([wrong, good])
    assert client.compose_user_message("set 30 minute timer", "status", {"situation": _timer_situation(due)}) == good
    retry = json.dumps(client.payloads[1]["messages"][-2:], ensure_ascii=False)
    assert f"Give the scheduled local time, {local}," in retry


# ------------------------------------------------------------------ D. a number said in words is read, not guessed


@pytest.mark.parametrize(
    ("words", "value"),
    [
        ("cien mil doscientas veintitrés", 100_223),
        ("ciento un mil", 101_000),
        ("doscientos cuarenta y seis mil novecientos", 246_900),
        ("mil novecientos noventa y nueve", 1_999),
        ("dos millones trescientos mil quinientos", 2_300_500),
        ("un millón", 1_000_000),
        ("mil millones", 1_000_000_000),
        ("veintiún mil", 21_000),
        ("setecientas una", 701),
        ("one hundred thousand two hundred twenty-three", 100_223),
        ("a hundred and five", 105),
        ("twenty five hundred", 2_500),
        ("three million forty thousand and seven", 3_040_007),
        ("seventy-seven", 77),
        ("cero", 0),
    ],
)
def test_the_spoken_number_is_read_with_its_thousands_and_millions(words: str, value: int) -> None:
    assert spoken_cardinal(words) == value


@pytest.mark.parametrize(
    "words", ["dos tres", "treinta cuarenta", "mil mil", "y dos", "cien y", "zero one", "cinco manzanas", "hundred"],
)
def test_words_that_are_not_one_number_are_not_read(words: str) -> None:
    assert spoken_cardinal(words) is None


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("cien mil doscientas veintitrés", 100_223),
        ("Trescientos cuarenta y dos mil ciento ocho.", 342_108),
        ("dos millones quinientos mil", 2_500_000),
        ("one hundred and five in digits", 105),
        ("how do you write forty two thousand in numbers", 42_000),
        ("¿cómo se escribe dos mil diez?", 2_010),
        ("escríbeme doscientos treinta mil en números", 230_000),
        ("write ninety-nine thousand in figures", 99_000),
        ("pasame mil quinientos en cifras", 1_500),
        ("seventy seven", 77),
        ("baxy, trescientos mil", 300_000),
    ],
)
def test_a_number_said_and_nothing_else_asked_is_written_in_figures(text: str, value: int) -> None:
    assert spoken_number_request(text) == value
    assert _general_factoid_prompt(text)
    assert llm._conversation_presentation_shape(text, conversation_kind="knowledge", has_history=True) == "spoken_number"


@pytest.mark.parametrize(
    "text",
    [
        "cinco",
        "veintitrés",
        "¿cómo se escribe veintitrés?",
        "escribe cien mil",
        "escribe cien mil en el bloc de notas",
        "cuánto es cien mil más dos",
        "dos más dos",
        "pon el volumen a cuarenta y cinco",
        "sube el volumen veinte",
        "tengo cien mil pesos",
        "how is the weather",
    ],
)
def test_a_lone_word_typing_arithmetic_and_amounts_are_not_that_request(text: str) -> None:
    assert spoken_number_request(text) is None


@pytest.mark.parametrize(("language", "figures"), [("es", "100.223"), ("en", "100,223")])
def test_the_model_is_handed_the_figures(language: str, figures: str) -> None:
    text = "cien mil doscientas veintitrés"
    shaped = json.loads(llm._shaped_presentation_text(text, "spoken_number", response_language=language))
    assert shaped == {"response_language": language, "said": text, "number": figures}
    year = json.loads(llm._shaped_presentation_text("dos mil veintiséis", "spoken_number", response_language="es"))
    assert year["number"] == "2026"


@pytest.mark.parametrize(
    ("reply", "accepted"),
    [
        ("100.223", True),
        ("Es 100.223.", True),
        ("100223", True),
        ("100,223", True),
        ("10223", False),
        ("102.230", False),
        ("100.223 o 100.224", False),
        ("¿100.223?", False),
        ("cien mil doscientos veintitrés", False),
    ],
)
def test_only_the_read_figures_pass(reply: str, accepted: bool) -> None:
    request = "cien mil doscientas veintitrés"
    assert llm._shaped_conversation_answer_violates_contract(reply, request, "spoken_number") is (not accepted)


@pytest.mark.parametrize(
    ("name", "query"),
    [
        ("pon la novecientos noventa y nueve fm", "99.9 FM"),
        ("sintoniza mil ochenta am", "1080 AM"),
        ("play eight hundred and ninety seven am", "897 AM"),
    ],
)
def test_the_radio_dial_keeps_reading_through_the_same_numbers(name: str, query: str) -> None:
    assert (radio_station_query(name) or "").startswith(query)


# ------------------------------------------------------------------ E. an alarm the person set is acknowledged


@pytest.mark.parametrize(
    "text",
    [
        "configuré una alarma para despertarme por la mañana",
        "Ya puse el despertador a las 7.",
        "programé un temporizador de diez minutos",
        "tengo una alarma puesta para las seis",
        "he puesto una alarma para mañana",
        "dejé programado el despertador",
        "recién me puse un recordatorio para la reunión",
        "creé un recordatorio para comprar pan",
        "I set an alarm to wake me up tomorrow",
        "I've already set a timer for the pasta",
        "i have an alarm set for 6 am",
        "ya configuré my alarm for tomorrow",
    ],
)
def test_an_alarm_the_person_set_is_what_they_tell(text: str) -> None:
    assert reported_own_schedule(text)
    assert _effects(text) is None
    decision = _explicit_stable_no_effect_turn_decision(text)
    assert decision is not None and decision["mode"] == "conversation" and decision["effect_operations"] == []
    assert llm._conversation_presentation_shape(text, conversation_kind="social", has_history=True) == "observation_ack"


@pytest.mark.parametrize(
    "text",
    [
        "configura una alarma para despertarme por la mañana",
        "configure una alarma para las 7",
        "¿configuré una alarma?",
        "configuré una alarma pero no suena, revísala",
        "puse una alarma a las 7, ¿está puesta?",
        "set an alarm for 7",
        "I want to set an alarm",
        "I set an alarm, can you check it",
        "ponme una alarma a las 7",
        "i set the volume to 50",
        "puse música",
        "tengo hambre",
        "tengo recordatorios pendientes",
        "tengo una alarma para las seis",
        "i have reminders for tomorrow",
    ],
)
def test_an_order_a_question_or_a_request_about_it_is_not_a_statement(text: str) -> None:
    assert not reported_own_schedule(text)


@pytest.mark.parametrize(
    ("reply", "accepted"),
    [
        ("¡Claro! ¿Quieres que te diga qué hora tienes configurada para tu alarma? 😊", False),
        ("Would you like me to check it?", False),
        ("Perfecto, que descanses y despiertes bien.", True),
        ("Genial, así no se te pasa la mañana.", True),
    ],
)
def test_the_acknowledgement_offers_nothing(reply: str, accepted: bool) -> None:
    request = "configuré una alarma para despertarme por la mañana"
    assert llm._shaped_conversation_answer_violates_contract(reply, request, "observation_ack") is (not accepted)


# ------------------------------------------------------------------ the whole turn


class _ClosedLlm:
    """A model that must not be asked to decide: these turns close before it."""

    def __init__(self) -> None:
        self.chat_kinds: list[str] = []

    @staticmethod
    def decide_turn(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise AssertionError("the readers close this turn before the model decides")

    def chat(self, _text: str, **kwargs: object) -> tuple[str, list[object]]:
        self.chat_kinds.append(str(kwargs.get("conversation_kind")))
        return "Respuesta.", []

    @staticmethod
    def public_lookup_requested(_text: str) -> bool:
        return False

    @staticmethod
    def _verify_semantic_effect_shape(_text: str) -> tuple[str, str]:
        return "no_effect", "zero"

    @staticmethod
    def detect_response_language(_text: str) -> str:
        return "es"

    @staticmethod
    def consume_deferred_response_language(_text: str) -> tuple[bool, str | None]:
        return True, "es"

    @staticmethod
    def retire_deferred_response_language(_text: str) -> None:
        return None


def _turn(text: str) -> dict[str, object]:
    tools = {
        name: _tool(name, required=required)
        for name, required in (
            ("system.time", ()),
            ("web.search", ("query",)),
            ("notification.schedule", ("dueUtc", "kind", "title")),
            ("notification.list", ()),
            ("input.text.type", ("text",)),
        )
    }
    return _prepare_turn_result(
        {"id": "turn-tanda05", "text": text},
        llm=_ClosedLlm(),
        planner_catalog=PlannerCatalog(list(tools.values())),
        turn_evidence=_NoEvidence(),
        encoder=lambda _texts: (),
        tool_by_name=tools,
    )


@pytest.mark.parametrize(
    "text", ["dime el mes actual", "i need information on today's date", "¿estamos a mitad de semana?", "dime hora que es"],
)
def test_the_turn_reads_the_clock(text: str) -> None:
    result = _turn(text)
    assert result["kind"] == "action"
    assert result["operation"] == "system.time"


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        ("cien mil doscientas veintitrés", "knowledge"),
        ("one hundred and five in digits", "knowledge"),
        ("configuré una alarma para despertarme por la mañana", "social"),
        ("I've already set a timer for the pasta", "social"),
    ],
)
def test_the_turn_answers_in_conversation(text: str, kind: str) -> None:
    result = _turn(text)
    assert result["kind"] == "conversation"
    assert result["effectOperations"] == []
    assert result["conversationKind"] == kind
