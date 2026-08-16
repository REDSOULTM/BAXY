"""Promote a frozen wake cascade from independent physical and FAR evidence.

The script never trains, copies, or changes model assets.  It only emits a
hash-bound calibration report and a new approved manifest beside the frozen
candidate after both evidence sources pass their original contracts.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from baxy_mind.wake_cascade import (  # noqa: E402
    CALIBRATION_REPORT_FILENAME,
    CALIBRATION_REPORT_SCHEMA,
    MANIFEST_SCHEMA,
    ROUTED_MANIFEST_SCHEMA,
    WakeCascadeConfig,
    load_wake_cascade_candidate_config,
)


PHYSICAL_SCHEMA = "baxy.wake-cascade-runtime-raw-development.v1"
NEGATIVE_SCHEMA = "baxy.wake-cascade-openslr-negative-regression.v1"
_SHA256 = re.compile(r"[0-9a-f]{64}")


class PromotionError(ValueError):
    """The supplied evidence cannot grant product wake authority."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as error:
        raise PromotionError("wake_cascade_promotion_json_invalid") from error
    if not isinstance(value, dict):
        raise PromotionError("wake_cascade_promotion_json_invalid")
    return value


def _object(payload: dict[str, Any], name: str) -> dict[str, Any]:
    value = payload.get(name)
    if not isinstance(value, dict):
        raise PromotionError("wake_cascade_promotion_evidence_invalid")
    return value


def _integer(payload: dict[str, Any], name: str, minimum: int = 0) -> int:
    value = payload.get(name)
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise PromotionError("wake_cascade_promotion_evidence_invalid")
    return value


def _number(payload: dict[str, Any], name: str, minimum: float = 0.0) -> float:
    value = payload.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PromotionError("wake_cascade_promotion_evidence_invalid")
    result = float(value)
    if not math.isfinite(result) or result < minimum:
        raise PromotionError("wake_cascade_promotion_evidence_invalid")
    return result


def _required_sha(value: object) -> str:
    if not isinstance(value, str):
        raise PromotionError("wake_cascade_promotion_evidence_invalid")
    result = value.casefold()
    if not _SHA256.fullmatch(result):
        raise PromotionError("wake_cascade_promotion_evidence_invalid")
    return result


def _asset_identity(config: WakeCascadeConfig) -> dict[str, Any]:
    return {
        "upstreamGraphSha256": list(config.upstream_graph_sha256),
        "melFiltersSha256": config.mel_filters_sha256,
        "logmelVerifierSha256": (
            list(config.verifier_graph_sha256s)
            if len(config.verifier_graph_sha256s) > 1
            else config.verifier_graph_sha256
        ),
    }


def _validate_candidate(payload: dict[str, Any]) -> None:
    calibration = payload.get("calibration")
    if (
        payload.get("schema") not in {MANIFEST_SCHEMA, ROUTED_MANIFEST_SCHEMA}
        or payload.get("approved") is not False
        or payload.get("developmentOnly") is not True
        or not isinstance(calibration, dict)
        or calibration.get("approved") is not False
    ):
        raise PromotionError("wake_cascade_candidate_not_frozen_development")


def _validate_physical(
    payload: dict[str, Any], *, candidate_hash: str, assets: dict[str, Any]
) -> tuple[int, int]:
    positive = _object(payload, "positive")
    negative = _object(payload, "negative")
    reported_assets = _object(payload, "assets")
    positive_files = _integer(positive, "files", 48)
    positive_accepted = _integer(positive, "acceptedFiles")
    negative_files = _integer(negative, "files", 96)
    negative_accepted = _integer(negative, "acceptedFiles")
    if (
        payload.get("schema") != PHYSICAL_SCHEMA
        or payload.get("scope")
        != "exact_production_stream_api_opened_wasapi_raw"
        or payload.get("role") != "validation"
        or payload.get("openedCorpusPassed") is not True
        or payload.get("candidateFrozen") is not True
        or payload.get("corpusFrozen") is not True
        or payload.get("promotable") is not True
        or payload.get("blindHumanPartitionAccessed") is not False
        or payload.get("effectsExecuted") != 0
        or payload.get("filenamesOrTranscriptsRetained") is not False
        or _required_sha(reported_assets.get("cascadeManifestSha256"))
        != candidate_hash
        or any(reported_assets.get(name) != value for name, value in assets.items())
        or positive_accepted != positive_files
        or negative_accepted != 0
    ):
        raise PromotionError("wake_cascade_physical_validation_failed")
    return positive_files, negative_files


