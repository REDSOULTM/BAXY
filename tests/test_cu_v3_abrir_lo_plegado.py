"""Ronda 20b, palanca 6: abrir lo plegado antes de buscar o de rendirse, y no tomar el marco por resultado.

Medido en la pasada r18 (vistas copiadas de model_calls.jsonl de v2-v3-38 y v2-v3-41):
- v3-38 / v3-39: «Configuración» vive en la lista del SplitButton «Nueva pestaña» de la Terminal; el clic se rechazó
  (opens_elsewhere), el reintento ofreció «none» y la misión paró con 9 pasos.
- v3-40 a: la orden sólo se alcanza por la paleta de comandos de esa lista.
- v3-41: «vista de iconos grandes» se escribió en el buscador del Panel de control y se tomó el título repetido de la
  ventana como resultado.
- v3-44: el reintento tras un clic fallido tecleó el nombre en inglés y una rutina pulsó la oferta de la ayuda.
"""

from __future__ import annotations

import copy

from baxy_mind import computer_use
from baxy_mind import cu_languages
from baxy_mind import cu_options
from baxy_mind import cu_lookup
from baxy_mind import cu_rules
from baxy_mind import cu_validate
from baxy_mind import cu_unfold
from baxy_mind import cu_step_prompt
from baxy_mind.semantic import missions

APPS = ("Terminal", "Panel de control", "Bloc de notas", "Calculadora", "Explorador de archivos")


def _terminal() -> dict:
    """v3-38, paso 2: la Terminal recién abierta (14 controles, 9 listados)."""

    return {
        "window": {"title": "Windows PowerShell", "process": "WindowsTerminal"},
        "controls": [
            {"i": 0, "kind": "TabItem", "name": "Windows PowerShell", "state": "selected", "zone": "TL"},
            {"i": 1, "kind": "Button", "name": "Cerrar pestaña", "zone": "TL"},
            {"i": 2, "kind": "SplitButton", "name": "Nueva pestaña", "state": "collapsed", "zone": "TL"},
            {"i": 7, "kind": "Button", "name": "Minimizar", "zone": "TR"},
            {"i": 8, "kind": "Button", "name": "Maximizar", "zone": "TR"},
            {"i": 9, "kind": "Button", "name": "Cerrar", "zone": "TR"},
            {"i": 10, "kind": "Text", "name": "Windows PowerShell", "zone": "TL"},
            {"i": 11, "kind": "ScrollBar", "name": "Vertical", "value": "0", "zone": "R"},
            {"i": 12, "kind": "TitleBar", "name": "Windows PowerShell", "zone": "T"},
        ],
        "text": {"TL": ["Windows PowerShell", "PS C:\\Users\\usuario>"]},
    }


def _terminal_list_open() -> dict:
    """v3-40, turno 2: la lista de «Nueva pestaña» abierta (Configuración, Paleta de comandos)."""

    view = _terminal()
    view["controls"][2] = {"i": 2, "kind": "SplitButton", "name": "Nueva pestaña", "state": "expanded", "zone": "TL"}
    view["controls"] += [
        {"i": 20, "kind": "MenuItem", "name": "Windows PowerShell", "zone": "TL"},
        {"i": 21, "kind": "MenuItem", "name": "Configuración", "zone": "TL"},
        {"i": 22, "kind": "MenuItem", "name": "Paleta de comandos", "zone": "TL"},
    ]
    return view


def _control_panel() -> dict:
    """v3-41: la ventana principal del Panel de control en vista Categoría («Ver por:» escrito junto al botón)."""

    return {
        "window": {"title": "Panel de control", "process": "explorer"},
        "controls": [
            {"i": 0, "kind": "Button", "name": "Subir a \"Escritorio\" (Alt + Flecha arriba)", "zone": "TL"},
            {"i": 1, "kind": "SplitButton", "name": "Todas las ubicaciones", "zone": "TL"},
            {"i": 2, "kind": "MenuItem", "name": "Panel de control", "zone": "TL"},
            {"i": 3, "kind": "Button", "name": "Ubicaciones anteriores", "zone": "TR"},
            {"i": 4, "kind": "Button", "name": "Actualizar \"Panel de control\" (F5)", "zone": "TR"},
            {"i": 5, "kind": "Edit", "name": "Cuadro de búsqueda", "zone": "TR"},
            {"i": 6, "kind": "Button", "name": "Buscar", "state": "readonly", "zone": "TR"},
            {"i": 7, "kind": "Button", "name": "Categoría", "state": "readonly", "zone": "TR"},
            {"i": 9, "kind": "Hyperlink", "name": "Sistema y seguridad", "state": "readonly", "zone": "TL"},
            {"i": 15, "kind": "Hyperlink", "name": "Hardware y sonido", "state": "readonly", "zone": "L"},
            {"i": 16, "kind": "Hyperlink", "name": "Ver dispositivos e impresoras", "state": "readonly", "zone": "L"},
            {"i": 24, "kind": "Hyperlink", "name": "Apariencia y personalización", "state": "readonly", "zone": "C"},
        ],
        "text": {
            "TL": ["Panel de control", "> Panel de control", "Ajustar la configuración del equipo"],
            "TR": ["Buscar en el Panel de control", "p", "Ver por:", "Categoría"],
        },
    }


