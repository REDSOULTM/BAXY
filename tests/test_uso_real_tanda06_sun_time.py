"""Tanda 6 (2026-09-24): t1 «he quedado con un amigo a la salida del sol mañana para correr, ¿qué hora será?»
searched the web and ended in no_response. The clause after the comma only asks when; the whole message is one
weather read (semantic.system._weather_read_intent), and tomorrow's sunrise is the answer.
"""

from __future__ import annotations

import json

import pytest

from baxy_mind import llm
from baxy_mind.semantic.reading import read

_OPERATIONS = ("system.time", "web.search", "weather.current", "media.play.query", "audio.volume")


def _effects(text: str) -> tuple[str, ...] | None:
    effects = read(text, available_operations=_OPERATIONS).effects
    return None if effects is None else effects.operations


_SEEN = {
    "location": "Curicó", "country": "Chile", "locatedBy": "public_ip_address", "temperatureC": 16.4,
    "apparentC": 15.8, "humidityPercent": 74, "windKmh": 2.3, "precipitationMm": 0, "condition": "nublado",
    "today": {"maxC": 17.1, "minC": 10.2, "rainProbabilityPercent": 3, "sunrise": "07:12", "sunset": "19:31"},
    "tomorrow": {"date": "2026-09-25", "maxC": 18.0, "minC": 11.0, "rainProbabilityPercent": 5,
                 "condition": "despejado", "sunrise": "07:10", "sunset": "19:32"},
}
_WEATHER = {
    "kind": "operation", "operation": "weather.current", "polarity": "success", "verified": True, "succeeded": True,
    "observed": {"version": 1, **_SEEN},
}
_T1 = "he quedado con un amigo a la salida del sol mañana para correr, ¿qué hora será?"


@pytest.mark.parametrize(
    "text",
    [
        _T1,  # t1, verbatim
        "quedé con mi hermana al atardecer, ¿a qué hora es?",
        "voy a pasear al perro cuando se ponga el sol mañana, ¿a qué hora?",
        "I'm meeting a friend at sunrise tomorrow to go running, what time is that?",
        "we're going fishing at dawn tomorrow, when is it?",
        "tengo una cita al amanecer, ¿cuándo es?",
    ],
)
def test_a_sun_time_asked_after_a_comma_is_one_weather_read(text: str) -> None:
    assert _effects(text) == ("weather.current",)


@pytest.mark.parametrize(
    "text",
    [
        "he quedado con un amigo mañana para correr, ¿qué hora será?",
        "espérame hasta que salga el sol",
        "dime el clima y pon música",
    ],
)
def test_no_sun_time_or_a_second_request_is_not_that_read(text: str) -> None:
    assert _effects(text) != ("weather.current",)


@pytest.mark.parametrize(
    ("reply", "published"),
    [
        ("Mañana el sol sale a las 07:10.", True),
        ("Mañana sale el sol a las 7:10, perfecto para correr.", True),
        ("Mañana el sol sale a las 07:12.", False),  # today's sunrise
        ("No se puede determinar la hora exacta de la salida del sol mañana.", False),
    ],
)
def test_tomorrows_sunrise_is_the_answer(reply: str, published: bool) -> None:
    facts = {"situation": json.dumps(_WEATHER)}
    payload = {"operation": "weather.current", "seen": _SEEN}
    defect = llm.compose_visible_defect(reply, "status", _T1, facts) or llm._payload_fact_defect(reply, payload, _T1)
    assert (defect == "") is published
