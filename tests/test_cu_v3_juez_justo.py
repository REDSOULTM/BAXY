"""Pasada v3 r9, falsos fracasos (v3-02, v3-09, v3-10, v3-13): the state asked showed on the final view and the model
said done, but its citation was refused and the final said «No pude». Twins built from the views the model was shown
(model_calls.jsonl of cu-universal-evidencia/v2-<caso>), each line as ``compact_view_text`` writes it."""

from __future__ import annotations

import re

from baxy_mind import cu_first_look
from baxy_mind import cu_validate
from baxy_mind import cu_projection
from baxy_mind import cu_reply_checks
from baxy_mind import cu_finals
from baxy_mind import operation_floor

_LINE = re.compile(r"^(?P<i>\d+) · (?P<kind>\w+) · «(?P<name>[^«»]*)»(?P<rest>.*)$")
_ZONES = {"TL", "T", "TR", "L", "C", "R", "BL", "B", "BR"}


def _view(title: str, lines: str, **extra: object) -> dict:
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
    return {"window": {"title": title, "process": "APP"}, "controls": controls, **extra}


def _first_look(view: dict) -> str:
    return "\n".join(cu_first_look.look_parts(view))


def _validate(raw: dict, view: dict, history: list[dict], goal: str) -> dict:
    return cu_validate.validate_decision(raw, view=view, last_failed=None, application_names=(), history=history, goal=goal)


_PPT_BEFORE = """
13 · TabItem · «Inicio» · selected · TL
14 · TabItem · «Insertar» · TL
16 · TabItem · «Diseño» · TL
17 · TabItem · «Transiciones» · TL
18 · TabItem · «Animaciones» · T
"""
# v3-02 turn 1, the view after the click on «Transiciones» (req 8).
_PPT_TAB = """
13 · TabItem · «Inicio» · TL
14 · TabItem · «Insertar» · TL
16 · TabItem · «Diseño» · TL
17 · TabItem · «Transiciones» · selected focused · TL
18 · TabItem · «Animaciones» · T
27 · MenuItem · «Animation Transition Gallery» · collapsed · TL
28 · ListItem · «Ninguna» · selected · TL
29 · ListItem · «Transformación» · TL
30 · ListItem · «Desvanecer» · TL
31 · ListItem · «Empuje» · TL
"""
_PPT_GOAL = "en el powerpoint que tengo abierto andá a la pestaña Transiciones"


def _click(step: int, label: str) -> dict:
    return {"step": step, "operation": "input.visible.click", "ok": True, "label": label, "changed": True}


def test_v3_02_tab_cited_by_its_line_is_the_tab_the_click_chose() -> None:
    first = _first_look(_view("Presentación1 - PowerPoint", _PPT_BEFORE))
    view = _view("Presentación1 - PowerPoint", _PPT_TAB, firstLook=first, chosenBeforeClick={"1": ["inicio"]})
    decision = _validate(
        {"act": "done", "evidence": "TabItem «Transiciones» · selected focused"}, view, [_click(1, "Transiciones")], _PPT_GOAL)
    assert decision["operation"] == "done"
    assert decision["arguments"] == {"evidence": "Transiciones"}


def test_v3_02_contracase_tab_chosen_before_the_click_was_already_there() -> None:
    first = _first_look(_view("Presentación1 - PowerPoint", _PPT_TAB))
    view = _view("Presentación1 - PowerPoint", _PPT_TAB, firstLook=first, chosenBeforeClick={"1": ["transiciones", "ninguna"]})
    decision = _validate(
        {"act": "done", "evidence": "TabItem «Transiciones» · selected focused"}, view, [_click(1, "Transiciones")], _PPT_GOAL)
    assert decision["operation"] == "done"
    assert decision["arguments"] == {"evidence": "Transiciones", "already": True}


def test_cited_line_with_a_state_the_control_lacks_stays_refused() -> None:
    first = _first_look(_view("Presentación1 - PowerPoint", _PPT_BEFORE))
    view = _view("Presentación1 - PowerPoint", _PPT_BEFORE, firstLook=first, chosenBeforeClick={"1": ["inicio"]})
    decision = _validate(
        {"act": "done", "evidence": "TabItem «Transiciones» · selected"}, view, [_click(1, "Transiciones")], _PPT_GOAL)
    assert decision["operation"] == "none"


