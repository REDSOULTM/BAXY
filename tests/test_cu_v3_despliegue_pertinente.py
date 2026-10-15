"""Ronda 24, palanca «despliegue de último recurso: sólo lo pertinente».

Antes de rendirse sólo se abre lo que puede llevar al objetivo, y nunca algo que cambia un valor o deshace lo hecho.
Medido en la pasada r23 (v3-26, v3-24, v3-07, v3-04, v3-01, v3-03, v3-17, v3-30, v3-27, v3-29, v3-40, t-form-3,
t-file-1, t-long-2, t-long-3, t-drag-4, t-scroll-2): ``_unfold_before_giving_up`` abría el primer SplitButton, ComboBox
o MenuItem plegado sin relación con el objetivo, y el reintento nombraba como «parecido» un Group, un Text o un
ScrollBar con parecido bajo. Las vistas son las de los casos, reducidas a los controles que deciden.
"""

from __future__ import annotations

import json
from pathlib import Path

from baxy_mind import computer_use as cu
from baxy_mind import cu_view
from baxy_mind import cu_meaning
from baxy_mind import cu_validate
from baxy_mind import cu_unfold
from baxy_mind import cu_step_prompt
from baxy_mind.semantic import cu_semejanza

# Revisión 2: las vistas reales de los casos, enteras (tests/data/cu_v3_r24_vistas_reales.json).
_REAL = json.loads((Path(__file__).parent / "data" / "cu_v3_r24_vistas_reales.json").read_text(encoding="utf-8"))


def _real(name: str) -> dict:
    return json.loads(json.dumps(_REAL[name]))


class _Scores:
    """An encoder ready that scores the view's names by a fixed table (``other``, 0.5 by default, for any other name)."""

    def __init__(self, table: dict[str, float], other: float = 0.5) -> None:
        self.table = table
        self.other = other
        self.state = cu_meaning.ENCODER_READY

    def scored(self, label, view, other_labels=(), *, wait=False):
        names = [str(control.get("name") or "").strip() for control in view.get("controls", [])]
        return tuple(sorted(((name, self.table.get(name, self.other)) for name in names if name),
                            key=lambda pair: -pair[1]))


def _opened(app: str) -> dict:
    return {"step": 1, "operation": "app.open", "appId": app, "ok": True, "changed": True}


def _terminal() -> dict:
    return {
        "window": {"title": "Windows PowerShell", "process": "WindowsTerminal"},
        "controls": [
            {"i": 0, "kind": "TabItem", "name": "Windows PowerShell", "state": "selected", "zone": "TL"},
            {"i": 2, "kind": "SplitButton", "name": "Nueva pestaña", "state": "collapsed", "zone": "TL"},
            {"i": 9, "kind": "Button", "name": "Cerrar", "zone": "TR"},
            {"i": 11, "kind": "ScrollBar", "name": "Vertical", "value": "0", "zone": "R"},
        ],
    }


def _word_ribbon() -> dict:
    """v3-01 / v3-04: PowerPoint con «Pegar» y «Dictar» plegados; v3-28: la lista de fuentes."""

    return {
        "window": {"title": "Presentación1 - PowerPoint", "process": "POWERPNT"},
        "controls": [
            {"i": 0, "kind": "SplitButton", "name": "Pegar", "state": "collapsed", "zone": "TL"},
            {"i": 2, "kind": "ComboBox", "name": "Fuente", "state": "collapsed", "value": "Aptos", "zone": "TL"},
            {"i": 3, "kind": "SplitButton", "name": "Dictar", "state": "collapsed", "zone": "TR"},
            {"i": 9, "kind": "Document", "name": "Diapositiva", "zone": "C"},
        ],
        "text": {"C": ["Haga clic para agregar título"]},
    }


def _charmap() -> dict:
    """v3-27, v3-29, v3-30, t-scroll-2: el Mapa de caracteres con sus dos listas de valores."""

    return {
        "window": {"title": "Mapa de caracteres", "process": "charmap"},
        "controls": [
            {"i": 1, "kind": "ComboBox", "name": "Fuente:", "state": "collapsed", "value": "Arial", "zone": "T"},
            {"i": 4, "kind": "ComboBox", "name": "Juego de caracteres:", "state": "collapsed", "value": "Unicode",
             "zone": "B"},
            {"i": 6, "kind": "Edit", "name": "Buscar:", "zone": "B"},
            {"i": 8, "kind": "Button", "name": "Seleccionar", "zone": "B"},
        ],
    }


# ------------------------------------------------ (1) sólo objetivos de orden o de lugar


def test_v3_01_v3_04_a_title_to_write_never_opens_paste_or_dictate() -> None:
    for goal in ("escribir «Proyecto final» en el título", "ponle 'Proyecto final' de título"):
        assert cu_unfold._unfold_before_giving_up(_word_ribbon(), [_opened("PowerPoint")], goal, None, None) is None, goal
    assert not cu_unfold._is_order_goal("ponle 'Proyecto final' de título")


def test_t_drag_4_t_long_3_a_drawing_never_reaches_the_loop_it_is_the_drag_limit() -> None:
    # Ronda 24 kept a drawing goal from opening «Zoom» or «Importar al lienzo» blind (data «drawGoal»). Estabilización
    # L: drawing is a declared limit and the mission stops before it, so that exception of _is_order_goal went with it.
    from baxy_mind.semantic.drag import asks_to_drag

    for goal in ("dibujar una línea horizontal con pinceles", "draw a red filled rectangle in the middle"):
        assert asks_to_drag(goal), goal


def test_counter_case_a_reading_goal_still_opens_nothing_blind() -> None:
    assert cu_unfold._unfold_before_giving_up(_terminal(), [_opened("Terminal")], "leer el perfil predeterminado", None,
                                       None) is None


