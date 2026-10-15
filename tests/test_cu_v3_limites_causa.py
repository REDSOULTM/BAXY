"""Computer use v3, límites del PC (M3): la causa llega a la respuesta.

Vivo 2026-10-07 (v3-72): «abre el administrador de tareas, ve a Rendimiento…» paró con
computer_use_window_elevated, pero la respuesta publicada dijo «el Administrador de tareas no me dejó entrar», sin
nombrar al administrador: la persona no sabe qué hacer. Un final de misión parado en un límite del PC (una ventana de
administrador, una pantalla de puerta) sin las palabras de su causa (datos: operation_floor.v1.json
«computerUse.causeWords») se veta «cause_omitted» y se reintenta con la pista; el suelo la dice siempre. Contracasos:
el mismo final vago en una parada que no es un límite del PC, y los finales que sí dicen la causa.
"""

from __future__ import annotations

import pytest

from baxy_mind import computer_use, operation_floor
from baxy_mind import cu_reply_checks
from baxy_mind import cu_finals
from baxy_mind import visible_defect
from baxy_mind.semantic.normalize import _accent_folded_with_punctuation

ELEVATED_SEEN = {
    "goal": "ir a rendimiento; luego ir a memoria", "reached": False, "stepsDone": ["trajo la aplicación al frente"],
    "windowTitle": "Administrador de tareas", "joined": False, "application": "Administrador de tareas",
    "stoppedBy": "computer_use_window_elevated",
    "subgoals": [{"goal": "ir a rendimiento", "application": "Administrador de tareas", "reached": False},
                 {"goal": "ir a memoria", "application": "Administrador de tareas", "reached": False}],
}
GATE_SEEN = {
    "goal": "ir a calendario", "reached": False, "stepsDone": [], "windowTitle": "Outlook", "joined": False,
    "application": "Outlook (classic)", "stoppedBy": "computer_use_app_gate",
    "gate": "Configuración de cuenta de correo electrónico",
}


def _fold(text: str) -> str:
    return _accent_folded_with_punctuation(text)


@pytest.mark.parametrize(
    ("seen", "reply"),
    [
        (ELEVATED_SEEN, "No pude ver la velocidad de la RAM porque el Administrador de tareas no me dejó entrar."),
        (ELEVATED_SEEN, "I couldn't get to Performance because Task Manager did not let me in."),
        (GATE_SEEN, "No pude llegar al calendario porque la pantalla se quedó igual."),
    ],
)
def test_a_limit_of_the_pc_told_without_its_cause_is_vetoed(seen: dict, reply: str) -> None:
    assert cu_reply_checks.mission_defect(_fold(reply), seen) == "cause_omitted"


@pytest.mark.parametrize(
    ("seen", "reply"),
    [
        (ELEVATED_SEEN, "No pude ir a Rendimiento: el Administrador de tareas corre como administrador y Windows no deja "
                        "que otra aplicación lo controle."),
        (ELEVATED_SEEN, "I couldn't get to Performance: Task Manager runs as administrator."),
        (GATE_SEEN, "No pude llegar al calendario: Outlook pide una cuenta y eso te toca a ti."),
        (GATE_SEEN, "No pude llegar al calendario: Outlook muestra «Configuración de cuenta de correo electrónico»."),
        (GATE_SEEN, "I couldn't get to the calendar: Outlook asks you to sign in first."),
    ],
)
def test_a_limit_told_with_its_cause_passes(seen: dict, reply: str) -> None:
    assert cu_reply_checks.mission_defect(_fold(reply), seen) is None


def test_a_stop_that_is_no_limit_of_the_pc_keeps_its_own_rules() -> None:
    seen = {**GATE_SEEN, "stoppedBy": "computer_use_surface_unchanged"}
    seen.pop("gate")
    assert cu_reply_checks.mission_defect(_fold("No pude llegar al calendario porque la pantalla se quedó igual."),
                                       seen) is None


def test_the_composer_gate_vetoes_the_vague_final_of_v3_72() -> None:
    facts = {"situation": {
        "kind": "failure", "polarity": "failure", "cause": "mission_failed",
        "reason": {
            "kind": "operation", "operation": "mission.computer.use", "polarity": "failure", "verified": False,
            "succeeded": False, "error": "computer_use_window_elevated",
            "observed": {"goal": "ir a rendimiento; luego ir a memoria" + computer_use.QUESTION_MARK
                                 + "dime la velocidad de la RAM", "application": "Administrador de tareas",
                         "reached": False, "steps": [{"step": 1, "operation": "app.open", "ok": True}],
                         "window": {"title": "Administrador de tareas", "process": "Taskmgr"},
                         "stoppedBy": "computer_use_window_elevated"},
        },
    }}
    situation = facts["situation"]["reason"]
    vague = "No pude ver la velocidad de la RAM porque el Administrador de tareas no me dejó entrar."
    named = ("No pude ir a Rendimiento: el Administrador de tareas corre como administrador y Windows no deja que "
             "otra aplicación lo controle.")
    asked = "abre el administrador de tareas, ve a Rendimiento, luego a Memoria y dime la velocidad de la RAM"
    assert visible_defect.compose_visible_defect(vague, "error", asked, {"situation": situation}) == "cause_omitted"
    assert visible_defect.compose_visible_defect(named, "error", asked, {"situation": situation}) != "cause_omitted"


def test_the_elevated_floor_offers_to_reopen_it_only_when_its_program_stays_unraised() -> None:
    # v3 r5a M5: BAXY opens what Windows would raise unasked with the person's rights; a window already running as
    # administrator stays an honest limit. Review of M5: the offer to try again without those rights is said only when
    # the window's program would stay unraised (computer_use_window_elevated_reopenable, a console measured live).
    observed = {"goal": "ir a la cola de impresion", "application": "Servicios", "reached": False,
                "steps": [{"step": 1, "operation": "app.open", "ok": True}],
                "stoppedBy": "computer_use_window_elevated_reopenable"}
    es = cu_finals.floor_sentence(observed, False, False)
    en = cu_finals.floor_sentence(observed, True, False)
    assert "administrador" in _fold(es) and "sin permisos de administrador" in _fold(es) and "intentar" in _fold(es)
    assert "without administrator rights" in en and "try" in en
    # Counter-case (v3-22/67/72): the Task Manager raises itself again; its limit carries no offer that would be false.
    task_manager = {**observed, "goal": "ir a rendimiento", "application": "Administrador de tareas",
                    "stoppedBy": "computer_use_window_elevated"}
    es = cu_finals.floor_sentence(task_manager, False, False)
    assert "administrador" in _fold(es) and "sin permisos" not in _fold(es) and "intentar" not in _fold(es)
    assert "without administrator rights" not in cu_finals.floor_sentence(task_manager, True, False)
    # Counter-case: another stop never carries the offer.
    other = {**observed, "stoppedBy": "computer_use_surface_unchanged"}
    assert "sin permisos" not in _fold(cu_finals.floor_sentence(other, False, False))


def test_the_reopenable_limit_is_vetoed_without_its_cause_like_the_elevated_one() -> None:
    # The same cause words hold for both elevated stops: a final without «administrador» is cause_omitted.
    words = operation_floor.floor_data()["computerUse"]["causeWords"]
    assert words["computer_use_window_elevated_reopenable"] == words["computer_use_window_elevated"]
