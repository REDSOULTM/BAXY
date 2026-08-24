"""R281: a silent model swap must turn this red instead of passing unnoticed."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments/mind_router_spike/attest_registered_runtime_r281.py"
EXPECTATION = ROOT / "artifacts/runtime/registered_runtime_expectation_r281.json"


def _module():
    spec = importlib.util.spec_from_file_location("r281", SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_expectation_is_published_and_names_a_model() -> None:
    published = json.loads(EXPECTATION.read_text(encoding="utf-8"))
    assert published["schema"] == "baxy.registered-runtime-expectation.r281.v1"
    # The declaration carries the schema it was written against, so a schema
    # change cannot pass as a missing field.
    assert published["manifestIsVersioned"] is True
    assert published["manifestSchema"] == "baxy-mind-runtime-v1"
    expected = published["expected"]
    assert expected is not None
    assert expected["ggufName"]
    assert expected["ggufSha256"]


def test_local_manifest_matches_the_published_expectation() -> None:
    module = _module()
    manifest = module.read_manifest()
    if manifest is None:
        pytest.skip("no registered runtime manifest on this machine")

    published = json.loads(EXPECTATION.read_text(encoding="utf-8"))
    observed = module.describe(manifest)

    # A schema change or a binary swap changes these; the tree must not stay
    # silent about either.
    assert module.manifest_schema(manifest) == published["manifestSchema"]
    assert observed["ggufName"] == published["expected"]["ggufName"]
    assert observed["ggufSha256"] == published["expected"]["ggufSha256"]
    assert observed["llamaServerName"] == published["expected"]["llamaServerName"]
    assert observed["llamaServerSha256"] == published["expected"]["llamaServerSha256"]
    assert (
        observed["nativeToolPolicyEnabled"]
        == published["expected"]["nativeToolPolicyEnabled"]
    )
    assert observed["sttSha256"] == published["expected"]["sttSha256"]
    assert observed.get("ttsSha256") == published["expected"].get("ttsSha256")
    assert published["expected"]["wakeManifestSha256"]
    assert observed["wakeManifestSha256"] == published["expected"]["wakeManifestSha256"]
    assert observed["wakeName"] == published["expected"]["wakeName"]


def test_a_manifest_without_a_schema_is_not_versioned() -> None:
    module = _module()
    assert module.manifest_schema({"schema": "baxy-mind-runtime-v1"}) == (
        "baxy-mind-runtime-v1"
    )
    assert module.manifest_schema({"gguf": "C:/m/model.gguf"}) is None
    assert module.manifest_schema(None) is None


def test_the_native_tool_policy_flag_no_longer_tracks_the_model_name() -> None:
    """No filename turns the forced tool-call contract on.

    It used to: a GGUF whose name contained ``qwen3`` got
    ``tool_choice: "required"``, which is why R276 and V8 were not measuring the
    same product. Goal 03 priced that contract on a fresh paraphrase population
    -- +3 correct raw decisions of 124 against -8 honest abstentions of 36 --
    and turned it off. Forcing a tool call when none of them serves is the
    unsolicited effect BAXY does not allow.
    """

    module = _module()
    gemma = module.describe({"gguf": "C:/m/gemma-4-E2B-it-qat-UD-Q4_K_XL.gguf"})
    qwen = module.describe({"gguf": "C:/m/qwen3-4b-instruct-q4_k_m.gguf"})

    assert gemma["nativeToolPolicyEnabled"] is False
    assert qwen["nativeToolPolicyEnabled"] is False


def test_the_expectation_records_identity_not_machine_paths() -> None:
    published = EXPECTATION.read_text(encoding="utf-8")
    # Absolute local paths would make the record unusable on any other machine.
    assert "C:\\\\" not in published
    assert "LOCALAPPDATA" not in published.replace("%LOCALAPPDATA%", "")
