"""Minimal OpenAI-compatible client for llama-server / Gemma 4."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Iterator

from .config import AgentConfig


class LLMClient:
    def __init__(self, config: AgentConfig):
        self.config = config

    def health(self, timeout_s: float = 2.0) -> bool:
        try:
            with urllib.request.urlopen(self.config.health_url, timeout=timeout_s) as resp:
                return resp.status == 200
        except Exception:
            return False

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        *,
        enable_thinking: bool | None = None,
        parallel_tool_calls: bool | None = None,
        max_tokens: int | None = None,
        timeout_s: float | None = None,
    ) -> dict[str, Any]:
        """Synchronous chat completion against the local llama-server.

        timeout_s overrides the per-call request timeout. Defaults to
        self.config.request_timeout_s. This is the wall-clock deadline of the
        HTTP request - if exceeded, raises RuntimeError('llm_timeout: ...').
        """
        thinking = self.config.enable_thinking if enable_thinking is None else enable_thinking
        body: dict[str, Any] = {
            "model": self.config.model,
            "stream": False,
            "messages": messages,
            "temperature": self.config.temperature,
            "top_p": self.config.top_p,
            "top_k": self.config.top_k,
            "repeat_penalty": self.config.repeat_penalty,
            "max_tokens": max_tokens or self.config.max_tokens,
            "chat_template_kwargs": {"enable_thinking": thinking},
        }
        if self.config.min_p is not None:
            body["min_p"] = self.config.min_p
        if self.config.seed is not None and int(self.config.seed) >= 0:
            body["seed"] = int(self.config.seed)
        if self.config.reasoning_format:
            body["reasoning_format"] = self.config.reasoning_format
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
            body["parse_tool_calls"] = self.config.parse_tool_calls
            body["parallel_tool_calls"] = self.config.parallel_tool_calls if parallel_tool_calls is None else parallel_tool_calls

        effective_timeout = float(timeout_s) if timeout_s is not None else self.config.request_timeout_s
        try:
            response = self._post_chat(body, timeout=effective_timeout)
        except RuntimeError as exc:
            if not _looks_like_unsupported_option_error(str(exc)):
                raise
            fallback = dict(body)
            fallback.pop("chat_template_kwargs", None)
            fallback.pop("reasoning_format", None)
            fallback.pop("parse_tool_calls", None)
            fallback.pop("parallel_tool_calls", None)
            response = self._post_chat(fallback, timeout=effective_timeout)
        return _normalize_response_tool_calls(response)

    def chat_stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        *,
        enable_thinking: bool | None = None,
        parallel_tool_calls: bool | None = None,
        max_tokens: int | None = None,
        timeout_s: float | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Streaming chat completion (SSE) against llama-server.

        Yields dicts of two shapes:
          - {"type": "delta", "content_delta": "...", "tool_call_delta": {...}|None}
            Emitted as tokens arrive. tool_call_delta is non-null when the
            stream is building up a tool_call (llama-server typically sends
            id/name/arguments in pieces).
          - {"type": "final", "finish_reason": "stop|tool_calls|length|...",
             "content": "<accumulated text>", "tool_calls": [<list>]}
            Emitted once at the end. tool_calls is the accumulated array
            with id/function.name/function.arguments fully assembled.

        Fase W pre-requisito: el TTS consume "delta" para sentence-chunking
        en cuanto el LLM empieza a emitir. agent.py todavia usa chat() no-stream.
        """
        thinking = self.config.enable_thinking if enable_thinking is None else enable_thinking
        body: dict[str, Any] = {
            "model": self.config.model,
            "stream": True,
            "messages": messages,
            "temperature": self.config.temperature,
            "top_p": self.config.top_p,
            "top_k": self.config.top_k,
            "repeat_penalty": self.config.repeat_penalty,
            "max_tokens": max_tokens or self.config.max_tokens,
            "chat_template_kwargs": {"enable_thinking": thinking},
        }
        if self.config.min_p is not None:
            body["min_p"] = self.config.min_p
        if self.config.seed is not None and int(self.config.seed) >= 0:
            body["seed"] = int(self.config.seed)
        if self.config.reasoning_format:
            body["reasoning_format"] = self.config.reasoning_format
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
            body["parse_tool_calls"] = self.config.parse_tool_calls
            body["parallel_tool_calls"] = (
                self.config.parallel_tool_calls if parallel_tool_calls is None else parallel_tool_calls
            )

        effective_timeout = float(timeout_s) if timeout_s is not None else self.config.request_timeout_s
        yield from self._stream_chat(body, timeout=effective_timeout)

    def _stream_chat(self, body: dict[str, Any], *, timeout: float) -> Iterator[dict[str, Any]]:
        req = urllib.request.Request(
            self.config.chat_url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
        )
        try:
            resp = urllib.request.urlopen(req, timeout=timeout)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"llm_http_error {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            reason = getattr(exc, "reason", None)
            if "timed out" in str(reason).lower() or "timeout" in str(reason).lower():
                raise RuntimeError(f"llm_timeout: request exceeded {timeout}s") from exc
            raise RuntimeError(f"llm_connection_error: {exc}") from exc

        # SSE parser: cada "linea data: {...}" es un frame. Lineas vacias separan.
        # Acumulamos content + tool_call fragments hasta finish_reason.
        accumulated_content = ""
        # tool_calls indexados por index (llama-server permite multiples)
        tool_calls_acc: dict[int, dict[str, Any]] = {}
        final_finish: str | None = None

        try:
            for raw_line in resp:
                line = raw_line.decode("utf-8", errors="replace").rstrip()
                if not line:
                    continue
                if not line.startswith("data:"):
                    continue
                data = line[5:].lstrip()
                if data == "[DONE]":
                    break
                try:
                    frame = json.loads(data)
                except (ValueError, TypeError):
                    continue
                choices = frame.get("choices") or []
                if not choices:
                    continue
                ch0 = choices[0]
                delta = ch0.get("delta") or {}
                finish_reason = ch0.get("finish_reason")

                content_piece = delta.get("content")
                tc_pieces = delta.get("tool_calls") or []

                tc_for_yield: dict[str, Any] | None = None
                for tc in tc_pieces:
                    idx = int(tc.get("index", 0))
                    slot = tool_calls_acc.setdefault(idx, {
                        "id": None, "type": "function",
                        "function": {"name": "", "arguments": ""},
                    })
                    if tc.get("id"):
                        slot["id"] = tc["id"]
                    if tc.get("type"):
                        slot["type"] = tc["type"]
                    fn = tc.get("function") or {}
                    if fn.get("name"):
                        slot["function"]["name"] += fn["name"]
                    if fn.get("arguments"):
                        slot["function"]["arguments"] += fn["arguments"]
                    tc_for_yield = slot

                if content_piece is None and tc_for_yield is None and finish_reason is None:
                    continue
                if content_piece:
                    accumulated_content += content_piece
                if content_piece or tc_for_yield:
                    yield {
                        "type": "delta",
                        "content_delta": content_piece or "",
                        "tool_call_delta": tc_for_yield,
                    }
                if finish_reason:
                    final_finish = finish_reason
                    break
        except (TimeoutError, OSError) as exc:
            raise RuntimeError(f"llm_stream_interrupted: {exc}") from exc
        finally:
            try:
                resp.close()
            except OSError:
                pass

        # Frame final con el resumen acumulado. Normalizamos arguments de
        # cada tool_call (issue #21384: string con braces literales se
        # serializa como JSON string en vez de array, mitigado por
        # normalize_tool_call_arguments).
        raw_tool_calls = [tool_calls_acc[k] for k in sorted(tool_calls_acc.keys())]
        yield {
            "type": "final",
            "finish_reason": final_finish or "stop",
            "content": accumulated_content,
            "tool_calls": normalize_tool_calls_list(raw_tool_calls),
        }

    def _post_chat(self, body: dict[str, Any], *, timeout: float) -> dict[str, Any]:
        req = urllib.request.Request(
            self.config.chat_url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"llm_http_error {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            # urllib raises URLError on socket timeout; surface a friendlier message.
            reason = getattr(exc, "reason", None)
            if "timed out" in str(reason).lower() or "timeout" in str(reason).lower():
                raise RuntimeError(f"llm_timeout: request exceeded {timeout}s") from exc
            raise RuntimeError(f"llm_connection_error: {exc}") from exc
        except TimeoutError as exc:
            raise RuntimeError(f"llm_timeout: request exceeded {timeout}s") from exc


def normalize_tool_call_arguments(raw: Any) -> dict[str, Any]:
    """Normaliza `tool_call.function.arguments` a dict.

    Issue #21384 (llama.cpp + Gemma 4): cuando los args contienen `{` o `}`
    literales (paths con `${var}`, regex con sets, JSON anidado), el parser
    serializa el array como string JSON en vez de array. El cliente debe
    aceptar ambos casos.

    Recibe: dict, str (JSON), list (raro), None.
    Devuelve: dict siempre. Si el parsing falla en todos los caminos
    razonables, devuelve {"_raw": str(raw), "_parse_error": "..."}.

    Item I1 #5 + Bloque C2/D4 del informe de optimizacion externa.
    """
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, list):
        # Caso muy raro pero documentado: el server devuelve un array
        # cuando el modelo emite un AST nested. Lo envolvemos.
        return {"_args_list": raw}
    if isinstance(raw, (int, float, bool)):
        return {"_value": raw}
    if not isinstance(raw, str):
        return {"_raw": str(raw), "_parse_error": "unsupported_type"}

    s = raw.strip()
    if not s:
        return {}

    # Path feliz: el string es JSON valido.
    try:
        parsed = json.loads(s)
    except (ValueError, TypeError):
        parsed = None
    if isinstance(parsed, dict):
        return parsed
    if isinstance(parsed, list):
        return {"_args_list": parsed}
    if isinstance(parsed, str):
        # Path #21384 / doble-stringificado: el server entrego un string
        # JSON cuyo contenido es a su vez JSON. Re-parsear una vez.
        try:
            inner = json.loads(parsed)
        except (ValueError, TypeError):
            inner = None
        if isinstance(inner, dict):
            return inner
        if isinstance(inner, list):
            return {"_args_list": inner}
        # Si tras re-parsear no llegamos a dict/list, devolvemos el string
        # primario como _value para no perder informacion.
        return {"_value": parsed}
    if parsed is not None:
        # Escalar JSON-valido distinto de string (numero, bool, null).
        return {"_value": parsed}

    # Path defensivo final: devolver raw para que el caller decida. NO
    # bloqueamos; el agente puede recuperarse pidiendo al LLM que reformule.
    return {"_raw": s, "_parse_error": "not_a_json_object"}


