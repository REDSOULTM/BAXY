"""Test a frozen hidden-layer wake embedding on exact causal product views."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sys
import time

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(HERE))
from audit_wav2vec2_hidden_wake_separability_v1 import (  # noqa: E402
    FEATURE_RECEPTIVE_FIELD_SAMPLES,
    FEATURE_STRIDE_SAMPLES,
    SAMPLE_RATE,
    _normalize,
    frame_mask,
    normalize_audio,
    pool_hidden,
    read_wav,
    score_metrics,
    select_development_records,
    sha256,
)
from baxy_mind.wake_verifier import (  # noqa: E402
    load_wake_verifier_candidate_config,
    verification_audio,
    verification_view_starts,
)
from evaluate_wake_verifier_negative_holdout_v1 import capture_audio  # noqa: E402


def target_sample_in_capture(
    *, target_onset_seconds: float, hit_end_seconds: float, pre_roll_samples: int
) -> int:
    raw_start = round(hit_end_seconds * SAMPLE_RATE) - pre_roll_samples
    return round(target_onset_seconds * SAMPLE_RATE) - raw_start


def sliding_vectors(
    hidden: np.ndarray,
    *,
    duration_seconds: float,
    pooling: str,
) -> tuple[np.ndarray, np.ndarray]:
    centers = (
        np.arange(hidden.shape[0], dtype=np.float64) * FEATURE_STRIDE_SAMPLES
        + FEATURE_RECEPTIVE_FIELD_SAMPLES / 2
    ) / SAMPLE_RATE
    vectors: list[np.ndarray] = []
    starts: list[float] = []
    for start in range(hidden.shape[0]):
        end_seconds = centers[start] + duration_seconds
        mask = (centers >= centers[start]) & (centers < end_seconds)
        if mask.sum() < 2:
            continue
        vectors.append(pool_hidden(hidden, mask, pooling))
        starts.append(float(centers[start]))
    if not vectors:
        raise ValueError("wav2vec2_product_scan_windows_empty")
    return np.stack(vectors), np.asarray(starts, dtype=np.float64)


def held_out_product_scores(
    aligned_features: np.ndarray,
    product_views: list[list[tuple[int, np.ndarray, np.ndarray]]],
    labels: np.ndarray,
    groups: list[str],
) -> tuple[np.ndarray, list[dict[str, object]]]:
    aligned = np.stack([_normalize(row) for row in aligned_features])
    group_array = np.asarray(groups)
    scores = np.empty(len(labels), dtype=np.float64)
    locations: list[dict[str, object]] = [{} for _ in labels]
    for group in sorted(set(groups)):
        held = group_array == group
        train = ~held
        positive_centroid = _normalize(aligned[train & (labels == 1)].mean(axis=0))
        negative_centroid = _normalize(aligned[train & (labels == 0)].mean(axis=0))
        for index in np.flatnonzero(held):
            best_score = -math.inf
            best: dict[str, object] | None = None
            for view_start, vectors, starts in product_views[index]:
                normalized = np.stack([_normalize(row) for row in vectors])
                values = (
                    normalized @ positive_centroid
                    - normalized @ negative_centroid
                )
                location = int(np.argmax(values))
                if float(values[location]) > best_score:
                    best_score = float(values[location])
                    best = {
                        "view_start_sample": view_start,
                        "window_start_seconds_in_view": float(starts[location]),
                    }
            if best is None:
                raise ValueError("wav2vec2_product_scan_view_missing")
            scores[index] = best_score
            locations[index] = best
    return scores, locations


def audit(
    *,
    corpus_manifest_path: Path,
    product_report_path: Path,
    development_audit_path: Path,
    stage1_model_path: Path,
    verifier_manifest_path: Path,
    model_directory: Path,
    output_path: Path,
    device: str,
) -> dict[str, object]:
    if output_path.exists():
        raise ValueError("wav2vec2_product_scan_output_exists")
    if device not in {"cpu", "cuda"}:
        raise ValueError("wav2vec2_product_scan_device_invalid")
    paths = [
        corpus_manifest_path,
        product_report_path,
        development_audit_path,
        stage1_model_path,
        verifier_manifest_path,
        model_directory,
    ]
    (
        corpus_manifest_path,
        product_report_path,
        development_audit_path,
        stage1_model_path,
        verifier_manifest_path,
        model_directory,
    ) = [path.resolve(strict=True) for path in paths]
    output_path = output_path.resolve()
    corpus = json.loads(corpus_manifest_path.read_text(encoding="utf-8-sig"))
    product_report = json.loads(product_report_path.read_text(encoding="utf-8-sig"))
    development_audit = json.loads(
        development_audit_path.read_text(encoding="utf-8-sig")
    )
    if not isinstance(corpus, dict):
        raise ValueError("wav2vec2_product_scan_corpus_invalid")
    records = select_development_records(corpus)
    if (
        product_report.get("schema")
        != "baxy.wake-verifier-product-capture-development.v1"
        or product_report.get("sources", {}).get("corpus_manifest_sha256")
        != sha256(corpus_manifest_path)
        or product_report.get("sources", {}).get("stage1_model_sha256")
        != sha256(stage1_model_path)
        or product_report.get("sources", {}).get("verifier_manifest_sha256")
        != sha256(verifier_manifest_path)
    ):
        raise ValueError("wav2vec2_product_scan_report_boundary_invalid")
    if (
        development_audit.get("schema")
        != "baxy.wav2vec2-hidden-wake-separability-audit.v1"
        or development_audit.get("blind_human_audio_accessed") is not False
    ):
        raise ValueError("wav2vec2_product_scan_development_audit_invalid")
    winner = development_audit.get("winner")
    if not isinstance(winner, dict):
        raise ValueError("wav2vec2_product_scan_winner_missing")
    layer = int(winner["layer"])
    duration = float(winner["window_duration_seconds"])
    pooling = str(winner["pooling"])
    verifier_config = load_wake_verifier_candidate_config(verifier_manifest_path)
    if verifier_config.stage1_model_sha256 != sha256(stage1_model_path):
        raise ValueError("wav2vec2_product_scan_stage1_mismatch")
    report_by_path = {
        str(record["relative_path"]): record
        for record in product_report.get("records", [])
        if isinstance(record, dict)
    }
    if set(report_by_path) != {
        str(record["output_relative_path"]) for record in records
    }:
        raise ValueError("wav2vec2_product_scan_record_identity_mismatch")

    import torch
    from transformers import Wav2Vec2ForCTC

    if device == "cuda" and not torch.cuda.is_available():
        raise ValueError("wav2vec2_product_scan_cuda_unavailable")
    torch_device = torch.device(device)
    model = Wav2Vec2ForCTC.from_pretrained(
        str(model_directory), local_files_only=True
    ).eval().to(torch_device)
    pre_roll_samples = (
        int(verifier_config.stage1_pre_roll_seconds * SAMPLE_RATE / 512) * 512
    )
    corpus_root = corpus_manifest_path.parent
    aligned_features: list[np.ndarray] = []
    product_views: list[list[tuple[int, np.ndarray, np.ndarray]]] = []
    view_diagnostics: list[dict[str, object]] = []
    started = time.perf_counter()
    with torch.inference_mode():
        for record in records:
            relative = str(record["output_relative_path"])
            source_report = report_by_path[relative]
            hit = source_report.get("stage1_hit")
            if not isinstance(hit, dict):
                raise ValueError(f"wav2vec2_product_scan_stage1_hit_missing:{relative}")
            audio = read_wav(corpus_root / relative)
            capture, source_start = capture_audio(
                audio,
                hit_end_seconds=float(hit["window_end_seconds"]),
                pre_roll_seconds=verifier_config.stage1_pre_roll_seconds,
                maximum_turn_samples=verifier_config.maximum_turn_samples,
            )
            if (
                source_start != source_report.get("capture_source_start_sample")
                or len(capture) != source_report.get("capture_samples")
            ):
                raise ValueError(f"wav2vec2_product_scan_capture_mismatch:{relative}")
            activity_start = int(source_report["verification_start_sample"])
            starts = verification_view_starts(
                primary_start_sample=verifier_config.primary_view_start_samples,
                activity_start_sample=activity_start,
                activity_lookback_samples=verifier_config.activity_lookback_samples,
            )
            target_capture_sample = target_sample_in_capture(
                target_onset_seconds=float(record["target_onset_in_clip_seconds"]),
                hit_end_seconds=float(hit["window_end_seconds"]),
                pre_roll_samples=pre_roll_samples,
            )
            activity_hidden: np.ndarray | None = None
            activity_target_seconds: float | None = None
            query_views: list[tuple[int, np.ndarray, np.ndarray]] = []
            for start in starts:
                view = verification_audio(
                    capture,
                    minimum_samples=verifier_config.minimum_samples,
                    maximum_samples=verifier_config.maximum_samples,
                    maximum_turn_samples=verifier_config.maximum_turn_samples,
                    start_sample=start,
                )
                if view is None:
                    continue
                if len(view) < verifier_config.maximum_samples:
                    view = np.pad(
                        view,
                        (0, verifier_config.maximum_samples - len(view)),
                        mode="constant",
                    )
                outputs = model(
                    torch.from_numpy(normalize_audio(view))
                    .unsqueeze(0)
                    .to(torch_device),
                    output_hidden_states=True,
                )
                hidden = outputs.hidden_states[layer][0].detach().float().cpu().numpy()
                vectors, window_starts = sliding_vectors(
                    hidden, duration_seconds=duration, pooling=pooling
                )
                query_views.append((start, vectors, window_starts))
                if start == activity_start:
                    activity_hidden = hidden
                    activity_target_seconds = (
                        target_capture_sample - start
                    ) / SAMPLE_RATE
                del outputs
            if activity_hidden is None or activity_target_seconds is None:
                raise ValueError(f"wav2vec2_product_scan_activity_view_missing:{relative}")
            target_mask = frame_mask(
                activity_hidden.shape[0],
                onset_seconds=activity_target_seconds,
                offset_seconds=0.0,
                duration_seconds=duration,
            )
            aligned_features.append(pool_hidden(activity_hidden, target_mask, pooling))
            product_views.append(query_views)
            view_diagnostics.append(
                {
                    "relative_path": relative,
                    "activity_view_target_seconds": activity_target_seconds,
                    "view_starts_samples": list(starts),
                }
            )
    labels = np.asarray(
        [1 if record["label"] == "positive" else 0 for record in records],
        dtype=np.int64,
    )
    groups = [str(record["speaker_group"]) for record in records]
    scores, locations = held_out_product_scores(
        np.stack(aligned_features), product_views, labels, groups
    )
    metrics = score_metrics(scores, labels)
    scored_records = []
    for record, score, location, diagnostic in zip(
        records, scores, locations, view_diagnostics, strict=True
    ):
        scored_records.append(
            {
                **diagnostic,
                "speaker_group": record["speaker_group"],
                "label": record["label"],
                "speaker_held_out_product_scan_score": float(score),
                **location,
            }
        )
    report: dict[str, object] = {
        "schema": "baxy.wav2vec2-hidden-wake-product-scan-audit.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "development_only_exact_causal_product_views",
        "sources": {
            "corpus_manifest_sha256": sha256(corpus_manifest_path),
            "product_report_sha256": sha256(product_report_path),
            "development_audit_sha256": sha256(development_audit_path),
            "stage1_model_sha256": sha256(stage1_model_path),
            "verifier_manifest_sha256": sha256(verifier_manifest_path),
            "model_weights_sha256": sha256(model_directory / "pytorch_model.bin"),
        },
        "frozen_embedding": {
            "layer": layer,
            "window_duration_seconds": duration,
            "pooling": pooling,
            "normalization": "per_product_view_mean_variance_then_l2_embedding",
            "query": "20ms_sliding_all_product_verification_views_max_score",
            "cross_validation": "leave_one_speaker_group_out_nearest_centroid",
        },
        "metrics": metrics,
        "records": scored_records,
        "runtime_seconds": time.perf_counter() - started,
        "candidate_frozen": False,
        "product_operating_point": True,
        "blind_human_audio_accessed": False,
        "effects_executed": 0,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus-manifest", type=Path, required=True)
    parser.add_argument("--product-report", type=Path, required=True)
    parser.add_argument("--development-audit", type=Path, required=True)
    parser.add_argument("--stage1-model", type=Path, required=True)
    parser.add_argument("--verifier-manifest", type=Path, required=True)
    parser.add_argument("--model-directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    report = audit(
        corpus_manifest_path=arguments.corpus_manifest,
        product_report_path=arguments.product_report,
        development_audit_path=arguments.development_audit,
        stage1_model_path=arguments.stage1_model,
        verifier_manifest_path=arguments.verifier_manifest,
        model_directory=arguments.model_directory,
        output_path=arguments.output,
        device=arguments.device,
    )
    print(json.dumps(report["metrics"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
