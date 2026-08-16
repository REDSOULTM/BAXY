"""Freeze the MSWC QbyE candidate before opening a fresh word evaluation."""

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
        raise ValueError(f"mswc_qbye_fresh_preregister_json_invalid:{path}")
    return value


def frozen_candidate(report_path: Path) -> dict[str, object]:
    report_path = report_path.resolve(strict=True)
    report = read_object(report_path)
    sources = report.get("sources")
    contract = report.get("contract")
    selected = report.get("selected")
    if (
        report.get("schema") != "baxy.mswc-spanish-qbye-angleproto-training.v1"
        or report.get("open_selection_examples_scored") is not False
        or not isinstance(sources, dict)
        or not isinstance(contract, dict)
        or not isinstance(selected, dict)
        or not isinstance(selected.get("open_keyword_tuning"), dict)
    ):
        raise ValueError(f"mswc_qbye_fresh_training_report_invalid:{report_path}")
    checkpoint_path = (report_path.parent / str(selected["checkpoint"])).resolve(
        strict=True
    )
    checkpoint_hash = sha256(checkpoint_path)
    if checkpoint_hash != selected.get("checkpoint_sha256"):
        raise ValueError("mswc_qbye_fresh_checkpoint_hash_mismatch")
    return {
        "training_report_path": report_path.as_posix(),
        "training_report_sha256": sha256(report_path),
        "training_feature_manifest_sha256": sources["feature_manifest_sha256"],
        "checkpoint_path": checkpoint_path.as_posix(),
        "checkpoint_sha256": checkpoint_hash,
        "layer": contract["layer"],
        "objective": contract["objective"],
        "seed": contract["seed"],
        "maximum_frames": contract["maximum_frames"],
        "embedding_size": contract["embedding_size"],
        "best_epoch": selected["best_epoch"],
        "tuning_metrics": selected["open_keyword_tuning"],
    }


def preregister(
    *,
    candidate_report_path: Path,
    reference_report_path: Path,
    fresh_feature_manifest_path: Path,
    output_path: Path,
) -> dict[str, object]:
    if output_path.exists():
        raise ValueError("mswc_qbye_fresh_preregister_schedule_invalid")
    fresh_feature_manifest_path = fresh_feature_manifest_path.resolve(strict=True)
    output_path = output_path.resolve()
    manifest = read_object(fresh_feature_manifest_path)
    records = manifest.get("records")
    contract = manifest.get("contract")
    if (
        manifest.get("schema")
        != "baxy.mswc-spanish-qbye-fresh-evaluation-wav2vec2-features.v2"
        or manifest.get("official_test_audio_accessed") is not False
        or manifest.get("blind_human_audio_accessed") is not False
        or not isinstance(records, list)
        or not isinstance(contract, dict)
        or contract.get("layers") != [16]
    ):
        raise ValueError("mswc_qbye_fresh_feature_boundary_invalid")
    candidate = frozen_candidate(candidate_report_path)
    reference = frozen_candidate(reference_report_path)
    if (
        candidate["layer"] != 16
        or reference["layer"] != 16
        or candidate["maximum_frames"] != reference["maximum_frames"]
        or candidate["embedding_size"] != reference["embedding_size"]
        or candidate["training_feature_manifest_sha256"]
        != reference["training_feature_manifest_sha256"]
    ):
        raise ValueError("mswc_qbye_fresh_candidate_contract_mismatch")
    enrollments = sum(
        isinstance(record, dict)
        and record.get("partition") == "open_keyword_enrollment"
        for record in records
    )
    queries = sum(
        isinstance(record, dict) and record.get("partition") == "open_keyword_query"
        for record in records
    )
    classes = {
        str(record["class_name"])
        for record in records
        if isinstance(record, dict)
    }
    if len(classes) != 200 or enrollments != 800 or queries != 2400:
        raise ValueError("mswc_qbye_fresh_partition_invalid")
    report: dict[str, object] = {
        "schema": "baxy.mswc-spanish-qbye-fresh-gate-preregistration.v2",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "freeze_hard_tail_candidate_before_fresh_open_word_evaluation",
        "sources": {
            "fresh_feature_manifest_path": fresh_feature_manifest_path.as_posix(),
            "fresh_feature_manifest_sha256": sha256(fresh_feature_manifest_path),
        },
        "contract": {
            "fresh_word_classes": len(classes),
            "fresh_enrollments": enrollments,
            "fresh_queries": queries,
            "gate_thresholds": {
                "minimum_top1_accuracy": 0.94,
                "minimum_pair_auc": 0.997,
                "maximum_equal_error_rate": 0.025,
                "minimum_true_pair_recall_at_zero_false_pairs": 0.20,
                "minimum_top1_delta_over_reference": -0.005,
                "minimum_pair_auc_delta_over_reference": -0.0005,
                "maximum_equal_error_rate_delta_over_reference": 0.005,
                "minimum_zero_false_recall_delta_over_reference": 0.0,
            },
            "single_aggregate_open": True,
            "no_individual_query_export": True,
            "no_post_evaluation_candidate_switching": True,
        },
        "candidate": candidate,
        "reference": reference,
        "fresh_examples_scored": False,
        "fresh_evaluation_open_count": 0,
        "baxy_human_examples_scored": False,
        "official_test_audio_accessed": False,
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
    parser.add_argument("--candidate-report", type=Path, required=True)
    parser.add_argument("--reference-report", type=Path, required=True)
    parser.add_argument("--fresh-feature-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = preregister(
        candidate_report_path=args.candidate_report,
        reference_report_path=args.reference_report,
        fresh_feature_manifest_path=args.fresh_feature_manifest,
        output_path=args.output,
    )
    print(json.dumps(report["contract"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
