"""Ronda 21 — el recibo no es la llegada y el final de una misión fallida pasa por los vetos (pasada r18).

t-menu-2: «No pude abrir el menú contextual porque no vi el control en la pantalla, pero llegué a la carpeta M.2 ADATA
(D:) y seleccioné la vista de detalles.» se publicó aunque mission_defect daba extra_claim: la misión fallida llega
envuelta ({kind: failure, reason: {operation: mission.computer.use}}) y los vetos sólo corrían con kind operation; y
el acto «menu» fallido se narraba «abrió el menú de …» también en stepsFailed.
v3-64: «…no hay ningún elemento en pantalla etiquetado como "tipo de inicio"» para un clic que buscó «Ordenar por tipo
de inicio» (visible_button_not_found): lo citado como ausente es sólo attempted.label.
Contracasos de cada regla al lado.
"""

from __future__ import annotations

import json

import pytest

from baxy_mind import operation_floor
from baxy_mind import cu_projection
from baxy_mind import cu_reply_checks
from baxy_mind import compose_situation
from baxy_mind import visible_defect
from baxy_mind import clock_facts
from baxy_mind import deterministic_finals
from baxy_mind.semantic.normalize import _accent_folded_with_punctuation


# The facts of the last t-menu-2 run (cu-universal-evidencia/v2-t-menu-2/compose_audit.jsonl, the published final's).
def _t_menu_2_observed(*, first_ok: bool = True) -> dict:
    return {
        "goal": "ir a baxy-prueba-v3; luego abrir el menu contextual de espacio vacio; luego hacer clic en ordenar "
                "por; luego ordená los archivos por tamaño",
        "application": "Explorador de archivos",
        "reached": False,
        "stepCount": 2,
        "steps": [
            {"step": 1, "operation": "input.visible.click", "source": "model", "subgoal": 1, "label": "M.2 ADATA (D:)",
             "index": 22, "manner": "menu", "ok": first_ok, "method": "contextmenu", "selected": first_ok,
             "surfaceChanged": False, "changed": first_ok, "kind": "TreeItem", "appeared": []},
            {"step": 2, "operation": "input.visible.click", "source": "model", "subgoal": 1, "label": "M.2 ADATA (D:)",
             "index": 22, "manner": "menu", "ok": False, "error": "no_progress"},
        ],
        "window": {"title": "baxy-prueba-v3 - Explorador de archivos", "process": "explorer"},
        "joined": False,
        "subgoals": [
            {"goal": "ir a baxy-prueba-v3", "application": "Explorador de archivos", "reached": True},
            {"goal": "abrir el menu contextual de espacio vacio", "application": "Explorador de archivos",
             "reached": False},
            {"goal": "hacer clic en ordenar por", "application": "Explorador de archivos", "reached": False},
            {"goal": "ordená los archivos por tamaño", "application": "Explorador de archivos", "reached": False},
        ],
        "screen": {
            "title": "baxy-prueba-v3 - Explorador de archivos",
            "values": [{"name": "baxy-prueba-v3", "value": "baxy-prueba-v3"},
                       {"name": "baxy-prueba-v3", "state": "selected"}, {"name": "Detalles", "state": "selected"}],
            "numbers": ["baxy-prueba-v3", "M.2 Samsung (C:)", "M.2 ADATA (D:)"],
            "lines": ["Ver", "Fecha de modificación", "Tipo", "Tamaño"],
        },
        "stoppedBy": "computer_use_no_step_visible",
    }


def _failed(observed: dict) -> dict:
    """The situation the App sends for a mission that failed (kind failure, cause mission_failed)."""

    return {
        "kind": "failure", "polarity": "failure", "cause": "mission_failed", "stepCount": 0, "steps": [],
        "reason": {"kind": "operation", "operation": "mission.computer.use", "polarity": "failure",
                   "verified": False, "succeeded": False, "error": observed["stoppedBy"], "observed": observed},
    }


def _facts(situation: dict) -> dict:
    return {"situation": json.dumps(situation, ensure_ascii=False)}


T_MENU_2_ASKED = "en el explorador, en baxy-prueba-v3, abrí el menú contextual en un espacio vacío y ordená por tamaño"
T_MENU_2_PUBLISHED = (
    "No pude abrir el menú contextual porque no vi el control en la pantalla, pero llegué a la carpeta M.2 ADATA (D:) "
    "y seleccioné la vista de detalles."
)


