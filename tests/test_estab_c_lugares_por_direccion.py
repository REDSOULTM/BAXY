"""Estabilización, encargo C: ir a un lugar de una aplicación por la dirección que declaran sus datos.

Banco r30: x10 «biblioteca → tienda» falló porque el clic por OCR en «TIENDA» no cambió la página de Steam; g1 «buscá
Cuphead» 0/3 porque Steam no deja escribir en su buscador; u1 y y8 («Tu biblioteca» de Spotify) inestables; «abrí la
página de Cuphead en Steam» lanzaba el juego. Los lugares con dirección viven en data/app_places.v1.json (los lee también
Baxy.Kernel/ApplicationPlaces, que compone la dirección; sus ejemplos atan a los dos lectores); la mente los abre con
app.open «place» como primer paso del sub-objetivo y la comprobación de la ventana decide si llegó.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from baxy_mind import computer_use as cu
from baxy_mind import cu_history
from baxy_mind import cu_model_calls
from baxy_mind import cu_projection
from baxy_mind import cu_finals
from baxy_mind.semantic import app_places, missions, patterns

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / "src" / "baxy_mind" / "data" / "app_places.v1.json").read_text(encoding="utf-8"))
NAMES = ("Steam", "Spotify", "Paint", "Bloc de notas", "Configuración", "Discord")
GAMES = (("steam", "252950", "Rocket League"), ("steam", "420", "Half-Life 2: Episode Two"))
OPERATIONS = tuple(sorted(set(re.findall(
    r'Descriptor\(\s*"([a-z][a-z0-9._]+)"',
    (ROOT / "src" / "Baxy.Kernel" / "Operations" / "ProductCatalog.cs").read_text(encoding="utf-8"),
))))


def _decide(goal: str, application: str | None, view: dict, history: list[dict] | None = None) -> dict:
    return cu._decide_step(
        None, objective=f"en {application} {goal}", goal=goal, application=application, success_check=None, view=view,
        history=history or [], budget_left=8, application_names=NAMES, subgoal=0, subgoal_count=1,
        translator=cu_model_calls.LabelTranslator(None, enabled=False), game_catalog=GAMES,
    )


def _behind() -> dict:
    # The person's own editor in front; the application asked for is not.
    return {"window": {"title": "notas.txt - Bloc de notas", "process": "notepad"}, "controls": []}


# ------------------------------------------------------------------------------------------ el dato y su lector


@pytest.mark.parametrize("example", DATA["examples"], ids=lambda example: f"{example['application']}:{example['goal']}")
def test_every_example_of_the_data_is_read_as_its_place(example: dict) -> None:
    expected = {"place": example["place"]}
    if "value" in example:
        expected["placeValue"] = example["value"]
    assert app_places.place_of(example["application"], example["goal"], GAMES) == expected
    # The address of the example has a scheme its application declares (the kernel's own test composes it).
    scheme = example["address"].split(":", 1)[0]
    assert scheme in DATA["applications"][example["application"]]["schemes"]


def test_every_address_of_the_data_opens_with_a_scheme_its_application_declares() -> None:
    for name, application in DATA["applications"].items():
        for place, entry in application["places"].items():
            if "address" not in entry:
                continue  # a place named without an address of its own (measured: no protocol reaches it)
            assert entry["address"].split(":", 1)[0] in application["schemes"], (name, place)
            assert len(re.findall(r"\{[a-z]+\}", entry["address"])) <= 1, (name, place)


@pytest.mark.parametrize(("application", "goal"), [
    ("Steam", "ir a configuracion"),  # a place of Steam with no address: computer use as before
    ("Paint", "ir a biblioteca"),  # an application with no places in the data
    ("Steam", "ir a la pestana biblioteca"),  # a browser's tab is no place of an application
    ("Steam", "hacer clic en biblioteca"),  # a click is not a place gone to
    ("Steam", "ir a pagina de cuphead"),  # a game not installed: no identifier, no address
    ("Spotify", "ir a tu biblioteca"),  # named in the data without an address (spotify:collection opens «Me gusta»)
    (None, "ir a biblioteca"),
])
def test_a_place_the_data_do_not_declare_has_no_address(application: str | None, goal: str) -> None:
    assert app_places.place_of(application, goal, GAMES) is None


# ------------------------------------------------------------------------------------------ el paso de la mente


def test_a_declared_place_is_opened_with_the_application_as_the_first_step() -> None:
    decision = _decide("ir a biblioteca", "Steam", _behind())
    assert decision["operation"] == "app.open"
    assert decision["arguments"] == {"appId": "Steam", "place": "library"}


def test_a_search_in_an_application_with_a_search_address_is_opened_by_it() -> None:
    decision = _decide("buscar Cuphead", "Steam", _behind())
    assert decision["arguments"] == {"appId": "Steam", "place": "results", "placeValue": "Cuphead"}


def test_the_place_is_opened_once_per_sub_goal_and_the_mission_goes_on_as_before() -> None:
    opened = [{"step": 1, "operation": "app.open", "ok": True, "appId": "Steam", "place": "library", "placeOpened": True}]
    decision = _decide("ir a biblioteca", "Steam", _behind(), opened)
    assert not (decision["operation"] == "app.open" and decision.get("arguments", {}).get("place"))


def test_contracase_a_place_without_address_opens_the_application_alone() -> None:
    decision = _decide("ir a configuracion", "Steam", _behind())
    assert decision["operation"] == "app.open"
    assert "place" not in decision["arguments"]


# ------------------------------------------------------------------------------------------ la lectura del pedido


def test_the_search_sub_goal_is_also_proved_by_the_place_opened_and_the_text_on_the_window() -> None:
    mission = missions.mission_request("abrí Steam, andá a la biblioteca y buscá Cuphead", NAMES)
    assert mission is not None and len(mission.steps) == 2
    assert mission.steps[0].success_check is not None and "stepDone:app.open" not in mission.steps[0].success_check
    # Review H3: the request named the library, which has no search address: the search is not sent to the store.
    assert "opened:" not in mission.steps[1].success_check
    assert app_places.place_of("Steam", mission.steps[1].goal, GAMES, said=mission_text_g1()) is None


def mission_text_g1() -> str:
    return "abrí Steam, andá a la biblioteca y buscá Cuphead"


@pytest.mark.parametrize(("application", "said", "goal"), [
    ("Steam", "en Steam buscá Rocket League en mi biblioteca", "buscar Rocket League en mi biblioteca"),
    ("Steam", "en Steam andá a la biblioteca y buscá Rocket League", "buscar Rocket League"),
    ("Spotify", "en Spotify, andá a tu biblioteca y buscá Los Bunkers", "buscar Los Bunkers"),
])
def test_review_h3_a_search_where_another_place_is_named_has_no_address(application: str, said: str, goal: str) -> None:
    assert app_places.place_of(application, goal, GAMES, said=said) is None
    assert app_places.arrival_term(application, goal, said) is None


def test_review_h3_a_search_said_in_the_store_or_alone_is_the_store_search() -> None:
    for said in ("en Steam buscá Cuphead", "en la tienda de Steam buscá Cuphead"):
        assert app_places.place_of("Steam", "buscar Cuphead", GAMES, said=said) == {
            "place": "results", "placeValue": "Cuphead"}
    mission = missions.mission_request("en Steam buscá Cuphead", NAMES)
    assert mission is not None and mission.success_check.startswith("stepDone:app.open&opened:results=cuphead|")


def test_a_search_in_an_application_without_places_keeps_its_check() -> None:
    mission = missions.mission_request("en Paint buscá lápiz", NAMES)
    assert mission is None or "opened:" not in (mission.success_check or "")


def test_the_page_of_an_installed_game_in_steam_is_a_mission_not_a_launch() -> None:
    intent = patterns.resolve_explicit_effects("abrí la página de Rocket League en Steam", OPERATIONS, NAMES, GAMES)
    assert intent is not None and intent.operations == ("mission.computer.use",)
    mission = missions.mission_request("abrí la página de Rocket League en Steam", NAMES)
    assert mission is not None and mission.success_check.startswith("stepDone:app.open&opened:game=rocket league|")
    assert app_places.place_of("Steam", mission.goal, GAMES) == {"place": "game", "placeValue": "252950"}


def test_contracase_launching_an_installed_game_still_launches_it() -> None:
    intent = patterns.resolve_explicit_effects("lanzá Rocket League", OPERATIONS, NAMES, GAMES)
    assert intent is not None and intent.operations == ("game.launch",)


def test_contracase_searching_a_band_in_spotify_said_last_still_plays_it() -> None:
    # The encargo's counter-case: «buscá X en Spotify» keeps its reading (media.play.query, it plays); only the order
    # said inside the application («en Spotify buscá X») is a search by the place's address. Reported, not changed.
    intent = patterns.resolve_explicit_effects("buscá Los Bunkers en Spotify", OPERATIONS, NAMES, GAMES)
    assert intent is not None and intent.operations == ("media.play.query",)
    inside = missions.mission_request("en Spotify buscá Los Bunkers", NAMES)
    assert inside is not None and inside.success_check.startswith("stepDone:app.open&opened:results=")


# ------------------------------------------------------------------------------------------ lo que se dice al final


def test_an_opening_that_opened_a_place_is_an_act_never_already_there() -> None:
    opening = {"step": 1, "operation": "app.open", "ok": True, "alreadyRunning": True, "place": "library",
               "placeOpened": True}
    assert cu_history._may_have_acted(opening)
    assert not cu_history._may_have_acted({**opening, "placeOpened": False, "place": None})
    observed = {"reached": True, "steps": [opening], "satisfiedBy": "mark:biblioteca"}
    said = cu_finals._place_said(observed, english=False)
    assert said.startswith("Listo"), said


# ------------------------------------------------------------------------------------------ banco f2c (lug-2, x10)


def _opening(place: str, value: str | None = None, subgoal: int | None = None) -> dict:
    step = {"step": 1, "operation": "app.open", "ok": True, "appId": "Steam", "alreadyRunning": True,
            "place": place, "placeOpened": True}
    if value is not None:
        step["placeValue"] = value
    if subgoal is not None:
        step["subgoal"] = subgoal
    return step


def test_f2c_a_search_by_the_address_is_told_by_the_floor_with_its_query() -> None:
    observed = {"reached": True, "goal": "buscar Cuphead", "application": "Steam", "window": {"title": "Steam"},
                "satisfiedBy": "stepDone:app.open&opened:results=cuphead", "steps": [_opening("results", "Cuphead")]}
    said = cu_finals.floor_first(observed, english=False, succeeded=True)
    assert said == "Listo, busqué «Cuphead» en «Steam».", said
    # The step is told as what it did, never as «trajo la aplicación al frente».
    assert cu_projection.describe_step(_opening("results", "Cuphead"), "es") == "buscó «Cuphead» por su dirección"


def test_f2c_places_opened_by_address_are_told_by_the_floor_with_the_persons_words() -> None:
    observed = {
        "reached": True, "goal": "ir a biblioteca; luego ir a tienda", "application": "Steam", "window": {"title": "Steam"},
        "steps": [_opening("library", subgoal=0), _opening("store", subgoal=1)],
        "subgoals": [
            {"goal": "ir a biblioteca", "application": "Steam", "reached": True, "acted": True, "satisfiedBy": "mark:biblioteca"},
            {"goal": "ir a tienda", "application": "Steam", "reached": True, "acted": True, "satisfiedBy": "page:store"},
        ],
        "satisfiedBy": "page:store",
    }
    said = cu_finals.floor_first(observed, english=False, succeeded=True)
    assert said.startswith("Listo") and "biblioteca" in said and "tienda" in said, said


# ------------------------------------------------------------------------------------------ banco c2 (lug-3, y10)


def test_c2_the_searched_name_keeps_the_article_the_person_capitalized() -> None:
    said = "en Spotify buscá Los Bunkers"
    mission = missions.mission_request(said, NAMES)
    assert mission is not None
    place = app_places.place_of("Spotify", mission.goal, GAMES, said=said)
    assert place == {"place": "results", "placeValue": "Los Bunkers"}
    observed = {"reached": True, "goal": mission.goal, "application": "Spotify", "window": {"title": "Spotify"},
                "satisfiedBy": "stepDone:app.open&opened:results=bunkers",
                "steps": [{**_opening("results", "Los Bunkers"), "appId": "Spotify"}]}
    assert cu_finals.floor_first(observed, english=False, succeeded=True) == "Listo, busqué «Los Bunkers» en «Spotify»."
    # Lower case («buscá los mejores juegos») is no name: the reading as before.
    assert app_places.place_of("Spotify", "buscar mejores juegos", GAMES, said="en Spotify buscá los mejores juegos") == {
        "place": "results", "placeValue": "mejores juegos"}


def test_c2_places_opened_by_address_are_told_in_the_persons_words_and_language() -> None:
    observed = {
        "reached": True, "goal": "ir a store; luego ir a library", "application": "Steam", "window": {"title": "Steam"},
        "steps": [_opening("store", subgoal=0), _opening("library", subgoal=1)],
        "subgoals": [
            {"goal": "ir a store", "application": "Steam", "reached": True, "acted": True, "satisfiedBy": "page:store"},
            {"goal": "ir a library", "application": "Steam", "reached": True, "acted": True,
             "satisfiedBy": "mark:biblioteca", "arrivedAs": "BIBLIOTECA"},
        ],
        "satisfiedBy": "mark:biblioteca",
    }
    said = cu_finals.floor_first(observed, english=True, succeeded=True)
    assert "library" in said and "store" in said and "iblioteca" not in said, said
