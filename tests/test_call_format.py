"""MOD3: a model's call format read from its own chat template (src/baxy_mind/call_format.py), and a call written as
text told by its form."""
import pytest

from baxy_mind import call_format
from plantillas_llamada import gemma4, llama32, qwen35


def test_qwen35s_template_gives_the_format_the_mind_was_written_with() -> None:
    # Byte for byte the constants the mind had (STUB_AGAIN, the prefill's cut, fill_call's start, doubt's marks).
    found = call_format.derive(qwen35)
    assert found == call_format.CALIBRATED
    assert found.stub_again("web_fetch") == "</tool_call>\n<tool_call>\n<function=web_fetch>"
    assert found.call_start("web_search") == "<tool_call>\n<function=web_search>\n"
    assert (found.first_mark, found.name_open, found.name_stop) == ("<tool_call>", "<function=", ">")
    assert found.marks == ("<tool_call>", "<function=")
    assert found.bools_as_text is True


def test_llama32s_template_gives_a_json_call_and_no_second_call() -> None:
    found = call_format.derive(llama32)
    assert found is not None
    assert found.opening == '{"name": "'
    assert found.name_stop == '"'
    assert found.again is None and found.stub_again("web_fetch") is None  # one call per reply: nothing to stop
    assert (found.turn_end, found.user_open) == ("<|eot_id|>", "<|start_header_id|>user<|end_header_id|>\n\n")
    assert found.bools_as_text is False
    assert found.marks == ('{"name":',)  # a lone quote is no mark


def test_gemma4s_template_gives_its_own_tokens_and_calls_side_by_side() -> None:
    found = call_format.derive(gemma4)
    assert found is not None
    assert found.opening == "<|tool_call>call:"
    assert found.stub_again("web_fetch") == "{}<tool_call|><|tool_call>call:web_fetch{"
    assert (found.turn_end, found.user_open) == ("<turn|>\n", "<|turn>user\n")
    assert found.bools_as_text is False


def test_a_template_that_writes_no_call_gives_no_format() -> None:
    def plain(messages, tools, add_generation_prompt=True):
        return "".join(f"{m['role']}: {m.get('content') or ''}\n" for m in messages)

    def failing(messages, tools, add_generation_prompt=True):
        raise RuntimeError("no template")

    assert call_format.derive(plain) is None
    assert call_format.derive(failing) is None


def test_a_call_written_as_text_is_told_by_its_form_in_any_format() -> None:
    qwen, llama = call_format.CALIBRATED, call_format.derive(llama32)
    written = [
        '{"name": "app_open", "arguments": {"appId": "Paint"}}',
        'Claro, lo abro: {"name": "app_open", "parameters": {"appId": "Paint"}}',
        '```json\n[{"name": "audio_mute", "arguments": {"state": true}}]\n```',
        '<|python_tag|>{"name": "web_search", "parameters": {"query": "clima"}}',
        "<|tool_call>call:app_open{appId:\"Paint\"}<tool_call|>",
        "<tool_call>\n<function=app_open>\n</function>\n</tool_call>",
    ]
    for text in written:
        assert call_format.written_call(text, llama), text
        assert call_format.written_call(text, qwen), text
    words = ["Listo, abrí Paint.", "Las llaves {} se usan en JSON.", 'Escribe {"a": 1} en el campo.',
             "El precio es 3 < 5 y 7 > 2.", ""]
    for text in words:
        assert not call_format.written_call(text, llama), text
        assert not call_format.written_call(text, qwen), text


def test_a_reply_streaming_as_json_is_not_told_to_the_voice() -> None:
    llama = call_format.derive(llama32)
    assert call_format.may_be_call('{"na', llama)
    assert call_format.may_be_call("Claro. <tool_call>", call_format.CALIBRATED)
    assert not call_format.may_be_call("Claro, ahora", llama)


def test_a_server_that_renders_nothing_or_cannot_be_reached_is_not_a_model_without_format() -> None:
    # Review of MOD3: the translator (Ollama, an API) answers /apply-template with an empty prompt; a refused connection
    # is the start's own failure, as a vocabulary that could not be read was.
    def empty(messages, tools, add_generation_prompt=True):
        return ""

    def unreachable(messages, tools, add_generation_prompt=True):
        raise ConnectionRefusedError("no server")

    with pytest.raises(call_format.Unrendered):
        call_format.derive(empty)
    with pytest.raises(ConnectionRefusedError):
        call_format.derive(unreachable)


def test_a_template_that_writes_the_tools_but_not_the_calls_gives_no_format() -> None:
    def tools_only(messages, tools, add_generation_prompt=True):
        listed = "".join(t["function"]["name"] for t in tools)
        return listed + "".join(f"<|im_start|>{m['role']}\n{m.get('content') or ''}<|im_end|>\n" for m in messages)

    assert call_format.derive(tools_only) is None


def test_words_about_json_or_lists_are_not_calls() -> None:
    qwen = call_format.CALIBRATED
    assert not call_format.written_call('Usa {"name": "x", "arguments": "y"} así.', qwen)
    for text in ("```python\nprint(1)\n```", "[1] primero, [2] después", 'El campo {"a": 1} va arriba.'):
        assert not call_format.may_be_call(text, qwen), text


def test_a_tool_called_by_its_catalog_name_is_a_call_in_any_form() -> None:
    # Held-out of MOD3 (a subagent that never saw the code): Mistral's «[TOOL_CALLS]», Python's form, a JSON cut short.
    names = ["app_open", "web_search", "file_read"]
    llama = call_format.derive(llama32)
    for text in ('[TOOL_CALLS]file_read[ARGS]{"path": "D:\\notas.txt"}', 'app_open(app="Bloc")',
                 '[web_search(query="farmacia")]', 'Lo miro: {"name": "file_read", "argu'):
        assert call_format.written_call(text, llama, names), text
    # A JSON example that begins as Llama 3.2's call does is not one; nor a function of a code example.
    for text in ('Un package.json empieza así: {"name": "mi-app", "version": "1.0.0"}.', "Llama a saludar(nombre)."):
        assert not call_format.written_call(text, llama, names), text
