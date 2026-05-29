"""Unit tests for LLMClient retry on connection reset (Fix 2)."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from ..infra.config import AgentConfig
from ..infra.llm_client import (
    LLMClient,
    _is_recoverable_connection_error,
    _is_proxy_zombie_error,
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


class TestIsProxyZombie(unittest.TestCase):
    """Firma del 500 del FRONT del router cuando el child worker murió (#13085)."""

    def test_could_not_establish_connection(self):
        e = RuntimeError("llm_http_error 500: proxy error: Could not establish connection")
        self.assertTrue(_is_proxy_zombie_error(e))

    def test_failed_to_read_connection(self):
        e = RuntimeError("llm_http_error 500: proxy error: Failed to read connection")
        self.assertTrue(_is_proxy_zombie_error(e))

    def test_plain_500_is_not_proxy_zombie(self):
        # un 500 genérico (bug del server, no proxy-zombie) NO dispara reinicio.
        e = RuntimeError("llm_http_error 500: internal server error")
        self.assertFalse(_is_proxy_zombie_error(e))

    def test_400_is_not_proxy_zombie(self):
        e = RuntimeError("llm_http_error 400: proxy error: bad request")
        self.assertFalse(_is_proxy_zombie_error(e))

    def test_connection_reset_is_not_proxy_zombie(self):
        # un reset de conexión lo maneja el otro path (no requiere restart).
        e = RuntimeError("[WinError 10054] connection reset")
        self.assertFalse(_is_proxy_zombie_error(e))


class TestProxyZombieRecovery(unittest.TestCase):
    """Recovery del proxy 500 (router-mode, child muerto): RESTART INMEDIATO
    + 1 reintento. Sin soft-retry, sin bucle de attempts.

    v21 2026-05-28: REVERTIDO al diseño del commit 7b2377d. La sesion previa
    a la mia habia agregado soft-retry (12s espera) + bucle de 3 attempts.
    Eso llevaba el recovery exitoso de ~3s a ~30-90s, percibido por el
    usuario como 'el server se cae'. El diseño simple: el child crashea ->
    restart (~3s) -> reintento. Si re-crashea, error explicito al user.
    """

    def setUp(self):
        self.client = LLMClient(AgentConfig.from_env())
        self.body = {"messages": [{"role": "user", "content": "hi"}]}

    def test_500_zombie_restart_then_retry_ok(self):
        """Caso normal: chat -> 500 zombie -> restart -> reintento OK."""
        responses = [
            RuntimeError("llm_http_error 500: proxy error: Could not establish connection"),
            {"choices": [{"message": {"content": "ok after restart"}}]},
        ]
        with patch.object(self.client, "_post_chat", side_effect=responses) as mock_post, \
             patch("gemma4_agent.llm_client._try_restart_managed_server",
                   return_value=True) as mock_restart, \
             patch("time.sleep"):
            result = self.client._post_chat_with_recovery(self.body, timeout=30.0)
            self.assertEqual(mock_post.call_count, 2)
            mock_restart.assert_called_once()
            self.assertEqual(result["choices"][0]["message"]["content"], "ok after restart")

    def test_500_zombie_restart_fails_raises(self):
        """Si el restart no recupera (manager devuelve False) -> error explicito."""
        with patch.object(self.client, "_post_chat",
                          side_effect=RuntimeError("llm_http_error 500: proxy error: Could not establish connection")), \
             patch("gemma4_agent.llm_client._try_restart_managed_server", return_value=False), \
             patch("time.sleep"):
            with self.assertRaises(RuntimeError) as ctx:
                self.client._post_chat_with_recovery(self.body, timeout=30.0)
            self.assertIn("llm_proxy_zombie_no_recovery", str(ctx.exception))

    def test_500_zombie_restart_ok_but_retry_500_raises(self):
        """Restart OK pero el retry vuelve a 500 (child re-crashea inmediato):
        propaga error explicito (no se intenta otro restart)."""
        with patch.object(self.client, "_post_chat",
                          side_effect=RuntimeError("llm_http_error 500: proxy error: Could not establish connection")) as mock_post, \
             patch("gemma4_agent.llm_client._try_restart_managed_server", return_value=True) as mock_restart, \
             patch("time.sleep"):
            with self.assertRaises(RuntimeError) as ctx:
                self.client._post_chat_with_recovery(self.body, timeout=30.0)
            self.assertIn("llm_proxy_zombie_after_restart", str(ctx.exception))
            # 1 chat inicial + 1 retry tras restart = 2 calls
            self.assertEqual(mock_post.call_count, 2)
            mock_restart.assert_called_once()


class TestTryRestartManagedServer(unittest.TestCase):
    """_try_restart_managed_server: reinicia SOLO un server gestionado, no el
    externo del usuario; lee el resultado de restart() correctamente."""

    def test_restarts_when_managed_and_running(self):
        from unittest.mock import MagicMock
        import gemma4_agent.infra.llm_client as lc
        mgr = MagicMock()
        mgr.is_running.return_value = True
        mgr.restart.return_value = "started"
        with patch("gemma4_agent.llama_server.get_shared_manager", return_value=mgr), \
             patch("gemma4_agent.profiles.get_active_profile", return_value=object()):
            self.assertTrue(lc._try_restart_managed_server())
            mgr.restart.assert_called_once()

    def test_noop_when_not_running(self):
        # server externo / no-gestionado -> is_running False -> NO reinicia.
        from unittest.mock import MagicMock
        import gemma4_agent.infra.llm_client as lc
        mgr = MagicMock()
        mgr.is_running.return_value = False
        with patch("gemma4_agent.llama_server.get_shared_manager", return_value=mgr), \
             patch("gemma4_agent.profiles.get_active_profile", return_value=object()):
            self.assertFalse(lc._try_restart_managed_server())
            mgr.restart.assert_not_called()

    def test_never_raises_on_error(self):
        import gemma4_agent.infra.llm_client as lc
        with patch("gemma4_agent.llama_server.get_shared_manager",
                   side_effect=RuntimeError("boom")):
            # nunca debe romper el turno por el recovery
            self.assertFalse(lc._try_restart_managed_server())


class TestSmokeProbeChat(unittest.TestCase):
    """_smoke_probe_chat: chat completion minimo end-to-end despues del restart.

    Cubre el gap entre /health y /v1/chat/completions en router-mode:
    el front responde 200 a /health pero el child todavia no acepta requests
    (investigacion 6 punto 3, llama.cpp issues #20684 #20921).
    """

    def test_smoke_probe_ok_when_200(self):
        from unittest.mock import MagicMock
        import gemma4_agent.infra.llm_client as lc
        fake_resp = MagicMock()
        fake_resp.status = 200
        fake_resp.__enter__ = lambda s: s
        fake_resp.__exit__ = lambda *a: None
        with patch("urllib.request.urlopen", return_value=fake_resp):
            self.assertTrue(lc._smoke_probe_chat(timeout_s=1.0))

    def test_smoke_probe_fail_on_proxy_zombie_500(self):
        """Si el smoke recibe el MISMO 500 del proxy zombie -> False
        (el restart no recupero de verdad)."""
        import gemma4_agent.infra.llm_client as lc
        import urllib.error
        err = urllib.error.HTTPError(
            url="http://x/v1/chat/completions", code=500,
            msg="Server Error", hdrs=None,
            fp=__import__("io").BytesIO(
                b"proxy error: Failed to read connection"),
        )
        with patch("urllib.request.urlopen", side_effect=err):
            self.assertFalse(lc._smoke_probe_chat(timeout_s=1.0))

    def test_smoke_probe_fail_on_connection_refused(self):
        import gemma4_agent.infra.llm_client as lc
        import urllib.error
        with patch("urllib.request.urlopen",
                   side_effect=urllib.error.URLError("[WinError 10061] refused")):
            self.assertFalse(lc._smoke_probe_chat(timeout_s=1.0))

    def test_smoke_probe_ok_on_400(self):
        """400 = server vivo rechaza el body, no zombie. Vale como 'vive'."""
        import gemma4_agent.infra.llm_client as lc
        import urllib.error
        err = urllib.error.HTTPError(
            url="http://x/v1/chat/completions", code=400,
            msg="Bad Request", hdrs=None,
            fp=__import__("io").BytesIO(b"bad model"),
        )
        with patch("urllib.request.urlopen", side_effect=err):
            self.assertTrue(lc._smoke_probe_chat(timeout_s=1.0))


if __name__ == "__main__":
    unittest.main()
