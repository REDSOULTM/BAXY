"""M179 (2026-10-06, App runs v5a–v5d): searches refused as limits and web follow-ups that lose their topic.

Owner rule restated by the coordinator: an order whose main verb is something BAXY does (search the web, play a title)
is no limit because of a detail BAXY does not control; the detail is said, it never cancels the order. In an elliptic
follow-up («¿y la libra?», «y el técnico de ellos») the query takes the NEW thing named and the rest of the context
before (today, the country, the team), never the old thing it replaces. Each row below was traced in the App's audit:

* F-w16-t2 «sí, órale, búscame unas por la Roma Norte» after «¿me puedes pedir unos tacos al pastor por Rappi?»: the
  decider restated «Busca unos tacos al pastor por Rappi en Roma Norte.» and decided limit (v5b, v5c, v5d); no reader
  proves «busca» + a kind of place in a place, so the limit's re-read (M78) found nothing → «Eso no lo hago: buscar…».
* D-p19-t1 «I'd like to watch a movie called After the Wedding with Spanish subtitles on.»: the decider's limit «Play
  the movie After the Wedding with Spanish subtitles.» in every run → «I do not provide movies with subtitles.»
* G-w03-t3 «no, la temporada 2, el primer episodio» after «pon Stranger Things en Netflix»: the decider's limit «Pon la
  temporada 2 del primer episodio de Stranger Things en Netflix.», which the readers prove as streaming.play.named; the
  re-read skipped it because the message leans on the conversation and only a canonical rewrite of the restatement
  was read (M112), and M171 had left it a limit. M179 supersedes that part of M171.
* I-w17-t2 «¿y la libra, cómo anda?» after the dollar: the decider restated «¿Cómo está el dólar hoy, por favor?» and
  the dollar was searched again (seen.query, every run) → «No encontré información sobre el tipo de cambio del dólar».
* I-w26-t5 «oye y el tecnico de ellos quien es ahora» four turns after «a que hora juega chile el martes»: the decider
  kept «¿Quién es el técnico de ellos ahora?» (v5a, v5c, v5d), searched as said; the coach of the Tigres came back.

Not changed: F-w60-t4 «y el vocalista que es de su vida sigue tocando» (the decider talked; who the band is lives only
in the song the player verified, see the report). Every phrasing beyond the rows is our own; nothing here depends on
the clock.
"""

from __future__ import annotations

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic.arguments import partial_explicit_arguments, watch_named_title
from baxy_mind.semantic.decider import ContextDecision, followup_thing_kept, with_the_searched_name
from baxy_mind.semantic.dialogue import DialogueState
from baxy_mind.semantic.web import searches_places_somewhere
from test_c03_m148_avisos_eso_y_cuentas import OPERATIONS, _Decider, _history, _tool

STREAMING = {"type": "object", "properties": {
    "service": {"type": "string", "enum": ["disney_plus", "netflix"]},
    "title": {"type": "string", "x-maxUtf8Bytes": 512, "x-nonWhitespace": True}},
    "required": ["service", "title"], "additionalProperties": False}

# The conversations as the App lived them in v5d (BAXY's replies are the run's).
W16_F = [
    "oye, ¿me puedes pedir unos tacos al pastor por Rappi? ando muerto de hambre güey",
    "Eso no lo hago: pedir tacos al pastor.",
    "sí, órale, búscame unas por la Roma Norte",
]
P19_D = ["I'd like to watch a movie called After the Wedding with Spanish subtitles on."]
W03_G = [
    "oye, pide un uber pa las 8 to the airport",
    "Eso no lo hago: pedir un Uber para ir al aeropuerto.",
    "ok ok, entonces pon Stranger Things en Netflix",
    "No se pudo poner Stranger Things en Netflix porque la plataforma pide iniciar sesión en este PC.",
    "no, la temporada 2, el primer episodio",
]
W17_I = [
    "¿podrías decirme cómo está el dólar hoy, por favor?",
    "Hoy el dólar vale 987.25 pesos chilenos.",
    "¿y la libra, cómo anda?",
]
W26_I = [
    "a que hora juega chile el martes",
    "Juegan el martes 6 de octubre de 2026 a las 23:30 hora local.",
    "recuerdame una hora antes de eso",
    "He configurado la alarma para el martes 6 de octubre de 2026 a las 22:30 y te la recordaré a esa hora.",
    "muestrame todas las alarmas y recordatorios q tengo pa esta semana",
    "Tienes 13 alarmas y recordatorios programados para esta semana.",
    "cancela la de las 7 que mañana no trabajo",
    "No pude cancelar el aviso.",
    "oye y el tecnico de ellos quien es ahora",
]


