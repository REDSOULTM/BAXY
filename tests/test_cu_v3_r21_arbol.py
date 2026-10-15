"""Ronda 21, bajada por el árbol de navegación (pasada r18: v3-23, v3-24, v3-25, v3-26, v3-67). Un lugar que vive dentro
de un nodo cerrado del árbol de navegación (columna izquierda, TreeItem collapsed) se alcanza abriendo los nodos por su
identidad (``manner`` «open»), sin codificador; el nodo donde ya está la ventana no es un paso hacia otro lugar; dos
controles con el mismo nombre no son ausencia; un clic por nombre fuera de la vista dicho en otro idioma es ciego; un
«reveal» de un nodo cerrado lo abre; abrir o desplegar una ruta con «>» la introduce. Vistas sacadas de la evidencia
(trace y model_calls de v2-v3-26 y v2-v3-67), con rectángulos sintéticos de la columna del árbol."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from baxy_mind import computer_use
from baxy_mind import cu_history
from baxy_mind import cu_navigation
from baxy_mind import cu_lookup
from baxy_mind import cu_rules
from baxy_mind import cu_validate
from baxy_mind.semantic import catalog, missions

INDEX = catalog.build_application_catalog_index(json.loads(
    (Path(__file__).resolve().parent / "data" / "cu_v3_start_catalog.v1.json").read_text(encoding="utf-8"))["names"])


def _r(x: int, y: int, w: int = 180, h: int = 20) -> dict:
    return {"x": x, "y": y, "w": w, "h": h}


def _dense(controls: list[dict]) -> list[dict]:
    """The view's list as the App hands it: each control at the position its index says (the gaps are unnamed panes
    the listing would show further down)."""

    by_index = {control["i"]: control for control in controls}
    return [by_index.get(n, {"i": n, "kind": "Pane", "name": "", "zone": "C"}) for n in range(max(by_index) + 1)]


def _event_viewer(*, logs_state: str = "collapsed", selected_logs: bool = False, children: bool = False,
                  custom_open: bool = False) -> dict:
    """The Event Viewer of v3-26 (step 1, req 8): the root selected and expanded, its children collapsed."""

    root_state = "expanded" if selected_logs else "selected expanded"
    controls = [
        {"i": 4, "kind": "Button", "name": "Introducción", "zone": "T", "rect": _r(300, 80)},
        {"i": 7, "kind": "Button", "name": "Resumen de registro", "zone": "B", "rect": _r(300, 500)},
        {"i": 8, "kind": "Button", "name": "Visor de eventos (local)", "state": "readonly", "zone": "TR", "rect": _r(900, 80)},
        {"i": 13, "kind": "Button", "name": "Actualizar", "state": "readonly", "zone": "R", "rect": _r(900, 200)},
        {"i": 15, "kind": "TreeItem", "name": "Visor de eventos (local)", "state": root_state, "zone": "TL", "rect": _r(4, 80)},
        {"i": 16, "kind": "TreeItem", "name": "Vistas personalizadas", "state": "expanded" if custom_open else "collapsed",
         "zone": "TL", "rect": _r(20, 100)},
    ]
    if custom_open:
        controls.append({"i": 40, "kind": "TreeItem", "name": "Eventos administrativos", "zone": "TL", "rect": _r(36, 120)})
    logs = "selected " + logs_state if selected_logs else logs_state
    controls.append({"i": 17, "kind": "TreeItem", "name": "Registros de Windows", "state": logs, "zone": "TL", "rect": _r(20, 140)})
    if children:
        controls += [
            {"i": 41, "kind": "TreeItem", "name": "Aplicación", "zone": "TL", "rect": _r(36, 160)},
            {"i": 42, "kind": "TreeItem", "name": "Sistema", "zone": "TL", "rect": _r(36, 180)},
        ]
    controls += [
        {"i": 18, "kind": "TreeItem", "name": "Registros de aplicaciones y servicios", "state": "collapsed", "zone": "TL",
         "rect": _r(20, 200)},
        {"i": 19, "kind": "TreeItem", "name": "Suscripciones", "zone": "TL", "rect": _r(20, 220)},
        {"i": 21, "kind": "Edit", "name": "Introducción y resumen", "state": "readonly", "zone": "B", "rect": _r(300, 600)},
        {"i": 22, "kind": "MenuItem", "name": "Archivo", "zone": "TL", "rect": _r(4, 30, 50)},
        {"i": 24, "kind": "MenuItem", "name": "Ver", "zone": "TL", "rect": _r(110, 30, 40)},
    ]
    if selected_logs:
        # v3-23: «Registros de Windows» chosen, its logs listed as rows of the central summary.
        controls += [
            {"i": 50, "kind": "DataItem", "name": "Aplicación", "zone": "C", "rect": _r(300, 300, 400)},
            {"i": 51, "kind": "DataItem", "name": "Sistema", "zone": "C", "rect": _r(300, 320, 400)},
        ]
    return {
        "window": {"title": "Visor de eventos", "process": "mmc", "rect": {"x": 0, "y": 0, "w": 1200, "h": 800}},
        "controls": _dense(controls), "controlCount": 80, "text": {},
    }


OPENED = {"operation": "app.open", "ok": True}
V3_26 = "abrí el Visor de eventos y en Sistema buscame un evento con ID 6005"


def _step(goal: str, view: dict, history: list[dict], objective: str = V3_26) -> dict | None:
    return cu_rules.deterministic_step(goal=goal, view=view, history=history, objective=objective)


def _opened(label: str, index: int) -> dict:
    return {"operation": "input.visible.click", "label": label, "index": index, "manner": "open", "ok": True}


def _checked(raw: dict, view: dict, goal: str, objective: str = V3_26, history: list[dict] | None = None) -> dict:
    return cu_validate.validate_decision(
        raw, view=view, last_failed=None, application_names=(), history=history or [], goal=goal, objective=objective,
    )


# ---------------------------------------------------------------- (a) bajada determinista

def _not_found(label: str) -> dict:
    return {"operation": "input.visible.click", "label": label, "ok": False, "error": "visible_button_not_found"}


def test_twin_v3_26_the_tree_is_opened_shallow_first_until_the_place_shows() -> None:
    # Revision 2 (finding 1): the view lists only part of the window, so the click by name off the view goes first.
    by_name = _step("ir a sistema", _event_viewer(), [OPENED])
    assert by_name is not None and by_name["reason"] == cu_lookup.REASON_BY_NAME
    assert by_name["arguments"] == {"label": "sistema"}
    # It found nothing: the nodes open.
    missed = _not_found("sistema")
    first = _step("ir a sistema", _event_viewer(), [OPENED, missed])
    assert first is not None and first["operation"] == "input.visible.click"
    assert first["arguments"] == {"label": "Vistas personalizadas", "index": 16, "manner": "open"}
    assert first["reason"] == cu_navigation.REASON_DESCENT
    # The opened node showed its own collapsed-free child; the next node of the same level goes before any deeper one.
    second = _step("ir a sistema", _event_viewer(custom_open=True), [OPENED, missed, _opened("Vistas personalizadas", 16)])
    assert second is not None and second["arguments"] == {"label": "Registros de Windows", "index": 17, "manner": "open"}
    # «Sistema» appeared as a node of the tree: the goal's own click, by its identity.
    third = _step("ir a sistema", _event_viewer(custom_open=True, logs_state="expanded", children=True),
                  [OPENED, missed, _opened("Vistas personalizadas", 16), _opened("Registros de Windows", 17)])
    assert third is not None and third["operation"] == "input.visible.click"
    assert third["arguments"] == {"label": "Sistema", "index": 42}


def test_the_descent_stops_at_its_cap_of_nodes() -> None:
    history = [OPENED, *(_opened(f"Nodo {n}", 90 + n) for n in range(cu_navigation._TREE_DESCENT_NODES))]
    step = _step("ir a sistema", _event_viewer(), history)
    assert step is None or step.get("arguments", {}).get("manner") != "open"


def test_twin_v3_23_the_content_row_waits_for_its_collapsed_node() -> None:
    # v3-23 «ahora anda a registros de windows, sistema» reads «ir a registros de windows; luego ir a sistema».
    view = _event_viewer(selected_logs=True)
    step = _step("ir a sistema", view, [OPENED])
    assert step is not None and step["arguments"] == {"label": "Registros de Windows", "index": 17, "manner": "open"}
    assert step["reason"] == cu_navigation.REASON_DESCENT_FIRST
    # Opened: the tree's «Sistema» is the place, never the row of the summary.
    after = _event_viewer(selected_logs=True, logs_state="expanded", children=True)
    went = _step("ir a sistema", after, [OPENED, _opened("Registros de Windows", 17)])
    assert went is not None and went["arguments"] == {"label": "Sistema", "index": 42}


EXPLORER = {
    "window": {"title": "Inicio - Explorador de archivos", "process": "explorer", "rect": {"x": 0, "y": 0, "w": 1200, "h": 800}},
    "controls": [
        {"i": 0, "kind": "TreeItem", "name": "Inicio", "state": "selected", "zone": "TL", "rect": _r(4, 100)},
        {"i": 1, "kind": "TreeItem", "name": "Escritorio", "zone": "L", "rect": _r(4, 140)},
        {"i": 2, "kind": "TreeItem", "name": "Descargas", "zone": "L", "rect": _r(4, 160)},
        {"i": 3, "kind": "TreeItem", "name": "Este equipo", "state": "collapsed", "zone": "L", "rect": _r(4, 300),
         "itemType": "Carpeta del sistema"},
        {"i": 4, "kind": "TreeItem", "name": "Red", "state": "collapsed", "zone": "BL", "rect": _r(4, 340),
         "itemType": "Red"},
        {"i": 5, "kind": "TreeItem", "name": "Disco local (C:)", "state": "collapsed", "zone": "BL", "rect": _r(20, 320),
         "itemType": "Disco local"},
        {"i": 6, "kind": "ListItem", "name": "Documentos", "zone": "C", "rect": _r(300, 200, 120, 120)},
    ],
    "controlCount": 7, "text": {},
}


def _explorer_documents(*, opened: bool = False) -> dict:
    """Revision 1: the Explorer on «Documentos», its navigation column a tree of collapsed nodes (the selected one
    collapsed too), the folder's rows in the content and the view listing only part of the window (300 controls)."""

    docs_state = "selected expanded" if opened else "selected collapsed"
    controls = [
        {"i": 0, "kind": "TreeItem", "name": "Inicio", "state": "collapsed", "zone": "L", "rect": _r(4, 100)},
        {"i": 1, "kind": "TreeItem", "name": "OneDrive - Personal", "state": "collapsed", "zone": "L", "rect": _r(4, 120)},
        {"i": 2, "kind": "TreeItem", "name": "Escritorio", "state": "collapsed", "zone": "L", "rect": _r(4, 160)},
        {"i": 3, "kind": "TreeItem", "name": "Descargas", "state": "collapsed", "zone": "L", "rect": _r(4, 180)},
        {"i": 4, "kind": "TreeItem", "name": "Documentos", "state": docs_state, "zone": "L", "rect": _r(4, 200)},
        {"i": 5, "kind": "TreeItem", "name": "Este equipo", "state": "collapsed", "zone": "L", "rect": _r(4, 300),
         "itemType": "Carpeta del sistema"},
        {"i": 8, "kind": "Button", "name": "Ordenar", "zone": "T", "rect": _r(400, 60, 80)},
        {"i": 13, "kind": "ListItem", "name": "carpeta1", "zone": "C", "rect": _r(300, 200, 400)},
        {"i": 14, "kind": "ListItem", "name": "carpeta2", "zone": "C", "rect": _r(300, 220, 400)},
        {"i": 15, "kind": "ListItem", "name": "carpeta3", "zone": "C", "rect": _r(300, 240, 400)},
        {"i": 16, "kind": "ListItem", "name": "notas.txt", "zone": "C", "rect": _r(300, 260, 400)},
    ]
    if opened:
        controls.append({"i": 30, "kind": "TreeItem", "name": "carpeta3", "zone": "L", "rect": _r(20, 220)})
    return {
        "window": {"title": "Documentos - Explorador de archivos", "process": "explorer",
                   "rect": {"x": 0, "y": 0, "w": 1200, "h": 800}},
        "controls": _dense(controls), "controlCount": 300, "text": {},
    }


