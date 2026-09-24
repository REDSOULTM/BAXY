"""Uso real 2026-09-23 (69 media rows of the replay): playing and asking about music, radio,
podcasts and audiobooks, said the way people say it.

- A request to listen said otherwise than «pon …» — a desire, an invitation («escuchemos»), the
  infinitive («tocar música reggae»), starting a podcast, the thing said first («… reprodúcelo»),
  or the music named alone («nueva música pop») — plays what it names, in the person's words.
- An address or a discourse marker said without a pause («oye toca la radio», «olly …», «hola
  google …») is not the first word of the request.
- What names nothing to play asks one short question: the radio without a station, a playlist or
  a podcast without a name, the bare order, the person's own favourite; the answer completes it.
- «Qué/quién … esta canción», «la música que estamos escuchando», «what's on the radio» read what
  plays (media.status).
- An application named as the place to play («en mi aplicación gaana») is not the local player.
"""

from __future__ import annotations

import pytest

from baxy_mind.__main__ import _explicit_arguments_from_evidence, _prepare_turn_result
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic.media import radio_station_query, spoken_media_order
from baxy_mind.semantic.patterns import (
    _completed_missing_music_request,
    resolve_explicit_clarification_intent,
    resolve_explicit_effects,
)
from baxy_mind.semantic.reading import read
from test_c03_pointless_questions import _NoEvidence, _tool
from test_c03_unknown_looked_up import _KnowledgeLlm

OPERATIONS = (
    "media.play.youtube", "media.play.query", "media.play.exact", "media.control", "media.status",
    "streaming.play.named", "app.open", "web.search", "notification.schedule", "audio.volume",
)


@pytest.mark.parametrize(
    ("text", "query"),
    [
        # The replay rows.
        ("tocar música reggae", "música reggae"),
        ("podrías ponerme música clásica", "música clásica"),
        ("mi deseo es escuchar algo de música country", "música country"),
        ("iniciar podcasts de nfl", "podcasts de nfl"),
        ("podcast especial shadi reprodúcelo", "podcast especial shadi"),
        ("escuchemos a la caza del octubre rojo", "la caza del octubre rojo"),
        ("empieza el capitulo cinco de el camino", "el capitulo cinco de el camino"),
        ("nueva música pop", "nueva música pop"),
        ("musica tercer dia", "musica tercer dia"),
        ("aleatorias canciones de coldplay", "coldplay"),
        ("olly pon algo de rock north roll", "rock north roll"),
        ("new pop music", "new pop music"),
        ("olly can we listen to reply all podcast", "reply all podcast"),
        ("i'd like to listen to hear a music of dance and country", "dance and country"),
        ("play something from keane's hopes and fears album", "keane's hopes and fears album"),
        ("vamos a escuchar la emisora ciento tres punto cinco", "103.5 FM en vivo"),
        # The same forms, unseen.
        ("Escuchemos a Soda Stereo", "Soda Stereo"),
        ("vamos a poner canciones de Shakira", "Shakira"),
        ("reproducir música electrónica", "música electrónica"),
        ("empieza el podcast de historia", "el podcast de historia"),
        ("let's listen to Daft Punk", "Daft Punk"),
        ("start the podcast about space", "the podcast about space"),
        ("canciones de amor", "amor"),
        ("oye pon rosalía", "rosalía"),
        ("hey google play reggae music", "reggae music"),
    ],
)
def test_a_request_to_listen_said_another_way_plays_what_it_names(text: str, query: str) -> None:
    reading = read(text, available_operations=OPERATIONS)

    assert reading.effects is not None and reading.effects.operations == ("media.play.youtube",)
    assert reading.clarification is None
    assert _explicit_arguments_from_evidence("media.play.youtube", reading.effects.evidence[0], (), ()) == {
        "query": query,
    }


def test_starting_the_next_episode_moves_to_the_next_one() -> None:
    reading = read("start the next episode", available_operations=OPERATIONS)

    assert reading.effects is not None and reading.effects.operations == ("media.control",)
    assert _explicit_arguments_from_evidence("media.control", reading.effects.evidence[0], (), ()) == {"action": "next"}


@pytest.mark.parametrize(
    "text",
    [
        # A remark about music, a level, talk, a game: nothing to play.
        "música muy fuerte", "musica mas baja", "canciones que me gustan", "podcasts que recomiendas",
        "me encanta la música", "i love music", "can we play a game", "let's play chess", "tocar la guitarra",
        "poner la mesa", "empieza la descarga", "¿música clásica o jazz?", "escuchemos", "vamos a ver",
    ],
)
def test_a_remark_or_another_act_is_not_a_request_to_listen(text: str) -> None:
    reading = read(text, available_operations=OPERATIONS)

    assert reading.effects is None or not any(op.startswith("media.play") for op in reading.effects.operations)


@pytest.mark.parametrize(
    ("text", "operation"),
    [
        ("oye abre chrome", "app.open"),
        ("hey google abre chrome", "app.open"),
        ("mira pon una alarma a las 7", "notification.schedule"),
    ],
)
def test_an_address_said_without_a_pause_is_not_part_of_the_request(text: str, operation: str) -> None:
    reading = read(text, available_operations=OPERATIONS, application_names=("Google Chrome",))

    assert reading.effects is not None and reading.effects.operations == (operation,)


@pytest.mark.parametrize("text", ["oye como va", "google el clima de hoy", "ok google", "bueno, gracias"])
def test_an_address_alone_or_a_word_that_is_not_one_leaves_the_text_as_it_was(text: str) -> None:
    reading = read(text, available_operations=OPERATIONS)

    assert reading.source != "addressed"


