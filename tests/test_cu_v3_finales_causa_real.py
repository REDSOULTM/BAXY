"""Ronda 20 P5 — Honestidad: el final dice la causa real y nunca narra lo no alcanzado (pasada r18).

v3-16: «Llegué al editor de la imagen pero no pude poner el filtro blanco y negro porque la pantalla se quedó
bloqueada.» con subgoals[0].reached=false y coveredBy=«Steam» entre los hechos de una parada sin paso visible.
v3-27: «No pude abrir el mapa de caracteres en este equipo» por un 4xx de la gramática del servidor local
(text.maxLength=65 536 escrito como `char{0,65536}`). v3-28 y v3-29: «no vi un control» cuando la lista se abrió y se
cerró, o la búsqueda no encontró nada. Contracasos de cada regla al lado.
"""

from __future__ import annotations

import copy
import json
import re

import pytest

from baxy_mind import llm, operation_floor
from baxy_mind import cu_vocabulary
from baxy_mind import cu_projection
from baxy_mind import computer_use_finals
from baxy_mind import compose_situation
from baxy_mind import llm_grammar
from baxy_mind.planner import validate_json_schema_instance
from baxy_mind.semantic import claims


# The facts of the last v3-16 run (cu-universal-evidencia/v2-v3-16/compose_audit.jsonl, the published final's).
def _v3_16_observed(*, first_reached: bool = False, stopped_by: str = "computer_use_no_step_visible") -> dict:
    return {
        "goal": "ir a editor de la imagen que tengo abierta; luego ponele un filtro blanco y negro, sin guardar",
        "application": "Fotos",
        "reached": False,
        "stepCount": 2,
        "steps": [
            {"step": 1, "operation": "app.open", "source": "model", "subgoal": 0, "appId": "Fotos", "ok": True,
             "alreadyRunning": True, "changed": True},
            {"step": 2, "operation": "input.visible.click", "source": "model", "subgoal": 0, "label": "Editar",
             "index": 13, "ok": True, "cascadeStage": "uia", "method": "invoke", "surfaceChanged": False,
             "absentOrDisabled": True, "selected": False, "toggled": False, "name": "Editar", "kind": "Button",
             "changed": True, "broughtNew": True, "appeared": ["atras"]},
        ],
        "window": {"title": "paisaje.jpg", "process": "Photos", "requested": True, "root": 10620132,
                   "foreground": False, "rect": {"x": 168, "y": 160, "w": 1424, "h": 732},
                   "coveredBy": {"title": "Steam", "process": "steamwebhelper"}},
        "joined": False,
        "authority": "shell_loop_over_uia_ocr_postread",
        "subgoals": [
            {"goal": "ir a editor de la imagen que tengo abierta", "application": "Fotos", "reached": first_reached,
             "stepCount": 2},
            {"goal": "ponele un filtro blanco y negro, sin guardar", "application": "Fotos", "reached": False,
             "stepCount": 0},
        ],
        "screen": {"title": "paisaje.jpg", "numbers": ["16:9", "9"],
                   "lines": ["16:9", "paisaJe.Jpg", "Restablecer", "9", "Opciones para guardar v'"]},
        "stoppedBy": stopped_by,
    }


def _failed(observed: dict) -> dict:
    """The situation the App sends for a mission that failed (kind failure, cause mission_failed)."""

    return {
        "kind": "failure", "polarity": "failure", "cause": "mission_failed", "stepCount": 0, "steps": [],
        "reason": {"kind": "operation", "operation": "mission.computer.use", "polarity": "failure",
                   "verified": False, "succeeded": False, "error": observed["stoppedBy"], "observed": observed},
    }


V3_16_PUBLISHED = (
    "Llegué al editor de la imagen pero no pude poner el filtro blanco y negro porque la pantalla se quedó "
    "bloqueada. Solo logré abrir la aplicación y hacer clic en editar."
)
V3_16_FIRST_DRAFT = (
    "Llegué al editor de la imagen pero no pude poner el filtro blanco y negro porque no vi el control en pantalla. "
    "Solo logré traer la aplicación al frente y hacer clic en «Editar»."
)


# ------------------------------------------------------------------------------------------------- (a) coveredBy
def test_v3_16_covered_by_is_no_fact_for_the_writer_on_another_stop():
    seen = cu_projection.project_seen(_v3_16_observed(), "es")
    assert "coveredBy" not in seen
    assert seen["stoppedBecause"] == "no vi en la pantalla un control con el que seguir"


def test_contracase_a_covered_window_still_names_what_covers_the_app():
    seen = cu_projection.project_seen(_v3_16_observed(stopped_by="computer_use_window_covered"), "es")
    assert seen["coveredBy"] == "Steam"
    assert "Steam" in seen["stoppedBecause"]


# ------------------------------------------------------------------------------- (b) unreached part, invented cause
@pytest.mark.parametrize("draft", [V3_16_PUBLISHED, V3_16_FIRST_DRAFT])
def test_v3_16_a_part_not_reached_told_as_done_is_vetoed(draft):
    assert computer_use_finals._computer_use_final_defect(draft, _failed(_v3_16_observed())) == "unreached_claim"


