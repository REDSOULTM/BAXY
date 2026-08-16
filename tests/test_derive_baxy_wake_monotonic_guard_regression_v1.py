from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest


def _module():
    path = (
        Path(__file__).resolve().parents[1]
        / "experiments"
        / "voice_latency"
        / "derive_baxy_wake_monotonic_guard_regression_v1.py"
    )
    spec = importlib.util.spec_from_file_location("derive_monotonic", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _parent() -> dict:
    return {
        "schema": "baxy.logmel-guarded-rescue-verifier.v1",
        "sources": {
            "base_verifier_sha256": "base",
            "guard_verifier_sha256": "guard-one",
        },
        "contract": {"deployment_threshold": 3.0, "rescue_threshold": 5.86},
        "files": {"graph_sha256": "parent-graph"},
    }


def _child() -> dict:
    return {
        "schema": "baxy.logmel-guard-chain-rescue-verifier.v2",
        "sources": {
            "base_verifier_sha256": "base",
            "guard_verifier_sha256": ["guard-one", "guard-two"],
        },
        "contract": {
            "deployment_threshold": 3.0,
            "rescue_threshold": 5.86,
            "monotonic_guard_chain": True,
        },
        "files": {"graph_sha256": "child-graph"},
    }


def test_monotonic_chain_requires_parent_guard_as_first_prefix() -> None:
    module = _module()
    assert module.validate_monotonic_chain(_parent(), _child())[2] == [
        "guard-one",
        "guard-two",
    ]

    child = _child()
    child["sources"]["guard_verifier_sha256"].reverse()
    with pytest.raises(ValueError, match="not_subset"):
        module.validate_monotonic_chain(_parent(), child)


def test_monotonic_chain_requires_identical_rescue_boundary() -> None:
    module = _module()
    child = _child()
    child["contract"]["rescue_threshold"] = 5.5
    with pytest.raises(ValueError, match="not_subset"):
        module.validate_monotonic_chain(_parent(), child)
