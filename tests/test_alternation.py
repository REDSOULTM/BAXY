"""MODX2: a model whose chat template wants the person's and the model's messages to alternate (MOD2 §4: Ministral-3-8B
answered every turn 500 «conversation roles must alternate», because the mind writes its notes as the person's
messages, after the person's own or after a call's results). What the template wants is read from it at the start, and
every conversation sent to it is joined as Mistral's own tokenizer joins one (alternation.py); a template that takes
them as they are gets the very same request."""
import io
import json
import urllib.error
from pathlib import Path

import pytest

from baxy_mind import alternation, call_format, llm_server
from plantillas_llamada import ministral3, qwen35

SYSTEM = {"role": "system", "content": "Eres BAXY."}
ASKED = {"role": "user", "content": "pon una alarma a las siete"}
CALL = {"role": "assistant", "content": "", "tool_calls": [{"id": "c0", "type": "function", "function": {
    "name": "alarm_set", "arguments": json.dumps({"time": "07:00"})}}]}
RESULT = {"role": "tool", "tool_call_id": "c0", "content": "Alarma puesta a las 07:00."}
NOTE = {"role": "user", "content": "[Nota interna, no la escribió la persona: comprueba el resultado.]"}


class _Reply(io.BytesIO):
    status = 200


def _server(monkeypatch, tmp_path: Path, template) -> tuple[llm_server.LlmServer, list[dict]]:
    """The mind's server object against a llama-server double whose template is ``template``: a conversation the
    template raises on is refused with a 500, as llama-server refuses it (MOD2, the 500 of every Ministral turn)."""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setenv("BAXY_VISION_SLOT_DIR", str(tmp_path / "slots"))
    monkeypatch.setattr(llm_server.threading.Thread, "start", lambda self: None)
    server = llm_server.LlmServer("model.gguf", "llama-server.exe")
    server._ready.set()
    sent: list[dict] = []

    def urlopen(request, timeout):
        body = json.loads(request.data or b"{}")
        sent.append(body)
        try:
            prompt = template(body["messages"], body.get("tools") or [], body.get("add_generation_prompt", True))
        except ValueError as error:
            raise urllib.error.HTTPError(request.full_url, 500, str(error), {}, io.BytesIO(b"{}")) from error
        if request.selector == "/apply-template":
            return _Reply(json.dumps({"prompt": prompt}).encode("utf-8"))
        return _Reply(json.dumps({"choices": [{"message": {"content": "Listo."}, "finish_reason": "stop"}],
                                  "prompt": prompt}).encode("utf-8"))

    monkeypatch.setattr(llm_server.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(llm_server.time, "sleep", lambda seconds: None)
    return server, sent


def test_a_template_that_wants_turns_to_alternate_is_read_and_a_note_after_a_result_reaches_it(monkeypatch,
                                                                                               tmp_path) -> None:
    server, sent = _server(monkeypatch, tmp_path, ministral3)
    server.alternate = alternation.required(server.render)
    assert server.alternate
    reply = server.chat({"messages": [SYSTEM, ASKED, CALL, RESULT, NOTE]})
    assert reply["choices"][0]["message"]["content"] == "Listo."
    # The note is read where it was, right after the result, with nothing of it changed.
    assert sent[-1]["messages"][-1] == {**RESULT, "content": f"{RESULT['content']}\n\n{NOTE['content']}"}
    assert "Alarma puesta a las 07:00.\n\n[Nota interna" in ministral3(sent[-1]["messages"], [], True)


def test_two_messages_of_the_person_in_a_row_are_joined_as_mistrals_own_tokenizer_joins_them(monkeypatch,
                                                                                             tmp_path) -> None:
    server, sent = _server(monkeypatch, tmp_path, ministral3)
    server.alternate = alternation.required(server.render)
    server.chat({"messages": [SYSTEM, ASKED, NOTE]})
    assert sent[-1]["messages"] == [SYSTEM, {"role": "user", "content": f"{ASKED['content']}\n\n{NOTE['content']}"}]
    # The read ahead and a call's arguments render the same conversation.
    assert server.template({"messages": [SYSTEM, ASKED, NOTE], "tools": [], "chat_template_kwargs": {}})


def test_its_call_format_is_read_through_the_joined_probes(monkeypatch, tmp_path) -> None:
    server, _ = _server(monkeypatch, tmp_path, ministral3)
    # As the 1.5.5 read it: the probe of a call refused (a note after its result), no template read, so the mind kept
    # Qwen3.5's format for this model.
    with pytest.raises(call_format.Unrendered):
        call_format.derive(server.render)
    server.alternate = alternation.required(server.render)
    fmt = call_format.derive(server.render)
    assert fmt is not None and fmt.opening == "[TOOL_CALLS]" and fmt.name_end == "[ARGS]{"


def test_a_template_that_takes_the_turns_as_they_come_gets_the_very_same_request(monkeypatch, tmp_path) -> None:
    server, sent = _server(monkeypatch, tmp_path, qwen35)
    assert not alternation.required(server.render)
    body = {"messages": [SYSTEM, ASKED, CALL, RESULT, NOTE], "tools": []}
    server.chat(body)
    assert sent[-1]["messages"] == body["messages"]


def test_the_conversation_given_is_never_changed_in_place() -> None:
    messages = [SYSTEM, dict(ASKED), dict(NOTE)]
    before = json.dumps(messages)
    alternation.fold(messages)
    assert json.dumps(messages) == before
    # A reply in words, a call and its result are not counted: a conversation that alternates is the same.
    turn2 = [SYSTEM, ASKED, CALL, RESULT, {"role": "assistant", "content": "Listo."}, {"role": "user", "content": "ok"}]
    assert alternation.fold(turn2) == turn2
