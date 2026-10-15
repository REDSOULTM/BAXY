"""v3 campo-texto: el campo correcto para escribir (pasada r9: v3-01, v3-04, v3-08, v3-11).

Gemelos de los casos con las vistas reales congeladas (los controles y el texto que el modelo vio en cada paso, de
cu-universal-evidencia/v2-<caso>/model_calls.jsonl y del journal) y sus contracasos de seguridad: buscar algo en una
app sí usa su buscador; un chat no recibe un texto que nadie confirmó.
"""

from __future__ import annotations

from baxy_mind import computer_use as cu
from baxy_mind import cu_creation
from baxy_mind import cu_validate
from baxy_mind.semantic import cu_buscar

_APPS = ("PowerPoint", "OneNote")


def _control(i: int, kind: str, name: str, state: str = "", value: str = "", zone: str = "C") -> dict:
    control: dict = {"i": i, "kind": kind, "name": name, "state": state, "zone": zone}
    if value:
        control["value"] = value
    return control


def _check(raw: dict, view: dict, goal: str, objective: str | None = None, history: list | None = None) -> dict:
    return cu_validate.validate_decision(
        raw, view=view, last_failed=None, application_names=_APPS, history=history or [], goal=goal,
        objective=objective or goal, application="PowerPoint",
    )


# ------------------------------------------------------------------ v3-01: escribir sobre un ListItem es pulsarlo
_BACKSTAGE = {
    "window": {"title": "PowerPoint", "process": "POWERPNT",
               "focused": {"kind": "ListItem", "name": "Presentación en blanco", "i": 12}},
    "controls": [
        _control(5, "ListItem", "Inicio", "selected", zone="TL"),
        _control(6, "ListItem", "Nuevo", zone="TL"),
        _control(7, "ListItem", "Abrir", zone="L"),
        _control(12, "ListItem", "Presentación en blanco", "selected focused", zone="L"),
        _control(13, "ListItem", "Presentación general de Cameo"),
        _control(17, "Button", "Recientes", zone="L"),
        _control(20, "Edit", "Buscar un archivo", zone="R"),
    ],
    "text": {"L": ["Abrir", "Presentación en blanco", "Recientes"], "C": ["Buscar un archivo"]},
}
_V301 = "abre powerpoint con una presentacion en blanco y en la primera diapo ponle de titulo Informe de ventas"


def test_v3_01_text_aimed_at_the_gallery_item_is_its_press():
    raw = {"act": "type", "text": "Informe de ventas", "field": "ListItem «Presentación en blanco»"}
    decision = _check(raw, _BACKSTAGE, _V301)
    assert decision["operation"] == "input.visible.click"
    assert decision["arguments"]["label"] == "Presentación en blanco"


def test_text_aimed_at_a_button_the_goal_does_not_name_is_refused():
    raw = {"act": "type", "text": "Informe de ventas", "field": "Recientes"}
    decision = _check(raw, _BACKSTAGE, _V301)
    assert decision["operation"] == "none"
    assert decision["code"] == "not_a_field"


# ------------------------------------------------------------------ v3-04: el buscador no recibe el título
_SLIDE = {
    "window": {"title": "Presentación1 - PowerPoint", "process": "POWERPNT",
               "focused": {"kind": "Edit", "name": "Búsqueda de Microsoft", "value": "Proyecto final", "i": 6}},
    "controls": [
        _control(1, "Button", "Guardar", zone="TL"),
        _control(6, "Edit", "Búsqueda de Microsoft", "focused", "Proyecto final", zone="T"),
        _control(8, "MenuItem", "\"Proyecto final\""),
        _control(9, "MenuItem", "Obtener ayuda sobre \"Proyecto final\""),
        _control(15, "TabItem", "Inicio", "selected", zone="TL"),
        _control(16, "TabItem", "Insertar", zone="TL"),
        _control(45, "Button", "Tarea siguiente", zone="B"),
    ],
    "text": {
        "T": ["p proyecto final", "Presentaciónl - PowerP..."],
        "C": ["Haga clic para agregar título", "Haga clic para agregar subtítulo"],
        "BL": ["Haga clic para agregar notas", "Diapositiva 1 de 1"],
    },
}
_V304_GOAL = "ponle 'Proyecto final' de título"
_V304 = (
    "abre powerpint, haz una presentación en blanco, ponle 'Proyecto final' de título y guárdala como proyecto-final "
    "en Documentos\\baxy-prueba-v3"
)


