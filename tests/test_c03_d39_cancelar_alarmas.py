"""D39 (owner's decision, 2026-09-29; v3d-final F-s040 «Cancela las alarmas, por favor.» → «¿Qué alarma deseas
cancelar?», request 253, decision path ``explicit_clarification``, missing ``which_alarm``).

The alarms named in the plural without saying which are read first (notification.list), and BAXY offers to cancel them
with the list: «Tienes 3 alarmas (7:00, 8:30 y 12:00). ¿Las cancelo todas?». Only a yes cancels them, each one by its
verified local clock (one notification.cancel.at per alarm, said with its part of the day so 7:00 is never 19:00);
with a single alarm BAXY names it and asks; with none it says so. This replaces the plural branch of the which-alarm
clarification of uso real 2026-09-24; a plural that says which alarms («de la mañana», «for tomorrow») is still asked.
"""

from __future__ import annotations

import copy
import json
from datetime import datetime, timedelta, timezone

import pytest

from baxy_mind import __main__ as mind
from baxy_mind.llm import LlmRuntime, _compose_situation_payload, _deterministic_final, _payload_fact_defect
from baxy_mind.semantic.dialogue import DialogueState
from baxy_mind.semantic.patterns import resolve_explicit_clarification_intent, resolve_explicit_effects
from baxy_mind.semantic.temporal import assents_to_alarm_offer, plural_alarm_cancellation

F_S040 = "Cancela las alarmas, por favor."
OPERATIONS = (
    "notification.list", "notification.cancel.at", "notification.cancel.latest", "notification.schedule",
    "reminder.create", "reminder.list",
)
LIST_SCHEMA = {
    "type": "object", "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 50}},
    "required": [], "additionalProperties": False,
}
CANCEL_AT = {
    "type": "object",
    "properties": {
        "hour": {"type": "integer", "minimum": 0, "maximum": 23},
        "kind": {"type": "string", "enum": ["alarm", "reminder"]},
        "minute": {"type": "integer", "minimum": 0, "maximum": 59},
        "period": {"type": "string", "enum": ["am", "pm"]},
    },
    "required": ["hour", "kind"],
    "additionalProperties": False,
}


def _tomorrow_utc(hour: int, minute: int) -> str:
    local = (datetime.now().astimezone() + timedelta(days=1)).replace(hour=hour, minute=minute, second=0, microsecond=0)
    return local.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _alarms_read(*clocks: tuple[int, int]) -> dict:
    """A verified notification.list as the provider writes it: these alarms tomorrow, and a reminder beside them."""

    notifications = [
        {"kind": "alarm", "title": "alarma", "nextRunUtc": _tomorrow_utc(hour, minute), "state": "Ready"}
        for hour, minute in clocks
    ] + [{"kind": "reminder", "title": "pagar la luz", "nextRunUtc": _tomorrow_utc(18, 0), "state": "Ready"}]
    return {
        "kind": "operation", "operation": "notification.list", "polarity": "success", "verified": True,
        "succeeded": True,
        "observed": {
            "version": 1, "count": len(notifications), "notifications": notifications, "staleTaskCount": 0,
            "resultLimit": 20, "resultsMayBeTruncated": False,
            "authority": "windows_task_scheduler_notification_list_postread",
        },
    }


def _payload(situation: dict, request: str = F_S040, language: str = "es") -> dict:
    # M62: the payload the composer gets for the offer (alarms alone, their number and whether all can be offered).
    return _compose_situation_payload(situation, language, request)


class _Writer(LlmRuntime):
    def __init__(self, drafts: list[str]) -> None:
        self._gguf = None
        self.drafts = list(drafts)
        self.requests: list[dict] = []

    def _post(self, payload: dict, **_kwargs: object) -> dict:
        self.requests.append(copy.deepcopy(payload))
        return {"choices": [{"message": {"content": self.drafts.pop(0)}, "finish_reason": "stop"}]}


# ------------------------------------------------------------------ the request is read, not asked


@pytest.mark.parametrize("text", [F_S040, "quita todas mis alarmas", "cancel my alarms", "Borra las alarmas"])
def test_alarms_in_the_plural_without_which_are_read(text: str) -> None:
    assert plural_alarm_cancellation(text)
    assert resolve_explicit_clarification_intent(text, OPERATIONS) is None
    effects = resolve_explicit_effects(text, OPERATIONS)
    assert effects is not None and effects.operations == ("notification.list",)
    # M62 (v3e2-final F-s040: the read held 20 of 38 notifications, «resultsMayBeTruncated»): the offer of every alarm
    # reads as many as the catalog lets it.
    assert mind._ground_explicit_arguments("notification.list", text, LIST_SCHEMA) == {"limit": 50}


@pytest.mark.parametrize(
    "text", ["delete my alarms for tomorrow", "apaga mis alarmas de la mañana tras el viernes", "remove my early alarms"],
)
def test_a_plural_that_says_which_alarms_is_still_asked(text: str) -> None:
    assert not plural_alarm_cancellation(text)
    asked = resolve_explicit_clarification_intent(text, OPERATIONS)
    assert asked is not None and asked.missing_fields == ("which_alarm",)


# ------------------------------------------------------------------ the offer, with the list


