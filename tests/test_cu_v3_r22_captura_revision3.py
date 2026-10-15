"""Ronda 22, revisión 3 de «captura-guardada-donde-se-pide».

Bloqueante (revisión 2, bloqueante 3): the parts not received were read for ANY single operation by its property names
only, so an operation that did the act itself was told it had not: computer use («en whatsapp escribe hola a mamá y
envíalo» → «No hice esto: «envíalo».» after a real send), a reply that sends its ``text``, a print over a
``documentId``, a volume raised by «súbelo». Now the reading is only for the operations the data declares as never
doing the act themselves, «sub» is an upload only toward a destination, and a time after «keep it on» is no place.
"""

from __future__ import annotations

import json

import pytest

from baxy_mind import compose_payload
from baxy_mind import deterministic_finals
from baxy_mind import payload_fact_checks
from baxy_mind.compose_facts import _with_unreceived_parts
from baxy_mind.semantic.acts_on_result import UnreceivedPart, read_for, unreceived_parts
from test_cu_v3_r22_captura_guardada import CAPTURE_SCHEMA, _situation


def _tool(operation: str, properties: dict) -> dict:
    return {"type": "function", "function": {
        "name": operation.replace(".", "_"), "canonical_name": operation,
        "parameters": {"type": "object", "properties": properties, "additionalProperties": False},
    }}


_STRING = {"type": "string"}
_TOOLS = {
    "mission.computer.use": _tool("mission.computer.use", {"application": _STRING, "goal": _STRING}),
    "email.latest.reply": _tool("email.latest.reply", {"text": _STRING}),
    "peripheral.print": _tool("peripheral.print", {"deviceId": _STRING, "documentId": _STRING}),
    "audio.volume.adjust": _tool("audio.volume.adjust", {"direction": _STRING}),
    "system.settings.adjust": _tool("system.settings.adjust", {"setting": _STRING, "direction": _STRING}),
    "bluetooth.radio.set": _tool("bluetooth.radio.set", {"state": _STRING}),
    "capture.screenshot": {"type": "function", "function": {
        "name": "capture_screenshot", "canonical_name": "capture.screenshot", "parameters": CAPTURE_SCHEMA}},
}


def _done(operation: str, observed: dict) -> dict:
    return {"kind": "operation", "operation": operation, "polarity": "success", "verified": True,
            "succeeded": True, "observed": observed}


@pytest.mark.parametrize(
    ("operation", "said", "observed"),
    [
        ("mission.computer.use", "en whatsapp escribe hola a mamá y envíalo",
         {"application": "WhatsApp", "reached": True, "steps": [{"action": "type", "text": "hola"},
                                                                {"action": "key", "key": "enter"}]}),
        ("mission.computer.use", "abre el bloc de notas, escribe hola y guárdalo en el escritorio",
         {"application": "Bloc de notas", "reached": True}),
        ("mission.computer.use", "abre el documento en word e imprímelo", {"application": "Word", "reached": True}),
        ("mission.computer.use", "en paint dibuja algo y guárdalo en documentos",
         {"application": "Paint", "reached": True}),
        ("email.latest.reply", "responde el último correo diciendo que llego tarde y envíalo", {}),
        ("peripheral.print", "abre el informe e imprímelo", {}),
        ("audio.volume.adjust", "el volumen está muy bajo, súbelo", {}),
        ("system.settings.adjust", "la pantalla está oscura, súbela", {}),
        ("bluetooth.radio.set", "turn on bluetooth and keep it on for an hour", {}),
    ],
)
def test_an_operation_that_may_do_the_act_itself_is_never_told_it_did_not(
    operation: str, said: str, observed: dict,
) -> None:
    facts = {"situation": json.dumps(_done(operation, observed))}
    assert not read_for(operation)
    assert _with_unreceived_parts(facts, said, _TOOLS) is facts


def test_computer_use_that_sent_keeps_the_base_final_and_the_honest_draft() -> None:
    said = "en whatsapp escribe hola a mamá y envíalo"
    facts = {"situation": json.dumps(_done("mission.computer.use", {
        "application": "WhatsApp", "reached": True,
        "steps": [{"action": "type", "text": "hola"}, {"action": "key", "key": "enter"}],
    }))}
    situation = _with_unreceived_parts(facts, said, _TOOLS)["situation"]
    situation = json.loads(situation) if isinstance(situation, str) else situation
    assert "unreceived" not in situation
    payload = compose_payload._compose_situation_payload(situation, "es", said)
    assert not any("envíalo" in str(item.get("target")) for item in payload.get("notDone") or [])
    final = deterministic_finals._deterministic_final(situation, payload, said, "es")
    assert "No hice esto" not in final
    assert payload_fact_checks._payload_fact_defect("Listo: en WhatsApp hice lo que pediste.", payload) != "unreceived_part_untold"


@pytest.mark.parametrize(
    "said",
    [
        "el volumen está muy bajo, súbelo",
        "la pantalla está oscura, súbela",
        "abre spotify y súbelo al máximo",
        "abre el reproductor y súbelo a 80",
        "turn on bluetooth and keep it on for an hour",
        "abre el documento y guárdalo hasta mañana",
    ],
)
def test_a_level_raised_or_a_time_kept_is_no_act_on_the_result(said: str) -> None:
    assert unreceived_parts(said, ["appId"]) == ()


@pytest.mark.parametrize(
    ("said", "parts"),
    [
        # Contracasos: an upload toward a destination and a keeping in a place are still read.
        ("toma una captura y súbela a la nube", (UnreceivedPart("upload", "súbela a la nube"),)),
        ("toma una captura y súbela a mi drive", (UnreceivedPart("upload", "súbela a mi drive"),)),
        ("take a screenshot and upload it", (UnreceivedPart("upload", "upload it"),)),
        ("abre el editor y guárdalo en el escritorio", (UnreceivedPart("keep", "guárdalo en el escritorio"),)),
    ],
)
def test_an_upload_toward_a_destination_is_still_read(said: str, parts: tuple) -> None:
    assert unreceived_parts(said, ["appId"]) == parts


def test_a_capture_still_tells_the_part_it_did_not_do() -> None:
    said = "toma una captura y mándala a mi jefe"
    assert read_for("capture.screenshot")
    facts = _with_unreceived_parts({"situation": json.dumps(_situation())}, said, _TOOLS)
    assert facts["situation"]["unreceived"] == [{"act": "send", "said": "mándala a mi jefe"}]