def test_v3_04_title_never_goes_into_the_search_box_it_presses_the_title_placeholder():
    raw = {"act": "type", "text": "Proyecto final", "field": "Búsqueda de Microsoft"}
    decision = _check(raw, _SLIDE, _V304_GOAL, _V304)
    assert decision["operation"] == "input.visible.click"
    assert decision["arguments"]["label"] == "Haga clic para agregar título"


def test_v3_04_typing_at_the_focused_search_box_goes_to_the_title_too():
    decision = _check({"act": "type", "text": "Proyecto final"}, _SLIDE, _V304_GOAL, _V304)
    assert decision["operation"] == "input.visible.click"
    assert decision["arguments"]["label"] == "Haga clic para agregar título"


def test_a_title_placeholder_control_takes_the_text_by_its_field():
    view = {**_SLIDE, "controls": [*_SLIDE["controls"], _control(52, "Edit", "Título 1")]}
    decision = _check({"act": "type", "text": "Proyecto final", "field": "Búsqueda de Microsoft"}, view, _V304_GOAL, _V304)
    assert decision["operation"] == "input.text.type"
    assert decision["arguments"]["field"] == "Título 1"
    assert decision["arguments"]["text"] == "Proyecto final"


def test_no_title_anywhere_is_an_honest_refusal_not_the_search_box():
    view = {**_SLIDE, "text": {"T": ["p proyecto final"]}}
    decision = _check({"act": "type", "text": "Proyecto final", "field": "Búsqueda de Microsoft"}, view, _V304_GOAL, _V304)
    assert decision["operation"] == "none"
    assert decision["code"] == "search_box_not_target"


def test_contracase_a_search_uses_the_app_search_box():
    # Lote r11 (v3-10): the app's search box is its search of content; «Búsqueda de Microsoft» is the box of its
    # commands and help (cu_lookup._command_box), used only for a goal that is a command.
    view = {
        **_SLIDE,
        "window": {**_SLIDE["window"], "focused": {"kind": "Edit", "name": "Buscar", "value": "", "i": 60}},
        "controls": [*_SLIDE["controls"], _control(60, "Edit", "Buscar", "focused", zone="L")],
    }
    raw = {"act": "type", "text": "Proyecto final", "field": "Buscar"}
    decision = _check(raw, view, "buscar Proyecto final", "busca Proyecto final en powerpoint")
    assert decision["operation"] == "input.text.type"
    assert decision["arguments"]["field"] == "Buscar"
    # The search typed at the box of commands and help, with no search of content in the view, is told what it is.
    raw = {"act": "type", "text": "Proyecto final", "field": "Búsqueda de Microsoft"}
    decision = _check(raw, _SLIDE, "buscar Proyecto final", "busca Proyecto final en powerpoint")
    assert decision["operation"] == "none" and decision["code"] == "command_box"


def test_contracase_a_message_box_never_takes_a_text_named_for_another_part():
    chat = {
        "window": {"title": "Chat", "process": "chat",
                   "focused": {"kind": "Edit", "name": "Buscar", "i": 1}},
        "controls": [
            _control(1, "Edit", "Buscar", "focused", zone="TL"),
            _control(2, "Edit", "Escribe un mensaje", zone="B"),
        ],
        "text": {"B": ["Escribe un mensaje"]},
    }
    decision = _check({"act": "type", "text": "Hola a todos", "field": "Buscar"}, chat, "ponle de título Hola a todos")
    assert decision["operation"] == "none"
    assert decision["code"] == "search_box_not_target"


# ------------------------------------------------------------------ un texto que no llega no se repite
# The history the App gives the mind (ComputerUseMission.HistoryForMind): step, operation, ok and, for a text, its
# «text», the «field» it named and the control that had the keyboard («into»).
def _typed(step: int, text: str, into: str, field: str | None = None) -> dict:
    item = {"step": step, "operation": "input.text.type", "ok": True, "text": text, "into": into}
    if field:
        item["field"] = field
    return item


def test_v3_04_the_same_text_into_the_same_field_is_not_sent_again():
    view = {**_SLIDE, "controls": [*_SLIDE["controls"], _control(52, "Edit", "Título 1", value="Proyecto final")]}
    history = [_typed(1, "Proyecto final", "Búsqueda de Microsoft", "Título 1")]
    decision = _check({"act": "type", "text": "Proyecto final", "field": "Título 1"}, view, "escribir Proyecto final", _V304)
    assert decision["operation"] == "input.text.type"
    decision = _check({"act": "type", "text": "Proyecto final", "field": "Título 1"}, view, "escribir Proyecto final", _V304,
                      history)
    assert decision["operation"] == "none"
    assert decision["code"] == "text_not_arriving"