def _searched_panel() -> dict:
    """v3-41, paso 4: lo que quedó tras escribir «iconos grandes» en el buscador (el título repite la búsqueda)."""

    return {
        "window": {"title": "iconos grandes - Panel de control", "process": "explorer"},
        "controls": [
            {"i": 0, "kind": "Button", "name": "Atrás a Panel de control (Alt + Flecha izquierda)", "zone": "TL"},
            {"i": 2, "kind": "Button", "name": "Subir a \"Escritorio\" (Alt + Flecha arriba)", "zone": "TL"},
            {"i": 6, "kind": "Button", "name": "Actualizar \"iconos grandes\" (F5)", "zone": "TR"},
            {"i": 7, "kind": "Edit", "name": "Cuadro de búsqueda", "value": "iconos grandes", "zone": "TR"},
            {"i": 10, "kind": "Hyperlink", "name": "Buscar \"iconos grandes\" en Ayuda y soporte técnico de Window",
             "state": "readonly", "zone": "TL"},
            {"i": 18, "kind": "ToolBar", "name": "Dirección: Panel de control", "zone": "T"},
            {"i": 20, "kind": "Pane", "name": "iconos grandes - Panel de control", "zone": "C"},
            {"i": 21, "kind": "Text", "name": "Ningún elemento coincide con el criterio de búsqueda.", "zone": "T"},
            {"i": 22, "kind": "TitleBar", "name": "iconos grandes - Panel de control", "zone": "T"},
        ],
        "text": {"TL": ["iconos grandes - Panel de control"], "TR": ["iconos grandes"]},
    }


class _Model:
    """A local model that answers the step with the given acts, in order, and records what it was asked."""

    def __init__(self, *acts: dict) -> None:
        self.acts = list(acts)
        self.payloads: list[dict] = []

    def _post_schema_object(self, payload: dict, label: str) -> object:
        if payload["messages"][0]["content"] != cu_step_prompt.STEP_PROMPT:
            return {"es": [], "en": []}
        self.payloads.append(copy.deepcopy(payload))
        return self.acts.pop(0) if self.acts else {"act": "none"}


def _opened(app: str) -> dict:
    return {"step": 1, "operation": "app.open", "appId": app, "ok": True, "changed": True}


def _validate(raw: dict, view: dict, goal: str, objective: str, history: list[dict] | None = None,
              last_failed: dict | None = None) -> dict:
    return cu_validate.validate_decision(
        raw, view=view, last_failed=last_failed, application_names=APPS, history=history or [_opened("Terminal")],
        goal=goal, objective=objective,
    )


TERMINAL_ASK = "en la terminal anda a configuracion y cambia el tema de la app a oscuro"


# ------------------------------------------------- (1) un clic vetado sobre un control con flecha abre su lista


def test_v3_38_the_click_on_new_tab_opens_its_list_instead_of_a_tab() -> None:
    for raw in ({"act": "click", "text": "Nueva pestaña"}, {"act": "click", "i": 2}):  # v3-38 by text, v3-39 by index
        step = _validate(raw, _terminal(), "ir a configuracion", TERMINAL_ASK)
        assert step["operation"] == "input.visible.click"
        assert step["arguments"] == {"label": "Nueva pestaña", "index": 2, "manner": "open"}
        assert step["reason"] == cu_validate.REASON_OPEN_LIST


def test_counter_case_a_new_tab_asked_for_presses_the_action_itself() -> None:
    step = _validate({"act": "click", "i": 2}, _terminal(), "ir a nueva pestaña", "en la terminal abrí una pestaña nueva")
    assert step["operation"] == "input.visible.click"
    assert "manner" not in step["arguments"]


def test_counter_case_a_split_button_whose_opening_failed_is_never_pressed() -> None:
    # A split button without ExpandCollapse: the worker answered cannot_open. The model gets its retry and the
    # control's own action (a new tab) is never pressed.
    failed = {"step": 2, "operation": "input.visible.click", "label": "Nueva pestaña", "index": 2, "manner": "open",
              "ok": False, "error": "cannot_open"}
    step = _validate({"act": "click", "i": 2}, _terminal(), "ir a configuracion", TERMINAL_ASK,
                     history=[_opened("Terminal"), failed], last_failed=failed)
    assert step["operation"] == "none" and step["code"] == "opens_elsewhere"
    assert step["code"] in computer_use._RETRIED


