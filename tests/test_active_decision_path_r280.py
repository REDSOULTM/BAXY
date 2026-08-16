"""R280: the forced tool-choice path is attributed to the model that reaches it."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments/mind_router_spike/audit_active_decision_path_r280.py"


def _module():
    spec = importlib.util.spec_from_file_location("r280", SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_r280_reads_the_gate_literal_from_the_runtime_itself() -> None:
    module = _module()
    # The token is parsed out of llm.py, not hardcoded in the audit's verdict.
    assert module._gate_token_from_source(ROOT) == "qwen3"


def test_r280_reports_the_path_off_for_a_gemma_manifest(tmp_path) -> None:
    module = _module()
    manifest = tmp_path / "mind-runtime-v1.json"
    manifest.write_text(
        json.dumps({"gguf": "C:/models/gemma-4-E2B-it-qat-UD-Q4_K_XL.gguf"}),
        encoding="utf-8",
    )

    result = module.build(ROOT, manifest_path=manifest)
    assert result["gate"]["nativeToolPolicyEnabled"] is False
    assert result["gate"]["toolChoiceSentByRegisteredRuntime"] is False
    assert result["verdict"] == (
        "forced_tool_choice_path_not_reached_by_the_registered_model"
    )


def test_r280_reports_the_path_on_for_a_qwen3_manifest(tmp_path) -> None:
    module = _module()
    manifest = tmp_path / "mind-runtime-v1.json"
    manifest.write_text(
        json.dumps({"gguf": "C:/models/qwen3-4b-instruct-q4_k_m.gguf"}),
        encoding="utf-8",
    )

    result = module.build(ROOT, manifest_path=manifest)
    assert result["gate"]["nativeToolPolicyEnabled"] is True
    assert result["verdict"] == "forced_tool_choice_path_active"


def test_r280_keeps_the_v8_pricing_and_withdraws_the_r276_attribution(tmp_path) -> None:
    module = _module()
    manifest = tmp_path / "mind-runtime-v1.json"
    manifest.write_text(
        json.dumps({"gguf": "C:/models/gemma-4-E2B.gguf"}), encoding="utf-8"
    )

    correction = module.build(ROOT, manifest_path=manifest)["correctsR277"]
    assert correction["v8PricingStillValid"] is True
    assert correction["r276UnsolicitedEffectsExplainedByForcedToolChoice"] is False
