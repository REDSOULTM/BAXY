"""INT36G (VIVO21, 14-11, 2 of 2): with a routine just made («los lunes, miércoles y viernes a las 10:00…»), «borra la de
las 10:00» took ~70 s and opened the making of a new routine. The 4B wrote «baxy_routines {}» again and again to the
decision's last token (768: ~20 s on the PC, ~34 s on the notebook), and that call only opens the guide of a new one.

Now a call of baxy_routines is written once (the request stops where another would begin, as for a stub), and when the
person has routines their words are read in a closed, typed question with those routines listed by what they are (time,
days, word, what they say or do): the model says whether they ask a new one or something of one they have, and which.
Deleting, turning off or on asks first, saying which routine, and only their «sí» acts."""
from __future__ import annotations

import json
from pathlib import Path

from baxy_mind import routine_fill
from baxy_mind.mind import STUB_AGAIN
from test_mind_final import _call
from test_mind_routine_guide import HEADSET, _guide_mind, _receipt
from test_mind_rut14_rutinas import SAVED, TEXT, TIMED, _reading

COFFEE = {"id": "r-00000b", "name": "07:30", "trigger": {"at": "07:30", "repeat": "daily"}, "active": True,
          "steps": [{"say": "Arriba, a desayunar"}]}


def _is_have(body: dict) -> bool:
    return ((body.get("response_format") or {}).get("json_schema") or {}).get("name") == "rutinas"


def _opened(tmp_path: Path, have: list, reads: list | None = None, routines: list | None = None):
    """The model calls baxy_routines {}; the closed question of which routine is answered with the next of ``have``,
    the reading of a new one with the next of ``reads``."""
    mind, server = _guide_mind(tmp_path, [_call("baxy_routines", {})],
                               [SAVED, COFFEE, HEADSET] if routines is None else routines)
    _reading(server, list(reads or []))
    plain_apart, plain_chat = server.ask_apart, server.chat
    server.have_asked = []

    def answer(body: dict) -> dict:
        server.have_asked.append(json.loads(json.dumps(body)))
        given = have.pop(0)
        return {"choices": [{"message": {"content": given if isinstance(given, str) else json.dumps(given)}}]}

    server.ask_apart = lambda body, timeout=60.0: answer(body) if _is_have(body) else plain_apart(body, timeout)
    server.chat = lambda body, timeout=120.0, gives_way=False: (answer(body) if _is_have(body)
                                                                else plain_chat(body, timeout, gives_way))
    return mind, server


def test_a_call_of_baxy_routines_is_written_once(tmp_path: Path) -> None:
    mind, server = _opened(tmp_path, [], [TIMED], routines=[])
    mind.decide(1, "que me saludes los lunes cuando llegue")
    assert STUB_AGAIN.format(wire="baxy_routines") in server.bodies[0]["stop"]


def test_their_routine_named_by_its_time_is_asked_by_what_it_is_and_deleted_on_their_yes(tmp_path: Path) -> None:
    mind, server = _opened(tmp_path, [{"a": "delete", "r": "10:00"}])
    asked = mind.decide(1, "borra la de las 10:00")
    assert asked["kind"] == "conversation" and asked["operation"] is None
    # which one, said by what it is: its days, its time and what it says, never the guide of a new one
    assert "10:00" in asked["reply"] and TEXT in asked["reply"] and "miércoles" in asked["reply"]
    assert asked["reply"].startswith("¿Borro") and "mañana o de la tarde" not in asked["reply"]
    # the routines were listed to the model by what they are, each with its key
    note = server.have_asked[0]["messages"][-1]["content"]
    assert "«10:00»: " in note and TEXT in note and "Arriba, a desayunar" in note and "audífonos" in note
    assert "borra la de las 10:00" in note
    deleted = mind.decide(2, "sí")
    assert deleted["kind"] == "action" and deleted["operation"] == "baxy.routines"
    assert deleted["arguments"] == {"action": "delete", "name": SAVED["id"]}


def test_nothing_is_deleted_without_their_yes(tmp_path: Path) -> None:
    mind, _ = _opened(tmp_path, [{"a": "delete", "r": "10:00"}])
    mind.decide(1, "borra la de las 10:00")
    kept = mind.decide(2, "no")
    assert kept["kind"] == "conversation" and kept["operation"] is None and mind._guide is None


def test_two_routines_it_may_be_are_asked_which(tmp_path: Path) -> None:
    mind, _ = _opened(tmp_path, [{"a": "delete", "r": "more than one"}])
    asked = mind.decide(1, "borra la de la mañana")
    assert asked["kind"] == "conversation" and asked["operation"] is None
    assert "¿Cuál" in asked["reply"] and mind._guide.step == "which"


