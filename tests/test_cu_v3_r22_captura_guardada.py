"""Ronda 22, palanca «captura-guardada-donde-se-pide» (uso real, pasada r18).

t2-c16 «toma una captura de pantalla y guardala en mis imagenes» and t3-c11 «hazme una captura de pantalla y guárdala en
el escritorio porfa» were told «Hice la captura de pantalla.»; t4-c09 «saca una captura de pantalla y guardala» was told
«…la guardé de forma privada en este dispositivo». The capture took no destination (EmptySchema), so the part «guárdala
en X» was lost in silence. The capture now takes an optional known ``folder`` read from the person's words
(semantic.captures), the handler saves a verified PNG there, and the final says where it is.
"""

from __future__ import annotations

import pytest

from baxy_mind import operation_floor
from baxy_mind import compose_payload
from baxy_mind import deterministic_finals
from baxy_mind import payload_fact_checks
from baxy_mind.argument_grounding import _ground_explicit_arguments
from baxy_mind.semantic.arguments import _explicit_arguments_from_evidence
from baxy_mind.semantic.captures import capture_save, capture_save_arguments
from test_c03_cpu_actor import Recorder

# The catalog's own argument schema of capture.screenshot / capture.active.window (ProductCatalog.CaptureSchema).
CAPTURE_SCHEMA = {
    "type": "object",
    "properties": {"folder": {"type": "string", "enum": ["desktop", "documents", "downloads", "pictures"]}},
    "required": [],
    "additionalProperties": False,
}


# --- the reader: the verb of keeping and the place --------------------------------------------------------------------

@pytest.mark.parametrize(
    ("said", "folder"),
    [
        # The three real cases of r18, as dictated (t3-c11 also as the decider restated it).
        ("toma una captura de pantalla y guardala en mis imagenes", "pictures"),
        ("hazme una captura de pantalla y guárdala en el escritorio porfa", "desktop"),
        ("Haz una captura de pantalla y guárdala en el escritorio.", "desktop"),
        ("saca una captura de pantalla y guardala", "pictures"),
        ("take a screenshot and save it to my desktop", "desktop"),
        ("take a screenshot and keep it", "pictures"),
        ("haz una captura y sálvala en documentos", "documents"),
        ("toma captura y la guardas en descargas", "downloads"),
        ("screenshot the window and save it in downloads please", "downloads"),
        # The screen's own «escritorio» before the verb is what was captured, not where it goes.
        ("sacá una captura del escritorio y guardala", "pictures"),
        # A place in another clause after the keeping is not its destination.
        ("captura y guárdala y luego abre el escritorio", "pictures"),
    ],
)
def test_a_capture_asked_to_be_kept_reads_its_known_folder(said: str, folder: str) -> None:
    assert capture_save_arguments(said) == {"folder": folder}


@pytest.mark.parametrize(
    "said",
    [
        # Contracasos: no verb of keeping, the capture stays private and no file is written.
        "hazme una captura y dime qué ves",
        "sacale un screenshot a la pantalla",
        "toma una captura del escritorio",
        "haz una captura de pantalla",
        # Negated keeping.
        "toma una captura pero no la guardes",
        "take a screenshot but don't save it",
    ],
)
def test_without_a_verb_of_keeping_the_capture_stays_private(said: str) -> None:
    assert capture_save(said) is None
    assert capture_save_arguments(said) == {}


def test_a_place_that_is_no_known_folder_is_never_saved_to_pictures_in_its_stead() -> None:
    save = capture_save("haz una captura y guárdala en mi pendrive")
    assert save is not None and save.folder is None
    assert capture_save_arguments("haz una captura y guárdala en mi pendrive") == {}


# --- the arguments: the reader's, never the model's --------------------------------------------------------------------

