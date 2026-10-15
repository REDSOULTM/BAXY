"""Ronda 20b, palanca 8 (pasada r18): the window's frame is no act.

v3-51: the modal dialog «Añadir escena» of a Qt application was read with its title bar and close button alone, and the
model was offered «TitleBar «Añadir escena»» as a control (it pressed it as the dialog's content). v3-62: the system
menu chain of a packaged application, which the provider now marks ``systemMenu`` by its place under the title bar.
"""

from __future__ import annotations

from baxy_mind import cu_step_prompt

_BAR = {"x": 100, "y": 100, "w": 600, "h": 30}


def _dialog(*content: dict) -> dict:
    return {
        "window": {"title": "Añadir escena", "process": "obs64"},
        "controls": [
            {"i": 0, "kind": "Button", "name": "Cerrar", "rect": {"x": 660, "y": 102, "w": 36, "h": 26}},
            {"i": 1, "kind": "TitleBar", "name": "Añadir escena", "rect": _BAR},
            *content,
        ],
    }


def _listed(view: dict, goal: str) -> str:
    return cu_step_prompt.compact_view_text(view, goal=goal)


def test_v3_51_the_title_bar_and_the_frame_close_are_not_offered() -> None:
    shown = _listed(_dialog(), "agrega una escena nueva que se llame Pruebas")
    assert "TitleBar" not in shown
    assert "«Cerrar»" not in shown


def test_the_dialogs_content_read_under_its_owner_is_offered() -> None:
    view = _dialog(
        {"i": 2, "kind": "Edit", "name": "Nombre de la escena", "rect": {"x": 150, "y": 200, "w": 400, "h": 24}},
        {"i": 3, "kind": "Button", "name": "Aceptar", "rect": {"x": 450, "y": 450, "w": 80, "h": 24}},
    )
    shown = _listed(view, "agrega una escena nueva que se llame Pruebas")
    assert "Nombre de la escena" in shown and "Aceptar" in shown
    assert "TitleBar" not in shown


def test_a_goal_that_closes_the_window_still_sees_its_close_button() -> None:
    # Contracase: closing, moving or restoring the window is done with its frame.
    assert "«Cerrar»" in _listed(_dialog(), "cierra esta ventana")


def test_a_close_button_of_the_content_is_not_the_frame() -> None:
    # Contracase: a «Cerrar» drawn below the title bar (a dialog's own button) stays offered.
    view = _dialog({"i": 2, "kind": "Button", "name": "Cerrar", "rect": {"x": 550, "y": 450, "w": 80, "h": 24}})
    view["controls"] = [control for control in view["controls"] if control["i"] != 0]
    assert "«Cerrar»" in _listed(view, "agrega una escena nueva")


def test_v3_62_a_marked_system_menu_is_hidden_unless_the_goal_asks_for_it() -> None:
    menu = {"i": 2, "kind": "MenuItem", "name": "Opciones", "systemMenu": True, "rect": {"x": 100, "y": 100, "w": 28, "h": 28}}
    content = {"i": 3, "kind": "ListItem", "name": "Firewall y protección de red", "rect": {"x": 100, "y": 300, "w": 300, "h": 40}}
    view = _dialog(menu, content)
    assert "Opciones" not in _listed(view, "ir a firewall y protección de red")
    assert "Opciones" in _listed(view, "mueve la ventana a la izquierda")
    # Contracase: an unmarked menu item of the content keeps being offered.
    unmarked = dict(menu, systemMenu=False, rect={"x": 100, "y": 200, "w": 60, "h": 24})
    assert "Opciones" in _listed(_dialog(unmarked, content), "ir a firewall y protección de red")


def _packaged_frame(*content: dict) -> dict:
    # The frame of a packaged application as the evidence of v3-62 read it (the C# test's PackagedFrame): its caption
    # buttons named after the window, drawn inside its title bar.
    return {
        "window": {"title": "Seguridad de Windows", "process": "SecHealthUI"},
        "controls": [
            {"i": 0, "kind": "Button", "name": "Minimizar Seguridad de Windows", "rect": {"x": 1580, "y": 0, "w": 46, "h": 32}},
            {"i": 1, "kind": "Button", "name": "Maximizar Seguridad de Windows", "rect": {"x": 1626, "y": 0, "w": 46, "h": 32}},
            {"i": 2, "kind": "Button", "name": "Cerrar Seguridad de Windows", "rect": {"x": 1672, "y": 0, "w": 46, "h": 32}},
            {"i": 3, "kind": "TitleBar", "name": "Seguridad de Windows", "rect": {"x": 0, "y": 0, "w": 1720, "h": 32}},
            *content,
        ],
    }


_FIREWALL = {"i": 4, "kind": "ListItem", "name": "Firewall y protección de red", "rect": {"x": 0, "y": 300, "w": 300, "h": 40}}


