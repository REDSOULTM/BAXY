"""Pure CTC primitives for a fail-closed BAXY wake-word verifier.

The first-stage detector is allowed to be permissive.  This module supplies
the second-stage comparison: it scores an exact BAXY pronunciation against
explicit confusable pronunciations over the same acoustic span.  It never
uses edit-distance acceptance, because a one-phoneme substitution is exactly
the distinction between BAXY and names such as Vaxi, Faxi, or Bakshi.

Heavy acoustic-model loading intentionally lives in experiment runners.  The
dynamic program and lexical proposal parser stay NumPy-only so their safety
contract can be unit tested in the normal repository test environment.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
import math
import re
import unicodedata

import numpy as np


# Every pronunciation below is an exact, development-backed rendering.  The
# English final /I/, Russian palatalized /sʲ/, and Spanish beta/tap variants
# close observed human misses without permitting a consonant substitution.
TARGET_SEQUENCES: tuple[tuple[str, ...], ...] = (
    ("b", "a", "k", "s", "i"),
    ("b", "æ", "k", "s", "i"),
    ("b", "æ", "k", "s", "ɪ"),
    ("b", "ɑ", "k", "s", "i"),
    ("b", "a", "k", "sʲ", "i"),
    ("b", "ɑ", "k", "sʲ", "i"),
    ("b", "ʌ", "k", "sʲ", "i"),
    ("b", "a", "ɾ", "k", "s", "i"),
    ("β", "a", "k", "s", "i"),
    ("β", "a", "ɾ", "k", "s", "i"),
)


def _confusable_sequences() -> tuple[tuple[str, ...], ...]:
    vowels = ("a", "æ", "ɑ", "ʌ")
    sibilants = ("s", "sʲ")
    endings = ("i", "ɪ")
    values: list[tuple[str, ...]] = []
    for initial in ("v", "f", "p"):
        for vowel in vowels:
            for sibilant in sibilants:
                for ending in endings:
                    values.append((initial, vowel, "k", sibilant, ending))
    for initial in ("b", "β"):
        for vowel in vowels:
            for ending in endings:
                values.append((initial, vowel, "k", "ʃ", ending))
    return tuple(values)


CONFUSABLE_SEQUENCES = _confusable_sequences()

# These are proposal spellings, not acceptance spellings.  A liberal lexical
# proposal only spends verifier compute; it never authorizes a turn itself.
LEXICAL_PROPOSAL_PREFIXES = (
    "baxy",
    "baxi",
    "basi",
    "bakse",
    "бакси",
    "баксе",
)


def encode_sequences(
    vocab: dict[str, int],
    sequences: Iterable[Sequence[str]],
) -> tuple[tuple[int, ...], ...]:
    """Map exact phoneme strings to IDs and reject an incomplete vocabulary."""

    encoded: list[tuple[int, ...]] = []
    for sequence in sequences:
        missing = [token for token in sequence if token not in vocab]
        if missing:
            raise ValueError(f"ctc_vocabulary_missing_token:{missing[0]}")
        encoded.append(tuple(int(vocab[token]) for token in sequence))
    if not encoded:
        raise ValueError("ctc_sequence_set_empty")
    return tuple(encoded)


def collapse_ctc_path(
    token_ids: Sequence[int], blank_id: int
) -> tuple[tuple[int, int, int], ...]:
    """Collapse a frame-level CTC path into ``(token, start, end)`` spans."""

    spans: list[list[int]] = []
    previous: int | None = None
    for frame, raw_token in enumerate(token_ids):
        token = int(raw_token)
        if token != previous:
            if token != blank_id:
                spans.append([token, frame, frame + 1])
            previous = token
        elif token != blank_id and spans and spans[-1][0] == token:
            spans[-1][2] = frame + 1
    return tuple((token, start, end) for token, start, end in spans)


def exact_sequence_spans(
    collapsed: Sequence[tuple[int, int, int]],
    sequences: Iterable[Sequence[int]],
) -> tuple[tuple[int, int, tuple[int, ...]], ...]:
    """Locate exact target sequences in a collapsed CTC path."""

    token_ids = tuple(item[0] for item in collapsed)
    matches: list[tuple[int, int, tuple[int, ...]]] = []
    for raw_sequence in sequences:
        sequence = tuple(int(token) for token in raw_sequence)
        if not sequence:
            raise ValueError("ctc_sequence_is_empty")
        for start in range(len(token_ids) - len(sequence) + 1):
            if token_ids[start : start + len(sequence)] == sequence:
                matches.append(
                    (
                        collapsed[start][1],
                        collapsed[start + len(sequence) - 1][2],
                        sequence,
                    )
                )
    return tuple(matches)


def ctc_sequence_log_probability(
    log_probabilities: np.ndarray,
    sequence: Sequence[int],
    blank_id: int,
) -> float:
    """Exact CTC forward probability for one sequence over a fixed span."""

    values = np.asarray(log_probabilities, dtype=np.float64)
    labels = tuple(int(token) for token in sequence)
    if values.ndim != 2 or values.shape[0] == 0 or values.shape[1] == 0:
        raise ValueError("ctc_log_probabilities_shape_invalid")
    if not labels:
        raise ValueError("ctc_sequence_is_empty")
    if not 0 <= blank_id < values.shape[1]:
        raise ValueError("ctc_blank_id_out_of_range")
    if any(token == blank_id or not 0 <= token < values.shape[1] for token in labels):
        raise ValueError("ctc_sequence_token_out_of_range")

    states: list[int] = [blank_id]
    for token in labels:
        states.extend((token, blank_id))
    previous = np.full(len(states), -math.inf, dtype=np.float64)
    previous[0] = values[0, blank_id]
    previous[1] = values[0, labels[0]]
    for frame in range(1, values.shape[0]):
        current = np.full(len(states), -math.inf, dtype=np.float64)
        for state, token in enumerate(states):
            candidates = [previous[state]]
            if state > 0:
                candidates.append(previous[state - 1])
            if (
                state > 1
                and token != blank_id
                and token != states[state - 2]
            ):
                candidates.append(previous[state - 2])
            total = candidates[0]
            for candidate in candidates[1:]:
                total = float(np.logaddexp(total, candidate))
            current[state] = total + values[frame, token]
        previous = current
    return float(np.logaddexp(previous[-1], previous[-2]))


def best_sequence_score(
    log_probabilities: np.ndarray,
    sequences: Iterable[Sequence[int]],
    blank_id: int,
) -> tuple[float, tuple[int, ...]]:
    """Return the highest exact-sequence CTC score."""

    scored = [
        (
            ctc_sequence_log_probability(log_probabilities, sequence, blank_id),
            tuple(int(token) for token in sequence),
        )
        for sequence in sequences
    ]
    if not scored:
        raise ValueError("ctc_sequence_set_empty")
    return max(scored, key=lambda item: item[0])


def score_verifier_span(
    log_probabilities: np.ndarray,
    *,
    start_frame: int,
    end_frame: int,
    target_sequences: Iterable[Sequence[int]],
    confusable_sequences: Iterable[Sequence[int]],
    blank_id: int,
    context_before_frames: int,
    context_after_frames: int,
) -> dict[str, object]:
    """Compare target and confusable CTC likelihoods on the identical span."""

    values = np.asarray(log_probabilities)
    if context_before_frames < 0 or context_after_frames < 0:
        raise ValueError("ctc_context_frames_invalid")
    bounded_start = max(0, int(start_frame) - context_before_frames)
    bounded_end = min(values.shape[0], int(end_frame) + context_after_frames)
    if bounded_start >= bounded_end:
        raise ValueError("ctc_verifier_span_invalid")
    segment = values[bounded_start:bounded_end]
    target_score, target = best_sequence_score(
        segment, target_sequences, blank_id
    )
    confusable_score, confusable = best_sequence_score(
        segment, confusable_sequences, blank_id
    )
    return {
        "start_frame": bounded_start,
        "end_frame": bounded_end,
        "target_log_probability": target_score,
        "confusable_log_probability": confusable_score,
        "margin": target_score - confusable_score,
        "target_sequence": list(target),
        "confusable_sequence": list(confusable),
    }


def _fold(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return "".join(
        character
        for character in decomposed
        if not unicodedata.combining(character)
    )


def lexical_word_spans(
    tokens: Sequence[str],
    timestamps: Sequence[float],
    *,
    final_token_seconds: float = 0.16,
) -> tuple[dict[str, object], ...]:
    """Recover timestamped words from a Parakeet BPE token stream."""

    if len(tokens) != len(timestamps):
        raise ValueError("lexical_token_timestamp_length_mismatch")
    if final_token_seconds <= 0.0:
        raise ValueError("lexical_final_token_seconds_invalid")
    words: list[tuple[str, int, int]] = []
    surface = ""
    first_index: int | None = None
    last_index: int | None = None

    def finish() -> None:
        nonlocal surface, first_index, last_index
        if surface and first_index is not None and last_index is not None:
            words.append((surface, first_index, last_index))
        surface = ""
        first_index = None
        last_index = None

    for index, raw_token in enumerate(tokens):
        folded = _fold(str(raw_token))
        if folded[:1].isspace() and surface:
            finish()
        pieces = re.findall(r"[^\W_]+", folded, flags=re.UNICODE)
        if not pieces:
            if folded:
                finish()
            continue
        for piece_index, piece in enumerate(pieces):
            if piece_index:
                finish()
            if first_index is None:
                first_index = index
            surface += piece
            last_index = index
        if folded and not folded[-1].isalnum():
            finish()
    finish()

    spans: list[dict[str, object]] = []
    for word, first, last in words:
        start = float(timestamps[first])
        end = float(timestamps[last]) + final_token_seconds
        if not math.isfinite(start) or not math.isfinite(end) or end <= start:
            raise ValueError("lexical_timestamp_invalid")
        spans.append(
            {
                "surface": word,
                "first_token": first,
                "last_token": last,
                "start_seconds": start,
                "end_seconds": end,
            }
        )
    return tuple(spans)


def is_lexical_target_proposal(surface: str) -> bool:
    """Return whether a word is a liberal proposal, never final acceptance."""

    folded = _fold(surface)
    return any(folded.startswith(prefix) for prefix in LEXICAL_PROPOSAL_PREFIXES)


def is_exact_lexical_target_proposal(surface: str) -> bool:
    """Return whether ASR emitted a complete target spelling, not a prefix.

    Prefixes such as ``basin`` or ``basis`` may cheaply request verifier
    compute, but they cannot define the final acoustic span.  A concatenated
    form such as ``BaxiFerrol`` remains recoverable when the independent CTC
    greedy path locates the exact /baksi/ sequence inside it.
    """

    return _fold(surface) in LEXICAL_PROPOSAL_PREFIXES


def lexical_proposal_spans(
    tokens: Sequence[str],
    timestamps: Sequence[float],
    *,
    final_token_seconds: float = 0.16,
) -> tuple[dict[str, object], ...]:
    """Locate liberal BAXY-like words in a Parakeet token stream."""

    proposals = [
        span
        for span in lexical_word_spans(
            tokens,
            timestamps,
            final_token_seconds=final_token_seconds,
        )
        if is_lexical_target_proposal(str(span["surface"]))
    ]
    return tuple(proposals)


def multiword_non_target_overlap(
    words: Sequence[dict[str, object]],
    *,
    start_seconds: float,
    end_seconds: float,
) -> bool:
    """Veto a CTC target assembled across multiple non-target ASR words.

    ``back seat`` is acoustically capable of containing the /baksi/ phoneme
    path even though it is not the standalone name.  A target-like Parakeet
    word overrides this guard; otherwise two overlapping words are explicit
    evidence that the CTC path crossed a lexical boundary.
    """

    if (
        not math.isfinite(start_seconds)
        or not math.isfinite(end_seconds)
        or end_seconds <= start_seconds
    ):
        raise ValueError("lexical_overlap_span_invalid")
    overlapping = [
        word
        for word in words
        if float(word["end_seconds"]) > start_seconds
        and float(word["start_seconds"]) < end_seconds
    ]
    if any(
        is_lexical_target_proposal(str(word["surface"]))
        for word in overlapping
    ):
        return False
    return len(overlapping) >= 2
