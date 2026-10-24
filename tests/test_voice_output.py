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
    monkeypatch.setattr(Speech, "_play", lambda self, audio, generation, queued, *rest: played.extend(audio))
    speech = Speech(lambda speaking: None, lambda queued, sounded, *rest: None)

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
                  notice: str = "") -> Speech:
    """A loaded voice whose synthesis is the text itself (a notice's: «audio:» and its text), with the mind's notice
    phrase given and its audio ready when one is."""
    monkeypatch.setenv("BAXY_RENEW_TTS_DIR", str(_model_dir(tmp_path)))
    monkeypatch.setattr(Speech, "_start", lambda self: None)
    monkeypatch.setattr(Speech, "_synthesize", lambda self, text, pause=True: f"audio:{text}")
    monkeypatch.setattr(Speech, "_sentences", lambda self, text: iter([text]))
    monkeypatch.setattr(Speech, "_play", lambda self, audio, generation, queued, *rest: played.extend(audio))
    speech = Speech(lambda speaking: None, lambda queued, sounded, *rest: None)
    deadline = time.monotonic() + 5
    while not speech.ready and time.monotonic() < deadline:
        time.sleep(0.01)
    assert speech.ready
    if notice:
        speech.set_notice(notice)
        while speech._notice_audio is None and time.monotonic() < deadline:
            time.sleep(0.01)
        assert speech._notice_audio == f"audio:{notice}"
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
    speech = _loaded_voice(tmp_path, monkeypatch, played, notice="Dame un segundo.")
    busy = threading.Event()
    monkeypatch.setattr(Speech, "_open_stream", lambda self: busy.wait(5))
    speech.prepare()  # the speech thread opens the output: what follows waits in the queue
    assert speech.speak("Dame un segundo.", notice=True)
    assert speech.speak("Tienes 36 juegos en Steam.")
    busy.set()
    _wait_for(played, 1)
    assert played == ["Tienes 36 juegos en Steam."]


