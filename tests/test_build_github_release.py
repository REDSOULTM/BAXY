"""The release a person downloads: parts below the limit, hashes that match, and the whole folder inside."""
from __future__ import annotations

import hashlib
import io
import json
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import build_github_release as release  # noqa: E402


def _depot(root: Path) -> Path:
    depot = root / "depot"
    for name, content in {
        "app/Baxy.exe": b"app",
        "models/model.gguf": bytes(range(256)) * 40,
        "llama/server.txt": b"cuda",
        "llama-vulkan/server.txt": b"vulkan",
    }.items():
        path = depot / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    return depot


def _entries(output: Path, archive: dict) -> dict[str, bytes]:
    joined = b"".join((output / part["file"]).read_bytes() for part in archive["parts"])
    with zipfile.ZipFile(io.BytesIO(joined)) as opened:
        return {name: opened.read(name) for name in opened.namelist()}


def test_parts_stay_below_the_limit_with_their_hash_and_rebuild_the_folder(tmp_path: Path) -> None:
    output = tmp_path / "out"

    manifest = release.build_manifest(_depot(tmp_path), output, "9.9.9", part_bytes=4000)

    assert json.loads((output / "release.json").read_text(encoding="utf-8")) == manifest
    assert manifest["baseUrl"].endswith("/v9.9.9/")
    archive = manifest["archives"][0]
    assert len(archive["parts"]) > 1
    for part in archive["parts"]:
        content = (output / part["file"]).read_bytes()
        assert len(content) == part["bytes"] <= 4000
        assert hashlib.sha256(content).hexdigest() == part["sha256"]
    entries = _entries(output, archive)
    assert set(entries) == {"app/Baxy.exe", "models/model.gguf", "llama-vulkan/server.txt"}
    assert entries["llama-vulkan/server.txt"] == b"vulkan"


def test_the_cuda_folder_goes_in_its_own_archive_only_for_nvidia(tmp_path: Path) -> None:
    # CUDA EULA 2.1: «only for use in systems with NVIDIA GPUs» (https://docs.nvidia.com/cuda/eula/index.html, 2026-11-06).
    output = tmp_path / "out"

    manifest = release.build_manifest(_depot(tmp_path), output, "9.9.9", part_bytes=4000)

    common, nvidia = manifest["archives"]
    assert "gpuVendor" not in common
    assert nvidia["name"] == "baxy-9.9.9-nvidia.zip"
    assert nvidia["gpuVendor"] == "10de"
    assert _entries(output, nvidia) == {"llama/server.txt": b"cuda"}
    assert nvidia["installedBytes"] == len(b"cuda")
    everything = sum(path.stat().st_size for path in (tmp_path / "depot").rglob("*") if path.is_file())
    assert manifest["installedBytes"] == everything - len(b"cuda")


def test_a_package_without_the_cuda_folder_is_refused(tmp_path: Path) -> None:
    depot = _depot(tmp_path)
    (depot / "llama" / "server.txt").unlink()
    (depot / "llama").rmdir()

    with pytest.raises(SystemExit):
        release.build_manifest(depot, tmp_path / "out", "1.0.0")


def test_a_folder_without_the_app_is_refused(tmp_path: Path) -> None:
    (tmp_path / "depot").mkdir()

    with pytest.raises(SystemExit):
        release.build_manifest(tmp_path / "depot", tmp_path / "out", "1.0.0")
