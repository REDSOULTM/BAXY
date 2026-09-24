"""Uso real tandas 5e and 6 (2026-09-24): weather fields and web answers that did not answer.

1. «Dime el UV index» got a web definition of the UV index and «¿Cómo esta el dew point ahora» a page about a dew
   point map: the UV index (now and the day's peak) and the dew point are readings of the weather read. Owners:
   semantic/web._SKY_MEASURE_WORDS / weather_asked_measures; provider OpenMeteoWeatherAdapter (C# tests); composer
   llm._weather_focus / _weather_fact_defect.
2. «cuál es el pronóstico del tiempo para la semana» got today and tomorrow only: the seven days come in the same
   read (``laterDays`` after tomorrow, each with its weekday), are sent to the composer only when the question asks
   the coming days, and the reply sums them up. Owners: semantic/web.weather_asks_week / weather_asks_coming_days;
   provider OpenMeteoWeatherAdapter (C# tests); llm._compose_situation_payload / _weather_focus / _weather_fact_defect.
3. «let me know my current location» was answered with the place and then the temperature, humidity and wind: the
   weather in a place reply is an unasked claim, repaired with the place focus. Owner: llm._weather_fact_defect and
   the extra_claim hint.
4. «he quedado con un amigo a la salida del sol mañana para correr, ¿qué hora será?» searched the whole sentence and
   ended in ⚠: a sun time told and then asked by a bare time question is the weather read. Owner:
   semantic/system._weather_read_intent / _sun_time_asked_after_it.

Every list mixes Spanish, English and Spanglish and holds phrasings never seen in a run; negative controls keep what
is not the live reading out of it.
"""

from __future__ import annotations

import json

import pytest

from baxy_mind import effect_intent, llm
from baxy_mind.semantic.web import weather_asked_measures
from test_c03_cpu_actor import Recorder

AVAILABLE = ("weather.current", "web.search", "system.time", "note.create", "app.open")


def _operations(text: str) -> tuple[str, ...] | None:
    intent = effect_intent.resolve_explicit_effects(text, AVAILABLE, ("Steam",), ())
    return None if intent is None else intent.operations


_SEEN = {
    "location": "Curicó",
    "region": "Región de Curicó",
    "country": "Chile",
    "locatedBy": "public_ip_address",
    "temperatureC": 16.4,
    "apparentC": 16.7,
    "humidityPercent": 74,
    "windKmh": 2.3,
    "precipitationMm": 0,
    "uvIndex": 0.4,
    "dewPointC": 11.8,
    "condition": "nublado",
    "today": {"maxC": 18.9, "minC": 12.6, "rainProbabilityPercent": 2, "uvIndexMax": 5.9,
              "sunrise": "07:33", "sunset": "19:44"},
    "tomorrow": {"date": "2026-09-25", "maxC": 20.5, "minC": 12.4, "rainProbabilityPercent": 10, "uvIndexMax": 6.3,
                 "condition": "nublado", "sunrise": "07:31", "sunset": "19:45"},
    "airQuality": {"usAqi": 84, "category": "moderada", "pm25": 15.9, "pm10": 21.4},
}
_WEATHER = {"operation": "weather.current", "seen": _SEEN}


def _weather_situation(seen: dict) -> dict:
    return {"kind": "operation", "operation": "weather.current", "polarity": "success", "verified": True,
            "succeeded": True, "observed": {"version": 1, **seen, "authority": "open_meteo_forecast_v1"}}


# --- 1. the UV index and the dew point are the weather read ------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "place"),
    [
        ("Dime el UV index", None),
        ("¿Cómo esta el dew point ahora", None),
        ("what's the uv index today", None),
        ("cuál es el índice UV en Lima", "Lima"),
        ("how high is the UV index right now in Miami", "Miami"),
        ("índice de radiación UV en Madrid hoy", "Madrid"),
        ("el índice UV de hoy?", None),
        ("dime el punto de rocío", None),
        ("what's the dew point outside", None),
        ("necesito saber el punto de rocío", None),
        ("hey baxy, qué tal el dew point hoy", None),
        ("UV index tomorrow in Cancun", "Cancun"),
    ],
)
def test_the_uv_index_and_the_dew_point_are_read_not_searched(text: str, place: str | None) -> None:
    assert _operations(text) == ("weather.current",), text
    assert effect_intent._weather_location(text) == place
    assert effect_intent.operation_domain_is_grounded(text, "weather.current") is True


@pytest.mark.parametrize(
    "text",
    [
        # What the index is, what it means or how to protect oneself is a topic, looked up.
        "qué es el índice UV",
        "what does the dew point mean",
        "cómo protegerme de la radiación UV hoy",
        # A UV lamp or filter is not the sky.
        "compra una lámpara UV",
        "dime cómo funciona una lámpara uv",
        "busca filtros UV para cámara",
        # Said, not asked.
        "the uv index is a scale from 0 to 11",
    ],
)
def test_what_is_not_the_live_uv_or_dew_point_is_not_the_weather_read(text: str) -> None:
    assert _operations(text) != ("weather.current",), text


