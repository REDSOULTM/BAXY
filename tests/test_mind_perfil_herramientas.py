"""Perfiles de herramientas (owner, 2026-11-08): the App leaves the tools of the person's profile out of the catalog and
names them as withheld. The model is shown the others whole and each withheld one as a stub (its title, that it is off in
this PC's tool profile, no arguments), with the wire name it has with every tool; a call to a stub reaches the App by its
operation, which refuses it as off (ToolProfile) with a result that says nothing ran (NativeTurnLoop.Refused).
VIVO1 F8 (09-11): with the withheld ones left out, the model called none and offered what it could not do."""
from pathlib import Path

from baxy_mind.mind import OFF_STUB, RING_STUB
from test_mind_final import _call, _mind

OPEN = {"name": "app.open", "description": "Abre una app.", "group": "Aplicaciones",
        "argumentsSchema": {"type": "object", "properties": {"appId": {"type": "string"}}}, "risk": "low_reversible",
        "confirms": []}
VOLUME = {"name": "audio.volume", "description": "Pone el volumen.", "group": "Audio",
          "argumentsSchema": {"type": "object", "properties": {}}, "risk": "low_reversible", "confirms": []}
ADJUST = {**VOLUME, "name": "audio.volume.adjust", "description": "Sube o baja el volumen."}


def _names(mind) -> list[str]:
    return [tool["function"]["name"] for tool in mind.tools]


def test_a_withheld_tool_is_shown_as_a_stub_and_every_tool_keeps_its_wire_name(tmp_path: Path) -> None:
    full, _ = _mind(tmp_path / "full", [])
    full.configure({"capabilities": [OPEN, VOLUME, ADJUST]})
    shown, _ = _mind(tmp_path / "profile", [])
    off = {"name": "audio.volume.adjust", "title": "Raise or lower the volume"}
    assert shown.configure({"capabilities": [OPEN, VOLUME], "withheld": [off]}) == 2
    volume = full.wires.name("audio.volume")
    assert volume != "audio_volume"  # a proper prefix of audio_volume_adjust is renamed (PC-C72)
    assert _names(shown) == _names(full)
    assert shown.wires.name("audio.volume") == volume
    assert "audio.volume.adjust" not in shown.wire_to_op.values()
    stub = next(t["function"] for t in shown.tools if t["function"]["name"] == full.wires.name("audio.volume.adjust"))
    assert stub["description"] == "Raise or lower the volume. " + OFF_STUB
    assert stub["parameters"] == {"type": "object", "properties": {}}
    whole = [t for t in shown.tools if t["function"]["name"] == volume]
    assert whole == [t for t in full.tools if t["function"]["name"] == volume]


def test_a_withheld_name_without_its_title_has_no_stub_and_keeps_its_way_to_the_app(tmp_path: Path) -> None:
    # VIVO1 F8, 2.ª vuelta (09-11, foco de 16 casos × 3 semillas, juez ciego): memory stubs made the 4B claim to have saved
    # or to remember (13 high falsehoods against 6 without them); the App names those without a title.
    mind, _ = _mind(tmp_path, [])
    mind.configure({"capabilities": [OPEN], "withheld": ["file.delete", {"name": "memory.save"}]})
    assert [t["function"]["name"] for t in mind.tools[3:]] == ["app_open"]
    assert mind.withheld == {"file_delete": "file.delete", "memory_save": "memory.save"}


def test_a_call_to_a_withheld_tool_goes_to_the_app_by_its_operation(tmp_path: Path) -> None:
    mind, _ = _mind(tmp_path, [_call("file_delete", {"path": "x.txt"})])
    mind.configure({"capabilities": [OPEN], "withheld": ["file.delete"]})
    result = mind.decide(1, "borra x.txt")
    assert result["kind"] == "action" and result["operation"] == "file.delete"


def test_with_nothing_withheld_the_tools_are_the_ones_of_before(tmp_path: Path) -> None:
    before, _ = _mind(tmp_path / "before", [])
    before.configure({"capabilities": [OPEN, VOLUME, ADJUST]})
    now, _ = _mind(tmp_path / "now", [])
    now.configure({"capabilities": [OPEN, VOLUME, ADJUST], "withheld": []})
    assert now.tools == before.tools and now.system == before.system and now.withheld == {}


def test_alarms_kept_off_keep_the_part_that_answers_what_already_rings(tmp_path: Path) -> None:
    # ALR5 (M2): with Alarmas outside the profile, one set before rang and no words stopped it. The stub had no
    # arguments, so «stop» could not be written, and the acknowledgement's rule did not see the tool.
    mind, server = _mind(tmp_path, [_call("schedule_alarms", {"action": "stop", "id": "89abcdef"})])
    mind.configure({"capabilities": [OPEN], "withheld": [{"name": "schedule.alarms", "title": "Alarm or reminder"}]})
    tool = next(t["function"] for t in mind.tools if t["function"]["name"] == "schedule_alarms")
    assert tool["description"] == "Alarm or reminder. " + RING_STUB
    assert tool["parameters"]["properties"]["action"] == {"type": "string", "enum": ["snooze", "stop"]}
    assert set(tool["parameters"]["properties"]) == {"action", "at", "id", "inMinutes"}  # no title, kind or limit
    assert "ringing now" in tool["parameters"]["properties"]["id"]["description"]
    assert mind.wire_to_op["schedule_alarms"] == "schedule.alarms" and mind.withheld == {}
    assert (mind.risk["schedule_alarms"], mind.confirms["schedule_alarms"]) == ("low_reversible", [])
    ringing = [{"id": "89abcdef", "kind": "alarm", "title": "sal a trabajar", "clock": "07:00"}]
    result = mind.decide(1, "silencia eso que me levanté hace rato", None, None, None, None, ringing)
    assert result["kind"] == "action" and result["operation"] == "schedule.alarms"
    assert result["arguments"] == {"action": "stop", "id": "89abcdef"}
    # the turn's note names the call, as with the whole tool
    assert any("schedule_alarms con action stop" in str(m.get("content")) for m in server.bodies[0]["messages"])


def test_another_tool_kept_off_is_the_stub_of_before_beside_the_alarms(tmp_path: Path) -> None:
    mind, _ = _mind(tmp_path, [])
    mind.configure({"capabilities": [OPEN], "withheld": [{"name": "schedule.alarms", "title": "Alarm or reminder"},
                                                         {"name": "audio.volume", "title": "Set the volume"},
                                                         "file.delete"]})
    stub = next(t["function"] for t in mind.tools if t["function"]["name"] == "audio_volume")
    assert stub == {"name": "audio_volume", "description": "Set the volume. " + OFF_STUB,
                    "parameters": {"type": "object", "properties": {}}}
    assert mind.withheld == {"audio_volume": "audio.volume", "file_delete": "file.delete"}
