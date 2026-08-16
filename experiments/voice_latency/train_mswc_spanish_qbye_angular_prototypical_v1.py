"""Train an open-vocabulary angular-prototypical word embedding on MSWC."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from importlib.metadata import version
import importlib.util
import json
import math
import os
from pathlib import Path
import random
import time

import numpy as np


_EVAL_PATH = Path(__file__).with_name(
    "evaluate_mswc_spanish_qbye_ssl_baseline_v1.py"
)
_EVAL_SPEC = importlib.util.spec_from_file_location("_baxy_qbye_eval_v1", _EVAL_PATH)
if _EVAL_SPEC is None or _EVAL_SPEC.loader is None:
    raise RuntimeError("mswc_qbye_angleproto_eval_import_invalid")
_EVAL = importlib.util.module_from_spec(_EVAL_SPEC)
_EVAL_SPEC.loader.exec_module(_EVAL)


def read_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"mswc_qbye_angleproto_json_invalid:{path}")
    return value


def fixed_sequence(values: np.ndarray, frames: int) -> tuple[np.ndarray, np.ndarray]:
    sequence = np.asarray(values, dtype=np.float32)
    if sequence.ndim != 2 or not len(sequence) or frames < 2:
        raise ValueError("mswc_qbye_angleproto_sequence_invalid")
    if len(sequence) > frames:
        start = (len(sequence) - frames) // 2
        sequence = sequence[start : start + frames]
    output = np.zeros((frames, sequence.shape[1]), dtype=np.float32)
    mask = np.zeros(frames, dtype=np.bool_)
    output[: len(sequence)] = sequence
    mask[: len(sequence)] = True
    return output, mask


def make_model(torch: object, hidden_size: int, embedding_size: int) -> object:
    nn = torch.nn

    class AttentiveStatisticsEmbedding(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.reduction = nn.Linear(hidden_size, 128)
            self.temporal = nn.Conv1d(128, 128, kernel_size=3, padding=1)
            self.activation = nn.PReLU(128)
            self.attention = nn.Sequential(
                nn.Linear(128, 64), nn.Tanh(), nn.Linear(64, 1)
            )
            self.dropout = nn.Dropout(0.10)
            self.output = nn.Linear(256, embedding_size)

        def forward(self, values: object, mask: object) -> object:
            hidden = self.reduction(values)
            hidden = self.temporal(hidden.transpose(1, 2))
            hidden = self.activation(hidden).transpose(1, 2)
            hidden = self.dropout(hidden)
            logits = self.attention(hidden).squeeze(-1)
            logits = logits.masked_fill(~mask, -torch.inf)
            weights = torch.softmax(logits, dim=1).unsqueeze(-1)
            mean = torch.sum(hidden * weights, dim=1)
            second = torch.sum(hidden.square() * weights, dim=1)
            standard_deviation = torch.sqrt(torch.clamp(second - mean.square(), min=1e-5))
            pooled = torch.cat([mean, standard_deviation], dim=-1)
            return torch.nn.functional.normalize(self.output(pooled), dim=-1)

    return AttentiveStatisticsEmbedding()


def angular_prototypical_logits(
    torch: object, embeddings: object, raw_scale: object
) -> object:
    if embeddings.ndim != 3 or embeddings.shape[1] < 2:
        raise ValueError("mswc_qbye_angleproto_episode_invalid")
    query = torch.nn.functional.normalize(embeddings[:, 0], dim=-1)
    anchors = torch.nn.functional.normalize(embeddings[:, 1:].mean(dim=1), dim=-1)
    scale = torch.nn.functional.softplus(raw_scale) + 1.0
    return (query @ anchors.T) * scale


def hardest_impostor_margin_loss(
    torch: object, embeddings: object, *, margin: float, temperature: float = 10.0
) -> object:
    if embeddings.ndim != 3 or embeddings.shape[0] < 2 or embeddings.shape[1] < 2:
        raise ValueError("mswc_qbye_angleproto_hard_episode_invalid")
    query = torch.nn.functional.normalize(embeddings[:, 0], dim=-1)
    anchors = torch.nn.functional.normalize(embeddings[:, 1:].mean(dim=1), dim=-1)
    cosines = query @ anchors.T
    rows = torch.arange(len(cosines), device=cosines.device)
    positives = cosines[rows, rows]
    negative_mask = torch.eye(len(cosines), dtype=torch.bool, device=cosines.device)
    hardest_negatives = cosines.masked_fill(negative_mask, -torch.inf).max(dim=1).values
    return torch.nn.functional.softplus(
        (hardest_negatives - positives + margin) * temperature
    ).mean() / temperature


def checkpoint_rank(metrics: dict[str, object], mode: str) -> tuple[float, ...]:
    top1 = float(metrics["top1_accuracy"])
    auc = float(metrics["pair_auc"])
    eer = float(metrics["equal_error_rate"])
    if mode == "standard":
        return (top1, auc, -eer)
    if mode == "tail_zero_false":
        core_pass = float(top1 >= 0.94 and auc >= 0.997 and eer <= 0.025)
        zero_recall = int(metrics["true_pairs_accepted_at_zero_false_pairs"]) / int(
            metrics["true_pairs"]
        )
        return (core_pass, zero_recall, top1, auc, -eer)
    raise ValueError("mswc_qbye_angleproto_checkpoint_mode_invalid")


def subcenter_arcface_logits(
    torch: object,
    embeddings: object,
    centers: object,
    labels: object,
    *,
    margin: float,
    scale: float,
) -> object:
    normalized_centers = torch.nn.functional.normalize(centers, dim=-1)
    cosines = torch.einsum("bd,ckd->bck", embeddings, normalized_centers).max(dim=-1).values
    rows = torch.arange(len(labels), device=labels.device)
    target = torch.clamp(cosines[rows, labels], -1.0 + 1e-6, 1.0 - 1e-6)
    logits = cosines.clone()
    logits[rows, labels] = torch.cos(torch.acos(target) + margin)
    return logits * scale


def train(
    *,
    feature_manifest_path: Path,
    output_root: Path,
    layer: int,
    objective: str,
    seed: int,
    open_split_seed: int,
    epochs: int,
    batches_per_epoch: int,
    classes_per_batch: int,
    examples_per_class: int,
    learning_rate: float,
    maximum_frames: int,
    embedding_size: int,
    classification_weight: float,
    hard_negative_weight: float,
    hard_negative_margin: float,
    subcenters: int,
    arcface_margin: float,
    arcface_scale: float,
    validation_interval_epochs: int,
    prediction_batch_size: int,
    device: str,
    initial_checkpoint_path: Path | None,
    checkpoint_selection_mode: str,
) -> dict[str, object]:
    if (
        output_root.exists()
        or objective not in {"angular_prototypical", "hybrid_angular_prototypical_arcface"}
        or layer < 0
        or epochs < 1
        or batches_per_epoch < 1
        or classes_per_batch < 2
        or examples_per_class < 2
        or learning_rate <= 0.0
        or maximum_frames < 2
        or embedding_size < 8
        or classification_weight < 0.0
        or hard_negative_weight < 0.0
        or not 0.0 <= hard_negative_margin < 1.0
        or subcenters < 1
        or not 0.0 < arcface_margin < 1.0
        or arcface_scale <= 1.0
        or validation_interval_epochs < 1
        or prediction_batch_size < 1
        or device not in {"cpu", "cuda"}
        or checkpoint_selection_mode not in {"standard", "tail_zero_false"}
    ):
        raise ValueError("mswc_qbye_angleproto_schedule_invalid")
    feature_manifest_path = feature_manifest_path.resolve(strict=True)
    initial_checkpoint_path = (
        initial_checkpoint_path.resolve(strict=True)
        if initial_checkpoint_path is not None
        else None
    )
    output_root = output_root.resolve()
    partial_root = output_root.with_name(output_root.name + ".partial")
    if partial_root.exists():
        raise FileExistsError(f"mswc_qbye_angleproto_partial_exists:{partial_root}")
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
        raise ValueError("mswc_qbye_angleproto_boundary_invalid")
    records = []
    for record in records_raw:
        if not isinstance(record, dict):
            raise ValueError("mswc_qbye_angleproto_record_invalid")
        records.append(record)
    features_by_layer = files.get("features_by_layer")
    if not isinstance(features_by_layer, dict) or not isinstance(
        features_by_layer.get(str(layer)), dict
    ):
        raise ValueError("mswc_qbye_angleproto_layer_missing")
    descriptor = features_by_layer[str(layer)]
    root = feature_manifest_path.parent
    feature_path = root / str(descriptor["path"])
    offset_path = root / str(files["offsets"])
    if (
        _EVAL.sha256(feature_path) != descriptor.get("sha256")
        or _EVAL.sha256(offset_path) != files.get("offsets_sha256")
    ):
        raise ValueError("mswc_qbye_angleproto_feature_hash_mismatch")
    features = np.load(feature_path, mmap_mode="r")
    offsets = np.load(offset_path)
    hidden_size = int(contract["hidden_size"])
    if (
        features.ndim != 2
        or features.shape[1] != hidden_size
        or len(offsets) != len(records) + 1
        or int(offsets[-1]) != len(features)
    ):
        raise ValueError("mswc_qbye_angleproto_feature_shape_invalid")

    training_indexes = [
        index for index, record in enumerate(records) if record["partition"] == "metric_training"
    ]
    training_class_names = sorted({str(records[index]["class_name"]) for index in training_indexes})
    class_to_id = {name: index for index, name in enumerate(training_class_names)}
    by_class = {
        class_to_id[name]: [
            index
            for index in training_indexes
            if str(records[index]["class_name"]) == name
        ]
        for name in training_class_names
    }
    if (
        len(training_class_names) != 1000
        or classes_per_batch > len(training_class_names)
        or any(len(indexes) < examples_per_class for indexes in by_class.values())
    ):
        raise ValueError("mswc_qbye_angleproto_training_class_contract_invalid")

    open_words = {
        str(record["class_name"])
        for record in records
        if str(record["partition"]).startswith("open_keyword_")
    }
    tuning_words, selection_words = _EVAL.split_open_words(
        open_words, seed=open_split_seed
    )
    tuning_enrollment_indexes = [
        index
        for index, record in enumerate(records)
        if record["partition"] == "open_keyword_enrollment"
        and str(record["class_name"]) in tuning_words
    ]
    tuning_query_indexes = [
        index
        for index, record in enumerate(records)
        if record["partition"] == "open_keyword_query"
        and str(record["class_name"]) in tuning_words
    ]
    if len(tuning_enrollment_indexes) != 400 or len(tuning_query_indexes) != 1200:
        raise ValueError("mswc_qbye_angleproto_tuning_partition_invalid")

    import torch

    if device == "cuda" and not torch.cuda.is_available():
        raise ValueError("mswc_qbye_angleproto_cuda_unavailable")
    torch_device = torch.device(device)
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    model = make_model(torch, hidden_size, embedding_size).to(torch_device)
    raw_scale = torch.nn.Parameter(torch.tensor(math.log(math.expm1(9.0)), device=torch_device))
    centers = None
    if objective == "hybrid_angular_prototypical_arcface":
        centers = torch.nn.Parameter(
            torch.empty(
                len(training_class_names), subcenters, embedding_size, device=torch_device
            )
        )
        torch.nn.init.normal_(centers, mean=0.0, std=0.02)
    initial_checkpoint_sha256 = None
    if initial_checkpoint_path is not None:
        initial_checkpoint = torch.load(
            initial_checkpoint_path, map_location="cpu", weights_only=False
        )
        if (
            not isinstance(initial_checkpoint, dict)
            or initial_checkpoint.get("schema")
            != "baxy.mswc-spanish-qbye-angleproto.v1"
            or initial_checkpoint.get("feature_manifest_sha256")
            != _EVAL.sha256(feature_manifest_path)
            or int(initial_checkpoint["layer"]) != layer
            or int(initial_checkpoint["hidden_size"]) != hidden_size
            or int(initial_checkpoint["embedding_size"]) != embedding_size
            or int(initial_checkpoint["maximum_frames"]) != maximum_frames
            or initial_checkpoint.get("training_class_names") != training_class_names
        ):
            raise ValueError("mswc_qbye_angleproto_initial_checkpoint_invalid")
        model.load_state_dict(initial_checkpoint["state_dict"])
        raw_scale.data.copy_(initial_checkpoint["raw_scale"].to(torch_device))
        checkpoint_centers = initial_checkpoint.get("class_centers")
        if (centers is None) != (checkpoint_centers is None):
            raise ValueError("mswc_qbye_angleproto_initial_centers_mismatch")
        if centers is not None:
            centers.data.copy_(checkpoint_centers.to(torch_device))
        initial_checkpoint_sha256 = _EVAL.sha256(initial_checkpoint_path)
    parameters = [*model.parameters(), raw_scale]
    if centers is not None:
        parameters.append(centers)
    optimizer = torch.optim.AdamW(parameters, lr=learning_rate, weight_decay=1e-4)

    def batch_arrays(indexes: list[int]) -> tuple[object, object]:
        fixed = []
        masks = []
        for index in indexes:
            sequence, mask = fixed_sequence(
                features[int(offsets[index]) : int(offsets[index + 1])], maximum_frames
            )
            fixed.append(sequence)
            masks.append(mask)
        return (
            torch.from_numpy(np.stack(fixed)).to(torch_device),
            torch.from_numpy(np.stack(masks)).to(torch_device),
        )

    def embed_indexes(indexes: list[int]) -> np.ndarray:
        outputs = []
        model.eval()
        with torch.inference_mode():
            for start in range(0, len(indexes), prediction_batch_size):
                selected = indexes[start : start + prediction_batch_size]
                values, mask = batch_arrays(selected)
                outputs.append(model(values, mask).float().cpu().numpy())
        return np.concatenate(outputs)

    def tuning_metrics() -> dict[str, object]:
        enrollment = embed_indexes(tuning_enrollment_indexes)
        queries = embed_indexes(tuning_query_indexes)
        metrics, _ = _EVAL.qbye_metrics(
            enrollment_embeddings=enrollment,
            enrollment_classes=[str(records[index]["class_name"]) for index in tuning_enrollment_indexes],
            query_embeddings=queries,
            query_classes=[str(records[index]["class_name"]) for index in tuning_query_indexes],
        )
        return metrics

    partial_root.mkdir(parents=True)
    generator = random.Random(seed)
    started = time.perf_counter()
    initial_validation = tuning_metrics()
    history = [
        {
            "epoch": 0,
            "mean_loss": None,
            "mean_angular_prototypical_loss": None,
            "mean_hardest_impostor_margin_loss": None,
            "mean_arcface_loss": None,
            "episode_top1_accuracy": None,
            "open_keyword_tuning": initial_validation,
        }
    ]
    best_rank: tuple[float, ...] = checkpoint_rank(
        initial_validation, checkpoint_selection_mode
    )
    best_epoch = 0
    best_state = {
        name: value.detach().cpu().clone() for name, value in model.state_dict().items()
    }
    best_scale = raw_scale.detach().cpu().clone()
    best_centers = centers.detach().cpu().clone() if centers is not None else None
    for epoch in range(1, epochs + 1):
        model.train()
        total_loss = 0.0
        total_proto_loss = 0.0
        total_hard_negative_loss = 0.0
        total_classification_loss = 0.0
        total_episode_correct = 0
        total_episode_queries = 0
        for _ in range(batches_per_epoch):
            chosen_classes = generator.sample(range(len(training_class_names)), classes_per_batch)
            episode_indexes = []
            for class_id in chosen_classes:
                episode_indexes.extend(
                    generator.sample(by_class[class_id], examples_per_class)
                )
            values, mask = batch_arrays(episode_indexes)
            optimizer.zero_grad(set_to_none=True)
            flat_embeddings = model(values, mask)
            episode_embeddings = flat_embeddings.reshape(
                classes_per_batch, examples_per_class, embedding_size
            )
            proto_logits = angular_prototypical_logits(
                torch, episode_embeddings, raw_scale
            )
            proto_targets = torch.arange(classes_per_batch, device=torch_device)
            proto_loss = torch.nn.functional.cross_entropy(proto_logits, proto_targets)
            hard_negative_loss = hardest_impostor_margin_loss(
                torch, episode_embeddings, margin=hard_negative_margin
            )
            classification_loss = torch.zeros((), device=torch_device)
            if centers is not None:
                global_labels = torch.tensor(
                    [
                        class_id
                        for class_id in chosen_classes
                        for _ in range(examples_per_class)
                    ],
                    dtype=torch.long,
                    device=torch_device,
                )
                class_logits = subcenter_arcface_logits(
                    torch,
                    flat_embeddings,
                    centers,
                    global_labels,
                    margin=arcface_margin,
                    scale=arcface_scale,
                )
                classification_loss = torch.nn.functional.cross_entropy(
                    class_logits, global_labels
                )
            loss = (
                proto_loss
                + hard_negative_weight * hard_negative_loss
                + classification_weight * classification_loss
            )
            loss.backward()
            torch.nn.utils.clip_grad_norm_(parameters, 5.0)
            optimizer.step()
            total_loss += float(loss.detach().cpu())
            total_proto_loss += float(proto_loss.detach().cpu())
            total_hard_negative_loss += float(hard_negative_loss.detach().cpu())
            total_classification_loss += float(classification_loss.detach().cpu())
            total_episode_correct += int(
                torch.count_nonzero(torch.argmax(proto_logits, dim=1) == proto_targets)
                .detach()
                .cpu()
            )
            total_episode_queries += classes_per_batch
        if epoch % validation_interval_epochs == 0 or epoch == epochs:
            validation = tuning_metrics()
            entry = {
                "epoch": epoch,
                "mean_loss": total_loss / batches_per_epoch,
                "mean_angular_prototypical_loss": total_proto_loss / batches_per_epoch,
                "mean_hardest_impostor_margin_loss": (
                    total_hard_negative_loss / batches_per_epoch
                ),
                "mean_arcface_loss": total_classification_loss / batches_per_epoch,
                "episode_top1_accuracy": total_episode_correct / total_episode_queries,
                "open_keyword_tuning": validation,
            }
            history.append(entry)
            rank = checkpoint_rank(validation, checkpoint_selection_mode)
            if rank > best_rank:
                best_rank = rank
                best_epoch = epoch
                best_state = {
                    name: value.detach().cpu().clone()
                    for name, value in model.state_dict().items()
                }
                best_scale = raw_scale.detach().cpu().clone()
                best_centers = centers.detach().cpu().clone() if centers is not None else None
    model.load_state_dict(best_state)
    final_tuning = tuning_metrics()
    checkpoint_path = partial_root / "mswc-spanish-qbye-angleproto-v1.pt"
    torch.save(
        {
            "schema": "baxy.mswc-spanish-qbye-angleproto.v1",
            "architecture": "attentive_statistics_pooling_over_frozen_wav2vec2_hidden_features",
            "hidden_size": hidden_size,
            "embedding_size": embedding_size,
            "maximum_frames": maximum_frames,
            "layer": layer,
            "objective": objective,
            "hard_negative_weight": hard_negative_weight,
            "hard_negative_margin": hard_negative_margin,
            "state_dict": best_state,
            "raw_scale": best_scale,
            "class_centers": best_centers,
            "training_class_names": training_class_names,
            "feature_manifest_sha256": _EVAL.sha256(feature_manifest_path),
            "feature_file_sha256": descriptor["sha256"],
            "offset_file_sha256": files["offsets_sha256"],
            "seed": seed,
            "best_epoch": best_epoch,
            "initial_checkpoint_sha256": initial_checkpoint_sha256,
            "checkpoint_selection_mode": checkpoint_selection_mode,
        },
        checkpoint_path,
    )
    report: dict[str, object] = {
        "schema": "baxy.mswc-spanish-qbye-angleproto-training.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "development_only_open_vocabulary_metric_training",
        "sources": {
            "feature_manifest_sha256": _EVAL.sha256(feature_manifest_path),
            "feature_file_sha256": descriptor["sha256"],
            "offset_file_sha256": files["offsets_sha256"],
            "official_reference_code": "https://github.com/kaistmm/Metric-UD-KWS",
            "official_reference_angleproto_sha": "ccc734e520bbfc3d50594fc2481a53f9348d00ed",
            "initial_checkpoint_path": (
                initial_checkpoint_path.as_posix()
                if initial_checkpoint_path is not None
                else None
            ),
            "initial_checkpoint_sha256": initial_checkpoint_sha256,
        },
        "contract": {
            "layer": layer,
            "objective": objective,
            "seed": seed,
            "open_split_seed": open_split_seed,
            "epochs": epochs,
            "batches_per_epoch": batches_per_epoch,
            "classes_per_batch": classes_per_batch,
            "examples_per_class": examples_per_class,
            "learning_rate": learning_rate,
            "maximum_frames": maximum_frames,
            "embedding_size": embedding_size,
            "classification_weight": classification_weight,
            "hard_negative_weight": hard_negative_weight,
            "hard_negative_margin": hard_negative_margin,
            "subcenters": subcenters,
            "arcface_margin": arcface_margin,
            "arcface_scale": arcface_scale,
            "validation_interval_epochs": validation_interval_epochs,
            "checkpoint_selection": checkpoint_selection_mode,
            "open_tuning_word_classes": len(tuning_words),
            "open_selection_word_classes_reserved": len(selection_words),
        },
        "history": history,
        "selected": {
            "best_epoch": best_epoch,
            "open_keyword_tuning": final_tuning,
            "checkpoint": checkpoint_path.name,
            "checkpoint_sha256": _EVAL.sha256(checkpoint_path),
        },
        "dependencies": {
            "torch": version("torch"),
            "numpy": version("numpy"),
            "torch_cuda": torch.version.cuda,
            "cuda_device": torch.cuda.get_device_name(0) if device == "cuda" else None,
        },
        "runtime_seconds": time.perf_counter() - started,
        "open_selection_examples_scored": False,
        "baxy_human_examples_scored": False,
        "official_test_audio_accessed": False,
        "blind_human_audio_accessed": False,
        "candidate_frozen": False,
        "effects_executed": 0,
    }
    report_path = partial_root / "training.report.v1.json"
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
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--layer", type=int, required=True)
    parser.add_argument(
        "--objective",
        choices=("angular_prototypical", "hybrid_angular_prototypical_arcface"),
        default="angular_prototypical",
    )
    parser.add_argument("--seed", type=int, default=3501)
    parser.add_argument("--open-split-seed", type=int, default=9107)
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batches-per-epoch", type=int, default=100)
    parser.add_argument("--classes-per-batch", type=int, default=64)
    parser.add_argument("--examples-per-class", type=int, default=4)
    parser.add_argument("--learning-rate", type=float, default=3e-4)
    parser.add_argument("--maximum-frames", type=int, default=50)
    parser.add_argument("--embedding-size", type=int, default=64)
    parser.add_argument("--classification-weight", type=float, default=0.25)
    parser.add_argument("--hard-negative-weight", type=float, default=0.0)
    parser.add_argument("--hard-negative-margin", type=float, default=0.1)
    parser.add_argument("--subcenters", type=int, default=3)
    parser.add_argument("--arcface-margin", type=float, default=0.2)
    parser.add_argument("--arcface-scale", type=float, default=30.0)
    parser.add_argument("--validation-interval-epochs", type=int, default=2)
    parser.add_argument("--prediction-batch-size", type=int, default=256)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    parser.add_argument("--initial-checkpoint", type=Path)
    parser.add_argument(
        "--checkpoint-selection-mode",
        choices=("standard", "tail_zero_false"),
        default="standard",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = train(
        feature_manifest_path=args.feature_manifest,
        output_root=args.output_root,
        layer=args.layer,
        objective=args.objective,
        seed=args.seed,
        open_split_seed=args.open_split_seed,
        epochs=args.epochs,
        batches_per_epoch=args.batches_per_epoch,
        classes_per_batch=args.classes_per_batch,
        examples_per_class=args.examples_per_class,
        learning_rate=args.learning_rate,
        maximum_frames=args.maximum_frames,
        embedding_size=args.embedding_size,
        classification_weight=args.classification_weight,
        hard_negative_weight=args.hard_negative_weight,
        hard_negative_margin=args.hard_negative_margin,
        subcenters=args.subcenters,
        arcface_margin=args.arcface_margin,
        arcface_scale=args.arcface_scale,
        validation_interval_epochs=args.validation_interval_epochs,
        prediction_batch_size=args.prediction_batch_size,
        device=args.device,
        initial_checkpoint_path=args.initial_checkpoint,
        checkpoint_selection_mode=args.checkpoint_selection_mode,
    )
    print(json.dumps(report["selected"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
