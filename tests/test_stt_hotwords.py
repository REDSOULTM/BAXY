"""The ear's hotwords (src/baxy_mind/stt_hotwords.py, voice.py): the installed applications and games the model is
shown become sherpa-onnx hotwords segmented as Parakeet writes them, and the recognizer is built with them. No audio
device and no model: tokens.txt is a small one written here, sherpa a stand-in."""
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from baxy_mind import stt_hotwords, voice
from baxy_mind.voice import Voice
from test_mind_final import _mind

# A SentencePiece-like tokens.txt: meta pieces first, merged pieces in the order they were made, then the characters.
PIECES = ["<unk>", "<|nospeech|>", "<pad>", "▁S", "am", "te", "▁Ste", "▁de", "ot", "if", "▁Spot", "or", "ms", "▁W",
          "lo", "▁b", "▁blo", "as", "▁not", "▁B", "▁Bl", "oc", "▁Bloc", "▁a",
          "▁", "S", "t", "e", "a", "m", "p", "o", "i", "f", "y", "d", "W", "r", "s", "b", "l", "c", "n", "B", "E", "A",
          "<blk>"]
TOKENS = "".join(f"{piece} {i}\n" for i, piece in enumerate(PIECES))


def _scores(vocab: str) -> dict[str, float]:
    return {line.split("\t")[0]: float(line.split("\t")[1]) for line in vocab.splitlines()}


def test_a_word_is_segmented_as_bpe_makes_it_the_earliest_merge_first() -> None:
    tokenizer = stt_hotwords.Tokenizer(TOKENS)
    assert tokenizer.word("Steam") == ["▁Ste", "am"]
    assert tokenizer.word("Spotify") == ["▁S", "p", "ot", "if", "y"]  # no «▁Sp»: «▁Spot» is never reached
    assert tokenizer.word("Worms") == ["▁W", "or", "ms"]
    assert tokenizer.word("Zelda") is None  # a character the model never writes


def test_names_become_the_words_the_model_writes() -> None:
    forms, _ = stt_hotwords.compile_hotwords(
        ["Steam™", "Spotify (64-bit)", "Worms 2026 R1", "Bloc de notas", "BAESAMS", "Steam", "Ba", "Steam 2"], TOKENS)
    # Trademarks, parentheses and versions go; a Spanish name also goes lowercase; a word in capitals also as the model
    # writes it (and only so here: this tokens.txt has no «M»); two letters or a number inside are not biased; once each.
    assert forms == ["Steam", "Spotify", "Worms", "Bloc de notas", "bloc de notas", "Baesams"]


def test_sherpa_markers_never_reach_a_hotword_line() -> None:
    forms, _ = stt_hotwords.compile_hotwords(["Steam:Worms", "Spotify/Steam", "Worms #1", "Steam @home"], TOKENS)
    assert forms and not any(mark in form for form in forms for mark in ":/#@")


def test_the_vocab_makes_sherpa_segment_every_form_as_the_model_writes_it() -> None:
    forms, vocab = stt_hotwords.compile_hotwords(["Steam", "Spotify", "Worms", "Bloc de notas", "Stem"], TOKENS)
    scores = _scores(vocab)
    tokenizer = stt_hotwords.Tokenizer(TOKENS)
    assert set(scores) == {p for form in forms for w in form.split() for p in tokenizer.word(w)}
    for form in forms:
        for word in form.split():
            assert stt_hotwords.viterbi(scores, word) == tokenizer.word(word)


def test_equal_scores_would_segment_a_name_another_way_and_the_fit_corrects_it() -> None:
    tokens = "".join(f"{p} {i}\n" for i, p in enumerate(["<unk>", "▁a", "▁ab", "bc", "▁", "a", "b", "c", "d"]))
    tokenizer = stt_hotwords.Tokenizer(tokens)
    assert tokenizer.word("abc") == ["▁ab", "c"]
    # With every piece at -1, sherpa would write «abc» as «▁a bc», the pieces of «a» and «dbc».
    assert stt_hotwords.viterbi({p: -1.0 for p in ["▁a", "▁ab", "bc", "▁", "c", "d"]}, "abc") == ["▁a", "bc"]
    forms, vocab = stt_hotwords.compile_hotwords(["abc", "a dbc"], tokens)
    assert forms == ["abc", "a dbc"]
    assert stt_hotwords.viterbi(_scores(vocab), "abc") == ["▁ab", "c"]