def test_v3_16_an_invented_cause_is_vetoed_even_without_a_part_told():
    draft = "No pude poner el filtro blanco y negro porque la pantalla se quedó bloqueada."
    assert computer_use_finals._computer_use_final_defect(draft, _failed(_v3_16_observed())) == "invented_cause"
    english = "I couldn't apply the black and white filter because the screen froze."
    assert computer_use_finals._computer_use_final_defect(english, _failed(_v3_16_observed())) == "invented_cause"


@pytest.mark.parametrize("draft", [
    "No pude llegar al editor de la imagen: no vi en la pantalla un control con el que seguir.",
    "No pude poner el filtro porque no vi en la pantalla un control con el que seguir; sólo hice clic en «Editar».",
    "I couldn't get to the image editor because I did not see on the screen a control to go on with.",
])
def test_contracase_the_observed_cause_and_no_claim_pass(draft):
    assert computer_use_finals._computer_use_final_defect(draft, _failed(_v3_16_observed())) == ""


def test_contracase_a_reached_part_may_be_told_and_then_what_was_missing():
    draft = (
        "Llegué al editor de la imagen, pero no pude poner el filtro blanco y negro porque no vi en la pantalla un "
        "control con el que seguir."
    )
    assert computer_use_finals._computer_use_final_defect(draft, _failed(_v3_16_observed(first_reached=True))) == ""


def test_contracase_a_verified_step_on_the_parts_object_backs_the_clause():
    observed = _v3_16_observed()
    observed["steps"][1]["label"] = observed["steps"][1]["name"] = "Editor"
    assert claims.claims_unreached_part("Abrí el editor.", "ir a editor de la imagen", ["Editor"]) == ""
    assert computer_use_finals._computer_use_final_defect("Abrí el editor de la imagen, pero no pude poner el filtro.",
                                          _failed(observed)) == ""


def test_contracase_the_covered_window_cause_passes_when_it_is_the_stop():
    observed = _v3_16_observed(stopped_by="computer_use_window_covered")
    draft = "No pude poner el filtro porque la ventana «Steam» tapa la aplicación."
    assert computer_use_finals._computer_use_final_defect(draft, _failed(observed)) == ""


def test_the_readers_deny_and_question_nothing():
    goal = "ir a editor de la imagen que tengo abierta"
    assert claims.claims_unreached_part("No llegué al editor de la imagen.", goal) == ""
    assert claims.claims_unreached_part("¿Llegué al editor?", goal) == ""
    assert claims.claims_unreached_part("I got to the image editor.", "go to the image editor")


# Revisión 1, hallazgo 1: the object of a purpose or of an attempt is no act told.
@pytest.mark.parametrize("draft", [
    "Hice clic en «Editar» para llegar al editor de la imagen, pero no se abrió; no vi en la pantalla un control con el "
    "que seguir.",
    "Intenté entrar al editor de la imagen, pero no vi en la pantalla un control con el que seguir.",
    "I tried to open the image editor, but I did not see on the screen a control to go on with.",
    "I clicked «Editar» to open the image editor, but I did not see on the screen a control to go on with.",
])
def test_review1_a_purpose_or_an_attempt_over_a_part_not_reached_passes(draft):
    assert computer_use_finals._computer_use_final_defect(draft, _failed(_v3_16_observed())) == ""


def _dark_theme_observed() -> dict:
    return {
        "goal": "pon el tema oscuro", "application": "Configuración", "reached": False,
        "steps": [
            {"step": 1, "operation": "input.visible.click", "label": "Personalización", "name": "Personalización",
             "ok": True},
            {"step": 2, "operation": "input.visible.click", "label": "Colores", "name": "Colores", "ok": True},
        ],
        "subgoals": [{"goal": "pon el tema oscuro", "application": "Configuración", "reached": False}],
        "stoppedBy": "computer_use_no_step_visible",
    }


def test_review1_contracase_in_another_app_a_purpose_passes_and_a_told_act_is_still_vetoed():
    observed = _dark_theme_observed()
    honest = "Entré en Colores para poner el tema oscuro, pero no vi en la pantalla un control con el que seguir."
    assert computer_use_finals._computer_use_final_defect(honest, _failed(observed)) == ""
    told = "Entré en Colores y puse el tema oscuro."
    assert computer_use_finals._computer_use_final_defect(told, _failed(observed)) == "unreached_claim"


@pytest.mark.parametrize("draft", [
    "Llegué al editor de la imagen e intenté poner el filtro.",
    "Entré al editor de la imagen para poner el filtro.",
    "I went to the image editor to apply the filter.",
])
def test_review1_contracase_an_act_told_before_a_purpose_or_an_attempt_is_still_vetoed(draft):
    assert computer_use_finals._computer_use_final_defect(draft, _failed(_v3_16_observed())) == "unreached_claim"


