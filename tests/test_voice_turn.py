"""The end of a spoken turn heard by the turn model (src/baxy_mind/voice_turn.py, Smart Turn v3.2) and the wait it sets in
Voice._over (uso-74): a turn heard complete closes after END_DONE_S, one heard unfinished after END_OPEN_S; the model
hears the request once per end of voice, TURN_AT_S into its silence."""
import hashlib
from pathlib import Path

import numpy
import pytest

from baxy_mind import voice, voice_turn
from baxy_mind.voice import RATE, Voice

LOUD, QUIET = 0.05, 0.002


class _Turn:
    """A turn model that says ``p`` and keeps what it heard."""

    def __init__(self, p: float) -> None:
        self.p = p
        self.heard: list[numpy.ndarray] = []

    def complete(self, audio: numpy.ndarray) -> float:
        self.heard.append(audio)
        return self.p


def _heard(turn: _Turn | None, *pieces: tuple[float, float], mode: str = "direct") -> Voice:
    listening = object.__new__(Voice)
    listening._mode, listening._released, listening._first = mode, False, 0
    listening._audio = numpy.concatenate([numpy.full(int(s * RATE), level, numpy.float32) for s, level in pieces])
    listening._speech = numpy.ones(len(listening._audio), bool)
    listening._total = len(listening._audio)
    listening._early_at = listening._early_heard = None
    listening._turn = turn
    return listening


def _more(listening: Voice, s: float, level: float) -> Voice:
    """The same request having heard ``s`` seconds more at ``level``."""
    listening._audio = numpy.concatenate([listening._audio, numpy.full(int(s * RATE), level, numpy.float32)])
    listening._speech = numpy.ones(len(listening._audio), bool)
    listening._total = len(listening._audio)
    return listening


def test_a_turn_heard_complete_closes_after_the_short_silence() -> None:
    assert voice.TURN_AT_S <= voice.END_DONE_S < voice.END_SILENCE_S < voice.END_SLOW_S
    turn = _Turn(0.9)
    listening = _heard(turn, (1.5, LOUD), (voice.END_DONE_S - 0.1, QUIET))
    assert not listening._over(0.0)
    assert _more(listening, 0.1, QUIET)._over(0.0)
    assert len(turn.heard) == 1  # once per end of voice, however many blocks of silence follow


def test_a_turn_heard_surely_unfinished_waits_the_long_silence() -> None:
    listening = _heard(_Turn(voice.TURN_OPEN_P / 2), (1.5, LOUD), (voice.END_SILENCE_S, QUIET))
    assert not listening._over(0.0)
    assert not _more(listening, round(voice.END_SLOW_S - voice.END_SILENCE_S - 0.1, 3), QUIET)._over(0.0)
    assert _more(listening, 0.1, QUIET)._over(0.0)


def test_a_turn_the_model_is_unsure_of_waits_in_between() -> None:
    assert voice.END_DONE_S < voice.END_UNSURE_S < voice.END_SLOW_S
    listening = _heard(_Turn((voice.TURN_OPEN_P + voice.TURN_P) / 2), (1.5, LOUD), (voice.END_SILENCE_S, QUIET))
    assert not listening._over(0.0)
    assert not _more(listening, round(voice.END_UNSURE_S - voice.END_SILENCE_S - 0.1, 3), QUIET)._over(0.0)
    assert _more(listening, 0.1, QUIET)._over(0.0)


def test_words_left_hanging_keep_the_long_wait_even_when_the_model_hears_the_turn_complete() -> None:
    from baxy_mind.voice import Heard
    listening = _heard(_Turn(0.9), (1.5, LOUD), (voice.END_DONE_S, QUIET))
    end = 1.5
    listening._early_at, listening._early_heard = end, Heard("abre el")
    assert not listening._over(0.0)
    listening = _more(listening, round(voice.END_SLOW_S - voice.END_DONE_S - 0.1, 3), QUIET)
    assert not listening._over(0.0)
    assert _more(listening, 0.1, QUIET)._over(0.0)
    finished = _heard(_Turn(0.9), (1.5, LOUD), (voice.END_DONE_S, QUIET))
    finished._early_at, finished._early_heard = end, Heard("abre el bloc de notas.")
    assert finished._over(0.0)


def test_the_model_is_not_asked_before_the_silence_it_hears_after() -> None:
    turn = _Turn(0.9)
    assert not _heard(turn, (1.5, LOUD), (voice.TURN_AT_S - 0.1, QUIET))._over(0.0)
    assert turn.heard == []


def test_voice_after_a_pause_is_heard_again_at_its_own_end() -> None:
    # «abre el… bloc de notas»: unfinished at the pause, complete at the end
    turn = _Turn(0.1)
    listening = _heard(turn, (1.0, LOUD), (1.0, QUIET))
    assert not listening._over(0.0)
    turn.p = 0.9
    listening = _more(_more(listening, 0.8, LOUD), voice.END_DONE_S, QUIET)
    assert listening._over(0.0)
    assert len(turn.heard) == 2


