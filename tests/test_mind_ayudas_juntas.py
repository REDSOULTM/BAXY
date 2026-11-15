"""INT36E: the form aids of the 1.5.3 in one turn. «power_unnamed» and «said_days» each look at one tool (a
system_power shutdown, a schedule_alarms create), so one call meets at most one of them; «mostrar» is the answer
check's. INT36F: «screen_unnamed» left the 1.5.3 (it lost a real request, BAN2 b2p-10, 10 of 10; leader's decision of
14-11, 12:55): a display_monitor_set runs as written again. When two hold calls of the same turn, each is held once, the second result
carries the line of the first (TURN_FACTS: one account of what did not run), and the model reads at most one data
per call: no loop, one more round per aid that held."""
import json
import re
from pathlib import Path

from baxy_mind import harness_language
from test_mind_final import _call, _mind, _say

FAILED = [{"role": "user", "content": "Cierra Velmora"},
          {"role": "assistant", "content": "No pude cerrar Velmora: sigue abierto en segundo plano."}]
BELOW_OFF = {"active": False, "monitor": "below"}
SHUTDOWN = {"action": "shutdown"}
DAILY = {"action": "create", "kind": "reminder", "at": "07:00", "recurrence": "daily", "title": "Llamar a mamá"}
ACCENTS = re.compile(r"[áéíóúñ¿¡]", re.I)


def _held(mind) -> list[dict]:
    told = []
    for message in mind.conversation:
        if message["role"] == "tool" and str(message.get("content")).startswith("{"):
            body = json.loads(str(message["content"]).split("\n", 1)[0])
            if body.get("status") == "not_run":
                told.append({**body, "content": str(message["content"])})
    return told


def test_a_screen_call_runs_as_written_again(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _mind(tmp_path, [_call("display_monitor_set", BELOW_OFF)])
    mind.new_session(FAILED)
    step = mind.decide(1, "pues apágalo ahí abajo")
    assert step["kind"] == "action" and step["operation"] == "display_monitor_set" and _held(mind) == []


def test_after_a_shutdown_held_the_same_call_again_runs_and_nothing_loops(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _mind(tmp_path, [_call("system_power", SHUTDOWN), _call("system_power", SHUTDOWN)])
    mind.new_session(FAILED)
    assert mind.decide(1, "pues apágalo ahí abajo")["operation"] == "system_power"
    assert len(_held(mind)) == 1 and len(server.bodies) == 2


def test_a_shutdown_and_an_alarm_on_some_days_in_one_phrase(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _mind(tmp_path, [_call("system_power", SHUTDOWN), _call("schedule_alarms", DAILY),
                                    _say("¿Quieres que te lo diga como rutina los lunes y jueves a las 7?")])
    mind.wire_to_op = {**mind.wire_to_op, "schedule_alarms": "schedule.alarms"}
    mind.new_session(FAILED)
    step = mind.decide(1, "bueno apágalo y avísame los lunes y jueves a las siete que llame a mamá")
    assert step["kind"] != "action" and len(server.bodies) == 3
    held = _held(mind)
    assert [h.get("error") for h in held] == ["computer_not_named", None]
    assert held[1]["days"] == ["Monday", "Thursday"]
    assert "system_power" in held[1]["content"] and "schedule_alarms" in held[1]["content"]


def test_in_english_two_held_in_one_turn_read_no_spanish(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _mind(tmp_path, [_call("system_power", SHUTDOWN), _call("schedule_alarms", DAILY),
                                    _say("Velmora is still open.")])
    try:
        mind.configure({"capabilities": [], "baxyVersion": "1.5.3", "lang": "en"})
        mind.wire_to_op = {**mind.wire_to_op, "schedule_alarms": "schedule.alarms"}
        mind.new_session([{"role": "user", "content": "close Velmora"},
                          {"role": "assistant", "content": "I could not close Velmora: it keeps running in the background."}])
        mind.decide(1, "ugh then just turn it off down there and remind me mondays and thursdays at seven")
        held = _held(mind)
        assert [h.get("error") for h in held] == ["computer_not_named", None]
        assert len(server.bodies) == 3
        for one in held:
            assert not ACCENTS.search(one["content"]) and "no se ejecut" not in one["content"], one["content"]
    finally:
        harness_language.use("es")
