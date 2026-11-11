"""The release a person downloads: parts below the limit, hashes that match, and the whole folder inside."""
from __future__ import annotations

import hashlib
import io
import json
import re
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
        **{f"licenses/{text}": text.encode() for text in release.NVIDIA_TEXTS},
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
    licenses = {f"licenses/{text}" for text in release.NVIDIA_TEXTS}
    assert set(entries) == {"app/Baxy.exe", "models/model.gguf", "llama-vulkan/server.txt", "distribution.json"} | licenses
    assert entries["llama-vulkan/server.txt"] == b"vulkan"


def test_what_a_run_of_the_folder_left_stays_out_of_every_archive(tmp_path: Path) -> None:
    # PKG-1: someone opened BAXY from the folder to try it. Steam's upload leaves these out (scripts/steam/app_build.vdf).
    depot = _depot(tmp_path)
    for left in ("mind-runtime-v1.hash-cache.json", "mind/baxy_mind/__pycache__/gpu.cpython-312.pyc",
                 "llama/__pycache__/x.cpython-312.pyc"):
        (depot / left).parent.mkdir(parents=True, exist_ok=True)
        (depot / left).write_bytes(b"left by a run, with this machine's paths inside")
    clean = release.build_manifest(_depot(tmp_path / "clean"), tmp_path / "clean-out", "9.9.9")

    manifest = release.build_manifest(depot, tmp_path / "out", "9.9.9")

    for archive in manifest["archives"]:
        assert not [name for name in _entries(tmp_path / "out", archive) if "__pycache__" in name or "hash-cache" in name]
    assert manifest["installedBytes"] == clean["installedBytes"]
    assert manifest["archives"][1]["installedBytes"] == clean["archives"][1]["installedBytes"]


def test_the_installed_folder_says_github_published_it_whatever_the_depot_said(tmp_path: Path) -> None:
    # actualizar-ordenes-app: the App updates a GitHub BAXY from GitHub's latest release, and leaves Steam's to Steam.
    depot = _depot(tmp_path)
    (depot / "distribution.json").write_text('{"schema":"baxy.distribution.v1","channel":"steam"}', encoding="utf-8")
    output = tmp_path / "out"

    manifest = release.build_manifest(depot, output, "9.9.9")

    marker = json.loads(_entries(output, manifest["archives"][0])["distribution.json"])
    assert marker == {"schema": "baxy.distribution.v1", "channel": "github", "repository": "REDSOULTM/BAXY"}


def test_the_cuda_folder_goes_in_its_own_archive_only_for_nvidia(tmp_path: Path) -> None:
    # CUDA EULA 2.1: «only for use in systems with NVIDIA GPUs» (https://docs.nvidia.com/cuda/eula/index.html, 2026-11-06).
    output = tmp_path / "out"

    manifest = release.build_manifest(_depot(tmp_path), output, "9.9.9", part_bytes=4000)

    common, nvidia = manifest["archives"]
    assert "gpuVendor" not in common
    assert nvidia["name"] == "baxy-9.9.9-nvidia.zip"
    assert nvidia["gpuVendor"] == "10de"
    texts = {f"licenses/{text}": text.encode() for text in release.NVIDIA_TEXTS}
    assert _entries(output, nvidia) == {"llama/server.txt": b"cuda", **texts}
    # The texts land on the same bytes the main archive already left: they take no more disk.
    assert nvidia["installedBytes"] == len(b"cuda")
    everything = sum(path.stat().st_size for path in (tmp_path / "depot").rglob("*") if path.is_file())
    # Plus the channel file the installer puts beside app (distribution.json).
    assert manifest["installedBytes"] == everything - len(b"cuda") + len(release.distribution())


