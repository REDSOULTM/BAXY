"""Uso real tandas 5e and 6 (2026-09-24): web answers that did not answer.

Measured over every web turn of both runs (14 web.search turns): no final dropped a fact its snippets stated. The
finals that said nothing either answered a read the web cannot give (the news, the UV index, the dew point — now
typed reads), or pasted a page's description of itself when no snippet held the asked fact («Los mejores
restaurantes italianos en Curico…», «Descubre los mejores restaurantes abiertos cerca de ti…», «…según la lista
de las acciones más caras…»), while the honest «not found» draft died on a word no page used («No se indica la hora
exacta…»).

1. «¿podrías poner las notícias mundiales?» searched portals and pasted CNN's description: the news asked with the
   infinitive after «podrías», «puedes», «could you», or «put on», are the headlines read. Owner:
   semantic/web._public_live_lookup_request (read by patterns._news_headlines_request).
2. «No se indica la hora exacta de la salida del sol» died three times on «exacta» (search_report_unsourced_claim)
   and «I couldn't find …» died as search_result_denied, whose hint and the unsupported-claim hint asked to «name
   the pages found» — which the owner rule of the same day vetoes. Saying what was not found claims nothing (its
   numbers are still checked), «in the results» shows the search, having «no information» is still denied, and the
   hints no longer ask for pages. Owner: llm._SEARCH_NOT_FOUND / _search_report_unsourced_words /
   _SEARCH_MECHANICS / _payload_fact_defect and the retry hints.
3. A page's own words published as the answer: its title or snippet heading (tanda 5e t2), its call to the reader
   («Descubre…, Consulta…», tanda 6 t46), its list cited («según la lista…», tanda 6 t41). Each falls with a hint
   that asks for the concrete thing or «not found», and the search instruction says a page's description of itself
   is not the answer. Owner: llm._search_report_names_a_page / _PAGE_CALL_TO_READER / _SEARCH_ATTRIBUTION and the
   web.search compose instruction.

Every list mixes Spanish, English and Spanglish and holds phrasings never seen in a run; negative controls keep what
is not a news request out.
"""

from __future__ import annotations

import json

import pytest

from baxy_mind import effect_intent, llm
from test_c03_cpu_actor import Recorder

AVAILABLE = ("web.news.headlines", "web.search", "weather.current", "system.time", "note.create", "app.open",
             "media.play.query", "audio.volume")


def _operations(text: str) -> tuple[str, ...] | None:
    intent = effect_intent.resolve_explicit_effects(text, AVAILABLE, ("Steam",), ())
    return None if intent is None else intent.operations


# --- 1. the news put on are the headlines read ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "¿podrías poner las notícias mundiales?",
        "¿puedes poner las noticias?",
        "could you put on the world news?",
        "put on the news",
        "put the news on please",
        "¿me puedes leer las noticias de hoy?",
        "can you read me today's headlines",
        "¿podrías darme las últimas noticias?",
        "puedes decirme las noticias de chile",
        "oye baxy, ¿me podrías mostrar los titulares?",
    ],
)
def test_the_news_asked_with_an_infinitive_or_put_on_are_the_headlines(text: str) -> None:
    assert _operations(text) == ("web.news.headlines",), text


@pytest.mark.parametrize(
    "text",
    [
        "put the news article in a note",
        "¿puedes poner música?",
        "podrías poner el volumen al 20",
        "qué significa la palabra noticias",
    ],
)
def test_what_is_not_the_news_is_not_the_headlines(text: str) -> None:
    assert _operations(text) != ("web.news.headlines",), text


# --- 2. «not found» survives its own wording; the results stay unmentioned ------------------------------------------

_SUN_PAGES = [
    {"title": "Calculadora Salida Puesta Sol - Hora Dorada y Azul", "url": "https://sol.example.com/calculadora",
     "snippet": "Calculadora gratis de salida y puesta del sol con hora dorada, hora azul y duración del día."},
    {"title": "Puesta del sol hoy", "url": "https://puesta.example.org/",
     "snippet": "¿A qué hora es la puesta del sol hoy? Salida y puesta del sol para 15,566 ciudades en 244 países."},
]


def _search_situation(results: list[dict]) -> dict:
    return {"kind": "operation", "operation": "web.search", "polarity": "success", "verified": True,
            "succeeded": True, "observed": {"version": 1, "query": "q", "count": len(results), "results": results}}