# Revisión 1, hallazgo 2: a light rewording of the observed cause is no invented cause.
@pytest.mark.parametrize("draft", [
    "No pude poner el filtro porque no vi ningún control para continuar.",
    "No pude llegar al editor porque no apareció ningún control con el que seguir.",
    "No pude poner el filtro porque no encontré el botón para seguir.",
    "I couldn't apply the filter because I didn't find a control to continue.",
])
def test_review1_a_reworded_observed_cause_passes(draft):
    assert computer_use_finals._computer_use_final_defect(draft, _failed(_v3_16_observed())) == ""


@pytest.mark.parametrize("draft", [
    "No pude poner el filtro porque la aplicación dejó de responder.",
    "No pude poner el filtro porque me faltaron permisos de administrador.",
    "I couldn't apply the filter because the connection dropped.",
])
def test_review1_contracase_a_cause_of_a_kind_no_fact_says_is_still_vetoed(draft):
    assert computer_use_finals._computer_use_final_defect(draft, _failed(_v3_16_observed())) == "invented_cause"


# Revisión 2, bloqueante 1: drafts of cu-universal-evidencia/*/compose_audit.jsonl vetoed as unreached_claim although
# honest. Facts reduced to what the readers use.
def _mission(goals: list[str], steps: list[dict], *, reached: list[bool] | None = None,
             stopped_by: str = "computer_use_no_step_visible", application: str = "App") -> dict:
    marks = reached or [False] * len(goals)
    return {
        "goal": "; luego ".join(goals), "application": application, "reached": False, "stepCount": len(steps),
        "steps": steps,
        "window": {"title": application, "process": "app", "requested": True},
        "subgoals": [{"goal": goal, "application": application, "reached": mark} for goal, mark in zip(goals, marks)],
        "stoppedBy": stopped_by,
    }


def _click(label: str, step: int = 1) -> dict:
    return {"step": step, "operation": "input.visible.click", "label": label, "name": label, "ok": True,
            "changed": True}


# (i) a denied act over the object, with a first person past only in the cause.
def test_review2_v3_02_a_denied_act_with_a_verb_in_the_cause_passes():
    observed = _mission(
        ["hacer clic en transiciones", "aplica la transición Desvanecer a la diapositiva actual"],
        [{"step": 1, "operation": "input.key.press", "key": "ctrl_k", "ok": True, "changed": True}],
        stopped_by="computer_use_surface_unchanged",
    )
    draft = "No pude hacer clic en la pestaña Transiciones porque la pantalla dejó de cambiar tras lo que hice."
    assert computer_use_finals._computer_use_final_defect(draft, _failed(observed)) == ""


@pytest.mark.parametrize("draft", [
    "No pude llegar a la tienda de Steam porque empezaste a usar el PC y paré a mitad para no estorbarte, pero sí "
    "llegué al canal de voz de Cotele en Discord.",
    "Llegué al canal de Cotele en Discord, pero no pude entrar a la tienda de Steam porque me detuve a mitad de camino "
    "para no estorbarte mientras empezabas a usar el PC.",
])
def test_review2_v2_c7_the_cause_is_its_own_clause(draft):
    observed = _mission(["ir a cotele", "ir a tienda"], [_click("Cotele!!!😎 / Choche")], reached=[True, False],
                        stopped_by="input_user_interrupted")
    assert computer_use_finals._computer_use_final_defect(draft, _failed(observed)) == ""


@pytest.mark.parametrize("draft", [
    "Abrí la tienda y no pude seguir porque empezaste a usar el PC.",
    "No pude seguir porque llegué a la tienda y empezaste a usar el PC.",
])
def test_review2_contracase_an_act_over_the_object_is_still_vetoed_in_any_clause(draft):
    observed = _mission(["ir a cotele", "ir a tienda"], [_click("Cotele")], reached=[True, False],
                        stopped_by="input_user_interrupted")
    assert computer_use_finals._computer_use_final_defect(draft, _failed(observed)) == "unreached_claim"
    english = _mission(["go to cotele", "go to the store"], [_click("Cotele")], reached=[True, False],
                       stopped_by="input_user_interrupted")
    told = "I got to the store, but I stopped because you started using the PC."
    assert computer_use_finals._computer_use_final_defect(told, _failed(english)) == "unreached_claim"
    honest = "I couldn't get to the store because you started using the PC and I stopped."
    assert computer_use_finals._computer_use_final_defect(honest, _failed(english)) == ""


# (ii) the head of «hacer clic en…», «pulsar el botón…», «abrir la pestaña…» is the control's name.
@pytest.mark.parametrize(("goal", "head"), [
    ("hacer clic en reemplazar todo", "reemplazar"),
    ("pulsá el botón Aceptar", "aceptar"),
    ("abrí la pestaña Ver", "ver"),
    ("hacé doble clic en Imagen", "imagen"),
    ("click the Save button", "save"),
    ("abrí el menú", "menu"),
    ("ir a editor de la imagen", "editor"),
])
def test_review2_part_head_skips_the_verbs_complement_and_the_controls_class(goal, head):
    assert claims.part_head(goal) == head


