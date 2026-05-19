"""RapidFuzz post-corrector against domain inventory.

The killer feature from the research report. Whisper-small with
`language='es'` will phoneticise English nouns ("Chrome" -> "Aurekrom",
"Benson Boone" -> "Benson Mould"). Re-training Whisper to handle this
is out of scope (CPU-only constraint, multi-user). Instead, we do
DETERMINISTIC fuzzy-matching of the raw Whisper output against a
finite set of known entities (apps, artists, songs, verbs).

Algorithm:
  1. Tokenise the Whisper output (whitespace).
  2. For each position, try 1-, 2-, and 3-gram windows.
  3. For each window, RapidFuzz.process.extractOne against EVERY
     category in the inventory (accent-stripped, lowercased).
  4. If any match scores ≥ THRESHOLD (default 78), replace the window
     with the canonical form and advance the cursor by the gram size.
  5. Otherwise, keep the original token and advance by 1.

Properties:
  - Deterministic: same input → same output (regression-testable).
  - Bounded latency: O(N * M) where N = transcript tokens, M = inventory
    size. With M < 200, runs in single-digit milliseconds.
  - Conservative: keeps original token unless a CLEAR fuzzy match exists.
    Threshold 78 is the operating point recommended in the research
    report. Lower → over-correction. Higher → misses good corrections.

Inspired by commercial Alexa/Google personalized entity resolution.
"""
from __future__ import annotations

import logging
import unicodedata
from typing import Sequence

logger = logging.getLogger(__name__)


# Match threshold (0-100). Below this, we keep the original token.
# Research report recommended 78 but empirical testing shows that's
# too strict for phonetic mistranscriptions:
#   'aurekrom' vs 'chrome' = 43 (Whisper's mistranscription score)
#   'benson mould' vs 'benson boone' = 66
#   'cross' vs 'chrome' = 55
# These are string-edit distances. Phonetic similarity (Metaphone/
# Soundex) would catch them better; that's a future enhancement.
# For now we use 65 to catch obvious-but-not-identical cases like
# 'Mould -> Boone' while leaving truly distant tokens alone.
DEFAULT_THRESHOLD = 65


def _normalise(s: str) -> str:
    """Lowercase + strip accents/diacritics, for fair comparison."""
    s = s.lower()
    s = "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )
    return s


class FuzzyCorrector:
    """Stateless. Constructed once with an inventory; reused across turns."""

    def __init__(
        self,
        inventory: dict[str, list[str]],
        threshold: int = DEFAULT_THRESHOLD,
    ) -> None:
        self._inventory = inventory
        self._threshold = threshold
        # Pre-normalize each category for fast comparison. We keep the
        # original strings to return canonical replacements.
        self._normalized: dict[str, list[tuple[str, str]]] = {}
        for cat, items in inventory.items():
            self._normalized[cat] = [(_normalise(x), x) for x in items]

    def correct(self, transcript: str) -> str:
        """Apply fuzzy correction to a Whisper raw transcript.

        Algorithm:
          For each position i, try ALL n-gram windows (3, 2, 1).
          For each window+inventory-item pair, compute the match score.
          Pick the window-replacement-size triple that maximizes score,
          BUT require the match to actually cover the window (no
          replacing 2 tokens with 1 unless the 2-gram is a near-perfect
          match to the candidate).
        """
        try:
            from rapidfuzz import fuzz
        except ImportError as exc:
            logger.warning(
                "rapidfuzz unavailable; correction disabled: %s", exc,
            )
            return transcript

        tokens = transcript.split()
        out: list[str] = []
        i = 0
        n = len(tokens)
        while i < n:
            best_replacement: str = tokens[i]
            best_score: float = 0
            best_size: int = 1
            for ngram in (3, 2, 1):
                if i + ngram > n:
                    continue
                window = " ".join(tokens[i:i + ngram])
                window_norm = _normalise(window)
                for cat, normalized_items in self._normalized.items():
                    for norm_item, orig_item in normalized_items:
                        # Use fuzz.ratio for symmetric string distance.
                        score = fuzz.ratio(window_norm, norm_item)
                        # Length penalty: if window and candidate have
                        # very different lengths, the score is inflated
                        # by partial overlap (e.g. 'abre chrome' partly
                        # matches 'chrome' because 'chrome' is in there).
                        # Penalize so a 1-gram clean match beats a 2-gram
                        # partial match.
                        len_diff = abs(len(window_norm) - len(norm_item))
                        len_max = max(len(window_norm), len(norm_item), 1)
                        coverage = 1.0 - (len_diff / len_max)
                        adjusted = score * coverage
                        # Threshold applies AFTER coverage adjustment so
                        # length-mismatched partial overlaps don't sneak
                        # in via inflated raw scores.
                        if adjusted < self._threshold:
                            continue
                        if adjusted > best_score:
                            best_score = adjusted
                            best_replacement = orig_item
                            best_size = ngram
            out.append(best_replacement)
            i += best_size
        return " ".join(out)

    def strip_wake_phrase(self, transcript: str) -> str:
        """Remove a leading wake phrase from the transcript.

        The wake detector fires when 'hey gemma' is heard. Whisper then
        often transcribes the wake phrase too (because the audio clip
        captured by the state machine includes the wake). The LLM
        downstream doesn't need it as input.

        Returns the transcript with wake-word prefix stripped, if found
        in the first ~3 tokens. Otherwise returns the transcript intact.
        """
        wake_words = self._inventory.get("wake_words", [])
        if not wake_words:
            return transcript
        tokens = transcript.split()
        if not tokens:
            return ""
        # Try to match the first 1-3 tokens against any known wake phrase.
        for ngram in (3, 2, 1):
            if ngram > len(tokens):
                continue
            prefix = " ".join(tokens[:ngram])
            prefix_norm = _normalise(prefix)
            for wake in wake_words:
                if _normalise(wake) == prefix_norm:
                    return " ".join(tokens[ngram:])
        return transcript
