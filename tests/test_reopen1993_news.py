"""Auditoría semántica 2026-09-20 (REOPEN1993, grupo N): la encuesta pide las
noticias, no nombres de portales. H0033 y H0374 «buscá noticias de hoy» y
H0509 «qué pasó hoy en el mundo» pasan de una web.search que listaba portales
a una lectura tipada web.news.headlines cuyo final cita los titulares."""

from __future__ import annotations

import pytest

from baxy_mind import effect_intent, llm

AVAILABLE = frozenset({"web.search", "weather.current", "web.news.headlines", "system.time"})


@pytest.mark.parametrize(
    ("text", "topic"),
    [
        ("buscá noticias de hoy", None),
        ("busca noticias de hoy", None),
        ("qué pasó hoy en el mundo", None),
        ("dame los titulares", None),
        ("noticias de tecnología", "tecnología"),
        ("news about Chile today", "Chile"),
        # NEWS2027 variants: a question about the news and a bare «top news».
        ("top news today", None),
        ("qué noticias hay de tecnología", "tecnología"),
        ("what's the latest news", None),
        ("cuáles son los titulares de deportes", "deportes"),
    ],
)
def test_news_requests_are_a_typed_headlines_read(text: str, topic: str | None) -> None:
    intent = effect_intent._news_read_intent(text, AVAILABLE)
    assert intent is not None and intent.operations == ("web.news.headlines",)
    assert effect_intent._news_topic(text) == topic
    assert effect_intent.operation_domain_is_grounded(text, "web.news.headlines") is True


@pytest.mark.parametrize(
    "text",
    [
        "qué clima hace hoy",
        "busca el archivo noticias.txt",
        "buscá noticias de hoy y decime la hora",
        "qué significa la palabra noticias",
        "qué es una noticia",
        "qué pasó ayer en mi casa",
        "no quiero noticias",
    ],
)
def test_other_requests_keep_their_own_reader(text: str) -> None:
    assert effect_intent._news_read_intent(text, AVAILABLE) is None


def test_without_the_typed_read_the_news_stay_a_web_search() -> None:
    assert effect_intent._news_read_intent("buscá noticias de hoy", {"web.search"}) is None


SEEN = {
    "count": 3,
    "headlines": [
        {"title": "Bachelet se retira de la carrera por la ONU", "source": "BBC", "publishedAt": "Sun, 20 Sep 2026 21:10:00 GMT"},
        {"title": "Sube el dólar tras el anuncio", "source": "Emol", "publishedAt": "Sun, 20 Sep 2026 20:00:00 GMT"},
        {"title": "Lluvias en la zona central este lunes", "source": "La Tercera", "publishedAt": "Sun, 20 Sep 2026 19:00:00 GMT"},
    ],
}
PAYLOAD = {"operation": "web.news.headlines", "seen": SEEN}


def test_the_reply_quotes_the_headlines() -> None:
    quoted = (
        "Los titulares de hoy: Bachelet se retira de la carrera por la ONU (BBC); "
        "Sube el dólar tras el anuncio (Emol); Lluvias en la zona central este lunes (La Tercera)."
    )
    assert llm._news_fact_defect(quoted, PAYLOAD) == ""
    assert llm._payload_fact_defect(quoted, PAYLOAD, "buscá noticias de hoy") == ""


def test_a_portal_listing_instead_of_headlines_is_missing_state() -> None:
    portals = "Aquí tienes algunas noticias de hoy: Últimas noticias de Chile y el mundo en Meganoticias; Emol."
    assert llm._news_fact_defect(portals, PAYLOAD) == "missing_state"


def test_the_absences_have_their_own_cause_facts() -> None:
    for code in ("news_feed_unavailable", "news_feed_unreadable", "news_feed_empty", "news_topic_without_headlines"):
        assert code in llm._CAUSE_FACT