@pytest.mark.parametrize(("goal", "said", "label"), [
    ("hacer clic en informe.docx", "hacé clic en informe.docx", "informe.docx"),
    ("hacer clic en nueva carpeta", "hacé clic en nueva carpeta", "nueva carpeta"),
    ("hacer clic en propiedades", "hacé clic en propiedades", "propiedades"),
    ("ir a proyectos", "andá a proyectos", "proyectos"),
])
def test_contracase_explorer_what_the_current_folder_holds_is_clicked_by_name_before_any_descent(
    goal: str, said: str, label: str,
) -> None:
    """Revision 1 (finding 1): a file, a command or a folder not listed, with the current node collapsed and the view
    partial, is clicked by name against the whole tree (the base's first step), never four nodes opened first."""

    step = _step(goal, _explorer_documents(), [], objective=said)
    assert step is not None and step["reason"] == cu_lookup.REASON_BY_NAME, step
    assert step["arguments"] == {"label": label}


def test_contracase_explorer_a_file_never_opens_a_node_even_after_its_click_by_name() -> None:
    view = _explorer_documents()
    tried = [{"operation": "input.visible.click", "label": "informe.docx", "ok": False, "error": "visible_button_not_found"}]
    step = _step("hacer clic en informe.docx", view, tried, objective="hacé clic en informe.docx")
    assert step is None or step.get("reason") != cu_navigation.REASON_DESCENT
    assert cu_navigation._tree_descent_step("informe.docx", view, [], None) is None


