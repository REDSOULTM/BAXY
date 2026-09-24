"""Uso real tanda 4c (2026-09-24, official window): the person's place. BAXY already read the weather of this PC's
city («Hoy en Curicó…») while, in the same session:

1. «i'd like to know my current location» got «I don't have access to your current location». Where the person is,
   asked as a whole question, is the weather read (it locates this PC by its public address and names the place).
   Owner: semantic/web.asks_own_place, read by _weather_lookup_query; composer llm._weather_fact_defect.
2. «dime la hora exacta de la puesta de sol en Badalona» searched pages about Chile's clock: «puesta de sol» is the
   sun time of the weather read. Owner: semantic/web._WEATHER_SUN_TIME.
3. «Whats the air quality hoy?» took 13.7 s and answered with a list of US pages: the air of a place is read with
   its weather (same public service). Owner: semantic/web.AIR_QUALITY_WORDS / weather_asks_air; provider
   OpenMeteoWeatherAdapter (C# tests); composer llm._weather_fact_defect.
4. «en qué lugares puedo pedir comida para llevar cerca» and «dime que esta pasando en mi ciudad» were searched
   without the place: near the person is searched near this PC's city (``nearby``; the provider adds only the city
   name). A request that names another place near which to look never gets the person's city. Owner:
   semantic/web.near_the_person; __main__._ground_explicit_arguments; WebBrowserAdapter (C# tests).

Every list mixes Spanish, English and Spanglish and holds phrasings never seen in a run.
"""

from __future__ import annotations

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind import effect_intent, llm
from baxy_mind.semantic.web import asks_own_place, near_the_person, weather_asks_air, weather_asks_sun_time

AVAILABLE = ("weather.current", "web.search", "web.news.headlines", "system.time", "app.open", "browser.navigate")
SEARCH_SCHEMA = {
    "type": "object",
    "properties": {
        "limit": {"type": "integer", "minimum": 1, "maximum": 20},
        "nearby": {"type": ["boolean", "null"]},
        "query": {"type": "string", "x-maxUtf8Bytes": 2000, "x-nonWhitespace": True},
    },
    "required": ["query"],
    "additionalProperties": False,
}


def _read(text: str) -> tuple[str, ...] | None:
    intent = effect_intent.resolve_explicit_effects(text, AVAILABLE, (), ())
    return intent.operations if intent is not None else None


# ---------------------------------------------------------------- 1. where the person is

_OWN_PLACE = [
    "i'd like to know my current location",  # tanda 4c t4
    "¿Dónde me encuentro ahora mismo?",
    "what's my location right now",
    "oye, en qué ciudad estamos?",
    "tell me where I am",
    "sabes dónde estoy?",
    "cuál es mi ubicación actual",
    "which country am I in",
    "where is this pc located",
    "dime mi ubicación",
]

_NOT_OWN_PLACE = [
    "dónde estoy guardando las fotos",
    "comparte mi ubicación con mamá",
    "where am I in the queue",
    "en qué carpeta estoy",
    "activa la ubicación",
    "save my location as home",
]


@pytest.mark.parametrize("text", _OWN_PLACE)
def test_where_the_person_is_is_the_place_the_weather_read_locates(text: str) -> None:
    assert asks_own_place(text)
    assert _read(text) == ("weather.current",)
    # No place is named: the read locates this PC itself.
    assert effect_intent._weather_location(text) is None
    assert effect_intent.operation_domain_is_grounded(text, "weather.current") is True


@pytest.mark.parametrize("text", _NOT_OWN_PLACE)
def test_a_place_word_that_is_not_where_the_person_is_is_not_read(text: str) -> None:
    assert not asks_own_place(text)
    assert _read(text) != ("weather.current",)


# ---------------------------------------------------------------- 2. the sun of a named place


