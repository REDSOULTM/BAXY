"""Evaluate concatenated QbyE checkpoint heads on open-word tuning only."""

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
        raise RuntimeError(f"mswc_qbye_ensemble_component_invalid:{filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_EVAL = load_component(
    "evaluate_mswc_spanish_qbye_ssl_baseline_v1.py", "_baxy_qbye_ensemble_eval_v1"
)
_TRAINER = load_component(
    "train_mswc_spanish_qbye_angular_prototypical_v1.py",
    "_baxy_qbye_ensemble_trainer_v1",
)


def read_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"mswc_qbye_ensemble_json_invalid:{path}")
    return value


def concatenate_embeddings(components: list[np.ndarray]) -> np.ndarray:
    if len(components) < 2 or len({len(values) for values in components}) != 1:
        raise ValueError("mswc_qbye_ensemble_components_invalid")
    normalized = [_EVAL.l2_normalize(values) for values in components]
    return _EVAL.l2_normalize(np.concatenate(normalized, axis=1))


def evaluate(
    *,
    feature_manifest_path: Path,
    checkpoint_paths: list[Path],
    output_path: Path,
    open_split_seed: int,
    prediction_batch_size: int,
    device: str,
) -> dict[str, object]:
    started = time.perf_counter()
    if (
        output_path.exists()
        or len(checkpoint_paths) < 2
        or prediction_batch_size < 1
        or device not in {"cpu", "cuda"}
    ):
        raise ValueError("mswc_qbye_ensemble_schedule_invalid")
    feature_manifest_path = feature_manifest_path.resolve(strict=True)
    checkpoint_paths = [path.resolve(strict=True) for path in checkpoint_paths]
    output_path = output_path.resolve()
    manifest = read_object(feature_manifest_path)
    files = manifest.get("files")
    contract = manifest.get("contract")
    records_raw = manifest.get("records")
    if (
        manifest.get("schema") != "baxy.mswc-spanish-qbye-wav2vec2-features.v1"
        or manifest.get("official_test_audio_accessed") is not False
        or manifest.get("blind_human_audio_accessed") is not False
        or not isinstance(files, dict)
        or not isinstance(contract, dict)
        or not isinstance(records_raw, list)
    ):
        raise ValueError("mswc_qbye_ensemble_boundary_invalid")
    records = []
    for record in records_raw:
        if not isinstance(record, dict):
            raise ValueError("mswc_qbye_ensemble_record_invalid")
        records.append(record)
    open_words = {
        str(record["class_name"])
        for record in records
        if str(record["partition"]).startswith("open_keyword_")
    }
    tuning_words, _ = _EVAL.split_open_words(open_words, seed=open_split_seed)
    enrollment_indexes = [
        index
        for index, record in enumerate(records)
        if record["partition"] == "open_keyword_enrollment"
        and str(record["class_name"]) in tuning_words
    ]
    query_indexes = [
        index
        for index, record in enumerate(records)
        if record["partition"] == "open_keyword_query"
        and str(record["class_name"]) in tuning_words
    ]
    root = feature_manifest_path.parent
    offset_path = root / str(files["offsets"])
    if _EVAL.sha256(offset_path) != files.get("offsets_sha256"):
        raise ValueError("mswc_qbye_ensemble_offsets_hash_mismatch")
    offsets = np.load(offset_path)
    features_by_layer = files.get("features_by_layer")
    if not isinstance(features_by_layer, dict):
        raise ValueError("mswc_qbye_ensemble_feature_files_invalid")

    import torch

    if device == "cuda" and not torch.cuda.is_available():
        raise ValueError("mswc_qbye_ensemble_cuda_unavailable")
    torch_device = torch.device(device)
    loaded_features = {}
    enrollment_components = []
    query_components = []
    component_reports = []
    for checkpoint_path in checkpoint_paths:
        checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
        if (
            not isinstance(checkpoint, dict)
            or checkpoint.get("schema") != "baxy.mswc-spanish-qbye-angleproto.v1"
            or checkpoint.get("feature_manifest_sha256") != _EVAL.sha256(feature_manifest_path)
        ):
            raise ValueError("mswc_qbye_ensemble_checkpoint_invalid")
        layer = int(checkpoint["layer"])
        descriptor = features_by_layer.get(str(layer))
        if not isinstance(descriptor, dict):
            raise ValueError("mswc_qbye_ensemble_layer_missing")
        if layer not in loaded_features:
            path = root / str(descriptor["path"])
            if _EVAL.sha256(path) != descriptor.get("sha256"):
                raise ValueError("mswc_qbye_ensemble_feature_hash_mismatch")
            loaded_features[layer] = np.load(path, mmap_mode="r")
        layer_features = loaded_features[layer]
        model = _TRAINER.make_model(
            torch, int(checkpoint["hidden_size"]), int(checkpoint["embedding_size"])
        ).to(torch_device)
        model.load_state_dict(checkpoint["state_dict"])
        model.eval()

        def embed(indexes: list[int]) -> np.ndarray:
            outputs = []
            with torch.inference_mode():
                for start in range(0, len(indexes), prediction_batch_size):
                    selected = indexes[start : start + prediction_batch_size]
                    fixed = []
                    masks = []
                    for index in selected:
                        sequence, mask = _TRAINER.fixed_sequence(
                            layer_features[int(offsets[index]) : int(offsets[index + 1])],
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

        enrollment_components.append(embed(enrollment_indexes))
        query_components.append(embed(query_indexes))
        component_reports.append(
            {
                "checkpoint_path": checkpoint_path.as_posix(),
                "checkpoint_sha256": _EVAL.sha256(checkpoint_path),
                "layer": layer,
                "objective": checkpoint["objective"],
                "seed": checkpoint["seed"],
                "best_epoch": checkpoint["best_epoch"],
            }
        )
        del model
    metrics, queries = _EVAL.qbye_metrics(
        enrollment_embeddings=concatenate_embeddings(enrollment_components),
        enrollment_classes=[str(records[index]["class_name"]) for index in enrollment_indexes],
        query_embeddings=concatenate_embeddings(query_components),
        query_classes=[str(records[index]["class_name"]) for index in query_indexes],
    )
    report: dict[str, object] = {
        "schema": "baxy.mswc-spanish-qbye-checkpoint-ensemble-tuning.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "development_only_open_word_tuning_ensemble_probe",
        "sources": {"feature_manifest_sha256": _EVAL.sha256(feature_manifest_path)},
        "contract": {
            "open_split_seed": open_split_seed,
            "open_partition": "tuning",
            "fusion": "concatenate_individually_l2_normalized_head_embeddings_then_l2_normalize",
            "components": component_reports,
        },
        "metrics": metrics,
        "queries": queries,
        "runtime_seconds": time.perf_counter() - started,
        "open_selection_examples_scored": False,
        "baxy_human_examples_scored": False,
        "blind_human_audio_accessed": False,
        "candidate_frozen": False,
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
    parser.add_argument("--feature-manifest", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--open-split-seed", type=int, default=9107)
    parser.add_argument("--prediction-batch-size", type=int, default=256)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = evaluate(
        feature_manifest_path=args.feature_manifest,
        checkpoint_paths=args.checkpoint,
        output_path=args.output,
        open_split_seed=args.open_split_seed,
        prediction_batch_size=args.prediction_batch_size,
        device=args.device,
    )
    print(json.dumps(report["metrics"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
