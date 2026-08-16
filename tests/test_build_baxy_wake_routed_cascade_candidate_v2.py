from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np

from baxy_mind.wake_cascade import load_wake_cascade_candidate_config


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "build_baxy_wake_routed_cascade_candidate_v2.py"
)
SPEC = importlib.util.spec_from_file_location("routed_builder", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fusion(root: Path, name: str, mel_bytes: bytes) -> Path:
    root.mkdir()
    graph = root / "graph.onnx"
    graph.write_bytes(name.encode())
    mel = root / "mel.npy"
    mel.write_bytes(mel_bytes)
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


def test_builder_binds_two_independent_routes(tmp_path: Path) -> None:
    mel = tmp_path / "canonical-mel.npy"
    np.save(mel, np.ones((80, 201), dtype=np.float32))
    mel_bytes = mel.read_bytes()
    original = _fusion(tmp_path / "original", "original", mel_bytes)
    legacy = _fusion(tmp_path / "legacy", "legacy", mel_bytes)
    expanded = _fusion(tmp_path / "expanded", "expanded", mel_bytes)
    legacy_verifier = tmp_path / "legacy.onnx"
    expanded_verifier = tmp_path / "expanded.onnx"
    legacy_verifier.write_bytes(b"legacy-verifier")
    expanded_verifier.write_bytes(b"expanded-verifier")
    output = tmp_path / "bundle"

    MODULE.build(
        legacy_original_fusion=original,
        legacy_adapted_fusion=legacy,
        expanded_adapted_fusion=expanded,
        legacy_logmel_verifier=legacy_verifier,
        expanded_logmel_verifier=expanded_verifier,
        output_directory=output,
        legacy_logmel_score_threshold=3.0,
        expanded_logmel_score_threshold=3.75,
        rescue_alias="basi",
        rescue_logit_threshold=0.3,
    )

    config = load_wake_cascade_candidate_config(output / "baxy-wake-cascade-v2.json")
    assert len(config.upstream_graph_paths) == 3
    assert len(config.verifier_graph_paths) == 2
    assert [route.name for route in config.routes] == [
        "legacy",
        "expanded_physical",
    ]
    assert config.routes[0].upstream_indexes == (0, 1)
    assert config.routes[0].verifier_threshold == 3.0
    assert config.routes[1].upstream_indexes == (1, 2)
    assert config.routes[1].verifier_threshold == 3.75


def test_builder_can_route_original_candidates_through_expanded_verifier(
    tmp_path: Path,
) -> None:
    mel = tmp_path / "canonical-mel.npy"
    np.save(mel, np.ones((80, 201), dtype=np.float32))
    mel_bytes = mel.read_bytes()
    original = _fusion(tmp_path / "original", "original", mel_bytes)
    legacy = _fusion(tmp_path / "legacy", "legacy", mel_bytes)
    expanded = _fusion(tmp_path / "expanded", "expanded", mel_bytes)
    legacy_verifier = tmp_path / "legacy.onnx"
    expanded_verifier = tmp_path / "expanded.onnx"
    legacy_verifier.write_bytes(b"legacy-verifier")
    expanded_verifier.write_bytes(b"expanded-verifier")
    output = tmp_path / "bundle"

    MODULE.build(
        legacy_original_fusion=original,
        legacy_adapted_fusion=legacy,
        expanded_adapted_fusion=expanded,
        legacy_logmel_verifier=legacy_verifier,
        expanded_logmel_verifier=expanded_verifier,
        output_directory=output,
        legacy_logmel_score_threshold=3.2,
        expanded_logmel_score_threshold=3.75,
        expanded_include_original=True,
    )

    config = load_wake_cascade_candidate_config(output / "baxy-wake-cascade-v2.json")
    assert config.routes[0].upstream_indexes == (0, 1)
    assert config.routes[1].upstream_indexes == (0, 1, 2)


def test_builder_binds_a_direct_verifier_as_lexical_proposal_only(
    tmp_path: Path,
) -> None:
    mel = tmp_path / "canonical-mel.npy"
    np.save(mel, np.ones((80, 201), dtype=np.float32))
    mel_bytes = mel.read_bytes()
    original = _fusion(tmp_path / "original", "original", mel_bytes)
    legacy = _fusion(tmp_path / "legacy", "legacy", mel_bytes)
    expanded = _fusion(tmp_path / "expanded", "expanded", mel_bytes)
    legacy_verifier = tmp_path / "legacy.onnx"
    expanded_verifier = tmp_path / "expanded.onnx"
    direct_verifier = tmp_path / "direct.onnx"
    legacy_verifier.write_bytes(b"legacy-verifier")
    expanded_verifier.write_bytes(b"expanded-verifier")
    direct_verifier.write_bytes(b"direct-verifier")
    output = tmp_path / "bundle"

    MODULE.build(
        legacy_original_fusion=original,
        legacy_adapted_fusion=legacy,
        expanded_adapted_fusion=expanded,
        legacy_logmel_verifier=legacy_verifier,
        expanded_logmel_verifier=expanded_verifier,
        direct_lexical_logmel_verifier=direct_verifier,
        output_directory=output,
        legacy_logmel_score_threshold=3.2,
        expanded_logmel_score_threshold=3.0,
        direct_lexical_logmel_score_threshold=3.0,
        direct_lexical_retry_speed_factors=(0.85, 1.14),
        direct_lexical_phonetic_confusion_score_gte=4.0,
        endpoint_lexical_score_threshold=-1.0,
        endpoint_lexical_retry_speed_factors=(0.85, 1.14),
        expanded_include_original=True,
    )

    config = load_wake_cascade_candidate_config(output / "baxy-wake-cascade-v2.json")
    assert len(config.verifier_graph_paths) == 3
    assert config.direct_lexical_verifier_index == 2
    assert config.direct_lexical_verifier_threshold == 3.0
    assert config.direct_lexical_retry_speed_factors == (0.85, 1.14)
    assert config.direct_lexical_hotwords_score == 5.0
    assert config.direct_lexical_minimum_consecutive_hops == 4
    assert config.direct_lexical_phonetic_confusion_score_gte == 4.0
    assert config.endpoint_lexical_verifier_index == 2
    assert config.endpoint_lexical_score_threshold == -1.0
    assert config.endpoint_lexical_retry_speed_factors == (0.85, 1.14)
    assert config.endpoint_lexical_aliases == frozenset(
        ("baxy", "baxi", "bakse", "backsy", "boxy")
    )
    assert all(route.verifier_index != 2 for route in config.routes)
