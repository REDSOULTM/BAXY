"""Auditoría semántica 2026-09-20 (REOPEN1993, grupo W): la encuesta pide el
clima, no páginas sobre el clima. Doce filas (H0034, H0061, H0339, H0415,
H0431, H0478, H0590, H0617, H0664, H0689, H0699, H0708) pasan de una
web.search «fallida por resultados no pertinentes» a una lectura tipada
weather.current del lugar nombrado o de la ubicación de este PC."""

from __future__ import annotations

import pytest

from baxy_mind import effect_intent, llm

AVAILABLE = frozenset({"web.search", "weather.current", "system.time", "app.open"})


@pytest.mark.parametrize(
    ("text", "location"),
    [
        ("busca el clima en Buenos Aires", "Buenos Aires"),
        ("busca el clima en buenos aires", "buenos aires"),
        ("qué clima hace hoy en Buenos Aires", "Buenos Aires"),
        ("que clima hace ahora en buenos aires", "buenos aires"),
        ("cual es el clima en buenos aires", "buenos aires"),
        ("qué clima hace en Buenos Aires", "Buenos Aires"),
        ("buscá el clima en madrid", "madrid"),
        ("qué clima hace hoy", None),
        ("mostrame el clima", None),
        ("va a llover mañana", None),
        # «en google» y «en internet» son medios, no lugares (H0431, H0708).
        ("buscá el clima en google", None),
        ("busca el clima en internet", None),
    ],
)
def test_weather_questions_are_a_typed_weather_read(text: str, location: str | None) -> None:
    intent = effect_intent._weather_read_intent(text, AVAILABLE)
    assert intent is not None and intent.operations == ("weather.current",)
    assert effect_intent._weather_location(text) == location
    assert effect_intent.operation_domain_is_grounded(text, "weather.current") is True


def test_a_name_that_is_not_a_place_still_goes_to_the_service_which_answers_it_honestly() -> None:
    # H0266 «busca el clima en Bruno Mars»: the read asks the service for that
    # place and reports weather_place_not_found; nothing is invented.
    assert effect_intent._weather_location("busca el clima en Bruno Mars") == "Bruno Mars"


def test_without_the_typed_read_the_weather_stays_a_web_search() -> None:
    assert effect_intent._weather_read_intent("qué clima hace hoy", {"web.search"}) is None


def test_a_compound_request_keeps_its_clause_reader() -> None:
    assert effect_intent._weather_read_intent(
        "abrí la calculadora y decime el clima", AVAILABLE
    ) is None


SEEN = {
    "location": "Buenos Aires",
    "country": "Argentina",
    "temperatureC": 18.8,
    "apparentC": 20.2,
    "humidityPercent": 92,
    "windKmh": 8.0,
    "precipitationMm": 0.0,
    "condition": "nublado",
    "today": {"maxC": 22.1, "minC": 14.0, "rainProbabilityPercent": 10},
    "tomorrow": {"maxC": 21.0, "minC": 12.5, "rainProbabilityPercent": 65, "condition": "lluvia débil"},
}
PAYLOAD = {"operation": "weather.current", "seen": SEEN}


@pytest.mark.parametrize(
    ("text", "asked", "defect"),
    [
        ("En Buenos Aires hay 18,8 °C, sensación de 20,2 °C, y está nublado.", "busca el clima en Buenos Aires", ""),
        ("En Buenos Aires hay 19 °C y está nublado.", "busca el clima en Buenos Aires", ""),
        ("En Buenos Aires hay 25 °C y está nublado.", "busca el clima en Buenos Aires", "invented_number"),
        ("Hay 19 °C y está nublado.", "busca el clima en Buenos Aires", "missing_state"),
        ("Mañana en Buenos Aires hay 65 % de probabilidad de lluvia, con máxima de 21 °C.", "va a llover mañana", ""),
        ("Mañana en Buenos Aires va a llover.", "va a llover mañana", "missing_state"),
        ("Encontré varias páginas sobre el clima en Buenos Aires.", "busca el clima en Buenos Aires", "missing_state"),
    ],
)
def test_the_reply_carries_only_observed_numbers_and_the_place(text: str, asked: str, defect: str) -> None:
    assert llm._weather_fact_defect(text, PAYLOAD, asked) == defect
    assert llm._payload_fact_defect(text, PAYLOAD, asked) == defect


def test_the_absences_have_their_own_cause_facts() -> None:
    for code in ("weather_place_not_found", "weather_location_unavailable", "weather_service_unavailable"):
        assert code in llm._CAUSE_FACT
