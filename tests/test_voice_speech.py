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
