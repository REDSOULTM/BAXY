"""Open the reserved MSWC word selection split for one frozen QbyE choice."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import time

import numpy as np


def load_component(filename: str, name: str) -> object:
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"mswc_qbye_selection_component_invalid:{filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_BASELINE = load_component(
    "evaluate_mswc_spanish_qbye_ssl_baseline_v1.py", "_baxy_qbye_selection_baseline_v1"
)
_TRAINER = load_component(
    "train_mswc_spanish_qbye_angular_prototypical_v1.py",
    "_baxy_qbye_selection_trainer_v1",
)


def read_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"mswc_qbye_selection_json_invalid:{path}")
    return value


def gate_passes(
    candidate: dict[str, object],
    baseline: dict[str, object],
    thresholds: dict[str, object],
) -> tuple[bool, dict[str, bool]]:
    checks = {
        "minimum_top1_accuracy": float(candidate["top1_accuracy"])
        >= float(thresholds["minimum_top1_accuracy"]),
        "minimum_pair_auc": float(candidate["pair_auc"])
        >= float(thresholds["minimum_pair_auc"]),
        "maximum_equal_error_rate": float(candidate["equal_error_rate"])
        <= float(thresholds["maximum_equal_error_rate"]),
        "minimum_true_pair_recall_at_zero_false_pairs": (
            int(candidate["true_pairs_accepted_at_zero_false_pairs"])
            / int(candidate["true_pairs"])
            >= float(thresholds["minimum_true_pair_recall_at_zero_false_pairs"])
        ),
        "minimum_top1_delta_over_frozen_ssl_baseline": (
            float(candidate["top1_accuracy"]) - float(baseline["top1_accuracy"])
            >= float(thresholds["minimum_top1_delta_over_frozen_ssl_baseline"])
        ),
    }
    return all(checks.values()), checks


def evaluate(
    *,
    preregistration_path: Path,
    feature_manifest_path: Path,
    output_path: Path,
    prediction_batch_size: int,
    device: str,
) -> dict[str, object]:
    started = time.perf_counter()
    if output_path.exists() or prediction_batch_size < 1 or device not in {"cpu", "cuda"}:
        raise ValueError("mswc_qbye_selection_schedule_invalid")
    preregistration_path = preregistration_path.resolve(strict=True)
    feature_manifest_path = feature_manifest_path.resolve(strict=True)
    output_path = output_path.resolve()
    preregistration = read_object(preregistration_path)
    manifest = read_object(feature_manifest_path)
    prereg_sources = preregistration.get("sources")
    prereg_contract = preregistration.get("contract")
    selected = preregistration.get("selected_candidate")
    frozen_baseline = preregistration.get("frozen_baseline")
    files = manifest.get("files")
    feature_contract = manifest.get("contract")
    records_raw = manifest.get("records")
    if (
        preregistration.get("schema")
        != "baxy.mswc-spanish-qbye-selection-preregistration.v1"
        or preregistration.get("open_selection_examples_scored") is not False
        or manifest.get("schema") != "baxy.mswc-spanish-qbye-wav2vec2-features.v1"
        or manifest.get("official_test_audio_accessed") is not False
        or manifest.get("blind_human_audio_accessed") is not False
        or not isinstance(prereg_sources, dict)
        or not isinstance(prereg_contract, dict)
        or not isinstance(selected, dict)
        or not isinstance(frozen_baseline, dict)
        or not isinstance(files, dict)
        or not isinstance(feature_contract, dict)
        or not isinstance(records_raw, list)
    ):
        raise ValueError("mswc_qbye_selection_boundary_invalid")
    if _BASELINE.sha256(feature_manifest_path) != prereg_sources.get(
        "feature_manifest_sha256"
    ):
        raise ValueError("mswc_qbye_selection_feature_manifest_mismatch")
    records = []
    for record in records_raw:
        if not isinstance(record, dict):
            raise ValueError("mswc_qbye_selection_record_invalid")
        records.append(record)
    open_words = {
        str(record["class_name"])
        for record in records
        if str(record["partition"]).startswith("open_keyword_")
    }
    _, selection_words = _BASELINE.split_open_words(
        open_words, seed=int(prereg_contract["open_split_seed"])
    )
    enrollment_indexes = [
        index
        for index, record in enumerate(records)
        if record["partition"] == "open_keyword_enrollment"
        and str(record["class_name"]) in selection_words
    ]
    query_indexes = [
        index
        for index, record in enumerate(records)
        if record["partition"] == "open_keyword_query"
        and str(record["class_name"]) in selection_words
    ]
    if len(enrollment_indexes) != 400 or len(query_indexes) != 1200:
        raise ValueError("mswc_qbye_selection_partition_invalid")
    root = feature_manifest_path.parent
    offset_path = root / str(files["offsets"])
    if _BASELINE.sha256(offset_path) != files.get("offsets_sha256"):
        raise ValueError("mswc_qbye_selection_offsets_hash_mismatch")
    offsets = np.load(offset_path)
    features_by_layer = files.get("features_by_layer")
    if not isinstance(features_by_layer, dict):
        raise ValueError("mswc_qbye_selection_feature_files_invalid")

    loaded_layers: dict[int, np.ndarray] = {}

    def layer_features(layer: int) -> np.ndarray:
        if layer in loaded_layers:
            return loaded_layers[layer]
        descriptor = features_by_layer.get(str(layer))
        if not isinstance(descriptor, dict):
            raise ValueError(f"mswc_qbye_selection_layer_missing:{layer}")
        path = root / str(descriptor["path"])
        if _BASELINE.sha256(path) != descriptor.get("sha256"):
            raise ValueError(f"mswc_qbye_selection_layer_hash_mismatch:{layer}")
        values = np.load(path, mmap_mode="r")
        loaded_layers[layer] = values
        return values

    enrollment_classes = [str(records[index]["class_name"]) for index in enrollment_indexes]
    query_classes = [str(records[index]["class_name"]) for index in query_indexes]

    baseline_layer = int(frozen_baseline["layer"])
    baseline_pooling = str(frozen_baseline["pooling"])
    baseline_centered = bool(frozen_baseline["training_global_center_subtracted"])
    baseline_features = layer_features(baseline_layer)
    training_center = None
    if baseline_centered:
        training_indexes = [
            index
            for index, record in enumerate(records)
            if record["partition"] == "metric_training"
        ]
        pooled_sum = None
        for index in training_indexes:
            embedding = _BASELINE.pooled_embedding(
                baseline_features[int(offsets[index]) : int(offsets[index + 1])],
                baseline_pooling,
            )
            if pooled_sum is None:
                pooled_sum = np.zeros_like(embedding)
            pooled_sum += embedding
        assert pooled_sum is not None
        training_center = pooled_sum / len(training_indexes)

    def baseline_embeddings(indexes: list[int]) -> np.ndarray:
        result = np.stack(
            [
                _BASELINE.pooled_embedding(
                    baseline_features[int(offsets[index]) : int(offsets[index + 1])],
                    baseline_pooling,
                )
                for index in indexes
            ]
        )
        return result - training_center if training_center is not None else result

    baseline_metrics, baseline_queries = _BASELINE.qbye_metrics(
        enrollment_embeddings=baseline_embeddings(enrollment_indexes),
        enrollment_classes=enrollment_classes,
        query_embeddings=baseline_embeddings(query_indexes),
        query_classes=query_classes,
    )

    checkpoint_path = Path(str(selected["checkpoint_path"])).resolve(strict=True)
    if _BASELINE.sha256(checkpoint_path) != selected.get("checkpoint_sha256"):
        raise ValueError("mswc_qbye_selection_checkpoint_hash_mismatch")
    import torch

    if device == "cuda" and not torch.cuda.is_available():
        raise ValueError("mswc_qbye_selection_cuda_unavailable")
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    if (
        not isinstance(checkpoint, dict)
        or checkpoint.get("schema") != "baxy.mswc-spanish-qbye-angleproto.v1"
        or int(checkpoint["layer"]) != int(selected["layer"])
        or checkpoint.get("feature_manifest_sha256")
        != prereg_sources["feature_manifest_sha256"]
    ):
        raise ValueError("mswc_qbye_selection_checkpoint_contract_invalid")
    candidate_layer = int(checkpoint["layer"])
    candidate_features = layer_features(candidate_layer)
    torch_device = torch.device(device)
    model = _TRAINER.make_model(
        torch, int(checkpoint["hidden_size"]), int(checkpoint["embedding_size"])
    ).to(torch_device)
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()

    def candidate_embeddings(indexes: list[int]) -> np.ndarray:
        outputs = []
        with torch.inference_mode():
            for start in range(0, len(indexes), prediction_batch_size):
                selected_indexes = indexes[start : start + prediction_batch_size]
                fixed = []
                masks = []
                for index in selected_indexes:
                    sequence, mask = _TRAINER.fixed_sequence(
                        candidate_features[
                            int(offsets[index]) : int(offsets[index + 1])
                        ],
                        int(checkpoint["maximum_frames"]),
                    )
                    fixed.append(sequence)
                    masks.append(mask)
                outputs.append(
                    model(
                        torch.from_numpy(np.stack(fixed)).to(torch_device),
                        torch.from_numpy(np.stack(masks)).to(torch_device),
                    )
                    .float()
                    .cpu()
                    .numpy()
                )
        return np.concatenate(outputs)

    candidate_metrics, candidate_queries = _BASELINE.qbye_metrics(
        enrollment_embeddings=candidate_embeddings(enrollment_indexes),
        enrollment_classes=enrollment_classes,
        query_embeddings=candidate_embeddings(query_indexes),
        query_classes=query_classes,
    )
    thresholds = prereg_contract.get("selection_gate")
    if not isinstance(thresholds, dict):
        raise ValueError("mswc_qbye_selection_thresholds_invalid")
    passed, checks = gate_passes(candidate_metrics, baseline_metrics, thresholds)
    report: dict[str, object] = {
        "schema": "baxy.mswc-spanish-qbye-selection-gate.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "single_open_of_reserved_word_selection_partition",
        "sources": {
            "preregistration_sha256": _BASELINE.sha256(preregistration_path),
            "feature_manifest_sha256": _BASELINE.sha256(feature_manifest_path),
            "checkpoint_sha256": _BASELINE.sha256(checkpoint_path),
        },
        "contract": {
            "open_split_seed": prereg_contract["open_split_seed"],
            "selection_word_classes": len(selection_words),
            "gate_thresholds": thresholds,
            "candidate": {
                "layer": selected["layer"],
                "objective": selected["objective"],
                "seed": selected["seed"],
                "best_epoch": selected["best_epoch"],
            },
            "baseline": {
                "layer": baseline_layer,
                "pooling": baseline_pooling,
                "training_global_center_subtracted": baseline_centered,
            },
        },
        "baseline": {"metrics": baseline_metrics, "queries": baseline_queries},
        "candidate": {"metrics": candidate_metrics, "queries": candidate_queries},
        "gate": {"passed": passed, "checks": checks},
        "runtime_seconds": time.perf_counter() - started,
        "open_selection_examples_scored": True,
        "open_selection_open_count": 1,
        "baxy_human_examples_scored": False,
        "official_test_audio_accessed": False,
        "blind_human_audio_accessed": False,
        "candidate_frozen": passed,
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
    parser.add_argument("--preregistration", type=Path, required=True)
    parser.add_argument("--feature-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prediction-batch-size", type=int, default=256)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = evaluate(
        preregistration_path=args.preregistration,
        feature_manifest_path=args.feature_manifest,
        output_path=args.output,
        prediction_batch_size=args.prediction_batch_size,
        device=args.device,
    )
    print(json.dumps(report["gate"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