@pytest.mark.parametrize(("goals", "label", "draft"), [
    (["abrir el dialogo de reemplazar", "poner buscar en casa", "poner reemplazar en hogar",
      "hacer clic en reemplazar todo"], "Editar",
     "No pude abrir el diálogo de reemplazar porque la ventana no se dejó leer; solo llegué a hacer clic en «Editar»."),
    (["abrir el dialogo de abrir", "hacer clic en abrir"], "Archivo",
     "Llegué al menú de Archivo pero no pude abrir el diálogo porque la ventana no se dejó leer. Solo logré hacer clic "
     "en «Archivo»."),
    (["hacé clic en Guardar"], "Archivo",
     "Hice clic en «Archivo», pero no vi en la pantalla un control con el que seguir."),
    (["pulsá el botón Aceptar"], "Opciones", "Pulsé el botón «Opciones», pero no vi el botón Aceptar."),
])
def test_review2_a_true_click_on_another_control_passes(goals, label, draft):
    observed = _mission(goals, [_click(label)], stopped_by="computer_use_view_unavailable")
    assert computer_use_finals._computer_use_final_defect(draft, _failed(observed)) == ""


@pytest.mark.parametrize(("goal", "draft"), [
    ("hacé clic en Guardar", "Hice clic en «Archivo» y después en «Guardar»."),
    ("pulsá el botón Aceptar", "Pulsé el botón Aceptar."),
    ("abrí la pestaña Ver", "Abrí la pestaña «Ver»."),
])
def test_review2_contracase_a_click_told_on_the_control_not_reached_is_still_vetoed(goal, draft):
    observed = _mission([goal], [_click("Archivo")], stopped_by="computer_use_view_unavailable")
    assert computer_use_finals._computer_use_final_defect(draft, _failed(observed)) == "unreached_claim"


# (iii) the text a typing step sent and the application an app.open opened back the object.
def test_review2_v3_30_the_typed_text_backs_the_object():
    observed = _mission(
        ["activar vista avanzada", "buscar flecha"],
        [_click("Ir a Unicode:"),
         {"step": 2, "operation": "input.text.type", "index": 5, "text": "flecha", "ok": False,
          "error": "input_effect_not_verified", "effectUncertain": True}],
        reached=[True, False],
    )
    draft = (
        "No logré encontrar la flecha en el mapa de caracteres porque no vi el control para seguir. Sí activé la vista "
        "avanzada y escribí «flecha» en el campo «Ir a Unicode:», que ahora muestra «flec»."
    )
    assert computer_use_finals._computer_use_final_defect(draft, _failed(observed)) == ""
    observed["steps"][1].update(ok=True, error=None, effectUncertain=False)
    assert computer_use_finals._computer_use_final_defect(draft, _failed(observed)) == ""


def test_review2_app_open_backs_the_object():
    observed = _mission(["ir a configuración de sonido"],
                        [{"step": 1, "operation": "app.open", "appId": "Configuración", "ok": True, "changed": True}])
    draft = "Abrí Configuración, pero no pude llegar al sonido."
    assert computer_use_finals._computer_use_final_defect(draft, _failed(observed)) == ""


def test_review2_contracase_text_no_step_sent_and_an_open_that_failed_back_nothing():
    typed = _mission(
        ["activar vista avanzada", "buscar flecha"],
        [{"step": 1, "operation": "input.text.type", "text": "flecha", "ok": False, "error": "input_focus_unproven"}],
        reached=[True, False],
    )
    assert computer_use_finals._computer_use_final_defect("Escribí flecha y busqué la flecha.", _failed(typed)) == "unreached_claim"
    opened = _mission(["ir a configuración de sonido"],
                      [{"step": 1, "operation": "app.open", "appId": "Configuración", "ok": False}])
    assert computer_use_finals._computer_use_final_defect("Abrí Configuración.", _failed(opened)) == "unreached_claim"


# Revisión 2, bloqueante 2: «bloquea» said of the observed cause is no locked screen.
def _elevated() -> dict:
    return _mission(["hacer clic en registros de windows", "hacer clic en sistema"], [],
                    stopped_by="computer_use_window_elevated", application="Visor de eventos")


def test_review2_v3_23_the_elevated_window_reworded_passes():
    draft = (
        "No pude hacer clic en Registros de Windows porque el Visor de eventos corre como administrador y bloquea el "
        "control."
    )
    assert computer_use_finals._computer_use_final_defect(draft, _failed(_elevated())) == ""
    assert computer_use_finals._computer_use_final_defect(
        "I couldn't click Windows Logs because Event Viewer runs as administrator and blocks control.",
        _failed(_elevated()),
    ) == ""


@pytest.mark.parametrize("draft", [
    "No pude hacer clic en Registros de Windows porque la pantalla se quedó bloqueada.",
    "No pude hacer clic en Registros de Windows porque la ventana estaba bloqueada por el teclado en pantalla.",
    "No pude hacer clic en Registros de Windows porque el Visor de eventos dejó de responder.",
])
def test_review2_contracase_a_locked_or_frozen_window_is_still_invented_on_an_elevated_stop(draft):
    assert computer_use_finals._computer_use_final_defect(draft, _failed(_elevated())) == "invented_cause"


