"""v3 combos-galerias (pasada r15b, sección D del diagnóstico: v3-27, v3-28, v3-29).

Gemelos con las vistas reales del Mapa de caracteres que el modelo vio (cu-universal-evidencia/v2-v3-28/model_calls.jsonl,
request 7) y sus contracasos: un clic en un combo cerrado cuyo valor nombra el objetivo se pone por su campo (la lista no
vive cuando la persona recupera el frente); un control deshabilitado se lista aparte, nunca se pulsa.
"""

from __future__ import annotations

from baxy_mind import computer_use as cu
from baxy_mind import cu_options
from baxy_mind import cu_validate
from baxy_mind import cu_step_prompt

_APPS = ("Mapa de caracteres",)


def _control(i: int, kind: str, name: str, state: str = "", zone: str = "C", value: str = "") -> dict:
    control: dict = {"i": i, "kind": kind, "name": name, "state": state, "zone": zone}
    if value:
        control["value"] = value
    return control


# The view of request 7 of v3-28 (25 controls; the Text labels and the system menu kept as they were listed).
_CHARMAP = {
    "window": {"title": "Mapa de caracteres", "process": "charmap"},
    "controls": [
        _control(0, "Edit", "Caracteres para copiar:", zone="C"),
        _control(1, "Button", "Seleccionar", zone="R"),
        _control(2, "CheckBox", "Vista avanzada", "on", zone="BL"),
        _control(3, "ComboBox", "Juego de caracteres:", "collapsed", zone="B"),
        _control(4, "Button", "Botón desplegable", zone="BR"),
        _control(5, "Edit", "Ir a Unicode:", zone="BR"),
        _control(6, "ComboBox", "Agrupar por:", "collapsed", zone="B"),
        _control(7, "Document", "Buscar:", zone="B"),
        _control(8, "ComboBox", "Fuente:", "collapsed", zone="T", value="Arial"),
        _control(9, "Button", "Ayuda", zone="TR"),
        _control(10, "Edit", "Carácter seleccionado", "readonly", zone="B"),
        _control(11, "MenuItem", "Sistema", "collapsed", zone="TL"),
        _control(12, "Button", "Minimizar", zone="TR"),
        _control(13, "Button", "Cerrar", zone="TR"),
        _control(14, "Pane", "Cuadrícula de caracteres", zone="C"),
        _control(15, "Text", "Caracteres para copiar:", zone="L"),
        _control(19, "Text", "Buscar:", zone="BL"),
        _control(21, "Text", "U+0021: Exclamación de cierre", zone="B"),
        _control(22, "Text", "Fuente:", zone="TL"),
    ],
    "text": {"R": ["Seleccionar", "Copiar"], "BR": ["Ir a Unicode:", "Buscar"]},
}
_V328_REQUEST = "en el mapa de caracteres cambia la fuente a Wingdings"
_V328_GOAL = "cambia la fuente a wingdings"


def _check(raw: dict, view: dict, goal: str, objective: str | None = None, history: list | None = None) -> dict:
    return cu_validate.validate_decision(
        raw, view=view, last_failed=None, application_names=_APPS, history=history or [], goal=goal,
        objective=objective or goal, application="Mapa de caracteres",
    )


# ------------------------------------------------------------------ D1: el combo cerrado se pone por su campo
def test_v3_28_a_click_on_the_closed_font_list_sets_the_value_the_goal_names():
    decision = _check({"act": "click", "i": 8}, _CHARMAP, _V328_GOAL, _V328_REQUEST)
    assert decision["operation"] == "input.text.type"
    # The request's own spelling, not the planner's lower-cased goal; the field by its label, replacing its value, and
    # only as one of the list's own entries («entry»: chosen by pattern, never written as free text).
    assert decision["arguments"] == {"text": "Wingdings", "field": "Fuente", "replace": True, "entry": True}


