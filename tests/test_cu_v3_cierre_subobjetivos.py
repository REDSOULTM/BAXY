"""Pasada r15b, cierre de sub-objetivos (t-form-1, t-long-3, t-form-3, t-long-2, t-drag-4): twins on the literal
requests and on the views the model was shown (model_calls of each case).

- The sub-goal that opens a form says where the values go and is closed by the form brought up by an act of its own
  (``appeared:``), never a free sub-goal with the head of the whole order as its goal.
- A text into a field that holds nothing (the body of a new document) is typed in, never «replaced».
- A second click on the tool a drawing goal names proves no drawing.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from baxy_mind import cu_evidence
from baxy_mind import cu_diagnosis
from baxy_mind import cu_validate
from baxy_mind import known_folders
from baxy_mind.semantic import missions

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "scripts" / "cu_live" / "cases"
APPS = ("Paint", "Word", "Bloc de notas", "Notepad")


@pytest.fixture(autouse=True)
def _documents(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(known_folders, "known_folder", lambda folder: {"documents": r"D:\Perfil\Documentos"}.get(folder))


def _case(name: str) -> str:
    return (CASES / f"{name}.turns").read_text(encoding="utf-8").strip()


# Estabilización L: t-long-3 as said draws a rectangle, the drag limit (never a mission); its canvas opener is read on
# the same order without the drawing clause.
T_LONG_3_WITHOUT_THE_DRAWING = (
    r"Open Paint, resize the canvas to 500 by 500 pixels, save it as baxy-cuadro.png in Documents\baxy-prueba-v3 and "
    "then close Paint"
)


def _text(case: str) -> str:
    return T_LONG_3_WITHOUT_THE_DRAWING if case == "t-long-3" else _case(case)


def _steps(text: str) -> list[tuple[str, str | None, bool]]:
    mission = missions.mission_request(text, APPS)
    assert mission is not None and mission.steps, text
    return [(step.goal, step.success_check, step.free) for step in mission.steps]


# ------------------------------------------------------------ a) el abridor de un formulario


def test_the_resize_opener_says_where_the_values_go_and_is_checked_by_what_appeared() -> None:
    steps = _steps(_case("t-form-1"))
    goal, check, free = steps[0]
    assert goal == "cambiale el tamano a la imagen, donde se ponen ancho y alto"
    assert free is False
    terms = check.split("|")
    # The unit's option first (the dialog opens in percent), then both fields side by side in each language.
    assert terms[:2] == ["appeared:pixeles", "appeared:pixels"]
    assert "appeared:horizontal&appeared:vertical" in terms
    assert all(term.startswith("appeared:") for term in terms)
    # The sub-goals after it are the form's own, as before.
    assert [goal for goal, _, _ in steps[1:]] == [
        "activar pixeles", "desactivar mantener la relacion de aspecto", "poner ancho en 800", "poner alto en 600",
        "hacer clic en aceptar"]


def test_the_canvas_opener_in_english_is_checked_the_same_way() -> None:
    from baxy_mind.semantic.drag import asks_to_drag

    assert asks_to_drag(_case("t-long-3")) and missions.mission_request(_case("t-long-3"), APPS) is None
    steps = _steps(_text("t-long-3"))
    goals = [goal for goal, _, _ in steps]
    opener = goals.index("resize the canvas, donde se ponen ancho y alto")
    assert steps[opener][1].startswith("appeared:pixeles|appeared:pixels|")
    assert steps[opener][2] is False
    assert goals[opener + 1] == "activar pixeles"


def test_the_table_opener_names_columns_and_rows_never_the_order_whole() -> None:
    steps = _steps(_case("t-form-3"))
    goal, check, free = steps[0]
    assert goal == "insert a table, donde se ponen columnas y filas"
    assert free is False
    # No unit: the two fields side by side, so a «Columnas» button alone (another tab) never closes it.
    assert check.split("|")[:2] == ["appeared:columnas&appeared:filas", "appeared:columns&appeared:rows"]
    assert [goal for goal, _, _ in steps[1:]] == ["poner columnas en 4", "poner filas en 3", "hacer clic en aceptar"]


def test_a_dialog_said_keeps_its_name_and_says_the_values() -> None:
    reads = missions._compound_reads(missions.fold(_case("t-form-4")))
    assert reads is not None
    goal, check, free = reads[0]
    assert goal == "abrir el dialogo de fuente, donde se ponen fuente, tamano y cursiva"
    assert check.startswith("appeared:fuente&appeared:tamano|") and free is False


def test_replacing_keeps_its_own_opener_and_check() -> None:
    reads = missions._compound_reads(missions.fold("reemplazá «casa» por «hogar»"))
    assert reads is not None
    assert reads[0] == ("abrir el dialogo de reemplazar", "control:reemplazar con|control:replace with", False)


# Review of cierre-de-subobjetivos (findings 4-6).


@pytest.mark.parametrize("case", ["t-form-1", "t-long-3", "t-form-3"])
def test_opening_the_application_is_no_act_of_a_form_opener(case: str) -> None:
    # A bare «abrir …» opener made the application opened its act: a done cited on the blank view passed.
    opener = next(goal for goal, check, _ in _steps(_text(case)) if (check or "").startswith("appeared:"))
    assert not cu_evidence.acted_with_effect([{"step": 1, "operation": "app.open", "ok": True}], opener)


def test_the_opener_keeps_what_to_open() -> None:
    goal, _, _ = _steps("en word inserta una tabla de 4 columnas y 3 filas")[0]
    assert goal == "inserta una tabla, donde se ponen columnas y filas"


def test_one_field_and_a_style_are_checked_side_by_side() -> None:
    # «Tamaño» alone is also a button of another tab: the field is checked beside the style, in each language.
    steps = _steps("en word abrí el cuadro de diálogo de fuente y poné arial, tamaño 20 y cursiva")
    check = next(check for _, check, _ in steps if (check or "").startswith("appeared:"))
    terms = check.split("|")
    assert terms[:2] == ["appeared:tamano&appeared:cursiva", "appeared:size&appeared:italic"]
    assert all("&" in term for term in terms)


# ------------------------------------------------------------ vistas de los casos (model_calls)

_LINE = re.compile(r"^(?P<i>\d+) · (?P<kind>\w+) · «(?P<name>[^«»]*)»(?P<rest>.*)$")
_ZONES = {"TL", "T", "TR", "L", "C", "R", "BL", "B", "BR"}


def _view(title: str, lines: str, focused: dict | None = None, **extra: object) -> dict:
    controls = []
    for line in lines.strip().splitlines():
        match = _LINE.match(line.strip())
        assert match is not None, line
        control: dict[str, object] = {"i": int(match["i"]), "kind": match["kind"], "name": match["name"]}
        for bit in (part.strip() for part in match["rest"].split(" · ") if part.strip()):
            if bit.startswith("valor=«"):
                control["value"] = bit[len("valor=«"):-1]
            elif bit in _ZONES:
                control["zone"] = bit
            elif not bit.startswith("x"):
                control["state"] = bit
        controls.append(control)
    # The model's «i» is the control's place in the view's list (the prompt lists 30 of them, by rank): the lines it
    # did not show stand as unnamed text.
    listed = {control["i"]: control for control in controls}
    controls = [listed.get(index, {"i": index, "kind": "Text", "name": ""}) for index in range(max(listed) + 1)]
    window: dict[str, object] = {"title": title, "process": "APP"}
    if focused is not None:
        window["focused"] = focused
    return {"window": window, "controls": controls, **extra}


def _validate(raw: dict, view: dict, history: list[dict], goal: str, *, objective: str | None = None) -> dict:
    return cu_validate.validate_decision(
        raw, view=view, last_failed=None, application_names=(), history=history, goal=goal, objective=objective)


def _click(step: int, label: str) -> dict:
    return {"step": step, "operation": "input.visible.click", "ok": True, "label": label, "changed": True}


# ------------------------------------------------------------ d) un campo vacío no se «reemplaza»

# t-long-2, model_calls #65: the new document's page, empty, beside the focused document.
_WORD_PAGE = """
0 · Document · «Documento1» · focused · R
1 · Edit · «Contenido de la página 1» · R
7 · Edit · «Buscar en documento» · valor=«Buscar en documento» · TL
15 · Button · «Guardar» · TL
23 · TabItem · «Inicio» · selected · TL
"""
_FAILED_TYPING = {
    "step": 3, "operation": "input.text.type", "ok": False, "text": "Informe semanal",
    "field": "Contenido de la página 1", "error": "input_field_not_replaceable",
}


def test_text_into_the_empty_page_of_a_new_document_goes_in_without_replace() -> None:
    view = _view("Documento1 - Word", _WORD_PAGE, focused={"kind": "Document", "name": "Documento1"})
    decision = _validate(
        {"act": "type", "text": "Informe semanal", "field": "Contenido de la página 1"}, view,
        [{"step": 1, "operation": "app.open", "ok": True}, _click(2, "Documento en blanco")],
        "escribir Informe semanal", objective=_case("t-long-2"))
    assert decision["operation"] == "input.text.type"
    assert decision["arguments"]["field"] == "Contenido de la página 1"
    assert "replace" not in decision["arguments"]


def test_a_field_that_holds_a_value_is_still_replaced() -> None:
    view = _view("Sin título - Paint", """
