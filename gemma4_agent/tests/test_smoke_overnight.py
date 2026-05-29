"""Overnight smoke suite — one fast smoke per fix won across the audit rounds.

Each smoke pins the CORE invariant of a fix so a regression trips here cheaply
(<5s total, no GPU, no network, no real models). The docstring of each test
names the EJE del norte rector it guards: ARQUITECTURA / FIABILIDAD / LATENCIA /
CALIDAD UX. This is a tripwire suite, not a replacement for the per-fix tests.

Run: PYTHONPATH=. python -m pytest gemma4_agent/tests/test_smoke_overnight.py -q
"""
from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

import numpy as np


class SmokeReliability(unittest.TestCase):
    # ---- round 11: llama_server lifecycle --------------------------------

    def test_shared_manager_atexit_noop_without_server(self):
        """FIABILIDAD: atexit teardown must never raise when no server ran."""
        from gemma4_agent.infra import llama_server as ls

        ls._SHARED_MANAGER = None
        ls._atexit_stop_shared_manager()  # must not raise

    def test_shared_manager_atexit_stops_managed(self):
        """FIABILIDAD: managed llama-server is stopped on exit (frees VRAM)."""
        from gemma4_agent.infra import llama_server as ls

        fake = mock.MagicMock()
        ls._SHARED_MANAGER = fake
        try:
            ls._atexit_stop_shared_manager()
            fake.stop.assert_called_once()
        finally:
            ls._SHARED_MANAGER = None

    def test_redact_sensitive_never_crashes_on_numpy(self):
        """FIABILIDAD: safety-path helper must not raise on a numpy value."""
        from gemma4_agent._shared import redact_sensitive
        out = redact_sensitive({"password": np.array([1, 2, 3])})
        self.assertEqual(out["password"], "***REDACTED***")

    def test_experience_corruption_recovery_importable(self):
        """FIABILIDAD: corruption-recovery path exists (quarantine + recreate)."""
        from gemma4_agent.memory_pkg import experience

        self.assertTrue(hasattr(experience.ExperienceMemory, "_quarantine_corrupt_db"))

    # ---- round 7: primitives ---------------------------------------------

    def test_middle_ellipsis_never_grows(self):
        """LATENCIA: the truncation primitive must never return MORE than limit."""
        from gemma4_agent.agent_core.agent_compaction import middle_ellipsis
        for limit in (10, 80, 160, 500):
            out = middle_ellipsis("x" * 1000, limit)
            self.assertLessEqual(len(out), limit, f"grew at limit={limit}")

    def test_sanitize_strips_unclosed_think(self):
        """CALIDAD UX: an unclosed <think> (budget-cut) must not reach the user."""
        from gemma4_agent.support.reasoning import sanitize_text
        self.assertNotIn("<think>", sanitize_text("hola <think>razonando sin cerrar"))

    def test_tracing_failsafe_bad_path(self):
        """FIABILIDAD: an unwritable trace path disables tracing, never crashes."""
        import tempfile
        from gemma4_agent.infra.tracing import TraceLogger
        # Parent is an existing FILE -> mkdir raises OSError (the realistic
        # failure: full disk / permission / parent-is-file). The round-7 fix
        # must disable tracing instead of crashing the agent constructor.
        fd, fpath = tempfile.mkstemp()
        import os
        os.close(fd)
        try:
            tl = TraceLogger(path=Path(fpath) / "subdir" / "traces.jsonl")
            self.assertFalse(tl.enabled, "bad path must disable tracing")
            tl.event("turn1", "turn_start", x=1)  # no-op, not a crash
        finally:
            os.unlink(fpath)

    # ---- round 6: telemetry ----------------------------------------------

    def test_telemetry_rotate_one_shot_guard(self):
        """ARQUITECTURA+LATENCIA: rotate() exists + the per-process one-shot guard
        wires rotate() into _ensure_initialized (round-6: rotate was dead code)."""
        import inspect
        from gemma4_agent.infra.telemetry import TelemetryStore
        self.assertTrue(hasattr(TelemetryStore, "rotate"))
        init_src = inspect.getsource(TelemetryStore._ensure_initialized)
        self.assertIn("_rotated_this_process", init_src)
        self.assertIn("rotate", init_src)


