"""Ronda 20 P1: el texto sólo va al campo que el pedido nombra (pasada r18: v3-11 t2, v3-03).

v3-11 t2: «escribe ahí: comprar pan, leche y huevos» con el teclado en el «Título de página» vacío de la página «Sin
título» que ya existía; la regla «escribir» lo escribió en el título (la vista es la de OneNote en
cu-universal-evidencia/v2-v3-11/model_calls.jsonl). v3-03: «Búsqueda de Microsoft» con su texto de ejemplo «Buscar»,
Ctrl+A y el texto por teclado terminaron en una forma de la diapositiva (vista de v2-v3-03/model_calls.jsonl y el
journal: window.focused = Pane «MsoDockTop» con el Edit todavía «focused»). Con sus contracasos.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

from baxy_mind import cu_fields
from baxy_mind import cu_acts
from baxy_mind import cu_meaning
from baxy_mind import cu_first_look
from baxy_mind import cu_text_place
from baxy_mind import cu_lookup
from baxy_mind import cu_rules
from baxy_mind import cu_validate
from baxy_mind import cu_finals
from baxy_mind.semantic import missions
from baxy_mind.semantic.cu_buscar import names_an_item, slot_text, text_slot


def _control(i: int, kind: str, name: str, state: str = "", value: str = "", zone: str = "C") -> dict:
    control: dict = {"i": i, "kind": kind, "name": name, "state": state, "zone": zone}
    if value:
        control["value"] = value
    return control


def _copy(view: dict) -> dict:
    return json.loads(json.dumps(view))


# ------------------------------------------------------------------ v3-11 t2: la página que ya existía
_ONENOTE = {
    "window": {"title": "Sin título - OneNote", "process": "ONENOTE",
               "focused": {"kind": "Document", "name": "Título de página", "i": 39}},
    "controls": [
        _control(3, "Edit", "Búsqueda de Microsoft", value="Buscar", zone="T"),
        _control(9, "TabItem", "Inicio", zone="TL"),
        _control(10, "TabItem", "Insertar", zone="TL"),
        _control(29, "TreeItem", "Nueva sección 4", "selected", value="Nueva sección 4", zone="BL"),
        _control(34, "Button", "Agregar página", zone="T"),
        _control(36, "ListItem", "Sin título", "selected", zone="T"),
        _control(37, "Button", "Buscar", zone="TR"),
        _control(39, "Document", "Título de página", "focused", zone="TR"),
        _control(40, "Edit", "Fecha y hora de la página", zone="TR"),
        _control(50, "List", "Páginas"),
        _control(53, "Pane", "Página de OneNote", zone="R"),
    ],
    "text": {"T": ["Agregar página", "Sin título"]},
}
# The sub-goal's first look (the App's «firstLook», ``look_parts``) already showed this page and its empty title.
_ONENOTE["firstLook"] = "\n".join(cu_first_look.look_parts(_ONENOTE))
_V311_T2 = "escribir comprar pan, leche y huevos"


def test_v3_11_t2_the_rule_never_types_into_a_title_the_goal_does_not_name():
    step = cu_rules.deterministic_step(goal=_V311_T2, view=_ONENOTE, history=[], application="OneNote",
                                 objective="en OneNote, escribe ahi: comprar pan, leche y huevos")
    # Before: {"operation": "input.text.type", "arguments": {"text": "comprar pan, leche y huevos"}} into the title.
    assert step is None or step["operation"] != "input.text.type", step


def test_the_body_beside_the_title_is_clicked_first_and_then_takes_the_text():
    view = _copy(_ONENOTE)
    view["controls"].append(_control(41, "Document", "Contenido de la página", zone="R"))
    step = cu_rules.deterministic_step(goal=_V311_T2, view=view, history=[], application="OneNote")
    assert step is not None and step["operation"] == "input.visible.click"
    assert step["arguments"] == {"label": "Contenido de la página", "index": 41}
    # Clicked and still on the title: the model's step, never the same click again.
    clicked = [{"step": 1, "operation": "input.visible.click", "label": "Contenido de la página", "index": 41, "ok": True}]
    again = cu_rules.deterministic_step(goal=_V311_T2, view=view, history=clicked, application="OneNote")
    assert again is None or again["operation"] != "input.text.type"
    # Contracase: the keyboard now on the body of the page, the text goes in at the caret.
    body = _copy(view)
    body["window"]["focused"] = {"kind": "Document", "name": "Contenido de la página", "i": 41}
    body["controls"][7]["state"] = ""
    body["controls"][-1]["state"] = "focused"
    typed = cu_rules.deterministic_step(goal=_V311_T2, view=body, history=clicked, application="OneNote")
    assert typed == {"operation": "input.text.type", "arguments": {"text": "comprar pan, leche y huevos"},
                     "reason": "el objetivo lo dice"}


def test_contracase_a_goal_that_names_the_title_still_writes_there():
    for goal in ("ponele de título Lista del super", "escribe el título: Lista del super"):
        assert text_slot(goal) == "titulo"
        assert slot_text(goal) == "Lista del super"
        step = cu_rules.deterministic_step(goal=goal, view=_ONENOTE, history=[], application="OneNote")
        assert step is not None and step["operation"] == "input.text.type", (goal, step)
        assert step["arguments"]["text"] == "Lista del super"
        assert step["arguments"]["field"] == "Título de página"


def test_contracase_the_notepad_editor_is_no_named_part_and_takes_the_text_at_the_caret():
    notepad = {
        "window": {"title": "Sin título - Bloc de notas", "process": "notepad",
                   "focused": {"kind": "Document", "name": "Editor de texto", "i": 3}},
        "controls": [_control(3, "Document", "Editor de texto", "focused")],
        "text": {},
    }
    step = cu_rules.deterministic_step(goal="escribir hola mundo", view=notepad, history=[])
    assert step == {"operation": "input.text.type", "arguments": {"text": "hola mundo"}, "reason": "el objetivo lo dice"}


def _check(raw: dict, view: dict, goal: str, objective: str | None = None) -> dict:
    return cu_validate.validate_decision(
        raw, view=view, last_failed=None, application_names=("OneNote",), history=[], goal=goal,
        objective=objective or goal, application="OneNote",
    )


def test_v3_11_the_model_never_fills_an_existing_empty_title_the_request_does_not_name():
    raw = {"act": "type", "text": "comprar pan, leche y huevos", "field": "Título de página"}
    decision = _check(raw, _ONENOTE, _V311_T2, "en OneNote, escribe ahi: comprar pan, leche y huevos")
    assert decision["operation"] != "input.text.type", decision


def test_contracase_a_title_new_in_this_sub_goal_or_one_the_request_names_still_takes_the_text():
    raw = {"act": "type", "text": "Lista del super", "field": "Título de página"}
    fresh = {key: value for key, value in _ONENOTE.items() if key != "firstLook"}
    assert _check(raw, fresh, "escribir Lista del super")["operation"] == "input.text.type"
    named = _check(raw, _ONENOTE, "escribir Lista del super", "crea una pagina y ponele de titulo Lista del super")
    assert named["operation"] == "input.text.type"


# ------------------------------------------------------------------ v3-03: el foco viejo y el texto de ejemplo
_POWERPOINT = {
    "window": {"title": "Presentación1 - PowerPoint", "process": "POWERPNT",
               "focused": {"kind": "Pane", "name": "MsoDockTop"}},
    "controls": [
        _control(6, "MenuItem", "Escriba para buscar y use las teclas de dirección arriba y a", "collapsed", zone="T"),
        _control(7, "Edit", "Búsqueda de Microsoft", "focused", value="Buscar", zone="T"),
        _control(13, "TabItem", "Inicio", zone="TL"),
        _control(14, "TabItem", "Insertar", "selected", zone="TL"),
        _control(22, "TabItem", "Vista", zone="TR"),
        _control(28, "Button", "Nueva diapositiva", zone="TL"),
        _control(50, "Button", "Clasificador de diapositivas", "off", zone="BR"),
        _control(52, "Button", "Presentación con diapositivas", "off", zone="BR"),
    ],
    "text": {},
}
_CLICKED_SEARCH = {"step": 3, "operation": "input.visible.click", "label": "Búsqueda de Microsoft", "index": 7,
                   "ok": True, "kind": "Edit"}


def test_v3_03_a_focused_state_window_focused_contradicts_is_stale():
    assert cu_fields._focused_field(_POWERPOINT) is None
    after_select_all = [_CLICKED_SEARCH, {"step": 4, "operation": "input.key.press", "key": "ctrl_a", "ok": True}]
    step = cu_rules.deterministic_step(goal="ir a Organizador de diapositivas", view=_POWERPOINT, history=after_select_all)
    # Before: {"text": "Organizador de diapositivas"} by keyboard into the slide's shape.
    assert step is None or step["operation"] != "input.text.type" or step["arguments"].get("index") == 7, step


def test_contracase_a_field_window_focused_names_keeps_the_keyboard():
    view = _copy(_POWERPOINT)
    view["window"]["focused"] = {"kind": "Edit", "name": "Búsqueda de Microsoft", "value": "Buscar", "i": 7}
    assert cu_fields._focused_field(view)["name"] == "Búsqueda de Microsoft"
    # The same without an index from window.focused and in the list: the state is the only word, and it counts.
    bare = _copy(_POWERPOINT)
    del bare["window"]["focused"]
    assert cu_fields._focused_field(bare)["name"] == "Búsqueda de Microsoft"


def test_v3_03_a_search_box_holding_only_its_example_text_takes_the_name_by_its_index():
    view = _copy(_POWERPOINT)
    view["window"]["focused"] = {"kind": "Edit", "name": "Búsqueda de Microsoft", "value": "Buscar", "i": 7}
    step = cu_lookup._type_into(view, [_CLICKED_SEARCH], "Organizador de diapositivas", view["controls"][1])
    # Before: {"key": "ctrl_a"} and then the text by keyboard.
    assert step == {"operation": "input.text.type", "reason": cu_acts._REASON_FIND,
                    "arguments": {"text": "Organizador de diapositivas", "index": 7, "replace": True}}


def test_contracase_a_focused_field_with_a_real_leftover_and_no_index_is_still_selected_with_the_keyboard():
    settings = {
        "window": {"title": "Configuración", "process": "SystemSettings",
                   "focused": {"kind": "Edit", "name": "Cuadro de búsqueda, Buscar una opción", "value": "colorespantalla"}},
        "controls": [],
        "text": {},
    }
    assert cu_lookup._type_into(settings, [], "colores") == {"operation": "input.key.press", "arguments": {"key": "ctrl_a"},
                                                        "reason": cu_acts._REASON_FIND}
    # The example text without an index is no content: typed at the caret of the field in focus, no Ctrl+A.
    example = _copy(settings)
    example["window"]["focused"]["value"] = "Buscar"
    example["window"]["focused"]["name"] = "Buscar"
    assert cu_lookup._type_into(example, [], "colores") == {"operation": "input.text.type", "arguments": {"text": "colores"},
                                                       "reason": cu_acts._REASON_FIND}


_COLD = SimpleNamespace(state=cu_meaning.ENCODER_COLD)
_READY = SimpleNamespace(state="ready")
_V303_OBJECTIVE = "in powerpoint add a new slide and switch to slide sorter view"


def test_v3_03_a_wrong_translation_does_not_exempt_the_search_while_the_view_shows_a_similar_control():
    held = cu_lookup._held_for_the_encoder(
        _COLD, "slide sorter", (), ("Organizador de diapositivas",), None, _POWERPOINT, [], _V303_OBJECTIVE,
    )
    assert held is True
    click = cu_lookup._search_click(_POWERPOINT["controls"][1], "slide sorter")
    names = ("slide sorter", "Organizador de diapositivas")
    assert cu_lookup._blind_lookup(click, [], _POWERPOINT, names, _V303_OBJECTIVE) is True
    # Said in the window's language, the search stays the rule's step.
    assert cu_lookup._blind_lookup(click, [], _POWERPOINT, ("clasificador",), "pasa al clasificador de diapositivas") is False
    # Without the view (the model's fallback), the search click stays the literal step.
    assert cu_lookup._blind_lookup(click, []) is False


def test_contracase_a_ready_encoder_or_a_view_with_nothing_similar_keeps_the_search_as_before():
    assert cu_lookup._held_for_the_encoder(
        _READY, "slide sorter", (), ("Organizador de diapositivas",), None, _POWERPOINT, [], _V303_OBJECTIVE,
    ) is False
    unlike = _copy(_POWERPOINT)
    unlike["controls"] = [control for control in unlike["controls"] if "diapositiva" not in control["name"]]
    assert cu_lookup._held_for_the_encoder(
        _COLD, "slide sorter", (), ("Organizador de diapositivas",), None, unlike, [], _V303_OBJECTIVE,
    ) is False
    click = cu_lookup._search_click(unlike["controls"][1], "slide sorter")
    assert cu_lookup._blind_lookup(click, [], unlike, ("slide sorter", "Organizador de diapositivas"), _V303_OBJECTIVE) is False
    # Settings and «fuentes»: nothing on the home page shares a word with it.
    settings = {
        "window": {"title": "Configuración", "process": "SystemSettings"},
        "controls": [
            _control(0, "Edit", "Cuadro de búsqueda, Buscar una opción"),
            _control(1, "ListItem", "Sistema"),
            _control(2, "ListItem", "Personalización"),
        ],
        "text": {},
    }
    click = cu_lookup._search_click(settings["controls"][0], "fonts")
    assert cu_lookup._blind_lookup(click, [], settings, ("fonts", "fuentes"), "go to fonts in settings") is False


# ------------------------------------------------------------------ el final dice dónde quedó el texto
def test_v3_11_the_final_says_the_text_went_into_the_page_title():
    typed = [{"step": 1, "operation": "input.text.type", "text": "comprar pan, leche y huevos", "ok": True,
              "into": "Título de página"}]
    assert cu_finals._typed_into_unnamed_part(typed[0])
    assert cu_finals._typed_left(typed, False) == "; antes de parar escribí «comprar pan, leche y huevos» en «Título de página»"
    assert cu_finals._typed_left(typed, True) == "; before stopping I typed «comprar pan, leche y huevos» into «Título de página»"


def test_contracase_a_text_into_the_part_the_step_chose_or_into_a_body_is_told_as_before():
    chosen = {"step": 1, "operation": "input.text.type", "text": "Lista del super", "ok": True,
              "into": "Título de página", "field": "Título de página"}
    body = {"step": 2, "operation": "input.text.type", "text": "pan", "ok": True, "into": "Editor de texto"}
    assert not cu_finals._typed_into_unnamed_part(chosen) and not cu_finals._typed_into_unnamed_part(body)
    assert cu_finals._typed_left([chosen, body], False) == "; antes de parar escribí «Lista del super» y «pan»"


# ------------------------------------------------------------------ revisión 1 de la ronda 20 P1
_V311_OBJECTIVE = "en OneNote, escribe ahi: comprar pan, leche y huevos"


def test_review_1_the_model_never_types_at_the_caret_into_an_existing_title_the_request_does_not_name():
    # Hallazgo 1: sin «field», el texto iba al cursor, o sea al título de la página que ya existía.
    decision = _check({"act": "type", "text": "comprar pan, leche y huevos"}, _ONENOTE, _V311_T2, _V311_OBJECTIVE)
    assert decision["operation"] != "input.text.type", decision
    assert decision["code"] == "part_not_named"


def test_review_1_contracases_a_new_part_a_named_part_a_placeholder_line_or_the_body_take_the_text_at_the_caret():
    raw = {"act": "type", "text": "comprar pan, leche y huevos"}
    # A part this sub-goal brought (the first look did not show it).
    fresh = {key: value for key, value in _ONENOTE.items() if key != "firstLook"}
    assert _check(raw, fresh, _V311_T2, _V311_OBJECTIVE)["operation"] == "input.text.type"
    # A part the request names.
    named = _check(raw, _ONENOTE, _V311_T2, "en OneNote, ponele de titulo comprar pan, leche y huevos")
    assert named["operation"] == "input.text.type", named
    # A placeholder line is no one's text, even when the first look showed it.
    slide = _copy(_ONENOTE)
    slide["window"]["focused"] = {"kind": "Edit", "name": "Haga clic para agregar título", "i": 39}
    slide["controls"][7] = _control(39, "Edit", "Haga clic para agregar título", "focused", zone="TR")
    slide["firstLook"] = "\n".join(cu_first_look.look_parts(slide))
    assert _check(raw, slide, _V311_T2, _V311_OBJECTIVE)["operation"] == "input.text.type"
    # The keyboard on the page's body.
    body = _copy(_ONENOTE)
    body["window"]["focused"] = {"kind": "Document", "name": "Contenido de la página", "i": 41}
    body["controls"][7]["state"] = ""
    body["controls"].append(_control(41, "Document", "Contenido de la página", "focused", zone="R"))
    body["firstLook"] = "\n".join(cu_first_look.look_parts(body))
    assert _check(raw, body, _V311_T2, _V311_OBJECTIVE)["operation"] == "input.text.type"


_FORM = {
    "window": {"title": "Nueva tarea", "process": "tasks",
               "focused": {"kind": "Edit", "name": "Agregar un título", "i": 4}},
    "controls": [
        _control(4, "Edit", "Agregar un título", "focused"),
        _control(5, "Edit", "Descripción"),
        _control(6, "Button", "Guardar"),
    ],
    "text": {},
}


def test_review_2_a_text_delivered_to_the_field_the_step_chose_is_no_text_into_the_part_that_had_the_keyboard():
    # Hallazgo 2: el foco en «Agregar un título», el texto entregado por índice a «Descripción».
    decision = cu_validate.validate_decision(
        {"act": "type", "text": "Comprar pan", "field": "Descripción"}, view=_FORM, last_failed=None,
        application_names=(), history=[], goal="escribir Comprar pan de descripcion",
        objective="ponle de descripción Comprar pan",
    )
    assert decision["operation"] == "input.text.type" and decision["arguments"]["field"] == "Descripción", decision
    by_field = {"step": 1, "operation": "input.text.type", "text": "Comprar pan", "ok": True,
                "into": "Agregar un título", "field": "Descripción", "replace": True}
    by_index = {"step": 1, "operation": "input.text.type", "text": "Comprar pan", "ok": True,
                "into": "Agregar un título", "index": 5, "replace": True}
    for step in (by_field, by_index):
        assert not cu_finals._typed_into_unnamed_part(step)
        assert cu_finals._typed_left([step], False) == "; antes de parar escribí «Comprar pan»"
    # Contracase: the same text at the caret did go into the title.
    at_caret = {"step": 1, "operation": "input.text.type", "text": "Comprar pan", "ok": True, "into": "Agregar un título"}
    assert cu_finals._typed_into_unnamed_part(at_caret)
    assert cu_finals._typed_left([at_caret], False) == "; antes de parar escribí «Comprar pan» en «Agregar un título»"


def test_review_3_a_document_without_a_title_is_no_title_part_in_either_language():
    # Hallazgo 3: «Sin título» es el nombre del documento entero (su cuerpo), no su parte «título».
    for name in ("Sin título", "Documento sin título - Documentos de Google", "Presentación sin título",
                 "Untitled", "Untitled - Notepad", "No title", "Without title"):
        assert not cu_text_place._names_a_part(name), name
        assert not cu_finals._typed_into_unnamed_part({"operation": "input.text.type", "ok": True, "text": "x", "into": name})
    # Contracase: the parts themselves, in both languages.
    for name in ("Título de página", "Título 1", "Title", "Page title", "Subtítulo", "Encabezado", "Heading 2"):
        assert cu_text_place._names_a_part(name), name
    document = {
        "window": {"title": "Sin título - Editor", "process": "editor",
                   "focused": {"kind": "Document", "name": "Sin título", "i": 2}},
        "controls": [_control(2, "Document", "Sin título", "focused")],
        "text": {},
    }
    step = cu_rules.deterministic_step(goal="escribir hola mundo", view=document, history=[])
    assert step == {"operation": "input.text.type", "arguments": {"text": "hola mundo"}, "reason": "el objetivo lo dice"}
    english = _copy(document)
    english["window"]["focused"]["name"] = english["controls"][0]["name"] = "Untitled"
    step = cu_rules.deterministic_step(goal="escribir hello world", view=english, history=[])
    assert step == {"operation": "input.text.type", "arguments": {"text": "hello world"}, "reason": "el objetivo lo dice"}
    typed = {"step": 1, "operation": "input.text.type", "text": "hola mundo", "ok": True, "into": "Sin título"}
    assert cu_finals._typed_left([typed], False) == "; antes de parar escribí «hola mundo»"


# ------------------------------------------------------------------ revisión 2 de la ronda 20 P1
def test_review2_1_an_index_the_app_read_from_the_focus_is_no_choice_of_the_step():
    # Hallazgo 1 (v3-11 t2 real): la App le pone al texto el índice del foco (window.focused «i» = 39) y el recibo lo
    # copia; ese índice no lo eligió el paso, y el texto quedó en el título.
    at_caret = {"step": 2, "operation": "input.text.type", "text": "comprar pan", "ok": True,
                "into": "Título de página", "index": 39, "atCaret": True}
    assert cu_finals._typed_into_unnamed_part(at_caret)
    assert cu_finals._typed_left([at_caret], False) == "; antes de parar escribí «comprar pan» en «Título de página»"
    # Contracases: the index of the field the sub-goal's last click aimed at, and a field the step named.
    clicked = {key: value for key, value in at_caret.items() if key != "atCaret"}
    named = {**at_caret, "field": "Título de página"}
    assert not cu_finals._typed_into_unnamed_part(clicked) and not cu_finals._typed_into_unnamed_part(named)


def test_review2_1_a_text_the_mind_lets_go_into_a_part_names_that_part_as_its_field():
    # The part new in this sub-goal takes the text, and the step says it chose it (so the App's check sees a choice).
    fresh = {key: value for key, value in _ONENOTE.items() if key != "firstLook"}
    decision = _check({"act": "type", "text": "comprar pan, leche y huevos"}, fresh, _V311_T2, _V311_OBJECTIVE)
    assert decision["operation"] == "input.text.type"
    assert decision["arguments"] == {"text": "comprar pan, leche y huevos", "field": "Título de página"}
    # Contracases: a body is no part and stays at the caret; a part the view does not list (no index for its label in
    # the App) stays at the caret too, never a field the App would refuse.
    body = _copy(_ONENOTE)
    body["window"]["focused"] = {"kind": "Document", "name": "Contenido de la página", "i": 41}
    body["controls"][7]["state"] = ""
    body["controls"].append(_control(41, "Document", "Contenido de la página", "focused", zone="R"))
    assert _check({"act": "type", "text": "pan"}, body, "escribir pan")["arguments"] == {"text": "pan"}
    unlisted = _copy(fresh)
    del unlisted["controls"][7]
    assert _check({"act": "type", "text": "pan"}, unlisted, "escribir pan")["arguments"] == {"text": "pan"}


def test_review2_2_a_title_named_only_by_the_objective_is_where_the_rule_writes():
    # Hallazgo 2: «escribe «Compras» como título» es el sub-objetivo «escribir compras»; el título es del objetivo. La
    # regla hacía clic en el cuerpo y escribía ahí, y «Listo» con el título escrito en el cuerpo.
    view = _copy(_ONENOTE)
    view["controls"].append(_control(41, "Document", "Contenido de la página", zone="R"))
    for objective in ("escribe «Compras» como título", 'type "Groceries" as the title'):
        goal = missions.read_clause(objective)[0]
        assert text_slot(goal) is None and text_slot(objective) is not None, (goal, objective)
        step = cu_rules.deterministic_step(goal=goal, view=view, history=[], application="OneNote", objective=objective)
        assert step is not None and step["operation"] == "input.text.type", (objective, step)
        assert step["arguments"]["field"] == "Título de página", step
        typed = {"step": 1, "operation": "input.text.type", "ok": True, "text": step["arguments"]["text"],
                 "into": "Título de página", "field": "Título de página", "index": 39}
        assert not cu_finals._typed_into_unnamed_part(typed)
    # Contracase: the same view with a request that names no part clicks the body first.
    step = cu_rules.deterministic_step(goal=_V311_T2, view=view, history=[], application="OneNote", objective=_V311_OBJECTIVE)
    assert step is not None and step["operation"] == "input.visible.click"
    assert step["arguments"] == {"label": "Contenido de la página", "index": 41}


def test_review2_3_naming_an_item_is_no_text_into_a_part_of_a_document():
    # Hallazgo 3: el cuadro donde se renombra una pestaña se llama «Título de la pestaña»; renombrar no es escribir en
    # una parte de un documento, en ninguna app.
    for goal in ("renombrar la pestaña a pruebas", "ponle de nombre pruebas", "cambiale el nombre a pruebas",
                 "rename the tab to tests", "give it a name"):
        assert names_an_item(goal), goal
    for goal in ("escribir pruebas", "escribe el nombre del cliente", "ponele de titulo pruebas", "buscar pruebas"):
        assert not names_an_item(goal), goal
    terminal = {
        "window": {"title": "Windows PowerShell", "process": "WindowsTerminal",
                   "focused": {"kind": "Edit", "name": "Título de la pestaña", "value": "Windows PowerShell", "i": 8}},
        "controls": [
            _control(0, "TabItem", "Windows PowerShell", "selected"),
            _control(8, "Edit", "Título de la pestaña", "focused", value="Windows PowerShell"),
        ],
        "text": {},
    }
    terminal["firstLook"] = "\n".join(cu_first_look.look_parts(terminal))
    renamed = cu_validate.validate_decision(
        {"act": "type", "text": "pruebas"}, view=terminal, last_failed=None, application_names=[], history=[],
        goal="renombrar la pestaña a pruebas",
    )
    assert renamed["operation"] == "input.text.type", renamed
    # The name box is chosen as the field (the App's check sees the choice, never a text into an unnamed part).
    assert renamed["arguments"] == {"text": "pruebas", "field": "Título de la pestaña"}
    # Contracase: a request that names no item nor part does not write over that title at the caret.
    written = cu_validate.validate_decision(
        {"act": "type", "text": "pruebas"}, view=terminal, last_failed=None, application_names=[], history=[],
        goal="escribir pruebas",
    )
    assert written["operation"] != "input.text.type" and written["code"] == "part_not_named", written


# ------------------------------------------------------------------ revisión 3 de la ronda 20 P1
def _word(document: str, title: str) -> dict:
    return {
        "window": {"title": title, "process": "WINWORD",
                   "focused": {"kind": "Document", "name": document, "i": 50}},
        "controls": [
            _control(3, "Edit", "Buscar en documento", value="Buscar en documento", zone="T"),
            _control(45, "TabItem", "Inicio", "selected", zone="T"),
            _control(50, "Document", document, "focused", value="Introducción al proyecto"),
        ],
        "text": {},
    }


def test_review3_b1_a_document_named_like_a_part_by_its_file_is_the_document_itself():
    # B1: Word expone el cuerpo como el Document llamado como el archivo; «Proyecto de título» no es la parte título.
    for document, title in (("Proyecto de título", "Proyecto de título - Word"),
                            ("Proyecto de título", "Proyecto de título.docx  -  Modo de compatibilidad - Word"),
                            ("Seminario de Título - Capítulo 2", "Seminario de Título - Capítulo 2 - Word"),
                            ("Cover letter header", "Cover letter header - Word")):
        view = _word(document, title)
        view["firstLook"] = "\n".join(cu_first_look.look_parts(view))
        objective = "en Word escribe hola mundo"
        step = cu_rules.deterministic_step(goal="escribir hola mundo", view=view, history=[], application="Word",
                                     objective=objective)
        assert step == {"operation": "input.text.type", "arguments": {"text": "hola mundo"},
                        "reason": "el objetivo lo dice"}, (document, step)
        decision = cu_validate.validate_decision(
            {"act": "type", "text": "hola mundo"}, view=view, last_failed=None, application_names=("Word",),
            history=[], goal="escribir hola mundo", objective=objective, application="Word",
        )
        assert decision["operation"] == "input.text.type" and decision["arguments"] == {"text": "hola mundo"}, decision
        # The App's receipt marks the document itself («intoDocument»): the text reached it and the final says no part.
        typed = {"step": 1, "operation": "input.text.type", "text": "hola mundo", "ok": True, "into": document,
                 "index": 50, "atCaret": True, "intoDocument": True}
        assert not cu_finals._typed_into_unnamed_part(typed)
        assert cu_finals._typed_left([typed], False) == "; antes de parar escribí «hola mundo»"
    # Contracases: a part of a document keeps its name as a part, whatever the window is called.
    assert cu_text_place._names_the_window("Sin título", "Sin título: Bloc de notas")
    for name, title in (("Título de página", "Sin título - OneNote"), ("Título", "Sin título - OneNote"),
                        ("Título 1", "Proyecto de título - Word"), ("Título de la pestaña", "Windows PowerShell")):
        assert not cu_text_place._names_the_window(name, title), (name, title)
    step = cu_rules.deterministic_step(goal=_V311_T2, view=_ONENOTE, history=[], application="OneNote", objective=_V311_OBJECTIVE)
    assert step is None or step["operation"] != "input.text.type", step
    heading = _word("Proyecto de título", "Proyecto de título - Word")
    heading["window"]["focused"] = {"kind": "Edit", "name": "Encabezado", "i": 51}
    heading["controls"][2]["state"] = ""
    heading["controls"].append(_control(51, "Edit", "Encabezado", "focused", value="Universidad"))
    heading["firstLook"] = "\n".join(cu_first_look.look_parts(heading))
    decision = cu_validate.validate_decision(
        {"act": "type", "text": "hola mundo"}, view=heading, last_failed=None, application_names=("Word",),
        history=[], goal="escribir hola mundo", objective="en Word escribe hola mundo", application="Word",
    )
    assert decision["operation"] != "input.text.type" and decision["code"] == "part_not_named", decision


_CALENDAR = {
    "window": {"title": "Calendario", "process": "calendar", "focused": {"kind": "Button", "name": "Nuevo evento", "i": 2}},
    "controls": [_control(2, "Button", "Nuevo evento", "focused"), _control(5, "DataGrid", "Octubre de 2026")],
    "text": {},
}


def _event_form() -> dict:
    form = {
        "window": {"title": "Calendario", "process": "calendar",
                   "focused": {"kind": "Edit", "name": "Agregar un título", "i": 12}},
        "controls": [
            _control(12, "Edit", "Agregar un título", "focused"),
            _control(14, "Edit", "Fecha de inicio", value="9 de octubre de 2026"),
            _control(20, "Document", "Cuerpo del evento"),
            _control(22, "Button", "Guardar"),
        ],
        "text": {},
    }
    form["firstLook"] = "\n".join(cu_first_look.look_parts(_CALENDAR))
    return form


def test_review3_b2_the_rule_writes_in_a_vacant_part_new_in_this_sub_goal_as_the_validator_does():
    # B2: el formulario recién abierto, foco en su título vacío; la regla hacía clic en el cuerpo, que nadie pidió.
    form = _event_form()
    for objective in ("crea un evento y escribe Reunión con Ana", "crea un evento llamado Reunión con Ana en el calendario"):
        step = cu_rules.deterministic_step(goal="escribir Reunión con Ana", view=form, history=[], application="Calendario",
                                     objective=objective)
        assert step is not None and step["operation"] == "input.text.type", (objective, step)
        assert step["arguments"]["text"] == "Reunión con Ana"
        assert step["arguments"].get("field") in (None, "Agregar un título"), step
        decision = cu_validate.validate_decision(
            {"act": "type", "text": "Reunión con Ana"}, view=form, last_failed=None, application_names=(),
            history=[], goal="escribir Reunión con Ana", objective=objective, application="Calendario",
        )
        assert decision["operation"] == "input.text.type", decision
        assert decision["arguments"] == step["arguments"], (decision, step)
    # A placeholder line is no one's text for the rule either, even when the first look showed it.
    slide = _copy(_ONENOTE)
    slide["window"]["focused"] = {"kind": "Edit", "name": "Haga clic para agregar título", "i": 39}
    slide["controls"][7] = _control(39, "Edit", "Haga clic para agregar título", "focused", zone="TR")
    slide["controls"].append(_control(41, "Document", "Contenido de la página", zone="R"))
    slide["firstLook"] = "\n".join(cu_first_look.look_parts(slide))
    step = cu_rules.deterministic_step(goal=_V311_T2, view=slide, history=[], application="OneNote", objective=_V311_OBJECTIVE)
    assert step is not None and step["operation"] == "input.text.type", step
    # Contracases: the same empty title the first look already showed is the person's, and the body is clicked first;
    # and one that holds text the person wrote, new or not.
    shown = _event_form()
    shown["firstLook"] = "\n".join(cu_first_look.look_parts(shown))
    step = cu_rules.deterministic_step(goal="escribir Reunión con Ana", view=shown, history=[], application="Calendario",
                                 objective="escribe Reunión con Ana")
    assert step is not None and step["operation"] == "input.visible.click", step
    assert step["arguments"] == {"label": "Cuerpo del evento", "index": 20}
    held = _event_form()
    held["controls"][0]["value"] = "Cumpleaños de Ana"
    step = cu_rules.deterministic_step(goal="escribir Reunión con Ana", view=held, history=[], application="Calendario",
                                 objective="escribe Reunión con Ana")
    assert step is not None and step["operation"] == "input.visible.click", step
