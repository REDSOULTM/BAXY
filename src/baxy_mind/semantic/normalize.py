"""The one normalization every reader shares.

Before Fase 3.5 the same fold lived four times (`effect_intent._fold`, `request_reading.fold`,
`llm._fold_dialogue_text`, the dialogue slot); a reader that normalized differently from its neighbour
read the same words differently. There is one now.
"""

from __future__ import annotations

import re
import unicodedata

__all__ = ["fold", "alternation"]


def fold(value: object) -> str:
    """Lowercase, without diacritics, with whitespace collapsed («Súbelo  YA» → «subelo ya»)."""

    decomposed = unicodedata.normalize("NFKD", str(value or "").casefold())
    return " ".join("".join(ch for ch in decomposed if not unicodedata.combining(ch)).split())


def alternation(words: frozenset[str] | tuple[str, ...] | set[str]) -> str:
    """A non-capturing regex alternation of folded words, longest first so a prefix never wins early."""

    return "(?:" + "|".join(re.escape(word) for word in sorted(set(words), key=lambda w: (-len(w), w))) + ")"
