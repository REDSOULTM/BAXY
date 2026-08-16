"""Derive an exact 100 h wake regression for a stricter guard-chain child."""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import time
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
for path in (ROOT / "src", HERE):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from baxy_mind.wake_cascade import (  # noqa: E402
    load_wake_cascade_candidate_config,
)


SCHEMA = "baxy.wake-cascade-openslr-negative-regression.v1"
PARENT_BUILD_SCHEMA = "baxy.logmel-guarded-rescue-verifier.v1"
CHILD_BUILD_SCHEMA = "baxy.logmel-guard-chain-rescue-verifier.v2"
CORPUS_SCHEMA = "baxy.openslr-librispeech-negative-holdout.v1"
SCREEN_SCHEMA = "baxy.wake-cascade-openslr-screen-checkpoint.v1"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("wake_monotonic_guard_json_invalid")
    return value


def load_component(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("wake_monotonic_guard_component_invalid")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def validate_monotonic_chain(
    parent_build: dict[str, Any], child_build: dict[str, Any]
) -> tuple[str, str, list[str], float, float]:
    parent_sources = parent_build.get("sources")
    child_sources = child_build.get("sources")
    parent_contract = parent_build.get("contract")
    child_contract = child_build.get("contract")
    parent_files = parent_build.get("files")
    child_files = child_build.get("files")
    if not all(
        isinstance(value, dict)
        for value in (
            parent_sources,
            child_sources,
            parent_contract,
            child_contract,
            parent_files,
            child_files,
        )
    ):
        raise ValueError("wake_monotonic_guard_build_invalid")
    assert isinstance(parent_sources, dict)
    assert isinstance(child_sources, dict)
    assert isinstance(parent_contract, dict)
    assert isinstance(child_contract, dict)
    assert isinstance(parent_files, dict)
    assert isinstance(child_files, dict)
    guards = child_sources.get("guard_verifier_sha256")
    base = parent_sources.get("base_verifier_sha256")
    parent_guard = parent_sources.get("guard_verifier_sha256")
    deployment = parent_contract.get("deployment_threshold")
    rescue = parent_contract.get("rescue_threshold")
    if (
        parent_build.get("schema") != PARENT_BUILD_SCHEMA
        or child_build.get("schema") != CHILD_BUILD_SCHEMA
        or not isinstance(base, str)
        or not isinstance(parent_guard, str)
        or not isinstance(guards, list)
        or len(guards) < 2
        or not all(isinstance(value, str) for value in guards)
        or guards[0] != parent_guard
        or child_sources.get("base_verifier_sha256") != base
        or child_contract.get("monotonic_guard_chain") is not True
        or child_contract.get("deployment_threshold") != deployment
        or child_contract.get("rescue_threshold") != rescue
        or not isinstance(deployment, (int, float))
        or not isinstance(rescue, (int, float))
        or not float(rescue) > float(deployment)
        or not isinstance(parent_files.get("graph_sha256"), str)
        or not isinstance(child_files.get("graph_sha256"), str)
    ):
        raise ValueError("wake_monotonic_guard_not_subset")
    return (
        str(base),
        str(parent_guard),
        list(guards),
        float(deployment),
        float(rescue),
    )


def _config_contract(config: Any) -> tuple[Any, ...]:
    return (
        config.upstream_graph_sha256,
        config.mel_filters_sha256,
        config.hop_samples,
        config.history_windows,
        config.primary_threshold,
        config.secondary_threshold,
        config.rescue_alias_index,
        config.rescue_alias_threshold,
        config.lexical_rescue_enabled,
        tuple(
            (route.name, route.upstream_indexes, route.verifier_threshold)
            for route in config.routes
        ),
    )


def derive(args: argparse.Namespace) -> dict[str, Any]:
    output = args.output.resolve()
    if output.exists():
        raise ValueError("wake_monotonic_guard_output_exists")
    parent_report_path = args.parent_report.resolve(strict=True)
    parent_manifest_path = args.parent_cascade_manifest.resolve(strict=True)
    child_manifest_path = args.child_cascade_manifest.resolve(strict=True)
    parent_build_path = args.parent_verifier_build_report.resolve(strict=True)
    child_build_path = args.child_verifier_build_report.resolve(strict=True)
    screen_path = args.screen_checkpoint.resolve(strict=True)
    corpus_path = args.corpus_manifest.resolve(strict=True)
    ffmpeg = args.ffmpeg.resolve(strict=True)
    parent_report = read_object(parent_report_path)
    parent_build = read_object(parent_build_path)
    child_build = read_object(child_build_path)
    screen = read_object(screen_path)
    corpus = read_object(corpus_path)
    false_hashes = parent_report.get("falseActivationAudioSha256")
    metrics = parent_report.get("metrics")
    sources = parent_report.get("sources")
    records = corpus.get("records")
    screened = screen.get("screened")
    if (
        parent_report.get("schema") != SCHEMA
        or parent_report.get("regressionPassed") is not False
        or parent_report.get("candidateFrozen") is not True
        or not isinstance(false_hashes, list)
        or not false_hashes
        or len(false_hashes) != len(set(false_hashes))
        or not isinstance(metrics, dict)
        or metrics.get("negativeFalseActivations") != len(false_hashes)
        or not isinstance(sources, dict)
        or sources.get("cascadeManifestSha256") != sha256(parent_manifest_path)
        or sources.get("screenCheckpointSha256") != sha256(screen_path)
        or sources.get("corpusManifestSha256") != sha256(corpus_path)
        or sources.get("ffmpegSha256") != sha256(ffmpeg)
        or corpus.get("schema") != CORPUS_SCHEMA
        or not isinstance(records, list)
        or not all(isinstance(record, dict) for record in records)
        or screen.get("schema") != SCREEN_SCHEMA
        or screen.get("completedRecords") != len(records)
        or not isinstance(screened, list)
    ):
        raise ValueError("wake_monotonic_guard_parent_boundary_invalid")
    validate_monotonic_chain(parent_build, child_build)
    parent_config = load_wake_cascade_candidate_config(parent_manifest_path)
    child_config = load_wake_cascade_candidate_config(child_manifest_path)
    if (
        _config_contract(parent_config) != _config_contract(child_config)
        or len(parent_config.verifier_graph_sha256s) != 2
        or len(child_config.verifier_graph_sha256s) != 2
        or parent_config.verifier_graph_sha256s[0]
        != child_config.verifier_graph_sha256s[0]
        or parent_config.verifier_graph_sha256s[1]
        != parent_build["files"]["graph_sha256"]
        or child_config.verifier_graph_sha256s[1]
        != child_build["files"]["graph_sha256"]
    ):
        raise ValueError("wake_monotonic_guard_candidate_contract_mismatch")

    record_indexes = {
        str(record.get("sha256")): index for index, record in enumerate(records)
    }
    if any(value not in record_indexes for value in false_hashes):
        raise ValueError("wake_monotonic_guard_false_hash_missing")
    by_record: dict[int, list[int]] = defaultdict(list)
    for locator in screened:
        if not isinstance(locator, dict):
            raise ValueError("wake_monotonic_guard_screen_invalid")
        record_index = locator.get("record")
        window_index = locator.get("window")
        if not isinstance(record_index, int) or not isinstance(window_index, int):
            raise ValueError("wake_monotonic_guard_screen_invalid")
        if record_index in {record_indexes[value] for value in false_hashes}:
            by_record[record_index].append(window_index)
    if set(by_record) != {record_indexes[value] for value in false_hashes}:
        raise ValueError("wake_monotonic_guard_screen_coverage_invalid")

    exact_path = HERE / "evaluate_baxy_wake_cascade_openslr_exact_parallel_v2.py"
    exact = load_component(exact_path, "_baxy_wake_monotonic_exact_v1")
    corpus_root = Path(str(corpus.get("corpus_root") or "")).resolve(strict=True)
    mel_filters = np.load(
        child_config.mel_filters_path, allow_pickle=False
    ).astype(np.float32)
    started = time.perf_counter()
    targeted: list[dict[str, Any]] = []
    for audio_hash in sorted(false_hashes):
        record_index = record_indexes[audio_hash]
        proposal, false_activation, observed_hash = exact._score_record(
            (record_index, by_record[record_index]),
            records=records,
            corpus_root=corpus_root,
            ffmpeg=ffmpeg,
            config=child_config,
            mel_filters=mel_filters,
        )
        if observed_hash != audio_hash or not proposal or false_activation:
            raise ValueError("wake_monotonic_guard_targeted_rejection_failed")
        targeted.append(
            {
                "audioSha256": audio_hash,
                "exactUpstreamProposal": proposal,
                "childFalseActivation": false_activation,
            }
        )
    targeted_seconds = time.perf_counter() - started
    exposure_hours = float(metrics.get("descriptiveExposureHours") or 0.0)
    if not exposure_hours > 0.0:
        raise ValueError("wake_monotonic_guard_exposure_invalid")
    derived_metrics = dict(metrics)
    derived_metrics.update(
        {
            "strongFalseActivations": 0,
            "negativeFalseActivations": 0,
            "pointFalseActivationsPerHour": 0.0,
            "far95UpperConfidencePerHourIfZero": (
                -math.log(0.05) / exposure_hours
            ),
        }
    )
    report = {
        "schema": SCHEMA,
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "scope": "previously_opened_100h_negative_monotonic_guard_derivation",
        "sources": {
            **sources,
            "cascadeManifestSha256": sha256(child_manifest_path),
            "parentCascadeManifestSha256": sha256(parent_manifest_path),
            "parentExactReportSha256": sha256(parent_report_path),
            "parentVerifierBuildReportSha256": sha256(parent_build_path),
            "childVerifierBuildReportSha256": sha256(child_build_path),
            "derivationSourceSha256": sha256(Path(__file__).resolve()),
            "exactEvaluatorSourceSha256": sha256(exact_path),
        },
        "contract": {
            **dict(parent_report.get("contract") or {}),
            "fullParentExactRegressionConsumed": True,
            "childAcceptanceStrictSubsetByConstruction": True,
            "parentFalseActivationsExactlyRescoredByChild": True,
            "parentFalseActivationCount": len(false_hashes),
            "childAddedGuardCount": len(
                child_build["sources"]["guard_verifier_sha256"]
            )
            - 1,
            "freshHoldoutClaimSupported": False,
            "promotionSupported": False,
        },
        "metrics": derived_metrics,
        "runtime": {
            **dict(parent_report.get("runtime") or {}),
            "targetedChildExactRescoreSeconds": targeted_seconds,
        },
        "parentFalseActivationAudioSha256": sorted(false_hashes),
        "targetedChildExactRecords": targeted,
        "falseActivationAudioSha256": [],
        "regressionPassed": True,
        "candidateDevelopmentUse": True,
        "candidateFrozen": True,
        "negativeCorpusPreviouslyAccessed": True,
        "blindHumanAudioAccessed": False,
        "transcriptsOrFilenamesRetained": False,
        "effectsExecuted": 0,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent-report", type=Path, required=True)
    parser.add_argument("--parent-cascade-manifest", type=Path, required=True)
    parser.add_argument("--child-cascade-manifest", type=Path, required=True)
    parser.add_argument("--parent-verifier-build-report", type=Path, required=True)
    parser.add_argument("--child-verifier-build-report", type=Path, required=True)
    parser.add_argument("--screen-checkpoint", type=Path, required=True)
    parser.add_argument("--corpus-manifest", type=Path, required=True)
    parser.add_argument("--ffmpeg", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    report = derive(parser.parse_args())
    print(
        json.dumps(
            {"passed": report["regressionPassed"], "metrics": report["metrics"]},
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
