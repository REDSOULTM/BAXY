"""Ronda 22 «ventanas-y-recibos-sin-ajenos-ni-falsos» (uso real, pasada r18).

t4-c19 «ponme el navegador y el word uno al lado del otro»: the floor published «Busqué las ventanas; hay 3:
«Verification page | Example Platform - Opera», «(14) Un día cualquiera…» y «Imagen sobre imagen», pero no pude terminar el
resto» — a failed mission told its only quiet read as done and listed windows the request never named. t4-c07 and
t1-c13: «Creé la carpeta» over a folder that already existed (receipt reachedState true). The views below are the
real ones of the evidence (tandas_r20/t4/compose_audit.jsonl line 92).
"""

from __future__ import annotations

import json

import pytest

from baxy_mind import compose_payload
from baxy_mind import computer_use_finals
from baxy_mind.operation_floor import floor_final
from baxy_mind.semantic import claims
from baxy_mind.semantic.windows import asks_to_name_windows

_WINDOWS = [
    {"windowId": "win_5e7bab303f1ff176a337424f3a7a3fde", "processId": 4100, "processName": "opera",
     "title": "Verification page | Example Platform - Opera", "state": "maximized", "foreground": False,
     "x": -7, "y": -7, "width": 1550, "height": 830},
    {"windowId": "win_0ab226b1fedf29bd44ccce7bb79a7ae5", "processId": 4100, "processName": "opera",
     "title": "(14) Un día cualquiera en la ciudad | VLOG - YouTube - Opera", "state": "normal",
     "foreground": False, "x": 0, "y": 0, "width": 768, "height": 816},
    {"windowId": "win_e43be62a010c59dce6a61109bfd50439", "processId": 4100, "processName": "opera",
     "title": "Imagen sobre imagen", "state": "normal", "foreground": False,
     "x": 1155, "y": 594, "width": 365, "height": 206},
]
_TITLES = ("Verification", "Un día cualquiera", "Imagen sobre imagen")


def _resolve() -> dict:
    return {
        "kind": "operation", "operation": "window.resolve", "polarity": "success", "verified": True,
        "succeeded": True, "readOnly": True,
        "observed": {
            "version": 1, "windows": _WINDOWS, "count": 3, "limit": 20, "offset": 0, "observedCount": 3,
            "complete": True, "totalCount": 3, "hasMore": False,
            "observationScope": "visible_top_level_windows",
            "pageConsistency": "fresh_enumeration_per_request",
        },
    }


def _failed_mission(reason: dict) -> dict:
    return {
        "kind": "failure", "polarity": "failure", "cause": "mission_failed", "stepCount": 1,
        "steps": [json.dumps(_resolve(), ensure_ascii=False)], "reason": reason,
    }


# ---------------------------------------------------------------- (b) the quiet read is never told as done

def test_t4_c19_the_failed_mission_says_the_effect_left_undone_never_the_list() -> None:
    reason = {"kind": "failure", "polarity": "failure", "cause": "step_data_missing", "operation": "window.snap"}
    final = floor_final(_failed_mission(reason), english=False)
    assert final == "No pude colocar la ventana."
    assert not any(title in final for title in _TITLES)
    assert "hay 3" not in final


def test_t4_c19_a_reason_with_no_operation_lists_nothing() -> None:
    # The facts of the run itself (no operation on the reason): nothing to tell, never the list.
    final = floor_final(_failed_mission({"kind": "failure", "polarity": "failure", "cause": "step_data_missing"}),
                        english=False)
    assert not any(title in final for title in _TITLES)


def test_contracase_a_completed_listing_still_names_the_windows() -> None:
    mission = {"kind": "status", "polarity": "success", "cause": "mission_completed", "stepCount": 1,
               "steps": [json.dumps(_resolve(), ensure_ascii=False)]}
    final = floor_final(mission, english=False)
    assert "hay 3" in final and "Verification page" in final


