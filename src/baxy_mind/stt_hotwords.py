"""The names the ear is biased towards: the installed applications and games the model is shown (catalog.configure),
as sherpa-onnx hotwords for Parakeet Ultra's beam search.

A hotword biases a path of tokens, so it has to be the path the model writes. sherpa-onnx makes that path itself:
with the default modeling unit («cjkchar») it splits «▁» from the letters (TranscripcionBaxy, 2026-10-09: «▁Ste am»
is refused, «▁B a x y» biases 5 tokens the model never writes); with «bpe» it segments each word by the best sum of
the scores in a bpe_vocab file (simple-sentencepiece). Ultra ships no vocab, and no scores make that sum reproduce
SentencePiece BPE for every word (from tokens.txt: 298 of 524 forms of the PC's catalog at best, 2026-10-23). So the
segmentation is made here as the model's tokenizer makes it (BPE: merge, again and again, the adjacent pair whose
piece came first; the pieces of tokens.txt are in that order, and it matches the model's tokenizer.json in every
form kept), and the vocab sherpa reads holds only the pieces of those segmentations: a form whose segmentation
sherpa would not find there is left out.

A name becomes the words the model would write for it: what is not a word («™», «(64-bit)», «2026 R1», «v1.8», «:»)
is dropped, a word in capitals also goes as the model writes it («HELLDIVERS» → «Helldivers»), and a name written
as a Spanish sentence also goes lowercase («Bloc de notas» → «bloc de notas», as it is said mid-sentence).
"""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

# What sherpa's hotword line reads as a marker (EncodeBase: «:score», «#threshold», «@phrase») or a separator («/»),
# and the symbols no name is said with.
_NOT_A_WORD = re.compile(r"[^\w\s'’&.-]|_")
_VERSION = re.compile(r"^(?:v?\d[\d.]*|r\d+|x(?:64|86)|\d+-bit)$", re.IGNORECASE)
_PARENTHESES = re.compile(r"\([^)]*\)|\[[^]]*\]")
MAX_WORDS = 5
WORD_START = "▁"


def _words(name: str) -> list[str]:
    name = _PARENTHESES.sub(" ", unicodedata.normalize("NFC", name))
    words = [w.strip(".-'’") for w in _NOT_A_WORD.sub(" ", name).split()]
    words = [w for w in words if w and any(c.isalnum() for c in w)]
    while words and _VERSION.match(words[-1]):
        words.pop()
    return words


def _forms(words: list[str]) -> list[str]:
    written = " ".join(words)
    titled = " ".join(w.capitalize() if len(w) >= 5 and w.isupper() and w.isalpha() else w for w in words)
    forms = [written, titled]
    if len(words) > 1 and words[0][:1].isupper() and words[0][1:].islower() and all(w.islower() for w in words[1:]):
        forms.append(written.lower())
    return list(dict.fromkeys(forms))


class Tokenizer:
    """SentencePiece BPE from tokens.txt alone («piece id» per line; ids in the order the pieces were made)."""

    def __init__(self, tokens: str) -> None:
        self.ids: dict[str, int] = {}
        for line in tokens.splitlines():
            piece, _, token_id = line.rpartition(" ")
            if piece and token_id.isdigit() and not (len(piece) > 2 and piece[0] == "<" and piece[-1] == ">"):
                self.ids[piece] = int(token_id)

    def word(self, word: str) -> list[str] | None:
        symbols = list(WORD_START + word)
        if any(s not in self.ids for s in symbols[1:]):
            return None  # a character the model never writes
        while True:
            best = None
            for k in range(len(symbols) - 1):
                merged = self.ids.get(symbols[k] + symbols[k + 1])
                if merged is not None and (best is None or merged < best[0]):
                    best = (merged, k)
            if best is None:
                return symbols if all(s in self.ids for s in symbols) else None
            k = best[1]
            symbols[k:k + 2] = [symbols[k] + symbols[k + 1]]


def viterbi(scores: dict[str, float], word: str) -> list[str] | None:
    """simple-sentencepiece's Encode (v0.7: GetDag + CalcDp + Cut) as sherpa runs it on one word of a hotword: the
    pieces of «▁word» with the best sum of scores, a tie to the shorter piece at the end."""
    text = (WORD_START + word).encode("utf-8")
    pieces = {p.encode("utf-8"): p for p in scores}
    longest = max((len(b) for b in pieces), default=0)
    n = len(text)
    best: list[tuple[float, int, str] | None] = [None] * (n + 1)
    best[n] = (0.0, 0, "")
    for i in range(n - 1, -1, -1):
        top: tuple[float, int, str] | None = None
        for j in range(i + 1, min(n, i + longest) + 1):
            piece, after = pieces.get(text[i:j]), best[j]
            if piece is None or after is None:
                continue
            total = scores[piece] + after[0]
            if top is None or total > top[0] or (total == top[0] and top[1] >= j):
                top = (total, j, piece)
        best[i] = top
    out, i = [], 0
    while i < n:
        step = best[i]
        if step is None:
            return None
        out.append(step[2])
        i = step[1]
    return out


FIT_ROUNDS = 50
FIT_STEP = 0.1


def compile_hotwords(names: Iterable[str], tokens: str) -> tuple[list[str], str]:
    """The hotword forms of the names and the bpe_vocab text that makes sherpa segment each as the model writes it.
    The vocab holds only the pieces of those segmentations; their scores start equal and are moved, a word at a time,
    towards the model's segmentation and away from the one sherpa would make (a perceptron: the PC's 645 words agree
    after 6 rounds, 0.4 s). A form with a word that still disagrees is left out."""
    tokenizer = Tokenizer(tokens)
    segmented: dict[str, list[list[str]]] = {}
    for name in names:
        words = _words(str(name))
        # «R», «EA»: a letter or two biased everywhere is not a name heard; a number inside a name («12», «3.13»)
        # is written by the model in pieces its tokenizer.json does not make the same way.
        if not words or len(words) > MAX_WORDS or sum(c.isalnum() for c in "".join(words)) < 3 \
                or any(c.isdigit() for c in "".join(words)):
            continue
        for form in _forms(words):
            pieces = [tokenizer.word(w) for w in form.split()]
            if form not in segmented and all(pieces):
                segmented[form] = pieces  # type: ignore[assignment]
    target = {w: p for form, words in segmented.items() for w, p in zip(form.split(), words)}
    scores = {p: -1.0 for pieces in target.values() for p in pieces}
    for _ in range(FIT_ROUNDS):
        wrong = 0
        for word, pieces in target.items():
            made = viterbi(scores, word)
            if made != pieces:
                wrong += 1
                for piece in pieces:
                    scores[piece] += FIT_STEP
                for piece in made or ():
                    scores[piece] -= FIT_STEP
        if not wrong:
            break
    agreed = {w for w, p in target.items() if viterbi(scores, w) == p}
    forms = [form for form in segmented if all(w in agreed for w in form.split())]
    text = "".join(f"{piece}\t{score:.6g}\n" for piece, score in sorted(scores.items(),
                                                                        key=lambda item: tokenizer.ids[item[0]]))
    return forms, text


def stream_hotwords(forms: Iterable[str], score: float) -> str:
    """The string sherpa's create_stream takes: one hotword per «/», each with its score per token."""
    return "/".join(f"{form} :{score:g}" for form in forms)
