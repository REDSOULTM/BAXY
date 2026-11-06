"""Turns BAXY's self-contained folder (scripts/build_steam.ps1) into a GitHub release: zips cut below GitHub's 2 GiB per
asset, the manifest with each part's SHA-256, and BAXY-Instalador.exe (src/Baxy.Installer) with that manifest inside.

    py -3.12 scripts/build_github_release.py --depot <folder> --output <folder> --version 1.2.1

The llama folder, which carries the CUDA runtime, goes in an archive of its own that the installer downloads only on a machine
with an NVIDIA GPU: the CUDA EULA (2.1) licenses the SDK for applications «only for use in systems with NVIDIA GPUs»
(https://docs.nvidia.com/cuda/eula/index.html, read 2026-11-06). BAXY picks its server at every start, and without that folder
computes with llama-vulkan. Models are stored as they are: they do not compress, and storing them keeps unpacking fast."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parent.parent
RELEASES = "https://github.com/REDSOULTM/BAXY/releases/download"
PART_BYTES = 1_900_000_000
STORED = {".gguf", ".onnx", ".bin", ".zip", ".png", ".jpg", ".woff2"}
CHUNK = 1 << 24
CUDA_FOLDER = "llama"
NVIDIA = "10de"  # PCI vendor id, as src/Baxy.Installer/MachineGpu.cs reads it


def _pack(depot: Path, files: list[Path], target: Path) -> None:
    with zipfile.ZipFile(target, "w", allowZip64=True) as archive:
        for path in files:
            method = zipfile.ZIP_STORED if path.suffix.lower() in STORED else zipfile.ZIP_DEFLATED
            archive.write(path, path.relative_to(depot).as_posix(), compress_type=method)


def _cut(archive: Path, part_bytes: int) -> list[dict]:
    """Cuts ``archive`` in numbered files beside it, removes it, and returns each part's name, size and SHA-256."""
    parts = []
    with archive.open("rb") as source:
        while chunk := source.read(min(CHUNK, part_bytes)):
            target = archive.with_name(f"{archive.name}.{len(parts):03d}")
            digest = hashlib.sha256()
            size = 0
            with target.open("wb") as output:
                while chunk:
                    output.write(chunk)
                    digest.update(chunk)
                    size += len(chunk)
                    chunk = source.read(min(CHUNK, part_bytes - size))
            parts.append({"file": target.name, "bytes": size, "sha256": digest.hexdigest()})
    archive.unlink()
    return parts


def build_manifest(depot: Path, output: Path, version: str, part_bytes: int = PART_BYTES) -> dict:
    """Packs ``depot`` in ``output``; the manifest the installer trusts, also written to ``output``/release.json."""
    if not (depot / "app" / "Baxy.exe").is_file():
        raise SystemExit(f"{depot} is not BAXY's folder: it has no app\\Baxy.exe")
    files = sorted(path for path in depot.rglob("*") if path.is_file())
    cuda = [path for path in files if path.relative_to(depot).parts[0] == CUDA_FOLDER]
    common = [path for path in files if path.relative_to(depot).parts[0] != CUDA_FOLDER]
    if not cuda:
        raise SystemExit(f"{depot} is not BAXY's folder: it has no {CUDA_FOLDER}")
    output.mkdir(parents=True, exist_ok=True)
    name = f"baxy-{version}.zip"
    nvidia = f"baxy-{version}-nvidia.zip"
    _pack(depot, common, output / name)
    _pack(depot, cuda, output / nvidia)
    manifest = {
        "version": version,
        "baseUrl": f"{RELEASES}/v{version}/",
        "installedBytes": sum(path.stat().st_size for path in common),
        "archives": [
            {"name": name, "parts": _cut(output / name, part_bytes)},
            {
                "name": nvidia,
                "gpuVendor": NVIDIA,
                "installedBytes": sum(path.stat().st_size for path in cuda),
                "parts": _cut(output / nvidia, part_bytes),
            },
        ],
    }
    (output / "release.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return manifest


def build_installer(output: Path, version: str) -> Path:
    """Publishes BAXY-Instalador.exe with ``output``/release.json inside."""
    subprocess.run(
        [
            "dotnet", "publish", str(REPOSITORY / "src" / "Baxy.Installer"), "-c", "Release", "--nologo", "-v:minimal",
            "-o", str(output / "installer"), f"-p:BaxyReleaseManifest={output / 'release.json'}", f"-p:Version={version}",
        ],
        check=True,
    )
    return output / "installer" / "BAXY-Instalador.exe"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--depot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--version", required=True)
    arguments = parser.parse_args()
    build_manifest(arguments.depot, arguments.output, arguments.version)
    print(build_installer(arguments.output, arguments.version))


if __name__ == "__main__":
    main()
