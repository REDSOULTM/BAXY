"""Uso real tandas 4f and 5 (2026-09-24): the weather and the air of a named place went to a web search or
asked which city, the air of a named downtown died in ⚠, and web reports that quoted a page's hours ended in
the bare list of page titles. Owner rule 2026-09-24: a web lookup is invisible and short — the answer itself in
one or two sentences, never a source, a site, the search or a list of pages — and still only what the pages say.
Paraphrased shapes (es, en, spanglish) with negative controls; synthetic pages."""

from __future__ import annotations

import pytest

from baxy_mind import effect_intent, llm
from test_c03_cpu_actor import Recorder

AVAILABLE = ("weather.current", "web.search", "system.time", "note.create", "app.open")


def _operations(text: str) -> tuple[str, ...] | None:
    intent = effect_intent.resolve_explicit_effects(text, AVAILABLE, ("Steam",), ())
    return None if intent is None else intent.operations


# --- the weather of a named place is the weather read of that place ---------------------


@pytest.mark.parametrize(
    ("text", "place"),
    [
        # Informing the person of it, and the weather «actual» / «de ahora».
        ("infórmanos del tiempo actual en Lugo", "Lugo"),
        ("infórmame del tiempo de hoy en Cádiz", "Cádiz"),
        ("dame el tiempo actual en Quito", "Quito"),
        ("dime el tiempo de ahora en Cuenca", "Cuenca"),
        ("inform me about the weather in Lima", "Lima"),
        ("update me on the weather in Chicago", "Chicago"),
        # «what is the weather» asks it as «what's the weather» does.
        ("what is the weather in Oslo", "Oslo"),
        ("what is the air quality in Denver", "Denver"),
        # The weather to come asked like the weather now; a town whose name has an article.
        ("qué tiempo hará en Salamanca mañana", "Salamanca"),
        ("¿qué tiempo hará en A Coruña mañana?", "A Coruña"),
    ],
)
def test_the_weather_of_a_named_place_is_read_for_that_place(text: str, place: str) -> None:
    assert _operations(text) == ("weather.current",), text
    assert effect_intent._weather_location(text) == place
    assert effect_intent.operation_domain_is_grounded(text, "weather.current") is True


@pytest.mark.parametrize(
    ("text", "place"),
    [
        ("wat level of air pollution hay en downtown Houston", "Houston"),
        ("How bad is the air pollution in down town Phoenix today", "Phoenix"),
        ("cuánto smog hay en el centro de Lima", "Lima"),
        ("cuál es el índice de calidad del aire en las afueras de Madrid", "Madrid"),
    ],
)
def test_the_air_of_a_part_of_a_town_is_the_air_of_the_town(text: str, place: str) -> None:
    # The weather service knows no «downtown Houston»: the part of the town is not its name.
    assert _operations(text) == ("weather.current",), text
    assert effect_intent._weather_location(text) == place


@pytest.mark.parametrize(
    "text",
    [
        "¿qué pronostican tus aplicaciones del tiempo para mañana?",
        "¿qué te dice la previsión meteorológica de pasado mañana?",
        "whats the forecast on my weather app for tomorrow",
        "dime la previsión meteorológica en mi ciudad",
    ],
)
def test_a_forecast_with_no_place_named_is_the_persons_place(text: str) -> None:
    # «en tus aplicaciones», «en mi ciudad» name no town: the read locates this PC.
    assert _operations(text) == ("weather.current",), text
    assert effect_intent._weather_location(text) is None


@pytest.mark.parametrize(
    ("text", "place"),
    [
        ("¿el sábado podremos comer al aire libre en Sevilla?", "Sevilla"),
        ("¿mañana se podrá hacer un asado afuera?", None),
        ("can we have a picnic outside on sunday in Austin", "Austin"),
        ("could we eat at a terrace in Rome tomorrow", "Rome"),
        ("will I be able to go to the beach tomorrow in Miami", "Miami"),
    ],
)
def test_a_plan_in_the_open_air_on_a_day_to_come_asks_the_forecast(text: str, place: str | None) -> None:
    assert _operations(text) == ("weather.current",), text
    assert effect_intent._weather_location(text) == place


