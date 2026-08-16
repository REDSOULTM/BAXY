from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "audit_baxy_hyperspotter_fusion_product_candidate_v1.py"
)
SPEC = importlib.util.spec_from_file_location(
    "audit_baxy_hyperspotter_fusion_product_candidate_v1", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def candidate(tmp_path: Path) -> tuple[Path, Path]:
    graph = tmp_path / "model.onnx"
    graph.write_bytes(b"not-a-real-graph")
    mel = tmp_path / "mel.npy"
    np.save(mel, np.ones((80, 201), dtype=np.float32), allow_pickle=False)
    ctc = tmp_path / "ctc.json"
    ctc.write_text(json.dumps({"schema": "baxy-wake-verifier-v1"}), encoding="utf-8")
    manifest = tmp_path / "fusion.json"
    manifest.write_text(
        json.dumps(
            {
                "schema": "baxy-hyperspotter-fusion-v1",
                "backend": "onnxruntime-hyperspotter-fixed-aliases-plus-phoneme-ctc",
                "graph": graph.name,
                "graphSha256": digest(graph),
                "graphBytes": graph.stat().st_size,
                "melFilters": mel.name,
                "melFiltersSha256": digest(mel),
                "melFiltersShape": [80, 201],
                "aliases": ["baxy", "baxi", "basi", "bakse"],
                "sampleRate": 16000,
                "audioSamples": 48000,
                "logmelFrames": 300,
                "logmelBins": 80,
                "policy": {
                    "ctc_feature": "full_clip_margin",
                    "ctc_center": 1.0,
                    "ctc_scale": 2.0,
                    "ctc_weight": 1.0,
                    "decision_threshold": 3.0,
                },
                "ctcVerifierManifestSha256": digest(ctc),
                "approved": False,
                "developmentOnly": True,
                "blindHumanAudioAccessed": False,
                "effectsExecuted": 0,
            }
        ),
        encoding="utf-8",
    )
    return manifest, ctc


def test_candidate_loader_validates_all_local_assets(tmp_path: Path) -> None:
    manifest, ctc = candidate(tmp_path)
    loaded = MODULE.load_fusion_candidate(manifest, ctc)
    assert loaded["mel_filters"].shape == (80, 201)
    assert loaded["policy"]["decision_threshold"] == 3.0

    (tmp_path / "model.onnx").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="hash_mismatch"):
        MODULE.load_fusion_candidate(manifest, ctc)


def test_numpy_logmel_has_fixed_runtime_shape() -> None:
    result = MODULE.numpy_log_mel_spectrogram(
        np.zeros(48_000, dtype=np.float32),
        np.ones((80, 201), dtype=np.float32) * np.float32(1e-3),
    )
    assert result.shape == (300, 80)
    assert result.dtype == np.float32
    assert np.isfinite(result).all()


def test_vectorized_ctc_matches_scalar_recurrence() -> None:
    rng = np.random.default_rng(9)
    probabilities = rng.random((3, 9, 5))
    probabilities /= probabilities.sum(axis=2, keepdims=True)
    values = np.log(probabilities)
    sequence = [1, 2]

    def scalar(item: np.ndarray) -> float:
        states = [0, 1, 0, 2, 0]
        previous = np.full(len(states), -np.inf)
        previous[0] = item[0, 0]
        previous[1] = item[0, 1]
        for frame in range(1, len(item)):
            current = np.full(len(states), -np.inf)
            for state, token in enumerate(states):
                total = previous[state]
                if state > 0:
                    total = np.logaddexp(total, previous[state - 1])
                if state > 1 and token != 0 and token != states[state - 2]:
                    total = np.logaddexp(total, previous[state - 2])
                current[state] = total + item[frame, token]
            previous = current
        return float(np.logaddexp(previous[-1], previous[-2]))

    expected = np.asarray([scalar(item) for item in values])
    actual = MODULE.ctc_log_probability_batch(values, sequence, blank_id=0)
    assert np.allclose(actual, expected)


def test_partition_metrics_exposes_decision_headroom() -> None:
    metrics = MODULE.partition_metrics(
        np.asarray([1, 1, 0, 0]),
        np.asarray([True, True, False, False]),
        np.asarray([0.5, 0.2, -0.1, -0.4]),
    )
    assert metrics["positiveHits"] == 2
    assert metrics["falseHits"] == 0
    assert metrics["minimumPositiveDecisionMargin"] == pytest.approx(0.2)
    assert metrics["maximumNegativeDecisionMargin"] == pytest.approx(-0.1)
