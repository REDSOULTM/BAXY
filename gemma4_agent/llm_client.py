"""Minimal OpenAI-compatible client for llama-server / Gemma 4."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

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
            return self._post_chat(body, timeout=effective_timeout)
        except RuntimeError as exc:
            if not _looks_like_unsupported_option_error(str(exc)):
                raise
            fallback = dict(body)
            fallback.pop("chat_template_kwargs", None)
            fallback.pop("reasoning_format", None)
            fallback.pop("parse_tool_calls", None)
            fallback.pop("parallel_tool_calls", None)
            return self._post_chat(fallback, timeout=effective_timeout)

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