def test_contracase_a_done_effect_after_an_intermediate_read_is_still_told() -> None:
    snap = {"kind": "operation", "operation": "window.snap", "polarity": "success", "verified": True,
            "succeeded": True, "observed": {"version": 1, "side": "left",
                                            "window": {"title": "Documento1 - Word", "processName": "WINWORD"}}}
    mission = {"kind": "failure", "polarity": "failure", "cause": "mission_failed", "stepCount": 3,
               "steps": [json.dumps(_resolve(), ensure_ascii=False), json.dumps(snap, ensure_ascii=False)],
               "reason": {"kind": "failure", "polarity": "failure", "cause": "step_data_missing",
                          "operation": "window.snap"}}
    final = floor_final(mission, english=False)
    assert final.startswith("Coloqué la ventana")
    assert "no pude colocar la ventana" in final
    assert not any(title in final for title in _TITLES)


# ---------------------------------------------------------------- (c) titles travel only when asked

def test_t4_c19_the_payload_of_the_failed_mission_carries_no_title() -> None:
    reason = {"kind": "failure", "polarity": "failure", "cause": "step_data_missing", "operation": "window.snap"}
    payload = compose_payload._compose_situation_payload(
        _failed_mission(reason), "es", "ponme el navegador y el word uno al lado del otro")
    dumped = json.dumps(payload, ensure_ascii=False)
    assert not any(title in dumped for title in _TITLES)
    assert payload["completedStepsInOrder"][0]["resultAtThisStep"]["seen"]["count"] == 3


@pytest.mark.parametrize("asked", ["¿qué ventanas tengo abiertas?", "lista las ventanas del navegador"])
def test_contracase_a_request_to_list_windows_keeps_the_titles(asked: str) -> None:
    mission = {"kind": "status", "polarity": "success", "cause": "mission_completed", "stepCount": 1,
               "steps": [json.dumps(_resolve(), ensure_ascii=False)]}
    dumped = json.dumps(compose_payload._compose_situation_payload(mission, "es", asked), ensure_ascii=False)
    assert "Verification page" in dumped


@pytest.mark.parametrize(
    ("text", "asked"),
    [
        ("ponme el navegador y el word uno al lado del otro", False),
        ("pon el word a la izquierda", False),
        ("minimiza la ventana del navegador", False),
        ("¿qué ventanas tengo abiertas?", True),
        ("lista las ventanas del navegador", True),
        ("dime los títulos de las pestañas", True),
        ("what windows do I have open?", True),
        # Revisión 2: what a window shows is asked too; a relative «que» inside an order asks nothing.
        ("¿qué documento tengo abierto en word y en el bloc de notas?", True),
        ("¿qué tengo abierto en el navegador?", True),
        ("que tengo abierto en el navegador", True),
        ("what page is open in chrome?", True),
        ("¿qué programas tengo abiertos?", True),
        ("minimiza lo que tengo abierto", False),
        ("cierra la pestaña que tengo abierta", False),
        ("abre el archivo de las notas", False),
        ("close what I have open", False),
    ],
)
def test_the_reader_of_a_request_to_name_windows(text: str, asked: bool) -> None:
    assert asks_to_name_windows(text) is asked


def _resolved(window: dict) -> str:
    return json.dumps({
        "kind": "operation", "operation": "window.resolve", "polarity": "success", "verified": True,
        "succeeded": True, "readOnly": True,
        "observed": {"version": 1, "windows": [window], "count": 1, "complete": True, "totalCount": 1,
                     "hasMore": False, "observationScope": "visible_top_level_windows"},
    }, ensure_ascii=False)


_WORD = {"windowId": "win_" + "a" * 32, "processId": 51, "processName": "WINWORD",
         "title": "Informe trimestral.docx - Word", "state": "normal", "foreground": True,
         "x": 0, "y": 0, "width": 1200, "height": 800}
_NOTEPAD = {"windowId": "win_" + "b" * 32, "processId": 52, "processName": "notepad",
            "title": "lista compras.txt - Bloc de notas", "state": "normal", "foreground": False,
            "x": 100, "y": 100, "width": 800, "height": 600}