def test_v3_38_v3_39_counter_case_the_split_button_still_opens_without_similarity() -> None:
    step = cu_unfold._unfold_before_giving_up(_terminal(), [_opened("Terminal")], "ir a configuracion",
                                       "en la terminal anda a configuracion", None)
    assert step is not None and step["arguments"] == {"label": "Nueva pestaña", "index": 2, "manner": "open"}
    # An order said freely opens it too.
    order = cu_unfold._unfold_before_giving_up(_terminal(), [_opened("Terminal")], "dividir el panel en vertical", None, None)
    assert order is not None and order["arguments"]["label"] == "Nueva pestaña"


# ------------------------------------------------ (2) un desplegable sólo si el objetivo lo nombra


def test_v3_27_v3_29_t_scroll_2_a_value_list_the_goal_does_not_name_stays_closed() -> None:
    for goal in ("copiar el símbolo del euro", "seleccionar el símbolo de copyright", "ir a flecha"):
        assert cu_unfold._unfold_before_giving_up(_charmap(), [_opened("Mapa de caracteres")], goal, None, None) is None, goal


def test_v3_17_the_zoom_selection_is_never_opened_to_crop() -> None:
    photos = {
        "window": {"title": "paisaje.jpg - Fotos", "process": "Photos"},
        "controls": [
            {"i": 2, "kind": "ComboBox", "name": "Selección de zoom", "state": "collapsed", "value": "100%", "zone": "B"},
            {"i": 4, "kind": "Button", "name": "Editar", "zone": "T"},
        ],
    }
    assert cu_unfold._unfold_before_giving_up(photos, [_opened("Fotos")], "recortar en proporción cuadrada", None, None) is None


def test_t_form_3_an_order_never_opens_the_location_list_of_a_save_dialog() -> None:
    # Revisión 2: the real view of the case, the person's «¿Guardar los cambios…?» left open over Word.
    dialog = _real("word_guardar_cambios")
    assert cu_unfold._dialog_bounds(dialog, [_opened("Word")]) == (True, None)
    goal = "insert a table, donde se ponen columnas y filas"
    assert cu_unfold._unfold_before_giving_up(dialog, [_opened("Word")], goal, "Insert a table", None) is None
    # Even a split button is not opened on a dialog the mission did not bring.
    dialog["controls"].append({"i": 16, "kind": "SplitButton", "name": "Herramientas", "state": "collapsed", "zone": "B",
                               "rect": {"x": 1300, "y": 760, "w": 90, "h": 30}})
    assert cu_unfold._unfold_before_giving_up(dialog, [_opened("Word")], goal, "Insert a table", None) is None


def test_v3_28_counter_case_the_goal_naming_the_font_and_a_value_opens_its_list() -> None:
    goal = "cambiar la fuente a Wingdings"
    assert cu_unfold._is_order_goal(goal)
    step = cu_unfold._unfold_before_giving_up(_word_ribbon(), [_opened("Word")], goal, "cambia la fuente a Wingdings", None)
    assert step is not None and step["arguments"]["label"] == "Fuente" and step["arguments"]["manner"] == "open"


# ------------------------------------------------ (3) nunca tras escribir o enviar, ni comandos que crean, ni detrás


def test_v3_30_nothing_is_opened_after_the_search_was_typed_and_sent() -> None:
    history = [
        _opened("Mapa de caracteres"),
        {"step": 2, "operation": "input.text.type", "text": "flecha", "ok": True},
        {"step": 3, "operation": "input.key.press", "key": "enter", "ok": True},
    ]
    assert cu_unfold._unfold_before_giving_up(_charmap(), history, "cambiar el juego de caracteres a unicode", None, None) is None
    # Counter-case: before writing, the goal that names the list opens it.
    step = cu_unfold._unfold_before_giving_up(_charmap(), [_opened("Mapa de caracteres")],
                                       "cambiar el juego de caracteres a unicode", None, None)
    assert step is not None and step["arguments"]["label"] == "Juego de caracteres:"


def _outlook() -> dict:
    return {
        "window": {"title": "Bandeja de entrada - Outlook", "process": "OUTLOOK"},
        "controls": [
            {"i": 3, "kind": "SplitButton", "name": "Copilot", "state": "collapsed", "zone": "TL"},
            {"i": 5, "kind": "SplitButton", "name": "Nuevo correo electrónico", "state": "collapsed", "zone": "TL"},
            {"i": 27, "kind": "TabItem", "name": "Inicio", "state": "selected", "zone": "T"},
            {"i": 28, "kind": "TabItem", "name": "Enviar y recibir", "zone": "T"},
            {"i": 29, "kind": "TabItem", "name": "Vista", "zone": "T"},
            {"i": 30, "kind": "TabItem", "name": "Carpeta", "zone": "T"},
            {"i": 58, "kind": "Button", "name": "Vista de lectura. Ocultar todos los paneles anclados.", "zone": "B"},
        ],
    }


