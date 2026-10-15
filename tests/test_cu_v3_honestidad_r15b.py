"""Pasada r15b (2026-10-08): datos perdidos y falsos éxitos, la parte de la mente.

v3-61 «decime cuándo fue el último examen de virus»: la ventana escribía «Último examen: 08-10-2026 10:28 (examen
rápido)», el borrador que lo decía («Llegué al último examen de virus de 08-10-2026 10:28…») murió como extra_claim, no
quedó presupuesto para otro y el suelo de la mente («Llegué a…, pero no pude leer en la pantalla la respuesta…») murió en
su propio veto (ungrounded_word: «leer»): sin final de la mente, el App dijo «Lo hice en la aplicación «Seguridad de
Windows»». v3-43 «dime qué plan de energía está activo»: la lectura final vio la página «Cargando»; el borrador inventó
«Equilibrado» (vetado con razón: no estaba en ningún dato), el honrado «No pude ver… no mostraba ese dato» murió como
ungrounded_word («mostraba») y el turno cayó en el mismo «Lo hice…». t-drag-4: un único clic que eligió la herramienta
y el «done» del modelo dieron por dibujada una línea. Las situaciones son las de compose_audit.jsonl, recortadas.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from baxy_mind import cu_validate
from baxy_mind import cu_projection
from baxy_mind import cu_reply_checks
from baxy_mind import cu_finals
from baxy_mind import deterministic_finals
from baxy_mind import visible_defect
from baxy_mind.semantic.normalize import _accent_folded_with_punctuation

LAST_SCAN = {
    "kind": "operation", "operation": "mission.computer.use", "polarity": "success", "verified": True,
    "succeeded": True,
    "observed": {
        "goal": "abrir Seguridad de Windows; y responder: decime cuándo fue el último examen de virus",
        "application": "Seguridad de Windows", "reached": True,
        "successCheck": "title:Seguridad de Windows|process:Seguridad de Windows", "stepCount": 1,
        "steps": [{"step": 1, "operation": "input.visible.click", "source": "model",
                   "label": "Protección contra virus y amenazas", "index": 6, "ok": True, "cascadeStage": "uia",
                   "method": "select", "surfaceChanged": False, "absentOrDisabled": False, "selected": True,
                   "toggled": False, "name": "Protección contra virus y amenazas", "kind": "ListItem", "changed": True,
                   "broughtNew": True}],
        "window": {"title": "Seguridad de Windows", "process": "SecHealthUI", "requested": True, "foreground": False,
                   "focused": {"kind": "Button", "name": "Examen rápido", "nameSource": "", "i": 16}},
        "joined": False, "authority": "shell_loop_over_uia_ocr_postread", "procedure": "learned",
        "satisfiedBy": "title:Seguridad de Windows",
        "screen": {"title": "Seguridad de Windows",
                   "values": [{"name": "Seguridad de Windows", "value": "Seguridad de Windows"},
                              {"name": "Protección contra virus y amenazas", "state": "selected"}],
                   "numbers": ["Último examen: 08-10-2026 10:28 (examen rápido)", "Se encontraron 0 amenazas.",
                               "El examen duró 10 minutos 6 segundos", "45485 archivos examinados."]},
    },
}
SCAN_SAID = "en Seguridad de Windows, decime cuándo fue el último examen de virus"

POWER_PLAN = {
    "kind": "operation", "operation": "mission.computer.use", "polarity": "success", "verified": True,
    "succeeded": True,
    "observed": {
        "goal": "hacer clic en opciones de energia; y responder: dime qué plan de energía está activo",
        "application": "Panel de control", "reached": True,
        "successCheck": "stepDone:input.visible.click:opciones de energia", "stepCount": 2,
        "steps": [
            {"step": 1, "operation": "app.open", "source": "procedure", "appId": "Panel de control", "ok": True,
             "alreadyRunning": False, "windowsActivation": True, "frontRestored": True, "changed": True},
            {"step": 2, "operation": "input.visible.click", "source": "model", "label": "Opciones de energía",
             "index": 32, "ok": True, "cascadeStage": "uia_surface", "method": "invoke", "surfaceChanged": True,
             "absentOrDisabled": False, "selected": False, "toggled": False, "name": "Opciones de energía",
             "kind": "Hyperlink", "changed": True},
        ],
        "window": {"title": "Sistema y seguridad", "process": "explorer", "requested": True, "foreground": True},
        "joined": False, "authority": "shell_loop_over_uia_ocr_postread", "procedure": "relearned",
        "satisfiedBy": "stepDone:input.visible.click:opciones de energia",
        "screen": {"title": "Opciones de energía", "values": [{"name": "Cargando", "value": "0"}],
                   "numbers": ["Actualizar \"Opciones de energía\" (F5)"]},
    },
}
PLAN_SAID = "dime qué plan de energía está activo"


def _defect(text: str, situation: dict, said: str) -> str:
    return visible_defect.compose_visible_defect(text, "status", said, {"situation": json.dumps(situation, ensure_ascii=False)})


def _floor(situation: dict, said: str, language: str = "es") -> str:
    return deterministic_finals._deterministic_final(situation, {}, said, language)


def test_v3_61_the_value_the_window_wrote_is_the_final_told_before_any_draft() -> None:
    told = cu_finals.floor_first(LAST_SCAN["observed"], False, True)
    assert told == "La ventana dice «Último examen: 08-10-2026 10:28 (examen rápido)»."
    assert cu_finals.floor_first(LAST_SCAN["observed"], True, True) == (
        "The window says «Último examen: 08-10-2026 10:28 (examen rápido)»."
    )
    assert _floor(LAST_SCAN, SCAN_SAID) == told
    assert _defect(told, LAST_SCAN, SCAN_SAID) == ""


def test_v3_61_a_draft_with_the_value_passes_and_one_without_it_is_still_vetoed() -> None:
    assert _defect("El último examen fue el 08-10-2026 10:28.", LAST_SCAN, SCAN_SAID) == ""
    # A date the window did not write is no answer.
    assert _defect("El último examen fue el 07-10-2026 10:28.", LAST_SCAN, SCAN_SAID) != ""
    assert _defect("Lo hice en la aplicación Seguridad de Windows.", LAST_SCAN, SCAN_SAID) != ""


def test_a_labelled_line_answers_only_when_it_is_the_one_its_question_names() -> None:
    seen = cu_projection.project_seen(LAST_SCAN["observed"], "es")
    two = json.loads(json.dumps(seen))
    two["screen"]["numbers"].append("Último examen: 01-10-2026 09:00 (examen completo)")
    assert cu_finals.question_answer(two, False) == ""
    other = json.loads(json.dumps(seen))
    other["question"] = "decime cuántas amenazas hay en cuarentena"
    assert cu_finals.question_answer(other, False) == ""


def test_v3_43_the_value_not_on_screen_is_an_honest_limit_the_composer_can_publish() -> None:
    told = _floor(POWER_PLAN, PLAN_SAID)
    assert told == (
        "Llegué a «Panel de control», pero no pude leer en la pantalla la respuesta a «dime qué plan de energía está "
        "activo»."
    )
    assert _defect(told, POWER_PLAN, PLAN_SAID) == ""
    assert cu_reply_checks.ungrounded_word(
        _accent_folded_with_punctuation(_floor(POWER_PLAN, PLAN_SAID, "en")),
        cu_projection.project_seen(POWER_PLAN["observed"], "es"), PLAN_SAID,
    ) is None
    assert _defect(
        "No pude ver qué plan de energía está activo porque la ventana no mostraba ese dato.", POWER_PLAN, PLAN_SAID
    ) == ""
    # «Equilibrado» was in no fact of the turn: the guess stays vetoed.
    assert _defect("El plan activo es Equilibrado.", POWER_PLAN, PLAN_SAID) != ""
    assert _defect("Llegué al plan de energía «Equilibrado» en el Panel de control.", POWER_PLAN, PLAN_SAID) != ""


def _paint_view() -> dict:
    return {
        "window": {"title": "Sin título - Paint", "process": "mspaint"},
        "controls": [{"i": 21, "kind": "Button", "name": "Pinceles", "state": "on"},
                     {"i": 40, "kind": "Pane", "name": "Lienzo"}],
    }


def _done(goal: str, history: list[dict], evidence: str = "Pinceles") -> dict:
    raw = {"act": "done", "evidence": evidence}
    return cu_validate._checked_act(
        raw, view=_paint_view(), last_failed=None, application_names=(), history=history, goal=goal)


BRUSH = {"operation": "input.visible.click", "ok": True, "changed": True, "label": "Pinceles"}


def test_t_drag_4_a_drawing_is_a_declared_limit_and_choosing_the_tool_is_done_by_its_click() -> None:
    # Estabilización L: drawing is the drag limit (known_unsupported_effect_request); the mission stops before it, so no click ever stands for a drawing.
    from baxy_mind.semantic.drag import asks_to_drag

    assert asks_to_drag("en paint dibujar una linea horizontal con pinceles")
    chosen = _done("seleccionar pinceles", [BRUSH])
    assert "arrastre" not in json.dumps(chosen, ensure_ascii=False)
