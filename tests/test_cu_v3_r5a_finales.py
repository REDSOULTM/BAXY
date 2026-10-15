"""Computer use v3, pasada r5a (cu-v3/r5a/falsos.md): finales de misión.

M6: un intento afirmado en el final («intenté», «I tried») necesita un paso de esa operación, hecho o fallido; con 0
pasos sólo se puede dar la causa de parada (v3-21: «I tried to click the Details tab…» con 0 pasos).
Cada regla con su contracaso.
"""

from __future__ import annotations

from baxy_mind import computer_use, operation_floor
from baxy_mind import cu_finals
from baxy_mind import visible_defect
from baxy_mind.semantic import claims
from baxy_mind.semantic.normalize import _accent_folded_with_punctuation


def _mission(steps: list[dict], stopped: str = "computer_use_window_elevated") -> dict:
    return {"situation": {
        "kind": "failure", "polarity": "failure", "cause": "mission_failed",
        "reason": {
            "kind": "operation", "operation": "mission.computer.use", "polarity": "failure", "verified": False,
            "succeeded": False, "error": stopped,
            "observed": {"goal": "ir a detalles", "application": "Administrador de tareas", "reached": False,
                         "steps": steps, "stoppedBy": stopped},
        },
    }}


FAILED_CLICK = {"step": 1, "operation": "input.visible.click", "ok": False, "name": "Detalles",
                "error": "window_elevated"}
REQUEST = "abre el administrador de tareas y ve a detalles"
REQUEST_EN = "open task manager and go to details"


# ---------------------------------------------------------------- M6: attempts need their step
def test_v3_21_an_attempt_with_no_step_is_refused():
    reply = ("I tried to click the Details tab, but I couldn't: Task Manager runs as administrator and Windows does not let "
             "another application control it.")
    assert visible_defect.compose_visible_defect(reply, "error", REQUEST_EN, _mission([])) == "unbacked_attempt"
    spanish = ("Intenté pulsar la pestaña Detalles, pero no pude: el Administrador de tareas corre como administrador y "
               "Windows no deja que otra aplicación lo controle.")
    assert visible_defect.compose_visible_defect(spanish, "error", REQUEST, _mission([])) == "unbacked_attempt"


def test_an_attempt_backed_by_a_failed_step_of_its_operation_is_published():
    reply = ("I tried to click the Details tab, but I couldn't: Task Manager runs as administrator and Windows does not let "
             "another application control it.")
    assert visible_defect.compose_visible_defect(reply, "error", REQUEST_EN, _mission([FAILED_CLICK])) == ""
    spanish = ("No pude ir a Detalles: intenté hacer clic en Detalles, pero el Administrador de tareas corre como administrador y Windows no "
               "deja que otra aplicación lo controle.")
    assert visible_defect.compose_visible_defect(spanish, "error", REQUEST, _mission([FAILED_CLICK])) == ""


def test_an_attempt_of_another_act_than_the_steps_is_refused():
    # A failed click backs a click attempt, never a typed text.
    assert claims.unbacked_attempt("Intenté escribir «memoria» en el buscador.", ["input.visible.click"])
    assert claims.unbacked_attempt("I tried to type the name.", ["input.visible.click"])
    assert not claims.unbacked_attempt("Intenté escribir «memoria» en el buscador.", ["input.text.type"])


def test_the_cause_alone_and_what_is_no_attempt_pass_with_no_step():
    for reply in (
        "No pude ir a Detalles: el Administrador de tareas corre como administrador y Windows no deja que otra "
        "aplicación lo controle.",
        "No intenté nada: el Administrador de tareas corre como administrador.",
        "Puede que se trate de un permiso de administrador.",
        "Si quieres que lo intente de nuevo, ciérralo primero.",
        "¿Quieres que lo intente otra vez?",
    ):
        assert claims.unbacked_attempt(reply, []) == "", reply


def test_attempts_outside_a_mission_are_not_judged():
    situation = {"situation": {"kind": "operation", "operation": "app.open", "polarity": "failure",
                               "verified": False, "succeeded": False, "error": "launch_failed",
                               "observed": {"name": "Paint"}}}
    assert visible_defect.compose_visible_defect("Intenté abrir Paint, pero no se abrió.", "error", "abre paint",
                                      situation) != "unbacked_attempt"


