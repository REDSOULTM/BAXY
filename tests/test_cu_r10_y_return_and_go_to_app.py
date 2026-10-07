"""Revisión 2026-10-07 (r10-y) del lector de misiones, tras dos fallos de la tanda ciega:

- «abrí la calculadora, poné el modo programador y después volvé a estándar»: «volvé a X» no era cláusula, el modo
  se tragaba «y después volvé a estándar» y la misión entera fue al modelo (55 s, sin pasos). Volver a un modo o a un
  lugar es cambiar a él; una cadena de modos son sub-metas, cada una con su comprobación.
- «go to Settings, then Bluetooth & devices»: ir a una aplicación nombrada entera, como primera cláusula, es abrirla;
  «then Bluetooth & devices» es el lugar con el verbo dicho una vez. Antes quedaba sin leer y el plan pedía
  app.open «Settings» (ambiguo).
"""

from __future__ import annotations

from baxy_mind import computer_use
from baxy_mind.semantic import missions

APPS = ("Steam", "Discord", "Calculadora", "Configuración", "Explorador de archivos", "Paint")


def _mission(said: str) -> missions.MissionRequest:
    mission = missions.mission_request(said, APPS)
    assert mission is not None, said
    return mission


def test_a_chain_of_modes_is_one_sub_goal_per_mode_each_with_its_check() -> None:
    mission = _mission("abrí la calculadora, poné el modo programador y después volvé a estándar")
    assert [(step.application, step.goal) for step in mission.steps] == [
        ("Calculadora", "activar modo programador"),
        ("Calculadora", "ir a estandar"),
    ]
    first, second = (step.success_check.split("|") for step in mission.steps)
    assert "control:programador:selected" in first and not any("estandar" in term for term in first)
    assert {"control:estandar:selected", "header:standard"} <= set(second)
    assert not any("programador" in term for term in second)


def test_going_back_reads_as_changing_in_either_language() -> None:
    back = _mission("en la calculadora pasá a científica y después regresá al modo estándar")
    assert [step.goal for step in back.steps] == ["ir a cientifica", "ir a estandar"]
    english = _mission("in Calculator switch to scientific, then go back to standard")
    assert [step.goal for step in english.steps] == ["ir a scientific", "ir a standard"]
    # A place goes back the same way.
    assert _mission("en Steam volvé a la biblioteca").goal == "ir a biblioteca"
    assert _mission("en Discord volvé a general").goal == "ir a general"


def test_saying_an_order_again_is_no_going_back_to_a_place() -> None:
    # «volvé a abrir la biblioteca» repeats the order: never a place called «abrir la biblioteca».
    again = missions.mission_request("en Steam volvé a abrir la biblioteca", APPS)
    assert again is None or "abrir" not in again.goal.split(" a ", 1)[-1]
    assert missions.read_clause("volve a intentarlo despues") is None or not missions.read_clause(
        "volve a intentarlo despues")[0].startswith("ir a")
    # The single mode change keeps its reading.
    assert _mission("abrí la calculadora y cambiá a científica").goal == "ir a cientifica"


def test_going_to_an_application_first_opens_it_and_the_next_place_is_its_own() -> None:
    english = _mission("go to Settings, then Bluetooth & devices")
    assert english.application == "Configuración" and english.goal == "ir a bluetooth & devices"
    assert "control:bluetooth y dispositivos:current" in english.success_check.split("|")
    spanish = _mission("andá a Configuración y después a Bluetooth y dispositivos")
    assert spanish.application == "Configuración" and spanish.goal == "ir a bluetooth y dispositivos"
    chain = _mission("andá a Configuración, después a Sistema y después a Pantalla")
    assert [step.goal for step in chain.steps] == ["ir a sistema", "ir a pantalla"]


def test_going_to_an_application_alone_or_a_place_named_like_none_stays_as_before() -> None:
    assert missions.mission_request("go to Settings", APPS) is None
    # A place inside the application in play is never taken for another application.
    inside = _mission("en Steam andá a la biblioteca y después a la tienda")
    assert [(step.application, step.goal) for step in inside.steps] == [("Steam", "ir a biblioteca"), ("Steam", "ir a tienda")]


def test_a_name_with_ampersand_is_clicked_by_its_localized_navigation_item_never_a_bluetooth_switch() -> None:
    # Settings' home lists «Bluetooth y dispositivos» as the navigation item and as a card, with a «Bluetooth» switch.
    view = {
        "window": {"title": "Configuración", "process": "SystemSettings"},
        "controls": [
            {"i": 3, "kind": "ListItem", "name": "Bluetooth y dispositivos", "state": "", "zone": "L"},
            {"i": 12, "kind": "Button", "name": "Bluetooth y dispositivos", "zone": "C"},
            {"i": 13, "kind": "Button", "name": "Bluetooth", "state": "on", "zone": "C"},
        ],
        "text": {"C": ["Bluetooth y dispositivos", "Bluetooth"]},
    }
    step = computer_use.deterministic_step(goal="ir a Bluetooth & devices", view=view, history=[])
    assert step is not None and step["arguments"] == {"label": "Bluetooth y dispositivos", "index": 3}
