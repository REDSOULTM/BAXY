from __future__ import annotations

from pathlib import Path
import sys
import threading

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import baxy_mind.speex_aec as aec_module
from baxy_mind.speex_aec import EchoCanceller, FRAME_SAMPLES, REFERENCE_SAMPLES


class _Function:
    def __init__(self, call):
        self.call = call

    def __call__(self, *args):
        return self.call(*args)


class _Library:
    def __init__(self, failure=None):
        self.failure = failure
        self.next_id = 1
        self.destroyed = []
        self.previous = {}
        self.native_calls = 0
        self.speex_echo_state_init = _Function(self.create_echo)
        self.speex_preprocess_state_init = _Function(self.create_preprocessor)
        self.speex_echo_state_destroy = _Function(
            lambda state: self.destroyed.append(("echo", state, threading.get_ident()))
        )
        self.speex_preprocess_state_destroy = _Function(
            lambda state: self.destroyed.append(("pre", state, threading.get_ident()))
        )
        self.speex_echo_ctl = _Function(lambda *_: -1 if failure == "config" else 0)
        self.speex_preprocess_ctl = _Function(lambda *_: 0)
        self.speex_echo_cancellation = _Function(self.cancel)
        self.speex_preprocess_run = _Function(self.preprocess)

    def create_echo(self, *_):
        if self.failure == "echo":
            return None
        state = self.next_id
        self.next_id += 1
        return state

    def create_preprocessor(self, *_):
        if self.failure == "pre":
            return None
        state = self.next_id
        self.next_id += 1
        self.previous[state] = np.zeros(FRAME_SAMPLES, dtype=np.int16)
        return state

    def cancel(self, _state, recorded, _played, clean):
        self.native_calls += 1
        np.ctypeslib.as_array(clean, shape=(FRAME_SAMPLES,))[:] = np.ctypeslib.as_array(
            recorded, shape=(FRAME_SAMPLES,)
        )

    def preprocess(self, state, clean):
        output = np.ctypeslib.as_array(clean, shape=(FRAME_SAMPLES,))
        previous = self.previous[state]
        self.previous[state] = output.copy()
        output[:] = previous
        return 1


def _install(monkeypatch, tmp_path, failure=None):
    path = tmp_path / "speexdsp.dll"
    path.write_bytes(b"fixture-only-library")
    library = _Library(failure)
    monkeypatch.setattr(aec_module, "resolve_echo_canceller_library", lambda: path)
    monkeypatch.setattr(aec_module.ctypes, "CDLL", lambda _path: library)
    return library


def test_missing_library_is_not_a_working_canceller(monkeypatch):
    monkeypatch.setattr(aec_module, "resolve_echo_canceller_library", lambda: None)
    with pytest.raises(RuntimeError, match="library_missing"):
        EchoCanceller()


@pytest.mark.parametrize("failure, released", [("echo", []), ("pre", ["echo"]), ("config", ["pre", "echo"])])
def test_partial_initialization_releases_owned_handles(monkeypatch, tmp_path, failure, released):
    library = _install(monkeypatch, tmp_path, failure)
    with pytest.raises(RuntimeError):
        EchoCanceller()
    assert [kind for kind, _, _ in library.destroyed] == released
    assert all(owner == threading.get_ident() for _, _, owner in library.destroyed)


def test_audio_and_echo_guard_share_the_same_frame_delay(monkeypatch, tmp_path):
    _install(monkeypatch, tmp_path)
    canceller = EchoCanceller()
    mic = np.full(FRAME_SAMPLES, .25, dtype=np.float32)
    history = np.full(REFERENCE_SAMPLES, 120, dtype=np.int16)
    first, first_mic, first_ref = canceller.process(mic, history)
    assert not first.any() and not first_mic.any() and not first_ref.any()
    mic[:] = .5
    history[:] = 240
    second, previous_mic, previous_ref = canceller.process(mic, history)
    assert np.all(second == .25)
    assert np.all(previous_mic == .25 * 32768)
    assert np.all(previous_ref == 120)
    assert np.all(mic == .5) and np.all(history == 240)
    canceller.close()


def test_sessions_have_separate_filter_history_and_close_once(monkeypatch, tmp_path):
    library = _install(monkeypatch, tmp_path)
    first, second = EchoCanceller(), EchoCanceller()
    mic = np.full(FRAME_SAMPLES, .25, dtype=np.float32)
    history = np.zeros(REFERENCE_SAMPLES, dtype=np.int16)
    first.process(mic, history)
    assert np.all(first.process(mic, history)[0] == .25)
    assert not second.process(mic, history)[0].any()
    first.close()
    first.close()
    with pytest.raises(RuntimeError, match="closed"):
        first.process(mic, history)
    second.close()
    assert len(library.destroyed) == 4
    assert len({state for _, state, _ in library.destroyed}) == 4


@pytest.mark.parametrize("bad", ["short_mic", "short_reference", "nan_mic", "inf_reference"])
def test_invalid_audio_never_enters_native_code(monkeypatch, tmp_path, bad):
    library = _install(monkeypatch, tmp_path)
    canceller = EchoCanceller()
    mic = np.zeros(FRAME_SAMPLES, dtype=np.float32)
    history = np.zeros(REFERENCE_SAMPLES, dtype=np.float32)
    if bad == "short_mic":
        mic = mic[:-1]
    elif bad == "short_reference":
        history = history[:-1]
    elif bad == "nan_mic":
        mic[0] = np.nan
    else:
        history[0] = np.inf
    with pytest.raises(ValueError):
        canceller.process(mic, history)
    assert library.native_calls == 0
    canceller.close()


def test_another_thread_cannot_use_or_release_session_state(monkeypatch, tmp_path):
    library = _install(monkeypatch, tmp_path)
    canceller = EchoCanceller()
    errors = []

    def other_thread():
        for action in (
            lambda: canceller.process(np.zeros(FRAME_SAMPLES), np.zeros(REFERENCE_SAMPLES)),
            canceller.close,
        ):
            try:
                action()
            except RuntimeError as error:
                errors.append(str(error))

    thread = threading.Thread(target=other_thread)
    thread.start()
    thread.join(timeout=5)
    assert not thread.is_alive()
    assert errors == ["echo_canceller_wrong_thread"] * 2
    assert not library.destroyed and library.native_calls == 0
    canceller.close()