def test_v3_07_no_assistant_nor_creating_command_and_the_unselected_tab_leads() -> None:
    goal = "desactivar reading pane porfa"
    scores = _Scores({"Vista": 0.88, "Enviar y recibir": 0.80, "Copilot": 0.86})
    step = cu_unfold._unfold_before_giving_up(_outlook(), [_opened("Outlook")], goal, None, None, semantic=scores)
    assert step is not None and step["arguments"] == {"label": "Vista", "index": 29}, step
    assert step["reason"] == cu_unfold.REASON_UNFOLD_TAB
    # Without an encoder no assistant and no creating command is opened either: only a tab.
    blind = cu_unfold._unfold_before_giving_up(_outlook(), [_opened("Outlook")], goal, None, None)
    assert blind is not None and blind["arguments"]["label"] in {"Vista", "Carpeta"}
    # A tab already pressed in the sub-goal is not pressed again. Ronda 29 (v3-08, v3-09: the list of «Compartir» opened
    # blind made BAXY ask the person to confirm what nobody had asked): «Enviar y recibir» is named for sending, the
    # Kernel's RiskPolicy asks before that click (RiskPolicyWorldActsTests), so it is never the tab tried blind, though
    # the encoder scores it above the next one; the next ordinary tab is.
    pressed = [_opened("Outlook"), {"step": 2, "operation": "input.visible.click", "label": "Vista", "index": 29,
                                    "ok": True}]
    again = cu_unfold._unfold_before_giving_up(_outlook(), pressed, goal, None, None, semantic=scores)
    assert again is not None and again["arguments"]["label"] == "Carpeta"
    # Two tabs tried: no tour of the strip. Revisión 1: the list of the command that creates is never opened, not even
    # as the last resort, and the assistant neither.
    pressed.append({"step": 3, "operation": "input.visible.click", "label": "Carpeta", "index": 30, "ok": True})
    assert cu_unfold._unfold_before_giving_up(_outlook(), pressed, goal, None, None, semantic=scores) is None
    assert cu_unfold._unfold_before_giving_up(_outlook(), pressed, goal, None, None) is None


def test_counter_case_the_persons_document_tabs_are_never_selected_blind() -> None:
    # t-menu-3: the editor's tabs are the person's files; the selected one names the window.
    notepad = {
        "window": {"title": "hello world - Bloc de notas", "process": "Notepad"},
        "controls": [
            {"i": 1, "kind": "TabItem", "name": "lista.txt. No modificado.", "zone": "TL"},
            {"i": 2, "kind": "TabItem", "name": "Sin título. No modificado.", "zone": "T"},
            {"i": 5, "kind": "TabItem", "name": "hello world. Modificado.", "state": "selected", "zone": "TR"},
        ],
    }
    assert cu_unfold._unfold_before_giving_up(notepad, [_opened("Bloc de notas")], "ir a View", None, None) is None
    # A strip that marks no tab selected cannot tell either.
    notepad["controls"][2]["state"] = ""
    assert cu_unfold._unfold_before_giving_up(notepad, [_opened("Bloc de notas")], "ir a View", None, None) is None


def test_counter_case_an_order_never_selects_a_tab_blind() -> None:
    # An order may live in any list: the tabs are for a place. Revisión 1: the creating list is never left as a resort
    # either (the probes of the review: three orders, the first «none» of each).
    for goal in ("imprimir el correo en doble cara", "marcar todos como leidos", "responder al correo"):
        assert cu_unfold._unfold_before_giving_up(_outlook(), [_opened("Outlook")], goal, None, None) is None, goal
    scores = _Scores({"Nuevo correo electrónico": 0.95})
    assert cu_unfold._unfold_before_giving_up(_outlook(), [_opened("Outlook")], "responder al correo", None, None,
                                       semantic=scores) is None


def test_review_1_only_the_list_that_adds_a_page_to_the_windows_strip_opens_among_creating_commands() -> None:
    # v3-38: «Nueva pestaña» is drawn in the row of the Terminal's tabs, whose selected tab names the window.
    with_rects = _terminal()
    with_rects["controls"][0]["rect"] = {"x": 0, "y": 0, "w": 200, "h": 32}
    with_rects["controls"][1]["rect"] = {"x": 210, "y": 2, "w": 60, "h": 28}
    step = cu_unfold._unfold_before_giving_up(with_rects, [_opened("Terminal")], "ir a configuracion", None, None)
    assert step is not None and step["arguments"] == {"label": "Nueva pestaña", "index": 2, "manner": "open"}
    # Counter-case: the same command drawn away from the strip's row is not that strip's list.
    with_rects["controls"][1]["rect"] = {"x": 210, "y": 300, "w": 60, "h": 28}
    assert cu_unfold._unfold_before_giving_up(with_rects, [_opened("Terminal")], "ir a configuracion", None, None) is None
    # Counter-case: a strip whose selected tab does not name the window is of sections, not of the window's pages.
    sections = _terminal()
    sections["controls"][0]["name"] = "Inicio"
    assert cu_unfold._unfold_before_giving_up(sections, [_opened("Terminal")], "ir a configuracion", None, None) is None
    # Counter-case: a command that creates nothing still opens without that strip (v3-28's split buttons).
    sections["controls"][1]["name"] = "Opciones"
    step = cu_unfold._unfold_before_giving_up(sections, [_opened("Terminal")], "ir a configuracion", None, None)
    assert step is not None and step["arguments"]["label"] == "Opciones"


def _notepad_with_dialog(brought: bool) -> dict:
    # Revisión 2: as the real window lists it (``notepad_guardar_como_markdown``), the popup host first and the dialog
    # after, both as wide and as tall as the window.
    layer = {"x": 0, "y": 0, "w": 1000, "h": 700}
    view = {
        "window": {"title": "Sin título: Bloc de notas", "process": "Notepad", "rect": dict(layer)},
        "controls": [
            {"i": 8, "kind": "Button", "name": "Minimizar", "zone": "TR", "rect": {"x": 880, "y": 0, "w": 60, "h": 37}},
            {"i": 9, "kind": "Button", "name": "Cerrar", "zone": "TR", "rect": {"x": 940, "y": 0, "w": 60, "h": 37}},
            {"i": 11, "kind": "MenuItem", "name": "Archivo", "state": "collapsed", "zone": "TL",
             "rect": {"x": 0, "y": 40, "w": 60, "h": 30}},
            {"i": 12, "kind": "SplitButton", "name": "Recientes", "state": "collapsed", "zone": "TL",
             "rect": {"x": 70, "y": 40, "w": 80, "h": 30}},
            {"i": 19, "kind": "Window", "name": "Ventana emergente", "zone": "C", "rect": dict(layer)},
            {"i": 20, "kind": "Window", "name": "Guardar como Markdown para conservar el formato", "zone": "C",
             "rect": dict(layer)},
            {"i": 21, "kind": "SplitButton", "name": "Opciones de formato", "state": "collapsed", "zone": "C",
             "rect": {"x": 350, "y": 400, "w": 200, "h": 40}},
            {"i": 22, "kind": "Button", "name": "Cancelar", "zone": "C", "rect": {"x": 600, "y": 400, "w": 100, "h": 40}},
        ],
    }
    return view