@pytest.mark.parametrize("operation", ["capture.screenshot", "capture.active.window"])
def test_the_capture_arguments_come_from_the_reader(operation: str) -> None:
    assert _explicit_arguments_from_evidence(operation, "hazme una captura de pantalla y guárdala en el escritorio porfa") == {
        "folder": "desktop"
    }
    # A bare capture is grounded with no arguments: the model is never asked to fill a folder.
    assert _explicit_arguments_from_evidence(operation, "sacale un screenshot a la pantalla") == {}
    assert _ground_explicit_arguments(operation, "toma una captura del escritorio", CAPTURE_SCHEMA) == {}
    assert _ground_explicit_arguments(operation, "saca una captura de pantalla y guardala", CAPTURE_SCHEMA) == {
        "folder": "pictures"
    }


def test_a_restatement_that_dropped_the_keeping_falls_back_to_the_persons_message() -> None:
    history = [{"role": "user", "content": "toma una captura de pantalla y guardala en mis imagenes"}]
    assert _ground_explicit_arguments(
        "capture.screenshot", "Toma una captura de pantalla.", CAPTURE_SCHEMA, history=history,
    ) == {"folder": "pictures"}


# --- the final: where it is, from the receipt --------------------------------------------------------------------------

def _situation(**saved: str) -> dict:
    return {
        "kind": "operation", "operation": "capture.screenshot", "polarity": "success",
        "verified": True, "succeeded": True,
        "observed": {"version": 1, "captureId": "capture_" + "0" * 32, "width": 1920, "height": 1080,
                     "sha256": "ab" * 32, "scope": "virtual_screen", "createdAtUtc": "2026-10-09T10:50:27Z", **saved},
    }


SAVED = {"savedFolder": "desktop", "fileName": "Screenshot 2026-10-09 075027.png", "savedSha256": "cd" * 32}


def test_the_writer_gets_the_folders_visible_name_and_the_file_not_privacy() -> None:
    payload = compose_payload._compose_situation_payload(_situation(**SAVED), "es", "hazme una captura y guárdala en el escritorio")
    seen = payload["seen"]
    assert seen["savedIn"] == "el Escritorio"
    assert seen["fileName"] == "Screenshot 2026-10-09 075027.png"
    assert "storedPrivately" not in seen
    assert "savedSha256" not in seen and "captureId" not in seen


def test_without_a_copy_the_writer_is_told_it_stayed_private_and_nothing_else() -> None:
    seen = compose_payload._compose_situation_payload(_situation(), "es", "hazme una captura y dime qué ves")["seen"]
    assert seen["storedPrivately"] is True
    assert "savedIn" not in seen and "fileName" not in seen


def test_a_saved_capture_told_as_private_or_without_its_place_is_vetoed() -> None:
    payload = compose_payload._compose_situation_payload(_situation(**SAVED), "es", "saca una captura de pantalla y guardala")
    untold = "Tomé una captura de pantalla completa del escritorio y la guardé de forma privada en este dispositivo."
    told = "Tomé una captura de toda la pantalla y la guardé en el Escritorio como «Screenshot 2026-10-09 075027.png»."
    assert payload_fact_checks._payload_fact_defect(untold, payload) == "capture_place_untold"
    assert payload_fact_checks._payload_fact_defect(told, payload) == ""


@pytest.mark.parametrize(
    "told",
    [
        # Tandas c27u…r29m t2-c16 (5 vetoed drafts, +0,94 s each): a report in the perfect is the capture told.
        "He tomado la captura de pantalla y la he guardado en el Escritorio, con el nombre Screenshot 2026-10-09 075027.png.",
        "He capturado la pantalla y la he guardado en el Escritorio, con el nombre Screenshot 2026-10-09 075027.png.",
        "Capturé la pantalla y la guardé en el Escritorio como «Screenshot 2026-10-09 075027.png».",
    ],
)
def test_estabilizacion_r5_a_capture_told_in_any_past_is_not_vetoed(told: str) -> None:
    payload = compose_payload._compose_situation_payload(_situation(**SAVED), "es", "saca una captura de pantalla y guardala")
    assert payload_fact_checks._payload_fact_defect(told, payload) == ""


@pytest.mark.parametrize("echo", ["Sacá un screenshot del área virtual.", "Toma una captura de pantalla.",
                                  "Take a screenshot of the screen."])
