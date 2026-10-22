"""Review of the mind (2026-10-22): each test holds one finding of the reviewers fixed in src/baxy_mind."""
import json
from pathlib import Path

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
