"""r25/r26: escribir en un campo que no tiene el foco, sin clic previo (libro de cuentas §4.1; banco x5, y4).

Con el frente devuelto a la persona, la vista se lee detrás y no dice dónde está el teclado. La regla «escribir» hacía
clic en el editor, el clic no se podía probar detrás y contaba como fallido; el modelo pedía lo correcto (type en
«Editor de texto») y el validador lo vetaba («no es un campo de la vista»).

r25 mandó el texto al campo por su nombre sólo «detrás» (window.foreground false) y aceptó el cuerpo con value "". En
el banco c25 ninguna de las dos ramas corrió: la vista que la App da a la mente (CompactForTheMind) no lleva
«foreground» ni un value vacío (evidencia_c25/v2-x5 seq 58, v2-y4 seq 56: input.visible.click.rule). r26 lee lo que la
vista sí lleva: donde no se lee NINGÚN foco, el texto va al único campo por su nombre (el proveedor lo entrega a ese
campo por valor o mensajes, o lo rechaza antes de todo efecto). Medido en vivo (evidencia_sub_r26a): x5 5,8 s, y4 4,7 s.
Con un foco leído (un botón, otro campo) la regla es la de v3: clic primero. Todo lo que decide una TECLA es v3 sin
tocar: tres revisiones adversariales (cu-v3/r26/rev*.md) mostraron que mover la tecla abre envíos sin confirmar; sus
sondas quedan aquí afirmando lo que v3 hace. Las vistas son las que llegan a la mente: sin «foreground», con «empty»
donde el proveedor leyó un valor vacío.
"""

from __future__ import annotations

from baxy_mind import cu_rules
from baxy_mind import cu_validate


def _control(i: int, kind: str, name: str, state: str = "", value: str | None = None, zone: str = "C", **more: object) -> dict:
    control: dict = {"i": i, "kind": kind, "name": name, "state": state, "zone": zone, **more}
    if value is not None:
        control["value"] = value
    return control


# El Bloc de notas abierto detrás de la ventana de la persona (c25 x5 paso 2), como lo recibe la mente: sin
# «foreground», nada «focused», el cuerpo leído vacío.
_NOTEPAD = {
    "window": {"title": "Sin título: Bloc de notas", "process": "Notepad"},
    "controls": [
        _control(0, "Document", "Editor de texto", empty=True),
        _control(2, "TabItem", "Sin título. No modificado.", zone="TL"),
        _control(7, "Button", "Agregar nueva pestaña", zone="TR"),
        _control(8, "MenuItem", "Archivo", "collapsed", zone="TL"),
        _control(9, "MenuItem", "Editar", "collapsed", zone="TL"),
        _control(13, "Button", "Negrita (Ctrl+N)", "off", zone="T"),
        _control(33, "Text", "Línea 1, Columna 1", zone="BL"),
        _control(34, "Text", "0 caracteres.", zone="BL"),
    ],
    "text": {"TL": ["Sin título", "Archivo", "Editar", "Ver"], "BL": ["Ln 1, Col 1", "0 caracteres."]},
}
_OPENED = [{"step": 1, "operation": "app.open", "appId": "Bloc de notas", "ok": True}]
_ASKED = {"key": "enter", "target": "message_composer"}


def _check(raw: dict, view: dict, goal: str, objective: str | None = None) -> dict:
    return cu_validate.validate_decision(
        raw, view=view, last_failed=None, application_names=("Bloc de notas",), history=list(_OPENED), goal=goal,
        objective=objective or goal, application="Bloc de notas",
    )


def _step(goal: str, view: dict, history: list[dict] | None = None, application: str = "x", **more: object) -> dict | None:
    return cu_rules.deterministic_step(goal=goal, view=view, history=history or [], application=application, **more)


