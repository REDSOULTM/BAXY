from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from baxy_mind.wake_verifier import (
    CALIBRATION_REPORT_FILENAME,
    CALIBRATION_REPORT_SCHEMA,
    CATEGORY_NAMES,
    decide_category_probabilities,
    has_exact_lexical_target,
    has_liberal_lexical_proposal,
    load_wake_verifier_candidate_config,
    load_wake_verifier_config,
    normalize_audio,
    stage1_eligible,
    verification_audio,
    verification_view_starts,
    WakeVerifierConfigurationError,
)


def _path_probabilities(categories: list[str]) -> np.ndarray:
    ids = {name: index for index, name in enumerate(CATEGORY_NAMES)}
    frames = ["blank"]
    for category in categories:
        frames.extend((category, "blank"))
    values = np.full((len(frames), len(CATEGORY_NAMES)), 1e-5)
    for index, category in enumerate(frames):
        values[index, ids[category]] = 1.0
    return values / values.sum(axis=1, keepdims=True)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_manifest(root: Path) -> Path:
    root.mkdir()
    graph = root / "verifier.onnx"
    data = root / "verifier.onnx.data"
    vocabulary = root / "vocab.json"
    graph.write_bytes(b"graph")
    data.write_bytes(b"weights")
    vocabulary.write_text(json.dumps({"<pad>": 0, "b": 1}), encoding="utf-8")
    manifest = root / "baxy-wake-verifier-v1.json"
    manifest.write_text(
        json.dumps(
            {
                "schema": "baxy-wake-verifier-v1",
                "backend": "onnxruntime-phoneme-ctc",
                "graph": graph.name,
                "graphData": data.name,
                "vocabulary": vocabulary.name,
                "graphSha256": _sha256(graph),
                "graphDataSha256": _sha256(data),
                "vocabularySha256": _sha256(vocabulary),
                "stage1ModelSha256": "1" * 64,
                "stage1Phrase": "Baxy",
                "stage1HopSamples": 2_560,
                "stage1DebounceSeconds": 2.0,
                "stage1PreRollSeconds": 5.0,
                "primaryViewStartSamples": 64_000,
                "activityLookbackSamples": 2_560,
                "activityAlignmentSamples": 320,
                "activityVadThreshold": 0.1,
                "sampleRate": 16_000,
                "minimumSamples": 16_000,
                "maximumSamples": 160_000,
                "maximumTurnSamples": 480_000,
                "broadThreshold": 0.02,
                "strongThreshold": 0.05,
                "decisionMargin": 0.5,
                "anchorMargin": 0.5,
            }
        ),
        encoding="utf-8",
    )
    return manifest


def _approve_manifest(manifest: Path) -> None:
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    report = manifest.with_name(CALIBRATION_REPORT_FILENAME)
    report.write_text(
        json.dumps(
            {
                "schema": CALIBRATION_REPORT_SCHEMA,
                "promotable": True,
                "candidate_frozen": True,
                "product_operating_point": True,
                "blind_human_partition_accessed": True,
                "assets": {
                    "graph_sha256": payload["graphSha256"],
                    "graph_data_sha256": payload["graphDataSha256"],
                    "vocabulary_sha256": payload["vocabularySha256"],
                    "stage1_model_sha256": payload["stage1ModelSha256"],
                    "stage1_phrase": payload["stage1Phrase"],
                    "stage1_hop_samples": payload["stage1HopSamples"],
                    "stage1_debounce_seconds": payload[
                        "stage1DebounceSeconds"
                    ],
                    "stage1_pre_roll_seconds": payload[
                        "stage1PreRollSeconds"
                    ],
                    "primary_view_start_samples": payload[
                        "primaryViewStartSamples"
                    ],
                    "activity_lookback_samples": payload[
                        "activityLookbackSamples"
                    ],
                    "activity_alignment_samples": payload[
                        "activityAlignmentSamples"
                    ],
                    "activity_vad_threshold": payload[
                        "activityVadThreshold"
                    ],
                    "sample_rate": payload["sampleRate"],
                    "minimum_samples": payload["minimumSamples"],
                    "maximum_samples": payload["maximumSamples"],
                    "maximum_turn_samples": payload["maximumTurnSamples"],
                    "broad_threshold": payload["broadThreshold"],
                    "strong_threshold": payload["strongThreshold"],
                    "decision_margin": payload["decisionMargin"],
                    "anchor_margin": payload["anchorMargin"],
                },
                "metrics": {
                    "human_recall": 1.0,
                    "negative_false_activations": 0,
                    "far_confidence": 0.95,
                    "far_upper_confidence_per_hour": 0.1,
                },
            }
        ),
        encoding="utf-8",
    )
    payload["calibration"] = {
        "approved": True,
        "report": report.name,
        "reportSha256": _sha256(report),
    }
    manifest.write_text(json.dumps(payload), encoding="utf-8")


def test_exact_ctc_target_accepts_without_lexical_asr() -> None:
    decision = decide_category_probabilities(
        _path_probabilities(["B", "AE", "K", "S", "IH"]),
        "",
        decision_margin=0.5,
        anchor_margin=0.5,
    )
    assert decision.accepted is True
    assert decision.method == "ctc_exact"


def test_vaxi_is_rejected_even_after_a_strong_proposal() -> None:
    decision = decide_category_probabilities(
        _path_probabilities(["V", "A", "K", "S", "I"]),
        "yeah",
        decision_margin=0.5,
        anchor_margin=0.5,
    )
    assert decision.accepted is False


