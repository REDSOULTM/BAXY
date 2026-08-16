from __future__ import annotations

import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys

import numpy as np
import pytest

from baxy_mind.wake_cascade import (
    CALIBRATION_REPORT_FILENAME,
    load_wake_cascade_candidate_config,
    load_wake_cascade_config,
)


def _module():
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "promote_wake_cascade_candidate.py"
    )
    spec = importlib.util.spec_from_file_location("wake_cascade_promotion", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _candidate(tmp_path: Path) -> tuple[Path, dict[str, object]]:
    upstream = []
    for index in range(2):
        graph = tmp_path / f"upstream-{index}.onnx"
        graph.write_bytes(f"graph-{index}".encode())
        upstream.append({"graph": graph.name, "graphSha256": _sha(graph)})
    verifier = tmp_path / "verifier.onnx"
    verifier.write_bytes(b"verifier")
    filters = tmp_path / "mel.npy"
    np.save(filters, np.ones((80, 201), dtype=np.float32))
    payload: dict[str, object] = {
        "schema": "baxy-wake-cascade-v1",
        "backend": "onnxruntime-hyperspotter-logmel-cascade",
        "phrase": "Baxy",
        "sampleRate": 16000,
        "windowSamples": 48000,
        "hopSamples": 4000,
        "historyWindows": 20,
        "debounceSeconds": 2.0,
        "primaryLogitGte": 0.5,
        "secondaryLogitGte": 0.3,
        "acousticAliases": ["baxy", "baxi", "basi", "bakse"],
        "lexicalAliases": ["baxy", "baxi", "boxy"],
        "upstreamModels": upstream,
        "melFilters": filters.name,
        "melFiltersSha256": _sha(filters),
        "logmelVerifier": {
            "graph": verifier.name,
            "graphSha256": _sha(verifier),
            "scoreGte": 3.0,
        },
        "calibration": {"approved": False},
        "approved": False,
        "developmentOnly": True,
        "effectsExecuted": 0,
    }
    path = tmp_path / "candidate.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path, payload


def _routed_candidate(tmp_path: Path) -> tuple[Path, dict[str, object]]:
    upstream = []
    for index in range(3):
        graph = tmp_path / f"routed-upstream-{index}.onnx"
        graph.write_bytes(f"routed-graph-{index}".encode())
        upstream.append({"graph": graph.name, "graphSha256": _sha(graph)})
    verifiers = []
    for index in range(2):
        graph = tmp_path / f"routed-verifier-{index}.onnx"
        graph.write_bytes(f"routed-verifier-{index}".encode())
        verifiers.append(
            {"graph": graph.name, "graphSha256": _sha(graph), "scoreGte": 3.0}
        )
    filters = tmp_path / "routed-mel.npy"
    np.save(filters, np.ones((80, 201), dtype=np.float32))
    payload: dict[str, object] = {
        "schema": "baxy-wake-cascade-v2",
        "backend": "onnxruntime-hyperspotter-logmel-cascade",
        "phrase": "Baxy",
        "sampleRate": 16000,
        "windowSamples": 48000,
        "hopSamples": 4000,
        "historyWindows": 20,
        "debounceSeconds": 2.0,
        "primaryLogitGte": 0.5,
        "secondaryLogitGte": 0.3,
        "acousticAliases": ["baxy", "baxi", "basi", "bakse"],
        "lexicalAliases": ["baxy", "baxi", "boxy"],
        "lexicalRescueEnabled": False,
        "upstreamModels": upstream,
        "melFilters": filters.name,
        "melFiltersSha256": _sha(filters),
        "logmelVerifiers": verifiers,
        "routes": [
            {"name": "legacy", "upstreamModelIndexes": [0, 1], "verifierIndex": 0},
            {"name": "expanded", "upstreamModelIndexes": [0, 1, 2], "verifierIndex": 1},
        ],
        "calibration": {"approved": False},
        "approved": False,
        "developmentOnly": True,
        "effectsExecuted": 0,
    }
    path = tmp_path / "routed-candidate.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path, payload


def _evidence(candidate: Path, config) -> tuple[dict, dict]:
    assets = {
        "cascadeManifestSha256": _sha(candidate),
        "upstreamGraphSha256": list(config.upstream_graph_sha256),
        "melFiltersSha256": config.mel_filters_sha256,
        "logmelVerifierSha256": (
            list(config.verifier_graph_sha256s)
            if len(config.verifier_graph_sha256s) > 1
            else config.verifier_graph_sha256
        ),
    }
    physical = {
        "schema": "baxy.wake-cascade-runtime-raw-development.v1",
        "scope": "exact_production_stream_api_opened_wasapi_raw",
        "role": "validation",
        "assets": assets,
        "positive": {"files": 48, "acceptedFiles": 48},
        "negative": {"files": 96, "acceptedFiles": 0},
        "openedCorpusPassed": True,
        "candidateFrozen": True,
        "corpusFrozen": True,
        "blindHumanPartitionAccessed": False,
        "promotable": True,
        "effectsExecuted": 0,
        "filenamesOrTranscriptsRetained": False,
    }
    hours = 100.59087965277777
    negative = {
        "schema": "baxy.wake-cascade-openslr-negative-regression.v1",
        "scope": "previously_opened_100h_negative_development_regression",
        "sources": {"cascadeManifestSha256": _sha(candidate)},
        "contract": {
            "everyBroadCandidateRescoredByExactCpuOnnx": True,
            "lexicalRescueEnabled": True,
            "lexicalRescueUsesProductParakeet": True,
        },
        "metrics": {
            "utterances": 28539,
            "descriptiveExposureHours": hours,
            "negativeFalseActivations": 0,
            "lexicalInvocations": 28539,
            "far95UpperConfidencePerHourIfZero": -math.log(0.05) / hours,
        },
        "regressionPassed": True,
        "candidateFrozen": True,
        "blindHumanAudioAccessed": False,
        "transcriptsOrFilenamesRetained": False,
        "effectsExecuted": 0,
    }
    return physical, negative


def test_promotion_output_is_accepted_by_product_loader(tmp_path: Path) -> None:
    module = _module()
    candidate, candidate_payload = _candidate(tmp_path)
    config = load_wake_cascade_candidate_config(candidate)
    physical, negative = _evidence(candidate, config)
    report, promoted = module.build_payloads(
        candidate_payload=candidate_payload,
        candidate_hash=_sha(candidate),
        config=config,
        physical_payload=physical,
        physical_hash="a" * 64,
        negative_payload=negative,
        negative_hash="b" * 64,
    )
    report_path = tmp_path / CALIBRATION_REPORT_FILENAME
    report_path.write_text(json.dumps(report), encoding="utf-8")
    promoted["calibration"]["reportSha256"] = _sha(report_path)
    manifest_path = tmp_path / "promoted.json"
    manifest_path.write_text(json.dumps(promoted), encoding="utf-8")

    loaded = load_wake_cascade_config(manifest_path)
    assert loaded.calibration["approved"] is True
    assert report["metrics"]["positiveAcceptedFiles"] == 48
    assert report["metrics"]["negativeFalseActivations"] == 0


def test_promotion_rejects_a_physical_false_activation(tmp_path: Path) -> None:
    module = _module()
    candidate, candidate_payload = _candidate(tmp_path)
    config = load_wake_cascade_candidate_config(candidate)
    physical, negative = _evidence(candidate, config)
    physical["negative"]["acceptedFiles"] = 1

    with pytest.raises(module.PromotionError, match="physical_validation_failed"):
        module.build_payloads(
            candidate_payload=candidate_payload,
            candidate_hash=_sha(candidate),
            config=config,
            physical_payload=physical,
            physical_hash="a" * 64,
            negative_payload=negative,
            negative_hash="b" * 64,
        )


def test_routed_promotion_binds_every_verifier(tmp_path: Path) -> None:
    module = _module()
    candidate, candidate_payload = _routed_candidate(tmp_path)
    config = load_wake_cascade_candidate_config(candidate)
    physical, negative = _evidence(candidate, config)
    negative["contract"]["lexicalRescueEnabled"] = False
    negative["contract"]["lexicalRescueUsesProductParakeet"] = False
    negative["metrics"]["lexicalInvocations"] = 0

    report, promoted = module.build_payloads(
        candidate_payload=candidate_payload,
        candidate_hash=_sha(candidate),
        config=config,
        physical_payload=physical,
        physical_hash="a" * 64,
        negative_payload=negative,
        negative_hash="b" * 64,
    )
    assert report["assets"]["logmelVerifierSha256"] == list(
        config.verifier_graph_sha256s
    )
    report_path = tmp_path / CALIBRATION_REPORT_FILENAME
    report_path.write_text(json.dumps(report), encoding="utf-8")
    promoted["calibration"]["reportSha256"] = _sha(report_path)
    manifest_path = tmp_path / "routed-promoted.json"
    manifest_path.write_text(json.dumps(promoted), encoding="utf-8")
    assert load_wake_cascade_config(manifest_path).calibration["approved"] is True


def test_promotion_rejects_evidence_for_another_candidate(tmp_path: Path) -> None:
    module = _module()
    candidate, candidate_payload = _candidate(tmp_path)
    config = load_wake_cascade_candidate_config(candidate)
    physical, negative = _evidence(candidate, config)
    negative["sources"]["cascadeManifestSha256"] = "c" * 64

    with pytest.raises(module.PromotionError, match="negative_regression_failed"):
        module.build_payloads(
            candidate_payload=candidate_payload,
            candidate_hash=_sha(candidate),
            config=config,
            physical_payload=physical,
            physical_hash="a" * 64,
            negative_payload=negative,
            negative_hash="b" * 64,
        )


def test_promotion_accepts_a_zero_lexical_rescue_candidate(tmp_path: Path) -> None:
    module = _module()
    candidate, candidate_payload = _candidate(tmp_path)
    candidate_payload["lexicalRescueEnabled"] = False
    candidate.write_text(json.dumps(candidate_payload), encoding="utf-8")
    config = load_wake_cascade_candidate_config(candidate)
    physical, negative = _evidence(candidate, config)
    negative["contract"]["lexicalRescueEnabled"] = False
    negative["contract"]["lexicalRescueUsesProductParakeet"] = False
    negative["metrics"]["lexicalInvocations"] = 0

    report, _ = module.build_payloads(
        candidate_payload=candidate_payload,
        candidate_hash=_sha(candidate),
        config=config,
        physical_payload=physical,
        physical_hash="a" * 64,
        negative_payload=negative,
        negative_hash="b" * 64,
    )
    assert report["metrics"]["negativeFalseActivations"] == 0