def test_the_value_is_read_after_the_box_name_in_english_too():
    view = {"window": {"title": "Character Map", "process": "charmap"},
            "controls": [_control(0, "ComboBox", "Font:", "collapsed", zone="T", value="Arial")]}
    decision = _check({"act": "click", "i": 0}, view, "set the font to Wingdings")
    assert decision["operation"] == "input.text.type"
    assert decision["arguments"]["text"] == "Wingdings" and decision["arguments"]["field"] == "Font"


def test_a_goal_without_a_value_keeps_the_click_that_opens_the_list():
    decision = _check({"act": "click", "i": 8}, _CHARMAP, "mostrar las fuentes", "muéstrame las fuentes del mapa de caracteres")
    assert decision["operation"] == "input.visible.click"
    assert decision["arguments"]["label"] == "Fuente:"


def test_another_closed_list_than_the_one_the_goal_names_is_only_clicked():
    # The goal sets the font; a click on «Agrupar por:» is the model's step as it was, never the font's value put there.
    decision = _check({"act": "click", "i": 6}, _CHARMAP, _V328_GOAL, _V328_REQUEST)
    assert decision["operation"] == "input.visible.click"
    assert decision["arguments"]["label"] == "Agrupar por:"


def test_a_list_already_showing_the_value_is_not_set_again():
    view = {**_CHARMAP, "controls": [
        _control(8, "ComboBox", "Fuente:", "collapsed", zone="T", value="Wingdings") if c["i"] == 8 else c
        for c in _CHARMAP["controls"]
    ]}
    decision = _check({"act": "click", "i": 8}, view, _V328_GOAL, _V328_REQUEST)
    assert decision["operation"] == "input.visible.click"


def test_a_read_only_closed_list_takes_its_entry_by_pattern():
    # Review of the branch (finding 2): «readonly» on a combo box is a list without text of its own (a drop-down list of
    # WPF, WinUI or Win32): exactly the box whose entry is chosen by pattern. Before the branch the click went through;
    # now the entry the goal names is chosen, never written.
    view = {**_CHARMAP, "controls": [
        _control(8, "ComboBox", "Fuente:", "collapsed readonly", zone="T", value="Arial") if c["i"] == 8 else c
        for c in _CHARMAP["controls"]
    ]}
    decision = _check({"act": "click", "i": 8}, view, _V328_GOAL, _V328_REQUEST)
    assert decision["operation"] == "input.text.type"
    assert decision["arguments"]["entry"] is True and decision["arguments"]["text"] == "Wingdings"


def test_a_read_only_list_with_a_percentage_takes_its_entry():
    # The reviewer's repro: «cambia el tamaño del texto a 125%» on a read-only «Tamaño del texto» list.
    view = {"window": {"title": "Configuración", "process": "systemsettings"},
            "controls": [_control(0, "ComboBox", "Tamaño del texto", "collapsed readonly", zone="C", value="100%")]}
    decision = _check({"act": "click", "i": 0}, view, "cambiar el tamaño del texto a 125%", "cambia el tamaño del texto a 125%")
    assert decision["operation"] == "input.text.type"
    assert decision["arguments"] == {"text": "125%", "field": "Tamaño del texto", "replace": True, "entry": True}


def test_the_model_typing_into_a_read_only_box_is_still_refused():
    # Contracase: only the entry rewritten from a click is chosen in a read-only box; a text the model types there is not.
    view = {**_CHARMAP, "controls": [
        _control(8, "ComboBox", "Fuente:", "collapsed readonly", zone="T", value="Arial") if c["i"] == 8 else c
        for c in _CHARMAP["controls"]
    ]}
    decision = _check({"act": "type", "text": "Wingdings", "field": "Fuente"}, view, _V328_GOAL, _V328_REQUEST)
    assert decision["operation"] == "none" and decision["code"] == "password_field"
    # Nor does an entry flag reach a field that is no list.
    readonly_edit = {**_CHARMAP, "controls": [*_CHARMAP["controls"], _control(30, "Edit", "Ruta", "readonly", zone="T")]}
    decision = _check({"act": "type", "text": "x", "field": "Ruta", "_entry": True}, readonly_edit, "poner x en ruta")
    assert decision["operation"] == "none"


