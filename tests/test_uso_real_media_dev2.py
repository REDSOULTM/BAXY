"""Uso real 2026-09-24 (second media development set, 65 rows): music, radio, podcasts and audiobooks
said the way people say them, which the turn refused, searched on the web or asked about.

- A station is played by any verb that plays or switches on a radio («toca», «enciende», «abre»,
  «sintoniza»), wherever its name puts «radio»; a station named alone plays; the radio channel or the
  radio «encendida» names no station and asks which one.
- A kind of music named alone («indie», «death metal ahora») plays; so does asking leave to listen
  («puedo escuchar…», «let me hear…»), a suggestion («qué tal si pones…», «how about playing…») and
  the order with «solo/just» in front.
- «Los mejores country», «lo mejor de Queen», «classic songs», «something pop», «some jazz», an artist
  and a title said together, a title joined by «of»: each names the music.
- What is the person's own (a playlist, their music) is still asked, as the owner ruled (tanda 4).
- Moving what plays forward or back with no amount asks the amount; resuming a podcast or an audiobook
  resumes what is paused.
- «pon duele como el cielo» is a song, not an event marked «como» a day; a negation inside a relative
  clause («que no sea de…») revokes nothing; a kind of game or a game played «conmigo» names no title.
"""

from __future__ import annotations

import pytest

from baxy_mind.__main__ import _explicit_arguments_from_evidence, _prepare_turn_result
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic.games import steam_library_title
from baxy_mind.semantic.media import radio_station_query
from baxy_mind.semantic.normalize import fold
from baxy_mind.semantic.patterns import _has_contradictory_correction, resolve_explicit_clarification_intent
from baxy_mind.semantic.reading import read
from test_c03_pointless_questions import _NoEvidence, _tool
from test_c03_unknown_looked_up import _KnowledgeLlm

OPERATIONS = (
    "media.play.youtube", "media.play.query", "media.play.exact", "media.control", "media.status",
    "media.seek.relative", "streaming.play.named", "app.open", "web.search", "notification.schedule",
    "audio.volume", "calendar.event.create", "game.entitlement.named", "game.launch",
)


def _played(text: str) -> dict[str, object] | None:
    reading = read(text, available_operations=OPERATIONS)
    assert reading.clarification is None, reading.clarification
    assert reading.effects is not None and reading.effects.operations == ("media.play.youtube",), reading.effects
    return _explicit_arguments_from_evidence("media.play.youtube", reading.effects.evidence[0], (), ())


def _not_played(text: str) -> None:
    reading = read(text, available_operations=OPERATIONS)
    assert reading.effects is None or "media.play.youtube" not in reading.effects.operations, reading.effects


def _asked(text: str) -> tuple[str, ...]:
    reading = read(text, available_operations=OPERATIONS)
    assert reading.clarification is not None, text
    return reading.clarification.missing_fields


# --- radio -------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "query"),
    [
        # The replay rows.
        ("toca bbc radio uno", "bbc radio uno en vivo"),
        ("enciende el emisora novecientos cincuenta y uno", "95.1 FM en vivo"),
        ("abre los cuarenta estación rock", "radio los cuarenta estacion rock en vivo"),
        ("radio tele taxi", "radio tele taxi en vivo"),
        # Unseen.
        ("enciende radio futuro", "radio futuro en vivo"),
        ("prende la emisora noventa y nueve punto siete", "99.7 FM en vivo"),
        ("sintoniza capital radio madrid", "capital radio madrid en vivo"),
        ("radio bío bío", "radio bio bio en vivo"),
        ("emisora cooperativa por favor", "radio cooperativa en vivo"),
    ],
)
def test_a_station_named_or_dialled_plays(text: str, query: str) -> None:
    assert _played(text) == {"query": query}


