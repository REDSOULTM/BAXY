"""Computer use: un editor abierto en su página de inicio (vivo v5/v6, 2026-10-07).

Excel y Word abrieron en su pantalla de inicio («Buenos días», «Libro/Documento en blanco», la lista de recientes y
«Buscar un archivo»); sus pestañas sólo existen con un documento abierto y el modelo pulsó «Inicio», «Cuenta» y
«Agregar un servicio» hasta rendirse. Una persona crea primero el documento en blanco que la página ofrece y después
va a la pestaña. Nunca un archivo reciente, nunca cuando la persona nombró un archivo suyo, nunca dos veces: lo que no
se puede se dice con su causa.
"""

from __future__ import annotations

import copy

import pytest

from baxy_mind import computer_use
from baxy_mind import cu_documents
from baxy_mind import cu_rules
from baxy_mind import cu_projection
from baxy_mind.semantic import missions


def _control(i: int, kind: str, name: str, state: str = "", rect: tuple[int, int, int, int] | None = None) -> dict:
    control: dict = {"i": i, "kind": kind, "name": name, "state": state, "value": None}
    if rect is not None:
        control["rect"] = {"x": rect[0], "y": rect[1], "w": rect[2], "h": rect[3]}
    return control


def _start_page(app: str = "Excel", blank: str = "Libro en blanco", blank_state: str = "selected focused") -> dict:
    """The live start page (journal 10:55:41Z), trimmed: the left column, the templates, the recent files."""

    controls = [
        _control(0, "MenuItem", "USUARIO DE PRUEBA", "collapsed", (588, 1, 63, 60)),
        _control(1, "Button", "Cerrar", "", (891, 1, 60, 60)),
        _control(2, "ListItem", "Inicio", "selected" if "focused" in blank_state else "selected focused", (9, 61, 89, 74)),
        _control(3, "ListItem", "Nuevo", "", (9, 140, 89, 74)),
        _control(4, "ListItem", "Abrir", "", (9, 219, 89, 74)),
        _control(5, "ListItem", "Cuenta", "", (9, 838, 89, 74)),
        _control(6, "ListItem", blank, blank_state, (158, 177, 225, 190)),
        _control(7, "ListItem", f"Le damos la bienvenida a {app}", "", (430, 177, 225, 190)),
        _control(8, "Button", "Recientes", "", (158, 422, 103, 38)),
        _control(9, "Edit", "Buscar un archivo", "", (688, 432, 508, 20)),
        _control(10, "ListItem", "YOUTUBE OFF MELI", "", (158, 506, 1039, 70)),
        _control(11, "ListItem", "Libro (1)", "", (158, 646, 1039, 70)),
        _control(12, "List", "Archivo", "", (9, 61, 89, 950)),
        _control(13, "Pane", "Vista Backstage", "", (98, 61, 853, 950)),
        _control(14, "Text", "Buenos días", "", (163, 61, 149, 51)),
        _control(15, "Group", "Nueva", "", (98, 112, 1159, 285)),
        _control(16, "List", "Plantillas", "", (158, 177, 1039, 190)),
        _control(17, "List", "Recientes", "", (158, 506, 1039, 700)),
    ]
    focused = next(control for control in controls if "focused" in control["state"].split())
    return {
        "window": {
            "title": app, "process": app.upper(), "processId": 10924, "requested": True,
            "rect": {"x": 8, "y": 0, "w": 944, "h": 1012},
            "focused": {"kind": focused["kind"], "name": focused["name"], "value": None},
        },
        "controls": controls,
        "controlCount": len(controls),
        "text": {"TL": [app, "Buenos días", "Inicio", "Nueva"], "L": [blank, "Recientes", "YOUTUBE OFF MELI"]},
    }


def _document_window() -> dict:
    return {
        "window": {"title": "Libro1 - Excel", "process": "EXCEL", "processId": 10924, "requested": True,
                   "rect": {"x": 8, "y": 0, "w": 944, "h": 1012}, "focused": {"kind": "DataItem", "name": "A1"}},
        "controls": [
            _control(0, "TabItem", "Archivo", "", (20, 60, 60, 30)),
            _control(1, "TabItem", "Inicio", "selected", (90, 60, 60, 30)),
            _control(2, "TabItem", "Insertar", "", (160, 60, 70, 30)),
            _control(3, "DataItem", "A1", "selected focused", (40, 200, 80, 20)),
        ],
        "controlCount": 4,
    }


