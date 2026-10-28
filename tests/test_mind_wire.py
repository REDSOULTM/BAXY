"""The names the model sees for the tools (wire names) are told apart by their shape (PC-C72): no name is a proper prefix
of another one, none is another one but for «_» or for the order of its parts, and each goes back to its operation.
A short name that was a prefix (audio_volume ⊂ audio_volume_adjust) made the 4B go on writing the long one."""
import json
import re
from pathlib import Path

from test_mind_final import _call, _mind, _say

_DATA = Path(__file__).resolve().parents[1] / "src" / "baxy_mind" / "data" / "tool_descriptions.en.v1.json"
_OPERATIONS = list(json.loads(_DATA.read_text(encoding="utf-8"))["tools"])


def _configured(tmp_path: Path, operations: list[str]):
    mind, server = _mind(tmp_path, [])
    mind.configure({"capabilities": [{"name": op, "description": f"Does {op}.", "risk": "low_reversible",
                                      "argumentsSchema": {"type": "object", "properties": {}}} for op in operations]})
    return mind, server


def _clashes(names: list[str]) -> list[tuple[str, str, str]]:
    found = []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if a == b:
                found.append(("same name", a, b))
            elif b.startswith(a + "_") or a.startswith(b + "_"):
                found.append(("proper prefix", a, b))
            elif a.replace("_", "") == b.replace("_", ""):
                found.append(("only «_»", a, b))
            elif sorted(a.split("_")) == sorted(b.split("_")):
                found.append(("order of parts", a, b))
    return found


def test_no_tool_name_the_model_sees_clashes_by_shape_with_another_over_the_whole_catalog(tmp_path: Path) -> None:
    mind, _ = _configured(tmp_path, _OPERATIONS)
    names = [t["function"]["name"] for t in mind.tools]
    assert len(names) == len(_OPERATIONS) + 3  # ask_user, confirm_pending, calculate
    assert _clashes(names) == []


def test_every_operation_goes_to_its_wire_name_and_back(tmp_path: Path) -> None:
    mind, _ = _configured(tmp_path, _OPERATIONS)
    seen = {t["function"]["name"] for t in mind.tools}
    for op in _OPERATIONS:
        wire = mind.wires.name(op)
        assert wire in seen and mind.wire_to_op[wire] == op and mind.wires.operation(wire) == op


def test_the_short_name_of_a_pair_gets_a_suffix_and_its_plain_name_still_reads_back(tmp_path: Path) -> None:
    from baxy_mind.wire import Wires
    wires = Wires(["x.level", "x.level.adjust", "y.go", "y.go.named", "z.one"])
    assert wires.name("x.level") == "x_level_set" and wires.name("x.level.adjust") == "x_level_adjust"
    assert wires.name("y.go") == "y_go_set" and wires.name("z.one") == "z_one"
    assert wires.renamed() == {"x.level": "x_level_set", "y.go": "y_go_set"}
    # Older receipts and histories said the plain name: it still reads as its operation.
    assert wires.operation("x_level") == "x.level" and wires.operation("x_level_set") == "x.level"
    assert wires.operation("x.level") == "x.level" and wires.operation("q_r") == "q.r"


def test_a_suffix_that_would_clash_takes_the_next_free_one() -> None:
    from baxy_mind.wire import Wires
    # The suffixed name is taken by another operation, or would be a prefix of one: the next suffix.
    taken = Wires(["a.b", "a.b.set", "a.b.set.c"])
    names = [taken.name(op) for op in ["a.b", "a.b.set", "a.b.set.c"]]
    assert _clashes(names) == [] and [taken.operation(n) for n in names] == ["a.b", "a.b.set", "a.b.set.c"]
    # A chain of prefixes: every short one gets its own name.
    chain = Wires(["m", "m.n", "m.n.o"])
    names = [chain.name(op) for op in ["m", "m.n", "m.n.o"]]
    assert _clashes(names) == [] and names[2] == "m_n_o"


def test_the_descriptions_cite_the_names_the_model_sees(tmp_path: Path) -> None:
    mind, _ = _mind(tmp_path, [])
    mind.configure({"capabilities": [{"name": op, "description": "", "argumentsSchema": {"type": "object"}}
                                     for op in _OPERATIONS]})
    names = {t["function"]["name"] for t in mind.tools}
    plain = {op.replace(".", "_") for op in _OPERATIONS}
    for tool in mind.tools:
        texts = [tool["function"]["description"]] + [
            str(p.get("description") or "") for p in tool["function"]["parameters"].get("properties", {}).values()]
        for text in texts:
            cited = set(re.findall(r"\b[a-z]+(?:_[a-z0-9]+)+\b", text)) & plain
            assert cited <= names, (tool["function"]["name"], cited - names)
    level = next(t for t in mind.tools if t["function"]["name"] == mind.wires.name("audio.volume.adjust"))
    assert f"(that one is {mind.wires.name('audio.volume')})" in level["function"]["description"]


def test_a_call_by_the_new_name_runs_its_operation_and_the_receipt_keeps_it(tmp_path: Path) -> None:
    mind, server = _configured(tmp_path, _OPERATIONS)
    wire = mind.wires.name("audio.volume")
    server.replies.extend([_call(wire, {"level": 20}), _say("Listo.")])
    step = mind.decide(1, "baja el volumen a 20")
    assert step["kind"] == "action" and step["operation"] == "audio.volume"
    mind.continue_turn(2, json.dumps({"status": "completed", "observed": {"level": 20}}))
    receipt = mind._turn["receipts"][0] if mind._turn else None
    assert receipt is None or (receipt["op"] == "audio.volume" and receipt["tool"] == wire)


def test_the_notes_of_a_pending_or_ended_call_say_its_new_name(tmp_path: Path) -> None:
    from baxy_mind.mind import ended_result
    mind, server = _configured(tmp_path, _OPERATIONS)
    wire = mind.wires.name("audio.volume")
    server.replies.append(_say("¿Lo bajo?"))
    mind.decide(1, "sí", pending={"operation": "audio.volume", "arguments": {"level": 20}})
    assert f"[Espera el sí de la persona: {wire} " in server.bodies[0]["messages"][-2]["content"]
    told = json.loads(ended_result({"operation": "audio.volume", "ended": "expired"}, mind.wires.name))
    assert f"call {wire} again" in told["next"]