def test_an_entry_chosen_inside_the_open_list_goes_through_the_guards_of_a_click() -> None:
    opened = {"step": 2, "operation": "input.visible.click", "label": "Nueva pestaña", "index": 2, "manner": "open",
              "ok": True}
    step = _validate({"act": "click", "text": "Configuración"}, _terminal_list_open(), "ir a configuracion", TERMINAL_ASK,
                     history=[_opened("Terminal"), opened])
    assert step["operation"] == "input.visible.click" and step["arguments"]["label"] == "Configuración", step
    # The profile entry of that list opens another tab: still refused, and an expanded control is not reopened.
    refused = _validate({"act": "click", "i": 2}, _terminal_list_open(), "ir a configuracion", TERMINAL_ASK,
                        history=[_opened("Terminal"), opened])
    assert refused["operation"] == "none" and refused["code"] == "opens_elsewhere"


# ------------------------------------------------ (3) el reintento ofrece la lista del control rechazado


def test_retry_instruction_offers_the_arrow_of_the_rejected_control() -> None:
    arrow = cu_step_prompt._rejected_arrow({"act": "click", "i": 2}, _terminal(), None)
    assert arrow is not None and arrow["i"] == 2
    said = cu_step_prompt.retry_instruction("no vale", [], arrow)
    assert '{"act":"open","i":2}' in said and "none" not in said
    # Counter-case: a rejected control without arrow keeps the old instruction.
    assert cu_step_prompt._rejected_arrow({"act": "click", "i": 1}, _terminal(), None) is None
    assert "none si no hay ninguno" in cu_step_prompt.retry_instruction("no vale", [], None)


# ------------------------------------------------ (2) antes del none, una lista cerrada no abierta todavía


def test_v3_38_before_giving_up_the_collapsed_split_button_is_opened() -> None:
    # The window's search shortcut already left the Terminal as it was (sin efecto): the step is the model's, as in r18.
    dead = {"step": 2, "operation": "input.key.press", "key": "ctrl_k", "ok": True, "changed": True, "sameView": True}
    model = _Model({"act": "none"}, {"act": "none"})
    decision = computer_use.decide_step(
        model, objective=TERMINAL_ASK, goal="ir a configuracion", application="Terminal", success_check=None,
        view=_terminal(), history=[_opened("Terminal"), dead], budget_left=9, application_names=APPS,
    )
    assert decision["operation"] == "input.visible.click", decision
    assert decision["arguments"] == {"label": "Nueva pestaña", "index": 2, "manner": "open"}
    assert decision["reason"] == cu_unfold.REASON_UNFOLD_BEFORE_NONE


def test_counter_case_a_sub_goal_that_opened_two_lists_opens_no_third() -> None:
    history = [_opened("Terminal")] + [
        {"step": n, "operation": "input.visible.click", "label": name, "index": n, "manner": "open", "ok": True}
        for n, name in ((2, "Uno"), (3, "Dos"))
    ]
    assert cu_unfold._unfold_before_giving_up(_terminal(), history, "ir a configuracion", TERMINAL_ASK, None) is None
    # And the list already opened in this sub-goal is not opened again.
    once = [_opened("Terminal"), {"step": 2, "operation": "input.visible.click", "label": "Nueva pestaña", "index": 2,
                                  "manner": "open", "ok": True}]
    assert cu_unfold._unfold_before_giving_up(_terminal(), once, "ir a configuracion", TERMINAL_ASK, None) is None


def test_counter_case_a_window_without_collapsed_controls_ends_as_before() -> None:
    notepad = {
        "window": {"title": "Sin título: Bloc de notas", "process": "Notepad"},
        "controls": [
            {"i": 0, "kind": "MenuItem", "name": "Archivo", "zone": "TL"},
            {"i": 1, "kind": "Document", "name": "Editor de texto", "zone": "C"},
            {"i": 2, "kind": "Button", "name": "Cerrar", "zone": "TR"},
        ],
    }
    model = _Model({"act": "none"})
    decision = computer_use.decide_step(
        model, objective="en el bloc de notas haz algo raro", goal="hacer algo raro", application="Bloc de notas",
        success_check=None, view=notepad, history=[_opened("Bloc de notas")], budget_left=9, application_names=APPS,
    )
    assert decision["operation"] == "none"


def test_the_system_menu_and_the_title_bar_are_never_unfolded() -> None:
    view = _terminal()
    view["controls"] = [control for control in view["controls"] if control["i"] != 2] + [
        {"i": 30, "kind": "MenuItem", "name": "Sistema", "state": "collapsed", "zone": "TL"},
    ]
    assert cu_unfold._unfold_before_giving_up(view, [_opened("Terminal")], "ir a configuracion", TERMINAL_ASK, None) is None


# ------------------------------------------------ (4) la paleta de comandos, sólo para una orden


def test_v3_40_an_order_goes_to_the_command_palette_of_the_open_list() -> None:
    opened = {"step": 2, "operation": "input.visible.click", "label": "Nueva pestaña", "index": 2, "manner": "open",
              "ok": True}
    step = cu_unfold._order_lookup("dividir el panel en vertical", _terminal_list_open(), [_opened("Terminal"), opened])
    assert step is not None and step["arguments"]["label"] == "Paleta de comandos"
    assert step["reason"] == cu_unfold.REASON_COMMAND_SEARCH