# Revisión 3: the observed cause of the stop's own kind, reworded, and a cause that denies another kind.
# The facts of cu-universal-evidencia/v2-u8/compose_audit.jsonl (Configuración, the published final's situation).
def _v2_u8() -> dict:
    return {
        "goal": "ir a sistema; luego ir a pantalla", "application": "Configuración", "reached": False, "stepCount": 2,
        "steps": [
            {"step": 1, "operation": "app.open", "source": "procedure", "subgoal": 0, "appId": "Configuración",
             "ok": True, "alreadyRunning": False, "changed": True},
            {"step": 2, "operation": "input.visible.click", "source": "procedure", "subgoal": 0, "label": "Sistema",
             "ok": True, "cascadeStage": "ocr", "surfaceChanged": True, "absentOrDisabled": False, "selected": True,
             "name": "Sistema", "changed": True},
        ],
        "window": {"title": "Configuración", "process": "SystemSettings", "requested": True,
                   "rect": {"x": 58, "y": 0, "w": 1282, "h": 1002},
                   "focused": {"kind": "Edit", "name": "Cuadro de búsqueda, Buscar una opción", "value": ""}},
        "joined": False, "elapsedMs": 34477, "modelMs": 0, "authority": "shell_loop_over_uia_ocr_postread",
        "subgoals": [
            {"goal": "ir a sistema", "application": "Configuración", "reached": False, "stepCount": 2},
            {"goal": "ir a pantalla", "application": "Configuración", "reached": False, "stepCount": 0},
        ],
        "screen": {"title": "Configuración",
                   "values": [{"name": "Inicio", "state": "selected"}, {"name": "Bluetooth", "state": "on"},
                              {"name": "Configuración", "value": "Configuración"}],
                   "numbers": ["ASUS TUF Gaming A15 FA506QM_FA506QM"],
                   "lines": ["uscar una opción de configuración", "REDNOTE", "Cambiar nombre",
                             "Configuración recomendada"]},
        "stoppedBy": "computer_use_time_exhausted",
    }


# cu-universal-evidencia/v2-v3-39/compose_audit.jsonl (Terminal, stopped on computer_use_surface_unchanged).
def _v2_v3_39() -> dict:
    return {
        "goal": "ir a settings; y responder: tell me which profile is the default", "application": "Terminal",
        "reached": False, "stepCount": 3,
        "steps": [
            {"step": 1, "operation": "app.open", "source": "model", "appId": "Terminal", "ok": True,
             "alreadyRunning": False, "changed": True},
            {"step": 2, "operation": "input.key.press", "source": "model", "key": "ctrl_k", "ok": True,
             "method": "keyboard", "changed": True},
            {"step": 3, "operation": "input.key.press", "source": "model", "key": "escape", "ok": True,
             "method": "keyboard", "changed": True},
        ],
        "window": {"title": "Windows PowerShell", "process": "WindowsTerminal", "requested": True, "foreground": False,
                   "rect": {"x": 191, "y": 192, "w": 1483, "h": 762}},
        "joined": False, "authority": "shell_loop_over_uia_ocr_postread",
        "screen": {"title": "Windows PowerShell",
                   "values": [{"name": "Windows PowerShell", "state": "selected"}, {"name": "Vertical", "value": "0"}],
                   "numbers": ["A11 rights reserved ."],
                   "lines": ["All rights reserved.", "Windows PowerShell", "Copyright (C) Microsoft Corporation."]},
        "stoppedBy": "computer_use_surface_unchanged",
    }


@pytest.mark.parametrize("draft", [
    "No pude ir a Sistema porque tardó demasiado.",
    "No pude ir a Sistema porque se agotó el tiempo de espera.",
    "No pude ir a Sistema porque se agotó el tiempo previsto.",
    "Llegué a la aplicación de Configuración pero no pude ir al Sistema porque se agotó el tiempo.",
])
def test_review3_v2_u8_the_time_out_told_in_its_own_words_passes(draft):
    assert computer_use_finals._computer_use_final_defect(draft, _failed(_v2_u8())) == ""


@pytest.mark.parametrize("draft", [
    "I couldn't go to System because it took too long.",
    "I couldn't go to System because it timed out.",
])
def test_review3_the_time_out_in_english_passes(draft):
    observed = _mission(["go to system"], [], stopped_by="computer_use_time_exhausted", application="Settings")
    assert computer_use_finals._computer_use_final_defect(draft, _failed(observed)) == ""


