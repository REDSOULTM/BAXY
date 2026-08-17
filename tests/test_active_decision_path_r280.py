"""R280: the forced tool-choice path is attributed to the model that reaches it.

R280 audited a gate that no longer exists. It asked which decision path the
*registered* model reached, and answered it by parsing the literal that
``llm.py`` tested the GGUF filename against: a model called ``qwen3`` got the
forced ``tool_choice: "required"`` contract and anything else did not.

Goal 03 priced that contract on a fresh paraphrase population with Qwen3-4B on
both sides — +3 correct raw decisions of 124, −8 honest abstentions of 36 — and
turned it off for every model, which removed the filename test R280 read. The
audit is therefore consumed evidence about a tree this one no longer is: §7
applies, and it is verified by its seal instead of regenerated.

What still has to hold is the reasoning R280 published, which never depended on
that literal, plus the contract that replaced it.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from sealed_evidence import assert_sealed

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments/mind_router_spike/audit_active_decision_path_r280.py"
ARTIFACT = ROOT / "artifacts/audit/active_decision_path_r280.json"
R280_ARTIFACT_SHA256 = (
    "37210507e43d15486056bead835631acb74c11f26768d35701caa04db7f2eed3"
)


def _module():
    spec = importlib.util.spec_from_file_location("r280", SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_r280_published_reading_is_sealed_against_silent_change() -> None:
    assert_sealed(ARTIFACT, R280_ARTIFACT_SHA256)
    published = json.loads(ARTIFACT.read_text(encoding="utf-8"))

    assert published["verdict"] == (
        "forced_tool_choice_path_not_reached_by_the_registered_model"
    )
    assert published["gate"]["filenameTokenRequired"] == "qwen3"
    assert published["constraints"]["effects_executed"] == 0
    assert published["constraints"]["opened_v9"] is False


def test_r280_keeps_the_v8_pricing_and_withdraws_the_r276_attribution() -> None:
    published = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    correction = published["correctsR277"]

    assert correction["v8PricingStillValid"] is True
    assert correction["r276UnsolicitedEffectsExplainedByForcedToolChoice"] is False


def test_the_filename_no_longer_decides_the_decision_contract() -> None:
    """The literal R280 read is gone, and nothing replaced it with another one.

    A model's filename deciding which decision contract runs is what let R276
    and V8 be compared as if they had measured the same product. The forced
    path is now off by default for every model and only an explicit override
    turns it on, so no name in a path can change what BAXY does.
    """

    source = (ROOT / "src/baxy_mind/llm.py").read_text(encoding="utf-8")
    module = _module()

    assert module._gate_token_from_source(ROOT) is None
    assert 'gguf and "qwen3" in Path(gguf).name.casefold()' not in source
    assert "self._native_tool_policy_enabled = False" in source