def test_explorer_a_folder_not_found_by_name_then_opens_the_tree() -> None:
    view = _explorer_documents()
    tried = [{"operation": "input.visible.click", "label": "proyectos", "ok": False, "error": "visible_button_not_found"}]
    step = _step("ir a proyectos", view, tried, objective="andá a proyectos")
    assert step is not None and step["reason"] == cu_navigation.REASON_DESCENT
    assert step["arguments"] == {"label": "Documentos", "index": 4, "manner": "open"}


def test_contracase_explorer_a_click_on_a_visible_folder_presses_its_row() -> None:
    """Revision 1 (finding 2): «hacer clic en carpeta3» chooses the row (the base's step), never opens «Documentos»."""

    step = _step("hacer clic en carpeta3", _explorer_documents(), [], objective="hacé clic en carpeta3")
    assert step is not None and step["arguments"] == {"label": "carpeta3", "index": 15}
    # With the node open and the folder twice (the tree's child and the row), the model's click by text is the row.
    chosen = _checked({"act": "click", "text": "carpeta3"}, _explorer_documents(opened=True), "hacer clic en carpeta3",
                      objective="hacé clic en carpeta3")
    assert chosen["operation"] == "input.visible.click" and chosen["arguments"]["index"] == 15


def test_explorer_going_to_a_visible_folder_opens_the_current_node_first() -> None:
    step = _step("ir a carpeta3", _explorer_documents(), [], objective="andá a carpeta3")
    assert step is not None and step["arguments"] == {"label": "Documentos", "index": 4, "manner": "open"}
    assert step["reason"] == cu_navigation.REASON_DESCENT_FIRST


