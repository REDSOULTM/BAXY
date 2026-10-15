"""Encargo V (estabilización, banco e2 c7): «en Discord andá al canal Cotele y después en Steam andá a la tienda» en modo
Normal entró al canal de voz sin preguntar. El primer clic de la cadena fue la etiqueta «cotele» (la regla, sin el
control en la vista); RiskPolicy juzgó «cotele» y el worker de UIA pulsó «Cotele!!!😎, Canal de voz, Choche», un ítem
que contiene la palabra. Ahora el worker no pulsa lo que pide más que su etiqueta y responde su nombre
(``visible_control_needs_confirmation``); el paso siguiente de la mente lo nombra entero, así RiskPolicy pregunta ligado a
esa invocación (y bypass lo pulsa). Sólo un acto que sale al mundo y que el objetivo nombra; lo demás, al modelo."""

from __future__ import annotations

from baxy_mind import cu_rules
from baxy_mind.semantic import account_acts

WINDOW = {"title": "@Ron92 - Discord", "process": "Discord", "focused": None}
CHANNEL = "Cotele!!!😎, Canal de voz, Choche"


def _view(*controls: dict) -> dict:
    return {"window": WINDOW, "controls": list(controls), "text": {}}


def _refused(label: str, name: str) -> dict:
    return {"step": 1, "operation": "input.visible.click", "ok": False, "label": label, "name": name,
            "error": cu_rules.NEEDS_CONFIRMATION_REFUSAL}


def test_the_chains_first_link_names_the_voice_channel_the_worker_left_unpressed() -> None:
    step = cu_rules.deterministic_step(
        goal="ir a cotele", view=_view({"i": 0, "kind": "ComboBox", "name": "Buscar", "state": "expanded"}),
        history=[_refused("cotele", CHANNEL)], application="Discord",
        objective="en Discord andá al canal Cotele y después en Steam andá a la tienda",
    )
    assert step is not None and step["operation"] == "input.visible.click"
    assert step["arguments"] == {"label": CHANNEL}


def test_a_channel_on_the_view_is_named_by_its_index_too() -> None:
    view = _view({"i": 60, "kind": "ListItem", "name": CHANNEL, "state": ""})
    step = cu_rules.deterministic_step(
        goal="ir a cotele", view=view, history=[_refused("cotele", CHANNEL)], objective="en Discord andá al canal Cotele",
    )
    assert step is not None and step["arguments"] == {"label": CHANNEL, "index": 60}


# Contracase: an act that goes out to the world and that the goal does not name is never pressed by a rule.
def test_a_world_act_the_goal_does_not_name_is_not_pressed_by_a_rule() -> None:
    step = cu_rules.deterministic_step(
        goal="ir a ajustes", view=_view(), history=[_refused("Transmisión", "Iniciar Transmisión")],
    )
    assert step is None or step.get("arguments", {}).get("label") != "Iniciar Transmisión"


# Contracase: a removal is the model's to decide, never a rule's (bypass would press it straight).
def test_a_removal_is_not_pressed_by_a_rule() -> None:
    step = cu_rules.deterministic_step(
        goal="ir a pruebas", view=_view(), history=[_refused("pruebas", "Eliminar pruebas")],
    )
    assert step is None or step.get("arguments", {}).get("label") != "Eliminar pruebas"


# Contracase: a text channel is no world act; the worker never refuses it and no rule names it for a confirmation.
def test_a_text_channel_is_no_world_act() -> None:
    assert account_acts.world_act("general (canal de texto)") is None
    assert account_acts.world_act(CHANNEL) == "call"
