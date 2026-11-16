"""MOD3: how three chat templates write a conversation, for fake servers (/apply-template). Each writes what the real
template of the model file writes for the probes of call_format.derive (rendered with jinja2 from tokenizer.chat_template
of Qwen3.5-4B, gemma-4-E4B-it and Llama-3.2-3B-Instruct, 15-11-2026: tmp\\MOD3\\pl), not the whole template."""
from __future__ import annotations

import json
from typing import Any


def _arguments(call: dict[str, Any]) -> dict[str, Any]:
    raw = call["function"].get("arguments") or {}
    return json.loads(raw) if isinstance(raw, str) else raw


def qwen35(messages: list[dict[str, Any]], tools: list[dict[str, Any]], add_generation_prompt: bool = True) -> str:
    """Qwen3.5's template (qwen3-coder XML calls; a top-level value with «| string», so a boolean is «True»)."""
    out = ""
    for m in messages:
        content = m.get("content") or ""
        if m["role"] == "assistant":
            for i, call in enumerate(m.get("tool_calls") or []):
                lead = ("\n\n" if content else "") if i == 0 else "\n"
                params = "".join(f"<parameter={k}>\n{v}\n</parameter>\n" for k, v in _arguments(call).items())
                content += f"{lead}<tool_call>\n<function={call['function']['name']}>\n{params}</function>\n</tool_call>"
            out += f"<|im_start|>assistant\n{content}<|im_end|>\n"
        elif m["role"] == "tool":
            out += f"<|im_start|>user\n<tool_response>\n{content}\n</tool_response><|im_end|>\n"
        else:
            out += f"<|im_start|>{m['role']}\n{content}<|im_end|>\n"
    return out + ("<|im_start|>assistant\n<think>\n\n</think>\n\n" if add_generation_prompt else "")


def llama32(messages: list[dict[str, Any]], tools: list[dict[str, Any]], add_generation_prompt: bool = True) -> str:
    """Llama 3.2's template: one JSON call per reply, «{"name": …, "parameters": …}»; more than one raises."""
    out = "<|begin_of_text|>"
    for m in messages:
        role = "ipython" if m["role"] == "tool" else m["role"]
        calls = m.get("tool_calls") or []
        if len(calls) > 1:
            raise ValueError("This model only supports single tool-calls at once!")
        content = (json.dumps({"name": calls[0]["function"]["name"], "parameters": _arguments(calls[0])})
                   if calls else m.get("content") or "")
        out += f"<|start_header_id|>{role}<|end_header_id|>\n\n{content}<|eot_id|>"
    return out + ("<|start_header_id|>assistant<|end_header_id|>\n\n" if add_generation_prompt else "")


def gemma4(messages: list[dict[str, Any]], tools: list[dict[str, Any]], add_generation_prompt: bool = True) -> str:
    """Gemma 4's template: «<|tool_call>call:NAME{…}<tool_call|>», calls one after another with nothing between."""
    out = "<bos>"
    for m in messages:
        role = "model" if m["role"] == "assistant" else m["role"]
        content = m.get("content") or ""
        if m["role"] == "tool":
            out += f"<|tool_response>response:{content}<tool_response|>"
            continue
        for call in m.get("tool_calls") or []:
            args = ",".join(f"{k}:{json.dumps(v)}" for k, v in _arguments(call).items())
            content += f"<|tool_call>call:{call['function']['name']}{{{args}}}<tool_call|>"
        out += f"<|turn>{role}\n{content}<turn|>\n"
    return out + ("<|turn>model\n" if add_generation_prompt else "")