# ---------------------------------------------------------------- M3: reached, question unread (v3-43)
def _reached(values: list[dict]) -> dict:
    return {
        "goal": "ir a opciones de energia" + computer_use.QUESTION_MARK + "qué plan de energía está activo",
        "application": "Panel de control", "reached": True,
        "satisfiedBy": "stepDone:input.visible.click:opciones de energia",
        "steps": [{"step": 1, "operation": "app.open", "ok": True},
                  {"step": 2, "operation": "input.visible.click", "ok": True, "name": "Opciones de energía"},
                  {"step": 3, "operation": "input.visible.click", "ok": True, "name": "Mostrar planes adicionales"}],
        "screen": {"values": values},
    }


def _reached_facts(observed: dict) -> dict:
    return {"situation": {"kind": "operation", "operation": "mission.computer.use", "polarity": "success",
                          "verified": True, "succeeded": True, "observed": observed}}


LOADING = [{"name": "Cargando", "value": 0}]
ASKED = "abre opciones de energía y dime qué plan de energía está activo"
ASKED_EN = "open opciones de energía and tell me which power plan is active"


def test_v3_43_the_floor_says_the_place_reached_and_the_question_unread_never_a_list():
    floor = cu_finals.floor_sentence(_reached(LOADING), False, True)
    assert floor.startswith("Llegué a «Opciones de energía»"), floor
    assert "no pude leer" in floor and "qué plan de energía está activo" in floor
    assert "hay 3" not in floor
    # The generic floor never counts a mission's steps as a list read.
    generic = operation_floor.floor_final(_reached_facts(_reached(LOADING))["situation"], False)
    assert "hay " not in generic, generic


def test_v3_43_a_settled_view_with_the_selected_option_is_answered():
    # Counter-case: once the page shows its selected plan, the floor answers it (no «no pude leer»).
    settled = _reached([{"name": "Equilibrado", "kind": "RadioButton", "state": "selected"},
                        {"name": "Economizador", "kind": "RadioButton", "state": ""}])
    settled["goal"] = ("ir a opciones de energia" + computer_use.QUESTION_MARK
                       + "dime si el plan es equilibrado o economizador")
    floor = cu_finals.floor_sentence(settled, False, True)
    assert "Equilibrado" in floor and "no pude leer" not in floor, floor


def test_v3_43_the_honest_draft_is_not_vetoed_as_a_failure_and_a_denied_arrival_still_is():
    facts = _reached_facts(_reached(LOADING))
    honest = "Llegué a Opciones de energía, pero no pude ver qué plan está activo: la página seguía cargando."
    assert visible_defect.compose_visible_defect(honest, "status", ASKED, facts) != "asserted_failure"
    denied = "No pude llegar a Opciones de energía, así que no sé qué plan está activo."
    assert visible_defect.compose_visible_defect(denied, "status", ASKED, facts) in {"asserted_failure", "unanswered_question"}
    # Without a question there is nothing unread: a «no pude ver» there is still a failure told.
    plain = _reached([])
    plain["goal"] = "ir a opciones de energia"
    assert not cu_finals.reached_but_unread(_accent_folded_with_punctuation(honest), plain)


def test_m3_review_a_draft_that_also_tells_a_failure_or_denies_the_place_is_still_vetoed():
    # Review of M3, measured on fable/cu-universal-v3 and on the first M3: both gave '' over a verified arrival.
    facts = _reached_facts(_reached(LOADING))
    for draft in ("No pude hacerlo: no se ve ningún plan.",
                  "No se muestra Opciones de energía; no pude ver el plan.",
                  "Opciones de energía no se muestra, así que no pude ver el plan."):
        assert visible_defect.compose_visible_defect(draft, "status", ASKED, facts) == "asserted_failure", draft
    assert visible_defect.compose_visible_defect("I couldn't do it: I couldn't see any plan.", "status", ASKED_EN,
                                      facts) == "asserted_failure"
    # Counter-cases: the unread answer alone, also when the place is named where it was read.
    for draft in ("Llegué a Opciones de energía, pero no pude ver qué plan está activo: la página seguía cargando.",
                  "No pude ver qué plan está activo en Opciones de energía: la página seguía cargando."):
        assert visible_defect.compose_visible_defect(draft, "status", ASKED, facts) != "asserted_failure", draft
    assert visible_defect.compose_visible_defect("I got to Opciones de energía, but I couldn't read which plan is active.",
                                      "status", ASKED_EN, facts) != "asserted_failure"
