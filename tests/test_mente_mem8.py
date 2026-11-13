"""MEM8 (MEM7 trazas, Esencial with the memory on and 4 records): «¿Qué recuerdas de mí?» wanted memory_recall (0,49-0,79
after «memory») and «Olvida mi dirección» memory_forget (0,17-0,35); neither was among the tools, and the call fell on an
empty memory_save held. While the switch is on the App names reading and forgetting with their title (a stub); their stub
says the switch as the App read it, never «Off», and that calling it reads and forgets nothing. Off, nothing changes."""
import pathlib

from baxy_mind.mind import MEMORY_OFF_WAY_STUB, MEMORY_ON_STUB, OFF_STUB
from test_mente_ese7 import HELD_ENABLE, HELD_SAVE, SETTINGS, _tool
from test_mind_final import _mind

READ = {"name": "memory.recall", "title": "Recall something"}
FORGET = {"name": "memory.forget", "title": "Forget"}
NOTE = {"name": "note.create", "title": "Create a note"}
DISABLE = {"name": "memory.disable", "description": "Deshabilita nuevas lecturas y escrituras de memoria local.",
           "argumentsSchema": {"type": "object", "additionalProperties": False, "required": ["enabled", "version"],
                               "properties": {"enabled": {"type": "boolean", "const": False},
                                              "version": {"type": "integer", "minimum": 1, "maximum": 1}}},
           "risk": "low_reversible", "group": None, "confirms": []}
OFF_WAY = {"name": "memory.disable", "title": "Turn memory off", "whole": DISABLE}


def _configured(tmp_path: pathlib.Path, withheld: list, **switch: bool):
    mind, _ = _mind(tmp_path, [])
    mind.configure({"capabilities": [SETTINGS], "withheld": [HELD_SAVE, HELD_ENABLE, *withheld], **switch})
    return mind


def test_with_the_memory_on_reading_and_forgetting_are_stubs_that_say_it_is_on(tmp_path: pathlib.Path) -> None:
    mind = _configured(tmp_path, [READ, FORGET, NOTE], memoryOff=False)
    for wire, title in (("memory_recall", "Recall something"), ("memory_forget", "Forget")):
        tool = _tool(mind, wire)
        assert tool["description"] == f"{title}. {MEMORY_ON_STUB}", tool
        assert tool["parameters"] == {"type": "object", "properties": {}}, tool
        assert "Off" not in tool["description"] and "is on" in tool["description"], tool
        assert mind.withheld[wire] == wire.replace("_", ".", 1), mind.withheld
    # Another tool's stub is as it was.
    assert _tool(mind, "note_create")["description"] == f"Create a note. {OFF_STUB}"


def test_with_the_memory_off_the_prefix_is_the_one_before(tmp_path: pathlib.Path) -> None:
    # The App sends no title for them while the switch is off (ToolProfile.StubbedWhileMemoryOn): no stub, as before.
    before = _configured(tmp_path, [{"name": "memory.recall"}, {"name": "memory.forget"}, NOTE], memoryOff=True)
    assert all(t["function"]["name"] not in ("memory_recall", "memory_forget") for t in before.tools)
    assert MEMORY_ON_STUB not in before._system() + str(before.tools)


def test_with_the_memory_on_the_way_off_is_a_short_stub_that_says_it_runs(tmp_path: pathlib.Path) -> None:
    """MEM8 D1c (revisión ciega D1b #1 y #2): the way off comes whole, shown with the short text; its call carries the
    constant the App needs (enabled false) and the whole tool's risk, so the doubt never asks a «sí» to turn it off."""
    mind = _configured(tmp_path, [READ, FORGET, OFF_WAY], memoryOff=False)
    tool = _tool(mind, "memory_disable")
    assert tool["description"] == f"Turn memory off. {MEMORY_OFF_WAY_STUB}", tool
    assert "enabled" not in tool["parameters"].get("properties", {}), tool
    assert mind.wire_to_op["memory_disable"] == "memory.disable" and "memory_disable" not in mind.withheld
    assert mind.constants["memory.disable"] == {"enabled": False}, mind.constants
    assert mind.risk["memory_disable"] == "low_reversible", mind.risk


def test_final_only_reading_and_forgetting_get_the_memory_on_stub(tmp_path: pathlib.Path) -> None:
    """Revisión ciega 3 #5: another memory tool with a title keeps OFF_STUB."""
    mind = _configured(tmp_path, [READ, {"name": "memory.export", "title": "Export memory"}], memoryOff=False)
    assert _tool(mind, "memory_export")["description"] == f"Export memory. {OFF_STUB}"
    assert _tool(mind, "memory_recall")["description"] == f"Recall something. {MEMORY_ON_STUB}"
