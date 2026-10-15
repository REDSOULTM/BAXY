"""Pasada r15b, secciones A1 y A2 de r16a/por_que_falla.md.

A1: el menú de sistema de la ventana («Sistema», «Barra de menús del sistema») fue la elección equivocada más frecuente
del modelo (v3-13, v3-16, v3-32, v3-33, v3-38, v3-39). No se le lista al modelo ni se acepta un clic sobre él salvo que
el objetivo pida mover, restaurar, minimizar, maximizar o cerrar la ventana; el rechazo tiene reintento.

A2: lo ya cumplido se cierra sin depender del «done» del modelo: el contador «diapositiva N de N» que sube en 1 tras el
clic (v3-03), el título nuevo que nombra lo creado (v3-04), la opción pedida ya elegida en la primera vista tras abrir
(v3-31); y un segundo clic idéntico que crea otra vez lo mismo en un sub-objetivo de crear uno se rechaza
(creates_again).

Las vistas son las de los prompts reales de la pasada (model_calls.jsonl de cada caso).
"""

from __future__ import annotations

from typing import Any

import pytest

from baxy_mind import computer_use as cu
from baxy_mind import cu_view
from baxy_mind import cu_creation
from baxy_mind import cu_validate
from baxy_mind import cu_step_prompt


def _c(i: int, kind: str, name: str, state: str = "", zone: str = "", value: str = "") -> dict:
    control: dict[str, Any] = {"i": i, "kind": kind, "name": name}
    if state:
        control["state"] = state
    if zone:
        control["zone"] = zone
    if value:
        control["value"] = value
    return control


class _Consulted(Exception):
    pass


class _NoModel:
    """The step is decided without the model."""

    def __getattr__(self, name: str):
        raise _Consulted(name)


class _Scripted:
    """The model answers the given acts in order and keeps every prompt it was shown."""

    def __init__(self, *replies: dict) -> None:
        self.replies = list(replies)
        self.prompts: list[str] = []

    def _post_schema_object(self, payload: dict, _label: str) -> dict:
        self.prompts.append("\n".join(str(message["content"]) for message in payload["messages"]))
        return self.replies.pop(0)


# v3-13, request 8: «en el reproductor multimedia de windows pon el tema oscuro desde configuración».
MEDIA_OBJECTIVE = "en el reproductor multimedia de windows pon el tema oscuro desde configuración"
MEDIA = {
    "window": {"title": "Reproductor multimedia", "process": "Microsoft.Media.Player"},
    "controls": [
        _c(0, "MenuItem", "Sistema", "collapsed"),
        _c(1, "Button", "Minimizar Reproductor multimedia", zone="TR"),
        _c(2, "Button", "Maximizar Reproductor multimedia", zone="TR"),
        _c(3, "Button", "Cerrar Reproductor multimedia", zone="TR"),
        _c(4, "Button", "Abrir navegación", zone="TL"),
        _c(5, "Button", "Hacer clic para buscar", zone="TL"),
        _c(6, "ListItem", "Página principal", zone="TL"),
        _c(7, "ListItem", "Biblioteca de música", zone="TL"),
        _c(8, "ListItem", "Biblioteca de videos", "selected", "TL"),
        _c(9, "ListItem", "Cola de reproducción", zone="L"),
        _c(10, "ListItem", "Listas de reproducción", zone="L"),
        _c(11, "ListItem", "Configuración", zone="BL"),
        _c(12, "TabItem", "Todos los videos", "selected", "TL"),
        _c(13, "TabItem", "Carpetas de videos", zone="T"),
        _c(14, "Button", "Agregar una carpeta", zone="TR"),
        _c(15, "MenuBar", "Sistema"),
        _c(16, "Text", "Reproductor multimedia", zone="TL"),
        _c(17, "TitleBar", "Reproductor multimedia", zone="T"),
        _c(18, "MenuBar", "Barra de menús del sistema", zone="TL"),
    ],
    "text": {"TL": ["Reproductor multimedia", "Todos los videos"], "T": ["Carpetas de videos"]},
}
OPENED = [{"step": 1, "operation": "app.open", "appId": "Reproductor multimedia", "ok": True}]