def test_a_password_list_takes_nothing():
    view = {**_CHARMAP, "controls": [
        _control(8, "ComboBox", "Fuente:", "collapsed password", zone="T", value="Arial") if c["i"] == 8 else c
        for c in _CHARMAP["controls"]
    ]}
    decision = _check({"act": "click", "i": 8}, view, _V328_GOAL, _V328_REQUEST)
    assert decision["operation"] == "none" and decision["code"] == "password_field"


def test_after_the_entry_was_not_found_the_click_opens_the_list():
    # The list had no entry of that name: the next click on it is the model's step (the list opens), not the same guess.
    failed = {"operation": "input.text.type", "ok": False, "text": "Wingdings", "field": "Fuente", "error": "input_entry_not_found"}
    decision = cu_validate.validate_decision(
        {"act": "click", "i": 8}, view=_CHARMAP, last_failed=failed, application_names=_APPS, history=[failed],
        goal=_V328_GOAL, objective=_V328_REQUEST, application="Mapa de caracteres",
    )
    assert decision["operation"] == "input.visible.click"
    assert decision["arguments"]["label"] == "Fuente:"


# Review of the branch (finding 1): a chained or descriptive goal says more than a value after the box's name; the
# rest of the goal is never read as the value.
def test_combo_value_never_swallows_the_rest_of_the_goal():
    assert cu_options.combo_value("cambia la fuente a arial en el documento", None, "Fuente:") is None
    assert cu_options.combo_value("set the font to arial and type hello", None, "Font:") is None
    assert cu_options.combo_value("pon el tamaño en 12 y escribe hola", None, "Tamaño:") is None
    assert cu_options.combo_value("cambia la fuente a una mas grande", None, "Fuente:") is None
    assert cu_options.combo_value("cambia la fuente a otra", None, "Fuente:") is None
    assert cu_options.combo_value("set the font to a bigger one", None, "Font:") is None
    assert cu_options.combo_value("pon la fuente en arial, luego guarda", None, "Fuente:") is None
    # A name of several words stays one value.
    assert cu_options.combo_value("set the font to times new roman", "set the font to Times New Roman", "Font:") == "Times New Roman"


def test_a_chained_goal_keeps_the_click_on_the_list():
    view = {**_CHARMAP, "controls": [
        _control(8, "ComboBox", "Fuente:", "collapsed", zone="T", value="Calibri") if c["i"] == 8 else c
        for c in _CHARMAP["controls"]
    ]}
    for goal in ("cambia la fuente a wingdings y escribe hola", "set the font to wingdings and type hello"):
        decision = _check({"act": "click", "i": 8}, view, goal)
        assert decision["operation"] == "input.visible.click", goal


def test_a_word_that_is_no_entry_is_only_asked_as_an_entry():
    # «negrita» or «google gatos» read as values are only looked for among the list's entries (none so named: nothing
    # changes), never written into the box.
    decision = _check({"act": "click", "i": 8}, _CHARMAP, "pon la fuente en negrita")
    assert decision["operation"] == "input.text.type" and decision["arguments"]["entry"] is True
    search = {"window": {"title": "Buscar", "process": "app"},
              "controls": [_control(0, "ComboBox", "Buscar", "collapsed", zone="T", value="")]}
    decision = _check({"act": "click", "i": 0}, search, "buscar en google gatos")
    assert decision["operation"] != "input.text.type" or decision["arguments"].get("entry") is True


# Review of the branch (finding 4): the box showing the entry chosen by pattern is the change itself.
_SET = {**_CHARMAP, "controls": [
    _control(8, "ComboBox", "Fuente:", "collapsed", zone="T", value="Wingdings") if c["i"] == 8 else c
    for c in _CHARMAP["controls"]
]}


def test_v3_28_done_cites_the_entry_the_list_shows_now():
    history = [{"step": 1, "operation": "input.text.type", "ok": True, "text": "Wingdings", "field": "Fuente", "entry": True}]
    decision = _check({"act": "done", "evidence": "Wingdings"}, _SET, _V328_GOAL, _V328_REQUEST, history)
    assert decision["operation"] == "done"
    assert decision["arguments"]["evidence"] == "Wingdings"