def test_review3_v2_v3_39_and_a_failed_step_told_in_their_own_words_pass():
    draft = "I couldn't see the default profile because the screen didn't update after what I did."
    assert computer_use_finals._computer_use_final_defect(draft, _failed(_v2_v3_39())) == ""
    saved = _mission(
        ["guardar el documento"],
        [{"step": 1, "operation": "input.visible.click", "label": "Guardar", "ok": False,
          "error": "input_visible_click_failed"}],
        stopped_by="computer_use_step_failed",
    )
    assert computer_use_finals._computer_use_final_defect("No pude guardar porque el clic en Guardar dio error.", _failed(saved)) == ""


@pytest.mark.parametrize("draft", [
    "No pude ir a Sistema porque la pantalla se quedó bloqueada.",
    "No pude ir a Sistema porque apareció un error.",
    "No pude ir a Sistema porque se agotó el tiempo previsto y apareció un error.",
    "No pude ir a Sistema porque no había conexión a internet.",
    "No pude ir a Sistema porque Windows se estaba actualizando.",
    "I couldn't go to System because the screen didn't update.",
])
def test_review3_contracase_a_kind_of_another_stop_is_still_invented_on_the_time_out(draft):
    assert computer_use_finals._computer_use_final_defect(draft, _failed(_v2_u8())) == "invented_cause"


def test_review3_contracase_the_stops_kinds_are_data_of_the_stop_never_of_another():
    assert claims.stop_families("computer_use_time_exhausted") == {"wait"}
    assert claims.stop_families("computer_use_no_step_visible") == frozenset()
    assert claims.stop_families("") == frozenset()
    # The screen not updating is no cause of the time out, nor a wait one of the screen that stopped changing.
    assert computer_use_finals._computer_use_final_defect(
        "I couldn't see the default profile because it took too long.", _failed(_v2_v3_39())) == "invented_cause"
    assert computer_use_finals._computer_use_final_defect(
        "I couldn't see the default profile because the screen locked.", _failed(_v2_v3_39())) == "invented_cause"
    # Every stop named in the data is one of the floor's causes or refined causes, every kind one of the families.
    floor = operation_floor.floor_data()
    stops = set(floor["computerUse"]["causes"]) | {
        key for key in floor["computerUse"]["refinedStops"] if key not in ("source", "stops")}
    rule = claims.data()["toldCauses"]
    assert set(rule["stopFamilies"]) <= stops
    assert {kind for kinds in rule["stopFamilies"].values() for kind in kinds} <= set(rule["families"])
    assert set(rule["negatedFamilies"]) <= set(rule["families"])


@pytest.mark.parametrize("draft", [
    "No pude ir a Sistema porque se agotó el tiempo previsto, aunque no apareció ningún error.",
    "No pude ir a Sistema porque se agotó el tiempo previsto, sin ningún error en la pantalla.",
    "No pude ir a Sistema porque se agotó el tiempo previsto sin que apareciera ningún error.",
    "No pude ir a Sistema porque se agotó el tiempo previsto; la pantalla no estaba bloqueada.",
])
def test_review3_v2_u8_a_denied_or_conceded_kind_after_the_cause_passes(draft):
    assert computer_use_finals._computer_use_final_defect(draft, _failed(_v2_u8())) == ""


def test_review3_the_cause_ends_with_its_clause():
    assert claims.told_causes("No pude porque se agotó el tiempo previsto, aunque no apareció ningún error.") == [
        "se agoto el tiempo previsto"]
    assert claims.told_causes("No pude porque, al final, se agotó el tiempo.") == ["al final"]
    assert claims.told_causes("Paré porque tardó demasiado, porque la pantalla se bloqueó.") == [
        "tardo demasiado", "la pantalla se bloqueo"]


@pytest.mark.parametrize("draft", [
    # A denial before a conjunction denies nothing after it.
    "No pude ir a Sistema porque no vi el botón y apareció un error.",
    "No pude ir a Sistema porque no respondía la ventana y luego se quedó bloqueada.",
    # The kinds whose denial is the cause itself.
    "No pude ir a Sistema porque no tenía permisos de administrador.",
    "No pude ir a Sistema porque estaba sin conexión.",
    # A second cause after the first.
    "No pude ir a Sistema porque tardó demasiado, porque la pantalla se bloqueó.",
])
def test_review3_contracase_a_kind_told_after_a_denial_out_of_its_scope_is_still_invented(draft):
    assert computer_use_finals._computer_use_final_defect(draft, _failed(_v2_u8())) == "invented_cause"


# --------------------------------------------------------------------------- (c) grammar-safe schemas on the wire
_CLIPBOARD_TEXT = {  # ProductCatalog.cs: Schema([String("text", maximumLength: 65_536)], ["text"])
    "type": "object",
    "properties": {"text": {"type": "string", "maxLength": 65536}},
    "required": ["text"],
    "additionalProperties": False,
}


def _envelope(schema: dict) -> dict:
    """The extraction envelope _extract_schema_object sends (grounded + arguments)."""

    return {
        "type": "object",
        "properties": {"grounded": {"type": "boolean"}, "arguments": {"anyOf": [schema, {"type": "null"}]}},
        "required": ["grounded", "arguments"],
        "additionalProperties": False,
    }