@pytest.mark.parametrize(
    ("text", "measures"),
    [
        ("Dime el UV index", {"uv"}),
        ("¿qué tan fuerte está la radiación ultravioleta?", {"uv"}),
        ("¿Cómo esta el dew point ahora", {"dew_point"}),
        ("dime el punto de rocío y la humedad", {"dew_point", "humidity"}),
        ("¿qué tiempo hace hoy?", set()),
    ],
)
def test_the_uv_index_and_the_dew_point_are_measures_the_question_names(text: str, measures: set[str]) -> None:
    assert weather_asked_measures(text) == frozenset(measures)


@pytest.mark.parametrize(
    ("asked", "reply"),
    [
        ("Dime el UV index", "El índice UV ahora es 0,4 y hoy llegó a un máximo de 5,9."),
        ("what's the uv index today", "The UV index is 0.4 now; today's peak is 5.9."),
        ("el índice UV de hoy?", "Hoy el UV llega a 6."),
        ("UV index tomorrow", "Tomorrow the UV index peaks at 6.3."),
        ("¿Cómo esta el dew point ahora", "El punto de rocío está en 11,8 °C."),
        ("what's the dew point outside", "The dew point is 11.8°C."),
    ],
)
def test_the_uv_and_dew_point_replies_say_the_observed_value(asked: str, reply: str) -> None:
    assert llm._weather_fact_defect(reply, _WEATHER, asked) == ""
    assert llm._payload_fact_defect(reply, _WEATHER, asked) == ""


@pytest.mark.parametrize(
    ("asked", "reply", "defect"),
    [
        # A definition or the temperature is not the asked value.
        ("Dime el UV index", "El índice UV mide la radiación ultravioleta del sol.", "missing_state"),
        ("Dime el UV index", "En Curicó hay 16,4 °C.", "missing_state"),
        # Tomorrow's peak is asked; today's is another day.
        ("UV index tomorrow", "The UV index peaks at 5.9.", "missing_state"),
        ("¿Cómo esta el dew point ahora", "La humedad está en 74 %.", "missing_state"),
        # An unread value is invented.
        ("Dime el UV index", "El índice UV ahora es 8.", "invented_number"),
        ("what's the dew point outside", "The dew point is 14°C.", "invented_number"),
    ],
)
def test_a_uv_or_dew_point_reply_without_the_observed_value_falls(asked: str, reply: str, defect: str) -> None:
    assert llm._weather_fact_defect(reply, _WEATHER, asked) == defect


@pytest.mark.parametrize(
    ("asked", "language", "named"),
    [
        ("Dime el UV index", "es", "seen.uvIndex (ahora) y today.uvIndexMax"),
        ("what's the uv index today", "en", "seen.uvIndex (now) and today.uvIndexMax"),
        ("UV index tomorrow", "en", "tomorrow.uvIndexMax"),
        ("¿Cómo esta el dew point ahora", "es", "el punto de rocío (dewPointC)"),
    ],
)
def test_the_instruction_asks_for_the_uv_or_dew_point_value(asked: str, language: str, named: str) -> None:
    instruction = llm._weather_answer_instruction(asked, language)
    assert named in instruction
    assert "Di la temperatura actual y el cielo" not in instruction
    assert "Say the current temperature and sky" not in instruction


def test_a_weather_draft_that_missed_the_asked_value_is_repaired_with_that_focus() -> None:
    # The retry hint of a weather draft was the window hint («abierto/open»); it is the asked focus now.
    missed = "El índice UV mide la radiación ultravioleta."
    answer = "El índice UV ahora es 0,4 y hoy llegó a 5,9."
    client = Recorder([missed, answer])
    reply = client.compose_user_message("Dime el UV index", "status", {"situation": json.dumps(_weather_situation(_SEEN))})
    assert reply == answer
    retry = json.dumps(client.payloads[1]["messages"], ensure_ascii=False)
    assert "seen.uvIndex (ahora) y today.uvIndexMax" in retry
    assert "abierto/open" not in retry


# --- 2. the week's forecast is read and summed up briefly ---------------------------------------------------------

