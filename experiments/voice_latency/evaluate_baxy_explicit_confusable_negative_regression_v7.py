"""Run the opened 100 h regression with an exact CTC-confusable veto."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path

import numpy as np


def load_component(filename: str, name: str) -> object:
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"baxy_explicit_confusable_component_invalid:{filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_V2 = load_component(
    "evaluate_baxy_contextual_fusion_negative_regression_v2.py",
    "_baxy_explicit_confusable_v2",
)
_ENSEMBLE = load_component(
    "audit_wake_ssl_ctc_ensemble_development_v1.py",
    "_baxy_explicit_confusable_ensemble",
)


def validate_ensemble_evidence(report: object) -> dict[str, int]:
    if not isinstance(report, dict):
        raise ValueError("baxy_explicit_confusable_evidence_invalid")
    metrics = report.get("metrics")
    records = report.get("records")
    if (
        report.get("schema") != "baxy.wake-ssl-ctc-ensemble-development.v1"
        or not isinstance(metrics, dict)
        or metrics.get("positive_accepted") != 18
        or metrics.get("positive_total") != 18
        or metrics.get("negative_false_accepts") != 0
        or metrics.get("negative_total") != 12
        or metrics.get("development_gate_passed") is not True
        or not isinstance(records, list)
        or len(records) != 30
    ):
        raise ValueError("baxy_explicit_confusable_evidence_invalid")
    positives = [record for record in records if record.get("label") == "positive"]
    negatives = [record for record in records if record.get("label") != "positive"]
    positive_confusables = sum(
        bool(record.get("ctc_greedy_exact_confusable")) for record in positives
    )
    negative_confusables = sum(
        bool(record.get("ctc_greedy_exact_confusable")) for record in negatives
    )
    if (
        len(positives) != 18
        or len(negatives) != 12
        or positive_confusables != 0
        or negative_confusables != 3
    ):
        raise ValueError("baxy_explicit_confusable_evidence_invalid")
    return {
        "positiveTotal": len(positives),
        "positiveExplicitConfusables": positive_confusables,
        "negativeTotal": len(negatives),
        "negativeExplicitConfusables": negative_confusables,
    }


def explicit_confusable_guard(probabilities: object, wake: object) -> bool:
    values = np.asarray(probabilities, dtype=np.float64)
    if (
        values.ndim != 2
        or values.shape[1] != len(wake.CATEGORY_NAMES)
        or not np.isfinite(values).all()
    ):
        raise ValueError("baxy_explicit_confusable_probabilities_invalid")
    collapsed = wake._collapse_path(np.argmax(values, axis=1))
    if _ENSEMBLE.contains_sequence(collapsed, wake.TARGET_IDS):
        return True
    return not _ENSEMBLE.contains_sequence(collapsed, wake.CONFUSABLE_IDS)


def evaluate(
    *,
    ensemble_report_path: Path,
    screening_cache_path: Path,
    expected_sentinel_candidates: int,
    output_path: Path,
    **inner_arguments: object,
) -> dict[str, object]:
    ensemble_path = ensemble_report_path.resolve(strict=True)
    evidence = validate_ensemble_evidence(_V2._PRODUCT.read_object(ensemble_path))
    if output_path.exists():
        raise ValueError("baxy_explicit_confusable_output_exists")

    report = _V2.evaluate(
        output_path=output_path,
        screening_cache_path=screening_cache_path,
        expected_sentinel_candidates=expected_sentinel_candidates,
        secondary_view_guard=explicit_confusable_guard,
        secondary_guard_contract={
            "name": "exact_greedy_ctc_confusable_veto",
            "targetSequenceHasAuthority": True,
            "confusableSequenceVeto": True,
            "requiresSameExactCpuFusionView": True,
            "selectedOnOpenedHumanDevelopment": True,
            **evidence,
        },
        contextual_hotword_score=5.0,
        contextual_view_policy="same_exact_fusion_view",
        additional_checkpoint_identities={
            "explicitConfusableEvidenceSha256": _V2._PRODUCT.sha256(ensemble_path),
            "explicitConfusableGuardVersion": "v1",
        },
        **inner_arguments,
    )
    report["schema"] = "baxy.explicit-confusable-same-view-negative-regression.v7"
    report["measuredAtUtc"] = datetime.now(timezone.utc).isoformat()
    report["scope"] = (
        "previously_opened_100h_exact_confusable_same_view_regression"
    )
    report["contract"].update(
        {
            "explicitConfusableEvidenceSha256": _V2._PRODUCT.sha256(
                ensemble_path
            ),
            "explicitConfusableHumanDevelopmentGatePassed": True,
            "explicitConfusableSelectionBeforeThisLongRegression": True,
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
    parser.add_argument("--ensemble-report", type=Path, required=True)
    parser.add_argument("--screening-cache", type=Path, required=True)
    parser.add_argument("--expected-sentinel-candidates", type=int, required=True)
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
        ensemble_report_path=arguments.ensemble_report,
        screening_cache_path=arguments.screening_cache,
        expected_sentinel_candidates=arguments.expected_sentinel_candidates,
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