def test_contracase_r5_the_capture_echoed_as_an_order_is_still_vetoed(echo: str) -> None:
    # SCREEN1399 H0093 «sacá un screenshot» → «Sacá un screenshot del área virtual.» over a private capture.
    payload = compose_payload._compose_situation_payload(_situation(), "es", "sacá un screenshot")
    assert payload_fact_checks._payload_fact_defect(echo, payload) == "capture_not_reported"
    assert payload_fact_checks._payload_fact_defect("Saqué una captura de toda la pantalla.", payload) == ""


def test_the_saved_capture_is_told_with_its_place_on_the_first_stage() -> None:
    told = "Tomé una captura de toda la pantalla y la guardé en el Escritorio como «Screenshot 2026-10-09 075027.png»."
    client = Recorder([told])
    facts = {"situation": _situation(**SAVED)}
    assert client.compose_user_message("hazme una captura de pantalla y guárdala en el escritorio porfa", "status", facts) == told
    assert "seen.savedIn the folder it was saved in" in client.payloads[0]["messages"][-1]["content"]


@pytest.mark.parametrize(
    ("english", "expected"),
    [
        # The file is the floor's identity of what was made (data «identity»: fileName); the fact says where it is.
        (False, "Hice la captura de pantalla «Screenshot 2026-10-09 075027.png»: la guardé en el Escritorio."),
        (True, "I captured the screen «Screenshot 2026-10-09 075027.png»: I saved it on the Desktop."),
    ],
)
def test_the_floor_says_where_the_saved_capture_is(english: bool, expected: str) -> None:
    assert operation_floor.floor_final(_situation(**SAVED), english) == expected


def test_the_floor_of_a_private_capture_is_unchanged() -> None:
    assert operation_floor.floor_final(_situation(), False) == "Hice la captura de pantalla."


# --- revisión r22, bloqueante 2: the keeping's object is the capture, the place a folder, and never the opposite ------

@pytest.mark.parametrize(
    "said",
    [
        # Asking it private is asking for what a capture already is: no file.
        "take a screenshot and keep it private",
        "toma una captura y guárdala en privado",
        # A dialog or menu whose title says save is what is captured, not a keeping.
        "toma una captura del diálogo de guardar como",
        "take a screenshot of the save as window",
        "screenshot the save game menu",
        # The verb's object is something else (the chained route reads the whole request).
        "guarda el archivo en el escritorio y luego toma una captura",
        "toma una captura y luego guarda el archivo en el escritorio",
        "toma una captura, abre el bloc de notas y guárdalo en el escritorio",
        # A verb of placing with no place keeps nothing.
        "toma una captura y déjala",
    ],
)
def test_a_keeping_that_is_not_of_the_capture_or_asks_it_private_writes_no_file(said: str) -> None:
    assert capture_save_arguments(said) == {}
    assert _ground_explicit_arguments("capture.screenshot", said, CAPTURE_SCHEMA) == {}


@pytest.mark.parametrize(
    ("said", "folder"),
    [
        ("toma una captura y déjala en el escritorio", "desktop"),
        ("toma una captura y ponla en el escritorio", "desktop"),
        ("toma una captura y la dejas en descargas", "downloads"),
        ("guárdame una captura de pantalla en el escritorio", "desktop"),
        ("take a screenshot and save it in the downloads folder", "downloads"),
        ("toma una captura y guárdala en la carpeta de descargas", "downloads"),
        ("toma una captura y guarda en descargas", "downloads"),
        ("toma una captura y luego guárdala en documentos", "documents"),
    ],
)
def test_a_capture_placed_in_a_known_folder_is_kept_there(said: str, folder: str) -> None:
    assert capture_save_arguments(said) == {"folder": folder}


# --- revisión r22, bloqueante 1: what the operation cannot take is told as not done ------------------------------------

@pytest.mark.parametrize(
    ("said", "folder", "unmet"),
    [
        ("toma una captura y guárdala en mi pendrive", None, ("mi pendrive",)),
        ("toma una captura y guárdala en la carpeta proyectos", None, ("carpeta proyectos",)),
        ("toma una captura y guárdala en el portapapeles", None, ("portapapeles",)),
        ("save a screenshot to my usb drive", None, ("my usb drive",)),
        ("toma una captura y guárdala en el escritorio y en documentos", "desktop", ("documentos",)),
        ("toma una captura y guárdala en la carpeta proyectos del escritorio", None, ("carpeta proyectos del escritorio",)),
    ],
)
def test_every_place_the_capture_cannot_take_is_kept_as_unmet(said: str, folder: str | None, unmet: tuple) -> None:
    save = capture_save(said)
    assert save is not None and save.folder == folder and save.unmet == unmet


