"""MODX2 (MOD3: «Granite 4.2 empieza muchas respuestas con </think>, que llegaría a la voz»; MODX2 measured 134 of 189
replies of granite-4.2-3b with it): its template opens the reply with an empty thought («<think></think>», thinking
off) and the model writes the closing mark again. The mark that closes this model's thought is read from its template
(the generation prompt with thinking on and off: call_format.thought_end); a reply that begins with it closes an empty
thought, as llama.cpp's reasoning parser reads one, and what follows is the reply: neither the voice nor the person
gets the mark. Nothing else of the reply changes, and a reply without it is the same."""
from baxy_mind import call_format
from baxy_mind.llm_server import _may_close_thought, _past_thought
from test_maximo_stream import _SseServer, _delta

GRANITE_ON = "<|im_start|>user\nPROBE<|im_end|>\n<|im_start|>assistant\n<think>\n"
GRANITE_OFF = "<|im_start|>user\nPROBE<|im_end|>\n<|im_start|>assistant\n<think></think>"
QWEN_ON = "<|im_start|>user\nPROBE<|im_end|>\n<|im_start|>assistant\n<think>\n"
QWEN_OFF = "<|im_start|>user\nPROBE<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"
GEMMA_ON = "<bos><|turn>system\n<|think|><turn|>\n<|turn>user\nPROBE<turn|>\n<|turn>model\n"
GEMMA_OFF = "<bos><|turn>user\nPROBE<turn|>\n<|turn>model\n"


def test_the_mark_that_closes_a_thought_is_read_from_the_template() -> None:
    assert call_format.thought_end(GRANITE_ON, GRANITE_OFF) == "</think>"
    assert call_format.thought_end(QWEN_ON, QWEN_OFF) == "</think>"
    assert call_format.thought_end(GEMMA_ON, GEMMA_OFF) is None
    assert call_format.thought_end(GRANITE_OFF, GRANITE_OFF) is None
    assert call_format.thought_end("", "") is None  # the translator renders no template


def test_a_reply_that_begins_with_it_is_what_follows_it_and_any_other_is_the_same() -> None:
    assert _past_thought("</think>La ventana se cerró.", "</think>") == "La ventana se cerró."
    assert _past_thought("  </think>\nHecho.", "</think>") == "Hecho."
    assert _past_thought("Escribe </think> para cerrar.", "</think>") == "Escribe </think> para cerrar."
    assert _past_thought("</think>Hecho.", None) == "</think>Hecho."
    assert _may_close_thought("</thi", "</think>") and not _may_close_thought("</think>H", "</think>")
    assert not _may_close_thought("Hola", "</think>")


def test_the_voice_never_gets_the_mark_and_the_reply_comes_without_it() -> None:
    chunks = [_delta("</th"), _delta("ink>La ventana "), _delta("se cerró."),
              {"choices": [{"index": 0, "finish_reason": "stop", "delta": {}}]}]
    fake = _SseServer(chunks)
    seen: list[tuple[str, bool]] = []
    try:
        server = fake.server()
        server.thought_end = "</think>"
        reply = server.chat({"messages": [], "tool_choice": "none"},
                            on_text=lambda text, done: seen.append((text, done)) or False)
    finally:
        fake.close()
    assert reply["choices"][0]["message"]["content"] == "La ventana se cerró."
    assert all("think" not in text for text, _ in seen) and seen[-1] == ("La ventana se cerró.", True)


def test_a_reply_not_streamed_comes_without_it_too() -> None:
    plain = {"choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant",
                                                                          "content": "</think>Listo."}}]}
    fake = _SseServer([], plain=plain)
    try:
        server = fake.server()
        server.thought_end = "</think>"
        reply = server.chat({"messages": []})
    finally:
        fake.close()
    assert reply["choices"][0]["message"]["content"] == "Listo."
