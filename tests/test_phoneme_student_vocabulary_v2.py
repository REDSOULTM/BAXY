from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments" / "voice_latency"))

from phoneme_student_vocabulary_v2 import (  # noqa: E402
    BLANK_ID,
    CATEGORY_NAMES,
    CONFUSABLE_IDS,
    TARGET_IDS,
    resolve_category_ids,
)


def test_target_inventory_preserves_boxing_and_ferrol_contrasts() -> None:
    ids = {name: index for index, name in enumerate(CATEGORY_NAMES)}
    boxing_prefix = (ids["B"], ids["A"], ids["K"], ids["S"], ids["IH"])
    ferrol = (
        ids["BETA"],
        ids["A"],
        ids["R_TAP"],
        ids["K"],
        ids["S"],
        ids["I"],
    )

    assert boxing_prefix not in TARGET_IDS
    assert ferrol in TARGET_IDS
    assert BLANK_ID == ids["blank"]
    assert all(sequence not in CONFUSABLE_IDS for sequence in TARGET_IDS)


def test_resolve_category_ids_is_disjoint_and_covers_teacher_head() -> None:
    tokens = [
        "<pad>",
        "b",
        "β",
        "v",
        "f",
        "p",
        "a",
        "æ",
        "ɑ",
        "ʌ",
        "k",
        "s",
        "sʲ",
        "ʃ",
        "i",
        "ɪ",
        "ɾ",
        "ŋ",
    ]
    resolved = resolve_category_ids(
        {token: index for index, token in enumerate(tokens)}, 0
    )

    flattened = [value for values in resolved.values() for value in values]
    assert sorted(flattened) == list(range(len(tokens)))
    assert len(flattened) == len(set(flattened))
    assert resolved["IH"] != resolved["I"]
    assert resolved["other"] == (tokens.index("ŋ"),)
