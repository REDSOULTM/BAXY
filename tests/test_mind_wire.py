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
            elif b.startswith(a) or a.startswith(b):
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
        assert wire in seen and mind.wire_to_op[wire] == op and mind.wires.known(wire) == op
        # Older receipts and kept sessions said the plain name: it still reads as its operation.
        assert mind.wires.known(op.replace(".", "_")) == op


def test_the_short_name_of_a_pair_gets_a_suffix_and_the_others_keep_theirs() -> None:
    from baxy_mind.wire import Wires
    wires = Wires(["x.level", "x.level.adjust", "y.go", "y.go.named", "z.one", "w.find", "w.finds"])
    assert [wires.name(op) for op in ["x.level", "x.level.adjust", "y.go", "y.go.named", "z.one", "w.find",
                                      "w.finds"]] == [
        "x_level_set", "x_level_adjust", "y_go_set", "y_go_named", "z_one", "w_find_set", "w_finds"]
    assert wires.known("x_level") == "x.level" and wires.known("x_level_set") == "x.level"
    assert wires.known("q_r") is None and wires.name("q.r") == "q_r"


def test_a_suffix_that_would_clash_by_shape_takes_the_next_free_one() -> None:
    from baxy_mind.wire import Wires
    for operations, short, expected in [
            (["a.b", "a.b.c", "a.b.set"], "a.b", "a_b_2set"),  # the suffixed name is another tool's
            (["a.b", "a.b.c", "a.bset"], "a.b", "a_b_2set"),  # the same but for «_»
            (["a.b", "a.b.c", "set.a.b"], "a.b", "a_b_2set"),  # the same parts in another order
            (["a.b", "a.b.c", "a.b.set.d"], "a.b", "a_b_2set"),  # a prefix of another tool's
            (["a.b", "a.b.c"], "a.b", "a_b_set")]:
        wires = Wires(operations)
        names = [wires.name(op) for op in operations]
        assert wires.name(short) == expected and _clashes(names) == [], operations
        assert [wires.known(n) for n in names] == operations
    # A chain of prefixes: every short one gets its own name; one the same as a fixed tool's is renamed too.
    chain = Wires(["m", "m.n", "m.n.o", "ask"], fixed=["ask_user"])
    names = [chain.name(op) for op in ["m", "m.n", "m.n.o", "ask"]]
    assert _clashes(names + ["ask_user"]) == [] and names[2] == "m_n_o"


def test_a_cited_name_is_rewritten_only_whole() -> None:
    from baxy_mind.wire import Wires
    wires = Wires(["x.level", "x.level.adjust"])
    assert wires.cite("(use x_level or x_level_adjust). That one is x_level.") ==         "(use x_level_set or x_level_adjust). That one is x_level_set."
    assert wires.cite("x_levels, ax_level, x.level") == "x_levels, ax_level, x.level"
    assert Wires(["z.one"]).cite("z_one") == "z_one"


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
    step = mind.decide(1, "deja el sonido en veinte por ciento")
    assert step["kind"] == "action" and step["operation"] == "audio.volume"
    mind.continue_turn(2, json.dumps({"status": "completed", "observed": {"level": 20}}))
    receipt = mind._turn["receipts"][0]
    assert receipt["op"] == "audio.volume" and receipt["tool"] == wire and receipt["completed"]
    assert any(row["function"]["name"] == wire for m in mind._turn["conv"] for row in m.get("tool_calls") or [])


def test_the_notes_of_a_pending_or_ended_call_say_its_new_name(tmp_path: Path) -> None:
    from baxy_mind.mind import ended_result
    mind, server = _configured(tmp_path, _OPERATIONS)
    wire = mind.wires.name("audio.volume")
    server.replies.append(_say("¿Lo bajo?"))
    mind.decide(1, "sí", pending={"operation": "audio.volume", "arguments": {"level": 20}})
    assert f"[Espera el sí de la persona: {wire} " in server.bodies[0]["messages"][-2]["content"]
    told = json.loads(ended_result({"operation": "audio.volume", "ended": "expired"}, mind.wires.name))
    assert f"call {wire} again" in told["next"]


def test_a_session_kept_with_the_plain_names_reads_back_with_the_names_shown(tmp_path: Path) -> None:
    mind, _ = _configured(tmp_path, _OPERATIONS)
    old = "message_send"
    new = mind.wires.name("message.send")
    assert new != old
    kept = [{"role": "user", "content": "manda el mensaje"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c1", "type": "function", "function": {"name": old, "arguments": "{}"}}]},
            {"role": "tool", "tool_call_id": "c1", "content": json.dumps({"status": "failed"})},
            {"role": "baxy.session", "ran": [f"{old} → falló"], "ran_count": 1, "calls": []}]
    mind.load_session(kept)
    assert mind.conversation[1]["tool_calls"][0]["function"]["name"] == new
    assert kept[1]["tool_calls"][0]["function"]["name"] == old  # the App's copy is not touched
    assert mind._ran == [f"{new} → falló"]
    assert mind._tries(mind.conversation) == [("message.send", "failed")]


def test_every_tool_name_written_in_the_mind_is_one_the_catalog_shows() -> None:
    # A literal wire name in the mind's code (web_search, app_open) is compared with what the model wrote: it must be
    # the name shown, or the comparison stops matching without a word when a catalog renames it.
    from baxy_mind.wire import Wires
    wires = Wires(_OPERATIONS)
    source = (Path(__file__).resolve().parents[1] / "src" / "baxy_mind" / "mind.py").read_text(encoding="utf-8")
    written = set(re.findall(r"[\"']([a-z]+(?:_[a-z0-9]+)+)[\"']", source))
    plain = {op.replace(".", "_"): op for op in _OPERATIONS}
    stale = sorted(name for name in written & set(plain) if wires.name(plain[name]) != name)
    assert stale == []


def test_the_reference_of_wire_names_the_app_reads_is_what_the_mind_gives_over_the_whole_catalog() -> None:
    """tests/fixtures/wire_names.v1.json is what the App's WireNames is checked against (WireNamesTests) and what the
    scripts with no catalog at hand read (scripts/renew/wire_names.py): it stays what Wires gives the mind's catalog,
    with the mind's own tools beside it, so the names the App cites never part from the ones the model sees."""
    from baxy_mind.mind import ASK_USER, CALCULATE, CONFIRM
    from baxy_mind.wire import Wires
    reference = json.loads((Path(__file__).resolve().parent / "fixtures" / "wire_names.v1.json").read_text(
        encoding="utf-8"))
    fixed = [tool["function"]["name"] for tool in (ASK_USER, CONFIRM, CALCULATE)]
    assert reference["fixed"] == fixed
    assert sorted(reference["names"]) == sorted(_OPERATIONS)
    wires = Wires(list(reference["names"]), fixed=fixed)
    assert reference["names"] == {op: wires.name(op) for op in reference["names"]}
