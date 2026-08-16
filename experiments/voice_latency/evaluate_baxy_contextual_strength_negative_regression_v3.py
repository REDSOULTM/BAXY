"""Re-run the opened 100-hour regression at the selected contextual score.

The v6 development sweep selected score 4.0 as the lowest integer bias that
retained all four opened human positives.  This wrapper binds that selection to
the exact v2 acoustic rescan, CPU parity belt, and privacy-preserving aggregate
report.  It remains development regression evidence, never a fresh FAR claim.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path


SELECTED_HOTWORD_SCORE = 4.0


def load_component(filename: str, name: str) -> object:
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"baxy_contextual_strength_negative_invalid:{filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_V2 = load_component(
    "evaluate_baxy_contextual_fusion_negative_regression_v2.py",
    "_baxy_contextual_strength_negative_v2",
)
_PRODUCT = _V2._PRODUCT


def bind_report(
    inner: dict[str, object],
    *,
    inner_report_sha256: str,
    strength_report_sha256: str,
) -> dict[str, object]:
    if inner.get("schema") != "baxy.contextual-hyperspotter-fusion-negative-regression.v2":
        raise ValueError("baxy_contextual_strength_negative_inner_invalid")
    report = dict(inner)
    report["schema"] = "baxy.contextual-strength-negative-regression.v3"
    report["measuredAtUtc"] = datetime.now(timezone.utc).isoformat()
    report["scope"] = "previously_opened_100h_selected_contextual_strength_regression"
    report["sources"] = {
        **dict(inner.get("sources") or {}),
        "innerV2ReportSha256": inner_report_sha256,
        "hotwordStrengthDevelopmentSha256": strength_report_sha256,
    }
    report["contract"] = {
        **dict(inner.get("contract") or {}),
        "contextualHotwordScore": SELECTED_HOTWORD_SCORE,
        "contextualScoreSelectionRule": (
            "lowest_integer_score_with_4_of_4_opened_human_positive_and_0_of_8_matched_negative"
        ),
        "scoreSelectedBeforeThisRegression": True,
    }
    return report


def evaluate(
    *,
    hotword_strength_development_path: Path,
    output_path: Path,
    **inner_arguments: object,
) -> dict[str, object]:
    if output_path.exists():
        raise ValueError("baxy_contextual_strength_negative_output_exists")
    strength_path = hotword_strength_development_path.resolve(strict=True)
    strength = _PRODUCT.read_object(strength_path)
    if (
        strength.get("schema")
        != "baxy.contextual-hotword-strength-development.v6"
        or strength.get("lowestCompleteRecallScore") != SELECTED_HOTWORD_SCORE
        or strength.get("scoreSummaries", {}).get("4.0", {}).get("positiveHits")
        != 4
        or strength.get("scoreSummaries", {}).get("4.0", {}).get("falseHits")
        != 0
    ):
        raise ValueError("baxy_contextual_strength_negative_selection_invalid")

    output_path = output_path.resolve()
    inner_path = output_path.with_suffix(output_path.suffix + ".inner-v2.json")
    if inner_path.exists():
        inner = _PRODUCT.read_object(inner_path)
    else:
        original_score = _V2._V4.CONTEXTUAL_HOTWORD_SCORE
        try:
            _V2._V4.CONTEXTUAL_HOTWORD_SCORE = SELECTED_HOTWORD_SCORE
            inner = _V2.evaluate(output_path=inner_path, **inner_arguments)
        finally:
            _V2._V4.CONTEXTUAL_HOTWORD_SCORE = original_score

    report = bind_report(
        inner,
        inner_report_sha256=_PRODUCT.sha256(inner_path),
        strength_report_sha256=_PRODUCT.sha256(strength_path),
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
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
    parser.add_argument("--hotword-strength-development", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cuda-batch-size", type=int, default=32)
    parser.add_argument("--record-batch-size", type=int, default=64)
    parser.add_argument("--stt-batch-size", type=int, default=8)
    parser.add_argument("--stage1-workers", type=int, default=16)
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    report = evaluate(
        hotword_strength_development_path=arguments.hotword_strength_development,
        output_path=arguments.output,
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
        cuda_batch_size=arguments.cuda_batch_size,
        record_batch_size=arguments.record_batch_size,
        stt_batch_size=arguments.stt_batch_size,
        stage1_workers=arguments.stage1_workers,
    )
    print(json.dumps(report["metrics"], sort_keys=True))
    return 0 if report["regressionPassed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
