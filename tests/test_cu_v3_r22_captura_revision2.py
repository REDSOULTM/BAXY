"""Ronda 22, revisión 2 de «captura-guardada-donde-se-pide».

Bloqueante 1: «take a screenshot and save it to my desktop now» read the place as «my desktop now» (unmet): a known
folder said with a possessive and followed by any word was lost. Bloqueante 2: a draft over a capture saved in the
Desktop that said «la guardé en Descargas» or «quedó privada» passed every veto, alone or as a mission's step.
Bloqueante 3: a part of the request the chosen operation's schema cannot receive («…y mándala a mi jefe») was lost in
silence for any operation but the capture's own places.
"""

from __future__ import annotations

import json

import pytest

from baxy_mind import compose_payload
from baxy_mind import deterministic_finals
from baxy_mind import payload_fact_checks
from baxy_mind import visible_defect
from baxy_mind.compose_facts import _with_unreceived_parts
from baxy_mind.semantic.acts_on_result import UnreceivedPart, unreceived_parts
from baxy_mind.semantic.captures import capture_save, capture_save_arguments
from test_cu_v3_r22_captura_guardada import CAPTURE_SCHEMA, SAVED, _situation

_SAVED_FILE = "Screenshot 2026-10-09 075027.png"


# --- bloqueante 1: a known folder said with a possessive, then other words, is that folder ----------------------------

@pytest.mark.parametrize(
    ("said", "folder"),
    [
        ("take a screenshot and save it to my desktop now", "desktop"),
        ("toma una captura y guárdala en mis imágenes ahora", "pictures"),
        ("toma una captura y guárdala en mi escritorio rápido", "desktop"),
        ("toma una captura y guárdala en mi escritorio con el nombre factura", "desktop"),
        ("toma una captura y guárdala en mi escritorio porfavor", "desktop"),
        ("take a screenshot and save it to my desktop for later", "desktop"),
        ("take a screenshot and save it in my downloads folder now", "downloads"),
        ("toma una captura y guárdala en el escritorio para después", "desktop"),
    ],
)
def test_a_known_folder_followed_by_other_words_is_kept_there_with_nothing_unmet(said: str, folder: str) -> None:
    save = capture_save(said)
    assert save is not None and save.folder == folder and save.unmet == ()


@pytest.mark.parametrize(
    ("said", "unmet"),
    [
        # Contracasos: a word that continues the folder's name, or a folder inside it, is a place it cannot take.
        ("toma una captura y guárdala en la carpeta descargas viejas", ("carpeta descargas viejas",)),
        ("toma una captura y guárdala en mi escritorio nuevo", ("mi escritorio nuevo",)),
        ("toma una captura y guárdala en documentos/proyectos", ("documentos/proyectos",)),
        ("toma una captura y guárdala en mi escritorio/proyectos", ("mi escritorio/proyectos",)),
        # The place not taken is quoted without the words of when it was asked.
        ("toma una captura y guárdala en mi pendrive ahora", ("mi pendrive",)),
    ],
)
def test_a_folder_name_continued_or_a_subfolder_stays_unmet(said: str, unmet: tuple) -> None:
    save = capture_save(said)
    assert save is not None and save.folder is None and save.unmet == unmet


# --- bloqueante 2: the place told is the one saved, and a saved capture is never «private» ----------------------------

@pytest.mark.parametrize(
    "draft",
    [
        f"Tomé una captura y la guardé en Descargas como «{_SAVED_FILE}».",
        f"Tomé la captura «{_SAVED_FILE}»; quedó privada en este PC, no la guardé en ningún lado.",
        f"Tomé la captura «{_SAVED_FILE}» y la guardé de forma privada.",
    ],
)
def test_a_saved_capture_told_elsewhere_or_private_is_vetoed(draft: str) -> None:
    facts = {"situation": _situation(**SAVED)}
    assert visible_defect.compose_visible_defect(draft, "status", "toma una captura y guárdala en el escritorio", facts) == (
        "capture_saved_place_contradicted"
    )


