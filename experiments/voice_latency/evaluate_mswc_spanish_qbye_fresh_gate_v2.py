"""Open one frozen MSWC fresh-word gate and export aggregate metrics only."""

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
        raise RuntimeError(f"mswc_qbye_fresh_gate_component_invalid:{filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_BASELINE = load_component(
    "evaluate_mswc_spanish_qbye_ssl_baseline_v1.py",
    "_baxy_qbye_fresh_gate_baseline_v2",
)
_TRAINER = load_component(
    "train_mswc_spanish_qbye_angular_prototypical_v1.py",
    "_baxy_qbye_fresh_gate_trainer_v2",
)


def read_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"mswc_qbye_fresh_gate_json_invalid:{path}")
    return value


def zero_false_recall(metrics: dict[str, object]) -> float:
    return int(metrics["true_pairs_accepted_at_zero_false_pairs"]) / int(
        metrics["true_pairs"]
    )


def gate_passes(
    candidate: dict[str, object],
    reference: dict[str, object],
    thresholds: dict[str, object],
) -> tuple[bool, dict[str, bool]]:
    checks = {
        "minimum_top1_accuracy": float(candidate["top1_accuracy"])
        >= float(thresholds["minimum_top1_accuracy"]),
        "minimum_pair_auc": float(candidate["pair_auc"])
        >= float(thresholds["minimum_pair_auc"]),
        "maximum_equal_error_rate": float(candidate["equal_error_rate"])
        <= float(thresholds["maximum_equal_error_rate"]),
        "minimum_true_pair_recall_at_zero_false_pairs": zero_false_recall(candidate)
        >= float(thresholds["minimum_true_pair_recall_at_zero_false_pairs"]),
        "minimum_top1_delta_over_reference": (
            float(candidate["top1_accuracy"]) - float(reference["top1_accuracy"])
            >= float(thresholds["minimum_top1_delta_over_reference"])
        ),
        "minimum_pair_auc_delta_over_reference": (
            float(candidate["pair_auc"]) - float(reference["pair_auc"])
            >= float(thresholds["minimum_pair_auc_delta_over_reference"])
        ),
        "maximum_equal_error_rate_delta_over_reference": (
            float(candidate["equal_error_rate"])
            - float(reference["equal_error_rate"])
            <= float(thresholds["maximum_equal_error_rate_delta_over_reference"])
        ),
        "minimum_zero_false_recall_delta_over_reference": (
            zero_false_recall(candidate) - zero_false_recall(reference)
            >= float(thresholds["minimum_zero_false_recall_delta_over_reference"])
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
        raise ValueError("mswc_qbye_fresh_gate_schedule_invalid")
    preregistration_path = preregistration_path.resolve(strict=True)
    feature_manifest_path = feature_manifest_path.resolve(strict=True)
    output_path = output_path.resolve()
    preregistration = read_object(preregistration_path)
    manifest = read_object(feature_manifest_path)
    sources = preregistration.get("sources")
    contract = preregistration.get("contract")
    candidate = preregistration.get("candidate")
    reference = preregistration.get("reference")
    files = manifest.get("files")
    feature_contract = manifest.get("contract")
    records_raw = manifest.get("records")
    if (
        preregistration.get("schema")
        != "baxy.mswc-spanish-qbye-fresh-gate-preregistration.v2"
        or preregistration.get("fresh_examples_scored") is not False
        or preregistration.get("fresh_evaluation_open_count") != 0
        or manifest.get("schema")
        != "baxy.mswc-spanish-qbye-fresh-evaluation-wav2vec2-features.v2"
        or manifest.get("official_test_audio_accessed") is not False
        or manifest.get("blind_human_audio_accessed") is not False
        or not isinstance(sources, dict)
        or not isinstance(contract, dict)
        or not isinstance(candidate, dict)
        or not isinstance(reference, dict)
        or not isinstance(files, dict)
        or not isinstance(feature_contract, dict)
        or not isinstance(records_raw, list)
    ):
        raise ValueError("mswc_qbye_fresh_gate_boundary_invalid")
    if _BASELINE.sha256(feature_manifest_path) != sources.get(
        "fresh_feature_manifest_sha256"
    ):
        raise ValueError("mswc_qbye_fresh_gate_feature_manifest_mismatch")
    records = []
    for record in records_raw:
        if not isinstance(record, dict):
            raise ValueError("mswc_qbye_fresh_gate_record_invalid")
        records.append(record)
    enrollment_indexes = [
        index
        for index, record in enumerate(records)
        if record.get("partition") == "open_keyword_enrollment"
    ]
    query_indexes = [
        index
        for index, record in enumerate(records)
        if record.get("partition") == "open_keyword_query"
    ]
    enrollment_classes = [str(records[index]["class_name"]) for index in enrollment_indexes]
    query_classes = [str(records[index]["class_name"]) for index in query_indexes]
    if (
        len(enrollment_indexes) != int(contract["fresh_enrollments"])
        or len(query_indexes) != int(contract["fresh_queries"])
        or len(set(enrollment_classes)) != int(contract["fresh_word_classes"])
        or set(enrollment_classes) != set(query_classes)
    ):
        raise ValueError("mswc_qbye_fresh_gate_partition_invalid")
    root = feature_manifest_path.parent
    offset_path = root / str(files["offsets"])
    if _BASELINE.sha256(offset_path) != files.get("offsets_sha256"):
        raise ValueError("mswc_qbye_fresh_gate_offsets_hash_mismatch")
    offsets = np.load(offset_path)
    features_by_layer = files.get("features_by_layer")
    if not isinstance(features_by_layer, dict):
        raise ValueError("mswc_qbye_fresh_gate_feature_files_invalid")
    descriptor = features_by_layer.get("16")
    if not isinstance(descriptor, dict):
        raise ValueError("mswc_qbye_fresh_gate_layer16_missing")
    feature_path = root / str(descriptor["path"])
    if _BASELINE.sha256(feature_path) != descriptor.get("sha256"):
        raise ValueError("mswc_qbye_fresh_gate_layer16_hash_mismatch")
    features = np.load(feature_path, mmap_mode="r")

    import torch

    if device == "cuda" and not torch.cuda.is_available():
        raise ValueError("mswc_qbye_fresh_gate_cuda_unavailable")
    torch_device = torch.device(device)

    def checkpoint_embeddings(
        frozen: dict[str, object], indexes: list[int]
    ) -> np.ndarray:
        checkpoint_path = Path(str(frozen["checkpoint_path"])).resolve(strict=True)
        if _BASELINE.sha256(checkpoint_path) != frozen.get("checkpoint_sha256"):
            raise ValueError("mswc_qbye_fresh_gate_checkpoint_hash_mismatch")
        checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
        if (
            not isinstance(checkpoint, dict)
            or checkpoint.get("schema") != "baxy.mswc-spanish-qbye-angleproto.v1"
            or int(checkpoint["layer"]) != 16
            or checkpoint.get("feature_manifest_sha256")
            != frozen.get("training_feature_manifest_sha256")
            or int(checkpoint["embedding_size"]) != int(frozen["embedding_size"])
            or int(checkpoint["maximum_frames"]) != int(frozen["maximum_frames"])
        ):
            raise ValueError("mswc_qbye_fresh_gate_checkpoint_contract_invalid")
        model = _TRAINER.make_model(
            torch, int(checkpoint["hidden_size"]), int(checkpoint["embedding_size"])
        ).to(torch_device)
        model.load_state_dict(checkpoint["state_dict"])
        model.eval()
        outputs = []
        with torch.inference_mode():
            for start in range(0, len(indexes), prediction_batch_size):
                selected_indexes = indexes[start : start + prediction_batch_size]
                fixed = []
                masks = []
                for index in selected_indexes:
                    sequence, mask = _TRAINER.fixed_sequence(
                        features[int(offsets[index]) : int(offsets[index + 1])],
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

    reference_metrics, _ = _BASELINE.qbye_metrics(
        enrollment_embeddings=checkpoint_embeddings(reference, enrollment_indexes),
        enrollment_classes=enrollment_classes,
        query_embeddings=checkpoint_embeddings(reference, query_indexes),
        query_classes=query_classes,
    )
    candidate_metrics, _ = _BASELINE.qbye_metrics(
        enrollment_embeddings=checkpoint_embeddings(candidate, enrollment_indexes),
        enrollment_classes=enrollment_classes,
        query_embeddings=checkpoint_embeddings(candidate, query_indexes),
        query_classes=query_classes,
    )
    thresholds = contract.get("gate_thresholds")
    if not isinstance(thresholds, dict):
        raise ValueError("mswc_qbye_fresh_gate_thresholds_invalid")
    passed, checks = gate_passes(candidate_metrics, reference_metrics, thresholds)
    report: dict[str, object] = {
        "schema": "baxy.mswc-spanish-qbye-fresh-gate.v2",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "single_aggregate_open_of_fresh_disjoint_word_evaluation",
        "sources": {
            "preregistration_sha256": _BASELINE.sha256(preregistration_path),
            "fresh_feature_manifest_sha256": _BASELINE.sha256(feature_manifest_path),
            "candidate_checkpoint_sha256": candidate["checkpoint_sha256"],
            "reference_checkpoint_sha256": reference["checkpoint_sha256"],
        },
        "contract": {
            "fresh_word_classes": contract["fresh_word_classes"],
            "fresh_enrollments": contract["fresh_enrollments"],
            "fresh_queries": contract["fresh_queries"],
            "gate_thresholds": thresholds,
            "no_individual_query_export": True,
        },
        "reference": {"metrics": reference_metrics},
        "candidate": {"metrics": candidate_metrics},
        "gate": {"passed": passed, "checks": checks},
        "runtime_seconds": time.perf_counter() - started,
        "fresh_examples_scored": True,
        "fresh_evaluation_open_count": 1,
        "individual_query_metrics_exported": False,
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