@pytest.mark.parametrize(
    "text",
    [
        # Booking, opening hours or rules of the place are not the weather.
        "¿podremos reservar una terraza en Valencia el domingo?",
        "can we go to the beach bar tomorrow, is it open",
        "¿se puede fumar en las terrazas de Madrid?",
        # Weather words that are not the weather.
        "el clima laboral está tenso en mi oficina",
        "cuéntame del tiempo en que vivías en Madrid",
        "infórmame del tiempo que falta para navidad",
        "cuéntame un chiste del clima",
        # What the thing is, not how it is now.
        "qué es el clima",
        "what is air pollution",
    ],
)
def test_what_is_not_a_live_weather_question_is_not_the_weather_read(text: str) -> None:
    assert _operations(text) != ("weather.current",), text


def test_a_named_place_never_becomes_the_persons_place_nor_a_kind_of_place() -> None:
    assert effect_intent._weather_location("can we have a picnic at a park in Boston tomorrow") == "Boston"
    assert effect_intent._weather_location("¿podremos cenar en una terraza en Bilbao el viernes?") == "Bilbao"
    assert effect_intent._weather_location("qué tiempo hace en mi pueblo") is None


# --- the reply to a plan in the open air is the weather of that place ------------------------

_SEEN = {
    "location": "Girona", "country": "España", "observedAtLocal": "2026-09-24T13:30",
    "temperatureC": 24.2, "apparentC": 25.0, "humidityPercent": 60, "windKmh": 9.0, "precipitationMm": 0,
    "condition": "despejado",
    "today": {"maxC": 26.0, "minC": 18.0, "rainProbabilityPercent": 5, "sunrise": "07:40", "sunset": "19:35"},
    "tomorrow": {"date": "2026-09-25", "maxC": 25.1, "minC": 17.4, "rainProbabilityPercent": 30,
                 "condition": "nublado", "sunrise": "07:41", "sunset": "19:33"},
}


def test_the_plan_is_answered_with_the_observed_weather_of_the_place() -> None:
    payload = {"operation": "weather.current", "seen": _SEEN}
    asked = "¿el domingo podremos comer en una terraza en Girona?"
    told = "En Girona hay 24,2 °C y está despejado ahora; el pronóstico del domingo no lo tengo."
    assert llm._weather_fact_defect(told, payload, asked) == ""
    # A figure no read carries, or a reply without the place, is not the answer.
    assert llm._weather_fact_defect("El domingo en Girona habrá 28 °C.", payload, asked) == "invented_number"
    assert llm._weather_fact_defect("Hay 24,2 °C y está despejado.", payload, asked) == "missing_state"


# --- a failed weather read that is an absence is told as that absence ----------------------


def _place_not_found() -> dict:
    return {
        "situation": {
            "kind": "failure", "polarity": "failure", "cause": "mission_failed", "stepCount": 0, "steps": [],
            "reason": {"kind": "operation", "operation": "weather.current", "polarity": "failure",
                       "verified": False, "succeeded": False, "error": "weather_place_not_found"},
        }
    }


@pytest.mark.parametrize(
    ("asked", "draft"),
    [
        ("qué tan contaminado está el aire en Nowhereville",
         "El servicio del clima no reconoce ese lugar, así que no tengo la contaminación de allí."),
        ("cuánto smog hay en Nowhereville",
         "No sé el nivel del aire allí: el servicio meteorológico no conoce ese sitio."),
        ("how polluted is the air in Nowhereville",
         "The weather service doesn't recognize that place, so I have no air reading for it."),
    ],
)
def test_the_unknown_place_told_is_the_failure_told(asked: str, draft: str) -> None:
    assert llm.compose_visible_defect(draft, "error", asked, _place_not_found()) == ""


def test_an_unknown_place_hidden_behind_a_reading_still_misses_the_failure() -> None:
    draft = "El aire en Nowhereville está limpio hoy."
    assert llm.compose_visible_defect(draft, "error", "cómo está el aire en Nowhereville", _place_not_found()) == (
        "missing_failure"
    )


# --- web answers: invisible, short, and still only what the pages say ------------------------