OPENED = [{"step": 1, "operation": "app.open", "applicationName": "Excel", "ok": True}]


def _step(goal: str = "ir a la pestaña insertar", *, view: dict | None = None, history: list[dict] | None = None,
          objective: str = "en Excel andá a la pestaña Insertar", application: str = "Excel") -> dict | None:
    return cu_rules.deterministic_step(
        goal=goal, view=view if view is not None else _start_page(), history=history if history is not None else OPENED,
        application=application, objective=objective,
    )


class _NoModel:
    def _post_schema_object(self, payload, label):  # pragma: no cover - the test fails if the model is asked
        raise AssertionError("the start page's step needs no model")


# ------------------------------------------------------------------ crear el documento en blanco


@pytest.mark.parametrize(
    ("app", "blank", "goal", "objective"),
    [
        ("Excel", "Libro en blanco", "ir a la pestaña insertar", "en Excel andá a la pestaña Insertar"),
        ("Word", "Documento en blanco", "ir a la pestaña diseno", "en Word andá a la pestaña Diseño"),
        ("Word", "Blank document", "ir a la pestaña layout", "in Word go to the Layout tab"),
        ("Excel", "Libro en blanco", "hacer clic en la pestaña insertar", "en Excel hacé clic en la pestaña Insertar"),
    ],
)
def test_a_tab_asked_on_a_start_page_creates_the_focused_blank_item_with_enter(app, blank, goal, objective) -> None:
    step = _step(goal, view=_start_page(app, blank), objective=objective, application=app)

    assert step is not None
    assert step["operation"] == "input.key.press"
    # A named list item has the keyboard: Enter sends nothing to anyone, so no target that asks.
    assert step["arguments"] == {"key": "enter"}
    assert step["code"] == cu_documents.EXPECTS_TITLE_CHANGE


def test_the_live_failure_is_decided_without_the_model() -> None:
    decision = computer_use.decide_step(
        _NoModel(), objective="en Excel andá a la pestaña Insertar", goal="ir a la pestaña insertar", application="Excel",
        success_check="control:insertar:selected|title:insertar", view=_start_page(), history=OPENED, budget_left=10,
        application_names=("Excel", "Word"),
    )

    assert decision["operation"] == "input.key.press"
    assert decision["code"] == cu_documents.EXPECTS_TITLE_CHANGE


def test_a_blank_item_without_the_keyboard_is_clicked_once_and_never_acted_on_again() -> None:
    view = _start_page(blank_state="")
    first = _step(view=view)
    assert first is not None and first["operation"] == "input.visible.click"
    assert first["arguments"] == {"label": "Libro en blanco", "index": 6}
    assert first["code"] == cu_documents.EXPECTS_TITLE_CHANGE

    # Review 2026-10-07: the click may have created the document already (its window slow to come); an Enter after it
    # could create a second one. The start page still there after the wait is said, never acted on again.
    clicked = [*OPENED, {"step": 2, "operation": "input.visible.click", "label": "Libro en blanco", "index": 6, "ok": True}]
    for after in (_step(view=_start_page(), history=clicked), _step(view=view, history=clicked)):
        assert after is not None and after["operation"] == "none" and after["code"] == cu_documents.NO_DOCUMENT_OPEN


def test_enter_only_when_the_focused_element_is_the_offer_itself() -> None:
    # The offer's own state says focused, but the window's focus is elsewhere (another list item): a click, not Enter.
    view = _start_page()
    view["window"]["focused"] = {"kind": "ListItem", "name": "Inicio", "value": None}

    step = _step(view=view)

    assert step is not None and step["operation"] == "input.visible.click"
    assert step["arguments"]["label"] == "Libro en blanco"


def test_once_the_document_is_open_the_tab_is_clicked() -> None:
    entered = [*OPENED, {"step": 2, "operation": "input.key.press", "key": "enter", "ok": True}]

    step = _step(view=_document_window(), history=entered)

    assert step is not None
    assert step["operation"] == "input.visible.click"
    assert step["arguments"] == {"label": "Insertar", "index": 2}
    assert "code" not in step