# v3-31, request 8: the first look after opening the snipping tool, already in window mode.
SNIP_OBJECTIVE = "abre recortes y cambia el modo a ventana"
SNIP = {
    "window": {"title": "Herramienta Recortes", "process": "SnippingTool",
               "focused": {"kind": "Button", "name": "Nueva captura de pantalla"}},
    "controls": [
        _c(0, "Button", "Nueva captura de pantalla", "focused", "TL"),
        _c(1, "Button", "Modo de captura establecido en recortes", "off", "TL"),
        _c(2, "ComboBox", "Menú desplegable de área de recorte y captura", "collapsed", "T"),
        _c(3, "ListItem", "Ventana", "selected", "T"),
        _c(4, "ComboBox", "Menú desplegable Retrasar recorte", "collapsed", "T"),
        _c(5, "ListItem", "Sin retraso", "selected", "T"),
        _c(6, "Button", "Extractor de texto", zone="TR"),
        _c(7, "Button", "Más de la barra de la aplicación", zone="TR"),
        _c(8, "MenuItem", "Sistema", "collapsed", "TL"),
        _c(9, "Button", "Minimizar", zone="TR"),
        _c(10, "Button", "Maximizar", zone="TR"),
        _c(11, "Button", "Cerrar", zone="TR"),
        _c(12, "Group", "Ventana", zone="T"),
        _c(13, "Group", "Sin retraso", zone="T"),
        _c(14, "TitleBar", "Herramienta Recortes", zone="T"),
        _c(15, "MenuBar", "Barra de menús del sistema", zone="TL"),
    ],
    "text": {"TL": ["Herramienta Recortes", "Nuevo"], "C": ["Presiona + Mayús + S para iniciar un recorte"]},
}
SNIP_OPENED = [{"step": 1, "operation": "app.open", "appId": "Herramienta Recortes", "ok": True}]


def _not_closed(objective: str, goal: str, application: str, view: dict, history: list) -> None:
    """The rules leave the step to the model, or take another one that is no closing (a press the goal dictates)."""

    try:
        step = _step(_NoModel(), objective, goal, application, view, history)
    except _Consulted:
        return
    assert step["operation"] != "done", step


def _step(llm: Any, objective: str, goal: str, application: str, view: dict, history: list) -> dict:
    return cu.decide_step(
        llm, objective=objective, goal=goal, application=application, success_check=None, view=view,
        history=list(history), budget_left=10, application_names=[application],
    )


# --- A1: the window's system menu -----------------------------------------------------------------------------------


def test_the_system_menu_is_never_listed_to_the_model() -> None:
    listed = cu_step_prompt.compact_view_text(MEDIA, goal=MEDIA_OBJECTIVE)

    assert "«Sistema»" not in listed and "Barra de menús del sistema" not in listed
    assert "«Configuración»" in listed and "«Cerrar Reproductor multimedia»" in listed


@pytest.mark.parametrize("goal", ["minimiza la ventana", "mueve la ventana a la izquierda", "restore the window",
                                  "maximize it", "cerrá la ventana de recortes"])
def test_a_goal_on_the_window_itself_still_sees_the_system_menu(goal: str) -> None:
    listed = cu_step_prompt.compact_view_text(MEDIA, goal=goal)

    assert "«Sistema»" in listed and "Barra de menús del sistema" in listed
    step = cu_validate.validate_decision({"act": "click", "i": 0}, view=MEDIA, last_failed=None,
                                application_names=["Reproductor multimedia"], history=list(OPENED), goal=goal)
    assert step["operation"] == "input.visible.click"


@pytest.mark.parametrize(("view", "index"), [(MEDIA, 0), (MEDIA, 15), (MEDIA, 18), (SNIP, 8), (SNIP, 15)])
def test_a_click_on_the_system_menu_is_refused_with_a_retry(view: dict, index: int) -> None:
    step = cu_validate.validate_decision({"act": "click", "i": index}, view=view, last_failed=None,
                                application_names=["Reproductor multimedia"], history=list(OPENED),
                                goal="ir a configuración")

    assert step["operation"] == "none" and step["code"] == "system_menu"
    assert "system_menu" in cu._RETRIED


