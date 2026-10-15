"""Estabilización L4: cinco límites de partida que la corrida en vivo limites1 (2026-10-11, 4d9c38ac1) no dijo como límite.

- t-drag-4 «en Paint draw una línea recta arrastrando el mouse …, más o menos por la mitad» → «En eso no encuentro un
  pedido para mí»: el lector del arrastre lo leía, pero el pedido no tenía autoridad (ni «draw» es un verbo de orden ni
  «más o menos» deja de ser una alternativa) y el guardia de lo oído de fondo lo tomó por charla. Ahora el arrastre que
  lee el lector de actos es un pedido (``patterns._is_direct_request``) y una aproximación no es una corrección.
- t-drag-3 «agarrá la nota … y llevala arrastrando a la esquina de arriba …» → el motor abrió Notas rápidas y paró con
  una causa genérica: llevar algo con el gesto dicho como manera es el límite (``semantic.drag``), y «drag and drop» es
  un solo acto.
- t-scroll-2 «búscame la omega mayúscula, la Ω, bajando en la lista» → tecleó en el buscador: lo buscado bajando por una
  lista se revela («mostrar X»), y una lista que la rueda ya no mueve, o movió las vueltas permitidas, es el límite de
  lista larga dicho por el propio paso (``cu_navigation._reveal_step``), nunca el modelo.
- t-scroll-3: el tiempo se fue en un clic por nombre de 33 s sobre «Fonts», fuera de la vista; Fuentes tiene dirección
  propia (ms-settings:fonts, sonda estab/L4_sonda) y el paso a la lista llega sin clics.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from baxy_mind import computer_use, cu_model_calls
from baxy_mind.cu_navigation import _reveal_step
from baxy_mind.semantic import app_places, guards, limits, missions, patterns
from baxy_mind.semantic.drag import asks_to_drag
from baxy_mind.semantic.normalize import fold

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "scripts" / "cu_live" / "cases"
OPERATIONS = ("mission.computer.use", "window.move", "window.snap", "filesystem.move", "app.open", "audio.volume")
APPS = ("Configuración", "Mapa de caracteres", "Explorador de archivos", "Paint", "Notas rápidas", "Bloc de notas")


def _case(name: str) -> str:
    return (CASES / f"{name}.turns").read_text(encoding="utf-8").strip()


# ------------------------------------------------------------------------------------------------- the drag, said

@pytest.mark.parametrize(
    "said",
    [
        _case("t-drag-3"),
        _case("t-drag-4"),
        "llevá la nota arrastrando a la esquina de arriba",
        "movela arrastrando hasta la papelera",
        "move the file to the folder by dragging it",
        "drag and drop the photo onto the desktop folder",
        "arrastrá y soltá lista.txt en la carpeta archivo",
        "en el explorador pasá lista.txt a la carpeta archivo arrastrándolo",
        "draw a line in Paint dragging the mouse from left to right",
        "dibujame un círculo en paint",
    ],
)
def test_the_drag_in_any_form_is_a_request_and_the_known_limit(said: str) -> None:
    assert asks_to_drag(said)
    # A request: the known limit closes the turn before the overheard-talk guard or the engine (turn_decide).
    assert patterns.effect_request_is_authoritative(said)
    assert patterns.known_unsupported_effect_request(said, OPERATIONS)
    assert missions.free_form_arguments(said, APPS) is None


@pytest.mark.parametrize(
    "said",
    [
        # A window, the pointer or a level, carried with the gesture said or not: their own operations.
        "llevá la ventana arrastrando a la izquierda",
        "arrastrá la nota a la otra pantalla",
        "arrastrá el puntero hasta Aceptar",
        "arrastrá el volumen al 50",
        # H2 (revisión L2): dictated, quoted or searched words are no act.
        "en el Bloc de notas escribí: arrastrá los archivos a la papelera",
        "escribí «drag and drop» en el bloc de notas",
        "en Spotify buscá Drag Me Down y ponela",
        "en discord mandale a Ana: llevalo arrastrando a la carpeta",
        "buscá cómo dibujar una línea en paint",
        # Talk: a gerund after a verb that carries nothing.
        "en el bloc de notas escribí hoy me fui arrastrando a casa",
        "ayer me fui arrastrando a casa de lo cansado que estaba",
    ],
)
def test_contracase_no_drag_where_nothing_is_dragged(said: str) -> None:
    assert not asks_to_drag(said)
    assert not patterns.known_unsupported_effect_request(said, OPERATIONS)


def test_t_drag_4_is_no_longer_read_as_overheard_talk_once_it_is_a_request() -> None:
    said = _case("t-drag-4")
    # The guard alone still sees fifteen words with no listed order verb; turn_decide lifts it for an authoritative
    # request (M112), which the drag now is.
    assert guards._unresolved_input_kind(said, APPS) == "overheard_speech"
    assert patterns.effect_request_is_authoritative(said)


@pytest.mark.parametrize(
    ("said", "corrected"),
    [
        ("dibujá una línea más o menos por la mitad", False),
        ("set the volume to more or less 40", False),
        ("poné el volumen más o menos a 30", False),
        # Contracases: a real alternative or a correction still is one.
        ("abrí el bloc de notas o la calculadora", True),
        ("abrí spotify, no, mejor youtube", True),
    ],
)
def test_an_approximation_is_no_alternative(said: str, corrected: bool) -> None:
    assert patterns._has_contradictory_correction(fold(said)) is corrected


# ------------------------------------------------------------------------------------------ the list, looked down

def test_t_scroll_2_looks_down_the_list_instead_of_typing_in_a_search() -> None:
    mission = missions.mission_request(_case("t-scroll-2"), APPS)
    assert [step.goal for step in mission.steps] == ["mostrar omega mayuscula", "seleccionar omega mayuscula"]
    assert mission.steps[0].success_check == "control:=omega mayuscula"


@pytest.mark.parametrize(
    ("said", "goal"),
    [
        ("en configuración find Times New Roman by scrolling down the list", "mostrar times new roman"),
        ("en el mapa de caracteres encontrá la omega bajando", "mostrar omega"),
        # Contracases: a search said without scrolling types it; a counted scroll is no reveal.
        ("en el mapa de caracteres buscá la omega mayúscula", "buscar omega mayúscula"),
        ("en el explorador buscá informe.docx", "buscar informe.docx"),
    ],
)
def test_what_is_looked_for_by_scrolling_is_shown(said: str, goal: str) -> None:
    assert missions.mission_request(said, APPS).goal == goal


def _scroll(*, ok: bool = True, changed: bool = True, label: str | None = None) -> dict:
    scroll = {"operation": "input.scroll", "ok": ok, "changed": changed, "surfaceChanged": changed}
    if label:
        scroll["label"] = label
    return scroll


_GRID = {"window": {"title": "Mapa de caracteres", "process": "charmap"}, "controls": [
    {"i": 0, "kind": "ComboBox", "name": "Fuente:"}, {"i": 1, "kind": "Edit", "name": "Buscar:"}]}


def test_a_list_the_wheel_does_not_move_is_the_long_list_limit_at_once() -> None:
    # t-scroll-2 live: the reveal by name found nothing and the wheel did not move the grid (ok false).
    stopped = _reveal_step("omega mayuscula", _GRID, [_scroll(ok=False, label="omega mayuscula"), _scroll(ok=False)])
    assert stopped == {"operation": "none", "arguments": {}, "reason": "la lista no acaba", "code": "limit:long_list"}
    unmoved = _reveal_step("omega mayuscula", _GRID, [_scroll(ok=False, label="omega mayuscula"), _scroll(changed=False)])
    assert unmoved["code"] == "limit:long_list"


def test_the_wheel_turns_a_sub_goal_may_spend_end_in_the_limit() -> None:
    spent = int(limits.limits_data()["longListScrolls"])
    first = [_scroll(ok=False, label="omega mayuscula")]
    going = _reveal_step("omega mayuscula", _GRID, first + [_scroll()] * (spent - 1))
    assert going["operation"] == "input.scroll" and "label" not in going["arguments"]
    assert _reveal_step("omega mayuscula", _GRID, first + [_scroll()] * spent)["code"] == "limit:long_list"
    # Shown: nothing more to do, the shell's check closes it.
    shown = {**_GRID, "controls": [*_GRID["controls"], {"i": 2, "kind": "ListItem", "name": "Omega mayuscula"}]}
    assert _reveal_step("omega mayuscula", shown, first + [_scroll()] * spent) is None


class _Typist:
    """A model that would type the name into the window's search (what t-scroll-2 did live)."""

    def _post_schema_object(self, payload: dict, label: str) -> object:
        if payload["messages"][0]["content"] == cu_model_calls.TRANSLATE_PROMPT:
            return {"es": [], "en": []}
        return {"act": "type", "index": 1, "text": "omega mayuscula"}