def _search_payload(results: list[dict]) -> dict:
    return {"operation": "web.search", "seen": {"query": "q", "count": len(results), "results": results}}


@pytest.mark.parametrize(
    ("asked", "answer"),
    [
        ("he quedado con un amigo a la salida del sol en Cádiz, ¿qué hora será?",
         "No se puede determinar la hora exacta de la salida del sol."),
        ("¿a qué hora amanece en Cádiz?", "No encontré la hora exacta del amanecer en Cádiz."),
        ("when does the sun rise in Cadiz", "I couldn't find the exact sunrise time for Cadiz."),
        # Tanda 7: «it isn't stated» narrates the pages read (now search_report_shows_the_search); the plain
        # not-found keeps this case's intent.
        ("sunrise time in Cadiz pls", "I couldn't find the precise time, sorry."),
    ],
)
def test_saying_it_was_not_found_is_no_unsourced_claim(asked: str, answer: str) -> None:
    assert llm._payload_fact_defect(answer, _search_payload(_SUN_PAGES), asked) == ""
    assert llm.compose_visible_defect(answer, "status", asked, {"situation": _search_situation(_SUN_PAGES)}) == ""


@pytest.mark.parametrize(
    "answer",
    [
        # An absence in the world is a claim, judged by its words.
        "No hay horario oficial de salida del sol en invierno.",
        # A number no page writes, even inside «not found».
        "No encontré la hora; suele ser a las 7:48.",
    ],
)
def test_a_claim_said_with_a_negation_is_still_judged(answer: str) -> None:
    assert llm._payload_fact_defect(answer, _search_payload(_SUN_PAGES), "¿a qué hora amanece en Cádiz?") == (
        "search_report_unsourced_claim"
    )


@pytest.mark.parametrize(
    "answer",
    [
        "No se indica la hora exacta de la salida del sol en los resultados.",
        "The exact sunrise time isn't in the results.",
        "Entre estos resultados no aparece la hora.",
    ],
)
def test_not_found_in_the_results_shows_the_search(answer: str) -> None:
    assert llm._payload_fact_defect(answer, _search_payload(_SUN_PAGES), "¿a qué hora amanece en Cádiz?") == (
        "search_report_shows_the_search"
    )


def test_having_no_information_is_still_denied_and_repaired_without_naming_pages() -> None:
    asked = "¿a qué hora amanece en Cádiz?"
    denied = "No hay datos del sol hoy."
    assert llm._payload_fact_defect(denied, _search_payload(_SUN_PAGES), asked) == "search_result_denied"
    answer = "No encontré la hora del amanecer en Cádiz."
    client = Recorder([denied, answer])
    assert client.compose_user_message(asked, "status", {"situation": _search_situation(_SUN_PAGES)}) == answer
    retry = json.dumps(client.payloads[1]["messages"], ensure_ascii=False)
    assert "no lo encontraste" in retry
    assert "nombra las páginas" not in retry


# --- 3. a page's name, its call to the reader or its list cited is not the answer -----------------------------------

_ITALIAN = [
    {"title": "Mejores restaurantes italianos en Curico - Tripadvisor", "url": "https://www.tripadvisor.cl/x",
     "snippet": "Los mejores restaurantes italianos en Curico , Región de Curicó : Consulta en Tripadvisor "
                "opiniones de restaurantes en Curico y busca por precio, ubicación y más ."},
    {"title": "Los 12 mejores restaurantes italianos de Curicó", "url": "https://guia.example.cl/italianos",
     "snippet": "Si eres un amante de la cocina italiana, has llegado al lugar correcto. En esta guía te "
                "presentaremos los mejores restaurantes italianos de Curicó."},
    {"title": "Trattoria Da Enzo - Cerro Alegre", "url": "https://enzo.example.cl/",
     "snippet": "Trattoria Da Enzo: cocina italiana casera en el Cerro Alegre, Curicó, abierta de martes a domingo."},
]
_OPEN_NEAR = [
    {"title": "Restaurantes abiertos cerca de mí | OpenTable", "url": "https://www.opentable.example/abiertos",
     "snippet": "Descubre los mejores restaurantes abiertos cerca de ti. Consulta menús, reseñas, fotos y elige entre "
                "los horarios de reservación disponibles."},
]
_STOCKS = [
    {"title": "Las 12 acciones más caras del mundo - Traders Union", "url": "https://tu.example.com/caras",
     "snippet": "¿Qué valores son los más caros del mundo? Los expertos de TU han preparado para ti una lista de las "
                "acciones más caras en estos momentos."},
]


