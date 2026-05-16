"""Helpers to keep Gemma thinking content out of chat history."""

from __future__ import annotations

import re
from typing import Any


THINKING_KEYS = {
    "reasoning",
    "reasoning_content",
    "reasoning_details",
    "thought",
    "thoughts",
}

THINKING_PATTERNS = (
    re.compile(r"(?is)<think>.*?</think>"),
    re.compile(r"(?is)<\|think\|>.*?(?=<\|(?:tool_call|start|end|message|assistant|user|system)\|>|$)"),
)

# El LLM a veces emite el formato de tool_call como TEXTO (string en el
# content) en vez de via el mecanismo nativo de tool_calls. Eso es un bug
# del parser/template. Si llega al user lo confunde — ve un mensaje como
# "<|tool_call>call:browser{action:<|"|>search...". Strippeamos esos
# tokens literales del content para que al menos el user no los vea.
# El system_prompt ya dice "Never invent custom tool-call syntax"; este
# es defense in depth.
TOOL_CALL_LEAK_PATTERNS = (
    # Forma observada en sesion 11:43: <|tool_call>...<tool_call|>
    re.compile(r"<\|tool_call\|?>.*?<\|?tool_call\|>", re.IGNORECASE | re.DOTALL),
    re.compile(r"<\|tool_call>.*?</?tool_call\|>", re.IGNORECASE | re.DOTALL),
    # Forma con call:<name>{...}
    re.compile(r"<\|tool_call\|?>[^<]*?(?=\n|$)", re.IGNORECASE),
    # Closing tag huerfano
    re.compile(r"</?tool_call\|>", re.IGNORECASE),
    re.compile(r"<\|tool_call\|>", re.IGNORECASE),
)


def sanitize_text(text: Any) -> str:
    """Remove visible thinking tags AND leaked tool_call markup from model text."""

    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)
    for pattern in THINKING_PATTERNS:
        text = pattern.sub("", text)
    for pattern in TOOL_CALL_LEAK_PATTERNS:
        text = pattern.sub("", text)
    return text.strip()


def sanitize_assistant_message(message: dict[str, Any]) -> dict[str, Any]:
    """Return a history-safe assistant message without reasoning fields."""

    clean: dict[str, Any] = {"role": "assistant", "content": sanitize_text(message.get("content"))}
    tool_calls = message.get("tool_calls")
    if tool_calls:
        clean["tool_calls"] = tool_calls
    return clean
