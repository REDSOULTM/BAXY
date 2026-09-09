"""Adapter qualification is bound to bytes and cannot leak across model roles."""
import copy
import io
import json

import pytest

from baxy_mind import cpu_prose_adapter as module, llm


@pytest.fixture
def profile(tmp_path, monkeypatch):
    base = tmp_path / "Qwen3-4B-Instruct-2507-Q4_K_M.gguf"
    adapter = tmp_path / "cpu.gguf"
    base.write_bytes(b"base fixture")
    adapter.write_bytes(b"adapter fixture")
    value = {"schema": module.SCHEMA, "gguf": str(adapter),
             "gguf_sha256": module.file_sha256(adapter),
             "base_gguf_sha256": module.file_sha256(base)}
    monkeypatch.setenv(module.ENVIRONMENT_VARIABLE, json.dumps(value))
    return base, adapter, value


def test_unconfigured_model_does_not_load_any_adapter(monkeypatch):
    monkeypatch.delenv(module.ENVIRONMENT_VARIABLE, raising=False)
    assert module.CpuProseAdapter.from_environment(None) is None


def test_valid_profile_resolves_exact_asset_and_base(profile):
    base, adapter, value = profile
    resolved = module.CpuProseAdapter.from_environment(str(base))
    assert resolved.gguf == adapter
    assert resolved.sha256 == value["gguf_sha256"]
    assert resolved.base_sha256 == value["base_gguf_sha256"]


@pytest.mark.parametrize("corruption", ["adapter", "base", "missing", "extra", "schema", "relative"])
def test_unqualified_or_tampered_profile_cannot_start(profile, monkeypatch, corruption):
    base, adapter, value = profile
    if corruption == "adapter":
        adapter.write_bytes(b"changed")
    elif corruption == "base":
        base.write_bytes(b"other model")
    elif corruption == "missing":
        value.pop("base_gguf_sha256")
    elif corruption == "extra":
        value["global"] = True
    elif corruption == "schema":
        value["schema"] = "unknown"
    else:
        value["gguf"] = "cpu.gguf"
    monkeypatch.setenv(module.ENVIRONMENT_VARIABLE, json.dumps(value))
    with pytest.raises(ValueError):
        module.CpuProseAdapter.from_environment(str(base))


def serve(monkeypatch, answers):
    calls = []
    responses = iter(answers)

    def exchange(operation, timeout):
        calls.append((operation, timeout))
        return io.BytesIO(json.dumps(next(responses)).encode())

    monkeypatch.setattr(module.urllib.request, "urlopen", exchange)
    return calls


def test_initial_nonzero_scale_is_reset_and_read_back_before_readiness(profile, monkeypatch):
    base, adapter, _ = profile
    resolved = module.CpuProseAdapter.from_environment(str(base))
    calls = serve(monkeypatch, [[{"id": 0, "path": str(adapter), "scale": 1.0}],
                                {"success": True}, [{"id": 0, "path": str(adapter), "scale": 0.0}]])
    resolved.initialize("http://127.0.0.1:1234", 10)
    assert len(calls) == 3
    assert json.loads(calls[1][0].data) == [{"id": 0, "scale": 0.0}]
    assert all(0 < timeout <= 5 for _, timeout in calls)


@pytest.mark.parametrize("fault", ["different_asset", "multiple_assets", "zero_not_applied"])
def test_server_state_mismatch_is_fatal(profile, monkeypatch, fault):
    base, adapter, _ = profile
    resolved = module.CpuProseAdapter.from_environment(str(base))
    initial = [{"id": 0, "path": str(adapter), "scale": 1.0}]
    if fault == "different_asset":
        initial[0]["path"] += ".other"
    elif fault == "multiple_assets":
        initial *= 2
    serve(monkeypatch, [initial, {"success": True}, initial])
    with pytest.raises(ValueError):
        resolved.initialize("http://127.0.0.1:1234", 10)


