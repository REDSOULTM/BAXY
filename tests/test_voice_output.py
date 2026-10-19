"""BAXY's spoken voice while it loads (src/baxy_mind/voice_output.py; FT/proveedores goal, E001): an answer given
before Supertonic has loaded waits and sounds once it has, and a voice with no model files refuses at once."""
import threading
import time
from pathlib import Path

import pytest

from baxy_mind import voice_output
from baxy_mind.voice_output import Speech


def _model_dir(tmp_path: Path) -> Path:
    for name in voice_output._MODEL_FILES:
        (tmp_path / name).write_bytes(b"")
    return tmp_path


def test_an_answer_given_while_the_voice_loads_sounds_once_it_has(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BAXY_RENEW_TTS_DIR", str(_model_dir(tmp_path)))
    loaded = threading.Event()
    played: list[str] = []

    def slow_start(self: Speech) -> None:
        loaded.wait(5)

    monkeypatch.setattr(Speech, "_start", slow_start)
    monkeypatch.setattr(Speech, "_sentences", lambda self, text: iter([text]))
    monkeypatch.setattr(Speech, "_play", lambda self, audio, generation, queued: played.extend(audio))
    speech = Speech(lambda speaking: None, lambda queued, sounded: None)

    assert not speech.ready
    assert speech.speak("Hola, ya estoy aquí.")
    time.sleep(0.2)
    assert played == []
    loaded.set()
    deadline = time.monotonic() + 5
    while not played and time.monotonic() < deadline:
        time.sleep(0.05)
    assert played == ["Hola, ya estoy aquí."]
    assert speech.ready


def test_a_voice_with_no_model_files_refuses_at_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BAXY_RENEW_TTS_DIR", str(tmp_path))
    speech = Speech(lambda speaking: None, lambda queued, sounded: None)
    assert speech.failure
    assert not speech.speak("Hola.")
    assert not speech.ready
