"""ESE7 (ESE6's open findings, Esencial with the memory off as it is born). «Activa la memoria» with nothing to save had
one call to make, memory_save, and the memory was turned on with a filler record («guardé que está encendida», 2 of 2):
memory.enable is held whole too, and the system text says which call a bare «enciende la memoria» is. A value that looks
like a secret was refused by memory_save with a receipt that names memory_sensitive_save, a tool Esencial did not show:
memory.sensitive.save is held whole too, and the text says which data go in it."""
import json
import pathlib

from test_mind_final import _call, _mind, _say

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROPERTIES = {"kind": {"type": "string", "enum": ["fact", "preference"]}, "selector": {"type": "string"},
              "value": {"type": ["null", "boolean", "number", "string"]},
              "version": {"type": "integer", "minimum": 1, "maximum": 1}}
SAVE = {"name": "memory.save", "description": "Guarda una memoria explícita local no secreta.",
        "argumentsSchema": {"type": "object", "additionalProperties": False,
                            "required": ["kind", "selector", "sensitivity", "value", "version"],
                            "properties": {**PROPERTIES, "sensitivity": {"type": "string", "enum": ["normal", "personal"]}}},
        "risk": "low_reversible", "group": None, "confirms": []}
ENABLE = {"name": "memory.enable", "description": "Habilita la memoria privada local.",
          "argumentsSchema": {"type": "object", "additionalProperties": False, "required": ["enabled", "version"],
                              "properties": {"enabled": {"type": "boolean", "const": True},
                                             "version": {"type": "integer", "minimum": 1, "maximum": 1}}},
          "risk": "privacy_sensitive", "group": None, "confirms": ["normal"]}
SETTINGS = {"name": "baxy.settings.set", "description": "Cambia un ajuste propio de BAXY.",
            "argumentsSchema": {"type": "object", "properties": {"setting": {"type": "string"},
                                                                 "value": {"type": "string"}}},
            "risk": "low_reversible", "confirms": []}
HELD_SAVE = {"name": "memory.save", "title": "Save to memory", "whole": SAVE}
HELD_ENABLE = {"name": "memory.enable", "title": "Turn memory on", "whole": ENABLE}
REST = [{"name": "memory.recall"}, {"name": "memory.disable"}, {"name": "note.create", "title": "Create a note"}]


def _tool(mind, wire: str) -> dict:
    return next(tool["function"] for tool in mind.tools if tool["function"]["name"] == wire)


def _memory_line(system: str) -> str:
    return next((line for line in system.splitlines() if line.startswith("Tu memoria")), "")


def _labels() -> dict:
    labels = json.loads((ROOT / "src" / "Baxy.App" / "Assets" / "operation-labels.v1.json").read_text(encoding="utf-8"))
    return {name: op.get("ficha", True) for name, op in labels["operations"].items()}


def test_the_switch_of_the_memory_is_shown_off_with_its_arguments_and_the_text_names_it(tmp_path: pathlib.Path) -> None:
    mind, _ = _mind(tmp_path, [])
    mind.configure({"capabilities": [SETTINGS], "withheld": [HELD_SAVE, HELD_ENABLE, *REST]})
    enable = _tool(mind, "memory_enable")
    assert enable["description"].startswith("Turn memory on. Off")
    assert "enabled" not in enable["parameters"].get("properties", {}), "a constant is the mind's, not the model's"
    assert mind.constants["memory.enable"] == {"enabled": True}
    assert mind.wire_to_op["memory_enable"] == "memory.enable" and "memory_enable" in mind._stubs
    # Weighed as the whole tool is: it waits for the person's «sí» in Normal by itself, as in any profile.
    assert mind.risk["memory_enable"] == "privacy_sensitive" and mind.confirms["memory_enable"] == ["normal"]
    line = _memory_line(mind.system)
    # Which call is which: the save with a datum, the switch alone when there is none to save.
    assert "memory_save" in line and "memory_enable" in line
    assert line.index("memory_save") < line.index("memory_enable")
    for word in ("tool_profile", "Diario", "perfil", "Ajustes", "Settings", "baxy_settings_set"):
        assert word not in line, word
    # The memory's other tools are still not shown.
    names = [tool["function"]["name"] for tool in mind.tools]
    assert "memory_recall" not in names and "memory_disable" not in names


def test_a_bare_turn_on_reaches_the_app_as_the_switch_and_no_save(tmp_path: pathlib.Path) -> None:
    mind, server = _mind(tmp_path, [_call("memory_enable", {"version": 1}), _say("¿Enciendo la memoria?")])
    mind.configure({"capabilities": [SETTINGS], "withheld": [HELD_SAVE, HELD_ENABLE, *REST]})
    step = mind.decide(1, "activa la memoria")
    assert step["operation"] == "memory.enable" and step["arguments"] == {"enabled": True, "version": 1}
    assert "memory_enable" in [tool["function"]["name"] for tool in server.bodies[0]["tools"]]


def test_with_the_save_alone_held_the_text_of_ese6_stands(tmp_path: pathlib.Path) -> None:
    # An App that holds only memory.save (ESE6): its text, which names no call it does not show.
    mind, _ = _mind(tmp_path, [])
    mind.configure({"capabilities": [SETTINGS], "withheld": [HELD_SAVE, {"name": "memory.enable"}, *REST]})
    line = _memory_line(mind.system)
    assert "memory_save" in line and "memory_enable" not in line and "memory_sensitive_save" not in line
    assert "memory_enable" not in [tool["function"]["name"] for tool in mind.tools]


def test_the_app_holds_whole_the_switch_of_the_memory() -> None:
    assert _labels()["memory.enable"] == "entera"
