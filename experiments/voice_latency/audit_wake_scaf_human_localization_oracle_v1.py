"""Separate SCAF embedding quality from product window-localization error."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import time

import numpy as np


_SCAF_PATH = Path(__file__).with_name(
    "train_wav2vec2_hidden_wake_scaf_embedding_v1.py"
)
_SCAF_SPEC = importlib.util.spec_from_file_location(
    "_baxy_wake_scaf_for_localization_oracle_v1", _SCAF_PATH
)
if _SCAF_SPEC is None or _SCAF_SPEC.loader is None:
    raise RuntimeError("wake_scaf_oracle_component_import_invalid")
_SCAF = importlib.util.module_from_spec(_SCAF_SPEC)
_SCAF_SPEC.loader.exec_module(_SCAF)


def read_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"wake_scaf_oracle_json_invalid:{path}")
    return value


def oracle_query_kind(record: dict[str, object]) -> str:
    if record["label"] == "positive":
        return "ground_truth_aligned_positive"
    if record.get("target_onset_seconds") is not None:
        return "ground_truth_aligned_hard_negative"
    return "all_sliding_windows_matched_negative"


def audit(
    *,
    model_path: Path,
    feature_manifest_path: Path,
    output_path: Path,
    window_offset_seconds: float,
    window_duration_seconds: float,
    prediction_batch_size: int,
    device: str,
) -> dict[str, object]:
    started = time.perf_counter()
    if output_path.exists() or window_duration_seconds <= 0.0 or prediction_batch_size < 1:
        raise ValueError("wake_scaf_oracle_schedule_invalid")
    model_path = model_path.resolve(strict=True)
    feature_manifest_path = feature_manifest_path.resolve(strict=True)
    output_path = output_path.resolve()
    manifest = read_object(feature_manifest_path)
    if (
        manifest.get("schema") != "baxy.wav2vec2-hidden-wake-training-features.v1"
        or manifest.get("blind_human_audio_accessed") is not False
    ):
        raise ValueError("wake_scaf_oracle_feature_boundary_invalid")
    files = manifest.get("files")
    contract = manifest.get("contract")
    source_records = manifest.get("records")
    if not isinstance(files, dict) or not isinstance(contract, dict) or not isinstance(source_records, list):
        raise ValueError("wake_scaf_oracle_manifest_invalid")
    records = []
    for record in source_records:
        if not isinstance(record, dict):
            raise ValueError("wake_scaf_oracle_record_invalid")
        records.append(record)
    root = feature_manifest_path.parent
    feature_path = root / str(files["features"])
    offset_path = root / str(files["offsets"])
    if (
        _SCAF.sha256(feature_path) != files.get("features_sha256")
        or _SCAF.sha256(offset_path) != files.get("offsets_sha256")
    ):
        raise ValueError("wake_scaf_oracle_feature_hash_mismatch")
    features = np.load(feature_path, mmap_mode="r")
    offsets = np.load(offset_path)

    import torch

    if device == "cuda" and not torch.cuda.is_available():
        raise ValueError("wake_scaf_oracle_cuda_unavailable")
    torch_device = torch.device(device)
    checkpoint = torch.load(model_path, map_location="cpu", weights_only=False)
    if (
        not isinstance(checkpoint, dict)
        or checkpoint.get("schema")
        not in {
            "baxy.mswc-wake-scaf-embedding.v1",
            "baxy.wav2vec2-hidden-wake-scaf-embedding.v1",
        }
        or not isinstance(checkpoint.get("state_dict"), dict)
    ):
        raise ValueError("wake_scaf_oracle_checkpoint_invalid")
    hidden_size = int(checkpoint["hidden_size"])
    embedding_size = int(checkpoint["embedding_size"])
    maximum_frames = int(checkpoint["maximum_frames"])
    if hidden_size != int(contract["hidden_size"]) or features.shape[1] != hidden_size:
        raise ValueError("wake_scaf_oracle_hidden_contract_mismatch")
    model = _SCAF.make_model(torch, hidden_size, embedding_size).to(torch_device)
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()

    def embed_arrays(arrays: list[np.ndarray]) -> list[np.ndarray]:
        outputs = []
        with torch.inference_mode():
            for start in range(0, len(arrays), prediction_batch_size):
                selected = arrays[start : start + prediction_batch_size]
                fixed = []
                masks = []
                for values in selected:
                    sequence, mask = _SCAF.fixed_sequence(values, maximum_frames)
                    fixed.append(sequence)
                    masks.append(mask)
                x = torch.from_numpy(np.stack(fixed)).to(torch_device)
                mask_tensor = torch.from_numpy(np.stack(masks)).to(torch_device)
                outputs.extend(model(x, mask_tensor).float().cpu().numpy())
        return outputs

    human_indexes = [
        index
        for index, record in enumerate(records)
        if str(record["corpus"]).startswith("human_")
    ]
    if len(human_indexes) != 30:
        raise ValueError("wake_scaf_oracle_human_count_invalid")
    window_frames = max(2, round(window_duration_seconds / 0.02))
    enrollment_arrays = []
    query_arrays_by_record: list[list[np.ndarray]] = []
    labels = []
    groups = []
    kinds = []
    for index in human_indexes:
        record = records[index]
        hidden = np.asarray(
            features[int(offsets[index]) : int(offsets[index + 1])], dtype=np.float32
        )
        positive = record["label"] == "positive"
        labels.append(1 if positive else 0)
        groups.append(str(record["group"]))
        kind = oracle_query_kind(record)
        kinds.append(kind)
        onset = record.get("target_onset_seconds")
        if onset is not None:
            centers = np.arange(len(hidden), dtype=np.float64) * 0.02 + 0.0125
            start_seconds = max(0.0, float(onset) + window_offset_seconds)
            start_frame = int(np.argmin(np.abs(centers - start_seconds)))
            aligned = hidden[start_frame : min(len(hidden), start_frame + window_frames)]
        else:
            aligned = hidden[:2]
        enrollment_arrays.append(aligned)
        if kind.startswith("ground_truth_aligned"):
            query_arrays_by_record.append([aligned])
        else:
            starts = list(range(0, max(1, len(hidden) - window_frames + 1)))
            final_start = max(0, len(hidden) - window_frames)
            if starts[-1] != final_start:
                starts.append(final_start)
            query_arrays_by_record.append(
                [hidden[start : min(len(hidden), start + window_frames)] for start in starts]
            )
    positive_positions = [index for index, label in enumerate(labels) if label == 1]
    positive_embeddings = embed_arrays(
        [enrollment_arrays[index] for index in positive_positions]
    )
    aligned_embeddings = np.zeros((len(human_indexes), embedding_size), dtype=np.float32)
    for index, embedding in zip(positive_positions, positive_embeddings, strict=True):
        aligned_embeddings[index] = embedding
    flat_queries = [array for arrays in query_arrays_by_record for array in arrays]
    flat_embeddings = embed_arrays(flat_queries)
    query_embeddings = []
    cursor = 0
    for arrays in query_arrays_by_record:
        query_embeddings.append(np.stack(flat_embeddings[cursor : cursor + len(arrays)]))
        cursor += len(arrays)
    target_array = np.asarray(labels, dtype=np.int64)
    margins, folds = _SCAF.human_group_margins(
        aligned_positive_embeddings=aligned_embeddings,
        scan_embeddings=query_embeddings,
        labels=target_array,
        groups=groups,
    )
    metrics = _SCAF.margin_metrics(margins, target_array)
    report: dict[str, object] = {
        "schema": "baxy.wake-scaf-human-localization-oracle.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "development_only_representation_diagnostic_not_product_policy",
        "sources": {
            "model_sha256": _SCAF.sha256(model_path),
            "feature_manifest_sha256": _SCAF.sha256(feature_manifest_path),
            "features_sha256": files["features_sha256"],
            "offsets_sha256": files["offsets_sha256"],
        },
        "contract": {
            "window_offset_seconds": window_offset_seconds,
            "window_duration_seconds": window_duration_seconds,
            "positive_queries": "ground_truth_aligned_single_window",
            "hard_negative_queries": "ground_truth_aligned_single_window",
            "matched_negative_queries": "all_20ms_sliding_windows",
            "cross_validation": "leave_one_complete_speaker_or_source_group_out",
            "fold_threshold": "nextafter_max_training_negative_query_score",
        },
        "metrics": {**metrics, "folds": folds},
        "records": [
            {
                "corpus": records[index]["corpus"],
                "relative_path": records[index]["relative_path"],
                "group": records[index]["group"],
                "label": records[index]["label"],
                "source_label": records[index].get("source_label"),
                "query_kind": kind,
                "speaker_held_out_margin": float(margin),
                "accepted": bool(margin >= 0.0),
            }
            for index, kind, margin in zip(human_indexes, kinds, margins, strict=True)
        ],
        "runtime_seconds": time.perf_counter() - started,
        "development_only": True,
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
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--feature-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--window-offset-seconds", type=float, default=-0.1)
    parser.add_argument("--window-duration-seconds", type=float, default=1.1)
    parser.add_argument("--prediction-batch-size", type=int, default=128)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    report = audit(
        model_path=arguments.model,
        feature_manifest_path=arguments.feature_manifest,
        output_path=arguments.output,
        window_offset_seconds=arguments.window_offset_seconds,
        window_duration_seconds=arguments.window_duration_seconds,
        prediction_batch_size=arguments.prediction_batch_size,
        device=arguments.device,
    )
    print(json.dumps(report["metrics"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
