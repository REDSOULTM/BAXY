"""Revisión de la ronda 20b (palanca 7, hallazgo 1): un toggle cuyo efecto quedó incierto (la casilla cambió y la marca
del hermano no apareció: visible_toggle_uncorroborated) es un acto que pudo actuar; la casilla mostrada en «on» después
no está «ya elegida desde antes». Gemela de ComputerUseSuccessCheck.AlreadyChosen."""

from __future__ import annotations

from baxy_mind import cu_view
from baxy_mind import cu_rules
from baxy_mind import cu_evidence
from baxy_mind import cu_validate

_MUTE = "Silenciar 'Audio del escritorio'"
_GOAL = "silenciar el audio del escritorio"


def _view(chosen_before: dict[str, list[str]]) -> dict:
    return {
        "controls": [
            {"kind": "CheckBox", "name": _MUTE, "state": "on"},
            {"kind": "Slider", "name": "Deslizador de volumen para 'Audio del escritorio':"},
        ],
        "chosenBeforeClick": chosen_before,
    }


def test_an_uncertain_toggle_on_the_control_is_no_already_chosen() -> None:
    history = [
        {"step": 1, "operation": "input.visible.click", "label": "Mezclador", "ok": True, "surfaceChanged": True},
        {
            "step": 2, "operation": "input.visible.click", "label": _MUTE, "ok": False, "effectUncertain": True,
            "error": "visible_toggle_uncorroborated",
        },
    ]

    assert cu_evidence._mission_proof(_view({"1": [], "2": []}), history, _GOAL) is None
    assert cu_evidence._proved_done(_view({"1": [], "2": []}), history, _GOAL, "x") is None


def test_contracase_a_box_on_before_any_act_on_it_is_already_chosen() -> None:
    history = [{"step": 1, "operation": "input.visible.click", "label": "Mezclador", "ok": True, "surfaceChanged": True}]

    assert cu_evidence._mission_proof(_view({"1": []}), history, _GOAL) == (_MUTE, True)


def test_contracase_a_refused_click_that_pressed_nothing_keeps_it_already_chosen() -> None:
    history = [
        {"step": 1, "operation": "input.visible.click", "label": "Mezclador", "ok": True, "surfaceChanged": True},
        {"step": 2, "operation": "input.visible.click", "label": _MUTE, "ok": False, "error": "visible_button_ambiguous"},
    ]

    assert cu_evidence._mission_proof(_view({"1": [], "2": []}), history, _GOAL) == (_MUTE, True)


def test_contracase_a_verified_click_that_chose_it_is_the_act() -> None:
    # A name that does not end in a quote mark (chosen_by_act trims the citation's marks).
    name = "Silenciar audio del escritorio"
    view = {"controls": [{"kind": "CheckBox", "name": name, "state": "on"}], "chosenBeforeClick": {"1": []}}
    history = [{"step": 1, "operation": "input.visible.click", "label": name, "ok": True, "toggled": True}]

    assert cu_evidence._mission_proof(view, history, _GOAL) == (name, False)


# Revisión 2 de la ronda 20b (B2): una entrada del menú clásico que conmuta un ajuste (su lectura estática la muestra
# marcada o de opción) llega como «checkable», un hecho neutro sin su estado de ahora, y el guard de objetivos de lugar
# la frena como a cualquier interruptor: el patrón de «Invertir colores» pulsado buscando «Colores».
_STATUS_BAR = "Ver › Barra de estado"
_REFRESH = "Ver › Actualizar"


def _menu_view(state: str) -> dict:
    return {
        "window": {"title": "Documento - Editor", "process": "editor"},
        "controls": [
            {"i": 0, "kind": "Button", "name": "Guardar", "state": ""},
            {"i": 1, "kind": "MenuItem", "name": _STATUS_BAR, "nameSource": "menu", "id": "hmenu.27", "state": state},
            {"i": 2, "kind": "MenuItem", "name": _REFRESH, "nameSource": "menu", "id": "hmenu.28", "state": ""},
        ],
        "text": {},
    }