def test_x5_y4_with_no_focus_read_the_text_goes_to_the_one_field_by_its_name_with_no_click_first():
    for goal, text in (("escribir hola BAXY", "hola BAXY"), ("escribir reunión a las 5", "reunión a las 5"),
                       ("escribir lista: pan", "lista: pan")):
        step = _step(goal, _NOTEPAD, list(_OPENED), "Bloc de notas")
        # Before (c24b, c25): {"operation": "input.visible.click", "arguments": {"label": "Editor de texto", "index": 0}},
        # which failed behind (visible_button_postread_unchanged) and ended the mission with no step.
        assert step is not None and step["operation"] == "input.text.type", (goal, step)
        # By its name: the App gives it the field's index and the provider never sends it by keys to another focus.
        assert step["arguments"] == {"text": text, "field": "Editor de texto"}, step
    # The mission's own document, with what it wrote (c1's «leche» after «lista: pan»), or one whose value was not
    # read: the same field v3 clicked and typed into, named and never replaced. Whose document it is, the shell decides
    # (ComputerUseLoopTests.R26ATextNamedForTheEditorWithoutTheKeyboardGoesToItsIndexAndNeverToRestoredContent).
    for document in (_control(0, "Document", "Editor de texto", value="lista: pan"), _control(0, "Document", "Editor de texto")):
        view = {**_NOTEPAD, "controls": [document, *_NOTEPAD["controls"][1:]]}
        assert _step("escribir leche", view, [], "Bloc de notas")["arguments"] == {"text": "leche", "field": "Editor de texto"}


def test_with_the_keyboard_read_on_a_button_the_field_is_clicked_first_as_in_v3():
    # r25 review (finding 1) and the r26 reviews' probe 7: the keyboard read on «Guardar», «Eliminar todo»: a text by
    # its label would leave the keyboard there and the Enter after it would press that button. The click first, as v3.
    for button in ("Guardar", "Eliminar todo", "Cerrar sesión"):
        for window in ({"focused": {"kind": "Button", "name": button, "i": 40}}, {}):
            view = {**_NOTEPAD, "window": {**_NOTEPAD["window"], **window},
                    "controls": [*_NOTEPAD["controls"], _control(40, "Button", button, "focused", zone="T")]}
            step = _step("escribir hola", view, list(_OPENED), "Bloc de notas")
            assert step is not None and step["operation"] == "input.visible.click", (button, step)
            assert step["arguments"] == {"label": "Editor de texto", "index": 0}


def test_a_password_never_takes_the_text_focused_or_not():
    focused = {"window": {"title": "Acceso", "process": "x"},
               "controls": [_control(0, "Edit", "Usuario", empty=True), _control(1, "Edit", "Contraseña", "focused password")]}
    assert _step("escribir hola", focused) is None
    # No focus read: the text names the one field that is no password, never the window's own focus.
    behind = {**focused, "controls": [focused["controls"][0], _control(1, "Edit", "Contraseña", "password")]}
    assert _step("escribir hola", behind)["arguments"] == {"text": "hola", "field": "Usuario"}
    # Only a password (or a password and two other fields) and no focus to read: v3 sent the text with no field, which
    # the provider types at the window's own focus (review 1, probes 1b and 1c). Never a text.
    only = {**focused, "controls": [_control(1, "Edit", "Contraseña", "password"), _control(2, "Button", "Entrar")]}
    assert _step("escribir hola", only) is None
    three = {**focused, "controls": [_control(0, "Edit", "Usuario"), _control(1, "Edit", "Contraseña", "password"),
                                     _control(2, "Edit", "Código")]}
    assert _step("escribir hola", three) is None
    # Contracase: with no password in the view the text at the caret stays the rule's step.
    plain = {**focused, "controls": [_control(0, "Edit", "Nombre"), _control(2, "Edit", "Código")]}
    assert _step("escribir hola", plain)["arguments"] == {"text": "hola"}


_NOTE = {"window": {"title": "Notas rápidas - OneNote", "process": "ONENOTE"},
         "controls": [_control(4, "Edit", "Título de página", value="Compras"), _control(9, "Button", "Compartir", zone="TR")]}


def test_the_title_of_a_note_the_request_does_not_name_is_neither_typed_into_nor_clicked_to_type():
    # v3-08, v3-11: the only field the view lists is the title of a page that was already there. Never by its label
    # and never the click that would put the keyboard there (v3 clicked it and, the focus unread, typed at that caret).
    assert _step("escribir leche", _NOTE, [], "OneNote", objective="en onenote escribí leche") is None
    on_it = {**_NOTE, "window": {**_NOTE["window"], "focused": {"kind": "Edit", "name": "Título de página", "i": 4}}}
    assert _step("escribir leche", on_it, [], "OneNote", objective="en onenote escribí leche") is None
    # Contracase: the request names the title: the field is clicked, as before, and then takes the text.
    named = _step("escribir compras", _NOTE, [], "OneNote", objective="en onenote escribe «Compras» como título")
    assert named is not None and named["operation"] == "input.visible.click", named
    assert named["arguments"] == {"label": "Título de página", "index": 4}


