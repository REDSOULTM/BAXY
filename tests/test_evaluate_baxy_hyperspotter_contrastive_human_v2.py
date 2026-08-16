from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "evaluate_baxy_hyperspotter_contrastive_human_v2.py"
)
SPEC = importlib.util.spec_from_file_location(
    "evaluate_baxy_hyperspotter_contrastive_human_v2", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_control_selection_is_deterministic_and_excludes_target() -> None:
    manifest = {
        "schema": "baxy.voxcpm2-ipa-filtered-wake-corpus.v1",
        "class_label": "adversarial_negative",
        "records": [
            {"phrase_text": value}
            for value in ("Baxy", "taxi", "backseat", "basic", "basket")
        ],
    }
    controls = MODULE.select_confusable_controls(
        manifest, count=3, aliases=("baxy", "baxi")
    )
    assert len(controls) == 3
    assert "Baxy" not in controls
    assert controls == MODULE.select_confusable_controls(
        manifest, count=3, aliases=("baxy", "baxi")
    )


def test_fixed_metrics_use_preregistered_threshold() -> None:
    metrics = MODULE.fixed_metrics(
        np.asarray([1, 1, 0, 0]),
        np.asarray([0.8, 0.3, 0.2, -0.1]),
        0.25,
    )
    assert metrics["auc"] == 1.0
    assert metrics["fixed_positive_hits"] == 2
    assert metrics["fixed_false_hits"] == 0


def test_edit_distance_handles_empty_and_substitution() -> None:
    assert MODULE.edit_distance("baxy", "baxi") == 1
    assert MODULE.edit_distance("", "baxi") == 4
