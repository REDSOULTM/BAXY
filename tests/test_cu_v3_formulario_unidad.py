"""Ronda 20b, palanca 2: el formulario es una unidad (pasada r18, t-long-3).

En t-long-3 («Open Paint, resize the canvas to 500 by 500 pixels, …») se aceptó el diálogo con «Mantener la relación
de aspecto» encendido y el final dijo «resize the canvas to 500 by 500» con el lienzo en 177×500. Lo que la evidencia
muestra (revisión 2, bloqueante 1): el 177 sólo aparece en la barra de estado («177 x 500píxeles») con el diálogo ya
cerrado, y los pasos 4 y 5 fueron de regla, sin vista guardada; nada prueba que el diálogo mostrara 177 antes de
Aceptar. Los controles de ``_resize_view`` (nombre, tipo, estado del vínculo) son los del diálogo que muestran las
llamadas al modelo de v2-t-long-3; sus valores son construidos para cada momento, salvo 888/500 (una llamada de ese
mismo fichero: Vertical 500 escrito, Horizontal recalculado a 888 desde 5760×3240 con el vínculo encendido).

- Planificador: cada campo después del primero se cumple sólo con los anteriores en su valor; la meta del abridor dice
  dónde van los valores, nunca los valores.
- Motor: un campo que la ventana cambió al poner otro se vuelve a poner una vez, antes apagando el vínculo encendido;
  si vuelve a cambiar, la misión para con su causa (linked_fields), sin aceptar.
- Final: una cifra que ninguna parte alcanzada (un formulario sólo entero) ni la pantalla sostiene se veta.

Revisión 1: la pantalla sola no sostiene una cifra (sólo confirma la de una parte alcanzada, ligada a su campo), una
cifra negada en su cláusula no se afirma, mantener la proporción ata igual los campos (sólo prohíbe apagar el
interruptor) y un número se sostiene en un campo sólo con límites de dígito («1500» no es 500).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from baxy_mind import cu_forms
from baxy_mind import cu_rules
from baxy_mind import known_folders
from baxy_mind.semantic import claims, cu_tipos, missions
from baxy_mind import computer_use_finals

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "scripts" / "cu_live" / "cases"
APPS = ("Paint", "Word", "Bloc de notas", "Notepad")


@pytest.fixture(autouse=True)
def _documents(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(known_folders, "known_folder", lambda folder: {"documents": r"D:\Perfil\Documentos"}.get(folder))


def _case(name: str) -> str:
    said = (CASES / f"{name}.turns").read_text(encoding="utf-8").strip()
    # Estabilización L: t-long-3 as said draws a rectangle, the drag limit (never a mission, see
    # test_cu_v3_cierre_subobjetivos); its form is read on the same order without the drawing clause.
    return said.replace(", draw a red filled rectangle in the middle", "") if name == "t-long-3" else said


def _steps(text: str) -> list[tuple[str, str | None]]:
    mission = missions.mission_request(text, APPS)
    assert mission is not None and mission.steps, text
    return [(step.goal, step.success_check) for step in mission.steps]


def _check(steps: list[tuple[str, str | None]], goal: str) -> str:
    return next(check for said, check in steps if said == goal) or ""


# Los controles del diálogo de cambiar tamaño como los muestran las llamadas al modelo de v2-t-long-3; los valores de
# cada momento son construidos (ver el docstring del módulo).
def _resize_view(horizontal: str, vertical: str, lock: str = "on") -> dict:
    return {
        "window": {"title": "Sin título - Paint", "process": "mspaint"},
        "controls": [
            {"i": 21, "kind": "RadioButton", "name": "Porcentaje", "state": "focused"},
            {"i": 22, "kind": "RadioButton", "name": "Píxeles", "state": "selected"},
            {"i": 23, "kind": "Edit", "name": "Horizontal", "value": horizontal},
            {"i": 24, "kind": "Button", "name": "Mantener la relación de aspecto", "state": lock},
            {"i": 25, "kind": "Edit", "name": "Vertical", "value": vertical},
            {"i": 26, "kind": "Edit", "name": "Horizontal Mínimo-89 Máximo89", "value": "0°"},
            {"i": 27, "kind": "Edit", "name": "Vertical Mínimo-89 Máximo89", "value": "0°"},
            {"i": 28, "kind": "Button", "name": "Aceptar"},
            {"i": 29, "kind": "Button", "name": "Cancelar"},
        ],
    }


def _typed(field: str, text: str) -> dict:
    return {"operation": "input.text.type", "ok": True, "field": field, "text": text}


def _step(goal: str, check: str, view: dict, history: list[dict]) -> dict | None:
    return cu_rules.deterministic_step(goal=goal, view=view, history=history, success_check=check)


# ------------------------------------------------------------ planificador


def test_t_long_3_the_second_field_holds_only_with_the_first_and_the_opener_carries_no_values() -> None:
    steps = _steps(_case("t-long-3"))
    goals = [goal for goal, _ in steps]
    assert "resize the canvas, donde se ponen ancho y alto" in goals
    assert not any("(500)" in goal for goal in goals)
    width = _check(steps, "poner ancho en 500")
    height = _check(steps, "poner alto en 500")
    assert width == "value:ancho=500|value:width=500|value:horizontal=500"
    # The names of one language side by side first: the dialog's own «Horizontal»/«Vertical» pair is there.
    terms = height.split("|")
    assert terms[:3] == ["value:ancho=500&value:alto=500", "value:width=500&value:height=500",
                         "value:horizontal=500&value:vertical=500"]
    assert all(term.count("&") == 1 for term in terms)
    assert len(height.encode("utf-8")) <= 512


def test_t_form_1_keeps_its_steps_and_the_height_field_reads_the_width_too() -> None:
    steps = _steps(_case("t-form-1"))
    assert [goal for goal, _ in steps] == [
        "cambiale el tamano a la imagen, donde se ponen ancho y alto", "activar pixeles",
        "desactivar mantener la relacion de aspecto", "poner ancho en 800", "poner alto en 600", "hacer clic en aceptar"]
    assert _check(steps, "poner alto en 600").startswith("value:ancho=800&value:alto=600|")


def test_keeping_the_link_said_still_ties_the_fields() -> None:
    # Revisión 1, bloqueante 3: with the link kept, the width set to 800 recalculates the height and the height set to
    # 600 recalculates the width; each part held alone and «800 por 600» passed. The fields are tied all the same.
    reads = missions._form_reads("cambia el tamano a 800 de ancho y 600 de alto manteniendo la proporcion")
    assert reads is not None
    height = next(check for goal, check, _ in reads if goal == "poner alto en 600")
    assert height.startswith("value:ancho=800&value:alto=600|")
    # One field alone is no form: nothing to tie nor to switch off.
    assert missions._form_reads("cambia el ancho a 500 manteniendo la proporcion") is None
    assert cu_tipos.keeps_link("resize it to 500 by 500 keeping the aspect ratio")
    assert not cu_tipos.keeps_link("resize the canvas to 500 by 500 pixels")


def test_replace_fields_stay_independent_checks() -> None:
    reads = missions._form_reads("reemplaza «casa» por «hogar»")
    assert reads is not None
    assert all("&" not in (check or "") for _, check, _ in reads)


# ------------------------------------------------------------ motor


HEIGHT = "poner alto en 500"


def _height_check() -> str:
    return _check(_steps(_case("t-long-3")), HEIGHT)


def test_t_long_3_a_width_recalculated_by_the_lock_switches_the_lock_off_then_sets_the_width_again() -> None:
    check = _height_check()
    typed_height = [_typed("Vertical", "500")]
    # Vertical 500 typed and Horizontal recalculated with the lock on (a constructed 177; the 177 of t-long-3 was only
    # seen on the status bar, revisión 2).
    first = _step(HEIGHT, check, _resize_view("177", "500"), typed_height)
    assert first is not None and first["operation"] == "input.visible.click"
    assert first["arguments"] == {"label": "Mantener la relación de aspecto", "index": 24}
    assert "Horizontal cambió a 177 al escribir" in str(first["reason"])
    # The lock off: the width is set again, by its label, replacing what it held.
    clicked = [*typed_height, {"operation": "input.visible.click", "ok": True, "label": "Mantener la relación de aspecto"}]
    second = _step(HEIGHT, check, _resize_view("177", "500", lock="off"), clicked)
    assert second is not None and second["operation"] == "input.text.type"
    assert second["arguments"] == {"text": "500", "field": "Horizontal", "replace": True}
    # Both hold: nothing more to do in the sub-goal (the shell closes it on its check).
    assert _step(HEIGHT, check, _resize_view("500", "500", lock="off"), [*clicked, _typed("Horizontal", "500")]) is None


def test_fields_that_change_each_other_again_stop_unaccepted_with_their_cause() -> None:
    check = _height_check()
    history = [_typed("Vertical", "500"), _typed("Horizontal", "500")]
    # No lock named on screen; the width set again moved the height: the height was set in this sub-goal already.
    stop = _step(HEIGHT, check, _resize_view("500", "281", lock="off"), history)
    assert stop is not None and stop["operation"] == "none"
    assert stop["code"] == cu_forms.LINKED_FIELDS
    data = json.loads((ROOT / "src" / "baxy_mind" / "data" / "operation_floor.v1.json").read_text(encoding="utf-8"))
    causes = next(value["causes"] for value in data.values() if isinstance(value, dict) and "causes" in value)
    assert set(causes["computer_use_linked_fields"]) == {"es", "en"}


KEPT = "cambiá el tamaño a 500 de ancho y 500 de alto manteniendo la proporción"


def test_a_kept_link_is_never_switched_off_and_the_oscillation_stops_the_mission() -> None:
    check = _height_check()
    typed_height = [_typed("Vertical", "500")]
    view = _resize_view("177", "500")
    # Contracase: the link not said kept is switched off first.
    first = cu_rules.deterministic_step(goal=HEIGHT, view=view, history=typed_height, success_check=check)
    assert first is not None and first["operation"] == "input.visible.click"
    again = cu_rules.deterministic_step(goal=HEIGHT, view=view, history=typed_height, success_check=check, objective=KEPT)
    assert again is not None and again["operation"] == "input.text.type"
    assert again["arguments"]["field"] == "Horizontal"
    # The width set again with the link on moved the height again: stopped unaccepted, the switch untouched.
    history = [*typed_height, _typed("Horizontal", "500")]
    stop = cu_rules.deterministic_step(
        goal=HEIGHT, view=_resize_view("500", "1412"), history=history, success_check=check, objective=KEPT)
    assert stop is not None and stop["operation"] == "none" and stop["code"] == cu_forms.LINKED_FIELDS


def test_a_number_holds_in_a_field_only_within_digit_bounds() -> None:
    # Revisión 1, bloqueante 4: 3000×1000 with the link on; height 500 moved the width to 1500, which «held» 500.
    assert not cu_tipos.value_holds("1500", "500")
    assert not cu_tipos.value_holds("500,5", "500")
    assert not cu_tipos.value_holds("2.500", "500")
    assert not cu_tipos.value_holds("5000", "500")
    # Contracases: the value as the window formats it, a decimal, a text.
    assert cu_tipos.value_holds("500 px", "500") and cu_tipos.value_holds("500px", "500")
    assert cu_tipos.value_holds("12,5 pt", "12,5") and cu_tipos.value_holds("hola mundo", "hola")
    # Revisión 2 (bloqueante 2): the decimal zeros a window formats the number with hold it; contracases: a decimal
    # that is not zero, a longer number.
    for shown, value in (("5,00 cm", "5"), ("500,00", "500"), ("500.0 px", "500"), ("12,50 pt", "12,5")):
        assert cu_tipos.value_holds(shown, value), (shown, value)
    for shown, value in (("500,5", "500"), ("500,05", "500"), ("1500,00", "500"), ("12,55", "12,5")):
        assert not cu_tipos.value_holds(shown, value), (shown, value)
    check = _height_check()
    step = _step(HEIGHT, check, _resize_view("1500", "500"), [_typed("Vertical", "500")])
    assert step is not None and step["operation"] == "input.visible.click"
    stop = _step(HEIGHT, check, _resize_view("1500", "500", lock="off"), [_typed("Vertical", "500"),
                                                                          _typed("Horizontal", "500")])
    assert stop is not None and stop["code"] == cu_forms.LINKED_FIELDS
    assert _step(HEIGHT, check, _resize_view("500", "500", lock="off"), [_typed("Vertical", "500")]) is None


def test_out_of_range_value_is_set_again_once_then_stops() -> None:
    check = _height_check()
    view = _resize_view("100", "500")
    view["controls"] = [control for control in view["controls"] if control["i"] != 24]
    again = _step(HEIGHT, check, view, [_typed("Vertical", "500")])
    assert again is not None and again["operation"] == "input.text.type"
    assert again["arguments"]["field"] == "Horizontal"
    stop = _step(HEIGHT, check, view, [_typed("Vertical", "500"), _typed("Horizontal", "500")])
    assert stop is not None and stop["operation"] == "none" and stop["code"] == cu_forms.LINKED_FIELDS


def test_a_form_that_holds_takes_no_step_and_a_formatted_value_still_holds() -> None:
    check = _height_check()
    assert _step(HEIGHT, check, _resize_view("500 px", "500 px", lock="off"), [_typed("Vertical", "500")]) is None
    # Before the sub-goal's own field is typed, the plain field step types it (one step, no extra).
    first = _step(HEIGHT, check, _resize_view("500", "3240", lock="off"), [])
    assert first is not None and first["operation"] == "input.text.type"
    assert first["arguments"]["field"] == "Vertical"


def test_independent_fields_go_through_with_no_extra_step() -> None:
    reads = missions._form_reads("reemplaza «casa» por «hogar»")
    goal, check, _ = reads[2]
    view = {"controls": [
        {"i": 0, "kind": "Edit", "name": "Buscar", "value": "casa"},
        {"i": 1, "kind": "Edit", "name": "Reemplazar con", "value": "hogar"},
    ]}
    assert _step(goal, check, view, [_typed("Reemplazar con", "hogar")]) is None
    assert cu_forms._form_unit_step(goal, check, view, []) is None


def test_t_form_1_with_the_lock_already_off_sets_the_height_in_one_step() -> None:
    check = _check(_steps(_case("t-form-1")), "poner alto en 600")
    view = _resize_view("800", "3240", lock="off")
    step = _step("poner alto en 600", check, view, [])
    assert step is not None and step["arguments"] == {"text": "600", "field": "Vertical", "replace": True}
    assert _step("poner alto en 600", check, _resize_view("800", "600", lock="off"), [_typed("Vertical", "600")]) is None


# ------------------------------------------------------------ final


_PARTS = [
    {"goal": "resize the canvas, donde se ponen ancho y alto", "reached": True},
    {"goal": "activar pixeles", "reached": True},
    {"goal": "poner ancho en 500", "reached": True},
    {"goal": "poner alto en 500", "reached": False},
    {"goal": "hacer clic en aceptar", "reached": False},
]


def test_a_figure_of_a_form_not_held_whole_is_unsustained() -> None:
    told = "I managed to resize the canvas to 500 by 500 pixels and activate the pixels."
    assert claims.unsustained_figure(told, _PARTS, ["Sin título - Paint"]) == "500"
    # Revisión 1, bloqueante 1: the screen alone sustains no figure; the width reached sustains one 500, once a text
    # of the last reading shows it, never two («500 by 500»).
    assert claims.unsustained_figure(told, _PARTS, ["500 x 500píxeles"]) == "500"
    assert claims.unsustained_figure(told, _PARTS, ["177 x 500px"]) == "500"
    dialog = [{"name": "Horizontal", "value": "177"}, {"name": "Vertical", "value": "500"}]
    assert claims.unsustained_figure("The canvas is now 500 pixels wide.", _PARTS, ["177", "500"], dialog) == "500"
    assert claims.unsustained_figure("Puse el ancho en 500.", _PARTS, ["500 x 500px"]) == ""
    # A form reached whole sustains it, unless the last reading shows its field holding another value.
    whole = [{**part, "reached": True} for part in _PARTS]
    assert claims.unsustained_figure(told, whole, []) == ""
    assert claims.unsustained_figure(told, whole, ["1500", "500"], [
        {"name": "Horizontal", "value": "1500"}, {"name": "Vertical", "value": "500"}]) == "500"
    # A figure no part asks for (one the screen read, a count) is no claim of the form.
    assert claims.unsustained_figure("The canvas shows 177 x 500 pixels.", _PARTS, ["177 x 500píxeles"]) == ""
    assert claims.unsustained_figure("I chose 1 of the 7 tools.", _PARTS, []) == ""
    # A quoted figure is no claim.
    assert claims.unsustained_figure("I typed «500» in Horizontal, but the window changed it.", _PARTS, []) == ""


def test_the_final_judge_vetoes_t_long_3_s_draft() -> None:
    observed = {
        "goal": "resize the canvas, donde se ponen ancho y alto; luego activar pixeles; luego poner ancho en 500; "
                "luego poner alto en 500; luego hacer clic en aceptar",
        "application": "Paint", "reached": False, "stoppedBy": "computer_use_linked_fields",
        "windowTitle": "Sin título - Paint",
        "steps": [{"step": 1, "operation": "input.text.type", "ok": True, "text": "500", "field": "Horizontal"}],
        "subgoals": [{**part, "application": "Paint"} for part in _PARTS],
    }
    situation = {
        "kind": "failure", "polarity": "failure", "cause": "mission_failed", "stepCount": 0, "steps": [],
        "reason": {"kind": "operation", "operation": "mission.computer.use", "polarity": "failure",
                   "verified": False, "succeeded": False, "error": observed["stoppedBy"], "observed": observed},
    }
    # Revisión 1, bloqueante 1: with the screen the stop really leaves (the status bar, or the dialog still open).
    screens = [
        {"lines": ["177 x 500px"]},
        {"values": [{"name": "Horizontal", "value": "177"}, {"name": "Vertical", "value": "500"}]},
    ]
    drafts = [
        "I managed to resize the canvas to 500 by 500 pixels.", "The canvas is now 500 by 500 pixels.",
        "Dejé el lienzo en 500 por 500 píxeles.",
    ]
    for screen in screens:
        for draft in drafts:
            judged = json.loads(json.dumps(situation))
            judged["reason"]["observed"]["screen"] = screen
            assert computer_use_finals._computer_use_final_defect(draft, judged) == "unsustained_figure", (screen, draft)
        # Contracase: the honest final of that stop.
        honest = json.loads(json.dumps(situation))
        honest["reason"]["observed"]["screen"] = screen
        assert computer_use_finals._computer_use_final_defect(
            "No pude dejar el lienzo en 500 por 500: la ventana cambió el ancho a 177, así que no confirmé el cambio.",
            honest) == ""


_FORM_800 = [
    {"goal": "cambiale el tamano a la imagen, donde se ponen ancho y alto", "reached": True},
    {"goal": "poner ancho en 800", "reached": True},
    {"goal": "poner alto en 600", "reached": False},
    {"goal": "hacer clic en aceptar", "reached": False},
]


def test_a_figure_denied_in_its_clause_is_no_claim() -> None:
    # Revisión 1, bloqueante 2: honest finals of an unfinished form, and of any app.
    assert claims.unsustained_figure(
        "Puse el ancho en 800, pero no pude dejar el alto en 600: la ventana lo cambió a 450, así que no confirmé el "
        "cambio.", _FORM_800, ["800", "450"]) == ""
    assert claims.unsustained_figure(
        "I set the width to 800, but I couldn't leave the height at 600: the window changed it to 450, so I didn't "
        "confirm the change.", _FORM_800, ["800", "450"]) == ""
    assert claims.unsustained_figure(
        "No pude dejar el lienzo en 500 por 500: la ventana cambió el ancho a 177…", _PARTS, []) == ""
    notepad = [
        {"goal": "abrir bloc de notas", "reached": True},
        {"goal": "escribir 2026 en el documento", "reached": False},
    ]
    assert claims.unsustained_figure("Abrí el Bloc de notas, pero no pude escribir 2026.", notepad, []) == ""
    assert claims.unsustained_figure("I opened Notepad, but I couldn’t type 2026.", notepad, []) == ""
    # Contracases: the same figures told as done.
    assert claims.unsustained_figure("Abrí el Bloc de notas y escribí 2026.", notepad, []) == "2026"
    assert claims.unsustained_figure(
        "Puse el ancho en 800 y el alto en 600.", _FORM_800, ["800", "450"]) == "600"
    # A decimal separator splits no clause: «no pude dejarlo en 12,5» denies 12,5 whole.
    font = [{"goal": "poner tamano en 12,5", "reached": False}]
    assert claims.unsustained_figure("No pude dejar el tamaño en 12,5.", font, []) == ""
    assert claims.unsustained_figure("Dejé el tamaño en 12,5.", font, []) == "12,5"


# ------------------------------------------------------------ revisión 2


WIDTH = "poner ancho en 500"
ACCEPT = "hacer clic en aceptar"


def _form_checks(text: str) -> dict[str, str | None]:
    mission = missions.mission_request(text, APPS)
    assert mission is not None and mission.steps
    return {step.goal: step.form_check for step in mission.steps}


def test_the_plan_gives_the_fields_and_the_button_of_a_tied_form_its_whole_check() -> None:
    # Bloqueante 1: the form id is the whole form's check, carried by each field and by the button that accepts it.
    forms = _form_checks(_case("t-long-3"))
    unit = _height_check()
    assert forms[WIDTH] == forms[HEIGHT] == forms[ACCEPT] == unit
    assert forms["activar pixeles"] is None and forms["resize the canvas, donde se ponen ancho y alto"] is None
    assert forms["hacer clic en guardar"] is None
    # Contracase: independent fields (a replace bar) carry none.
    replace = _form_checks("en el bloc de notas reemplaza «casa» por «hogar»")
    assert not any(replace.values())


def test_the_form_check_is_an_argument_the_catalog_declares() -> None:
    import re

    catalog = (ROOT / "src" / "Baxy.Kernel" / "Operations" / "ProductCatalog.cs").read_text(encoding="utf-8")
    start = catalog.index('"steps",', catalog.index('"mission.computer.use"'))
    items = catalog[catalog.index("itemSchema: Schema(", start): catalog.index('["goal"])', start)]
    declared = dict(re.findall(r'String\("(\w+)",[^)]*?maximumUtf8Bytes: (\d+)', items))
    assert "formCheck" in declared
    mission = missions.mission_request(_case("t-long-3"), APPS)
    assert mission is not None
    for step in mission.arguments()["steps"]:
        assert set(step) <= set(declared), step
        if "formCheck" in step:
            assert len(step["formCheck"].encode("utf-8")) <= int(declared["formCheck"])
    # Contracase: a sub-goal of no form sends no formCheck at all.
    assert "formCheck" not in next(step for step in mission.arguments()["steps"] if step["goal"] == "activar pixeles")


def test_the_lock_is_switched_off_before_the_first_field_when_the_request_fixes_both() -> None:
    # Bloqueante 1 (proactive): the request fixes both fields the lock ties and the view shows it on.
    unit = _height_check()
    step = cu_rules.deterministic_step(
        goal=WIDTH, view=_resize_view("100", "100"), history=[], success_check=_check(_steps(_case("t-long-3")), WIDTH),
        form_check=unit)
    assert step is not None and step["operation"] == "input.visible.click"
    assert step["arguments"] == {"label": "Mantener la relación de aspecto", "index": 24}
    # Once pressed (or shown off) the field is typed.
    clicked = [{"operation": "input.visible.click", "ok": True, "label": "Mantener la relación de aspecto"}]
    typed = cu_rules.deterministic_step(goal=WIDTH, view=_resize_view("100", "100", lock="off"), history=clicked,
                                  success_check=_check(_steps(_case("t-long-3")), WIDTH), form_check=unit)
    assert typed is not None and typed["operation"] == "input.text.type" and typed["arguments"]["field"] == "Horizontal"
    # Contracases: a request that keeps the link, and a sub-goal of no form, type at once with the lock on.
    kept = cu_rules.deterministic_step(goal=WIDTH, view=_resize_view("100", "100"), history=[], form_check=unit,
                                 success_check=_check(_steps(_case("t-long-3")), WIDTH), objective=KEPT)
    assert kept is not None and kept["operation"] == "input.text.type"
    alone = cu_rules.deterministic_step(goal=WIDTH, view=_resize_view("100", "100"), history=[])
    assert alone is not None and alone["operation"] == "input.text.type"


def test_a_field_recalculated_on_focus_loss_never_reaches_the_accept_with_the_lock_on() -> None:
    # The reviewer's scenario (scratchpad probe2): a field that recalculates the other only when it loses the focus
    # (a WinUI NumberBox, a WinForms NumericUpDown) shows 500/500 until the form is accepted. The sub-goal that sets the
    # height sees nothing changed; what prevents the recalculation is the lock switched off before the first field.
    unit = _height_check()
    assert _step(HEIGHT, unit, _resize_view("500", "500"), [_typed("Vertical", "500")]) is None
    first = cu_rules.deterministic_step(goal=WIDTH, view=_resize_view("100", "100"), history=[], form_check=unit,
                                  success_check=_check(_steps(_case("t-long-3")), WIDTH))
    assert first is not None and first["arguments"]["label"] == "Mantener la relación de aspecto"


def test_the_form_is_evaluated_whole_again_before_its_button_accepts_it() -> None:
    unit = _height_check()
    accept = _check(_steps(_case("t-long-3")), ACCEPT)
    # The view the model saw in v2-t-long-3: Vertical 500 typed, Horizontal recalculated to 888 with the lock on.
    seen = _resize_view("888", "500")
    first = cu_rules.deterministic_step(goal=ACCEPT, view=seen, history=[], success_check=accept, form_check=unit)
    assert first is not None and first["operation"] == "input.visible.click"
    assert first["arguments"]["label"] == "Mantener la relación de aspecto"
    clicked = [{"operation": "input.visible.click", "ok": True, "label": "Mantener la relación de aspecto"}]
    again = cu_rules.deterministic_step(goal=ACCEPT, view=_resize_view("888", "500", lock="off"), history=clicked,
                                  success_check=accept, form_check=unit)
    assert again is not None and again["operation"] == "input.text.type"
    assert again["arguments"] == {"text": "500", "field": "Horizontal", "replace": True}
    # Changed again after it was set: never accepted, the mission stops with its cause.
    stop = cu_rules.deterministic_step(goal=ACCEPT, view=_resize_view("500", "281", lock="off"),
                                 history=[*clicked, _typed("Horizontal", "500")], success_check=accept, form_check=unit)
    assert stop is not None and stop["operation"] == "none" and stop["code"] == cu_forms.LINKED_FIELDS
    # Contracases: the whole form holding, the button is pressed; with no form check, the button as before.
    held = cu_rules.deterministic_step(goal=ACCEPT, view=_resize_view("500", "500", lock="off"), history=[],
                                 success_check=accept, form_check=unit)
    assert held is not None and held["operation"] == "input.visible.click" and held["arguments"]["label"] == "Aceptar"
    plain = cu_rules.deterministic_step(goal=ACCEPT, view=seen, history=[], success_check=accept)
    assert plain is not None and plain["operation"] == "input.visible.click" and plain["arguments"]["label"] == "Aceptar"


def test_a_form_reached_whole_sustains_no_more_figures_than_the_pair_the_screen_shows() -> None:
    # Bloqueante 1 (final): every part reached, the status bar «177 x 500px» after the form was accepted.
    whole = [{**part, "reached": True} for part in _PARTS]
    told = "I resized the canvas to 500 by 500 pixels."
    assert claims.unsustained_figure(told, whole, ["177 x 500px"]) == "500"
    assert claims.unsustained_figure("Dejé el lienzo en 500 por 500 píxeles.", whole, ["177 x 500píxeles"]) == "500"
    # Contracases: the pair as asked, a pair of none of its figures, no pair on screen.
    assert claims.unsustained_figure(told, whole, ["500 x 500px"]) == ""
    assert claims.unsustained_figure(told, whole, ["1920 x 1080"]) == ""
    assert claims.unsustained_figure(told, whole, ["Sin título - Paint"]) == ""
    assert claims.unsustained_figure("The canvas is 500 pixels high.", whole, ["177 x 500px"]) == ""


def test_decimal_zeros_of_a_formatted_field_hold_its_value() -> None:
    # Bloqueante 2 (scratchpad probe2): a position and size dialog shows «5,00 cm».
    reads = missions._form_reads("cambia el tamano a 5 de ancho y 3 de alto")
    assert reads is not None
    goal, check, _ = next(read for read in reads if read[0] == "poner alto en 3")
    view = {"controls": [
        {"i": 1, "kind": "Edit", "name": "Ancho", "value": "5,00 cm"},
        {"i": 2, "kind": "Edit", "name": "Alto", "value": "3,00 cm"},
        {"i": 3, "kind": "Button", "name": "Aceptar"},
    ]}
    assert cu_rules.deterministic_step(goal=goal, view=view, history=[_typed("Alto", "3")], success_check=check) is None
    assert cu_forms._form_confirm_step(check, view, []) is None
    parts = [{"goal": "poner ancho en 5", "reached": True}, {"goal": "poner alto en 3", "reached": True}]
    fields = [{"name": "Ancho", "value": "5,00 cm"}, {"name": "Alto", "value": "3,00 cm"}]
    assert claims.unsustained_figure("Puse el ancho en 5 y el alto en 3.", parts, [], fields) == ""
    # Contracase: a field showing another decimal does not hold it.
    other = [{"name": "Ancho", "value": "5,50 cm"}, {"name": "Alto", "value": "3,00 cm"}]
    assert claims.unsustained_figure("Puse el ancho en 5 y el alto en 3.", parts, [], other) == "5"


def test_a_denial_of_another_act_joined_by_a_conjunction_denies_no_figure() -> None:
    # Bloqueante 3 (scratchpad probe3): one per language.
    assert claims.unsustained_figure(
        "No dibujé el rectángulo y dejé el lienzo en 500 por 500.", _PARTS, ["177 x 500px"]) == "500"
    assert claims.unsustained_figure(
        "I didn't draw the rectangle and I left the canvas at 500 by 500.", _PARTS, ["177 x 500px"]) == "500"
    assert claims.unsustained_figure(
        "I didn't draw the rectangle and I resized the canvas to 500 by 500.", _PARTS, ["177 x 500px"]) == "500"
    assert claims.unsustained_figure(
        "No dibujé el rectángulo y el lienzo quedó en 500 por 500.", _PARTS, ["177 x 500px"]) == "500"
    # Contracases: the denial between the act and the figure, or carried by an elliptical conjunct.
    for honest in (
        "No pude poner el ancho en 500 y el alto en 500.", "I couldn't set the width to 500 and the height to 500.",
        "Abrí Paint y no pude dejar el lienzo en 500 por 500.", "I opened Paint and couldn't leave the canvas at 500 by 500.",
        "No puse el ancho en 500 ni el alto en 500.",
    ):
        assert claims.unsustained_figure(honest, _PARTS, ["177 x 500px"]) == "", honest


# ------------------------------------------------------------ revisión 3


def _judged(parts: list[dict], screen: dict, reached: bool, steps: list[dict] | None = None, stop: str = "") -> dict:
    """A situation of the final judge: a verified mission (reached) or one that failed (the reviewer's probes)."""

    observed = {
        "goal": "; luego ".join(part["goal"] for part in parts), "application": "Paint", "reached": reached,
        "windowTitle": "Sin título - Paint", "steps": steps or [], "subgoals": parts, "screen": screen,
    }
    if reached:
        return {"operation": "mission.computer.use", "polarity": "success", "verified": True, "succeeded": True,
                "observed": observed}
    observed["stoppedBy"] = stop
    return {
        "kind": "failure", "polarity": "failure", "cause": "mission_failed", "stepCount": 0, "steps": [],
        "reason": {"kind": "operation", "operation": "mission.computer.use", "polarity": "failure",
                   "verified": False, "succeeded": False, "error": stop, "observed": observed},
    }


def test_a_figure_told_again_in_another_statement_is_no_further_claim() -> None:
    # Bloqueante 1: verified successes that repeat the figures asked.
    size = [{"goal": "poner ancho en 800", "reached": True}, {"goal": "poner alto en 600", "reached": True},
            {"goal": "hacer clic en aceptar", "reached": True}]
    judged = _judged(size, {"lines": ["800 x 600px"]}, True)
    for told in (
        "Puse el ancho en 800 y el alto en 600; ahora la imagen mide 800 x 600 píxeles.",
        "I set the width to 800 and the height to 600; the image is now 800 x 600 pixels.",
        "I set the width to 800 and the height to 600, so the image is now 800 x 600 pixels.",
    ):
        assert computer_use_finals._computer_use_final_defect(told, judged) == "", told
    table = [{"goal": "poner columnas en 3", "reached": True}, {"goal": "poner filas en 4", "reached": True},
             {"goal": "hacer clic en aceptar", "reached": True}]
    assert computer_use_finals._computer_use_final_defect(
        "Inserté la tabla de 3 por 4: 3 columnas y 4 filas.", _judged(table, {"lines": []}, True)) == ""
    # Contracases: told twice in one statement, the figure sustained once is still unsustained.
    assert claims.unsustained_figure("I managed to resize the canvas to 500 by 500 pixels.", _PARTS, ["177 x 500px"]) \
        == "500"
    assert claims.unsustained_figure("Puse el ancho en 500 y el alto en 500.", _PARTS, ["177 x 500px"]) == "500"
    assert claims.unsustained_figure(
        "Puse el ancho en 500; el lienzo quedó en 500 por 500.", _PARTS, ["177 x 500px"]) == "500"


_NOTEPAD = [{"goal": "abrir bloc de notas", "reached": True}, {"goal": "escribir 2026 en el documento", "reached": False}]


def test_honest_finals_of_failed_missions_assert_no_figure() -> None:
    # Bloqueante 2: attempts, «unable», «imposible», «en vez de», a request, a denial after the figure.
    typed = _judged(_NOTEPAD, {"lines": []}, False,
                    [{"step": 1, "operation": "input.text.type", "ok": False, "text": "2026"}], "computer_use_no_progress")
    for honest in (
        "Intenté escribir 2026, pero el Bloc de notas no lo mostró.", "I tried to type 2026, but Notepad didn't show it.",
        "Abrí el Bloc de notas, pero 2026 no aparece en el documento.",
    ):
        assert computer_use_finals._computer_use_final_defect(honest, typed) == "", honest
    for honest in ("I opened Notepad, but I was unable to type 2026.",
                   "Abrí el Bloc de notas, pero me fue imposible escribir 2026."):
        assert claims.unsustained_figure(honest, _NOTEPAD, []) == "", honest
    linked = _judged(_FORM_800, {"values": [{"name": "Ancho", "value": "800"}, {"name": "Alto", "value": "450"}]}, False,
                     [{"step": 1, "operation": "input.text.type", "ok": True, "text": "800", "field": "Ancho"}],
                     cu_forms.LINKED_FIELDS)
    for honest in (
        "Puse el ancho en 800, pero el alto quedó en 450 en vez de 600.",
        "I set the width to 800, but the height ended up at 450 instead of 600.",
        "Pediste 600 de alto, pero la ventana lo dejó en 450, así que no confirmé el cambio.",
    ):
        assert computer_use_finals._computer_use_final_defect(honest, linked) == "", honest
    assert claims.unsustained_figure(
        "I set the width to 800, but I was unable to set the height to 600.", _FORM_800, ["800", "450"]) == ""
    stop = _judged(_PARTS, {"lines": ["177 x 500px"]}, False,
                   [{"step": 1, "operation": "input.text.type", "ok": True, "text": "500", "field": "Horizontal"}],
                   cu_forms.LINKED_FIELDS)
    for honest in (
        "Intenté dejar el lienzo en 500 por 500, pero la ventana volvió a cambiar el ancho, así que no lo confirmé.",
        "I tried to set the canvas to 500 by 500, but the window kept changing the width, so I didn't confirm it.",
    ):
        assert computer_use_finals._computer_use_final_defect(honest, stop) == "", honest
    # Contracases: an act told after the attempt or the request, and a figure told done with «sin» after it.
    assert claims.unsustained_figure("Intenté varias veces y al final dejé el lienzo en 500 por 500.", _PARTS,
                                     ["177 x 500px"]) == "500"
    assert claims.unsustained_figure("I tried twice and then I set the canvas to 500 by 500.", _PARTS,
                                     ["177 x 500px"]) == "500"
    assert claims.unsustained_figure("Pediste 500 por 500 y dejé el lienzo en 500 por 500.", _PARTS,
                                     ["177 x 500px"]) == "500"
    assert claims.unsustained_figure("El lienzo quedó en 500 por 500 sin problemas.", _PARTS, ["177 x 500px"]) == "500"
    assert claims.unsustained_figure("Escribí 2026 sin problemas.", _NOTEPAD, []) == "2026"
    assert computer_use_finals._computer_use_final_defect("Abrí el Bloc de notas y escribí 2026.", typed) != ""


def test_a_conjunct_with_a_function_verb_is_no_ellipsis() -> None:
    # Bloqueante 3: «está», «is» are the verb of another statement, whatever verb the model chooses.
    for told in (
        "No tuve que apagar nada y el lienzo está en 500 por 500.",
        "I didn't draw the rectangle and the canvas is 500 by 500.",
        "No dibujé el rectángulo y el lienzo es de 500 por 500.",
        "I didn't draw the rectangle and the canvas was 500 by 500.",
        "No dibujé el rectángulo y el lienzo quedó en 500 por 500.",
    ):
        assert claims.unsustained_figure(told, _PARTS, ["177 x 500px"]) == "500", told
    # Contracases: elliptical conjuncts keep the denial.
    for honest in (
        "No pude poner el ancho en 500 y el alto en 500.", "I couldn't set the width to 500 and the height to 500.",
        "No puse el ancho en 500 ni el alto en 500.", "No pude dejar el ancho en 500 y tampoco el alto en 500.",
    ):
        assert claims.unsustained_figure(honest, _PARTS, ["177 x 500px"]) == "", honest
