"""Preregister and certify BAXY's combined physical wake v17 program.

The frozen cascade evaluator is authoritative for its branch.  This external
supplement closes the preregistration gap around the endpoint and fusion
branches without changing the wake tree, weights, thresholds, or audio
selection before the reserved physical corpus is opened.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
VOICE = REPO / "experiments/voice_latency"
CAPTURE_SCRIPT = VOICE / "capture_controlled_physical_wake_corpus_v1.py"
CASCADE_EVALUATOR = VOICE / "evaluate_baxy_wake_cascade_runtime_raw_v1.py"
ENDPOINT_EVALUATOR = VOICE / "evaluate_baxy_endpoint_voice_runtime_v1.py"
FUSION_SCRIPT = VOICE / "fuse_baxy_cascade_endpoint_reports_v1.py"
VALIDATOR = Path(__file__).resolve()
BASE_SCHEMA = "baxy.wake-cascade-physical-validation-preregistration.v2"
SUPPLEMENT_SCHEMA = "baxy.wake-v17-combined-validation-supplement.v2"
RECEIPT_SCHEMA = "baxy.wake-v17-combined-validation-receipt.v2"
CASCADE_SCHEMA = "baxy.wake-cascade-runtime-raw-development.v1"
ENDPOINT_SCHEMA = "baxy.endpoint-voice-runtime-development.v1"
FUSION_SCHEMA = "baxy.cascade-endpoint-fusion-development.v1"
EXPECTED_PROGRAM_TREE_SHA256 = (
    "756a5b311b20ed833da182595766c9d577cca89f20d7a4355eb972576f0f90c0"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object: {path}")
    return value


def write_json_exclusive(path: Path, payload: dict[str, Any]) -> None:
    path = path.resolve()
    if path.exists():
        raise FileExistsError(f"refusing to overwrite {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _relative(path: Path) -> str:
    return str(path.resolve().relative_to(REPO))


def _measurement_hashes() -> dict[str, str]:
    return {
        _relative(path): sha256(path)
        for path in (
            CAPTURE_SCRIPT,
            CASCADE_EVALUATOR,
            ENDPOINT_EVALUATOR,
            FUSION_SCRIPT,
            VALIDATOR,
        )
    }


def validate_base_preregistration(base_path: Path) -> dict[str, Any]:
    base = read_object(base_path)
    evaluation = base.get("evaluationContract")
    tree = evaluation.get("programTree") if isinstance(evaluation, dict) else None
    if (
        base.get("schema") != BASE_SCHEMA
        or base.get("role") != "validation"
        or base.get("candidateFrozen") is not True
        or base.get("corpusSelectionFrozen") is not True
        or base.get("blindHumanPartitionAccessed") is not False
        or base.get("effectsExecuted") != 0
        or not isinstance(evaluation, dict)
        or not isinstance(tree, dict)
        or tree.get("pythonFiles") != 344
        or tree.get("sha256") != EXPECTED_PROGRAM_TREE_SHA256
        or evaluation.get("captureScriptSha256") != sha256(CAPTURE_SCRIPT)
        or evaluation.get("evaluatorScriptSha256") != sha256(CASCADE_EVALUATOR)
        or evaluation.get("endpointEvaluatorScriptSha256") != sha256(ENDPOINT_EVALUATOR)
        or evaluation.get("fusionScriptSha256") != sha256(FUSION_SCRIPT)
        or evaluation.get("verificationPolicy") != "cascade_or_score_gated_endpoint"
    ):
        raise ValueError(
            "base physical wake preregistration is not the frozen v17 contract"
        )
    return base


def preregister(args: argparse.Namespace) -> dict[str, Any]:
    base_path = args.base_preregistration.resolve(strict=True)
    base = validate_base_preregistration(base_path)
    source = base["sourceSelection"]
    capture = base["captureContract"]
    evaluation = base["evaluationContract"]
    candidate_manifest = args.cascade_manifest.resolve(strict=True)
    stt_directory = args.stt_directory.resolve(strict=True)
    positive_root = args.positive_root.resolve(strict=True)
    negative_root = args.negative_root.resolve(strict=True)
    stt_files = evaluation["sttFilesSha256"]
    if sha256(candidate_manifest) != base["candidate"]["manifestSha256"] or any(
        sha256((stt_directory / name).resolve(strict=True)) != expected
        for name, expected in stt_files.items()
    ):
        raise ValueError(
            "candidate or STT assets do not match the base preregistration"
        )
    output_paths = {
        "captureDirectory": str(args.capture_directory.resolve()),
        "cascadeReport": _relative(args.cascade_report),
        "endpointReport": _relative(args.endpoint_report),
        "fusionReport": _relative(args.fusion_report),
        "combinedReceipt": _relative(args.combined_receipt),
    }
    supplement = {
        "schema": SUPPLEMENT_SCHEMA,
        "createdAtUtc": datetime.now(timezone.utc).isoformat(),
        "measurementStatus": "unopened",
        "preregisteredBeforePhysicalCapture": True,
        "basePreregistration": {
            "path": _relative(base_path),
            "sha256": sha256(base_path),
        },
        "frozenWakeProgramTree": evaluation["programTree"],
        "measurementSourcesSha256": _measurement_hashes(),
        "physicalPath": {
            "inputDevice": args.input_device,
            "inputDeviceName": args.input_device_name,
            "outputDevice": args.output_device,
            "outputDeviceName": args.output_device_name,
            "rawCaptureHelper": str(args.raw_capture_helper.resolve(strict=True)),
            "rawCaptureHelperSha256": sha256(args.raw_capture_helper.resolve()),
            "captureTransport": capture["captureTransport"],
        },
        "assetPaths": {
            "cascadeManifest": str(candidate_manifest),
            "cascadeManifestSha256": sha256(candidate_manifest),
            "sttDirectory": str(stt_directory),
            "sttFilesSha256": stt_files,
            "positiveRoot": str(positive_root),
            "negativeRoot": str(negative_root),
        },
        "sourceSelection": source,
        "captureContract": capture,
        "combinedPolicy": {
            "name": evaluation["verificationPolicy"],
            "cascadeBranchPolicy": "cascade",
            "positiveFiles": 48,
            "requiredPositiveHits": 48,
            "negativeFiles": 96,
            "maximumNegativeHits": 0,
            "maximumLatencyP50Seconds": 1.5,
            "maximumLatencyP95Seconds": 2.0,
            "latencyDefinition": (
                "maximum_of_cascade_compute_and_endpoint_wall_group_percentiles"
            ),
            "endpointDirectScoreGte": evaluation["endpointDirectScoreGte"],
            "endpointAliases": evaluation["endpointAliases"],
            "blockSamples": evaluation["blockSamples"],
        },
        "plannedOutputs": output_paths,
        "captureInvocation": {
            "includeAllWavs": True,
            "inputDevice": args.input_device,
            "outputDevice": args.output_device,
        },
        "effectsExecuted": 0,
        "blindHumanPartitionAccessed": False,
    }
    write_json_exclusive(args.output, supplement)
    return supplement


def _finite(value: object, label: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"invalid {label}")
    return number


def _records(group: dict[str, Any], flag: str, expected: int) -> list[dict[str, Any]]:
    records = group.get("records")
    if (
        group.get("files") != expected
        or not isinstance(records, list)
        or len(records) != expected
    ):
        raise ValueError("wake report group count mismatch")
    hashes: set[str] = set()
    for index, record in enumerate(records):
        if (
            not isinstance(record, dict)
            or record.get("record") != index
            or not isinstance(record.get("audioSha256"), str)
            or len(record["audioSha256"]) != 64
            or not isinstance(record.get(flag), bool)
            or record["audioSha256"] in hashes
        ):
            raise ValueError("wake report record identity mismatch")
        hashes.add(record["audioSha256"])
    return records


def _validate_capture_manifest(
    supplement: dict[str, Any], corpus_manifest_path: Path
) -> dict[str, Any]:
    manifest = read_object(corpus_manifest_path)
    physical = manifest.get("physicalPath")
    sources = manifest.get("sources")
    counts = manifest.get("counts")
    expected_physical = supplement["physicalPath"]
    capture = supplement["captureContract"]
    selection = supplement["sourceSelection"]
    if (
        not isinstance(physical, dict)
        or not isinstance(sources, dict)
        or not isinstance(counts, dict)
        or manifest.get("blindHumanPartitionAccessed") is not False
        or manifest.get("effectsExecuted") != 0
        or physical.get("inputDevice") != expected_physical["inputDeviceName"]
        or physical.get("outputDevice") != expected_physical["outputDeviceName"]
        or physical.get("captureTransport") != capture["captureTransport"]
        or physical.get("rawCaptureHelperSha256") != capture["rawCaptureHelperSha256"]
        or any(
            physical.get(name) != capture[name]
            for name in (
                "playbackGain",
                "preRollSecondsNotRetained",
                "postRollSecondsNotRetained",
                "maximumSourceSeconds",
                "maximumCaptureAttempts",
                "minimumPathCorrelation",
                "minimumCapturedSnrDb",
            )
        )
        or manifest.get("seed") != selection["seed"]
        or counts.get("positive") != selection["positiveFiles"]
        or counts.get("negative") != selection["negativeFiles"]
        or sources.get("positiveRootSha256") != selection["positiveRootSha256"]
        or sources.get("negativeRootSha256") != selection["negativeRootSha256"]
    ):
        raise ValueError("captured physical corpus does not match the supplement")
    return manifest


def _validate_report_headers(
    supplement: dict[str, Any],
    cascade: dict[str, Any],
    endpoint: dict[str, Any],
    fusion: dict[str, Any],
    *,
    corpus_manifest_sha256: str,
) -> None:
    policy = supplement["combinedPolicy"]
    base_candidate = read_object(
        (REPO / supplement["basePreregistration"]["path"]).resolve(strict=True)
    )["candidate"]
    cascade_branch_passed = (
        cascade.get("positive", {}).get("acceptedFiles") == policy["positiveFiles"]
        and cascade.get("negative", {}).get("acceptedFiles") == 0
    )
    if (
        cascade.get("schema") != CASCADE_SCHEMA
        or cascade.get("role") != "development"
        or cascade.get("preregistrationSha256") is not None
        or cascade.get("corpusManifestSha256") != corpus_manifest_sha256
        or cascade.get("openedCorpusPassed") is not cascade_branch_passed
        or cascade.get("candidateFrozen") is not cascade_branch_passed
        or cascade.get("corpusFrozen") is not False
        or cascade.get("promotable") is not False
        or cascade.get("developmentOnly") is not True
        or cascade.get("blindHumanPartitionAccessed") is not False
        or cascade.get("effectsExecuted") != 0
        or cascade.get("contract", {}).get("blockSamples") != policy["blockSamples"]
        or cascade.get("contract", {}).get("verificationPolicy")
        != policy["cascadeBranchPolicy"]
        or cascade.get("assets", {}).get("cascadeManifestSha256")
        != base_candidate["manifestSha256"]
        or cascade.get("assets", {}).get("upstreamGraphSha256")
        != base_candidate["upstreamGraphSha256"]
        or cascade.get("assets", {}).get("melFiltersSha256")
        != base_candidate["melFiltersSha256"]
        or cascade.get("assets", {}).get("logmelVerifierSha256")
        != base_candidate["logmelVerifierSha256"]
        or endpoint.get("schema") != ENDPOINT_SCHEMA
        or endpoint.get("corpusManifestSha256") != corpus_manifest_sha256
        or endpoint.get("candidateFrozen") is not False
        or endpoint.get("developmentOnly") is not True
        or endpoint.get("promotable") is not False
        or endpoint.get("blindHumanPartitionAccessed") is not False
        or endpoint.get("effectsExecuted") != 0
        or endpoint.get("contract", {}).get("endpointDirectScoreGte")
        != policy["endpointDirectScoreGte"]
        or endpoint.get("contract", {}).get("endpointAliases")
        != policy["endpointAliases"]
        or endpoint.get("contract", {}).get("ttsSuppressed") is not True
        or endpoint.get("assets", {}).get("cascadeManifestSha256")
        != base_candidate["manifestSha256"]
        or endpoint.get("assets", {}).get("sttDirectory")
        != Path(supplement["assetPaths"]["sttDirectory"]).name
        or fusion.get("schema") != FUSION_SCHEMA
        or fusion.get("corpusManifestSha256") != corpus_manifest_sha256
        or fusion.get("developmentOnly") is not True
        or fusion.get("promotable") is not False
        or fusion.get("blindHumanPartitionAccessed") is not False
        or fusion.get("effectsExecuted") != 0
    ):
        raise ValueError("wake report header contract mismatch")


def _validate_group(
    cascade: dict[str, Any],
    endpoint: dict[str, Any],
    fusion: dict[str, Any],
    *,
    expected: int,
) -> tuple[int, set[str]]:
    cascade_records = _records(cascade, "accepted", expected)
    endpoint_records = _records(endpoint, "hit", expected)
    fusion_records = _records(fusion, "cascadeOrEndpoint", expected)
    combined_hits = 0
    identities: set[str] = set()
    for index, (acoustic, lexical, combined) in enumerate(
        zip(cascade_records, endpoint_records, fusion_records, strict=True)
    ):
        acoustic_hit = acoustic["accepted"]
        lexical_hit = lexical["hit"]
        expected_combined = acoustic_hit or lexical_hit
        if (
            len(
                {
                    acoustic["audioSha256"],
                    lexical["audioSha256"],
                    combined["audioSha256"],
                }
            )
            != 1
            or combined.get("record") != index
            or combined.get("cascade") is not acoustic_hit
            or combined.get("endpoint") is not lexical_hit
            or combined.get("cascadeOrEndpoint") is not expected_combined
            or combined.get("cascadeAndEndpoint") is not (acoustic_hit and lexical_hit)
        ):
            raise ValueError("wake fusion is not identity-preserving")
        identities.add(acoustic["audioSha256"])
        combined_hits += int(expected_combined)
    policies = fusion.get("policies", {})
    combined_policy = policies.get("cascadeOrEndpoint", {})
    if (
        combined_policy.get("hits") != combined_hits
        or combined_policy.get("files") != expected
        or combined_policy.get("rate") != combined_hits / expected
    ):
        raise ValueError("wake fusion summary does not match its records")
    return combined_hits, identities


def validate(args: argparse.Namespace) -> dict[str, Any]:
    supplement_path = args.supplement.resolve(strict=True)
    supplement = read_object(supplement_path)
    if (
        supplement.get("schema") != SUPPLEMENT_SCHEMA
        or supplement.get("measurementStatus") != "unopened"
        or supplement.get("preregisteredBeforePhysicalCapture") is not True
        or supplement.get("effectsExecuted") != 0
        or supplement.get("blindHumanPartitionAccessed") is not False
        or supplement.get("measurementSourcesSha256") != _measurement_hashes()
    ):
        raise ValueError("combined wake supplement is not frozen and unopened")
    helper = Path(supplement["physicalPath"]["rawCaptureHelper"]).resolve(strict=True)
    if sha256(helper) != supplement["physicalPath"]["rawCaptureHelperSha256"]:
        raise ValueError("RAW capture helper changed after supplement")
    assets = supplement["assetPaths"]
    candidate_manifest = Path(assets["cascadeManifest"]).resolve(strict=True)
    stt_directory = Path(assets["sttDirectory"]).resolve(strict=True)
    if (
        sha256(candidate_manifest) != assets["cascadeManifestSha256"]
        or any(
            sha256((stt_directory / name).resolve(strict=True)) != expected
            for name, expected in assets["sttFilesSha256"].items()
        )
        or not Path(assets["positiveRoot"]).resolve(strict=True).is_dir()
        or not Path(assets["negativeRoot"]).resolve(strict=True).is_dir()
    ):
        raise ValueError("wake assets changed after supplement")
    planned = supplement["plannedOutputs"]
    expected_paths = {
        "cascadeReport": args.cascade_report.resolve(),
        "endpointReport": args.endpoint_report.resolve(),
        "fusionReport": args.fusion_report.resolve(),
        "combinedReceipt": args.output.resolve(),
    }
    for name, path in expected_paths.items():
        if str(path.relative_to(REPO)) != planned[name]:
            raise ValueError(f"unexpected {name} path")
    base_path = (REPO / supplement["basePreregistration"]["path"]).resolve(strict=True)
    if sha256(base_path) != supplement["basePreregistration"]["sha256"]:
        raise ValueError("base preregistration changed after supplement")
    validate_base_preregistration(base_path)
    capture_directory = Path(planned["captureDirectory"]).resolve(strict=True)
    corpus_manifest_path = (capture_directory / "manifest.v1.json").resolve(strict=True)
    _validate_capture_manifest(supplement, corpus_manifest_path)
    cascade = read_object(expected_paths["cascadeReport"])
    endpoint = read_object(expected_paths["endpointReport"])
    fusion = read_object(expected_paths["fusionReport"])
    _validate_report_headers(
        supplement,
        cascade,
        endpoint,
        fusion,
        corpus_manifest_sha256=sha256(corpus_manifest_path),
    )
    if fusion.get("sourceReports") != {
        "cascadeSha256": sha256(expected_paths["cascadeReport"]),
        "endpointSha256": sha256(expected_paths["endpointReport"]),
    }:
        raise ValueError("fusion source report hashes do not match")
    policy = supplement["combinedPolicy"]
    positive_hits, positive_ids = _validate_group(
        cascade["positive"],
        endpoint["positive"],
        fusion["positive"],
        expected=policy["positiveFiles"],
    )
    negative_hits, negative_ids = _validate_group(
        cascade["negative"],
        endpoint["negative"],
        fusion["negative"],
        expected=policy["negativeFiles"],
    )
    if positive_ids & negative_ids:
        raise ValueError("positive and negative physical audio overlap")
    cascade_p50 = _finite(cascade["positive"]["runtimeSeconds"]["p50"], "cascade p50")
    cascade_p95 = _finite(cascade["positive"]["runtimeSeconds"]["p95"], "cascade p95")
    endpoint_p50 = _finite(
        endpoint["positive"]["runtimeSeconds"]["wallP50"], "endpoint p50"
    )
    endpoint_p95 = _finite(
        endpoint["positive"]["runtimeSeconds"]["wallP95"], "endpoint p95"
    )
    aggregate_p50 = max(cascade_p50, endpoint_p50)
    aggregate_p95 = max(cascade_p95, endpoint_p95)
    checks = {
        "positiveHitsExact": positive_hits == policy["requiredPositiveHits"],
        "negativeHitsWithinMaximum": negative_hits <= policy["maximumNegativeHits"],
        "latencyP50WithinMaximum": (
            aggregate_p50 <= policy["maximumLatencyP50Seconds"]
        ),
        "latencyP95WithinMaximum": (
            aggregate_p95 <= policy["maximumLatencyP95Seconds"]
        ),
        "positiveNegativeAudioDisjoint": not bool(positive_ids & negative_ids),
        "allReportIdentitiesMatched": True,
        "allFrozenSourcesMatched": True,
        "effectsExecutedZero": True,
    }
    passed = all(checks.values())
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "supplementSha256": sha256(supplement_path),
        "basePreregistrationSha256": sha256(base_path),
        "corpusManifestSha256": sha256(corpus_manifest_path),
        "sourceReports": {
            "cascadeSha256": sha256(expected_paths["cascadeReport"]),
            "endpointSha256": sha256(expected_paths["endpointReport"]),
            "fusionSha256": sha256(expected_paths["fusionReport"]),
        },
        "combinedPolicy": policy["name"],
        "metrics": {
            "positiveHits": positive_hits,
            "positiveFiles": policy["positiveFiles"],
            "negativeFalseActivations": negative_hits,
            "negativeFiles": policy["negativeFiles"],
            "latencyP50Seconds": aggregate_p50,
            "latencyP95Seconds": aggregate_p95,
        },
        "checks": checks,
        "validationPassed": passed,
        "promotionEligible": passed,
        "promotionExecuted": False,
        "blindHumanPartitionAccessed": False,
        "effectsExecuted": 0,
    }
    write_json_exclusive(args.output, receipt)
    return receipt


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    prereg = subparsers.add_parser("preregister")
    prereg.add_argument("--base-preregistration", type=Path, required=True)
    prereg.add_argument("--output", type=Path, required=True)
    prereg.add_argument("--capture-directory", type=Path, required=True)
    prereg.add_argument("--cascade-report", type=Path, required=True)
    prereg.add_argument("--endpoint-report", type=Path, required=True)
    prereg.add_argument("--fusion-report", type=Path, required=True)
    prereg.add_argument("--combined-receipt", type=Path, required=True)
    prereg.add_argument("--input-device", type=int, required=True)
    prereg.add_argument("--input-device-name", required=True)
    prereg.add_argument("--output-device", type=int, required=True)
    prereg.add_argument("--output-device-name", required=True)
    prereg.add_argument("--raw-capture-helper", type=Path, required=True)
    prereg.add_argument("--cascade-manifest", type=Path, required=True)
    prereg.add_argument("--stt-directory", type=Path, required=True)
    prereg.add_argument("--positive-root", type=Path, required=True)
    prereg.add_argument("--negative-root", type=Path, required=True)
    check = subparsers.add_parser("validate")
    check.add_argument("--supplement", type=Path, required=True)
    check.add_argument("--cascade-report", type=Path, required=True)
    check.add_argument("--endpoint-report", type=Path, required=True)
    check.add_argument("--fusion-report", type=Path, required=True)
    check.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    payload = preregister(args) if args.command == "preregister" else validate(args)
    summary = (
        {"measurementStatus": payload["measurementStatus"]}
        if args.command == "preregister"
        else {
            "validationPassed": payload["validationPassed"],
            **payload["metrics"],
        }
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if args.command == "preregister" or payload["validationPassed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
