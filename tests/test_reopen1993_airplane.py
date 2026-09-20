"""REOPEN1957 H0107 «poneme el modo avión» (D11): el modo avión es todas las
radios apagadas por la API de radios de Windows, con postlectura de cada una;
la mente lo lee como system.settings.set airplane_mode."""

from __future__ import annotations

import pytest

from baxy_mind import __main__ as mind
from baxy_mind import effect_intent, llm

AVAILABLE = frozenset({"system.settings.set", "system.settings.status", "wifi.radio.set", "bluetooth.radio.set", "app.open"})
SCHEMA = {"type": "object", "properties": {"setting": {"type": "string"}, "value": {"type": "integer"}}, "required": ["setting", "value"], "additionalProperties": False}


@pytest.mark.parametrize(
    ("text", "value"),
    [("poneme el modo avión", 1), ("activá el modo avión", 1), ("turn on airplane mode", 1), ("apagá el modo avión", 0), ("quitá el modo avión", 0)],
)
def test_airplane_mode_orders_set_every_radio(text: str, value: int) -> None:
    intent = effect_intent.resolve_explicit_effects(text, AVAILABLE, (), ())
    assert intent is not None and intent.operations == ("system.settings.set",)
    assert effect_intent.airplane_mode_request(text) == value
    assert mind._ground_explicit_arguments("system.settings.set", text, SCHEMA) == {"setting": "airplane_mode", "value": value}
    assert effect_intent.operation_domain_is_grounded(text, "system.settings.set") is True


def test_a_question_about_airplane_mode_is_a_read() -> None:
    text = "está activado el modo avión?"
    intent = effect_intent.resolve_explicit_effects(text, AVAILABLE, (), ())
    assert intent is not None and intent.operations == ("system.settings.status",)
    assert effect_intent.airplane_mode_question(text) is True


def test_a_negation_and_the_old_limit() -> None:
    assert effect_intent.resolve_explicit_effects("no pongas el modo avión", AVAILABLE, (), ()) is None
    assert effect_intent.known_unsupported_effect_request("poneme el modo avión", {"app.open"}) is True


@pytest.mark.parametrize(
    ("text", "on", "defect"),
    [
        ("Activé el modo avión: todas las radios quedaron apagadas.", True, ""),
        ("El modo avión quedó desactivado.", True, "extra_claim"),
        ("El modo avión está desactivado; las radios siguen encendidas.", False, ""),
        ("Listo.", True, "missing_state"),
    ],
)
def test_the_reply_states_the_observed_airplane_mode(text: str, on: bool, defect: str) -> None:
    payload = {"operation": "system.settings.set", "seen": {"setting": "airplane_mode", "airplaneMode": on, "changed": True, "radios": []}}
    assert llm._payload_fact_defect(text, payload, "poneme el modo avión") == defect
