"""M70 (held-out v3h t14/t16): the report of a search is judged by what the pages and the question say.

Pinned on the compose audit of the owner's frozen held-out replayed in the real app (run conv-v3h, traces t14 and t16:
the Google News results, the drafts of each stage and what was published). The request the drafts were judged
against is the decider's («Buscá qué dijo la crítica sobre Oppenheimer.», «¿Cuándo sale la próxima temporada de The
Last of Us?»): the composer words a result against the turn as the mind understood it (dialogue state).

- t14 «averiguá qué dijo la crítica»: the retry «…John Carpenter no se subió a los elogios…» died on «subio» over the
  title «John Carpenter no se sube a los elogios de Oppenheimer» (a stem that changes at its fourth letter), and the
  third draft «Nadie lo dijo.», which names nothing of the pages or the question, was published.
- t16 «fijate cuándo sale la próxima temporada»: no title gives a date; «No hay fecha de estreno confirmada…» died on
  «fecha», «confirmada» and «…sin confirmar una fecha de estreno» also as a failure asserted, though the question
  asked for a date. The last resort fell to the bare «No lo encontré.»: the «Us» of «The Last of Us» was read as the
  person's pronoun and the named not-found was never built.
- Once those words stopped vetoing them, the retries «Cierta página señala… Otra menciona…» and «Un artículo de La
  Vanguardia indica…» show the search (owner rule 2026-09-24): they stay vetoed.
"""

from __future__ import annotations

import pytest

from baxy_mind.llm import (
    _payload_fact_defect,
    _search_not_found_report,
    _search_report_absence_claim,
    _search_report_names_nothing,
    _search_report_unsourced_words,
    _shares_inflected_stem,
    compose_visible_defect,
)
from baxy_mind.semantic.web import asked_dimension_words, searched_clause
from test_c03_cpu_actor import Recorder

_T14_ASK = "Buscá qué dijo la crítica sobre Oppenheimer."
_T14_RESULTS = [
    ("Cuál es la mirada crítica de los científicos sobre la película Oppenheimer", "Infobae, Tue, 01 Aug 2023 07:00:00 GMT"),
    ("James Cameron critica a Christopher Nolan por cómo abordó Oppenheimer", "Indie Hoy, Wed, 02 Jul 2025 07:00:00 GMT"),
    ("Así le dijo Christopher Nolan a Cillian Murphy que protagonizaría Oppenheimer",
     "Paloma & Nacho, Mon, 30 Jun 2025 07:00:00 GMT"),
    ("El nieto de Oppenheimer lamenta una escena en especial de la película: \"definitivamente la habría removido\" "
     "le dijo a Time", "Xataka México, Sun, 30 Jul 2023 07:00:00 GMT"),
    ("John Carpenter no se sube a los elogios de Oppenheimer: Qué dijo", "Indie Hoy, Tue, 07 May 2024 07:00:00 GMT"),
]
_T14_DRAFTS = [
    "La crítica de los científicos señala que la película no refleja con precisión la mirada de los científicos sobre "
    "Oppenheimer.",
    "Cierta página señala que el nieto de Oppenheimer lamentó una escena especial y dijo definitivamente la habría "
    "removido. Otra menciona que John Carpenter no se subió a los elogios de la película.",
    "Nadie lo dijo.",
]

_T16_ASK = "¿Cuándo sale la próxima temporada de The Last of Us?"
_T16_RESULTS = [
    ("La temporada 3 de ‘The Last of Us’ reúne a Laura Bailey, Ian Alexander y John Goodman",
     "Infobae, Tue, 29 Sep 2026 15:15:50 GMT"),
    ("Dos vienen de los videojuegos: La tercera temporada de The Last of Us suma nuevos actores",
     "Punto Cruzado, Mon, 28 Sep 2026 17:43:58 GMT"),
    ("Max anuncia mes de estreno para segunda temporada de The Last Of Us", "TVN, Thu, 24 Sep 2026 07:50:34 GMT"),
    ("La serie ‘The Last of Us’ recupera a dos actores de los videojuegos para la tercera temporada",
     "Diario AS, Mon, 28 Sep 2026 09:15:00 GMT"),
    ("'The Last of Us' ficha otros tres actores para la tercera temporada (¿y última?)",
     "La Vanguardia, Mon, 28 Sep 2026 07:11:19 GMT"),
]
_T16_DRAFTS = [
    "No hay fecha de estreno confirmada para la próxima temporada de The Last of Us.",
    "Un artículo de La Vanguardia indica que la tercera temporada podría ser la última, sin confirmar una fecha de "
    "estreno.",
    "Los resultados hablan de una tercera temporada en septiembre de 2026.",
]


def _payload(query: str, results: list[tuple[str, str]]) -> dict:
    return {
        "operation": "web.search",
        "seen": {
            "query": query,
            "count": len(results),
            "results": [
                {"title": title, "url": "https://news.google.com/rss/articles/CBMi", "snippet": snippet}
                for title, snippet in results
            ],
            "authority": "google_news_rss_search",
        },
    }


def _situation(payload: dict) -> dict:
    return {"kind": "operation", "operation": "web.search", "polarity": "success", "verified": True,
            "succeeded": True, "observed": {"version": 1, **payload["seen"]}}


_T14 = _payload("qué dijo la crítica sobre Oppenheimer", _T14_RESULTS)
_T16 = _payload("Cuándo sale la próxima temporada de The Last of Us", _T16_RESULTS)


# (a) inflection of a stem that changes at its fourth letter.

