"""Minimal OpenAI-compatible client for llama-server / Gemma 4."""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from typing import Any, Iterator

from .config import AgentConfig


logger = logging.getLogger(__name__)


# Connection-reset patterns que indican que el server crasheo/reloadeo
# durante el handshake. NO incluir genericos como "timeout" que pueden ser
# del LLM tardando legitimamente. Patrones ya normalizados (sin espacios
# ni underscores) para matchear despues del lower+replace en el helper.
_RECOVERABLE_CONN_ERRORS = (
    "10054",                  # WinError 10054 (forcibly closed by remote host)
    "10061",                  # WinError 10061 (no connection could be made)
    "connectionreset",        # ConnectionResetError / "connection reset"
    "connectionrefused",      # "connection refused"
    "brokenpipe",             # "broken pipe" / BrokenPipeError
    "connectionaborted",      # ConnectionAbortedError
    "remotedisconnected",     # http.client.RemoteDisconnected
)


def _is_recoverable_connection_error(exc: Exception) -> bool:
    """True si el error sugiere que vale la pena reintentar tras health-poll.

    Patron tipico: profile change -> server.stop() -> stop() libera el puerto;
    client manda request en la ventana siguiente -> server.start() en curso.
    El socket queda en estado inconsistente y devuelve 10054. Si esperamos
    a que /health vuelva (server arrancado de nuevo), el retry funciona.
    """
    s = str(exc).lower().replace(" ", "").replace("_", "")
    return any(token in s for token in _RECOVERABLE_CONN_ERRORS)