# ----------------------------------------------------------------------- (d) the vetoes judge a failed mission's final
@pytest.mark.parametrize("first_ok", [True, False])
def test_t_menu_2_a_failed_missions_final_that_arrives_off_mission_is_vetoed(first_ok):
    situation = _failed(_t_menu_2_observed(first_ok=first_ok))
    assert compose_situation._computer_use_mission(situation) is situation["reason"]
    assert visible_defect.compose_visible_defect(T_MENU_2_PUBLISHED, "error", T_MENU_2_ASKED, _facts(situation)) != ""


def test_t_menu_2_the_mission_veto_is_what_says_it():
    seen = cu_projection.project_seen(_t_menu_2_observed(), "es")
    assert cu_reply_checks.mission_defect(_accent_folded_with_punctuation(T_MENU_2_PUBLISHED), seen) == "extra_claim"


@pytest.mark.parametrize("draft", [
    "No pude abrir el menú contextual del espacio vacío: no vi en la pantalla un control con el que seguir.",
    "Llegué a baxy-prueba-v3, pero no pude abrir el menú contextual: no vi en la pantalla un control con el que "
    "seguir.",
])
def test_contracase_a_failed_missions_final_that_only_says_the_cause_passes(draft):
    situation = _failed(_t_menu_2_observed(first_ok=False))
    assert visible_defect.compose_visible_defect(draft, "error", T_MENU_2_ASKED, _facts(situation)) == ""


def test_contracase_a_reached_missions_final_is_judged_as_before():
    observed = _t_menu_2_observed()
    observed.update(reached=True, stoppedBy=None)
    observed["subgoals"] = [observed["subgoals"][0]]
    observed["goal"] = "ir a baxy-prueba-v3"
    observed["steps"] = [{"step": 1, "operation": "input.visible.click", "label": "baxy-prueba-v3", "ok": True,
                          "kind": "TreeItem", "surfaceChanged": True, "changed": True}]
    situation = {"kind": "operation", "operation": "mission.computer.use", "polarity": "success", "verified": True,
                 "succeeded": True, "observed": observed}
    assert visible_defect.compose_visible_defect("Llegué a baxy-prueba-v3.", "status", "andá a baxy-prueba-v3",
                                      _facts(situation)) == ""


# --------------------------------------------------------------------- (e) a step that failed is told as an attempt
def test_t_menu_2_a_failed_menu_act_is_told_as_tried_never_as_opened():
    seen = cu_projection.project_seen(_t_menu_2_observed(first_ok=False), "es")
    assert seen["stepsFailed"] == ["intentó abrir el menú de «M.2 ADATA (D:)»"] * 2
    assert "stepsDone" in seen and seen["stepsDone"] == []
    english = cu_projection.project_seen(_t_menu_2_observed(first_ok=False), "en")
    assert english["stepsFailed"][0] == "tried to open the menu of «M.2 ADATA (D:)»"


@pytest.mark.parametrize("manner, done, tried", [
    (None, "clic en «Biblioteca»", "intentó hacer clic en «Biblioteca»"),
    ("open", "abrió «Biblioteca»", "intentó abrir «Biblioteca»"),
    ("double", "doble clic en «Biblioteca»", "intentó hacer doble clic en «Biblioteca»"),
])
def test_contracase_a_step_done_keeps_its_verb_of_doing(manner, done, tried):
    step = {"operation": "input.visible.click", "label": "Biblioteca", "ok": True}
    if manner:
        step["manner"] = manner
    assert cu_projection.describe_step(step, "es") == done
    assert cu_projection.describe_step({**step, "ok": False}, "es") == tried


def test_the_step_words_are_data():
    words = operation_floor.floor_data()["computerUse"]["stepWords"]
    assert set(words) >= {"es", "en", "esTried", "enTried"}
    for language in ("es", "en", "esTried", "enTried"):
        assert set(words[language]) == {"open", "menu", "double", "click"}
        assert all("{label}" in phrase for phrase in words[language].values())


# ------------------------------------------------------------- (f) a not-found click quotes only what it looked for
def _not_found(label: str, error: str = "visible_button_not_found") -> dict:
    # The situation of v3-64's final (cu-universal-evidencia/v2-v3-64/compose_audit.jsonl).
    return {"kind": "failure", "polarity": "failure", "cause": "mission_failed", "stepCount": 0, "steps": [],
            "reason": {"kind": "operation", "operation": "input.visible.click", "polarity": "failure",
                       "verified": False, "succeeded": False, "error": error, "attempted": {"label": label}}}


V3_64_ASKED = "en servicios ordena por tipo de inicio"
V3_64_PUBLISHED = (
    'No se pudo ordenar la lista porque no hay ningún elemento en pantalla etiquetado como "tipo de inicio" para '
    "hacer clic."
)


