"""MOD3: the mind with a model whose calls are not Qwen3.5's (MOD2: only Qwen started, mind.py:3236, and a call
written as text reached the person): it starts, reads its format from its template, and never says a call."""
import json
from pathlib import Path

from baxy_mind.mind import Mind
from plantillas_llamada import llama32, qwen35
from test_mind_final import FakeServer, _say


class TemplateServer(FakeServer):
    """A server with a chat template (/apply-template) and a vocabulary where only ``single`` is one token."""

    def __init__(self, replies: list, render, single: str) -> None:
        super().__init__(replies)
        self._render, self.single = render, single
        self.prefilled: list[str] = []
        self.kept = 0

    def render(self, messages, tools, add_generation_prompt, timeout: float = 10.0) -> str:
        return self._render(messages, tools, add_generation_prompt)

    def template(self, body: dict, timeout: float = 10.0) -> str:
        return self._render(body["messages"], body.get("tools") or [], True)

    def tokenize(self, text: str) -> list[int]:
        return [7] if text == self.single else [1, 2, 3]

    def prefix_key(self, warm) -> str:
        return "key"

    def restore_prefix(self, key: str) -> None:
        return None

    def read_prefix(self, body: dict, on_progress=None) -> dict:
        return {"usage": {"prompt_tokens": 100}}

    def save_prefix(self, key: str, facts: dict) -> bool:
        return False

    def prefill(self, prompt: str, timeout: float = 60.0) -> dict:
        self.prefilled.append(prompt)
        return {"timings": {}}


def _rows(tmp_path: Path, stage: str) -> list[dict]:
    rows = [json.loads(line) for line in (tmp_path / "turns.jsonl").read_text(encoding="utf-8").splitlines()]
    return [row for row in rows if row["stage"] == stage]


def _started(tmp_path: Path, replies: list, render, single: str) -> tuple[Mind, TemplateServer]:
    server = TemplateServer(replies, render, single)
    mind = Mind(server, tmp_path / "turns.jsonl")  # type: ignore[arg-type]
    mind.warm()
    return mind, server


def test_a_model_whose_call_opening_is_no_token_starts_and_says_what_is_off(tmp_path: Path) -> None:
    # Before: RuntimeError «<tool_call> is not one token of this model» and the mind never started (Gemma, Granite,
    # Llama with BAXY_MIND_LLM_GGUF; MOD2 §3).
    mind, _ = _started(tmp_path, [], llama32, single="<|python_tag|>")
    assert mind.call_tokens == []
    [row] = _rows(tmp_path, "warm.format")
    assert row["opening"] == '{"name": "'
    assert {"call_bias", "doubt", "stub_stop", "calibrated_sampling"} <= set(row["off"])
    assert "prefill" not in row["off"] and "fill" not in row["off"]


def test_qwen35_starts_as_it_did(tmp_path: Path) -> None:
    mind, server = _started(tmp_path, [_say("Hola.")], qwen35, single="<tool_call>")
    assert mind.call_tokens == [7]
    assert not (tmp_path / "turns.jsonl").exists() or not _rows(tmp_path, "warm.format")
    assert mind.decide(1, "hola")["reply"] == "Hola."
    body = server.bodies[-1]
    assert (body["temperature"], body["top_p"], body["top_k"], body["min_p"]) == (0.2, 0.8, 20, 0.0)


def test_a_call_written_as_json_never_reaches_the_person(tmp_path: Path) -> None:
    # Before: the JSON was BAXY's answer, said aloud (MOD2 «llamada en texto»).
    call = '{"name": "app_open", "parameters": {"appId": "Paint"}}'
    mind, server = _started(tmp_path, [_say(call), _say(call), _say("Ahora no puedo abrirlo.")], llama32,
                            single="<|python_tag|>")
    result = mind.decide(1, "abre paint")
    assert result["reply"] == "Ahora no puedo abrirlo."
    assert server.bodies[1]["tool_choice"] == "none"  # answered again in words
    told = [m["content"] for m in server.bodies[2]["messages"] if m["role"] == "user"]
    assert "llamada a una herramienta escrita como texto" in told[-1]
    assert [r.get("kind") for r in _rows(tmp_path, "turn.decide")][:2] == ["malformed_call", "text_call"]