@pytest.mark.parametrize(
    ("asked", "answer", "results"),
    [
        # The t2 final: the heading of a listing page, no restaurant named.
        ("dónde está el restaurante italiano mas cercano",
         "Los mejores restaurantes italianos en Curico, región de Curicó.", _ITALIAN),
        ("closest italian place pls", "Los 12 mejores restaurantes italianos de Curicó.", _ITALIAN),
        ("best italian food near me", "Mejores restaurantes italianos en Curico.", _ITALIAN),
    ],
)
def test_a_pages_name_is_not_the_answer(asked: str, answer: str, results: list[dict]) -> None:
    assert llm._payload_fact_defect(answer, _search_payload(results), asked) == "search_report_names_a_page"


@pytest.mark.parametrize(
    ("asked", "answer", "results"),
    [
        # The t46 final: the page's call to its visitor.
        ("sería genial cenar en un restaurante abierto en el centro",
         "Descubre los mejores restaurantes abiertos cerca de ti. Consulta menús, reseñas, fotos y elige entre los "
         "horarios de reservación disponibles.", _OPEN_NEAR),
        ("any restaurants open now", "Consulta menús y reseñas de restaurantes abiertos cerca de ti.", _OPEN_NEAR),
    ],
)
def test_a_pages_call_to_the_reader_is_page_voice(asked: str, answer: str, results: list[dict]) -> None:
    assert llm._payload_fact_defect(answer, _search_payload(results), asked) == "search_report_page_voice"


@pytest.mark.parametrize("answer", ["Consulté varias páginas sobre restaurantes.", "Busqué restaurantes abiertos."])
def test_baxys_own_past_is_not_the_pages_call(answer: str) -> None:
    # «consulté», «busqué» fold to «consulte», «busque»: read with their accents they are BAXY telling the search.
    assert llm._payload_fact_defect(answer, _search_payload(_OPEN_NEAR), "any restaurants open now") == (
        "search_report_shows_the_search"
    )


def test_a_pages_list_cited_shows_the_search() -> None:
    # The t41 final.
    answer = "El precio de las acciones puede ser alto según la lista de las acciones más caras del mundo."
    assert llm._payload_fact_defect(answer, _search_payload(_STOCKS), "alto precio de las acciones") == (
        "search_report_shows_the_search"
    )


@pytest.mark.parametrize(
    ("asked", "answer", "results"),
    [
        # A place a snippet names is the answer.
        ("dónde está el restaurante italiano mas cercano",
         "Trattoria Da Enzo, cocina italiana casera en el Cerro Alegre, Curicó.", _ITALIAN),
        ("closest italian place pls", "Trattoria Da Enzo, en el Cerro Alegre.", _ITALIAN),
        # Not finding one is said briefly.
        ("any restaurants open now", "No encontré uno en concreto.", _OPEN_NEAR),
        # «Mira,» is a discourse marker, not the page's order; a verb the person used is theirs.
        ("dónde está el restaurante italiano mas cercano", "Mira, Trattoria Da Enzo está en el Cerro Alegre.", _ITALIAN),
        ("consulta los horarios de los restaurantes abiertos", "No encontré los horarios de reservación.", _OPEN_NEAR),
    ],
)
def test_a_concrete_answer_or_not_finding_it_passes(asked: str, answer: str, results: list[dict]) -> None:
    assert llm._payload_fact_defect(answer, _search_payload(results), asked) == ""


def test_a_pages_name_is_repaired_with_its_own_hint() -> None:
    asked = "dónde está el restaurante italiano mas cercano"
    named = "Los mejores restaurantes italianos en Curico, región de Curicó."
    answer = "Trattoria Da Enzo, en el Cerro Alegre, Curicó."
    client = Recorder([named, answer])
    assert client.compose_user_message(asked, "status", {"situation": _search_situation(_ITALIAN)}) == answer
    first = client.payloads[0]["messages"][-1]["content"]
    assert "Lo que una página dice de sí misma" in first
    retry = json.dumps(client.payloads[1]["messages"], ensure_ascii=False)
    assert "Eso es el nombre de una página, no la respuesta" in retry