# v3-02 turn 2, after the click on «Desvanecer» (req 15): the model clicked it again.
_PPT_FADE = """
18 · TabItem · «Transiciones» · selected focused · TL
19 · TabItem · «Animaciones» · T
32 · ListItem · «Desvanecer» · selected · TL
36 · Button · «Efectos de transición» · collapsed · T
42 · Button · «Aplicar a todas» · T
"""
_FADE_GOAL = "En PowerPoint, aplica la transición Desvanecer a la diapositiva activa"


def test_v3_02_click_again_on_the_option_the_click_chose_is_done() -> None:
    first = _first_look(_view("Presentación1 - PowerPoint", _PPT_TAB))
    view = _view("Presentación1 - PowerPoint", _PPT_FADE, firstLook=first, chosenBeforeClick={"1": ["transiciones", "ninguna"]})
    decision = _validate({"act": "click", "i": 32, "label": "Desvanecer"}, view, [_click(1, "Desvanecer")], _FADE_GOAL)
    assert decision["operation"] == "done"
    assert decision["arguments"] == {"evidence": "Desvanecer"}


def test_click_on_an_option_never_pressed_is_still_a_click() -> None:
    view = _view("Presentación1 - PowerPoint", _PPT_FADE, chosenBeforeClick={})
    decision = _validate({"act": "click", "i": 32, "label": "Desvanecer"}, view, [_click(1, "Transiciones")], _FADE_GOAL)
    assert decision["operation"] == "input.visible.click"


# v3-09 sub-goal 2 (req 14): the highlighter selected after the click, cited in an invented form.
_ONENOTE_DRAW = """
8 · TabItem · «Inicio» · TL
10 · TabItem · «Dibujar» · selected · TL
13 · SplitButton · «Borrador de trazos» · collapsed · TL
15 · SplitButton · «Pluma: Negro, 1 mm» · collapsed · T
18 · SplitButton · «Marcador de resaltado: Amarillo, 5 mm» · selected collapsed · T
19 · SplitButton · «Pluma: Azul oscuro, 1 mm» · collapsed · T
40 · TreeItem · «Nueva sección 3» · selected · valor=«Nueva sección 3» · L
"""


def test_v3_09_invented_citation_leaves_the_option_the_click_chose() -> None:
    history = [_click(6, "Dibujar"), _click(7, "Marcador de resaltado: Amarillo, 5 mm"),
               _click(8, "Marcador de resaltado: Amarillo, 5 mm")]
    view = _view("Sin título - OneNote", _ONENOTE_DRAW, chosenBeforeClick={"7": ["dibujar", "nueva seccion 3"]})
    decision = _validate(
        {"act": "done", "evidence": "control:=marcador amarillo:selected"}, view, history, "seleccionar marcador amarillo")
    assert decision["operation"] == "done"
    assert decision["arguments"] == {"evidence": "Marcador de resaltado: Amarillo, 5 mm"}


def test_invented_citation_with_the_option_not_last_pressed_stays_refused() -> None:
    history = [_click(7, "Marcador de resaltado: Amarillo, 5 mm"), _click(8, "Borrador de trazos")]
    view = _view("Sin título - OneNote", _ONENOTE_DRAW, chosenBeforeClick={"7": [], "8": []})
    decision = _validate(
        {"act": "done", "evidence": "control:=marcador amarillo:selected"}, view, history, "seleccionar marcador amarillo")
    assert decision["operation"] == "none"


# v3-10 (req 8): «receta» typed into OneNote's search box, its results listed; the model cited a joined OCR line.
_ONENOTE_SEARCH = """
2 · Edit · «Búsqueda de Microsoft» · focused · valor=«receta» · T
3 · MenuItem · «Más resultados de cuadernos de Copilot» · T
4 · MenuItem · «Más resultados de cuadernos» · T
7 · MenuItem · «"receta"» · C
13 · TabItem · «Inicio» · TL
31 · TreeItem · «Nueva sección 3» · selected · valor=«Nueva sección 3» · L
"""
_ONENOTE_HOME = """
4 · Edit · «Búsqueda de Microsoft» · valor=«Buscar» · T
9 · TabItem · «Inicio» · TL
27 · TreeItem · «Nueva sección 3» · selected · valor=«Nueva sección 3» · L
"""
_SEARCH_GOAL = "search my onenote notebooks for receta"
_SEARCH_HISTORY = [
    _click(1, "Búsqueda de Microsoft"),
    {"step": 2, "operation": "input.text.type", "ok": True, "text": "receta", "changed": True, "query": True},
]


