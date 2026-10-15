"""v3 r6 lectores, tanda t2-r4 c15: «turn bluetooth on, gonna connect my headphones» con el Bluetooth ya encendido.

El adaptador no tocó la radio (ya estaba encendida), su lectura posterior la vio encendida y el Core lo convertía en
«the change could not be observed». Ahora es el pedido hecho con ``changed:false``: la mente lo dice como «ya estaba
encendido», nunca como «lo encendí», y el suelo de la App y de la mente dice lo mismo. Contracaso: una radio que sí
cambió se cuenta como cambiada.
"""

from __future__ import annotations

import pytest

from baxy_mind.compose_payload import _compose_situation_payload
from baxy_mind.payload_fact_checks import _payload_fact_defect


def _situation(operation: str, state: bool, changed: bool) -> dict:
    return {
        "kind": "operation",
        "operation": operation,
        "polarity": "success",
        "verified": True,
        "succeeded": True,
        "observed": {
            "version": 1, "state": state, "changed": changed, "radioCount": 1,
            "authority": "windows_radio_api_postread",
        },
    }


@pytest.mark.parametrize("operation", ["bluetooth.radio.set", "wifi.radio.set"])
def test_a_radio_already_in_state_is_a_fact_the_reply_carries(operation: str) -> None:
    payload = _compose_situation_payload(_situation(operation, True, False), "es", "prende el bluetooth")
    assert payload["seen"]["alreadyInState"] is True


def test_a_switched_radio_is_not_told_as_already_there() -> None:
    payload = _compose_situation_payload(_situation("bluetooth.radio.set", True, True), "es", "prende el bluetooth")
    assert "alreadyInState" not in payload.get("seen", {})
    assert payload["seen"]["radioOn"] is True


@pytest.mark.parametrize(
    ("reply", "defect"),
    [
        ("El Bluetooth ya estaba encendido.", ""),
        ("Bluetooth was already on.", ""),
        # Revisión adversarial: el estado dicho en pasiva o como adjetivo no es un cambio.
        ("Bluetooth was already turned on.", ""),
        ("Bluetooth is already switched on.", ""),
        ("Bluetooth was already active.", ""),
        ("I switched it on.", "extra_claim"),
        ("Activé el Bluetooth.", "extra_claim"),
        # A change that did not happen, and a reply that hides that nothing changed.
        ("Encendí el Bluetooth.", "extra_claim"),
        ("I turned Bluetooth on.", "extra_claim"),
        ("Listo, el Bluetooth está encendido.", "missing_state"),
    ],
)
def test_the_reply_says_it_already_was_and_claims_no_switch(reply: str, defect: str) -> None:
    payload = _compose_situation_payload(
        _situation("bluetooth.radio.set", True, False), "es", "turn bluetooth on, gonna connect my headphones",
    )
    assert _payload_fact_defect(reply, payload, "turn bluetooth on, gonna connect my headphones") == defect
