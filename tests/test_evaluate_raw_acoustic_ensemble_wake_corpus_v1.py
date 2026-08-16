from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


def _module():
    script = (
        Path(__file__).resolve().parents[1]
        / "experiments"
        / "voice_latency"
        / "evaluate_raw_acoustic_ensemble_wake_corpus_v1.py"
    )
    spec = importlib.util.spec_from_file_location("baxy_raw_ensemble", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_ensemble_accepts_early_transient_three_model_consensus() -> None:
    gate = _module()

    accepted, reason = gate.ensemble_decision(
        base_maximum=0.06,
        aligned_maximum=0.07,
        primary_scores=[0.10, 0.08, 0.01, 0.005],
    )

    assert accepted
    assert reason == "early_three_model_consensus"


def test_ensemble_rejects_late_or_sustained_responses() -> None:
    gate = _module()

    late, late_reason = gate.ensemble_decision(
        base_maximum=0.4,
        aligned_maximum=0.4,
        primary_scores=[0.06, 0.08, 0.40, 0.02],
    )
    sustained, sustained_reason = gate.ensemble_decision(
        base_maximum=0.2,
        aligned_maximum=0.2,
        primary_scores=[0.20, 0.10, 0.08, 0.05],
    )

    assert not late and late_reason == "late_primary_peak"
    assert not sustained and sustained_reason == "sustained_non_wake_response"


def test_ensemble_rejects_cross_model_disagreement() -> None:
    gate = _module()

    accepted, reason = gate.ensemble_decision(
        base_maximum=0.02,
        aligned_maximum=0.09,
        primary_scores=[0.10, 0.08, 0.01],
    )

    assert not accepted
    assert reason == "base_model_disagrees"