def test_v3_10_the_search_box_baxy_wrote_with_its_results_proves_the_search() -> None:
    first = _first_look(_view("Sin título - OneNote", _ONENOTE_HOME))
    view = _view("Sin título - OneNote", _ONENOTE_SEARCH, firstLook=first, newText=["9", "eceta"])
    decision = _validate(
        {"act": "done", "evidence": "9 | Sin titulo | - OneNote | Archivo | Inicio | Insertar | v Cuadernos de Copiol"},
        view, _SEARCH_HISTORY, _SEARCH_GOAL)
    assert decision["operation"] == "done"
    assert decision["arguments"] == {"evidence": "Búsqueda de Microsoft"}


def test_contracase_citing_only_what_was_typed_is_no_proof() -> None:
    first = _first_look(_view("Sin título - OneNote", _ONENOTE_HOME))
    view = _view("Sin título - OneNote", _ONENOTE_SEARCH, firstLook=first, newText=["9", "eceta"])
    decision = _validate({"act": "done", "evidence": "receta"}, view, _SEARCH_HISTORY, _SEARCH_GOAL)
    assert decision["operation"] != "done" or decision["arguments"]["evidence"] != "receta"


def test_contracase_search_box_alone_with_nothing_found_proves_nothing() -> None:
    first = _first_look(_view("Sin título - OneNote", _ONENOTE_HOME))
    lines = "\n".join(line for line in _ONENOTE_SEARCH.strip().splitlines() if "receta\"" not in line)
    view = _view("Sin título - OneNote", lines, firstLook=first)
    decision = _validate({"act": "done", "evidence": "9 | Sin titulo | - OneNote"}, view, _SEARCH_HISTORY, _SEARCH_GOAL)
    assert decision["operation"] == "none"


# v3-13 (req 9): the app's theme was already «Oscuro»; the mission opened Settings and its theme section.
_PLAYER_HOME = """
11 · ListItem · «Configuración» · BL
12 · ListItem · «Biblioteca de música» · BL
"""
_PLAYER_THEME = """
12 · ListItem · «Configuración» · selected · BL
19 · RadioButton · «Claro» · BL
20 · RadioButton · «Oscuro» · selected · BL
21 · RadioButton · «Usar configuración del sistema» · BL
28 · Text · «Configuración» · T
41 · Text · «Oscuro» · R
"""
_THEME_GOAL = "en el reproductor multimedia de windows pon el tema oscuro desde configuración"


def test_v3_13_option_chosen_before_any_act_on_it_is_said_already() -> None:
    first = _first_look(_view("Reproductor multimedia", _PLAYER_HOME))
    view = _view("Reproductor multimedia", _PLAYER_THEME, firstLook=first,
                 chosenBeforeClick={"1": [], "2": ["configuracion"]})
    history = [_click(1, "Configuración"), _click(2, "Tema de la aplicación")]
    decision = _validate({"act": "done", "evidence": "RadioButton «Oscuro» · selected"}, view, history, _THEME_GOAL)
    assert decision["operation"] == "done"
    assert decision["arguments"] == {"evidence": "Oscuro", "already": True}


def test_v3_13_invented_citation_also_leaves_already() -> None:
    first = _first_look(_view("Reproductor multimedia", _PLAYER_HOME))
    view = _view("Reproductor multimedia", _PLAYER_THEME, firstLook=first,
                 chosenBeforeClick={"1": [], "2": ["configuracion"]})
    history = [_click(1, "Configuración"), _click(2, "Tema de la aplicación")]
    decision = _validate({"act": "done", "evidence": "tema: oscuro (activo)"}, view, history, _THEME_GOAL)
    assert decision["operation"] == "done"
    assert decision["arguments"] == {"evidence": "Oscuro", "already": True}


def test_v3_13_final_says_it_was_already_chosen_never_no_pude() -> None:
    observed = {
        "goal": _THEME_GOAL, "application": "Reproductor multimedia", "reached": True, "alreadyChosen": "Oscuro",
        "satisfiedBy": "model_evidence", "evidence": "Oscuro",
        "steps": [_click(1, "Configuración"), _click(2, "Tema de la aplicación")],
    }
    said = cu_finals.floor_first(observed, english=False, succeeded=True)
    assert said == "«Oscuro» ya estaba elegido en «Reproductor multimedia»."
    assert cu_finals.floor_sentence(observed, english=False, succeeded=True) == said
    assert cu_finals.floor_first(observed, english=True, succeeded=True) == "«Oscuro» was already chosen in «Reproductor multimedia»."


