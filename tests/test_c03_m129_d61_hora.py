"""M129 — D61.1 (owner, 2026-10-02): an alarm, reminder or event at an hour of 1 to 12 said without its part of the
day is set for the next time that hour comes, without asking morning or afternoon («pon una alarma a las 7» at 15:00
is 19:00, at 05:00 it is 07:00; «a las 12» alike). The part of the day said («de la tarde», «pm»), a 24-hour clock or
the context still decide it; an hour that cannot exist is still asked. The reply says the time chosen, so the person
can correct it. It replaces the reviewed literals' morning-or-afternoon question (H0036, H0197, H0222, H0234, H0473,
H0119). Every phrasing here is our own.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind import llm
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic.dialogue import DialogueState
from baxy_mind.semantic.patterns import resolve_explicit_clarification_intent
from baxy_mind.semantic.reading import read
from baxy_mind.semantic.temporal import alarm_for_hour

LOCAL = timezone(timedelta(hours=-3))
OPERATIONS = ("notification.schedule", "reminder.create", "calendar.event.create", "notification.cancel.at",
              "task.create")


def _at(day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 10, day, hour, minute, tzinfo=LOCAL)  # Friday 2 October 2026


def _local(utc: str | None) -> datetime | None:
    return None if utc is None else datetime.fromisoformat(utc.replace("Z", "+00:00")).astimezone(LOCAL)


@pytest.mark.parametrize(
    ("value", "context", "now", "expected"),
    [
        ("a las 7", "pon una alarma a las 7", _at(2, 15), _at(2, 19)),
        ("a las 7", "pon una alarma a las 7", _at(2, 5), _at(2, 7)),
        ("a las 7", "pon una alarma a las 7", _at(2, 20), _at(3, 7)),
        ("a las 12", "pon una alarma a las 12", _at(2, 15), _at(3, 0)),
        ("a las 12", "pon una alarma a las 12", _at(2, 5), _at(2, 12)),
        ("at 8", "set an alarm for 8", _at(2, 15), _at(2, 20)),
        ("a las cinco", "recuérdame a las cinco sacar la basura", _at(2, 21), _at(3, 5)),
        ("a las 5 y media", "recuérdame a las 5 y media llamar al médico", _at(2, 15), _at(2, 17, 30)),
        # The day said keeps its day: the first time that hour comes on it.
        ("a las 7", "despiértame mañana a las 7", _at(2, 15), _at(3, 7)),
        # What was said still decides it.
        ("a las 7 de la tarde", "pon una alarma a las 7 de la tarde", _at(2, 5), _at(2, 19)),
        ("a las 7 pm", "pon una alarma a las 7 pm", _at(2, 5), _at(2, 19)),
        ("a las 19", "pon una alarma a las 19", _at(2, 5), _at(2, 19)),
        ("a las 7", "pon una alarma esta tarde a las 7", _at(2, 5), _at(2, 19)),
    ],
)
def test_the_next_time_that_hour_comes(value: str, context: str, now: datetime, expected: datetime) -> None:
    assert _local(sidecar._canonical_due_utc(value, context, now_utc=now)) == expected


@pytest.mark.parametrize(
    ("text", "operation"),
    [
        ("pon una alarma a las 7", "notification.schedule"),
        ("ponme la alarma a las 9", "notification.schedule"),
        ("set an alarm for 8", "notification.schedule"),
        ("despiértame a las 6", "notification.schedule"),
        ("recuérdame regar las plantas a las 5", "reminder.create"),
        ("recuérdame la junta de mañana a las cinco", "reminder.create"),
        ("agenda una reunión el lunes a las 3", "calendar.event.create"),
        ("reunirme con pablo mañana a las tres", "calendar.event.create"),
    ],
)
def test_the_hour_without_its_part_of_the_day_is_not_asked(text: str, operation: str) -> None:
    assert resolve_explicit_clarification_intent(text, OPERATIONS) is None
    reading = read(text, available_operations=OPERATIONS)
    assert reading.clarification is None
    assert reading.effects is not None and reading.effects.operations == (operation,)


@pytest.mark.parametrize(
    ("text", "missing"),
    [
        # No part of the day makes these exist: still asked.
        ("pon una alarma a las 99", "alarm_time"),
        ("pon una alarma a las 13 pm", "valid_hour_0_to_23"),
        # What the alarm is for is no hour.
        ("pon una alarma para una reunión", "alarm_time"),
    ],
)
def test_an_hour_that_cannot_be_one_is_still_asked(text: str, missing: str) -> None:
    asked = resolve_explicit_clarification_intent(text, OPERATIONS)
    assert asked is not None and missing in asked.missing_fields


@pytest.mark.parametrize(
    ("folded", "expected"),
    [
        ("set an alarm for 8", "at 8"),
        ("set an alarm for eight tomorrow", "at eight"),
        ("pon una alarma para 7", "a las 7"),
        ("set an alarm for 8 minutes", None),
        ("pon una alarma para una reunion", None),
        ("set an alarm for 8 am", None),
        ("set a timer for 8", None),
    ],
)
def test_the_hour_after_for_on_an_alarm(folded: str, expected: str | None) -> None:
    assert alarm_for_hour(folded) == expected


def test_the_arguments_carry_the_next_time_that_hour_comes() -> None:
    arguments = sidecar._explicit_arguments_from_evidence("notification.schedule", "set an alarm for 8")
    assert arguments is not None and arguments["dueUtc"] == "at 8"
    assert _local(sidecar._canonical_due_utc(arguments["dueUtc"], "set an alarm for 8", now_utc=_at(2, 9))) == _at(2, 20)


def test_an_event_starts_the_next_time_that_hour_comes_on_its_day() -> None:
    event = sidecar._explicit_calendar_event_arguments("agenda una reunión mañana de 3 a 4", now_utc=_at(2, 15))
    assert event is not None
    assert _local(event["startUtc"]) == _at(3, 3) and _local(event["endUtc"]) == _at(3, 4)


class _Model:
    """A turn read before the model: the decider is never asked."""

    _native_tool_policy_enabled = False

    def decide_in_context(self, *_a, **_k):
        raise AssertionError("the decider was not to be asked")

    def public_lookup_requested(self, _text):
        return False

    def _verify_semantic_effect_shape(self, _text):
        return "no_effect", "zero"

    def detect_response_language(self, _text):
        return "es"

    def consume_deferred_response_language(self, _text):
        return True, None

    def retire_deferred_response_language(self, _text):
        return None

    def __getattr__(self, name):
        def missing(*_a, **_k):
            raise RuntimeError(f"no {name} here")
        return missing


def _tool(name: str) -> dict:
    schema = {"type": "object", "properties": {}, "required": [], "additionalProperties": False}
    return {"type": "function", "function": {"name": name.replace(".", "_"), "canonical_name": name,
                                             "description": name, "risk": "low_reversible", "parameters": schema}}


@pytest.mark.parametrize(("text", "operation"), [("pon una alarma a las 7", "notification.schedule"),
                                                 ("set an alarm for 8", "notification.schedule")])
def test_the_turn_schedules_without_a_question(text: str, operation: str) -> None:
    tools = {name: _tool(name) for name in OPERATIONS}
    result = sidecar._prepare_turn_result(
        {"id": "m129", "text": text, "history": [{"role": "user", "content": text}]},
        llm=_Model(), planner_catalog=PlannerCatalog(list(tools.values())), encoder=lambda _t: (),
        tool_by_name=tools, dialogue_state=DialogueState(),
    )
    assert result["kind"] == "action" and result["effectOperations"] == [operation]


def test_the_reply_says_the_time_chosen() -> None:
    due = datetime(2026, 10, 2, 19, 0).astimezone()  # 19:00 on this machine's own clock face
    # «a las 7» for the 19:00 chosen would hide the choice: the composer is sent back.
    assert llm._scheduled_notification_defect("Listo, tu alarma suena a las 7.", [due]) != ""
    assert llm._scheduled_notification_defect("Listo, tu alarma suena a las 19:00.", [due]) == ""
