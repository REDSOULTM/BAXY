from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "ctc_wake_verifier.py"
)
SPEC = importlib.util.spec_from_file_location("ctc_wake_verifier", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _log_probabilities(path: list[int], classes: int = 8) -> np.ndarray:
    probabilities = np.full((len(path), classes), 0.001, dtype=np.float64)
    for frame, token in enumerate(path):
        probabilities[frame, token] = 0.993
    probabilities /= probabilities.sum(axis=1, keepdims=True)
    return np.log(probabilities)


def test_collapse_ctc_path_retains_exact_frame_spans() -> None:
    collapsed = MODULE.collapse_ctc_path([0, 1, 1, 0, 2, 2, 0], blank_id=0)

    assert collapsed == ((1, 1, 3), (2, 4, 6))


def test_exact_sequence_spans_does_not_allow_one_phoneme_substitution() -> None:
    collapsed = MODULE.collapse_ctc_path([0, 1, 0, 2, 0, 3, 0], blank_id=0)

    assert MODULE.exact_sequence_spans(collapsed, [(1, 2, 3)]) == (
        (1, 6, (1, 2, 3)),
    )
    assert MODULE.exact_sequence_spans(collapsed, [(4, 2, 3)]) == ()


def test_ctc_forward_probability_prefers_the_emitted_sequence() -> None:
    values = _log_probabilities([0, 1, 0, 2, 0])

    expected = MODULE.ctc_sequence_log_probability(values, (1, 2), blank_id=0)
    confusable = MODULE.ctc_sequence_log_probability(values, (3, 2), blank_id=0)

    assert expected > confusable


def test_verifier_compares_target_and_confusable_on_identical_span() -> None:
    values = _log_probabilities([0, 0, 1, 0, 2, 0, 3, 0])

    scored = MODULE.score_verifier_span(
        values,
        start_frame=2,
        end_frame=7,
        target_sequences=[(1, 2, 3)],
        confusable_sequences=[(4, 2, 3)],
        blank_id=0,
        context_before_frames=1,
        context_after_frames=1,
    )

    assert scored["start_frame"] == 1
    assert scored["end_frame"] == 8
    assert scored["margin"] > 0.0


def test_span_context_rejects_invalid_bounds() -> None:
    with pytest.raises(ValueError, match="ctc_verifier_span_invalid"):
        MODULE.score_verifier_span(
            _log_probabilities([0, 1]),
            start_frame=4,
            end_frame=5,
            target_sequences=[(1,)],
            confusable_sequences=[(2,)],
            blank_id=0,
            context_before_frames=0,
            context_after_frames=0,
        )


def test_lexical_proposals_parse_bpe_and_concatenated_brand() -> None:
    tokens = [" We", " use", " B", "a", "xi", "fer", "rol", "."]
    timestamps = [0.0, 0.2, 0.8, 0.9, 1.0, 1.2, 1.4, 1.6]

    proposals = MODULE.lexical_proposal_spans(tokens, timestamps)

    assert len(proposals) == 1
    assert proposals[0]["surface"] == "baxiferrol"
    assert proposals[0]["start_seconds"] == pytest.approx(0.8)
    assert proposals[0]["end_seconds"] == pytest.approx(1.56)


def test_lexical_proposals_accept_russian_development_spelling() -> None:
    proposals = MODULE.lexical_proposal_spans(
        [" Б", "ак", "се", "."], [0.9, 1.0, 1.2, 1.4]
    )

    assert proposals[0]["surface"] == "баксе"


def test_lexical_proposal_is_not_fuzzy_edit_distance() -> None:
    assert MODULE.lexical_proposal_spans([" V", "a", "xi"], [0.1, 0.2, 0.3]) == ()


def test_only_complete_spellings_can_define_final_lexical_locator() -> None:
    assert MODULE.is_exact_lexical_target_proposal("Baxi") is True
    assert MODULE.is_exact_lexical_target_proposal("Basi") is True
    assert MODULE.is_exact_lexical_target_proposal("basin") is False
    assert MODULE.is_exact_lexical_target_proposal("basis") is False
    assert MODULE.is_lexical_target_proposal("BaxiFerrol") is True
    assert MODULE.is_exact_lexical_target_proposal("BaxiFerrol") is False


def test_multiword_overlap_vetoes_back_seat_ctc_assembly() -> None:
    words = MODULE.lexical_word_spans(
        [" B", "ack", " se", "at", "."],
        [0.56, 0.8, 1.04, 1.28, 1.84],
    )

    assert MODULE.multiword_non_target_overlap(
        words, start_seconds=0.7, end_seconds=1.4
    )


def test_target_like_word_prevents_multiword_veto() -> None:
    words = MODULE.lexical_word_spans(
        [" B", "a", "xy", " turn"], [0.8, 0.9, 1.0, 1.2]
    )

    assert not MODULE.multiword_non_target_overlap(
        words, start_seconds=0.8, end_seconds=1.3
    )