def test_contracase_explorer_a_visible_place_expands_nothing() -> None:
    step = _step("ir a descargas", EXPLORER, [], objective="andá a Descargas")
    assert step is not None and step["arguments"] == {"label": "Descargas", "index": 2}


def test_contracase_network_places_and_drives_are_never_opened_blind() -> None:
    only_slow = {**EXPLORER, "controls": [c for c in EXPLORER["controls"] if c["i"] != 3]}
    step = cu_navigation._tree_descent_step("fotos", only_slow, [], None)
    assert step is None
    step = cu_navigation._tree_descent_step("fotos", EXPLORER, [], None)
    assert step is not None and step["arguments"]["label"] == "Este equipo"


def test_contracase_a_tree_of_the_content_is_no_navigation() -> None:
    content_tree = {
        "window": {"title": "Editor", "process": "x", "rect": {"x": 0, "y": 0, "w": 1200, "h": 800}},
        "controls": [
            {"i": 0, "kind": "TreeItem", "name": "Capítulo 1", "state": "collapsed", "zone": "C", "rect": _r(400, 200)},
            {"i": 1, "kind": "TreeItem", "name": "Capítulo 2", "state": "collapsed", "zone": "C", "rect": _r(400, 220)},
        ],
        "text": {},
    }
    assert cu_navigation._tree_descent_step("sección 3", content_tree, [], None) is None


