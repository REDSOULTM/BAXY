from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import sys
import threading
import types
import weakref

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import baxy_mind.dtln_aec as aec


def _install(monkeypatch, tmp_path, failure=None):
    hashes = {}
    for name in aec.MODEL_HASHES:
        payload = name.encode()
        (tmp_path / name).write_bytes(payload)
        hashes[name] = hashlib.sha256(payload).hexdigest()
    (tmp_path / "LICENSE").write_bytes(b"fixture license")
    monkeypatch.setattr(aec, "MODEL_HASHES", hashes)
    monkeypatch.setattr(aec, "LICENSE_SHA256", hashlib.sha256(b"fixture license").hexdigest())
    monkeypatch.setattr(aec, "resolve_echo_canceller_directory", lambda: tmp_path)
    handles = []
    calls = []

    class Model:
        def __init__(self, model_path, num_threads):
            assert num_threads == 1
            self.width = 257 if model_path.endswith("_1.tflite") else 512
            self.tensors = {}
            handles.append(weakref.ref(self))

        def allocate_tensors(self):
            if failure == "allocate" and self.width == 512:
                raise RuntimeError("allocate failed")

        def get_input_details(self):
            width = 123 if failure == "schema" else self.width
            return [
                {"index": i, "shape": shape, "dtype": np.float32}
                for i, shape in enumerate(((1, 1, width), (1, 2, 512, 2), (1, 1, width)))
            ]

        def get_output_details(self):
            return self.get_input_details()[:2]

        def set_tensor(self, index, value):
            self.tensors[index] = value.copy()

        def invoke(self):
            calls.append(self.width)

        def get_tensor(self, index):
            if index == 1:
                return self.tensors[1] + 1
            value = 1 if self.width == 257 else 0
            return np.full((1, 1, self.width), value, np.float32)

    module = types.ModuleType("ai_edge_litert.interpreter")
    module.Interpreter = Model
    monkeypatch.setitem(sys.modules, "ai_edge_litert.interpreter", module)
    return handles, calls


def test_missing_models_are_not_a_working_canceller(monkeypatch):
    monkeypatch.setattr(aec, "resolve_echo_canceller_directory", lambda: None)
    with pytest.raises(RuntimeError, match="models_missing"):
        aec.EchoCanceller()


@pytest.mark.parametrize("name", [*aec.MODEL_HASHES, "LICENSE"])
def test_unattested_assets_never_enter_native_code(monkeypatch, tmp_path, name):
    handles, _ = _install(monkeypatch, tmp_path)
    (tmp_path / name).write_bytes(b"wrong asset")
    with pytest.raises(RuntimeError, match="hash_mismatch"):
        aec.EchoCanceller()
    assert not handles


@pytest.mark.parametrize("failure", ["allocate", "schema"])
def test_failed_initialization_releases_models(monkeypatch, tmp_path, failure):
    handles, _ = _install(monkeypatch, tmp_path, failure)
    with pytest.raises(RuntimeError):
        aec.EchoCanceller()
    assert handles and all(handle() is None for handle in handles)


def test_guard_pair_tracks_the_384_sample_model_delay(monkeypatch, tmp_path):
    _install(monkeypatch, tmp_path)
    canceller = aec.EchoCanceller()
    mic = np.linspace(-.25, .25, 512, dtype=np.float32)
    reference = np.arange(4512, dtype=np.float32)
    _, raw, paired = canceller.process(mic, reference)
    np.testing.assert_array_equal(raw, np.r_[np.zeros(384), mic[:128]] * 32768)
    np.testing.assert_array_equal(paired, np.r_[np.zeros(384), reference[:-384]])
    next_mic = mic / 2
    next_reference = reference + 512
    _, raw, paired = canceller.process(next_mic, next_reference)
    np.testing.assert_array_equal(raw, np.r_[mic[-384:], next_mic[:128]] * 32768)
    np.testing.assert_array_equal(paired, reference + 128)
    np.testing.assert_array_equal(reference, np.arange(4512))
    canceller.close()


def test_sessions_have_separate_recurrent_states_and_release_once(monkeypatch, tmp_path):
    handles, _ = _install(monkeypatch, tmp_path)
    first, second = aec.EchoCanceller(), aec.EchoCanceller()
    assert all(np.all(state == 3) for state in first._states + second._states)
    first.process(np.zeros(512), np.zeros(4512))
    assert all(np.all(state == 7) for state in first._states)
    assert all(np.all(state == 3) for state in second._states)
    first.close()
    first.close()
    with pytest.raises(RuntimeError, match="closed"):
        first.process(np.zeros(512), np.zeros(4512))
    assert all(handle() is None for handle in handles[:2])
    assert all(handle() is not None for handle in handles[2:])
    second.close()
    assert all(handle() is None for handle in handles)


@pytest.mark.parametrize("bad", ["short_mic", "short_reference", "nan_mic", "inf_reference"])
def test_invalid_audio_never_enters_native_code(monkeypatch, tmp_path, bad):
    _, calls = _install(monkeypatch, tmp_path)
    canceller = aec.EchoCanceller()
    calls.clear()
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
        canceller.process(mic, history)
    assert not calls
    canceller.close()


@pytest.mark.parametrize("value", [np.nan, np.inf, 1.01])
def test_invalid_native_output_is_not_emitted(monkeypatch, tmp_path, value):
    _install(monkeypatch, tmp_path)
    canceller = aec.EchoCanceller()
    monkeypatch.setattr(canceller, "_hop", lambda *_: np.full(128, value, np.float32))
    with pytest.raises(RuntimeError, match="output_invalid"):
        canceller.process(np.zeros(512), np.zeros(4512))
    canceller.close()


def test_other_thread_cannot_use_or_release_models(monkeypatch, tmp_path):
    handles, calls = _install(monkeypatch, tmp_path)
    canceller = aec.EchoCanceller()
    calls.clear()
    errors = []

    def other_thread():
        for action in (lambda: canceller.process(np.zeros(512), np.zeros(4512)), canceller.close):
            try:
                action()
            except RuntimeError as error:
                errors.append(str(error))

    thread = threading.Thread(target=other_thread)
    thread.start()
    thread.join(timeout=5)
    assert not thread.is_alive()
    assert errors == ["echo_canceller_wrong_thread"] * 2
    assert not calls and all(handle() is not None for handle in handles)
    canceller.close()


@pytest.fixture
def installer(monkeypatch, tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    _install(monkeypatch, source)
    script = Path(__file__).resolve().parents[1] / "scripts/install_dtln_aec.py"
    spec = importlib.util.spec_from_file_location("install_dtln_fixture", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, source, tmp_path / "destination"


def test_installation_and_reuse_preserve_pinned_bytes(installer):
    module, source, destination = installer
    assert module.install(destination, source)["reused"] is False
    assert module.install(destination, source)["reused"] is True
    for name in [*aec.MODEL_HASHES, "LICENSE"]:
        assert (destination / name).read_bytes() == (source / name).read_bytes()


def test_failed_installation_does_not_publish_partial_bundle(installer):
    module, source, destination = installer
    (source / "LICENSE").write_bytes(b"invalid")
    with pytest.raises(ValueError, match="hash_mismatch"):
        module.install(destination, source)
    assert not destination.exists()


def test_installer_does_not_overwrite_different_existing_assets(installer):
    module, source, destination = installer
    module.install(destination, source)
    changed = destination / next(iter(aec.MODEL_HASHES))
    changed.write_bytes(b"existing content")
    with pytest.raises(ValueError, match="hash_mismatch"):
        module.install(destination, source)
    assert changed.read_bytes() == b"existing content"
