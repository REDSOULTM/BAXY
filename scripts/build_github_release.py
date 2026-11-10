"""Turns BAXY's self-contained folder (scripts/build_steam.ps1) into a GitHub release: zips cut below GitHub's 2 GiB per
asset, the manifest with each part's SHA-256, and BAXY-Instalador.exe (src/Baxy.Installer) with that manifest inside.

    py -3.12 scripts/build_github_release.py --depot <folder> --output <folder> --version 1.3.0

The llama folder, which carries the CUDA runtime, goes in an archive of its own that the installer downloads only on a machine
with an NVIDIA GPU: the CUDA EULA (2.1) licenses the SDK for applications «only for use in systems with NVIDIA GPUs»
(https://docs.nvidia.com/cuda/eula/index.html, read 2026-11-06). BAXY picks its server at every start, and without that folder
computes with llama-vulkan. That archive also carries, under licenses, the texts of what the llama folder holds, so it does not
travel without them: CUDA EULA 1.2 forbids removing NVIDIA's notices and 2.7 asks for cuBLAS's (read 2026-11-07), and the folder
also holds the Visual C++ runtime. Unpacked, they land on the same bytes the main archive leaves. Models are stored as they are:
they do not compress, and storing them keeps unpacking fast. What a run of the folder left in it (the App's hash cache and
Python's bytecode, with the paths of the machine that ran it) stays out of both archives, as Steam's upload leaves it out
(scripts/steam/app_build.vdf)."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path

from check_package_licenses import is_run_leftover

REPOSITORY = Path(__file__).resolve().parent.parent
GITHUB_REPOSITORY = "REDSOULTM/BAXY"
RELEASES = f"https://github.com/{GITHUB_REPOSITORY}/releases/download"
# Where the installed BAXY was published (src/Baxy.Core/Operations/BaxyDistribution.cs): GitHub, whose latest release it
# looks for and installs with this installer. The depot's own (steam or itch, scripts/build_steam.ps1) does not travel here.
DISTRIBUTION = "distribution.json"
PART_BYTES = 1_900_000_000
STORED = {".gguf", ".onnx", ".bin", ".zip", ".png", ".jpg", ".woff2"}
CHUNK = 1 << 24
CUDA_FOLDER = "llama"
NVIDIA = "10de"  # PCI vendor id, as src/Baxy.Installer/MachineGpu.cs reads it
# THIRD_PARTY_NOTICES.md, «Runtime CUDA 12»: CUDA and cuBLAS (with Attachment B), what llama-server and ggml carry inside, and the
# Visual C++ runtime build_steam.ps1 copies beside them.
NVIDIA_TEXTS = (
    "NVIDIA-CUDA-EULA-12.4.1.txt", "LICENSE-llama.cpp.txt", "cpp-httplib-LICENSE.txt", "BoringSSL-LICENSE.txt",
    "nlohmann-json-LICENSE.txt", "xxHash-LICENSE.txt", "llamafile-sgemm-LICENSE.txt", "Microsoft-VisualCpp-Redistributable.txt",
)


def _pack(depot: Path, files: list[Path], target: Path, written: dict[str, bytes] | None = None) -> None:
    with zipfile.ZipFile(target, "w", allowZip64=True) as archive:
        for path in files:
            method = zipfile.ZIP_STORED if path.suffix.lower() in STORED else zipfile.ZIP_DEFLATED
            archive.write(path, path.relative_to(depot).as_posix(), compress_type=method)
        for name, content in (written or {}).items():
            archive.writestr(name, content, compress_type=zipfile.ZIP_DEFLATED)


def distribution() -> bytes:
    """The channel file of a BAXY GitHub's installer put in place."""
    marker = {"schema": "baxy.distribution.v1", "channel": "github", "repository": GITHUB_REPOSITORY}
    return json.dumps(marker, indent=1).encode("utf-8")


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
    files = sorted(path for path in depot.rglob("*")
                   if path.is_file() and not is_run_leftover(path.relative_to(depot).as_posix()))
    cuda = [path for path in files if path.relative_to(depot).parts[0] == CUDA_FOLDER]
    common = [path for path in files if path.relative_to(depot).parts[0] != CUDA_FOLDER
              and path.relative_to(depot).as_posix() != DISTRIBUTION]
    if not cuda:
        raise SystemExit(f"{depot} is not BAXY's folder: it has no {CUDA_FOLDER}")
    texts = [depot / "licenses" / text for text in NVIDIA_TEXTS]
    if missing := [text.name for text in texts if not text.is_file()]:
        raise SystemExit(f"{depot} lacks the licenses of its {CUDA_FOLDER} folder: {', '.join(missing)}")
    output.mkdir(parents=True, exist_ok=True)
    name = f"baxy-{version}.zip"
    nvidia = f"baxy-{version}-nvidia.zip"
    marker = distribution()
    _pack(depot, common, output / name, {DISTRIBUTION: marker})
    _pack(depot, cuda + texts, output / nvidia)
    manifest = {
        "version": version,
        "baseUrl": f"{RELEASES}/v{version}/",
        "installedBytes": sum(path.stat().st_size for path in common) + len(marker),
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