@pytest.mark.parametrize(
    "text",
    [
        "por favor sintonice el canal de radio",
        "radio encendida",
        "turn on the radio station",
        "enciende la estación de radio",
        "prende la radio ahora",
    ],
)
def test_the_radio_without_a_station_asks_which_one(text: str) -> None:
    assert _asked(text) == ("station_or_genre",)
    _not_played(text)
    assert radio_station_query(text) is None


@pytest.mark.parametrize(
    "text",
    ["mi radio", "la radio está muy alta", "sintonizar un canal de radio para dormir", "radio apagada", "escucho radio siempre"],
)
def test_what_names_no_station_plays_none(text: str) -> None:
    _not_played(text)


# --- the music named -------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "query"),
    [
        # The replay rows.
        ("indie", "indie"),
        ("death metal ahora", "death metal"),
        ("olly death metal now", "death metal"),
        ("puedo escuchar algo de rosalía", "rosalía"),
        ("please let me hear six hundred and sixty six the number of the beast",
         "six hundred and sixty six the number of the beast"),
        ("por favor pon los mejores country", "los mejores country"),
        ("play classic songs", "classic songs"),
        ("play me something pop", "something pop"),
        ("pon michael buble save the last dance", "michael buble save the last dance"),
        ("pon duele como el cielo", "duele como el cielo"),
        ("vamos a oír algo de country y salsa que no sea de los estados unidos",
         "country y salsa que no sea de los estados unidos"),
        # Unseen.
        ("hard rock", "hard rock"),
        ("reggaeton por favor", "reggaeton"),
        ("smooth jazz now", "smooth jazz"),
        ("podemos escuchar a Soda Stereo", "Soda Stereo"),
        ("let me hear bohemian rhapsody", "bohemian rhapsody"),
        ("pon lo mejor de queen", "lo mejor de queen"),
        ("play the greatest hits of abba", "the greatest hits of abba"),
        ("pon los éxitos de juan gabriel", "los éxitos de juan gabriel"),
        ("pon canciones románticas", "canciones románticas"),
        ("play some jazz", "jazz"),
        ("pon un poco de salsa", "salsa"),
        ("pon bad bunny tití me preguntó", "bad bunny tití me preguntó"),
        ("pon shakira hips dont lie", "shakira hips dont lie"),
        ("pon vivir como los ángeles", "vivir como los ángeles"),
        ("pon rock y salsa que no sean de los ochenta", "rock y salsa que no sean de los ochenta"),
        ("qué tal si pones algo de shakira", "shakira"),
        ("how about playing some jazz", "jazz"),
        ("just play some jazz", "jazz"),
    ],
)
def test_the_music_named_plays(text: str, query: str) -> None:
    assert _played(text) == {"query": query}


@pytest.mark.parametrize(
    "text",
    [
        "no rock", "me gusta el rock", "odio el reggaeton", "el rock es lo mejor", "rock?", "me gusta escuchar jazz",
        "play some of that", "solo quiero dormir", "turn on the lights", "enciende la luz",
    ],
)
def test_a_remark_or_another_act_plays_nothing(text: str) -> None:
    _not_played(text)


@pytest.mark.parametrize(
    "text",
    [
        # Nothing named.
        "pon otras canciones", "pon canciones", "play some music", "please turn on my music", "enciende la música",
        # The person's own collection (owner ruling, tanda 4).
        "quiero algo de música qué tal si pones mi playlist de ejercicio",
        "i want some music how about playing my workout playlist",
        "solo reproduce canciones de mi lista de reproducción",
    ],
)
def test_what_names_nothing_to_play_or_is_the_persons_own_is_asked(text: str) -> None:
    assert _asked(text) == ("query",)
    _not_played(text)


def test_a_song_said_with_como_is_not_an_event_but_a_marked_day_still_is() -> None:
    assert resolve_explicit_clarification_intent("pon duele como el cielo", OPERATIONS) is None
    marked = read("marca el trece de junio como el cumpleaños de mi hermano", available_operations=OPERATIONS)
    assert marked.effects is not None and marked.effects.operations == ("calendar.event.create",)