def test_the_offer_names_every_alarm_and_asks() -> None:
    situation = _alarms_read((7, 0), (8, 30), (12, 0))
    payload = _payload(situation)
    good = "Tienes 3 alarmas para mañana (07:00, 08:30 y 12:00). ¿Las cancelo todas?"
    assert _payload_fact_defect(good, payload, F_S040) == ""
    assert _payload_fact_defect("Cancelé tus 3 alarmas.", payload, F_S040) == "effect_claim"
    assert _payload_fact_defect("Tienes 3 alarmas: 07:00, 08:30 y 12:00.", payload, F_S040) == "alarm_offer_missing"
    assert _payload_fact_defect("Tienes 3 alarmas (07:00 y 08:30). ¿Las cancelo?", payload, F_S040) == (
        "alarm_offer_missing"
    )
    writer = _Writer([good])
    assert writer.compose_user_message(F_S040, "status", {"situation": json.dumps(situation)}) == good
    assert "¿Las cancelo todas?" in json.dumps(writer.requests[0]["messages"], ensure_ascii=False)


def test_with_no_draft_the_offer_is_said_from_the_read() -> None:
    situation = _alarms_read((7, 0), (8, 30), (12, 0))
    writer = _Writer(["Cancelé tus alarmas."] * 3)
    assert writer.compose_user_message(F_S040, "status", {"situation": json.dumps(situation)}) == (
        "Tienes 3 alarmas (07:00 mañana, 08:30 mañana y 12:00 mañana). ¿Las cancelo todas?"
    )


def test_one_alarm_is_named_and_none_is_said() -> None:
    one = _alarms_read((7, 0))
    assert _deterministic_final(one, _payload(one), F_S040, "es") == "Tienes una alarma, a las 07:00 mañana. ¿La cancelo?"
    none = _alarms_read()
    assert _deterministic_final(none, _payload(none), F_S040, "es") == "No tienes alarmas programadas."
    english = _alarms_read((7, 0), (19, 5))
    assert _deterministic_final(english, _payload(english, "cancel my alarms", "en"), "cancel my alarms", "en") == (
        "You have 2 alarms (07:00 tomorrow and 19:05 tomorrow). Shall I cancel them all?"
    )


# ------------------------------------------------------------------ only the yes cancels, each by its clock


def _offered(situation: dict, request: str = F_S040) -> DialogueState:
    state = DialogueState()
    state.expect(request, ["notification.list"])
    state.record(situation)
    return state


@pytest.mark.parametrize("answer", ["sí", "Sí, cancélalas todas.", "dale", "sí, todas"])
def test_the_yes_cancels_each_alarm_read(answer: str) -> None:
    state = _offered(_alarms_read((7, 0), (8, 30), (12, 0), (19, 5)))
    request = state.accepted_alarm_cancellation(answer)
    assert request == (
        "cancela la alarma de las 7:00 de la mañana y cancela la alarma de las 8:30 de la mañana y "
        "cancela la alarma de las 12:00 de la tarde y cancela la alarma de las 19:05"
    )
    effects = resolve_explicit_effects(request, OPERATIONS)
    assert effects is not None and effects.operations == ("notification.cancel.at",) * 4
    assert [mind._ground_explicit_arguments("notification.cancel.at", clause, CANCEL_AT) for clause in effects.evidence] == [
        {"hour": 7, "kind": "alarm", "period": "am"},
        {"hour": 8, "kind": "alarm", "minute": 30, "period": "am"},
        {"hour": 12, "kind": "alarm", "period": "pm"},
        {"hour": 19, "kind": "alarm", "minute": 5},
    ]


def test_the_yes_in_english_and_a_minute_with_its_zero() -> None:
    state = _offered(_alarms_read((0, 5), (6, 45)), "cancel my alarms")
    request = state.accepted_alarm_cancellation("yes, all of them")
    assert request == "cancel the alarm at 12:05 am and cancel the alarm at 6:45 am"
    effects = resolve_explicit_effects(request, OPERATIONS)
    assert effects is not None
    assert [mind._ground_explicit_arguments("notification.cancel.at", clause, CANCEL_AT) for clause in effects.evidence] == [
        {"hour": 12, "kind": "alarm", "minute": 5, "period": "am"},
        {"hour": 6, "kind": "alarm", "minute": 45, "period": "am"},
    ]


@pytest.mark.parametrize("answer", ["no", "solo la de las 7", "¿cuáles son?", "mejor no"])
def test_anything_but_the_yes_cancels_nothing(answer: str) -> None:
    assert not assents_to_alarm_offer(answer)
    assert _offered(_alarms_read((7, 0), (8, 30))).accepted_alarm_cancellation(answer) is None


def test_the_offer_lasts_one_turn_and_needs_an_alarm_read() -> None:
    state = _offered(_alarms_read((7, 0), (8, 30)))
    state.expect("¿qué hora es?", ["system.time"])
    assert state.accepted_alarm_cancellation("sí") is None
    assert _offered(_alarms_read()).accepted_alarm_cancellation("sí") is None
    # A listing asked as a listing offers nothing.
    assert _offered(_alarms_read((7, 0)), "¿qué alarmas tengo?").accepted_alarm_cancellation("sí") is None
    # More alarms than a plan holds (eight steps) are not cancelled in one yes.
    many = _offered(_alarms_read(*((hour, 0) for hour in range(6, 15))))
    assert many.accepted_alarm_cancellation("sí") is None
