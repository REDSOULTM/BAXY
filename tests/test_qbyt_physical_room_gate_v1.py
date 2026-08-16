from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest


def _module():
    script = (
        Path(__file__).resolve().parents[1]
        / "experiments"
        / "voice_latency"
        / "run_qbyt_physical_room_gate_v1.py"
    )
    spec = importlib.util.spec_from_file_location("baxy_qbyt_physical_gate", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_qbyt_decision_margin_is_score_minus_frozen_threshold() -> None:
    gate = _module()

    assert gate.qbyt_decision_margin(0.75, 0.25) == 0.5


@pytest.mark.parametrize("score,threshold", [(float("nan"), 0.0), (0.0, float("inf"))])
def test_qbyt_decision_margin_rejects_nonfinite_values(
    score: float,
    threshold: float,
) -> None:
    gate = _module()

    with pytest.raises(ValueError, match="wake_qbyt_score_invalid"):
        gate.qbyt_decision_margin(score, threshold)


def test_parser_uses_one_captured_snr_contract_for_both_groups() -> None:
    gate = _module()
    arguments = gate._parser().parse_args(
        [
            "--physical-output",
            "--candidate",
            "candidate.json",
            "--model-directory",
            "teacher",
            "--model-name",
            "qbyt-v2",
            "--positive",
            "positive",
            "--negative",
            "negative",
            "--output",
            "report.json",
            "--input-device",
            "mic",
            "--output-device",
            "speaker",
            "--minimum-captured-snr-db",
            "7.5",
        ]
    )

    assert arguments.minimum_captured_snr_db == 7.5
    assert not hasattr(arguments, "minimum_snr_db")
