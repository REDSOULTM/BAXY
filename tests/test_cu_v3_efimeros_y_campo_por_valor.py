"""Ronda 20, palanca P7: lo efímero y el campo nombrado por su texto de ejemplo (pasada r18: v3-28, v3-10).

v3-28 (cu-universal-evidencia/v2-v3-28, model_calls request 7): el modelo pidió ``{"act":"open","i":8}`` sobre el
ComboBox «Fuente:» cerrado; la reescritura D1 (el combo cuyo valor nombra el objetivo se pone por su entrada) sólo
estaba en la rama del clic, y la lista abierta se cerró cuando la persona recuperó el frente. D1 se decide ahora por el
control al que va el acto, no por el verbo.

v3-10 (cu-universal-evidencia/v2-v3-10, model_calls request 8): la vista tenía el foco en el Edit «Buscar (presione
Entrar para el primer resultado)» con valor=«Buscar blocs de notas» (su texto de ejemplo) y el modelo respondió
``{"act":"type","text":"receta","field":"Buscar blocs de notas"}``; el validador sólo buscaba el campo por nombre y lo
rechazó. El campo se resuelve ahora por su valor cuando es el único escribible con el teclado o la caja de búsqueda.
"""

from __future__ import annotations

from baxy_mind import cu_validate

from test_cu_v3_combos_galerias import _CHARMAP, _V328_GOAL, _V328_REQUEST, _control


def _check(raw: dict, view: dict, goal: str, objective: str | None = None, history: list | None = None,
           last_failed: dict | None = None, apps: tuple[str, ...] = ("Mapa de caracteres",),
           application: str = "Mapa de caracteres") -> dict:
    return cu_validate.validate_decision(
        raw, view=view, last_failed=last_failed, application_names=apps, history=history or [], goal=goal,
        objective=objective or goal, application=application,
    )


# ------------------------------------------------------------------ v3-28: D1 por destino, no por verbo
def test_v3_28_the_arrow_of_the_closed_font_list_sets_the_value_the_goal_names():
    decision = _check({"act": "open", "i": 8}, _CHARMAP, _V328_GOAL, _V328_REQUEST)
    assert decision["operation"] == "input.text.type"
    assert decision["arguments"] == {"text": "Wingdings", "field": "Fuente", "replace": True, "entry": True}


def test_a_context_menu_on_the_closed_font_list_is_the_same_pick():
    decision = _check({"act": "menu", "i": 8}, _CHARMAP, _V328_GOAL, _V328_REQUEST)
    assert decision["operation"] == "input.text.type"
    assert decision["arguments"]["entry"] is True and decision["arguments"]["text"] == "Wingdings"


def test_opening_the_font_list_without_a_value_named_stays_an_open():
    # Contracase: «abrí la lista de fuentes» names no value; the arrow is the model's act as it was.
    decision = _check({"act": "open", "i": 8}, _CHARMAP, "abrir la lista de fuentes", "abrí la lista de fuentes")
    assert decision["operation"] == "input.visible.click"
    assert decision["arguments"] == {"label": "Fuente:", "index": 8, "manner": "open"}


def test_a_third_identical_open_is_still_cut_by_the_guard():
    # Contracase: the same open that just failed is not sent again.
    failed = {"operation": "input.visible.click", "label": "Fuente:", "index": 8, "manner": "open", "ok": False}
    decision = _check({"act": "open", "i": 8}, _CHARMAP, "abrir la lista de fuentes", "abrí la lista de fuentes",
                      last_failed=failed)
    assert decision["operation"] == "none"


def test_after_the_entry_failed_on_that_box_the_open_is_the_models_step():
    # The pick by entry failed on «Fuente:»: the arrow is the model's step as it was, never the same guess again.
    failed = {"operation": "input.text.type", "field": "Fuente", "ok": False}
    decision = _check({"act": "open", "i": 8}, _CHARMAP, _V328_GOAL, _V328_REQUEST, last_failed=failed)
    assert decision["operation"] == "input.visible.click"
    assert decision["arguments"]["manner"] == "open"