def _bounds(node: object) -> list[int]:
    if isinstance(node, list):
        return [bound for item in node for bound in _bounds(item)]
    if not isinstance(node, dict):
        return []
    own = [value for key, value in node.items() if key in llm_grammar._GRAMMAR_REPETITION_BOUNDS and isinstance(value, int)]
    return own + [bound for value in node.values() for bound in _bounds(value)]


def test_v3_27_the_wire_schema_carries_no_repetition_above_the_ceiling():
    payload = {"messages": [], "response_format": {"type": "json_schema", "json_schema": {
        "name": "grounded_arguments", "schema": _envelope(_CLIPBOARD_TEXT)}}}
    kept = copy.deepcopy(payload)
    wire = llm_grammar._grammar_safe_payload(payload)
    assert all(bound <= llm_grammar.GRAMMAR_REPETITION_CEILING for bound in _bounds(wire))
    assert llm_grammar.GRAMMAR_REPETITION_CEILING <= 2000
    assert payload == kept  # the full schema stays for the validators and the retries


def test_contracase_schemas_without_large_bounds_go_out_byte_for_byte():
    small = {"type": "object", "properties": {"name": {"type": "string", "maxLength": 260, "minLength": 1},
                                              "items": {"type": "array", "maxItems": 16}},
             "required": ["name"], "additionalProperties": False}
    payload = {"response_format": {"type": "json_schema", "json_schema": {"name": "x", "schema": _envelope(small)}}}
    before = json.dumps(payload, ensure_ascii=False)
    assert llm_grammar._grammar_safe_payload(payload) is payload
    assert json.dumps(llm_grammar._grammar_safe_payload(payload), ensure_ascii=False) == before
    assert llm_grammar.grammar_safe_schema(small) is small
    # A property called like a bound is a property, never a bound.
    named = {"type": "object", "properties": {"maxLength": {"type": "integer"}}}
    assert llm_grammar.grammar_safe_schema(named) is named


def test_contracase_the_full_schema_still_refuses_a_text_over_its_bound():
    assert validate_json_schema_instance({"text": "hola"}, _CLIPBOARD_TEXT)
    assert validate_json_schema_instance({"text": "x" * 60_000}, _CLIPBOARD_TEXT)
    assert not validate_json_schema_instance({"text": "x" * 70_000}, _CLIPBOARD_TEXT)


def test_v3_27_post_sends_the_safe_copy(monkeypatch):
    sent: list[dict] = []

    def fake_post(payload, **_kwargs):
        sent.append(payload)
        return {"choices": [{"message": {"content": "{}"}}]}

    monkeypatch.setattr(llm, "post_chat_completion", fake_post)
    client = object.__new__(llm.LlmRuntime)
    payload = {"messages": [{"role": "user", "content": "copia hola al portapapeles"}],
               "response_format": {"type": "json_schema", "json_schema": {
                   "name": "grounded_arguments", "schema": _envelope(_CLIPBOARD_TEXT)}}}
    client._post(payload)
    assert sent and all(bound <= llm_grammar.GRAMMAR_REPETITION_CEILING for bound in _bounds(sent[0]))
    assert _bounds(payload) == [65536]


# ------------------------------------------------------------------------------------------- (d) internal fault
def test_v3_27_the_internal_fault_is_said_as_bauxys_own_and_never_on_this_pc():
    said = operation_floor.failure_sentences()["internal_fault"]
    assert "no es un límite de este equipo" in said[0]
    fact = compose_situation._CAUSE_FACT["internal_fault"]
    assert "internal fault" in fact and "no limit of this PC" in fact
    # Contracase: a semantic failure keeps its own cause.
    assert "on this PC" in compose_situation._CAUSE_FACT["plan_incomplete"]


# ------------------------------------------------------------------------------ (e) lost opening, empty search
def test_review1_an_opened_list_is_never_said_closed():
    # Revisión 1, hallazgo 3 (v3-28, «elegí la fuente Wingdings» on a PC without it): every real «opened» receipt
    # carries surfaceChanged false (DesktopUiaWorker Click-Result) and the list may still be on the screen, so the
    # stop keeps its plain cause; «lostOpening» was withdrawn.
    observed = {
        "goal": "elegí la fuente Wingdings", "application": "Mapa de caracteres", "reached": False,
        "stoppedBy": "computer_use_no_step_visible",
        "steps": [
            {"step": 1, "operation": "input.visible.click", "label": "Fuente:", "ok": True, "manner": "open",
             "method": "expand", "opened": True, "surfaceChanged": False},
            {"step": 2, "operation": "input.visible.click", "label": "Fuente:", "ok": False,
             "error": "computer_use_no_progress"},
        ],
        "screen": {"lines": ["Fuente:", "Arial", "Calibri", "Cambria", "Consolas"]},
    }
    assert cu_projection.refined_stop(observed) == ""
    assert cu_projection.project_seen(observed, "es")["stoppedBecause"] == (
        "no vi en la pantalla un control con el que seguir")
    assert "lostOpening" not in operation_floor.floor_data()["computerUse"]["refinedStops"]