def test_by_label_alone_too() -> None:
    step = cu_validate.validate_decision({"act": "click", "text": "Sistema"}, view=SNIP, last_failed=None,
                                application_names=["Herramienta Recortes"], history=list(SNIP_OPENED),
                                goal="poner un retraso de 5 segundos")

    assert step["operation"] == "none" and step["code"] == "system_menu"


def test_v3_13_twin_the_retry_goes_to_the_place() -> None:
    # The live model pressed «Sistema» three times; now it never sees it, and a press of it gets the retry.
    model = _Scripted({"act": "click", "i": 0}, {"act": "click", "i": 11})

    step = _step(model, MEDIA_OBJECTIVE, MEDIA_OBJECTIVE, "Reproductor multimedia", MEDIA, OPENED)

    assert step["operation"] == "input.visible.click" and step["arguments"]["label"] == "Configuración"
    assert "«Sistema»" not in model.prompts[0] and "system_menu" not in model.prompts[0]
    assert "menú de sistema" in model.prompts[1]


@pytest.mark.parametrize(("kind", "name"), [("MenuItem", "Archivo"), ("MenuItem", "Más opciones"),
                                            ("ListItem", "Sistema"), ("TreeItem", "System")])
def test_contracase_menus_of_the_window_and_places_named_system_stay(kind: str, name: str) -> None:
    # A menu of the window's own and a place named «Sistema» (Settings' page) are no system menu.
    view = {**MEDIA, "controls": [_c(0, kind, name, zone="TL"), _c(1, "Button", "Otra cosa", zone="C")]}

    assert f"«{name}»" in cu_step_prompt.compact_view_text(view, goal="ir a sistema")
    step = cu_validate.validate_decision({"act": "click", "i": 0}, view=view, last_failed=None,
                                application_names=["Configuración"], history=[], goal="ir a sistema")
    assert step.get("code") != "system_menu"


def test_a_lone_menu_drawn_in_the_title_bar_is_the_system_menu_whatever_its_name() -> None:
    # The geometry of _system_menu (live v3-34): the only menu item inside the title bar.
    view = {
        "window": {"title": "Notas", "process": "Notes"},
        "controls": [
            {"i": 0, "kind": "TitleBar", "name": "Notas", "rect": {"x": 0, "y": 0, "w": 800, "h": 32}},
            {"i": 1, "kind": "MenuItem", "name": "Menú", "rect": {"x": 2, "y": 2, "w": 28, "h": 28}},
            {"i": 2, "kind": "Button", "name": "Nueva nota", "rect": {"x": 10, "y": 60, "w": 80, "h": 30}},
        ],
        "text": {},
    }

    assert "«Menú»" not in cu_step_prompt.compact_view_text(view, goal="crea una nota")
    assert cu_validate.validate_decision({"act": "click", "i": 1}, view=view, last_failed=None, application_names=["Notas"],
                                history=[], goal="crea una nota")["code"] == "system_menu"


# --- A2: what is already done closes without the model --------------------------------------------------------------

# v3-03, request 9 (its controls numbered in the order listed): «in powerpoint add a new slide and switch to slide sorter view», sub-goal 1 «add a new slide».
SLIDES_FIRST_LOOK = "\n".join([
    "presentacion1 - powerpoint", "guardar", "insertar", "nueva diapositiva", "clasificador de diapositivas",
    "diapositiva 1 de 1", "haga clic para agregar titulo",
])
SLIDES = {
    "window": {"title": "Presentación1 - PowerPoint", "process": "POWERPNT",
               "focused": {"kind": "TabItem", "name": "Insertar"}},
    "controls": [
        _c(0, "Button", "Guardar", zone="TL"),
        _c(1, "MenuItem", "Más opciones", "collapsed", "TL"),
        _c(2, "TabItem", "Insertar", "selected focused", "TL"),
        _c(3, "TabItem", "Vista", zone="TR"),
        _c(4, "SplitButton", "Nueva diapositiva", "collapsed", "TL"),
        _c(5, "Button", "Nueva diapositiva", zone="TL"),
        _c(6, "Button", "Clasificador de diapositivas", "off", "BR"),
    ],
    "text": {"TL": ["Nueva", "diapositiva v"], "BL": ["Diapositiva 2 de 2"]},
    "newText": ["2", "• haga clic para agregar texto", "diapositiva 2 de 2"],
    "newTextAfterClick": ["2", "• haga clic para agregar texto", "diapositiva 2 de 2"],
    "firstLook": SLIDES_FIRST_LOOK,
}
SLIDES_OBJECTIVE = "in powerpoint add a new slide and switch to slide sorter view"
ADDED = [
    {"step": 1, "operation": "input.visible.click", "label": "Insertar", "index": 2, "ok": True, "changed": True},
    {"step": 2, "operation": "input.visible.click", "label": "Nueva diapositiva", "index": 4, "ok": True,
     "changed": True},
]