def test_two_sends_to_the_focus_that_changed_nothing_stop():
    notepad = {
        "window": {"title": "Sin título - Bloc de notas", "process": "notepad",
                   "focused": {"kind": "Document", "name": "Editor de texto", "i": 3}},
        "controls": [_control(3, "Document", "Editor de texto", "focused")],
        "text": {},
    }
    history = [_typed(1, "hola", "Editor de texto"), _typed(2, "hola", "Editor de texto")]
    decision = _check({"act": "type", "text": "hola"}, notepad, "escribir hola", "escribe hola", history)
    assert decision["code"] == "text_not_arriving"
    first = _check({"act": "type", "text": "hola"}, notepad, "escribir hola", "escribe hola", history[:1])
    assert first["operation"] == "input.text.type"


def test_review_three_sends_into_the_named_field_stop_the_fourth():
    # Review r10 finding 3: three «Proyecto final» into «Título 1» (the field never showing it) gave a fourth.
    view = {**_SLIDE, "controls": [*_SLIDE["controls"], _control(52, "Edit", "Título 1")]}
    history = [_typed(n, "Proyecto final", "Búsqueda de Microsoft", "Título 1") for n in (1, 2, 3)]
    decision = _check({"act": "type", "text": "Proyecto final", "field": "Título 1"}, view, _V304_GOAL, _V304, history)
    assert decision["operation"] == "none"
    assert decision["code"] == "text_not_arriving"


def test_contracase_the_same_word_into_other_cells_is_no_repetition():
    # Review r10 finding 3: two «sí» typed into two cells must not stop the third cell's.
    sheet = {
        "window": {"title": "Libro1 - Hoja", "process": "sheet", "focused": {"kind": "Edit", "name": "D2", "i": 4}},
        "controls": [_control(4, "Edit", "D2", "focused")],
        "newText": ["sí"],
        "text": {},
    }
    history = [_typed(1, "sí", "B2"), _typed(2, "sí", "C2")]
    decision = _check({"act": "type", "text": "sí"}, sheet, "escribir sí en B2, C2 y D2", "escribe sí en B2, C2 y D2", history)
    assert decision["operation"] == "input.text.type"
    assert decision["arguments"]["text"] == "sí"


# ------------------------------------------------------------------ v3-08 / v3-11: la página nueva y su título
_NEW_PAGE = {
    "window": {"title": "Sin título - OneNote", "process": "ONENOTE",
               "focused": {"kind": "Document", "name": "Título de página", "value": "", "i": 36}},
    "controls": [
        _control(4, "Edit", "Búsqueda de Microsoft", value="Buscar", zone="T"),
        _control(24, "Button", "Nuevo cuaderno", zone="L"),
        _control(27, "TreeItem", "Nueva sección 1", "selected", "Nueva sección 1", zone="L"),
        _control(28, "TreeItem", "Crear una nueva sección", zone="L"),
        _control(31, "Button", "Agregar página", zone="T"),
        _control(32, "Button", "Ordenar páginas", zone="T"),
        _control(36, "Document", "Título de página", "focused", zone="TR"),
        _control(37, "Edit", "Fecha y hora de la página", zone="TR"),
        _control(47, "List", "Páginas"),
    ],
    "text": {},
}
_ADDED = [
    {"operation": "app.open", "ok": True, "appId": "OneNote"},
    {"operation": "input.visible.click", "ok": True, "label": "Agregar página", "changed": True},
]


def test_v3_08_the_new_page_is_reached_when_its_empty_title_takes_the_keyboard():
    decision = cu_creation._created_by_effect("creá una página nueva", _NEW_PAGE, _ADDED)
    assert decision is not None and decision["operation"] == "done"
    assert decision["arguments"]["evidence"] == "Título de página"


def test_v3_08_decide_step_ends_the_creation_without_the_model():
    class _NoModel:
        def __getattr__(self, name):
            raise AssertionError("el modelo no hace falta")

    decision = cu.decide_step(
        _NoModel(), objective="abrí onenote, creá una página nueva y ponele de título Lista del super",
        goal="creá una página nueva", application="OneNote", success_check=None, view=_NEW_PAGE, history=_ADDED,
        budget_left=7, application_names=_APPS, subgoal=0, subgoal_count=2,
    )
    assert decision["operation"] == "done"