def test_a_start_page_still_there_after_the_creation_is_said_never_entered_again() -> None:
    entered = [*OPENED, {"step": 2, "operation": "input.key.press", "key": "enter", "ok": True}]

    step = _step(history=entered)

    assert step is not None
    assert step["operation"] == "none"
    assert step["code"] == cu_documents.NO_DOCUMENT_OPEN


# ------------------------------------------------------------------ contracasos: nada se crea


@pytest.mark.parametrize(
    "objective",
    [
        "en Word abrí informe.docx y andá a la pestaña Diseño",
        "en Excel andá a la pestaña Insertar del libro Presupuesto",
        "in Excel open my budget workbook and go to the Insert tab",
        "en Word andá a la pestaña Diseño del archivo de la tesis",
    ],
)
def test_a_file_the_person_named_is_never_replaced_by_a_blank_one(objective) -> None:
    step = _step(objective=objective)

    assert step is not None
    assert step["operation"] == "none"
    assert step["code"] == cu_documents.NO_DOCUMENT_OPEN


def test_a_start_page_without_a_blank_item_creates_nothing_and_opens_no_recent_file() -> None:
    view = _start_page()
    view["controls"] = [control for control in view["controls"] if control["name"] != "Libro en blanco"]
    view["window"]["focused"] = {"kind": "ListItem", "name": "Inicio", "value": None}

    step = _step(view=view)

    assert step is None or step["operation"] not in {"input.key.press", "input.visible.click"}


def test_a_recent_file_named_like_a_blank_one_is_not_an_offer() -> None:
    view = _start_page()
    view["controls"] = [control for control in view["controls"] if control["name"] != "Libro en blanco"]
    # The person's own file, in the list of recent files, called «Plantilla en blanco»; the keyboard on it.
    view["controls"].append(_control(20, "ListItem", "Plantilla en blanco", "selected focused", (158, 716, 1039, 70)))
    view["window"]["focused"] = {"kind": "ListItem", "name": "Plantilla en blanco", "value": None}

    assert _step(view=view) is None


def _explorer_folder(*, with_list: bool = True, with_type: bool = True, with_headers: bool = False) -> dict:
    """File Explorer on «Descargas», extensions hidden: the person's file «Documento en blanco» has the keyboard."""

    item = _control(3, "ListItem", "Documento en blanco", "selected focused", (300, 220, 600, 24))
    if with_type:
        item["itemType"] = "Documento de Microsoft Word"
    controls = [
        _control(0, "TabItem", "Descargas", "selected", (10, 5, 200, 30)),
        _control(1, "TreeItem", "Escritorio", "", (10, 200, 200, 24)),
        _control(2, "ListItem", "Factura marzo", "", (300, 196, 600, 24)),
        item,
    ]
    if with_headers:
        controls += [_control(10, "HeaderItem", "Nombre", "", (300, 170, 200, 24)),
                     _control(11, "HeaderItem", "Fecha de modificación", "", (500, 170, 200, 24))]
    if with_list:
        controls.append(_control(12, "List", "Vista de elementos", "", (290, 160, 900, 700)))
    return {
        "window": {"title": "Descargas", "process": "explorer", "processId": 4242, "requested": True,
                   "rect": {"x": 0, "y": 0, "w": 1200, "h": 900},
                   "focused": {"kind": "ListItem", "name": "Documento en blanco", "value": None}},
        "controls": controls,
        "controlCount": len(controls),
    }


@pytest.mark.parametrize(
    ("with_list", "with_type", "with_headers"),
    [(True, True, False), (True, False, False), (False, True, False), (False, False, True)],
)
def test_a_file_named_like_a_blank_offer_in_a_folder_is_never_entered(with_list, with_type, with_headers) -> None:
    # Review 2026-10-07: in File Explorer, «andá a la pestaña Imágenes» on «Descargas» pressed Enter on the person's
    # file «Documento en blanco» (the recent-files guard only saw a list called «Recientes»). An offer is accepted only
    # outside every list but the offers' own, and never in a view that shows files (item types, file columns).
    view = _explorer_folder(with_list=with_list, with_type=with_type, with_headers=with_headers)

    step = _step(
        "ir a la pestaña imagenes", view=view, history=[], objective="en el explorador de archivos andá a la pestaña Imágenes",
        application="Explorador de archivos",
    )

    assert step is None or step.get("code") not in {cu_documents.EXPECTS_TITLE_CHANGE, cu_documents.NO_DOCUMENT_OPEN}
    assert step is None or step["operation"] != "input.key.press"


