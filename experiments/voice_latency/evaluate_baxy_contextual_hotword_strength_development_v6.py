"""Sweep bounded Parakeet hotword strength on opened human development data.

The v5 experiment showed that cross-scope consensus loses valid speakers.  This
follow-up varies only the contextual decoder bias while keeping the acoustic
policy, aliases, captures, model assets, and lexical boundary fixed.  Temporary
per-score reports retain no transcript or filename; the final report contains
aggregate counts only.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import tempfile


HOTWORD_SCORES = (1.0, 2.0, 3.0, 4.0)


def load_component(filename: str, name: str) -> object:
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"baxy_contextual_strength_component_invalid:{filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_V5 = load_component(
    "evaluate_baxy_contextual_consensus_development_v5.py",
    "_baxy_contextual_strength_v5",
)
_PRODUCT = _V5._PRODUCT


def retain_complete_recall(
    score_summaries: dict[str, dict[str, object]],
) -> list[float]:
    return [
        float(score)
        for score, summary in score_summaries.items()
        if summary.get("positiveHits") == summary.get("positiveTotal") == 4
        and summary.get("falseHits") == 0
    ]


def evaluate(
    *,
    expanded_corpus_manifest_path: Path,
    stage1_model_path: Path,
    ctc_manifest_path: Path,
    fusion_manifest_path: Path,
    stt_directory: Path,
    ffmpeg_path: Path,
    prior_contextual_development_path: Path,
    failed_negative_regression_path: Path,
    prior_consensus_development_path: Path,
    output_path: Path,
    stt_batch_size: int,
) -> dict[str, object]:
    if output_path.exists() or stt_batch_size < 1:
        raise ValueError("baxy_contextual_strength_schedule_invalid")
    prior_consensus_development_path = prior_consensus_development_path.resolve(
        strict=True
    )
    prior = _PRODUCT.read_object(prior_consensus_development_path)
    if (
        prior.get("schema") != "baxy.contextual-consensus-development.v5"
        or prior.get("policy", {}).get("contextualHotwordScore") != 5.0
        or prior.get("policySummaries", {}).get("currentFullHot", {}).get(
            "positiveHits"
        )
        != 4
    ):
        raise ValueError("baxy_contextual_strength_prior_invalid")

    score_summaries: dict[str, dict[str, object]] = {
        "5.0": prior["policySummaries"]["currentFullHot"]
    }
    original_score = _V5._V4.CONTEXTUAL_HOTWORD_SCORE
    try:
        with tempfile.TemporaryDirectory(prefix="baxy-contextual-strength-") as temp:
            temp_root = Path(temp)
            for score in HOTWORD_SCORES:
                _V5._V4.CONTEXTUAL_HOTWORD_SCORE = score
                one = _V5.evaluate(
                    expanded_corpus_manifest_path=expanded_corpus_manifest_path,
                    stage1_model_path=stage1_model_path,
                    ctc_manifest_path=ctc_manifest_path,
                    fusion_manifest_path=fusion_manifest_path,
                    stt_directory=stt_directory,
                    ffmpeg_path=ffmpeg_path,
                    prior_contextual_development_path=(
                        prior_contextual_development_path
                    ),
                    failed_negative_regression_path=failed_negative_regression_path,
                    output_path=temp_root / f"score-{score:.1f}.json",
                    stt_batch_size=stt_batch_size,
                )
                score_summaries[f"{score:.1f}"] = one["policySummaries"][
                    "currentFullHot"
                ]
                print(
                    "BAXY_CONTEXTUAL_STRENGTH|"
                    f"score={score:.1f}|"
                    f"positive={score_summaries[f'{score:.1f}']['positiveHits']}/4|"
                    f"false={score_summaries[f'{score:.1f}']['falseHits']}/8",
                    flush=True,
                )
    finally:
        _V5._V4.CONTEXTUAL_HOTWORD_SCORE = original_score

    complete_recall = sorted(retain_complete_recall(score_summaries))
    report: dict[str, object] = {
        "schema": "baxy.contextual-hotword-strength-development.v6",
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "scope": "opened_human_development_hotword_strength_selection",
        "sources": {
            "priorConsensusDevelopmentSha256": _PRODUCT.sha256(
                prior_consensus_development_path
            ),
            "failedNegativeRegressionSha256": _PRODUCT.sha256(
                failed_negative_regression_path
            ),
        },
        "scoreSummaries": dict(
            sorted(score_summaries.items(), key=lambda item: float(item[0]))
        ),
        "completeRecallScores": complete_recall,
        "lowestCompleteRecallScore": complete_recall[0] if complete_recall else None,
        "selectionRule": "lowest_score_with_4_of_4_positive_and_0_of_8_matched_negative",
        "expandedHumanDevelopmentAudioAccessed": True,
        "blindHumanAudioAccessed": False,
        "audioTranscriptsOrFilenamesRetained": False,
        "candidateFrozen": False,
        "productOperatingPoint": False,
        "effectsExecuted": 0,
    }
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expanded-corpus-manifest", type=Path, required=True)
    parser.add_argument("--stage1-model", type=Path, required=True)
    parser.add_argument("--ctc-verifier-manifest", type=Path, required=True)
    parser.add_argument("--fusion-manifest", type=Path, required=True)
    parser.add_argument("--stt-directory", type=Path, required=True)
    parser.add_argument("--ffmpeg", type=Path, required=True)
    parser.add_argument("--prior-contextual-development", type=Path, required=True)
    parser.add_argument("--failed-negative-regression", type=Path, required=True)
    parser.add_argument("--prior-consensus-development", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--stt-batch-size", type=int, default=8)
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    report = evaluate(
        expanded_corpus_manifest_path=arguments.expanded_corpus_manifest,
        stage1_model_path=arguments.stage1_model,
        ctc_manifest_path=arguments.ctc_verifier_manifest,
        fusion_manifest_path=arguments.fusion_manifest,
        stt_directory=arguments.stt_directory,
        ffmpeg_path=arguments.ffmpeg,
        prior_contextual_development_path=arguments.prior_contextual_development,
        failed_negative_regression_path=arguments.failed_negative_regression,
        prior_consensus_development_path=arguments.prior_consensus_development,
        output_path=arguments.output,
        stt_batch_size=arguments.stt_batch_size,
    )
    print(json.dumps(report["scoreSummaries"], sort_keys=True))
    return 0 if report["completeRecallScores"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
