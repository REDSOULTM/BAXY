"""Publish aggregate failure evidence for the frozen ServiceNow blind run."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any


SCHEMA = "baxy.servicenow-semantic-fusion-blind-failure-analysis.v1"
EVALUATION_SCHEMA = "baxy.servicenow-semantic-fusion-blind-evaluation.v1"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _anchor_category(anchor: str) -> str:
    if anchor.isdigit():
        return "numeric"
    if re.search(r"[A-Z]", anchor) and anchor == anchor.upper():
        return "uppercase"
    return "named"


def analyze(arguments: argparse.Namespace) -> dict[str, Any]:
    repository_root = arguments.repository_root.resolve(strict=True)
    evaluation_path = arguments.evaluation.resolve(strict=True)
    detail_path = arguments.detail.resolve(strict=True)
    output_path = arguments.output.resolve()
    if output_path.exists():
        raise RuntimeError("semantic_fusion_blind_failure_analysis_output_exists")

    evaluation = json.loads(evaluation_path.read_text(encoding="utf-8-sig"))
    detail = json.loads(detail_path.read_text(encoding="utf-8-sig"))
    if (
        evaluation.get("schema") != EVALUATION_SCHEMA
        or evaluation.get("status") != "failed"
        or evaluation.get("detail", {}).get("sha256") != sha256(detail_path)
        or detail.get("schema") != EVALUATION_SCHEMA
        or detail.get("partition") != "blind"
        or detail.get("effectsExecuted") != 0
        or evaluation.get("effectsExecuted") != 0
    ):
        raise RuntimeError("semantic_fusion_blind_failure_analysis_input_invalid")

    cases = detail["cases"]
    all_anchors = 0
    primary_preserved = 0
    semantic_preserved = 0
    fusion_recovered = 0
    fusion_lost = 0
    failed_cases = 0
    missed_categories: Counter[str] = Counter()
    missed_anchors: Counter[str] = Counter()
    for case in cases:
        anchors = list(case["criticalAnchors"])
        primary = set(case["primaryCriticalAnchorsPreserved"])
        semantic = set(case["criticalAnchorsPreserved"])
        all_anchors += len(anchors)
        primary_preserved += sum(anchor in primary for anchor in anchors)
        semantic_preserved += sum(anchor in semantic for anchor in anchors)
        fusion_recovered += sum(
            anchor not in primary and anchor in semantic for anchor in anchors
        )
        fusion_lost += sum(
            anchor in primary and anchor not in semantic for anchor in anchors
        )
        missed = [anchor for anchor in anchors if anchor not in semantic]
        failed_cases += bool(missed)
        missed_anchors.update(missed)
        missed_categories.update(_anchor_category(anchor) for anchor in missed)

    repeated_occurrences = sum(
        count for count in missed_anchors.values() if count > 1
    )
    failed_checks = sorted(
        key for key, passed in evaluation["checks"].items() if not passed
    )
    passed_checks = sorted(
        key for key, passed in evaluation["checks"].items() if passed
    )
    generator = Path(__file__).resolve(strict=True)
    artifact: dict[str, Any] = {
        "schema": SCHEMA,
        "analyzedAtUtc": datetime.now(timezone.utc).isoformat(),
        "status": "candidate_rejected",
        "evidence": {
            "evaluation": {
                "path": evaluation_path.relative_to(repository_root).as_posix(),
                "sha256": sha256(evaluation_path),
            },
            "detail": {
                "path": detail_path.as_posix(),
                "sha256": sha256(detail_path),
                "storedOutsideRepository": not detail_path.is_relative_to(
                    repository_root
                ),
            },
        },
        "gate": {
            "failedChecks": failed_checks,
            "passedChecks": passed_checks,
            "criticalAnchorRecall": evaluation["metrics"][
                "criticalAnchorRecall"
            ],
            "minimumCriticalAnchorRecall": evaluation["thresholds"][
                "minimumCriticalAnchorRecall"
            ],
            "corpusWer": evaluation["metrics"]["corpusWer"],
            "initialSignalLatencyP95Seconds": evaluation["metrics"][
                "initialSignalLatencyP95Seconds"
            ],
        },
        "failureMechanism": {
            "criticalAnchors": all_anchors,
            "primaryPreserved": primary_preserved,
            "semanticPreserved": semantic_preserved,
            "primaryRecall": round(primary_preserved / max(1, all_anchors), 6),
            "semanticRecall": round(semantic_preserved / max(1, all_anchors), 6),
            "fusionRecovered": fusion_recovered,
            "fusionLost": fusion_lost,
            "remainingMisses": all_anchors - semantic_preserved,
            "casesWithRemainingMisses": failed_cases,
            "remainingMissesBySurfaceClass": dict(sorted(missed_categories.items())),
            "distinctMissedSurfaces": len(missed_anchors),
            "repeatedMissOccurrences": repeated_occurrences,
            "singleOccurrenceMisses": sum(
                count for count in missed_anchors.values() if count == 1
            ),
            "secondaryTriggeredCases": evaluation["metrics"][
                "secondaryTriggeredCases"
            ],
            "diagnosis": (
                "primary_decoder_entity_and_identifier_recall_is_the_limiting_stage;"
                "semantic_fusion_improved_recall_without_erasing_any_preserved_anchor;"
                "postal_only_secondary_routing_did_not_cover_the_remaining_entity_surface"
            ),
        },
        "decision": {
            "candidatePromoted": False,
            "sameBlindPartitionMayBeUsedForTuning": False,
            "sameBlindPartitionMayBeReevaluatedForPromotion": False,
            "requiredNextArchitecture": (
                "catalog_derived_entity_recovery_or_constrained_decoding_calibrated_on_"
                "independent_development_data_then_measured_on_a_new_disjoint_blind_oracle"
            ),
        },
        "wakeProgramTree": evaluation["wakeProgramTree"],
        "generator": {
            "path": generator.relative_to(repository_root).as_posix(),
            "sha256": sha256(generator),
        },
        "effectsExecuted": 0,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return artifact


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--evaluation", type=Path, required=True)
    parser.add_argument("--detail", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    artifact = analyze(arguments)
    print(
        json.dumps(
            {
                "output": str(arguments.output),
                "status": artifact["status"],
                "sha256": sha256(arguments.output),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
