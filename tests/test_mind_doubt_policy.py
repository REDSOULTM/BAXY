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


class FakeSystemOne:
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
    server.complete_name = lambda body, written: "_close"  # the rest of the rival «app»: app_close
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