def _searched(topic: str) -> DialogueState:
    """The dialogue state after a verified search of ``topic`` (the query the provider saw)."""

    state = DialogueState()
    state.expect(topic, ["web.search"])
    state.record({"operation": "web.search", "verified": True, "succeeded": True, "observed": {"query": topic}})
    return state


def _turn(said: list[str], decision: ContextDecision, state: DialogueState | None = None) -> dict:
    """``said``: the conversation, user first and alternating, ending in the person's message."""

    tools = {name: _tool(name) for name in OPERATIONS}
    return sidecar._prepare_turn_result(
        {"id": "m179", "text": said[-1], "history": _history(said)},
        llm=_Decider(decision), planner_catalog=PlannerCatalog(list(tools.values())), encoder=lambda _t: (),
        tool_by_name=tools, dialogue_state=state or DialogueState(),
    )


def _limit(restated: str) -> ContextDecision:
    return ContextDecision(restated, "limit", (), "")


def _search(restated: str) -> ContextDecision:
    return ContextDecision(restated, "action", ("web.search",), "")


def _is_limit(result: dict) -> bool:
    return result["kind"] == "conversation" and result.get("conversationKind") == "unsupported"


def _does(result: dict, operation: str) -> bool:
    return result["kind"] == "action" and result["operation"] == operation


# ------------------------------------------------------------------ a search for places in a place is no limit


@pytest.mark.parametrize(
    ("said", "restated"),
    [
        (W16_F, "Busca unos tacos al pastor por Rappi en Roma Norte."),
        (["pedime una muzza por PedidosYa", "Eso no lo hago: pedir comida por PedidosYa.",
          "dale, buscame unas pizzerías por Palermo entonces"], "Busca pizzerías en Palermo por PedidosYa."),
        (["order me some ramen on Uber Eats", "I don't order food for you.",
          "yeah go ahead, look for some ramen spots in Shibuya"], "Look for ramen spots in Shibuya on Uber Eats."),
    ],
)
def test_a_search_for_places_somewhere_is_searched(said: list[str], restated: str) -> None:
    assert searches_places_somewhere(said[-1], restated)
    result = _turn(said, _limit(restated))
    assert _does(result, "web.search")
    assert result["objective"] == restated


@pytest.mark.parametrize(
    ("said", "restated"),
    [
        # A ride is no place (DEV-D D-s056, D-s090 stay limits).
        (["busca un taxi para ir a casa"], "Busca un taxi para ir a casa."),
        (["find me an uber to the liberty bell"], "Find me an Uber to the Liberty Bell."),
        # A search with the order or the booking in the same message is that transaction.
        (["búscame un restaurante en Providencia y resérvame una mesa"], "Reserva una mesa en un restaurante."),
        # The same follow-up with no place said, and the first message ordering food.
        (W16_F[:2] + ["sí, órale, búscame unas"], "Busca unos tacos al pastor por Rappi."),
        (W16_F[:1], "Pide tacos al pastor por Rappi."),
        (["baxy pídeme una pizza grande de pepperoni"], "Pide una pizza grande de pepperoni."),
    ],
)
def test_a_ride_or_an_order_stays_a_limit(said: list[str], restated: str) -> None:
    assert _is_limit(_turn(said, _limit(restated)))


def test_the_persons_own_things_are_never_searched_on_the_web() -> None:
    assert not searches_places_somewhere("busca mis fotos de tacos en Descargas", "Busca fotos de tacos.")