CALCULATOR = {
    "window": {"title": "Calculadora", "process": "CalculatorApp", "rect": {"x": 0, "y": 0, "w": 400, "h": 600}},
    "controls": [
        {"i": 0, "kind": "Button", "name": "Abrir navegación", "zone": "TL", "rect": _r(4, 30, 40, 40)},
        {"i": 1, "kind": "Text", "name": "Modo estándar", "zone": "T", "rect": _r(60, 30, 120, 30)},
        {"i": 2, "kind": "Button", "name": "Uno", "zone": "B", "rect": _r(10, 500, 60, 40)},
    ],
    "text": {},
}


def test_contracase_a_window_without_collapsed_nodes_keeps_its_navigation_opener() -> None:
    assert cu_navigation._tree_descent_step("programador", CALCULATOR, [], None) is None
    step = _step("ir a programador", CALCULATOR, [], objective="poné la calculadora en programador")
    assert step is None or step.get("reason") != cu_navigation.REASON_DESCENT


# ------------------------------------------------- (b) el nodo actual no es un paso hacia otro lugar

def test_twin_v3_26_the_current_node_is_refused_with_the_way_on() -> None:
    refused = _checked({"act": "click", "i": 15}, _event_viewer(), "ir a sistema")
    assert refused["operation"] == "none" and refused["code"] == "already_current"
    assert "open" in refused["reason"]
    assert "already_current" in computer_use._RETRIED


def test_contracase_the_person_names_the_current_node() -> None:
    pressed = _checked({"act": "click", "i": 15}, _event_viewer(), "hacer clic en visor de eventos (local)",
                       objective="hacé clic en Visor de eventos (local)")
    assert pressed["operation"] == "input.visible.click" and pressed["arguments"]["index"] == 15


# ---------------------------------------------------------- (c) ambigüedad no es ausencia

def test_twin_v3_24_two_exact_names_choose_the_navigation_item() -> None:
    view = _event_viewer()
    view["controls"][9] = {"i": 9, "kind": "Button", "name": "Registros de aplicaciones y servicios", "zone": "R",
                            "rect": _r(900, 300)}
    chosen = _checked({"act": "click", "text": "Registros de aplicaciones y servicios"}, view,
                      "filtrar el registro de aplicacion por nivel error",
                      objective="filtra el registro de Aplicación por nivel Error")
    assert chosen["operation"] == "input.visible.click"
    assert chosen["arguments"] == {"label": "Registros de aplicaciones y servicios", "index": 18}


def test_two_exact_names_without_one_navigation_item_are_said_ambiguous() -> None:
    view = _event_viewer()
    view["controls"][9] = {"i": 9, "kind": "Button", "name": "Propiedades", "zone": "R", "rect": _r(900, 300)}
    view["controls"][10] = {"i": 10, "kind": "Button", "name": "Propiedades", "zone": "BR", "rect": _r(900, 600)}
    refused = _checked({"act": "click", "text": "Propiedades"}, view, "abrir las propiedades del registro")
    assert refused["operation"] == "none" and refused["code"] == "label_ambiguous"
    assert "2" in refused["reason"] and "label_ambiguous" in computer_use._RETRIED