def _validate_negative_regression(
    payload: dict[str, Any], *, candidate_hash: str, lexical_rescue_enabled: bool
) -> tuple[int, float, int, float]:
    sources = _object(payload, "sources")
    contract = _object(payload, "contract")
    metrics = _object(payload, "metrics")
    utterances = _integer(metrics, "utterances", 1)
    exposure_hours = _number(metrics, "descriptiveExposureHours", 1e-9)
    false_activations = _integer(metrics, "negativeFalseActivations")
    lexical_invocations = _integer(metrics, "lexicalInvocations")
    far_upper = _number(metrics, "far95UpperConfidencePerHourIfZero")
    exact_zero_event_bound = -math.log(0.05) / exposure_hours
    if (
        payload.get("schema") != NEGATIVE_SCHEMA
        or payload.get("scope")
        != "previously_opened_100h_negative_development_regression"
        or payload.get("regressionPassed") is not True
        or payload.get("candidateFrozen") is not True
        or payload.get("blindHumanAudioAccessed") is not False
        or payload.get("transcriptsOrFilenamesRetained") is not False
        or payload.get("effectsExecuted") != 0
        or contract.get("everyBroadCandidateRescoredByExactCpuOnnx") is not True
        or contract.get("lexicalRescueEnabled", True) is not lexical_rescue_enabled
        or contract.get("lexicalRescueUsesProductParakeet") is not lexical_rescue_enabled
        or not lexical_rescue_enabled and lexical_invocations != 0
        or _required_sha(sources.get("cascadeManifestSha256")) != candidate_hash
        or false_activations != 0
        or exposure_hours < (-math.log(0.05) / 0.1)
        or far_upper > 0.1
        or not math.isclose(far_upper, exact_zero_event_bound, abs_tol=1e-12)
    ):
        raise PromotionError("wake_cascade_negative_regression_failed")
    return utterances, exposure_hours, false_activations, far_upper


def build_payloads(
    *,
    candidate_payload: dict[str, Any],
    candidate_hash: str,
    config: WakeCascadeConfig,
    physical_payload: dict[str, Any],
    physical_hash: str,
    negative_payload: dict[str, Any],
    negative_hash: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return calibration and approved-manifest payloads or fail closed."""

    _validate_candidate(candidate_payload)
    assets = _asset_identity(config)
    positive_files, physical_negative_files = _validate_physical(
        physical_payload, candidate_hash=candidate_hash, assets=assets
    )
    utterances, exposure_hours, false_activations, far_upper = (
        _validate_negative_regression(
            negative_payload,
            candidate_hash=candidate_hash,
            lexical_rescue_enabled=config.lexical_rescue_enabled,
        )
    )
    measured_at = datetime.now(timezone.utc).isoformat()
    report = {
        "schema": CALIBRATION_REPORT_SCHEMA,
        "measuredAtUtc": measured_at,
        "role": "validation",
        "candidateFrozen": True,
        "corpusFrozen": True,
        "physicalRoomValidated": True,
        "promotable": True,
        "assets": assets,
        "metrics": {
            "positiveFiles": positive_files,
            "positiveAcceptedFiles": positive_files,
            "physicalNegativeFiles": physical_negative_files,
            "negativeRegressionUtterances": utterances,
            "negativeFiles": physical_negative_files + utterances,
            "negativeFalseActivations": false_activations,
            "farConfidence": 0.95,
            "farExposureHours": exposure_hours,
            "farUpperConfidencePerHour": far_upper,
        },
        "evidence": {
            "candidateManifestSha256": candidate_hash,
            "physicalValidationSha256": physical_hash,
            "negativeRegressionSha256": negative_hash,
        },
        "effectsExecuted": 0,
    }
    promoted = deepcopy(candidate_payload)
    promoted["measuredAtUtc"] = measured_at
    promoted["calibration"] = {
        "approved": True,
        "report": CALIBRATION_REPORT_FILENAME,
        "reportSha256": "pending",
    }
    promoted["approved"] = True
    promoted["developmentOnly"] = False
    promoted["promotionEvidence"] = deepcopy(report["evidence"])
    return report, promoted


def _write_json_exclusive(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as sink:
        json.dump(payload, sink, ensure_ascii=False, indent=2)
        sink.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-manifest", type=Path, required=True)
    parser.add_argument("--physical-validation", type=Path, required=True)
    parser.add_argument("--negative-regression", type=Path, required=True)
    parser.add_argument("--output-report", type=Path, required=True)
    parser.add_argument("--output-manifest", type=Path, required=True)
    args = parser.parse_args()

    candidate = args.candidate_manifest.resolve(strict=True)
    physical = args.physical_validation.resolve(strict=True)
    negative = args.negative_regression.resolve(strict=True)
    output_report = args.output_report.resolve()
    output_manifest = args.output_manifest.resolve()
    if output_report.name != CALIBRATION_REPORT_FILENAME:
        raise SystemExit(f"Output report must be named {CALIBRATION_REPORT_FILENAME}.")
    if output_report.parent != candidate.parent or output_manifest.parent != candidate.parent:
        raise SystemExit("Promotion outputs must be adjacent to the frozen candidate assets.")
    if output_report.exists() or output_manifest.exists():
        raise SystemExit("Promotion output already exists.")

    candidate_payload = read_object(candidate)
    config = load_wake_cascade_candidate_config(candidate)
    report, promoted = build_payloads(
        candidate_payload=candidate_payload,
        candidate_hash=sha256(candidate),
        config=config,
        physical_payload=read_object(physical),
        physical_hash=sha256(physical),
        negative_payload=read_object(negative),
        negative_hash=sha256(negative),
    )
    _write_json_exclusive(output_report, report)
    promoted["calibration"]["reportSha256"] = sha256(output_report)
    _write_json_exclusive(output_manifest, promoted)
    print(
        json.dumps(
            {
                "promoted": True,
                "manifest": str(output_manifest),
                "manifestSha256": sha256(output_manifest),
                "reportSha256": sha256(output_report),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