def test_final_without_already_chosen_is_unchanged() -> None:
    observed = {
        "goal": _THEME_GOAL, "application": "Reproductor multimedia", "reached": True, "evidence": "Oscuro",
        "satisfiedBy": "model_evidence", "steps": [_click(1, "Configuración"), _click(2, "Oscuro")],
    }
    assert "ya estaba" not in cu_finals.floor_sentence(observed, english=False, succeeded=True)


# Falsos éxitos (pasada v3 r9).
# v3-11 (req 16): «crea una página nueva» ended on OneNote's warning about a section name and cited it as done.
_ONENOTE_WARNING = """
31 · TreeItem · «Crear una nueva sección» · BL
34 · Edit · «Cuadro de texto Nombre de sección» · focused · valor=«n» · L
36 · Text · «Ya existe una sección con ese nombre. Utilice otro nombre.» · L
"""


def test_v3_11_a_warning_that_something_failed_is_no_proof() -> None:
    first = _first_look(_view("Sin título - OneNote", _ONENOTE_HOME))
    view = _view("Sin título - OneNote", _ONENOTE_WARNING, firstLook=first)
    history = [_click(1, "Crear una nueva sección"),
               {"step": 2, "operation": "input.text.type", "ok": True, "text": "n", "changed": True}]
    decision = _validate(
        {"act": "done", "evidence": "Ya existe una sección con ese nombre. Utilice otro nombre."}, view, history,
        "en onenote crea una pagina nueva")
    assert decision["operation"] == "none"
    # Counter-case: a reading cites what the window says, a warning too.
    reading = _validate(
        {"act": "done", "evidence": "Ya existe una sección con ese nombre. Utilice otro nombre."}, view, history,
        "leer el aviso de onenote")
    assert reading["operation"] == "done"


def test_v3_43_a_loading_bar_is_no_fact_to_answer_with() -> None:
    observed = {
        "goal": "hacer clic en opciones de energia; y responder: ¿qué plan está activo?", "application": "Panel de control",
        "reached": True, "steps": [_click(1, "Opciones de energía")],
        "screen": {"values": [{"name": "Cargando", "value": "0"}, {"name": "Equilibrado", "value": "seleccionado"}]},
    }
    seen = cu_projection.project_seen(observed, "es")
    assert [item["name"] for item in seen["screen"]["values"]] == ["Equilibrado"]
    assert cu_reply_checks.ungrounded_word("llegue al plan de energia cargando", seen) is not None


def test_r15b_v3_16_a_busy_bar_is_no_fact_either() -> None:
    # Pasada r15b (v3-16): the image editor still opening showed a ProgressBar «Ocupado»; the App reads such a look
    # again (ComputerUseMission.ShowsLoading, data «computerUse.loadingBar») and drops the bar from what the final
    # quotes (ComputerUseMission.ScreenExcerpt). Review of fable/cu-v3-carga-preguntas (finding 4): «Ocupado» and
    # «Busy» are a loading indicator only on a ProgressBar; on another control they are the window's fact, so the
    # mind's filter (any control, no kind) keeps them and drops only the names that always mean a wait.
    floor = operation_floor.floor_data()["computerUse"]
    bar = re.compile(floor["loadingBar"])
    anywhere = re.compile(floor["loading"])
    assert all(bar.search(name) for name in ("ocupado", "busy", "cargando", "loading"))
    assert not anywhere.search("ocupado") and not anywhere.search("busy")
    observed = {
        "goal": "abrir el calendario; y responder: ¿cómo se muestra la reunión?", "application": "Calendario",
        "reached": True, "steps": [_click(1, "Reunión")],
        "screen": {"values": [{"name": "Cargando", "value": "0"}, {"name": "Ocupado", "state": "selected"},
                              {"name": "Busy", "state": "selected"}]},
    }
    seen = cu_projection.project_seen(observed, "es")
    assert [item["name"] for item in seen["screen"]["values"]] == ["Ocupado", "Busy"]
