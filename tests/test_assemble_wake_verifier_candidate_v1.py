from __future__ import annotations

import importlib.util
import json
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "assemble_wake_verifier_candidate_v1.py"
)
SPEC = importlib.util.spec_from_file_location(
    "assemble_wake_verifier_candidate_v1", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_bundle_binds_both_stages_and_long_turn_contract(tmp_path: Path) -> None:
    sources = tmp_path / "sources"
    sources.mkdir()
    stage1 = sources / "stage1.onnx"
    graph = sources / "verifier.onnx"
    data = sources / "verifier.onnx.data"
    vocabulary = sources / "vocab.json"
    stage1.write_bytes(b"stage1")
    graph.write_bytes(b"graph")
    data.write_bytes(b"data")
    vocabulary.write_text("{}", encoding="utf-8")
    output = tmp_path / "candidate"

    report = MODULE.assemble(
        stage1_model=stage1,
        verifier_graph=graph,
        vocabulary=vocabulary,
        output_directory=output,
    )

    verifier = json.loads(
        (output / "baxy-wake-verifier-v1.json").read_text(encoding="utf-8")
    )
    assert verifier["stage1ModelSha256"] == report["assets"][
        "stage1_model_sha256"
    ]
    assert verifier["stage1PreRollSeconds"] == 5.0
    assert verifier["maximumSamples"] == 48_000
    assert verifier["maximumTurnSamples"] == 480_000
    assert verifier["primaryViewStartSamples"] == 64_000
    assert verifier["activityLookbackSamples"] == 2_560
    assert verifier["activityAlignmentSamples"] == 320
    assert verifier["activityVadThreshold"] == 0.1
    assert verifier["decisionMargin"] == 0.3
    assert verifier["calibration"]["approved"] is False
    assert report["candidate_frozen"] is False