def test_counter_case_a_content_search_never_goes_to_the_palette() -> None:
    assert cu_unfold._order_lookup("buscar hola", _terminal_list_open(), [_opened("Terminal")]) is None
    assert cu_unfold._order_lookup("ir a configuracion", _terminal_list_open(), [_opened("Terminal")]) is None


# ------------------------------------------------ (6) una opción de la vista se elige en su control


def test_v3_41_a_view_option_opens_the_control_that_shows_the_current_one() -> None:
    step = cu_rules.deterministic_step(
        goal="activar vista de iconos grandes", view=_control_panel(), history=[_opened("Panel de control")],
        application="Panel de control", objective="abre el panel de control y ponlo en vista de iconos grandes",
    )
    assert step is not None and step["operation"] == "input.visible.click"
    assert step["arguments"]["label"] == "Categoría"
    assert step["reason"] == cu_options.REASON_VIEW_OPTION


def test_v3_41_the_option_in_the_open_menu_is_chosen() -> None:
    view = _control_panel()
    view["controls"] += [
        {"i": 40, "kind": "MenuItem", "name": "Categoría", "zone": "TR"},
        {"i": 41, "kind": "MenuItem", "name": "Iconos grandes", "zone": "TR"},
        {"i": 42, "kind": "MenuItem", "name": "Iconos pequeños", "zone": "TR"},
    ]
    history = [_opened("Panel de control"),
               {"step": 2, "operation": "input.visible.click", "label": "Categoría", "index": 7, "ok": True}]
    step = cu_rules.deterministic_step(
        goal="activar vista de iconos grandes", view=view, history=history, application="Panel de control",
        objective="abre el panel de control y ponlo en vista de iconos grandes",
    )
    assert step is not None and step["operation"] == "input.visible.click"
    assert step["arguments"]["label"] == "Iconos grandes"


def test_v3_41_a_view_option_never_types_into_the_content_search() -> None:
    # Review 2 (finding 2): the window shows the option's control («Ver por: Categoría»), already pressed in this
    # sub-goal and its menu not showing the option: the content search is still never the route.
    pressed = {"step": 2, "operation": "input.visible.click", "label": "Categoría", "index": 7, "ok": True}
    step = cu_rules.deterministic_step(
        goal="activar vista de iconos grandes", view=_control_panel(), history=[_opened("Panel de control"), pressed],
        application="Panel de control", objective="abre el panel de control y ponlo en vista de iconos grandes",
    )
    assert not cu_lookup._searches_content(step), step


def test_counter_case_a_search_of_the_option_words_still_goes_to_the_search() -> None:
    step = cu_rules.deterministic_step(
        goal="buscar iconos grandes", view=_control_panel(), history=[_opened("Panel de control")],
        application="Panel de control", objective="en el explorador busca iconos grandes",
    )
    assert cu_lookup._searches_content(step)


def test_counter_case_the_calculator_mode_keeps_its_route() -> None:
    assert missions.view_option_named("modo cientifico") is None
    assert missions.view_option_named("vista previa") is None
    assert missions.view_option_named("vista de iconos grandes") == "iconos grandes"
    assert missions.view_option_named("ordenar por nombre") == "nombre"


# ------------------------------------------------ (7) el marco y la navegación nunca son resultado


def test_v3_41_the_window_title_and_navigation_are_no_result() -> None:
    view = _searched_panel()
    typed = [_opened("Panel de control"),
             {"step": 2, "operation": "input.text.type", "text": "iconos grandes", "ok": True}]
    assert cu_lookup._result_naming(view, "iconos grandes", typed) is None
    for control in view["controls"]:
        if control["kind"] in ("Pane", "TitleBar", "ToolBar") or control["name"].startswith(("Atrás", "Subir", "Actualizar")):
            assert cu_lookup._frame_of_the_window(view, control)


def test_counter_case_a_list_item_that_appeared_after_typing_is_a_result() -> None:
    view = _searched_panel()
    view["controls"].append({"i": 30, "kind": "ListItem", "name": "Iconos grandes", "zone": "C"})
    typed = [_opened("Panel de control"),
             {"step": 2, "operation": "input.text.type", "text": "iconos grandes", "ok": True}]
    picked = cu_lookup._result_naming(view, "iconos grandes", typed)
    assert picked is not None and picked["arguments"]["label"] == "Iconos grandes"


# ------------------------------------------------ (8) traducir el reintento y la oferta de ayuda de la rutina