@pytest.mark.parametrize("mode", ["wake", "direct"])
def test_the_model_hears_the_request_up_to_now_and_at_most_its_window(mode: str) -> None:
    # wake: the request opened BEFORE_S into a quiet room, and the model hears from BEFORE_S before it, as Ultra does
    turn = _Turn(0.9)
    _heard(turn, (voice.BEFORE_S, QUIET), (2.0, LOUD), (voice.TURN_AT_S, QUIET), mode=mode)._over(
        voice.BEFORE_S if mode == "wake" else 0.0)
    assert len(turn.heard[0]) == int((voice.BEFORE_S + 2.0 + voice.TURN_AT_S) * RATE)
    long_turn = _Turn(0.9)
    _heard(long_turn, (3.0, QUIET), (8.5, LOUD), (voice.TURN_AT_S, QUIET))._over(0.0)  # under MAX_S, over TURN_S
    assert len(long_turn.heard[0]) == voice_turn.TURN_S * RATE


def test_without_the_model_the_hanging_words_set_the_wait() -> None:
    listening = _heard(None, (1.5, LOUD), (voice.END_SILENCE_S, QUIET))
    assert listening._over(0.0)


def test_in_a_loud_room_the_model_is_not_asked_and_the_rule_decides() -> None:
    # steady noise above VOICE_RMS fills the pause (Silero hears no speech in it): the model would hear it complete
    noise = voice.VOICE_RMS * 2
    turn = _Turn(0.9)
    listening = _heard(turn, (1.5, LOUD), (voice.END_DONE_S, noise))
    listening._speech[int(1.5 * RATE):] = False
    assert not listening._over(0.0)
    assert turn.heard == []
    listening = _more(listening, round(voice.END_SILENCE_S - voice.END_DONE_S, 3), noise)
    listening._speech[int(1.5 * RATE):] = False
    assert listening._over(0.0)


def test_the_floor_of_a_quiet_and_a_loud_room() -> None:
    # a fifth of the blocks quiet is a quiet room; the same blocks at twice VOICE_RMS, a loud one
    blocks = int(voice.BLOCK)
    speech = numpy.full(8 * blocks, LOUD, numpy.float32)
    assert not voice.loud_floor(numpy.concatenate([numpy.full(3 * blocks, QUIET, numpy.float32), speech]))
    assert voice.loud_floor(numpy.concatenate([numpy.full(3 * blocks, voice.VOICE_RMS * 2, numpy.float32), speech]))
    assert not voice.loud_floor(numpy.zeros(0, numpy.float32))


def test_features_keep_the_last_window_and_pad_before_a_short_one() -> None:
    rng = numpy.random.default_rng(0)
    short = rng.standard_normal(3 * RATE).astype(numpy.float32) * 0.1
    padded = numpy.concatenate([numpy.zeros(5 * RATE, numpy.float32), short])
    assert voice_turn.features(short).shape == (80, 800)
    assert numpy.array_equal(voice_turn.features(short), voice_turn.features(padded))
    long = rng.standard_normal(11 * RATE).astype(numpy.float32) * 0.1
    assert numpy.array_equal(voice_turn.features(long), voice_turn.features(long[-voice_turn.TURN_S * RATE:]))


def test_the_installed_model_loads_and_says_a_probability(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("onnxruntime")
    if not voice_turn.default_path().is_file():
        pytest.skip("scripts/voice/instalar_fin_de_turno.ps1 was not run on this machine")
    monkeypatch.delenv("BAXY_RENEW_TURN", raising=False)
    monkeypatch.delenv("BAXY_RENEW_TURN_MODEL", raising=False)
    path = voice_turn.model_path()
    assert path == voice_turn.default_path()
    t = numpy.arange(RATE) / RATE
    p = voice_turn.Turn(path).complete(numpy.concatenate([0.1 * numpy.sin(2 * numpy.pi * 180 * t),
                                                          numpy.zeros(RATE // 5)]).astype(numpy.float32))
    assert 0.0 <= p <= 1.0


def test_the_switch_and_the_model_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    model = tmp_path / "turn.onnx"
    model.write_bytes(b"x")
    monkeypatch.setattr(voice_turn, "MODEL_SHA256", hashlib.sha256(b"x").hexdigest())
    monkeypatch.setenv("BAXY_RENEW_TURN_MODEL", str(model))
    assert voice_turn.model_path() == model
    monkeypatch.setenv("BAXY_RENEW_TURN", "0")
    assert voice_turn.model_path() is None
    monkeypatch.delenv("BAXY_RENEW_TURN")
    monkeypatch.setenv("BAXY_RENEW_TURN_MODEL", str(tmp_path / "missing.onnx"))
    assert voice_turn.model_path() is None
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.delenv("BAXY_RENEW_TURN_MODEL")
    assert voice_turn.model_path() is None  # nothing installed under this LOCALAPPDATA


def test_a_file_that_is_not_the_published_model_is_not_used(monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
                                                            capsys: pytest.CaptureFixture[str]) -> None:
    other = tmp_path / voice_turn.MODEL_NAME
    other.write_bytes(b"not the model")
    monkeypatch.setenv("BAXY_RENEW_TURN_MODEL", str(other))
    assert voice_turn.model_path() is None
    assert "not smart-turn-v3.2-cpu.onnx as published" in capsys.readouterr().err
