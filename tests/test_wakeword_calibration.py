from __future__ import annotations

import importlib.util
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from baxy_mind.wakeword import (
    CALIBRATION_REPORT_FILENAME,
    DEFAULT_HOP_SAMPLES,
    WINDOW_SAMPLES,
    inspect_wakeword_candidate_config,
    inspect_wakeword_config,
)


def _wake_evaluator_module():
    script = Path(__file__).resolve().parents[1] / "scripts" / "evaluate_wake_corpus.py"
    spec = importlib.util.spec_from_file_location("baxy_wake_evaluator", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_one_sided_far_bound_does_not_treat_zero_hits_as_zero_risk() -> None:
    evaluator = _wake_evaluator_module()

    five_hours = evaluator.one_sided_poisson_upper_rate_per_hour(0, 5 * 3600.0, 0.95)
    thirty_hours = evaluator.one_sided_poisson_upper_rate_per_hour(0, 30 * 3600.0, 0.95)

    assert five_hours is not None and five_hours > 0.1
    assert thirty_hours is not None and thirty_hours < 0.1
    assert abs(thirty_hours - (-math.log(0.05) / 30.0)) < 1e-12


def test_one_sided_far_bound_accounts_for_observed_false_activations() -> None:
    evaluator = _wake_evaluator_module()

    one_hit_50_hours = evaluator.one_sided_poisson_upper_rate_per_hour(1, 50 * 3600.0, 0.95)

    assert one_hit_50_hours is not None
    assert 0.09 < one_hit_50_hours < 0.1


def test_installer_preserves_hash_bound_calibration_evidence(tmp_path) -> None:
    powershell = shutil.which("powershell") or shutil.which("pwsh")
    if powershell is None:
        return
    source = tmp_path / "source"
    source.mkdir()
    model = source / "baxy-trained.onnx"
    model.write_bytes(b"calibrated-baxy-model")
    model_sha256 = hashlib.sha256(model.read_bytes()).hexdigest()
    report = {
        "schema": "baxy-wake-corpus-gate-v3",
        "measured_at": "2026-07-23T00:00:00+00:00",
        "mode": "acoustic",
        "model": {
            "backend": "livekit-wakeword",
            "model": "baxy",
            "phrase": "Baxy",
            "sample_rate": 16000,
            "window_samples": WINDOW_SAMPLES,
            "hop_samples": DEFAULT_HOP_SAMPLES,
            "threshold": 0.7,
            "debounce_seconds": 2.0,
            "model_sha256": model_sha256,
        },
        "false_reject_rate": 0.01,
        "far": {
            "method": "poisson_one_sided_upper_exact",
            "confidence": 0.95,
            "upper_confidence_per_hour": 0.09,
        },
        "corpus_sufficient": True,
        "promotion_criteria": {
            "false_reject_rate_lte": 0.05,
            "false_activations_per_hour_lte": 0.1,
            "far_confidence_gte": 0.95,
        },
        "promotable": True,
    }
    report_path = source / CALIBRATION_REPORT_FILENAME
    report_path.write_text(json.dumps(report) + "\n", encoding="utf-8")
    destination = tmp_path / "installed"
    script = Path(__file__).resolve().parents[1] / "scripts" / "install_baxy_wake_model.ps1"

    result = subprocess.run(
        [
            powershell,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
            "-ModelPath",
            str(model),
            "-CalibrationReport",
            str(report_path),
            "-DestinationDirectory",
            str(destination),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    config, error = inspect_wakeword_config(destination / "baxy-wakeword-v1.json")
    assert config is not None
    assert error is None
    assert (destination / CALIBRATION_REPORT_FILENAME).is_file()


def test_candidate_asset_has_no_direct_authority_but_keeps_hash_provenance(
    tmp_path, monkeypatch
) -> None:
    model = tmp_path / "candidate.onnx"
    model.write_bytes(b"proposal-only")
    manifest = tmp_path / "baxy-wakeword-v1.json"
    manifest.write_text(
        json.dumps(
                {
                    "schema": "baxy-wakeword-v1",
                    "sampleRate": 16_000,
                "windowSamples": WINDOW_SAMPLES,
                "modelName": "baxy",
                "phrase": "Baxy",
                "model": model.name,
                "sha256": hashlib.sha256(model.read_bytes()).hexdigest(),
                "hopSamples": DEFAULT_HOP_SAMPLES,
                "debounceSeconds": 2.0,
                "threshold": 0.05,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("BAXY_VOICE_WAKE_ALLOW_UNCALIBRATED", raising=False)

    direct, direct_error = inspect_wakeword_config(manifest)
    candidate, candidate_error = inspect_wakeword_candidate_config(manifest)

    assert direct is None
    assert direct_error == "wake_word_calibration_required"
    assert candidate is not None
    assert candidate_error is None
    assert candidate.model_sha256 == hashlib.sha256(model.read_bytes()).hexdigest()