1 · RadioButton · «Píxeles» · selected focused · C
2 · Edit · «Horizontal» · valor=«1152» · C
4 · Edit · «Vertical» · valor=«648» · C
""")
    decision = _validate({"act": "type", "text": "800", "field": "Horizontal"}, view, [_click(1, "Píxeles")],
                         "poner ancho en 800", objective=_case("t-form-1"))
    assert decision["operation"] == "input.text.type"
    assert decision["arguments"]["replace"] is True


def test_the_retry_after_a_refused_field_says_why_and_the_way_out() -> None:
    view = _view("Documento1 - Word", _WORD_PAGE, focused={"kind": "Document", "name": "Documento1"})
    said = cu_diagnosis.failed_click_diagnosis(_FAILED_TYPING, view)
    assert said.startswith("ese campo no se reemplaza")
    assert "«Documento1»" in said and "type sin field" in said
    # Counter-cases: a text with no field named has no field diagnosis, and a click's diagnosis is unchanged.
    assert cu_diagnosis.failed_click_diagnosis({**_FAILED_TYPING, "field": ""}, view) == ""
    assert cu_diagnosis.failed_click_diagnosis(
        {"operation": "input.visible.click", "ok": False, "label": "Guardar", "index": 15}, view
    ) == "no hizo nada: otro control u otro camino, nunca el mismo clic"


# ------------------------------------------------------------ e) elegir la herramienta no dibuja

# t-drag-4, model_calls #22-#23: «Línea» chosen by the first click; the model clicked it again.
_PAINT_LINE = """
3 · Button · «Guardar» · TL
13 · Button · «Lápiz» · off · TL
20 · ListItem · «Línea» · T
21 · Button · «Línea» · on focused · T
27 · Button · «Rectángulo» · off · T
"""


def test_a_drawing_goal_never_reaches_the_loop_it_is_the_drag_limit() -> None:
    # Estabilización L: the drawing of t-drag-4 is a declared limit; the mission stops before it, so the second click on
    # its tool is never judged as a drawing done.
    from baxy_mind.semantic.drag import asks_to_drag

    assert asks_to_drag(_case("t-drag-4"))


def test_choosing_the_tool_said_is_still_done_by_the_click_again() -> None:
    goal = "elegí la herramienta Línea"
    view = _view("Sin título - Paint", _PAINT_LINE, chosenBeforeClick={"1": ["pinceles"]})
    decision = _validate({"act": "click", "i": 21, "label": "Línea"}, view, [_click(1, "Línea")], goal, objective=goal)
    assert decision["operation"] == "done" and decision["arguments"]["evidence"] == "Línea"
    # Already chosen before the click: told as it already was.
    before = _view("Sin título - Paint", _PAINT_LINE, chosenBeforeClick={"1": ["linea"]})
    already = _validate({"act": "click", "i": 21, "label": "Línea"}, before, [_click(1, "Línea")], goal, objective=goal)
    assert already["operation"] == "done" and already["arguments"].get("already") is True


@pytest.mark.parametrize(("goal", "kind", "name", "state"), [
    ("la Línea", "Button", "Línea", "on"),
    ("activar pixeles", "RadioButton", "Píxeles", "selected"),
    # Review of cierre-de-subobjetivos (finding 1): goals of setting an option whatever their verb; a second click
    # would put «Centrar» back to the left or switch the toggle off again.
    ("centrar el texto", "Button", "Centrar", "on"),
    ("encender el modo oscuro", "Button", "Modo oscuro", "on"),
    ("habilitar la regla", "CheckBox", "Regla", "on"),
    ("ordenar por fecha", "RadioButton", "Fecha", "selected"),
    ("poner el texto en negrita", "Button", "Negrita", "on"),
])
def test_a_goal_that_names_the_option_is_done_by_the_click_again(goal: str, kind: str, name: str, state: str) -> None:
    view = _view("Documento - APP", f"""
