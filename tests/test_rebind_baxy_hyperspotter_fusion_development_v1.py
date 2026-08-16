from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "rebind_baxy_hyperspotter_fusion_development_v1.py"
)
SPEC = importlib.util.spec_from_file_location(
    "rebind_baxy_hyperspotter_fusion_development_v1", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_bundle(root: Path) -> tuple[Path, Path]:
    root.mkdir()
    graph = root / "model.onnx"
    graph.write_bytes(b"unchanged-development-graph")
    mel = root / "mel.npy"
    np.save(mel, np.ones((80, 201), dtype=np.float32), allow_pickle=False)
    old_ctc = root / "old-ctc.json"
    old_ctc.write_text(
        json.dumps({"schema": "baxy-wake-verifier-v1"}), encoding="utf-8"
    )
    manifest = root / "baxy-hyperspotter-fusion-v1.json"
    manifest.write_text(
        json.dumps(
            {
                "schema": "baxy-hyperspotter-fusion-v1",
                "backend": "onnxruntime-hyperspotter-fixed-aliases-plus-phoneme-ctc",
                "graph": graph.name,
                "graphSha256": digest(graph),
                "graphBytes": graph.stat().st_size,
                "melFilters": mel.name,
                "melFiltersSha256": digest(mel),
                "melFiltersShape": [80, 201],
                "aliases": ["baxy", "baxi", "basi", "bakse"],
                "sampleRate": 16000,
                "audioSamples": 48000,
                "logmelFrames": 300,
                "logmelBins": 80,
                "policy": {
                    "ctc_feature": "full_clip_margin",
                    "ctc_center": 1.0,
                    "ctc_scale": 2.0,
                    "ctc_weight": 1.0,
                    "decision_threshold": 3.0,
                },
                "ctcVerifierManifestSha256": digest(old_ctc),
                "approved": False,
                "developmentOnly": True,
                "blindHumanAudioAccessed": False,
                "effectsExecuted": 0,
            }
        ),
        encoding="utf-8",
    )
    return manifest, graph


def test_rebind_preserves_assets_and_binds_only_the_new_ctc(tmp_path: Path) -> None:
    source, graph = source_bundle(tmp_path / "source")
    new_ctc = tmp_path / "new-ctc.json"
    new_ctc.write_text(
        json.dumps({"schema": "baxy-wake-verifier-v1", "candidate": "new"}),
        encoding="utf-8",
    )
    output = tmp_path / "output"

    report = MODULE.rebind(
        source_manifest_path=source,
        ctc_manifest_path=new_ctc,
        output_directory=output,
    )

    rebound = json.loads(
        (output / "baxy-hyperspotter-fusion-v1.json").read_text(encoding="utf-8")
    )
    assert rebound["ctcVerifierManifestSha256"] == digest(new_ctc)
    assert rebound["graphSha256"] == digest(graph)
    assert rebound["developmentRebind"]["graphChanged"] is False
    assert rebound["developmentRebind"]["policyChanged"] is False
    assert report["candidateFrozen"] is False
    assert digest(output / graph.name) == digest(graph)


def test_rebind_rejects_a_tampered_source_asset(tmp_path: Path) -> None:
    source, graph = source_bundle(tmp_path / "source")
    graph.write_bytes(b"tampered")
    new_ctc = tmp_path / "new-ctc.json"
    new_ctc.write_text(
        json.dumps({"schema": "baxy-wake-verifier-v1"}), encoding="utf-8"
    )

    with pytest.raises(ValueError, match="source_hash_mismatch"):
        MODULE.rebind(
            source_manifest_path=source,
            ctc_manifest_path=new_ctc,
            output_directory=tmp_path / "output",
        )
