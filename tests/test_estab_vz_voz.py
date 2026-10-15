"""Encargo VZ (imp3d imp-dc-voz, Normal): after «sí» to joining Cotele the same mission asked again, drafted from the
person's words: «¿Quieres confirmar que entres al canal Cotele en Discord o cancelar la acción?». An act that goes out
to the world (the App's pendingAction «worldAct» and «actName», RiskPolicy.WorldActOf) is asked in BAXY's first person
from data (operation_floor «worldActAsked»), before any draft."""

from __future__ import annotations

import json

from baxy_mind import operation_floor


def _pending(arguments: dict, **act: str) -> dict:
    # The situation of trace t2 (compose_audit.jsonl), with the act the App now names.
    return {
        "kind": "confirmation",
        "polarity": "pending",
        "cause": "step_needs_confirmation",
        "choices": ["confirmar", "confirm", "cancelar", "cancel"],
        "step": 1,
        "pendingRequest": "en Discord entrá al canal Cotele",
        "pendingAction": json.dumps({
            "operation": arguments.pop("operation", "input.visible.click"),
            "purpose": "Cumplir exactamente el efecto solicitado.",
            "arguments": arguments,
            **act,
        }, ensure_ascii=False),
    }


IMP3D_T2 = _pending(
    {"label": "Cotele!!!😎 (canal de voz), RED, duración de la llamada: 0 m ... vado (bloqueado)", "index": 29, "window": 919326},
    worldAct="call", actName="Cotele!!!😎",
)


def test_the_voice_channel_is_asked_in_baxys_first_person() -> None:
    said = operation_floor.pending_final(IMP3D_T2, False)
    assert said == "¿Quieres confirmar que entre en «Cotele!!!😎» o cancelar?"
    assert "entres" not in said
    assert operation_floor.pending_final(IMP3D_T2, True) == "Do you want to confirm that I join «Cotele!!!😎», or cancel?"
    assert operation_floor.tells_first(IMP3D_T2), "said from data before any draft"


def test_a_press_that_goes_out_names_its_control() -> None:
    situation = _pending({"label": "Iniciar Transmisión", "index": 46}, worldAct="broadcast", actName="Iniciar Transmisión")
    assert operation_floor.pending_final(situation, False) == "¿Quieres confirmar que pulse «Iniciar Transmisión» o cancelar?"


def test_every_family_of_the_data_has_its_question() -> None:
    families = {family["name"] for family in json.loads(
        (operation_floor._DATA.parent / "world_acts.v1.json").read_text(encoding="utf-8"))["families"]}
    asked = operation_floor.floor_data()["worldActAsked"]
    assert families <= set(asked)
    for family in families:
        assert all("{name}" in asked[family][language] for language in ("es", "en"))


def test_the_enter_on_a_message_box_keeps_its_own_question() -> None:
    # Enter over a message composer is family «send» with no name: the operation's own wording (encargo E) says it.
    situation = _pending({"operation": "input.key.press", "key": "enter", "target": "message_composer"},
                         worldAct="send", actName="")
    assert operation_floor.pending_final(situation, False) == "¿Quieres confirmar que envíe el mensaje o cancelar?"


def test_an_act_with_no_world_family_keeps_the_writer() -> None:
    assert operation_floor.pending_final(_pending({"label": "Eliminar", "index": 3}), False) == ""


def test_a_cancelled_world_act_is_not_said_as_a_question() -> None:
    cancelled = {
        "kind": "status",
        "cause": "remaining_steps_cancelled",
        "cancelledAction": json.loads(IMP3D_T2["pendingAction"]),
    }
    assert "confirmar" not in operation_floor.pending_final(cancelled, False)