_BROUGHT = ["Ventana emergente", "Guardar como Markdown para conservar el formato", "Opciones de formato", "Cancelar"]


def test_t_file_1_nothing_behind_the_dialog_the_last_act_brought() -> None:
    last = {"step": 3, "operation": "input.visible.click", "label": "Guardar como", "ok": True, "appeared": _BROUGHT}
    step = cu_unfold._unfold_before_giving_up(_notepad_with_dialog(True), [_opened("Bloc de notas"), last],
                                       "guardar el archivo como texto", None, None)
    assert step is not None and step["arguments"]["label"] == "Opciones de formato", step
    # A dialog the mission did not bring: nothing at all.
    old = {"step": 3, "operation": "input.visible.click", "label": "Edición", "ok": True}
    assert cu_unfold._unfold_before_giving_up(_notepad_with_dialog(False), [_opened("Bloc de notas"), old],
                                       "guardar el archivo como texto", None, None) is None


def test_review_2_t_file_1_the_real_dialog_the_last_act_brought_is_found_behind_the_popup_host() -> None:
    view = _real("notepad_guardar_como_markdown")
    windows = [control["name"] for control in view["controls"] if control["kind"] == "Window"]
    assert windows[0] == "Ventana emergente"
    brought = ["Ventana emergente", "Guardar como Markdown para conservar el formato", "Guardar como archivo Markdown",
               "Guardar como archivo de texto", "Cancelar"]
    last = {"step": 3, "operation": "input.visible.click", "label": "Guardar como", "ok": True, "appeared": brought}
    has_dialog, bounds = cu_unfold._dialog_bounds(view, [_opened("Bloc de notas"), last])
    # The dialog is drawn where what it brought is (its title and its buttons), not over the whole window its layer
    # covers.
    assert has_dialog and bounds == {"x": 482.0, "y": 325.0, "w": 611.0, "h": 220.0}, bounds
    # Its menus and the person's tabs are behind it: nothing is opened there.
    assert cu_unfold._unfold_before_giving_up(view, [_opened("Bloc de notas"), last], "guardar el archivo como texto",
                                       None, None) is None
    # Counter-case: the same dialog the mission did not bring.
    old = {"step": 3, "operation": "input.visible.click", "label": "Edición", "ok": True}
    assert cu_unfold._dialog_bounds(view, [_opened("Bloc de notas"), old]) == (True, None)


def test_review_2_a_windows_own_document_window_dock_or_panel_is_no_dialog() -> None:
    # The console's document window (mmc), a window's docks, a side panel: none covers the window below its title bar.
    for name in ("visor_eventos_inicio", "visor_eventos_registros", "programador_de_tareas", "servicios",
                 "obs_ventana_principal", "word_panel_navegacion"):
        view = _real(name)
        assert any(control["kind"] == "Window" for control in view["controls"]), name
        assert cu_unfold._dialog_bounds(view, [_opened("x")]) == (False, None), name


# ------------------------------------------------ lugar: el nodo de navegación cerrado


def test_v3_26_v3_24_a_place_opens_the_closed_navigation_node() -> None:
    viewer = {
        "window": {"title": "Visor de eventos", "process": "mmc"},
        "controls": [
            {"i": 25, "kind": "TreeItem", "name": "Vistas personalizadas", "state": "collapsed", "zone": "L"},
            {"i": 26, "kind": "TreeItem", "name": "Registros de Windows", "state": "collapsed", "zone": "L"},
            {"i": 27, "kind": "TreeItem", "name": "Registros de aplicaciones y servicios", "state": "collapsed",
             "zone": "L"},
            {"i": 40, "kind": "SplitButton", "name": "Acción", "state": "collapsed", "zone": "TL"},
        ],
    }
    scores = _Scores({"Registros de Windows": 0.9, "Registros de aplicaciones y servicios": 0.85})
    step = cu_unfold._unfold_before_giving_up(viewer, [_opened("Visor de eventos")], "ir a sistema", None, None,
                                       semantic=scores)
    assert step is not None and step["arguments"] == {"label": "Registros de Windows", "index": 26, "manner": "open"}


def test_review_2_v3_26_v3_24_the_real_console_opens_the_node_with_its_document_window_listed() -> None:
    view = _real("visor_eventos_inicio")
    assert any(control["kind"] == "Window" and control["name"] == "Visor de eventos (local)"
               for control in view["controls"])
    expected = {"label": "Registros de Windows", "index": 17, "manner": "open"}
    # Without the encoder the descent opens the tree in its own order (``_tree_descent_step``): a node, never nothing.
    step = cu_unfold._unfold_before_giving_up(view, [_opened("Visor de eventos")], "ir a sistema", None, None)
    assert step is not None and step["arguments"] == {"label": "Vistas personalizadas", "index": 16, "manner": "open"}
    scores = _Scores({"Registros de Windows": 0.9, "Registros de aplicaciones y servicios": 0.85}, other=0.3)
    step = cu_unfold._unfold_before_giving_up(view, [_opened("Visor de eventos")], "ir a sistema", None, None,
                                       semantic=scores)
    assert step is not None and step["arguments"] == expected, step