def test_a_name_two_fields_share_and_a_field_that_is_not_written_are_clicked_as_before():
    twins = {"window": {"title": "Formulario", "process": "x"},
             "controls": [_control(0, "Edit", "Horizontal", empty=True), _control(1, "ComboBox", "Horizontal", value="100")]}
    assert _step("escribir 5", twins)["operation"] == "input.visible.click"
    page = {"window": {"title": "Página", "process": "x"}, "controls": [_control(0, "Document", "Artículo", "readonly")]}
    assert _step("escribir 5", page)["operation"] == "input.visible.click"


def test_c1_the_models_type_into_the_named_editor_read_empty_is_accepted_as_an_insertion():
    raw = {"act": "type", "text": "lista: pan", "field": "Editor de texto"}
    decision = _check(raw, _NOTEPAD, "escribir lista: pan")
    # Before: none, «Editor de texto» no es un campo de la vista (label_not_visible), then none on the retry.
    assert decision["operation"] == "input.text.type", decision
    assert decision["arguments"] == {"text": "lista: pan", "field": "Editor de texto"}, "inserted, never replaced"


def test_n6_a_named_document_of_unknown_content_is_no_empty_body():
    # r25 review (finding 3): Word's view of the person's thesis lists its body with no value: unknown, never «empty».
    word = {
        "window": {"title": "Tesis final.docx - Word", "process": "WINWORD"},
        "controls": [_control(5, "Document", "Página 1 contenido"), _control(9, "Button", "Guardar", zone="TL")],
    }
    decision = cu_validate.validate_decision(
        {"act": "type", "text": "hola", "field": "Página 1 contenido"}, view=word, last_failed=None,
        application_names=("Word",), history=[], goal="escribir hola", objective="escribí hola", application="Word",
    )
    assert decision["operation"] == "none", decision


def test_a_named_editor_that_holds_the_persons_text_and_a_button_named_as_a_field_are_still_refused():
    view = {**_NOTEPAD, "controls": [_control(0, "Document", "Editor de texto", value="la casa roja, la casa azul")]
            + _NOTEPAD["controls"][1:]}
    assert _check({"act": "type", "text": "hola", "field": "Editor de texto"}, view, "escribir hola")["operation"] == "none"
    refused = _check({"act": "type", "text": "hola", "field": "Agregar nueva pestaña"}, _NOTEPAD, "escribir hola")
    assert refused["operation"] == "none" and refused.get("code") == "not_a_field", refused


# Discord detrás (c6, s14): el compositor y la búsqueda de mensajes; nada con el teclado.
_DISCORD = {
    "window": {"title": "@Ron92 - Discord", "process": "Discord"},
    "controls": [
        _control(3, "Hyperlink", "Ron92 (mensaje directo)", zone="L"),
        _control(20, "ComboBox", "Buscar .wolfsoultm.4191", zone="TR"),
        _control(31, "Edit", "Mensaje @Ron92", zone="B"),
    ],
    "text": {"B": ["Enviar mensaje a @Ron92"]},
}


def test_s14_c6_in_a_chat_the_message_box_is_still_clicked_before_typing():
    step = _step("escribir prueba BAXY C6", _DISCORD, [], "Discord")
    assert step is not None and step["operation"] == "input.visible.click", step
    assert step["arguments"] == {"label": "Mensaje @Ron92", "index": 31}
    # Clicked: the text goes in now, never the same click again, and never the search by its label.
    clicked = [{"step": 1, "operation": "input.visible.click", "label": "Mensaje @Ron92", "index": 31, "ok": True}]
    typed = _step("escribir prueba BAXY C6", _DISCORD, clicked, "Discord")
    assert typed is not None and typed["operation"] == "input.text.type" and "field" not in typed["arguments"], typed