def _slides(**changes: Any) -> dict:
    return {**SLIDES, **changes}


@pytest.mark.parametrize("goal", ["add a new slide", "agrega una diapositiva nueva", "añade una diapositiva"])
def test_v3_03_twin_the_slide_count_one_more_closes_the_sub_goal(goal: str) -> None:
    step = _step(_NoModel(), SLIDES_OBJECTIVE, goal, "PowerPoint", SLIDES, ADDED)

    assert step["operation"] == "done" and step["arguments"]["evidence"] == "diapositiva 2 de 2"
    assert step["reason"] == cu_creation.REASON_CREATED_BY_DIFF


@pytest.mark.parametrize(("goal", "view", "history"), [
    # Two more than at the first look: not the one thing asked; the model judges.
    ("add a new slide", _slides(newTextAfterClick=["diapositiva 3 de 3"], text={"BL": ["Diapositiva 3 de 3"]}), ADDED),
    # The first look counted nothing: no difference to read.
    ("add a new slide", _slides(firstLook="presentacion1 - powerpoint\ninsertar"), ADDED),
    # The goal says how many: one more is not all of it.
    ("add three new slides", SLIDES, ADDED),
    # Not a creating goal.
    ("ir a la diapositiva 2", SLIDES, ADDED),
    # The last step was no click.
    ("add a new slide", SLIDES, [*ADDED, {"step": 3, "operation": "input.key.press", "key": "ctrl_m", "ok": True}]),
    # Nothing done in the sub-goal.
    ("add a new slide", SLIDES, []),
])
def test_contracases_of_the_count(goal: str, view: dict, history: list) -> None:
    _not_closed(SLIDES_OBJECTIVE, goal, "PowerPoint", view, history)


def test_v3_03_twin_a_second_identical_press_that_creates_again_is_refused() -> None:
    # The count rule left aside (no counter): the press that just made something is not pressed again.
    view = _slides(firstLook="presentacion1 - powerpoint")
    step = cu_validate.validate_decision({"act": "click", "text": "Nueva diapositiva", "i": 5}, view=view, last_failed=None, application_names=["PowerPoint"],
                                history=list(ADDED), goal="add a new slide")

    assert step["operation"] == "none" and step["code"] == "creates_again"


@pytest.mark.parametrize(("goal", "view"), [
    ("add a new slide", _slides(newTextAfterClick=[])),  # it made nothing appear
    ("add three new slides", SLIDES),  # the goal says how many
    ("haz clic en nueva diapositiva", SLIDES),  # no creating goal
    ("add a new slide", _slides(controls=[*SLIDES["controls"], _c(7, "Menu", "Diseños", zone="C")])),  # a menu opened
])
def test_contracases_of_creates_again(goal: str, view: dict) -> None:
    step = cu_validate.validate_decision({"act": "click", "text": "Nueva diapositiva", "i": 5}, view=view, last_failed=None, application_names=["PowerPoint"],
                                history=list(ADDED), goal=goal)

    assert step["operation"] == "input.visible.click"