def test_a_split_button_or_a_menu_with_a_submenu_is_never_rewritten_to_an_entry():
    # Contracase: no combo box, no combo_value pick, even when the goal says «X a Y» after its name.
    view = {"window": {"title": "Terminal", "process": "terminal"}, "controls": [
        _control(2, "SplitButton", "Nueva pestaña", "collapsed", zone="T"),
        _control(3, "MenuItem", "Fuente", "collapsed", zone="T"),
    ]}
    for index, label in ((2, "Nueva pestaña"), (3, "Fuente")):
        decision = _check({"act": "open", "i": index}, view, "cambia la fuente a consolas", "cambia la fuente a Consolas",
                          apps=("Terminal",), application="Terminal")
        assert decision["operation"] == "input.visible.click"
        assert decision["arguments"] == {"label": label, "index": index, "manner": "open"}


# ------------------------------------------------------------------ v3-10: el campo nombrado por su valor
_ONENOTE_GOAL = "search my onenote notebooks for receta"
_SEARCH_FIELD = "Buscar (presione Entrar para el primer resultado)"

# The view of request 8 of v3-10 (the first controls of the 30 listed; the focus line as the prompt said it).
_ONENOTE = {
    "window": {
        "title": "Sin título - OneNote", "process": "ONENOTE",
        "focused": {"kind": "Edit", "name": _SEARCH_FIELD, "value": "Buscar blocs de notas"},
    },
    "controls": [
        _control(0, "Hyperlink", "Ninguna coincidencia en: todos los blocs de notas", "readonly", zone="TR"),
        _control(1, "Hyperlink", "Buscar en la página (Ctrl+B)", "readonly", zone="TR"),
        _control(2, "MenuItem", "Personalizar barra de herramientas de acceso rápido", "collapsed", zone="TL"),
        _control(3, "MenuItem", "Escriba para buscar y use las teclas de dirección arriba y a", "collapsed", zone="T"),
        _control(4, "Edit", "Búsqueda de Microsoft", zone="T", value="Buscar"),
        _control(5, "MenuItem", "APELLIDO EJEMPLO PERSONA A", "collapsed", zone="TR"),
        _control(9, "Button", "Pestaña Archivo", zone="TL"),
    ],
}
_PRESSED_SEARCH = [{"operation": "input.visible.click", "label": "Buscar", "ok": True}]


def _onenote(raw: dict, view: dict = _ONENOTE) -> dict:
    return _check(raw, view, _ONENOTE_GOAL, history=_PRESSED_SEARCH, apps=("OneNote",), application="OneNote")


def test_v3_10_the_search_field_named_by_its_example_text_takes_the_search():
    decision = _onenote({"act": "type", "text": "receta", "field": "Buscar blocs de notas"})
    assert decision["operation"] == "input.text.type"
    assert decision["arguments"] == {"text": "receta", "field": _SEARCH_FIELD, "replace": True}


def test_the_persons_draft_in_a_message_box_is_never_a_field_by_its_value():
    # Contracase: «hola» is the person's draft in a message box with the keyboard; the refusal stays.
    view = {"window": {"title": "Chat", "process": "chat",
                       "focused": {"kind": "Edit", "name": "Escribe un mensaje", "value": "hola"}},
            "controls": [_control(0, "Button", "Enviar", zone="BR")]}
    decision = _check({"act": "type", "text": "hola", "field": "hola"}, view, "escribir hola", apps=("Chat",),
                      application="Chat")
    assert decision["operation"] == "none"
    assert decision["code"] == "label_not_visible"


def test_a_field_without_the_keyboard_holding_the_persons_text_is_never_resolved_by_its_value():
    # Contracase: «Juan Pérez» is what the person wrote in «Nombre», which has no keyboard and is no search box.
    view = {"window": {"title": "Formulario", "process": "forms"},
            "controls": [_control(0, "Edit", "Nombre", zone="C", value="Juan Pérez"),
                         _control(1, "Button", "Aceptar", zone="BR")]}
    decision = _check({"act": "type", "text": "Ana", "field": "Juan Pérez"}, view, "poner ana en el nombre",
                      "poné Ana en el nombre", apps=("Formulario",), application="Formulario")
    assert decision["operation"] == "none"
    assert decision["code"] == "label_not_visible"


