"""Estabilización L3: buscar dentro de la biblioteca de Steam es un límite declarado.

g1 («en Steam andá a la biblioteca y buscá Cuphead») fue inestable toda la misión (0/3 en la fase 1, 3/3, luego 0/1: el
modelo elige Ctrl+K o vuelve a hacer clic en BIBLIOTECA): Steam, dibujado con CEF, no deja escribir de forma fiable en el
buscador de su biblioteca. El límite vive en los datos del lugar (app_places.v1.json: la biblioteca «search»: false) y lo
aplica el lector general de límites (semantic.limits.with_declared_limits): la misión va a la biblioteca, que es lo
seguro, y el suelo dice corto que no puede buscar ahí y ofrece buscarlo en la tienda. «buscá Cuphead en Steam» y «… en la
tienda» siguen buscando en la tienda por su dirección (lug-2); «buscá X en Spotify» sigue reproduciendo.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from baxy_mind.cu_finals import floor_first
from baxy_mind.semantic import app_places, limits, missions, patterns

ROOT = Path(__file__).resolve().parents[1]
NAMES = ("Steam", "Spotify", "Paint", "Bloc de notas", "Configuración", "Discord")
GAMES = (("steam", "252950", "Rocket League"), ("steam", "268910", "Cuphead"))
OPERATIONS = tuple(sorted(set(re.findall(
    r'Descriptor\(\s*"([a-z][a-z0-9._]+)"',
    (ROOT / "src" / "Baxy.Kernel" / "Operations" / "ProductCatalog.cs").read_text(encoding="utf-8"),
))))


def _marked(said: str) -> dict:
    mission = missions.mission_request(said, NAMES)
    assert mission is not None, said
    marked = limits.with_declared_limits(mission.arguments())
    assert marked is not None
    return marked


def _limits_of(marked: dict) -> list[object]:
    return [step.get("limit") for step in marked.get("steps") or ()]


# ------------------------------------------------------------------------------------------ the data of the place


def test_the_library_says_it_cannot_be_searched_and_the_store_is_where_it_searches() -> None:
    steam = json.loads((ROOT / "src" / "baxy_mind" / "data" / "app_places.v1.json").read_text(encoding="utf-8"))[
        "applications"]["Steam"]["places"]
    assert steam["library"]["search"] is False
    assert app_places.search_offer("Steam") == "store"
    assert app_places.said_as("Steam", "store", "es") == "la tienda"
    assert app_places.said_as("Steam", "library", "en") == "the library"


# ------------------------------------------------------------------------------------------ the reading (g1 and its forms)


@pytest.mark.parametrize("said", [
    "en Steam andá a la biblioteca y buscá Cuphead",  # g1
    "abrí Steam, andá a la biblioteca y buscá Cuphead",
    "en Steam andá a la biblioteca y buscá Rocket League",
])
def test_g1_goes_to_the_library_and_stops_on_the_search(said: str) -> None:
    marked = _marked(said)
    steps = marked["steps"]
    assert _limits_of(marked) == [None, limits.PLACE_SEARCH], steps
    assert app_places.goes_to("Steam", steps[0]["goal"], "library"), steps
    assert app_places.place_of("Steam", steps[0]["goal"], GAMES) == {"place": "library"}


@pytest.mark.parametrize("arguments", [
    {"goal": "buscar Cuphead en mi biblioteca", "application": "Steam", "successCheck": "text:cuphead"},
    {"goal": "buscá Cuphead en mi biblioteca de Steam", "application": "Steam", "successCheck": "text:cuphead",
     "steps": [{"goal": "buscar Cuphead", "application": "Steam", "successCheck": "text:cuphead"}]},
])
def test_a_search_said_in_the_library_goes_there_first(arguments: dict) -> None:
    marked = limits.with_declared_limits(arguments)
    steps = marked["steps"]
    assert _limits_of(marked) == [None, limits.PLACE_SEARCH], steps
    assert steps[0]["goal"] == "ir a biblioteca" and steps[0]["application"] == "Steam"
    assert steps[0]["successCheck"], steps


@pytest.mark.parametrize("said", [
    "en Steam buscá Cuphead en mi biblioteca",
    "en Steam buscá Rocket League en mi biblioteca",
])
def test_the_person_s_words_for_a_search_in_the_library_are_the_limit(said: str) -> None:
    marked = _marked(said)
    assert _limits_of(marked)[-1] == limits.PLACE_SEARCH, marked
    assert any(app_places.goes_to("Steam", step.get("goal"), "library") for step in marked["steps"][:-1]), marked


@pytest.mark.parametrize("said", [
    # No reader reads these: the decider hands the engine the person's own words (free_form_arguments).
    "buscá Cuphead en mi biblioteca de Steam",
    "en mi biblioteca de Steam buscá Cuphead",
    "search Cuphead in my Steam library",
])
def test_the_engine_s_free_form_search_in_the_library_is_the_limit_too(said: str) -> None:
    assert missions.mission_request(said, NAMES) is None
    arguments = missions.free_form_arguments(said, NAMES)
    assert arguments is not None and arguments.get("application") == "Steam", arguments
    marked = limits.with_declared_limits(arguments)
    assert _limits_of(marked) == [None, limits.PLACE_SEARCH], marked
    assert app_places.goes_to("Steam", marked["steps"][0]["goal"], "library")


# ------------------------------------------------------------------------------------------ contracases


@pytest.mark.parametrize("said", [
    "en Steam buscá Cuphead",
    "en Steam buscá Cuphead en la tienda",
    "en Spotify buscá Los Bunkers",
    "en Spotify, andá a tu biblioteca y buscá Los Bunkers",
])
def test_contracase_a_search_the_application_can_do_is_no_limit(said: str) -> None:
    mission = missions.mission_request(said, NAMES)
    assert mission is not None, said
    assert limits.PLACE_SEARCH not in _limits_of(limits.with_declared_limits(mission.arguments()) or {})


def test_contracase_lug2_the_store_search_keeps_its_address() -> None:
    for said in ("en Steam buscá Cuphead", "en la tienda de Steam buscá Cuphead"):
        assert app_places.place_of("Steam", "buscar Cuphead", GAMES, said=said) == {
            "place": "results", "placeValue": "Cuphead"}
        assert app_places.search_limit("Steam", "buscar Cuphead", said) is None
    arguments = missions.free_form_arguments("buscá Cuphead en Steam", NAMES)
    assert limits.PLACE_SEARCH not in _limits_of(limits.with_declared_limits(arguments) or {})


def test_contracase_searching_a_band_in_spotify_still_plays_it() -> None:
    intent = patterns.resolve_explicit_effects("buscá Los Bunkers en Spotify", OPERATIONS, NAMES, GAMES)
    assert intent is not None and intent.operations == ("media.play.query",)
    assert app_places.search_limit("Spotify", "buscar Los Bunkers", "buscá Los Bunkers en Spotify") is None


def test_contracase_going_to_the_library_alone_is_no_limit() -> None:
    marked = _marked("en Steam andá a la biblioteca")
    assert limits.PLACE_SEARCH not in _limits_of(marked)


# ------------------------------------------------------------------------------------------ what the floor says


def _stopped_in_the_library() -> dict:
    return {
        "goal": "en Steam andá a la biblioteca y buscá Cuphead", "reached": False,
        "stoppedBy": limits.PLACE_SEARCH_STOP,
        "steps": [{"step": 1, "operation": "app.open", "ok": True, "appId": "Steam", "place": "library",
                   "placeOpened": True, "subgoal": 0}],
        "subgoals": [
            {"goal": "ir a biblioteca", "application": "Steam", "reached": True, "arrivedAs": "Biblioteca",
             "acted": True},
            {"goal": "buscar Cuphead", "application": "Steam", "reached": False},
        ],
    }


def test_the_limit_is_said_short_with_the_store_offered() -> None:
    observed = _stopped_in_the_library()
    assert floor_first(observed, english=False, succeeded=False) == (
        "Llegué a «Biblioteca», pero no puedo hacer lo que sigue: el buscador de la biblioteca no me deja escribir; "
        "si querés, lo busco en la tienda.")
    assert floor_first(observed, english=True, succeeded=False) == (
        "I got to «Biblioteca», but I can't do the rest: the library's search box doesn't let me type; if you want, "
        "I'll search the store for it.")