# v3-04, request 9: «haz una presentación en blanco», after the press on the start page's «Presentación en blanco».
BLANK_FIRST_LOOK = "\n".join([
    "powerpoint", "inicio", "nuevo", "presentacion en blanco", "bienvenido a powerpoint", "recientes",
    "presentacion final", "buscar",
])
BLANK = {
    "window": {"title": "Presentación1 - PowerPoint", "process": "POWERPNT"},
    "controls": [
        _c(0, "Button", "Autoguardado", "off", "TL"),
        _c(1, "Button", "Guardar", zone="TL"),
        _c(4, "Button", "‪Presentación1‬ - PowerPoint", zone="T"),
        _c(6, "Edit", "Búsqueda de Microsoft", zone="T", value="Buscar"),
        _c(12, "TabItem", "Inicio", "selected", "TL"),
        _c(13, "TabItem", "Insertar", zone="TL"),
        _c(57, "TitleBar", "‪Presentación1‬ - PowerPoint", zone="T"),
    ],
    "text": {},
    "newTextAfterClick": [],
    "firstLook": BLANK_FIRST_LOOK,
}
BLANK_OBJECTIVE = ("abre powerpint, haz una presentación en blanco, ponle 'Proyecto final' de título y guárdala como "
                   "proyecto-final en Documentos\\baxy-prueba-v3")
PRESSED_BLANK = [
    {"step": 1, "operation": "app.open", "appId": "PowerPoint", "ok": True},
    {"step": 2, "operation": "input.visible.click", "label": "Presentación en blanco", "index": 12, "ok": True,
     "changed": True},
]


@pytest.mark.parametrize("goal", ["haz una presentación en blanco", "crea una presentación nueva",
                                  "create a blank presentation"])
def test_v3_04_twin_the_new_title_naming_the_thing_closes_the_sub_goal(goal: str) -> None:
    history = PRESSED_BLANK
    if goal.startswith("create"):
        history = [PRESSED_BLANK[0], {**PRESSED_BLANK[1], "label": "Blank Presentation"}]
    step = _step(_NoModel(), BLANK_OBJECTIVE, goal, "PowerPoint", BLANK, history)

    assert step["operation"] == "done" and step["arguments"]["evidence"] == "Presentación1 - PowerPoint"
    assert cu_view.view_contains(BLANK, step["arguments"]["evidence"])


@pytest.mark.parametrize(("label", "view"), [
    # A recent file opened from the list: its title names a presentation, but the person's, not a new one.
    ("Presentación final", {**BLANK, "window": {"title": "Presentación final - PowerPoint", "process": "POWERPNT"}}),
    # The title is the one of the first look: nothing was born.
    ("Presentación en blanco", {**BLANK, "window": {"title": "PowerPoint", "process": "POWERPNT"}}),
    # The new title names something else.
    ("Presentación en blanco", {**BLANK, "window": {"title": "Opciones - PowerPoint", "process": "POWERPNT"}}),
])
def test_contracases_of_the_new_title(label: str, view: dict) -> None:
    history = [PRESSED_BLANK[0], {**PRESSED_BLANK[1], "label": label}]
    _not_closed(BLANK_OBJECTIVE, "haz una presentación en blanco", "PowerPoint", view, history)


def test_v3_31_twin_the_mode_already_chosen_is_said_as_it_was() -> None:
    step = _step(_NoModel(), SNIP_OBJECTIVE, "cambia el modo a ventana", "Herramienta Recortes", SNIP, SNIP_OPENED)

    assert step["operation"] == "done"
    assert step["arguments"] == {"evidence": "Ventana", "already": True}


@pytest.mark.parametrize(("goal", "history"), [
    ("cambia el modo a rectángulo", SNIP_OPENED),  # the option asked is not the chosen one
    ("quita el modo ventana", SNIP_OPENED),  # undoing it is no choosing
    ("deselect window", SNIP_OPENED),
    ("cerrá la ventana", SNIP_OPENED),  # no choosing verb
    # An act of the sub-goal already ran: the receipts and the model judge, never «already».
    ("cambia el modo a ventana", [*SNIP_OPENED, {"step": 2, "operation": "input.visible.click",
                                                "label": "Modo de captura establecido en recortes", "ok": True}]),
])
def test_contracases_of_already_chosen(goal: str, history: list) -> None:
    _not_closed(SNIP_OBJECTIVE, goal, "Herramienta Recortes", SNIP, history)


def test_a_switch_on_is_never_already_chosen() -> None:
    view = {**SNIP, "controls": [_c(0, "Button", "Ventana", "on", "T"), _c(1, "Button", "Otra", zone="C")]}

    _not_closed(SNIP_OBJECTIVE, "pon ventana", "Herramienta Recortes", view, SNIP_OPENED)


# --- Review of sistema-cumplido (35870c47b): the closings say done only of what was done ----------------------------


