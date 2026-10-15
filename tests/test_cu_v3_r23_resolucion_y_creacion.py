"""Ronda 23, resolución de nombres y creación (comprobación en vivo r21: v3-23, v3-35). (a) La resolución de nombres de
la regla quita lo que el validador vetará (el menú de sistema, el marco) y cuenta la celda de una fila como la fila; con
un nodo del árbol del mismo nombre, el nodo gana para «ir a». (b) Una meta que crea una cosa y una vista con un único
mando que la crea: la regla lo pulsa por índice, sin codificador. Vistas reales del journal de la pasada r21
(``data/cu_v3_r23_vistas.json``)."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from baxy_mind.semantic.missions import fold as missions_fold
from baxy_mind import cu_vocabulary
from baxy_mind import cu_view
from baxy_mind import cu_window
from baxy_mind import cu_creation
from baxy_mind import cu_navigation
from baxy_mind import cu_rules
from baxy_mind import cu_validate

VIEWS = json.loads((Path(__file__).resolve().parent / "data" / "cu_v3_r23_vistas.json").read_text(encoding="utf-8"))
OBJECTIVE_23 = "en Visor de eventos, anda a registros de windows, sistema"
GOAL_35 = "crea una nota rapida nueva"


def _v23() -> dict:
    return copy.deepcopy(VIEWS["v3_23_registros_de_windows"])


def _v35() -> dict:
    return copy.deepcopy(VIEWS["v3_35_nota_rapida"])


def _step(goal: str, view: dict, history: list[dict] | None = None, objective: str = OBJECTIVE_23) -> dict | None:
    return cu_rules.deterministic_step(goal=goal, view=view, history=history or [], objective=objective)


def _with(view: dict, *controls: dict) -> dict:
    view["controls"] = [*view["controls"], *controls]
    return view


def _r(x: int, y: int, w: int, h: int) -> dict:
    return {"x": x, "y": y, "w": w, "h": h}


# ---------------------------------------------------------------- (a) v3-23

def test_v3_23_real_view_opens_the_current_node_never_the_system_menu() -> None:
    view = _v23()
    step = _step("ir a sistema", view)
    assert step is not None and step["operation"] == "input.visible.click"
    assert step["arguments"] == {"label": "Registros de Windows", "index": 19, "manner": "open"}
    assert step["reason"] == cu_navigation.REASON_DESCENT_FIRST
    assert not cu_validate._presses_system_menu(view, step["arguments"], "ir a sistema")


def test_v3_23_after_the_node_opened_its_tree_child_is_the_place() -> None:
    view = _with(
        _v23(),
        {"i": 58, "kind": "TreeItem", "name": "Aplicación", "state": "", "rect": _r(545, 483, 80, 18), "zone": "TL"},
        {"i": 59, "kind": "TreeItem", "name": "Sistema", "state": "", "rect": _r(545, 537, 80, 18), "zone": "TL"},
    )
    view["controls"][19]["state"] = "selected expanded focused"
    step = _step("ir a sistema", view, [{"operation": "input.visible.click", "label": "Registros de Windows",
                                         "index": 19, "manner": "open", "ok": True}])
    assert step is not None and step["arguments"] == {"label": "Sistema", "index": 59}


def test_a_tree_node_drawn_out_of_the_left_column_still_wins_over_the_row_for_going() -> None:
    view = _with(_v23(), {"i": 59, "kind": "TreeItem", "name": "Sistema", "state": "", "rect": _r(700, 600, 80, 18),
                          "zone": "C"})
    step = _step("ir a sistema", view)
    assert step is not None and step["arguments"] == {"label": "Sistema", "index": 59}


def test_clicking_the_visible_row_presses_the_row_not_the_tree() -> None:
    # Contracase: «hacer clic en» a visible row presses that row (r21 revision 1, finding 2), never the system menu.
    step = _step("hacer clic en sistema", _v23())
    assert step is not None and step["arguments"] == {"label": "Sistema", "index": 56}


def test_a_row_cell_is_the_row_and_two_separate_rows_stay_two() -> None:
    view = _v23()
    controls = view["controls"]
    assert cu_view._row_cell(controls[57], controls)
    assert not cu_view._row_cell(controls[56], controls)
    assert cu_view.find_control({"controls": [controls[56], controls[57]]}, "Sistema")["i"] == 56
    # Contracase: two rows named alike in two lists, neither inside the other: still ambiguous.
    other = {"i": 70, "kind": "DataItem", "name": "Sistema", "state": "", "rect": _r(739, 800, 360, 22), "zone": "B"}
    two = {"controls": [controls[56], controls[57], other]}
    assert cu_view.find_control(two, "Sistema") is None
    assert len(cu_rules._controls_carrying(two, ("Sistema",), None, True)) == 2
    # A cell drawn outside a row of its name is a control of its own.
    loose = {**controls[57], "rect": _r(300, 900, 60, 18)}
    assert not cu_view._row_cell(loose, [controls[56], loose])


def test_the_system_menu_stays_a_candidate_when_the_goal_asks_for_the_window_menu() -> None:
    view = _v23()
    menu = view["controls"][32]
    kept = cu_window._without_vetoed(view, "minimiza la ventana con el menu de sistema")
    assert any(control is menu for control in kept["controls"])
    dropped = cu_window._without_vetoed(view, "ir a sistema")
    assert not any(control is menu for control in dropped["controls"])
    # Only the system menu named so: going there is never a press on it.
    alone = _v23()
    alone["controls"] = [c for c in alone["controls"] if not (c.get("name") == "Sistema" and c["i"] != 32)]
    step = _step("ir a sistema", alone, [{"operation": "input.visible.click", "label": "sistema", "ok": False,
                                          "error": "visible_button_not_found"}])
    assert step is None or (step.get("arguments") or {}).get("index") != 32


# ---------------------------------------------------------------- (b) v3-35

def test_v3_35_real_view_presses_the_one_creating_command_by_index() -> None:
    view = _v35()
    step = _step(GOAL_35, view, objective=GOAL_35)
    assert step == {"operation": "input.visible.click", "arguments": {"label": "Nueva nota", "index": 0},
                    "reason": cu_creation.REASON_CREATING}
    assert cu_creation._creation_refusal(step, view, [], GOAL_35) is None


def test_v3_35_never_twice_nor_after_another_click() -> None:
    pressed = {"operation": "input.visible.click", "label": "Nueva nota", "name": "Nueva nota", "index": 0,
               "ok": True, "broughtNew": True}
    assert cu_creation._creating_command_step(GOAL_35, _v35(), [pressed]) is None


def test_two_commands_creating_the_asked_thing_leave_the_model_to_choose() -> None:
    view = _with(_v35(), {"i": 16, "kind": "Button", "name": "Agregar nota", "state": "", "rect": _r(820, 341, 40, 40),
                          "zone": "TL"})
    assert cu_creation._creating_command_step(GOAL_35, view, []) is None


def test_the_command_shares_a_word_with_what_is_asked() -> None:
    # «Crear una nueva sección» never for a page; «Agregar página» is the one that creates it.
    view = {"window": {"title": "Cuaderno"}, "controls": [
        {"i": 0, "kind": "Button", "name": "Crear una nueva sección", "state": "", "rect": _r(10, 100, 120, 30), "zone": "TL"},
        {"i": 1, "kind": "Button", "name": "Agregar página", "state": "", "rect": _r(200, 100, 120, 30), "zone": "T"},
    ], "text": {}}
    step = cu_creation._creating_command_step("crea una pagina nueva", view, [])
    assert step is not None and step["arguments"] == {"label": "Agregar página", "index": 1}
    # No command creates a folder: the rule does not apply.
    assert cu_creation._creating_command_step("crea una carpeta llamada informes", view, []) is None


def test_quantities_content_items_and_disabled_commands_are_not_pressed() -> None:
    assert cu_creation._creating_command_step("crea dos notas nuevas", _v35(), []) is None
    content = _v35()
    content["controls"][0] = {**content["controls"][0], "kind": "ListItem"}
    assert cu_creation._creating_command_step(GOAL_35, content, []) is None
    disabled = _v35()
    disabled["controls"][0] = {**disabled["controls"][0], "state": "disabled"}
    assert cu_creation._creating_command_step(GOAL_35, disabled, []) is None
    # A goal that creates nothing never reaches the rule.
    assert cu_creation._creating_command_step("ir a nueva nota", _v35(), []) is None


# ---------------------------------------------------------------- revisión 1

MENUS = json.loads((Path(__file__).resolve().parent / "data" / "cu_menus_teclas_vistas.json").read_text(encoding="utf-8"))


def test_r1_a_goal_that_changes_the_existing_note_never_presses_new_note_on_the_real_view() -> None:
    for goal in ("agrega pan a la nota", "agrega leche a la nota de compras", "agrega color morado a la nota",
                 "crea un recordatorio en la nota", "haz la nota morada", "crear nota morada"):
        step = _step(goal, _v35(), objective=goal)
        assert step is None or (step.get("arguments") or {}).get("label") != "Nueva nota", goal
        assert cu_creation._creating_command_step(goal, _v35(), []) is None, goal
    # Contracase: the object right after the verb, introduced as a new one, is still pressed.
    for goal in ("crea una nota nueva", "hazme una nota", "crea otra nota", "add a new note"):
        step = cu_creation._creating_command_step(goal, _v35(), [])
        assert step is not None and step["arguments"] == {"label": "Nueva nota", "index": 0}, goal


def _commands(*controls: tuple[str, str]) -> dict:
    return {"window": {"title": "Ventana"}, "text": {}, "controls": [
        {"i": i, "kind": kind, "name": name, "state": "", "rect": _r(10 + 130 * i, 100, 120, 30), "zone": "T"}
        for i, (kind, name) in enumerate(controls)
    ]}


def test_r1_a_complement_or_another_place_is_never_the_thing_created() -> None:
    slides = _commands(("SplitButton", "Nueva diapositiva"), ("Button", "Negrita"))
    for goal in ("inserta una imagen en la diapositiva", "agrega un titulo a la diapositiva"):
        assert cu_creation._creating_command_step(goal, slides, []) is None, goal
    mail = _commands(("Button", "Nuevo correo electrónico"), ("Button", "Responder"))
    assert cu_creation._creating_command_step("crea una regla para el correo de juan", mail, []) is None
    folder = _commands(("Button", "Nueva carpeta"), ("Button", "Copiar"))
    assert cu_creation._creating_command_step("crea una carpeta en el escritorio", folder, []) is None
    # Contracases: the thing itself, said as a new one.
    assert cu_creation._creating_command_step("agrega una diapositiva", slides, [])["arguments"]["index"] == 0
    assert cu_creation._creating_command_step("crea una carpeta nueva", folder, [])["arguments"]["index"] == 0
    assert cu_creation._creating_command_step("crea un correo nuevo", mail, [])["arguments"]["index"] == 0


def test_r1_created_object_reads_only_the_indefinite_object_after_the_verb() -> None:
    from baxy_mind.semantic import cu_tipos

    rules = cu_vocabulary._evidence_rules()

    def read(goal: str) -> str | None:
        return cu_tipos.created_object(goal, rules["creatingGoal"], rules["creatingQuantity"])

    assert read("crea una nota rapida nueva") == "nota rapida nueva"
    assert read("add a new slide") == "slide"
    assert read("agrega a la nota pan") is None
    assert read("crea la nota") is None
    assert read("crea dos notas") is None
    assert read("ir a una nota") is None


def test_r1_the_only_exact_name_vetoed_never_falls_to_a_partial_carrier_on_obs_settings() -> None:
    for view in (MENUS[4], MENUS[5]):
        for goal in ("ir a sistema", "hacer clic en sistema"):
            # Neither the group that merely carries the name nor the vetoed system menu: the model's step.
            assert _step(goal, copy.deepcopy(view), objective=goal) is None, goal
    # Contracase: with another control named exactly so, the vetoed system menu still steps aside (v3-23).
    view = _v23()
    kept = cu_window._without_vetoed(view, "ir a sistema", ("sistema",))
    assert not any(control is view["controls"][32] for control in kept["controls"])
    only = _v23()
    only["controls"] = [c for c in only["controls"] if not (c.get("name") == "Sistema" and c["i"] != 32)]
    assert cu_window._without_vetoed(only, "ir a sistema", ("sistema",)) is only


# ---------------------------------------------------------------- revisión 2

EDGE = json.loads((Path(__file__).resolve().parent / "data" / "cu_v3_vistas_motor_lugar.json").read_text(encoding="utf-8"))


def test_r2_adding_this_page_to_favorites_never_creates_a_page_on_the_real_edge_view() -> None:
    # Real Edge view: «Agregar esta página a favoritos (Ctrl+D)» adds a favourite to the person's browser, data the
    # goal does not name; the step is the model's.
    for goal in ("crea una pagina nueva", "agrega una pagina"):
        assert cu_creation._creating_command_step(goal, copy.deepcopy(EDGE["edge_ayuda"]["vista"]), []) is None, goal
    # Contracase: a command that creates a new page, on the same view, is still pressed.
    view = copy.deepcopy(EDGE["edge_ayuda"]["vista"])
    view["controls"][10] = {**view["controls"][10], "name": "Nueva página (Ctrl+N)", "state": ""}
    step = cu_creation._creating_command_step("crea una pagina nueva", view, [])
    assert step is not None and step["arguments"] == {"label": "Nueva página (Ctrl+N)", "index": 10}
    assert step["reason"] == cu_creation.REASON_CREATING


def test_r2_a_command_that_puts_an_existing_thing_somewhere_is_never_the_one_that_creates() -> None:
    for goal, name in (
        ("create a new page", "Add this page to favorites (Ctrl+D)"),
        ("crea un contacto nuevo", "Agregar contacto a favoritos"),
        ("crea una nota", "Agregar nota al contacto"),
        ("crea un evento", "Agregar evento a mi calendario"),
        ("agrega una imagen", "Agregar imagen a la colección"),
        ("crea una nota", "Agregar la nota"),
        ("crea una nota", "Agregar a notas"),
    ):
        assert cu_creation._creating_command_step(goal, _commands(("Button", name)), []) is None, (goal, name)
    # Contracases: the command that makes a new one, shortcut included.
    for goal, name in (
        ("create a new page", "Add a page"),
        ("crea un contacto nuevo", "Nuevo contacto"),
        ("crea una nota", "Agregar nota"),
        ("crea un evento", "Crear un evento nuevo (Ctrl+Shift+E)"),
        ("agrega una imagen", "Insertar imagen"),
    ):
        step = cu_creation._creating_command_step(goal, _commands(("Button", name)), [])
        assert step is not None and step["arguments"] == {"label": name, "index": 0}, (goal, name)


def test_r2_creating_command_object_reads_only_a_new_object_with_nothing_after_it() -> None:
    from baxy_mind.semantic import cu_tipos

    pattern = cu_vocabulary._evidence_rules()["creatingCommand"]

    def read(name: str) -> str | None:
        return cu_tipos.creating_command_object(missions_fold(name).strip(), pattern)

    assert read("Nueva nota") == "nota"
    assert read("Crear una nueva sección") == "seccion"
    assert read("Add a slide") == "slide"
    assert read("Nueva página (Ctrl+N)") == "pagina"
    assert read("Agregar esta página a favoritos (Ctrl+D)") is None
    assert read("Add the note") is None
    assert read("Agregar a favoritos") is None
    assert read("Favoritos") is None
