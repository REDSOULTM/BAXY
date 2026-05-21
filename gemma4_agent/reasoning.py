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
    # UNCLOSED <think> with no </think>: happens when generation is cut
    # mid-thinking (token budget / timeout). Without this the raw thinking
    # ("<think>razonando...") LEAKS to the user. Strip from <think> to EOL/EOS.
    # Runs AFTER the closed-tag pattern, so a properly closed block is already
    # gone and this only catches a dangling opener.
    re.compile(r"(?is)<think>.*$"),
)

# Stray model control tokens (<|end|>, <|start|>, <|message|>, ...) that the
# template/parser sometimes leaks into content. The <|think|> pattern above
# stops at a lookahead token but leaves that token in place; and a truncated
# turn can drop a bare <|end|>. Strip any leftover <|...|> marker so the user
# never sees raw control tokens.
_CONTROL_TOKEN_RE = re.compile(r"<\|[a-z_]+\|>", re.IGNORECASE)

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
    # Strip any leftover control tokens (e.g. a bare <|end|> the think pattern
    # stopped at, or a token from a truncated turn). Done last so the patterns
    # above keep their lookahead semantics.
    text = _CONTROL_TOKEN_RE.sub("", text)
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

# Gemma 4 sometimes serialises a tool call in its NATIVE JSON shape that
# the llama-server parser fails to lift into tool_calls (documented bug:
# llama.cpp #21384, mlx-lm #1096, Google's own function-calling docs). It
# lands in message.content as one of:
#   <|tool_call>{"name": "steam", "arguments": {...}}<tool_call|>
#   ```tool_call\n{"name": "steam", "arguments": {...}}\n```
#   ```json\n{"name": "steam", "arguments": {...}}\n```
#   bare  {"name": "steam", "arguments": {...}}   (or "parameters")
# We find each '{' that starts a JSON object containing a "name" key,
# extract the balanced object (regex can't reliably match nested JSON),
# and parse it. The Python-function form `steam(action="open")` is
# handled separately by _LEAKED_CALL_RE.
_NAME_KEY_RE = re.compile(r'"(?:name|tool_name)"\s*:\s*"[a-z][a-z0-9_]{1,40}"')


def _extract_balanced_json(text: str, open_idx: int) -> str | None:
    """Return the substring of the balanced {...} starting at open_idx,
    respecting string quoting/escapes. None if unbalanced."""
    if open_idx >= len(text) or text[open_idx] != "{":
        return None
    depth = 0
    i = open_idx
    in_str = False
    while i < len(text):
        ch = text[i]
        if in_str:
            if ch == "\\":
                i += 2
                continue
            if ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[open_idx : i + 1]
        i += 1
    return None


def _detect_gemma_json_call(
    content: str,
    known_tool_names: set[str] | None,
) -> dict[str, Any] | None:
    """Detect a Gemma-4 native-JSON tool call leaked into content.

    Returns the OpenAI-shaped tool_call dict, or None. Guarded by
    known_tool_names when provided so prose with a stray '{"name": ...}'
    can't be misread as a call.
    """
    if not content or "{" not in content:
        return None
    # Look near each "name"/"tool_name" key for the enclosing JSON object.
    for km in _NAME_KEY_RE.finditer(content):
        # Walk backwards from the key to the nearest '{' that opens its object.
        open_idx = content.rfind("{", 0, km.start())
        while open_idx != -1:
            blob = _extract_balanced_json(content, open_idx)
            if blob is not None and km.start() < open_idx + len(blob):
                obj = None
                try:
                    obj = json.loads(blob)
                except Exception:
                    obj = None
                if isinstance(obj, dict):
                    rescued = _gemma_obj_to_call(obj, known_tool_names)
                    if rescued is not None:
                        return rescued
                break
            open_idx = content.rfind("{", 0, open_idx)
    return None


def _gemma_obj_to_call(
    obj: dict[str, Any],
    known_tool_names: set[str] | None,
) -> dict[str, Any] | None:
    name = obj.get("name") or obj.get("tool_name")
    if not isinstance(name, str) or not name:
        return None
    if known_tool_names is not None and name not in known_tool_names:
        return None
    raw_args = obj.get("arguments")
    if raw_args is None:
        raw_args = obj.get("parameters")
    if isinstance(raw_args, str):
        try:
            raw_args = json.loads(raw_args)
        except Exception:
            raw_args = {}
    if not isinstance(raw_args, dict):
        raw_args = {}
    try:
        args_json = json.dumps(raw_args, ensure_ascii=False)
    except Exception:
        return None
    return {
        "id": f"call_rescue_{uuid.uuid4().hex[:12]}",
        "type": "function",
        "function": {"name": name, "arguments": args_json},
    }


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