def test_revision_2_the_last_reads_of_a_completed_mission_keep_their_titles() -> None:
    # Revisión 2 (scratchpad/probe_c.py): the question asks what the windows show; its answer is their titles.
    mission = {"kind": "status", "polarity": "success", "cause": "mission_completed", "stepCount": 2,
               "steps": [_resolved(_WORD), _resolved(_NOTEPAD)]}
    for asked in ("¿qué documento tengo abierto en word y en el bloc de notas?",
                  "revisa word y el bloc de notas"):
        dumped = json.dumps(compose_payload._compose_situation_payload(mission, "es", asked), ensure_ascii=False)
        assert "Informe trimestral.docx - Word" in dumped and "lista compras.txt - Bloc de notas" in dumped


def test_contracase_a_read_an_effect_needed_travels_without_titles_in_a_completed_mission() -> None:
    snap = {"kind": "operation", "operation": "window.snap", "polarity": "success", "verified": True,
            "succeeded": True, "readOnly": False,
            "observed": {"version": 1, "side": "left", "window": {"windowId": _WORD["windowId"], "state": "normal"}}}
    mission = {"kind": "status", "polarity": "success", "cause": "mission_completed", "stepCount": 3,
               "steps": [_resolved(_WORD), _resolved(_NOTEPAD), json.dumps(snap)]}
    payload = compose_payload._compose_situation_payload(mission, "es", "pon el word a la izquierda")
    dumped = json.dumps(payload, ensure_ascii=False)
    assert "Informe trimestral" not in dumped and "lista compras" not in dumped
    assert payload["completedStepsInOrder"][0]["resultAtThisStep"]["seen"]["count"] == 1
    # Asked what the windows show, the same reads keep them.
    asked = compose_payload._compose_situation_payload(mission, "es", "¿qué documento tengo abierto en word?")
    assert "Informe trimestral.docx - Word" in json.dumps(asked, ensure_ascii=False)


# ---------------------------------------------------------------- (d) a receipt that found the state already there

def _directory(reached: bool) -> dict:
    return {
        "kind": "operation", "operation": "filesystem.create.directory", "polarity": "success", "verified": True,
        "succeeded": True,
        "observed": {"resourceId": "fs_" + "0" * 32, "name": "ramo calculo 2", "kind": "directory", "size": 0,
                     "sha256": None, "reachedState": reached, "folder": "desktop"},
    }


def _written(reached: bool) -> dict:
    return {
        "kind": "operation", "operation": "filesystem.write.text", "polarity": "success", "verified": True,
        "succeeded": True,
        "observed": {"resourceId": "fs_" + "1" * 32, "name": "nota.txt", "kind": "file", "size": 5,
                     "sha256": "a" * 64, "reachedState": reached, "folder": "documents"},
    }


def test_t4_c07_a_folder_that_existed_is_said_as_already_there() -> None:
    assert floor_final(_directory(True), english=False) == "La carpeta «ramo calculo 2» ya estaba en el Escritorio."
    assert floor_final(_directory(True), english=True) == "The folder «ramo calculo 2» was already on the Desktop."


def test_contracase_a_new_folder_is_still_created() -> None:
    assert floor_final(_directory(False), english=False) == "Creé la carpeta «ramo calculo 2»."


def test_an_identical_write_is_said_as_already_there_and_a_new_one_written() -> None:
    assert floor_final(_written(True), english=False) == "El archivo «nota.txt» ya tenía ese contenido."
    assert floor_final(_written(False), english=False) == "Escribí el archivo «nota.txt»."


def test_t1_c13_creation_is_vetoed_over_a_folder_that_existed() -> None:
    ledger = computer_use_finals._act_ledger(_directory(True))
    assert ledger is not None and not {"crear", "hacer"} & ledger
    assert claims.unbacked_act("Creé la carpeta «facturas octubre» en el Escritorio.", ledger) == "creé"
    assert claims.unbacked_act("La carpeta «facturas octubre» ya estaba en el Escritorio.", ledger) == ""


