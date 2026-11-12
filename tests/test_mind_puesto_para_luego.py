"""ALR5 (B7): an alarm or reminder just set was told «Te he recordado que llames al veterinario en media hora», as if the
person had been reminded already. The facts line of a completed call whose result is set for later (its scheduledFor)
says that it has not rung yet; a snooze's result, of one that did ring, does not."""

import json

from baxy_mind.mind import SET_FOR_LATER, _outcome


def _set(**observed: object) -> str:
    return json.dumps({"status": "completed", "verification": "readback", "observed": {
        "version": 1, "kind": "reminder", "title": "Llamar al veterinario", "dueLocal": "2026-11-09 14:51",
        "scheduledFor": "today", **observed}})


def test_one_set_for_later_is_told_it_has_not_rung_yet() -> None:
    assert _outcome(_set()).endswith(SET_FOR_LATER)
    assert "no ha sonado" in SET_FOR_LATER


def test_a_snooze_and_a_call_with_nothing_set_for_later_are_not() -> None:
    assert SET_FOR_LATER not in _outcome(_set(snoozed=True, ringing=False))
    done = json.dumps({"status": "completed", "verification": "readback", "observed": {"ok": True}})
    assert SET_FOR_LATER not in _outcome(done)
    failed = json.dumps({"status": "failed", "error": "notification_schedule_invalid",
                         "observed": {"scheduledFor": "today"}})
    assert SET_FOR_LATER not in _outcome(failed)
