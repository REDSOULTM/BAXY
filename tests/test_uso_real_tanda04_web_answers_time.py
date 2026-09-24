"""Uso real tanda 4 (official window, 50 unseen real messages): web answers that did not
answer and the time of another place.

Replayed here with fresh es/en/spanglish paraphrases and synthetic pages, never the
private literals:

- A report of English pages written in Spanish (or the other way round) died word by
  word as «unsourced» and every search in another language ended in the bare list of
  titles; one paraphrased verb among many sourced words cost a second draft. A claim
  still falls, and a number is now checked against the page the sentence cites.
- «las páginas que encontré tratan de otra cosa» was the instruction's own example and
  preceded reports of pages that were about the request.
- «convertir nueve de la mañana huso horario a madrid» was searched on the web; the time
  of another place is this PC's clock read with that place's zone, and the arithmetic
  is the mind's.
"""

from __future__ import annotations

import json

import pytest

from baxy_mind import __main__ as mind_main
from baxy_mind import effect_intent
from baxy_mind import llm
from baxy_mind.semantic.normalize import fold
from baxy_mind.semantic.temporal import clock_elsewhere


def _search_payload(results: list[dict]) -> dict:
    return {"operation": "web.search", "seen": {"query": "q", "count": len(results), "results": results}}


# --- 1. A report is judged by what can be checked --------------------------------------

_AIR_RESULTS = [
    {"title": "AirWatch - Local air quality", "url": "https://www.airwatch.example.gov/",
     "snippet": "AirWatch is your one-stop source for air quality data, with the forecast and "
     "health advice for your local area."},
    {"title": "Air Quality Index Today", "url": "https://aqi-today.example.com/",
     "snippet": "Current AQI, hourly forecast, pollutant levels and health advice. PM2.5 was 12 "
     "in the last reading."},
]
_AIR_ASK = "cómo está el air quality hoy?"


@pytest.mark.parametrize(
    "report",
    [
        # A Spanish report of English pages: every content word is a translation.
        "Según airwatch.example.gov, AirWatch es la fuente única de datos de calidad del aire, "
        "con el pronóstico y consejos de salud para tu zona. Según aqi-today.example.com, se "
        "ofrece el índice actual, el pronóstico por hora y los niveles de contaminantes.",
        "aqi-today.example.com informa que el PM2.5 marcó 12 en la última lectura.",
    ],
)
def test_a_report_in_the_other_language_of_its_pages_is_not_unsourced(report: str) -> None:
    payload = _search_payload(_AIR_RESULTS)
    assert llm._search_report_unsourced_words(report, payload, _AIR_ASK) == []
    assert llm._payload_fact_defect(report, payload, _AIR_ASK) == ""


def test_a_translated_report_still_owes_the_pages_numbers() -> None:
    invented = "Según aqi-today.example.com, el PM2.5 marcó 35 en la última lectura."
    payload = _search_payload(_AIR_RESULTS)
    assert llm._search_report_unsourced_words(invented, payload, _AIR_ASK) == ["35"]
    assert llm._payload_fact_defect(invented, payload, _AIR_ASK) == "search_report_unsourced_claim"


_GAME_RESULTS = [
    {"title": "How to Play Charades: Rules and Tips", "url": "https://www.howtoplay.example.com/charades",
     "snippet": "A complete guide with the rules and strategy tips to play charades with a group of "
     "friends at a party."},
    {"title": "Charades rules in two minutes - VideoSite", "url": "https://videos.example.com/watch?v=1",
     "snippet": "Learn the rules of charades quickly, with no distractions, just the rules of the game."},
]


@pytest.mark.parametrize(
    "report",
    [
        "According to videos.example.com, the rules of charades are learned quickly in an "
        "explanation with no distractions, just the rules of the game.",
        "Según howtoplay.example.com, la guía completa abarca las reglas y consejos de estrategia "
        "para jugar charades con un grupo de amigos en una fiesta.",
    ],
)
def test_one_paraphrased_word_among_many_sourced_ones_is_the_reports_wording(report: str) -> None:
    payload = _search_payload(_GAME_RESULTS)
    assert llm._payload_fact_defect(report, payload, "how do you play charades") == ""


@pytest.mark.parametrize(
    "claim",
    [
        # A cause of its own, two words no page carries.
        "According to howtoplay.example.com, charades was invented in Victorian England.",
        # A short sentence whose one content word is the model's.
        "Según videos.example.com, está prohibido.",
    ],
)
def test_a_claim_of_the_models_own_still_falls(claim: str) -> None:
    payload = _search_payload(_GAME_RESULTS)
    assert llm._payload_fact_defect(claim, payload, "how do you play charades") == "search_report_unsourced_claim"


