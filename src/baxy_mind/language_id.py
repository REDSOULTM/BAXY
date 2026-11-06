"""Which language an answer is in, Spanish or English, so the voice says it in its own (review 2026-11-04: on an
English Windows a Spanish answer was read with English rules, «1.500 pesos» as one point five zero zero pesos).

langid.py (Lui & Baldwin 2012, «langid.py: An Off-the-shelf Language Identification Tool», ACL demo): a multinomial
naive Bayes over byte n-grams picked across domains, trained on 97 languages. Its model is vendored unchanged from
py3langid 0.3.0 (Adrien Barbaresi's maintained fork, BSD-3-Clause, data/langid/LICENSE and PROVENANCE.txt); the
classification below is langid.py's own (instance2fv, nb_classprobs, the log-sum-exp normalization) restricted to
«es» and «en», as its set_languages does, without the fork's web service and command line. The pickle holds only lists,
a dict and two arrays of the standard library: it is read with an unpickler that refuses any other class.

Below SURE the text does not settle it («Listo.», «OK.», «Done.»), and the language the App tagged is kept: the
interface's. Measured 2026-11-04 on 84 replies written with this file (tests/data/language_id_replies.v1.json) and 120
held out, written by a subagent that saw neither this file nor its threshold (language_id_heldout.v1.json), half in
each language: a reply whose n-grams the model does not know scores its prior, 0.661-0.664, and every other one at
least 0.858; SURE sits in that gap (anything from 0.67 to 0.80 gives the same answers). Said in the right language,
with the App tagging Spanish / English: 80/84 / 81/84 and 108/120 / 115/120 (the App's tag alone: 42/84 and 60/120
either way); the rest are short replies left to the tag, and three Spanish ones made of English names and one or two
Spanish words («Le di skip.», «The Weeknd, Blinding Lights, en Spotify Premium.») read as English. A minimum of
letters only lost answers («Sí.», «It is 10:30.» score 1.0) and was not kept.
"""
from __future__ import annotations

import lzma
import math
import pickle
from collections import Counter
from functools import lru_cache
from pathlib import Path

import numpy as np

MODEL = Path(__file__).with_name("data") / "langid" / "model.plzma"
LANGS = ("es", "en")
SURE = 0.8  # measured: see the module's docstring


class _Arrays(pickle.Unpickler):
    """The model's pickle: data and the standard library's arrays, nothing else."""

    def find_class(self, module: str, name: str):
        if module == "array" and name in ("array", "_array_reconstructor"):
            return super().find_class(module, name)
        raise pickle.UnpicklingError(f"langid model: {module}.{name} refused")


@lru_cache(maxsize=1)
def _model() -> tuple[np.ndarray, np.ndarray, object, dict]:
    with lzma.open(MODEL) as handle:
        nb_ptc, nb_pc, nb_classes, tk_nextmove, tk_output = _Arrays(handle).load()
    columns = [nb_classes.index(lang) for lang in LANGS]
    ptc = np.array(nb_ptc).reshape(len(nb_ptc) // len(nb_pc), len(nb_pc))[:, columns]
    return ptc, np.array(nb_pc)[columns], tk_nextmove, tk_output


def load() -> None:
    """Reads the model now (0.35-0.52 s on the PC), so the first answer does not wait for it."""
    _model()


def identify(text: str) -> tuple[str, float]:
    """(«es» or «en», its probability against the other one)."""
    ptc, pc, nextmove, output = _model()
    state, features = 0, []
    for byte in text.encode("utf-8", errors="surrogatepass"):
        state = nextmove[(state << 8) + byte]
        features.extend(output.get(state, ()))
    vector = np.zeros(ptc.shape[0], dtype=np.uint16)
    for index, count in Counter(features).items():
        vector[index] = count
    scores = vector @ ptc + pc
    best = int(np.argmax(scores))
    return LANGS[best], 1.0 / (1.0 + math.exp(float(scores[1 - best] - scores[best])))


def said_in(text: str, tagged: str) -> str:
    """The language text is said in: its own when the text settles it, else the one the App tagged."""
    lang, sure = identify(text)
    return lang if sure >= SURE else tagged