def test_a_notice_with_no_answer_yet_is_said_and_the_answer_follows(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    played: list[str] = []
    speech = _loaded_voice(tmp_path, monkeypatch, played, notice="Dame un segundo.")
    assert speech.speak("Dame un segundo.", notice=True)
    _wait_for(played, 1)
    assert speech.speak("Listo, abrí Steam.")
    _wait_for(played, 2)
    assert played == ["audio:Dame un segundo.", "Listo, abrí Steam."]


def test_the_notice_is_the_mind_s_phrase_synthesized_when_it_is_given(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Al máximo 9.2a: the notice was «Un momento.», fixed in the code and synthesized at load; it is now the phrase
    the model wrote (catalog.ready), synthesized as soon as the voice has it, and nothing else is taken as the notice."""
    played: list[str] = []
    speech = _loaded_voice(tmp_path, monkeypatch, played)
    assert not speech.speak("Un momento.", notice=True)  # no phrase from the mind: no notice
    speech.set_notice("Sigo en ello.")
    deadline = time.monotonic() + 5
    while speech._notice_audio is None and time.monotonic() < deadline:
        time.sleep(0.01)
    assert not speech.speak("Un momento.", notice=True)
    assert speech.speak("Sigo en ello.", notice=True)
    _wait_for(played, 1)
    assert played == ["audio:Sigo en ello."]


def test_a_notice_given_while_the_voice_loads_is_synthesized_once_it_has(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BAXY_RENEW_TTS_DIR", str(_model_dir(tmp_path)))
    loaded = threading.Event()
    monkeypatch.setattr(Speech, "_start", lambda self: loaded.wait(5))
    monkeypatch.setattr(Speech, "_synthesize", lambda self, text, pause=True: f"audio:{text}")
    speech = Speech(lambda speaking: None, lambda queued, sounded, *rest: None)
    speech.set_notice("Sigo en ello.")
    assert not speech.speak("Sigo en ello.", notice=True)  # a notice is never synthesized when it is asked
    loaded.set()
    deadline = time.monotonic() + 5
    while speech._notice_audio is None and time.monotonic() < deadline:
        time.sleep(0.01)
    assert speech._notice_audio == "audio:Sigo en ello."


def test_an_empty_notice_from_the_mind_is_never_said(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    played: list[str] = []
    speech = _loaded_voice(tmp_path, monkeypatch, played)
    speech.set_notice("")
    assert not speech.speak("", notice=True)
    assert speech._notice_audio is None


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
    speech = Speech(lambda speaking: None, lambda queued, sounded, *rest: None)
    assert speech.failure
    assert not speech.speak("Hola.")
    assert not speech.ready


def test_the_notice_sounds_from_its_audio_kept_at_load_and_never_holds_the_synthesis(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Owner, 2026-10-20: an answer waited 3.6 s behind «Un momento», which was synthesized like any sentence."""
    played: list[str] = []
    speech = _loaded_voice(tmp_path, monkeypatch, played, notice="Dame un segundo.")
    started: list[str] = []
    monkeypatch.setattr(Speech, "_sentences", lambda self, text: started.append(text) or iter([text]))
    assert speech.speak("Dame un segundo.", notice=True)
    _wait_for(played, 1)
    assert speech.speak("Listo, abrí Steam.")
    _wait_for(played, 2)
    assert started == ["Listo, abrí Steam."]
    assert played == ["audio:Dame un segundo.", "Listo, abrí Steam."]


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
    monkeypatch.setattr(Speech, "_play", lambda self, audio, generation, queued, *rest: played.extend(audio))
    speech = Speech(lambda speaking: None, lambda queued, sounded, *rest: None)
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


# --- the mouth follows the voice (owner, 2026-10-21) ------------------------------------------------------------------

class _FakeStream:
    latency = 0.09

    def __init__(self, on_write=None) -> None:
        self.on_write = on_write

    def write(self, block) -> None:
        if self.on_write:
            self.on_write()

    def abort(self) -> None:
        pass

    def close(self) -> None:
        pass


def _player(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, lips: list[dict], stream: _FakeStream) -> Speech:
    monkeypatch.setenv("BAXY_RENEW_TTS_DIR", str(_model_dir(tmp_path)))
    monkeypatch.setattr(Speech, "_start", lambda self: None)
    monkeypatch.setattr(Speech, "_open_stream", lambda self: stream)
    monkeypatch.setattr(voice_output, "TAIL_S", 0.0)
    speech = Speech(lambda speaking: None, lambda queued, sounded, *rest: None, lips.append)
    speech.rate = 1000
    return speech


def test_the_mouth_is_closed_in_silence_and_open_at_the_voices_loudness() -> None:
    import numpy as np

    rate = 24000
    t = np.arange(rate // 2) / rate
    voice = (voice_output.LOUDNESS * np.sqrt(2) * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
    level = voice_output.lip_envelope(np.concatenate([np.zeros(rate // 2, np.float32), voice]), rate)
    step = int(rate * voice_output.LIP_STEP_S)
    assert len(level) == -(-rate // step)
    half = len(level) // 2
    assert max(level[:half - 1]) == 0.0
    assert all(0.7 < v < 0.9 for v in level[half + 1:])


def test_each_take_says_when_it_sounds_and_the_next_one_follows_it(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import numpy as np

    lips: list[dict] = []
    speech = _player(tmp_path, monkeypatch, lips, _FakeStream())
    first, second = np.full(500, 0.1, np.float32), np.full(300, 0.1, np.float32)
    before = time.time() * 1000
    speech._play(iter([first, second]), speech._generation, time.monotonic())
    takes = [lip for lip in lips if "t0" in lip]
    assert len(takes) == 2
    # the first take sounds once the output's latency has passed; the second right where the first one ends (0.5 s)
    assert before + 90 - 5 <= takes[0]["t0"] <= time.time() * 1000 + 90
    assert abs(takes[1]["t0"] - (takes[0]["t0"] + 500)) <= 1
    assert takes[0]["step"] == 40 and len(takes[0]["env"]) == 13 and len(takes[1]["env"]) == 8


def test_a_voice_cut_short_tells_the_mouth_to_close(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import numpy as np

    lips: list[dict] = []
    stream = _FakeStream()
    speech = _player(tmp_path, monkeypatch, lips, stream)
    writes = []
    stream.on_write = lambda: (writes.append(1), len(writes) == 3 and speech.cancel())
    speech._play(iter([np.full(2000, 0.1, np.float32)]), speech._generation, time.monotonic())
    assert [k for lip in lips for k in lip if k in ("t0", "stop")] == ["t0", "stop"]
    assert abs(lips[-1]["stop"] - time.time() * 1000) < 500


# --- 9.2b: the notice counts until the answer is heard, not until it is published -------------------------------------

def test_a_notice_asked_while_a_given_answer_is_still_synthesized_sounds_before_it(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An answer published at 2.4 s that sounds at 3.9 s left more than 3 s without a signal: the notice asked at 2.5 s
    waited behind the answer's synthesis. It sounds from its own audio while that synthesis runs."""
    from concurrent.futures import Future

    played: list[str] = []
    speech = _loaded_voice(tmp_path, monkeypatch, played, notice="Dame un segundo.")
    first: Future = Future()

    def sentences(self: Speech, text: str):
        def audio():
            yield first.result()
        return voice_output._Sentences(first, audio())

    monkeypatch.setattr(Speech, "_sentences", sentences)
    assert speech.speak("Listo, abrí Steam.")
    time.sleep(0.1)  # the speech thread waits for the answer's first sentence
    assert speech.speak("Dame un segundo.", notice=True)
    _wait_for(played, 1)
    assert played == ["audio:Dame un segundo."]
    first.set_result("Listo, abrí Steam.")
    _wait_for(played, 2)
    assert played == ["audio:Dame un segundo.", "Listo, abrí Steam."]


def test_a_notice_asked_once_the_answer_sounds_is_never_said(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import numpy as np

    lips: list[dict] = []
    stream = _FakeStream()
    speech = _player(tmp_path, monkeypatch, lips, stream)
    speech._notice_text, speech._notice_audio = "Sigo en ello.", np.zeros(10, np.float32)
    asked: list[bool] = []
    stream.on_write = lambda: asked.append(speech.speak("Sigo en ello.", notice=True)) if not asked else None
    speech._play(iter([np.full(500, 0.1, np.float32)]), speech._generation, time.monotonic())
    assert asked == [False]
    assert speech.speak("Sigo en ello.", notice=True)  # the answer ended: a later turn's notice is taken


def test_the_first_sound_says_whether_it_is_the_notice_or_the_answer(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import numpy as np
    from baxy_mind.voice import Voice

    sounds: list[tuple] = []
    monkeypatch.setenv("BAXY_RENEW_TTS_DIR", str(_model_dir(tmp_path)))
    monkeypatch.setattr(Speech, "_start", lambda self: None)
    monkeypatch.setattr(Speech, "_open_stream", lambda self: _FakeStream())
    monkeypatch.setattr(voice_output, "TAIL_S", 0.0)
    speech = Speech(lambda speaking: None, lambda queued, sounded, notice: sounds.append(notice))
    speech.rate = 1000
    speech._play(iter([np.full(100, 0.1, np.float32)]), speech._generation, time.monotonic(), True)
    speech._play(iter([np.full(100, 0.1, np.float32)]), speech._generation, time.monotonic())
    assert sounds == [True, False]
    # The App closes a turn's notice when its answer is heard: the voice tells it so.
    events: list[dict] = []
    voice = object.__new__(Voice)
    voice._write, voice._mode, voice._on_spoken, voice._answered = events.append, "wake", lambda *rest: None, 0
    voice._sounding(1.0, 1.2, False)
    assert events == [{"type": "voice.event", "event": "sound", "mode": "wake", "notice": False}]
    # The answers that sounded are counted (a feed of WAV files waits for them, voice_feed.py); the notice is not one.
    voice._sounding(1.0, 1.2, True)
    assert voice._answered == 1
