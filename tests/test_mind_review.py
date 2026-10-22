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


LONG = "https://news.google.com/rss/articles/" + "CBMi" + "x" * 300 + "?oc=5"
FOUND = json.dumps({"status": "completed", "observed": {"results": [{"title": "Lluvia", "url": LONG}]}})


def test_short_references_go_with_the_exported_session_and_a_new_session_forgets_them(tmp_path: Path,
                                                                                         monkeypatch) -> None:
    # Review 3: after a relaunch ref:r1 stood for another address, or for none.
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _mind(tmp_path, [_call("web_search", {"query": "clima"}), _say("Encontré una noticia.")])
    mind.decide(1, "el clima")
    mind.continue_turn(2, FOUND)
    kept = mind.export_session()
    relaunched, _ = _mind(tmp_path, [_call("web_fetch", {"url": "ref:r1"})])
    relaunched.load_session(kept)
    assert relaunched.conversation == [m for m in kept if m.get("role") in {"user", "assistant", "tool"}]
    assert relaunched.decide(3, "ábrela")["arguments"]["url"] == LONG
    relaunched.server.replies.append(_call("web_fetch", {"url": "ref:r1"}))
    relaunched.new_session()
    assert relaunched.decide(4, "ábrela")["arguments"]["url"] == "ref:r1"


def test_the_ids_the_mind_writes_never_repeat_in_a_session(tmp_path: Path, monkeypatch) -> None:
    # Review 13: confirm_{len(conversation)} repeated once the conversation was trimmed to the same length.
    from baxy_mind import mind as mind_module
    monkeypatch.setattr(mind_module, "HISTORY_TURNS", 1)
    mind, _ = _mind(tmp_path, [_say("¿Lo borro?"), _say("Listo."), _say("¿Lo borro?"), _say("Listo.")])
    ids = []
    for request in ("borra a.txt", "borra b.txt"):
        mind.decide(1, request)
        mind.confirm(2, True, "Sí")
        ids.append(mind.conversation[-1]["tool_calls"][0]["id"])
        mind.continue_turn(3, json.dumps({"status": "completed"}))
    kept = mind.export_session()
    mind.load_session(kept)
    mind.server.replies.append(_say("¿Lo borro?"))
    mind.decide(4, "borra c.txt")
    mind.confirm(5, True, "Sí")
    ids.append(mind.conversation[-1]["tool_calls"][0]["id"])
    assert len(set(ids)) == 3


def _rows(tmp_path: Path) -> list[dict]:
    return [json.loads(line) for line in (tmp_path / "turns.jsonl").read_text(encoding="utf-8").splitlines()]


def test_a_heartbeat_that_read_the_persons_memory_keeps_it_out_of_the_trace(tmp_path: Path) -> None:
    # Review 4: the heartbeat's JSON and its words carried what it deduced from memory into turns.jsonl.
    decision = {"pedido": "ninguno", "preferencia": "le gusta el jazz de noche", "vence": "nada", "bloqueo": "nada",
                "analisis": "Es de noche y le gusta el jazz.", "intervenir": True}
    mind, _ = _mind(tmp_path, [_say(json.dumps(decision, ensure_ascii=False)), _say("¿Te pongo jazz?")])
    mind.beat(1, {"now": "22:00", "memory": ["le gusta el jazz de noche"]})
    rows = _rows(tmp_path)
    assert "jazz" not in json.dumps(rows, ensure_ascii=False)
    assert rows[0]["intervene"] is True


def test_a_heartbeat_without_memory_keeps_its_trace(tmp_path: Path) -> None:
    decision = {"pedido": "ninguno", "preferencia": "ninguna", "vence": "nada", "bloqueo": "disco lleno",
                "analisis": "El disco está lleno.", "intervenir": True}
    mind, _ = _mind(tmp_path, [_say(json.dumps(decision, ensure_ascii=False)), _say("Tu disco está lleno.")])
    mind.beat(1, {"now": "22:00"})
    assert "disco lleno" in _rows(tmp_path)[0]["content"]


def test_a_doubted_memory_call_keeps_the_persons_words_out_of_the_trace(tmp_path: Path, monkeypatch) -> None:
    from test_mind_doubt_policy import _call as _doubted, _mind as _doubt_mind
    monkeypatch.setenv("BAXY_S1_DOUBT", "0.9")
    mind, _ = _doubt_mind(tmp_path, [_doubted("memory_save", {"text": "mi clave es 4321"}, 0.3), _say("¿Lo guardo?")])
    mind.wire_to_op["memory_save"] = "memory.save"
    mind.decide(1, "recuerda que mi clave es 4321")
    assert "4321" not in json.dumps(_rows(tmp_path), ensure_ascii=False)


def test_the_tool_chosen_is_not_completed_again_as_its_own_rival(tmp_path: Path, monkeypatch) -> None:
    # Review 9: the first «rival» was the chosen token itself: one more call to the server and one less real rival.
    from test_mind_doubt_policy import _layer2, _rival_call
    mind, server, _ = _layer2(tmp_path, monkeypatch, "system_power", [_rival_call(0.5)])
    written: list[str] = []
    server.complete_name = lambda body, text: written.append(text) or "_close"
    mind.decide(1, "apaga el pc")
    assert [text[-3:] for text in written] == ["app"]