# ------------------------------------------------------------------ a title to watch is played, with its detail


def test_d_p19_t1_the_named_film_is_played_and_its_service_asked() -> None:
    restated = "Play the movie After the Wedding with Spanish subtitles."
    result = _turn(P19_D, _limit(restated))
    assert _does(result, "streaming.play.named")
    assert partial_explicit_arguments("streaming.play.named", result["objective"], STREAMING) == {
        "title": "After the Wedding"}


@pytest.mark.parametrize(
    ("text", "restated", "title"),
    [
        ("quiero ver la película Roma con subtítulos en inglés", "Pon la película Roma con subtítulos en inglés.",
         "Roma"),
        ("I want to watch the series Dark with English dubbing", "Play the series Dark with English dubbing.", "Dark"),
    ],
)
def test_a_title_to_watch_with_a_detail_is_played(text: str, restated: str, title: str) -> None:
    assert watch_named_title(text) == title
    assert _does(_turn([text], _limit(restated)), "streaming.play.named")


@pytest.mark.parametrize(
    ("said", "restated"),
    [
        (W03_G, "Pon la temporada 2 del primer episodio de Stranger Things en Netflix."),
        (["play Stranger Things on Netflix", "Netflix asks for a sign-in on this PC.", "no, season 2, the first one"],
         "Play season 2 episode 1 of Stranger Things on Netflix."),
        (["pon Merlina en Netflix", "Listo, Merlina está sonando en Netflix.", "mejor el capítulo 3"],
         "Pon el capítulo 3 de Merlina en Netflix."),
    ],
)
def test_a_season_or_an_episode_is_a_detail_of_the_title(said: list[str], restated: str) -> None:
    result = _turn(said, _limit(restated))
    assert _does(result, "streaming.play.named")
    assert result["objective"] == restated


@pytest.mark.parametrize(
    ("said", "restated"),
    [
        # The screen or the device to watch it on is where BAXY does not reach.
        (["quiero ver la serie Dark en la tele del living"], "Pon Dark en la tele del living."),
        (["pon Bluey en Disney+", "Listo, Bluey está en Disney+.", "no, en la tele del living"],
         "Pon Bluey en Disney+ en la tele del living."),
        # A film with no title named, with a detail (DEV-D D-p29-t3).
        (["Scary stories sounds great to me. I would like to watch this movie with English subtitles."],
         "Play a scary movie with English subtitles."),
    ],
)
def test_where_baxy_does_not_reach_stays_a_limit(said: list[str], restated: str) -> None:
    assert _is_limit(_turn(said, _limit(restated)))


# ------------------------------------------------------------------ the new thing of a follow-up is searched


@pytest.mark.parametrize(
    ("said", "restated", "searched"),
    [
        (W17_I, "¿Cómo está el dólar hoy, por favor?", "¿Cómo está la libra hoy, por favor?"),
        (["how much is the dollar today in pesos?", "Today the dollar is at 940 pesos.",
          "and the pound, how is it doing?"], "How much is the dollar today in pesos?",
         "How much is the pound today in pesos?"),
        (["who is the lakers coach now?", "JJ Redick coaches the Lakers.", "and the Celtics?"],
         "Who is the Lakers' coach now?", "Who is the Celtics' coach now?"),
    ],
)
def test_the_new_thing_takes_the_place_of_the_old(said: list[str], restated: str, searched: str) -> None:
    result = _turn(said, _search(restated))
    assert _does(result, "web.search")
    assert result["objective"] == searched


