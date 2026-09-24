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
        ("sunrise time in Cadiz pls", "It isn't stated anywhere precise, sorry."),
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