def test_an_offer_inside_an_unnamed_kind_of_list_is_no_offer() -> None:
    # The recent files' list carries no «Recientes» name (or it was cut from the capped view): its item is no offer.
    view = _start_page()
    view["controls"] = [control for control in view["controls"] if control["name"] != "Libro en blanco"]
    view["controls"].append(_control(20, "ListItem", "Documento en blanco", "", (158, 716, 1039, 70)))
    view["controls"].append(_control(21, "List", "Elementos", "", (158, 500, 1039, 400)))

    assert _step(view=view) is None


def test_two_blank_offers_are_not_guessed_between() -> None:
    view = _start_page()
    view["controls"].append(_control(20, "ListItem", "Presentación en blanco 4:3", "", (430, 177, 225, 190)))

    assert _step(view=view) is None


def test_a_window_whose_title_names_a_document_is_no_start_page() -> None:
    # The File view of an open document offers «Libro en blanco» too: the open document is where the tab is.
    view = _start_page()
    view["window"]["title"] = "Presupuesto - Excel"

    assert _step(view=view) is None


def test_only_a_tab_is_a_reason_to_create_never_a_plain_place_nor_the_browser() -> None:
    plain = _step("ir a insertar")
    assert plain is None or plain.get("code") != cu_documents.EXPECTS_TITLE_CHANGE
    browser = _step(application=missions.BROWSER_CATEGORY, objective="andá a la pestaña Insertar")
    assert browser is None or browser.get("code") != cu_documents.EXPECTS_TITLE_CHANGE
    # A tab already on screen is clicked as before, start page or not.
    view = copy.deepcopy(_start_page())
    view["controls"].append(_control(20, "TabItem", "Insertar", "", (160, 60, 70, 30)))
    tab = _step(view=view)
    assert tab is not None and tab["operation"] == "input.visible.click" and tab["arguments"]["label"] == "Insertar"


# ------------------------------------------------------------------ lectura y causa


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Libro en blanco", True), ("Documento en blanco", True), ("Blank workbook", True),
        ("Presentación en blanco", True), ("Empty project", True), ("Nuevo", False), ("Nueva carpeta", False),
        ("Plantilla en blanco.xlsx", False), ("Le damos la bienvenida a Excel", False),
        ("Una hoja en blanco para escribir la tesis completa del semestre", False),
    ],
)
def test_names_a_blank_item(name, expected) -> None:
    assert missions.names_a_blank_item(name) is expected


@pytest.mark.parametrize(
    ("objective", "expected"),
    [
        ("en Excel andá a la pestaña Insertar", False),
        ("en Word creá un documento nuevo y andá a Diseño", False),
        ("in Word open a blank document and go to the Layout tab", False),
        ("en Word abrí informe.docx", True),
        ("en Word andá al documento de la tesis", True),
        ("open my budget workbook in Excel", True),
    ],
)
def test_names_a_file(objective, expected) -> None:
    assert missions.names_a_file(objective) is expected


@pytest.mark.parametrize(
    ("objective", "application", "expected"),
    [
        ("en el explorador de archivos andá a la pestaña Imágenes", "Explorador de archivos", False),
        ("in File Explorer go to the Pictures tab", "Explorador de archivos", False),
        ("en el explorador de archivos abrí el archivo informe", "Explorador de archivos", True),
        ("en Word andá al documento de la tesis", "Word", True),
    ],
)
def test_the_applications_own_name_names_no_file(objective, application, expected) -> None:
    # Review 2026-10-07: «archivos» inside «explorador de archivos» stopped an Explorer tab goal as «no document open».
    assert missions.names_a_file(objective, application) is expected


@pytest.mark.parametrize(("name", "expected"), [("Plantillas", True), ("Nueva", True), ("Templates", True),
                                                ("Vista de elementos", False), ("Recientes", False)])