def test_v3_62_caption_buttons_named_after_the_window_are_not_offered() -> None:
    shown = _listed(_packaged_frame(_FIREWALL), "ir a firewall y protección de red")
    assert "Firewall y protección de red" in shown
    assert "Minimizar Seguridad de Windows" not in shown
    assert "Maximizar Seguridad de Windows" not in shown
    assert "Cerrar Seguridad de Windows" not in shown


def test_v3_62_a_goal_on_the_window_still_sees_them() -> None:
    # Contracase: minimizing or closing the window is done with its frame, whatever the button's name says after the verb.
    assert "Minimizar Seguridad de Windows" in _listed(_packaged_frame(_FIREWALL), "minimiza la ventana")
    assert "Cerrar Seguridad de Windows" in _listed(_packaged_frame(_FIREWALL), "cierra esta ventana")


def test_a_content_button_starting_with_a_caption_verb_stays_offered() -> None:
    # Contracase: «Cerrar todas las pestañas» below the title bar is the window's content, not its frame.
    tabs = {"i": 5, "kind": "Button", "name": "Cerrar todas las pestañas", "rect": {"x": 300, "y": 40, "w": 24, "h": 24}}
    assert "Cerrar todas las pestañas" in _listed(_packaged_frame(_FIREWALL, tabs), "ir a firewall y protección de red")


def test_v3_44_the_settings_page_windows_hands_devices_and_printers_to_is_that_place() -> None:
    # Objetivo 3: the Control Panel's «Dispositivos e impresoras» is opened by Windows 11 in Settings, on «Impresoras y
    # escáneres»; the place table names it so the arrival there is the place asked.
    from baxy_mind.semantic.missions import label_alternatives

    assert "impresoras y escaneres" in label_alternatives("devices and printers")
    assert "dispositivos e impresoras" in label_alternatives("devices and printers")
    assert "devices and printers" in label_alternatives("printers & scanners")
    # Contracase: the bare «impresoras» keeps only its own translation.
    assert label_alternatives("impresoras") == ("printers",)


# Review 3 of palanca 8 (B2): the close of a frame is hidden only where something else gets out of the window. A
# notice whose content is only written keeps its title-bar close for any wording of the goal, a dialog drawn over the
# window keeps its own, and a goal that leaves the window sees it; v3-62 (the main window with its content) and v3-51
# (the frame alone, its content not read yet) stay hidden.
def _notice(*content: dict) -> dict:
    return {
        "window": {"title": "Aviso", "process": "app"},
        "controls": [
            {"i": 0, "kind": "TitleBar", "name": "Aviso", "rect": {"x": 300, "y": 300, "w": 400, "h": 30}},
            {"i": 1, "kind": "Button", "name": "Cerrar", "rect": {"x": 660, "y": 302, "w": 36, "h": 26}},
            *content,
        ],
    }


_NOTICE_TEXT = {"i": 2, "kind": "Text", "name": "La operación terminó", "rect": {"x": 320, "y": 360, "w": 300, "h": 20}}


def test_a_notice_whose_content_is_only_written_keeps_its_close() -> None:
    for goal in ("sal del aviso", "descarta el aviso", "dismiss the notice", "sigue con la configuración"):
        assert "«Cerrar»" in _listed(_notice(_NOTICE_TEXT), goal), goal


def test_a_goal_that_leaves_the_window_sees_its_close() -> None:
    one = {"i": 2, "kind": "Button", "name": "Uno", "rect": {"x": 320, "y": 360, "w": 40, "h": 40}}
    assert "«Cerrar»" in _listed(_notice(one), "quit the calculator")
    # Contracase: a goal inside the window with a control of its own to act on does not see the frame's close.
    assert "«Cerrar»" not in _listed(_notice(one), "pulsa el uno")


def test_a_dialog_over_the_window_keeps_its_own_close() -> None:
    view = _packaged_frame(_FIREWALL, *_notice(
        {"i": 7, "kind": "Button", "name": "Aceptar", "rect": {"x": 600, "y": 400, "w": 80, "h": 24}})["controls"])
    for index, control in enumerate(view["controls"]):
        control["i"] = index
    shown = _listed(view, "ir a firewall y protección de red")
    assert "«Cerrar»" in shown, "the dialog's own close"
    assert "Cerrar Seguridad de Windows" not in shown and "Minimizar Seguridad de Windows" not in shown


def test_the_minimize_of_a_notice_stays_hidden() -> None:
    view = _notice(_NOTICE_TEXT, {"i": 3, "kind": "Button", "name": "Minimizar", "rect": {"x": 620, "y": 302, "w": 36, "h": 26}})
    assert "«Minimizar»" not in _listed(view, "sal del aviso")
