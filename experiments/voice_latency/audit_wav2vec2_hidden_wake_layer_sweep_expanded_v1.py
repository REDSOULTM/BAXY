"""Sweep Wav2Vec2 layers on expanded, speaker-held-out product wake scans."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from importlib.metadata import version
import json
import math
from pathlib import Path
import sys
import time

import numpy as np


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from audit_wav2vec2_hidden_wake_expanded_development_v1 import (  # noqa: E402
    canonical_group,
    selected_records,
)
from audit_wav2vec2_hidden_wake_product_scan_v1 import sliding_vectors  # noqa: E402
from audit_wav2vec2_hidden_wake_separability_v1 import (  # noqa: E402
    _normalize,
    frame_mask,
    normalize_audio,
    pool_hidden,
    read_wav,
    sha256,
)


LAYERS = (0, 2, 4, 8, 12, 16, 20, 24)
OFFSETS_SECONDS = (-0.10, 0.0)
DURATIONS_SECONDS = (0.35, 0.50, 0.70, 0.90)
POOLING_METHODS = ("mean", "max")


def normalize_rows(values: np.ndarray) -> np.ndarray:
    rows = np.asarray(values, dtype=np.float32)
    if rows.ndim != 2 or not len(rows) or not np.isfinite(rows).all():
        raise ValueError("wake_layer_sweep_vectors_invalid")
    norms = np.linalg.norm(rows, axis=1, keepdims=True)
    if np.any(norms <= 0.0):
        raise ValueError("wake_layer_sweep_vector_norm_invalid")
    return rows / norms


def speaker_held_out_product_margins(
    *,
    aligned_positive_vectors: np.ndarray,
    product_vectors: list[np.ndarray],
    labels: np.ndarray,
    groups: list[str],
) -> tuple[np.ndarray, np.ndarray, list[dict[str, object]]]:
    aligned = np.asarray(aligned_positive_vectors, dtype=np.float32)
    if aligned.ndim != 2 or len(aligned) != len(labels) or not np.isfinite(aligned).all():
        raise ValueError("wake_layer_sweep_aligned_vectors_invalid")
    scans = [normalize_rows(values) for values in product_vectors]
    targets = np.asarray(labels, dtype=np.int64)
    group_array = np.asarray(groups)
    margins = np.empty(len(targets), dtype=np.float64)
    raw_scores = np.empty(len(targets), dtype=np.float64)
    fold_reports: list[dict[str, object]] = []
    for group in sorted(set(groups)):
        held = group_array == group
        train = ~held
        positive_indexes = np.flatnonzero(train & (targets == 1))
        negative_indexes = np.flatnonzero(train & (targets == 0))
        if not len(positive_indexes) or not len(negative_indexes):
            raise ValueError(f"wake_layer_sweep_fold_class_missing:{group}")
        positive_centroid = _normalize(
            normalize_rows(aligned[positive_indexes]).mean(axis=0)
        )
        negative_centroid = _normalize(
            np.concatenate([scans[index] for index in negative_indexes], axis=0).mean(axis=0)
        )
        direction = positive_centroid - negative_centroid
        training_negative_clip_scores = np.asarray(
            [float(np.max(scans[index] @ direction)) for index in negative_indexes]
        )
        threshold = float(np.nextafter(training_negative_clip_scores.max(), math.inf))
        held_indexes = np.flatnonzero(held)
        held_scores = np.asarray(
            [float(np.max(scans[index] @ direction)) for index in held_indexes]
        )
        held_margins = held_scores - threshold
        raw_scores[held_indexes] = held_scores
        margins[held_indexes] = held_margins
        held_labels = targets[held_indexes]
        fold_reports.append(
            {
                "held_group": group,
                "training_positive_clips": int(len(positive_indexes)),
                "training_negative_clips": int(len(negative_indexes)),
                "training_negative_threshold": threshold,
                "held_positive_count": int(np.count_nonzero(held_labels == 1)),
                "held_negative_count": int(np.count_nonzero(held_labels == 0)),
                "held_positive_accepted": int(
                    np.count_nonzero(held_margins[held_labels == 1] >= 0.0)
                ),
                "held_negative_false_accepts": int(
                    np.count_nonzero(held_margins[held_labels == 0] >= 0.0)
                ),
            }
        )
    return margins, raw_scores, fold_reports


def margin_metrics(margins: np.ndarray, labels: np.ndarray) -> dict[str, object]:
    from sklearn.metrics import roc_auc_score

    values = np.asarray(margins, dtype=np.float64)
    targets = np.asarray(labels, dtype=np.int64)
    positives = values[targets == 1]
    negatives = values[targets == 0]
    if not len(positives) or not len(negatives) or not np.isfinite(values).all():
        raise ValueError("wake_layer_sweep_metrics_invalid")
    return {
        "speaker_held_out_auc": float(roc_auc_score(targets, values)),
        "threshold": 0.0,
        "positive_accepted": int(np.count_nonzero(positives >= 0.0)),
        "positive_total": int(len(positives)),
        "negative_false_accepts": int(np.count_nonzero(negatives >= 0.0)),
        "negative_total": int(len(negatives)),
    }


def config_rank(metrics: dict[str, object]) -> tuple[int, int, float]:
    return (
        -int(metrics["negative_false_accepts"]),
        int(metrics["positive_accepted"]),
        float(metrics["speaker_held_out_auc"]),
    )


def audit(
    *,
    legacy_manifest_path: Path,
    expanded_manifest_path: Path,
    model_directory: Path,
    output_path: Path,
    layers: list[int],
    device: str,
) -> dict[str, object]:
    if (
        output_path.exists()
        or not layers
        or len(set(layers)) != len(layers)
        or min(layers) < 0
        or device not in {"cpu", "cuda"}
    ):
        raise ValueError("wake_layer_sweep_schedule_invalid")
    legacy_manifest_path = legacy_manifest_path.resolve(strict=True)
    expanded_manifest_path = expanded_manifest_path.resolve(strict=True)
    model_directory = model_directory.resolve(strict=True)
    output_path = output_path.resolve()
    legacy = json.loads(legacy_manifest_path.read_text(encoding="utf-8-sig"))
    expanded = json.loads(expanded_manifest_path.read_text(encoding="utf-8-sig"))
    if not isinstance(legacy, dict) or not isinstance(expanded, dict):
        raise ValueError("wake_layer_sweep_manifest_invalid")
    records = selected_records(legacy, expanded)
    if any(record.get("partition") != "development" for record in records):
        raise ValueError("wake_layer_sweep_blind_boundary_invalid")

    import torch
    from transformers import Wav2Vec2ForCTC

    if device == "cuda" and not torch.cuda.is_available():
        raise ValueError("wake_layer_sweep_cuda_unavailable")
    torch_device = torch.device(device)
    model = Wav2Vec2ForCTC.from_pretrained(
        str(model_directory), local_files_only=True
    ).eval().to(torch_device)
    hidden_count = len(model.wav2vec2.encoder.layers) + 1
    if max(layers) >= hidden_count:
        raise ValueError("wake_layer_sweep_layer_invalid")
    roots = {
        "legacy": legacy_manifest_path.parent,
        "expanded": expanded_manifest_path.parent,
    }
    hidden_records: list[dict[int, np.ndarray]] = []
    started = time.perf_counter()
    with torch.inference_mode():
        for record in records:
            path = roots[str(record["corpus"])] / str(record["output_relative_path"])
            wav = record.get("wav")
            if not isinstance(wav, dict) or sha256(path) != wav.get("sha256"):
                raise ValueError(f"wake_layer_sweep_audio_hash_mismatch:{path}")
            audio = normalize_audio(read_wav(path))
            outputs = model.wav2vec2(
                torch.from_numpy(audio).unsqueeze(0).to(torch_device),
                output_hidden_states=True,
            )
            hidden_records.append(
                {
                    layer: outputs.hidden_states[layer][0]
                    .detach()
                    .float()
                    .cpu()
                    .numpy()
                    for layer in layers
                }
            )
            del outputs

    labels = np.asarray(
        [1 if record["label"] == "positive" else 0 for record in records],
        dtype=np.int64,
    )
    groups = [canonical_group(record) for record in records]
    configurations: list[dict[str, object]] = []
    winner: dict[str, object] | None = None
    winner_rank: tuple[int, int, float] | None = None
    for layer in layers:
        hidden_for_layer = [values[layer] for values in hidden_records]
        for offset in OFFSETS_SECONDS:
            for duration in DURATIONS_SECONDS:
                for pooling in POOLING_METHODS:
                    aligned = []
                    product = []
                    for hidden, record in zip(hidden_for_layer, records, strict=True):
                        if record["label"] == "positive":
                            onset = float(record["target_onset_in_clip_seconds"])
                            mask = frame_mask(
                                hidden.shape[0],
                                onset_seconds=onset,
                                offset_seconds=offset,
                                duration_seconds=duration,
                            )
                            aligned.append(pool_hidden(hidden, mask, pooling))
                        else:
                            # Placeholder is never used for the positive centroid.
                            aligned.append(np.zeros(hidden.shape[1], dtype=np.float32))
                        vectors, _ = sliding_vectors(
                            hidden,
                            duration_seconds=duration,
                            pooling=pooling,
                        )
                        product.append(vectors)
                    margins, raw_scores, folds = speaker_held_out_product_margins(
                        aligned_positive_vectors=np.stack(aligned),
                        product_vectors=product,
                        labels=labels,
                        groups=groups,
                    )
                    metrics = margin_metrics(margins, labels)
                    result: dict[str, object] = {
                        "layer": layer,
                        "window_offset_seconds": offset,
                        "window_duration_seconds": duration,
                        "pooling": pooling,
                        "metrics": metrics,
                        "folds": folds,
                        "records": [
                            {
                                "corpus": record["corpus"],
                                "relative_path": record["output_relative_path"],
                                "group": group,
                                "label": record["label"],
                                "raw_speaker_held_out_score": float(raw_score),
                                "calibrated_margin": float(margin),
                                "accepted": bool(margin >= 0.0),
                            }
                            for record, group, raw_score, margin in zip(
                                records, groups, raw_scores, margins, strict=True
                            )
                        ],
                    }
                    configurations.append(result)
                    rank = config_rank(metrics)
                    if winner_rank is None or rank > winner_rank:
                        winner_rank = rank
                        winner = result
    assert winner is not None
    configurations.sort(key=lambda item: config_rank(item["metrics"]), reverse=True)
    report: dict[str, object] = {
        "schema": "baxy.wav2vec2-hidden-wake-expanded-layer-sweep.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "expanded_development_only_speaker_held_out_product_scan",
        "sources": {
            "legacy_manifest_sha256": sha256(legacy_manifest_path),
            "expanded_manifest_sha256": sha256(expanded_manifest_path),
            "model_weights_sha256": sha256(model_directory / "pytorch_model.bin"),
            "model_config_sha256": sha256(model_directory / "config.json"),
        },
        "dependencies": {
            "torch": version("torch"),
            "transformers": version("transformers"),
            "numpy": version("numpy"),
            "scikit_learn": version("scikit-learn"),
            "torch_cuda": torch.version.cuda,
            "torch_cudnn": torch.backends.cudnn.version(),
            "cuda_device": torch.cuda.get_device_name(0) if device == "cuda" else None,
        },
        "method": {
            "layers": layers,
            "window_offsets_seconds": list(OFFSETS_SECONDS),
            "window_durations_seconds": list(DURATIONS_SECONDS),
            "pooling_methods": list(POOLING_METHODS),
            "configuration_count": len(configurations),
            "training_positive_representation": "ground_truth_aligned_window",
            "training_negative_representation": "all_sliding_windows",
            "inference": "maximum_score_over_all_20ms_sliding_windows",
            "cross_validation": "leave_one_complete_speaker_or_source_group_out",
            "fold_calibration": "nextafter_max_training_negative_clip_score",
            "selection": "fewest_false_accepts_then_positive_accepts_then_auc",
        },
        "winner": winner,
        "configurations": configurations,
        "runtime_seconds": time.perf_counter() - started,
        "candidate_frozen": False,
        "product_operating_point": False,
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
    parser.add_argument("--legacy-manifest", type=Path, required=True)
    parser.add_argument("--expanded-manifest", type=Path, required=True)
    parser.add_argument("--model-directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--layers", type=int, nargs="+", default=list(LAYERS))
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    report = audit(
        legacy_manifest_path=arguments.legacy_manifest,
        expanded_manifest_path=arguments.expanded_manifest,
        model_directory=arguments.model_directory,
        output_path=arguments.output,
        layers=arguments.layers,
        device=arguments.device,
    )
    winner = report["winner"]
    print(
        json.dumps(
            {
                "layer": winner["layer"],
                "window_offset_seconds": winner["window_offset_seconds"],
                "window_duration_seconds": winner["window_duration_seconds"],
                "pooling": winner["pooling"],
                "metrics": winner["metrics"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