# ------------------------------------------- (d) clic por nombre fuera de la vista dicho en otro idioma

V3_25 = "event viewer, go to windows logs > system and tell me the event ID of the most recent one"


def test_twin_v3_25_the_click_by_name_in_another_language_is_blind() -> None:
    view = _event_viewer()
    step = _step("hacer clic en windows logs", view, [OPENED], objective=V3_25)
    # The descent leaves a place said in English on a Spanish tree that shows a name like it to the model.
    assert step is not None and step["reason"] == cu_lookup.REASON_BY_NAME
    assert cu_lookup._blind_lookup(step, [OPENED], view, ("windows logs",), V3_25)


def test_contracase_paint_palette_by_name_stays_a_rule() -> None:
    paint = {
        "window": {"title": "Sin título - Paint", "process": "mspaint", "rect": {"x": 0, "y": 0, "w": 1200, "h": 800}},
        "controls": [{"i": n, "kind": "Button", "name": f"Herramienta {n}", "zone": "T"} for n in range(60)],
        "controlCount": 300, "text": {},
    }
    step = {"operation": "input.visible.click", "arguments": {"label": "Azul"}, "reason": cu_lookup.REASON_BY_NAME}
    assert not cu_lookup._blind_lookup(step, [], paint, ("azul",), "pintá de azul")


# --------------------------------------------------------- (e) reveal de un nodo cerrado lo abre

TASKS = {
    "window": {"title": "Programador de tareas", "process": "mmc", "rect": {"x": 0, "y": 0, "w": 1200, "h": 800}},
    "controls": [
        {"i": 14, "kind": "Button", "name": "Biblioteca del Programador de tareas", "state": "readonly", "zone": "TR",
         "rect": _r(900, 80)},
        {"i": 28, "kind": "TreeItem", "name": "Programador de tareas (local)", "state": "expanded", "zone": "TL", "rect": _r(4, 80)},
        {"i": 29, "kind": "TreeItem", "name": "Biblioteca del Programador de tareas", "state": "selected expanded",
         "zone": "TL", "rect": _r(20, 100)},
        {"i": 30, "kind": "TreeItem", "name": "ASUS", "zone": "TL", "rect": _r(36, 120)},
        {"i": 31, "kind": "TreeItem", "name": "GoogleSystem", "state": "collapsed", "zone": "TL", "rect": _r(36, 140)},
        {"i": 33, "kind": "TreeItem", "name": "Microsoft", "state": "collapsed", "zone": "TL", "rect": _r(36, 160)},
        {"i": 59, "kind": "DataItem", "name": "AMDRyzenMasterSDKTask", "state": "selected", "zone": "TR", "rect": _r(600, 200)},
        {"i": 60, "kind": "ListItem", "name": "Historial", "zone": "C", "rect": _r(600, 400)},
    ],
    "text": {"TL": ["Programador de tareas", "Microsoft"]},
}
TASKS = {**TASKS, "controls": _dense(TASKS["controls"])
}


def test_twin_v3_67_reveal_of_a_collapsed_node_opens_it() -> None:
    opened = _checked({"act": "reveal", "text": "Microsoft"}, TASKS, "hacer clic en windows",
                      objective="task scheduler: open library > microsoft > windows > defrag")
    assert opened["operation"] == "input.visible.click"
    assert opened["arguments"] == {"label": "Microsoft", "index": 33, "manner": "open"}


def test_contracase_r9_v3_47_reveal_of_a_visible_item_stays_already_in_view() -> None:
    refused = _checked({"act": "reveal", "text": "Historial"}, TASKS, "ir a historial")
    assert refused["operation"] == "none" and refused["code"] == "already_in_view"


