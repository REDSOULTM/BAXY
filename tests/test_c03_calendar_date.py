"""The local calendar date survives the real UTC/offset composition contract."""
import json

import pytest

from baxy_mind.llm import (
    _compose_situation_payload,
    _payload_fact_defect,
    compose_visible_defect,
)


SITUATION = {
    "kind": "operation", "operation": "system.time", "polarity": "success",
    "verified": True, "succeeded": True,
    "observed": {"utc": "2026-09-07T01:04:11.4543673+00:00", "localUtcOffsetMinutes": -180},
}


@pytest.mark.parametrize("user_text", ["y la fecha?", "and the date?"])
def test_date_projection_uses_the_local_day_not_the_utc_day(user_text: str) -> None:
    payload = _compose_situation_payload(SITUATION, "es", user_text)
    assert payload["date"] == "2026-09-06"
    assert "clock" not in payload


def test_explicit_date_and_clock_keep_both_observed_fields() -> None:
    payload = _compose_situation_payload(SITUATION, "es", "fecha y hora")
    assert payload["date"] == "2026-09-06"
    assert payload["clock"] == "22:04"


def test_date_request_survives_the_completed_mission_step_projection() -> None:
    payload = _compose_situation_payload(
        {"kind": "status", "cause": "mission_completed", "polarity": "success",
         "steps": [SITUATION]}, "es", "y la fecha?",
    )
    facts = payload["completedStepsInOrder"][0]["resultAtThisStep"]
    assert facts["date"] == "2026-09-06"
    assert "clock" not in facts


@pytest.mark.parametrize("answer,valid", [
    ("Hoy es 2026-09-06.", True),
    ("Hoy es 6 de septiembre de 2026.", True),
    ("Es 6 de septiembre.", True),
    ("It is September 6, 2026.", True),
    ("It is 6 September 2026.", True),
    ("Hoy es 7 de septiembre de 2026.", False),
    ("Es 6 de octubre de 2026.", False),
    ("It is September 6, 2025.", False),
    ("Hoy es 2026-09-06, o 2026-09-07.", False),
    ("Son las 22:04.", False),
])
def test_calendar_facts_accept_natural_dates_and_reject_substitution(answer: str, valid: bool) -> None:
    facts = {"situation": json.dumps(SITUATION)}
    user_text = "and the date?" if answer.startswith("It is") else "y la fecha?"
    payload = _compose_situation_payload(SITUATION, "es", user_text)
    assert (compose_visible_defect(answer, "status", user_text, facts) == "") is valid
    assert (_payload_fact_defect(answer, payload) == "") is valid


def test_optional_clock_cannot_contradict_the_same_capture() -> None:
    facts = {"situation": json.dumps(SITUATION)}
    assert compose_visible_defect(
        "Hoy es 2026-09-06 y son las 23:04.", "status", "y la fecha?", facts,
    )
