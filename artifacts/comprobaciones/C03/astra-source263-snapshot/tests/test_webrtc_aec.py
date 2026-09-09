from __future__ import annotations

import hashlib
from pathlib import Path
import sys
import threading
from types import SimpleNamespace
import weakref

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import baxy_mind.webrtc_aec as aec


def _native(monkeypatch):
    handles, calls = [], []

    class Native:
        bad = None

        def __init__(self, rate, channels, delay):
            assert (rate, channels, delay) == (16000, 1, 0)
            self.linear = np.zeros(64, np.float32)
            self.final = np.zeros(128, np.float32)
            handles.append(weakref.ref(self))

        def process(self, near, far):
            calls.append((near.copy(), far.copy()))
            assert near.shape == far.shape == (160,)
            assert near.flags.c_contiguous and far.flags.c_contiguous
            linear, final = np.r_[self.linear, near], np.r_[self.final, near]
            self.last = linear[:160].copy()
            self.linear, self.final = linear[160:], final[160:]
            if self.bad == "final":
                return np.full(160, np.nan, np.float32)
            return final[:160].copy()

        def last_linear_frame(self):
            if self.bad == "linear":
                return np.full(160, 1.01, np.float32)
            if self.bad == "shape":
                return np.zeros(159, np.float32)
            return self.last

    monkeypatch.setattr(aec, "_native_runtime", lambda: Native)
    return Native, handles, calls


def test_bridge_preserves_every_sample_and_aligns_both_views_with_raw(monkeypatch):
    _, _, calls = _native(monkeypatch)
    rng = np.random.default_rng(257)
    signal = rng.uniform(-.1, .1, 50 * 512).astype(np.float32)
    far = rng.uniform(-2000, 2000, signal.size).astype(np.float32)
    history = np.r_[np.zeros(4000, np.float32), far]
    engine = aec.EchoCanceller()
    outputs = [engine.process(signal[i:i+512], history[i:i+4512]) for i in range(0, signal.size, 512)]
    expected = np.r_[np.zeros(256, np.float32), signal[:-256]]
    for name in ("recognition", "confirmation"):
        np.testing.assert_array_equal(np.concatenate([getattr(frame, name) for frame in outputs]), expected)
    np.testing.assert_array_equal(np.concatenate([frame.microphone for frame in outputs]), expected * 32768)
    delayed_history = np.r_[np.zeros(256, np.float32), history[:-256]]
    for index, frame in enumerate(outputs):
        np.testing.assert_array_equal(frame.reference, delayed_history[index*512:index*512+4512])
    np.testing.assert_array_equal(np.concatenate([near for near, _ in calls]), signal)
    np.testing.assert_array_equal(np.concatenate([ref for _, ref in calls]), far / 32768)
    engine.close()


def test_reference_history_and_input_arrays_are_not_mutated(monkeypatch):
    _native(monkeypatch)
    engine = aec.EchoCanceller()
    mic = np.linspace(-.25, .25, 512, dtype=np.float32)
    history = np.arange(4512, dtype=np.float32)
    first = engine.process(mic, history)
    second = engine.process(mic / 2, history + 512)
    np.testing.assert_array_equal(first.reference, np.r_[np.zeros(256), history[:-256]])
    np.testing.assert_array_equal(second.reference, history + 256)
    np.testing.assert_array_equal(first.microphone, np.r_[np.zeros(256), mic[:256]] * 32768)
    np.testing.assert_array_equal(second.microphone, np.r_[mic[-256:], mic[:256] / 2] * 32768)
    np.testing.assert_array_equal(history, np.arange(4512))
    engine.close()


def test_sessions_own_native_state_and_close_releases_it(monkeypatch):
    _, handles, _ = _native(monkeypatch)
    first, second = aec.EchoCanceller(), aec.EchoCanceller()
    first.process(np.full(512, .1), np.zeros(4512))
    np.testing.assert_array_equal(second.process(np.zeros(512), np.zeros(4512)).recognition, np.zeros(512))
    first.close()
    first.close()
    assert handles[0]() is None and handles[1]() is not None
    with pytest.raises(RuntimeError, match="closed"):
        first.process(np.zeros(512), np.zeros(4512))
    second.close()
    assert handles[1]() is None


@pytest.mark.parametrize("bad", ["short_mic", "short_reference", "nan_mic", "inf_reference"])
def test_invalid_audio_never_enters_native_code(monkeypatch, bad):
    _, _, calls = _native(monkeypatch)
    engine = aec.EchoCanceller()
    mic, history = np.zeros(512), np.zeros(4512)
    if bad == "short_mic":
        mic = mic[:-1]
    elif bad == "short_reference":
        history = history[:-1]
    elif bad == "nan_mic":
        mic[0] = np.nan
    else:
        history[0] = np.inf
    with pytest.raises(ValueError):
        engine.process(mic, history)
    assert not calls
    engine.close()


@pytest.mark.parametrize("bad", ["final", "linear", "shape"])
def test_invalid_output_from_either_native_view_is_rejected(monkeypatch, bad):
    native, _, _ = _native(monkeypatch)
    native.bad = bad
    engine = aec.EchoCanceller()
    with pytest.raises(RuntimeError, match="output_invalid"):
        engine.process(np.zeros(512), np.zeros(4512))
    engine.close()


def test_another_thread_cannot_process_or_release_native_state(monkeypatch):
    _, handles, calls = _native(monkeypatch)
    engine = aec.EchoCanceller()
    errors = []

    def other_thread():
        for action in (lambda: engine.process(np.zeros(512), np.zeros(4512)), engine.close):
            try:
                action()
            except RuntimeError as error:
                errors.append(str(error))

    worker = threading.Thread(target=other_thread)
    worker.start()
    worker.join(timeout=5)
    assert not worker.is_alive()
    assert errors == ["echo_canceller_wrong_thread"] * 2
    assert not calls and handles[0]() is not None
    engine.close()


@pytest.mark.parametrize("failure", [None, "version", "bytes", "path"])
def test_native_identity_is_verified_before_use(monkeypatch, tmp_path, failure):
    path = tmp_path / "native.pyd"
    path.write_bytes(b"fixture native")
    expected = hashlib.sha256(path.read_bytes()).hexdigest()
    monkeypatch.setattr(aec, "NATIVE_SHA256", expected)
    distribution = SimpleNamespace(
        version="0.2.0" if failure == "version" else aec.RUNTIME_VERSION,
        locate_file=lambda _: path,
    )
    monkeypatch.setattr(aec.importlib.metadata, "distribution", lambda _: distribution)
    if failure == "bytes":
        path.write_bytes(b"different native")
    module = SimpleNamespace(__file__=str(tmp_path / "other.pyd") if failure == "path" else str(path), EchoCanceller=object)
    monkeypatch.setattr(aec.importlib, "import_module", lambda _: module)
    assert aec.echo_canceller_available() is (failure is None)
    if failure:
        with pytest.raises(RuntimeError, match="mismatch"):
            aec._native_runtime()
    else:
        assert aec._native_runtime() is object
