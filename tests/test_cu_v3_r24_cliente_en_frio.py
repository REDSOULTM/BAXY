"""Ronda 24 (uso real r23, palanca «cliente-en-frio-listo-por-interaccion»).

t1-c09#1 «mandale a Ron92 por discord que hoy no llego a jugar…», t2-c07#1 «… que llego en 10 min…» y t3-c07 t1
«mandale a ron92 por discord que ya voy saliendo…», con el cliente cerrado: el cliente se abrió en frío, la búsqueda
del chat se usó antes de que respondiera y ``message.recipient.resolve`` volvió con ``recipient_identity_not_verified``
y efecto observado. Sin hecho en el mapa de causas, el turno cayó en «No pude confirmar el resultado con «Ron92».»,
que insinúa un envío que nunca se intentó. Ahora el adaptador devuelve ``recipient_not_opened`` sin efecto cuando no
tocó ningún compositor, y la mente lo dice como hecho: no se abrió el chat, no se escribió ni envió nada.
"""

from __future__ import annotations

import json

import pytest

from baxy_mind import operation_floor
from baxy_mind import deterministic_finals
from baxy_mind import compose_situation

SAID = "mandale a Ron92 por discord que hoy no llego a jugar"


def _resolve_failed(error: str, uncertain: bool) -> dict:
    reason = {
        "kind": "operation", "operation": "message.recipient.resolve", "polarity": "failure", "verified": False,
        "succeeded": False, "error": error, "target": "Ron92",
        "attempted": {"channel": "discord", "recipient": "Ron92"},
        "notDone": [{"operation": "message.send", "target": "Ron92"}],
    }
    if uncertain:
        reason["cause"] = "external_effect_ambiguous"
        reason["effectUncertain"] = True
    return {"kind": "failure", "polarity": "failure", "cause": "mission_failed", "stepCount": 0, "steps": [],
            "reason": reason}


def test_the_unopened_chat_has_a_cause_fact_that_says_nothing_was_sent() -> None:
    assert compose_situation._cause_fact_key("recipient_not_opened") == "recipient_not_opened"
    fact = compose_situation._cause_in_prose("recipient_not_opened", "es")
    assert "no message was written or sent" in fact
    # The mind does not name the app: the fact is generic.
    for app in ("discord", "whatsapp", "telegram", "slack"):
        assert app not in fact.lower()


@pytest.mark.parametrize("recipient", ["Ron92", "ron92"])
def test_r23_cold_client_failure_is_not_said_as_an_unconfirmed_result(recipient: str) -> None:
    situation = json.loads(json.dumps(_resolve_failed("recipient_not_opened", uncertain=False)))
    situation["reason"]["target"] = recipient
    situation["reason"]["attempted"]["recipient"] = recipient
    situation["reason"]["notDone"][0]["target"] = recipient
    said = deterministic_finals._deterministic_final(situation, {}, SAID, "es")
    assert "confirmar" not in said
    assert said.startswith(f"No pude enviar el mensaje a «{recipient}»")
    assert said.endswith(", porque " + operation_floor.failure_family_cause("recipient_not_opened", False) + ".")
    english = deterministic_finals._deterministic_final(situation, {}, "tell Ron92 on discord I can't play today", "en")
    assert "confirm" not in english
    assert english.endswith(", because " + operation_floor.failure_family_cause("recipient_not_opened", True) + ".")


def test_the_family_cause_names_no_app() -> None:
    for english in (False, True):
        cause = operation_floor.failure_family_cause("recipient_not_opened", english)
        assert cause
        assert "discord" not in cause.lower() and "whatsapp" not in cause.lower()


def test_contracase_a_resolve_that_may_have_typed_near_a_composer_stays_uncertain() -> None:
    # The flow typed where a conversation's composer may have taken the text: still «could not confirm», never
    # «nothing was written».
    situation = _resolve_failed("recipient_identity_not_verified", uncertain=True)
    said = deterministic_finals._deterministic_final(situation, {}, SAID, "es")
    assert ", porque" not in said
    assert compose_situation._cause_fact_key("recipient_identity_not_verified") is None


def test_contracase_an_attempted_send_not_verified_stays_unverified() -> None:
    # message.send was attempted and its delivery not seen: it may have gone out, so it is said as unconfirmed.
    send = {
        "kind": "operation", "operation": "message.send", "polarity": "failure", "verified": False,
        "succeeded": False, "error": "message_delivery_not_verified", "cause": "external_effect_ambiguous",
        "effectUncertain": True, "target": "Ron92", "attempted": {"recipientId": "recipient_1", "text": "hola"},
    }
    situation = {"kind": "failure", "polarity": "failure", "cause": "mission_failed", "stepCount": 0, "steps": [],
                 "reason": send}
    said = deterministic_finals._deterministic_final(situation, {}, SAID, "es")
    assert "no pude confirmar" in said.lower()
    assert "no se pudo abrir el chat" not in said