def test_contracase_a_new_section_name_box_is_no_new_page():
    section = {
        **_NEW_PAGE,
        "window": {**_NEW_PAGE["window"], "focused": {
            "kind": "Edit", "name": "Cuadro de texto Nombre de sección", "value": "Nueva sección 1", "i": 29}},
    }
    history = [{"operation": "input.visible.click", "ok": True, "label": "Crear una nueva sección", "changed": True}]
    assert cu_creation._created_by_effect("creá una página nueva", section, history) is None


def test_contracase_a_title_that_holds_text_is_not_a_new_page():
    held = {**_NEW_PAGE, "window": {**_NEW_PAGE["window"], "focused": {
        "kind": "Document", "name": "Título de página", "value": "Compras", "i": 36}}}
    assert cu_creation._created_by_effect("creá una página nueva", held, _ADDED) is None


def test_v3_08_the_title_goes_into_the_page_title_placeholder():
    decision = _check(
        {"act": "type", "text": "Lista del super", "field": "Título de página"}, _NEW_PAGE,
        "ponele de título Lista del super", "abrí onenote, creá una página nueva y ponele de título Lista del super",
    )
    assert decision["operation"] == "input.text.type"
    assert decision["arguments"]["field"] == "Título de página"
    # A document is never replaced whole: the provider refuses a replace on one.
    assert "replace" not in decision["arguments"]


def test_v3_11_a_fragment_nobody_asked_for_is_no_section_name():
    view = {
        **_NEW_PAGE,
        "window": {**_NEW_PAGE["window"], "focused": {
            "kind": "Edit", "name": "Cuadro de texto Nombre de sección", "value": "Nueva sección 4", "i": 30}},
        "controls": [*_NEW_PAGE["controls"], _control(30, "Edit", "Cuadro de texto Nombre de sección", "focused",
                                                      "Nueva sección 4")],
    }
    decision = _check(
        {"act": "type", "text": "n", "field": "Cuadro de texto Nombre de sección"}, view, "crea una pagina nueva",
        "abre onenote, crea una pagina nueva y escribe comprar pan, leche y huevos",
    )
    assert decision["operation"] == "none"
    assert decision["code"] == "text_not_requested"


def test_text_slot_reads_the_part_and_never_a_search():
    assert cu_buscar.text_slot("ponle 'Proyecto final' de título") == "titulo"
    assert cu_buscar.text_slot("put Sales as the title") == "title"
    assert cu_buscar.text_slot("buscar el título Proyecto") is None
    assert cu_buscar.text_slot("guárdala como proyecto-final") is None


# ------------------------------------------------------------------ revisión r10: contracasos de seguridad
_CONTACTS = {
    "window": {"title": "Contactos", "process": "contacts",
               "focused": {"kind": "Edit", "name": "Buscar contactos", "i": 2}},
    "controls": [
        _control(2, "Edit", "Buscar contactos", "focused", zone="T"),
        _control(5, "Edit", "Nombre", value="María Pérez", zone="C"),
        _control(6, "Edit", "Teléfono", value="555 1234", zone="C"),
        _control(9, "Button", "Guardar", zone="TR"),
    ],
    "text": {},
}


def test_review_a_filter_by_name_never_writes_over_the_persons_name():
    # Finding 1: «por nombre» is how to filter, not a place; the text goes to the search box, «María Pérez» stays.
    goal = "filtrá los contactos por nombre Juan"
    for raw in ({"act": "type", "text": "Juan", "field": "Buscar contactos"}, {"act": "type", "text": "Juan"}):
        decision = _check(raw, _CONTACTS, goal)
        assert decision["operation"] == "input.text.type"
        assert decision["arguments"].get("field") in (None, "Buscar contactos")


def test_review_text_slot_reads_no_part_in_an_order_or_a_description():
    assert cu_buscar.text_slot("ordená la lista por nombre") is None
    assert cu_buscar.text_slot("mostrá los archivos de nombre largo") is None
    assert cu_buscar.text_slot("mostrá las notas de título largo") is None
    assert cu_buscar.text_slot("sort the files by name") is None
    assert cu_buscar.text_slot("ponele de título Lista del super") == "titulo"


