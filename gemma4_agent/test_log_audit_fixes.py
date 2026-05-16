"""Tests for fixes from log audit (Bugs F, I, K)."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from .agent import TOOL_RULES
from .domain_tools import media_tool


class TestMediaSpotifyFallback(unittest.TestCase):
    """Bug F: spotify provider should fallback to youtube, not fail."""

    def test_spotify_falls_back_to_youtube(self):
        executor = MagicMock(return_value={
            "ok": True, "action": "youtube_play", "url": "https://youtube.com/..."
        })
        result = media_tool(
            {"action": "play", "provider": "spotify", "query": "cancion"},
            executor,
        )
        self.assertTrue(result.get("ok"), f"expected ok=True, got {result}")
        # Debe haber llamado a browser youtube_play
        executor.assert_called_once()
        call_args = executor.call_args
        self.assertEqual(call_args.args[0], "browser")
        self.assertEqual(call_args.args[1]["action"], "youtube_play")
        # Debe marcar el fallback
        self.assertEqual(result.get("fallback_from"), "spotify")
        note = result.get("fallback_note", "").lower()
        self.assertIn("youtube", note)
        self.assertIn("spotify", note)

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
        # No fallback_from cuando se pidio youtube directamente
        self.assertNotIn("fallback_from", result)

    def test_truly_unknown_provider_errors_with_hint(self):
        executor = MagicMock(return_value={"ok": True})
        result = media_tool(
            {"action": "play", "provider": "weirdservice", "query": "X"},
            executor,
        )
        self.assertFalse(result.get("ok"))
        # Hint debe sugerir alternativas validas
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
