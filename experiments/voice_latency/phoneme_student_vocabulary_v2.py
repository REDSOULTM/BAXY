"""Lossless task vocabulary for the small BAXY phoneme verifier.

The first distillation vocabulary merged vowel and final-vowel variants.  That
made the reduced greedy path for ``boxing`` indistinguishable from a permitted
BAXY pronunciation.  This module keeps every contrast used by the frozen
teacher verifier while still aggregating the teacher's much larger IPA
vocabulary into a small student head.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence


CATEGORY_TOKENS: dict[str, tuple[str, ...]] = {
    "blank": (),
    "B": ("b",),
    "BETA": ("β",),
    "V": ("v",),
    "F": ("f",),
    "P": ("p",),
    "A": ("a",),
    "AE": ("æ",),
    "AA": ("ɑ",),
    "UH": ("ʌ",),
    "K": ("k",),
    "S": ("s",),
    "S_PAL": ("sʲ",),
    "SH": ("ʃ",),
    "I": ("i",),
    "IH": ("ɪ",),
    "R_TAP": ("ɾ",),
    "other": (),
}
CATEGORY_NAMES = tuple(CATEGORY_TOKENS)


# Exact category projections of ctc_wake_verifier.TARGET_SEQUENCES.  Keeping
# this list explicit makes a future change to either contract fail visibly.
TARGET_CATEGORY_SEQUENCES: tuple[tuple[str, ...], ...] = (
    ("B", "A", "K", "S", "I"),
    ("B", "AE", "K", "S", "I"),
    ("B", "AE", "K", "S", "IH"),
    ("B", "AA", "K", "S", "I"),
    ("B", "A", "K", "S_PAL", "I"),
    ("B", "AA", "K", "S_PAL", "I"),
    ("B", "UH", "K", "S_PAL", "I"),
    ("B", "A", "R_TAP", "K", "S", "I"),
    ("BETA", "A", "K", "S", "I"),
    ("BETA", "A", "R_TAP", "K", "S", "I"),
)


def _confusable_category_sequences() -> tuple[tuple[str, ...], ...]:
    vowels = ("A", "AE", "AA", "UH")
    sibilants = ("S", "S_PAL")
    endings = ("I", "IH")
    values: list[tuple[str, ...]] = []
    for initial in ("V", "F", "P"):
        for vowel in vowels:
            for sibilant in sibilants:
                for ending in endings:
                    values.append((initial, vowel, "K", sibilant, ending))
    for initial in ("B", "BETA"):
        for vowel in vowels:
            for ending in endings:
                values.append((initial, vowel, "K", "SH", ending))
    return tuple(values)


CONFUSABLE_CATEGORY_SEQUENCES = _confusable_category_sequences()


def resolve_category_ids(
    vocabulary: dict[str, int], blank_id: int
) -> dict[str, tuple[int, ...]]:
    """Resolve disjoint teacher token sets and assign the remainder to other."""

    values: dict[str, tuple[int, ...]] = {"blank": (int(blank_id),)}
    used = {int(blank_id)}
    for category, tokens in CATEGORY_TOKENS.items():
        if category in {"blank", "other"}:
            continue
        missing = [token for token in tokens if token not in vocabulary]
        if missing:
            raise ValueError(f"phoneme_student_v2_vocabulary_missing:{missing[0]}")
        ids = tuple(sorted({int(vocabulary[token]) for token in tokens}))
        if used.intersection(ids):
            raise ValueError(f"phoneme_student_v2_category_overlap:{category}")
        values[category] = ids
        used.update(ids)
    values["other"] = tuple(
        index for index in range(max(vocabulary.values()) + 1) if index not in used
    )
    if not values["other"]:
        raise ValueError("phoneme_student_v2_other_category_empty")
    return values


def encode_category_sequences(
    sequences: Iterable[Sequence[str]],
) -> tuple[tuple[int, ...], ...]:
    """Encode category names using the stable student-head order."""

    category_ids = {name: index for index, name in enumerate(CATEGORY_NAMES)}
    encoded = []
    for raw_sequence in sequences:
        sequence = tuple(str(value) for value in raw_sequence)
        if not sequence:
            raise ValueError("phoneme_student_v2_sequence_empty")
        missing = [name for name in sequence if name not in category_ids]
        if missing:
            raise ValueError(f"phoneme_student_v2_sequence_unknown:{missing[0]}")
        encoded.append(tuple(category_ids[name] for name in sequence))
    if not encoded:
        raise ValueError("phoneme_student_v2_sequence_set_empty")
    return tuple(encoded)


TARGET_IDS = encode_category_sequences(TARGET_CATEGORY_SEQUENCES)
CONFUSABLE_IDS = encode_category_sequences(CONFUSABLE_CATEGORY_SEQUENCES)
BLANK_ID = CATEGORY_NAMES.index("blank")