def test_a_negation_inside_a_relative_clause_revokes_nothing() -> None:
    assert not _has_contradictory_correction(fold("pon rock y salsa que no sean de los ochenta"))
    assert _has_contradictory_correction(fold("pon rock y no subas el volumen"))


# --- moving and resuming what plays ------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    ["adelanta por favor", "botón de rebobina", "rewind please", "retrocede un poco", "fast forward the podcast", "adelántalo"],
)
def test_moving_what_plays_with_no_amount_asks_the_amount(text: str) -> None:
    assert read(text, available_operations=OPERATIONS).clarification.operations == ("media.seek.relative",)
    assert _asked(text) == ("seconds",)


@pytest.mark.parametrize("text", ["adelanta la reunión", "adelanta 30 segundos"])
def test_an_amount_or_another_object_is_not_asked_for_seconds(text: str) -> None:
    clarification = read(text, available_operations=OPERATIONS).clarification
    assert clarification is None or clarification.operations != ("media.seek.relative",)


@pytest.mark.parametrize("text", ["resume last played audiobook", "continúa el audiolibro", "reanuda el podcast"])
def test_resuming_a_podcast_or_an_audiobook_resumes_what_is_paused(text: str) -> None:
    reading = read(text, available_operations=OPERATIONS)

    assert reading.clarification is None
    assert reading.effects is not None and reading.effects.operations == ("media.control",)
    assert _explicit_arguments_from_evidence("media.control", reading.effects.evidence[0], (), ()) == {"action": "play"}


@pytest.mark.parametrize("text", ["sabes sobre la letra de esta canción", "conoces a este artista"])
def test_asking_whether_baxy_knows_what_plays_reads_what_plays(text: str) -> None:
    reading = read(text, available_operations=OPERATIONS)

    assert reading.effects is not None and reading.effects.operations == ("media.status",)


# --- games -------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    ["jugar un juego de carreras", "puedes jugar póker conmigo", "quiero jugar un partida de trivial",
     "juega una partida de ajedrez", "play chess with me"],
)
def test_a_kind_of_game_or_a_game_with_baxy_names_no_title(text: str) -> None:
    assert steam_library_title(text) is None


def test_a_named_game_is_still_a_title() -> None:
    assert steam_library_title("juega hollow knight") == "hollow knight"


# --- the whole turn ----------------------------------------------------------------------------------------


class _AskingLlm(_KnowledgeLlm):
    @staticmethod
    def formulate_explicit_clarification_question(*_args: object, **_kwargs: object) -> str:
        return "¿Cuántos segundos?"


def _turn(text: str) -> dict[str, object]:
    tools = {
        name: _tool(name, required=required)
        for name, required in (
            ("web.search", ("query",)),
            ("media.play.youtube", ("query",)),
            ("media.play.query", ("query",)),
            ("media.seek.relative", ("seconds",)),
            ("media.status", ()),
        )
    }
    return _prepare_turn_result(
        {"id": "turn-media-dev2", "text": text},
        llm=_AskingLlm("x"),
        planner_catalog=PlannerCatalog(list(tools.values())),
        turn_evidence=_NoEvidence(),
        encoder=lambda _texts: (),
        tool_by_name=tools,
    )


@pytest.mark.parametrize(
    "text",
    [
        # Fifteen words with no order verb at a clause start: a request to listen, not overheard talk.
        "vamos a oír algo de country y salsa que no sea de los estados unidos",
        "radio tele taxi",
        "death metal ahora",
    ],
)
def test_the_turn_plays_the_music_named(text: str) -> None:
    result = _turn(text)

    assert result["kind"] == "action"
    assert result["operation"] == "media.play.youtube"


def test_the_turn_asks_how_far_to_move() -> None:
    result = _turn("adelanta por favor")

    assert result["kind"] == "clarify"
    assert result["question"] == "¿Cuántos segundos?"