def test_a_written_text_is_still_no_proof_of_itself():
    # Contracase: a text written into a box (no «entry») is on screen because it was written.
    for history in ([{"step": 1, "operation": "input.text.type", "ok": True, "text": "Wingdings", "field": "Fuente"}],
                    [{"step": 1, "operation": "input.text.type", "ok": True, "text": "Wingdings"}]):
        decision = _check({"act": "done", "evidence": "Wingdings"}, _SET, _V328_GOAL, _V328_REQUEST, history)
        assert decision["operation"] == "none"
    # Nor an entry the box does not show (the list kept Arial).
    history = [{"step": 1, "operation": "input.text.type", "ok": True, "text": "Wingdings", "field": "Fuente", "entry": True}]
    decision = _check({"act": "done", "evidence": "Wingdings"}, _CHARMAP, _V328_GOAL, _V328_REQUEST, history)
    assert decision["operation"] == "none"


def test_combo_value_reads_only_a_linked_short_value():
    assert cu_options.combo_value("cambia la fuente a wingdings", "cambia la fuente a Wingdings", "Fuente:") == "Wingdings"
    assert cu_options.combo_value("pon el tamaño en 12", None, "Tamaño:") == "12"
    assert cu_options.combo_value("cambia la fuente del documento", None, "Fuente:") is None
    assert cu_options.combo_value("abre la fuente", None, "Fuente:") is None
    assert cu_options.combo_value("cambia la fuente a una que se lea mejor en pantalla grande", None, "Fuente:") is None


# ------------------------------------------------------------------ D2: los deshabilitados se listan, no se pulsan
# The view of v3-29 after «copyright symbol» was typed: «Copiar» and «Buscar» drawn but disabled (10 Button in the
# tree, 7 in the view).
_WAITING = {**_CHARMAP, "disabled": [
    {"kind": "Button", "name": "Copiar", "state": "disabled", "zone": "R"},
    {"kind": "Button", "name": "Buscar", "state": "disabled", "zone": "BR"},
]}


def test_v3_29_the_disabled_buttons_are_listed_apart_as_waiting():
    shown = cu_step_prompt.compact_view_text(_WAITING, goal="buscar copyright symbol")
    line = next(line for line in shown.splitlines() if line.startswith("deshabilitados"))
    assert "Button «Copiar» R" in line and "Button «Buscar» BR" in line
    # No index: nothing in the prompt invites a click on them by number.
    assert all(not line.startswith(("Copiar", "Buscar")) for line in shown.splitlines())


def test_a_view_without_disabled_controls_has_no_such_line():
    assert "deshabilitados" not in cu_step_prompt.compact_view_text(_CHARMAP, goal="buscar copyright symbol")


def test_v3_29_the_disabled_find_button_is_the_prompts_and_never_pressed_by_its_name():
    # Estabilización R18: the veto «control_disabled» only repeated the prompt's own line («deshabilitados (se habilitan
    # con otro paso antes…)», above) and fired 0 times in every model call of cu-v3. Without it, a click by the disabled
    # button's name is a click by text like any other: it goes to the enabled control the view lists under that name
    # (here the field «Buscar:»), never to the disabled button, which the view does not list.
    decision = _check({"act": "click", "text": "Buscar"}, _WAITING, "buscar copyright symbol")
    assert decision["operation"] == "input.visible.click"
    assert decision["arguments"] == {"label": "Buscar:", "index": 7}
    assert "control_disabled" not in cu._RETRIED


def test_the_enabled_field_of_the_same_name_is_still_clicked():
    # «Buscar:» the Document is enabled and listed: a click on it by index stays the model's step.
    decision = _check({"act": "click", "i": 7}, _WAITING, "buscar copyright symbol")
    assert decision["operation"] == "input.visible.click"
    assert decision["arguments"]["label"] == "Buscar:"