def test_contracase_a_place_said_in_another_language_opens_no_node_blind() -> None:
    view = {**TASKS, "controlCount": 80}
    step = _step("hacer clic en windows", view, [], objective="task scheduler: open library > microsoft > windows > defrag")
    assert step is None or step.get("reason") != cu_navigation.REASON_DESCENT
    # Said in the window's language, the same tree is opened by the rule once its click by name found nothing
    # (revision 2, finding 1: before that, the click by name goes first).
    first = _step("hacer clic en defrag", view, [], objective="programador de tareas: abrí la carpeta defrag")
    assert first is not None and first["reason"] == cu_lookup.REASON_BY_NAME
    spanish = _step("hacer clic en defrag", view, [_not_found("defrag")],
                    objective="programador de tareas: abrí la carpeta defrag")
    assert spanish is not None and spanish["reason"] == cu_navigation.REASON_DESCENT
    assert spanish["arguments"] == {"label": "GoogleSystem", "index": 31, "manner": "open"}


def test_twin_v3_67_the_library_is_one_navigation_item_of_two_names() -> None:
    chosen = _checked({"act": "click", "text": "Biblioteca del Programador de tareas"}, TASKS, "hacer clic en library",
                      objective="task scheduler: open library > microsoft > windows > defrag")
    assert chosen["operation"] == "input.visible.click" and chosen["arguments"]["index"] == 29


# ------------------------------------------------------------- (f) abrir una ruta la introduce

def test_twin_v3_67_an_opening_verb_introduces_the_route() -> None:
    route = missions._route("open library > microsoft > windows > defrag")
    assert route is not None and route[1] == ["library", "microsoft", "windows", "defrag"]
    reads = missions._compound_reads("open library > microsoft > windows > defrag")
    assert reads is not None
    goals = [goal for goal, _, _ in reads]
    assert goals == ["hacer clic en library", "hacer clic en microsoft", "hacer clic en windows", "hacer clic en defrag"]
    assert not any(">" in goal for goal in goals)
    spanish = missions._compound_reads("abre biblioteca > microsoft > windows")
    assert spanish is not None and [goal for goal, _, _ in spanish][0] == "hacer clic en biblioteca"


@pytest.mark.parametrize(("text", "goal"), [
    ("programador de tareas: abrí biblioteca > microsoft > windows > defrag y decime la próxima ejecución",
     "hacer clic en biblioteca; luego hacer clic en microsoft; luego hacer clic en windows; luego hacer clic en defrag; "
     "y responder: decime la próxima ejecución"),
    ("en el programador de tareas, abrí biblioteca > microsoft > windows > defrag y decime la próxima ejecución",
     "hacer clic en biblioteca; luego hacer clic en microsoft; luego hacer clic en windows; luego hacer clic en defrag; "
     "y responder: decime la próxima ejecución"),
    ("en el bloc de notas abre archivo > guardar como", "hacer clic en archivo; luego hacer clic en guardar como"),
])
def test_twin_v3_67_spanish_the_frame_before_the_opening_verb_is_no_sub_goal(text: str, goal: str) -> None:
    """Revision 1 (finding 3): what is left before the opening verb («de tareas abri») is no free sub-goal."""

    mission = missions.mission_request(text, INDEX)
    assert mission is not None and mission.goal == goal, mission and mission.goal


def test_contracase_an_order_before_a_route_stays_a_sub_goal() -> None:
    reads = missions._compound_reads("gira la imagen 90 grados a la derecha desde el menu imagen > girar")
    assert reads is not None and reads[-1][0].startswith("gira la imagen")


def test_contracase_texts_with_a_sign_are_no_route() -> None:
    assert missions._route("abre paint") is None
    assert missions._route("escribi 5 > 3") is None
    assert missions._route("abri el archivo a>b.txt") is None
    reads = missions._compound_reads("abri el archivo a>b.txt")
    assert reads is None or not any(goal.startswith("hacer clic en ") for goal, _, _ in reads)


# ------------------------------------- revisión 2: el nodo actual abierto y la entrada que empieza por abrir