def test_v3_44_the_lookup_after_a_failed_click_uses_the_window_language() -> None:
    # Integración 20b: since r20b-8 «devices and printers» is a place of the table (the page Windows hands it to), so
    # its Spanish name comes from the table and the translator adds nothing new (``_lookup_translations`` never repeats
    # a name already said). Either way the retry's lookup on a Spanish window types the window's name, never the English.
    panel = _searched_panel()
    known = cu_languages._lookup_translations("devices and printers", lambda target: ("Dispositivos e impresoras",))
    assert known == ()
    assert cu_languages._name_to_look_up(
        "devices and printers", known, panel, [], "open devices and printers") == "dispositivos e impresoras"
    # A place the table does not know takes the translator's name, as v3-44 measured.
    names = cu_languages._lookup_translations("color filters", lambda target: ("Filtros de color",))
    assert names == ("Filtros de color",)
    assert cu_languages._lookup_translations("color filters", None) == ()
    assert cu_languages._name_to_look_up("color filters", names, panel, [], "open color filters") == "Filtros de color"


def test_v3_44_a_routine_press_on_the_help_offer_is_refused() -> None:
    view = _searched_panel()
    step = {"operation": "input.visible.click", "arguments": {"label": view["controls"][4]["name"], "index": 10},
            "reason": "el resultado de la búsqueda"}
    assert cu_unfold._routine_opens_help(step, view, "ir a devices and printers", "ver la impresora predeterminada")
    # Counter-case: the person asks for the help.
    assert not cu_unfold._routine_opens_help(step, view, "ir a ayuda", "busca iconos grandes en la ayuda")


# ------------------------------------------------ revisión 1 de la palanca 6


def _word(focused_document: bool = True) -> dict:
    """Word con la cinta: dos listas de fuente y «Pegar» plegadas, la búsqueda de órdenes y el documento de la persona."""

    view = {
        "window": {"title": "Documento1 - Word", "process": "WINWORD"},
        "controls": [
            {"i": 0, "kind": "SplitButton", "name": "Pegar", "state": "collapsed", "zone": "TL"},
            {"i": 2, "kind": "ComboBox", "name": "Fuente", "state": "collapsed", "value": "Aptos", "zone": "TL"},
            {"i": 3, "kind": "ComboBox", "name": "Tamaño de fuente", "state": "collapsed", "value": "12", "zone": "TL"},
            {"i": 5, "kind": "Edit", "name": "¿Qué desea hacer?", "zone": "T"},
            {"i": 9, "kind": "Document", "name": "Documento1", "value": "Notas de la reunión del martes", "zone": "C"},
        ],
        "text": {"C": ["Notas de la reunión del martes"]},
    }
    if focused_document:
        view["window"]["focused"] = {"kind": "Document", "name": "Documento1", "value": "Notas de la reunión del martes"}
    return view


def _dead_key() -> dict:
    return {"step": 2, "operation": "input.key.press", "key": "ctrl_k", "ok": True, "changed": True, "sameView": True}


def test_review_1_a_reading_goal_never_opens_a_list_blind() -> None:
    model = _Model({"act": "none"}, {"act": "none"})
    decision = computer_use.decide_step(
        model, objective="en word decime cuantas palabras tiene", goal="leer la cantidad de palabras", application="Word",
        success_check=None, view=_word(), history=[_opened("Word"), _dead_key()], budget_left=9,
        application_names=APPS + ("Word",),
    )
    assert decision["operation"] == "none", decision
    assert cu_unfold._unfold_before_giving_up(_word(), [_opened("Word")], "leer la cantidad de palabras", None, None) is None
    # Counter-case: an order still opens the first collapsed list before giving up.
    unfolded = cu_unfold._unfold_before_giving_up(_word(), [_opened("Word")], "ir a configuracion", None, None)
    assert unfolded is not None and unfolded["arguments"]["manner"] == "open"


def test_review_2_the_order_is_never_typed_into_the_persons_document() -> None:
    pressed = {"step": 3, "operation": "input.visible.click", "label": "¿Qué desea hacer?", "index": 5, "ok": True}
    model = _Model({"act": "none"}, {"act": "none"})
    decision = computer_use.decide_step(
        model, objective="en word inserta una tabla", goal="insertar una tabla", application="Word", success_check=None,
        view=_word(), history=[_opened("Word"), _dead_key(), pressed], budget_left=9, application_names=APPS + ("Word",),
    )
    assert decision["operation"] != "input.text.type", decision
    step = cu_unfold._order_lookup("insertar una tabla", _word(), [_opened("Word"), pressed])
    assert step is not None and step["operation"] == "none" and step["code"] == cu_lookup.SEARCH_FOCUS_UNPROVEN


def test_review_2_the_shell_prompt_never_takes_the_order() -> None:
    pressed = {"step": 3, "operation": "input.visible.click", "label": "Paleta de comandos", "index": 22, "ok": True}
    step = cu_unfold._order_lookup("dividir el panel en vertical", _terminal(), [_opened("Terminal"), pressed])
    assert step is not None and step["operation"] == "none" and step["code"] == cu_lookup.SEARCH_FOCUS_UNPROVEN


