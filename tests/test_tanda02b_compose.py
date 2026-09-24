"""tanda-02b: compositions that ended in ⚠ with an honest draft, and a
recomposed conversation that answered the previous topic with an invented date.

Situations are synthetic (place and figures invented for the test); the
requests are the tanda's."""

from __future__ import annotations

import json

import pytest

from baxy_mind import llm

_SEEN = {
    "location": "Rosario",
    "country": "Argentina",
    "locatedBy": "public_ip_address",
    "temperatureC": 17.3,
    "apparentC": 16,
    "humidityPercent": 71,
    "windKmh": 6.1,
    "precipitationMm": 0,
    "condition": "nublado",
    "today": {"maxC": 21, "minC": 11.2, "rainProbabilityPercent": 6, "sunrise": "07:02", "sunset": "19:21"},
    "tomorrow": {"maxC": 22.5, "minC": 12.5, "rainProbabilityPercent": 35, "sunrise": "07:01", "sunset": "19:22"},
}
_WEATHER = {
    "kind": "operation", "operation": "weather.current", "polarity": "success",
    "verified": True, "succeeded": True, "observed": {"version": 1, **_SEEN},
}
_PAYLOAD = {"operation": "weather.current", "seen": _SEEN}
_AMOUNT = "¿Cuántas pulgadas are we getting today?"
_SUNSET = "necesito el horario de la caída del sol para mañana."


def _weather_defect(text: str, asked: str) -> str:
    facts = {"situation": json.dumps(_WEATHER)}
    return llm.compose_visible_defect(text, "status", asked, facts) or llm._payload_fact_defect(text, _PAYLOAD, asked)


@pytest.mark.parametrize("reply", [
    "No tengo la cantidad en pulgadas, pero hoy hay un 6 % de probabilidad de lluvia.",
    "No se proporciona información sobre pulgadas de precipitación hoy. La lluvia tiene una probabilidad del 6%.",
    "Hoy no está lloviendo (0 mm) y la probabilidad de lluvia es del 6 %.",
])
def test_an_honest_rain_amount_answer_with_todays_probability_is_published(reply: str) -> None:
    assert _weather_defect(reply, _AMOUNT) == ""


@pytest.mark.parametrize(("reply", "defect"), [
    # An observed number said as an amount is an invented amount.
    ("Hoy caerán 16 pulgadas, con un 6 % de probabilidad de lluvia.", "invented_number"),
    ("Hoy caerán 6 mm de lluvia.", "invented_number"),
    # Tomorrow's probability does not answer a question about today, and a
    # figure that merely contains the digits («21 %» for 6 %) is not it.
    ("Mañana hay un 35 % de probabilidad de lluvia.", "missing_state"),
    ("Hoy la probabilidad de lluvia es del 21 %.", "missing_state"),
    ("Hoy no va a llover.", "missing_state"),
    ("Hoy la probabilidad de lluvia es del 40 %.", "invented_number"),
])
def test_an_invented_or_wrong_day_rain_answer_still_fails(reply: str, defect: str) -> None:
    assert _weather_defect(reply, _AMOUNT) == defect


def test_a_rain_question_without_a_day_accepts_either_read_day_and_a_named_place_is_still_required() -> None:
    assert _weather_defect("Hay un 35 % de probabilidad de lluvia mañana en Rosario.", "¿necesito paraguas?") == ""
    assert _weather_defect("Hoy hay un 6 % de probabilidad de lluvia.", "¿necesito paraguas?") == ""
    assert _weather_defect("Hoy hay un 6 % de probabilidad de lluvia.", "¿llueve hoy en Rosario?") == "missing_state"
    assert _weather_defect("En Rosario hoy hay un 6 % de probabilidad de lluvia.", "¿llueve hoy en Rosario?") == ""
    # A general report still names the place it read.
    assert _weather_defect("Hay 17,3 °C y está nublado.", "qué clima hace hoy") == "missing_state"


@pytest.mark.parametrize("reply", [
    "La puesta del sol mañana en Rosario será a las 19:22.",
    "Mañana el sol se pone a las 19:22.",
])
def test_the_observed_sun_clock_is_not_an_invented_clock(reply: str) -> None:
    assert _weather_defect(reply, _SUNSET) == ""


@pytest.mark.parametrize(("reply", "defect"), [
    ("Mañana el sol se pone a las 20:15.", "extra_claim"),
    ("Mañana el sol se pone a las 19:21.", "missing_state"),
])
def test_an_unread_or_wrong_day_sun_clock_still_fails(reply: str, defect: str) -> None:
    assert _weather_defect(reply, _SUNSET) == defect