def test_review_2_v3_07_the_real_outlook_picks_the_view_tab_and_never_opens_the_persons_folders() -> None:
    view = _real("outlook_bandeja_con_carpetas")
    goal = "desactivar reading pane porfa"
    tabs = [control for control in view["controls"] if control["kind"] == "TabItem"]
    # «Minimizar el panel de carpetas» (y=173) is a pane's button: the frame's band stays its top row, the tabs below.
    assert tabs and not any(cu_view._in_title_bar(view, tab) for tab in tabs)
    assert cu_view._in_title_bar(view, next(control for control in view["controls"] if control["name"] == "Notificaciones"))
    scores = _Scores({"Vista": 0.88}, other=0.3)
    step = cu_unfold._unfold_before_giving_up(view, [_opened("Outlook")], goal, None, None, semantic=scores)
    assert step is not None and step["arguments"] == {"label": "Vista", "index": 45}, step
    # A goal that switches something never descends the tree: no folder of the person's is opened, with or without the
    # encoder, along the whole fallback of the sub-goal.
    folders = {control["name"] for control in view["controls"] if control["kind"] == "TreeItem"}
    for semantic in (scores, None):
        history = [_opened("Outlook")]
        for n in range(6):
            step = cu_unfold._unfold_before_giving_up(view, history, goal, None, None, semantic=semantic)
            if step is None:
                break
            assert step["arguments"]["label"] not in folders, step
            history.append({"step": n + 2, "operation": "input.visible.click", "ok": True, **step["arguments"]})
    # Counter-case: a goal that goes to a place still descends the tree.
    step = cu_unfold._unfold_before_giving_up(view, [_opened("Outlook")], "ir a historial de conversaciones antiguas", None,
                                       None)
    assert step is not None and step["arguments"]["manner"] == "open" and step["arguments"]["label"] in folders, step


# ------------------------------------------------ (4) el reintento sólo nombra un parecido accionable


def test_v3_03_v3_17_v3_40_the_retry_never_names_a_frame_or_a_low_similarity() -> None:
    low = [{"i": 4, "kind": "TabItem", "name": "Pestaña Archivo", "similarity": 0.845}]
    assert "o none si no hay ninguno" in cu_step_prompt.retry_instruction("no vale", low)
    # Revisión 1: being the most similar name of the view is no exception to the click's similarity (v3-04: «Tarea
    # siguiente» was the first, at 0.80; «Ver» at 0.855 < 0.86).
    for name, similarity in (("Tarea siguiente", 0.80), ("Ver", 0.855)):
        said = cu_step_prompt.retry_instruction("no vale", [{"i": 3, "kind": "Button", "name": name, "similarity": similarity}])
        assert "o none si no hay ninguno" in said and name not in said, said
    # Counter-case: at the click's similarity it is named.
    said = cu_step_prompt.retry_instruction("no vale", [{"i": 8, "kind": "MenuItem", "name": "Ver",
                                             "similarity": cu_semejanza.CLICK_SIMILARITY}])
    assert "«Ver»" in said and "none" not in said
    for kind, name in (("Group", "Dimensiones"), ("Text", "Examinar texto"), ("ScrollBar", "Vertical")):
        said = cu_step_prompt.retry_instruction("no vale", [{"i": 7, "kind": kind, "name": name, "similarity": 0.95}])
        assert "o none si no hay ninguno" in said and name not in said, (kind, said)


def test_counter_case_videos_library_keeps_its_hint_and_the_retry_names_it() -> None:
    said = cu_step_prompt.retry_instruction("no vale", [{"i": 8, "kind": "ListItem", "name": "Videos", "similarity": 0.91}])
    assert "«Videos»" in said and "none" not in said


def test_similar_controls_drop_frames_and_texts(monkeypatch) -> None:
    view = {
        "window": {"title": "Fotos", "process": "Photos"},
        "controls": [
            {"i": 1, "kind": "Group", "name": "Dimensiones", "zone": "R"},
            {"i": 2, "kind": "Text", "name": "Examinar texto", "zone": "C"},
            {"i": 3, "kind": "ScrollBar", "name": "Vertical", "zone": "R"},
            {"i": 4, "kind": "Button", "name": "Recortar", "zone": "T"},
        ],
    }

    class _Any:
        state = cu_meaning.ENCODER_READY

        def scored(self, label, view, others=(), *, wait=False):
            return (("Recortar", 0.9), ("Dimensiones", 0.88), ("Examinar texto", 0.87), ("Vertical", 0.86))

    monkeypatch.setattr(cu_step_prompt, "similar_hints", lambda scored, usable: [name for name, _ in scored])
    hints = cu_step_prompt._similar_controls("recortar la imagen", view, (), _Any())
    assert [control["name"] for control in hints] == ["Recortar"]
    assert hints[0]["similarity"] == 0.9


# ------------------------------------------------ (5) el único control con el nombre exacto


def test_v3_37_the_one_control_named_by_the_check_is_pressed_before_the_palette() -> None:
    view = _terminal()
    view["controls"][1] = {"i": 2, "kind": "SplitButton", "name": "Nueva pestaña", "state": "expanded", "zone": "TL"}
    view["controls"] += [
        {"i": 21, "kind": "MenuItem", "name": "Configuración", "zone": "TL"},
        {"i": 22, "kind": "MenuItem", "name": "Paleta de comandos", "zone": "TL"},
    ]
    # Revisión 3: «Configuración» came with the act of this sub-goal that opened the list (its ``appeared``).
    opened_list = {"step": 2, "operation": "input.key.press", "key": "ctrl_shift_space", "ok": True,
                   "appeared": ["Configuración", "Paleta de comandos"]}
    step = cu_unfold._exactly_named_step("abrir los ajustes de la terminal", "born:Configuración", view,
                                  [_opened("Terminal"), opened_list])
    assert step is not None and step["arguments"] == {"label": "Configuración", "index": 21}
    assert step["reason"] == cu_unfold.REASON_EXACT_NAME