def test_review_2_counter_case_the_palette_field_with_the_keyboard_takes_the_order() -> None:
    view = _terminal()
    field = {"i": 40, "kind": "Edit", "name": "Nombre del comando", "state": "focused", "zone": "T"}
    view["controls"].append(field)
    view["window"]["focused"] = dict(field)
    # The palette's field appeared with the press (the shell's «appeared»): the field it brought up has the keyboard.
    view["newText"] = ["Nombre del comando", "Dividir panel"]
    pressed = {"step": 3, "operation": "input.visible.click", "label": "Paleta de comandos", "index": 22, "ok": True,
               "surfaceChanged": True, "appeared": ["nombre del comando", "dividir panel"]}
    step = cu_unfold._order_lookup("dividir el panel en vertical", view, [_opened("Terminal"), pressed])
    assert step is not None and step["operation"] == "input.text.type"
    assert step["arguments"]["text"] == "dividir el panel en vertical"


def test_review_2_reading_and_checking_goals_are_no_orders() -> None:
    for goal in ("leer el perfil predeterminado", "decir cual es el tema", "verificar que quedo oscuro",
                 "confirmar que se guardo", "make sure it is dark", "cual es el tema?"):
        assert not cu_unfold._is_order_goal(goal), goal
        assert cu_unfold._order_lookup(goal, _terminal_list_open(), [_opened("Terminal")]) is None
    assert cu_unfold._is_order_goal("dividir el panel en vertical")


def _panel_without_view_button() -> dict:
    view = _control_panel()
    view["controls"] = [control for control in view["controls"] if control["name"] != "Categoría"]
    view["text"]["TR"] = ["Buscar en el Panel de control"]
    return view


def _panel_with_view_menu_open() -> dict:
    """The «Ver por: Categoría» control with its menu already open, the option not in it (another menu's entries)."""

    view = _control_panel()
    view["controls"] = [
        {**control, "state": "expanded"} if control["name"] == "Categoría" else control for control in view["controls"]
    ]
    return view


def _labelled_as(view: dict, label: str) -> dict:
    """The same window with the option's control labelled by another family's label («Ordenar por:»)."""

    view = copy.deepcopy(view)
    view["text"]["TR"] = [label if line == "Ver por:" else line for line in view["text"]["TR"]]
    return view


def test_review_3_an_order_or_view_option_with_its_control_shown_never_searches_content() -> None:
    # Review 2 (finding 2): the refusal holds only while the window shows the option's control, collapsed or open.
    # Review 3 of palanca 6 (finding 2): the control of the option's own family («Ver por:» for a view, «Ordenar por:»
    # for an order).
    pressed = {"step": 2, "operation": "input.visible.click", "label": "Categoría", "index": 7, "ok": True}
    for label, goals in (("Ver por:", ("ir a vista de iconos grandes", "activar vista de iconos grandes")),
                         ("Ordenar por:", ("hacer clic en ordenar por nombre", "ir a ordenar por fecha"))):
        for view, goal in ((_labelled_as(view, label), goal)
                           for view in (_control_panel(), _panel_with_view_menu_open()) for goal in goals):
            step = cu_rules.deterministic_step(
                goal=goal, view=view, history=[_opened("Panel de control"), pressed],
                application="Panel de control", objective="abre el panel de control y " + goal,
            )
            assert not cu_lookup._searches_content(step), (goal, step)


def test_review_3_going_to_a_view_option_opens_the_control_that_shows_it() -> None:
    step = cu_rules.deterministic_step(
        goal="ir a vista de iconos grandes", view=_control_panel(), history=[_opened("Panel de control")],
        application="Panel de control", objective="abre el panel de control y ponlo en vista de iconos grandes",
    )
    assert step is not None and step["arguments"]["label"] == "Categoría"
    assert step["reason"] == cu_options.REASON_VIEW_OPTION


def test_review_3_counter_case_a_place_without_option_words_is_still_looked_up() -> None:
    step = cu_rules.deterministic_step(
        goal="ir a opciones de energia", view=_panel_without_view_button(), history=[_opened("Panel de control")],
        application="Panel de control", objective="abre el panel de control y anda a opciones de energia",
    )
    assert cu_lookup._searches_content(step), step
    assert cu_lookup._searches_content({"operation": "input.visible.click",
                                            "arguments": {"label": "Lupa", "search": "nombre"}})


def test_review_2_a_field_named_as_the_search_of_orders_takes_the_order() -> None:
    view = _word(focused_document=False)
    view["window"]["focused"] = {"i": 5, "kind": "Edit", "name": "¿Qué desea hacer?"}
    pressed = {"step": 3, "operation": "input.visible.click", "label": "¿Qué desea hacer?", "index": 5, "ok": True}
    step = cu_unfold._order_lookup("insertar una tabla", view, [_opened("Word"), pressed])
    assert step is not None and step["operation"] == "input.text.type", step


