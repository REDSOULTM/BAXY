"""Piper request integrity, child ownership and explicit per-language assets."""
import json
from types import SimpleNamespace

import numpy as np
import pytest

from baxy_mind import piper_tts
from baxy_mind.semantic.request import spoken_language


@pytest.fixture
def engine(tmp_path, monkeypatch):
    model = tmp_path / "voice.onnx"
    model.write_bytes(b"model-fixture")
    model.with_suffix(".onnx.json").write_text(
        json.dumps({"audio": {"sample_rate": 22050}}), encoding="utf-8"
    )
    monkeypatch.setattr(piper_tts, "resolve_piper_executable", lambda: tmp_path / "piper.exe")
    return piper_tts.PiperEngine(model)


def test_piper_transports_unicode_and_newlines_as_one_request(engine, monkeypatch):
    observed = {}
    audio = np.array([-32768, 0, 32767], dtype="<i2").tobytes()

    def launch(command, **options):
        observed.update(command=command, options=options)

        def communicate(input=None, **_):
            observed["input"] = input
            return audio, b""

        return SimpleNamespace(communicate=communicate, returncode=0, poll=lambda: 0)

    monkeypatch.setattr(piper_tts.subprocess, "Popen", launch)
    text = '¡Hola!\nYou asked me to say "español".'
    pcm = engine.generate(text)
    assert json.loads(observed["input"]) == {"text": text}
    assert observed["input"].count(b"\n") == 1
    assert "shell" not in observed["options"]
    assert "--output_raw" in observed["command"]
    assert "--json-input" in observed["command"]
    assert observed["options"]["creationflags"] == getattr(piper_tts.subprocess, "CREATE_NO_WINDOW", 0)
    assert pcm.dtype == np.float32
    assert pcm.tolist() == [-1.0, 0.0, 32767 / 32768]


def test_cancel_during_synthesis_kills_and_reaps_owned_child(engine, monkeypatch):
    calls = []
    cancelled = False

    class Child:
        returncode = None

        def communicate(self, input=None, **_):
            nonlocal cancelled
            calls.append("communicate")
            if self.returncode is None:
                cancelled = True
                raise piper_tts.subprocess.TimeoutExpired("piper", 0.1)
            return b"", b""

        def poll(self):
            return self.returncode

        def kill(self):
            calls.append("kill")
            self.returncode = -9

    monkeypatch.setattr(piper_tts.subprocess, "Popen", lambda *_, **__: Child())
    with pytest.raises(InterruptedError):
        engine.generate("Mensaje cancelado", cancelled=lambda: cancelled)
    assert calls == ["communicate", "kill", "communicate"]


def test_synthesis_deadline_reaps_the_child(engine, monkeypatch):
    calls = []
    clock = iter([0.0, 30.1])
    child = SimpleNamespace(
        poll=lambda: None, kill=lambda: calls.append("kill"),
        communicate=lambda **_: calls.append("reap"),
    )
    monkeypatch.setattr(piper_tts.subprocess, "Popen", lambda *_, **__: child)
    monkeypatch.setattr(piper_tts.time, "monotonic", lambda: next(clock))
    with pytest.raises(TimeoutError, match="tts_synthesis_deadline"):
        engine.generate("Mensaje")
    assert calls == ["kill", "reap"]


@pytest.mark.parametrize("code,audio,error", [(7, b"", RuntimeError), (0, b"", ValueError), (0, b"x", ValueError)])
def test_failed_or_invalid_pcm_is_not_reported_as_audio(engine, monkeypatch, code, audio, error):
    child = SimpleNamespace(communicate=lambda **_: (audio, b"diagnostic"), returncode=code, poll=lambda: code)
    monkeypatch.setattr(piper_tts.subprocess, "Popen", lambda *_, **__: child)
    with pytest.raises(error):
        engine.generate("Mensaje")


def test_missing_english_voice_does_not_use_the_spanish_voice(tmp_path, monkeypatch):
    spanish = tmp_path / "spanish.onnx"
    spanish.write_bytes(b"es")
    monkeypatch.setenv("BAXY_NEURAL_TTS_MODEL", str(spanish))
    monkeypatch.delenv("BAXY_NEURAL_TTS_ENGLISH_MODEL", raising=False)
    monkeypatch.setattr(piper_tts, "resolve_asset", lambda _: SimpleNamespace(path=None, candidates=()))
    assert piper_tts.resolve_neural_tts_model() == spanish
    assert piper_tts.resolve_neural_tts_model("en") is None


@pytest.mark.parametrize("text,expected", [
    ("It is 07:14.", "en"),
    ("The file read failed because the content is invalid UTF-8.", "en"),
    ("I couldn't read the file because it wasn't found in the sandbox.", "en"),
    ("¡Hola! Aquí BAXY. ¿En qué te puedo ayudar hoy?", "es"),
    ("Son las 07:15.", "es"),
    ("You asked me to answer in Spanish.", "en"),
    ("Me pediste que responda en inglés.", "es"),
    ("Abrí Steam y PlayStation.", "es"),
])
def test_voice_follows_composed_text_without_executing_quoted_instructions(text, expected):
    assert spoken_language(text) == expected