def test_the_stream_string_carries_each_hotword_with_its_score() -> None:
    assert stt_hotwords.stream_hotwords(["Steam", "bloc de notas"], 1.5) == "Steam :1.5/bloc de notas :1.5"


def test_configure_keeps_the_names_the_model_is_shown(tmp_path: Path) -> None:
    mind, _ = _mind(tmp_path, [])
    mind.configure({"capabilities": [], "applicationCatalog": {"names": ["Steam", "Uninstall Foo", "Bloc de notas"]},
                    "gameCatalog": {"entries": [{"name": "Worms W.M.D", "appId": "1"}, {"appId": "2"}]}})
    assert mind.names == ["Steam", "Bloc de notas", "Worms W.M.D"]


class _Recognizer:
    built: list[dict] = []

    def __init__(self, **options) -> None:
        self.options = options
        vocab = options.get("bpe_vocab")
        self.vocab = Path(vocab).read_text(encoding="utf-8") if vocab else None  # read while it is built, as sherpa
        self.hotwords: list[str | None] = []

    @classmethod
    def from_transducer(cls, **options) -> "_Recognizer":
        made = cls(**options)
        cls.built.append(options)
        return made

    def create_stream(self, hotwords: str | None = None) -> SimpleNamespace:
        self.hotwords.append(hotwords)
        return SimpleNamespace(accept_waveform=lambda *_: None, result=None)

    def decode_stream(self, stream) -> None:
        stream.result = SimpleNamespace(text=" Abre Steam.", tokens=[], timestamps=[])


def _stt(tmp_path: Path) -> Path:
    (tmp_path / "tokens.txt").write_text(TOKENS, encoding="utf-8")
    return tmp_path


def _voice(monkeypatch: pytest.MonkeyPatch) -> Voice:
    monkeypatch.setattr(Voice, "_load", lambda self: self._loaded.set())
    monkeypatch.setattr(voice, "Speech", lambda *_: SimpleNamespace(speaking=False, ready=False))
    return Voice(lambda _message: None)


def test_the_recognizer_is_built_with_the_names_as_hotwords(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("BAXY_RENEW_STT_HOTWORDS", raising=False)
    listening = _voice(monkeypatch)
    listening.hear_names(["Steam", "Spotify"])
    listening._recognize(SimpleNamespace(OfflineRecognizer=_Recognizer), _stt(tmp_path))
    recognizer = listening._recognizer
    assert recognizer.options["decoding_method"] == "modified_beam_search"
    assert recognizer.options["modeling_unit"] == "bpe" and "▁Ste\t" in recognizer.vocab
    assert not Path(recognizer.options["bpe_vocab"]).exists()  # a temporary file, gone once sherpa read it
    assert listening._transcribe(np.full(16000, 0.1, np.float32), None) == "Abre Steam."
    assert recognizer.hotwords == [f"Steam :{voice.HOTWORDS_SCORE:g}/Spotify :{voice.HOTWORDS_SCORE:g}"]


def test_without_names_or_with_the_hotwords_off_it_is_today_s_greedy_recognizer(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(voice, "NAMES_WAIT_S", 0.01)
    listening = _voice(monkeypatch)
    listening._recognize(SimpleNamespace(OfflineRecognizer=_Recognizer), _stt(tmp_path))  # no catalog.configure
    assert listening._recognizer.options["decoding_method"] == "greedy_search"
    monkeypatch.setenv("BAXY_RENEW_STT_HOTWORDS", "0")
    listening = _voice(monkeypatch)
    listening.hear_names(["Steam"])
    listening._recognize(SimpleNamespace(OfflineRecognizer=_Recognizer), _stt(tmp_path))
    assert listening._recognizer.options["decoding_method"] == "greedy_search"
    listening._transcribe(np.full(16000, 0.1, np.float32), None)
    assert listening._recognizer.hotwords == [None]


def test_names_after_the_first_are_not_taken(monkeypatch: pytest.MonkeyPatch) -> None:
    listening = _voice(monkeypatch)
    listening.hear_names(["Steam"])
    listening.hear_names(["Spotify"])
    assert listening._names == ["Steam"]
