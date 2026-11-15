"""RUT17 (VIVO22, 14-11: «Borra la rutina de las diez de la mañana.» → «No tengo ninguna rutina «diez de la mañana».
Tienes: «20:00».», while «Borra la rutina de las 10:00.» found it): a name said in a fixed order that is none of their
routines' by form may be a time in words. The model writes the time those words say in a closed, typed object; the mind
compares it with each routine's clock, and the one routine at that time is asked about by what it is: only their «sí»
acts. No list of words reads the time."""
from __future__ import annotations

import json
from pathlib import Path

from baxy_mind import routine_fill
from test_mind_int37b_rutina_conversacion_nueva import EIGHT, MORNING, TEN
from test_mind_routine_guide import _guide_mind


def _clock_mind(tmp_path: Path, written: str | Exception, routines: list | None = None):
    """The model's reading of the time a name says is ``written`` (its JSON as written, or an error raised)."""
    mind, server = _guide_mind(tmp_path, [], [TEN, EIGHT] if routines is None else routines)
    server.clock_asked = []
    plain = server.chat

    def chat(body: dict, timeout: float = 120.0, gives_way: bool = False) -> dict:
        if ((body.get("response_format") or {}).get("json_schema") or {}).get("name") == "hora":
            server.clock_asked.append(body)
            if isinstance(written, Exception):
                raise written
            return {"choices": [{"message": {"content": written}}]}
        return plain(body, timeout, gives_way)

    server.chat = chat
    mind.new_session([])
    return mind, server


def test_the_time_in_words_of_one_routine_is_asked_by_what_it_is_and_deleted_on_their_yes(tmp_path: Path) -> None:
    mind, server = _clock_mind(tmp_path, '{"h": "10"}')
    asked = mind.decide(1, "Borra la rutina de las diez de la mañana.")
    assert asked["kind"] == "conversation" and asked["operation"] is None
    assert asked["reply"].startswith("¿Borro esta rutina:") and "10:00" in asked["reply"] and MORNING in asked["reply"]
    assert "«diez de la mañana»" in server.clock_asked[0]["messages"][-1]["content"]
    deleted = mind.decide(2, "Sí.")
    assert deleted["kind"] == "action" and deleted["arguments"] == {"action": "delete", "name": TEN["id"]}


def test_their_no_leaves_it(tmp_path: Path) -> None:
    mind, _ = _clock_mind(tmp_path, '{"h": "20"}')
    asked = mind.decide(1, "Desactiva la rutina de las ocho de la noche.")
    assert asked["reply"].startswith("¿Desactivo esta rutina:") and "sábados" in asked["reply"]
    kept = mind.decide(2, "No.")
    assert kept["kind"] == "conversation" and kept["operation"] is None and mind._guide is None


def test_no_time_read_or_none_of_theirs_goes_on_as_before(tmp_path: Path) -> None:
    for name, written in (("ninguna", '{"h": "none"}'), ("otra", '{"h": "9", "m": "15"}'), ("ilegible", "quizá"),
                          ("fallo", OSError("caído"))):
        mind, _ = _clock_mind(tmp_path / name, written)
        told = mind.decide(1, "Borra la rutina de las nueve y cuarto.")
        # the name goes to RoutinesHandler as said (it answers routine_not_found and nothing is deleted)
        assert told["kind"] == "action" and told["arguments"] == {"action": "delete", "name": "nueve y cuarto"}, name


def test_a_name_of_theirs_is_not_read_again(tmp_path: Path) -> None:
    mind, server = _clock_mind(tmp_path, '{"h": "10"}')
    deleted = mind.decide(1, "Borra la rutina de las 10:00.")   # its own name: at once (REM2 B-1), as before
    assert deleted["kind"] == "action" and deleted["arguments"] == {"action": "delete", "name": "10 00"}
    assert server.clock_asked == []


def test_two_routines_at_that_time_are_not_taken_for_one(tmp_path: Path) -> None:
    again = {**TEN, "id": "r-77e0c2", "name": "despertar"}
    mind, _ = _clock_mind(tmp_path, '{"h": "10"}', routines=[TEN, again, EIGHT])
    told = mind.decide(1, "Borra la rutina de las diez de la mañana.")
    assert told["kind"] == "action" and told["arguments"]["name"] == "diez de la mañana"


def test_the_closed_reading_is_typed() -> None:
    body = routine_fill.clock_body("diez de la mañana", 0)
    schema = body["response_format"]["json_schema"]["schema"]
    assert schema["properties"]["h"]["enum"][:2] == ["none", "0"] and len(schema["properties"]["m"]["enum"]) == 60
    assert routine_fill.clock_parsed({"choices": [{"message": {"content": '{"h": "22", "m": "30"}'}}]}) == "22:30"
    assert routine_fill.clock_parsed({"choices": [{"message": {"content": '{"h": "none"}'}}]}) is None
    assert json.loads(json.dumps(body))["max_tokens"] == routine_fill.CLOCK_TOKENS
