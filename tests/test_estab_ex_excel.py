"""Encargo EX (tandas n5 y n6, t4-c06 «bro abre excel y crea un blank workbook»).

n5: the click on «Libro en blanco» made «Libro1 - Excel», the model then pressed the title's own button «Libro1 - Excel»
(it opened «Guardar este archivo») and the reserve template said «la pantalla todavía no muestra que haya quedado
hecho». n6: Excel was read through that dialog, left open, and the mission said «no vi en la pantalla un control con el
que seguir». The real payloads are tests/data/ex_excel_payloads.json; the App's side is
ComputerUseLoopTests.EstabEx.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from baxy_mind import cu_documents, cu_finals, cu_gates, cu_window
from baxy_mind.semantic import missions

PAYLOADS = json.loads((ROOT / "tests" / "data" / "ex_excel_payloads.json").read_text(encoding="utf-8"))
REQUEST = "bro abre excel y crea un blank workbook"
APPS = ("Excel", "Word", "PowerPoint", "Bloc de notas", "Paint", "Discord")


def _control(i: int, kind: str, name: str, state: str = "", value: str | None = None) -> dict:
    control: dict = {"i": i, "kind": kind, "name": name}
    if state:
        control["state"] = state
    if value is not None:
        control["value"] = value
    return control


def _new_workbook_view() -> dict:
    # The look n5 decided its second step on (model_calls request 99): the new workbook, nothing written in it.
    return {
        "window": {"title": "Libro1 - Excel", "process": "EXCEL", "requested": True,
                   "focused": {"kind": "DataItem", "name": "A1"}},
        "controls": [
            _control(8, "Button", "Guardar"), _control(10, "Button", "‪Libro1‬ - Excel"),
            _control(16, "Button", "Pestaña Archivo"), _control(17, "TabItem", "Inicio", "selected"),
            _control(44, "Edit", "Barra de fórmulas"), _control(50, "Button", "Agregar hoja"),
            _control(51, "TabItem", "Hoja1", "selected"), _control(61, "Pane", "Libro1"),
            _control(63, "Pane", "Hoja Hoja1", "selected"),
        ],
    }


def _save_pane_view() -> dict:
    # The look n6 began on (its step 1): Excel read through «Guardar este archivo», an empty title.
    return {
        "window": {"title": "", "process": "EXCEL", "requested": True, "modal": True,
                   "focused": {"kind": "Edit", "name": "Nombre de archivo", "value": "Libro1"}},
        "controls": [
            _control(0, "Edit", "Nombre de archivo", "focused", "Libro1"),
            _control(1, "ComboBox", "Guardar como tipo", "collapsed", "Libro de Excel (*.xlsx)"),
            _control(6, "Button", "Guardar"), _control(7, "Button", "Cancelar"), _control(9, "Button", "Cerrar"),
            _control(10, "Window", "Guardar este archivo"), _control(11, "Text", "Guardar este archivo"),
        ],
    }


def _blank_click(created: str | None = "Libro1") -> dict:
    step = {"step": 1, "operation": "input.visible.click", "label": "Libro en blanco", "ok": True, "kind": "ListItem",
            "broughtNew": True}
    if created is not None:
        step["createdDocument"] = created
    return step


# (1) The plan: an order to create the offer of a whole blank document is its creation, as choosing it is.


def test_a_blank_workbook_ordered_is_planned_as_its_creation() -> None:
    arguments = missions.mission_request(REQUEST, APPS).arguments()
    assert arguments["goal"] == "crear blank workbook"
    assert arguments["application"] == "Excel"
    assert arguments["successCheck"] == "stepDone:input.visible.click:=blank workbook"
    assert missions.read_clause("creá un documento en blanco") == (
        "crear documento en blanco", "stepDone:input.visible.click:=documento en blanco")


def test_creating_what_is_no_blank_document_keeps_its_reading() -> None:
    # Contracases: a part of a document in blank, a new one with no blank word, and a named folder are read as before.
    assert missions.read_clause("crea una hoja en blanco")[0] != "crear hoja en blanco"
    assert missions.read_clause("crea un libro nuevo") == ("crea un libro nuevo", None)
    assert missions.read_clause("crea una carpeta llamada ramo")[0] == "crear carpeta ramo"


# (1) The step: the click the App recorded as making the workbook ends the sub-goal; nothing is pressed after it.


def test_the_recorded_workbook_closes_the_subgoal_with_no_other_click() -> None:
    done = cu_documents._new_document_made("crear blank workbook", _new_workbook_view(), [_blank_click()])
    assert done is not None
    assert done["operation"] == "done"
    assert done["arguments"]["evidence"] == "Libro1"


def test_without_the_record_or_with_content_nothing_closes_it() -> None:
    # Contracases: no record of the App (the model decides), a record of another document, and a sheet with a cell
    # written (no blank workbook).
    view = _new_workbook_view()
    assert cu_documents._new_document_made("crear blank workbook", view, [_blank_click(None)]) is None
    assert cu_documents._new_document_made("crear blank workbook", view, [_blank_click("Libro2")]) is None
    written = copy.deepcopy(view)
    written["controls"].append(_control(70, "DataItem", "A1", value="hola"))
    assert cu_documents._new_document_made("crear blank workbook", written, [_blank_click()]) is None
    # Nor a goal that is not the blank item («escribir hola» in the new workbook).
    assert cu_documents._new_document_made("escribir hola", view, [_blank_click()]) is None


# (2) The title's own button names the window: never a step.


def test_the_title_button_is_the_window_frame() -> None:
    view = _new_workbook_view()
    title_button = view["controls"][1]
    assert cu_window._frame_off_goal(view, title_button, "crear blank workbook") is True
    # Contracases: a command of the ribbon, and a button named as a title that names no document («Calculadora»).
    assert cu_window._frame_off_goal(view, view["controls"][0], "crear blank workbook") is False
    calculator = {"window": {"title": "Calculadora"}, "controls": [_control(1, "Button", "Calculadora")]}
    assert cu_window._frame_off_goal(calculator, calculator["controls"][0], "ir a calculadora") is False


# (3) A modal dialog the mission did not open is said, never pressed.


def test_an_inherited_dialog_is_said_and_nothing_pressed() -> None:
    opened = [{"step": 1, "operation": "app.open", "appId": "Excel", "ok": True, "alreadyRunning": True}]
    stop = cu_gates.inherited_dialog(_save_pane_view(), opened, "crear blank workbook", 0)
    assert stop is not None
    assert stop["operation"] == "none" and stop["code"] == cu_gates.APP_GATE
    assert stop["arguments"] == {"evidence": "Guardar este archivo", "gate": "dialog"}


def test_a_dialog_of_the_mission_or_of_the_goal_is_no_inherited_one() -> None:
    view = _save_pane_view()
    # Contracases: the mission acted before (its own click opened it), a later sub-goal, the goal names the dialog's
    # control, and a window read as itself.
    acted = [{"step": 1, "operation": "input.visible.click", "label": "Libro1 - Excel", "ok": True}]
    assert cu_gates.inherited_dialog(view, acted, "crear blank workbook", 0) is None
    assert cu_gates.inherited_dialog(view, [], "crear blank workbook", 1) is None
    assert cu_gates.inherited_dialog(view, [], "hacer clic en cancelar", 0) is None
    plain = copy.deepcopy(view)
    del plain["window"]["modal"]
    assert cu_gates.inherited_dialog(plain, [], "crear blank workbook", 0) is None


# The finals, from the real payloads.


def test_the_workbook_made_is_told_from_the_floor() -> None:
    # n5's observed as the mission now leaves it: the plan's goal, the one click the App recorded, the new workbook.
    observed = copy.deepcopy(PAYLOADS["n5"]["observed"])
    observed["goal"] = "crear blank workbook"
    observed["steps"] = [{**observed["steps"][0], "createdDocument": "Libro1"}]
    observed["stepCount"] = 1
    observed["window"] = {**observed["window"], "title": "Libro1 - Excel", "focused": {"kind": "DataItem", "name": "A1"}}
    observed["screen"] = {"title": "Libro1 - Excel", "values": [], "lines": ["Hoja1", "Listo"]}
    observed["evidence"] = "Libro1"
    assert cu_finals.floor_first(observed, False, True) == "Listo, creé «Libro1»."
    # The reserve template is the same sentence: it never denies the workbook the last read shows.
    assert cu_finals.floor_sentence(observed, False, True) == "Listo, creé «Libro1»."


def test_the_old_draft_and_template_were_the_defect() -> None:
    # The real n5 record: the vetoed draft and the template that denied the workbook (evidence of the cause).
    assert PAYLOADS["n5"]["draft"] == "Abrí Excel y guardé el libro como Libro1."
    assert PAYLOADS["n5"]["template"].startswith("Llevo dos pasos en «Excel», pero la pantalla todavía no muestra")


def test_the_inherited_dialog_is_said_in_the_final() -> None:
    observed = copy.deepcopy(PAYLOADS["n6"]["observed"])
    assert observed["stoppedBy"] == "computer_use_no_step_visible"
    observed["stoppedBy"] = "computer_use_app_gate"
    observed["gate"] = {"kind": "dialog", "text": "Guardar este archivo"}
    assert cu_finals.floor_first(observed, False, False) == (
        "No pude hacerlo en «Excel»: la aplicación tiene abierto «Guardar este archivo», que no abrí yo, "
        "así que no pulsé nada ahí."
    )
    assert cu_finals.floor_first(observed, True, False) == (
        "I couldn't do it in «Excel»: the application has «Guardar este archivo» open, which I did not open, "
        "so I pressed nothing there."
    )