def test_a_known_folder_alone_leaves_nothing_unmet() -> None:
    assert capture_save("hazme una captura de pantalla y guárdala en el escritorio porfa").unmet == ()


def test_the_place_not_taken_reaches_the_writer_as_not_done() -> None:
    payload = compose_payload._compose_situation_payload(_situation(), "es", "toma una captura y guárdala en mi pendrive")
    assert payload["seen"]["storedPrivately"] is True
    assert payload["notDone"] == [{"action": "guardar la captura", "target": "mi pendrive"}]
    both = compose_payload._compose_situation_payload(_situation(**SAVED), "es", "toma una captura y guárdala en el escritorio y en documentos")
    assert both["seen"]["savedIn"] == "el Escritorio"
    assert both["notDone"] == [{"action": "guardar la captura", "target": "documentos"}]
    # Contracaso: a capture with nothing unmet carries no notDone.
    assert "notDone" not in compose_payload._compose_situation_payload(_situation(**SAVED), "es", "guárdala en el escritorio")


def test_a_final_that_loses_or_claims_the_place_not_taken_is_vetoed() -> None:
    payload = compose_payload._compose_situation_payload(_situation(), "es", "toma una captura y guárdala en mi pendrive")
    silent = "Tomé una captura de toda la pantalla y la guardé de forma privada en este dispositivo."
    claimed = "Tomé una captura de toda la pantalla y la guardé en tu pendrive."
    told = "Tomé una captura de toda la pantalla; quedó privada en este PC porque no pude guardarla en tu pendrive."
    assert payload_fact_checks._payload_fact_defect(silent, payload) == "capture_unmet_untold"
    assert payload_fact_checks._payload_fact_defect(claimed, payload) == "capture_unmet_untold"
    assert payload_fact_checks._payload_fact_defect(told, payload) == ""


def test_the_floor_says_the_place_not_taken() -> None:
    payload = compose_payload._compose_situation_payload(_situation(), "es", "toma una captura y guárdala en mi pendrive")
    final = deterministic_finals._deterministic_final(_situation(), payload, "toma una captura y guárdala en mi pendrive", "es")
    assert final == "Hice la captura de pantalla. No la guardé en «mi pendrive»."
    assert payload_fact_checks._payload_fact_defect(final, payload) == ""


def test_the_writer_is_asked_for_the_place_not_taken_and_the_persons_message_backs_a_restatement() -> None:
    told = "Tomé una captura de toda la pantalla, pero no la guardé en tu pendrive: quedó privada en este PC."
    client = Recorder([told])
    facts = {"situation": _situation()}
    assert client.compose_user_message(
        "Toma una captura de pantalla.", "status", facts, said="toma una captura y guárdala en mi pendrive",
    ) == told
    assert "mi pendrive" in client.payloads[0]["messages"][-1]["content"]


def test_a_chained_mission_with_a_capture_tells_the_place_not_taken_and_only_then() -> None:
    import json

    step = json.dumps(_situation())
    mission = {"kind": "operation", "cause": "mission_completed", "steps": [step]}
    said = "abre la calculadora, toma una captura y guárdala en mi pendrive"
    payload = compose_payload._compose_situation_payload(mission, "es", said)
    assert payload["notDone"] == [{"action": "guardar la captura", "target": "mi pendrive"}]
    # Contracaso: a mission with no capture step carries no capture keeping.
    other = {"kind": "operation", "cause": "mission_completed", "steps": [json.dumps({**_situation(), "operation": "app.open"})]}
    assert "notDone" not in compose_payload._compose_situation_payload(other, "es", said)


def test_the_place_not_taken_is_quoted_as_the_person_wrote_it() -> None:
    assert capture_save("toma una captura y guárdala en mi música").unmet == ("mi música",)
