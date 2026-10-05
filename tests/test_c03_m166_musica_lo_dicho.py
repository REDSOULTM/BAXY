"""M166 (2026-10-05, App runs v4w/v4x/v4y): the music the person asks for is looked up with the title and the artist the
person said.

DEV-H H-w22-t2 «esa no pone bailando solo», after «baxy tirame en spotify cualquier tema de los bunkers mientras
cocino» → «He puesto "El Detenido" de Los Bunkers en Spotify…». The decider restated it «Pon otra canción de Los Bunkers
en Spotify.» (v4w; v4x «Esa no, otra.» → query «Los Bunkers bailando»; v4y «Pon en Spotify «Los Bunkers - Bailando
Solo».» with media.play.exact) and the readers read the restatement: Spotify was asked «otra canción de Los Bunkers»
and another song played; in v4y the exact title held the artist and Spotify showed nothing. The person's own message,
read once «esa no» is set aside, names «bailando solo»; that is what goes (``semantic.arguments.as_the_person_named``,
run inside ``__main__._as_the_person_spelled`` at the end of both argument paths). A query keeps the artist the decided
value adds when the person said it earlier («Los Bunkers»); an exact title is the song's title alone.

Rows are quoted with their real text and the history the App lived; every other phrasing is our own.
"""

from __future__ import annotations

from typing import Any

from baxy_mind import __main__ as sidecar
from baxy_mind import llm
from baxy_mind.semantic.arguments import music_named_in_message
from baxy_mind.semantic.dialogue import DialogueState

PLAY_QUERY = {"type": "object", "properties": {
    "provider": {"type": "string", "enum": ["spotify"], "x-maxUtf8Bytes": 1024},
    "query": {"type": "string", "x-maxUtf8Bytes": 1024, "x-nonWhitespace": True},
}, "required": ["provider", "query"], "additionalProperties": False}
PLAY_EXACT = {"type": "object", "properties": {
    "provider": {"type": "string", "enum": ["spotify"], "x-maxUtf8Bytes": 1024},
    "title": {"type": "string", "x-maxUtf8Bytes": 1024, "x-nonWhitespace": True},
}, "required": ["provider", "title"], "additionalProperties": False}


def _tool(operation: str, schema: dict[str, Any]) -> dict[str, Any]:
    return {"type": "function", "function": {"name": operation.replace(".", "_"), "canonical_name": operation,
                                             "description": operation, "risk": "low_reversible", "parameters": schema}}


def _history(said: list[str]) -> list[dict[str, str]]:
    return [{"role": "user" if index % 2 == 0 else "assistant", "content": line} for index, line in enumerate(said)]


class _Abstaining:
    def extract_direct_arguments(self, *_args: object, **_kwargs: object) -> llm.DirectArgumentExtraction:
        return llm.DirectArgumentExtraction(arguments=None, evidence=(), fallback_question="¿Qué canción?")

    def formulate_missing_argument_question(self, *_args: object, **_kwargs: object) -> str:
        return "¿Qué canción?"


def _arguments(operation: str, schema: dict[str, Any], said: list[str], request: str,
               decided: tuple[tuple[str, Any], ...]) -> tuple[Any, str]:
    """The App's arguments request: the decider's restatement as text, the lived conversation as history."""

    sidecar._remember_decided_arguments(request, (operation,), decided)
    return sidecar._direct_arguments_result(
        {"operation": operation, "text": request, "history": _history(said), "responseLanguage": "es"},
        llm=_Abstaining(), tool=_tool(operation, schema), dialogue_state=DialogueState(),
    )


def _named(operation: str, arguments: dict[str, Any], said: list[str]) -> dict[str, Any]:
    return sidecar._as_the_person_spelled(operation, arguments, said[-1], _history(said))


# ------------------------------------------------------------------ H-w22-t2, the title the person said

H_W22 = [
    "baxy tirame en spotify cualquier tema de los bunkers mientras cocino",
    "He puesto \"El Detenido\" de Los Bunkers en Spotify y ya está sonando.",
    "esa no pone bailando solo",
]


