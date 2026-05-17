"""Helpers to keep Gemma thinking content out of chat history."""

from __future__ import annotations

import json
import re
import uuid
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


# ---------------------------------------------------------------------------
# Rescue parser: when the LLM emits a tool call as TEXT instead of via the
# native tool_call mechanism, we parse the text and synthesize a real tool
# call so the agent loop can still execute it.
#
# Observed bug shapes (real production logs):
#   - web(action="search", query="de que trata GTA 5")
#   - media({"action": "play", "provider": "disney", "query": "Loki"})
#   - browser(action='search', browser='Opera', query='something')
#   - whatsapp(action="send", to="Juan", text="hola")
#
# The model "knows" the syntax but emits it as a final text response with
# tool_call_count=0. From the user perspective this looks like the agent
# replied with internal commands. We catch it post-hoc and re-execute.
# ---------------------------------------------------------------------------

# Regex tuned to common shapes: "<tool_name>(<args>)" at start of line or
# whole content. Tool names are snake_case ASCII. Args span until the
# matching close paren (we count manually to handle nested parens/quotes).
_LEAKED_CALL_RE = re.compile(
    r"^\s*([a-z][a-z0-9_]{1,40})\s*\((.*)\)\s*$",
    re.DOTALL,
)


def _find_matching_paren(text: str, start: int = 0) -> int:
    """Find index of the close paren that matches the open at `start`,
    respecting Python-style string quoting. Returns -1 if not found."""
    if start >= len(text) or text[start] != "(":
        return -1
    depth = 0
    i = start
    in_str: str | None = None
    while i < len(text):
        ch = text[i]
        if in_str:
            if ch == "\\" and i + 1 < len(text):
                i += 2
                continue
            if ch == in_str:
                in_str = None
        else:
            if ch in ("'", '"'):
                in_str = ch
            elif ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    return i
        i += 1
    return -1


def _parse_kwargs(text: str) -> dict[str, Any] | None:
    """Best-effort parse of Python-like kwargs (action="x", query="y") or
    a single dict literal ({"action": "x", ...}). Returns dict or None."""
    text = text.strip()
    if not text:
        return {}
    # Case 1: single dict literal.
    if text.startswith("{") and text.endswith("}"):
        try:
            return json.loads(text)
        except Exception:
            # Python single-quote dicts: try a tolerant ast eval.
            try:
                import ast
                val = ast.literal_eval(text)
                return val if isinstance(val, dict) else None
            except Exception:
                return None
    # Case 2: kwargs. Use ast to parse "k=v, k=v" by wrapping in a call.
    try:
        import ast
        node = ast.parse(f"_f({text})", mode="eval")
        call = node.body
        if not isinstance(call, ast.Call):
            return None
        result: dict[str, Any] = {}
        for kw in call.keywords:
            if kw.arg is None:
                continue
            try:
                result[kw.arg] = ast.literal_eval(kw.value)
            except Exception:
                # If value is a complex expression we can't eval safely,
                # store its source code as string fallback.
                try:
                    result[kw.arg] = ast.unparse(kw.value)
                except Exception:
                    continue
        # Also support positional args being a single dict literal:
        #   media({"action": "play", ...})
        if not result and call.args and len(call.args) == 1:
            try:
                val = ast.literal_eval(call.args[0])
                if isinstance(val, dict):
                    return val
            except Exception:
                pass
        return result
    except Exception:
        return None


def detect_leaked_tool_call(
    content: str,
    *,
    known_tool_names: set[str] | None = None,
) -> dict[str, Any] | None:
    """Detect if `content` looks like a leaked tool call. Returns an
    OpenAI-shaped tool_call dict suitable to feed back into the loop, or
    None if no leak detected.

    Returns shape:
        {"id": "call_<uuid>", "type": "function",
         "function": {"name": "<tool>", "arguments": "<json string>"}}
    """
    if not content or not isinstance(content, str):
        return None
    stripped = content.strip()
    # Quick reject: must contain '(' and ')' and start with a lowercase letter.
    if "(" not in stripped or not stripped[0].isalpha():
        return None
    # Allow content like "web(action=...)" possibly with trailing punctuation.
    m = _LEAKED_CALL_RE.match(stripped)
    if not m:
        # Maybe there's narration first ("Voy a llamar web(...)"). F-007:
        # cambiar de "ultima llamada" a "primera que matchee known_tool_names".
        # Multi-call leak: 'web(...) y luego whatsapp(...)' debe rescatar
        # web (primero) no whatsapp.
        last_call = None
        for cand in re.finditer(
            r"\b([a-z][a-z0-9_]{1,40})\s*\(",
            stripped,
        ):
            cand_name = cand.group(1)
            if known_tool_names is not None and cand_name not in known_tool_names:
                continue
            open_idx = cand.end() - 1
            close_idx = _find_matching_paren(stripped, open_idx)
            if close_idx > open_idx:
                last_call = (cand_name, stripped[open_idx + 1: close_idx])
                break  # primera que matchee, no ultima
        if not last_call:
            return None
        name, body = last_call
    else:
        name, body = m.group(1), m.group(2)

    # Tool name allowlist (if provided): avoids treating prose like
    # "esto(es algo)" as a tool call.
    if known_tool_names is not None and name not in known_tool_names:
        return None

    parsed = _parse_kwargs(body)
    if parsed is None:
        return None
    try:
        args_json = json.dumps(parsed, ensure_ascii=False)
    except Exception:
        return None
    return {
        "id": f"call_rescue_{uuid.uuid4().hex[:12]}",
        "type": "function",
        "function": {"name": name, "arguments": args_json},
    }
