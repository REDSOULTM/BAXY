"""TPV7 (VIVO11, 11-11-2026, candidata 1.4.0 en Esencial: «Crea una nota que diga hola» → BAXY ofrece → «sí» → «Nota
creada: "Hola"» sin llamar note.create). A tool withheld by the profile is a stub with no arguments: turned on with the
person's «sí», the model could only call it empty, or say it was done. The App now hands the whole tool over inside the
same turn (turn.continue «toolOn»), and the turn's next request carries its real schema."""
import json
import pathlib

from baxy_mind.mind import OFF_STUB
from test_mind_final import _call, _mind, _say

NOTE = {"name": "note.create", "description": "Crea una nota con un título y un texto.",
        "argumentsSchema": {"type": "object", "required": ["title", "body"],
                            "properties": {"title": {"type": "string"}, "body": {"type": "string"}}},
        "risk": "low_reversible", "effects": ["writes_user_data"], "confirms": []}
CLOCK = {"name": "system.time", "description": "La hora.", "argumentsSchema": {"type": "object", "properties": {}},
         "risk": "read_only", "confirms": []}
OFF = [{"name": "note.create", "title": "Create a note"}, {"name": "web.fetch", "title": "Read a web page"}]


def _tool(mind, wire: str) -> dict:
    return next(tool["function"] for tool in mind.tools if tool["function"]["name"] == wire)


def test_a_tool_turned_on_takes_its_stubs_place_whole(tmp_path: pathlib.Path) -> None:
    mind, _ = _mind(tmp_path, [])
    mind.configure({"capabilities": [CLOCK], "withheld": OFF})
    order = [tool["function"]["name"] for tool in mind.tools]
    assert _tool(mind, "note_create") == {"name": "note_create", "description": f"Create a note. {OFF_STUB}",
                                          "parameters": {"type": "object", "properties": {}}}
    assert mind.tool_on(NOTE)
    whole = _tool(mind, "note_create")
    assert OFF_STUB not in whole["description"]
    assert set(whole["parameters"]["properties"]) == {"title", "body"}
    assert whole["parameters"]["required"] == ["title", "body"]
    # In its own place: what comes before it in the prompt is the same, so only what follows is read again.
    assert [tool["function"]["name"] for tool in mind.tools] == order
    assert mind.wire_to_op["note_create"] == "note.create" and "note_create" not in mind.withheld
    assert mind.risk["note_create"] == "low_reversible" and mind.confirms["note_create"] == []
    assert mind.effects["note_create"] == ["writes_user_data"]
    # The other one stays off.
    assert OFF_STUB in _tool(mind, "web_fetch")["description"] and "web_fetch" in mind.withheld


def test_a_tool_off_that_has_no_stub_is_not_taken(tmp_path: pathlib.Path) -> None:
    # The memory's tools are off with no stub (VIVO1 F8): the model cannot call them, so nothing holds them for a «sí»
    # and the mind takes none of them before the App restarts it with the profile's catalog.
    save = {"name": "memory.save", "description": "Guarda un dato de la persona.",
            "argumentsSchema": {"type": "object", "required": ["fact"], "properties": {"fact": {"type": "string"}}},
            "risk": "low_reversible", "confirms": []}
    mind, _ = _mind(tmp_path, [])
    mind.configure({"capabilities": [CLOCK], "withheld": OFF + [{"name": "memory.save"}]})
    order = [tool["function"]["name"] for tool in mind.tools]
    assert "memory_save" not in order and "memory_save" in mind.withheld
    assert not mind.tool_on(save)
    assert [tool["function"]["name"] for tool in mind.tools] == order and "memory_save" in mind.withheld


def test_only_a_tool_that_is_off_is_turned_on(tmp_path: pathlib.Path) -> None:
    mind, _ = _mind(tmp_path, [])
    mind.configure({"capabilities": [CLOCK], "withheld": OFF})
    before = json.dumps(mind.tools)
    assert not mind.tool_on(CLOCK)  # already whole
    assert not mind.tool_on({"name": "file.delete", "argumentsSchema": {}})  # not one of this catalog
    assert not mind.tool_on({})
    assert json.dumps(mind.tools) == before


def test_the_turns_next_request_carries_the_whole_tool_and_its_call_keeps_its_arguments(tmp_path: pathlib.Path) -> None:
    said = {"title": "hola", "body": "hola"}
    mind, server = _mind(tmp_path, [_call("note_create", {}), _call("note_create", said), _say("Listo.")])
    mind.configure({"capabilities": [CLOCK], "withheld": OFF})
    first = mind.decide(1, "crea una nota que diga hola")
    assert first["operation"] == "note.create" and first["arguments"] == {}
    assert mind.tool_on(NOTE)
    second = mind.continue_turn(2, json.dumps({"status": "rejected", "error": "not_run_tool_turned_on"}))
    assert second["operation"] == "note.create" and second["arguments"] == said
    sent = next(tool["function"] for tool in server.bodies[-1]["tools"] if tool["function"]["name"] == "note_create")
    assert set(sent["parameters"]["properties"]) == {"title", "body"}


def test_a_stub_is_not_called_again_after_a_call_in_the_same_reply(tmp_path: pathlib.Path) -> None:
    # MUS1 (VIVO13, «Lee la página es.wikipedia.org/wiki/Pudú» in Esencial: the offer took 84-87 s): the stub has no
    # arguments, and the 4B wrote «web_fetch {}» 37 times over until DECISION_TOKENS (768 tokens, 78 s; reproduced on
    # the PC 2/2). The request stops where a second call to a stub would begin after a call, so the first call and its
    # probabilities are the same and the rest is never written; a tool turned on is no longer stopped.
    mind, server = _mind(tmp_path, [_call("web_fetch", {}), _say("¿Enciendo la lectura de páginas?")])
    mind.configure({"capabilities": [CLOCK], "withheld": OFF})
    mind.decide(1, "lee la página")
    stops = server.bodies[0]["stop"]
    assert "</tool_call>\n<tool_call>\n<function=web_fetch>" in stops
    assert "</tool_call>\n<tool_call>\n<function=note_create>" in stops
    assert not any("system_time" in stop for stop in stops)
    assert mind.tool_on(NOTE)
    mind2, server2 = _mind(tmp_path, [_say("hola")])
    mind2.configure({"capabilities": [CLOCK], "withheld": OFF})
    mind2.tool_on(NOTE)
    mind2.decide(1, "hola")
    assert server2.bodies[0]["stop"] == ["</tool_call>\n<tool_call>\n<function=web_fetch>"]


def test_without_stubs_no_stop_is_asked(tmp_path: pathlib.Path) -> None:
    mind, server = _mind(tmp_path, [_say("Son las diez.")])
    mind.configure({"capabilities": [CLOCK]})
    mind.decide(1, "qué hora es")
    assert "stop" not in server.bodies[0]
