"""BAXY's spoken voice at its edges (src/baxy_mind/voice_output.py): an answer the full queue refuses leaves nothing
behind, and closing the voice never closes the output while the speech thread writes to it."""
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from baxy_mind import voice_output
from baxy_mind.voice_output import Speech


def _model_dir(tmp_path: Path) -> Path:
    for name in voice_output._MODEL_FILES:
        (tmp_path / name).write_bytes(b"")
    return tmp_path


def test_an_answer_the_full_queue_refuses_is_neither_synthesized_nor_counted(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BAXY_RENEW_TTS_DIR", str(_model_dir(tmp_path)))
    monkeypatch.setattr(Speech, "_run", lambda self: self._ready.set())  # loaded, and nothing takes from the queue
    synthesized: list[str] = []
    monkeypatch.setattr(Speech, "_sentences", lambda self, text: synthesized.append(text) or iter([text]))
    speech = Speech(lambda speaking: None, lambda queued, sounded, notice: None)
    while not speech._queue.full():
        speech.prepare()
    assert not speech.speak("x")
    assert synthesized == []
    assert speech._answers == 0


class _Output:
    """An output that tells whether it was closed or aborted while a write was under way."""

    latency = 0.0

    def __init__(self) -> None:
        self.writing = False
        self.wrote = threading.Event()
        self.overlaps: list[str] = []
        self.closed = False

    def start(self) -> None:
        pass

    def write(self, _block) -> None:
        self.writing = True
        self.wrote.set()
        time.sleep(0.05)
        self.writing = False

    def abort(self) -> None:
        if self.writing:
            self.overlaps.append("abort")

    def close(self) -> None:
        if self.writing:
            self.overlaps.append("close")
        self.closed = True


def test_closing_the_voice_never_closes_the_output_while_it_is_written(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    output = _Output()
    monkeypatch.setitem(sys.modules, "sounddevice", SimpleNamespace(
        OutputStream=lambda **_kwargs: output, query_hostapis=lambda: []))
    monkeypatch.setenv("BAXY_RENEW_TTS_DIR", str(_model_dir(tmp_path)))
    monkeypatch.setattr(Speech, "_start", lambda self: None)
    monkeypatch.setattr(Speech, "_sentences", lambda self, text: iter([np.full(self.rate * 2, 0.1, np.float32)]))
    speech = Speech(lambda speaking: None, lambda queued, sounded, notice: None)
    deadline = time.monotonic() + 5
    while not speech.ready and time.monotonic() < deadline:
        time.sleep(0.01)
    assert speech.speak("Hola, soy BAXY.")
    assert output.wrote.wait(5)
    speech.close()
    assert output.overlaps == []
    assert output.closed


@pytest.mark.parametrize(("reply", "takes"), [
    ("Listo, Spotify está abierto. ¿Quieres que suba el volumen?", 2),  # a short reply: its first sentence sounds sooner
    ("Listo. Spotify está abierto y sonando.", 1),                      # a word or two first: one call (issue #30)
    ("Spotify está abierto y sonando.", 1),
    # a word or two first, then more sentences: the opener goes with the next one only, and the rest are their own
    ("Listo. Spotify está abierto y sonando. La canción es de Queen. Quedan dos minutos.", 3),
])
def test_a_first_sentence_of_more_than_a_few_words_is_synthesized_alone(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reply: str, takes: int) -> None:
    monkeypatch.setenv("BAXY_RENEW_TTS_DIR", str(_model_dir(tmp_path)))
    monkeypatch.setattr(Speech, "_run", lambda self: self._ready.set())
    synthesized: list[str] = []
    monkeypatch.setattr(Speech, "_synthesize",
                        lambda self, text, pause=True: synthesized.append(text) or np.zeros(1, np.float32))
    speech = Speech(lambda speaking: None, lambda queued, sounded, notice: None)
    list(speech._sentences(reply))
    assert len(synthesized) == takes


def test_joining_the_whole_reply_after_a_short_opener_stays_behind_its_switch(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BAXY_RENEW_TTS_JOIN_ALL", "1")
    test_a_first_sentence_of_more_than_a_few_words_is_synthesized_alone(
        tmp_path, monkeypatch, "Listo. Spotify está abierto y sonando. La canción es de Queen.", 1)


class _Sherpa:
    """sherpa-onnx as far as loading the voice goes: it tells whether the engine was built."""

    def __init__(self) -> None:
        self.built: list[object] = []
        for name in ("OfflineTtsConfig", "OfflineTtsModelConfig", "OfflineTtsSupertonicModelConfig"):
            setattr(self, name, lambda **kwargs: SimpleNamespace(**kwargs))

    def OfflineTts(self, config):  # noqa: N802 - sherpa-onnx's own name
        self.built.append(config)
        return SimpleNamespace(sample_rate=44100, generate=lambda *args, **kwargs: SimpleNamespace(
            samples=np.zeros(441, np.float32), sample_rate=44100))


# Uso real 2026-11-02: with about 1 GB left to commit on the PC, loading the voice died in the engine («bad allocation»,
# 0xC0000409, a native abort no handler catches) and took the mind with it. With less memory left to commit than the
# voice needs it is not loaded: the mind goes on without a voice. Encargo 10 (punto 6): a passing low point does not
# turn it off for the whole session; it is deferred (the state says why) and retried on the next use, and only after the
# retries run out is it a failure.
def test_a_voice_without_the_memory_to_load_it_is_deferred_then_fails_after_the_cap(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    folder = _model_dir(tmp_path)
    (folder / "baxy-voice.json").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("BAXY_RENEW_TTS_DIR", str(folder))
    sherpa = _Sherpa()
    monkeypatch.setitem(sys.modules, "sherpa_onnx", sherpa)
    monkeypatch.setattr(voice_output, "commit_available_mb", lambda: voice_output.VOICE_COMMIT_MB - 1, raising=False)
    speech = Speech(lambda speaking: None, lambda queued, sounded, notice: None)

    deadline = time.monotonic() + 5
    while not speech.deferred and time.monotonic() < deadline:
        time.sleep(0.02)
    assert "MB" in speech.deferred and "memory" in speech.deferred  # deferred, not a failure, and it says why
    assert not speech.ready and not speech.failure
    assert sherpa.built == []

    deadline = time.monotonic() + 5
    while not speech.failure and time.monotonic() < deadline:
        speech.speak("Hola.")  # each use retries the load, still with no room to commit
        time.sleep(0.05)
    assert "MB" in speech.failure and "memory" in speech.failure
    assert not speech.ready
    assert sherpa.built == []
    assert not speech.speak("Hola.")
    speech.close()