def test_a_saved_capture_told_where_it_is_passes_and_a_private_one_keeps_its_rules() -> None:
    facts = {"situation": _situation(**SAVED)}
    told = f"Tomé una captura de toda la pantalla y la guardé en el Escritorio como «{_SAVED_FILE}»."
    assert visible_defect.compose_visible_defect(told, "status", "toma una captura y guárdala en el escritorio", facts) == ""
    # Privacy denied in its own clause is not affirmed.
    denied = f"Tomé una captura; no quedó privada: la guardé en el Escritorio como «{_SAVED_FILE}»."
    assert visible_defect.compose_visible_defect(denied, "status", "toma una captura y guárdala en el escritorio", facts) == ""
    # Contracaso: with no copy saved, «privada» is the truth and a folder is the invented one.
    private = {"situation": _situation()}
    assert visible_defect.compose_visible_defect(
        "Tomé una captura de toda la pantalla; quedó privada en este PC.", "status", "toma una captura", private,
    ) == ""
    assert visible_defect.compose_visible_defect(
        "Tomé una captura y la guardé en el escritorio.", "status", "toma una captura", private,
    ) == "invented_capture_location"


def _mission_with_saved_capture() -> dict:
    opened = {"kind": "operation", "operation": "app.open", "polarity": "success", "verified": True,
              "succeeded": True, "observed": {"displayName": "Calculadora"}}
    return {"kind": "operation", "cause": "mission_completed", "polarity": "success", "verified": True,
            "succeeded": True, "steps": [json.dumps(opened), json.dumps(_situation(**SAVED))]}


@pytest.mark.parametrize(
    ("draft", "defect"),
    [
        ("Abrí la Calculadora y tomé una captura de pantalla; quedó privada en este PC.",
         "capture_saved_place_contradicted"),
        ("Abrí la Calculadora y tomé una captura de pantalla que guardé en Documentos.",
         "capture_saved_place_contradicted"),
        (f"Abrí la Calculadora y tomé una captura de pantalla que guardé en el Escritorio como «{_SAVED_FILE}».", ""),
    ],
)
def test_a_missions_capture_step_is_told_where_it_was_saved(draft: str, defect: str) -> None:
    said = "abre la calculadora, toma una captura y guárdala en el escritorio"
    assert visible_defect.compose_visible_defect(draft, "status", said, {"situation": _mission_with_saved_capture()}) == defect


# --- bloqueante 3: any part the operation's schema cannot receive is told as not done ---------------------------------

_CAPTURE_TOOLS = {
    operation: {"type": "function", "function": {"name": operation.replace(".", "_"), "canonical_name": operation,
                                                  "parameters": CAPTURE_SCHEMA}}
    for operation in ("capture.screenshot", "capture.active.window")
}


def test_a_keeping_led_into_by_a_wish_is_still_the_captures() -> None:
    assert capture_save_arguments("toma una captura, quiero guardarla en el escritorio") == {"folder": "desktop"}
    assert capture_save_arguments("take a screenshot, I want to save it in downloads") == {"folder": "downloads"}
    # Contracaso: another clause between them still keeps what that clause made.
    assert capture_save_arguments("toma una captura, abre el bloc de notas y guárdalo en el escritorio") == {}


@pytest.mark.parametrize(
    ("said", "properties", "parts"),
    [
        ("toma una captura y mándala a mi jefe", ["folder"], (UnreceivedPart("send", "mándala a mi jefe"),)),
        ("take a screenshot and send it to my boss", ["folder"], (UnreceivedPart("send", "send it to my boss"),)),
        ("toma una captura y súbela a la nube", ["folder"], (UnreceivedPart("upload", "súbela a la nube"),)),
        ("abre el informe y imprímelo porfa", ["appId"], (UnreceivedPart("print", "imprímelo"),)),
        ("abre el editor y guárdalo en el escritorio", ["appId"], (UnreceivedPart("keep", "guárdalo en el escritorio"),)),
        # Kept where asked (the schema has a folder), but the name asked has no property.
        ("toma una captura y guárdala en mi escritorio con el nombre factura", ["folder"],
         (UnreceivedPart("name", "factura"),)),
    ],
)
def test_a_part_the_schema_cannot_receive_is_read_for_any_operation(said: str, properties: list, parts: tuple) -> None:
    assert unreceived_parts(said, properties) == parts