def test_review_a_named_part_that_holds_text_is_never_replaced_by_a_redirect():
    # Finding 1: the part the goal names already holds text; the search box is no place for it and nothing is replaced.
    held = {**_CONTACTS, "controls": [*_CONTACTS["controls"][:1], _control(5, "Edit", "Nombre", value="María Pérez")]}
    decision = _check({"act": "type", "text": "Juan", "field": "Buscar contactos"}, held, "ponele Juan de nombre")
    assert decision["operation"] == "none"
    assert decision["code"] == "search_box_not_target"


def test_review_a_new_form_waiting_to_be_saved_is_no_creation():
    # Finding 2: a form opened by «Nuevo X» exists only once saved.
    event = {
        "window": {"title": "Calendario", "process": "calendar",
                   "focused": {"kind": "Edit", "name": "Agregar un título", "i": 3}},
        "controls": [_control(3, "Edit", "Agregar un título", "focused"), _control(8, "Button", "Guardar")],
        "text": {},
    }
    clicked = [{"step": 1, "operation": "input.visible.click", "ok": True, "label": "Nuevo evento", "changed": True}]
    assert cu_creation._created_by_effect("creá un evento nuevo el viernes a las 5", event, clicked) is None
    assert cu_creation._created_by_effect("creá un evento nuevo", event, clicked) is None
    contact = {
        "window": {"title": "Contactos", "process": "contacts", "focused": {"kind": "Edit", "name": "Nombre", "i": 5}},
        "controls": [_control(5, "Edit", "Nombre", "focused")],
        "text": {},
    }
    added = [{"step": 1, "operation": "input.visible.click", "ok": True, "label": "Nuevo contacto", "changed": True}]
    assert cu_creation._created_by_effect("agregá un contacto nuevo", contact, added) is None
    # Even a document part, with a control that saves on offer, is a form still to be saved.
    with_save = {**_NEW_PAGE, "controls": [*_NEW_PAGE["controls"], _control(60, "Button", "Guardar y cerrar")]}
    assert cu_creation._created_by_effect("creá una página nueva", with_save, _ADDED) is None


def test_review_a_page_title_seen_at_the_start_is_no_new_page():
    # Finding 6: an existing page showed «Título de página» on the first look; the App would refuse that citation.
    # The App folds the first look (ComputerUseSuccessCheck.LookText).
    seen = {**_NEW_PAGE, "firstLook": "sin titulo - onenote\ntitulo de pagina\nagregar pagina"}
    assert cu_creation._created_by_effect("creá una página nueva", seen, _ADDED) is None


def test_review_a_text_aimed_at_a_discarding_button_is_never_its_press():
    # Finding 5: neither the rest of the request nor a removing or discarding name makes a press of a text.
    view = {
        "window": {"title": "Borrador", "process": "mail", "focused": {"kind": "Document", "name": "Cuerpo", "i": 1}},
        "controls": [_control(1, "Document", "Cuerpo", "focused"), _control(2, "Button", "Descartar"),
                     _control(3, "Button", "Eliminar")],
        "text": {},
    }
    for name in ("Descartar", "Eliminar"):
        decision = _check({"act": "type", "text": "hola", "field": name}, view, "escribir hola",
                          f"escribí hola y si no sirve {name.lower()} el borrador")
        assert decision["operation"] == "none"
        assert decision["code"] == "not_a_field"
    # Not even when the sub-goal names it: a text never turns into a removal.
    decision = _check({"act": "type", "text": "hola", "field": "Eliminar"}, view, "escribir hola y eliminar")
    assert decision["code"] == "not_a_field"


def test_review_a_number_said_in_words_is_a_requested_value():
    # Finding 7: «2» for «dos» is the request's value; a stray letter at the focus is not.
    form = {
        "window": {"title": "Pedido", "process": "shop", "focused": {"kind": "Edit", "name": "Cantidad", "i": 4}},
        "controls": [_control(4, "Edit", "Cantidad", "focused")],
        "text": {},
    }
    decision = _check({"act": "type", "text": "2", "field": "Cantidad"}, form, "poné dos en cantidad")
    assert decision["operation"] == "input.text.type"
    assert decision["arguments"]["text"] == "2"
    stray = _check({"act": "type", "text": "n"}, form, "crea una pagina nueva",
                   "abre onenote, crea una pagina nueva y escribe comprar pan, leche y huevos")
    assert stray["operation"] == "none"
    assert stray["code"] == "text_not_requested"
