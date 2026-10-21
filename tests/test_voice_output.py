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


def _loaded_voice(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, played: list[str],
                  notice_gate: threading.Event | None = None) -> Speech:
    """A loaded voice whose synthesis is the text itself; a notice's waits for notice_gate."""
    monkeypatch.setenv("BAXY_RENEW_TTS_DIR", str(_model_dir(tmp_path)))
    monkeypatch.setattr(Speech, "_start", lambda self: None)

    def sentences(self: Speech, text: str):
        if notice_gate is not None and text == "Un momento.":
            notice_gate.wait(5)
        yield text

    monkeypatch.setattr(Speech, "_sentences", sentences)
    monkeypatch.setattr(Speech, "_play", lambda self, audio, generation, queued: played.extend(audio))
    speech = Speech(lambda speaking: None, lambda queued, sounded: None)
    deadline = time.monotonic() + 5
    while not speech.ready and time.monotonic() < deadline:
        time.sleep(0.01)
    assert speech.ready
    return speech


def _wait_for(played: list[str], count: int) -> None:
    deadline = time.monotonic() + 5
    while len(played) < count and time.monotonic() < deadline:
        time.sleep(0.02)
    time.sleep(0.1)  # nothing else follows


def test_an_answer_given_before_the_notice_sounds_drops_the_notice(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Owner, 2026-10-20: «Un momento.» cut in on what BAXY was about to say and held the answer back."""
    played: list[str] = []
    gate = threading.Event()
    speech = _loaded_voice(tmp_path, monkeypatch, played, gate)
    assert speech.speak("Un momento.", notice=True)
    assert speech.speak("Tienes 36 juegos en Steam.")
    gate.set()
    _wait_for(played, 1)
    assert played == ["Tienes 36 juegos en Steam."]


def test_a_notice_with_no_answer_yet_is_said_and_the_answer_follows(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    played: list[str] = []
    speech = _loaded_voice(tmp_path, monkeypatch, played)
    assert speech.speak("Un momento.", notice=True)
    _wait_for(played, 1)
    assert speech.speak("Listo, abrí Steam.")
    _wait_for(played, 2)
    assert played == ["Un momento.", "Listo, abrí Steam."]


def test_a_loaded_voice_starts_an_answers_synthesis_when_it_is_given(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The answer is synthesized while what is ahead of it sounds, not after."""
    played: list[str] = []
    speech = _loaded_voice(tmp_path, monkeypatch, played)
    started: list[str] = []
    monkeypatch.setattr(Speech, "_sentences", lambda self, text: started.append(text) or iter([text]))
    assert speech.speak("Hola.")
    assert started == ["Hola."]
    _wait_for(played, 1)
    assert played == ["Hola."]


def test_a_voice_with_no_model_files_refuses_at_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BAXY_RENEW_TTS_DIR", str(tmp_path))
    speech = Speech(lambda speaking: None, lambda queued, sounded: None)
    assert speech.failure
    assert not speech.speak("Hola.")
    assert not speech.ready


def test_the_notice_sounds_from_its_audio_kept_at_load_and_never_holds_the_synthesis(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Owner, 2026-10-20: an answer waited 3.6 s behind «Un momento», which was synthesized like any sentence."""
    played: list[object] = []
    speech = _loaded_voice(tmp_path, monkeypatch, played)  # type: ignore[arg-type]
    started: list[str] = []
    monkeypatch.setattr(Speech, "_sentences", lambda self, text: started.append(text) or iter([text]))
    speech._notice_audio = "audio del aviso"  # type: ignore[assignment]
    assert speech.speak("Un momento.", notice=True)
    _wait_for(played, 1)  # type: ignore[arg-type]
    assert speech.speak("Listo, abrí Steam.")
    _wait_for(played, 2)  # type: ignore[arg-type]
    assert started == ["Listo, abrí Steam."]
    assert played == ["audio del aviso", "Listo, abrí Steam."]


def test_what_was_cancelled_is_not_synthesized_and_does_not_hold_the_next_answer(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Owner talking over BAXY, 2026-10-20: the cancelled answer's sentences still went through the one synthesis
    thread and the next answer waited 2.8-5.7 s behind them."""
    monkeypatch.setenv("BAXY_RENEW_TTS_DIR", str(_model_dir(tmp_path)))
    monkeypatch.setattr(Speech, "_start", lambda self: None)
    synthesized: list[str] = []
    gate = threading.Event()

    def synthesize(self: Speech, text: str, pause: bool = True) -> str:
        if text.startswith("Uno"):
            gate.wait(5)
        synthesized.append(text)
        return text

    monkeypatch.setattr(Speech, "_synthesize", synthesize)
    monkeypatch.setattr(voice_output, "spoken", lambda text: text)
    played: list[str] = []
    monkeypatch.setattr(Speech, "_play", lambda self, audio, generation, queued: played.extend(audio))
    speech = Speech(lambda speaking: None, lambda queued, sounded: None)
    deadline = time.monotonic() + 5
    while not speech.ready and time.monotonic() < deadline:
        time.sleep(0.01)
    long_answer = "Uno, una frase bastante larga para que no se junte con las demás. " \
                  "Dos, otra frase igual de larga que nadie va a escuchar nunca. Tres, la última frase larga del todo."
    assert speech.speak(long_answer)
    speech.cancel()
    gate.set()
    assert speech.speak("Listo, abrí Steam.")
    _wait_for(played, 1)
    assert played == ["Listo, abrí Steam."]
    assert not any(text.startswith(("Dos", "Tres")) for text in synthesized)
