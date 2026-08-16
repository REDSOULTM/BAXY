"""Derive a stricter QbyT threshold from opened human and 100 h diagnostics."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from audit_wav2vec2_hidden_wake_separability_v1 import sha256  # noqa: E402


def select_threshold(
    *, human_qbyt_only_scores: list[float], contextual_false_scores: list[float]
) -> float:
    if (
        not human_qbyt_only_scores
        or not contextual_false_scores
        or not all(math.isfinite(value) for value in human_qbyt_only_scores)
        or not all(math.isfinite(value) for value in contextual_false_scores)
    ):
        raise ValueError("wake_qbyt_threshold_evidence_invalid")
    lower = max(contextual_false_scores)
    upper = min(human_qbyt_only_scores)
    if not lower < upper:
        raise ValueError("wake_qbyt_threshold_separation_missing")
    return lower + (upper - lower) / 2.0


def derive(
    *,
    base_candidate_path: Path,
    human_evidence_path: Path,
    negative_diagnostic_path: Path,
    output_path: Path,
) -> dict[str, object]:
    if output_path.exists():
        raise ValueError("wake_qbyt_threshold_output_exists")
    base_candidate_path = base_candidate_path.resolve(strict=True)
    human_evidence_path = human_evidence_path.resolve(strict=True)
    negative_diagnostic_path = negative_diagnostic_path.resolve(strict=True)
    output_path = output_path.resolve()
    base = json.loads(base_candidate_path.read_text(encoding="utf-8-sig"))
    human = json.loads(human_evidence_path.read_text(encoding="utf-8-sig"))
    negative = json.loads(negative_diagnostic_path.read_text(encoding="utf-8-sig"))
    human_records = human.get("qbytFallbackDiagnostics", [])
    false_scores = negative.get("secondaryDiagnostics", {}).get(
        "contextualEvidenceQbyTScores", []
    )
    if (
        base.get("schema") != "baxy.wav2vec2-qbyt-wake-candidate.v1"
        or human.get("schema") != "baxy.qbyt-contextual-development.v9"
        or human.get("policySummaries", {})
        .get("sameViewQbyTOrDualDecode", {})
        .get("gatePassed")
        is not True
        or human.get("qbytContract", {}).get("candidateSha256")
        != sha256(base_candidate_path)
        or not isinstance(human_records, list)
        or len(human_records) != 3
        or negative.get("schema")
        != "baxy.qbyt-dual-same-view-negative-regression.v10"
        or negative.get("regressionPassed") is not False
        or negative.get("metrics", {}).get("guardedNegativeFalseActivations") != 1
        or not isinstance(false_scores, list)
        or len(false_scores) != 1
    ):
        raise ValueError("wake_qbyt_threshold_boundary_invalid")
    human_qbyt_only = [
        float(record["maximumFusionPassingQbyTScore"])
        for record in human_records
        if record.get("qbytAccepted") is True
        and record.get("dualDecodeAccepted") is False
    ]
    threshold = select_threshold(
        human_qbyt_only_scores=human_qbyt_only,
        contextual_false_scores=[float(value) for value in false_scores],
    )
    old_threshold = float(base["policy"]["threshold"])
    if not old_threshold < threshold:
        raise ValueError("wake_qbyt_threshold_not_stricter")
    report = {
        **base,
        "schema": "baxy.wav2vec2-qbyt-wake-candidate.v2",
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "scope": "opened_development_composite_threshold_after_100h_failure",
        "sources": {
            **base["sources"],
            "baseCandidateSha256": sha256(base_candidate_path),
            "humanEvidenceSha256": sha256(human_evidence_path),
            "negativeDiagnosticSha256": sha256(negative_diagnostic_path),
        },
        "policy": {**base["policy"], "threshold": threshold},
        "thresholdSelection": {
            "rule": "midpoint_between_max_contextual_false_and_min_qbyt_only_human",
            "previousThreshold": old_threshold,
            "maximumContextualFalseScore": max(false_scores),
            "minimumQbyTOnlyHumanScore": min(human_qbyt_only),
            "selectedThreshold": threshold,
            "humanCompositeGatePreservedBySeparation": True,
            "opened100hFalseRejectedBySeparation": True,
        },
        "candidateFrozen": False,
        "productOperatingPoint": False,
        "freshHoldoutClaimSupported": False,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-candidate", type=Path, required=True)
    parser.add_argument("--human-evidence", type=Path, required=True)
    parser.add_argument("--negative-diagnostic", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    report = derive(
        base_candidate_path=arguments.base_candidate,
        human_evidence_path=arguments.human_evidence,
        negative_diagnostic_path=arguments.negative_diagnostic,
        output_path=arguments.output,
    )
    print(json.dumps(report["thresholdSelection"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
