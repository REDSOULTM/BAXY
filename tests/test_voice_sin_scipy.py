"""uso-116 (N26): what the first answer's voice waits for at start. The voice's load imported scipy.signal for one
resampling: 1.1 s alone, 3.4 s of the 4.2 s the first answer waited on the PC beside the rest of the start. And numpy's
OpenBLAS was started with one thread (and its committed buffer) per core, before voice.py limited them."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from baxy_mind import resample, voice_echo

try:
    from scipy import signal
except ImportError:  # not in the runtime: pylock.test-win-x64.toml has it
    signal = None
needs_scipy = pytest.mark.skipif(signal is None, reason="scipy is only in the test lock")

SRC = str(Path(__file__).resolve().parent.parent / "src")


def _run(code: str) -> str:
    env = {**os.environ, "PYTHONPATH": SRC}
    for name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
        env.pop(name, None)
    done = subprocess.run([sys.executable, "-X", "utf8", "-c", code], capture_output=True, text=True, env=env,
                          timeout=120)
    assert done.returncode == 0, done.stderr[-2000:]
    return done.stdout


def test_the_voice_and_the_echo_stage_resample_without_scipy():
    used = _run("""
import sys, json
import numpy as np
from baxy_mind import voice, voice_echo, voice_output
voice_output.shifted(np.zeros(4410, np.float32), voice_output.Fraction(35, 34))
voice_echo.Resampler(48000, 16000)(np.zeros(480, np.float32))
print(json.dumps(sorted(name for name in sys.modules if name.split(".")[0] == "scipy")[:5]))
""")
    assert json.loads(used) == []


def test_numpy_starts_with_one_blas_thread_whichever_module_of_the_mind_comes_first():
    # OpenBLAS reads its variable when numpy loads: voice.py set it after importing voice_echo, which imports numpy.
    for module in ("baxy_mind.voice", "baxy_mind.voice_output", "baxy_mind.__main__"):
        seen = _run(f"""
import os, sys
class Spy:
    def find_spec(self, name, path=None, target=None):
        if name == "numpy" and not hasattr(Spy, "seen"):
            Spy.seen = os.environ.get("OPENBLAS_NUM_THREADS")
            print(Spy.seen)
        return None
sys.meta_path.insert(0, Spy())
import {module}
""")
        assert seen.split()[:1] == ["1"], module


@needs_scipy
@pytest.mark.parametrize("up,down", [(34, 35), (35, 34), (1, 3), (3, 1), (147, 160), (100, 99)])
@pytest.mark.parametrize("size", [1, 7, 4410, 66150])
def test_resample_poly_is_scipys(up, down, size):
    audio = np.random.default_rng(size + up).normal(0.0, 0.2, size).astype(np.float32)
    ours = resample.resample_poly(audio, up, down)
    theirs = signal.resample_poly(audio, up, down)
    assert ours.dtype == np.float32 and ours.shape == theirs.shape
    assert np.max(np.abs(ours - theirs)) < 2e-5


@needs_scipy
@pytest.mark.parametrize("up,down", [(1, 3), (2, 3), (147, 160), (5, 1)])
@pytest.mark.parametrize("size", [1, 480, 3000])
def test_upfirdn_is_scipys(up, down, size):
    audio = np.random.default_rng(size).normal(0.0, 0.2, size).astype(np.float32)
    width = max(up, down)
    taps = (signal.firwin(32 * width + 1, 0.9 / width) * up).astype(np.float32)
    ours = resample.Polyphase(taps, up, down)(audio)
    theirs = signal.upfirdn(taps, audio, up, down)
    assert ours.shape == theirs.shape
    assert np.max(np.abs(ours - theirs)) < 2e-5


@needs_scipy
def test_lowpass_is_firwins():
    for taps, cutoff in ((1401, 1 / 35), (97, 0.3)):
        assert np.allclose(resample.lowpass(taps, cutoff, np.hamming(taps)), signal.firwin(taps, cutoff), atol=1e-12)
        assert np.allclose(resample.lowpass(taps, cutoff, np.kaiser(taps, 5.0)),
                           signal.firwin(taps, cutoff, window=("kaiser", 5.0)), atol=1e-12)


def test_the_echo_stages_stream_has_no_seams():
    # Chunk after chunk gives what the whole does, the same as before the change (Resampler's contract).
    rate_in, rate_out = 48000, 16000
    audio = np.sin(2 * np.pi * 440 * np.arange(rate_in) / rate_in).astype(np.float32)
    stream = voice_echo.Resampler(rate_in, rate_out)
    pieces = [stream(audio[at:at + 480]) for at in range(0, len(audio), 480)]
    whole = voice_echo.Resampler(rate_in, rate_out)(audio)
    joined = np.concatenate(pieces)
    size = min(len(joined), len(whole))
    assert size > rate_out - 200
    assert np.max(np.abs(joined[:size] - whole[:size])) < 1e-4
