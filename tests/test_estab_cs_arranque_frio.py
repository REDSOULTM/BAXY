"""Encargo CS de estabilización (banco fz1, primera corrida tras reiniciar, 2026-10-13): «en Steam andá a la biblioteca»
con Steam cerrado. La primera ventana fue el actualizador («Actualizando Steam...» a 0, «Verificando instalación...» y un
solo botón «Cancelar»); el modelo respondió {"act":"open","i":0}, que se ejecutó como clic en «Cancelar» y abortó el
arranque. Lo que una ventana muestra en curso (una barra de progreso) no lo detiene un clic que nadie pidió; «cancelá la
actualización» sí lo pulsa. Las palabras están en data/account_acts.v1.json («abortsInProgress»). La espera de la
apertura a la ventana principal es de la App (ComputerUseLoopTests: AnUpdaterWindowOfAnApplicationJustStarted...)."""

from __future__ import annotations

import copy

import pytest

from baxy_mind import cu_validate
from baxy_mind.semantic.account_acts import aborts_unasked

CHECK = "control:biblioteca:current|title:biblioteca|page:biblioteca|control:library:current|title:library|mark:biblioteca"

# The view the model got in banco fz1 s12 (model_calls.jsonl, request 9), as the mind receives it.
UPDATER = {
    "window": {"title": "Steam", "process": "steam", "processId": 7268, "requested": True, "foreground": False},
    "controls": [
        {"i": 0, "kind": "Button", "name": "Cancelar", "zone": "BR"},
        {"i": 4, "kind": "Text", "name": "Actualizando Steam...", "zone": "C"},
        {"i": 5, "kind": "ProgressBar", "name": "Actualizando Steam...", "value": "0", "zone": "C"},
        {"i": 6, "kind": "Text", "name": "Verificando instalación...", "zone": "B"},
        {"i": 7, "kind": "Button", "name": "Maximizar", "state": "disabled", "zone": "TR"},
    ],
    # Its OCR as read (the garbled repeats kept the existing «updating» gate from holding: too many other lines).
    "text": {
        "TL": ["O", "Steam"], "TR": ["x"], "L": ["Actualizando Steam...", "Actuüando Steam..."],
        "BL": ["Verificando nstalacón...", "Verificando hstalación..."], "BR": ["Cancelar"],
    },
}


LAUNCHER = "Lanzador"


def _decide(view: dict, answer: dict, goal: str, objective: str) -> dict:
    """The model's answer through every check of its act (the step s12 sent: «e5_cold», the model's own)."""

    history = [{"step": 1, "operation": "app.open", "appId": LAUNCHER, "ok": True}]
    return cu_validate.validate_decision(
        answer, view=copy.deepcopy(view), last_failed=None, application_names=[LAUNCHER], goal=goal, history=history,
        objective=objective, success_check=CHECK, application=LAUNCHER,
    )


def test_the_frozen_view_is_no_gate_screen() -> None:
    from baxy_mind.cu_gates import app_gate

    assert app_gate(copy.deepcopy(UPDATER)) is None, "the refusal below is the guard's, not the gate's"


def _presses(step: dict, label: str) -> bool:
    arguments = step.get("arguments") if isinstance(step.get("arguments"), dict) else {}
    return step.get("operation") == "input.visible.click" and arguments.get("label") == label


@pytest.mark.parametrize("answer", [{"act": "open", "i": 0}, {"act": "click", "i": 0}])
def test_the_updaters_cancel_is_never_pressed_on_the_way_to_a_place(answer: dict) -> None:
    step = _decide(UPDATER, answer, "ir a biblioteca", "en Lanzador andá a la biblioteca")
    assert not _presses(step, "Cancelar"), step
    assert step.get("code") == "aborts_in_progress", step


@pytest.mark.parametrize(
    ("goal", "objective"),
    [
        ("cancelar la actualizacion", "cancelá la actualización de Lanzador"),
        ("cancel the update", "cancel Lanzador's update"),
    ],
)
def test_a_mission_that_asks_to_cancel_presses_it(goal: str, objective: str) -> None:
    step = _decide(UPDATER, {"act": "click", "i": 0}, goal, objective)
    assert _presses(step, "Cancelar"), step


def test_a_cancel_with_nothing_in_progress_stays_the_models() -> None:
    dialog = copy.deepcopy(UPDATER)
    dialog["controls"] = [control for control in dialog["controls"] if control["kind"] != "ProgressBar"]
    step = _decide(dialog, {"act": "click", "i": 0}, "ir a biblioteca", "en Lanzador andá a la biblioteca")
    assert _presses(step, "Cancelar"), step


@pytest.mark.parametrize(
    ("label", "said", "aborts"),
    [
        ("Cancelar", ("ir a biblioteca",), True),
        ("Salir", ("go to the library",), True),
        ("Close", ("abrir la biblioteca",), True),
        ("Cancelar", ("cancelá la descarga",), False),
        ("Stop", ("stop the download",), False),
        ("Cancelar", ("ir a biblioteca", "cerrá Steam cuando termine"), False),
        ("Cancelar", ("ir a biblioteca sin cancelar nada",), True),
        ("Biblioteca", ("ir a biblioteca",), False),
        ("Lista de cancelaciones", ("ir a biblioteca",), False),
    ],
)
def test_what_stops_work_in_progress_and_who_asks_for_it(label: str, said: tuple[str, ...], aborts: bool) -> None:
    assert aborts_unasked(label, *said) is aborts
