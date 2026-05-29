"""VoiceRunner.disable() calls _tts.stop(), which kills the Piper worker
thread. On the NEXT enable() the runner reuses the same _tts object, so unless
enable() re-calls _tts.start() the queue is never consumed again and the agent
goes MUTE on every voice off/on cycle (sibling of the 'TTS mudo sin flush'
lifecycle gap).

EJE del norte rector: FIABILIDAD / CALIDAD UX (el agente no debe quedar mudo
tras un ciclo stop/start de la voz)."""
from __future__ import annotations

import unittest
from unittest import mock

from gemma4_agent.infra.voice_runner import VoiceRunner


class TestTtsReEnable(unittest.TestCase):
    def _runner_with_mocks(self):
        runner = VoiceRunner()
        # Fake TTS: loaded, tracks start/stop calls.
        tts = mock.MagicMock()
        tts.load.return_value = True
        tts.is_loaded.return_value = True
        # Fake pipeline: load/start succeed.
        pipe = mock.MagicMock()
        pipe.load.return_value = True
        pipe.start.return_value = True
        self._patches = [
            mock.patch("gemma4_agent.voice_runner.StreamingTTS", return_value=tts),
            mock.patch("gemma4_agent.voice_runner.VoicePipeline", return_value=pipe),
        ]
        for p in self._patches:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in self._patches])
        return runner, tts, pipe

    def test_tts_started_on_first_enable(self):
        runner, tts, _ = self._runner_with_mocks()
        self.assertTrue(runner.enable())
        tts.start.assert_called_once()

    def test_tts_restarted_after_disable_enable_cycle(self):
        runner, tts, _ = self._runner_with_mocks()
        runner.enable()
        runner.disable()
        tts.stop.assert_called()  # disable killed the worker
        # Re-enable: the SAME tts object is reused; start() MUST be called again
        # or the agent stays mute.
        runner._enabled = False  # disable() set this False already; explicit
        runner.enable()
        self.assertGreaterEqual(
            tts.start.call_count, 2,
            "enable() after disable() must restart the TTS worker",
        )

    def test_tts_load_failure_does_not_block_voice(self):
        """Coverage gap (Fase 3): if TTS load() fails, voice must still enable
        (mic/wake/STT work; the agent just can't speak). start() must NOT be
        called on the unloaded TTS, and re-enable must not crash."""
        runner = VoiceRunner()
        tts = mock.MagicMock()
        tts.load.return_value = False     # speech unavailable
        tts.is_loaded.return_value = False
        pipe = mock.MagicMock()
        pipe.load.return_value = True
        pipe.start.return_value = True
        with mock.patch("gemma4_agent.voice_runner.StreamingTTS", return_value=tts), \
                mock.patch("gemma4_agent.voice_runner.VoicePipeline", return_value=pipe):
            self.assertTrue(runner.enable(), "voice must enable even if TTS load fails")
            tts.start.assert_not_called()  # never start an unloaded TTS worker
            runner.disable()
            runner._enabled = False
            self.assertTrue(runner.enable(), "re-enable must not crash with failed TTS")
            tts.start.assert_not_called()


if __name__ == "__main__":
    unittest.main()