def test_h_w22_t2_v4w_spotify_is_asked_the_title_said() -> None:
    arguments, question = _arguments(
        "media.play.query", PLAY_QUERY, H_W22, "Pon otra canción de Los Bunkers en Spotify.",
        (("provider", "Spotify"), ("query", "otra canción de Los Bunkers")),
    )
    assert (arguments, question) == ({"provider": "spotify", "query": "bailando solo Los Bunkers"}, "")


def test_h_w22_t2_v4x_and_v4y_the_same_row() -> None:
    # v4x: the query the App used («Los Bunkers bailando») lost «solo».
    assert _named("media.play.query", {"provider": "spotify", "query": "Los Bunkers bailando"}, H_W22) == {
        "provider": "spotify", "query": "bailando solo Los Bunkers",
    }
    # v4y: after «Los Bunkers - Bailando Solo - En Vivo» played, the exact title held the artist and Spotify showed
    # nothing; the song's title is the person's.
    said = [H_W22[0], "He puesto «Los Bunkers - Bailando Solo - En Vivo» en Spotify.", H_W22[2]]
    arguments, question = _arguments(
        "media.play.exact", PLAY_EXACT, said, "Pon en Spotify «Los Bunkers - Bailando Solo».",
        (("provider", "Spotify"), ("title", "Los Bunkers - Bailando Solo")),
    )
    assert (arguments, question) == ({"provider": "spotify", "title": "bailando solo"}, "")


def test_the_reader_sets_the_rejection_aside() -> None:
    assert music_named_in_message("media.play.query", "esa no pone bailando solo") == {"query": "bailando solo"}
    assert music_named_in_message("media.play.query", "no, esa no, pon tren al sur de los prisioneros") == {
        "query": "tren al sur de los prisioneros",
    }
    assert music_named_in_message("media.play.query", "not that one, play Tren al sur by Los Prisioneros") == {
        "query": "Tren al sur by Los Prisioneros",
    }
    # No title said: nothing named.
    for text in ("no esta no, ponme otra de el", "esa no, una más movida po", "no esa no, la otra versión que es en vivo",
                 "esa no, pon la versión en vivo", "pon la última de Rosalía en spotify", "pone otra"):
        assert music_named_in_message("media.play.query", text) == {}, text


# ------------------------------------------------------------------ variants in other words, the other language

def test_variants_the_title_and_the_artist_said_go() -> None:
    # The decider's artist nobody said is not used.
    said = ["play Monastery by Men I Trust on spotify"]
    assert _named("media.play.query", {"provider": "spotify", "query": "Monastery Coldplay"}, said)["query"] == (
        "Monastery by Men I Trust"
    )
    said = ["pon la canción monastery de men i trust en spotify"]
    assert _named("media.play.query", {"provider": "spotify", "query": "Monastery de Linkin Park"}, said)["query"] == (
        "monastery de men i trust"
    )
    # «esa no, pon X» after a song of the same artist: the title said, with the artist said before.
    said = ["pon algo de los prisioneros en spotify", "Suena «Muevan las industrias» de Los Prisioneros.",
            "no, esa no, pon el baile de los que sobran"]
    assert _named("media.play.query", {"provider": "spotify", "query": "otra de Los Prisioneros"}, said)["query"] == (
        "el baile de los que sobran Los Prisioneros"
    )
    said = ["put on some Radiohead", "Playing «Creep» by Radiohead on Spotify.", "not that one, play karma police"]
    assert _named("media.play.query", {"provider": "spotify", "query": "another Radiohead song"}, said)["query"] == (
        "karma police Radiohead"
    )
    # An exact title with words the message did not say is the person's title.
    said = ["play some Radiohead", "Playing «Creep» by Radiohead.", "not that one, play karma police"]
    assert _named("media.play.exact", {"provider": "spotify", "title": "Radiohead - Karma Police"}, said)["title"] == (
        "karma police"
    )


# ------------------------------------------------------------------ what must not change