@pytest.mark.parametrize(
    ("said", "properties"),
    [
        # Contracasos: the schema receives it, the act is refused, alone, or asks nothing an argument holds.
        ("escribe hola a juan y mándalo", ["channel", "recipient", "text"]),
        ("toma una captura y guárdala en el escritorio", ["folder"]),
        ("toma una captura y no la mandes", ["folder"]),
        ("mándala a mi jefe", ["folder"]),
        ("toma una captura y guárdala", ["folder"]),
        ("hazme una captura y dime qué ves", ["folder"]),
    ],
)
def test_a_part_the_schema_receives_or_no_act_on_the_result_is_nothing_unreceived(said: str, properties: list) -> None:
    assert unreceived_parts(said, properties) == ()


def test_the_part_not_received_reaches_the_writer_the_floor_and_the_veto() -> None:
    said = "toma una captura y mándala a mi jefe"
    facts = _with_unreceived_parts({"situation": json.dumps(_situation())}, said, _CAPTURE_TOOLS)
    situation = facts["situation"]
    assert situation["unreceived"] == [{"act": "send", "said": "mándala a mi jefe"}]
    payload = compose_payload._compose_situation_payload(situation, "es", said)
    assert payload["notDone"] == [{"action": "enviarlo", "target": "mándala a mi jefe"}]
    final = deterministic_finals._deterministic_final(situation, payload, said, "es")
    assert final == "Hice la captura de pantalla. No hice esto: «mándala a mi jefe»."
    assert payload_fact_checks._payload_fact_defect(final, payload) == ""
    assert payload_fact_checks._payload_fact_defect("Hice la captura de pantalla.", payload) == "unreceived_part_untold"
    assert payload_fact_checks._payload_fact_defect("Tomé una captura y se la envié a tu jefe.", payload) == "unreceived_part_untold"
    assert payload_fact_checks._payload_fact_defect("Tomé una captura, pero no se la envié a tu jefe.", payload) == ""


def test_the_name_not_received_is_told_beside_the_saved_place() -> None:
    said = "toma una captura y guárdala en mi escritorio con el nombre factura"
    facts = _with_unreceived_parts({"situation": _situation(**SAVED)}, said, _CAPTURE_TOOLS)
    payload = compose_payload._compose_situation_payload(facts["situation"], "es", said)
    assert payload["seen"]["savedIn"] == "el Escritorio"
    final = deterministic_finals._deterministic_final(facts["situation"], payload, said, "es")
    assert final == (
        f"Hice la captura de pantalla «{_SAVED_FILE}»: la guardé en el Escritorio. No le puse el nombre «factura»."
    )
    assert payload_fact_checks._payload_fact_defect(final, payload) == ""


def test_only_a_single_served_operation_carries_unreceived_parts() -> None:
    said = "toma una captura y mándala a mi jefe"
    # Contracasos: a mission (its plan gives each part a step), an operation not served, nothing unreceived.
    mission = {"situation": _mission_with_saved_capture()}
    assert _with_unreceived_parts(mission, said, _CAPTURE_TOOLS) is mission
    unknown = {"situation": {**_situation(), "operation": "app.open"}}
    assert _with_unreceived_parts(unknown, said, _CAPTURE_TOOLS) is unknown
    plain = {"situation": json.dumps(_situation())}
    assert _with_unreceived_parts(plain, "toma una captura", _CAPTURE_TOOLS) is plain