_NUTRITION_RESULTS = [
    {"title": "Lasagna calories | foodfacts", "url": "https://foodfacts.example.com/lasagna",
     "snippet": "Comprehensive nutrition facts and health benefits for lasagna."},
    {"title": "Lasagna - Eat Stats", "url": "https://eatstats.example.org/lasagna",
     "snippet": "1 serving of lasagna contains 480 Calories: 40% carbs, 35% fat and 25% protein."},
]


def test_a_number_belongs_to_the_page_the_sentence_cites() -> None:
    payload = _search_payload(_NUTRITION_RESULTS)
    asked = "nutrition facts for lasagna please"
    honest = "According to eatstats.example.org, one serving of lasagna contains 480 Calories with 40% carbs."
    misattributed = "According to foodfacts.example.com, one serving of lasagna contains 480 Calories with 40% carbs."
    assert llm._payload_fact_defect(honest, payload, asked) == ""
    assert llm._payload_fact_defect(misattributed, payload, asked) == "search_report_unsourced_claim"
    # A number glued to a name is the name («24hours.example.com»), and a number
    # the page writes in words is the page's («three countries»).
    worded = [{"title": "Three flags that are not rectangles", "url": "https://24flags.example.com/",
               "snippet": "Only three countries have a flag that is not a rectangle."}]
    assert llm._payload_fact_defect(
        "According to 24flags.example.com, only 3 countries have a flag that is not a rectangle.",
        _search_payload(worded), "is there a flag that is not a rectangle",
    ) == ""


# --- 2. The report says what a page answers first, and names no «other thing» -------------

def test_the_report_instruction_answers_first_and_never_offers_the_other_thing_example() -> None:
    import inspect

    source = inspect.getsource(llm.LlmRuntime.compose_user_message)
    assert "tratan de otra cosa" not in source
    assert "about something else" not in source
    assert "dilo primero con las palabras de esa" in source
    assert "say it first with that page's words" in source


# --- 3. The time of another place is this clock read with that place's zone ---------------

@pytest.mark.parametrize(
    "text, place",
    [
        ("por favor convertir nueve de la mañana huso horario a madrid", "madrid"),
        ("qué hora es en tokio", "tokio"),
        ("dime la hora de Lima", "lima"),
        ("oye y en buenos aires qué hora es ahorita", "buenos aires"),
        ("time in sydney please", "sydney"),
        ("what's the time over in los angeles right now", "los angeles"),
        ("hey, what time is it in the UK", "uk"),
        ("¿cuántas horas de diferencia hay con México?", "mexico"),
        ("how many hours ahead is tokyo", "tokyo"),
        ("pásame las 5 de la tarde a hora de bogotá", "bogota"),
        ("what's 9am tokyo time", "tokyo"),
        ("si en madrid son las 10 de la noche qué hora es aquí", "madrid"),
        ("dime la hora en La Paz porfa", "la paz"),
    ],
)
def test_the_place_of_a_clock_elsewhere_is_read(text: str, place: str) -> None:
    found = clock_elsewhere(fold(text))
    assert found is not None and found.place == place
    intent = effect_intent.resolve_explicit_effects(text, ("system.time", "web.search"), (), ())
    assert intent is not None and intent.operations == ("system.time",)
    assert effect_intent.operation_domain_is_grounded(text, "system.time") is True
    assert mind_main._explicit_arguments_from_evidence("system.time", fold(text)) == {"place": place}


@pytest.mark.parametrize(
    "text, zone",
    [
        ("in the eastern timezone, what time is it now", "America/New_York"),
        ("qué hora es en la costa oeste", "America/Los_Angeles"),
        ("dime la hora del pacífico", "America/Los_Angeles"),
        ("what time is it in GMT", "UTC"),
        ("la hora peninsular por favor", "Europe/Madrid"),
    ],
)
def test_a_zone_named_by_its_name_is_read_as_that_zone(text: str, zone: str) -> None:
    found = clock_elsewhere(fold(text))
    assert found is not None and found.place == zone


