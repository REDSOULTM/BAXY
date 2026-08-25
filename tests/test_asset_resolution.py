from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from baxy_mind.assets import AssetDescriptorError, load_asset_descriptor, resolve_asset


ROOT = Path(__file__).resolve().parents[1]
DESCRIPTOR = ROOT / "assets.manifest.json"
BOOTSTRAP = ROOT / "scripts" / "bootstrap.ps1"
RUN_BAXY = ROOT / "scripts" / "run_baxy.ps1"
MIND_RUNTIME_DISCOVERY = ROOT / "src" / "Baxy.App" / "MindRuntimeDiscovery.cs"
MAIN_WINDOW_VIEW_MODEL = ROOT / "src" / "Baxy.App" / "MainWindowViewModel.cs"


def test_descriptor_declares_repository_legacy_assets_without_copying_them(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("BAXY_ASSETS_ROOT", raising=False)
    monkeypatch.delenv("BAXY_ASSETS_OVERRIDE", raising=False)
    monkeypatch.delenv("BAXY_MIND_LLM_GGUF", raising=False)

    descriptor, _ = load_asset_descriptor()
    assert any(
        "\\legacy\\models\\artifacts\\" in candidate
        for candidate in descriptor["assets"]["conversation_model"]["candidates"]
    )


def test_machine_local_override_wins_and_stays_outside_repository(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    model = tmp_path / "private-assets" / "model.gguf"
    model.parent.mkdir()
    model.write_bytes(b"fixture")
    override = tmp_path / "assets.local.json"
    override.write_text(
        json.dumps(
            {
                "schema": "baxy-assets-local-v1",
                "assets": {"conversation_model": [str(model)]},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("BAXY_ASSETS_OVERRIDE", str(override))
    monkeypatch.delenv("BAXY_MIND_LLM_GGUF", raising=False)

    resolution = resolve_asset("conversation_model")

    assert resolution.path == model.resolve()
    assert not resolution.path.is_relative_to(ROOT)


def test_unknown_override_asset_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    override = tmp_path / "assets.local.json"
    override.write_text(
        json.dumps(
            {
                "schema": "baxy-assets-local-v1",
                "assets": {"invented_asset": ["C:\\fixture\\asset.bin"]},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("BAXY_ASSETS_OVERRIDE", str(override))

    with pytest.raises(AssetDescriptorError, match="asset_override_unknown_assets"):
        resolve_asset("conversation_model")


@pytest.mark.skipif(os.name != "nt", reason="PowerShell resolver is Windows-only")
def test_powershell_and_python_select_the_same_asset(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    server = tmp_path / "llama-server.exe"
    server.write_bytes(b"fixture")
    override = tmp_path / "assets.local.json"
    override.write_text(
        json.dumps(
            {
                "schema": "baxy-assets-local-v1",
                "assets": {"llama_server": [str(server)]},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("BAXY_ASSETS_OVERRIDE", str(override))
    monkeypatch.delenv("BAXY_ASSETS_ROOT", raising=False)
    python_resolution = resolve_asset("llama_server")
    command = (
        ". .\\scripts\\asset_resolver.ps1; "
        "$result=Resolve-BaxyAsset -Name 'llama_server'; "
        "[Console]::Out.Write($result.Path)"
    )

    completed = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )

    assert completed.returncode == 0, completed.stderr
    assert python_resolution.path is not None
    assert Path(completed.stdout).resolve() == python_resolution.path


@pytest.mark.skipif(os.name != "nt", reason="PowerShell resolver is Windows-only")
def test_powershell_resolves_optional_directory_without_required_files(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    voice = tmp_path / "voice"
    voice.mkdir()
    descriptor = json.loads(DESCRIPTOR.read_text(encoding="utf-8"))
    descriptor["assets"]["optional_fixture_directory"] = {
        "kind": "directory",
        "required": False,
        "environment": "BAXY_OPTIONAL_FIXTURE_DIRECTORY",
        "candidates": [str(tmp_path / "missing-default")],
        "repair": "fixture",
    }
    descriptor_path = tmp_path / "assets.manifest.json"
    descriptor_path.write_text(json.dumps(descriptor), encoding="utf-8")
    override = tmp_path / "assets.local.json"
    override.write_text(
        json.dumps(
            {
                "schema": "baxy-assets-local-v1",
                "assets": {"optional_fixture_directory": [str(voice)]},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("BAXY_ASSETS_OVERRIDE", str(override))
    command = (
        ". .\\scripts\\asset_resolver.ps1; "
        "$result=Resolve-BaxyAsset -Name 'optional_fixture_directory' "
        f"-DescriptorPath '{descriptor_path}'; "
        "[Console]::Out.Write($result.Path)"
    )

    completed = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )

    assert completed.returncode == 0, completed.stderr
    assert Path(completed.stdout).resolve() == voice.resolve()


def test_active_runtime_has_no_machine_bound_baxy_path_literals() -> None:
    forbidden = ("D:\\\\BAXY", "C:\\\\Users\\\\usuario")
    offenders: list[str] = []
    roots = (ROOT / "src", ROOT / "scripts", ROOT / "main.py")
    for root in roots:
        files = [root] if root.is_file() else root.rglob("*")
        for path in files:
            if not path.is_file() or path.suffix.casefold() not in {
                ".cs",
                ".py",
                ".ps1",
            }:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for literal in forbidden:
                if literal in text:
                    offenders.append(f"{path.relative_to(ROOT)}: {literal}")

    assert offenders == [], "Rutas de máquina fuera de assets.manifest.json:\n" + "\n".join(
        offenders
    )


def test_bootstrap_installs_only_dependencies_and_never_downloads_models() -> None:
    source = BOOTSTRAP.read_text(encoding="utf-8")

    assert "setup_mind_voice.ps1" in source
    assert "register_mind_runtime.ps1" in source
    assert "Resolve-BaxyAsset" in source
    assert "Get-BaxyMindRuntimeStatus" in source
    assert "pip install" in source
    assert "install_nemotron_streaming_stt.ps1" not in source
    assert "Invoke-WebRequest" not in source
    assert "Start-BitsTransfer" not in source
    assert "curl.exe" not in source


def test_development_launcher_delegates_runtime_hash_verification_to_app() -> None:
    launcher = RUN_BAXY.read_text(encoding="utf-8")
    discovery = MIND_RUNTIME_DISCOVERY.read_text(encoding="utf-8")
    view_model = MAIN_WINDOW_VIEW_MODEL.read_text(encoding="utf-8")

    assert "mind_runtime_manifest.ps1" not in launcher
    assert "Get-BaxyMindRuntimeStatus" not in launcher
    assert '$env:BAXY_MIND_DISABLED = "1"' in launcher
    assert "Remove-Item Env:BAXY_MIND_DISABLED" in launcher
    assert '$env:BAXY_MIND_NGL = "0"' in launcher
    assert "$env:BAXY_ASSET_DESCRIPTOR" in launcher
    assert "pendiente de verificación SHA-256" in launcher
    assert "Manifiesto y activos SHA-256 verificados" not in launcher

    assert "MindRuntimeDiscovery.TryConfigureCurrentProcess()" not in view_model
    assert "MindRuntimeDiscovery.DiscoverVerified()" in view_model
    assert "MindRuntimeDiscovery.ApplyVerified(discovery)" in view_model
    assert "MatchesSttHash" in discovery
    assert "SHA256.HashData(stream)" in discovery
