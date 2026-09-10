"""Named noon/midnight values preserve facts through both composition gates."""
import json

import pytest

from baxy_mind import llm


def _situation(clock):
    return {"kind": "status", "polarity": "success", "operation": "system.time",
            "observed": {"utc": f"2026-09-10T{clock}:00Z", "localUtcOffsetMinutes": 0}}


@pytest.mark.parametrize("gate", ["payload", "visible"])
@pytest.mark.parametrize("clock, reply", [
    ("12:00", "Son las 12 del mediodía."),
    ("12:00", "Son las doce del mediodía."),
    ("12:00", "Es mediodía."),
    ("12:00", "Mediodía."),
    ("12:00", "It is noon."),
    ("12:00", "It's noon."),
    ("12:00", "The local time is noon."),
    ("12:00", "12 noon."),
    ("00:00", "Es medianoche."),
    ("00:00", "Medianoche."),
    ("00:00", "Son las doce de la noche."),
    ("00:00", "It is midnight."),
    ("00:00", "The time is midnight."),
    ("00:00", "12 midnight."),
    ("00:00", "The time is 12:00 AM."),
    ("12:00", "The time is 12:00 PM."),
])
def test_named_clock_preserves_the_observation(gate, clock, reply):
    situation = _situation(clock)
    if gate == "payload":
        defect = llm._payload_fact_defect(reply, llm._compose_situation_payload(situation, "es"))
    else:
        english = any(word in reply for word in ("noon", "midnight", "The time"))
        question = "What time is it?" if english else "¿Qué hora es?"
        defect = llm.compose_visible_defect(reply, "status", question, {"situation": json.dumps(situation)})
    assert defect == ""


@pytest.mark.parametrize("reply", [
    "No es mediodía.", "No son las doce del mediodía.", "No es medianoche.",
    "Antes del mediodía.", "Después del mediodía.", "A medianoche.",
    "La reunión es al mediodía.", "When it is midnight.",
    "Son las once del mediodía.", "Es casi mediodía.",
    "Es mediodía y cinco.", "It is five past noon.",
    "No es medianoche o mediodía.", "Es mediodía menos cinco.",
])
@pytest.mark.parametrize("clock", ["12:00", "00:00"])
def test_non_exact_or_non_asserted_named_time_does_not_supply_a_clock(reply, clock):
    assert llm._payload_fact_defect(reply, {"clock": clock})


@pytest.mark.parametrize("reply", [
    "Son las 12:00 o medianoche.", "Es mediodía, o medianoche.",
    "It is 12:00 PM or midnight.", "Es medianoche; son las 12:00.",
])
@pytest.mark.parametrize("clock", ["12:00", "00:00"])
def test_every_asserted_clock_value_must_agree(reply, clock):
    assert llm._payload_fact_defect(reply, {"clock": clock}) == "reversed_result"


@pytest.mark.parametrize("clock, reply", [
    ("12:01", "Es mediodía."), ("00:01", "It is midnight."),
    ("00:00", "The time is 12:00 PM."), ("12:00", "The time is 12:00 AM."),
])
def test_named_times_do_not_erase_minutes_or_half_of_day(clock, reply):
    assert llm._payload_fact_defect(reply, {"clock": clock})


def test_date_only_response_still_rejects_an_added_wrong_named_time():
    situation = _situation("12:00")
    facts = {"situation": json.dumps(situation)}
    assert llm.compose_visible_defect(
        "Hoy es 10 de septiembre de 2026; es medianoche.", "status", "¿Qué fecha es?", facts,
    ) == "reversed_result"
