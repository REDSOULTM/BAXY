"""Ownership of native playback, cancellation and device failure."""
from pathlib import Path
import sys
import threading
from types import SimpleNamespace

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from baxy_mind import voice_output  # noqa: E402


def test_queue_selects_voice_sample_rate_and_identity_for_each_language(monkeypatch):
    completed = threading.Event()
    identities = []
    generated = []
    opened_rates = []
    loaded = []

    class Engine:
        def __init__(self, path):
            self.model_path = path
            self.identity = (path.name, f"hash-{path.stem}")
            self.sample_rate = 16000 if path.stem == "es" else 22050
            loaded.append(path.stem)

        def generate(self, text, *, cancelled):
            assert not cancelled()
            generated.append((self.model_path.stem, text, threading.get_ident()))
            return np.zeros(50, dtype=np.float32)

    class Stream:
        def __init__(self, **options):
            opened_rates.append(options["samplerate"])

        def __enter__(self):
            return self

        def write(self, _samples):
            pass

        def __exit__(self, *_):
            pass

    def on_state(speaking):
        if not speaking:
            identities.append((output.voice_name, output.voice_sha256))
            if len(identities) == 3:
                completed.set()

    monkeypatch.setitem(sys.modules, "sounddevice", SimpleNamespace(OutputStream=Stream))
    monkeypatch.setattr(voice_output, "PiperEngine", Engine)
    monkeypatch.setattr(voice_output, "resolve_neural_tts_model", lambda language="es": Path(f"{language}.onnx"))
    output = voice_output.NeuralSpeechOutput(on_state)
    texts = ["Son las 07:13.", "It is 07:14.", "Son las 07:15."]
    try:
        for text in texts:
            assert output.speak(text)
        assert completed.wait(5)
        assert identities == [("es", "hash-es"), ("en", "hash-en"), ("es", "hash-es")]
        assert opened_rates == [16000, 22050, 16000]
        assert loaded == ["es", "en"]
        assert [(language, text) for language, text, _ in generated] == list(zip(["es", "en", "es"], texts))
        assert len({owner for _, _, owner in generated}) == 1
        assert generated[0][2] != threading.get_ident()
    finally:
        assert output.stop(timeout=5)


@pytest.mark.parametrize("mode", ["complete", "cancel", "device_failure"])
def test_playback_keeps_one_worker_owner_through_close(monkeypatch, mode):
    waveform = np.arange(95, dtype=np.float32) / 100
    first_write = threading.Event()
    release_write = threading.Event()
    closed = threading.Event()
    speech_ended = threading.Event()
    calls = []
    chunks = []

    def record(name):
        calls.append((name, threading.get_ident()))

    class Stream:
        def __init__(self, **kwargs):
            assert kwargs["channels"] == 1
            assert kwargs["dtype"] == "float32"
            record("open")

        def __enter__(self):
            record("start")
            return self

        def write(self, samples):
            record("write")
            chunks.append(samples.copy())
            if len(chunks) == 1:
                first_write.set()
                assert release_write.wait(5)
                if mode == "device_failure":
                    raise OSError("device disappeared")

        def abort(self):
            record("abort")

        def __exit__(self, *_error):
            record("close")
            closed.set()

    monkeypatch.setitem(sys.modules, "sounddevice", SimpleNamespace(OutputStream=Stream))
    monkeypatch.setattr(voice_output, "resolve_neural_tts_model", lambda *_: Path("voice.onnx"))
    monkeypatch.setattr(voice_output, "PiperEngine", lambda path: SimpleNamespace(
        model_path=path, identity=(path.name, "voice-hash"),
        sample_rate=1000, generate=lambda _text, **_: waveform))
    output = voice_output.NeuralSpeechOutput(
        lambda speaking: speech_ended.set() if not speaking else None)
    try:
        assert output.speak("development playback")
        assert first_write.wait(5)
        if mode == "cancel":
            output.cancel()
            assert not closed.is_set(), "caller cannot close an in-flight native write"
        release_write.set()
        assert speech_ended.wait(5)
        assert closed.is_set()
        assert output.stop(timeout=5)
        assert len({owner for _, owner in calls}) == 1
        assert calls[0][1] != threading.get_ident()
        assert calls[-1][0] == "close"
        if mode == "complete":
            np.testing.assert_array_equal(np.concatenate(chunks), waveform)
            assert output.last_error is None
        elif mode == "cancel":
            assert len(chunks) == 1
            assert [name for name, _ in calls][-2:] == ["abort", "close"]
            assert output.last_error is None
        else:
            assert output.last_error == "tts_failed:OSError"
    finally:
        release_write.set()
        output.stop(timeout=5)
