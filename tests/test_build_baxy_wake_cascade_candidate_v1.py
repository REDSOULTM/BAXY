from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np

from baxy_mind.wake_cascade import load_wake_cascade_candidate_config


def _module():
    script = (
        Path(__file__).resolve().parents[1]
        / "experiments"
        / "voice_latency"
        / "build_baxy_wake_cascade_candidate_v1.py"
    )
    spec = importlib.util.spec_from_file_location("baxy_wake_cascade_builder", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fusion(root: Path, name: str) -> Path:
    root.mkdir()
    graph = root / "graph.onnx"
    graph.write_bytes(name.encode())
    mel = root / "mel.npy"
    np.save(mel, np.ones((80, 201), dtype=np.float32))
    manifest = root / "fusion.json"
    manifest.write_text(
        json.dumps(
            {
                "schema": "baxy-hyperspotter-fusion-v1",
                "aliases": ["baxy", "baxi", "basi", "bakse"],
                "sampleRate": 16000,
                "audioSamples": 48000,
                "logmelFrames": 300,
                "logmelBins": 80,
                "graph": graph.name,
                "graphSha256": _sha(graph),
                "melFilters": mel.name,
                "melFiltersSha256": _sha(mel),
            }
        ),
        encoding="utf-8",
    )
    return manifest


def test_builder_emits_a_hash_valid_non_authoritative_bundle(tmp_path: Path) -> None:
    builder = _module()
    original = _fusion(tmp_path / "original", "original")
    adapted = _fusion(tmp_path / "adapted", "adapted")
    verifier = tmp_path / "verifier.onnx"
    verifier.write_bytes(b"verifier")
    output = tmp_path / "bundle"

    result = builder.build(
        original_fusion=original,
        adapted_fusion=adapted,
        logmel_verifier=verifier,
        output_directory=output,
    )

    manifest = output / "baxy-wake-cascade-v1.json"
    config = load_wake_cascade_candidate_config(manifest)
    assert result["approved"] is False
    assert config.verifier_threshold == 3.0
    assert json.loads(manifest.read_text())["calibration"] == {"approved": False}


def test_builder_uses_the_measured_verifier_threshold(tmp_path: Path) -> None:
    builder = _module()
    original = _fusion(tmp_path / "original", "original")
    adapted = _fusion(tmp_path / "adapted", "adapted")
    verifier = tmp_path / "verifier.onnx"
    verifier.write_bytes(b"verifier")
    output = tmp_path / "bundle"

    builder.build(
        original_fusion=original,
        adapted_fusion=adapted,
        logmel_verifier=verifier,
        output_directory=output,
        logmel_score_threshold=3.1515625,
    )

    config = load_wake_cascade_candidate_config(
        output / "baxy-wake-cascade-v1.json"
    )
    assert config.verifier_threshold == 3.1515625


def test_builder_can_bind_a_measured_single_alias_rescue(tmp_path: Path) -> None:
    builder = _module()
    original = _fusion(tmp_path / "original", "original")
    adapted = _fusion(tmp_path / "adapted", "adapted")
    verifier = tmp_path / "verifier.onnx"
    verifier.write_bytes(b"verifier")
    output = tmp_path / "bundle"

    builder.build(
        original_fusion=original,
        adapted_fusion=adapted,
        logmel_verifier=verifier,
        output_directory=output,
        rescue_alias="basi",
        rescue_logit_threshold=0.3,
    )

    config = load_wake_cascade_candidate_config(
        output / "baxy-wake-cascade-v1.json"
    )
    assert config.rescue_alias_index == 2
    assert config.rescue_alias_threshold == 0.3


def test_builder_can_disable_lexical_rescue(tmp_path: Path) -> None:
    builder = _module()
    original = _fusion(tmp_path / "original", "original")
    adapted = _fusion(tmp_path / "adapted", "adapted")
    verifier = tmp_path / "verifier.onnx"
    verifier.write_bytes(b"verifier")
    output = tmp_path / "bundle"

    builder.build(
        original_fusion=original,
        adapted_fusion=adapted,
        logmel_verifier=verifier,
        output_directory=output,
        lexical_rescue_enabled=False,
    )

    config = load_wake_cascade_candidate_config(
        output / "baxy-wake-cascade-v1.json"
    )
    assert not config.lexical_rescue_enabled