def test_names_a_templates_list(name, expected) -> None:
    assert missions.names_a_templates_list(name) is expected


@pytest.mark.parametrize(("name", "expected"), [("Recientes", True), ("Compartidos conmigo", True), ("Recent", True),
                                                ("Plantillas", False), ("Nueva", False)])
def test_names_own_files_list(name, expected) -> None:
    assert missions.names_own_files_list(name) is expected


def test_the_final_says_the_start_page_as_the_cause() -> None:
    seen = cu_projection.project_seen(
        {"goal": "ir a la pestaña diseno", "reached": False, "application": "Word",
         "stoppedBy": "computer_use_no_document_open", "steps": []},
        "es",
    )

    assert seen["stoppedBecause"] == "la aplicación está en su pantalla de inicio, sin ningún documento abierto"
    assert "operaci" not in seen["stoppedBecause"]


# ------------------------------------------------------------------ Estabilización G3: el pedido presupone un documento
# Tandas f2nb t2-c10, t3-c02, t4-c13: Word and Excel born on their start page; the model typed «1» twice into the start
# page's name box for «seleccioná la fila 1», and «seleccionar titulo» closed by the model's own evidence after a click
# on «Inicio». A request about a document already open is said as such on a start page with none.

@pytest.mark.parametrize(("app", "blank", "objective", "goal"), [
    ("Word", "Documento en blanco", "en word poné el titulo en negrita y centralo", "seleccionar titulo"),
    ("Excel", "Libro en blanco", "en el excel que tengo abierto seleccioná la fila 1 y ponela en negrita",
     "seleccionar fila 1"),
    ("Word", "Documento en blanco", "en el word que tengo abierto ponle negrita al texto que tengo seleccionado",
     "en el word que tengo abierto ponle negrita al texto que tengo seleccionado"),
    ("Word", "Blank document", "in the Word doc I have open make the title bold", "select title"),
])
def test_g3_a_request_about_an_open_document_on_a_start_page_is_said_never_acted(app, blank, objective, goal) -> None:
    decision = computer_use.decide_step(
        _NoModel(), objective=objective, goal=goal, application=app, success_check=None,
        view=_start_page(app, blank), history=[{**OPENED[0], "applicationName": app}], budget_left=10,
        application_names=("Excel", "Word"),
    )

    assert decision["operation"] == "none"
    assert decision["code"] == cu_documents.NO_DOCUMENT_OPEN


def test_g3_contracaso_a_tab_on_a_start_page_still_creates_the_blank_document() -> None:
    decision = computer_use.decide_step(
        _NoModel(), objective="en Word andá a la pestaña Diseño", goal="ir a la pestaña diseno",
        application="Word", success_check="control:diseno:selected", view=_start_page("Word", "Documento en blanco"),
        history=[{**OPENED[0], "applicationName": "Word"}], budget_left=10, application_names=("Excel", "Word"),
    )
    assert decision["operation"] == "input.key.press" and decision["code"] == cu_documents.EXPECTS_TITLE_CHANGE


def test_g3_contracaso_with_the_document_open_the_request_goes_on() -> None:
    view = _document_window()
    step = cu_rules.deterministic_step(
        goal="seleccionar fila 1", view=view, history=OPENED, application="Excel",
        objective="en el excel que tengo abierto seleccioná la fila 1 y ponela en negrita",
    )
    assert step is None or step.get("code") != cu_documents.NO_DOCUMENT_OPEN


@pytest.mark.parametrize(("text", "expected"), [
    ("en word poné el titulo en negrita y centralo", True),
    ("en el excel que tengo abierto seleccioná la fila 1 y ponela en negrita", True),
    ("en el word que tengo abierto ponle negrita al texto que tengo seleccionado", True),
    ("in the excel that I have open select row 1", True),
    ("en word escribí el titulo en negrita", False),
    ("abrí excel y creá un libro en blanco", False),
    ("abre un documento nuevo de word y poné el titulo en negrita", False),
    ("en paint elegí el lápiz con color azul", False),
    ("en word andá a la pestaña Diseño", False),
    ("", False),
])
def test_g3_presupposes_an_open_document(text, expected) -> None:
    assert missions.presupposes_an_open_document(text) is expected
