"""voice_runner reuses ONE VoicePipeline instance across enable()/disable()
cycles (the UI toggles voice off/on). If stop() is called mid-CAPTURE without
resetting the state machine, the pipeline stays in CAPTURE with a stale
_capture_buf; the next start()'s first chunk appends to that stale buffer and
can fire _finish_capture -> a PHANTOM command transcribed from the previous
session's audio.

EJE del norte rector: FIABILIDAD (el agente no debe emitir un comando fantasma
de una sesión anterior tras un ciclo stop/start del usuario). Teardown hygiene,
mismo patrón lifecycle de las rondas previas."""
from __future__ import annotations

import unittest
from unittest import mock

import numpy as np

from gemma4_agent.voice.pipeline import VoicePipeline, State


class TestStopResetsStateMachine(unittest.TestCase):
    def _pipe(self):
        # on_command must never be called as a side effect of stop().
        self.commands = []
        return VoicePipeline(on_command=lambda t, d, r: self.commands.append(t))

    def test_stop_returns_to_idle_and_clears_buffer(self):
        pipe = self._pipe()
        # Simulate a wake mid-capture: state CAPTURE + a stale buffer.
        pipe._state = State.CAPTURE
        pipe._capture_buf = [np.ones(256, dtype=np.int16) * 1000 for _ in range(20)]
        pipe._eos_silence_count = 5
        pipe._preroll.append(np.zeros(256, dtype=np.int16))

        pipe.stop()

        self.assertEqual(pipe.state, State.IDLE, "stop must reset to IDLE")
        self.assertEqual(pipe._capture_buf, [], "stale capture buffer must be cleared")
        self.assertEqual(pipe._eos_silence_count, 0)
        self.assertEqual(len(pipe._preroll), 0)

    def test_stop_during_capture_does_not_emit_phantom_after_restart(self):
        pipe = self._pipe()
        # Put it in CAPTURE with a loud stale buffer that WOULD pass the silence
        # gate and transcribe if it leaked into a restarted session.
        pipe._state = State.CAPTURE
        pipe._capture_buf = [np.ones(800, dtype=np.int16) * 2000 for _ in range(40)]
        pipe._capture_start_ts = 0.0  # "old" capture

        pipe.stop()

        # After stop the machine is IDLE. Feed a chunk as if a restarted session
        # delivered audio: in IDLE it must go to wake detection, NOT capture, so
        # no command is emitted from the stale buffer.
        with mock.patch.object(pipe._wake, "feed") as wake_feed:
            pipe._on_chunk(np.zeros(256, dtype=np.int16))
            wake_feed.assert_called_once()
        self.assertEqual(self.commands, [], "no phantom command after stop/restart")

    def test_stop_is_safe_when_components_unloaded(self):
        # reset() on never-loaded wake/vad must not raise.
        pipe = self._pipe()
        pipe.stop()  # already IDLE, components unloaded
        self.assertEqual(pipe.state, State.IDLE)


if __name__ == "__main__":
    unittest.main()
