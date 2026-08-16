from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


def _module():
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "preregister_wake_cascade_physical_validation.py"
    )
    spec = importlib.util.spec_from_file_location(
        "wake_cascade_physical_preregistration", script
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_preregistration_binds_every_routed_verifier() -> None:
    module = _module()

    class Config:
        upstream_graph_sha256 = ("a" * 64, "b" * 64, "c" * 64)
        mel_filters_sha256 = "d" * 64
        verifier_graph_sha256 = "e" * 64
        verifier_graph_sha256s = ("e" * 64, "f" * 64)

    assert module._candidate_assets(Config(), "0" * 64) == {
        "manifestSha256": "0" * 64,
        "upstreamGraphSha256": ["a" * 64, "b" * 64, "c" * 64],
        "melFiltersSha256": "d" * 64,
        "logmelVerifierSha256": ["e" * 64, "f" * 64],
    }


def test_hybrid_preregistration_programs_are_versioned() -> None:
    module = _module()

    assert module.ENDPOINT_EVALUATOR_SCRIPT.name == (
        "evaluate_baxy_endpoint_voice_runtime_v1.py"
    )
    assert module.FUSION_SCRIPT.name == "fuse_baxy_cascade_endpoint_reports_v1.py"
    assert module.ENDPOINT_EVALUATOR_SCRIPT.is_file()
    assert module.FUSION_SCRIPT.is_file()
