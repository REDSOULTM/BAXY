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
