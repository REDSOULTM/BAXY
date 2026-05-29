"""Tests for fixes from log audit (Bugs F, I, K)."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from ..agent_core.agent import TOOL_RULES
from ..domain_tools import media_tool


class TestMediaSpotifyNative(unittest.TestCase):
    """Bug O: spotify provider should open Spotify natively (desktop or web)."""

    def test_spotify_opens_deeplink_or_web(self):
        # Post 2026-05-15: Spotify ahora hace auto-play (executor SI se
        # llama para focus + verify + keypress). Test que valida: el
        # deeplink se dispatched + provider es spotify + Popen llamado.
        from unittest.mock import patch
        def _exec(name, args):
            if name == "window" and args.get("action") == "focus":
                return {"ok": True}
            if name == "window" and args.get("action") == "active":
                return {"ok": True, "active": {"title": "Spotify"}}
            return {"ok": True}
        executor = MagicMock(side_effect=_exec)
        with patch("gemma4_agent.domain_tools.subprocess.Popen") as mock_popen, \
             patch("gemma4_agent.domain_tools._find_streaming_app",
                   return_value={"kind": "exe",
                                  "launch_target": r"C:\Spotify.exe"}), \
             patch("time.sleep"):
            result = media_tool(
                {"action": "play", "provider": "spotify", "query": "benson boone",
                 "auto_play": False},  # explicit false para mantener semantica del test viejo
                executor,
            )
        executor.assert_not_called()
        self.assertTrue(result.get("ok"), f"expected ok=True, got {result}")
        self.assertEqual(result.get("provider"), "spotify")
        self.assertIn("spotify:search:", result.get("deeplink", ""))
        mock_popen.assert_called_once()
        call = mock_popen.call_args.args[0]
        self.assertIn("start", call)
        self.assertTrue(any("spotify:search" in str(p) for p in call))

    def test_spotify_web_fallback_when_no_desktop(self):
        # Si el detector no encuentra app instalada, debe caer a Spotify Web.
        from unittest.mock import patch
        executor = MagicMock()
        with patch("gemma4_agent.domain_tools._find_streaming_app",
                   return_value={"kind": None, "launch_target": None}), \
             patch("gemma4_agent.domain_tools.webbrowser.open", return_value=True) as mock_open:
            result = media_tool(
                {"action": "play", "provider": "spotify", "query": "X"},
                executor,
            )
        self.assertTrue(result.get("ok"))
        self.assertEqual(result.get("provider"), "spotify_web")
        url = result.get("url", "")
        self.assertIn("open.spotify.com/search/", url)
        mock_open.assert_called_once()

    def test_spotify_requires_query(self):
        # 2026-05-22: comportamiento cambió — "pon una canción" SIN query
        # ahora reproduce random (Liked Songs shuffle si hay username, sino
        # Play global). El test viejo verificaba que rechazaba sin query.
        # Hoy es OK sin query (es una decisión de producto: Spotify random).
        # Memoria: project_spotify_random_2026_05_22.
        executor = MagicMock()
        result = media_tool(
            {"action": "play", "provider": "spotify"},
            executor,
        )
        # Random play sin query es válido — solo verificamos que es spotify.
        self.assertEqual(result.get("provider"), "spotify")

    def test_apple_music_falls_back_to_youtube(self):
        executor = MagicMock(return_value={"ok": True})
        result = media_tool(
            {"action": "play", "provider": "apple_music", "query": "cancion"},
            executor,
        )
        self.assertEqual(result.get("fallback_from"), "apple_music")

    def test_youtube_still_works_directly(self):
        executor = MagicMock(return_value={"ok": True})
        result = media_tool(
            {"action": "play", "provider": "youtube", "query": "X"},
            executor,
        )
        self.assertNotIn("fallback_from", result)

    def test_truly_unknown_provider_errors_with_hint(self):
        executor = MagicMock(return_value={"ok": True})
        result = media_tool(
            {"action": "play", "provider": "weirdservice", "query": "X"},
            executor,
        )
        self.assertFalse(result.get("ok"))
        hint = result.get("install_hint", "")
        self.assertIn("youtube", hint.lower())


class TestStreamingPlatforms(unittest.TestCase):
    """Streaming providers: Netflix, Disney+, HBO Max, Prime Video.

    Cubre el alias resolution, app detection, deeplink (cuando disponible),
    y web fallback (siempre). Mockean subprocess/webbrowser para no abrir
    ventanas en CI/dev.
    """

    def test_alias_resolution(self):
        from ..domain_tools import _resolve_streaming_provider
        cases = [
            ("netflix", "netflix"), ("NETFLIX", "netflix"),
            ("disney", "disney"), ("disney+", "disney"),
            ("Disney Plus", "disney"), ("disney_plus", "disney"),
            ("hbo_max", "hbo_max"), ("max", "hbo_max"), ("HBO Max", "hbo_max"),
            ("prime", "prime_video"), ("prime video", "prime_video"),
            ("Amazon Prime", "prime_video"), ("primevideo", "prime_video"),
            ("spotify", "spotify"),
        ]
        for alias, expected_canonical in cases:
            r = _resolve_streaming_provider(alias)
            self.assertIsNotNone(r, f"alias {alias!r} should resolve")
            self.assertEqual(r[0], expected_canonical, f"alias {alias!r}")

    def test_unknown_alias_returns_none(self):
        from ..domain_tools import _resolve_streaming_provider
        self.assertIsNone(_resolve_streaming_provider("twitch"))
        self.assertIsNone(_resolve_streaming_provider(""))
        self.assertIsNone(_resolve_streaming_provider("youtube"))

    def test_netflix_opens_web_search(self):
        # auto_play=false para evitar needs_user (no profile setup en este test).
        from unittest.mock import patch
        with patch("gemma4_agent.domain_tools.webbrowser.open", return_value=True) as wb:
            result = media_tool(
                {"action": "play", "provider": "netflix",
                 "query": "stranger things", "auto_play": False},
                MagicMock(),
            )
        self.assertTrue(result.get("ok"))
        self.assertEqual(result.get("provider"), "netflix_web")
        self.assertIn("netflix.com/search", result.get("url", ""))
        wb.assert_called_once()
        called_url = wb.call_args.args[0]
        self.assertIn("stranger%20things", called_url)

    def test_disney_plus_alias_resolves(self):
        from unittest.mock import patch
        with patch("gemma4_agent.domain_tools.webbrowser.open", return_value=True):
            result = media_tool(
                {"action": "play", "provider": "disney+",
                 "query": "Loki", "auto_play": False},
                MagicMock(),
            )
        self.assertTrue(result.get("ok"))
        self.assertEqual(result.get("provider"), "disney_web")
        self.assertIn("disneyplus.com", result.get("url", ""))

    def test_hbo_max_opens_search_url(self):
        # CDP probe 2026-05-16 verified: play.hbomax.com/search?q= works
        # post-login. Use it directly (not the marketing home, not /buscar).
        from unittest.mock import patch
        with patch("gemma4_agent.domain_tools.webbrowser.open", return_value=True):
            result = media_tool(
                {"action": "play", "provider": "max",
                 "query": "house of dragon", "auto_play": False},
                MagicMock(),
            )
        self.assertTrue(result.get("ok"))
        url = result.get("url", "")
        self.assertIn("hbomax.com", url)
        # max.com redirige a hbomax.com — never use www.max.com/search.
        self.assertFalse(url.startswith("https://www.max.com/search"))

    def test_prime_video_alias_resolves(self):
        from unittest.mock import patch
        with patch("gemma4_agent.domain_tools.webbrowser.open", return_value=True):
            result = media_tool(
                {"action": "play", "provider": "prime",
                 "query": "the boys", "auto_play": False},
                MagicMock(),
            )
        self.assertTrue(result.get("ok"))
        self.assertIn("primevideo.com", result.get("url", ""))

    def test_streaming_requires_query(self):
        result = media_tool(
            {"action": "play", "provider": "netflix", "auto_play": False},
            MagicMock(),
        )
        self.assertFalse(result.get("ok"))
        self.assertIn("query", str(result.get("error", "")).lower())

    def test_status_exposes_streaming_platforms(self):
        # status no requiere mock — solo lee disco
        result = media_tool({"action": "status"}, MagicMock())
        self.assertTrue(result.get("ok"))
        sp = result.get("streaming_platforms", {})
        for canonical in ("spotify", "netflix", "disney", "hbo_max", "prime_video"):
            self.assertIn(canonical, sp, f"status should report {canonical}")
            # Cada entry tiene app_installed bool y has_deeplink bool
            self.assertIn("app_installed", sp[canonical])
            self.assertIn("has_deeplink", sp[canonical])

    def test_spotify_deeplink_when_desktop_installed(self):
        # 2026-05-28: Popen ahora se llama 2 veces (la app evolucionó —
        # primer Popen para focus check, segundo para abrir el deeplink).
        # El contract real es: AL MENOS una llamada con el spotify:search.
        from unittest.mock import patch
        with patch("gemma4_agent.domain_tools.subprocess.Popen") as popen, \
             patch("gemma4_agent.domain_tools._find_streaming_app",
                   return_value={"kind": "exe", "launch_target": r"C:\X\Spotify.exe"}):
            result = media_tool(
                {"action": "play", "provider": "spotify", "query": "benson boone"},
                MagicMock(),
            )
        self.assertTrue(result.get("ok"))
        self.assertEqual(result.get("provider"), "spotify")
        self.assertIn("spotify:search:", result.get("deeplink", ""))
        # Al menos UNA llamada — no exactly once.
        self.assertGreaterEqual(popen.call_count, 1)


class TestBrowserToolRule(unittest.TestCase):
    """Bug I: browser rule should clarify minimize/maximize/close → window(...)."""

    def test_browser_rule_mentions_window_for_minimize(self):
        rule = TOOL_RULES.get("browser", "")
        self.assertIn("minimize", rule.lower())
        self.assertIn("window(", rule.lower())

    def test_browser_rule_has_concrete_example(self):
        rule = TOOL_RULES.get("browser", "")
        # Debe tener un ejemplo concreto (opera)
        self.assertIn("opera", rule.lower())


class TestDetectCrashSignature(unittest.TestCase):
    """Bug K: log inspection for crash diagnostics."""

    def setUp(self):
        from ..infra.config import AgentConfig
        from ..infra.llama_server import LlamaServerManager
        self.tmp = tempfile.TemporaryDirectory()
        tmp_root = Path(self.tmp.name)
        captures = tmp_root / "captures"
        captures.mkdir()
        logs = tmp_root / "logs"
        logs.mkdir()
        self.log_path = logs / "llama-server.err.log"
        # Build config with custom captures_dir
        # AgentConfig is frozen dataclass; use dataclasses.replace
        from dataclasses import replace
        base = AgentConfig.from_env()
        self.cfg = replace(base, captures_dir=captures)
        self.mgr = LlamaServerManager(config=self.cfg)

    def tearDown(self):
        self.tmp.cleanup()

    def _write_log(self, content: str) -> None:
        self.log_path.write_text(content, encoding="utf-8")

    def test_no_log_file_returns_empty(self):
        # Sin log file -> dict con kind=None
        result = self.mgr.detect_crash_signature()
        self.assertIsNone(result["kind"])

    def test_detects_cuda_illegal_memory(self):
        self._write_log(
            "slot update_slots: id 0 | task 100 | progress=0.99\n"
            "CUDA error: an illegal memory access was encountered\n"
            "  current device: 0, in function ggml_backend_cuda_synchronize\n"
        )
        result = self.mgr.detect_crash_signature()
        self.assertEqual(result["kind"], "cuda_illegal_memory")
        self.assertIn("CUDA", result["summary"])
        self.assertIn("CUDA error", result["log_excerpt"])

    def test_detects_oom(self):
        self._write_log("model loaded\nerror: out of memory allocating tensor\n")
        result = self.mgr.detect_crash_signature()
        self.assertEqual(result["kind"], "oom")

    def test_detects_context_overflow(self):
        self._write_log(
            "request body received\n"
            '{"error":{"message":"request exceeds the available context size"}}\n'
        )
        result = self.mgr.detect_crash_signature()
        self.assertEqual(result["kind"], "context_overflow")

    def test_clean_log_returns_none(self):
        self._write_log(
            "main: model loaded\n"
            "main: server is listening on http://127.0.0.1:8080\n"
            "main: starting the main loop...\n"
        )
        result = self.mgr.detect_crash_signature()
        self.assertIsNone(result["kind"])


if __name__ == "__main__":
    unittest.main()