@pytest.mark.parametrize(
    "text",
    [
        "qué hora es",
        "what time is it",
        "¿me podrías dar la hora?",
        "qué hora es en este momento",
        "qué hora es en la pc",
        "es hora de dormir",
        "dime la hora de la cita",
        "cuál es la hora de salida del vuelo",
        "¿a qué hora abre el banco en Madrid?",
        "reunión a las 3 en Madrid",
        "recuérdame a las 9 en la oficina",
        "qué hora es, para saber si llego",
        # Two zones to convert between: this clock is neither.
        "convert 3pm EST to madrid time",
        "what time is it in london and in paris",
        # The place of another question in the same request is not the clock's.
        "what time is it and what's the weather in paris",
        "dime la hora y si el volumen está en silencio",
        "dime la hora y cuánta batería queda en el portátil",
        "lista mis tareas. después de eso qué hora es. finalmente pon el audio en silencio",
        "give me the time needed to download it to my laptop",
        # Refused, remembered or written: not asked now.
        "no me digas la hora en Madrid",
        "ayer te pedí la hora en Madrid",
        "escribe una nota que diga qué hora es en Madrid",
    ],
)
def test_this_clock_an_event_or_two_zones_are_not_a_clock_elsewhere(text: str) -> None:
    assert clock_elsewhere(fold(text)) is None
    assert mind_main._explicit_arguments_from_evidence("system.time", fold(text)) == {}


_NOW = "2026-09-24T11:18:52.1234567Z"


def _time_situation(place: dict) -> dict:
    return {
        "kind": "operation", "operation": "system.time", "polarity": "success",
        "verified": True, "succeeded": True,
        "observed": {"version": 1, "utc": _NOW, "localUtcOffsetMinutes": -180, "place": place},
    }


_MADRID = {"name": "Madrid", "country": "España", "timeZone": "Europe/Madrid",
           "utcOffsetMinutes": 120, "authority": "named_place_geocoded"}
_TOKYO = {"name": "Tokio", "country": "Japón", "timeZone": "Asia/Tokyo",
          "utcOffsetMinutes": 540, "authority": "named_place_geocoded"}


@pytest.mark.parametrize(
    "asked, place, language, facts",
    [
        ("qué hora es en madrid", _MADRID, "es", {"clock": "13:18", "clockAt": "Madrid", "place": "Madrid"}),
        ("convertir nueve de la mañana huso horario a madrid", _MADRID, "es",
         {"given": "09:00", "givenAt": "aquí", "clock": "14:00", "clockAt": "Madrid"}),
        ("si en madrid son las 10 de la noche qué hora es aquí", _MADRID, "es",
         {"given": "22:00", "givenAt": "Madrid", "clock": "17:00", "clockAt": "aquí"}),
        ("if it's 11pm here what time is it in tokyo", _TOKYO, "en",
         {"given": "23:00", "clock": "11:00", "clockAt": "Tokyo", "day": "the next day"}),
        ("diferencia horaria con tokio", _TOKYO, "es", {"difference": "12 h más que aquí", "clock": "20:18"}),
        ("hora en tokio", _TOKYO, "es", {"clock": "20:18"}),
    ],
)
def test_the_mind_computes_the_time_there_and_the_conversion(asked, place, language, facts) -> None:
    payload = llm._compose_situation_payload(_time_situation(place), language, user_text=asked)
    for key, value in facts.items():
        assert payload[key] == value, key
    # The zone identifier and this PC's instant are not words for the narrator.
    assert "timeZone" not in json.dumps(payload) and "localUtcOffsetMinutes" not in json.dumps(payload)


@pytest.mark.parametrize(
    "asked, reply, defect",
    [
        ("convertir nueve de la mañana huso horario a madrid", "Las 9:00 de aquí son las 14:00 en Madrid.", ""),
        ("convertir nueve de la mañana huso horario a madrid", "Las 9:00 de aquí son las 15:00 en Madrid.", "missing_name"),
        ("qué hora es en madrid", "En Madrid son las 13:18.", ""),
        # This PC's clock recited for Madrid, or the place left out.
        ("qué hora es en madrid", "En Madrid son las 08:18.", "missing_name"),
        ("qué hora es en madrid", "Son las 13:18.", "missing_state"),
        ("what time is it in madrid", "It's 1:18 PM in Madrid.", ""),
    ],
)
def test_the_reply_owes_the_computed_time_and_the_place(asked: str, reply: str, defect: str) -> None:
    situation = _time_situation(_MADRID)
    language = "en" if asked.startswith("what") else "es"
    payload = llm._compose_situation_payload(situation, language, user_text=asked)
    visible = llm.compose_visible_defect(reply, "status", asked, {"situation": json.dumps(situation)})
    assert llm._payload_fact_defect(reply, payload, asked) == defect
    assert visible == defect or (defect and visible)


@pytest.mark.parametrize("code", ["time_place_not_found", "time_place_service_unavailable", "time_place_zone_ambiguous"])
def test_the_absences_of_a_place_time_have_their_cause_facts(code: str) -> None:
    assert code in llm._CAUSE_FACT