@pytest.mark.parametrize(("goal", "name", "process"), [
    # Finding 1: the goal asks more than the option held (selected is not playing, applied, renamed, sent, emptied).
    ("pon la canción despacito", "Despacito", "Microsoft.Media.Player"),
    ("cambia el nombre de informe a final", "informe", "explorer"),
    ("cambia el fondo de pantalla a paisaje", "Paisaje", "SystemSettings"),
    ("usa el chat de juan pérez para mandar hola", "Juan Pérez", "WhatsApp"),
    ("deja la bandeja de entrada vacía", "Bandeja de entrada", "olk"),
    ("selecciona juan pérez y bórralo", "Juan Pérez", "WhatsApp"),
    ("pon el volumen a 50", "50", "SystemSettings"),
])
def test_finding_1_a_goal_saying_more_than_the_option_is_never_already(goal: str, name: str, process: str) -> None:
    view = {"window": {"title": "Ventana", "process": process},
            "controls": [_c(0, "ListItem", name, "selected"), _c(1, "ListItem", "Otra cosa"),
                         _c(2, "Button", "Eliminar")], "text": {}}

    _not_closed(goal, goal, "Aplicación", view, [{"step": 1, "operation": "app.open", "appId": "Aplicación", "ok": True}])


@pytest.mark.parametrize(("goal", "name"), [
    ("pon el tema oscuro", "Oscuro"), ("set the theme to dark", "Dark"), ("switch to list view", "List"),
    ("selecciona ventana", "Ventana"), ("usa el modo oscuro", "Oscuro"),
])
def test_finding_1_the_option_alone_is_still_already(goal: str, name: str) -> None:
    view = {"window": {"title": "Configuración", "process": "SystemSettings"},
            "controls": [_c(0, "ListItem", name, "selected"), _c(1, "ListItem", "Otra")], "text": {}}

    step = _step(_NoModel(), goal, goal, "Configuración", view,
                 [{"step": 1, "operation": "app.open", "appId": "Configuración", "ok": True}])
    assert step["operation"] == "done" and step["arguments"] == {"evidence": name, "already": True}


@pytest.mark.parametrize("goal", ["agrega una diapositiva con el título Ventas", "add a slide titled Sales",
                                  "añade una diapositiva de título y objetos", "agrega una diapositiva 3"])
def test_finding_2_the_count_never_closes_a_goal_asking_more_than_the_slide(goal: str) -> None:
    _not_closed(SLIDES_OBJECTIVE, goal, "PowerPoint", SLIDES, ADDED)


WORD_FIRST_LOOK = "word\ninicio\nnuevo\ndocumento en blanco\nrecientes"
WORD_NEW = {
    "window": {"title": "Documento1 - Word", "process": "WINWORD"},
    "controls": [_c(0, "Button", "Guardar", zone="TL"), _c(1, "TabItem", "Inicio", "selected", "TL")],
    "text": {}, "newTextAfterClick": ["Documento1"], "firstLook": WORD_FIRST_LOOK,
}
WORD_PRESSED = [
    {"step": 1, "operation": "app.open", "appId": "Word", "ok": True},
    {"step": 2, "operation": "input.visible.click", "label": "Documento en blanco", "ok": True, "changed": True},
]


@pytest.mark.parametrize("goal", ["crea un documento llamado informe", "crea un documento en blanco que diga hola mundo"])
def test_finding_2_the_new_title_never_closes_a_goal_asking_more_than_the_document(goal: str) -> None:
    _not_closed(goal, goal, "Word", WORD_NEW, WORD_PRESSED)


def test_finding_2_the_document_alone_still_closes_by_its_new_title() -> None:
    step = _step(_NoModel(), "crea un documento en blanco", "crea un documento en blanco", "Word", WORD_NEW,
                 WORD_PRESSED)

    assert step["operation"] == "done" and step["arguments"]["evidence"] == "Documento1 - Word"


MAIL_NEW = {
    "window": {"title": "Sin título - Mensaje (HTML)", "process": "OUTLOOK"},
    "controls": [_c(0, "Edit", "Para"), _c(1, "Edit", "Asunto"), _c(2, "Button", "Enviar")],
    "text": {}, "newTextAfterClick": ["Para", "Asunto"],
    "firstLook": "bandeja de entrada - outlook\nnuevo correo\nbandeja de entrada",
}
MAIL_PRESSED = [{"step": 1, "operation": "input.visible.click", "label": "Nuevo correo", "ok": True, "changed": True}]


