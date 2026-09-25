"""The one normalization every reader shares.

Before Fase 3.5 the same fold lived four times (`effect_intent._fold`, `request_reading.fold`,
`llm._fold_dialogue_text`, the dialogue slot); a reader that normalized differently from its neighbour
read the same words differently. There is one now.
"""

from __future__ import annotations

import re
import unicodedata

__all__ = ["fold", "alternation", "spelled_out"]


def fold(value: object) -> str:
    """Lowercase, without diacritics, with whitespace collapsed («Súbelo  YA» → «subelo ya»)."""

    decomposed = unicodedata.normalize("NFKD", str(value or "").casefold())
    return " ".join("".join(ch for ch in decomposed if not unicodedata.combining(ch)).split())


# Tanda 7b «¿y el finde?» → «¿va a llover el fin de semana?» was rejected as words nobody said: a short or chat
# form and its full words are the same words. Folded; each short form is a whole word.
_SPELLED_OUT = {
    "finde": "fin de semana", "porfa": "por favor", "porfi": "por favor", "porfis": "por favor", "xfa": "por favor",
    "xfavor": "por favor", "tb": "tambien", "tmb": "tambien", "tambn": "tambien", "q": "que", "k": "que",
    "ke": "que", "xq": "porque", "pq": "porque", "porq": "porque", "pa": "para", "pal": "para el",
    "toy": "estoy", "ahorita": "ahora", "nomas": "no mas", "peli": "pelicula", "pelis": "peliculas",
    "compu": "computadora", "cel": "celular", "celu": "celular", "tele": "television", "msj": "mensaje",
    "dsp": "despues", "dps": "despues", "u": "you", "ur": "your", "pls": "please", "plz": "please",
    "tmrw": "tomorrow", "tmr": "tomorrow", "2morrow": "tomorrow", "2day": "today", "wknd": "weekend",
    "gonna": "going to", "wanna": "want to", "gotta": "got to", "cuz": "because", "coz": "because",
    "bc": "because", "msg": "message", "pic": "picture", "pics": "pictures",
}
_SHORT_FORM = re.compile(r"(?<![\w'])(?:" + "|".join(sorted(map(re.escape, _SPELLED_OUT), key=len, reverse=True)) + r")(?![\w'])")


def spelled_out(folded: str) -> str:
    """A folded text with its short and chat forms in full words («el finde porfa» → «el fin de semana por favor»)."""

    return _SHORT_FORM.sub(lambda found: _SPELLED_OUT[found.group(0)], folded)


def alternation(words: frozenset[str] | tuple[str, ...] | set[str]) -> str:
    """A non-capturing regex alternation of folded words, longest first so a prefix never wins early."""

    return "(?:" + "|".join(re.escape(word) for word in sorted(set(words), key=lambda w: (-len(w), w))) + ")"
