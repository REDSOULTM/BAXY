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


def test_asking_is_never_held(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BAXY_S1_DOUBT", "0.9")
    mind, _ = _mind(tmp_path, [_call("ask_user", {"question": "¿Qué cierro?"}, 0.2)])
    assert mind.decide(1, "ciérralo")["kind"] == "clarify"
