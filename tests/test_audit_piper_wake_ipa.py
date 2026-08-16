from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "audit_piper_wake_ipa.py"
)
SPEC = importlib.util.spec_from_file_location("audit_piper_wake_ipa", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


@pytest.mark.parametrize(
    ("decoded", "expected"),
    [
        ("b aː k s i", ("b", "a", "k", "s", "i")),
        ("ˈb æ k s i5", ("b", "æ", "k", "s", "i5")),
        ("b ɑˑ k s i", ("b", "ɑ", "k", "s", "i")),
        ("b a ts iː", ("b", "a", "ts", "i")),
    ],
)
def test_normalize_ipa_removes_only_non_segmental_marks(
    decoded: str, expected: tuple[str, ...]
) -> None:
    assert MODULE.normalize_ipa(decoded) == expected


def test_target_distance_accepts_only_declared_vowels() -> None:
    assert MODULE.target_distance(("b", "a", "k", "s", "i")) == 0
    assert MODULE.target_distance(("b", "æ", "k", "s", "i")) == 0
    assert MODULE.target_distance(("b", "ɑ", "k", "s", "i")) == 0
    assert MODULE.target_distance(("b", "a", "k", "sʲ", "i")) == 0
    assert MODULE.target_distance(("b", "ʌ", "k", "sʲ", "i")) == 0
    assert MODULE.target_distance(("b", "ɛ", "k", "s", "i")) == 1
    assert MODULE.target_distance(("v", "a", "k", "s", "i")) == 1
    assert MODULE.target_distance(("b", "a", "k", "s", "i5")) == 1


def test_edit_distance_is_over_phoneme_tokens() -> None:
    assert MODULE.edit_distance(("b", "a", "k", "s", "i"), ()) == 5
    assert MODULE.edit_distance(("b", "a", "ts", "i"), ("b", "a", "k", "s", "i")) == 2


def test_select_dense_wavs_fails_closed_on_gap(tmp_path: Path) -> None:
    (tmp_path / "clip_000000.wav").touch()
    (tmp_path / "clip_000002.wav").touch()

    with pytest.raises(FileNotFoundError, match="clip_000001.wav"):
        MODULE.select_dense_wavs(tmp_path, 3)


def test_trim_ctc_predictions_removes_each_rows_padding() -> None:
    assert MODULE.trim_ctc_predictions(
        [[1, 2, 3, 99], [4, 5, 99, 99]], [3, 2]
    ) == [[1, 2, 3], [4, 5]]


def test_trim_ctc_predictions_rejects_impossible_length() -> None:
    with pytest.raises(ValueError, match="ctc_output_length_invalid"):
        MODULE.trim_ctc_predictions([[1, 2]], [3])
