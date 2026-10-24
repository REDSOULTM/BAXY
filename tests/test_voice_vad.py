"""Silero VAD in the voice (src/baxy_mind/voice.py, Vad and voiced): every 512 samples heard are one window, given with
the 64 before as sherpa-onnx asks; a window's speech counts for the block in which it was heard whole; a block is voice
only when it is loud and heard as speech, so steady noise above VOICE_RMS never keeps a request open."""
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from baxy_mind import voice
from baxy_mind.voice import BLOCK, RATE, VAD_STEP, Vad, voiced


class _Model:
    """sherpa-onnx's VadModel as Vad uses it: keeps the windows it was given; speech in every other one."""

    def __init__(self) -> None:
        self.windows: list[np.ndarray] = []

    def window_size(self) -> int:
        return VAD_STEP + 64

    def reset(self) -> None:
        self.windows.clear()

    def is_speech(self, window: np.ndarray) -> bool:
        self.windows.append(window.copy())
        return len(self.windows) % 2 == 1


def _fake_sherpa(model: _Model) -> SimpleNamespace:
    return SimpleNamespace(VadModel=SimpleNamespace(create=lambda _config: model),
                           VadModelConfig=lambda **_kw: None, SileroVadModelConfig=lambda **_kw: None)


def test_every_window_is_heard_once_with_its_context_and_marks_the_block_where_it_ends() -> None:
    model = _Model()
    vad = Vad(_fake_sherpa(model))
    audio = np.arange(5 * BLOCK, dtype=np.float32)
    marks = np.concatenate([vad.marks(block) for block in audio.reshape(-1, BLOCK)])
    windows = len(audio) // VAD_STEP
    assert len(model.windows) == windows
    heard = np.concatenate([np.zeros(64, np.float32), audio])
    for k, window in enumerate(model.windows):
        assert np.array_equal(window, heard[k * VAD_STEP:k * VAD_STEP + VAD_STEP + 64])
    assert list(np.flatnonzero(marks)) == [k * VAD_STEP + VAD_STEP - 1 for k in range(0, windows, 2)]
    vad.reset()
    assert not model.windows and np.array_equal(vad.marks(np.ones(VAD_STEP, np.float32)), np.eye(VAD_STEP)[-1] > 0)


def test_a_block_is_voice_only_when_it_is_loud_and_heard_as_speech() -> None:
    loud, quiet = np.full(BLOCK, 0.05, np.float32), np.full(BLOCK, 0.002, np.float32)
    speech, none = np.eye(BLOCK)[BLOCK // 2] > 0, np.zeros(BLOCK, bool)
    audio = np.concatenate([loud, loud, quiet, quiet])
    assert list(voiced(audio, np.concatenate([speech, none, speech, none]))) == [True, False, False, False]


def test_silero_never_takes_steady_noise_or_silence_for_speech() -> None:
    sherpa_onnx = pytest.importorskip("sherpa_onnx")
    pytest.importorskip("silero_vad")
    spectrum = np.fft.rfft(np.random.default_rng(3).standard_normal(4 * RATE))
    pink = np.fft.irfft(spectrum / np.sqrt(np.maximum(np.arange(len(spectrum)), 1)), 4 * RATE)
    noise = (pink / np.std(pink) * 0.03).astype(np.float32)  # 2.5 times VOICE_RMS: loud in every block
    assert (np.sqrt((noise.reshape(-1, BLOCK) ** 2).mean(axis=1)) >= voice.VOICE_RMS).all()
    vad = Vad(sherpa_onnx)
    for audio in (noise, np.zeros(2 * RATE, np.float32)):
        vad.reset()
        marks = np.concatenate([vad.marks(block) for block in audio.reshape(-1, BLOCK)])
        assert not voiced(audio, marks).any()


def test_the_silero_model_is_found_without_running_its_package() -> None:
    # Al máximo (notebook, 2026-10-24): importlib.resources.files("silero_vad") imported the package, and the package
    # imports torch: the mind grew by 149 MiB (USS) for the path of a file. The voice runs the .onnx with sherpa-onnx.
    pytest.importorskip("silero_vad")
    code = ("import sys\n"
            "from types import SimpleNamespace as N\n"
            "from baxy_mind.voice import Vad\n"
            "seen = {}\n"
            "model = N(window_size=lambda: 576, reset=lambda: None)\n"
            "Vad(N(VadModel=N(create=lambda config: model), VadModelConfig=lambda **kw: None,\n"
            "      SileroVadModelConfig=lambda **kw: seen.update(kw)))\n"
            "import os\n"
            "print(os.path.isfile(seen['model']), 'silero_vad' in sys.modules, 'torch' in sys.modules)\n")
    env = dict(os.environ, PYTHONPATH=str(Path(voice.__file__).resolve().parents[1]))
    out = subprocess.run([sys.executable, "-X", "utf8", "-c", code], capture_output=True, text=True, env=env, timeout=120)
    assert out.returncode == 0, out.stderr
    assert out.stdout.split() == ["True", "False", "False"]
