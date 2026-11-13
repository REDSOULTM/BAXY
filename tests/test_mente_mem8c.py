"""MEM8C (REV20 M-1, M-4, M-5): the count of what BAXY's memory keeps and its switch, as the check reads them, are the
ones of the turn. M-1: 4 records at the start, «Olvidar todo» in the panel, then «¿qué recuerdas de mí?»: the note said
«tiene 4 datos» to a true «no tengo nada guardado» until the App restarted (the count went once, in catalog.configure).
The App now sends it with each turn (turn.decide «memoryRecords», as it is then: none known after a change). M-4:
«Apaga la memoria» completed and, in the same turn, «no tengo nada guardado» was marked with the fact «encendida»."""
import pathlib

from baxy_mind.answer_check import MEMORY_KEPT_UNREAD_FACT, MEMORY_OFF_FACT, MEMORY_UNREAD_FACT, check
from test_mente_ese7 import HELD_ENABLE, HELD_SAVE, SETTINGS
from test_mind_final import _mind, _say

ASKED = "¿Qué tienes guardado de mí?"
NOTHING = "No tengo nada guardado de ti."
READ = {"name": "memory.recall", "title": "Recall something"}
FORGET = {"name": "memory.forget", "title": "Forget"}


def _facts(found: list[dict]) -> list[str]:
    return [f["fact"] for f in found if f["rule"] == "memory_off_empty"]


def test_m4_a_way_off_completed_in_the_turn_is_the_switch_the_fact_says() -> None:
    off = {"op": "memory.disable", "tool": "memory_disable", "arguments": {}, "completed": True, "read": False}
    found = _facts(check(NOTHING, "Apaga la memoria y dime qué tienes de mí.", [off], [("memory.disable", True, False)],
                         memory_unread=True, memory_records=4))
    assert found == [MEMORY_OFF_FACT], found
    assert "encendida" not in found[0]


def test_m4_a_way_off_earlier_in_the_conversation_counts_too_and_on_again_after_it_does_not() -> None:
    earlier = [("memory.disable", True, False)]
    assert _facts(check(NOTHING, ASKED, [], earlier, memory_unread=True, memory_records=4)) == [MEMORY_OFF_FACT]
    # Turned on again after it (the last switch call completed is the one now): on, unread, its count not known.
    again = [("memory.disable", True, False), ("memory.enable", True, False)]
    assert _facts(check(NOTHING, ASKED, [], again, memory_unread=True, memory_records=4)) == [MEMORY_UNREAD_FACT]
    # One that did not complete changes nothing.
    failed = [("memory.disable", False, False)]
    assert _facts(check(NOTHING, ASKED, [], failed, memory_unread=True, memory_records=4)) == [
        MEMORY_KEPT_UNREAD_FACT.format(n=4)]


def _on(tmp_path: pathlib.Path, replies: list):
    mind, server = _mind(tmp_path, replies)
    mind.configure({"capabilities": [SETTINGS], "withheld": [HELD_SAVE, HELD_ENABLE, READ, FORGET], "memoryOff": False,
                    "memoryRecords": 4})
    return mind, server


def _second_request(server) -> str:
    return str([body["messages"] for body in server.bodies[1:]])


def test_m1_the_count_the_check_reads_is_the_turns_not_the_configures(tmp_path: pathlib.Path) -> None:
    # The turn says 4: the note says 4.
    mind, server = _on(tmp_path / "a", [_say(NOTHING), _say("Tengo 4 datos guardados que este perfil no lee.")])
    mind.memory_records = 4
    mind.decide("r1", ASKED)
    assert "tiene 4 datos" in _second_request(server), server.bodies
    # «Olvidar todo» in the panel: the App's count is not known now, whatever catalog.configure said.
    mind, server = _on(tmp_path / "b", [_say(NOTHING), _say("Puede que tenga recuerdos tuyos.")])
    mind.memory_records = None
    mind.decide("r1", ASKED)
    told = _second_request(server)
    assert "tiene 4 datos" not in told and "no sabes si los hay" in told, server.bodies
    # And 0: «no tengo nada guardado» is so, no second answer.
    mind, server = _on(tmp_path / "c", [_say(NOTHING)])
    mind.memory_records = 0
    mind.decide("r1", ASKED)
    assert len(server.bodies) == 1, server.bodies
