"""Fuse HyperSpotter with continuous product phoneme-CTC margins.

Feature choice, linear weight, normalization, and zero-false threshold are
selected on legacy human development.  Expanded development is excluded from
selection and evaluated only after the policy is fixed.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
import math
from pathlib import Path
import sys

import numpy as np


BETA_GRID = (-4.0, -2.0, -1.0, -0.5, -0.25, 0.0, 0.25, 0.5, 1.0, 2.0, 4.0)
WINDOW_LENGTHS = (25, 35, 45, 60)
WINDOW_STRIDE = 5


def load_component(filename: str, name: str) -> object:
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"baxy_ctc_continuous_component_invalid:{filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_BASE = load_component(
    "train_baxy_hyperspotter_binary_v1.py", "_baxy_ctc_continuous_base_v4"
)
_EVALUATOR = load_component(
    "evaluate_baxy_hyperspotter_human_development_v1.py",
    "_baxy_ctc_continuous_evaluator_v4",
)


def standardized(values: np.ndarray, reference_mask: np.ndarray) -> tuple[np.ndarray, float, float]:
    values = np.asarray(values, dtype=np.float64)
    reference = values[np.asarray(reference_mask, dtype=np.bool_)]
    center = float(np.mean(reference))
    scale = float(np.std(reference))
    if not math.isfinite(center) or not math.isfinite(scale) or scale <= 1e-9:
        raise ValueError("baxy_ctc_continuous_standardization_invalid")
    return (values - center) / scale, center, scale


def select_policy(
    *,
    labels: np.ndarray,
    hyper_scores: np.ndarray,
    features: dict[str, np.ndarray],
) -> dict[str, object]:
    labels = np.asarray(labels, dtype=np.int64)
    hyper = np.asarray(hyper_scores, dtype=np.float64)
    if set(labels.tolist()) != {0, 1} or hyper.shape != labels.shape:
        raise ValueError("baxy_ctc_continuous_policy_labels_invalid")
    candidates = []
    for feature_name, raw in sorted(features.items()):
        values = np.asarray(raw, dtype=np.float64)
        if values.shape != labels.shape or not np.isfinite(values).all():
            raise ValueError("baxy_ctc_continuous_policy_feature_invalid")
        center = float(np.mean(values))
        scale = float(np.std(values))
        if scale <= 1e-9:
            continue
        normalized = (values - center) / scale
        for beta in BETA_GRID:
            scores = hyper + beta * normalized
            threshold = float(np.nextafter(np.max(scores[labels == 0]), np.inf))
            metrics = _BASE.binary_metrics(labels, scores)
            candidates.append(
                {
                    "feature": feature_name,
                    "feature_center": center,
                    "feature_scale": scale,
                    "beta": beta,
                    "threshold": threshold,
                    "positive_hits": int(
                        np.count_nonzero(scores[labels == 1] >= threshold)
                    ),
                    "false_hits": int(
                        np.count_nonzero(scores[labels == 0] >= threshold)
                    ),
                    "auc": float(metrics["auc"]),
                    "equal_error_rate": float(metrics["equal_error_rate"]),
                }
            )
    if not candidates:
        raise ValueError("baxy_ctc_continuous_policy_candidates_missing")
    selected = max(
        candidates,
        key=lambda value: (
            int(value["positive_hits"]),
            float(value["auc"]),
            -float(value["equal_error_rate"]),
            -abs(float(value["beta"])),
            value["feature"] == "full_clip_margin",
        ),
    )
    return {"candidates": candidates, "selected": selected}


def continuous_ctc_margins(
    log_probabilities: np.ndarray, wake_module: object
) -> tuple[float, float]:
    values = np.asarray(log_probabilities, dtype=np.float64)
    if values.ndim != 2 or len(values) < min(WINDOW_LENGTHS):
        raise ValueError("baxy_ctc_continuous_log_probabilities_invalid")

    def margin_batch(segments: np.ndarray) -> np.ndarray:
        target = np.max(
            np.stack(
                [
                    ctc_log_probability_batch(
                        segments, sequence, blank_id=wake_module.BLANK_ID
                    )
                    for sequence in wake_module.TARGET_IDS
                ]
            ),
            axis=0,
        )
        confusable = np.max(
            np.stack(
                [
                    ctc_log_probability_batch(
                        segments, sequence, blank_id=wake_module.BLANK_ID
                    )
                    for sequence in wake_module.CONFUSABLE_IDS
                ]
            ),
            axis=0,
        )
        return target - confusable

    full = float(margin_batch(values[None, :, :])[0])
    windows = []
    for length in WINDOW_LENGTHS:
        final_start = max(0, len(values) - length)
        starts = list(range(0, final_start + 1, WINDOW_STRIDE))
        if not starts or starts[-1] != final_start:
            starts.append(final_start)
        segments = np.stack([values[start : start + length] for start in starts])
        windows.extend(margin_batch(segments).tolist())
    maximum = float(max(windows))
    if not math.isfinite(full) or not math.isfinite(maximum):
        raise ValueError("baxy_ctc_continuous_margin_invalid")
    return full, maximum


def ctc_log_probability_batch(
    log_probabilities: np.ndarray,
    sequence: tuple[int, ...] | list[int],
    *,
    blank_id: int,
) -> np.ndarray:
    values = np.asarray(log_probabilities, dtype=np.float64)
    tokens = [int(token) for token in sequence]
    if values.ndim != 3 or not tokens or values.shape[1] < 1:
        raise ValueError("baxy_ctc_continuous_batch_invalid")
    states = [blank_id]
    for token in tokens:
        states.extend((token, blank_id))
    state_ids = np.asarray(states, dtype=np.int64)
    batch = len(values)
    previous = np.full((batch, len(states)), -np.inf, dtype=np.float64)
    previous[:, 0] = values[:, 0, blank_id]
    previous[:, 1] = values[:, 0, tokens[0]]
    allow_skip = np.asarray(
        [
            state > 1
            and token != blank_id
            and token != states[state - 2]
            for state, token in enumerate(states)
        ],
        dtype=np.bool_,
    )
    for frame in range(1, values.shape[1]):
        total = previous.copy()
        total[:, 1:] = np.logaddexp(total[:, 1:], previous[:, :-1])
        if np.any(allow_skip):
            skip_states = np.flatnonzero(allow_skip)
            total[:, skip_states] = np.logaddexp(
                total[:, skip_states], previous[:, skip_states - 2]
            )
        previous = total + values[:, frame, state_ids]
    return np.logaddexp(previous[:, -1], previous[:, -2])


def evaluate(
    *,
    human_feature_manifest_path: Path,
    human_source_manifest_path: Path,
    legacy_root: Path,
    expanded_root: Path,
    verifier_manifest_path: Path,
    ctc_development_report_path: Path,
    hyperspotter_root: Path,
    hyperspotter_site_packages: Path,
    official_checkpoint_path: Path,
    candidate_checkpoint_path: Path,
    output_path: Path,
    hyper_batch_size: int,
    device: str,
) -> dict[str, object]:
    if output_path.exists() or hyper_batch_size < 1 or device not in {"cpu", "cuda"}:
        raise ValueError("baxy_ctc_continuous_schedule_invalid")
    inputs = [
        human_feature_manifest_path,
        human_source_manifest_path,
        legacy_root,
        expanded_root,
        verifier_manifest_path,
        ctc_development_report_path,
        hyperspotter_root,
        hyperspotter_site_packages,
        official_checkpoint_path,
        candidate_checkpoint_path,
    ]
    (
        human_feature_manifest_path,
        human_source_manifest_path,
        legacy_root,
        expanded_root,
        verifier_manifest_path,
        ctc_development_report_path,
        hyperspotter_root,
        hyperspotter_site_packages,
        official_checkpoint_path,
        candidate_checkpoint_path,
    ) = [path.resolve(strict=True) for path in inputs]
    output_path = output_path.resolve()
    human_manifest = _BASE._LOGMEL.read_object(human_feature_manifest_path)
    source_manifest = _BASE._LOGMEL.read_object(human_source_manifest_path)
    ctc_report = _BASE._LOGMEL.read_object(ctc_development_report_path)
    if (
        human_manifest.get("schema")
        != "baxy.baxy-hyperspotter-human-logmel.v1"
        or human_manifest.get("blind_human_audio_accessed") is not False
        or source_manifest.get("schema")
        != "baxy.wav2vec2-hidden-wake-training-features.v1"
        or source_manifest.get("blind_human_audio_accessed") is not False
        or ctc_report.get("schema") != "baxy.wake-ssl-ctc-ensemble-development.v1"
        or ctc_report.get("blind_human_audio_accessed") is not False
    ):
        raise ValueError("baxy_ctc_continuous_boundary_invalid")
    records = human_manifest.get("records")
    files = human_manifest.get("files")
    if not isinstance(records, list) or not isinstance(files, dict) or len(records) != 30:
        raise ValueError("baxy_ctc_continuous_records_invalid")
    feature_path = human_feature_manifest_path.parent / str(files["logmel"])
    offset_path = human_feature_manifest_path.parent / str(files["offsets"])
    if (
        _BASE._LOGMEL.sha256(feature_path) != files.get("logmel_sha256")
        or _BASE._LOGMEL.sha256(offset_path) != files.get("offsets_sha256")
    ):
        raise ValueError("baxy_ctc_continuous_hyper_feature_hash_invalid")
    features = np.load(feature_path, mmap_mode="r")
    offsets = np.load(offset_path)
    model, tokenizer, torch, torch_device, checkpoint = _EVALUATOR.load_candidate(
        hyperspotter_root=hyperspotter_root,
        hyperspotter_site_packages=hyperspotter_site_packages,
        official_checkpoint_path=official_checkpoint_path,
        candidate_checkpoint_path=candidate_checkpoint_path,
        device=device,
    )

    import torch.nn as nn

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
    hyper_batches = []
    with torch.inference_mode():
        for start in range(0, len(records), hyper_batch_size):
            indexes = list(range(start, min(start + hyper_batch_size, len(records))))
            lengths = [int(offsets[index + 1] - offsets[index]) for index in indexes]
            values = np.zeros((len(indexes), max(lengths), 80), dtype=np.float32)
            for row, index in enumerate(indexes):
                values[row, : lengths[row]] = features[
                    int(offsets[index]) : int(offsets[index + 1])
                ]
            with torch.autocast(
                device_type=device, dtype=torch.float16, enabled=device == "cuda"
            ):
                logits = model.run_classifier(
                    torch.from_numpy(values).to(torch_device),
                    alias_weights,
                    torch.tensor(lengths, dtype=torch.long, device=torch_device),
                )
            hyper_batches.append(logits.max(dim=1).values.float().cpu().numpy())
    hyper_scores = np.concatenate(hyper_batches).astype(np.float64)

    # Release the CUDA acoustic model before mapping the 1.26 GB external-data
    # ONNX graph.  This avoids paging while preserving the completed scores.
    import gc

    del model, alias_weights, keyword_values
    if device == "cuda":
        torch.cuda.empty_cache()
    gc.collect()

    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root / "src") not in sys.path:
        sys.path.insert(0, str(repo_root / "src"))
    from baxy_mind import wake_verifier as wake
    import soundfile as sf

    verifier_config = wake.load_wake_verifier_candidate_config(verifier_manifest_path)
    verifier = wake.OnnxWakeVerifier(verifier_config)
    source_lookup = {
        (str(record["corpus"]), str(record["relative_path"])): record
        for record in source_manifest.get("records", [])
        if isinstance(record, dict) and record.get("corpus") in {
            "human_legacy",
            "human_expanded",
        }
    }
    roots = {"human_legacy": legacy_root, "human_expanded": expanded_root}
    full_margins = []
    window_margins = []
    for index, record in enumerate(records):
        key = (str(record["corpus"]), str(record["relative_path"]))
        source = source_lookup.get(key)
        if source is None:
            raise ValueError("baxy_ctc_continuous_source_mapping_invalid")
        path = (roots[key[0]] / key[1]).resolve(strict=True)
        if _BASE._LOGMEL.sha256(path) != source.get("audio_sha256"):
            raise ValueError("baxy_ctc_continuous_audio_hash_invalid")
        waveform, sample_rate = sf.read(str(path), dtype="float32", always_2d=True)
        audio = waveform.mean(axis=1)
        if sample_rate != wake.SAMPLE_RATE or len(audio) != verifier_config.maximum_samples:
            raise ValueError("baxy_ctc_continuous_audio_contract_invalid")
        logits = verifier._session.run(
            ["logits"], {"input_values": wake.normalize_audio(audio)}
        )[0]
        probabilities = wake.compress_category_logits_numpy(
            logits, verifier._category_ids
        )
        full, window = continuous_ctc_margins(
            np.log(np.maximum(probabilities, 1e-12)), wake
        )
        full_margins.append(full)
        window_margins.append(window)
        print(f"BAXY_CTC_CONTINUOUS|{index + 1}/{len(records)}", flush=True)

    labels = np.asarray([record["label"] == "positive" for record in records], dtype=np.int64)
    corpora = np.asarray([str(record["corpus"]) for record in records])
    legacy = corpora == "human_legacy"
    expanded = corpora == "human_expanded"
    feature_values = {
        "full_clip_margin": np.asarray(full_margins, dtype=np.float64),
        "maximum_window_margin": np.asarray(window_margins, dtype=np.float64),
    }
    policy = select_policy(
        labels=labels[legacy],
        hyper_scores=hyper_scores[legacy],
        features={name: values[legacy] for name, values in feature_values.items()},
    )
    selected = policy["selected"]
    selected_feature = feature_values[str(selected["feature"])]
    normalized_feature = (
        selected_feature - float(selected["feature_center"])
    ) / float(selected["feature_scale"])
    combined_scores = hyper_scores + float(selected["beta"]) * normalized_feature
    threshold = float(selected["threshold"])
    decisions = combined_scores >= threshold

    def metrics(mask: np.ndarray) -> dict[str, object]:
        result = _BASE.binary_metrics(labels[mask], combined_scores[mask])
        positive = labels[mask] == 1
        negative = ~positive
        return {
            **result,
            "fixed_threshold": threshold,
            "fixed_positive_hits": int(np.count_nonzero(decisions[mask] & positive)),
            "fixed_false_hits": int(np.count_nonzero(decisions[mask] & negative)),
        }

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
            raise ValueError("baxy_ctc_continuous_ctc_mapping_invalid")
        ctc_decisions.append(bool(matched["ctc_product_detected"]))
    fusion = _EVALUATOR.fusion_metrics(
        labels=labels,
        ctc_decisions=np.asarray(ctc_decisions),
        hyper_decisions=decisions,
    )
    report: dict[str, object] = {
        "schema": "baxy.baxy-hyperspotter-ctc-continuous-development.v4",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "legacy_selected_expanded_excluded_continuous_ctc_fusion",
        "sources": {
            "human_feature_manifest_sha256": _BASE._LOGMEL.sha256(
                human_feature_manifest_path
            ),
            "human_source_manifest_sha256": _BASE._LOGMEL.sha256(
                human_source_manifest_path
            ),
            "verifier_manifest_sha256": _BASE._LOGMEL.sha256(verifier_manifest_path),
            "ctc_development_report_sha256": _BASE._LOGMEL.sha256(
                ctc_development_report_path
            ),
            "candidate_checkpoint_sha256": _BASE._LOGMEL.sha256(
                candidate_checkpoint_path
            ),
        },
        "contract": {
            "beta_grid": list(BETA_GRID),
            "window_lengths": list(WINDOW_LENGTHS),
            "window_stride": WINDOW_STRIDE,
            "feature_normalization": "legacy_partition_mean_and_standard_deviation",
            "selection_partition": "human_legacy",
            "independent_evaluation_partition": "human_expanded",
            "expanded_partition_used_for_policy_selection": False,
            "audio_or_filenames_retained": False,
        },
        "policy_selection": policy,
        "legacy_selection_metrics": metrics(legacy),
        "expanded_independent_metrics": metrics(expanded),
        "all_human_diagnostic": metrics(np.ones(len(records), dtype=np.bool_)),
        "fixed_policy_ctc_fusion": fusion,
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
    parser.add_argument("--human-source-manifest", type=Path, required=True)
    parser.add_argument("--legacy-root", type=Path, required=True)
    parser.add_argument("--expanded-root", type=Path, required=True)
    parser.add_argument("--verifier-manifest", type=Path, required=True)
    parser.add_argument("--ctc-development-report", type=Path, required=True)
    parser.add_argument("--hyperspotter-root", type=Path, required=True)
    parser.add_argument("--hyperspotter-site-packages", type=Path, required=True)
    parser.add_argument("--official-checkpoint", type=Path, required=True)
    parser.add_argument("--candidate-checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--hyper-batch-size", type=int, default=30)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    report = evaluate(
        human_feature_manifest_path=arguments.human_feature_manifest,
        human_source_manifest_path=arguments.human_source_manifest,
        legacy_root=arguments.legacy_root,
        expanded_root=arguments.expanded_root,
        verifier_manifest_path=arguments.verifier_manifest,
        ctc_development_report_path=arguments.ctc_development_report,
        hyperspotter_root=arguments.hyperspotter_root,
        hyperspotter_site_packages=arguments.hyperspotter_site_packages,
        official_checkpoint_path=arguments.official_checkpoint,
        candidate_checkpoint_path=arguments.candidate_checkpoint,
        output_path=arguments.output,
        hyper_batch_size=arguments.hyper_batch_size,
        device=arguments.device,
    )
    print(
        json.dumps(
            {
                "selected": report["policy_selection"]["selected"],
                "legacy": report["legacy_selection_metrics"],
                "expanded": report["expanded_independent_metrics"],
                "fusion": report["fixed_policy_ctc_fusion"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