def test_adapter_mismatch_is_not_retried_as_a_health_poll(profile, monkeypatch):
    base, _, _ = profile
    monkeypatch.setenv("BAXY_MIND_LLM_ENDPOINT", "http://127.0.0.1:1234")
    monkeypatch.setenv("BAXY_MIND_LLM_GGUF", str(base))

    class Health(io.BytesIO):
        status = 200

    calls = []
    monkeypatch.setattr(llm.urllib.request, "urlopen", lambda *args, **kwargs: Health(b"{}"))

    def reject(self, endpoint, timeout):
        calls.append((endpoint, timeout))
        raise ValueError("wrong adapter")

    monkeypatch.setattr(module.CpuProseAdapter, "initialize", reject)
    client = llm.LlmRuntime()
    try:
        with pytest.raises(ValueError, match="wrong adapter"):
            client._wait_ready(timeout=.05)
        assert len(calls) == 1
        assert 0 < calls[0][1] <= .05
        command = client._server_command()
        assert command.count("--lora") == 1
        assert command[command.index("--lora") + 1] == str(client._cpu_prose_adapter.gguf)
    finally:
        client.close()


def facts(mission=False):
    situation = {"kind": "operation", "operation": "system.status", "observed": {
        "scope": "cpu", "cpu": {"usagePercent": 31.25, "physicalCoreCount": 6,
                                 "logicalProcessorCount": 10, "model": "Example CPU"},
        "failures": [],
    }}
    if mission:
        situation = {"kind": "status", "cause": "mission_completed", "polarity": "success",
                     "steps": [json.dumps(situation)]}
    return {"situation": situation}


@pytest.mark.parametrize("mission", [False, True])
def test_only_cpu_writer_receives_qualified_profile(profile, mission):
    base, _, _ = profile

    class Recorder(llm.LlmRuntime):
        def __init__(self):
            self._gguf = str(base)
            self._cpu_prose_adapter = module.CpuProseAdapter.from_environment(str(base))
            self.payloads = []

        def _post(self, payload):
            self.payloads.append(payload)
            return {"choices": [{"message": {"content": "El uso de CPU es del 31,25%."}, "finish_reason": "stop"}]}

    client = Recorder()
    assert client.compose_user_message("cuánta CPU uso", "status", facts(mission)) == "El uso de CPU es del 31,25%."
    assert len(client.payloads) == 1
    assert client.payloads[0]["lora"] == [{"id": 0, "scale": 1.0}]
    assert client.payloads[0]["temperature"] == .7


@pytest.mark.parametrize("kind,observed,cause", [
    ("status", {}, ""),
    ("status", {"cpu": {}}, ""),
    ("confirmation", {"cpu": {"usagePercent": 10}}, ""),
    ("status", {"cpu": {"usagePercent": 10}}, "acting"),
    ("conversation", {"cpu": {"usagePercent": 10}}, ""),
    ("status", {"processes": [{"cpuPercent": 10}]}, ""),
    ("status", {"cpu": {"usagePercent": 10}, "memory": {"totalBytes": 100}}, ""),
    ("status", {"cpu": {"usagePercent": 10}, "failures": ["sampling failed"]}, ""),
])
def test_other_roles_and_unqualified_observations_do_not_select_adapter(kind, observed, cause):
    assert not module.applies_to_cpu_prose({"kind": kind, "cause": cause}, observed)


def test_transport_defaults_every_other_request_to_zero_without_mutating_it(monkeypatch):
    client = object.__new__(llm.LlmRuntime)
    client._cpu_prose_adapter = object()
    captured = []
    monkeypatch.setattr(llm, "post_chat_completion", lambda payload, **kwargs: captured.append(payload) or {})
    payload = {"messages": [{"role": "user", "content": "¿Cómo te llamas?"}]}
    original = copy.deepcopy(payload)
    client._post(payload)
    assert captured[0]["lora"] == [{"id": 0, "scale": 0.0}]
    assert payload == original
    client._post({**payload, "lora": [{"id": 0, "scale": 1.0}]})
    assert captured[1]["lora"] == [{"id": 0, "scale": 1.0}]
