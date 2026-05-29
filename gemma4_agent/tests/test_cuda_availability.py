"""Q.0: ctranslate2 CUDA support is the authoritative signal for
STT GPU availability — not torch.cuda.is_available(). torch may
be CPU-only on operator systems even when faster-whisper can run
on GPU via ctranslate2's own CUDA build.
"""
from __future__ import annotations

import unittest


class CtranslateCudaProbeTest(unittest.TestCase):
    """These tests document the contract that ctranslate2 is the
    source of truth for GPU availability in this project's STT
    pipeline. Tests don't REQUIRE CUDA to pass — they SKIP cleanly
    on systems without it."""

    def test_ctranslate2_importable(self) -> None:
        try:
            import ctranslate2
        except ImportError:
            self.skipTest("ctranslate2 not installed")
        self.assertTrue(hasattr(ctranslate2, "get_cuda_device_count"))

    def test_ctranslate2_cuda_count_is_int(self) -> None:
        try:
            import ctranslate2
        except ImportError:
            self.skipTest("ctranslate2 not installed")
        count = ctranslate2.get_cuda_device_count()
        self.assertIsInstance(count, int)
        self.assertGreaterEqual(count, 0)

    def test_faster_whisper_gpu_inference_works(self) -> None:
        """End-to-end probe: load tiny model on cuda, transcribe
        1s of audio. SKIPS if no CUDA device, FAILS if device
        present but inference raises (the Q.0 bug)."""
        try:
            import ctranslate2
            from faster_whisper import WhisperModel
            import numpy as np
        except ImportError as exc:
            self.skipTest(f"deps missing: {exc}")
        if ctranslate2.get_cuda_device_count() < 1:
            self.skipTest("no CUDA device detected")
        m = WhisperModel("tiny", device="cuda", compute_type="float16")
        audio = (np.random.randn(16000) * 100).astype(np.float32) / 32768
        try:
            segs, _ = m.transcribe(audio, language="es", beam_size=1)
            list(segs)  # force generator
        except RuntimeError as exc:
            # The Q.0 bug: "cublas64_12.dll not found" or similar
            # runtime DLL missing. Fail explicitly with the
            # actionable hint.
            self.fail(
                f"GPU inference failed despite CUDA device present.\n"
                f"  Error: {exc}\n"
                f"  Fix: pip install nvidia-cublas-cu12 nvidia-cudnn-cu12\n"
                f"        python scripts/setup_cuda_runtime.py\n"
                f"  See: docs/architecture/sprint_prompts/sprint_hotfix_2026_05_17_q0.md"
            )


if __name__ == "__main__":
    unittest.main()
