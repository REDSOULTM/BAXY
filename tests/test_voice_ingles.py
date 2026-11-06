"""BAXY's voice in English (Steam release; src/baxy_mind/voice_output.py and __main__.py): the App's voice.speak says
the language of each answer («lang»), and the answer reaches Supertonic normalized and tagged in it, every take of it;
an App that sends none is answered in Spanish as always. What the voice makes before the App asks (a foreseen take, the
turn's notice) is made in the language the App last asked for, and never said for an answer in another one. Nothing is
played and no model is loaded: a stand-in sherpa_onnx records what it is asked to say."""
import json
import pathlib
import sys
import time
import types

import numpy as np
import pytest

from baxy_mind import voice_output
from baxy_mind.speech_text import Utterance
from baxy_mind.voice_output import Speech, clause_cut

RECIPE = {"lang": "es", "steps": 6, "speed": 1.0, "seed": 7}  # no «shift»: nothing to resample


class _Tts:
    sample_rate = 44100

    def __init__(self, asked: list) -> None:
        self.asked = asked

    def generate(self, text: str, config: object) -> types.SimpleNamespace:
        self.asked.append((text, dict(config.extra)))
        t = np.arange(self.sample_rate // 10) / self.sample_rate
        return types.SimpleNamespace(samples=(0.5 * np.sin(2 * np.pi * 220 * t)).tolist())


def _sherpa(asked: list) -> types.ModuleType:
    module = types.ModuleType("sherpa_onnx")
    module.GenerationConfig = type("GenerationConfig", (), {"sid": 0, "num_steps": 0, "speed": 1.0, "extra": {}})
    for name in ("OfflineTtsConfig", "OfflineTtsModelConfig", "OfflineTtsSupertonicModelConfig"):
        setattr(module, name, lambda **_kw: None)
    module.OfflineTts = lambda _config: _Tts(asked)
    return module


def _voice(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, asked: list, played: list) -> Speech:
    for name in voice_output._MODEL_FILES:
        (tmp_path / name).write_bytes(b"")
    (tmp_path / "baxy-voice.json").write_text(json.dumps(RECIPE), encoding="utf-8")
    monkeypatch.setenv("BAXY_RENEW_TTS_DIR", str(tmp_path))
    monkeypatch.setitem(sys.modules, "sherpa_onnx", _sherpa(asked))
    monkeypatch.setattr(Speech, "_play", lambda self, audio, generation, queued, *rest: played.append(list(audio)))
    speech = Speech(lambda speaking: None, lambda *spoken: None)
    assert speech._ready.wait(30) and not speech.failure, speech.failure
    asked.clear()  # the load's own «Hola.»
    return speech


def _until(condition, seconds: float = 10) -> None:
    deadline = time.monotonic() + seconds
    while not condition() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert condition()


def test_an_english_answer_reaches_supertonic_in_english_every_take_of_it(
        tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    asked: list = []
    played: list = []
    speech = _voice(tmp_path, monkeypatch, asked, played)
    try:
        # a first sentence cut at its clause, then the next one
        assert speech.speak(Utterance("I opened the report you asked for, and it is 21 °C outside at 10:30. "
                                      "Dr. Lee wrote to ana@example.com.", "en"))
        _until(lambda: len(played) == 1)
        assert asked == [
            ("I opened the report you asked for,", {"lang": "en", "seed": "7"}),
            ("and it is twenty one degrees Celsius outside at ten thirty.", {"lang": "en", "seed": "7"}),
            ("Doctor Lee wrote to ana at example.com.", {"lang": "en", "seed": "7"}),
        ]
        # a short opener is said with the sentence after it, in English too
        assert speech.speak(Utterance("Done. It costs $4.99.", "en"))
        _until(lambda: len(played) == 2)
        assert asked[3:] == [("Done. It costs four dollars and ninety nine cents.", {"lang": "en", "seed": "7"})]
    finally:
        speech.close()


@pytest.mark.parametrize("text", ["Son las 10:30.", Utterance("Son las 10:30.", None), Utterance("Son las 10:30.", "fr")])
def test_an_answer_with_no_language_or_an_unknown_one_is_spanish_as_before(
        tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, text: str) -> None:
    asked: list = []
    played: list = []
    speech = _voice(tmp_path, monkeypatch, asked, played)
    try:
        assert speech.speak(text)
        _until(lambda: len(played) == 1)
        assert asked == [("Son las diez y media.", {"lang": "es", "seed": "7"})]
    finally:
        speech.close()


def test_a_take_foreseen_in_one_language_is_never_said_for_an_answer_in_another(
        tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    asked: list = []
    played: list = []
    speech = _voice(tmp_path, monkeypatch, asked, played)
    try:
        reply = "Done."  # too short to settle its language: the App's tag says it
        assert speech.foresee(reply, True)  # before any voice.speak the App's tag is Spanish
        _until(lambda: len(asked) == 1)
        assert speech.speak(Utterance(reply, "en"))
        _until(lambda: len(played) == 1)
        assert asked == [(reply, {"lang": "es", "seed": "7"}), (reply, {"lang": "en", "seed": "7"})]
        # a text that settles its language is foreseen in it whatever the App tagged, and its answer is said from
        # that take
        asked.clear()
        assert speech.foresee("La música ya está sonando en Spotify.", True)
        _until(lambda: len(asked) == 1)
        assert speech.speak(Utterance("La música ya está sonando en Spotify.", "en"))
        _until(lambda: len(played) == 2)
        assert asked == [("La música ya está sonando en Espótifai.", {"lang": "es", "seed": "7"})]
    finally:
        speech.close()


def test_a_notice_made_in_another_language_is_not_said(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    asked: list = []
    played: list = []
    speech = _voice(tmp_path, monkeypatch, asked, played)
    try:
        speech.set_notice("One moment.").result(10)  # made in Spanish: the App has not spoken English yet
        assert not speech.speak(Utterance("One moment.", "en"), notice=True)
        assert speech.speak(Utterance("Hello.", "en"))
        _until(lambda: len(played) == 1)
        asked.clear()
        speech.set_notice("One moment.").result(10)
        assert asked == [("One moment.", {"lang": "en", "seed": "7"})]
        assert speech.speak(Utterance("One moment.", "en"), notice=True)
    finally:
        speech.close()


def test_number_words_are_a_list_only_in_their_own_language() -> None:
    assert clause_cut("You can pick from one, two or three of the saved playlists today.", "en") is None
    sentence = "I opened the report you asked for, and it is on your desktop now."
    assert clause_cut(sentence, "en") == sentence.index(",") + 1
    # review 2026-11-04: Spanish is cut as before, after «One,» too
    spanish = "Instalé el juego en tu Xbox One, y quedó listo para jugar esta noche."
    assert clause_cut(spanish) == spanish.index(",") + 1
    assert clause_cut("Puedes elegir uno, dos o tres de las listas guardadas hoy.") is None


# --- the App's voice.speak (src/baxy_mind/__main__.py) ---------------------------------------------------------------

@pytest.mark.parametrize(("text", "message", "lang", "said"), [
    ("OK, 10:30.", {"lang": "en"}, "en", "OK, ten thirty."),            # too short to settle: the App's tag
    ("OK, 10:30.", {"lang": "en-US"}, "en", "OK, ten thirty."),
    ("OK, 10:30.", {}, "es", "OK, diez y media."),                      # an App from before English: Spanish
    ("OK, 10:30.", {"lang": "de"}, "es", "OK, diez y media."),
    # review 2026-11-04: a Spanish answer on an English interface is said in Spanish («1.500» was one point five...)
    ("Son 1.500 pesos chilenos.", {"lang": "en"}, "es", "Son mil quinientos pesos chilenos."),
    ("It costs $1,500 in total.", {}, "en", "It costs one thousand five hundred dollars in total."),
])
def test_voice_speak_s_language_reaches_the_synthesis(
        tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, text: str, message: dict, lang: str, said: str) -> None:
    from baxy_mind import __main__ as sidecar
    asked: list = []
    played: list = []
    (tmp_path / "voz").mkdir()
    speech = _voice(tmp_path / "voz", monkeypatch, asked, played)  # closed by the sidecar when the App leaves
    incoming = [{"type": "voice.speak", "id": 1, "text": text, **message}, None]
    written: list[dict] = []

    def read_message():
        if incoming[0] is None:
            _until(lambda: len(played) == 1)  # the App closes once the answer has sounded
        return incoming.pop(0)

    class FakeServer:
        REQUEST_SECONDS = 24.0
        name = "model.gguf"
        deadline = None

        def __init__(self, *args, **kwargs) -> None:
            pass

        start = close = lambda self: None

    class FakeMind:
        notice = ""
        foresee = None
        gave_way = None

        def __init__(self, *args) -> None:
            pass

    class FakeVoice:
        def __init__(self, *args, **kwargs) -> None:
            self.speech = speech

        def stop(self) -> None:
            pass

    monkeypatch.setenv("BAXY_MIND_LLM_GGUF", "model.gguf")
    monkeypatch.setenv("BAXY_MIND_LLAMA_SERVER", "its-server.exe")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.delenv("BAXY_S1_GGUF", raising=False)
    monkeypatch.setattr(sidecar, "declared_build", lambda path: "b11609")  # the server is a fake
    monkeypatch.setattr(sidecar, "LlmServer", FakeServer)
    monkeypatch.setattr(sidecar, "Mind", FakeMind)
    monkeypatch.setattr(sidecar, "Voice", FakeVoice)
    monkeypatch.setattr(sidecar.protocol, "read_message", read_message)
    monkeypatch.setattr(sidecar.protocol, "write_message", written.append)
    assert sidecar.main() == 0
    result = next(reply for reply in written if reply["type"] == "voice.speak.result")
    assert result["accepted"] is True
    assert asked == [(said, {"lang": lang, "seed": "7"})]


def test_a_turn_that_says_its_language_first_has_its_answer_foreseen_and_its_notice_made_in_it(
        tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    asked: list = []
    played: list = []
    speech = _voice(tmp_path, monkeypatch, asked, played)
    try:
        speech.speak_in("en")  # the session's first turn.decide, before any voice.speak
        speech.set_notice("One moment.").result(10)
        assert speech.foresee("The music is playing.", True)
        _until(lambda: len(asked) == 2)
        assert speech.speak(Utterance("One moment.", "en"), notice=True)
        _until(lambda: len(played) == 1)  # said before the answer is given: an answer given first drops it
        assert speech.speak(Utterance("The music is playing.", "en"))
        _until(lambda: len(played) == 2)
        # the answer is said from its foreseen take: nothing synthesized again, all of it in English
        assert asked == [("One moment.", {"lang": "en", "seed": "7"}), ("The music is playing.", {"lang": "en", "seed": "7"})]
    finally:
        speech.close()


@pytest.mark.parametrize(("lang", "told"), [("en", ["en", "en"]), (None, [])])
def test_turn_decide_and_turn_notice_tell_the_voice_their_language_and_never_the_model(
        tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, lang: str | None, told: list) -> None:
    from concurrent.futures import Future

    from baxy_mind import __main__ as sidecar
    tagged = {"lang": lang} if lang else {}
    incoming = [{"type": "turn.decide", "id": 1, "text": "play some music", **tagged},
                {"type": "turn.notice", "id": 2, **tagged}, None]
    seen: list = []  # (what the mind was given, the voice's language then)

    class FakeServer:
        REQUEST_SECONDS = 24.0
        name = "model.gguf"
        deadline = None

        def __init__(self, *args, **kwargs) -> None:
            pass

        start = close = lambda self: None

    class FakeSpeech:
        failure = ""
        ready = True

        def __init__(self) -> None:
            self.lang = "es"
            self.told: list = []

        def speak_in(self, tag) -> None:
            self.told.append(tag)
            self.lang = tag

        def foresee(self, text, done):
            return True

        def prepare(self) -> None:
            pass

        def set_notice(self, text: str) -> Future:
            seen.append((("notice", text), self.lang))
            done: Future = Future()
            done.set_result(None)
            return done

        def close(self) -> None:
            pass

    speech = FakeSpeech()

    class FakeMind:
        notice = ""
        foresee = None
        gave_way = None

        def __init__(self, *args) -> None:
            pass

        notices_are_slow = False

        def decide(self, *given):
            seen.append((given, speech.lang))
            return {"type": "turn.result", "id": given[0]}

        def notice_of(self) -> str:
            return "One moment."

    class FakeVoice:
        def __init__(self, *args, **kwargs) -> None:
            self.speech = speech

        def unsure(self, text: str) -> list:
            return []

        def stop(self) -> None:
            pass

    monkeypatch.setenv("BAXY_MIND_LLM_GGUF", "model.gguf")
    monkeypatch.setenv("BAXY_MIND_LLAMA_SERVER", "its-server.exe")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.delenv("BAXY_S1_GGUF", raising=False)
    monkeypatch.setattr(sidecar, "declared_build", lambda path: "b11609")  # the server is a fake
    monkeypatch.setattr(sidecar, "LlmServer", FakeServer)
    monkeypatch.setattr(sidecar, "Mind", FakeMind)
    monkeypatch.setattr(sidecar, "Voice", FakeVoice)

    def read_message():
        if incoming[0] is None:
            _until(lambda: len(seen) == 2)  # the App leaves once the notice is made: a request waiting would skip it
        return incoming.pop(0)

    monkeypatch.setattr(sidecar.protocol, "read_message", read_message)
    monkeypatch.setattr(sidecar.protocol, "write_message", lambda message: None)
    assert sidecar.main() == 0
    assert speech.told == told
    voice_lang = lang or "es"
    # the mind is given the text alone, as without the field: «lang» never reaches the model's prompt
    assert seen == [((1, "play some music", None, [], None, None), voice_lang), (("notice", "One moment."), voice_lang)]


def test_a_notice_is_made_in_its_own_language_whatever_the_app_tagged(
        tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    asked: list = []
    played: list = []
    speech = _voice(tmp_path, monkeypatch, asked, played)
    try:
        speech.speak_in("en")  # an English interface, a person who speaks Spanish: the model's notice is Spanish
        speech.set_notice("Un momento, reviso tu correo.").result(10)
        assert asked == [("Un momento, reviso tu correo.", {"lang": "es", "seed": "7"})]
        assert speech.speak(Utterance("Un momento, reviso tu correo.", "en"), notice=True)
    finally:
        speech.close()