def normalize_tool_calls_list(tool_calls: list[Any]) -> list[dict[str, Any]]:
    """Aplica normalize_tool_call_arguments a cada tool_call de una lista.

    Preserva id/type/function.name; solo robustifica function.arguments.
    Si una entry no respeta el shape OpenAI, la deja pasar sin tocar.
    """
    out: list[dict[str, Any]] = []
    for tc in tool_calls or []:
        if not isinstance(tc, dict):
            out.append(tc)
            continue
        fn = tc.get("function")
        if not isinstance(fn, dict):
            out.append(tc)
            continue
        normalized = dict(tc)
        normalized_fn = dict(fn)
        normalized_fn["arguments"] = normalize_tool_call_arguments(fn.get("arguments"))
        normalized["function"] = normalized_fn
        out.append(normalized)
    return out


def _normalize_response_tool_calls(response: dict[str, Any]) -> dict[str, Any]:
    """Recorre choices[*].message.tool_calls y normaliza arguments.

    No mutamos el objeto original; devolvemos una copia ligera con la
    sustitucion. Si la estructura no coincide con OpenAI, devolvemos
    response tal cual.
    """
    if not isinstance(response, dict):
        return response
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        return response
    new_choices = []
    changed = False
    for choice in choices:
        if not isinstance(choice, dict):
            new_choices.append(choice)
            continue
        msg = choice.get("message")
        if not isinstance(msg, dict):
            new_choices.append(choice)
            continue
        tc_list = msg.get("tool_calls")
        if not isinstance(tc_list, list) or not tc_list:
            new_choices.append(choice)
            continue
        new_msg = dict(msg)
        new_msg["tool_calls"] = normalize_tool_calls_list(tc_list)
        new_choice = dict(choice)
        new_choice["message"] = new_msg
        new_choices.append(new_choice)
        changed = True
    if not changed:
        return response
    out = dict(response)
    out["choices"] = new_choices
    return out


def _looks_like_unsupported_option_error(message: str) -> bool:
    low = message.casefold()
    return "llm_http_error 400" in low and any(
        token in low
        for token in (
            "unknown",
            "unsupported",
            "invalid",
            "chat_template_kwargs",
            "reasoning_format",
            "parse_tool_calls",
            "parallel_tool_calls",
        )
    )