@pytest.mark.parametrize(("goal", "label"), [
    ("hacer clic en filtrar registro actual", "filtrar registro actual"),
    ("hacer clic en crear vista personalizada", "crear vista personalizada"),
    ("hacer clic en propiedades", "propiedades"),
    ("ir a ayuda", "ayuda"),
])
def test_contracase_current_node_open_the_actions_pane_command_is_clicked_by_name_first(goal: str, label: str) -> None:
    """Revision 2 (finding 1): the console's root «selected expanded» and a partial view; a command of the actions pane
    is no place of the tree: the click by name goes first (the base's one step), never four nodes opened before it."""

    step = _step(goal, _event_viewer(), [OPENED], objective="visor de eventos: " + goal)
    assert step is not None and step["reason"] == cu_lookup.REASON_BY_NAME, step
    assert step["arguments"] == {"label": label}


def test_contracase_task_scheduler_command_with_the_library_open_is_clicked_by_name_first() -> None:
    view = {**TASKS, "controlCount": 120}
    step = _step("hacer clic en crear tarea basica", view, [OPENED],
                 objective="programador de tareas: hace clic en Crear tarea básica")
    assert step is not None and step["reason"] == cu_lookup.REASON_BY_NAME, step
    # Only once its click by name found nothing would a node open.
    after = _step("hacer clic en crear tarea basica", view, [OPENED, _not_found("crear tarea basica")],
                  objective="programador de tareas: hace clic en Crear tarea básica")
    assert after is None or after.get("reason") != cu_lookup.REASON_BY_NAME


@pytest.mark.parametrize(("text", "first"), [
    ("hace clic en abrir reciente > notas", "abrir reciente"),
    ("click open recent > notes", "open recent"),
    ("anda a abrir reciente > notas", "abrir reciente"),
    ("pulsa abrir reciente > notas", "abrir reciente"),
])
def test_contracase_menu_entry_starting_with_an_opening_verb_keeps_its_word(text: str, first: str) -> None:
    route = missions._route(text)
    assert route is not None and route[1][0] == first, route


@pytest.mark.parametrize(("text", "goal"), [
    ("en el bloc de notas, hace clic en Abrir reciente > notas.txt", "hacer clic en abrir reciente; luego hacer clic en notas"),
    ("visual studio code: click Open Recent > notes.txt", "hacer clic en open recent; luego hacer clic en notes"),
])
def test_contracase_mission_keeps_the_entry_the_person_named(text: str, goal: str) -> None:
    mission = missions.mission_request(text, INDEX)
    assert mission is not None and mission.goal.startswith(goal), mission and mission.goal


@pytest.mark.parametrize("text", ["abri 5 > 3", "open 5 > 3", "abre 10 > 2"])
def test_contracase_an_opening_verb_before_numbers_names_no_route(text: str) -> None:
    assert missions._route(text) is None


def test_a_place_not_found_by_name_and_shown_by_the_descent_is_clicked() -> None:
    """Revision 2 (finding 1): the click by name that found nothing pressed nothing; the node the descent opened shows
    the place, which is clicked by its identity."""

    missed = _not_found("sistema")
    history = [OPENED, missed, _opened("Registros de Windows", 17)]
    assert cu_history._before_unfolding_misses(history) == [OPENED, _opened("Registros de Windows", 17)]
    step = _step("ir a sistema", _event_viewer(logs_state="expanded", children=True), history)
    assert step is not None and step["arguments"] == {"label": "Sistema", "index": 42}


def test_contracase_a_name_not_found_with_no_node_opened_since_stays_failed() -> None:
    history = [OPENED, _opened("Registros de Windows", 17), _not_found("sistema")]
    assert cu_history._before_unfolding_misses(history) == history
    pressed = {"operation": "input.visible.click", "label": "Sistema", "index": 42, "ok": False, "error": "no_effect"}
    assert cu_history._before_unfolding_misses([pressed, _opened("Registros de Windows", 17)])[0] == pressed
