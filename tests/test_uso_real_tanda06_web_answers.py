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

Every list mixes Spanish, English and Spanglish and holds phrasings never seen in a run; negative controls keep what
is not a news request out.
"""

from __future__ import annotations

import pytest

from baxy_mind import effect_intent

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