@pytest.mark.parametrize(
    ("text", "place"),
    [
        ("dime la hora exacta de la puesta de sol en Badalona.", "Badalona"),  # tanda 4c t5
        ("a qué hora es la salida de sol mañana en Cusco", "Cusco"),
        ("when's sunset in Lisbon tomorrow", "Lisbon"),
        ("a qué hora se pone el sol hoy", None),
        ("puesta de sol en Mendoza a qué hora", "Mendoza"),
    ],
)
def test_a_sun_time_is_the_weather_read_of_the_place_named(text: str, place: str | None) -> None:
    assert weather_asks_sun_time(text)
    assert _read(text) == ("weather.current",)
    assert effect_intent._weather_location(text) == place


# ---------------------------------------------------------------- 3. the air


@pytest.mark.parametrize(
    ("text", "place"),
    [
        ("Whats the air quality hoy?", None),  # tanda 4c t27
        ("cómo está la calidad del aire en Ciudad de México", "Ciudad de México"),
        ("hay smog hoy en santiago?", "santiago"),
        ("what's the AQI near me", None),
        ("air quality in delhi right now", "delhi"),
        ("qué tan contaminado está el aire hoy", None),
        ("how polluted is the air today in Lima", "Lima"),
        ("¿está muy contaminado el aire ahora?", None),
        ("el aire está limpio hoy?", None),
        ("la calidad del aire mañana en Bogotá", "Bogotá"),
        ("cómo está el aire hoy en Quito", "Quito"),
    ],
)
def test_the_air_of_a_place_is_the_weather_read(text: str, place: str | None) -> None:
    assert weather_asks_air(text)
    assert _read(text) == ("weather.current",)
    assert effect_intent._weather_location(text) == place


@pytest.mark.parametrize(
    "text",
    [
        "cómo reducir la contaminación del aire",
        "what causes air pollution",
        "busca noticias sobre la contaminación del aire",
        "qué es el smog",
        "calidad del producto",
        "air fryer recipes",
        "el aire acondicionado hoy no funciona",
        "the air conditioner is broken today",
        "está listo el informe",
    ],
)
def test_the_air_as_a_topic_is_not_a_reading(text: str) -> None:
    assert _read(text) != ("weather.current",)


# ---------------------------------------------------------------- 4. near the person


@pytest.mark.parametrize(
    ("text", "query"),
    [
        ("en qué lugares puedo pedir comida para llevar cerca", "en qué lugares puedo pedir comida para llevar cerca"),
        ("dime restaurantes veganos cerca de mí", "dime restaurantes veganos cerca de mí"),
        ("any pharmacies open nearby?", "any pharmacies open nearby"),
        ("pizzerías abiertas en la noche cerca", "pizzerías abiertas en la noche cerca"),
        ("eventos gratis en mi ciudad este finde", "eventos gratis en mi ciudad este finde"),
        ("dime que esta pasando en mi ciudad", "noticias locales"),  # tanda 4c t45
        ("what's going on around here", "local news"),
    ],
)
def test_near_the_person_is_searched_near_this_pcs_city(text: str, query: str) -> None:
    assert near_the_person(text)
    assert sidecar._ground_explicit_arguments("web.search", text, SEARCH_SCHEMA) == {"query": query, "nearby": True}


@pytest.mark.parametrize(
    "text",
    [
        # Negative controls: another place is named, and only that place is searched.
        "busca hoteles cercanos al aeropuerto de Santiago",
        "restaurantes cerca de la Plaza de Armas",
        "farmacias de turno en Ñuñoa cerca",
        "best sushi near Times Square",
        "qué está pasando en la ciudad de Nueva York",
        "¿Qué está pasando en Barcelona?",
        "restaurantes cercanos en madrid",
        "what's happening around the world",
        # Nothing near anyone.
        "busca recetas de pan de masa madre",
    ],
)
def test_a_request_about_another_place_never_carries_the_persons(text: str) -> None:
    assert not near_the_person(text)
    grounded = sidecar._ground_explicit_arguments("web.search", text, SEARCH_SCHEMA)
    assert grounded is None or "nearby" not in grounded


def test_the_news_of_a_named_city_keeps_the_city() -> None:
    grounded = sidecar._ground_explicit_arguments(
        "web.search", "qué está pasando en la ciudad de Nueva York", SEARCH_SCHEMA,
    )
    assert grounded == {"query": "noticias en la ciudad de Nueva York"}