def test_counter_case_two_controls_carrying_the_name_leave_it_to_the_model() -> None:
    view = {
        "window": {"title": "Inicio", "process": "explorer"},
        "controls": [
            {"i": 1, "kind": "ListItem", "name": "Símbolo del sistema", "zone": "C"},
            {"i": 2, "kind": "ListItem", "name": "Símbolo del sistema (administrador)", "zone": "C"},
        ],
    }
    assert cu_unfold._exactly_named_step("ir a símbolo del sistema", "control:Símbolo del sistema", view, []) is None
    # And a reading goal never presses.
    view["controls"].pop()
    assert cu_unfold._exactly_named_step("leer símbolo del sistema", "control:Símbolo del sistema", view, []) is None


def test_counter_case_a_new_tab_asked_for_still_presses_its_action() -> None:
    step = cu_validate.validate_decision(
        {"act": "click", "i": 2}, view=_terminal(), last_failed=None, application_names=("Terminal",),
        history=[_opened("Terminal")], goal="ir a nueva pestaña", objective="en la terminal abrí una pestaña nueva",
    )
    assert step["operation"] == "input.visible.click" and "manner" not in step["arguments"]


def _player() -> dict:
    return {
        "window": {"title": "Reproductor multimedia", "process": "Player"},
        "controls": [
            {"i": 3, "kind": "Button", "name": "Silenciar", "zone": "B"},
            {"i": 7, "kind": "Slider", "name": "Brillo", "value": "40", "zone": "B"},
            {"i": 8, "kind": "Slider", "name": "Volumen", "value": "60", "zone": "B"},
            {"i": 9, "kind": "CheckBox", "name": "Repetir", "state": "off", "zone": "B"},
        ],
    }


def test_review_1_the_exact_name_never_presses_a_control_that_keeps_a_value() -> None:
    # A slider pressed blind lands on its middle (the worker finds no pattern and clicks the centre): its value changes.
    for goal, check in (("subir el brillo al maximo", "control:Brillo"), ("ir a brillo", "control:Brillo"),
                        ("desactivar volumen", "control:volumen:off"), ("ir a repetir", "control:Repetir:on")):
        assert cu_unfold._exactly_named_step(goal, check, _player(), [_opened("Reproductor")]) is None, goal
    # Counter-case: the button of that view named by the check is still pressed.
    step = cu_unfold._exactly_named_step("silenciar el audio", "control:Silenciar", _player(), [_opened("Reproductor")])
    assert step is not None and step["arguments"] == {"label": "Silenciar", "index": 3}


def test_review_1_the_exact_name_never_presses_a_fold_of_several_controls() -> None:
    # v3-39: the worker folds controls of one kind and name into one with «repeated» (two real controls here).
    view = {
        "window": {"title": "Inicio", "process": "explorer"},
        "controls": [
            {"i": 4, "kind": "ListItem", "name": "Windows PowerShell", "repeated": 1, "zone": "C"},
            {"i": 5, "kind": "ListItem", "name": "Símbolo del sistema", "zone": "C"},
        ],
    }
    check = "control:Windows PowerShell:selected"
    assert cu_unfold._exactly_named_step("ir a windows powershell", check, view, []) is None
    # Counter-case: one control of that name is pressed.
    del view["controls"][0]["repeated"]
    step = cu_unfold._exactly_named_step("ir a windows powershell", check, view, [])
    assert step is not None and step["arguments"] == {"label": "Windows PowerShell", "index": 4}


class _Fixed:
    state = cu_meaning.ENCODER_READY

    def __init__(self, *pairs) -> None:
        self.pairs = tuple(pairs)

    def scored(self, label, view, others=(), *, wait=False):
        return self.pairs


def test_review_3_no_name_under_the_click_similarity_is_named_not_even_the_one_near_a_place(monkeypatch) -> None:
    monkeypatch.setattr(cu_step_prompt, "similar_hints", lambda scored, usable: [name for name, _ in scored])
    slide = {
        "window": {"title": "Presentación1 - PowerPoint", "process": "POWERPNT"},
        "controls": [
            {"i": 13, "kind": "TabItem", "name": "Pestaña Archivo", "zone": "TL"},
            {"i": 15, "kind": "TabItem", "name": "Inicio", "state": "selected", "zone": "TL"},
            {"i": 45, "kind": "Button", "name": "Tarea siguiente", "zone": "B"},
        ],
    }
    # v3-04: a goal that writes a title; «Tarea siguiente» is the first and only hint, under 0.86: «none» stays.
    hints = cu_step_prompt._similar_controls("ponle 'Proyecto final' de título", slide, (), _Fixed(("Tarea siguiente", 0.85)))
    assert [control["name"] for control in hints] == ["Tarea siguiente"]
    said = cu_step_prompt.retry_instruction("no vale", hints)
    assert "o none si no hay ninguno" in said and "Tarea siguiente" not in said
    # v3-03: a place («slide sorter») and the one name near it, «Pestaña Archivo» at 0.845, led to Backstage when the
    # retry named it and took «none» away: under the click's similarity it is not named and «none» stays offered.
    one = cu_step_prompt._similar_controls("ir a slide sorter", slide, (), _Fixed(("Pestaña Archivo", 0.845)))
    assert [control["name"] for control in one] == ["Pestaña Archivo"]
    said = cu_step_prompt.retry_instruction("no vale", one)
    assert "o none si no hay ninguno" in said and "Pestaña Archivo" not in said, said
    two = cu_step_prompt._similar_controls("ir a tarea", slide, (), _Fixed(("Tarea siguiente", 0.85), ("Inicio", 0.845)))
    assert len(two) == 2 and "o none si no hay ninguno" in cu_step_prompt.retry_instruction("no vale", two)
    # Counter-case: the one name near a place at the click's similarity is named.
    at = cu_step_prompt._similar_controls("ir a tarea", slide, (), _Fixed(("Tarea siguiente", cu_semejanza.CLICK_SIMILARITY)))
    said = cu_step_prompt.retry_instruction("no vale", at)
    assert "«Tarea siguiente»" in said and "none" not in said