def test_turning_one_off_asks_it_by_what_it_is(tmp_path: Path) -> None:
    mind, _ = _opened(tmp_path, [{"a": "turn_off", "r": "07:30"}])
    asked = mind.decide(1, "apaga la del desayuno")
    assert asked["reply"].startswith("¿Desactivo") and "Arriba, a desayunar" in asked["reply"]
    done = mind.decide(2, "sí")
    assert done["arguments"] == {"action": "disable", "name": COFFEE["id"]}


def test_a_new_routine_is_made_as_before(tmp_path: Path) -> None:
    # RUT17: without SAVED, the same routine, which BAXY now says they have (test_mind_rut17_duplicada)
    mind, server = _opened(tmp_path, [{"a": "new"}], [TIMED], routines=[COFFEE, HEADSET])
    asked = mind.decide(1, f"quiero que los lunes, miércoles y viernes a las 10 de la mañana me digas {TEXT}")
    assert asked["kind"] == "conversation" and "¿La guardo?" in asked["reply"]
    assert len(server.have_asked) == 1


def test_with_no_routines_nothing_more_is_asked(tmp_path: Path) -> None:
    mind, server = _opened(tmp_path, [], [TIMED], routines=[])
    mind.decide(1, "quiero que los lunes, miércoles y viernes a las 10 de la mañana me digas hola")
    assert server.have_asked == []


def test_a_key_that_is_none_of_theirs_asks_which(tmp_path: Path) -> None:
    mind, _ = _opened(tmp_path, [{"a": "delete", "r": "la de las nueve"}])
    asked = mind.decide(1, "borra la de las 10:00")
    assert asked["operation"] is None and mind._guide.step == "which"


def test_unreadable_goes_on_as_before(tmp_path: Path) -> None:
    mind, _ = _opened(tmp_path, ["no json"], [TIMED])
    asked = mind.decide(1, "borra la de las 10:00")
    assert asked["operation"] is None and mind._guide is not None


def test_the_schema_is_closed_values_and_one_text(tmp_path: Path) -> None:
    schema = routine_fill.HAVE_SCHEMA
    assert schema["additionalProperties"] is False and schema["required"] == ["a"]
    assert set(schema["properties"]["a"]["enum"]) == {"new", "delete", "turn_off", "turn_on", "change", "list", "no", "other"}
    # the routine by its name, one of theirs or «more than one»: a closed list of values, the 4B wrote the time for a key
    body = routine_fill.have_body([SAVED, COFFEE], "borra la de las 10:00", "es", 0)
    assert body["response_format"]["json_schema"]["schema"]["properties"]["r"]["enum"] == ["10:00", "07:30", "more than one"]


def test_their_yes_deletes_the_one_asked_even_if_the_list_changed(tmp_path: Path) -> None:
    mind, _ = _opened(tmp_path, [{"a": "delete", "r": "10:00"}])
    mind.decide(1, "borra la de las 10:00")
    mind.routines = [COFFEE, SAVED]
    deleted = mind.decide(2, "sí")
    assert deleted["arguments"] == {"action": "delete", "name": SAVED["id"]}
    told = mind.continue_turn(3, _receipt({"deleted": SAVED}))
    assert told["kind"] == "conversation"


def test_their_only_routine_with_no_key_is_asked_by_what_it_is(tmp_path: Path) -> None:
    mind, _ = _opened(tmp_path, [{"a": "delete"}], routines=[SAVED])
    asked = mind.decide(1, "borra la de las 10:00")
    assert asked["reply"].startswith("¿Borro esta rutina:") and TEXT in asked["reply"]


def test_beside_an_alarm_result_their_routines_at_a_time_are_said(tmp_path: Path) -> None:
    """Held-out, a new conversation: «bórrame la de las nueve y media» went to the alarms, «no hay alarmas»."""
    mind, server = _guide_mind(tmp_path, [_call("schedule_alarms", {"action": "list"}),
                                          {"choices": [{"message": {"content": "Listo."}}]}], [SAVED, COFFEE, HEADSET])
    mind.decide(1, "bórrame la de las 10:00")
    mind.continue_turn(2, _receipt({"alarms": []}))
    facts = [m["content"] for m in server.bodies[-1]["messages"] if m["role"] == "tool"][-1]
    assert "rutinas con hora" in facts and "baxy_routines" in facts and TEXT in facts and "Arriba, a desayunar" in facts
    assert "audífonos" not in facts.split("rutinas con hora", 1)[1]   # a routine with a word has no time


def test_beside_a_new_alarm_nothing_is_said(tmp_path: Path) -> None:
    mind, server = _guide_mind(tmp_path, [_call("schedule_alarms", {"action": "create", "at": "07:00"}),
                                          {"choices": [{"message": {"content": "Listo."}}]}], [SAVED])
    mind.decide(1, "pon una alarma a las 7")
    mind.continue_turn(2, _receipt({"created": True}))
    facts = [m["content"] for m in server.bodies[-1]["messages"] if m["role"] == "tool"][-1]
    assert "rutinas con hora" not in facts