# ------------------------------------------------ revisión 2 de la palanca 6


def _web_page() -> dict:
    """Escenario A: una página en Edge con un texto que empieza como una búsqueda de órdenes y la búsqueda del sitio
    con el foco."""

    field = {"i": 6, "kind": "Edit", "name": "Buscar en el sitio", "state": "focused", "zone": "T"}
    return {
        "window": {"title": "Inicio - Sitio - Microsoft Edge", "process": "msedge", "focused": dict(field)},
        "controls": [
            {"i": 2, "kind": "Text", "name": "¿Qué quieres hacer hoy?", "zone": "C"},
            {"i": 4, "kind": "Hyperlink", "name": "Ayuda", "zone": "C"},
            field,
        ],
        "text": {"C": ["¿Qué quieres hacer hoy?", "Ayuda"]},
    }


def test_review_2_1_a_text_that_starts_like_the_search_of_orders_is_never_pressed() -> None:
    view = _web_page()
    assert cu_unfold._command_search_control(view) is None
    model = _Model({"act": "none"}, {"act": "none"})
    decision = computer_use.decide_step(
        model, objective="cambia el idioma de la pagina a ingles", goal="cambiar el idioma a ingles",
        application="Edge", success_check=None, view=view, history=[_opened("Edge")], budget_left=9,
        application_names=APPS + ("Edge",),
    )
    assert decision.get("reason") != cu_unfold.REASON_COMMAND_SEARCH, decision
    assert decision["operation"] != "input.text.type", decision
    # Even after a press on that text, the order is never typed into the site's search.
    pressed = {"step": 2, "operation": "input.visible.click", "label": "¿Qué quieres hacer hoy?", "index": 2, "ok": True}
    step = cu_unfold._order_lookup("cambiar el idioma a ingles", view, [_opened("Edge"), pressed])
    assert step is None or step["operation"] != "input.text.type", step


def test_review_2_1_counter_case_the_whole_name_as_a_field_or_button_is_the_search_of_orders() -> None:
    for kind in ("Edit", "Button", "MenuItem"):
        view = _web_page()
        view["controls"][0] = {"i": 2, "kind": kind, "name": "¿Qué quieres hacer?", "zone": "T"}
        assert cu_unfold._command_search_control(view) is not None, kind
    view = _web_page()
    view["controls"][0] = {"i": 2, "kind": "Text", "name": "¿Qué quieres hacer?", "zone": "T"}
    assert cu_unfold._command_search_control(view) is None
    assert cu_unfold._command_search_control(_word()) is not None


def test_review_2_1_a_search_that_already_had_the_keyboard_never_takes_the_order() -> None:
    # Escenario B: «¿Qué desea hacer?» pressed and ok, the keyboard still in «Buscar en el documento», which had it
    # before the press (not among what the press made appear).
    view = _word(focused_document=False)
    field = {"i": 7, "kind": "Edit", "name": "Buscar en el documento", "state": "focused", "zone": "L"}
    view["controls"].append(field)
    view["window"]["focused"] = dict(field)
    pressed = {"step": 3, "operation": "input.visible.click", "label": "¿Qué desea hacer?", "index": 5, "ok": True,
               "surfaceChanged": True, "appeared": ["resultados"]}
    step = cu_unfold._order_lookup("insertar una tabla", view, [_opened("Word"), pressed])
    assert step is not None and step["operation"] == "none" and step["code"] == cu_lookup.SEARCH_FOCUS_UNPROVEN
    # Counter-case: the same kind of field, made to appear by the press, takes the order.
    pressed["appeared"] = ["buscar en el documento"]
    step = cu_unfold._order_lookup("insertar una tabla", view, [_opened("Word"), pressed])
    assert step is not None and step["operation"] == "input.text.type", step


def _settings() -> dict:
    """Contracaso de (6): Configuración de Windows, con su búsqueda y sin ningún control de opción de la vista."""

    return {
        "window": {"title": "Configuración", "process": "SystemSettings"},
        "controls": [
            {"i": 0, "kind": "Button", "name": "Atrás", "zone": "TL"},
            {"i": 2, "kind": "Edit", "name": "Buscar una configuración", "zone": "TL"},
            {"i": 4, "kind": "ListItem", "name": "Sistema", "zone": "L"},
            {"i": 5, "kind": "ListItem", "name": "Personalización", "zone": "L"},
            {"i": 6, "kind": "ListItem", "name": "Accesibilidad", "zone": "L"},
            {"i": 8, "kind": "ComboBox", "name": "Tema", "state": "collapsed", "zone": "C"},
        ],
        "text": {"TL": ["Configuración"], "C": ["Inicio"]},
    }


