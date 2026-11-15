"""INT37B (VIVO22, 14-11: «Borra la de las 10:00.» 0 of 15 in the App, 19-20 of 20 in INT36G's bench): the bench's figure
was the routine just made in the same conversation; in the App each try is a new conversation, and there the model reads
nothing of the routines kept (only the mind has them, from the App's turn.decide). It goes to schedule_alarms, whose
result in the App says no alarm («notification_clock_not_found»), and says there is nothing to delete.

The conversation of the App, as INT37B's proxy recorded it: two routines kept as the App writes them («10:00» on Mondays,
Wednesdays and Fridays, «20:00» on Saturdays), a new conversation, the model's schedule_alarms cancel at 10:00 and the
App's result word for word. Beside that result the routines at a time are said (INT36G 8662a7ec8, measured here in the
App: Completo asks about the right one 5 of 5); then BAXY asked, the person said «No.», the model called baxy_routines
and the closed read took «No.» for «turn_off» 5 of 5 («¿Desactivo esta rutina…?»): a no now has its own value, and BAXY
leaves the routines as they are."""
from __future__ import annotations

import json
from pathlib import Path

from baxy_mind import routine_fill
from test_mind_final import _call
from test_mind_int36g_rutina_por_hora import _opened
from test_mind_routine_guide import _guide_mind

MORNING = "Buenos días, Leonor, que tengas un gran día"
# RoutinesHandler's store as the App wrote it in INT37B's run (routines-store\routines.v1.json), ids and times invented
TEN = {"id": "r-3a1d09", "name": "10:00", "active": True, "createdUtc": "2026-11-15T02:59:32Z",
       "trigger": {"at": "10:00", "repeat": "days", "days": ["mon", "wed", "fri"]}, "steps": [{"say": MORNING}],
       "changedUtc": "2026-11-15T02:59:32Z"}
EIGHT = {"id": "r-126adc", "name": "20:00", "active": True, "createdUtc": "2026-11-15T02:59:38Z",
         "trigger": {"at": "20:00", "repeat": "days", "days": ["sat"]}, "steps": [{"say": "hora de sacar la basura»"}],
         "changedUtc": "2026-11-15T02:59:38Z"}
# WindowsScheduledNotificationAdapter's result for a cancel at a time no alarm has (INT37B's proxy, word for word)
NO_CLOCK = json.dumps({"status": "failed", "error": "notification_clock_not_found"})


def test_in_a_new_conversation_the_alarm_result_says_their_routine_at_that_time(tmp_path: Path) -> None:
    mind, server = _guide_mind(tmp_path, [_call("schedule_alarms", {"action": "cancel", "at": "10:00"}),
                                          {"choices": [{"message": {"content": "Listo."}}]}], [TEN, EIGHT])
    mind.new_session([])
    mind.decide(1, "Borra la de las 10:00.")
    # what the model read before its call: nothing of the routines (the cause; INT37B's proxy, the App's request)
    first = json.dumps(server.bodies[0]["messages"], ensure_ascii=False)
    assert MORNING not in first
    mind.continue_turn(2, NO_CLOCK)
    facts = [m["content"] for m in server.bodies[-1]["messages"] if m["role"] == "tool"][-1]
    assert "notification_clock_not_found" in facts and "baxy_routines" in facts
    # all the tool does to them: asked to pause one, the 4B offered to delete it while this said «changes and deletes»
    assert "las cambia, las desactiva y las borra" in facts
    assert "«10:00»: los lunes, miércoles y viernes a las 10:00" in facts and MORNING in facts


def test_their_no_to_the_question_about_one_leaves_their_routines(tmp_path: Path) -> None:
    mind, server = _opened(tmp_path, [{"a": "no"}], routines=[TEN, EIGHT])
    left = mind.decide(1, "No.")
    assert left["kind"] == "conversation" and left["operation"] is None
    assert left["reply"] == "Listo, lo dejo." and mind._guide is None
    assert len(server.have_asked) == 1


def test_a_no_is_a_value_of_the_closed_read() -> None:
    body = routine_fill.have_body([TEN, EIGHT], "No.", "es", 0)
    assert "no" in body["response_format"]["json_schema"]["schema"]["properties"]["a"]["enum"]
    assert "no (" in body["messages"][0]["content"]
    assert routine_fill.have_parsed({"choices": [{"message": {"content": '{"a": "no"}'}}]}, ["10:00", "20:00"]) == ("no", [])


def _listed_facts(tmp_path: Path, said: str) -> str:
    mind, server = _guide_mind(tmp_path, [_call("schedule_alarms", {"action": "list"}),
                                          {"choices": [{"message": {"content": "Listo."}}]}], [TEN, EIGHT])
    mind.new_session([])
    mind.decide(1, said)
    mind.continue_turn(2, json.dumps({"status": "completed", "verification": "unchanged", "observed": {
        "version": 1, "count": 0, "notifications": [], "ringingNow": [], "staleTaskCount": 0, "resultLimit": 20,
        "resultsMayBeTruncated": False, "changed": False}}))
    return [m["content"] for m in server.bodies[-1]["messages"] if m["role"] == "tool"][-1]


def test_the_time_they_wrote_that_is_one_routines_is_said_beside_it(tmp_path: Path) -> None:
    """Esencial in the App: the 4B listed the alarms, read both routines and asked «¿las quieres eliminar?» 5 of 5."""
    facts = _listed_facts(tmp_path, "Borra la de las 10:00.")
    assert "«20:00»: los sábados" in facts
    assert facts.endswith("; la hora que escribió la persona, 10:00, es la de su rutina «10:00»]")


def test_a_time_in_words_or_of_no_routine_adds_nothing(tmp_path: Path) -> None:
    for said in ("Borra la de las diez de la mañana.", "Borra la de las 9:30.", "borra la de las 110:00"):
        assert "escribió la persona" not in _listed_facts(tmp_path / said[-6:].strip(".:"), said)
