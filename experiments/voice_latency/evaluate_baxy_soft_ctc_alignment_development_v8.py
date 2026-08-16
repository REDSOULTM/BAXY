"""Select a local soft-CTC alignment guard on opened development audio.

The score uses a bounded local CTC Viterbi path for BAXY pronunciations and
subtracts the best path for measured confusable pronunciations.  It therefore
tests temporal phoneme order without requiring every target phone to win the
frame-wise argmax.  Only aggregate policy counts are retained.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
import math
from pathlib import Path

import numpy as np


MINIMUM_ALIGNMENT_FRAMES = 8
MAXIMUM_ALIGNMENT_FRAMES = 40
MARGIN_THRESHOLDS = tuple(value / 4.0 for value in range(-16, 33))


def load_component(filename: str, name: str) -> object:
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"baxy_soft_ctc_component_invalid:{filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_V5 = load_component(
    "evaluate_baxy_contextual_consensus_development_v5.py",
    "_baxy_soft_ctc_consensus_v5",
)


def best_local_ctc_viterbi_score(
    log_probabilities: np.ndarray,
    sequence: tuple[int, ...],
    *,
    blank_id: int,
    minimum_frames: int = MINIMUM_ALIGNMENT_FRAMES,
    maximum_frames: int = MAXIMUM_ALIGNMENT_FRAMES,
) -> float:
    """Return the best length-normalized local CTC Viterbi path score."""

    values = np.asarray(log_probabilities, dtype=np.float64)
    if (
        values.ndim != 2
        or values.shape[0] < 1
        or not sequence
        or minimum_frames < len(sequence)
        or maximum_frames < minimum_frames
        or blank_id < 0
        or blank_id >= values.shape[1]
        or any(token < 0 or token >= values.shape[1] for token in sequence)
        or not np.isfinite(values).all()
    ):
        raise ValueError("baxy_soft_ctc_alignment_input_invalid")

    states = [blank_id]
    for token in sequence:
        states.extend((int(token), blank_id))
    state_ids = np.asarray(states, dtype=np.int64)
    allow_skip = np.asarray(
        [
            state > 1
            and token != blank_id
            and token != states[state - 2]
            for state, token in enumerate(states)
        ],
        dtype=np.bool_,
    )
    state_count = len(states)
    previous = np.full(
        (maximum_frames + 1, state_count), -math.inf, dtype=np.float64
    )
    best = -math.inf
    for frame in range(values.shape[0]):
        current = np.full_like(previous, -math.inf)
        prior = previous[:-1]
        total = prior.copy()
        total[:, 1:] = np.maximum(total[:, 1:], prior[:, :-1])
        skip_states = np.flatnonzero(allow_skip)
        if len(skip_states):
            total[:, skip_states] = np.maximum(
                total[:, skip_states], prior[:, skip_states - 2]
            )
        current[1:] = total + values[frame, state_ids][None, :]
        current[1, 1] = values[frame, state_ids[1]]
        completed = np.maximum(
            current[minimum_frames:, -1], current[minimum_frames:, -2]
        )
        lengths = np.arange(
            minimum_frames, maximum_frames + 1, dtype=np.float64
        )
        best = max(best, float(np.max(completed / lengths)))
        previous = current
    if not math.isfinite(best):
        raise ValueError("baxy_soft_ctc_alignment_missing")
    return best


def soft_local_ctc_margin(probabilities: np.ndarray, wake: object) -> float:
    values = np.asarray(probabilities, dtype=np.float64)
    if (
        values.ndim != 2
        or values.shape[1] != len(wake.CATEGORY_NAMES)
        or not np.isfinite(values).all()
    ):
        raise ValueError("baxy_soft_ctc_probabilities_invalid")
    log_probabilities = np.log(np.maximum(values, 1e-12))
    target = max(
        best_local_ctc_viterbi_score(
            log_probabilities, tuple(sequence), blank_id=wake.BLANK_ID
        )
        for sequence in wake.TARGET_IDS
    )
    confusable = max(
        best_local_ctc_viterbi_score(
            log_probabilities, tuple(sequence), blank_id=wake.BLANK_ID
        )
        for sequence in wake.CONFUSABLE_IDS
    )
    margin = target - confusable
    if not math.isfinite(margin):
        raise ValueError("baxy_soft_ctc_margin_invalid")
    return margin


def fixed_view_observer(
    margins: dict[int, float],
    probabilities_by_view: dict[int, np.ndarray],
    wake: object,
) -> dict[str, float] | None:
    if not probabilities_by_view:
        return None
    scores = {
        start: soft_local_ctc_margin(probabilities, wake)
        for start, probabilities in probabilities_by_view.items()
    }
    fusion_passing = [
        score for start, score in scores.items() if margins.get(start, -math.inf) >= 0.0
    ]
    return {
        "maximumSoftLocalCtcMargin": max(scores.values()),
        "maximumFusionPassingSoftLocalCtcMargin": (
            max(fusion_passing) if fusion_passing else -math.inf
        ),
    }


def threshold_name(prefix: str, threshold: float) -> str:
    sign = "p" if threshold >= 0.0 else "m"
    magnitude = int(round(abs(threshold) * 100.0))
    return f"{prefix}_{sign}{magnitude:04d}"


def additional_policy_factory(
    *,
    established: bool,
    fixed: bool,
    full_hot: bool,
    observation: object,
    base_signals: object = None,
) -> dict[str, bool]:
    del base_signals
    score = None
    fusion_passing_score = None
    if isinstance(observation, dict):
        candidate = observation.get("maximumSoftLocalCtcMargin")
        if isinstance(candidate, (int, float)) and math.isfinite(float(candidate)):
            score = float(candidate)
        fusion_candidate = observation.get("maximumFusionPassingSoftLocalCtcMargin")
        if isinstance(fusion_candidate, (int, float)) and math.isfinite(
            float(fusion_candidate)
        ):
            fusion_passing_score = float(fusion_candidate)
    policies: dict[str, bool] = {}
    for threshold in MARGIN_THRESHOLDS:
        local = score is not None and score >= threshold
        same_view_local = (
            fusion_passing_score is not None and fusion_passing_score >= threshold
        )
        policies[threshold_name("softLocalOnly", threshold)] = local
        policies[threshold_name("guardedSoftLocal", threshold)] = established or (
            fixed and full_hot and same_view_local
        )
    return policies


def select_threshold(report: dict[str, object]) -> dict[str, object] | None:
    summaries = report["policySummaries"]
    eligible = []
    for threshold in MARGIN_THRESHOLDS:
        local = summaries[threshold_name("softLocalOnly", threshold)]
        guarded = summaries[threshold_name("guardedSoftLocal", threshold)]
        if (
            local["positiveHits"] == 4
            and local["falseHits"] == 0
            and guarded["positiveHits"] == 4
            and guarded["falseHits"] == 0
        ):
            eligible.append(threshold)
    if not eligible:
        return None
    selected = max(eligible)
    return {
        "rule": "maximum_grid_threshold_with_4_of_4_positive_and_0_of_8_negative_for_local_and_guarded_policies",
        "threshold": selected,
        "localPolicy": threshold_name("softLocalOnly", selected),
        "guardedPolicy": threshold_name("guardedSoftLocal", selected),
    }


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
    failed_strength_regression_path: Path,
    output_path: Path,
    stt_batch_size: int,
) -> dict[str, object]:
    failed_strength_regression_path = failed_strength_regression_path.resolve(
        strict=True
    )
    failed_strength = _V5._PRODUCT.read_object(failed_strength_regression_path)
    if (
        failed_strength.get("schema")
        != "baxy.contextual-strength-negative-regression.v3"
        or failed_strength.get("regressionPassed") is not False
        or failed_strength.get("metrics", {}).get(
            "guardedNegativeFalseActivations"
        )
        != 1
    ):
        raise ValueError("baxy_soft_ctc_evidence_invalid")

    report = _V5.evaluate(
        expanded_corpus_manifest_path=expanded_corpus_manifest_path,
        stage1_model_path=stage1_model_path,
        ctc_manifest_path=ctc_manifest_path,
        fusion_manifest_path=fusion_manifest_path,
        stt_directory=stt_directory,
        ffmpeg_path=ffmpeg_path,
        prior_contextual_development_path=prior_contextual_development_path,
        failed_negative_regression_path=failed_negative_regression_path,
        output_path=output_path,
        stt_batch_size=stt_batch_size,
        fixed_view_observer=fixed_view_observer,
        additional_policy_factory=additional_policy_factory,
        contextual_hotword_score=4.0,
    )
    selected = select_threshold(report)
    report["schema"] = "baxy.soft-ctc-alignment-development.v8"
    report["measuredAtUtc"] = datetime.now(timezone.utc).isoformat()
    report["scope"] = "opened_human_development_soft_local_ctc_selection"
    report["sources"]["failedStrengthRegressionSha256"] = _V5._PRODUCT.sha256(
        failed_strength_regression_path
    )
    report["policy"].update(
        {
            "softCtcAlignment": "bounded_local_length_normalized_viterbi_target_minus_confusable",
            "guardRequiresSameFusionPassingView": True,
            "minimumAlignmentFrames": MINIMUM_ALIGNMENT_FRAMES,
            "maximumAlignmentFrames": MAXIMUM_ALIGNMENT_FRAMES,
            "thresholdGrid": list(MARGIN_THRESHOLDS),
            "selectionPerformedBeforeAnyNewLongNegativeRegression": True,
        }
    )
    report["selectedSoftCtcPolicy"] = selected
    report["softCtcDevelopmentGatePassed"] = selected is not None
    report["developmentEligiblePolicies"] = (
        [selected["guardedPolicy"]] if selected is not None else []
    )
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
    parser.add_argument("--failed-strength-regression", type=Path, required=True)
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
        failed_strength_regression_path=arguments.failed_strength_regression,
        output_path=arguments.output,
        stt_batch_size=arguments.stt_batch_size,
    )
    print(json.dumps(report["selectedSoftCtcPolicy"], sort_keys=True))
    return 0 if report["softCtcDevelopmentGatePassed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