def test_the_failed_wheel_never_reaches_the_model() -> None:
    decided = computer_use.decide_step(
        _Typist(), objective=_case("t-scroll-2"), goal="mostrar omega mayuscula", application="Mapa de caracteres",
        success_check="control:=omega mayuscula", view=_GRID,
        history=[{"step": 2, **_scroll(ok=False, label="omega mayuscula")}, {"step": 3, **_scroll(ok=False)}],
        budget_left=20, application_names=APPS, subgoal=0, subgoal_count=2,
    )
    assert decided["operation"] == "none" and decided["code"] == "limit:long_list"


@pytest.mark.parametrize("objective", ["en Chrome bajá 5 veces", "scroll down five times in Chrome"])
def test_contracase_a_counted_scroll_is_still_done(objective: str) -> None:
    view = {"window": {"title": "Noticias - Google Chrome", "process": "chrome"}, "controls": [
        {"i": 0, "kind": "List", "name": "Noticias"}]}
    assert not computer_use._looks_in_a_list(objective, "baja 5 veces", view, {"index": 0})


# ------------------------------------------------------------------------------------------ Settings › Fuentes

def test_t_scroll_3_reaches_the_fonts_by_address() -> None:
    mission = missions.mission_request(_case("t-scroll-3"), APPS)
    places = [app_places.place_of(step.application, step.goal) for step in mission.steps]
    assert [place and place["place"] for place in places] == ["personalization", "fonts", None, None]
    assert mission.steps[2].goal == "mostrar times new roman"


# ------------------------------------------------------------------------------------------ the bank does not move

def test_no_turn_of_the_bank_drags_or_looks_down_a_list() -> None:
    names = [line.strip() for line in (CASES / "BANCO_72.txt").read_text(encoding="utf-8").splitlines() if line.strip()]
    said = [line for name in names for line in (CASES / f"{name}.turns").read_text(encoding="utf-8").splitlines()
            if line.strip()]
    assert len(said) >= 72
    assert [line for line in said if asks_to_drag(line)] == []
    assert [line for line in said if "mostrar " in (getattr(missions.mission_request(line, APPS), "goal", "") or "")
            and "bajando" in fold(line)] == []
