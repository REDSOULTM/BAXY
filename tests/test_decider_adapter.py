"""The decider's LoRA is bound to bytes, off by default, and on only in the contextual decider's request."""
import json

import pytest

from baxy_mind import cpu_prose_adapter, decider_adapter as module, llm


@pytest.fixture
def profile(tmp_path, monkeypatch):
    base = tmp_path / "Qwen3.5-4B-Q4_K_M.gguf"
    adapter = tmp_path / "decider.gguf"
    base.write_bytes(b"base fixture")
    adapter.write_bytes(b"adapter fixture")
    value = {"schema": module.SCHEMA, "gguf": str(adapter),
             "gguf_sha256": cpu_prose_adapter.file_sha256(adapter),
             "base_gguf_sha256": cpu_prose_adapter.file_sha256(base)}
    monkeypatch.setenv(module.ENVIRONMENT_VARIABLE, json.dumps(value))
    return base, adapter, value


def test_valid_profile_resolves_and_loads_without_applying(profile):
    base, adapter, _ = profile
    resolved = module.DeciderAdapter.from_environment(str(base))
    assert resolved.gguf == adapter
    assert resolved.server_arguments() == ["--lora", str(adapter), "--lora-init-without-apply"]


@pytest.mark.parametrize("corruption", ["adapter", "base", "schema"])
def test_tampered_profile_cannot_start(profile, monkeypatch, corruption):
    base, adapter, value = profile
    if corruption == "adapter":
        adapter.write_bytes(b"changed")
    elif corruption == "base":
        base.write_bytes(b"other model")
    else:
        value["schema"] = cpu_prose_adapter.SCHEMA
    monkeypatch.setenv(module.ENVIRONMENT_VARIABLE, json.dumps(value))
    with pytest.raises(ValueError):
        module.DeciderAdapter.from_environment(str(base))


def test_only_the_decider_request_turns_it_on(profile, monkeypatch):
    base, adapter, _ = profile
    runtime = object.__new__(llm.LlmRuntime)
    runtime._decider_adapter = module.DeciderAdapter.from_environment(str(base))
    runtime._decider_prompt = None
    runtime._normalize_request_budget = lambda timeout: timeout
    sent = []

    def post(payload, timeout=None, **kwargs):
        sent.append(payload)
        content = {"request": "Abre Spotify.", "decision": "action", "operations": ["app.open"], "question": ""}
        return {"choices": [{"message": {"content": json.dumps(content)}}]}

    runtime._post = post
    decided = runtime.decide_in_context("abre spotify", [], [("app.open", "Abre una aplicación.")])
    assert list(decided.operations) == ["app.open"]
    assert sent[0]["lora"] == [{"id": 0, "scale": 1.0}]
