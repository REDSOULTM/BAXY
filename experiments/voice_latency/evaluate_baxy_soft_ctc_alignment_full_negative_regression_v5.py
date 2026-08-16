"""Run the full 100 h regression with the preregistered soft-CTC guard."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path


def load_component(filename: str, name: str) -> object:
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"baxy_soft_ctc_full_component_invalid:{filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_V2 = load_component(
    "evaluate_baxy_contextual_fusion_negative_regression_v2.py",
    "_baxy_soft_ctc_full_v2",
)
_V8 = load_component(
    "evaluate_baxy_soft_ctc_alignment_development_v8.py",
    "_baxy_soft_ctc_full_v8",
)


def validate_development_binding(
    development: object, failed_regression: object
) -> float:
    if not isinstance(development, dict) or not isinstance(failed_regression, dict):
        raise ValueError("baxy_soft_ctc_full_evidence_invalid")
    selected = development.get("selectedSoftCtcPolicy")
    if (
        development.get("schema") != "baxy.soft-ctc-alignment-development.v8"
        or development.get("softCtcDevelopmentGatePassed") is not True
        or development.get("blindHumanAudioAccessed") is not False
        or development.get("audioTranscriptsOrFilenamesRetained") is not False
        or development.get("policy", {}).get("guardRequiresSameFusionPassingView")
        is not True
        or development.get("policy", {}).get("contextualHotwordScore") != 4.0
        or development.get("policy", {}).get(
            "selectionPerformedBeforeAnyNewLongNegativeRegression"
        )
        is not True
        or not isinstance(selected, dict)
        or selected.get("threshold") != -0.25
        or failed_regression.get("schema")
        != "baxy.contextual-strength-negative-regression.v3"
        or failed_regression.get("regressionPassed") is not False
        or failed_regression.get("metrics", {}).get(
            "guardedNegativeFalseActivations"
        )
        != 1
        or failed_regression.get("blindHumanAudioAccessed") is not False
    ):
        raise ValueError("baxy_soft_ctc_full_evidence_invalid")
    return float(selected["threshold"])


def evaluate(
    *,
    development_report_path: Path,
    failed_strength_regression_path: Path,
    fusion_manifest_path: Path,
    ctc_manifest_path: Path,
    cuda_parity_report_path: Path,
    teacher_directory: Path,
    prior_holdout_report_path: Path,
    prior_stage1_scan_path: Path,
    corpus_manifest_path: Path,
    stage1_model_path: Path,
    ffmpeg_path: Path,
    stt_directory: Path,
    sherpa_site_packages_path: Path | None,
    output_path: Path,
    cuda_batch_size: int,
    record_batch_size: int,
    stt_batch_size: int,
    stage1_workers: int,
) -> dict[str, object]:
    development_report_path = development_report_path.resolve(strict=True)
    failed_strength_regression_path = failed_strength_regression_path.resolve(
        strict=True
    )
    development = _V2._PRODUCT.read_object(development_report_path)
    failed_regression = _V2._PRODUCT.read_object(failed_strength_regression_path)
    threshold = validate_development_binding(development, failed_regression)

    def soft_guard(probabilities: object, wake: object) -> bool:
        return _V8.soft_local_ctc_margin(probabilities, wake) >= threshold

    report = _V2.evaluate(
        fusion_manifest_path=fusion_manifest_path,
        ctc_manifest_path=ctc_manifest_path,
        cuda_parity_report_path=cuda_parity_report_path,
        teacher_directory=teacher_directory,
        prior_holdout_report_path=prior_holdout_report_path,
        prior_stage1_scan_path=prior_stage1_scan_path,
        corpus_manifest_path=corpus_manifest_path,
        stage1_model_path=stage1_model_path,
        ffmpeg_path=ffmpeg_path,
        stt_directory=stt_directory,
        sherpa_site_packages_path=sherpa_site_packages_path,
        output_path=output_path,
        cuda_batch_size=cuda_batch_size,
        record_batch_size=record_batch_size,
        stt_batch_size=stt_batch_size,
        stage1_workers=stage1_workers,
        secondary_view_guard=soft_guard,
        secondary_guard_contract={
            "name": "soft_local_ctc_target_minus_confusable",
            "threshold": threshold,
            "minimumAlignmentFrames": _V8.MINIMUM_ALIGNMENT_FRAMES,
            "maximumAlignmentFrames": _V8.MAXIMUM_ALIGNMENT_FRAMES,
            "selectedOnOpenedHumanDevelopment": True,
        },
        contextual_hotword_score=4.0,
        additional_checkpoint_identities={
            "softCtcDevelopmentReportSha256": _V2._PRODUCT.sha256(
                development_report_path
            ),
            "softCtcThreshold": str(threshold),
            "failedStrengthRegressionSha256": _V2._PRODUCT.sha256(
                failed_strength_regression_path
            ),
        },
    )
    report["schema"] = "baxy.soft-ctc-alignment-full-negative-regression.v5"
    report["measuredAtUtc"] = datetime.now(timezone.utc).isoformat()
    report["scope"] = "previously_opened_100h_full_rescan_preregistered_soft_ctc_guard"
    report["contract"].update(
        {
            "softCtcThresholdSelectedBeforeThisRegression": True,
            "softCtcDevelopmentGatePassed": True,
            "softCtcRequiresSameFusionPassingView": True,
        }
    )
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--development-report", type=Path, required=True)
    parser.add_argument("--failed-strength-regression", type=Path, required=True)
    parser.add_argument("--fusion-manifest", type=Path, required=True)
    parser.add_argument("--ctc-verifier-manifest", type=Path, required=True)
    parser.add_argument("--cuda-parity-report", type=Path, required=True)
    parser.add_argument("--teacher-directory", type=Path, required=True)
    parser.add_argument("--prior-holdout-report", type=Path, required=True)
    parser.add_argument("--prior-stage1-scan", type=Path, required=True)
    parser.add_argument("--corpus-manifest", type=Path, required=True)
    parser.add_argument("--stage1-model", type=Path, required=True)
    parser.add_argument("--ffmpeg", type=Path, required=True)
    parser.add_argument("--stt-directory", type=Path, required=True)
    parser.add_argument("--sherpa-site-packages", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cuda-batch-size", type=int, default=32)
    parser.add_argument("--record-batch-size", type=int, default=64)
    parser.add_argument("--stt-batch-size", type=int, default=8)
    parser.add_argument("--stage1-workers", type=int, default=16)
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    report = evaluate(
        development_report_path=arguments.development_report,
        failed_strength_regression_path=arguments.failed_strength_regression,
        fusion_manifest_path=arguments.fusion_manifest,
        ctc_manifest_path=arguments.ctc_verifier_manifest,
        cuda_parity_report_path=arguments.cuda_parity_report,
        teacher_directory=arguments.teacher_directory,
        prior_holdout_report_path=arguments.prior_holdout_report,
        prior_stage1_scan_path=arguments.prior_stage1_scan,
        corpus_manifest_path=arguments.corpus_manifest,
        stage1_model_path=arguments.stage1_model,
        ffmpeg_path=arguments.ffmpeg,
        stt_directory=arguments.stt_directory,
        sherpa_site_packages_path=arguments.sherpa_site_packages,
        output_path=arguments.output,
        cuda_batch_size=arguments.cuda_batch_size,
        record_batch_size=arguments.record_batch_size,
        stt_batch_size=arguments.stt_batch_size,
        stage1_workers=arguments.stage1_workers,
    )
    print(
        json.dumps(
            {"passed": report["regressionPassed"], "metrics": report["metrics"]},
            sort_keys=True,
        )
    )
    return 0 if report["regressionPassed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