@pytest.mark.parametrize(
    ("said", "restated"),
    [
        # The decider kept the new thing (I-w25-t3, F-w53-t2).
        (["¿cómo está el dólar hoy?", "Hoy el dólar vale 940 pesos.", "¿y el euro cómo anda?"],
         "¿Cómo va el euro hoy?"),
        # «el del Banco Nación» names no new thing (H-w24-t2).
        (["cuánto está el dólar hoy", "Hoy el dólar oficial está a 1.050 pesos.",
          "ok y el del banco nación cuánto está?"],
         "¿A cuánto está hoy el dólar del Banco Nación?"),
        # Two old things could be the one replaced: the decider's restatement stands.
        (["¿cuánto vale el dólar contra el euro hoy?", "El dólar vale 0,92 euros.", "¿y la libra?"],
         "¿Cuánto vale el dólar contra el euro hoy?"),
        # A follow-up with no article, and a first message.
        (["how much is the dollar today?", "Today the dollar is at 940 pesos.", "and in euros?"],
         "How much is the dollar today in euros?"),
        (["¿y la libra, cómo anda?"], "¿Cómo está la libra?"),
    ],
)
def test_a_search_that_keeps_its_thing_is_not_touched(said: list[str], restated: str) -> None:
    result = _turn(said, _search(restated))
    assert _does(result, "web.search")
    assert result["objective"] == restated


def test_only_a_search_takes_the_new_thing() -> None:
    # The substitution itself would read any follow-up; only a search decision is given it.
    assert followup_thing_kept("Pon el brillo en 40.", "y el volumen?", "pon el brillo en 40") == (
        "Pon el volumen en 40.")
    said = ["pon el brillo en 40", "Listo, el brillo está en 40.", "¿y el volumen?"]
    result = _turn(said, ContextDecision("¿En cuánto está el brillo?", "action", ("system.settings.status",), ""))
    assert result["objective"] == "¿En cuánto está el brillo?"


# ------------------------------------------------------------------ «de ellos» is the one named in the last search


def test_i_w26_t5_their_coach_is_the_coach_of_the_team_searched() -> None:
    state = _searched("¿A qué hora juega Chile el martes?")
    result = _turn(W26_I, _search("¿Quién es el técnico de ellos ahora?"), state)
    assert _does(result, "web.search")
    assert result["objective"] == "¿Quién es el técnico de Chile ahora?"


@pytest.mark.parametrize(
    ("said", "restated", "topic", "searched"),
    [
        (["when do the Lakers play next?", "They play the Kings on Monday at 23:00.", "and who's their coach now?"],
         "Who is their coach now?", "When do the Lakers play next?", "Who is Lakers' coach now?"),
        (["¿cuándo vuelven a tocar los bunkers?", "Tocan el sábado en el Movistar Arena.",
          "¿y el baterista de ellos sigue siendo el mismo?"],
         "¿El baterista de ellos sigue siendo el mismo?", "¿Cuándo vuelven a tocar Los Bunkers?",
         "¿El baterista de Los Bunkers sigue siendo el mismo?"),
    ],
)
def test_their_is_the_one_named_in_the_last_search(said: list[str], restated: str, topic: str, searched: str) -> None:
    assert with_the_searched_name(restated, said[-1], topic) == searched
    result = _turn(said, _search(restated), _searched(topic))
    assert result["objective"] == searched


@pytest.mark.parametrize(
    ("restated", "text", "topic"),
    [
        # Nothing searched before.
        ("¿Quién es el técnico de ellos ahora?", W26_I[-1], None),
        # The last search names two, or none.
        ("¿Quién es el técnico de ellos ahora?", W26_I[-1], "¿Cuándo juegan Chile y Perú?"),
        ("¿El baterista de ellos sigue siendo el mismo?", "¿y el baterista de ellos?",
         "¿Cuándo tocan Los Bunkers en Santiago?"),
        ("¿Quién es el técnico de ellos ahora?", W26_I[-1], "¿a qué hora es el partido?"),
        # The restatement already names who (G-w42-t3 in v5d), or the person did not say the pronoun.
        ("Who is the Lakers' coach now?", "and who's their coach now?", "When do the Lakers play next?"),
        ("¿Quién es el técnico de ellos ahora?", "y el técnico quién es ahora", "¿A qué hora juega Chile el martes?"),
    ],
)
def test_their_stays_without_one_name_to_put(restated: str, text: str, topic: str | None) -> None:
    assert with_the_searched_name(restated, text, topic) is None
