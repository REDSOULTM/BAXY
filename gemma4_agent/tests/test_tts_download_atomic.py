"""download_voice() writes the Piper .onnx/.json to disk. A network drop
mid-stream must NOT leave a truncated file at the final path: voice_files_exist()
would report it present, load() would fail on the corrupt model, and TTS would
be bricked until manual cleanup (same failure class as the experience.py
corruption bug). The download must be atomic (temp .part -> os.replace) and
clean up the partial on failure.

EJE del norte rector: FIABILIDAD (persistencia en disco; un fallo de red no debe
dejar un artefacto que envenena cargas futuras)."""
from __future__ import annotations

import io
import unittest
from pathlib import Path
from unittest import mock

from gemma4_agent.voice import tts


class _FakeResp:
    """Context-manager HTTP response that streams `data`, optionally raising
    partway through to simulate a dropped connection."""
    def __init__(self, data: bytes, fail_after: int | None = None):
        self._buf = io.BytesIO(data)
        self._fail_after = fail_after
        self._read = 0
        self.headers = {"Content-Length": str(len(data))}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self, n):
        if self._fail_after is not None and self._read >= self._fail_after:
            raise OSError("connection reset")
        chunk = self._buf.read(n)
        self._read += len(chunk)
        return chunk


class TestAtomicDownload(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmpdir = Path(tempfile.mkdtemp())
        self._patch = mock.patch.object(tts, "PIPER_MODEL_DIR", self.tmpdir)
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_successful_download_lands_complete_file(self):
        payload = b"x" * (200 * 1024)
        with mock.patch("urllib.request.urlopen", return_value=_FakeResp(payload)):
            ok = tts.download_voice("es_MX-claude-high")
        self.assertTrue(ok)
        onnx = self.tmpdir / "es_MX-claude-high.onnx"
        self.assertTrue(onnx.is_file())
        self.assertEqual(onnx.stat().st_size, len(payload))
        # No leftover .part files.
        self.assertEqual(list(self.tmpdir.glob("*.part")), [])

    def test_midstream_failure_leaves_no_partial_at_final_path(self):
        payload = b"x" * (200 * 1024)
        # Fail after the first 64KB chunk -> simulates a network drop.
        with mock.patch("urllib.request.urlopen",
                        return_value=_FakeResp(payload, fail_after=64 * 1024)):
            ok = tts.download_voice("es_MX-claude-high")
        self.assertFalse(ok)
        # The final path must NOT exist (no truncated model to brick load()).
        self.assertFalse((self.tmpdir / "es_MX-claude-high.onnx").is_file())
        # And no .part garbage left behind.
        self.assertEqual(list(self.tmpdir.glob("*.part")), [])
        self.assertFalse(tts.voice_files_exist("es_MX-claude-high"))


if __name__ == "__main__":
    unittest.main()