# Dotted-method leak: the model writes the compound tool's ACTION as a
# Python method — `window.close(query="das Fenster")`, `audio.set_volume(
# level=20)` — instead of `window(action="close", ...)`. Seen live on
# "schliesse das Fenster" (DE) 2026-05-20: it leaked as text, unrescued,
# so the window never closed. We rewrite tool.action(args) into the normal
# compound form with action injected.
_DOTTED_CALL_RE = re.compile(
    r"^\s*([a-z][a-z0-9_]{1,40})\.([a-z][a-z0-9_]{1,40})\s*\((.*)\)\s*$",
    re.DOTALL,
)


def _detect_dotted_method_call(
    stripped: str, known_tool_names: set[str] | None
) -> dict[str, Any] | None:
    m = _DOTTED_CALL_RE.match(stripped)
    if not m:
        return None
    tool, action, body = m.group(1), m.group(2), m.group(3)
    if known_tool_names is not None and tool not in known_tool_names:
        return None
    parsed = _parse_kwargs(body)
    if parsed is None:
        parsed = {}
    # Don't clobber an explicit action the model also passed.
    parsed.setdefault("action", action)
    try:
        args_json = json.dumps(parsed, ensure_ascii=False)
    except Exception:
        return None
    return {
        "id": f"call_rescue_{uuid.uuid4().hex[:12]}",
        "type": "function",
        "function": {"name": tool, "arguments": args_json},
    }


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
    # First: Gemma-4 native-JSON form ({"name": "...", "arguments": {...}},
    # optionally wrapped in <|tool_call> markers or ``` fences). The
    # Python-function form is handled by the paren logic below.
    gemma_json = _detect_gemma_json_call(stripped, known_tool_names)
    if gemma_json is not None:
        return gemma_json
    # Dotted-method form `tool.action(args)` — more specific than the plain
    # paren form, so try it first (e.g. window.close(query="x")).
    dotted = _detect_dotted_method_call(stripped, known_tool_names)
    if dotted is not None:
        return dotted
    # Quick reject for the Python-function form: must contain '(' and ')'
    # and start with a lowercase letter.
    if "(" not in stripped or not stripped[0].isalpha():
        return None
    # Scanner: find the FIRST balanced tool(...) call whose name is known and
    # whose body parses. Handles narration ("Voy a llamar web(...)") and
    # MULTI-CALL leaks — incl. two space-separated calls
    # `system(action="memory") system(action="recall")`, where the greedy
    # whole-string regex below would grab a broken body. F-007: first match,
    # not last.
    def _scan_first_valid() -> tuple[str, dict[str, Any]] | None:
        for cand in re.finditer(r"\b([a-z][a-z0-9_]{1,40})\s*\(", stripped):
            cand_name = cand.group(1)
            if known_tool_names is not None and cand_name not in known_tool_names:
                continue
            open_idx = cand.end() - 1
            close_idx = _find_matching_paren(stripped, open_idx)
            if close_idx <= open_idx:
                continue
            cand_parsed = _parse_kwargs(stripped[open_idx + 1: close_idx])
            if cand_parsed is not None:
                return cand_name, cand_parsed
        return None

    # Allow content like "web(action=...)" possibly with trailing punctuation.
    m = _LEAKED_CALL_RE.match(stripped)
    name: str | None = None
    parsed: dict[str, Any] | None = None
    if m:
        cand_name, body = m.group(1), m.group(2)
        if known_tool_names is None or cand_name in known_tool_names:
            cand_parsed = _parse_kwargs(body)
            if cand_parsed is not None:
                name, parsed = cand_name, cand_parsed
    if parsed is None:
        # Primary didn't match, or matched with an unparseable (greedy) body
        # → scan for the first valid balanced call instead of giving up.
        scanned = _scan_first_valid()
        if scanned is None:
            return None
        name, parsed = scanned

    # Tool name allowlist (if provided): avoids treating prose like
    # "esto(es algo)" as a tool call.
    if known_tool_names is not None and name not in known_tool_names:
        return None
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
