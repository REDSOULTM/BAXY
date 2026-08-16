from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments/mind_router_spike/probe_runtime_manifest_r222.py"
ARTIFACT = ROOT / "artifacts/audit/runtime_manifest_preflight_r222.json"


def _module():
    spec = importlib.util.spec_from_file_location("r222", SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_r222_publishes_only_read_only_runtime_identity() -> None:
    report = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    assert report["outcome"]["resolved"] is False
    assert report["outcome"]["error"] == "hash SHA-256 no coincide: stt_dir"
    assert report["constraints"]["model_started"] is False
    assert "tts_model" in report["manifest"]["keys"]


def test_r222_instrument_never_starts_a_model() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    assert "LlmRuntime" not in source
    assert "turn.decide" not in source