def test_the_refusal_names_the_field_that_has_the_keyboard():
    view = {**_ONENOTE, "window": {**_ONENOTE["window"],
                                   "focused": {"kind": "Edit", "name": _SEARCH_FIELD, "value": ""}}}
    decision = _onenote({"act": "type", "text": "receta", "field": "Buscar blocs de notas"}, view)
    assert decision["operation"] == "none"
    assert decision["code"] == "label_not_visible"
    assert f"«{_SEARCH_FIELD}»" in decision["reason"]


def test_a_password_with_that_value_is_never_written():
    view = {"window": {"title": "Cuenta", "process": "acct",
                       "focused": {"kind": "Edit", "name": "Contraseña", "value": "Contraseña", "state": "focused password"}},
            "controls": [_control(0, "Edit", "Contraseña", "focused password", zone="C", value="Contraseña")]}
    decision = _check({"act": "type", "text": "x1", "field": "Contraseña"}, view, "escribir x1", apps=("Cuenta",),
                      application="Cuenta")
    assert decision["operation"] == "none"


# ------------------------------------------------------------------ revisión 2: nunca el cuerpo de un editor
def _editor(view: dict) -> dict:
    return _check({"act": "type", "text": "leche", "field": "Lista de compras"}, view,
                  "escribir leche en la lista de compras", apps=("Editor",), application="Editor")


def test_a_documents_body_holding_that_text_is_never_a_field_by_its_value():
    # Contracase (revisión 2, bloqueante d): the focused Document holds the person's «Lista de compras»; replacing it
    # by its value would wipe the document. The refusal stays as in the base.
    view = {"window": {"title": "Notas - Editor", "process": "editor",
                       "focused": {"kind": "Document", "name": "Editor de texto", "value": "Lista de compras"}},
            "controls": [_control(0, "Button", "Archivo", zone="TL")]}
    decision = _editor(view)
    assert decision["operation"] == "none"
    assert decision["code"] == "label_not_visible"


def test_an_edit_in_the_zone_of_the_focused_document_is_never_a_field_by_its_value():
    view = {"window": {"title": "Notas - Editor", "process": "editor",
                       "focused": {"kind": "Document", "name": "Documento", "zone": "C"}},
            "controls": [_control(0, "Edit", "Contenido de la página 1", "focused", zone="C", value="Lista de compras"),
                         _control(1, "Button", "Archivo", zone="TL")]}
    decision = _editor(view)
    assert decision["operation"] == "none"
    assert decision["code"] == "label_not_visible"


def test_a_plain_text_editors_edit_body_is_never_a_field_by_its_value():
    # The body of a plain-text editor is an Edit with the keyboard: tall in the view, or with no rectangle at all.
    body = {"kind": "Edit", "name": "Editor de texto", "value": "Lista de compras", "state": "focused", "zone": "C"}
    for rect in ({"x": 0, "y": 60, "w": 900, "h": 600}, None):
        control = {**body, "i": 0, **({"rect": rect} if rect else {})}
        view = {"window": {"title": "Notas - Editor", "process": "editor", "focused": dict(body)},
                "controls": [control, _control(1, "Button", "Archivo", zone="TL")]}
        decision = _editor(view)
        assert decision["operation"] == "none"
        assert decision["code"] == "label_not_visible"


def test_a_one_line_form_field_with_the_keyboard_is_still_named_by_its_example_text():
    # Contracase of the cut: a form's one-line Edit with the keyboard showing its example text keeps the rule.
    field = {"kind": "Edit", "name": "Nombre", "value": "Ej.: Juan Pérez", "state": "focused", "zone": "C"}
    view = {"window": {"title": "Formulario", "process": "forms", "focused": dict(field)},
            "controls": [{**field, "i": 0, "rect": {"x": 40, "y": 80, "w": 300, "h": 24}},
                         _control(1, "Button", "Aceptar", zone="BR")]}
    decision = _check({"act": "type", "text": "Ana", "field": "Ej.: Juan Pérez"}, view, "poner ana en el nombre",
                      "poné Ana en el nombre", apps=("Formulario",), application="Formulario")
    assert decision["operation"] == "input.text.type"
    assert decision["arguments"] == {"text": "Ana", "field": "Nombre", "replace": True}
