"""Freeze a reproducible V5 SSL-prototype plus CTC-rule wake candidate."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(HERE))
from audit_wake_ssl_ctc_ensemble_development_v1 import ensemble_accept  # noqa: E402
from audit_wav2vec2_hidden_wake_product_scan_v1 import sliding_vectors  # noqa: E402
from audit_wav2vec2_hidden_wake_separability_v1 import (  # noqa: E402
    _normalize,
    frame_mask,
    pool_hidden,
    sha256,
)
from audit_wav2vec2_hidden_wake_layer_sweep_expanded_v1 import normalize_rows  # noqa: E402
from baxy_mind.wake_verifier import load_wake_verifier_candidate_config  # noqa: E402


def read_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"wake_v5_candidate_json_invalid:{path}")
    return value


def fit_prototype(
    *,
    features: np.ndarray,
    offsets: np.ndarray,
    records: list[dict[str, object]],
    duration_seconds: float,
    offset_seconds: float,
    pooling: str,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, float, np.ndarray]:
    positive_vectors = []
    negative_windows = []
    scans = []
    labels = []
    for index, record in enumerate(records):
        hidden = np.asarray(
            features[int(offsets[index]) : int(offsets[index + 1])], dtype=np.float32
        )
        vectors, _ = sliding_vectors(
            hidden, duration_seconds=duration_seconds, pooling=pooling
        )
        normalized_scan = normalize_rows(vectors)
        scans.append(normalized_scan)
        positive = record["label"] == "positive"
        labels.append(1 if positive else 0)
        if positive:
            onset = record.get("target_onset_seconds")
            if onset is None:
                raise ValueError("wake_v5_candidate_human_onset_missing")
            mask = frame_mask(
                hidden.shape[0],
                onset_seconds=float(onset),
                offset_seconds=offset_seconds,
                duration_seconds=duration_seconds,
            )
            positive_vectors.append(pool_hidden(hidden, mask, pooling))
        else:
            negative_windows.append(normalized_scan)
    if not positive_vectors or not negative_windows:
        raise ValueError("wake_v5_candidate_classes_missing")
    positive_centroid = _normalize(
        normalize_rows(np.stack(positive_vectors)).mean(axis=0)
    ).astype(np.float32)
    negative_centroid = _normalize(
        np.concatenate(negative_windows, axis=0).mean(axis=0)
    ).astype(np.float32)
    direction = (positive_centroid - negative_centroid).astype(np.float32)
    scores = np.asarray(
        [float(np.max(vectors @ direction)) for vectors in scans], dtype=np.float64
    )
    target_array = np.asarray(labels, dtype=np.int64)
    threshold = float(np.nextafter(scores[target_array == 0].max(), math.inf))
    return positive_centroid, negative_centroid, direction, threshold, scores


def threshold_metrics(
    scores: np.ndarray, labels: np.ndarray, threshold: float
) -> dict[str, object]:
    values = np.asarray(scores, dtype=np.float64)
    targets = np.asarray(labels, dtype=np.int64)
    positives = values[targets == 1]
    negatives = values[targets == 0]
    return {
        "threshold": threshold,
        "positive_accepted": int(np.count_nonzero(positives >= threshold)),
        "positive_total": int(len(positives)),
        "negative_false_accepts": int(np.count_nonzero(negatives >= threshold)),
        "negative_total": int(len(negatives)),
    }


def fallback_threshold(
    scores: np.ndarray,
    labels: np.ndarray,
    explicit_confusable: np.ndarray,
) -> float:
    values = np.asarray(scores, dtype=np.float64)
    targets = np.asarray(labels, dtype=np.int64)
    vetoed = np.asarray(explicit_confusable, dtype=np.bool_)
    if values.shape != targets.shape or values.shape != vetoed.shape:
        raise ValueError("wake_v5_candidate_threshold_shape_invalid")
    eligible_negatives = values[(targets == 0) & ~vetoed]
    if not len(eligible_negatives) or not np.isfinite(eligible_negatives).all():
        raise ValueError("wake_v5_candidate_threshold_population_invalid")
    return float(np.nextafter(eligible_negatives.max(), math.inf))


def build(
    *,
    feature_manifest_path: Path,
    ensemble_report_path: Path,
    verifier_manifest_path: Path,
    stage1_model_path: Path,
    output_root: Path,
) -> dict[str, object]:
    if output_root.exists():
        raise ValueError("wake_v5_candidate_output_exists")
    feature_manifest_path = feature_manifest_path.resolve(strict=True)
    ensemble_report_path = ensemble_report_path.resolve(strict=True)
    verifier_manifest_path = verifier_manifest_path.resolve(strict=True)
    stage1_model_path = stage1_model_path.resolve(strict=True)
    output_root = output_root.resolve()
    partial_root = output_root.with_name(output_root.name + ".partial")
    if partial_root.exists():
        raise ValueError("wake_v5_candidate_partial_exists")
    feature_manifest = read_object(feature_manifest_path)
    ensemble = read_object(ensemble_report_path)
    if (
        feature_manifest.get("schema")
        != "baxy.wav2vec2-hidden-wake-training-features.v1"
        or ensemble.get("schema") != "baxy.wake-ssl-ctc-ensemble-development.v1"
        or feature_manifest.get("blind_human_audio_accessed") is not False
        or ensemble.get("blind_human_audio_accessed") is not False
        or ensemble.get("metrics", {}).get("development_gate_passed") is not True
    ):
        raise ValueError("wake_v5_candidate_boundary_invalid")
    contract = feature_manifest.get("contract")
    files = feature_manifest.get("files")
    records = feature_manifest.get("records")
    hidden_winner = ensemble.get("hidden_winner")
    if (
        not isinstance(contract, dict)
        or not isinstance(files, dict)
        or not isinstance(records, list)
        or not isinstance(hidden_winner, dict)
        or int(contract.get("layer", -1)) != int(hidden_winner.get("layer", -2))
    ):
        raise ValueError("wake_v5_candidate_contract_invalid")
    typed_records = [record for record in records if isinstance(record, dict)]
    if len(typed_records) != len(records):
        raise ValueError("wake_v5_candidate_records_invalid")
    human_indexes = [
        index
        for index, record in enumerate(typed_records)
        if str(record["corpus"]).startswith("human_")
    ]
    human_records = [typed_records[index] for index in human_indexes]
    if (
        len(human_records) != 30
        or sum(record["label"] == "positive" for record in human_records) != 18
        or sum(record["label"] == "negative" for record in human_records) != 12
    ):
        raise ValueError("wake_v5_candidate_human_counts_invalid")
    feature_root = feature_manifest_path.parent
    feature_path = feature_root / str(files["features"])
    offset_path = feature_root / str(files["offsets"])
    if (
        sha256(feature_path) != files.get("features_sha256")
        or sha256(offset_path) != files.get("offsets_sha256")
    ):
        raise ValueError("wake_v5_candidate_feature_hash_mismatch")
    all_features = np.load(feature_path, mmap_mode="r")
    all_offsets = np.load(offset_path)
    human_lengths = [
        int(all_offsets[index + 1]) - int(all_offsets[index]) for index in human_indexes
    ]
    human_offsets = np.zeros(len(human_indexes) + 1, dtype=np.int64)
    human_offsets[1:] = np.cumsum(human_lengths)
    human_features = np.concatenate(
        [
            np.asarray(
                all_features[int(all_offsets[index]) : int(all_offsets[index + 1])]
            )
            for index in human_indexes
        ],
        axis=0,
    )
    labels = np.asarray(
        [1 if record["label"] == "positive" else 0 for record in human_records],
        dtype=np.int64,
    )
    ensemble_by_path = {
        str(record["relative_path"]): record
        for record in ensemble.get("records", [])
        if isinstance(record, dict)
    }
    explicit_confusables = np.asarray(
        [
            bool(ensemble_by_path[str(record["relative_path"])]["ctc_greedy_exact_confusable"])
            for record in human_records
        ],
        dtype=np.bool_,
    )
    if len(ensemble_by_path) != len(human_records):
        raise ValueError("wake_v5_candidate_ensemble_alignment_invalid")
    ctc_positives = np.asarray(
        [
            bool(ensemble_by_path[str(record["relative_path"])]["ctc_product_detected"])
            for record in human_records
        ],
        dtype=np.bool_,
    )
    grid_results: list[dict[str, object]] = []
    best_rank: tuple[int, int, int, float] | None = None
    best_values: tuple[
        float,
        float,
        str,
        np.ndarray,
        np.ndarray,
        np.ndarray,
        float,
        np.ndarray,
        dict[str, object],
        dict[str, object],
        list[dict[str, object]],
    ] | None = None
    for window_offset in (-0.10, 0.0):
        for duration in (0.35, 0.50, 0.70, 0.90):
            for pooling in ("mean", "max"):
                (
                    positive_centroid,
                    negative_centroid,
                    direction,
                    _,
                    scores,
                ) = fit_prototype(
                    features=human_features,
                    offsets=human_offsets,
                    records=human_records,
                    duration_seconds=duration,
                    offset_seconds=window_offset,
                    pooling=pooling,
                )
                threshold = fallback_threshold(scores, labels, explicit_confusables)
                ssl_metrics = threshold_metrics(scores, labels, threshold)
                development_records = []
                for record, score in zip(human_records, scores, strict=True):
                    relative = str(record["relative_path"])
                    source = ensemble_by_path[relative]
                    ssl_accepted = bool(score >= threshold)
                    accepted, method = ensemble_accept(
                        ssl_accepted=ssl_accepted,
                        explicit_confusable=bool(source["ctc_greedy_exact_confusable"]),
                        ctc_positive=bool(source["ctc_product_detected"]),
                    )
                    development_records.append(
                        {
                            "corpus": record["corpus"],
                            "relative_path": relative,
                            "group": record["group"],
                            "label": record["label"],
                            "ssl_score": float(score),
                            "ssl_margin": float(score - threshold),
                            "ssl_accepted": ssl_accepted,
                            "ctc_positive": source["ctc_product_detected"],
                            "ctc_explicit_confusable": source["ctc_greedy_exact_confusable"],
                            "ensemble_method": method,
                            "ensemble_accepted": accepted,
                        }
                    )
                positive_records = [
                    record for record in development_records if record["label"] == "positive"
                ]
                negative_records = [
                    record for record in development_records if record["label"] == "negative"
                ]
                ensemble_metrics = {
                    "positive_accepted": sum(
                        record["ensemble_accepted"] for record in positive_records
                    ),
                    "positive_total": len(positive_records),
                    "negative_false_accepts": sum(
                        record["ensemble_accepted"] for record in negative_records
                    ),
                    "negative_total": len(negative_records),
                }
                fallback_positive_mask = (labels == 1) & ~ctc_positives
                fallback_margins = scores[fallback_positive_mask] - threshold
                fallback_accepted = int(np.count_nonzero(fallback_margins >= 0.0))
                minimum_fallback_margin = float(fallback_margins.min())
                grid_results.append(
                    {
                        "window_offset_seconds": window_offset,
                        "window_duration_seconds": duration,
                        "pooling": pooling,
                        "ssl": ssl_metrics,
                        "ensemble": ensemble_metrics,
                        "positive_records_requiring_ssl_fallback": int(
                            np.count_nonzero(fallback_positive_mask)
                        ),
                        "positive_records_accepted_by_ssl_fallback": fallback_accepted,
                        "minimum_ssl_fallback_positive_margin": minimum_fallback_margin,
                    }
                )
                rank = (
                    -int(ensemble_metrics["negative_false_accepts"]),
                    int(ensemble_metrics["positive_accepted"]),
                    fallback_accepted,
                    minimum_fallback_margin,
                )
                if best_rank is None or rank > best_rank:
                    best_rank = rank
                    best_values = (
                        window_offset,
                        duration,
                        pooling,
                        positive_centroid,
                        negative_centroid,
                        direction,
                        threshold,
                        scores,
                        ssl_metrics,
                        ensemble_metrics,
                        development_records,
                    )
    assert best_values is not None
    (
        window_offset,
        duration,
        pooling,
        positive_centroid,
        negative_centroid,
        direction,
        threshold,
        scores,
        ssl_metrics,
        ensemble_metrics,
        development_records,
    ) = best_values
    grid_results.sort(
        key=lambda item: (
            -int(item["ensemble"]["negative_false_accepts"]),
            int(item["ensemble"]["positive_accepted"]),
            int(item["positive_records_accepted_by_ssl_fallback"]),
            float(item["minimum_ssl_fallback_positive_margin"]),
        ),
        reverse=True,
    )
    if ensemble_metrics != {
        "positive_accepted": 18,
        "positive_total": 18,
        "negative_false_accepts": 0,
        "negative_total": 12,
    }:
        rejection_path = output_root.with_name(
            output_root.name + ".rejected-development.v1.json"
        )
        if rejection_path.exists():
            raise ValueError("wake_v5_candidate_rejection_output_exists")
        rejection_report = {
            "schema": "baxy.wake-ssl-ctc-global-prototype-rejection.v1",
            "measured_at_utc": datetime.now(timezone.utc).isoformat(),
            "sources": {
                "feature_manifest_sha256": sha256(feature_manifest_path),
                "ensemble_development_report_sha256": sha256(ensemble_report_path),
            },
            "method": {
                "hidden_layer": int(hidden_winner["layer"]),
                "configuration_count": len(grid_results),
                "selection": (
                    "fewest_ensemble_false_accepts_then_ensemble_positive_recall_"
                    "then_ssl_fallback_recall_then_minimum_fallback_margin"
                ),
            },
            "configuration_grid": grid_results,
            "selected_configuration": {
                "window_offset_seconds": window_offset,
                "window_duration_seconds": duration,
                "pooling": pooling,
                "ssl": ssl_metrics,
                "ensemble": ensemble_metrics,
                "records": development_records,
            },
            "decision": "rejected_global_prototype_did_not_reproduce_development_gate",
            "candidate_frozen": False,
            "product_operating_point": False,
            "blind_human_audio_accessed": False,
            "effects_executed": 0,
        }
        rejection_path.write_text(
            json.dumps(rejection_report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        raise ValueError(f"wake_v5_candidate_development_gate_failed:{ensemble_metrics}")

    verifier = load_wake_verifier_candidate_config(verifier_manifest_path)
    if sha256(stage1_model_path) != verifier.stage1_model_sha256:
        raise ValueError("wake_v5_candidate_stage1_mismatch")
    partial_root.mkdir(parents=True)
    prototype_path = partial_root / "wake-ssl-prototype-v5.npz"
    np.savez(
        prototype_path,
        positive_centroid=positive_centroid,
        negative_centroid=negative_centroid,
        direction=direction,
        threshold=np.asarray([threshold], dtype=np.float64),
    )
    report: dict[str, object] = {
        "schema": "baxy.wake-ssl-ctc-candidate.v5",
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "feature_manifest_sha256": sha256(feature_manifest_path),
            "features_sha256": files["features_sha256"],
            "offsets_sha256": files["offsets_sha256"],
            "ensemble_development_report_sha256": sha256(ensemble_report_path),
            "stage1_model_sha256": sha256(stage1_model_path),
            "verifier_manifest_sha256": sha256(verifier_manifest_path),
            "verifier_graph_sha256": sha256(verifier.graph_path),
            "verifier_graph_data_sha256": sha256(verifier.graph_data_path),
            "verifier_vocabulary_sha256": sha256(verifier.vocabulary_path),
        },
        "ssl": {
            "hidden_layer": int(hidden_winner["layer"]),
            "window_offset_seconds": window_offset,
            "window_duration_seconds": duration,
            "pooling": pooling,
            "window_hop": "one_wav2vec2_frame_20ms",
            "feature_normalization": "l2_per_window",
            "score": "cosine_positive_centroid_minus_cosine_negative_centroid",
            "threshold": threshold,
            "threshold_calibration_population": (
                "development_negatives_reaching_ssl_after_explicit_ctc_confusable_veto"
            ),
            "prototype_file": prototype_path.name,
            "prototype_sha256": sha256(prototype_path),
            "prototype_dimension": int(direction.shape[0]),
        },
        "decision": {
            "precedence": [
                "ctc_positive_authority",
                "ctc_explicit_confusable_veto",
                "ssl_score_at_or_above_threshold",
                "reject",
            ],
            "ctc_positive_authority": "existing_v4_product_acceptance",
            "ctc_confusable_veto": "exact_greedy_general_phoneme_category_sequence",
            "hardcoded_speaker_or_filename_rules": False,
        },
        "development_fit": {
            "configuration_selection": (
                "fewest_ensemble_false_accepts_then_ensemble_positive_recall_"
                "then_ssl_fallback_recall_then_minimum_fallback_margin"
            ),
            "configuration_grid": grid_results,
            "ssl": ssl_metrics,
            "ensemble": ensemble_metrics,
            "records": development_records,
        },
        "candidate_frozen": True,
        "product_operating_point": False,
        "negative_holdout_scored": False,
        "blind_human_audio_accessed": False,
        "effects_executed": 0,
    }
    report_path = partial_root / "candidate.v5.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(partial_root, output_root)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feature-manifest", type=Path, required=True)
    parser.add_argument("--ensemble-report", type=Path, required=True)
    parser.add_argument("--verifier-manifest", type=Path, required=True)
    parser.add_argument("--stage1-model", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    report = build(
        feature_manifest_path=arguments.feature_manifest,
        ensemble_report_path=arguments.ensemble_report,
        verifier_manifest_path=arguments.verifier_manifest,
        stage1_model_path=arguments.stage1_model,
        output_root=arguments.output_root,
    )
    print(
        json.dumps(
            {
                "prototype_sha256": report["ssl"]["prototype_sha256"],
                "ssl_development": report["development_fit"]["ssl"],
                "ensemble_development": report["development_fit"]["ensemble"],
                "candidate_frozen": report["candidate_frozen"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
