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


def sanitize_text(text: Any) -> str:
    """Remove visible thinking tags from model text."""

    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)
    for pattern in THINKING_PATTERNS:
        text = pattern.sub("", text)
    return text.strip()


def sanitize_assistant_message(message: dict[str, Any]) -> dict[str, Any]:
    """Return a history-safe assistant message without reasoning fields."""

    clean: dict[str, Any] = {"role": "assistant", "content": sanitize_text(message.get("content"))}
    tool_calls = message.get("tool_calls")
    if tool_calls:
        clean["tool_calls"] = tool_calls
    return clean
