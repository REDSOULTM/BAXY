"""MOD4: a closed question of the mind (a grammar of literals: the person's «sí», the agreement, the alarm that rings) goes
to Ollama and to the APIs as the output schema each one takes, since none takes a GBNF grammar; one that refuses it is
asked the plain question again, and is not sent the schema any more."""

from __future__ import annotations

import json
import threading

import pytest

pytest.importorskip("anthropic")

from baxy_mind import external_model as traductor  # noqa: E402
from test_external_model import MODELS, FakeOllama, answer_with, compatible_stack, post  # noqa: E402

VALUES = ["now", "no", "later", "maybe", "ask", "different", "yours"]
# Mind.THEIR_ANSWER_GRAMMAR, as written (the mind is not imported: the translator runs without its packages).
THEIR_ANSWER_GRAMMAR = "root ::= " + " | ".join(f'"{value}"' for value in VALUES)
CLOSED = {"messages": [{"role": "system", "content": "Reply with one word."}, {"role": "user", "content": "«¿La enciendo?» «dale»"}],
          "max_tokens": 4, "grammar": THEIR_ANSWER_GRAMMAR, "chat_template_kwargs": {"enable_thinking": False},
          "temperature": 0.0, "top_p": 0.8, "top_k": 20, "min_p": 0.0, "seed": 0}
SCHEMA = {"type": "object", "properties": {"answer": {"type": "string", "enum": VALUES}}, "required": ["answer"],
          "additionalProperties": False}


def test_only_a_grammar_of_literals_alone_is_a_closed_question():
    assert traductor.closed_values(CLOSED) == VALUES
    assert traductor.closed_values({**CLOSED, "grammar": 'root ::= "yes" | "no"'}) == ["yes", "no"]
    assert traductor.closed_values({**CLOSED, "grammar": 'root ::= [a-z]+'}) is None
    assert traductor.closed_values({**CLOSED, "grammar": 'root ::= "a" | b\nb ::= "c"'}) is None
    assert traductor.closed_values({**CLOSED, "tools": [{"type": "function"}]}) is None
    assert traductor.closed_values({**CLOSED, "response_format": {"type": "json_object"}}) is None
    assert traductor.closed_values({k: v for k, v in CLOSED.items() if k != "grammar"}) is None


def test_a_compatible_api_gets_the_values_as_its_schema_at_the_temperature_asked(tmp_path):
    upstream, url, server = compatible_stack(tmp_path, provider="compatible")
    upstream.answers.append(answer_with({"role": "assistant", "content": '{"answer": "now"}'}))
    reply = json.loads(post(url, "/v1/chat/completions", CLOSED))
    server.shutdown()
    sent = upstream.requests[0]
    assert sent["response_format"] == {"type": "json_schema", "json_schema": {"name": "answer", "strict": True, "schema": SCHEMA}}
    assert sent["temperature"] == 0.0 and "grammar" not in sent
    assert reply["choices"][0]["message"]["content"] == '{"answer": "now"}'  # as the model wrote it: the mind reads its shape


def test_a_decision_is_sent_as_before(tmp_path):
    upstream, url, server = compatible_stack(tmp_path, provider="compatible")
    upstream.answers.append(answer_with({"role": "assistant", "content": "hola"}))
    post(url, "/v1/chat/completions", {"messages": [{"role": "user", "content": "hola"}], "max_tokens": 768, "temperature": 0.6})
    server.shutdown()
    assert set(upstream.requests[0]) == {"model", "messages", "max_tokens"}


@pytest.mark.parametrize("refuses, learned", [({"temperature"}, {"temperature"}), ({"response_format"}, {"temperature", "format"})])
def test_what_an_api_refuses_of_a_closed_question_is_asked_without_and_never_again(tmp_path, capsys, refuses, learned):
    upstream, url, server = compatible_stack(tmp_path, provider="compatible")

    def rule(sent):
        if refuses & set(sent):
            return {"status": 400, "error": {"message": "Unsupported parameter"}}
        return answer_with({"role": "assistant", "content": "now"})

    upstream.rule = rule
    first = json.loads(post(url, "/v1/chat/completions", CLOSED))
    tried = len(upstream.requests)
    second = json.loads(post(url, "/v1/chat/completions", CLOSED))
    server.shutdown()
    assert first["choices"][0]["message"]["content"] == second["choices"][0]["message"]["content"] == "now"
    assert not refuses & set(upstream.requests[-1])
    assert len(upstream.requests) - tried == 1  # learned: the second goes at once as it is taken
    out = capsys.readouterr().out
    assert "ERROR[" not in out  # a try asked again is no failure for Settings
    assert all(name in out for name in learned)


def test_a_server_error_to_the_schema_is_asked_plainly_too(tmp_path, capsys):
    # llama-server b11609 with granite-4.2-3b: 500 «Unexpected empty grammar stack after accepting piece» (MOD4, pod).
    upstream, url, server = compatible_stack(tmp_path, provider="compatible")
    upstream.rule = lambda sent: ({"status": 500, "error": {"message": "Unexpected empty grammar stack"}} if "response_format" in sent
                                  else answer_with({"role": "assistant", "content": "</think>later"}))
    reply = json.loads(post(url, "/v1/chat/completions", CLOSED))
    server.shutdown()
    assert reply["choices"][0]["message"]["content"] == "</think>later"
    assert "ERROR[" not in capsys.readouterr().out


def test_a_closed_question_refused_also_plainly_is_the_failure_it_was(tmp_path, capsys):
    upstream, url, server = compatible_stack(tmp_path, provider="compatible")
    upstream.rule = lambda sent: {"status": 400, "error": {"message": "bad"}}
    with pytest.raises(Exception):
        post(url, "/v1/chat/completions", CLOSED)
    server.shutdown()
    assert len(upstream.requests) == 3 and "response_format" not in upstream.requests[-1]
    assert capsys.readouterr().out.count("ERROR[") == 1


def test_ollama_gets_the_values_as_its_format_with_room_for_them(tmp_path):
    ollama = FakeOllama(MODELS, [{"message": {"role": "assistant", "content": '{"answer":"no"}'}, "done_reason": "stop",
                                  "prompt_eval_count": 40, "eval_count": 6}])
    backend = traductor.Ollama(ollama.url, "grande:4b")
    translator = traductor.Translator(None, traductor.Spend(tmp_path / "g.jsonl", float("inf")), "low", "grande:4b", backend)
    server = traductor.serve(translator, 0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    reply = json.loads(post(f"http://127.0.0.1:{server.server_address[1]}", "/v1/chat/completions", CLOSED))
    server.shutdown()
    ollama.server.shutdown()
    sent = ollama.requests[0]
    assert sent["format"] == SCHEMA and "temperature" not in sent  # Ollama's temperature goes in its options
    assert sent["options"]["num_predict"] == traductor.CLOSED_TOKENS and sent["options"]["temperature"] == 0.0
    assert reply["choices"][0]["message"]["content"] == '{"answer":"no"}'


def test_claude_and_the_responses_api_get_the_values_as_their_own_output_format():
    shaped = {**{k: v for k, v in CLOSED.items() if k != "grammar"}, "response_format": traductor.closed_format(VALUES)}
    assert traductor.to_request(shaped, "low")["output_config"]["format"] == {"type": "json_schema", "schema": SCHEMA}
    responses = traductor.Responses("https://api.openai.com/v1", "k", "gpt", "openai").to_request(shaped)
    assert responses["text"] == {"format": {"type": "json_schema", "name": "answer", "schema": SCHEMA, "strict": True}}
    assert "temperature" not in responses
