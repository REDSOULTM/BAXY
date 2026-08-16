from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "evaluate_mswc_spanish_whisper_forced_alignment_tuning_v9.py"
)
SPEC = importlib.util.spec_from_file_location(
    "evaluate_mswc_spanish_whisper_forced_alignment_tuning_v9", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class _Tokenizer:
    eot = 99

    @staticmethod
    def encode(text: str) -> list[int]:
        return [ord(value) for value in text]


def test_candidate_token_sequences_controls_prefix_and_eot() -> None:
    tokens = MODULE.candidate_token_sequences(
        tokenizer=_Tokenizer(),
        candidates=["casa"],
        token_prefix="leading_space",
        include_eot=True,
    )
    assert tokens == [[32, 99, 97, 115, 97, 99]]


def test_aggregate_token_probabilities_applies_length_normalization() -> None:
    probabilities = [np.asarray([0.5, 0.5]), np.asarray([0.25])]
    unnormalized = MODULE.aggregate_token_probabilities(
        probabilities, length_power=0.0
    )
    mean_log = MODULE.aggregate_token_probabilities(probabilities, length_power=1.0)
    assert np.allclose(unnormalized, [np.log(0.25), np.log(0.25)])
    assert np.allclose(mean_log, [np.log(0.5), np.log(0.25)])


def test_load_candidate_mask_requires_exact_alignment(tmp_path: Path) -> None:
    path = tmp_path / "shortlist.npz"
    np.savez_compressed(
        path,
        schema=np.asarray(["baxy.mswc-forced-alignment-shortlist.v1"]),
        candidate_mask=np.asarray([[1, 0], [1, 1]], dtype=np.uint8),
        query_audio_sha256=np.asarray(["a" * 64, "b" * 64]),
        query_words=np.asarray(["casa", "mundo"]),
        candidate_words=np.asarray([["casa", "cosa"], ["mundo", "manda"]]),
        depth=np.asarray([3], dtype=np.int32),
    )
    mask, depth = MODULE.load_candidate_mask(
        path=path,
        query_audio_sha256=["a" * 64, "b" * 64],
        query_words=["casa", "mundo"],
        candidate_words=[["casa", "cosa"], ["mundo", "manda"]],
    )
    assert depth == 3
    assert mask.tolist() == [[True, False], [True, True]]


def test_incomplete_probe_cannot_be_accepted() -> None:
    selected = {
        "metrics": {
            "hard_candidate_top1_accuracy": 0.99,
            "pair_auc": 0.999,
            "equal_error_rate": 0.01,
        },
        "zero_false_true_pair_recall": 0.5,
    }
    floor = {
        "hard_candidate_top1_accuracy_minimum": 0.94,
        "pair_auc_minimum": 0.99,
        "equal_error_rate_maximum": 0.05,
        "zero_false_true_pair_recall_minimum": 0.2,
    }
    assert not MODULE.promotion_accepted(
        selected=selected, quality_floor=floor, complete=False
    )