def test_a_number_that_ends_the_sentence_is_checked_too() -> None:
    assert llm._weather_fact_defect("En Rosario hay 17,3 °C y mañana el sol se pone a las 20:15.", _PAYLOAD, _SUNSET) == "invented_number"
    assert llm._weather_fact_defect("En Rosario hace 25.", _PAYLOAD, "qué clima hace") == "invented_number"


_CONVERSATION = {"situation": json.dumps({"kind": "conversation", "polarity": "success"})}
_HTML = "¿Cómo incluir un archivo HTML en otro  HTML?"


@pytest.mark.parametrize("reply", [
    "Incluyes el archivo HTML dentro de otro usando la etiqueta <iframe> con la ruta del archivo.",
    "Puedes usar <iframe> o copiar el contenido dentro de <body>.",
])
def test_an_html_element_in_a_technical_answer_is_not_a_template_hole(reply: str) -> None:
    assert llm.compose_visible_defect(reply, "conversation", _HTML, _CONVERSATION) == ""


@pytest.mark.parametrize("reply", [
    "Usa la etiqueta <nombre del archivo>.",
    "La hora actual es <hora actual>.",
    "Incluye <archivo> en la página.",
])
def test_a_template_hole_in_angle_brackets_still_fails(reply: str) -> None:
    assert llm.compose_visible_defect(reply, "conversation", _HTML, _CONVERSATION) == "copied_instruction"


_PREVIOUS = "Dentro de 64 días será el 27 de noviembre."
_WITH_CONTEXT = {**_CONVERSATION, "context": _PREVIOUS, "priorRequests": ["what will the date be in 64 days"]}


@pytest.mark.parametrize("request_text", ["¡ave, cesar!", "chistes", "¿Porque el cielo es celeste?"])
def test_a_message_that_stands_on_its_own_does_not_inherit_the_previous_answer(request_text: str) -> None:
    assert llm._referenced_previous_answer(request_text, _WITH_CONTEXT) == ""


@pytest.mark.parametrize("request_text", ["¿y eso qué significa?", "¿por qué?", "explícamelo mejor"])
def test_a_follow_up_that_points_back_keeps_the_previous_answer(request_text: str) -> None:
    assert llm._referenced_previous_answer(request_text, _WITH_CONTEXT) == _PREVIOUS


def test_a_recomposed_conversation_cannot_answer_the_previous_topic_with_an_unread_date() -> None:
    invented = "Hoy sumando 64 días sería el 10 de abril."
    assert llm.compose_visible_defect(invented, "conversation", "¡ave, cesar!", _WITH_CONTEXT) == "unverified_present_fact"
    # Even the previous answer's own date is not this message's answer.
    restated = "Dentro de 64 días será el 27 de noviembre."
    assert llm.compose_visible_defect(restated, "conversation", "¡ave, cesar!", _WITH_CONTEXT) == "unverified_present_fact"
    assert llm.compose_visible_defect("Hoy es martes.", "conversation", "¡ave, cesar!", _CONVERSATION) == "unverified_present_fact"
    assert llm.compose_visible_defect("Today is September 3.", "conversation", "hi there", _CONVERSATION) == "unverified_present_fact"


@pytest.mark.parametrize("reply", [
    "¡Ave, César! ¿Cómo estás? ¿Qué tal si contamos un chiste rápido? 😄",
    "¡Ave! Hoy te saludo como un romano.",
    "La Revolución Francesa empezó en 1789.",
])
def test_a_social_or_knowledge_reply_without_a_present_claim_is_published(reply: str) -> None:
    assert llm.compose_visible_defect(reply, "conversation", "¡ave, cesar!", _WITH_CONTEXT) == ""


def test_a_follow_up_may_restate_what_the_previous_answer_said() -> None:
    reply = "Que dentro de 64 días será el 27 de noviembre."
    assert llm.compose_visible_defect(reply, "conversation", "¿y eso qué significa?", _WITH_CONTEXT) == ""
    assert llm.compose_visible_defect(
        "Que dentro de 64 días será el 2 de diciembre.", "conversation", "¿y eso qué significa?", _WITH_CONTEXT,
    ) == "unverified_present_fact"


def test_what_the_person_said_can_be_repeated() -> None:
    assert llm.compose_visible_defect(
        "Dentro de 3 días, el viernes, es tu festival.", "conversation",
        "el viernes tengo un festival, dentro de 3 días", _CONVERSATION,
    ) == ""