def test_the_nvidia_part_carries_the_texts_the_notices_name_for_it() -> None:
    # Its 34 files carried none of them (LIC1, 2026-11-07); downloaded alone it must: CUDA EULA 1.2 «remove copyright or other
    # proprietary notices» is forbidden and 2.7 asks for cuBLAS's notices (https://docs.nvidia.com/cuda/eula/index.html, v13.5).
    notices = (Path(release.REPOSITORY) / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    section = notices.split("\n## Runtime CUDA 12 en el paquete\n", 1)[1].split("\n## ", 1)[0]
    assert set(release.NVIDIA_TEXTS) == set(re.findall(r"`([^`/]+\.txt)`", section))


@pytest.mark.parametrize("text", ["NVIDIA-CUDA-EULA-12.4.1.txt", "LICENSE-llama.cpp.txt"])
def test_a_package_missing_a_text_of_the_nvidia_part_is_refused(tmp_path: Path, text: str) -> None:
    depot = _depot(tmp_path)
    (depot / "licenses" / text).unlink()

    with pytest.raises(SystemExit, match=text):
        release.build_manifest(depot, tmp_path / "out", "1.0.0")


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


# FIR1 (decisión A1, 10-11-2026): release.json names the installer and is signed apart; a test key never reaches GitHub.
def _pem(body: bytes) -> str:
    import base64

    return "-----BEGIN PUBLIC KEY-----\n" + base64.b64encode(body).decode() + "\n-----END PUBLIC KEY-----\n"


def test_a_release_for_github_is_refused_with_a_test_key_and_the_twin_is_not(tmp_path: Path, monkeypatch) -> None:
    keys = tmp_path / "keys.pem"
    keys.write_text(_pem(b"test key") + _pem(b"real key"), encoding="ascii")
    listed = tmp_path / "test-keys.txt"
    listed.write_text("# comment\n" + hashlib.sha256(b"test key").hexdigest() + "  a test\n", encoding="utf-8")
    monkeypatch.setattr(release, "TEST_KEYS", listed)

    with pytest.raises(SystemExit, match="TEST key"):
        release.refuse_test_keys(keys, "https://github.com/REDSOULTM/BAXY/releases/download/v9.9.9/")
    release.refuse_test_keys(keys, "http://127.0.0.1:18791/")
    keys.write_text(_pem(b"real key"), encoding="ascii")
    release.refuse_test_keys(keys, "https://github.com/REDSOULTM/BAXY/releases/download/v9.9.9/")
    keys.write_text("no key here", encoding="ascii")
    with pytest.raises(SystemExit, match="no public key"):
        release.refuse_test_keys(keys, "http://127.0.0.1:18791/")


def test_the_repository_carries_keys_and_its_test_list_is_fingerprints() -> None:
    assert release.fingerprints(release.PRODUCT_KEYS.read_text(encoding="ascii"))
    assert all(re.fullmatch(r"[0-9a-f]{64}", line) for line in release.known_test_keys())


def test_release_json_names_the_installer_by_size_and_hash(tmp_path: Path) -> None:
    output = tmp_path / "out"
    release.build_manifest(_depot(tmp_path), output, "9.9.9", part_bytes=4000)
    exe = tmp_path / "BAXY-Instalador.exe"
    exe.write_bytes(b"MZ the installer")

    manifest = release.name_installer(output, exe)

    assert manifest["installer"] == {"file": "BAXY-Instalador.exe", "bytes": 16,
                                     "sha256": hashlib.sha256(b"MZ the installer").hexdigest()}
    assert json.loads((output / "release.json").read_text(encoding="utf-8")) == manifest


def test_a_twin_downloads_only_from_this_machine(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="this machine"):
        release.build_twin(tmp_path, "9.9.9", "https://example.com/", tmp_path / "k.pem", "k")


def test_the_release_and_its_twin_are_signed_each_with_the_key_of_its_own_folder(tmp_path: Path, monkeypatch) -> None:
    signed: list[tuple[str, str, Path | None]] = []
    monkeypatch.setattr(release, "refuse_test_keys", lambda keys, url: None)
    monkeypatch.setattr(release, "build_manifest", lambda depot, output, version: (
        output.mkdir(parents=True, exist_ok=True),
        (output / "release.json").write_text(json.dumps({"version": version, "archives": []}), encoding="utf-8")))
    monkeypatch.setattr(release, "build_installer", lambda output, version, keys: output / "BAXY-Instalador.exe")
    monkeypatch.setattr(release, "name_installer", lambda output, exe: None)

    def sign(manifest: Path, keys: Path, key_name: str = release.SIGNING_KEY, folder: Path | None = None) -> None:
        signed.append((manifest.parent.name, key_name, folder))
        manifest.with_name("release.json.sig").write_text("sig", encoding="ascii")

    monkeypatch.setattr(release, "sign", sign)
    owner, test = tmp_path / "owner", tmp_path / "test"
    monkeypatch.setattr(sys, "argv", ["build_github_release.py", "--depot", str(tmp_path), "--output", str(tmp_path / "out"),
                                      "--version", "9.9.9", "--signing-folder", str(owner),
                                      "--twin-url", "http://127.0.0.1:18791/", "--twin-keys", str(tmp_path / "t.pem"),
                                      "--twin-signing-key", "t", "--twin-signing-folder", str(test)])

    release.main()

    assert signed == [("out", release.SIGNING_KEY, owner), ("twin", "t", test)]


@pytest.mark.skipif(sys.platform != "win32", reason="DPAPI keeps the private key")
def test_the_signing_tool_signs_and_a_changed_byte_does_not_verify(tmp_path: Path) -> None:
    import subprocess

    keys = tmp_path / "test.pem"
    release._signing(["new", "--name", "t", "--folder", str(tmp_path / "k"), "--public", str(keys)])
    manifest = tmp_path / "release.json"
    manifest.write_text('{"version":"9.9.9"}', encoding="utf-8")

    release.sign(manifest, keys, "t", tmp_path / "k")
    manifest.write_text('{"version":"9.9.8"}', encoding="utf-8")

    with pytest.raises(subprocess.CalledProcessError):
        release._signing(["verify", "--keys", str(keys), str(manifest)])
    assert release.fingerprints(keys.read_text(encoding="ascii"))[0] in subprocess.run(
        ["dotnet", "run", str(release.SIGNING_TOOL), "--", "public", "--name", "t", "--folder", str(tmp_path / "k"),
         "--public", str(tmp_path / "again.pem")], check=True, capture_output=True, text=True).stdout