def test_contracase_creation_and_saving_stay_backed_when_something_changed() -> None:
    assert claims.unbacked_act("Creé la carpeta «facturas octubre».", computer_use_finals._act_ledger(_directory(False))) == ""
    assert claims.unbacked_act("Guardé el texto en «nota.txt».", computer_use_finals._act_ledger(_written(False))) == ""
    assert claims.unbacked_act("Guardé el texto en «nota.txt».", computer_use_finals._act_ledger(_written(True))) == "guardé"


def test_the_payload_marks_the_state_already_held_and_no_effect_applied() -> None:
    held = compose_payload._compose_situation_payload(_directory(True), "es", "crea una carpeta en el escritorio ramo calculo 2")
    assert held["seen"]["alreadyInState"] is True and "effect" not in held
    made = compose_payload._compose_situation_payload(_directory(False), "es", "crea una carpeta en el escritorio ramo calculo 2")
    assert "alreadyInState" not in made["seen"] and made["effect"] == "applied"


def test_held_state_acts_come_from_data() -> None:
    assert claims.held_state_acts({"reachedState": True}) >= {"crear", "escribir", "guardar"}
    assert claims.held_state_acts({"reachedState": False}) == frozenset()
    assert claims.held_state_acts(None) == frozenset()


# ---------------------------------------------------------------- t2-c18, t3-c15: the snapped window is named

def _snap(side: str, title: str, process: str, **observed: object) -> dict:
    return {"kind": "operation", "operation": "window.snap", "polarity": "success", "verified": True,
            "succeeded": True, "readOnly": False,
            "observed": {"version": 1, "side": side, **observed,
                         "window": {"windowId": "win_2e2a17656b7b80141f4c671a1b641f3b", "processName": process,
                                    "title": title, "state": "normal"}}}


def test_t2_c18_both_snapped_windows_are_named_with_their_side() -> None:
    # Revisión 2 (tandas_r20/t2/compose_audit.jsonl, the draft vetoed for missing_prior_open): the floor said
    # «Coloqué la ventana: a la izquierda y coloqué la ventana: a la derecha», naming no window.
    mission = {"kind": "status", "polarity": "success", "cause": "mission_completed", "stepCount": 3,
               "steps": [json.dumps(_resolve(), ensure_ascii=False),
                         json.dumps(_snap("left", "Documento1  -  Autorecuperado - Word", "WINWORD"),
                                    ensure_ascii=False),
                         json.dumps(_snap("right", "Encontrar información sobre el dispositivo Windows | Microsoft "
                                               "Support", "msedge"), ensure_ascii=False)]}
    assert floor_final(mission, english=False) == (
        "Coloqué la ventana «Documento1 - Autorecuperado - Word» a la izquierda y coloqué la ventana «Encontrar "
        "información sobre el dispositivo Windows | Microsoft Support» a la derecha.")


def test_t3_c15_a_single_snap_is_named_and_its_side_has_no_loose_colon() -> None:
    assert floor_final(_snap("left", "Documento1 - Word", "WINWORD"), english=False) == (
        "Coloqué la ventana «Documento1 - Word» a la izquierda.")
    assert floor_final(_snap("left", "Documento1 - Word", "WINWORD"), english=True) == (
        "I snapped the window «Documento1 - Word» on the left.")


def test_contracase_a_fact_that_is_no_part_of_the_clause_keeps_the_detail_separator() -> None:
    assert floor_final(_snap("left", "Documento1 - Word", "WINWORD", fitsInHalf=False), english=False) == (
        "Coloqué la ventana «Documento1 - Word» a la izquierda: no cabe en media pantalla y ocupa un poco más.")


def test_contracase_a_receipt_with_no_window_record_still_says_the_side() -> None:
    snap = {"kind": "operation", "operation": "window.snap", "polarity": "success", "verified": True,
            "succeeded": True, "observed": {"version": 1, "side": "right"}}
    assert floor_final(snap, english=False) == "Coloqué la ventana a la derecha."