def test_what_must_not_change() -> None:
    # The decided value keeps every word said (and adds the artist said before): it stays.
    assert _named("media.play.query", {"provider": "spotify", "query": "Bailando Solo de Los Bunkers"}, H_W22) == {
        "provider": "spotify", "query": "Bailando Solo de Los Bunkers",
    }
    said = ["play Monastery by Men I Trust"]
    assert _named("media.play.exact", {"provider": "spotify", "title": "Monastery"}, said)["title"] == "Monastery"
    # M147/M157: an artist respelled by the model goes as the person wrote it, as before.
    said = ["ya cambiando de tema, pone algo de javiera mena en spotify"]
    assert _named("media.play.query", {"provider": "spotify", "query": "Javier Mené"}, said)["query"] == "javiera mena"
    # No title said: «música de los 80», «la última de Rosalía» (the decider's own title, nobody's, is not made worse),
    # «otra de él», «una más movida», «la en vivo».
    for query in ("música de los 80", "80s"):
        assert _named("media.play.query", {"provider": "spotify", "query": query}, ["pon música de los 80"])["query"] == query
    for query in ("Rosalía", "Despechá de Rosalía"):
        said = ["pon la última de Rosalía en spotify"]
        assert _named("media.play.query", {"provider": "spotify", "query": query}, said)["query"] == query
    said = ["oye ponme la rola nueva de carin leon", "Puse «Carín León - Primera Cita».", "no esta no, ponme otra de el"]
    assert _named("media.play.query", {"provider": "spotify", "query": "otra canción de Carín León"}, said)["query"] == (
        "otra canción de Carín León"
    )
    said = ["oye, tírame unas canciones de Mon Laferte por Spotify mientras cocino", "Suena «Mi Buen Amor».",
            "esa no, una más movida po"]
    assert _named("media.play.query", {"provider": "spotify", "query": "una canción más movida de Mon Laferte"},
                  said)["query"] == "una canción más movida de Mon Laferte"
    said = [H_W22[0], H_W22[1], "esa no, pon la versión en vivo"]
    assert _named("media.play.query", {"provider": "spotify", "query": "El Detenido en vivo de Los Bunkers"},
                  said)["query"] == "El Detenido en vivo de Los Bunkers"
    # A title with a typo the service forgives: the model's spelling is a near miss and stays (an exact title too).
    said = ["pon bohemian rapsodi de queen"]
    assert _named("media.play.query", {"provider": "spotify", "query": "Bohemian Rhapsody de Queen"}, said)["query"] == (
        "Bohemian Rhapsody de Queen"
    )
    assert _named("media.play.exact", {"provider": "spotify", "title": "Bohemian Rhapsody"}, said)["title"] == (
        "Bohemian Rhapsody"
    )
    # A long YouTube request, said in other words.
    said = ["¿me pones el trailer de Dune Part Three en YouTube porfa?"]
    assert _named("media.play.youtube", {"query": "tráiler de Dune: Part Three"}, said) == {
        "query": "tráiler de Dune: Part Three",
    }
    # DEV-F F-w28-t4: what follows the comma is the person's situation, not what to play (M118's query stays).
    said = ["ponme algo de lo-fi pa concentrarme, tengo que terminar el informe de la u"]
    assert _named("media.play.query", {"provider": "spotify", "query": "lo-fi para concentrarse"}, said)["query"] == (
        "lo-fi para concentrarse"
    )
    # DEV-G G-w23-t1/t2 (v4y): the query was already the person's words; «la otra versión que es en vivo» names no
    # title, so the decided value stays.
    said = ["pon la canción monastery de men i trust en spotify"]
    assert _named("media.play.query", {"provider": "spotify", "query": "monastery de men i trust"}, said)["query"] == (
        "monastery de men i trust"
    )
    said = [said[0], "Puse la música «Linkin Park - SuperXero - By Myself Demo»: se está reproduciendo.",
            "no esa no, la otra versión que es en vivo"]
    assert _named("media.play.exact", {"provider": "spotify", "title": "Monastery"}, said)["title"] == "Monastery"
    # Other operations are untouched.
    said = ["busca bailando solo de los bunkers"]
    assert _named("web.search", {"query": "otra canción de Los Bunkers"}, said) == {
        "query": "otra canción de Los Bunkers",
    }
