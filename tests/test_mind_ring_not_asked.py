"""ALR9 (VIVO9; banco de ALR7: «todavía no la apagues» stopped what rang 9 of 18, every time by the model's own call,
never by the acknowledgement rule): the model's stop or snooze of what rings runs only when the person's words, read by
the model in a closed question of their own (Mind._ring_not_asked, as SIS3 reads a «sí»), ask to stop or snooze it."""
import json
from pathlib import Path

from baxy_mind.mind import RING_NOT_ASKED, RING_READ_GRAMMAR, RING_READ_SYSTEM
from test_mind_final import _call, _mind, _say

ALARM = {"id": "89abcdef", "kind": "alarm", "title": "sal a trabajar", "clock": "07:00"}
CAPABILITY = {"capabilities": [{"name": "schedule.alarms", "description": "Alarms.", "risk": "low_reversible",
                                "argumentsSchema": {"type": "object", "properties": {"action": {"type": "string"}}}}]}


def _read_as(server, kind: str) -> None:
    """The closed question answers ``kind`` whatever the scripted model proposed."""
    def ask_apart(body: dict, timeout: float = 60.0) -> dict:
        server.closed.append(json.loads(json.dumps(body)))
        return {"choices": [{"message": {"content": kind}}]}
    server.ask_apart = ask_apart


def test_a_stop_the_words_do_not_ask_for_is_held_and_it_keeps_ringing(tmp_path: Path) -> None:
    mind, server = _mind(tmp_path, [_call("schedule_alarms", {"action": "stop", "id": "89abcdef"}),
                                    _say("Vale, la dejo sonar."),
                                    _say("Vale, la dejo sonar.")])
    mind.configure(CAPABILITY)
    _read_as(server, "seguir")
    result = mind.decide(1, "Todavía no la apagues.", None, None, None, None, [ALARM])
    assert result["kind"] != "action" and result["reply"] == "Vale, la dejo sonar."
    told = [m["content"] for m in server.bodies[1]["messages"] if m.get("role") == "tool"]
    assert told and told[-1].startswith(RING_NOT_ASKED)
    closed = server.closed[0]
    assert closed["messages"][0]["content"] == RING_READ_SYSTEM and closed["grammar"] == RING_READ_GRAMMAR
    assert "«Todavía no la apagues.»" in closed["messages"][1]["content"]
    assert "la alarma id 89abcdef «sal a trabajar» de las 07:00" in closed["messages"][1]["content"]


def test_a_stop_the_words_ask_for_runs_as_before(tmp_path: Path) -> None:
    mind, server = _mind(tmp_path, [_call("schedule_alarms", {"action": "stop", "id": "89abcdef"})])
    mind.configure(CAPABILITY)
    _read_as(server, "parar")
    result = mind.decide(1, "Ya me levanté, apágala de una vez.", None, None, None, None, [ALARM])
    assert result["kind"] == "action" and result["arguments"] == {"action": "stop", "id": "89abcdef"}


def test_a_snooze_read_as_snooze_runs_and_one_read_as_something_else_is_held(tmp_path: Path) -> None:
    mind, server = _mind(tmp_path, [_call("schedule_alarms", {"action": "snooze", "id": "89abcdef"})])
    mind.configure(CAPABILITY)
    _read_as(server, "posponer")
    assert mind.decide(1, "Déjame dormir un ratito más, porfa.", None, None, None, None, [ALARM])["kind"] == "action"
    mind, server = _mind(tmp_path, [_call("schedule_alarms", {"action": "snooze", "id": "89abcdef"}),
                                    _say("¿Quieres que la ponga más bajita?"),
                                    _say("¿Quieres que la ponga más bajita?")])
    mind.configure(CAPABILITY)
    _read_as(server, "otra")
    assert mind.decide(1, "¿La puedes poner más bajita?", None, None, None, None, [ALARM])["kind"] != "action"


def test_an_unreadable_answer_holds_it(tmp_path: Path) -> None:
    mind, server = _mind(tmp_path, [_call("schedule_alarms", {"action": "stop", "id": "89abcdef"}), _say("Sigue sonando."),
                                    _say("Sigue sonando.")])
    mind.configure(CAPABILITY)
    _read_as(server, "quizá")
    assert mind.decide(1, "uff no sé", None, None, None, None, [ALARM])["kind"] != "action"
    # ALR9C: the labels are Spanish (parar, posponer, seguir, otra): an English word is no kind, and holds it too.
    mind, server = _mind(tmp_path, [_call("schedule_alarms", {"action": "stop", "id": "89abcdef"}), _say("Sigue sonando."),
                                    _say("Sigue sonando.")])
    mind.configure(CAPABILITY)
    _read_as(server, "stop")
    assert mind.decide(1, "uff no sé", None, None, None, None, [ALARM])["kind"] != "action"
    assert server.closed[0]["grammar"] == 'root ::= "parar" | "posponer" | "seguir" | "otra"'


def test_the_acknowledgement_rule_and_the_other_actions_never_ask_it(tmp_path: Path) -> None:
    mind, server = _mind(tmp_path, [])
    mind.configure(CAPABILITY)
    _read_as(server, "seguir")
    assert mind.decide(1, "Gracias.", None, None, None, None, [ALARM])["kind"] == "action"  # ring_answer
    mind, server = _mind(tmp_path, [_call("schedule_alarms", {"action": "create", "title": "x", "inMinutes": 5})])
    mind.configure(CAPABILITY)
    _read_as(server, "seguir")
    assert mind.decide(1, "y ponme otra en cinco minutos", None, None, None, None, [ALARM])["kind"] == "action"
    assert server.closed == []