_APERITIF = [
    {"title": "La hora del aperitivo en Girona", "url": "https://www.gironaguia.com/aperitivo",
     "snippet": "El aperitivo se toma entre las 12:30 y las 14:00, sobre todo los domingos, en las plazas del casco antiguo."},
    {"title": "Bares con terraza para el aperitivo", "url": "https://terrazasgi.cat/bares",
     "snippet": "Las terrazas del centro abren desde las 11:00 los fines de semana."},
]
_TURTLES = [
    {"title": "Tortugas Ninja - Enciclopedia", "url": "https://es.enciclopedia.example.org/wiki/Tortugas_Ninja",
     "snippet": "Las Tortugas Ninja son cuatro tortugas mutantes adolescentes entrenadas en el arte del ninjutsu "
     "que viven en las alcantarillas de Nueva York."},
    {"title": "Teenage Mutant Ninja Turtles | Fan Wiki", "url": "https://turtlesfan.example.com/wiki",
     "snippet": "Four teenage mutant turtles trained in ninjutsu who live in the sewers of New York City."},
]


def _search_situation(results: list[dict]) -> dict:
    return {"kind": "operation", "operation": "web.search", "polarity": "success", "verified": True,
            "succeeded": True, "observed": {"version": 1, "query": "q", "count": len(results), "results": results}}


def _search_payload(results: list[dict]) -> dict:
    return {"operation": "web.search", "seen": {"query": "q", "count": len(results), "results": results}}


@pytest.mark.parametrize(
    ("asked", "answer"),
    [
        ("¿Qué son las Tortugas Ninja?",
         "Las Tortugas Ninja son cuatro tortugas mutantes adolescentes entrenadas en ninjutsu que viven en las "
         "alcantarillas de Nueva York."),
        ("what are the ninja turtles",
         "They are four teenage mutant turtles trained in ninjutsu who live in the sewers of New York City."),
        ("dime qué son las ninja turtles porfa",
         "Son cuatro tortugas mutantes adolescentes que viven en las alcantarillas de Nueva York."),
    ],
)
def test_the_answer_is_said_as_something_known(asked: str, answer: str) -> None:
    facts = {"situation": _search_situation(_TURTLES)}
    assert llm.compose_visible_defect(answer, "status", asked, facts) == ""
    assert llm._payload_fact_defect(answer, _search_payload(_TURTLES), asked) == ""


@pytest.mark.parametrize(
    "shown",
    [
        "Según es.enciclopedia.example.org, las Tortugas Ninja son cuatro tortugas mutantes.",
        "Según la Enciclopedia, las Tortugas Ninja son cuatro tortugas mutantes.",
        "Busqué en internet y encontré estas páginas: «Tortugas Ninja - Enciclopedia».",
        "De acuerdo con varias fuentes, son cuatro tortugas mutantes adolescentes.",
        "According to turtlesfan.example.com, they are four teenage mutant turtles.",
        "I searched and found these pages about the turtles.",
        "Turtlesfan dice que son cuatro tortugas mutantes adolescentes.",
    ],
)
def test_an_answer_that_shows_the_lookup_falls(shown: str) -> None:
    assert llm._payload_fact_defect(shown, _search_payload(_TURTLES), "¿Qué son las Tortugas Ninja?") == (
        "search_report_shows_the_search"
    )


def test_the_persons_words_and_the_pages_own_words_are_not_the_lookup_showing() -> None:
    # A snippet that itself says «según …» may be repeated; a word the person said is theirs.
    results = [{"title": "Consejos de salud", "url": "https://salud.example.org/agua",
                "snippet": "Según la OMS, conviene beber agua a lo largo del día."}]
    asked = "¿cuánta agua conviene beber según la OMS?"
    assert llm._payload_fact_defect(
        "Según la OMS, conviene beber agua a lo largo del día.", _search_payload(results), asked
    ) == ""
    # A place that is also a site's name is the place when the pages say it.
    place = [{"title": "Turismo en Curicó", "url": "https://www.curico.cl/turismo",
              "snippet": "Curicó tiene ascensores históricos y cerros con miradores."}]
    assert llm._payload_fact_defect(
        "Curicó tiene ascensores históricos y cerros con miradores.", _search_payload(place),
        "qué ver en la ciudad",
    ) == ""


def test_a_long_walk_through_the_pages_is_too_long() -> None:
    walk = ("Las Tortugas Ninja son cuatro tortugas mutantes. Viven en las alcantarillas de Nueva York. "
            "Están entrenadas en el arte del ninjutsu. Son adolescentes.")
    assert llm._payload_fact_defect(walk, _search_payload(_TURTLES), "¿Qué son las Tortugas Ninja?") == (
        "search_report_runs_long"
    )