3 · Button · «Guardar» · TL
21 · {kind} · «{name}» · {state} focused · T
""", chosenBeforeClick={"1": ["otra"]})
    decision = _validate({"act": "click", "i": 21, "label": name}, view, [_click(1, name)], goal, objective=goal)
    assert decision["operation"] == "done" and decision["arguments"]["evidence"] == name


@pytest.mark.parametrize("goal", ["en Paint draw una línea recta", "dibujá con el Pincel"])
def test_a_drawing_goal_is_the_drag_limit_never_a_click_again_on_its_tool(goal: str) -> None:
    from baxy_mind.semantic.drag import asks_to_drag

    assert asks_to_drag(goal)


# ------------------------------------------------------------ f) el estado leído gana a la cuenta de pulsaciones

# Ronda 28. Tanda c27u2 (redpc, 2026-10-10) t4-c04 t3, model call 91: the theme «Windows (oscuro), 1 imágenes» pressed
# twice (both ok) and shown selected; the third click was refused («por tercera vez»), the model said none and the final
# was «no vi en la pantalla un control con el que seguir» over the state it had just read.
_THEMES = """
4 · Edit · «Cuadro de búsqueda, Buscar una opción» · T
11 · ListItem · «Personalización» · selected · L
19 · Button · «Personalización» · TL
20 · ListItem · «Windows (oscuro), 1 imágenes» · {state}T
21 · ListItem · «Movimiento capturado, 4 imágenes» · T
22 · ListItem · «Windows (claro), 1 imágenes» · TR
26 · ListItem · «Fondo» · C
44 · List · «Seleccionar un tema para aplicarlo» · C
"""
_DARK_GOAL = "vale y ahora en configuracion pon el modo oscuro"
_DARK = "Windows (oscuro), 1 imágenes"
_DARK_FOLDED = "windows (oscuro), 1 imagenes"


def _theme_view(*, selected: bool = True, chosen_before: tuple[int, ...] = (4,)) -> dict:
    lines = _THEMES.replace("{state}", "selected focused · " if selected else "")
    before = {str(step): ["personalizacion", *([_DARK_FOLDED] if step in chosen_before else [])] for step in (3, 4)}
    return _view("Configuración", lines, chosenBeforeClick=before)


def _theme_history(clicks: int = 2) -> list[dict]:
    return [
        {"step": 1, "operation": "app.open", "ok": True, "appId": "Configuración"},
        _click(2, "Personalización"), *(_click(3 + n, _DARK) for n in range(clicks)),
    ]


# Revisión 1 de r28 (bloqueante 1): a third click on an option the sub-goal's own click chose is never made a done by
# the mind, whatever the goal: the state read closes the sub-goal only through the plan's check, in the App.
@pytest.mark.parametrize("goal", [
    _DARK_GOAL, "pon el modo claro", "pon el tema windows claro", "sube el brillo", "quita el modo oscuro", "ir a fondo",
])
def test_a_third_click_on_a_chosen_option_the_goal_does_not_name_is_never_a_done(goal: str) -> None:
    for view in (_theme_view(), _theme_view(selected=False), _theme_view(chosen_before=(3, 4))):
        decision = _validate({"act": "click", "i": 20}, view, _theme_history(), goal, objective=goal)
        assert decision["operation"] == "none", (goal, decision)


_SETTINGS_APPS = ("Configuración", "Paint", "Word")


def test_a_mission_said_after_a_spoken_link_keeps_its_goal_and_its_check() -> None:
    # Why t4-c04 t3 closed nothing: «vale y ahora» left the mission unread, so its plan was the whole phrase with no
    # check. Read without the link, the plan is the same as the order said alone, with the check the theme satisfies.
    from baxy_mind.semantic import arguments

    alone = arguments._explicit_arguments_from_evidence(
        "mission.computer.use", "en configuracion pon el modo oscuro", _SETTINGS_APPS)
    assert alone is not None and alone["goal"] == "activar modo oscuro"
    assert "control:oscuro:selected" in str(alone["successCheck"]).split("|")
    for said in (_DARK_GOAL, "y ahora en configuracion pon el modo oscuro", "ok, ahora en configuracion pon el modo oscuro"):
        assert arguments._explicit_arguments_from_evidence("mission.computer.use", said, _SETTINGS_APPS) == alone, said
    # Counter-cases: the reader itself still reads nothing of the linked phrase (no route changes), an order with no
    # link is left as said, and a word that only starts like one is no link.
    assert missions.mission_request(_DARK_GOAL, _SETTINGS_APPS) is None
    assert missions.without_spoken_link("en configuracion pon el modo oscuro") == "en configuracion pon el modo oscuro"
    assert missions.without_spoken_link("Valentina en word") == "Valentina en word"
    assert arguments._explicit_arguments_from_evidence("mission.computer.use", "vale y ahora contame un chiste", _SETTINGS_APPS) is None
