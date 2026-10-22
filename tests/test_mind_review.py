"""Review of the mind (2026-10-22): each test holds one finding of the reviewers fixed in src/baxy_mind."""
import json
import urllib.error
from pathlib import Path

import pytest

from test_mind_final import _call, _mind, _say


def _calls(*calls: tuple[str, dict]) -> dict:
    return {"choices": [{"message": {"content": "", "tool_calls": [
        {"id": f"c{i}", "function": {"name": name, "arguments": json.dumps(arguments)}}
        for i, (name, arguments) in enumerate(calls, 1)]}}]}


def test_a_queued_call_does_not_run_after_the_call_before_it_failed(tmp_path: Path) -> None:
    # Review 1: app_open failed and input_text_type then typed into the person's own window.
    mind, server = _mind(tmp_path, [_calls(("app_open", {"appId": "Bloc de notas"}),
                                           ("input_text_type", {"text": "hola"})),
                                    _say("No pude abrir el Bloc de notas.")])
    mind.wire_to_op = {"app_open": "app.open", "input_text_type": "input.text.type"}
    assert mind.decide(1, "abre el bloc de notas y escribe hola")["operation"] == "app.open"
    result = mind.continue_turn(2, json.dumps({"status": "failed", "error": "application_not_found"}))
    assert result["kind"] == "conversation" and result["operation"] is None
    tools = {m["tool_call_id"]: m["content"] for m in server.bodies[-1]["messages"] if m["role"] == "tool"}
    assert json.loads(tools["c2"])["status"] == "not_run"


def test_a_queued_call_runs_after_the_call_before_it_completed(tmp_path: Path) -> None:
    mind, _ = _mind(tmp_path, [_calls(("app_open", {"appId": "Bloc de notas"}), ("input_text_type", {"text": "hola"}))])
    mind.wire_to_op = {"app_open": "app.open", "input_text_type": "input.text.type"}
    mind.decide(1, "abre el bloc de notas y escribe hola")
    assert mind.continue_turn(2, json.dumps({"status": "completed"}))["operation"] == "input.text.type"


class _Dead:
    returncode = 1

    def poll(self) -> int:
        return 1


@pytest.mark.parametrize("call", [
    lambda s: s.tokenize("hola"), lambda s: s.chat({"messages": []}),
    lambda s: s.complete_name({"messages": [], "tools": [], "chat_template_kwargs": {}}, "<tool_call>"),
    lambda s: s.fill_call({"messages": []}, "app_open")])
def test_a_dead_model_server_ends_the_mind_from_any_call(monkeypatch, call) -> None:
    # Review 2: only chat() exited, and tokenize (the history's trim) raised URLError first: the mind never relaunched.
    from baxy_mind import llm_server

    class Exited(Exception):
        pass

    def exit_(code: int) -> None:
        raise Exited(code)

    monkeypatch.setattr(llm_server.os, "_exit", exit_)
    server = llm_server.LlmServer("model.gguf", "llama-server.exe")
    server._process = _Dead()  # type: ignore[assignment]
    server._ready.set()
    with pytest.raises(Exited) as exited:
        call(server)
    assert exited.value.args == (70,)


def test_a_decision_that_failed_leaves_nothing_of_its_request_in_the_conversation(tmp_path: Path) -> None:
    # Review 2: the clock and the words of a failed decide stayed, and the next turn could run that old request.
    down = urllib.error.URLError(ConnectionRefusedError())
    mind, server = _mind(tmp_path, [_say("Hola."), down, _say("Son las siete.")])
    mind.decide(1, "hola")
    before = json.loads(json.dumps(mind.conversation))
    with pytest.raises(urllib.error.URLError):
        mind.decide(2, "borra la carpeta de descargas")
    assert mind.conversation == before
    mind.decide(3, "qué hora es")
    assert "borra la carpeta de descargas" not in json.dumps(server.bodies[-1]["messages"], ensure_ascii=False)


def test_an_answer_to_a_question_whose_decision_failed_still_answers_it_next_time(tmp_path: Path) -> None:
    down = urllib.error.URLError(ConnectionRefusedError())
    mind, server = _mind(tmp_path, [_call("ask_user", {"question": "¿A qué hora?"}), down,
                                    _call("schedule_alarms", {"time": "07:00"})])
    assert mind.decide(1, "pon una alarma")["kind"] == "clarify"
    with pytest.raises(urllib.error.URLError):
        mind.decide(2, "a las 7")
    assert mind.decide(3, "a las 7")["kind"] == "action"
    messages = server.bodies[-1]["messages"]
    assert [m["content"] for m in messages if m["role"] == "tool"] == ["a las 7"]
    assert [m["role"] for m in messages[-2:]] == ["assistant", "tool"]  # the answer, not a new request


def _snap_correction(tmp_path: Path, monkeypatch, filled: dict):
    # B-MED-1 (notebook traces): Qwen chose window_resolve, Laya window_snap, and fill_call wrote windowId "1", invented.
    from test_mind_doubt_policy import FakeSystemOne, _call as _doubted, _mind as _doubt_mind
    monkeypatch.setenv("BAXY_S1_DOUBT", "")
    monkeypatch.setenv("BAXY_S1_VETO", "0.6")
    monkeypatch.setenv("BAXY_S1_CORRECT", "1")
    reply = _doubted("window_resolve", {"query": "la ventana"}, 0.5)
    reply["choices"][0]["logprobs"]["content"][5]["top_logprobs"].append({"token": "app", "logprob": -0.7})
    mind, server = _doubt_mind(tmp_path, [reply, _say("¿Qué ventana pongo a la izquierda?")])
    server.complete_name = lambda body, written: "_snap"
    server.fill_call = lambda body, wire: {"name": wire, "arguments": filled, "timings": {}}
    schema = {"type": "object", "properties": {"windowId": {"type": "string"}, "position": {"type": "string"}},
              "required": ["windowId", "position"]}
    mind.tools = [{"type": "function", "function": {"name": n, "description": "Window. More.", "parameters": p}}
                  for n, p in (("window_resolve", {}), ("app_snap", schema))]
    mind.wire_to_op = {"window_resolve": "window.resolve", "app_snap": "app.snap"}
    mind.risk = {"window_resolve": "read_only", "app_snap": "low_reversible"}
    mind.system_one = FakeSystemOne("app_snap")  # type: ignore[assignment]
    return mind, server


def test_a_correction_with_an_argument_the_conversation_never_showed_asks(tmp_path: Path, monkeypatch) -> None:
    mind, server = _snap_correction(tmp_path, monkeypatch, {"windowId": "1", "position": "left"})
    result = mind.decide(1, "pon la ventana de la izquierda")
    assert result["kind"] == "conversation" and result["operation"] is None
    assert "app_snap" not in json.dumps([m.get("tool_calls") for m in server.bodies[-1]["messages"]])


def test_a_correction_missing_a_required_argument_asks(tmp_path: Path, monkeypatch) -> None:
    mind, _ = _snap_correction(tmp_path, monkeypatch, {"position": "left"})
    assert mind.decide(1, "pon la ventana 1 a la left")["operation"] is None


def test_a_correction_whose_arguments_the_person_said_runs(tmp_path: Path, monkeypatch) -> None:
    mind, _ = _snap_correction(tmp_path, monkeypatch, {"windowId": "1", "position": "Left"})
    result = mind.decide(1, "pon la ventana 1 a la left")
    assert result["operation"] == "app.snap" and result["arguments"] == {"windowId": "1", "position": "Left"}
