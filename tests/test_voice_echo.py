"""What the PC plays is taken out of the microphone before the wake word, the VAD and the recognizer hear it
(src/baxy_mind/voice_echo.py; uso real 2026-11-03: a song's words went into a request). The stage's pieces, its place in
voice.py, the owner's switch and BAXY_ECHO_CANCEL=0; AEC3 itself where the runtime has it."""
import sys
from types import SimpleNamespace

import numpy as np
import pytest

from baxy_mind import voice, voice_echo
from baxy_mind.voice import BLOCK, RATE, Heard, Voice
from baxy_mind.voice_echo import Loopback, ReferenceGain, Resampler


def test_the_resampler_streams_without_seams_at_the_usual_rates() -> None:
    rng = np.random.default_rng(1)
    for rate in (48000, 44100, 96000):
        audio = rng.standard_normal(rate).astype(np.float32)
        whole = Resampler(rate, RATE)(audio)
        resampler, parts, at = Resampler(rate, RATE), [], 0
        while at < len(audio):
            size = int(rng.integers(50, 1500))
            parts.append(resampler(audio[at:at + size]))
            at += size
        chunked = np.concatenate(parts)
        assert np.array_equal(chunked, whole)
        assert abs(len(chunked) - len(audio) * RATE // rate) < 200   # the filter's start, never a drift


def test_the_resampler_keeps_the_voice_band_and_drops_what_16_khz_cannot_hold() -> None:
    t = np.arange(48000) / 48000
    for tone, kept in ((1000, True), (6000, True), (11000, False)):
        out = Resampler(48000, RATE)(np.sin(2 * np.pi * tone * t).astype(np.float32))[400:]
        level = float(np.sqrt(np.mean(out ** 2)))
        assert (level > 0.6) is kept, (tone, level)


def _loopback(held: list[np.ndarray]) -> Loopback:
    """A Loopback with ``held`` already heard, without a sound device."""
    loop = Loopback.__new__(Loopback)
    loop._lock, loop._rate, loop.trimmed = voice_echo.threading.Lock(), RATE, 0
    loop._held = voice_echo.deque(np.asarray(h, np.float32) for h in held)
    loop._samples = sum(len(h) for h in held)
    return loop


def test_nothing_playing_hands_silence_and_a_song_that_starts_comes_after_it() -> None:
    assert not _loopback([]).take(BLOCK).any()
    started = _loopback([np.ones(600)]).take(BLOCK)
    assert not started[:BLOCK - 600].any() and started[BLOCK - 600:].all()


def test_the_reference_handed_is_the_oldest_held_and_a_long_lead_is_dropped() -> None:
    near = _loopback([np.arange(1, 1001), np.arange(1001, 2201)])   # 2200 held: within SLACK_HIGH_S of a block
    assert np.array_equal(near.take(BLOCK), np.arange(1, BLOCK + 1)) and near.trimmed == 0
    far = _loopback([np.arange(1, 4001)])                             # 2400 over the block: down to SLACK_LOW_S
    got = far.take(BLOCK)
    keep = BLOCK + int(voice_echo.SLACK_LOW_S * RATE)
    assert far.trimmed == 4000 - keep
    assert np.array_equal(got, np.arange(4000 - keep + 1, 4000 - keep + 1 + BLOCK))


def test_a_quiet_reference_is_raised_and_a_loud_one_never_clipped() -> None:
    gain = ReferenceGain()
    quiet = 10 ** (-40 / 20) * np.sin(np.arange(BLOCK) / 5).astype(np.float32)   # peaks of a song at Windows' 8 %
    raised = gain(quiet)
    assert np.max(np.abs(raised)) == pytest.approx(voice_echo.REF_TARGET, rel=1e-3)
    hiss = 10 ** (-80 / 20) * np.sin(np.arange(BLOCK) / 5).astype(np.float32)
    assert np.max(np.abs(ReferenceGain()(hiss))) == pytest.approx(voice_echo.REF_GAIN_CAP * 1e-4, rel=1e-3)
    loud = gain(0.9 * np.sign(np.sin(np.arange(BLOCK) / 3)).astype(np.float32))
    assert np.max(np.abs(loud)) <= voice_echo.REF_TARGET + 1e-6
    assert not ReferenceGain()(np.zeros(BLOCK, np.float32)).any()


def test_a_silence_does_not_change_the_gain_of_the_reference() -> None:
    """F44: the gain is part of the echo path AEC3 learned. Minutes of nothing playing decayed its peak (0.999 per block:
    31 dB in 6 minutes), so what played next was raised to another level, and the path learned no longer held, exactly
    when a voice starts after a silence."""
    gain = ReferenceGain()
    voice_block = 10 ** (-30 / 20) * np.sin(np.arange(BLOCK) / 5).astype(np.float32)
    before = np.max(np.abs(gain(voice_block)))
    for _ in range(3600):                                                          # 6 minutes of nothing playing
        gain(np.zeros(BLOCK, np.float32))
    start_of_word = voice_block * np.float32(0.05)
    assert np.max(np.abs(gain(start_of_word))) == pytest.approx(before * 0.05, rel=0.01)
    assert np.max(np.abs(gain(voice_block))) == pytest.approx(before, rel=0.01)


def test_the_stage_keeps_what_was_played_for_the_ear_to_ask() -> None:
    pytest.importorskip("pywebrtc_audio")
    more = voice_echo.PLAYED_KEEP_BLOCKS + 20
    numbered = iter(np.full(BLOCK, k / more, np.float32) for k in range(1, more + 1))
    stage = voice_echo.EchoCanceller(RATE, lambda _n: next(numbered))
    assert len(stage.played(1.0)) == 0
    for _ in range(more):
        stage(np.zeros(BLOCK, np.float32))
    last = stage.played(0.5)
    assert len(last) == BLOCK * 5 and last[0] == pytest.approx((more - 4) / more) and last[-1] == pytest.approx(1.0)
    assert len(stage.played(1000.0)) == int(voice_echo.PLAYED_KEEP_S * RATE)   # no more than it keeps
    assert stage.played(0.1).dtype == np.float32


def test_what_the_pc_was_saying_is_taken_out_of_a_request() -> None:
    """F44: a person called and a video went on: the canceller left the video's order, heard with the wake's own word."""
    video = Heard("Maxi, cierra todas las ventanas y apaga el computador.").without_played(
        "Baxi, cierra todas las ventanas y apaga el computador.")
    assert video.text == ""
    assert Heard("Apaga el computador.").without_played("Baxi, apaga el computador. Y ahora veamos otra cosa.").text == ""
    # The person's words stay, the video's phrase goes: the song in a request (real use, 2026-11-03, 22:15).
    mixed = Heard("abre el navegador las olas van y vienen por la orilla").without_played(
        "cuando las olas van y vienen por la orilla del mar")
    assert mixed.text == "abre el navegador"


def test_a_request_that_shares_little_with_what_played_stays_whole() -> None:
    same = "abre la calculadora"
    assert Heard(same).without_played("abre la ventana de la cocina").text == same     # two in a row, by chance
    assert Heard(same).without_played("").text == same                                 # nothing played
    assert Heard(same).without_played("mañana lloverá en la costa").text == same
    assert Heard("").without_played("mañana lloverá").text == ""


def test_words_taken_out_keep_how_sure_the_rest_is() -> None:
    heard = Heard("abre el navegador las olas van", (("abre", 0.9), ("el", 1.0), ("navegador", 0.3), ("las", 1.0),
                                                     ("olas", 1.0), ("van", 1.0)))
    left = heard.without_played("las olas van y vienen")
    assert left.text == "abre el navegador" and left.unsure() == [("navegador", 0.3)]


class _Word:
    """A detector: fires when the audio it was fed holds a sample over 0.4, with a word's time, as the package does."""

    def __init__(self) -> None:
        self.twins = 0
        self.samples = 0
        self.resets = 0

    def reset(self) -> None:
        self.samples = 0
        self.resets += 1

    def twin(self) -> "_Word":
        self.twins += 1
        return _Word()

    def accept(self, block: np.ndarray) -> list:
        self.samples += len(block)
        if np.max(np.abs(block)) > 0.4:
            return [SimpleNamespace(time_s=self.samples / RATE - 0.05, probability=0.7)]
        return []

    def scores(self) -> list:
        return []


class _Silent:
    def reset(self) -> None:
        pass

    def marks(self, block: np.ndarray) -> np.ndarray:
        return np.zeros(len(block), bool)


def _gated(played: np.ndarray | None, written: list[dict]) -> Voice:
    """A Voice hearing «Baxy» after the word, whose stage played ``played`` (None: no stage, the switch is off)."""
    ear = object.__new__(Voice)
    ear._lock = voice_echo.threading.Lock()
    ear._mode, ear._detector, ear._vad = "wake", _Word(), _Silent()
    ear._on_early, ear._on_wake, ear._heard, ear._wake_log, ear._write = None, None, 0, None, written.append
    ear._wake_peak, ear._recent, ear._played_twin = voice.WAKE_TARGET, None, None
    ear._echo = None if played is None else voice_echo.Stage(lambda b: b, lambda: None, lambda s: played[-int(s * RATE):])
    ear._blocks = voice.queue.Queue()
    ear._reset()
    return ear


def _hear(ear: Voice, blocks: list[np.ndarray]) -> None:
    for block in blocks:
        with ear._lock:
            ear._feed(block)
            check = ear._call_to_check()
        if check is not None:
            played = ear._played_it(*check)
            with ear._lock:
                ear._settle_call(played)


_QUIET, _WORD = np.full(BLOCK, 0.01, np.float32), np.full(BLOCK, 0.5, np.float32)
_HOLD = int(voice_echo.PLAYED_HOLD_S * 10) + 1


def _opened(written: list[dict]) -> bool:
    return any(message.get("event") == "wake_detected" for message in written)


def test_a_call_with_nothing_playing_opens_at_once() -> None:
    written: list[dict] = []
    ear = _gated(np.zeros(8 * RATE, np.float32), written)
    _hear(ear, [_QUIET] * 3 + [_WORD])
    assert _opened(written) and ear._start is not None and ear._detector.twins == 0


def test_with_the_switch_off_a_call_opens_at_once() -> None:
    written: list[dict] = []
    ear = _gated(None, written)
    _hear(ear, [_QUIET] * 3 + [_WORD])
    assert _opened(written) and ear._start is not None


def test_the_word_the_pc_played_opens_no_request(capsys: pytest.CaptureFixture[str]) -> None:
    """F44: what the PC plays says «Baxy», the microphone hears it before AEC3 has learned the room: the same detector
    on the reference hears it too, so nobody called. Nothing is told to the App, nothing is transcribed."""
    written: list[dict] = []
    played = np.full(8 * RATE, 0.001, np.float32)
    played[6 * RATE + 800:6 * RATE + 1600] = 0.01                                # a quiet loopback: Windows' volume
    ear = _gated(played, written)
    _hear(ear, [_QUIET] * 3 + [_WORD])
    assert not _opened(written) and ear._start is None                           # waiting for the word's end on it
    _hear(ear, [_QUIET] * _HOLD)
    assert not _opened(written) and ear._start is None
    assert ear._held_call is None and not [m for m in written if m.get("type") == "voice.transcript"]
    lines = [line for line in capsys.readouterr().err.splitlines() if " wake " in line]
    assert len(lines) == 1 and "played by the PC" in lines[0] and "p=0.700" in lines[0]


def test_a_package_that_asks_for_a_short_hold_opens_sooner_and_still_finds_the_played_word() -> None:
    """uso-79: k6r decides as it hears, so its firing waits 0.2 s, not the second a chunked detector needs. The same
    second stays for a package that names nothing."""
    written: list[dict] = []
    played = np.full(8 * RATE, 0.001, np.float32)
    played[4 * RATE + 800:4 * RATE + 1600] = 0.01                 # the PC sounding, its word far from this firing
    ear = _gated(played, written)
    ear._detector.played_hold_s = 0.2
    _hear(ear, [_QUIET] * 3 + [_WORD])
    assert not _opened(written)
    _hear(ear, [_QUIET] * 3)  # 0.2 s and its rounding: not the 11 blocks of the second
    assert _opened(written) and ear._start is not None
    written.clear()
    played = np.full(8 * RATE, 0.001, np.float32)
    played[7 * RATE + 800:7 * RATE + 1600] = 0.01                  # the last 8 s are read: the word 0.2 s before their end
    ear = _gated(played, written)
    ear._detector.played_hold_s = 0.2
    _hear(ear, [_QUIET] * 3 + [_WORD] + [_QUIET] * 3)
    assert not _opened(written) and ear._start is None and ear._held_call is None


def test_a_word_the_pc_played_a_moment_before_is_not_this_call() -> None:
    """BAXY said «soy Baxy», or a video did, and the person calls three seconds later: their call stands."""
    written: list[dict] = []
    played = np.full(8 * RATE, 0.001, np.float32)
    played[3 * RATE + 800:3 * RATE + 1600] = 0.01                                # 3 s before where the firing is read
    ear = _gated(played, written)
    _hear(ear, [_QUIET] * 3 + [_WORD])
    _hear(ear, [_QUIET] * _HOLD)
    assert _opened(written) and ear._start is not None


def test_a_persons_call_over_what_the_pc_plays_opens_from_where_it_was_said() -> None:
    """A song with no «Baxy» in it: the call is held until the reference was heard, then opens at the word's own time,
    so the request's first words are not lost."""
    written: list[dict] = []
    # The detector here fires over 0.4: a peak of 1 normalized to WAKE_TARGET (0.45) would read as the word, so the
    # played audio has its peak in a block of its own below the fake's bar: only the level of its rest matters.
    played = np.full(8 * RATE, 0.3, np.float32)
    ear = _gated(played, written)
    ear._detector.twin = lambda: SimpleNamespace(reset=lambda: None, accept=lambda _block: [])
    _hear(ear, [_QUIET] * 3 + [_WORD])
    said_at = ear._held_call.start
    assert not _opened(written)
    _hear(ear, [_QUIET] * _HOLD)
    assert _opened(written) and ear._start == pytest.approx(said_at) and ear._held_call is None


def test_a_check_that_fails_lets_the_call_through(capsys: pytest.CaptureFixture[str]) -> None:
    written: list[dict] = []
    ear = _gated(np.full(8 * RATE, 0.3, np.float32), written)

    def short_of_memory():
        raise MemoryError("no room")

    ear._detector.twin = short_of_memory
    _hear(ear, [_QUIET] * 3 + [_WORD] + [_QUIET] * _HOLD)
    assert _opened(written)
    assert "played" in capsys.readouterr().err


def test_a_reset_forgets_the_call_being_checked() -> None:
    written: list[dict] = []
    ear = _gated(np.full(8 * RATE, 0.3, np.float32), written)
    _hear(ear, [_QUIET] * 3 + [_WORD])
    assert ear._held_call is not None
    ear._reset()
    assert ear._held_call is None and ear._call_to_check() is None


def test_each_wake_says_whether_the_stage_is_on(capsys: pytest.CaptureFixture[str]) -> None:
    """F44: nobody could tell whether the cancellation was on when the installer's voice was answered."""
    ear = _gated(np.zeros(8 * RATE, np.float32), [])
    _hear(ear, [_QUIET] * 3 + [_WORD])
    assert "echo=on" in capsys.readouterr().err
    ear = _gated(None, [])
    _hear(ear, [_QUIET] * 3 + [_WORD])
    assert "echo=off" in capsys.readouterr().err


def test_a_stage_that_opens_says_so_and_on_what(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    pytest.importorskip("pywebrtc_audio")

    class _Open:
        name = "Altavoces de prueba"
        trimmed = 0

        def __init__(self, _rate: int) -> None:
            pass

        def take(self, count: int) -> np.ndarray:
            return np.zeros(count, np.float32)

        def close(self) -> None:
            pass

    monkeypatch.setattr(voice_echo, "Loopback", _Open)
    stage = voice_echo.open_stage(RATE)
    assert stage is not None
    assert "echo cancellation on: Altavoces de prueba" in capsys.readouterr().err


def test_aec3_takes_a_quiet_loopbacks_song_out_of_the_microphone() -> None:
    """The case measured on the PC: the loopback 20+ dB under the echo the microphone hears. AEC3 on the loopback as it
    comes leaves it (render under its active_render_limit); the stage takes most of it out."""
    aec3 = pytest.importorskip("pywebrtc_audio")
    rng = np.random.default_rng(5)
    seconds = 8
    song = np.convolve(rng.standard_normal(seconds * RATE), np.ones(4) / 4, "same").astype(np.float32)
    reference = song * np.float32(10 ** (-61 / 20) / np.std(song))
    path = np.zeros(400, np.float32)
    path[[320, 345, 390]] = [1.0, -0.4, 0.2]                                   # 20 ms late, two reflections
    echo = np.convolve(song, path)[:len(song)] * np.float32(10 ** (-38 / 20) / np.std(song))
    mic = (echo + rng.normal(0, 10 ** (-70 / 20), len(echo))).astype(np.float32)
    blocks = iter(reference[at:at + BLOCK] for at in range(0, len(reference), BLOCK))
    stage = voice_echo.EchoCanceller(RATE, lambda _n: next(blocks))
    plain = aec3.EchoCanceller(RATE, 1, 0)
    out_stage, out_plain = np.zeros_like(mic), np.zeros_like(mic)
    for at in range(0, len(mic), BLOCK):
        out_stage[at:at + BLOCK] = stage(mic[at:at + BLOCK])
        out_plain[at:at + BLOCK] = plain.process(mic[at:at + BLOCK], reference[at:at + BLOCK])
    tail = slice(3 * RATE, None)                                             # after AEC3 has learnt the path
    removed = lambda out: 10 * np.log10(np.mean(mic[tail] ** 2) / np.mean(out[tail] ** 2))  # noqa: E731
    assert removed(out_plain) < 3
    assert removed(out_stage) > 10


class _Stream:
    def __init__(self, callback, **_kwargs) -> None:
        self.callback, self.closed = callback, False
        _Stream.opened.append(self)

    def start(self) -> None:
        pass

    def close(self) -> None:
        self.closed = True

    def hear(self, block: np.ndarray) -> None:
        self.callback(block.reshape(-1, 1), len(block), None, None)


class _Speech:
    speaking = ready = False
    deferred = ""

    def __init__(self, *_args) -> None:
        pass


def _ear(monkeypatch: pytest.MonkeyPatch, events: list[str]) -> Voice:
    """A Voice whose microphone is a fake sounddevice stream and whose stage halves each block."""
    _Stream.opened = []
    monkeypatch.setitem(sys.modules, "sounddevice", SimpleNamespace(InputStream=_Stream))

    def open_stage(rate: int):
        events.append("open")
        return voice_echo.Stage(lambda block: block * 0.5, lambda: events.append("close"), lambda _seconds: np.zeros(0))

    def load(self: Voice) -> None:
        self._recognizer, self._input, self._vad = object(), True, None
        self._loaded.set()

    monkeypatch.setattr(voice_echo, "open_stage", open_stage)
    monkeypatch.setattr(voice, "Speech", _Speech)
    monkeypatch.setattr(Voice, "_load", load)
    monkeypatch.setattr(Voice, "_device", lambda self: None)
    monkeypatch.setattr(Voice, "_listen", lambda self: None)
    return Voice(lambda _message: None)


def test_the_microphone_is_heard_through_the_stage_and_the_switch_reopens_it(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BAXY_ECHO_CANCEL", raising=False)
    events: list[str] = []
    ear = _ear(monkeypatch, events)
    assert ear.start("direct")
    _Stream.opened[-1].hear(np.full(BLOCK, 0.4, np.float32))
    assert ear._blocks.get_nowait() == pytest.approx(0.2) and ear.status()["echo"] is True
    assert ear.start("direct")                        # the same switch: the open microphone stays
    assert len(_Stream.opened) == 1 and events == ["open"]
    assert ear.start("direct", echo_cancel=False)     # the owner switched it off: opened again without it
    assert _Stream.opened[0].closed and events == ["open", "close"] and ear.status()["echo"] is False
    _Stream.opened[-1].hear(np.full(BLOCK, 0.4, np.float32))
    assert ear._blocks.get_nowait() == pytest.approx(0.4)
    assert ear.start("direct", echo_cancel=True)
    ear.stop()
    assert _Stream.opened[-1].closed and events == ["open", "close", "open", "close"]


def test_baxy_echo_cancel_0_turns_the_stage_off_whatever_the_switch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BAXY_ECHO_CANCEL", "0")
    events: list[str] = []
    ear = _ear(monkeypatch, events)
    assert ear.start("direct", echo_cancel=True)
    _Stream.opened[-1].hear(np.full(BLOCK, 0.4, np.float32))
    assert ear._blocks.get_nowait() == pytest.approx(0.4) and events == [] and ear.status()["echo"] is False


def test_a_loopback_that_does_not_open_leaves_the_microphone_as_before(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(_rate: int) -> Loopback:
        raise OSError("no WASAPI loopback")

    monkeypatch.setattr(voice_echo, "Loopback", broken)
    assert voice_echo.open_stage(RATE) is None