def _menu_click(view: dict, label: str, index: int) -> dict:
    raw = {"act": "click", "label": label, "i": index, "why": "probar"}
    return cu_validate.validate_decision(raw, view=view, last_failed=None, application_names=[], goal="ir a Opciones", history=[])


def test_a_checkable_menu_entry_is_no_way_to_a_place() -> None:
    step = _menu_click(_menu_view("checkable"), _STATUS_BAR, 1)

    assert step["operation"] == "none" and step.get("code") == "changes_a_setting"
    assert cu_view._is_switch(_menu_view("checkable")["controls"][1])


def test_contracase_a_plain_menu_command_still_passes() -> None:
    step = _menu_click(_menu_view("checkable"), _REFRESH, 2)

    assert step["operation"] == "input.visible.click"
    assert not cu_view._is_switch(_menu_view("checkable")["controls"][2])


# Revisión 3 de la ronda 20b (B-B): «checkable» no dice el estado de ahora. Para «activar» o «desactivar» la entrada del
# menú cerrado no se pulsa a ciegas (lo apagaría si ya estaba encendido): decide el modelo, que abre el menú; activar y
# desactivar nunca dan el mismo clic. Con el menú abierto el ítem dibujado trae su estado y la rutina actúa sobre él.
def _set(goal: str, view: dict) -> dict | None:
    return cu_rules.deterministic_step(goal=goal, view=view, history=[])


def test_on_and_off_never_press_a_checkable_entry_of_unknown_state() -> None:
    view = _menu_view("checkable")
    on, off = _set("activar barra de estado", view), _set("desactivar barra de estado", view)

    assert on is None and off is None
    for state in ("checkable", "on", "off", "checkable on", "checkable off"):
        shown = _menu_view(state)
        pair = _set("activar barra de estado", shown), _set("desactivar barra de estado", shown)
        assert not (pair[0] is not None and pair[0] == pair[1]), state
    for goal in ("activar barra de estado", "desactivar barra de estado"):
        step = cu_validate.validate_decision(
            {"act": "click", "label": _STATUS_BAR, "i": 1, "why": "probar"},
            view=view, last_failed=None, application_names=[], goal=goal, history=[],
        )
        assert step["operation"] == "none" and step.get("code") == "changes_a_setting"


def test_contracase_the_opened_menu_item_with_its_state_is_set() -> None:
    view = _menu_view("checkable")
    view["controls"].append({"i": 3, "kind": "MenuItem", "name": "Barra de estado", "state": "on"})

    assert _set("activar barra de estado", view) is None
    off = _set("desactivar barra de estado", view)
    assert off is not None and off["operation"] == "input.visible.click" and off["arguments"]["index"] == 3


def test_contracase_a_click_goal_on_the_entry_still_presses_it() -> None:
    step = cu_validate.validate_decision(
        {"act": "click", "label": _STATUS_BAR, "i": 1, "why": "probar"}, view=_menu_view("checkable"), last_failed=None,
        application_names=[], goal="hacer clic en barra de estado", history=[],
    )

    assert step["operation"] == "input.visible.click"


# Revisión 3 de la ronda 20b (B-A): una entrada del menú cerrado no está en pantalla; «mostrar opciones» desplaza la
# lista aunque «Herramientas › Opciones...» esté listada. Contracaso: el ítem dibujado ya no pide desplazar.
def test_a_closed_menu_entry_is_not_on_screen_for_a_reveal() -> None:
    view = _menu_view("")
    view["controls"].append({"i": 3, "kind": "MenuItem", "name": "Herramientas › Opciones...", "nameSource": "menu",
                             "id": "hmenu.30", "state": ""})
    step = _set("mostrar opciones", view)

    assert step is not None and step["operation"] == "input.scroll"
    view["controls"].append({"i": 4, "kind": "ListItem", "name": "Opciones", "state": ""})
    assert _set("mostrar opciones", view) is None