@pytest.mark.parametrize("goal", ["crea un correo para juan que diga hola", "crea un correo nuevo", "create a new email"])
def test_finding_2_a_form_still_to_send_made_nothing(goal: str) -> None:
    _not_closed(goal, goal, "Outlook", MAIL_NEW, MAIL_PRESSED)


def test_finding_3_the_count_needs_the_click_that_creates_the_thing() -> None:
    view = {
        "window": {"title": "Documento1 - Word", "process": "WINWORD"},
        "controls": [_c(0, "Button", "Negrita")], "text": {"BL": ["Página 2 de 2"]},
        "firstLook": "documento1 - word\nsalto de pagina\nnegrita\npagina 1 de 1", "newTextAfterClick": ["Página 2 de 2"],
    }
    pressed = [{"step": 1, "operation": "input.visible.click", "label": "Negrita", "ok": True, "changed": True}]

    for goal in ("agrega una página", "agrega una página con una tabla"):
        _not_closed(goal, goal, "Word", view, pressed)
    # The control that creates a page, pressed last, still closes the bare goal.
    created = [{**pressed[0], "label": "Nueva página"}]
    step = _step(_NoModel(), "agrega una página", "agrega una página", "Word", view, created)
    assert step["operation"] == "done" and step["arguments"]["evidence"] == "Página 2 de 2"


def test_finding_4_a_recent_file_whose_name_says_new_is_no_new_one() -> None:
    first_look = "powerpoint\npresentacion en blanco\nnueva presentacion de ventas"
    view = {"window": {"title": "Nueva presentación de ventas - PowerPoint", "process": "POWERPNT"},
            "controls": [_c(0, "TabItem", "Inicio", "selected")], "text": {},
            "newTextAfterClick": ["Nueva presentación de ventas"], "firstLook": first_look}
    history = [PRESSED_BLANK[0], {**PRESSED_BLANK[1], "label": "Nueva presentación de ventas"}]

    _not_closed("crea una presentación", "crea una presentación", "PowerPoint", view, history)


NOTES_TITLE_MENU = {
    "window": {"title": "Notas rápidas", "process": "Notes", "rect": {"x": 0, "y": 0, "w": 800, "h": 600}},
    "controls": [
        {"i": 0, "kind": "TitleBar", "name": "Notas rápidas", "rect": {"x": 0, "y": 0, "w": 800, "h": 40}},
        {"i": 1, "kind": "MenuItem", "name": "Más opciones", "state": "collapsed",
         "rect": {"x": 700, "y": 5, "w": 30, "h": 30}},
        {"i": 2, "kind": "Button", "name": "Minimizar", "rect": {"x": 740, "y": 0, "w": 20, "h": 30}},
        {"i": 3, "kind": "Document", "name": "Nota", "rect": {"x": 0, "y": 40, "w": 800, "h": 560}},
    ],
    "text": {},
}


def test_finding_5_a_lone_title_bar_menu_the_goal_names_is_the_goals_place() -> None:
    goal = "abre más opciones y elige exportar"

    assert "«Más opciones»" in cu_step_prompt.compact_view_text(NOTES_TITLE_MENU, goal=goal)
    step = cu_validate.validate_decision({"act": "click", "i": 1}, view=NOTES_TITLE_MENU, last_failed=None,
                                application_names=["Notas"], history=[], goal=goal)
    assert step["operation"] == "input.visible.click" and step["arguments"]["label"] == "Más opciones"


@pytest.mark.parametrize("goal", ["exporta la nota", "ir a sistema"])
def test_finding_5_contracase_unnamed_it_stays_the_system_menu(goal: str) -> None:
    assert "«Más opciones»" not in cu_step_prompt.compact_view_text(NOTES_TITLE_MENU, goal=goal)
    step = cu_validate.validate_decision({"act": "click", "i": 1}, view=NOTES_TITLE_MENU, last_failed=None,
                                application_names=["Notas"], history=[], goal=goal)
    assert step["code"] == "system_menu"