@pytest.mark.parametrize(
    "text",
    ["oye toca la radio", "toca fm", "pon la radio", "escucha la radio", "turn on the radio", "Radio por favor"],
)
def test_the_radio_without_a_station_asks_which_one(text: str) -> None:
    asked = resolve_explicit_clarification_intent(text, OPERATIONS)

    assert asked is not None and asked.missing_fields == ("station_or_genre",)
    assert radio_station_query(text) is None


@pytest.mark.parametrize(
    ("previous", "answer", "query"),
    [
        ("oye toca la radio", "cooperativa", "radio cooperativa en vivo"),
        ("toca fm", "la 99.9", "99.9 FM en vivo"),
    ],
)
def test_the_station_answered_plays_that_station(previous: str, answer: str, query: str) -> None:
    completed = _completed_missing_music_request(answer, previous, OPERATIONS)

    assert completed is not None
    intent = resolve_explicit_effects(completed, OPERATIONS)
    assert intent is not None and intent.operations == ("media.play.youtube",)
    assert _explicit_arguments_from_evidence("media.play.youtube", completed, (), ()) == {"query": query}


@pytest.mark.parametrize(
    "text",
    [
        "poner mi canción favorita del año pasado",
        "vamos a poner mi lista de canciones más reproducidas",
        "olly toca un buen tema de mi cantante jazz favorito",
        "play my favorite song",
        "empieza la playlist",
        "pon un podcast",
        "toca",
    ],
)
def test_what_names_nothing_to_play_asks_what_to_play(text: str) -> None:
    reading = read(text, available_operations=OPERATIONS)

    assert reading.clarification is not None and reading.clarification.missing_fields == ("query",)
    assert reading.effects is None or "media.play.youtube" not in reading.effects.operations


def test_the_answer_to_what_to_play_is_played() -> None:
    completed = _completed_missing_music_request("Bohemian Rhapsody", "poner mi canción favorita del año pasado", OPERATIONS)

    assert completed == "pon música de Bohemian Rhapsody"
    assert _explicit_arguments_from_evidence("media.play.youtube", completed, (), ()) == {"query": "Bohemian Rhapsody"}


def test_a_request_for_later_is_not_asked_what_to_play() -> None:
    reading = read(
        "me gustaría escuchar call me de aretha franklin después de esta canción", available_operations=OPERATIONS,
    )

    assert reading.clarification is None


@pytest.mark.parametrize(
    "text",
    [
        "en qué año salió esta canción",
        "cómo llamarías al tipo de música que estamos escuchando",
        "oye por favor dime el nombre de esta canción que se está reproduciendo actualmente",
        "what's on the radio right now",
        "que canción es la que estamos escuchando",
        "de qué disco es esta canción",
        "who sings the song we're listening to",
    ],
)
def test_asking_about_what_plays_reads_what_plays(text: str) -> None:
    reading = read(text, available_operations=OPERATIONS)

    assert reading.effects is not None and reading.effects.operations == ("media.status",)


@pytest.mark.parametrize(
    "text",
    [
        "hola google pon mi lista de reproducción wacky en mi aplicación gaana",
        "hi google play me playlist wacky in my gaana application",
        "pon rock en la aplicacion deezer",
    ],
)
def test_an_application_named_as_the_place_to_play_is_not_the_local_player(text: str) -> None:
    reading = read(text, available_operations=OPERATIONS)

    assert reading.effects is None or not any(op.startswith("media.play") for op in reading.effects.operations)


@pytest.mark.parametrize("text", ["pon rock en la app de spotify", "play jazz on the spotify app"])
def test_the_spotify_application_named_stays_spotify(text: str) -> None:
    intent = resolve_explicit_effects(text, OPERATIONS)

    assert intent is not None and intent.operations == ("media.play.query",)


def test_the_spoken_forms_keep_the_persons_words() -> None:
    assert spoken_media_order("¿Escuchemos algo?") is None
    assert spoken_media_order("tengo ganas de escuchar a Los Redondos") == "pon Los Redondos"
    assert spoken_media_order("me gustaría escuchar cumbia") == "pon música de cumbia"
    assert spoken_media_order("abre chrome") is None


# --- the whole turn: the readers decide before the model's own reading -------------------------------------


class _AskingLlm(_KnowledgeLlm):
    """A model that would answer each of these as talk (the replay refused, searched the web or asked off topic)."""

    @staticmethod
    def formulate_explicit_clarification_question(*_args: object, **_kwargs: object) -> str:
        return "¿Qué emisora pongo?"


def _turn(text: str) -> dict[str, object]:
    tools = {
        name: _tool(name, required=required)
        for name, required in (
            ("web.search", ("query",)),
            ("media.play.youtube", ("query",)),
            ("media.play.query", ("query",)),
            ("media.status", ()),
        )
    }
    return _prepare_turn_result(
        {"id": "turn-media", "text": text},
        llm=_AskingLlm("x"),
        planner_catalog=PlannerCatalog(list(tools.values())),
        turn_evidence=_NoEvidence(),
        encoder=lambda _texts: (),
        tool_by_name=tools,
    )


@pytest.mark.parametrize(
    ("text", "operation"),
    [
        ("tocar música reggae", "media.play.youtube"),
        ("iniciar podcasts de nfl", "media.play.youtube"),
        ("escuchemos a la caza del octubre rojo", "media.play.youtube"),
        ("en qué año salió esta canción", "media.status"),
    ],
)
def test_the_turn_acts_on_the_read_request(text: str, operation: str) -> None:
    result = _turn(text)

    assert result["kind"] == "action"
    assert result["operation"] == operation


def test_the_turn_asks_the_station_of_a_bare_radio() -> None:
    result = _turn("oye toca la radio")

    assert result["kind"] == "clarify"
    assert result["question"] == "¿Qué emisora pongo?"