def test_a_claim_no_page_makes_still_falls_without_any_source() -> None:
    invented = "Las Tortugas Ninja fueron creadas en Japón en 1950."
    assert llm._payload_fact_defect(invented, _search_payload(_TURTLES), "¿Qué son las Tortugas Ninja?") == (
        "search_report_unsourced_claim"
    )


def test_not_finding_it_is_said_briefly_without_the_search() -> None:
    asked = "¿a qué hora cierra el museo de cera de Girona?"
    facts = {"situation": _search_situation(_APERITIF)}
    for answer in ("No lo encontré.", "No encontré a qué hora cierra el museo de cera de Girona."):
        assert llm.compose_visible_defect(answer, "status", asked, facts) == ""
        assert llm._payload_fact_defect(answer, _search_payload(_APERITIF), asked) == ""
    assert llm.compose_visible_defect("I couldn't find it.", "status", "when does the wax museum close", facts) == ""


def test_the_hours_a_page_writes_are_the_pages_not_invented_clocks() -> None:
    asked = "¿a qué hora se toma el aperitivo en Girona los domingos?"
    answer = "El aperitivo se toma entre las 12:30 y las 14:00, sobre todo los domingos."
    facts = {"situation": _search_situation(_APERITIF)}
    assert llm.compose_visible_defect(answer, "status", asked, facts) == ""
    assert llm._payload_fact_defect(answer, _search_payload(_APERITIF), asked) == ""
    # An hour no page writes is still invented.
    assert llm.compose_visible_defect("El aperitivo se toma a las 16:45.", "status", asked, facts) == "extra_claim"


def test_the_answer_publishes_on_the_first_stage_and_the_writer_is_told_to_hide_the_search() -> None:
    asked = "¿a qué hora se toma el aperitivo en Girona los domingos?"
    answer = "El aperitivo se toma entre las 12:30 y las 14:00, sobre todo los domingos."
    client = Recorder([answer])
    assert client.compose_user_message(asked, "status", {"situation": _search_situation(_APERITIF)}) == answer
    assert len(client.payloads) == 1
    sent = client.payloads[0]["messages"][-1]["content"]
    assert "una o dos oraciones cortas" in sent
    assert "Nunca menciones la búsqueda, las páginas, los sitios ni ninguna fuente" in sent
    assert "gironaguia.com" not in sent.split("seen.results son")[1]
    # Two short sentences fit; a walk through the pages does not. M85 (DEV-D v3o D-p27-t3 ⚠): 120, so that a draft cut
    # by its budget still leaves the shorter retry its time inside the 5 s composition.
    assert client.payloads[0]["max_tokens"] == 120


def test_a_draft_that_shows_the_search_is_repaired_with_its_own_hint() -> None:
    asked = "¿a qué hora se toma el aperitivo en Girona los domingos?"
    shown = "Según gironaguia.com, el aperitivo se toma entre las 12:30 y las 14:00."
    answer = "El aperitivo se toma entre las 12:30 y las 14:00, sobre todo los domingos."
    client = Recorder([shown, answer])
    assert client.compose_user_message(asked, "status", {"situation": _search_situation(_APERITIF)}) == answer
    retry_system = client.payloads[1]["messages"][0]["content"]
    assert "nunca menciones la búsqueda, una página, un sitio ni una fuente" in retry_system


def test_three_drafts_that_show_the_search_end_in_no_list_of_pages() -> None:
    asked = "¿a qué hora se toma el aperitivo en Girona los domingos?"
    shown = "Según gironaguia.com, el aperitivo se toma entre las 12:30 y las 14:00."
    client = Recorder([shown] * 3)
    reply = client.compose_user_message(asked, "status", {"situation": _search_situation(_APERITIF)})
    assert "gironaguia.com" not in reply and "páginas" not in reply


@pytest.mark.parametrize(
    "asked",
    ["¿Quién es Quimet Aperitivos?", "decime una curiosidad"],
)
def test_who_what_and_curiosity_answers_are_told_to_name_no_page(asked: str) -> None:
    client = Recorder(["Es una ruta de bares con terraza para el aperitivo."] * 3)
    client.compose_user_message(asked, "status", {"situation": _search_situation(_APERITIF)})
    sent = client.payloads[0]["messages"][-1]["content"]
    assert "nunca nombres una página, un sitio ni la búsqueda" in sent
    assert "Wikipedia" not in sent
