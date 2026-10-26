"""System One, layer 0 in the mind (BAXY_S1_DOUBT): an action the model was not sure of does not run; the model asks."""
import json
import math
from pathlib import Path

import pytest

from baxy_mind.mind import Mind


class FakeServer:
    context = 49152

    def __init__(self, replies: list) -> None:
        self.replies = replies
        self.bodies: list[dict] = []

    def chat(self, body: dict) -> dict:
        self.bodies.append(json.loads(json.dumps(body)))
        return self.replies.pop(0)

    def template(self, body: dict) -> str:
        return "PROMPT"


def _token(text: str, p: float) -> dict:
    return {"token": text, "logprob": math.log(p), "top_logprobs": [{"token": text, "logprob": math.log(p)}]}


def _call(name: str, arguments: dict, p_name: float) -> dict:
    head, tail = name.split("_", 1)
    logprobs = [_token("<tool_call>", 0.95), _token("\n", 1.0), _token("<", 1.0), _token("function", 1.0),
                _token("=", 1.0), _token(head, p_name), _token("_" + tail, 1.0), _token(">", 1.0)]
    return {"choices": [{"message": {"content": "", "tool_calls": [
        {"id": "c1", "function": {"name": name, "arguments": json.dumps(arguments)}}]},
        "logprobs": {"content": logprobs}}]}


def _say(text: str) -> dict:
    return {"choices": [{"message": {"content": text}}]}


def _mind(tmp_path: Path, replies: list) -> tuple[Mind, FakeServer]:
    server = FakeServer(replies)
    mind = Mind(server, tmp_path / "turns.jsonl")  # type: ignore[arg-type]
    mind.call_tokens = [248058]
    mind.wire_to_op = {"system_power": "system.power", "app_open": "app.open"}
    return mind, server