@pytest.mark.parametrize("error", ["visible_button_not_found", "visible_control_label_mismatch"])
def test_v3_64_a_piece_of_the_label_quoted_as_absent_is_vetoed(error):
    situation = _not_found("Ordenar por tipo de inicio", error)
    assert visible_defect.compose_visible_defect(V3_64_PUBLISHED, "error", V3_64_ASKED, _facts(situation)) == (
        "absent_label_misquoted"
    )


def test_v3_64_the_last_resort_is_the_data_template_with_the_label():
    situation = _not_found("Ordenar por tipo de inicio")
    final = deterministic_finals._deterministic_final(situation, {}, V3_64_ASKED, "es")
    assert final == "No encontré «Ordenar por tipo de inicio»; no pulsé nada."
    assert visible_defect.compose_visible_defect(final, "error", V3_64_ASKED, _facts(situation)) == ""
    assert deterministic_finals._deterministic_final(situation, {}, V3_64_ASKED, "en") == (
        "I did not find «Ordenar por tipo de inicio»; I pressed nothing."
    )


@pytest.mark.parametrize("draft", [
    "No encontré «Guardar como» en la pantalla, así que no pulsé nada.",
    'No encontré "guardar como"; no pulsé nada.',
    "No encontré ese botón en la pantalla, así que no pulsé nada.",
])
def test_contracase_the_label_looked_for_or_no_quote_passes(draft):
    situation = _not_found("Guardar como")
    assert visible_defect.compose_visible_defect(draft, "error", "en el bloc de notas hacé clic en Guardar como",
                                      _facts(situation)) == ""


def test_contracase_a_click_that_failed_for_another_cause_is_not_judged_by_its_label():
    situation = _not_found("Guardar como", "window_elevated")
    assert deterministic_finals._absent_label_misquoted("No pude pulsar «Guardar»: la ventana es de administrador.", situation) is False
    assert deterministic_finals._absent_label_final(situation, "es") == ""


# Revisión 3: with earlier steps made, «no pulsé nada» is false; the M107 floor tells each step and the names those
# steps carry are quotes the not-found veto allows.
def _not_found_after(step: dict, label: str = "Guardar como") -> dict:
    situation = _not_found(label)
    situation["stepCount"] = 1
    situation["steps"] = [json.dumps(step, ensure_ascii=False)]
    situation["reason"] = json.dumps(situation["reason"], ensure_ascii=False)
    return situation


_CLICK_DONE = {"kind": "operation", "operation": "input.visible.click", "polarity": "success", "verified": True,
               "succeeded": True, "attempted": {"label": "Archivo"},
               "observed": {"label": "Archivo", "surfaceChanged": True}}
_APP_OPENED = {"kind": "operation", "operation": "app.open", "polarity": "success", "verified": True,
               "succeeded": True, "attempted": {"appId": "Bloc de notas"},
               "observed": {"appId": "Bloc de notas", "displayName": "Bloc de notas", "alreadyRunning": False}}


@pytest.mark.parametrize(("step", "asked"), [
    (_CLICK_DONE, "en el bloc de notas hacé clic en Archivo y después en Guardar como"),
    (_APP_OPENED, "abrí el bloc de notas y hacé clic en guardar como"),
])
def test_contracase_a_not_found_click_after_steps_made_keeps_the_floor_by_steps(step, asked):
    situation = _not_found_after(step)
    final = deterministic_finals._deterministic_final(situation, {}, asked, "es")
    assert "no pulsé nada" not in final
    assert final == operation_floor.with_family_cause(
        operation_floor.floor_final(situation, False, clock_facts._local_now()), situation, False,
    )
    assert deterministic_finals._absent_label_final(situation, "es") == ""


def test_contracase_the_opened_app_is_told_beside_the_label_not_found():
    situation = _not_found_after(_APP_OPENED)
    asked = "abrí el bloc de notas y hacé clic en guardar como"
    final = deterministic_finals._deterministic_final(situation, {}, asked, "es")
    assert "«Bloc de notas»" in final
    assert visible_defect.compose_visible_defect(final, "error", asked, _facts(situation)) == ""
    draft = "Abrí «Bloc de notas», pero no encontré «Guardar como»."
    assert visible_defect.compose_visible_defect(draft, "error", asked, _facts(situation)) == ""


def test_the_name_of_a_step_made_is_an_allowed_quote_and_a_piece_of_the_label_is_not():
    situation = _not_found_after(_CLICK_DONE)
    assert deterministic_finals._absent_label_misquoted("Pulsé «Archivo», pero no encontré «Guardar como».", situation) is False
    assert deterministic_finals._absent_label_misquoted("Pulsé «Archivo», pero no encontré «Guardar».", situation) is True