def test_s1_a_box_whose_enter_sends_is_never_written_by_its_label_and_its_enter_asks():
    # Review 2 (R1, probe S1): the one field is a comment or reply box. By its label the text would be in the box with
    # the keyboard elsewhere. The box is clicked first, as in v3, by the reading that marks the key (the box with the
    # keyboard would be asked as a message); with the keyboard read on it, Enter carries the target RiskPolicy asks for.
    for name in ("Añade un comentario…", "Add a comment…", "Responder", "Reply", "Publicar una respuesta", "Post your reply",
                 "Enviar a Juan"):
        for window in ({"focused": {"kind": "Button", "name": "Me gusta", "i": 9}}, {}):
            view = {"window": {"title": "Publicación", "process": "x", **window},
                    "controls": [_control(5, "Edit", name, empty=True), _control(9, "Button", "Me gusta")]}
            step = _step("escribir muy bueno", view)
            assert step is not None and step["operation"] == "input.visible.click", (name, step)
            assert step["arguments"] == {"label": name, "index": 5}
        on_it = {"window": {"title": "Publicación", "process": "x", "focused": {"kind": "Edit", "name": name, "i": 5}},
                 "controls": [_control(5, "Edit", name, "focused"), _control(9, "Button", "Me gusta")]}
        assert _step("apretar enter", on_it)["arguments"] == _ASKED, name


def test_review_3_after_a_text_by_its_label_the_key_is_v3s_and_asks_where_the_focus_is_not_read():
    # Review 3 (N1a, N1b, N1c): boxes that send with a name no list knows, a one-field web form with a send button, a
    # search beside a draft of the person's. The text may go in by its label where no focus is read; the Enter after
    # it is decided by v3 untouched: with the focus not read it is asked, whatever click came before.
    for name in ("Aa", "Tu respuesta", "Mandar a Juan", "Compartir con Juan", "Di algo…", "Nota para Ron"):
        chat = {"window": {"title": "Chat con Juan", "process": "x"},
                "controls": [_control(5, "Edit", name, value="hola"), _control(6, "Button", "Adjuntar")]}
        clicked = [{"step": 2, "operation": "input.visible.click", "label": name, "index": 5, "ok": True}]
        for history in ([], clicked):
            assert _step("apretar enter", chat, history)["arguments"] == _ASKED, (name, history)
    form = {"window": {"title": "Contacto", "process": "x"},
            "controls": [_control(5, "Edit", "Tu correo", value="a@b.cl"), _control(6, "Button", "Suscribirme"), _control(7, "Button", "Enviar")]}
    clicked = [{"step": 2, "operation": "input.visible.click", "label": "Tu correo", "index": 5, "ok": True}]
    assert _step("apretar enter", form, clicked)["arguments"] == _ASKED
    draft = {"window": {"title": "Chat", "process": "x"},
             "controls": [_control(9, "Edit", "Buscar", value="hades"), _control(10, "Button", "Buscar"), _control(11, "ListItem", "@Ron"),
                          _control(12, "Edit", "Escribe un mensaje", value="borrador de la persona")]}
    searched = [{"step": 1, "operation": "input.text.type", "text": "hades", "field": "Buscar", "ok": True},
                {"step": 2, "operation": "input.visible.click", "label": "Buscar", "index": 10, "kind": "Button", "ok": True}]
    assert _step("buscar hades", draft, searched)["arguments"] == _ASKED
    assert _step("apretar enter", draft, searched)["arguments"] == _ASKED


def test_buscar_is_v3s_the_search_field_is_clicked_first():
    settings = {"window": {"title": "Configuración", "process": "SystemSettings", "requested": True},
                "controls": [_control(4, "Edit", "Cuadro de búsqueda, Buscar una opción", zone="T"),
                             _control(6, "ListItem", "Inicio", "selected", zone="TL")], "text": {}}
    opened = [{"step": 1, "operation": "app.open", "appId": "Configuración", "ok": True}]
    step = _step("buscar mouse", settings, opened, "Configuración")
    assert step is not None and step["operation"] == "input.visible.click", step
    assert step["arguments"] == {"label": "Cuadro de búsqueda, Buscar una opción", "index": 4}
