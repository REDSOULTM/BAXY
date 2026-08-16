from __future__ import annotations

import importlib.util
from pathlib import Path
import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "experiments"
    / "voice_latency"
    / "evaluate_r16_sapi_voice_semantics_development_v1.py"
)
SPEC = importlib.util.spec_from_file_location("r16_sapi_voice_v1", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_normalized_words_fold_diacritics_and_punctuation() -> None:
    assert MODULE.normalized_words("¡Café, BAXY!") == ("cafe", "baxy")


def test_word_edit_distance_handles_insert_delete_and_substitute() -> None:
    assert MODULE.edit_distance(("abre", "notas"), ("abre", "notas")) == 0
    assert MODULE.edit_distance(("abre", "notas"), ("abre",)) == 1
    assert MODULE.edit_distance(("abre",), ("cierra", "notas")) == 2


def test_zero_failure_confidence_supports_99_percent_at_337() -> None:
    lower = MODULE.one_sided_lower_if_zero_failures(337)
    assert lower > 0.99
    assert MODULE.one_sided_lower_if_zero_failures(298) < 0.99


def test_accepted_effect_sets_preserve_order_and_empty() -> None:
    row = {"compatible_effect_operation_sets": [["a", "b"], []]}
    assert MODULE.accepted_effect_sets(row) == {("a", "b"), ()}


def test_checkpoint_contains_only_inert_development_state() -> None:
    checkpoint = MODULE.empty_checkpoint({"corpusSha256": "x"})
    assert checkpoint["completedRecords"] == 0
    assert checkpoint["results"] == []
    assert "execution" not in checkpoint


def test_segment_rejects_invalid_trailing_silence() -> None:
    class Vad:
        window_size_samples = 512

        def reset(self) -> None:
            pass

    with pytest.raises(ValueError, match="baxy_sapi_voice_trailing_silence_invalid"):
        MODULE.segment_with_product_vad(
            Vad(),
            np.zeros(512, dtype=np.float32),
            trailing_silence_seconds=0.0,
        )

    with pytest.raises(ValueError, match="baxy_sapi_voice_retained_silence_invalid"):
        MODULE.segment_with_product_vad(
            Vad(),
            np.zeros(512, dtype=np.float32),
            trailing_silence_seconds=0.7,
            retained_trailing_silence_seconds=0.8,
        )