# ------------------------------------------------ revisión 3: born: nombra lo que tiene que aparecer


class _NoneModel:
    def _post_schema_object(self, payload: dict, label: str) -> dict:
        del payload, label
        return {"act": "none"}


def _terminal_with_the_persons_tab() -> dict:
    view = _terminal()
    view["controls"].insert(1, {"i": 1, "kind": "TabItem", "name": "Símbolo del sistema", "zone": "TL"})
    return view


def _explorer_with_informes() -> dict:
    return {
        "window": {"title": "Documentos", "process": "explorer"},
        "controls": [
            {"i": 3, "kind": "SplitButton", "name": "Nuevo", "state": "collapsed", "zone": "TL"},
            {"i": 8, "kind": "ListItem", "name": "informes", "zone": "C"},
            {"i": 9, "kind": "ListItem", "name": "facturas", "zone": "C"},
        ],
    }


def test_review_3_a_born_name_never_presses_a_control_the_view_already_showed() -> None:
    # v3-37: the person's own tab «Símbolo del sistema» was there when the sub-goal started; pressing it switches the
    # person's tab and makes no new tab appear (BornContainer asks the tabs to grow).
    check = "born:simbolo del sistema|born:command prompt"
    goal = "abrir una pestaña nueva de simbolo del sistema"
    assert cu_unfold._exactly_named_step(goal, check, _terminal_with_the_persons_tab(), [_opened("Terminal")]) is None
    # The folder «informes» the person already has is never what a creation of «informes» presses.
    assert cu_unfold._exactly_named_step("crear una carpeta llamada informes", "born:informes", _explorer_with_informes(),
                                  [_opened("Explorador")]) is None
    # appeared: names what an act has to bring, the same.
    assert cu_unfold._exactly_named_step(goal, "appeared:simbolo del sistema", _terminal_with_the_persons_tab(),
                                  [_opened("Terminal")]) is None
    # A step that brought other names, or a step that failed, does not make the person's tab one of them.
    other = {"step": 2, "operation": "input.key.press", "key": "ctrl_shift_space", "ok": True, "appeared": ["Azure"]}
    failed = {"step": 3, "operation": "input.key.press", "key": "ctrl_shift_space", "ok": False,
              "appeared": ["Símbolo del sistema"]}
    assert cu_unfold._exactly_named_step(goal, check, _terminal_with_the_persons_tab(),
                                  [_opened("Terminal"), other, failed]) is None


def test_review_3_counter_case_a_born_name_an_act_brought_is_pressed_and_a_control_atom_still_is() -> None:
    goal = "abrir una pestaña nueva de simbolo del sistema"
    view = _terminal()
    view["controls"][1] = {"i": 2, "kind": "SplitButton", "name": "Nueva pestaña", "state": "expanded", "zone": "TL"}
    view["controls"].append({"i": 23, "kind": "MenuItem", "name": "Símbolo del sistema", "zone": "TL"})
    brought = {"step": 2, "operation": "input.key.press", "key": "ctrl_shift_space", "ok": True,
               "appeared": ["Símbolo del sistema", "Azure Cloud Shell"]}
    step = cu_unfold._exactly_named_step(goal, "born:simbolo del sistema|born:command prompt", view,
                                  [_opened("Terminal"), brought])
    assert step is not None and step["arguments"] == {"label": "Símbolo del sistema", "index": 23}
    # A control: atom names what is pressed or reached: the control the view already showed still stands for it.
    step = cu_unfold._exactly_named_step("silenciar el audio", "control:Silenciar", _player(), [_opened("Reproductor")])
    assert step is not None and step["arguments"] == {"label": "Silenciar", "index": 3}


def test_review_3_the_step_on_the_persons_tab_is_the_list_of_the_new_tab_not_the_tab() -> None:
    step = cu.decide_step(
        _NoneModel(), objective="en la terminal abrí una pestaña nueva de simbolo del sistema",
        goal="abrir una pestaña nueva de simbolo del sistema", application="Terminal",
        success_check="born:simbolo del sistema|born:command prompt", view=_terminal_with_the_persons_tab(),
        history=[_opened("Terminal")], budget_left=8, application_names=("Terminal",),
    )
    assert not (step.get("operation") == "input.visible.click" and step["arguments"].get("index") == 1), step
    assert step.get("reason") != cu_unfold.REASON_EXACT_NAME, step
    assert step.get("operation") == "input.visible.click" and step["arguments"].get("index") == 2, step
    assert step["arguments"].get("manner") == "open", step


def test_review_3_a_creation_never_presses_the_persons_folder_of_that_name() -> None:
    step = cu.decide_step(
        _NoneModel(), objective="en el explorador creá una carpeta llamada informes",
        goal="crear una carpeta llamada informes", application="Explorador", success_check="born:informes",
        view=_explorer_with_informes(), history=[_opened("Explorador")], budget_left=8,
        application_names=("Explorador",),
    )
    assert not (step.get("operation") == "input.visible.click" and step["arguments"].get("index") == 8), step
    assert step.get("reason") != cu_unfold.REASON_EXACT_NAME, step


# ------------------------------------------------ revisión 4: el menú cercano a un lugar y los interruptores


