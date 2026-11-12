"""ESE6 (GUA3/ESE5 lote A, Esencial with the memory off as it is born: «Recuerda que mi perro se llama Chispo.» → «sí»
saved nothing in 18 of 18, and «guardado» was said with nothing saved in 9 of 18). The memory had no call of its own in
Esencial, only the switch to a whole larger profile (MEMORY_OFF_FACT); and a stub with no arguments (ESE5) loses what was
to be saved. The App now sends memory.save whole beside its title (withheld «whole»): the mind shows it off with its
arguments, its call reaches the App with them, where it is held and, with the person's «sí», run in one step with the
memory turned on (NativeTurnLoop.AnswerMemoryOffHeldAsync). The system text names that call, and no profile."""
import json
import pathlib

from test_mind_final import _call, _mind, _say

ROOT = pathlib.Path(__file__).resolve().parents[1]
SAVE = {"name": "memory.save", "description": "Guarda una memoria explícita local no secreta.",
        "argumentsSchema": {"type": "object", "additionalProperties": False,
                            "required": ["kind", "selector", "value", "version"],
                            "properties": {"kind": {"type": "string", "enum": ["fact", "preference"]},
                                           "selector": {"type": "string"},
                                           "value": {"type": ["null", "boolean", "number", "string"]},
                                           "version": {"type": "integer", "minimum": 1, "maximum": 1}}},
        "risk": "low_reversible", "group": None, "confirms": []}
SETTINGS = {"name": "baxy.settings.set", "description": "Cambia un ajuste propio de BAXY.",
            "argumentsSchema": {"type": "object", "properties": {"setting": {"type": "string"},
                                                                 "value": {"type": "string"}}},
            "risk": "low_reversible", "confirms": []}
OFF = [{"name": "memory.save", "title": "Save to memory", "whole": SAVE}, {"name": "memory.recall"},
       {"name": "memory.enable"}, {"name": "note.create", "title": "Create a note"}]


def _tool(mind, wire: str) -> dict:
    return next(tool["function"] for tool in mind.tools if tool["function"]["name"] == wire)


def _memory_line(system: str) -> str:
    return next((line for line in system.splitlines() if line.startswith("Tu memoria")), "")


def test_a_tool_held_whole_is_shown_off_with_its_arguments(tmp_path: pathlib.Path) -> None:
    mind, _ = _mind(tmp_path, [])
    mind.configure({"capabilities": [SETTINGS], "withheld": OFF})
    save = _tool(mind, "memory_save")
    assert save["description"].startswith("Save to memory. Off")
    assert {"kind", "selector", "value"} <= set(save["parameters"]["properties"])
    assert save["parameters"]["required"] == ["kind", "selector", "value", "version"]
    # A tool's stub with no arguments stays as it was, and the memory's other tools are still not shown.
    assert _tool(mind, "note_create")["parameters"] == {"type": "object", "properties": {}}
    names = [tool["function"]["name"] for tool in mind.tools]
    assert "memory_recall" not in names and "memory_enable" not in names
    # Weighed as the whole tool is, and still one of the profile's stubs (it is not called twice in one reply).
    assert mind.wire_to_op["memory_save"] == "memory.save"
    assert mind.risk["memory_save"] == "low_reversible" and mind.confirms["memory_save"] == []
    assert "memory_save" in mind._stubs


def test_the_system_text_names_that_call_and_no_profile(tmp_path: pathlib.Path) -> None:
    mind, _ = _mind(tmp_path, [])
    mind.configure({"capabilities": [SETTINGS], "withheld": OFF})
    line = _memory_line(mind.system)
    assert "memory_save" in line and "sí" in line
    for word in ("tool_profile", "Diario", "perfil", "Ajustes", "Settings", "baxy_settings_set"):
        assert word not in line, word


def test_the_held_call_reaches_the_app_with_the_arguments_the_model_gave(tmp_path: pathlib.Path) -> None:
    said = {"kind": "fact", "selector": "nombre del perro", "value": "Chispo", "version": 1}
    mind, server = _mind(tmp_path, [_call("memory_save", said), _say("¿Enciendo la memoria para guardarlo?")])
    mind.configure({"capabilities": [SETTINGS], "withheld": OFF})
    step = mind.decide(1, "recuerda que mi perro se llama Chispo")
    assert step["operation"] == "memory.save" and step["arguments"] == said
    sent = next(tool["function"] for tool in server.bodies[0]["tools"] if tool["function"]["name"] == "memory_save")
    assert "selector" in sent["parameters"]["properties"]


def test_without_the_whole_tool_the_text_of_before_stands(tmp_path: pathlib.Path) -> None:
    # An App that does not send it whole (before ESE6): no stub, and the fact that names the profile's switch.
    mind, _ = _mind(tmp_path, [])
    mind.configure({"capabilities": [SETTINGS], "withheld": [{"name": "memory.save"}, {"name": "memory.recall"}]})
    assert "memory_save" not in [tool["function"]["name"] for tool in mind.tools]
    assert "tool_profile" in _memory_line(mind.system)


def test_the_app_holds_whole_memory_save_and_little_else() -> None:
    labels = json.loads((ROOT / "src" / "Baxy.App" / "Assets" / "operation-labels.v1.json").read_text(encoding="utf-8"))
    memory = {name: op.get("ficha", True) for name, op in labels["operations"].items() if name.startswith("memory.")}
    assert memory["memory.save"] == "entera"
    # ESE7: the memory's switch too (test_mente_ese7); the rest of the memory has no stub, and no other tool goes whole.
    assert [name for name, stub in memory.items() if stub is not False] == ["memory.enable", "memory.save"]
    assert [name for name, op in labels["operations"].items() if op.get("ficha") == "entera"] == [
        "memory.enable", "memory.save"]
