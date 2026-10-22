"""BAXY's spoken voice at its edges (src/baxy_mind/voice_output.py): an answer the full queue refuses leaves nothing
behind."""
from pathlib import Path

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
    speech = Speech(lambda speaking: None, lambda queued, sounded: None)
    while not speech._queue.full():
        speech.prepare()
    assert not speech.speak("x")
    assert synthesized == []
    assert speech._answers == 0