def test_review_4_t_menu_3_the_one_menu_near_a_place_is_named_and_a_tab_or_a_switch_is_not(monkeypatch) -> None:
    monkeypatch.setattr(cu_step_prompt, "similar_hints", lambda scored, usable: [name for name, _ in scored])

    def window(control: dict) -> dict:
        return {"window": {"title": "*hello world: Bloc de notas", "process": "notepad"}, "controls": [control]}

    # t-menu-3: «Ver» alone near «view» at 0.855 is a menu: opening it changes nothing, the retry names it.
    menu = cu_step_prompt._similar_controls("ir a view", window({"i": 8, "kind": "MenuItem", "name": "Ver"}), (),
                                _Fixed(("Ver", 0.855)))
    said = cu_step_prompt.retry_instruction("no vale", menu)
    assert "«Ver»" in said and "none" not in said, said
    # Counter-cases: a tab (v3-03's «Pestaña Archivo» turns the window's page), a checkable entry (a switch), a goal
    # that is no place, or two names near it: «none» stays offered.
    for control, goal, pairs in (
        ({"i": 4, "kind": "TabItem", "name": "Ver"}, "ir a view", (("Ver", 0.855),)),
        ({"i": 8, "kind": "MenuItem", "name": "Ver", "state": "checkable"}, "ir a view", (("Ver", 0.855),)),
        ({"i": 8, "kind": "MenuItem", "name": "Ver"}, "ponle 'Ver' de título", (("Ver", 0.855),)),
    ):
        hints = cu_step_prompt._similar_controls(goal, window(control), (), _Fixed(*pairs))
        said = cu_step_prompt.retry_instruction("no vale", hints)
        assert "o none si no hay ninguno" in said and "«Ver»" not in said, (control, goal, said)
    two = {"window": {"title": "Bloc de notas"}, "controls": [{"i": 8, "kind": "MenuItem", "name": "Ver"},
                                                              {"i": 7, "kind": "MenuItem", "name": "Editar"}]}
    said = cu_step_prompt.retry_instruction("no vale", cu_step_prompt._similar_controls("ir a view", two, (), _Fixed(("Ver", 0.855),
                                                                                         ("Editar", 0.85))))
    assert "o none si no hay ninguno" in said


class _Answers:
    """A model that answers the same step every time it is asked."""

    def __init__(self, answer: dict) -> None:
        self.answer = answer

    def _post_schema_object(self, payload: dict, label: str) -> dict:
        del payload, label
        return dict(self.answer)


def _settings(state: str) -> dict:
    return {
        "window": {"title": "Configuración", "process": "SystemSettings"},
        "controls": [
            {"i": 0, "kind": "Button", "name": "Bluetooth", "state": state, "zone": "C"},
            {"i": 1, "kind": "Button", "name": "Agregar dispositivo", "zone": "C"},
        ],
        "text": {},
    }


def _switch_player(state: str) -> dict:
    return {
        "window": {"title": "Reproductor", "process": "player"},
        "controls": [
            {"i": 3, "kind": "Button", "name": "Repetir", "state": state, "zone": "B"},
            {"i": 4, "kind": "Button", "name": "Aleatorio", "state": state, "zone": "B"},
            {"i": 5, "kind": "Button", "name": "Reproducir", "zone": "B"},
        ],
        "text": {},
    }


def _tried(key: str, step: int) -> dict:
    return {"step": step, "operation": "input.key.press", "key": key, "ok": True, "changed": False}


def _presses(step: dict, label: str) -> bool:
    return step.get("operation") == "input.visible.click" and step.get("arguments", {}).get("label") == label


def test_review_4_the_exact_name_never_presses_a_switch() -> None:
    for goal, view, name in (
        ("ir a bluetooth", _settings("on"), "Bluetooth"), ("activar bluetooth", _settings("on"), "Bluetooth"),
        ("desactivar bluetooth", _settings("off"), "Bluetooth"), ("activar repetir", _switch_player("on"), "Repetir"),
        ("activar aleatorio", _switch_player("on"), "Aleatorio"), ("hacer clic en repetir", _switch_player("off"), "Repetir"),
    ):
        assert cu_unfold._exactly_named_step(goal, None, view, [_opened("App")]) is None, (goal, name)
    # Counter-case: a button that keeps no state is still pressed by its exact name.
    step = cu_unfold._exactly_named_step("hacer clic en reproducir", None, _switch_player("on"), [_opened("App")])
    assert step is not None and step["arguments"] == {"label": "Reproducir", "index": 5}


def test_review_4_going_to_or_switching_never_flips_the_persons_switch_through_the_last_resort() -> None:
    history = [_opened("Configuración"), _tried("ctrl_k", 2), _tried("ctrl_f", 3)]
    cases = (
        # (a) going to the page never switches what carries its name.
        (_Answers({"act": "none"}), "ir a bluetooth", _settings("on"), "Bluetooth", history),
        # (b) already on, the model's «done» is rejected: the last resort never turns it off.
        (_Answers({"act": "done", "evidence": "Bluetooth Activado"}), "activar bluetooth", _settings("on"), "Bluetooth",
         history),
        # (c) already off: «desactivar» never turns it on.
        (_Answers({"act": "none"}), "desactivar bluetooth", _settings("off"), "Bluetooth", history),
        # (d) a player's «Repetir» and «Aleatorio» already on.
        (_Answers({"act": "done", "evidence": "Repetir activado"}), "activar repetir", _switch_player("on"), "Repetir",
         [_opened("Reproductor")]),
        (_Answers({"act": "done", "evidence": "Aleatorio activado"}), "activar aleatorio", _switch_player("on"),
         "Aleatorio", [_opened("Reproductor")]),
    )
    for model, goal, view, name, steps in cases:
        step = cu.decide_step(
            model, objective=goal, goal=goal, application=None, success_check=None, view=view, history=steps,
            budget_left=8, application_names=(),
        )
        assert not _presses(step, name), (goal, step)
        assert step.get("reason") != cu_unfold.REASON_EXACT_NAME, (goal, step)