def test_an_unsure_action_does_not_run_and_the_model_asks_in_its_own_words(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BAXY_S1_DOUBT", "0.4")
    mind, server = _mind(tmp_path, [_call("system_power", {"action": "shutdown"}, 0.3),
                                    _say("¿Qué quieres que cierre: la ventana de delante o el PC?")])
    result = mind.decide(1, "ahora ciérralo")
    assert result["kind"] == "conversation"
    assert result["operation"] is None
    assert result["reply"] == "¿Qué quieres que cierre: la ventana de delante o el PC?"
    second = server.bodies[1]
    assert second["tool_choice"] == "none"
    assert "system_power" in second["messages"][-1]["content"]
    assert not any(m.get("tool_calls") for m in second["messages"])  # the call it nearly made is not in the conversation
    rows = [json.loads(line) for line in (tmp_path / "turns.jsonl").read_text(encoding="utf-8").splitlines()]
    assert rows[0]["kind"] == "doubt_ask" and rows[0]["operation"] == "system.power"
    assert rows[0]["doubt"]["confidence"] < 0.4


@pytest.mark.parametrize("threshold", ["", "0.4"])
def test_a_sure_action_or_layer_0_off_runs_as_before(tmp_path, monkeypatch, threshold) -> None:
    monkeypatch.setenv("BAXY_S1_DOUBT", threshold)
    p_name = 0.3 if not threshold else 0.99
    mind, _ = _mind(tmp_path, [_call("app_open", {"appId": "Spotify"}, p_name)])
    result = mind.decide(1, "abre spotify")
    assert result["kind"] == "action" and result["operation"] == "app.open"


# Holdout v6 V6E052 («bórrame plan_b.txt de la carpeta BAXY-bench», s0): held at 0.35, the model asked «¿Quieres que
# borre plan_b.txt…?» in words and nothing waited for the answer. A call the kernel confirms whatever its arguments (a
# risk of CONFIRMED_RISKS in normal mode) is not held by layer 0: its confirmation names the exact action. In Bypass, or
# for system.power (normal mode runs it unasked), layer 0 holds it as before. Ablación e: only with
# BAXY_S1_PASS_CONFIRMED=1; by default layer 0 holds it as in cien (V6D131 of the decision bench).
@pytest.mark.parametrize("passing,mode,wire,risk,held", [
    ("1", None, "filesystem_known_trash_named", "recoverable_delete", False),
    ("1", "bypass", "filesystem_known_trash_named", "recoverable_delete", True),
    ("1", None, "system_power", "work_loss", True),
    (None, None, "filesystem_known_trash_named", "recoverable_delete", True),
    (None, None, "app_close", "work_loss", True),
])
def test_layer_0_leaves_to_the_kernel_a_call_it_confirms(tmp_path, monkeypatch, passing, mode, wire, risk,
                                                         held) -> None:
    monkeypatch.setenv("BAXY_S1_DOUBT", "0.4")
    if passing:
        monkeypatch.setenv("BAXY_S1_PASS_CONFIRMED", passing)
    else:
        monkeypatch.delenv("BAXY_S1_PASS_CONFIRMED", raising=False)
    monkeypatch.setenv("BAXY_DATA_DIR", str(tmp_path))
    if mode:
        (tmp_path / "confirmation-mode").write_text(mode, encoding="utf-8")
    mind, _ = _mind(tmp_path, [_call(wire, {"fileName": "plan_b.txt"}, 0.3), _say("¿Quieres que borre plan_b.txt?")])
    mind.wire_to_op["filesystem_known_trash_named"] = "filesystem.known.trash.named"
    mind.risk = {wire: risk}
    result = mind.decide(1, "bórrame plan_b.txt de la carpeta BAXY-bench")
    assert (result["kind"] == "conversation") is held
    assert (result["operation"] is None) is held


class FakeSystemOne:
    ready = True

    def __init__(self, choice) -> None:
        self.choice = choice
        self.asked: list[dict] = []

    def choose(self, text, history, options):
        self.asked.append({"text": text, "options": dict(options)})
        if self.choice is None:
            return None  # not up yet, or failed: the turn goes on as the model decided
        return {"choice": self.choice, "p": 0.9, "probabilities": {self.choice: 0.9}, "ms": 140}


def _layer2(tmp_path, monkeypatch, choice, replies):
    monkeypatch.setenv("BAXY_S1_DOUBT", "")
    monkeypatch.setenv("BAXY_S1_VETO", "0.6")
    mind, server = _mind(tmp_path, replies)
    server.complete_name = lambda prompt, written: "_close"  # the rest of the rival «app»: app_close
    mind.tools = [{"type": "function", "function": {"name": n, "description": d + ". More.", "parameters": {}}}
                  for n, d in (("system_power", "Shut down the PC"), ("app_close", "Close an application"))]
    one = FakeSystemOne(choice)
    mind.system_one = one  # type: ignore[assignment]
    return mind, server, one


def _rival_call(p_name: float) -> dict:
    reply = _call("system_power", {"action": "shutdown"}, p_name)
    name = reply["choices"][0]["logprobs"]["content"][5]
    name["top_logprobs"].append({"token": "app", "logprob": math.log(1 - p_name)})
    return reply


def test_layer2_holds_an_unsure_action_the_decision_model_reads_otherwise(tmp_path, monkeypatch) -> None:
    mind, server, one = _layer2(tmp_path, monkeypatch, "app_close",
                                [_rival_call(0.5), _say("¿Cierro la ventana de delante o apago el PC?")])
    result = mind.decide(1, "ahora ciérralo")
    assert result["kind"] == "conversation" and result["operation"] is None
    assert set(one.asked[0]["options"]) == {"system_power", "app_close", "ask_user", "responder_con_palabras"}
    assert one.asked[0]["options"]["app_close"] == "Close an application."
    note = server.bodies[1]["messages"][-1]["content"]
    assert "system_power" in note and "app_close" in note
    rows = [json.loads(line) for line in (tmp_path / "turns.jsonl").read_text(encoding="utf-8").splitlines()]
    assert rows[0]["system_one"]["choice"] == "app_close"


@pytest.mark.parametrize("choice", ["system_power", None])
def test_layer2_lets_the_action_run_when_the_decision_model_agrees_or_is_not_up(tmp_path, monkeypatch, choice) -> None:
    mind, _, _ = _layer2(tmp_path, monkeypatch, choice, [_rival_call(0.5)])
    assert mind.decide(1, "apaga el pc")["operation"] == "system.power"


def test_layer2_is_not_asked_when_the_model_is_sure(tmp_path, monkeypatch) -> None:
    mind, _, one = _layer2(tmp_path, monkeypatch, "app_close", [_rival_call(0.95)])
    assert mind.decide(1, "apaga el pc")["operation"] == "system.power"
    assert one.asked == []


def test_asking_is_never_held(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BAXY_S1_DOUBT", "0.9")
    mind, _ = _mind(tmp_path, [_call("ask_user", {"question": "¿Qué cierro?"}, 0.2)])
    assert mind.decide(1, "ciérralo")["kind"] == "clarify"


def _correcting(tmp_path, monkeypatch, risk: str, filled):
    monkeypatch.setenv("BAXY_S1_CORRECT", "1")
    mind, server, one = _layer2(tmp_path, monkeypatch, "app_close",
                                [_rival_call(0.5), _say("¿Cierro la ventana de delante o apago el PC?")])
    mind.wire_to_op["app_close"] = "app.close"
    mind.risk = {"system_power": "work_loss", "app_close": risk}
    fills: list[str] = []

    def fill_call(body, wire):
        fills.append(wire)
        return filled

    server.fill_call = fill_call
    return mind, server, fills


def test_layer2_corrects_to_a_harmless_tool_the_model_fills_itself(tmp_path, monkeypatch) -> None:
    mind, server, fills = _correcting(tmp_path, monkeypatch, "low_reversible",
                                      {"name": "app_close", "arguments": {"appId": "Spotify"}, "timings": {}})
    result = mind.decide(1, "ahora ciérralo")
    assert result["kind"] == "action" and result["operation"] == "app.close"
    assert result["arguments"] == {"appId": "Spotify"}
    assert fills == ["app_close"] and len(server.bodies) == 1  # no second decision: the model only filled the tool
    rows = [json.loads(line) for line in (tmp_path / "turns.jsonl").read_text(encoding="utf-8").splitlines()]
    assert rows[0]["system_one"]["corrected"] is True


@pytest.mark.parametrize("risk, filled", [
    # a tool the kernel does not always confirm is never put in its mouth (work_loss: test_mind_system_one_max.py)
    ("external_communication", {"name": "app_close", "arguments": {}, "timings": {}}),
    ("low_reversible", None),  # the model did not write that call
    ("low_reversible", {"name": "system_power", "arguments": {}, "timings": {}})])
def test_layer2_asks_when_it_cannot_correct(tmp_path, monkeypatch, risk, filled) -> None:
    mind, _, _ = _correcting(tmp_path, monkeypatch, risk, filled)
    result = mind.decide(1, "ahora ciérralo")
    assert result["kind"] == "conversation" and result["operation"] is None


@pytest.mark.parametrize("effects, operation", [(["window_input"], None), (["network"], None), (None, "app.close")])
def test_layer2_never_corrects_to_a_tool_with_an_effect_of_the_catalog(tmp_path, monkeypatch, effects,
                                                                         operation) -> None:
    # Al máximo 5.1: a tool that sends keys, clicks or commands to a window, or what the model wrote out of the PC, is
    # never filled by «corrige», whatever its risk; a catalog without the field (the saved measurement ones) corrects by
    # risk alone, as before.
    mind, _, fills = _correcting(tmp_path, monkeypatch, "low_reversible",
                                 {"name": "app_close", "arguments": {"appId": "Spotify"}, "timings": {}})
    empty = {"type": "object", "properties": {}, "required": [], "additionalProperties": False}
    close = {"name": "app.close", "description": "Close an application", "argumentsSchema": empty,
             "risk": "low_reversible"}
    if effects is not None:
        close["effects"] = effects
    mind.configure({"capabilities": [{"name": "system.power", "description": "Shut down the PC",
                                      "argumentsSchema": empty, "risk": "work_loss"}, close]})
    assert mind.decide(1, "ahora ciérralo")["operation"] == operation
    assert fills == ([] if operation is None else ["app_close"])


def test_layer2_does_not_correct_when_correcting_is_off(tmp_path, monkeypatch) -> None:
    mind, _, fills = _correcting(tmp_path, monkeypatch, "low_reversible",
                                 {"name": "app_close", "arguments": {}, "timings": {}})
    monkeypatch.setenv("BAXY_S1_CORRECT", "")
    assert mind.decide(1, "ahora ciérralo")["operation"] is None
    assert fills == []


def test_layer_0_asks_once_per_misunderstanding(tmp_path, monkeypatch) -> None:
    # 4.2 (SAGE-Agent): the person's answer to BAXY's doubt question was held again by the same doubt, with no limit.
    monkeypatch.setenv("BAXY_S1_DOUBT", "0.4")
    mind, _ = _mind(tmp_path, [_call("system_power", {"action": "shutdown"}, 0.3), _say("¿Qué cierro?"),
                               _call("system_power", {"action": "shutdown"}, 0.3),
                               _call("system_power", {"action": "shutdown"}, 0.3), _say("¿Qué cierro?")])
    assert mind.decide(1, "ciérralo")["operation"] is None
    assert mind.decide(2, "el PC")["operation"] == "system.power"  # its answer: layer 0 does not ask again
    mind.continue_turn(3, json.dumps({"status": "cancelled"}))
    assert mind.decide(4, "ciérralo otra vez")["operation"] is None  # a new request is held as before


def test_the_answer_to_ask_user_is_not_held_by_layer_0(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BAXY_S1_DOUBT", "0.4")
    mind, _ = _mind(tmp_path, [_call("ask_user", {"question": "¿Qué cierro?"}, 0.9),
                               _call("system_power", {"action": "shutdown"}, 0.3)])
    assert mind.decide(1, "ciérralo")["kind"] == "clarify"
    assert mind.decide(2, "el PC")["operation"] == "system.power"


def test_the_answer_to_a_doubt_question_goes_to_layer_2(tmp_path, monkeypatch) -> None:
    mind, server, one = _layer2(tmp_path, monkeypatch, "app_close",
                                [_rival_call(0.3), _say("¿Cierro la ventana o apago el PC?"), _rival_call(0.3),
                                 _say("¿La ventana de delante o el PC entero?")])
    monkeypatch.setenv("BAXY_S1_DOUBT", "0.4")
    assert mind.decide(1, "ciérralo")["operation"] is None
    assert one.asked == []  # layer 0 asked first
    assert mind.decide(2, "eso")["operation"] is None
    assert len(one.asked) == 1  # the answer: the decision model reads it, and it asks (with its other option)
    assert "app_close" in server.bodies[-1]["messages"][-1]["content"]


@pytest.mark.parametrize("approve,p_name,held", [(True, 0.78, True), (True, 0.999, False), (False, 0.78, False)])
def test_a_yes_the_model_is_not_sure_of_is_held_and_asked(tmp_path, monkeypatch, approve, p_name, held) -> None:
    # Confirmaciones 2026-10-23: «sí pero el otro» approved a pending trash at 0.77-0.79; plain yeses were ≥ 0.998.
    monkeypatch.delenv("BAXY_S1_DOUBT", raising=False)
    monkeypatch.delenv("BAXY_CONFIRM_FLOOR", raising=False)
    reply = _call("confirm_pending", {"approve": approve}, p_name)
    reply["choices"][0]["logprobs"]["content"][0] = _token("<tool_call>", 1.0)  # the call itself is sure, as on the model
    mind, server = _mind(tmp_path, [reply, _say("¿Cuál archivo quieres que mande a la papelera?")])
    pending = {"operation": "filesystem.known.trash.named", "arguments": {"fileName": "notas.txt"}}
    result = mind.decide(1, "sí pero el otro", pending)
    if held:
        assert result["kind"] == "conversation" and result["operation"] is None
        assert "confirm_pending" in server.bodies[1]["messages"][-1]["content"]
    else:
        assert result["kind"] == "action" and result["operation"] == "confirmation.answer"
        assert result["arguments"]["approve"] is approve


def test_the_confirm_floor_can_be_turned_off(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BAXY_CONFIRM_FLOOR", "0")
    mind, _ = _mind(tmp_path, [_call("confirm_pending", {"approve": True}, 0.5)])
    result = mind.decide(1, "sí", {"operation": "app.close", "arguments": {"appId": "Paint"}})
    assert result["operation"] == "confirmation.answer"