class SmokeLatency(unittest.TestCase):
    def test_per_mode_timeout_orders_fast_below_research(self):
        """LATENCIA+FIABILIDAD: fast_action deadline < research deadline, both bounded."""
        from gemma4_agent.support.modes import choose_mode
        fast = choose_mode("hola", "fast_action", 256)
        research = choose_mode("investiga la historia de Roma", "research", 256)
        self.assertLess(fast.request_timeout_s, research.request_timeout_s)
        self.assertGreaterEqual(fast.request_timeout_s, 20)
        self.assertLessEqual(research.request_timeout_s, 150)

    def test_wake_predict_throttle_default(self):
        """LATENCIA: wake predict decimation default keeps idle CPU ~75% lower."""
        from gemma4_agent.voice import wake
        self.assertGreaterEqual(wake.LIVEKIT_PREDICT_EVERY_N_CHUNKS, 2)


class SmokeVoice(unittest.TestCase):
    def test_silence_gate_rms_floor(self):
        """CALIDAD UX: silence gate floor is set (blocks Whisper hallucination)."""
        from gemma4_agent.voice import pipeline
        self.assertGreater(pipeline.MIN_CAPTURE_RMS, 0)

    def test_pipeline_stop_resets_to_idle(self):
        """FIABILIDAD: stop() returns the state machine to IDLE (no phantom cmd)."""
        from gemma4_agent.voice.pipeline import VoicePipeline, State
        pipe = VoicePipeline(on_command=lambda *a: None)
        pipe._state = State.CAPTURE
        pipe._capture_buf = [np.ones(256, dtype=np.int16)]
        pipe.stop()
        self.assertEqual(pipe.state, State.IDLE)
        self.assertEqual(pipe._capture_buf, [])

    def test_tts_download_is_atomic(self):
        """FIABILIDAD: voice download writes via a .part temp (atomic rename)."""
        import inspect
        from gemma4_agent.voice import tts
        src = inspect.getsource(tts.download_voice)
        self.assertIn(".part", src)
        self.assertIn("os.replace", src)

    def test_stt_rejects_empty_audio(self):
        """FIABILIDAD: STT returns '' for empty/degenerate audio (no decode)."""
        from gemma4_agent.voice.stt import STT
        s = STT()
        # Not loaded -> '' ; and the size guard short-circuits a tiny buffer.
        self.assertEqual(s.transcribe(np.zeros(10, dtype=np.int16)), "")

    def test_no_speech_state_mapped(self):
        """CALIDAD UX: NO_SPEECH feedback signal exists in the pipeline vocab."""
        import inspect
        from gemma4_agent.voice import pipeline
        self.assertIn("NO_SPEECH", inspect.getsource(pipeline.VoicePipeline._finish_capture))


class SmokeArchitecture(unittest.TestCase):
    def test_loop_detection_never_crashes_on_mixed_keys(self):
        """FIABILIDAD: the loop detector must not raise on mixed-key tool args."""
        from gemma4_agent.safety_pkg.loop_detection import _hash_tool_call, _result_signature
        # Mixed str/int keys used to raise TypeError in the signature hash.
        h = _hash_tool_call("t", {1: "a", "b": 2}, _result_signature({"ok": True}))
        self.assertIsInstance(h, str)

    def test_lazy_loaders_have_locks(self):
        """ARQUITECTURA: lazy model loaders use a module lock (no double-load race)."""
        from gemma4_agent.routing import semantic_router

        from gemma4_agent.tools_pkg import mcp_server

        self.assertTrue(hasattr(semantic_router, "_LOAD_LOCK"))
        self.assertTrue(hasattr(mcp_server, "_REGISTRY_LOCK"))

    def test_log_handles_helper_exists(self):
        """FIABILIDAD: the server manager closes its child-log handles."""
        from gemma4_agent.infra.llama_server import LlamaServerManager
        self.assertTrue(hasattr(LlamaServerManager, "_close_log_handles"))


if __name__ == "__main__":
    unittest.main()
