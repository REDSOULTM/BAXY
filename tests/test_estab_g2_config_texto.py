"""Estabilización G2: «abre configuracion que quiero ver lo de la pantalla» en el notebook (tandas f2, t2-c03).

La Configuración del notebook abre en «Inicio», que recomienda «Pantalla de bloqueo» y no muestra ningún control
«Pantalla». La regla tomó «Pantalla de bloqueo» por contención («pantalla» ⊂ «pantalla de bloqueo»), el modelo vagó por
Personalización y en el paso 8 tecleó en el buscador «d ingo, ii de octubre», la fecha de la vista previa leída por OCR.
Tres arreglos: (1) al ir a un lugar, la contención no vale cuando el nombre añade palabras propias que nombran otro
lugar; (2) el modelo no teclea, yendo a un lugar, un texto que no sale del pedido; (3) las secciones de Configuración se
abren por su dirección ms-settings: (data/app_places.v1.json, el mecanismo del encargo C).

Las vistas son las reales congeladas (tests/data/estab_g2_config_vistas.json).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from baxy_mind.semantic.missions import fold as missions_fold
from baxy_mind import computer_use as cu
from baxy_mind import cu_view
from baxy_mind import cu_goals
from baxy_mind import cu_unasked
from baxy_mind import cu_rules
from baxy_mind import cu_validate
from baxy_mind import cu_model_calls
from baxy_mind.semantic import app_places, missions

ROOT = Path(__file__).resolve().parents[1]
VIEWS = json.loads((Path(__file__).parent / "data" / "estab_g2_config_vistas.json").read_text(encoding="utf-8"))["views"]
REQUEST = "abre configuracion que quiero ver lo de la pantalla"
NAMES = ("Configuración", "Steam", "Spotify", "Calculadora", "Bloc de notas", "PowerPoint")
SEARCH_BOX = "Cuadro de búsqueda, Buscar una opción"


def _view(*controls: dict, title: str = "Configuración", text: dict | None = None) -> dict:
    return {"window": {"title": title, "process": "x"}, "controls": list(controls), "text": text or {}}


def _control(i: int, kind: str, name: str, zone: str = "C") -> dict:
    return {"i": i, "kind": kind, "name": name, "zone": zone, "rect": {"x": 10, "y": 40 * i + 10, "w": 200, "h": 30}}


# ------------------------------------------------------------------------- (1) otro lugar no es el lugar


def test_the_lock_screen_recommendation_is_never_the_display_by_containment() -> None:
    home = VIEWS["nb_inicio_1343"]
    assert cu_view.find_control(home, "pantalla", placing=True) is None
    # Not going to a place, containment still counts as before.
    assert cu_view.find_control(home, "pantalla")["name"] == "Pantalla de bloqueo"


def test_on_the_notebooks_home_going_to_the_display_looks_it_up_and_never_presses_the_lock_screen() -> None:
    step = cu_rules.deterministic_step(goal="ir a pantalla", view=VIEWS["nb_inicio_1343"], history=[],
                                 application="Configuración", objective=REQUEST)
    assert step is not None
    assert "bloqueo" not in missions_fold(json.dumps(step["arguments"], ensure_ascii=False))
    # The window's search, with the place's name (the keyboard is on the search box).
    assert step == {**step, "operation": "input.text.type", "arguments": {"text": "pantalla"}}


def test_contracase_the_display_item_and_the_other_sections_are_still_pressed() -> None:
    system = cu_rules.deterministic_step(goal="ir a pantalla", view=VIEWS["nb_sistema_u8"], history=[],
                                   application="Configuración", objective=REQUEST)
    assert system["arguments"] == {"label": "Pantalla", "index": 23}
    home = VIEWS["nb_inicio_1343"]
    for goal, label in (("ir a sonido", "Sonido"), ("ir a bluetooth y dispositivos", "Bluetooth y dispositivos"),
                        ("ir a personalizacion", "Personalización"), ("ir a sistema", "Sistema")):
        step = cu_rules.deterministic_step(goal=goal, view=home, history=[], application="Configuración", objective=goal)
        assert step["operation"] == "input.visible.click" and step["arguments"]["label"] == label, goal


@pytest.mark.parametrize(("label", "name", "title", "another"), [
    ("pantalla", "Pantalla de bloqueo", "Configuración", True),
    ("screen", "Lock screen", "Settings", True),
    ("estandar", "Operadores estándar", "Calculadora", True),  # banco e3/f1/f2x1 y1: pressed for «volvé a estándar»
    ("bluetooth", "Bluetooth y dispositivos", "Configuración", False),  # a name that joins places
    ("bluetooth", "Bluetooth & devices", "Settings", False),
    ("youtube", "Never Gonna Give You Up - YouTube", "Opera", False),  # a title's part
    ("biblioteca", "Tu biblioteca", "Spotify", False),  # only a function word added
    ("biblioteca", "Abre Tu biblioteca", "Spotify", False),  # a verb that opens the place (data placeToggle)
    ("centro de movilidad", "Ver centro de movilidad", "Panel de control", False),  # a verb that leads there
    ("pantalla", "Configuración de pantalla", "Configuración", False),  # the window's own name added
    ("pantalla", "Pantalla 2", "Configuración", False),  # a number
    ("pantalla", "Pantalla", "Configuración", False),  # equal
    ("pantalla", "Pantallas", "Configuración", False),  # glued letters: judged as before
])
def test_a_name_that_adds_words_of_its_own_names_another_place(label: str, name: str, title: str, another: bool) -> None:
    assert cu_view.names_another_place(label, name, {"window": {"title": title}}) is another


@pytest.mark.parametrize(("label", "line", "another"), [
    ("pantalla", "Pantalla de bloqueo", True),
    ("tienda", "Buscar en la tienda", True),
    # Banco e3/f1/f2x1 x10, y10: the reading joins Steam's labels in one line; no function word links them.
    ("biblioteca", "BIBLIOTECA COMUNIDAD", False),
    ("store", "https://store.steampowered.com/", False),
])
def test_a_written_line_names_another_place_only_when_a_function_word_links_its_words(
    label: str, line: str, another: bool,
) -> None:
    assert cu_view.names_another_place(label, line, {"window": {"title": "Steam"}}, written=True) is another


def test_contracase_steams_written_row_still_takes_its_label() -> None:
    steam = _view(_control(0, "Pane", "Steam"), title="Steam", text={
        "TL": ["O Steam", "\"D TIENDA", "BIBLIOTECA COMUNIDAD", "https://store.steampowered.com/"],
        "T": ["Buscar en la tienda"],
    })
    for goal, label in (("ir a biblioteca", "biblioteca"), ("ir a tienda", "tienda")):
        step = cu_rules.deterministic_step(goal=goal, view=steam, history=[], application="Steam", objective=goal)
        assert step == {**step, "operation": "input.visible.click", "arguments": {"label": label}}, goal


def test_y1_twin_the_standard_operators_group_is_not_the_standard_mode() -> None:
    calculator = _view(
        _control(0, "Button", "Abrir navegación", "TL"), _control(1, "Group", "Operadores estándar"),
        _control(2, "Button", "Igual a", "B"), title="Calculadora",
    )
    assert cu_view.find_control(calculator, "estandar", placing=True) is None
    step = cu_rules.deterministic_step(goal="ir a estandar", view=calculator, history=[], application="Calculadora",
                                 objective="abrí la calculadora, poné el modo programador y después volvé a estándar")
    assert step is None or step["arguments"].get("label") != "Operadores estándar"


# ------------------------------------------------------------------------- (2) texto que nadie pidió


def _type(text: str, goal: str, objective: str, view: dict | None = None, field: str | None = SEARCH_BOX) -> dict:
    raw = {"act": "type", "text": text, **({"field": field} if field else {})}
    return cu_validate.validate_decision(
        raw, view=view or VIEWS["nb_pantalla_de_bloqueo_1344"], last_failed=None, application_names=NAMES, history=[],
        goal=goal, objective=objective, application="Configuración",
        success_check="control:pantalla:current|page:pantalla|control:display:current|page:display",
    )


def test_the_ocr_date_typed_in_settings_search_while_going_to_the_display_is_refused() -> None:
    refused = _type("d ingo, ii de octubre", "ir a pantalla", REQUEST)
    assert refused["operation"] == "none" and refused["code"] == "types_unasked_text"
    assert "types_unasked_text" in cu._RETRIED  # the model gets one more try, with the refusal in front of it
    # At the focus too (no field named).
    assert cu_unasked.unasked_text("domingo, 11 de octubre", "ir a pantalla", REQUEST) == "types_unasked_text"


def test_contracase_the_places_name_and_its_other_names_are_typed() -> None:
    for text in ("pantalla", "display", "Pantallas"):
        typed = _type(text, "ir a pantalla", REQUEST)
        assert typed["operation"] == "input.text.type" and typed["arguments"]["text"] == text, text


@pytest.mark.parametrize(("text", "goal", "objective"), [
    ("mouse", "buscar mouse", "en Configuración buscá mouse"),  # a search types what it searches
    ("hola", "escribir hola", "abrí el Bloc de notas y escribí hola"),  # writing types what it writes
    ("Querido Juan, te espero mañana", "escribir un mensaje", "abrí el Bloc de notas y escribí un mensaje"),
    ("2^10", "hacer clic en igual", "abrí la calculadora y calculá 2 elevado a 10"),  # derived: signs and numbers
    ("youtube.com", "ir a youtube", "andá a youtube en Opera"),  # an address derived from the request
    ("Organizador de diapositivas", "ir a slide sorter",  # pasada r30 v3-03: the place translated by the model
     "in powerpoint add a new slide and switch to slide sorter view"),
    ("Proyecto final", "ponle 'Proyecto final' de título", "abre powerpoint y ponle 'Proyecto final' de título"),
])
def test_contracase_a_text_that_comes_from_the_request_or_a_goal_that_writes_is_never_refused(
    text: str, goal: str, objective: str,
) -> None:
    assert cu_unasked.unasked_text(text, goal, objective) is None


def test_the_stray_letter_rule_is_the_same_rule() -> None:
    # Live v3-11: «n» as a section's name, in a field or at the focus, whatever the goal.
    assert cu_unasked.unasked_text("n", "crea una pagina nueva", "abre onenote, crea una pagina nueva y escribe comprar pan") == (
        "text_not_requested"
    )
    assert cu_unasked.unasked_text("x", "escribir x", "en el Bloc de notas escribí x") is None


# ------------------------------------------------------------------------- (3) Configuración por dirección

# The bank's Settings cases (scripts/cu_live/cases), each sub-goal with the place its address opens (measured on redpc,
# estab/G2_sonda) or None where Settings has no address for it and the mission goes on by clicks as before.
BANK = {
    "s03": ["bluetooth"],
    "c5": ["personalization", "colors"],
    "u8": ["system", "display"],
    "n4": [None],  # ms-settings:apps opens «Aplicaciones instaladas», not «Aplicaciones»
    "v3": ["system", "sound"],
    "v10": [None, "language"],  # «Hora e idioma» has no address of its own
    "x3": ["accessibility"],
    "x4": ["personalization", "themes"],
    "y2": ["bluetooth"],
    "y9": [None],  # a search: Settings has no address that searches
}


@pytest.mark.parametrize("case", sorted(BANK))
def test_the_banks_settings_cases_read_the_same_destination(case: str) -> None:
    said = (ROOT / "scripts" / "cu_live" / "cases" / f"{case}.turns").read_text(encoding="utf-8").strip()
    mission = missions.mission_request(said, NAMES)
    steps = mission.steps or (mission,)
    assert [step.application for step in steps] == ["Configuración"] * len(steps)
    # The question a sub-goal carries is the final's, never its place (as the step reads it: ``question_step_goal``).
    places = [
        app_places.place_of(step.application, cu_goals.question_step_goal(step.goal, step.application), said=said)
        for step in steps
    ]
    assert [place and place["place"] for place in places] == BANK[case]


def test_v11_and_the_notebooks_request_read_their_sections() -> None:
    assert app_places.place_of("Configuración", "ir a bluetooth y dispositivos") == {"place": "bluetooth"}
    assert app_places.place_of("Configuración", "ir a sistema") == {"place": "system"}
    mission = missions.mission_request(REQUEST, NAMES)
    assert app_places.place_of(mission.application, mission.goal, said=REQUEST) == {"place": "display"}


def test_the_notebooks_request_opens_the_display_by_its_address_as_its_first_step() -> None:
    step = cu._decide_step(
        None, objective=REQUEST, goal="ir a pantalla", application="Configuración", success_check=None,
        view=VIEWS["nb_inicio_1343"], history=[], budget_left=8, application_names=NAMES, subgoal=0, subgoal_count=1,
        translator=cu_model_calls.LabelTranslator(None, enabled=False),
    )
    assert step["operation"] == "app.open" and step["arguments"] == {"appId": "Configuración", "place": "display"}


def test_contracase_the_lock_screen_said_by_name_is_its_own_section() -> None:
    assert app_places.place_of("Configuración", "ir a pantalla de bloqueo") == {"place": "lockscreen"}
    assert app_places.place_of("Configuración", "ir a hora e idioma") is None
    assert app_places.place_of("Configuración", "buscar pantalla") is None
