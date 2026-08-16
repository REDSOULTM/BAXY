"""Freeze one tuning-selected QbyE candidate before opening selection words."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"mswc_qbye_select_json_invalid:{path}")
    return value


def tuning_rank(report: dict[str, object]) -> tuple[float, float, float]:
    selected = report.get("selected")
    if not isinstance(selected, dict) or not isinstance(
        selected.get("open_keyword_tuning"), dict
    ):
        raise ValueError("mswc_qbye_select_tuning_metrics_missing")
    metrics = selected["open_keyword_tuning"]
    return (
        float(metrics["top1_accuracy"]),
        float(metrics["pair_auc"]),
        -float(metrics["equal_error_rate"]),
    )


def select(
    *,
    training_report_paths: list[Path],
    baseline_tuning_report_path: Path,
    output_path: Path,
) -> dict[str, object]:
    if output_path.exists() or len(training_report_paths) < 2:
        raise ValueError("mswc_qbye_select_schedule_invalid")
    output_path = output_path.resolve()
    baseline_tuning_report_path = baseline_tuning_report_path.resolve(strict=True)
    baseline = read_object(baseline_tuning_report_path)
    if (
        baseline.get("schema") != "baxy.mswc-spanish-qbye-ssl-baseline.v1"
        or not isinstance(baseline.get("selected_run"), dict)
        or not isinstance(baseline.get("contract"), dict)
        or baseline["contract"].get("open_partition") != "tuning"
    ):
        raise ValueError("mswc_qbye_select_baseline_invalid")
    candidates = []
    feature_manifest_hash = None
    open_split_seed = None
    for path_raw in training_report_paths:
        path = path_raw.resolve(strict=True)
        report = read_object(path)
        sources = report.get("sources")
        contract = report.get("contract")
        selected = report.get("selected")
        if (
            report.get("schema") != "baxy.mswc-spanish-qbye-angleproto-training.v1"
            or report.get("open_selection_examples_scored") is not False
            or not isinstance(sources, dict)
            or not isinstance(contract, dict)
            or not isinstance(selected, dict)
        ):
            raise ValueError(f"mswc_qbye_select_training_report_invalid:{path}")
        current_feature_hash = str(sources["feature_manifest_sha256"])
        current_split_seed = int(contract["open_split_seed"])
        if feature_manifest_hash is None:
            feature_manifest_hash = current_feature_hash
            open_split_seed = current_split_seed
        elif (
            feature_manifest_hash != current_feature_hash
            or open_split_seed != current_split_seed
        ):
            raise ValueError("mswc_qbye_select_candidate_contract_mismatch")
        checkpoint_path = path.parent / str(selected["checkpoint"])
        checkpoint_path = checkpoint_path.resolve(strict=True)
        if sha256(checkpoint_path) != selected.get("checkpoint_sha256"):
            raise ValueError("mswc_qbye_select_checkpoint_hash_mismatch")
        candidates.append(
            {
                "training_report_path": path.as_posix(),
                "training_report_sha256": sha256(path),
                "checkpoint_path": checkpoint_path.as_posix(),
                "checkpoint_sha256": selected["checkpoint_sha256"],
                "layer": contract["layer"],
                "objective": contract["objective"],
                "seed": contract["seed"],
                "best_epoch": selected["best_epoch"],
                "open_keyword_tuning": selected["open_keyword_tuning"],
                "rank": tuning_rank(report),
            }
        )
    best = max(
        candidates,
        key=lambda item: (
            tuple(item["rank"]),
            -int(item["layer"]),
            str(item["objective"]),
            -int(item["seed"]),
        ),
    )
    baseline_selected = baseline["selected_run"]
    report: dict[str, object] = {
        "schema": "baxy.mswc-spanish-qbye-selection-preregistration.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "freeze_tuning_choice_before_open_keyword_selection_evaluation",
        "sources": {
            "feature_manifest_sha256": feature_manifest_hash,
            "baseline_tuning_report_path": baseline_tuning_report_path.as_posix(),
            "baseline_tuning_report_sha256": sha256(baseline_tuning_report_path),
        },
        "contract": {
            "open_split_seed": open_split_seed,
            "candidate_rank": "top1_then_pair_auc_then_negative_eer",
            "selection_gate": {
                "minimum_top1_accuracy": 0.90,
                "minimum_pair_auc": 0.99,
                "maximum_equal_error_rate": 0.05,
                "minimum_true_pair_recall_at_zero_false_pairs": 0.20,
                "minimum_top1_delta_over_frozen_ssl_baseline": 0.0,
            },
            "no_post_selection_candidate_switching": True,
        },
        "candidates": candidates,
        "selected_candidate": {
            key: best[key]
            for key in (
                "training_report_path",
                "training_report_sha256",
                "checkpoint_path",
                "checkpoint_sha256",
                "layer",
                "objective",
                "seed",
                "best_epoch",
                "open_keyword_tuning",
            )
        },
        "frozen_baseline": {
            "layer": baseline_selected["layer"],
            "pooling": baseline_selected["pooling"],
            "training_global_center_subtracted": baseline_selected[
                "training_global_center_subtracted"
            ],
            "open_keyword_tuning": baseline_selected["metrics"],
        },
        "open_selection_examples_scored": False,
        "baxy_human_examples_scored": False,
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
    parser.add_argument("--training-report", type=Path, nargs="+", required=True)
    parser.add_argument("--baseline-tuning-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = select(
        training_report_paths=args.training_report,
        baseline_tuning_report_path=args.baseline_tuning_report,
        output_path=args.output,
    )
    print(json.dumps(report["selected_candidate"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
