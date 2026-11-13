"""ALR10 (VIVO19 R19-1): BAXY's last question goes into the closed question of what rings (Mind._ring_not_asked) only if
it was asked while that rang. «¿Quieres que active la herramienta de notas?» asked with nothing ringing, its «sí» taken
on the card, then the alarm snoozed earlier rang again under a new id: «Para la alarma.» beside that question was read
«seguir», held, and it kept ringing."""
import json
from pathlib import Path

from test_mind_final import _call, _mind, _say

AGAIN = {"id": "57cafaca", "kind": "alarm", "title": "Alarma en un minuto", "clock": "04:48"}
FIRST = {"id": "a41f64b4", "kind": "alarm", "title": "Alarma en un minuto", "clock": "04:42"}
CAPABILITY = {"capabilities": [{"name": "schedule.alarms", "description": "Alarms.", "risk": "low_reversible",
                                "argumentsSchema": {"type": "object", "properties": {"action": {"type": "string"}}}}]}


def _read_by_question(server) -> None:
    """The closed question answers «seguir» when it is told a question of BAXY's, «parar» otherwise (what the 4B did)."""
    def ask_apart(body: dict, timeout: float = 60.0) -> dict:
        server.closed.append(json.loads(json.dumps(body)))
        asked = "El asistente había preguntado" in body["messages"][1]["content"]
        return {"choices": [{"message": {"content": "seguir" if asked else "parar"}}]}
    server.ask_apart = ask_apart


def test_a_question_asked_before_it_rang_is_not_told_and_the_stop_runs(tmp_path: Path) -> None:
    mind, server = _mind(tmp_path, [_say("¿Quieres que active la herramienta de notas para crearla?"),
                                    _call("schedule_alarms", {"action": "stop", "id": "57cafaca"}),
                                    _say("No se paró."), _say("No se paró.")])
    mind.configure(CAPABILITY)
    _read_by_question(server)
    mind.decide(1, "Crea una nota que diga regar las plantas.")
    result = mind.decide(2, "Para la alarma.", None, None, None, None, [AGAIN])
    assert "El asistente había preguntado" not in server.closed[0]["messages"][1]["content"]
    assert result["kind"] == "action" and result["arguments"] == {"action": "stop", "id": "57cafaca"}


def test_a_ring_snoozed_and_ringing_again_starts_clean(tmp_path: Path) -> None:
    mind, server = _mind(tmp_path, [_say("Entendido. ¿Quieres que la alarma se detenga o se posponga?"),
                                    _say("Entendido. ¿Quieres que la alarma se detenga o se posponga?"),
                                    _call("schedule_alarms", {"action": "stop", "id": "57cafaca"}),
                                    _say("No se paró."), _say("No se paró.")])
    mind.configure(CAPABILITY)
    _read_by_question(server)
    mind.decide(1, "Todavía no la apagues.", None, None, None, None, [FIRST])
    result = mind.decide(2, "Para la alarma.", None, None, None, None, [AGAIN])
    assert result["kind"] == "action" and result["arguments"] == {"action": "stop", "id": "57cafaca"}


def test_a_question_asked_while_it_rang_is_still_told(tmp_path: Path) -> None:
    mind, server = _mind(tmp_path, [_say("¿La paro?"), _say("¿La paro?"),
                                    _call("schedule_alarms", {"action": "stop", "id": "a41f64b4"})])
    mind.configure(CAPABILITY)
    server.closed = []

    def ask_apart(body: dict, timeout: float = 60.0) -> dict:
        server.closed.append(json.loads(json.dumps(body)))
        return {"choices": [{"message": {"content": "parar"}}]}
    server.ask_apart = ask_apart
    mind.decide(1, "Oye BAXY.", None, None, None, None, [FIRST])
    result = mind.decide(2, "Sí.", None, None, None, None, [FIRST])
    assert result["kind"] == "action"
    assert "El asistente había preguntado: «¿La paro?»" in server.closed[0]["messages"][1]["content"]
