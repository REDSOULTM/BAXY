from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "experiments"
    / "voice_latency"
    / "evaluate_parakeet_mswc_spanish_word_gate_v1.py"
)
SPEC = importlib.util.spec_from_file_location("parakeet_mswc_v1", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_normalized_words_fold_case_and_diacritics_without_substrings() -> None:
    assert MODULE.normalized_words("¡MÚSICA!") == ("musica",)
    assert MODULE.normalized_words("abre-calendario") == ("abre", "calendario")


def test_levenshtein_distance_handles_empty_and_substitution() -> None:
    assert MODULE.levenshtein_distance("hola", "hola") == 0
    assert MODULE.levenshtein_distance("hola", "ola") == 1
    assert MODULE.levenshtein_distance("", "voz") == 3


def test_aggregate_checkpoint_contains_no_record_identity() -> None:
    checkpoint = MODULE.empty_checkpoint({"manifest": "a" * 64}, 2)
    assert checkpoint["completedRecords"] == 0
    assert checkpoint["classTotals"] == [0, 0]
    forbidden = {"record", "className", "speaker", "filename", "transcript"}
    assert forbidden.isdisjoint(checkpoint)


def test_summary_computes_micro_macro_and_cer() -> None:
    checkpoint = MODULE.empty_checkpoint({"manifest": "a" * 64}, 2)
    checkpoint.update(
        {
            "completedRecords": 4,
            "exactCorrect": 3,
            "targetPresentCorrect": 4,
            "emptyTranscripts": 0,
            "editDistanceSum": 2,
            "referenceCharacters": 20,
            "audioSeconds": 4.0,
            "decodeSeconds": 1.0,
            "classTotals": [2, 2],
            "classCorrect": [2, 1],
        }
    )
    summary = MODULE.summarize(checkpoint)
    assert summary["exactUtteranceAccuracy"] == 0.75
    assert summary["targetTokenRecall"] == 1.0
    assert summary["macroExactUtteranceAccuracy"] == 0.75
    assert summary["characterErrorRate"] == 0.1
    assert summary["audioRealtimeFactor"] == 0.25
