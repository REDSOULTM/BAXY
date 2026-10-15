"""Python and installation PowerShell agree on the optional CPU adapter profile."""
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from scripts import baxy_runtime_config as config

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def registration(tmp_path):
    paths = {key: tmp_path / value for key, value in {
        "python": "python.exe", "gguf": "base.gguf", "llama_server": "llama-server.exe",
        "adapter": "cpu.gguf",
    }.items()}
    for key, path in paths.items():
        path.write_bytes(key.encode())
    source = tmp_path / "src"
    (source / "baxy_mind").mkdir(parents=True)
    (source / "baxy_mind/__main__.py").write_text("")
    stt = tmp_path / "stt"
    stt.mkdir()
    for name in config.STT_FILES:
        (stt / name).write_bytes(name.encode())
    value = {"schema": "baxy-mind-runtime-v1", "python_path": str(source),
             "stt_dir": str(stt), "stt_sha256": config.stt_sha256(stt),
             "wake_manifest": None, "wake_manifest_sha256": None,
             "tts_model": None, "tts_sha256": None, "ngl": 99, "wake_on_start": False}
    for key in ("python", "gguf", "llama_server"):
        value[key] = str(paths[key])
        value[key + "_sha256"] = config.file_sha256(paths[key])
    value["cpu_prose_adapter"] = {
        "schema": "baxy-cpu-prose-adapter-v1", "gguf": str(paths["adapter"]),
        "gguf_sha256": config.file_sha256(paths["adapter"]),
        "base_gguf_sha256": value["gguf_sha256"],
    }
    return tmp_path / "runtime.json", value, paths


@pytest.mark.parametrize("mutation", ["valid", "absent", "changed_asset", "wrong_base", "extra", "null", "missing"])
def test_runtime_readers_agree_on_adapter_registration(registration, mutation):
    manifest, value, paths = registration
    if mutation == "absent":
        value.pop("cpu_prose_adapter")
    elif mutation == "changed_asset":
        paths["adapter"].write_bytes(b"changed")
    elif mutation == "wrong_base":
        value["cpu_prose_adapter"]["base_gguf_sha256"] = "0" * 64
    elif mutation == "extra":
        value["cpu_prose_adapter"]["global"] = True
    elif mutation == "null":
        value["cpu_prose_adapter"] = None
    elif mutation == "missing":
        value["cpu_prose_adapter"].pop("gguf_sha256")
    manifest.write_text(json.dumps(value), encoding="utf-8")
    expected = mutation in {"valid", "absent"}
    if expected:
        result = config.resolve_runtime(manifest_path=manifest)
        assert (result.cpu_prose_adapter is not None) == (mutation == "valid")
        exported = result.adapter_environment()["BAXY_MIND_CPU_PROSE_ADAPTER"]
        assert bool(exported) == (mutation == "valid")
        if exported:
            assert json.loads(exported) == result.cpu_prose_adapter
    else:
        with pytest.raises(ValueError):
            config.resolve_runtime(manifest_path=manifest)
    powershell = shutil.which("pwsh") or shutil.which("powershell")
    assert powershell, "Windows product validation requires PowerShell"
    quote = lambda path: "'" + str(path).replace("'", "''") + "'"
    command = ". " + quote(ROOT / "scripts/mind_runtime_manifest.ps1") + "; "
    command += "Get-BaxyMindRuntimeStatus -ManifestPath " + quote(manifest) + " | ConvertTo-Json -Compress -Depth 5"
    completed = subprocess.run([powershell, "-NoProfile", "-NonInteractive", "-Command", command],
                               capture_output=True, text=True, timeout=30,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["Valid"] is expected


def test_explicit_other_base_does_not_inherit_adapter(registration):
    manifest, value, _ = registration
    manifest.write_text(json.dumps(value), encoding="utf-8")
    other = manifest.parent / "other.gguf"
    other.write_bytes(b"another base")
    # Explicit components retain their existing hash verification contract;
    # qualify the selected override in that registration for this resolution.
    with pytest.raises(ValueError, match="gguf"):
        config.resolve_runtime(manifest_path=manifest, gguf=other)