_LATER = [
    {"date": "2026-09-26", "weekday": "sábado", "condition": "lluvia", "maxC": 17.2, "minC": 11.0,
     "rainProbabilityPercent": 70},
    {"date": "2026-09-27", "weekday": "domingo", "condition": "lluvia débil", "maxC": 16.0, "minC": 10.2,
     "rainProbabilityPercent": 45},
    {"date": "2026-09-28", "weekday": "lunes", "condition": "parcialmente nublado", "maxC": 19.4, "minC": 11.5,
     "rainProbabilityPercent": 5},
    {"date": "2026-09-29", "weekday": "martes", "condition": "despejado", "maxC": 21.1, "minC": 12.0,
     "rainProbabilityPercent": 0},
    {"date": "2026-09-30", "weekday": "miércoles", "condition": "mayormente despejado", "maxC": 22.3, "minC": 13.1,
     "rainProbabilityPercent": 3},
]
_WEEK_SEEN = {**_SEEN, "laterDays": _LATER}
_WEEK = {"operation": "weather.current", "seen": _WEEK_SEEN}


@pytest.mark.parametrize(
    "text",
    [
        "cuál es el pronóstico del tiempo para la semana",
        "what's the forecast for the week",
        "dame el clima de los próximos días",
        "how's the weather looking the next few days",
        "el weather de esta semana porfa",
        "pronóstico extendido para Lima",
        "weekly forecast",
        "¿va a llover el resto de la semana?",
    ],
)
def test_the_week_is_asked_as_the_coming_days(text: str) -> None:
    assert _operations(text) == ("weather.current",), text
    assert llm.weather_asks_week(text)
    assert llm.weather_asks_coming_days(text)


@pytest.mark.parametrize(
    ("text", "coming"),
    [
        ("¿el sábado podremos comer al aire libre en Sevilla?", True),
        ("clima para pasado mañana", True),
        ("will it rain on friday", True),
        # Today, tomorrow or no day: the read of today and tomorrow answers them.
        ("¿qué tiempo hace hoy?", False),
        ("¿llueve mañana?", False),
        ("how's the weather", False),
        # The week gone by is no forecast.
        ("¿llovió la semana pasada?", False),
    ],
)
def test_a_day_after_tomorrow_is_one_of_the_coming_days(text: str, coming: bool) -> None:
    assert llm.weather_asks_coming_days(text) is coming
    assert llm.weather_asks_week(text) is False


@pytest.mark.parametrize(
    ("asked", "reply"),
    [
        ("cuál es el pronóstico del tiempo para la semana",
         "Esta semana en Curicó irá de 10,2 a 22,3 °C, con lluvia probable el sábado (70 %) y el domingo (45 %)."),
        ("what's the forecast for the week",
         "This week in Curicó highs go from 16 to 22.3°C; rain is likely on Saturday (70%)."),
        ("¿va a llover el resto de la semana?", "El sábado hay un 70 % de probabilidad de lluvia y el domingo un 45 %."),
        ("¿el sábado podremos comer al aire libre en Curicó?",
         "El sábado en Curicó habrá lluvia, con 70 % de probabilidad y máxima de 17,2 °C."),
        ("will it rain on tuesday", "Tuesday looks dry: 0% chance of rain."),
        ("clima para pasado mañana", "Pasado mañana, el sábado, habrá lluvia con máxima de 17,2 °C en Curicó."),
    ],
)
def test_the_coming_days_are_answered_from_the_days_read(asked: str, reply: str) -> None:
    assert llm._weather_fact_defect(reply, _WEEK, asked) == ""


@pytest.mark.parametrize(
    ("asked", "reply", "defect"),
    [
        # The t39 reply: today and tomorrow only, for the week.
        ("cuál es el pronóstico del tiempo para la semana",
         "En Curicó hay 16,4 °C y está nublado; mañana máxima de 20,5 °C y mínima de 12,4 °C.", "missing_state"),
        ("¿el sábado podremos comer al aire libre en Curicó?", "En Curicó hay 16,4 °C.", "missing_state"),
        # A figure of no day read is invented.
        ("what's the forecast for the week", "This week highs reach 25°C in Curicó.", "invented_number"),
    ],
)
def test_the_coming_days_are_not_answered_with_today_or_an_unread_figure(asked: str, reply: str, defect: str) -> None:
    assert llm._weather_fact_defect(reply, _WEEK, asked) == defect


@pytest.mark.parametrize(
    ("asked", "reply", "defect"),
    [
        # The weekday named is today's: the weather now answers it.
        ("¿qué tiempo hace hoy jueves?", "Hoy jueves en Curicó hay 16,4 °C y está nublado.", ""),
        ("¿cómo estará el jueves?", "El jueves en Curicó hay 16,4 °C.", ""),
        ("what's the weather like today, thursday", "Today in Curicó it's 16.4°C and cloudy.", ""),
        # Another weekday is not answered with the weather now.
        ("¿cómo estará el lunes?", "En Curicó hay 16,4 °C.", "missing_state"),
    ],
)
def test_a_weekday_that_is_today_is_answered_with_the_weather_now(asked: str, reply: str, defect: str) -> None:
    seen = {**_WEEK_SEEN, "today": {**_SEEN["today"], "date": "2026-09-24", "weekday": "jueves"}}
    assert llm._weather_fact_defect(reply, {"operation": "weather.current", "seen": seen}, asked) == defect


