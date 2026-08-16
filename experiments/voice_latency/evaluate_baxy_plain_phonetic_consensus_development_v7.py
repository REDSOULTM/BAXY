"""Select a soft plain-ASR confirmation on opened human development audio.

The contextual decoder must still emit an exact measured BAXY spelling.  The
independent plain decoder may confirm a token at a bounded character distance,
which tests whether the fourth positive lost by exact dual decoding can be
recovered without accepting the eight matched negatives.  No transcript or
filename is retained in the report.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import re
import unicodedata


_WORD_RE = re.compile(r"[^\W_]+", re.UNICODE)
_PLAIN_TARGETS = ("baxy", "baxi", "basi", "bakse")
_TARGET_PHONETIC_KEY = "baksi"


def load_component(filename: str, name: str) -> object:
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(
            f"baxy_plain_phonetic_consensus_component_invalid:{filename}"
        )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_V5 = load_component(
    "evaluate_baxy_contextual_consensus_development_v5.py",
    "_baxy_plain_phonetic_consensus_v5",
)


def normalize_token(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return "".join(character for character in decomposed if not unicodedata.combining(character))


def spanish_phonetic_key(value: str) -> str:
    """Return a small deterministic grapheme key for measured Spanish variants."""

    token = normalize_token(value)
    result: list[str] = []
    index = 0
    while index < len(token):
        pair = token[index : index + 2]
        if pair == "qu":
            result.append("k")
            index += 2
            continue
        character = token[index]
        following = token[index + 1] if index + 1 < len(token) else ""
        if character == "x":
            result.append("ks")
        elif character == "c":
            result.append("s" if following in {"e", "i"} else "k")
        elif character in {"q", "k"}:
            result.append("k")
        elif character in {"z", "s"}:
            result.append("s")
        elif character in {"v", "b"}:
            result.append("b")
        elif character == "y":
            result.append("i")
        elif character == "h":
            pass
        else:
            result.append(character)
        index += 1
    return "".join(result)


def levenshtein_distance(left: str, right: str) -> int:
    """Return the exact unit-cost edit distance using O(min(n, m)) memory."""

    if len(left) < len(right):
        left, right = right, left
    previous = list(range(len(right) + 1))
    for left_index, left_character in enumerate(left, start=1):
        current = [left_index]
        for right_index, right_character in enumerate(right, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[right_index] + 1,
                    previous[right_index - 1]
                    + (left_character != right_character),
                )
            )
        previous = current
    return previous[-1]


def minimum_plain_wake_distance(transcript: str) -> int | None:
    words = [normalize_token(word) for word in _WORD_RE.findall(transcript)]
    spans = [
        "".join(words[start : start + width])
        for start in range(len(words))
        for width in (1, 2)
        if start + width <= len(words)
    ]
    keys = [spanish_phonetic_key(span) for span in spans if 3 <= len(span) <= 12]
    if not keys:
        return None
    return min(levenshtein_distance(key, _TARGET_PHONETIC_KEY) for key in keys)


def has_plain_near_wake_evidence(
    transcript: str, wake: object, *, maximum_distance: int = 1
) -> bool:
    if _V5._V4.has_contextual_wake_evidence(transcript, wake):
        return True
    distance = minimum_plain_wake_distance(transcript)
    return distance is not None and distance <= maximum_distance


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
    maximum_distance: int,
) -> dict[str, object]:
    if maximum_distance < 0 or maximum_distance > 3:
        raise ValueError("baxy_plain_phonetic_consensus_distance_invalid")
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
        or failed_strength.get("contract", {}).get("contextualHotwordScore")
        != 4.0
    ):
        raise ValueError("baxy_plain_phonetic_consensus_evidence_invalid")

    def plain_predicate(transcript: str, wake: object) -> bool:
        return has_plain_near_wake_evidence(
            transcript, wake, maximum_distance=maximum_distance
        )

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
        plain_evidence_predicate=plain_predicate,
        hot_evidence_predicate=_V5._V4.has_contextual_wake_evidence,
    )
    report["schema"] = "baxy.plain-phonetic-consensus-development.v7"
    report["measuredAtUtc"] = datetime.now(timezone.utc).isoformat()
    report["scope"] = "opened_human_development_plain_phonetic_consensus_selection"
    report["sources"]["failedStrengthRegressionSha256"] = _V5._PRODUCT.sha256(
        failed_strength_regression_path
    )
    report["policy"].update(
        {
            "plainDecoderEvidence": "known_exact_alias_or_minimum_span_phonetic_distance",
            "plainDecoderTargets": list(_PLAIN_TARGETS),
            "plainDecoderTargetPhoneticKey": _TARGET_PHONETIC_KEY,
            "plainDecoderMaximumPhoneticDistance": maximum_distance,
            "hotDecoderEvidence": "exact_measured_contextual_wake_term",
            "selectionPerformedBeforeAnyNewLongNegativeRegression": True,
        }
    )
    report["developmentEligiblePolicies"] = [
        name
        for name, summary in report["policySummaries"].items()
        if summary["positiveHits"] == 4 and summary["falseHits"] == 0
    ]
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
    parser.add_argument("--maximum-distance", type=int, choices=(0, 1, 2, 3), default=1)
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
        maximum_distance=arguments.maximum_distance,
    )
    print(json.dumps(report["policySummaries"], sort_keys=True))
    return 0 if report["developmentEligiblePolicies"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