def test_a_call_written_again_as_text_is_not_said(tmp_path: Path) -> None:
    call = '{"name": "app_open", "parameters": {"appId": "Paint"}}'
    mind, _ = _started(tmp_path, [_say(call), _say(call), _say(call)], llama32, single="<|python_tag|>")
    assert mind.decide(1, "abre paint")["reply"] == ""


def test_the_decision_keeps_the_servers_sampling_for_another_format(tmp_path: Path) -> None:
    mind, server = _started(tmp_path, [_say("Hola.")], llama32, single="<|python_tag|>")
    mind.decide(1, "hola")
    body = server.bodies[-1]
    assert body["temperature"] == 0.2 and not {"top_p", "top_k", "min_p"} & set(body)


def test_the_read_ahead_cuts_where_the_persons_turn_opens_in_the_models_template(tmp_path: Path) -> None:
    # Before: it looked for «<|im_start|>user\n» and read nothing ahead with any other template («unrendered»).
    mind, server = _started(tmp_path, [], llama32, single="<|python_tag|>")
    mind.conversation = [{"role": "user", "content": "hola"}, {"role": "assistant", "content": "Hola."}]
    assert mind.prefill() is True
    assert server.prefilled[-1].endswith("Hola.<|eot_id|>")


def test_no_doubt_is_read_where_no_token_opens_a_call(tmp_path: Path) -> None:
    mind, _ = _started(tmp_path, [], llama32, single="<|python_tag|>")
    reply = {"choices": [{"message": {"content": "", "tool_calls": [{"function": {"name": "app_open"}}]},
                          "logprobs": {"content": [{"token": '{"', "logprob": -0.1, "top_logprobs": []}]}}]}
    assert mind._doubt_of(reply) is None


def test_the_note_on_a_call_written_as_text_does_not_stay_in_the_conversation(tmp_path: Path) -> None:
    call = '{"name": "app_open", "parameters": {"appId": "Paint"}}'
    mind, _ = _started(tmp_path, [_say(call), _say(call), _say("Ahora no puedo abrirlo.")], llama32,
                       single="<|python_tag|>")
    mind.decide(1, "abre paint")
    assert not any("escrita como texto" in str(m.get("content")) for m in mind.conversation)


def test_a_server_that_renders_no_template_keeps_the_format_it_had(tmp_path: Path) -> None:
    # Review of MOD3: the translator to Ollama or an API answers /apply-template with an empty prompt.
    from baxy_mind import call_format

    mind, _ = _started(tmp_path, [], lambda messages, tools, add_generation_prompt: "", single="<tool_call>")
    assert mind.call_format == call_format.CALIBRATED and mind.call_tokens == [7]


def test_with_the_stock_models_call_token_a_reply_that_explains_json_is_said_as_it_was(tmp_path: Path) -> None:
    # Review REVX1 (F1): with Qwen3.5's «<tool_call>» one token, never sampled where no call may be written, the 1.5.4
    # read only the marks of its opening; an answer that explains a JSON or names a control token is said, in one request.
    for said in ('Claro, un ejemplo: {"name": "Ana", "arguments": {"edad": 30}}',
                 "El token <|im_end|> cierra cada mensaje en ChatML.", "web_fetch(url) es la herramienta que lee una página."):
        mind, server = _started(tmp_path, [_say(said)], qwen35, single="<tool_call>")
        assert mind.text_calls_by_form() is False
        assert mind.decide(1, "explícamelo")["reply"] == said
        assert len(server.bodies) == 1
