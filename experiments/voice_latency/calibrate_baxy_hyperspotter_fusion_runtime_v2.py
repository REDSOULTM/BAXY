"""Package a runtime-calibrated BAXY fusion candidate without model retraining.

The threshold adjustment is derived only from the permitted legacy human
selection partition.  Expanded development is explicitly excluded.  A fixed
0.05 decision-score guard absorbs ONNX/preprocessing numerical drift while
the original graph, Mel matrix, and CTC verifier identities remain frozen.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import shutil


RUNTIME_DECISION_GUARD = 0.05


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError("baxy_hyper_runtime_calibration_json_invalid")
    return value


def adjacent_file(manifest_path: Path, name: object, suffix: str) -> Path:
    if not isinstance(name, str) or not name or Path(name).name != name:
        raise ValueError("baxy_hyper_runtime_calibration_asset_invalid")
    path = (manifest_path.parent / name).resolve(strict=True)
    if path.parent != manifest_path.parent or path.suffix.lower() != suffix:
        raise ValueError("baxy_hyper_runtime_calibration_asset_invalid")
    return path


def select_runtime_threshold(
    *,
    base_threshold: float,
    maximum_legacy_negative_margin: float,
    minimum_legacy_positive_margin: float,
    guard: float = RUNTIME_DECISION_GUARD,
) -> dict[str, float]:
    values = (
        base_threshold,
        maximum_legacy_negative_margin,
        minimum_legacy_positive_margin,
        guard,
    )
    if (
        not all(math.isfinite(float(value)) for value in values)
        or maximum_legacy_negative_margin < 0.0
        or guard <= 0.0
    ):
        raise ValueError("baxy_hyper_runtime_calibration_margin_invalid")
    adjustment = maximum_legacy_negative_margin + guard
    remaining_positive_margin = minimum_legacy_positive_margin - adjustment
    if remaining_positive_margin <= guard:
        raise ValueError("baxy_hyper_runtime_calibration_headroom_insufficient")
    return {
        "baseDecisionThreshold": float(base_threshold),
        "observedMaximumLegacyNegativeMargin": float(
            maximum_legacy_negative_margin
        ),
        "observedMinimumLegacyPositiveMargin": float(
            minimum_legacy_positive_margin
        ),
        "fixedNumericalGuard": float(guard),
        "thresholdAdjustment": float(adjustment),
        "calibratedDecisionThreshold": float(base_threshold + adjustment),
        "expectedMaximumLegacyNegativeMargin": float(-guard),
        "expectedMinimumLegacyPositiveMargin": float(remaining_positive_margin),
    }


def calibration_from_audit(
    *,
    base_manifest: dict[str, object],
    base_manifest_sha256: str,
    audit_report: dict[str, object],
) -> dict[str, object]:
    policy = base_manifest.get("policy")
    sources = audit_report.get("sources")
    legacy = audit_report.get("legacyDevelopment")
    expanded = audit_report.get("expandedIndependentDevelopment")
    if (
        base_manifest.get("schema") != "baxy-hyperspotter-fusion-v1"
        or base_manifest.get("approved") is not False
        or base_manifest.get("blindHumanAudioAccessed") is not False
        or not isinstance(policy, dict)
        or policy.get("ctc_feature") != "full_clip_margin"
        or audit_report.get("schema")
        != "baxy.hyperspotter-fusion-product-runtime-audit.v1"
        or audit_report.get("blindHumanAudioAccessed") is not False
        or audit_report.get("humanDevelopmentAudioAccessed") is not True
        or audit_report.get("developmentOnly") is not True
        or not isinstance(sources, dict)
        or sources.get("fusionManifestSha256") != base_manifest_sha256
        or not isinstance(legacy, dict)
        or not isinstance(expanded, dict)
        or legacy.get("positiveTotal") != 14
        or legacy.get("negativeTotal") != 4
        or legacy.get("positiveHits") != 14
        or int(legacy.get("falseHits", 0)) < 1
        or expanded.get("positiveTotal") != 4
        or expanded.get("negativeTotal") != 8
    ):
        raise ValueError("baxy_hyper_runtime_calibration_evidence_invalid")
    try:
        selected = select_runtime_threshold(
            base_threshold=float(policy["decision_threshold"]),
            maximum_legacy_negative_margin=float(
                legacy["maximumNegativeDecisionMargin"]
            ),
            minimum_legacy_positive_margin=float(
                legacy["minimumPositiveDecisionMargin"]
            ),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("baxy_hyper_runtime_calibration_evidence_invalid") from error
    return {
        "schema": "baxy.hyperspotter-fusion-runtime-calibration.v2",
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "selectionPartition": "human_legacy",
        "expandedPartitionUsedForSelection": False,
        "selectionRule": "maximum_legacy_negative_plus_fixed_0.05_guard",
        **selected,
        "candidateGraphRetrained": False,
        "candidateGraphChanged": False,
        "humanDevelopmentAudioAccessed": True,
        "blindHumanAudioAccessed": False,
        "audioOrFilenamesRetained": False,
        "approved": False,
        "developmentOnly": True,
        "effectsExecuted": 0,
    }


def link_or_copy(source: Path, destination: Path) -> str:
    try:
        os.link(source, destination)
        return "hardlink"
    except OSError:
        shutil.copy2(source, destination)
        return "copy"


def package(
    *,
    base_manifest_path: Path,
    runtime_audit_path: Path,
    output_directory: Path,
) -> dict[str, object]:
    base_manifest_path = base_manifest_path.resolve(strict=True)
    runtime_audit_path = runtime_audit_path.resolve(strict=True)
    output_directory = output_directory.resolve()
    partial = output_directory.with_name(output_directory.name + ".partial")
    if output_directory.exists() or partial.exists():
        raise FileExistsError("baxy_hyper_runtime_calibration_output_exists")
    base = read_object(base_manifest_path)
    audit = read_object(runtime_audit_path)
    base_hash = sha256(base_manifest_path)
    calibration = calibration_from_audit(
        base_manifest=base,
        base_manifest_sha256=base_hash,
        audit_report=audit,
    )
    graph = adjacent_file(base_manifest_path, base.get("graph"), ".onnx")
    mel = adjacent_file(base_manifest_path, base.get("melFilters"), ".npy")
    if (
        sha256(graph) != base.get("graphSha256")
        or sha256(mel) != base.get("melFiltersSha256")
    ):
        raise ValueError("baxy_hyper_runtime_calibration_asset_hash_mismatch")

    partial.mkdir(parents=True)
    graph_mode = link_or_copy(graph, partial / graph.name)
    mel_mode = link_or_copy(mel, partial / mel.name)
    calibration.update(
        {
            "baseCandidateManifestSha256": base_hash,
            "sourceRuntimeAuditSha256": sha256(runtime_audit_path),
            "graphSha256": sha256(graph),
            "melFiltersSha256": sha256(mel),
        }
    )
    report_path = partial / "runtime-calibration-development.v2.json"
    report_path.write_text(
        json.dumps(calibration, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    calibrated = dict(base)
    calibrated["measuredAtUtc"] = datetime.now(timezone.utc).isoformat()
    calibrated["policy"] = {
        **dict(base["policy"]),
        "decision_threshold": calibration["calibratedDecisionThreshold"],
    }
    calibrated["runtimeCalibration"] = {
        "schema": "baxy.hyperspotter-fusion-runtime-calibration.v2",
        "report": report_path.name,
        "reportSha256": sha256(report_path),
        "selectionPartition": "human_legacy",
        "expandedPartitionUsedForSelection": False,
        "fixedNumericalGuard": RUNTIME_DECISION_GUARD,
    }
    calibrated["approved"] = False
    calibrated["developmentOnly"] = True
    manifest_path = partial / "baxy-hyperspotter-fusion-v1.json"
    manifest_path.write_text(
        json.dumps(calibrated, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    bundle = {
        "schema": "baxy.hyperspotter-fusion-candidate-bundle.v2",
        "manifest": manifest_path.name,
        "manifestSha256": sha256(manifest_path),
        "files": [graph.name, mel.name, report_path.name],
        "materialization": {"graph": graph_mode, "melFilters": mel_mode},
        "approved": False,
        "developmentOnly": True,
        "effectsExecuted": 0,
    }
    (partial / "candidate.bundle.v2.json").write_text(
        json.dumps(bundle, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    partial.rename(output_directory)
    return {"manifest": calibrated, "calibration": calibration, "bundle": bundle}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-manifest", type=Path, required=True)
    parser.add_argument("--runtime-audit", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    result = package(
        base_manifest_path=arguments.base_manifest,
        runtime_audit_path=arguments.runtime_audit,
        output_directory=arguments.output_directory,
    )
    print(
        json.dumps(
            {
                "policy": result["manifest"]["policy"],
                "calibration": result["calibration"],
                "materialization": result["bundle"]["materialization"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
