"""Calibrate HyperSpotter with the existing acoustic stage-one excess score.

Alpha and the zero-false threshold are selected only on the legacy human
development partition.  Expanded development is excluded from selection and
is evaluated after the policy is fixed.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path

import numpy as np


ALPHA_GRID = (0.0, 5.0, 10.0, 20.0, 40.0, 80.0, 160.0)
STAGE1_REFERENCE = 0.0175


def load_component(filename: str, name: str) -> object:
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"baxy_stage1_calibration_component_invalid:{filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_BASE = load_component(
    "train_baxy_hyperspotter_binary_v1.py", "_baxy_stage1_calibration_base_v3"
)
_EVALUATOR = load_component(
    "evaluate_baxy_hyperspotter_human_development_v1.py",
    "_baxy_stage1_calibration_evaluator_v3",
)


def adjusted_scores(
    hyper_scores: np.ndarray, stage1_scores: np.ndarray, alpha: float
) -> np.ndarray:
    hyper = np.asarray(hyper_scores, dtype=np.float64)
    stage1 = np.asarray(stage1_scores, dtype=np.float64)
    if hyper.shape != stage1.shape or alpha < 0.0:
        raise ValueError("baxy_stage1_calibration_scores_invalid")
    return hyper - alpha * np.maximum(stage1 - STAGE1_REFERENCE, 0.0)


def select_policy(
    *, labels: np.ndarray, hyper_scores: np.ndarray, stage1_scores: np.ndarray
) -> dict[str, object]:
    labels = np.asarray(labels, dtype=np.int64)
    if set(labels.tolist()) != {0, 1}:
        raise ValueError("baxy_stage1_calibration_labels_invalid")
    candidates = []
    for alpha in ALPHA_GRID:
        scores = adjusted_scores(hyper_scores, stage1_scores, alpha)
        threshold = float(
            np.nextafter(np.max(scores[labels == 0]), np.inf)
        )
        metrics = _BASE.binary_metrics(labels, scores)
        positive_hits = int(np.count_nonzero(scores[labels == 1] >= threshold))
        candidate = {
            "alpha": alpha,
            "threshold": threshold,
            "positive_hits": positive_hits,
            "false_hits": int(np.count_nonzero(scores[labels == 0] >= threshold)),
            "auc": float(metrics["auc"]),
            "equal_error_rate": float(metrics["equal_error_rate"]),
        }
        candidates.append(candidate)
    selected = max(
        candidates,
        key=lambda value: (
            int(value["positive_hits"]),
            float(value["auc"]),
            -float(value["equal_error_rate"]),
            -float(value["alpha"]),
        ),
    )
    return {"grid": candidates, "selected": selected}


def evaluate(
    *,
    human_feature_manifest_path: Path,
    legacy_product_report_path: Path,
    expanded_product_report_path: Path,
    ctc_development_report_path: Path,
    hyperspotter_root: Path,
    hyperspotter_site_packages: Path,
    official_checkpoint_path: Path,
    candidate_checkpoint_path: Path,
    output_path: Path,
    batch_size: int,
    device: str,
) -> dict[str, object]:
    if output_path.exists() or batch_size < 1 or device not in {"cpu", "cuda"}:
        raise ValueError("baxy_stage1_calibration_schedule_invalid")
    inputs = [
        human_feature_manifest_path,
        legacy_product_report_path,
        expanded_product_report_path,
        ctc_development_report_path,
        hyperspotter_root,
        hyperspotter_site_packages,
        official_checkpoint_path,
        candidate_checkpoint_path,
    ]
    (
        human_feature_manifest_path,
        legacy_product_report_path,
        expanded_product_report_path,
        ctc_development_report_path,
        hyperspotter_root,
        hyperspotter_site_packages,
        official_checkpoint_path,
        candidate_checkpoint_path,
    ) = [path.resolve(strict=True) for path in inputs]
    output_path = output_path.resolve()
    human_manifest = _BASE._LOGMEL.read_object(human_feature_manifest_path)
    legacy_report = _BASE._LOGMEL.read_object(legacy_product_report_path)
    expanded_report = _BASE._LOGMEL.read_object(expanded_product_report_path)
    ctc_report = _BASE._LOGMEL.read_object(ctc_development_report_path)
    if (
        human_manifest.get("schema")
        != "baxy.baxy-hyperspotter-human-logmel.v1"
        or human_manifest.get("blind_human_audio_accessed") is not False
        or legacy_report.get("schema")
        != "baxy.wake-verifier-product-capture-development.v1"
        or legacy_report.get("blind_human_partition_accessed") is not False
        or expanded_report.get("schema")
        != "baxy.wake-verifier-expanded-development.v1"
        or expanded_report.get("blind_human_audio_accessed") is not False
        or ctc_report.get("schema") != "baxy.wake-ssl-ctc-ensemble-development.v1"
        or ctc_report.get("blind_human_audio_accessed") is not False
    ):
        raise ValueError("baxy_stage1_calibration_boundary_invalid")
    records = human_manifest.get("records")
    files = human_manifest.get("files")
    if not isinstance(records, list) or not isinstance(files, dict) or len(records) != 30:
        raise ValueError("baxy_stage1_calibration_records_invalid")
    feature_path = human_feature_manifest_path.parent / str(files["logmel"])
    offset_path = human_feature_manifest_path.parent / str(files["offsets"])
    if (
        _BASE._LOGMEL.sha256(feature_path) != files.get("logmel_sha256")
        or _BASE._LOGMEL.sha256(offset_path) != files.get("offsets_sha256")
    ):
        raise ValueError("baxy_stage1_calibration_feature_hash_invalid")
    features = np.load(feature_path, mmap_mode="r")
    offsets = np.load(offset_path)
    if len(offsets) != len(records) + 1 or int(offsets[-1]) != len(features):
        raise ValueError("baxy_stage1_calibration_feature_shape_invalid")
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
    score_batches = []
    with torch.inference_mode():
        for start in range(0, len(records), batch_size):
            indexes = list(range(start, min(start + batch_size, len(records))))
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
            score_batches.append(logits.max(dim=1).values.float().cpu().numpy())
    hyper_scores = np.concatenate(score_batches).astype(np.float64)
    labels = np.asarray([record["label"] == "positive" for record in records], dtype=np.int64)
    corpora = np.asarray([str(record["corpus"]) for record in records])

    product_lookup = {}
    for corpus, report in (("human_legacy", legacy_report), ("human_expanded", expanded_report)):
        for record in report.get("records", []):
            if isinstance(record, dict):
                product_lookup[(corpus, str(record["relative_path"]))] = record
    stage1_scores = []
    for record in records:
        product = product_lookup.get((str(record["corpus"]), str(record["relative_path"])))
        if product is None:
            raise ValueError("baxy_stage1_calibration_product_mapping_invalid")
        hit = product.get("stage1_hit")
        stage1_scores.append(
            float(hit["score"]) if isinstance(hit, dict) else 0.0
        )
    stage1_scores_array = np.asarray(stage1_scores, dtype=np.float64)
    legacy_mask = corpora == "human_legacy"
    expanded_mask = corpora == "human_expanded"
    policy = select_policy(
        labels=labels[legacy_mask],
        hyper_scores=hyper_scores[legacy_mask],
        stage1_scores=stage1_scores_array[legacy_mask],
    )
    alpha = float(policy["selected"]["alpha"])
    threshold = float(policy["selected"]["threshold"])
    scores = adjusted_scores(hyper_scores, stage1_scores_array, alpha)
    decisions = scores >= threshold

    def partition_metrics(mask: np.ndarray) -> dict[str, object]:
        metrics = _BASE.binary_metrics(labels[mask], scores[mask])
        positive = labels[mask] == 1
        negative = ~positive
        return {
            **metrics,
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
            raise ValueError("baxy_stage1_calibration_ctc_mapping_invalid")
        ctc_decisions.append(bool(matched["ctc_product_detected"]))
    fusion = _EVALUATOR.fusion_metrics(
        labels=labels,
        ctc_decisions=np.asarray(ctc_decisions),
        hyper_decisions=decisions,
    )
    report: dict[str, object] = {
        "schema": "baxy.baxy-hyperspotter-stage1-calibration-development.v3",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "legacy_selected_expanded_excluded_stage1_excess_calibration",
        "sources": {
            "human_feature_manifest_sha256": _BASE._LOGMEL.sha256(
                human_feature_manifest_path
            ),
            "legacy_product_report_sha256": _BASE._LOGMEL.sha256(
                legacy_product_report_path
            ),
            "expanded_product_report_sha256": _BASE._LOGMEL.sha256(
                expanded_product_report_path
            ),
            "ctc_development_report_sha256": _BASE._LOGMEL.sha256(
                ctc_development_report_path
            ),
            "candidate_checkpoint_sha256": _BASE._LOGMEL.sha256(
                candidate_checkpoint_path
            ),
        },
        "contract": {
            "alpha_grid": list(ALPHA_GRID),
            "stage1_reference": STAGE1_REFERENCE,
            "score": "hyper_max_alias_logit_minus_alpha_times_positive_stage1_excess",
            "selection_partition": "human_legacy",
            "independent_evaluation_partition": "human_expanded",
            "expanded_partition_used_for_policy_selection": False,
            "audio_or_filenames_retained": False,
        },
        "policy_selection": policy,
        "legacy_selection_metrics": partition_metrics(legacy_mask),
        "expanded_independent_metrics": partition_metrics(expanded_mask),
        "all_human_diagnostic": partition_metrics(np.ones(len(records), dtype=np.bool_)),
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
    parser.add_argument("--legacy-product-report", type=Path, required=True)
    parser.add_argument("--expanded-product-report", type=Path, required=True)
    parser.add_argument("--ctc-development-report", type=Path, required=True)
    parser.add_argument("--hyperspotter-root", type=Path, required=True)
    parser.add_argument("--hyperspotter-site-packages", type=Path, required=True)
    parser.add_argument("--official-checkpoint", type=Path, required=True)
    parser.add_argument("--candidate-checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=30)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    report = evaluate(
        human_feature_manifest_path=arguments.human_feature_manifest,
        legacy_product_report_path=arguments.legacy_product_report,
        expanded_product_report_path=arguments.expanded_product_report,
        ctc_development_report_path=arguments.ctc_development_report,
        hyperspotter_root=arguments.hyperspotter_root,
        hyperspotter_site_packages=arguments.hyperspotter_site_packages,
        official_checkpoint_path=arguments.official_checkpoint,
        candidate_checkpoint_path=arguments.candidate_checkpoint,
        output_path=arguments.output,
        batch_size=arguments.batch_size,
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
