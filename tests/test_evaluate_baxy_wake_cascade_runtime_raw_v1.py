from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pytest


def _module():
    script = (
        Path(__file__).resolve().parents[1]
        / "experiments"
        / "voice_latency"
        / "evaluate_baxy_wake_cascade_runtime_raw_v1.py"
    )
    spec = importlib.util.spec_from_file_location("baxy_wake_runtime_gate", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("samples", [1, 8_000, 32_000, 80_000])
def test_stream_padding_supplies_realistic_left_and_sufficient_tail(
    samples: int,
) -> None:
    gate = _module()
    source = np.ones(samples, dtype=np.float32)
    streamed = gate.stream_audio(source)
    assert np.all(streamed[:16_000] == 0.0)
    assert np.array_equal(streamed[16_000 : 16_000 + samples], source)
    assert len(streamed) >= 48_000
    assert len(streamed) - 16_000 - samples >= 20_000 or len(streamed) == 48_000


def test_group_rejects_unknown_verification_policy() -> None:
    gate = _module()
    with pytest.raises(
        ValueError, match="baxy_wake_cascade_verification_policy_invalid"
    ):
        gate._evaluate_group(
            [],
            detector=object(),
            recognizer=object(),
            block_samples=512,
            verification_policy="unknown",
        )


def test_validation_preregistration_binds_candidate_corpus_and_programs(
    tmp_path: Path,
) -> None:
    gate = _module()
    candidate = tmp_path / "candidate.json"
    candidate.write_text("{}", encoding="utf-8")
    capture_script = tmp_path / "capture.py"
    capture_script.write_text("capture", encoding="utf-8")
    evaluator_script = tmp_path / "evaluator.py"
    evaluator_script.write_text("evaluate", encoding="utf-8")
    program_root = tmp_path / "program"
    program_root.mkdir()
    program_source = program_root / "runtime.py"
    program_source.write_text("runtime", encoding="utf-8")
    gate.ROOT = tmp_path
    gate.PROGRAM_SOURCE_ROOTS = (program_root,)
    gate.CAPTURE_SCRIPT = capture_script
    gate.__file__ = str(evaluator_script)
    stt = tmp_path / "stt"
    stt.mkdir()
    stt_hashes = {}
    for name in gate.STT_FILES:
        path = stt / name
        path.write_text(name, encoding="utf-8")
        stt_hashes[name] = gate.room._sha256(path)
    config = SimpleNamespace(
        upstream_graph_sha256=("a" * 64, "b" * 64),
        mel_filters_sha256="c" * 64,
        verifier_graph_sha256="d" * 64,
    )
    source = {
        "seed": 7,
        "sources": {"positiveRootSha256": "e" * 64, "negativeRootSha256": "f" * 64},
        "counts": {"positive": 48, "negative": 96},
        "physicalPath": {
            "captureTransport": "wasapi_raw_iaudioclient2",
            "rawCaptureHelperSha256": "1" * 64,
            "playbackGain": 0.65,
            "preRollSecondsNotRetained": 0.25,
            "postRollSecondsNotRetained": 0.5,
            "maximumSourceSeconds": 20.0,
            "maximumCaptureAttempts": 6,
            "minimumPathCorrelation": 0.10,
            "minimumCapturedSnrDb": 3.0,
        },
    }
    preregistration = {
        "schema": gate.PREREGISTRATION_SCHEMA,
        "role": "validation",
        "candidateFrozen": True,
        "corpusSelectionFrozen": True,
        "candidate": {
            "manifestSha256": gate.room._sha256(candidate),
            "upstreamGraphSha256": ["a" * 64, "b" * 64],
            "melFiltersSha256": "c" * 64,
            "logmelVerifierSha256": "d" * 64,
        },
        "sourceSelection": {
            "seed": 7,
            "positiveFiles": 48,
            "negativeFiles": 96,
            "positiveRootSha256": "e" * 64,
            "negativeRootSha256": "f" * 64,
        },
        "captureContract": dict(source["physicalPath"]),
        "evaluationContract": {
            "blockSamples": 512,
            "verificationPolicy": "cascade",
            "captureScriptSha256": gate.room._sha256(capture_script),
            "evaluatorScriptSha256": gate.room._sha256(evaluator_script),
            "sttFilesSha256": stt_hashes,
            "programTree": gate.fingerprint_program_tree(
                repository_root=tmp_path,
                source_roots=(program_root,),
            ),
        },
        "blindHumanPartitionAccessed": False,
        "effectsExecuted": 0,
    }
    path = tmp_path / "preregistration.json"
    import json

    path.write_text(json.dumps(preregistration), encoding="utf-8")

    assert gate._validate_preregistration(
        path,
        cascade_manifest=candidate,
        config=config,
        corpus_source=source,
        stt_directory=stt,
        block_samples=512,
        verification_policy="cascade",
    ) == gate.room._sha256(path)

    program_source.write_text("changed after preregistration", encoding="utf-8")
    with pytest.raises(ValueError, match="preregistration_mismatch"):
        gate._validate_preregistration(
            path,
            cascade_manifest=candidate,
            config=config,
            corpus_source=source,
            stt_directory=stt,
            block_samples=512,
            verification_policy="cascade",
        )
    program_source.write_text("runtime", encoding="utf-8")

    source["counts"]["negative"] = 95
    with pytest.raises(ValueError, match="preregistration_mismatch"):
        gate._validate_preregistration(
            path,
            cascade_manifest=candidate,
            config=config,
            corpus_source=source,
            stt_directory=stt,
            block_samples=512,
            verification_policy="cascade",
        )