# ---------------------------------------------------------------- 5. the replies

_SEEN = {
    "location": "Curicó",
    "region": "Región de Curicó",
    "country": "Chile",
    "locatedBy": "public_ip_address",
    "temperatureC": 13.6,
    "apparentC": 12.1,
    "humidityPercent": 81,
    "windKmh": 11.2,
    "precipitationMm": 0,
    "condition": "nublado",
    "today": {"maxC": 16.2, "minC": 10.4, "rainProbabilityPercent": 3, "sunrise": "07:12", "sunset": "19:28"},
    "tomorrow": {"date": "2026-09-25", "maxC": 17.0, "minC": 9.8, "rainProbabilityPercent": 6,
                 "condition": "nublado", "sunrise": "07:11", "sunset": "19:29"},
    "airQuality": {"usAqi": 75, "category": "moderada", "pm25": 32.4, "pm10": 33.1},
}
_WEATHER = {"operation": "weather.current", "seen": _SEEN}


@pytest.mark.parametrize(
    ("reply", "asked", "defect"),
    [
        ("Estás en Curicó, Región de Curicó, Chile, según la dirección pública de este PC.",
         "¿dónde estoy?", ""),
        ("You're in Curicó, Chile, going by this PC's public address.", "i'd like to know my current location", ""),
        ("Estás en Chile.", "¿dónde estoy?", "missing_state"),
        ("Estás en Curicó y hay 25 °C.", "¿dónde estoy?", "invented_number"),
    ],
)
def test_the_place_reply_names_the_place_and_no_weather_is_required(reply: str, asked: str, defect: str) -> None:
    assert llm._weather_fact_defect(reply, _WEATHER, asked) == defect


@pytest.mark.parametrize(
    ("reply", "asked", "defect"),
    [
        ("En Curicó la calidad del aire es moderada: índice 75, con PM2.5 de 32,4 µg/m³.",
         "Whats the air quality hoy?", ""),
        ("The air in Curicó is moderate today, AQI 75 and PM10 at 33.1 µg/m³.", "how's the air quality", ""),
        ("En Curicó la calidad del aire es moderada.", "calidad del aire hoy", "missing_state"),
        ("En Curicó el índice de calidad del aire es 42.", "calidad del aire hoy", "invented_number"),
    ],
)
def test_the_air_reply_says_the_observed_index(reply: str, asked: str, defect: str) -> None:
    assert llm._weather_fact_defect(reply, _WEATHER, asked) == defect


def test_the_sun_time_of_a_named_place_is_its_observed_clock() -> None:
    payload = {"operation": "weather.current", "seen": {**_SEEN, "location": "Badalona", "region": "Cataluña",
                                                         "country": "España"}}
    asked = "dime la hora exacta de la puesta de sol en Badalona."
    assert llm._weather_fact_defect("En Badalona el sol se pone hoy a las 19:28.", payload, asked) == ""
    assert llm._weather_fact_defect("En Badalona el sol se pone hoy a las 20:15.", payload, asked) == "invented_number"


def test_the_city_a_search_ran_near_is_observed_in_its_report() -> None:
    payload = {"operation": "web.search", "seen": {
        "query": "en qué lugares puedo pedir comida para llevar cerca Curicó", "near": "Curicó", "count": 1,
        "results": [{"title": "Comida para llevar - Delivery", "url": "https://example.cl/delivery",
                     "snippet": "Pide comida para llevar de locales con despacho."}],
    }}
    asked = "en qué lugares puedo pedir comida para llevar cerca"
    # Owner rule 2026-09-24: the answer says where, never that it searched or which site.
    reply = "Cerca de Curicó hay locales con despacho para pedir comida para llevar."
    assert llm._search_report_unsourced_words(reply, payload, asked) == []
    without_near = {"operation": "web.search", "seen": {k: v for k, v in payload["seen"].items() if k != "near"}}
    assert "curico" in llm._search_report_unsourced_words(reply, without_near, asked)


def test_a_search_near_the_person_without_this_pcs_place_has_its_cause() -> None:
    assert "web_search_place_unavailable" in llm._CAUSE_FACT
