"""Seal the aggregate verdict of the consumed blind STT campaign.

The blind reports are immutable evidence and must never become development
data.  This script validates their exact hashes and preregistered thresholds,
then publishes only aggregate results and the rejection decision.  It does not
inspect or expose individual blind cases.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA = "baxy.stt-blind-campaign-verdict.v1"
CONTRACT_SCHEMA = "baxy.stt-evaluator-preopen-contract.v3"
RAW_REPORT_SCHEMA = "baxy.stt-real-audio-evaluation.v3"
FUSION_REPORT_SCHEMA = "baxy.stt-bounded-completion-fallback-evaluation.v3"
POLICY = {
    "primary": "parakeet_greedy",
    "fallback": "nemotron_auto",
    "selector": "bounded_completion_v2",
}
EXPECTED_WAKE_TREE = {
    "pythonFiles": 344,
    "sha256": "756a5b311b20ed833da182595766c9d577cca89f20d7a4355eb972576f0f90c0",
}
EXPECTED_INPUTS = {
    "contract": {
        "path": "artifacts/research/stt_real_audio_fusion_blind_preopen_contract_v1.json",
        "sha256": "24fb9ff12939968d9d951f8ca93c8d5268f102d6f3619e31016aecfbb18f297e",
        "schema": CONTRACT_SCHEMA,
    },
    "minds14Primary": {
        "path": "artifacts/validation/stt_minds14_parakeet_greedy_blind_v1.json",
        "sha256": "336daf02341ad7bbf82a4f165b1cb51166a501a1c3d158e790c11a5dbb1e6231",
        "schema": RAW_REPORT_SCHEMA,
    },
    "audioArenaPrimary": {
        "path": "artifacts/validation/stt_audio_arena_parakeet_greedy_blind_v1.json",
        "sha256": "7feff92cfaac9e161c28c2bdab83f47ad3a0ab8137f72aa852bfafd36e6954a2",
        "schema": RAW_REPORT_SCHEMA,
    },
    "minds14Fallback": {
        "path": "artifacts/validation/stt_minds14_nemotron_auto_blind_v1.json",
        "sha256": "e694c29929b450ade9fe16c8ee8581467c6b1dd87ac0456e00a6a146a6e32e39",
        "schema": RAW_REPORT_SCHEMA,
    },
    "audioArenaFallback": {
        "path": "artifacts/validation/stt_audio_arena_nemotron_auto_blind_v1.json",
        "sha256": "800b3c438b3310767f261394be91fae9ab98c9b6809845138f772830b6efb48a",
        "schema": RAW_REPORT_SCHEMA,
    },
    "minds14Fusion": {
        "path": "artifacts/validation/stt_minds14_bounded_fusion_blind_v1.json",
        "sha256": "92c4997309c722499e650680489874fecf06c96c1b70c00c4247728f4a493ba6",
        "schema": FUSION_REPORT_SCHEMA,
    },
    "audioArenaFusion": {
        "path": "artifacts/validation/stt_audio_arena_bounded_fusion_blind_v1.json",
        "sha256": "40c44233e8d84f293e9c18a660d84e79ad385556fa046aa94496470ac852ab02",
        "schema": FUSION_REPORT_SCHEMA,
    },
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_bound_input(root: Path, name: str) -> tuple[dict[str, Any], dict[str, str]]:
    expected = EXPECTED_INPUTS[name]
    path = (root / expected["path"]).resolve(strict=True)
    actual_hash = sha256(path)
    if actual_hash != expected["sha256"]:
        raise RuntimeError(f"stt_blind_verdict_input_hash_mismatch:{name}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema") != expected["schema"]:
        raise RuntimeError(f"stt_blind_verdict_input_schema_mismatch:{name}")
    return value, {
        "path": expected["path"],
        "sha256": actual_hash,
        "schema": expected["schema"],
    }


def validate_raw_report(
    report: dict[str, Any], source: str, engine: str, expected_cases: int
) -> None:
    metrics = report.get("aggregate", {}).get("metrics", {})
    contract = report.get("contract", {})
    if (
        report.get("source") != source
        or report.get("partition") != "blind"
        or report.get("engine") != engine
        or report.get("effectsExecuted") != 0
        or metrics.get("cases") != expected_cases
        or metrics.get("decodeErrors") != 0
        or contract.get("sha256") != EXPECTED_INPUTS["contract"]["sha256"]
    ):
        raise RuntimeError(f"stt_blind_verdict_raw_report_invalid:{source}:{engine}")


def validate_fusion_report(
    report: dict[str, Any], source: str, expected_cases: int
) -> None:
    metrics = report.get("aggregate", {}).get("metrics", {})
    threshold = report.get("aggregate", {}).get("threshold", {})
    contract = report.get("inputs", {}).get("contract", {})
    required_threshold = (
        threshold.get("minimumIntentSemanticPreservation")
        if source == "minds14"
        else threshold.get("minimumCriticalAnchorRecall")
    )
    if (
        report.get("source") != source
        or report.get("partition") != "blind"
        or report.get("status") != "failed"
        or report.get("effectsExecuted") != 0
        or metrics.get("cases") != expected_cases
        or metrics.get("decodeErrors") != 0
        or required_threshold != 0.99
        or contract.get("sha256") != EXPECTED_INPUTS["contract"]["sha256"]
    ):
        raise RuntimeError(f"stt_blind_verdict_fusion_report_invalid:{source}")


def build_verdict(root: Path) -> dict[str, Any]:
    values: dict[str, dict[str, Any]] = {}
    receipts: dict[str, dict[str, str]] = {}
    for name in EXPECTED_INPUTS:
        values[name], receipts[name] = read_bound_input(root, name)

    contract = values["contract"]
    if (
        contract.get("role") != "blind"
        or contract.get("modelAudioDecoded") is not False
        or contract.get("candidatePolicy") != POLICY
        or contract.get("effectsExecuted") != 0
        or contract.get("wakeProgramTree", {}).get("pythonFiles")
        != EXPECTED_WAKE_TREE["pythonFiles"]
        or contract.get("wakeProgramTree", {}).get("sha256")
        != EXPECTED_WAKE_TREE["sha256"]
        or {
            item.get("source"): item.get("status")
            for item in contract.get("developmentReports", [])
        }
        != {"audio_arena": "passed", "minds14": "passed"}
    ):
        raise RuntimeError("stt_blind_verdict_contract_invalid")

    validate_raw_report(values["minds14Primary"], "minds14", "parakeet_greedy", 196)
    validate_raw_report(
        values["audioArenaPrimary"], "audio_arena", "parakeet_greedy", 50
    )
    validate_raw_report(values["minds14Fallback"], "minds14", "nemotron_auto", 196)
    validate_raw_report(
        values["audioArenaFallback"], "audio_arena", "nemotron_auto", 50
    )
    validate_fusion_report(values["minds14Fusion"], "minds14", 196)
    validate_fusion_report(values["audioArenaFusion"], "audio_arena", 50)

    minds_metrics = values["minds14Fusion"]["aggregate"]["metrics"]
    minds_checks = values["minds14Fusion"]["aggregate"]["checks"]
    audio_metrics = values["audioArenaFusion"]["aggregate"]["metrics"]
    audio_checks = values["audioArenaFusion"]["aggregate"]["checks"]
    closed_at = max(
        str(values[name]["measuredAtUtc"])
        for name in EXPECTED_INPUTS
        if name != "contract"
    )
    return {
        "schema": SCHEMA,
        "campaign": "stt_real_audio_bounded_fusion_blind_v1",
        "closedAtUtc": closed_at,
        "status": "failed",
        "promotionDecision": "rejected",
        "candidatePromoted": False,
        "blindPartitionsConsumed": True,
        "blindResultsAllowedForTuning": False,
        "thresholdsChangedAfterOpening": False,
        "candidatePolicy": POLICY,
        "wakeProgramTree": EXPECTED_WAKE_TREE,
        "results": {
            "minds14": {
                "cases": minds_metrics["cases"],
                "fallbackCases": minds_metrics["fallbackCases"],
                "transcriptIntentAccuracy": minds_metrics["transcriptIntentAccuracy"],
                "minimumTranscriptIntentAccuracy": 0.95,
                "intentSemanticPreservation": minds_metrics[
                    "intentSemanticPreservation"
                ],
                "minimumIntentSemanticPreservation": 0.99,
                "endpointAvailabilityP95Seconds": minds_metrics[
                    "endpointAvailabilityP95Seconds"
                ],
                "failedChecks": [
                    name for name, passed in minds_checks.items() if not passed
                ],
            },
            "audioArena": {
                "cases": audio_metrics["cases"],
                "fallbackCases": audio_metrics["fallbackCases"],
                "corpusWer": audio_metrics["corpusWer"],
                "maximumCorpusWer": 0.20,
                "criticalAnchorRecall": audio_metrics["criticalAnchorRecall"],
                "minimumCriticalAnchorRecall": 0.99,
                "criticalAnchors": values["audioArenaPrimary"]["aggregate"]["metrics"][
                    "criticalAnchors"
                ],
                "criticalAnchorsPreserved": values["audioArenaPrimary"]["aggregate"][
                    "metrics"
                ]["criticalAnchorsPreserved"],
                "endpointAvailabilityP95Seconds": audio_metrics[
                    "endpointAvailabilityP95Seconds"
                ],
                "failedChecks": [
                    name for name, passed in audio_checks.items() if not passed
                ],
            },
        },
        "failureMechanisms": [
            "minds14_intent_semantic_preservation_below_preregistered_threshold",
            "audio_arena_critical_anchor_recall_below_preregistered_threshold",
        ],
        "nextRequiredEvidence": (
            "A fresh independent real-speech holdout must be preregistered before "
            "any candidate decode; this consumed blind population cannot select, "
            "tune, or certify a later candidate."
        ),
        "inputs": receipts,
        "effectsExecuted": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[2]
    )
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    root = arguments.root.resolve(strict=True)
    output = arguments.output.resolve()
    if output.exists():
        raise RuntimeError(f"stt_blind_verdict_output_exists:{output}")
    verdict = build_verdict(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(verdict, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "output": output.as_posix(),
                "status": verdict["status"],
                "sha256": sha256(output),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