def test_review_2_2_a_place_named_like_a_view_is_looked_up_without_the_options_control() -> None:
    for goal in ("ir a vista de tareas", "activar vista de tareas", "hacer clic en vista de tareas",
                 "ir a vista de lectura"):
        step = cu_rules.deterministic_step(
            goal=goal, view=_settings(), history=[_opened("Configuración")], application="Configuración",
            objective="en configuracion " + goal,
        )
        assert step is not None and cu_lookup._searches_content(step), (goal, step)
    assert not cu_options._view_option_shown(_settings())
    assert cu_options._view_option_shown(_control_panel())
    assert cu_options._view_option_shown(_panel_with_view_menu_open())


# ------------------------------------------------ revisión 3 de la palanca 6


def _installed_apps() -> dict:
    """Hallazgo 2: Configuración en Aplicaciones instaladas, con la lista de orden de la persona («Ordenar por:»
    junto al ComboBox «Nombre») y ningún control de la vista."""

    return {
        "window": {"title": "Configuración", "process": "SystemSettings"},
        "controls": [
            {"i": 0, "kind": "Button", "name": "Atrás", "zone": "TL"},
            {"i": 2, "kind": "Edit", "name": "Buscar una configuración", "zone": "TL"},
            {"i": 4, "kind": "ListItem", "name": "Sistema", "zone": "L"},
            {"i": 5, "kind": "ListItem", "name": "Personalización", "zone": "L"},
            {"i": 7, "kind": "Edit", "name": "Buscar aplicaciones", "zone": "C"},
            {"i": 8, "kind": "Text", "name": "Ordenar por:", "zone": "C"},
            {"i": 9, "kind": "ComboBox", "name": "Nombre", "state": "collapsed", "zone": "C"},
            {"i": 10, "kind": "ListItem", "name": "Reproductor", "zone": "C"},
        ],
        "text": {"TL": ["Configuración"], "C": ["Aplicaciones instaladas", "Ordenar por:", "Nombre"]},
    }


def test_review_3_2_a_view_goal_never_opens_the_persons_order_list() -> None:
    for goal in ("ir a vista de tareas", "activar vista de tareas"):
        step = cu_rules.deterministic_step(
            goal=goal, view=_installed_apps(), history=[_opened("Configuración")], application="Configuración",
            objective="en configuracion " + goal,
        )
        assert step is not None and step.get("reason") != cu_options.REASON_VIEW_OPTION, (goal, step)
        assert step["arguments"].get("label") != "Nombre", (goal, step)
        assert cu_lookup._searches_content(step), (goal, step)
    assert not cu_options._view_option_shown(_installed_apps(), "vista de tareas")
    assert cu_options._view_option_shown(_installed_apps(), "ordenar por tamano")


def test_review_3_2_with_the_order_list_open_a_view_goal_still_searches() -> None:
    view = _installed_apps()
    view["controls"][6] = {**view["controls"][6], "state": "expanded"}
    view["controls"] += [{"i": 20, "kind": "ListItem", "name": "Nombre", "zone": "C"},
                         {"i": 21, "kind": "ListItem", "name": "Tamaño", "zone": "C"}]
    opened = {"step": 2, "operation": "input.visible.click", "label": "Nombre", "index": 9, "manner": "open", "ok": True}
    model = _Model({"act": "none"}, {"act": "none"})
    decision = computer_use.decide_step(
        model, objective="en configuracion activa la vista de tareas", goal="ir a vista de tareas",
        application="Configuración", success_check=None, view=view, history=[_opened("Configuración"), opened],
        budget_left=9, application_names=APPS + ("Configuración",),
    )
    assert decision["operation"] != "none", decision
    assert cu_lookup._searches_content(decision), decision


def test_review_3_2_counter_case_an_order_goal_opens_its_order_list() -> None:
    step = cu_rules.deterministic_step(
        goal="ir a ordenar por tamaño", view=_installed_apps(), history=[_opened("Configuración")],
        application="Configuración", objective="en configuracion ordena las aplicaciones por tamaño",
    )
    assert step is not None and step["arguments"]["label"] == "Nombre", step
    assert step["reason"] == cu_options.REASON_VIEW_OPTION
    assert missions.view_option_family("vista de iconos grandes") == "view"
    assert missions.view_option_family("ordenar por nombre") == "sort"
    assert missions.view_option_family("agrupar por tipo") == "group"
    assert missions.view_option_family("vista previa") is None


def test_retry_instruction_offers_done_before_the_arrow_when_the_act_creates_again() -> None:
    # Integración 20b (ronda 20 P4 con palanca 6): a rejected act that would create again what is already there offers
    # «done» first, even on a control with an arrow; without ``admits_done`` the arrow's opening is offered.
    arrow = cu_step_prompt._rejected_arrow({"act": "click", "i": 2}, _terminal(), None)
    assert arrow is not None
    said = cu_step_prompt.retry_instruction("no vale", [], arrow, admits_done=True)
    assert "elegí done citando lo que apareció" in said and '{"act":"open"' not in said
    assert '{"act":"open","i":2}' in cu_step_prompt.retry_instruction("no vale", [], arrow, admits_done=False)