def test_v3_29_an_empty_search_is_the_cause():
    observed = {
        "goal": "buscar copyright symbol; luego pégalo en una sticky note nueva", "reached": False,
        "stoppedBy": "computer_use_no_step_visible",
        "steps": [  # compose_audit of the last v3-29 run
            {"step": 3, "operation": "input.text.type", "text": "copyright symbol", "ok": True, "appeared": ["buscar"]},
            {"step": 4, "operation": "input.key.press", "key": "enter", "ok": True,
             "appeared": ["restablecer", "no hay caracteres disponibles"]},
            {"step": 5, "operation": "app.open", "appId": "Notas rápidas", "ok": True},
        ],
    }
    assert cu_projection.refined_stop(observed) == "emptySearch"
    assert cu_projection.project_seen(observed, "es")["stoppedBecause"] == "la búsqueda no encontró nada"


def test_contracases_of_the_refined_stops():
    kept = {"stoppedBy": "computer_use_no_step_visible",
            "steps": [{"operation": "input.visible.click", "ok": True, "opened": True, "surfaceChanged": True}]}
    assert cu_projection.refined_stop(kept) == ""
    retyped = {"stoppedBy": "computer_use_no_step_visible", "steps": [
        {"operation": "input.key.press", "ok": True, "appeared": ["sin resultados"]},
        {"operation": "input.text.type", "ok": True, "text": "copyright"},
    ]}
    assert cu_projection.refined_stop(retyped) == ""
    own_cause = {"stoppedBy": "computer_use_window_covered",
                 "steps": [{"operation": "input.visible.click", "ok": True, "opened": True}]}
    assert cu_projection.refined_stop(own_cause) == ""
    found = {"stoppedBy": "computer_use_no_step_visible", "steps": [
        {"operation": "input.key.press", "ok": True, "appeared": ["© copyright sign"]}]}
    assert cu_projection.refined_stop(found) == ""
    plain = cu_projection.project_seen({"stoppedBy": "computer_use_no_step_visible", "steps": []}, "es")
    assert plain["stoppedBecause"] == "no vi en la pantalla un control con el que seguir"


def test_review1_an_empty_search_needs_a_search_and_its_view():
    # Hallazgo 4 (1): «conéctate a la red Casa», a click on Wi-Fi where the window says no networks; no search.
    networks = {"stoppedBy": "computer_use_no_step_visible", "steps": [
        {"operation": "input.visible.click", "ok": True, "label": "Wi-Fi", "appeared": ["No hay redes disponibles"]}]}
    assert cu_projection.refined_stop(networks) == ""
    # (2): «Agregar dispositivo» shows none found; a state of the window, no search.
    devices = {"stoppedBy": "computer_use_surface_unchanged", "steps": [
        {"operation": "input.visible.click", "ok": True, "label": "Agregar dispositivo",
         "appeared": ["No se encontraron dispositivos"]}]}
    assert cu_projection.refined_stop(devices) == ""
    # (3): «bluetoth» found nothing, then clicks on Dispositivos and Bluetooth left the search behind.
    left = {"stoppedBy": "computer_use_no_step_visible", "steps": [
        {"operation": "input.text.type", "ok": True, "text": "bluetoth"},
        {"operation": "input.key.press", "ok": True, "key": "enter", "appeared": ["No se encontraron resultados"]},
        {"operation": "input.visible.click", "ok": True, "label": "Dispositivos", "surfaceChanged": True,
         "appeared": ["Bluetooth"]},
        {"operation": "input.visible.click", "ok": True, "label": "Bluetooth"},
    ]}
    assert cu_projection.refined_stop(left) == ""
    assert cu_projection.project_seen(left, "es")["stoppedBecause"] == (
        "no vi en la pantalla un control con el que seguir")
    # Integración ronda 20 (P5 + P8): «no hay … disponibles» is evidence.noResults since P8 (v3-29), and every reader of
    # that rule (the judge's echo and typed_by_baxy checks, this refinement) reads it only after a search: a line with
    # no search before it, or one that a click after the typing brought, is a state of the window, never an empty search.
    assert re.search(cu_vocabulary._evidence_rules()["noResults"], "no hay redes disponibles")
    clicked = {"stoppedBy": "computer_use_no_step_visible", "steps": [
        {"operation": "input.text.type", "ok": True, "text": "casa"},
        {"operation": "input.visible.click", "ok": True, "label": "Wi-Fi", "appeared": ["No hay redes disponibles"]}]}
    assert cu_projection.refined_stop(clicked) == ""
    # Contracases: the same search with its stop right after it, and a search-as-you-type that found nothing.
    assert cu_projection.refined_stop({**left, "steps": left["steps"][:2]}) == "emptySearch"
    typed = {"stoppedBy": "computer_use_no_step_visible", "steps": [
        {"operation": "input.text.type", "ok": True, "text": "bluetoth", "appeared": ["Sin resultados"]}]}
    assert cu_projection.refined_stop(typed) == "emptySearch"
