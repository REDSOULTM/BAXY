"""Evaluate a frozen BAXY HyperSpotter candidate on human development audio.

The operating threshold is read from the speaker-disjoint synthetic training
report before human scores are produced.  The report is aggregate-only and
never accesses the blind human partition.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
import types

import numpy as np


def load_component(filename: str, name: str) -> object:
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"baxy_hyperspotter_human_component_invalid:{filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_TRAIN = load_component(
    "train_baxy_hyperspotter_binary_v1.py",
    "_baxy_hyperspotter_human_train_v1",
)
_METRICS = load_component(
    "evaluate_mswc_hyperspotter_spanish_tuning_v1.py",
    "_baxy_hyperspotter_human_metrics_v1",
)


def read_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError("baxy_hyperspotter_human_json_invalid")
    return value


def score_metrics(
    *,
    labels: np.ndarray,
    scores: np.ndarray,
    groups: np.ndarray,
    fixed_threshold: float,
) -> dict[str, object]:
    labels = np.asarray(labels, dtype=np.int64)
    scores = np.asarray(scores, dtype=np.float64)
    groups = np.asarray(groups)
    if (
        labels.shape != scores.shape
        or labels.shape != groups.shape
        or set(labels.tolist()) != {0, 1}
        or not np.isfinite(scores).all()
        or not np.isfinite(fixed_threshold)
    ):
        raise ValueError("baxy_hyperspotter_human_scores_invalid")
    auc, eer, eer_threshold = _METRICS.binary_auc_eer(
        targets=labels, scores=scores
    )
    positives = labels == 1
    negatives = ~positives
    fixed = scores >= fixed_threshold
    global_threshold = float(np.nextafter(np.max(scores[negatives]), np.inf))
    global_decision = scores >= global_threshold
    cross_validated = np.zeros(len(scores), dtype=np.bool_)
    for group in sorted(set(groups.tolist())):
        held = groups == group
        training_negatives = scores[negatives & ~held]
        if not len(training_negatives):
            raise ValueError("baxy_hyperspotter_human_group_negatives_missing")
        threshold = float(np.nextafter(np.max(training_negatives), np.inf))
        cross_validated[held] = scores[held] >= threshold
    return {
        "auc": auc,
        "equal_error_rate": eer,
        "equal_error_threshold": eer_threshold,
        "fixed_synthetic_threshold": {
            "threshold": fixed_threshold,
            "positive_hits": int(np.count_nonzero(fixed & positives)),
            "false_hits": int(np.count_nonzero(fixed & negatives)),
        },
        "human_global_zero_false_diagnostic": {
            "threshold": global_threshold,
            "positive_hits": int(np.count_nonzero(global_decision & positives)),
            "false_hits": int(np.count_nonzero(global_decision & negatives)),
        },
        "leave_one_group_out_zero_false_diagnostic": {
            "groups": len(set(groups.tolist())),
            "positive_hits": int(np.count_nonzero(cross_validated & positives)),
            "false_hits": int(np.count_nonzero(cross_validated & negatives)),
        },
    }


def fusion_metrics(
    *, labels: np.ndarray, ctc_decisions: np.ndarray, hyper_decisions: np.ndarray
) -> dict[str, int]:
    labels = np.asarray(labels, dtype=np.int64)
    ctc = np.asarray(ctc_decisions, dtype=np.bool_)
    hyper = np.asarray(hyper_decisions, dtype=np.bool_)
    if labels.shape != ctc.shape or labels.shape != hyper.shape:
        raise ValueError("baxy_hyperspotter_human_fusion_shape_invalid")
    positives = labels == 1
    negatives = ~positives
    fused = ctc | hyper
    return {
        "ctc_positive_hits": int(np.count_nonzero(ctc & positives)),
        "ctc_false_hits": int(np.count_nonzero(ctc & negatives)),
        "hyper_positive_hits": int(np.count_nonzero(hyper & positives)),
        "hyper_false_hits": int(np.count_nonzero(hyper & negatives)),
        "fused_positive_hits": int(np.count_nonzero(fused & positives)),
        "fused_false_hits": int(np.count_nonzero(fused & negatives)),
        "new_positive_rescues": int(np.count_nonzero(hyper & positives & ~ctc)),
        "positive_overlap": int(np.count_nonzero(hyper & positives & ctc)),
    }


def partition_fusion_metrics(
    *,
    labels: np.ndarray,
    ctc_decisions: np.ndarray,
    hyper_decisions: np.ndarray,
    partitions: np.ndarray,
) -> dict[str, dict[str, int]]:
    labels = np.asarray(labels, dtype=np.int64)
    ctc = np.asarray(ctc_decisions, dtype=np.bool_)
    hyper = np.asarray(hyper_decisions, dtype=np.bool_)
    partitions = np.asarray(partitions)
    if not (labels.shape == ctc.shape == hyper.shape == partitions.shape):
        raise ValueError("baxy_hyperspotter_human_partition_shape_invalid")
    result: dict[str, dict[str, int]] = {}
    for partition in sorted(set(partitions.tolist())):
        mask = partitions == partition
        positive = labels[mask] == 1
        negative = ~positive
        fused = ctc[mask] | hyper[mask]
        result[str(partition)] = {
            "positive_records": int(np.count_nonzero(positive)),
            "negative_records": int(np.count_nonzero(negative)),
            "ctc_positive_hits": int(np.count_nonzero(ctc[mask] & positive)),
            "ctc_false_hits": int(np.count_nonzero(ctc[mask] & negative)),
            "hyper_positive_hits": int(np.count_nonzero(hyper[mask] & positive)),
            "hyper_false_hits": int(np.count_nonzero(hyper[mask] & negative)),
            "fused_positive_hits": int(np.count_nonzero(fused & positive)),
            "fused_false_hits": int(np.count_nonzero(fused & negative)),
        }
    return result


def load_candidate(
    *,
    hyperspotter_root: Path,
    hyperspotter_site_packages: Path,
    official_checkpoint_path: Path,
    candidate_checkpoint_path: Path,
    device: str,
) -> tuple[object, object, object, object, dict[str, object]]:
    import torch

    if device == "cuda" and not torch.cuda.is_available():
        raise ValueError("baxy_hyperspotter_human_cuda_unavailable")
    for name, value in (
        ("float_", np.float64),
        ("complex_", np.complex128),
        ("string_", np.bytes_),
        ("unicode_", np.str_),
    ):
        if not hasattr(np, name):
            setattr(np, name, value)
    wandb_stub = types.ModuleType("wandb")
    wandb_stub.__spec__ = importlib.machinery.ModuleSpec("wandb", loader=None)
    wandb_stub.Settings = lambda **_kwargs: None
    whisper_stub = types.ModuleType("whisper")
    whisper_stub.__spec__ = importlib.machinery.ModuleSpec("whisper", loader=None)
    whisper_stub.load_model = lambda *_args, **_kwargs: None
    sys.modules["wandb"] = wandb_stub
    sys.modules["whisper"] = whisper_stub
    if str(hyperspotter_site_packages) not in sys.path:
        sys.path.append(str(hyperspotter_site_packages))
    if str(hyperspotter_root) not in sys.path:
        sys.path.insert(0, str(hyperspotter_root))
    pandas_was_loaded = "pandas" in sys.modules
    pandas_module = sys.modules.get("pandas")
    if not pandas_was_loaded:
        sys.modules["pandas"] = None
    try:
        from src.models import ConformerLightning
    finally:
        if not pandas_was_loaded:
            sys.modules.pop("pandas", None)
        elif pandas_module is not None:
            sys.modules["pandas"] = pandas_module
    ConformerLightning.set_decoders = lambda _self, _cfg: None
    previous_directory = Path.cwd()
    original_torch_load = torch.load

    def trusted_checkpoint_load(*args: object, **kwargs: object) -> object:
        kwargs.setdefault("weights_only", False)
        return original_torch_load(*args, **kwargs)

    try:
        os.chdir(hyperspotter_root)
        torch.load = trusted_checkpoint_load
        lightning_model = ConformerLightning.load_from_checkpoint(
            str(official_checkpoint_path), map_location="cpu"
        )
    finally:
        torch.load = original_torch_load
        os.chdir(previous_directory)
    checkpoint = torch.load(
        candidate_checkpoint_path, map_location="cpu", weights_only=False
    )
    if (
        not isinstance(checkpoint, dict)
        or checkpoint.get("schema")
        not in {
            "baxy.baxy-hyperspotter-binary.v1",
            "baxy.baxy-hyperspotter-physical-adaptation.v3",
        }
        or checkpoint.get("official_checkpoint_sha256")
        != _TRAIN._LOGMEL.sha256(official_checkpoint_path)
        or checkpoint.get("upstream_commit") != _TRAIN.EXPECTED_UPSTREAM_COMMIT
        or checkpoint.get("aliases") != list(_TRAIN.ALIASES)
        or not isinstance(checkpoint.get("model_state_dict"), dict)
    ):
        raise ValueError("baxy_hyperspotter_human_checkpoint_invalid")
    model = lightning_model.model
    model.load_state_dict(checkpoint["model_state_dict"])
    torch_device = torch.device(device)
    model = model.to(torch_device).eval()
    return model, lightning_model.tokenizer, torch, torch_device, checkpoint


def evaluate(
    *,
    human_feature_manifest_path: Path,
    legacy_root: Path,
    expanded_root: Path,
    ctc_development_report_path: Path,
    hyperspotter_root: Path,
    hyperspotter_site_packages: Path,
    official_checkpoint_path: Path,
    candidate_checkpoint_path: Path,
    candidate_training_report_path: Path,
    output_path: Path,
    batch_size: int,
    device: str,
) -> dict[str, object]:
    if output_path.exists() or batch_size < 1 or device not in {"cpu", "cuda"}:
        raise ValueError("baxy_hyperspotter_human_schedule_invalid")
    paths = [
        human_feature_manifest_path,
        legacy_root,
        expanded_root,
        ctc_development_report_path,
        hyperspotter_root,
        hyperspotter_site_packages,
        official_checkpoint_path,
        candidate_checkpoint_path,
        candidate_training_report_path,
    ]
    (
        human_feature_manifest_path,
        legacy_root,
        expanded_root,
        ctc_development_report_path,
        hyperspotter_root,
        hyperspotter_site_packages,
        official_checkpoint_path,
        candidate_checkpoint_path,
        candidate_training_report_path,
    ) = [path.resolve(strict=True) for path in paths]
    output_path = output_path.resolve()
    human_manifest = read_object(human_feature_manifest_path)
    ctc_report = read_object(ctc_development_report_path)
    training_report = read_object(candidate_training_report_path)
    if (
        human_manifest.get("schema")
        != "baxy.wav2vec2-hidden-wake-training-features.v1"
        or human_manifest.get("blind_human_audio_accessed") is not False
        or ctc_report.get("schema") != "baxy.wake-ssl-ctc-ensemble-development.v1"
        or ctc_report.get("blind_human_audio_accessed") is not False
        or training_report.get("schema")
        != "baxy.baxy-hyperspotter-binary-training.v1"
        or training_report.get("human_development_audio_accessed") is not False
        or training_report.get("blind_human_audio_accessed") is not False
    ):
        raise ValueError("baxy_hyperspotter_human_boundary_invalid")
    selected = training_report.get("selected")
    if (
        not isinstance(selected, dict)
        or selected.get("checkpoint_sha256")
        != _TRAIN._LOGMEL.sha256(candidate_checkpoint_path)
        or not isinstance(selected.get("validation"), dict)
    ):
        raise ValueError("baxy_hyperspotter_human_training_report_invalid")
    fixed_threshold = float(selected["validation"]["zero_false_threshold"])

    roots = {"human_legacy": legacy_root, "human_expanded": expanded_root}
    records = [
        record
        for record in human_manifest.get("records", [])
        if isinstance(record, dict) and record.get("corpus") in roots
    ]
    if len(records) != 30:
        raise ValueError("baxy_hyperspotter_human_record_count_invalid")
    audio_paths = []
    for record in records:
        path = (
            roots[str(record["corpus"])] / str(record["relative_path"])
        ).resolve(strict=True)
        if _TRAIN._LOGMEL.sha256(path) != record.get("audio_sha256"):
            raise ValueError("baxy_hyperspotter_human_audio_hash_mismatch")
        audio_paths.append(path)

    started = time.perf_counter()
    model, tokenizer, torch, torch_device, checkpoint = load_candidate(
        hyperspotter_root=hyperspotter_root,
        hyperspotter_site_packages=hyperspotter_site_packages,
        official_checkpoint_path=official_checkpoint_path,
        candidate_checkpoint_path=candidate_checkpoint_path,
        device=device,
    )
    sys.modules.pop("whisper", None)
    while str(hyperspotter_site_packages) in sys.path:
        sys.path.remove(str(hyperspotter_site_packages))
    sys.path.insert(0, str(hyperspotter_site_packages))
    importlib.invalidate_caches()
    import soundfile as sf
    import whisper
    import torch.nn as nn

    arrays = []
    for path in audio_paths:
        waveform, sample_rate = sf.read(str(path), dtype="float32", always_2d=True)
        if sample_rate != 16_000:
            raise ValueError("baxy_hyperspotter_human_sample_rate_invalid")
        feature = (
            whisper.log_mel_spectrogram(
                torch.from_numpy(waveform.mean(axis=1)), n_mels=80
            )
            .transpose(0, 1)
            .contiguous()
            .cpu()
            .numpy()
            .astype(np.float32)
        )
        arrays.append(feature)
    aliases = list(checkpoint["aliases"])
    keyword_ids = tokenizer(aliases)["input_ids"]
    keyword_lengths = torch.tensor([len(value) for value in keyword_ids], dtype=torch.long)
    keyword_values = nn.utils.rnn.pad_sequence(
        [torch.tensor(value, dtype=torch.long, device=torch_device) for value in keyword_ids],
        padding_value=tokenizer.pad_token_id,
        batch_first=True,
    )
    with torch.inference_mode():
        alias_weights = model.get_text_weights(keyword_values, keyword_lengths)
    score_batches = []
    with torch.inference_mode():
        for start in range(0, len(arrays), batch_size):
            current = arrays[start : start + batch_size]
            lengths = [len(value) for value in current]
            values = np.zeros((len(current), max(lengths), 80), dtype=np.float32)
            for row, value in enumerate(current):
                values[row, : len(value)] = value
            with torch.autocast(
                device_type=device, dtype=torch.float16, enabled=device == "cuda"
            ):
                logits = model.run_classifier(
                    torch.from_numpy(values).to(torch_device),
                    alias_weights,
                    torch.tensor(lengths, dtype=torch.long, device=torch_device),
                )
            score_batches.append(logits.max(dim=1).values.float().cpu().numpy())
    scores = np.concatenate(score_batches)
    labels = np.asarray(
        [record.get("label") == "positive" for record in records], dtype=np.int64
    )
    groups = np.asarray([str(record["group"]) for record in records])
    metrics = score_metrics(
        labels=labels,
        scores=scores,
        groups=groups,
        fixed_threshold=fixed_threshold,
    )

    ctc_lookup = {
        (str(record["corpus"]), str(record["relative_path"])): record
        for record in ctc_report.get("records", [])
        if isinstance(record, dict)
    }
    ctc_decisions = []
    for record in records:
        corpus = "legacy" if record["corpus"] == "human_legacy" else "expanded"
        matched = ctc_lookup.get((corpus, str(record["relative_path"])))
        if matched is None:
            raise ValueError("baxy_hyperspotter_human_ctc_mapping_invalid")
        ctc_decisions.append(bool(matched["ctc_product_detected"]))
    ctc_decisions_array = np.asarray(ctc_decisions)
    decision_scores = scores.astype(np.float64)
    fixed_hyper_decisions = decision_scores >= fixed_threshold
    fusion = fusion_metrics(
        labels=labels,
        ctc_decisions=ctc_decisions_array,
        hyper_decisions=fixed_hyper_decisions,
    )
    human_global_threshold = float(
        metrics["human_global_zero_false_diagnostic"]["threshold"]
    )
    global_hyper_decisions = decision_scores >= human_global_threshold
    global_fusion = fusion_metrics(
        labels=labels,
        ctc_decisions=ctc_decisions_array,
        hyper_decisions=global_hyper_decisions,
    )
    partitions = np.asarray([str(record["corpus"]) for record in records])
    per_corpus = partition_fusion_metrics(
        labels=labels,
        ctc_decisions=ctc_decisions_array,
        hyper_decisions=fixed_hyper_decisions,
        partitions=partitions,
    )
    report: dict[str, object] = {
        "schema": "baxy.baxy-hyperspotter-human-development.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "fixed_human_development_aggregate_only",
        "sources": {
            "human_feature_manifest_sha256": _TRAIN._LOGMEL.sha256(
                human_feature_manifest_path
            ),
            "ctc_development_report_sha256": _TRAIN._LOGMEL.sha256(
                ctc_development_report_path
            ),
            "official_checkpoint_sha256": _TRAIN._LOGMEL.sha256(
                official_checkpoint_path
            ),
            "candidate_checkpoint_sha256": _TRAIN._LOGMEL.sha256(
                candidate_checkpoint_path
            ),
            "candidate_training_report_sha256": _TRAIN._LOGMEL.sha256(
                candidate_training_report_path
            ),
        },
        "contract": {
            "aliases": aliases,
            "fixed_threshold_source": "speaker_disjoint_synthetic_validation_zero_false",
            "fixed_threshold": fixed_threshold,
            "records": len(records),
            "positive_records": int(labels.sum()),
            "negative_records": int((labels == 0).sum()),
            "speaker_groups": len(set(groups.tolist())),
            "audio_or_filenames_retained": False,
        },
        "metrics": metrics,
        "fixed_threshold_ctc_fusion": fusion,
        "human_global_zero_false_ctc_fusion_diagnostic": global_fusion,
        "fixed_threshold_per_corpus": per_corpus,
        "runtime_seconds": time.perf_counter() - started,
        "candidate_frozen": True,
        "human_development_audio_accessed": True,
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
    parser.add_argument("--human-feature-manifest", type=Path, required=True)
    parser.add_argument("--legacy-root", type=Path, required=True)
    parser.add_argument("--expanded-root", type=Path, required=True)
    parser.add_argument("--ctc-development-report", type=Path, required=True)
    parser.add_argument("--hyperspotter-root", type=Path, required=True)
    parser.add_argument("--hyperspotter-site-packages", type=Path, required=True)
    parser.add_argument("--official-checkpoint", type=Path, required=True)
    parser.add_argument("--candidate-checkpoint", type=Path, required=True)
    parser.add_argument("--candidate-training-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=30)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    report = evaluate(
        human_feature_manifest_path=arguments.human_feature_manifest,
        legacy_root=arguments.legacy_root,
        expanded_root=arguments.expanded_root,
        ctc_development_report_path=arguments.ctc_development_report,
        hyperspotter_root=arguments.hyperspotter_root,
        hyperspotter_site_packages=arguments.hyperspotter_site_packages,
        official_checkpoint_path=arguments.official_checkpoint,
        candidate_checkpoint_path=arguments.candidate_checkpoint,
        candidate_training_report_path=arguments.candidate_training_report,
        output_path=arguments.output,
        batch_size=arguments.batch_size,
        device=arguments.device,
    )
    print(
        json.dumps(
            {
                "metrics": report["metrics"],
                "fixed_threshold_ctc_fusion": report[
                    "fixed_threshold_ctc_fusion"
                ],
                "human_global_zero_false_ctc_fusion_diagnostic": report[
                    "human_global_zero_false_ctc_fusion_diagnostic"
                ],
                "fixed_threshold_per_corpus": report[
                    "fixed_threshold_per_corpus"
                ],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
