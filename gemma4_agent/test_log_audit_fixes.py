"""Tests for fixes from log audit (Bugs F, I, K)."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from .agent import TOOL_RULES
from .domain_tools import media_tool


class TestMediaSpotifyNative(unittest.TestCase):
    """Bug O: spotify provider should open Spotify natively (desktop or web)."""

    def test_spotify_opens_deeplink_or_web(self):
        from unittest.mock import patch
        executor = MagicMock()
        # Mock subprocess.Popen so we don't actually launch anything
        with patch("gemma4_agent.domain_tools.subprocess.Popen") as mock_popen, \
             patch("gemma4_agent.domain_tools._find_spotify_executable",
                   return_value=r"C:\Users\test\AppData\Roaming\Spotify\Spotify.exe"):
            result = media_tool(
                {"action": "play", "provider": "spotify", "query": "benson boone"},
                executor,
            )
        # No debe haber llamado executor (no fallback a browser).
        executor.assert_not_called()
        # Debe haber abierto el deeplink spotify:
        self.assertTrue(result.get("ok"), f"expected ok=True, got {result}")
        self.assertEqual(result.get("provider"), "spotify")
        self.assertIn("spotify:search:", result.get("deeplink", ""))
        # Y haber llamado subprocess.Popen con el cmd start
        mock_popen.assert_called_once()
        call = mock_popen.call_args.args[0]
        self.assertIn("start", call)
        self.assertTrue(any("spotify:search" in str(p) for p in call))

    def test_spotify_web_fallback_when_no_desktop(self):
        from unittest.mock import patch
        executor = MagicMock()
        with patch("gemma4_agent.domain_tools._find_spotify_executable", return_value=None), \
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
        executor = MagicMock()
        result = media_tool(
            {"action": "play", "provider": "spotify"},
            executor,
        )
        self.assertFalse(result.get("ok"))
        # Mensaje debe mencionar query
        self.assertIn("query", str(result.get("error", "")).lower())

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
        from .config import AgentConfig
        from .llama_server import LlamaServerManager
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