def _request_headers(content_type: str = "application/json", sse: bool = False) -> dict[str, str]:
    """Sprint 12 hardening: si GEMMA4_LLAMA_API_KEY esta seteado, añade
    el header Authorization: Bearer <key> que llama-server espera cuando
    arranca con --api-key. Si no esta seteado, headers sin Authorization
    (el server tampoco lo va a pedir)."""
    headers: dict[str, str] = {"Content-Type": content_type}
    if sse:
        headers["Accept"] = "text/event-stream"
    api_key = (os.environ.get("GEMMA4_LLAMA_API_KEY") or "").strip()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


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
        force_tool: bool = False,
        thinking_budget: int | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        """Synchronous chat completion against the local llama-server.

        timeout_s overrides the per-call request timeout. Defaults to
        self.config.request_timeout_s. This is the wall-clock deadline of the
        HTTP request - if exceeded, raises RuntimeError('llm_timeout: ...').
        """
        thinking = self.config.enable_thinking if enable_thinking is None else enable_thinking
        body: dict[str, Any] = {
            # In router mode the agent passes the per-turn router preset name
            # ("<profile>-text" / "<profile>-vision"); else the configured model.
            "model": model or self.config.model,
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
        # Cap reasoning tokens (when thinking is on) so a turn can't run away
        # to 13k-15k thinking tokens and blow the latency budget. llama.cpp
        # honors `thinking_budget_tokens` (b9090). -1/None = unbounded.
        if thinking and thinking_budget is not None and int(thinking_budget) >= 0:
            body["thinking_budget_tokens"] = int(thinking_budget)
        if tools:
            body["tools"] = tools
            # tool_choice: ESTE build de llama.cpp (b9090) espera un STRING
            # estilo OpenAI ("auto"/"required"/"none"), NO el objeto {"type":..}
            # — pasar objeto lo rechaza con 'Expected string, using default'
            # (verificado en el err log). El default "auto" deja al modelo
            # elegir; force_tool=True usa "required" para OBLIGAR un tool-call.
            # Fix respaldado por la literatura (arXiv:2504.19277: los SLM fallan
            # por "uncontrolled generation"; la cura es constrained/structured
            # output, que tool_choice=required activa vía la gramática interna).
            body["tool_choice"] = "required" if force_tool else "auto"
            body["parse_tool_calls"] = self.config.parse_tool_calls
            body["parallel_tool_calls"] = self.config.parallel_tool_calls if parallel_tool_calls is None else parallel_tool_calls

        effective_timeout = float(timeout_s) if timeout_s is not None else self.config.request_timeout_s
        response = self._post_chat_with_recovery(body, timeout=effective_timeout)
        return _normalize_response_tool_calls(response)

    def _post_chat_with_recovery(self, body: dict[str, Any], *, timeout: float) -> dict[str, Any]:
        """Wrapper de _post_chat que recupera de:
          - Connection reset (server reloadeando: poll /health, 1 retry)
          - Unsupported option (server build sin features OpenAI extras: retry sin esas keys)

        Maximo 1 reintento por categoria; si falla tras retry, propaga.
        """
        try:
            return self._post_chat(body, timeout=timeout)
        except RuntimeError as exc:
            # Caso 1: connection reset -> server reloading. Esperar /health
            # y reintentar UNA vez. Limit total wait a min(15s, timeout/2).
            if _is_recoverable_connection_error(exc):
                wait_budget = min(15.0, timeout / 2.0)
                deadline = time.monotonic() + wait_budget
                logger.info(
                    "llm connection reset (server probably reloading); "
                    "polling /health up to %.1fs before retry: %s",
                    wait_budget, exc,
                )
                healthy = False
                while time.monotonic() < deadline:
                    if self.health(timeout_s=1.0):
                        healthy = True
                        break
                    time.sleep(0.5)
                if healthy:
                    logger.info("llm server healthy again; retrying chat once")
                    try:
                        return self._post_chat(body, timeout=timeout)
                    except RuntimeError as retry_exc:
                        # Si tambien falla en el retry: no insistir mas
                        # (evita esconder bugs reales del server).
                        if _is_recoverable_connection_error(retry_exc):
                            raise RuntimeError(
                                f"llm_connection_reset_after_retry: {retry_exc}"
                            ) from retry_exc
                        # Cae al manejo de unsupported_option si aplica
                        if _looks_like_unsupported_option_error(str(retry_exc)):
                            return self._post_chat_fallback(body, timeout=timeout)
                        raise
                # Health nunca volvio en wait_budget: propagar
                raise RuntimeError(
                    f"llm_connection_reset_no_recovery: server did not become "
                    f"healthy within {wait_budget:.1f}s. Original: {exc}"
                ) from exc

            # Caso 2: unsupported option (build sin extras OpenAI) -> retry sin esas keys.
            if _looks_like_unsupported_option_error(str(exc)):
                return self._post_chat_fallback(body, timeout=timeout)

            raise

    def _post_chat_fallback(self, body: dict[str, Any], *, timeout: float) -> dict[str, Any]:
        """Retry sin los campos OpenAI-extra que algunos builds rechazan."""
        fallback = dict(body)
        fallback.pop("chat_template_kwargs", None)
        fallback.pop("reasoning_format", None)
        fallback.pop("parse_tool_calls", None)
        fallback.pop("parallel_tool_calls", None)
        return self._post_chat(fallback, timeout=timeout)

    def chat_stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        *,
        enable_thinking: bool | None = None,
        parallel_tool_calls: bool | None = None,
        max_tokens: int | None = None,
        timeout_s: float | None = None,
        thinking_budget: int | None = None,
        model: str | None = None,
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
        ctk: dict[str, Any] = {"enable_thinking": thinking}
        if thinking_budget is not None:
            ctk["thinking_budget"] = int(thinking_budget)
        body: dict[str, Any] = {
            # In router mode the agent passes the per-turn router preset name
            # ("<profile>-text" / "<profile>-vision"); else the configured model.
            # Without this the stream sent "gemma-4" and the router 400'd — the
            # reason agent.py never adopted streaming. Now threaded through.
            "model": model or self.config.model,
            "stream": True,
            "messages": messages,
            "temperature": self.config.temperature,
            "top_p": self.config.top_p,
            "top_k": self.config.top_k,
            "repeat_penalty": self.config.repeat_penalty,
            "max_tokens": max_tokens or self.config.max_tokens,
            "chat_template_kwargs": ctk,
        }
        if self.config.min_p is not None:
            body["min_p"] = self.config.min_p
        if self.config.seed is not None and int(self.config.seed) >= 0:
            body["seed"] = int(self.config.seed)
        if self.config.reasoning_format:
            body["reasoning_format"] = self.config.reasoning_format
        if tools:
            body["tools"] = tools
            # String form — this build wants OpenAI-style strings, not objects.
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
            headers=_request_headers(sse=True),
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
            headers=_request_headers(),
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
