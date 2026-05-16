"""Unit tests for LLMClient retry on connection reset (Fix 2)."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from .config import AgentConfig
from .llm_client import (
    LLMClient,
    _is_recoverable_connection_error,
)


class TestIsRecoverable(unittest.TestCase):

    def test_winerror_10054(self):
        e = RuntimeError(
            "llm_connection_error: <urlopen error [WinError 10054] "
            "Se ha forzado la interrupcion de una conexion existente por el host remoto>"
        )
        self.assertTrue(_is_recoverable_connection_error(e))

    def test_winerror_10061(self):
        e = RuntimeError("[WinError 10061] No connection could be made")
        self.assertTrue(_is_recoverable_connection_error(e))

    def test_connection_reset_linux(self):
        e = RuntimeError("ConnectionResetError: [Errno 104] Connection reset by peer")
        self.assertTrue(_is_recoverable_connection_error(e))

    def test_broken_pipe(self):
        e = RuntimeError("[Errno 32] Broken pipe")
        self.assertTrue(_is_recoverable_connection_error(e))

    def test_timeout_is_not_recoverable(self):
        # Timeouts pueden ser legitimos del LLM tardando — no reintentar.
        e = RuntimeError("llm_timeout: request exceeded 60.0s")
        self.assertFalse(_is_recoverable_connection_error(e))

    def test_http_400_is_not_recoverable(self):
        # Errores 4xx son del cliente / payload — no reintentar.
        e = RuntimeError("llm_http_error 400: invalid arguments")
        self.assertFalse(_is_recoverable_connection_error(e))

    def test_http_500_is_not_recoverable_by_this_path(self):
        # 500 puede ser bug del server, no reload. Lo deja pasar al caller.
        e = RuntimeError("llm_http_error 500: internal")
        self.assertFalse(_is_recoverable_connection_error(e))


class TestPostChatWithRecovery(unittest.TestCase):

    def setUp(self):
        self.client = LLMClient(AgentConfig.from_env())
        self.body = {"messages": [{"role": "user", "content": "hi"}]}

    def test_success_first_try_no_retry(self):
        with patch.object(self.client, "_post_chat",
                          return_value={"choices": [{"message": {"content": "ok"}}]}) as mock_post:
            result = self.client._post_chat_with_recovery(self.body, timeout=30.0)
            self.assertEqual(mock_post.call_count, 1)
            self.assertIn("choices", result)

    def test_reset_then_healthy_retries_once(self):
        # 1ra llamada: connection reset; despues health=True; 2da llamada: ok.
        responses = [
            RuntimeError("[WinError 10054] connection reset"),
            {"choices": [{"message": {"content": "ok after retry"}}]},
        ]
        with patch.object(self.client, "_post_chat",
                          side_effect=responses) as mock_post, \
             patch.object(self.client, "health", return_value=True):
            result = self.client._post_chat_with_recovery(self.body, timeout=30.0)
            self.assertEqual(mock_post.call_count, 2)
            self.assertEqual(result["choices"][0]["message"]["content"], "ok after retry")

    def test_reset_health_never_returns_raises(self):
        # connection reset, pero el server nunca vuelve healthy: propaga error.
        with patch.object(self.client, "_post_chat",
                          side_effect=RuntimeError("[WinError 10054] connection reset")), \
             patch.object(self.client, "health", return_value=False), \
             patch("time.sleep"):  # acelerar el poll loop
            with self.assertRaises(RuntimeError) as ctx:
                # timeout=2 -> wait_budget=1s; el loop terminara rapido.
                self.client._post_chat_with_recovery(self.body, timeout=2.0)
            self.assertIn("llm_connection_reset_no_recovery", str(ctx.exception))

    def test_reset_then_reset_again_raises(self):
        # connection reset; health=True; pero segundo intento tambien reset:
        # propaga sin tercer retry.
        with patch.object(self.client, "_post_chat",
                          side_effect=RuntimeError("[WinError 10054] connection reset")), \
             patch.object(self.client, "health", return_value=True), \
             patch("time.sleep"):
            with self.assertRaises(RuntimeError) as ctx:
                self.client._post_chat_with_recovery(self.body, timeout=30.0)
            self.assertIn("llm_connection_reset_after_retry", str(ctx.exception))

    def test_unsupported_option_falls_back_without_keys(self):
        # Build viejo de llama-server rechaza chat_template_kwargs (400).
        # Cliente debe reintentar sin esos keys, NO entrar en el retry de reset.
        body_with_extras = {
            **self.body,
            "chat_template_kwargs": {"enable_thinking": False},
            "reasoning_format": "",
        }
        responses = [
            RuntimeError("llm_http_error 400: unknown field chat_template_kwargs"),
            {"choices": [{"message": {"content": "fallback ok"}}]},
        ]
        with patch.object(self.client, "_post_chat",
                          side_effect=responses) as mock_post:
            result = self.client._post_chat_with_recovery(body_with_extras, timeout=30.0)
            self.assertEqual(mock_post.call_count, 2)
            # Segunda llamada debe NO tener los extras
            second_body = mock_post.call_args_list[1].args[0]
            self.assertNotIn("chat_template_kwargs", second_body)
            self.assertNotIn("reasoning_format", second_body)

    def test_non_recoverable_error_propagates(self):
        # 400 Bad Request por args invalidos -> propaga sin retry.
        with patch.object(self.client, "_post_chat",
                          side_effect=RuntimeError("llm_http_error 400: messages required")):
            with self.assertRaises(RuntimeError):
                self.client._post_chat_with_recovery(self.body, timeout=30.0)


if __name__ == "__main__":
    unittest.main()