def test_exact_target_inserted_after_adjacent_vaxi_prefix_is_rejected() -> None:
    probabilities = _path_probabilities(["V", "B", "A", "K", "S", "I"])

    rejected = decide_category_probabilities(
        probabilities,
        "",
        decision_margin=0.3,
        anchor_margin=0.5,
    )
    assert rejected.accepted is False


def test_lexical_anchor_recovers_internal_greedy_insertion() -> None:
    probabilities = _path_probabilities(["B", "A", "other", "S_PAL", "I"])
    decision = decide_category_probabilities(
        probabilities,
        "En la línea Baxi.",
        decision_margin=0.5,
        anchor_margin=0.5,
    )
    assert decision.accepted is True
    assert decision.method == "ctc_lexical_anchor"


def test_basin_is_liberal_only_and_cannot_authorize_anchor() -> None:
    assert has_liberal_lexical_proposal("mix it in a large basin") is True
    assert has_exact_lexical_target("mix it in a large basin") is False


def test_broad_proposal_requires_strong_acoustics_or_exact_lexical_target() -> None:
    assert (
        stage1_eligible(
            0.03, "Basi", broad_threshold=0.02, strong_threshold=0.05
        )
        is True
    )
    assert (
        stage1_eligible(
            0.03, "ordinary speech", broad_threshold=0.02, strong_threshold=0.05
        )
        is False
    )
    assert (
        stage1_eligible(
            0.03, "", broad_threshold=0.02, strong_threshold=0.05
        )
        is True
    )
    assert (
        stage1_eligible(
            0.05, "ordinary speech", broad_threshold=0.02, strong_threshold=0.05
        )
        is True
    )
    assert (
        stage1_eligible(
            0.019, "Baxi", broad_threshold=0.02, strong_threshold=0.05
        )
        is False
    )


def test_declared_baxiferrol_asr_variants_are_exact_compound_aliases() -> None:
    assert has_exact_lexical_target("Esperamos en Baxiferrol") is True
    assert has_exact_lexical_target("Esperamos en Maxiferror") is True
    assert has_exact_lexical_target("Esperamos en Maxiferrón") is True
    assert has_exact_lexical_target("Esperamos en Maxi Ferrol") is True
    assert has_exact_lexical_target("Отдел сервиса Баксин") is True


def test_audio_normalization_matches_zero_mean_unit_variance_contract() -> None:
    result = normalize_audio(np.array([1.0, 2.0, 3.0], dtype=np.float32))
    assert result.shape == (1, 3)
    np.testing.assert_allclose(result.mean(), 0.0, atol=1e-6)
    np.testing.assert_allclose(result.var(), 1.0, atol=1e-5)


def test_long_mission_keeps_only_attested_wake_prefix() -> None:
    audio = np.arange(30 * 16_000, dtype=np.float32)
    selected = verification_audio(
        audio,
        minimum_samples=16_000,
        maximum_samples=160_000,
        maximum_turn_samples=480_000,
    )
    assert selected is not None
    assert len(selected) == 160_000
    np.testing.assert_array_equal(selected, audio[:160_000])


def test_vad_turn_offset_removes_historical_audio_before_prefix() -> None:
    audio = np.arange(20 * 16_000, dtype=np.float32)
    selected = verification_audio(
        audio,
        minimum_samples=16_000,
        maximum_samples=160_000,
        maximum_turn_samples=480_000,
        start_sample=5 * 16_000,
    )
    assert selected is not None
    np.testing.assert_array_equal(
        selected, audio[5 * 16_000 : 15 * 16_000]
    )


def test_verification_views_try_primary_then_aligned_activity_context() -> None:
    assert verification_view_starts(
        primary_start_sample=64_000,
        activity_start_sample=71_040,
        activity_lookback_samples=2_560,
    ) == (64_000, 68_480, 71_040)


def test_manifest_fails_closed_without_product_calibration(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    manifest = _write_manifest(tmp_path / "asset")
    monkeypatch.delenv(
        "BAXY_VOICE_WAKE_VERIFIER_ALLOW_UNCALIBRATED", raising=False
    )

    with pytest.raises(
        WakeVerifierConfigurationError, match="wake_verifier_calibration_required"
    ):
        load_wake_verifier_config(manifest)
    candidate = load_wake_verifier_candidate_config(manifest)
    assert candidate.graph_sha256 == _sha256(candidate.graph_path)
    assert candidate.calibration == {}


def test_explicit_development_override_still_verifies_every_asset_hash(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    manifest = _write_manifest(tmp_path / "asset")
    monkeypatch.setenv("BAXY_VOICE_WAKE_VERIFIER_ALLOW_UNCALIBRATED", "on")
    config = load_wake_verifier_config(manifest)
    assert config.graph_path.name == "verifier.onnx"
    assert config.stage1_model_sha256 == "1" * 64
    assert config.stage1_phrase == "Baxy"

    config.graph_data_path.write_bytes(b"modified")
    with pytest.raises(
        WakeVerifierConfigurationError, match="wake_verifier_asset_hash_mismatch"
    ):
        load_wake_verifier_config(manifest)


def test_product_calibration_binds_complete_stage1_and_operating_point(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    manifest = _write_manifest(tmp_path / "asset")
    _approve_manifest(manifest)
    monkeypatch.delenv(
        "BAXY_VOICE_WAKE_VERIFIER_ALLOW_UNCALIBRATED", raising=False
    )

    assert load_wake_verifier_config(manifest).calibration["approved"] is True

    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["stage1DebounceSeconds"] = 2.5
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(
        WakeVerifierConfigurationError, match="wake_verifier_calibration_mismatch"
    ):
        load_wake_verifier_config(manifest)
