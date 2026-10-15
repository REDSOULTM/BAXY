"""Goal v3 punto 0, arreglo 3 (ráfaga compuesta): cuando el paso determinista de la mente ya sabe la secuencia entera
de ir a un lugar que no está en pantalla (abrir la búsqueda o el desplegable, escribir el destino, elegir el resultado
que lo nombra), el clic en el control que ABRE la búsqueda la lleva entera (``search``) y el shell la ejecuta en una sola
ráfaga. Un campo que ya es la búsqueda sigue paso a paso; «buscar X» (enviar la búsqueda) no elige resultado; un
resultado que llega a una persona se pide con ese resultado nombrado (``choose``) para que RiskPolicy confirme; una
ráfaga que paró por otra causa no deja una tecla ni un texto sobre lo que quedó a medias."""

from __future__ import annotations

from baxy_mind import cu_lookup
from baxy_mind import cu_rules

WINDOW = {"title": "Amigos - Discord", "process": "Discord", "focused": None}


def _view(*controls: dict) -> dict:
    return {"window": WINDOW, "controls": list(controls), "text": {}}


def test_a_search_opener_carries_the_whole_sequence() -> None:
    view = _view({"i": 0, "kind": "Button", "name": "Buscar o iniciar una conversación", "state": ""})
    step = cu_rules.deterministic_step(goal="ir a Cotele", view=view, history=[])
    assert step["operation"] == "input.visible.click"
    assert step["arguments"] == {"label": "Buscar o iniciar una conversación", "index": 0, "search": "Cotele"}


def test_a_drop_down_is_an_opener_too() -> None:
    view = _view({"i": 3, "kind": "ComboBox", "name": "Buscar", "state": "collapsed"})
    step = cu_rules.deterministic_step(goal="ir a Cotele", view=view, history=[])
    assert step["arguments"].get("search") == "Cotele"


# Contracase: a field that is already the search box is clicked alone; its text reaches it behind the person's window.
def test_a_search_field_goes_step_by_step_as_before() -> None:
    view = _view({"i": 0, "kind": "Edit", "name": "Buscar", "state": ""})
    step = cu_rules.deterministic_step(goal="ir a Cotele", view=view, history=[])
    assert step["arguments"] == {"label": "Buscar", "index": 0}


# Contracase: «buscar X» submits the search (Enter); it never chooses a result in a burst.
def test_a_search_goal_never_chooses_a_result_in_a_burst() -> None:
    view = _view({"i": 0, "kind": "Button", "name": "Buscar", "state": ""})
    step = cu_rules.deterministic_step(goal="buscar Hades", view=view, history=[])
    assert step["operation"] == "input.visible.click" and "search" not in step["arguments"]


def test_a_result_that_needs_the_persons_yes_is_asked_for_with_that_result_named() -> None:
    view = _view({"i": 0, "kind": "Button", "name": "Buscar o iniciar una conversación", "state": ""})
    history = [
        {"step": 1, "operation": "input.visible.click", "ok": True, "label": "Buscar o iniciar una conversación",
         "index": 0, "search": "Cotele", "searchBurst": True},
        {"step": 2, "operation": "input.text.type", "ok": True, "text": "Cotele", "searchBurst": True},
        {"step": 3, "operation": "input.visible.click", "ok": False, "label": "Cotele (canal de voz)",
         "error": cu_lookup.SEARCH_RESULT_NEEDS_CONFIRMATION, "searchBurst": True},
    ]
    step = cu_rules.deterministic_step(goal="ir a Cotele", view=view, history=history)
    assert step["arguments"] == {
        "label": "Buscar o iniciar una conversación", "index": 0, "search": "Cotele", "choose": "Cotele (canal de voz)",
    }


# A burst that stopped for another cause (the result was not there): its opener is not tried again and nothing is
# typed nor pressed on what it left half done; the next way of the routine is tried.
def test_a_burst_that_found_nothing_goes_on_with_the_next_way() -> None:
    view = _view({"i": 0, "kind": "Button", "name": "Buscar o iniciar una conversación", "state": ""})
    history = [
        {"step": 1, "operation": "input.visible.click", "ok": True, "label": "Buscar o iniciar una conversación",
         "index": 0, "search": "Cotele", "searchBurst": True},
        {"step": 2, "operation": "input.text.type", "ok": True, "text": "Cotele", "searchBurst": True},
        {"step": 3, "operation": "input.visible.click", "ok": False, "label": "Cotele",
         "error": "visible_search_result_not_found", "searchBurst": True},
    ]
    step = cu_rules.deterministic_step(goal="ir a Cotele", view=view, history=history)
    assert step is None or step["operation"] != "input.text.type"
    assert step is None or "search" not in step.get("arguments", {})
    assert step is None or step.get("arguments", {}).get("key") != "escape"
