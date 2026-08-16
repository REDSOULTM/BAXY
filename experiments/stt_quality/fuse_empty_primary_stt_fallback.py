"""Fuse a primary STT with a tightly bounded streaming completion fallback.

This is an effect-free selector for frozen development or blind reports. It
never invents a score:
every selected transcript and timing comes from two reports emitted by the
same frozen evaluator, contract, runtime, source partition and case set.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPORT_SCHEMA = "baxy.stt-real-audio-evaluation.v3"
FUSION_SCHEMA = "baxy.stt-bounded-completion-fallback-evaluation.v3"
FALLBACK_ENGINE = "nemotron_auto"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_report(path: Path, expected_engine: str) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(value, dict)
        or value.get("schema") != REPORT_SCHEMA
        or value.get("partition") not in {"development", "blind"}
        or value.get("engine") != expected_engine
        or value.get("effectsExecuted") != 0
    ):
        raise RuntimeError(f"stt_fusion_report_invalid:{path}")
    return value


def nearest_rank(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return round(ordered[max(0, math.ceil(percentile * len(ordered)) - 1)], 6)


def normalized_tokens(text: str) -> list[str]:
    folded = "".join(
        character
        for character in unicodedata.normalize("NFKD", text.casefold())
        if not unicodedata.combining(character)
    )
    return re.findall(r"[a-z0-9]+(?:'[a-z0-9]+)?", folded)


def use_fallback(primary_text: str, fallback_text: str) -> tuple[bool, str]:
    primary_tokens = normalized_tokens(primary_text)
    fallback_tokens = normalized_tokens(fallback_text)
    if not primary_tokens:
        return True, "primary_empty"
    additional_tokens = len(fallback_tokens) - len(primary_tokens)
    if (
        5 <= len(primary_tokens) <= 6
        and 3 <= additional_tokens <= 5
        and fallback_tokens[-len(primary_tokens) :] == primary_tokens
    ):
        return True, "bounded_primary_prefix_completed_by_streaming_fallback"
    return False, "primary_retained"


def validate_pair(primary: dict[str, Any], fallback: dict[str, Any]) -> None:
    for field in ("source", "partition", "contract", "evaluator", "runtime"):
        if primary.get(field) != fallback.get(field):
            raise RuntimeError(f"stt_fusion_report_pair_mismatch:{field}")
    primary_ids = [str(case.get("caseId")) for case in primary["cases"]]
    fallback_ids = [str(case.get("caseId")) for case in fallback["cases"]]
    if (
        primary_ids != fallback_ids
        or len(primary_ids) != len(set(primary_ids))
        or any(
            left.get("reference") != right.get("reference")
            or left.get("referenceTokens") != right.get("referenceTokens")
            for left, right in zip(primary["cases"], fallback["cases"], strict=True)
        )
    ):
        raise RuntimeError("stt_fusion_case_binding_mismatch")


def thresholds(source: str, partition: str) -> dict[str, float | int]:
    if source == "minds14":
        return {
            "expectedCases": 84 if partition == "development" else 196,
            "minimumNonemptyRate": 1.0,
            "minimumTranscriptIntentAccuracy": 0.95,
            "minimumIntentSemanticPreservation": 0.99,
            "maximumEndpointAvailabilityP95Seconds": 1.5,
            "maximumFallbackRealTimeFactorP95": 0.50,
        }
    if source == "audio_arena":
        return {
            "expectedCases": 12 if partition == "development" else 50,
            "minimumNonemptyRate": 1.0,
            "maximumCorpusWer": 0.20,
            "maximumCaseWerP95": 0.50,
            "minimumCriticalAnchorRecall": 0.99,
            "maximumEndpointAvailabilityP95Seconds": 1.5,
            "maximumFallbackRealTimeFactorP95": 0.50,
        }
    raise RuntimeError(f"stt_fusion_source_unsupported:{source}")


def fuse(
    primary: dict[str, Any], fallback: dict[str, Any], primary_engine: str
) -> dict[str, Any]:
    validate_pair(primary, fallback)
    source = str(primary["source"])
    partition = str(primary["partition"])
    fused_cases: list[dict[str, Any]] = []
    for primary_case, fallback_case in zip(
        primary["cases"], fallback["cases"], strict=True
    ):
        fallback_invoked, selection_reason = use_fallback(
            str(primary_case["productTranscript"]),
            str(fallback_case["productTranscript"]),
        )
        selected = fallback_case if fallback_invoked else primary_case
        endpoint_availability = (
            float(fallback_case["maximumChunkDecodeSeconds"])
            + float(fallback_case["finalizationLatencySeconds"])
            if fallback_invoked
            else float(primary_case["finalizationLatencySeconds"])
        )
        fused_case: dict[str, Any] = {
            "caseId": selected["caseId"],
            "selectedEngine": (FALLBACK_ENGINE if fallback_invoked else primary_engine),
            "fallbackInvoked": fallback_invoked,
            "selectionReason": selection_reason,
            "reference": selected["reference"],
            "transcript": selected["productTranscript"],
            "nonempty": selected["nonempty"],
            "referenceTokens": selected["referenceTokens"],
            "wordErrors": selected["wordErrors"],
            "wer": selected["wer"],
            "criticalAnchors": selected["criticalAnchors"],
            "criticalAnchorsPreserved": selected["criticalAnchorsPreserved"],
            "endpointAvailabilitySeconds": round(endpoint_availability, 6),
            "error": selected["error"],
        }
        for field in ("language", "intent", "intentOracle"):
            if field in selected:
                fused_case[field] = selected[field]
        fused_cases.append(fused_case)

    reference_tokens = sum(int(case["referenceTokens"]) for case in fused_cases)
    word_errors = sum(int(case["wordErrors"]) for case in fused_cases)
    anchors = sum(len(case["criticalAnchors"]) for case in fused_cases)
    preserved = sum(len(case["criticalAnchorsPreserved"]) for case in fused_cases)
    intent_cases = [case for case in fused_cases if "intentOracle" in case]
    metrics: dict[str, Any] = {
        "cases": len(fused_cases),
        "fallbackCases": sum(case["fallbackInvoked"] for case in fused_cases),
        "fallbackRate": round(
            sum(case["fallbackInvoked"] for case in fused_cases)
            / max(1, len(fused_cases)),
            6,
        ),
        "nonemptyRate": round(
            sum(bool(case["nonempty"]) for case in fused_cases)
            / max(1, len(fused_cases)),
            6,
        ),
        "decodeErrors": sum(case["error"] is not None for case in fused_cases),
        "corpusWer": round(word_errors / max(1, reference_tokens), 6),
        "caseWerP95": nearest_rank([float(case["wer"]) for case in fused_cases], 0.95),
        "criticalAnchorRecall": (
            1.0 if anchors == 0 else round(preserved / anchors, 6)
        ),
        "endpointAvailabilityP50Seconds": nearest_rank(
            [float(case["endpointAvailabilitySeconds"]) for case in fused_cases],
            0.50,
        ),
        "endpointAvailabilityP95Seconds": nearest_rank(
            [float(case["endpointAvailabilitySeconds"]) for case in fused_cases],
            0.95,
        ),
        "fallbackRealTimeFactorP95": fallback["aggregate"]["metrics"][
            "realTimeFactorP95"
        ],
    }
    if intent_cases:
        metrics.update(
            {
                "referenceIntentOracleAccuracy": round(
                    sum(
                        case["intentOracle"]["referenceCorrect"]
                        for case in intent_cases
                    )
                    / len(intent_cases),
                    6,
                ),
                "transcriptIntentAccuracy": round(
                    sum(
                        case["intentOracle"]["transcriptCorrect"]
                        for case in intent_cases
                    )
                    / len(intent_cases),
                    6,
                ),
                "intentSemanticPreservation": round(
                    sum(
                        case["intentOracle"]["semanticPreserved"]
                        for case in intent_cases
                    )
                    / len(intent_cases),
                    6,
                ),
            }
        )

    threshold = thresholds(source, partition)
    checks = {
        "expectedCases": metrics["cases"] == threshold["expectedCases"],
        "nonemptyRate": metrics["nonemptyRate"] >= threshold["minimumNonemptyRate"],
        "decodeErrors": metrics["decodeErrors"] == 0,
        "endpointAvailabilityP95": metrics["endpointAvailabilityP95Seconds"]
        <= threshold["maximumEndpointAvailabilityP95Seconds"],
        "fallbackRealTimeFactorP95": metrics["fallbackRealTimeFactorP95"]
        <= threshold["maximumFallbackRealTimeFactorP95"],
    }
    if "maximumCorpusWer" in threshold:
        checks["corpusWer"] = metrics["corpusWer"] <= threshold["maximumCorpusWer"]
        checks["caseWerP95"] = metrics["caseWerP95"] <= threshold["maximumCaseWerP95"]
        checks["criticalAnchorRecall"] = (
            metrics["criticalAnchorRecall"] >= threshold["minimumCriticalAnchorRecall"]
        )
    if "minimumTranscriptIntentAccuracy" in threshold:
        checks["transcriptIntentAccuracy"] = (
            metrics["transcriptIntentAccuracy"]
            >= threshold["minimumTranscriptIntentAccuracy"]
        )
        checks["intentSemanticPreservation"] = (
            metrics["intentSemanticPreservation"]
            >= threshold["minimumIntentSemanticPreservation"]
        )
    return {
        "schema": FUSION_SCHEMA,
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "partition": partition,
        "status": "passed" if all(checks.values()) else "failed",
        "policy": {
            "primary": primary_engine,
            "fallback": FALLBACK_ENGINE,
            "fallbackCondition": (
                "primary is empty, or a five-to-six-token primary is the exact "
                "suffix of a streaming transcript with three-to-five preceding "
                "tokens"
            ),
            "parallelStreamingRequired": True,
            "endpointAvailabilityMeasurement": (
                "primary finalization, or fallback maximum measured chunk decode "
                "plus fallback flush when primary is empty"
            ),
            "physicalEndpointLatencyStillRequired": True,
        },
        "inputs": {
            "primary": primary["evaluator"] | {"reportStatus": primary["status"]},
            "fallback": fallback["evaluator"] | {"reportStatus": fallback["status"]},
            "contract": primary["contract"],
            "runtime": primary["runtime"],
        },
        "aggregate": {"metrics": metrics, "threshold": threshold, "checks": checks},
        "cases": fused_cases,
        "effectsExecuted": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--primary-report", type=Path, required=True)
    parser.add_argument(
        "--primary-engine",
        choices=("product_parakeet", "parakeet_greedy"),
        required=True,
    )
    parser.add_argument("--fallback-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    if arguments.output.exists():
        raise RuntimeError(f"stt_fusion_output_exists:{arguments.output}")
    primary_path = arguments.primary_report.resolve(strict=True)
    fallback_path = arguments.fallback_report.resolve(strict=True)
    primary = read_report(primary_path, arguments.primary_engine)
    fallback = read_report(fallback_path, FALLBACK_ENGINE)
    result = fuse(primary, fallback, arguments.primary_engine)
    result["inputs"]["primary"].update(
        {"reportPath": primary_path.as_posix(), "reportSha256": sha256(primary_path)}
    )
    result["inputs"]["fallback"].update(
        {"reportPath": fallback_path.as_posix(), "reportSha256": sha256(fallback_path)}
    )
    result["fusionEvaluator"] = {
        "path": Path(__file__).resolve().as_posix(),
        "sha256": sha256(Path(__file__).resolve()),
    }
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "output": str(arguments.output),
                "status": result["status"],
                "source": result["source"],
                "sha256": sha256(arguments.output),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
