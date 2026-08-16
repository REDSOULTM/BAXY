from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import numpy as np
import pytest

from baxy_mind.wakeword import WakeWordRuntimeError


def _module():
    script = (
        Path(__file__).resolve().parents[1]
        / "experiments"
        / "voice_latency"
        / "run_hyperspotter_fusion_physical_room_gate_v1.py"
    )
    spec = importlib.util.spec_from_file_location("baxy_fusion_physical_gate", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_combined_margin_matches_the_frozen_policy_equation() -> None:
    gate = _module()
    margin = gate.combined_decision_margin(
        np.asarray([[1.0, 4.0, 2.0, 3.0]], dtype=np.float32),
        3.0,
        {
            "ctc_center": 1.0,
            "ctc_scale": 2.0,
            "ctc_weight": 1.0,
            "decision_threshold": 3.0,
        },
    )

    assert margin == 2.0


def test_combined_margin_rejects_an_invalid_hyper_contract() -> None:
    gate = _module()
    with pytest.raises(WakeWordRuntimeError, match="wake_fusion_hyper_logits_invalid"):
        gate.combined_decision_margin(
            np.asarray([1.0, 2.0], dtype=np.float32),
            0.0,
            {
                "ctc_center": 0.0,
                "ctc_scale": 1.0,
                "ctc_weight": 1.0,
                "decision_threshold": 0.0,
            },
        )


def test_sigmoid_is_stable_for_large_decision_margins() -> None:
    gate = _module()

    assert gate._sigmoid(1_000.0) == 1.0
    assert gate._sigmoid(-1_000.0) == 0.0
