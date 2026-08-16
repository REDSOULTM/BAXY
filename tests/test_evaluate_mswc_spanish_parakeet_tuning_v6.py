from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "evaluate_mswc_spanish_parakeet_tuning_v6.py"
)
SPEC = importlib.util.spec_from_file_location(
    "evaluate_mswc_spanish_parakeet_tuning_v6", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_normalize_text_folds_accents_case_and_punctuation() -> None:
    assert MODULE.normalize_text("  ¡CORAZÓN!  ") == "corazon"


def test_transcript_candidate_scores_prefers_exact_or_best_token() -> None:
    whole = MODULE.transcript_candidate_scores(
        transcripts=["La casa."],
        candidate_words=[["casa", "cosa"]],
        method="whole_transcript_edit",
    )
    token = MODULE.transcript_candidate_scores(
        transcripts=["La casa."],
        candidate_words=[["casa", "cosa"]],
        method="whole_or_token_edit",
    )
    assert token[0, 0] == 1.0
    assert token[0, 0] > token[0, 1]
    assert token[0, 0] > whole[0, 0]