def test_the_week_instruction_sums_up_the_days_after_tomorrow() -> None:
    instruction = llm._weather_answer_instruction("cuál es el pronóstico del tiempo para la semana", "es")
    assert "seen.laterDays" in instruction
    assert "sin enumerar cada día" in instruction
    assert "La lectura cubre sólo hoy y mañana" not in instruction
    # A question about today still says the read it has.
    today = llm._weather_answer_instruction("¿qué tiempo hace hoy?", "es")
    assert "seen.laterDays" not in today
    assert "La lectura cubre sólo hoy y mañana" in today


@pytest.mark.parametrize(
    ("asked", "sent"),
    [
        ("cuál es el pronóstico del tiempo para la semana", True),
        ("¿el sábado podremos comer al aire libre?", True),
        ("¿qué tiempo hace hoy?", False),
        ("¿llueve mañana?", False),
    ],
)
def test_the_days_after_tomorrow_are_sent_only_when_asked(asked: str, sent: bool) -> None:
    payload = llm._compose_situation_payload(_weather_situation(_WEEK_SEEN), "es", asked)
    assert ("laterDays" in payload["seen"]) is sent
    assert payload["seen"]["temperatureC"] == 16.4


# --- 3. where the person is: only the place ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("asked", "reply"),
    [
        ("let me know my current location", "You are in Curicó, Región de Curicó, Chile."),
        ("¿dónde estoy ahora mismo?", "Estás en Curicó, Chile."),
        ("where am i rn", "Around Curicó, Chile."),
        ("en qué ciudad estoy", "En Curicó, en la Región de Curicó."),
    ],
)
def test_the_place_reply_is_the_place_alone(asked: str, reply: str) -> None:
    assert llm._weather_fact_defect(reply, _WEATHER, asked) == ""


@pytest.mark.parametrize(
    ("asked", "reply"),
    [
        # The t21 reply: the place and then the weather nobody asked for.
        ("let me know my current location",
         "You are currently in Curico, Region de Curico, Chile. The temperature is 16.4°C, with a humidity "
         "of 74% and wind speed of 2.3 km/h."),
        ("¿dónde estoy?", "Estás en Curicó, Chile, y está nublado."),
        ("where am i", "You're in Curicó, Chile, where the weather is mild."),
    ],
)
def test_the_weather_added_to_the_place_is_an_extra_claim(asked: str, reply: str) -> None:
    assert llm._weather_fact_defect(reply, _WEATHER, asked) == "extra_claim"


def test_a_place_reply_with_the_weather_is_repaired_with_the_place_focus() -> None:
    added = "Estás en Curicó, Chile. Hay 16,4 °C."
    answer = "Estás en Curicó, Chile."
    client = Recorder([added, answer])
    reply = client.compose_user_message("¿dónde estoy?", "status", {"situation": json.dumps(_weather_situation(_SEEN))})
    assert reply == answer
    retry = json.dumps(client.payloads[1]["messages"], ensure_ascii=False)
    assert "nada del clima" in retry


# --- 4. a sun time told, then asked «¿qué hora será?» ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "place"),
    [
        ("he quedado con un amigo a la salida del sol mañana para correr, ¿qué hora será?", None),
        ("i'm meeting a friend at sunrise tomorrow, what time is that?", None),
        ("voy a salir a correr al amanecer, ¿a qué hora es?", None),
        ("quiero ver la puesta de sol hoy, what time?", None),
        ("i am going to watch the sunset in Malibu today, what time is that?", "Malibu"),
    ],
)
def test_a_sun_time_told_and_then_asked_is_the_weather_read(text: str, place: str | None) -> None:
    assert _operations(text) == ("weather.current",), text
    assert effect_intent._weather_location(text) == place


@pytest.mark.parametrize(
    "text",
    [
        # The clock now, asked after a remark about the sunset.
        "el atardecer me encanta, ¿qué hora es?",
        "sunset is beautiful, what time is it?",
        # An order and a question are two requests.
        "pon música al atardecer, ¿a qué hora será?",
    ],
)
def test_the_clock_now_or_an_order_is_not_the_sun_time(text: str) -> None:
    assert _operations(text) != ("weather.current",), text


def test_the_sun_time_told_is_answered_with_tomorrows_clock() -> None:
    asked = "he quedado con un amigo a la salida del sol mañana para correr, ¿qué hora será?"
    assert llm._weather_fact_defect("Mañana el sol sale a las 07:31.", _WEATHER, asked) == ""
    assert llm._weather_fact_defect("Mañana el sol sale a las 07:33.", _WEATHER, asked) == "missing_state"
