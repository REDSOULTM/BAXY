from __future__ import annotations

import importlib.util
import hashlib
import json
import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "measure_mind_budget.py"
SPEC = importlib.util.spec_from_file_location("measure_mind_budget", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
gate = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = gate
SPEC.loader.exec_module(gate)


def test_workload_uses_only_the_current_public_protocol() -> None:
    workload = gate.build_workload()

    assert len(workload) == 45
    assert {item.request_type for item in workload} == {
        "turn.decide",
        "arguments",
        "narrate",
    }
    assert all(item.message["type"] == item.request_type for item in workload)
    assert all(item.message["type"] != "route" for item in workload)
    assert {item.expected_reply_type for item in workload} == {
        "turn.result",
        "arguments.result",
        "narrate.result",
    }
    assert all(
        not str(item.message.get("operation") or "").startswith("memory.")
        for item in workload
    )


def test_runtime_identity_attests_components_without_disclosing_paths(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "private-user-directory"
    python = runtime_root / "venv" / "python.exe"
    python_path = runtime_root / "source"
    mind = python_path / "baxy_mind"
    gguf = runtime_root / "models" / "winner.gguf"
    server = runtime_root / "llama" / "llama-server.exe"
    stt = runtime_root / "stt"
    for directory in (python.parent, mind, gguf.parent, server.parent, stt):
        directory.mkdir(parents=True, exist_ok=True)
    python.write_bytes(b"python")
    (mind / "__main__.py").write_text("", encoding="utf-8")
    gguf.write_bytes(b"gguf")
    server.write_bytes(b"server")
    stt_files = (
        "encoder.int8.onnx",
        "decoder.int8.onnx",
        "joiner.int8.onnx",
        "tokens.txt",
    )
    for name in stt_files:
        (stt / name).write_bytes(name.encode("utf-8"))

    def sha256(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    stt_fingerprint = "".join(f"{name}:{sha256(stt / name)}\n" for name in stt_files)
    manifest = runtime_root / "mind-runtime-v1.json"
    manifest.write_text(
        json.dumps(
            {
                "schema": "baxy-mind-runtime-v1",
                "python": str(python),
                "python_sha256": sha256(python),
                "python_path": str(python_path),
                "gguf": str(gguf),
                "gguf_sha256": sha256(gguf),
                "llama_server": str(server),
                "llama_server_sha256": sha256(server),
                "stt_dir": str(stt),
                "stt_sha256": hashlib.sha256(stt_fingerprint.encode()).hexdigest(),
                "wake_manifest": None,
                "wake_manifest_sha256": None,
                "ngl": 42,
                "wake_on_start": False,
            }
        ),
        encoding="utf-8",
    )

    resolved = gate.resolve_runtime(manifest_path=manifest)
    public = gate.public_runtime_identity(resolved)
    serialized = json.dumps(public)

    assert resolved.source == "registered_manifest"
    assert public["profiles"]["gpu_layers"] == 42
    assert public["gguf"]["name"] == "winner.gguf"
    assert str(runtime_root) not in serialized
    assert "private-user-directory" not in serialized


def test_runtime_accepts_and_attests_an_authenticated_optional_tts_model(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "private-user-directory"
    python = runtime_root / "venv" / "python.exe"
    python_path = runtime_root / "source"
    gguf = runtime_root / "models" / "winner.gguf"
    server = runtime_root / "llama" / "llama-server.exe"
    stt = runtime_root / "stt"
    tts = runtime_root / "tts" / "voice.onnx"
    for directory in (
        python.parent,
        python_path / "baxy_mind",
        gguf.parent,
        server.parent,
        stt,
        tts.parent,
    ):
        directory.mkdir(parents=True, exist_ok=True)
    python.write_bytes(b"python")
    (python_path / "baxy_mind" / "__main__.py").write_text("", encoding="utf-8")
    gguf.write_bytes(b"gguf")
    server.write_bytes(b"server")
    tts.write_bytes(b"tts")
    stt_files = (
        "encoder.int8.onnx",
        "decoder.int8.onnx",
        "joiner.int8.onnx",
        "tokens.txt",
    )
    for name in stt_files:
        (stt / name).write_bytes(name.encode("utf-8"))

    def sha256(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    stt_fingerprint = "".join(f"{name}:{sha256(stt / name)}\n" for name in stt_files)
    manifest = runtime_root / "mind-runtime-v1.json"
    manifest.write_text(
        json.dumps(
            {
                "schema": "baxy-mind-runtime-v1",
                "python": str(python),
                "python_sha256": sha256(python),
                "python_path": str(python_path),
                "gguf": str(gguf),
                "gguf_sha256": sha256(gguf),
                "llama_server": str(server),
                "llama_server_sha256": sha256(server),
                "stt_dir": str(stt),
                "stt_sha256": hashlib.sha256(stt_fingerprint.encode()).hexdigest(),
                "wake_manifest": None,
                "wake_manifest_sha256": None,
                "ngl": 42,
                "wake_on_start": False,
                "tts_model": str(tts),
                "tts_sha256": sha256(tts),
            }
        ),
        encoding="utf-8",
    )

    assert gate.resolve_runtime(manifest_path=manifest).source == "registered_manifest"


def test_runtime_accepts_current_per_file_stt_identity(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    python = runtime_root / "venv" / "python.exe"
    python_path = runtime_root / "source"
    gguf = runtime_root / "model.gguf"
    server = runtime_root / "llama-server.exe"
    stt = runtime_root / "stt"
    for directory in (python.parent, python_path / "baxy_mind", stt):
        directory.mkdir(parents=True, exist_ok=True)
    python.write_bytes(b"python")
    (python_path / "baxy_mind" / "__main__.py").write_text("", encoding="utf-8")
    gguf.write_bytes(b"gguf")
    server.write_bytes(b"server")
    stt_files = (
        "encoder.int8.onnx",
        "decoder.int8.onnx",
        "joiner.int8.onnx",
        "tokens.txt",
    )
    for name in stt_files:
        (stt / name).write_bytes(name.encode("utf-8"))

    def sha256(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    manifest = runtime_root / "mind-runtime-v1.json"
    manifest.write_text(
        json.dumps(
            {
                "schema": "baxy-mind-runtime-v1",
                "python": str(python),
                "python_sha256": sha256(python),
                "python_path": str(python_path),
                "gguf": str(gguf),
                "gguf_sha256": sha256(gguf),
                "llama_server": str(server),
                "llama_server_sha256": sha256(server),
                "stt_dir": str(stt),
                "stt_sha256": {name: sha256(stt / name) for name in stt_files},
                "ngl": 42,
                "wake_on_start": False,
            }
        ),
        encoding="utf-8",
    )

    assert gate.resolve_runtime(manifest_path=manifest).source == "registered_manifest"


def test_profile_deadlines_match_the_real_desktop_transport() -> None:
    gpu = gate.PROFILE_LIMITS["gpu"]
    cpu = gate.PROFILE_LIMITS["cpu_fallback"]

    for profile in (gpu, cpu):
        assert profile["handshake"] == 120.0
        assert profile["turn.decide"] == 22.0
        assert profile["arguments"] == 20.0
        assert "chat" not in profile
    assert gpu["narrate"] == 20.0
    assert gpu["llm_http"] == 19.0
    assert cpu["narrate"] == 130.0
    assert cpu["llm_http"] == 120.0


def test_profile_http_deadline_is_the_product_contract_not_a_gate_constant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The gate must measure the deadline the product really grants.

    The CPU profile once inherited the GPU 19-second llama-server timeout and
    failed a valid 12.4-second answer. Binding both profiles to
    ``_request_timeout_from_env`` keeps the gate from drifting away from the
    shipped contract again, in either direction.
    """

    from baxy_mind.llm import _request_timeout_from_env

    for profile_name, gpu_layers in (("gpu", 99), ("cpu_fallback", 0)):
        monkeypatch.setenv("BAXY_MIND_NGL", str(gpu_layers))
        monkeypatch.delenv("BAXY_MIND_LLM_REQUEST_TIMEOUT", raising=False)
        product_default = _request_timeout_from_env()
        gate_deadline = gate.PROFILE_LIMITS[profile_name]["llm_http"]

        assert gate_deadline == product_default, (
            f"el perfil {profile_name} mide un deadline HTTP distinto del "
            "contrato productivo"
        )
        # The product clamps whatever the gate exports; a gate value that gets
        # clamped would silently measure a different deadline than it reports.
        assert _request_timeout_from_env(str(gate_deadline)) == gate_deadline


def test_cpu_narrate_window_contains_its_own_http_deadline() -> None:
    """message.compose needs room for the HTTP deadline plus IPC and contracts."""

    for profile_name in ("gpu", "cpu_fallback"):
        profile = gate.PROFILE_LIMITS[profile_name]
        assert profile["narrate"] > profile["llm_http"], (
            f"la ventana JSONL de {profile_name} no cubre su propio deadline HTTP"
        )


def test_all_explicit_runtime_does_not_depend_on_a_stale_manifest(
    tmp_path: Path,
) -> None:
    python = tmp_path / "venv" / "python.exe"
    python_path = tmp_path / "source"
    gguf = tmp_path / "model.gguf"
    server = tmp_path / "llama-server.exe"
    python.parent.mkdir()
    (python_path / "baxy_mind").mkdir(parents=True)
    python.write_bytes(b"python")
    (python_path / "baxy_mind" / "__main__.py").write_text("", encoding="utf-8")
    gguf.write_bytes(b"gguf")
    server.write_bytes(b"server")
    stale_manifest = tmp_path / "stale.json"
    stale_manifest.write_text("{not-json", encoding="utf-8")

    resolved = gate.resolve_runtime(
        manifest_path=stale_manifest,
        python=python,
        python_path=python_path,
        gguf=gguf,
        llama_server=server,
        gpu_layers=7,
    )

    assert resolved.source == "explicit_components"
    assert resolved.gpu_layers == 7
    assert resolved.manifest_sha256 == ""


def test_default_core_candidates_prioritize_canonical_release_before_publish(
    tmp_path: Path,
) -> None:
    assert gate.default_core_candidates(tmp_path) == (
        gate.BUILD_LAYOUT.core_executable(tmp_path),
        gate.BUILD_LAYOUT.core_publish_executable(tmp_path),
    )


def test_discover_core_prefers_canonical_release_over_publish(
    tmp_path: Path,
) -> None:
    canonical, published = gate.default_core_candidates(tmp_path)
    for candidate in (canonical, published):
        candidate.parent.mkdir(parents=True, exist_ok=True)
        candidate.write_bytes(b"core")

    resolved = gate.discover_core(
        None,
        candidates=(canonical, published),
    )

    assert resolved == canonical.resolve(strict=True)


def test_discover_core_uses_publish_only_as_fallback(tmp_path: Path) -> None:
    canonical, published = gate.default_core_candidates(tmp_path)
    published.parent.mkdir(parents=True, exist_ok=True)
    published.write_bytes(b"published-core")

    resolved = gate.discover_core(
        None,
        candidates=(canonical, published),
    )

    assert resolved == published.resolve(strict=True)


def test_discover_core_explicit_path_overrides_default_candidates(
    tmp_path: Path,
) -> None:
    explicit = tmp_path / "chosen" / "baxy-core.exe"
    default = tmp_path / "autodetected" / "baxy-core.exe"
    for candidate in (explicit, default):
        candidate.parent.mkdir(parents=True, exist_ok=True)
        candidate.write_bytes(b"core")

    resolved = gate.discover_core(explicit, candidates=(default,))

    assert resolved == explicit.resolve(strict=True)


def test_discover_core_fails_clearly_when_release_outputs_do_not_exist(
    tmp_path: Path,
) -> None:
    canonical, published = gate.default_core_candidates(tmp_path)

    with pytest.raises(FileNotFoundError) as raised:
        gate.discover_core(None, candidates=(canonical, published))

    message = str(raised.value)
    assert "compila Baxy.Core en Release o indica --core" in message
    assert str(canonical) in message
    assert str(published) in message


def test_discover_core_fails_clearly_for_missing_explicit_path(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "missing" / "baxy-core.exe"

    with pytest.raises(FileNotFoundError, match="indicado por --core"):
        gate.discover_core(missing)


def test_core_catalog_probe_uses_and_cleans_a_private_baxy_profile(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    local_app_data = tmp_path / "Local"
    core = tmp_path / "baxy-core.exe"
    core.write_bytes(b"core")
    observed: dict[str, object] = {}

    class FakeProcess:
        def __init__(self, command, *, environment, cwd):
            observed["command"] = command
            observed["environment"] = environment
            observed["cwd"] = cwd

        def next_message(self, timeout):
            observed["timeout"] = timeout
            return {
                "type": "hello",
                "capabilities": [
                    {
                        "name": "system.time",
                        "description": "Lee la hora.",
                        "argumentsSchema": {"type": "object"},
                        "risk": "read",
                    }
                ],
            }

        def close(self, *, graceful_message, timeout):
            observed["closed"] = (graceful_message, timeout)

    removed: list[Path] = []
    pinned_dotnet = tmp_path / ".dotnet" / "dotnet.exe"
    monkeypatch.setenv("LOCALAPPDATA", str(local_app_data))
    monkeypatch.setattr(gate, "JsonLineProcess", FakeProcess)
    monkeypatch.setattr(gate, "dotnet_executable", lambda: str(pinned_dotnet))
    monkeypatch.setattr(
        gate.shutil,
        "rmtree",
        lambda path, *, ignore_errors: removed.append(Path(path)),
    )

    capabilities = gate.current_core_capabilities(core)

    data_root = Path(observed["environment"]["BAXY_DATA_DIR"])
    assert data_root.parent == local_app_data.resolve() / "BAXY"
    assert data_root.name.startswith("mind-budget-core-")
    assert observed["environment"]["DOTNET_ROOT"] == str(pinned_dotnet.parent)
    assert observed["environment"]["DOTNET_ROOT_X64"] == str(pinned_dotnet.parent)
    assert removed == [data_root]
    assert observed["closed"] == (None, 15.0)
    assert capabilities[0]["name"] == "system.time"


def test_safe_argument_clarification_is_a_valid_bounded_result() -> None:
    item = next(
        item for item in gate.build_workload() if item.request_type == "arguments"
    )

    failure = gate.validate_reply(
        item,
        {
            "type": "arguments.result",
            "id": item.case_id,
            "operation": item.message["operation"],
            "arguments": None,
            "ok": False,
            "question": "¿Qué dato falta?",
        },
    )

    assert failure == ""

    semantic_failure = gate.validate_semantic_reply(
        item,
        {
            "type": "arguments.result",
            "id": item.case_id,
            "operation": item.message["operation"],
            "arguments": None,
            "ok": False,
            "question": "¿Qué dato falta?",
        },
    )
    assert semantic_failure == "semantic_arguments_missing"


def test_semantic_oracle_rejects_an_unasked_effect() -> None:
    item = gate.build_workload()[10]

    failure = gate.validate_semantic_reply(
        item,
        {
            "type": "turn.result",
            "id": item.case_id,
            "kind": "action",
            "operation": "wifi.disconnect",
            "intentOperations": ["wifi.disconnect"],
            "effectOperations": ["wifi.disconnect"],
            "question": "",
            "reply": "",
        },
    )

    assert failure == "semantic_action_operation"


def test_semantic_oracle_requires_exact_literal_arguments() -> None:
    item = gate.build_workload()[30 + 3]

    failure = gate.validate_semantic_reply(
        item,
        {
            "type": "arguments.result",
            "id": item.case_id,
            "operation": "audio.mute",
            "arguments": {"state": True},
            "ok": True,
            "question": "",
        },
    )

    assert failure == "semantic_arguments_mismatch"


def test_argument_reply_must_preserve_the_authenticated_operation() -> None:
    item = next(
        item for item in gate.build_workload() if item.request_type == "arguments"
    )

    failure = gate.validate_reply(
        item,
        {
            "type": "arguments.result",
            "id": item.case_id,
            "operation": "system.shutdown",
            "arguments": {},
            "ok": True,
            "question": "",
        },
    )

    assert failure == "unexpected_argument_operation"


def test_process_gpu_attribution_ignores_unrelated_pids() -> None:
    rows = {
        "pid_10_luid_0x0_phys_0": 64 * 2**20,
        "pid_11_luid_0x0_phys_0": 32 * 2**20,
        "pid_99_luid_0x0_phys_0": 4_096 * 2**20,
        "not_a_pid": 7 * 2**20,
    }

    assert gate.ProcessTreeGpuSampler.attributed_bytes(rows, {10, 11}) == (96 * 2**20)


def test_cpu_gpu_check_uses_attributed_tree_not_noisy_global_delta() -> None:
    evaluated = gate.evaluate_profile(
        "cpu_fallback",
        {
            "requests_completed": 45,
            "requests_expected": 45,
            "errors": [],
            "gpu_telemetry_available": True,
            "process_gpu_telemetry_available": True,
            "vram_delta_mib": 999,
            "process_tree_vram_peak_mib": 0.0,
            "tree_ram_peak_mib": 6_000.0,
            "startup": {"catalog_ready_seconds": 45.0},
            "timeouts_seconds": {"handshake": 120.0},
            "latency_seconds": {"turn.decide": {"count": 30, "p50": 20.0}},
        },
        gpu_vram_budget_mib=3_072,
        cpu_vram_tolerance_mib=128,
        cpu_ram_budget_mib=8_192,
        cpu_turn_p50_budget_seconds=22.0,
    )

    assert evaluated["checks"]["no_material_gpu_allocation"] is True
    assert evaluated["status"] == "passed"


def test_cpu_profile_fails_when_process_tree_exceeds_ram_budget() -> None:
    evaluated = gate.evaluate_profile(
        "cpu_fallback",
        {
            "requests_completed": 45,
            "requests_expected": 45,
            "errors": [],
            "gpu_telemetry_available": True,
            "process_gpu_telemetry_available": True,
            "process_tree_vram_peak_mib": 0.0,
            "tree_ram_peak_mib": 8_192.1,
            "startup": {"catalog_ready_seconds": 45.0},
            "timeouts_seconds": {"handshake": 120.0},
            "latency_seconds": {"turn.decide": {"count": 30, "p50": 20.0}},
        },
        gpu_vram_budget_mib=3_072,
        cpu_vram_tolerance_mib=128,
        cpu_ram_budget_mib=8_192,
        cpu_turn_p50_budget_seconds=22.0,
    )

    assert evaluated["checks"]["ram_within_budget"] is False
    assert evaluated["status"] == "failed"


def test_reply_validation_redacts_model_and_runtime_details() -> None:
    item = gate.build_workload()[0]
    reply = {
        "type": "error",
        "id": item.case_id,
        "code": "request_failed",
        "message": r"failed under C:\Users\secret\model.gguf",
    }

    failure = gate.validate_reply(item, reply)

    assert failure == "sidecar_error:request_failed"
    assert "secret" not in failure
    assert "model.gguf" not in failure


def test_source_has_no_legacy_model_path_or_route_request() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "legacy/models" not in source
    assert '"type": "route"' not in source