@pytest.mark.parametrize(("word", "seen"), [("subio", "sube"), ("subieron", "sube"), ("lamento", "lamenta")])
def test_a_conjugated_stem_is_the_same_word(word: str, seen: str) -> None:
    assert _shares_inflected_stem(word, seen)


@pytest.mark.parametrize(
    ("word", "seen"),
    [("ganso", "gana"), ("casino", "casa"), ("salto", "salsa"), ("pesca", "peso"), ("carta", "caro"), ("subio", "sub")],
)
def test_words_that_only_begin_alike_are_not_the_same_word(word: str, seen: str) -> None:
    assert not _shares_inflected_stem(word, seen)


def test_t14_the_retry_word_subio_is_the_title_sube_but_a_word_of_its_own_is_not() -> None:
    assert _search_report_unsourced_words(_T14_DRAFTS[0], _T14, _T14_ASK) == ["refleja", "precision"]
    assert _search_report_unsourced_words(_T14_DRAFTS[1], _T14, _T14_ASK) == []
    assert _search_report_unsourced_words(
        "John Carpenter rechazó los elogios de Oppenheimer.", _T14, _T14_ASK
    ) == ["rechazo"]


# (b) what the question asks for is said when it was not found.

def test_a_question_of_when_where_or_how_much_asks_for_its_dimension() -> None:
    assert {"fecha", "dia", "date"} <= asked_dimension_words(_T16_ASK)
    assert {"lugar", "place"} <= asked_dimension_words("¿Dónde queda el museo?")
    assert {"precio", "price"} <= asked_dimension_words("how much is a ticket")
    assert asked_dimension_words(_T14_ASK) == frozenset()


def test_t16_a_date_asked_and_not_confirmed_is_what_was_not_found() -> None:
    assert _search_report_unsourced_words(_T16_DRAFTS[0], _T16, _T16_ASK) == []
    assert _search_report_unsourced_words(_T16_DRAFTS[1], _T16, _T16_ASK) == []
    assert not _search_report_absence_claim(_T16_DRAFTS[0], _T16, _T16_ASK)
    assert compose_visible_defect(_T16_DRAFTS[1], "status", _T16_ASK, {"situation": _situation(_T16)}) == ""
    assert _search_not_found_report(_T16_DRAFTS[1], _situation(_T16))


def test_t16_a_date_given_is_still_checked_against_the_pages() -> None:
    # Publication dates are not the release date: «septiembre» is no page's word, and a date no page writes is not.
    assert _search_report_unsourced_words(_T16_DRAFTS[2], _T16, _T16_ASK) == ["hablan", "septiembre"]
    assert _search_report_unsourced_words("La tercera temporada se estrena el 12 de marzo.", _T16, _T16_ASK) == [
        "12", "marzo",
    ]


def test_without_a_question_of_when_the_date_is_the_reports_own() -> None:
    ask = "Buscá qué se sabe de la próxima temporada de The Last of Us."
    other = _payload("qué se sabe de la próxima temporada de The Last of Us", _T16_RESULTS)
    assert _search_report_unsourced_words(_T16_DRAFTS[0], other, ask) == ["fecha", "confirmada"]
    assert _search_report_absence_claim(_T16_DRAFTS[0], other, ask)


# (c) a report that names nothing of what was looked up.

def test_t14_a_report_that_names_nothing_is_not_publishable() -> None:
    assert _search_report_names_nothing("Nadie lo dijo.", _T14, _T14_ASK)
    assert _payload_fact_defect("Nadie lo dijo.", _T14, _T14_ASK) == "search_report_names_nothing"
    for named in ("No encontré qué dijo la crítica sobre Oppenheimer.", "No lo encontré.",
                  "James Cameron criticó a Christopher Nolan por cómo abordó Oppenheimer."):
        assert not _search_report_names_nothing(named, _T14, _T14_ASK)
        assert _payload_fact_defect(named, _T14, _T14_ASK) == ""


def test_the_retries_that_show_the_search_stay_vetoed() -> None:
    assert _payload_fact_defect(_T14_DRAFTS[1], _T14, _T14_ASK) == "search_report_shows_the_search"
    assert _payload_fact_defect(_T16_DRAFTS[1], _T16, _T16_ASK) == "search_report_shows_the_search"


def test_the_not_found_names_a_title_with_us_in_it() -> None:
    assert searched_clause(_T16_ASK, "es") == ("cuándo sale la próxima temporada de The Last of Us", True)
    assert searched_clause("Cuándo sale la próxima temporada de The Last of Us", "es") == (
        "cuándo sale la próxima temporada de The Last of Us", True,
    )
    # The person's own «nos» still leaves the plain not-found.
    assert searched_clause("¿Dónde nos vemos mañana?", "es") is None


# The turns end to end, with the drafts the model wrote.

def test_t14_ends_in_the_not_found_that_names_what_was_looked_up() -> None:
    client = Recorder(list(_T14_DRAFTS))
    assert client.compose_user_message(_T14_ASK, "status", {"situation": _situation(_T14)}) == (
        "No encontré qué dijo la crítica sobre Oppenheimer."
    )
    assert len(client.payloads) == 3


def test_t16_publishes_that_no_date_is_confirmed() -> None:
    client = Recorder(list(_T16_DRAFTS))
    assert client.compose_user_message(_T16_ASK, "status", {"situation": _situation(_T16)}) == _T16_DRAFTS[0]
    assert len(client.payloads) == 1


def test_t16_without_a_publishable_draft_names_what_was_looked_up() -> None:
    client = Recorder([_T16_DRAFTS[2]] * 3)
    assert client.compose_user_message(_T16_ASK, "status", {"situation": _situation(_T16)}) == (
        "No encontré cuándo sale la próxima temporada de The Last of Us."
    )
