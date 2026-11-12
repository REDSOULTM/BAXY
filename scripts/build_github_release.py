"""Turns BAXY's self-contained folder (scripts/build_steam.ps1) into a GitHub release: zips cut below GitHub's 2 GiB per
asset, the manifest with each part's SHA-256, and BAXY-Instalador.exe (src/Baxy.Installer) with that manifest inside.

    py -3.12 scripts/build_github_release.py --depot <folder> --output <folder> --version 1.3.0
        [--twin-url http://127.0.0.1:18791/ --twin-keys <test.pem> --twin-signing-key <test key name>]

FIR1 (decisión A1 del líder, 10-11-2026): release.json also names BAXY-Instalador.exe by size and SHA-256 and is signed apart
(release.json.sig, scripts/ReleaseSigning.cs) with the owner's key, which never leaves his PC: BAXY runs an update's
installer, and the installer uses its parts, only under that signature (src/Baxy.Core/Operations/ReleaseSignature.cs). The
twin, which downloads from this machine to test a build, is the same installer with a test key named on purpose; a GitHub
release is refused while a key of release-keys/test-keys.txt is the one BAXY would trust
(documentacion/FIRMA_ACTUALIZACIONES.md).

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
import base64
import hashlib
import json
import os
import re
import subprocess
import urllib.parse
import zipfile
from pathlib import Path

from check_package_licenses import is_run_leftover

REPOSITORY = Path(__file__).resolve().parent.parent
PRODUCT_KEYS = REPOSITORY / "release-keys" / "update-keys.pem"
TEST_KEYS = REPOSITORY / "release-keys" / "test-keys.txt"
SIGNING_TOOL = REPOSITORY / "scripts" / "ReleaseSigning.cs"
SIGNING_KEY = "BAXY-actualizaciones"
INSTALLER = "BAXY-Instalador.exe"
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


def build_installer(output: Path, version: str, keys: Path = PRODUCT_KEYS) -> Path:
    """Publishes BAXY-Instalador.exe with ``output``/release.json inside and ``keys`` as the keys it trusts."""
    subprocess.run(
        [
            "dotnet", "publish", str(REPOSITORY / "src" / "Baxy.Installer"), "-c", "Release", "--nologo", "-v:minimal",
            "-o", str(output / "installer"), f"-p:BaxyReleaseManifest={output / 'release.json'}", f"-p:Version={version}",
            f"-p:BaxyUpdateKeys={keys}",
        ],
        check=True,
    )
    return output / "installer" / INSTALLER


def fingerprints(pem: str) -> list[str]:
    """The SHA-256 of each public key of a PEM text (its SubjectPublicKeyInfo DER), as ReleaseSigning.cs prints it."""
    blocks = re.findall(r"-----BEGIN PUBLIC KEY-----(.*?)-----END PUBLIC KEY-----", pem, re.S)
    return [hashlib.sha256(base64.b64decode("".join(block.split()))).hexdigest() for block in blocks]


def known_test_keys() -> set[str]:
    lines = TEST_KEYS.read_text(encoding="utf-8").splitlines()
    return {line.split()[0] for line in lines if line.strip() and not line.startswith("#")}


def this_machine(base_url: str) -> bool:
    """A plain address for this machine itself, decided on the host it goes to, not on how its text begins (UNI1, REV8
    F1: «http://127.0.0.1:80@example.test/» goes to example.test; RFC 3986, authority = [ userinfo "@" ] host [ ":" port ])."""
    address = urllib.parse.urlsplit(base_url)
    return (address.scheme == "http" and address.hostname == "127.0.0.1" and address.username is None
            and base_url.startswith("http://127.0.0.1:"))


def refuse_test_keys(keys: Path, base_url: str) -> None:
    """A release for the public (not this machine's twin) never carries a test key, nor a file without a key."""
    found = fingerprints(keys.read_text(encoding="ascii"))
    if not found:
        raise SystemExit(f"{keys} holds no public key")
    if this_machine(base_url):
        return
    if test := sorted(set(found) & known_test_keys()):
        raise SystemExit(f"{keys} holds the TEST key {test[0][:16]}…: generate the real one first "
                         "(documentacion/FIRMA_ACTUALIZACIONES.md, «La clave real»)")


def name_installer(output: Path, exe: Path) -> dict:
    """release.json, now naming the installer by size and SHA-256: what BAXY checks before running it."""
    manifest = json.loads((output / "release.json").read_text(encoding="utf-8"))
    manifest["installer"] = {"file": INSTALLER, "bytes": exe.stat().st_size, "sha256": _sha256(exe)}
    (output / "release.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return manifest


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def _signing(command: list[str]) -> None:
    subprocess.run(["dotnet", "run", str(SIGNING_TOOL), "--", *command], check=True)


def sign(manifest: Path, keys: Path, key_name: str = SIGNING_KEY, folder: Path | None = None) -> None:
    """Writes release.json.sig with the private key ``key_name`` and checks it with ``keys``, the ones the installer trusts."""
    where = ["--folder", str(folder)] if folder else []
    _signing(["sign", "--name", key_name, *where, str(manifest)])
    _signing(["verify", "--keys", str(keys), str(manifest)])


def build_twin(output: Path, version: str, base_url: str, keys: Path, key_name: str, folder: Path | None = None) -> Path:
    """The installer that downloads the same parts from this machine, under a test key: in ``output``/twin, with the folder
    to serve (``served``: the parts, linked, and its own signed release.json)."""
    if not this_machine(base_url) or not base_url.endswith("/"):
        raise SystemExit(f"a twin downloads from this machine only, not {base_url}")
    twin = output / "twin"
    served = twin / "served"
    served.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((output / "release.json").read_text(encoding="utf-8"))
    manifest.pop("installer", None)
    manifest["baseUrl"] = base_url
    (twin / "release.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    exe = build_installer(twin, version, keys)
    name_installer(twin, exe)
    sign(twin / "release.json", keys, key_name, folder)
    for archive in manifest["archives"]:
        for part in archive["parts"]:
            if not (served / part["file"]).exists():
                os.link(output / part["file"], served / part["file"])
    for name in ("release.json", "release.json.sig"):
        (served / name).write_bytes((twin / name).read_bytes())
    return exe


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--depot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--keys", type=Path, default=PRODUCT_KEYS, help="the public keys the installer trusts")
    parser.add_argument("--signing-key", default=SIGNING_KEY, help="the private key that signs (scripts/ReleaseSigning.cs)")
    parser.add_argument("--signing-folder", type=Path, help="where that key is, when not in %%APPDATA%%\\BAXY-firma")
    parser.add_argument("--twin-url", help="also a twin that downloads from this machine, e.g. http://127.0.0.1:18791/")
    parser.add_argument("--twin-keys", type=Path, help="the twin's test public key")
    parser.add_argument("--twin-signing-key", help="the twin's test private key")
    # INT28: the owner's key and the twin's test key live in different folders; one --signing-folder for both made the
    # real signature look for the owner's key among the test keys (or the twin's among the owner's).
    parser.add_argument("--twin-signing-folder", type=Path, help="where the twin's test key is (default: --signing-folder)")
    parser.add_argument("--twin-only", action="store_true", help="the parts and the twin, no installer for GitHub")
    arguments = parser.parse_args()
    if arguments.twin_url and (not arguments.twin_keys or not arguments.twin_signing_key):
        raise SystemExit("a twin names its test key: --twin-keys and --twin-signing-key")
    if not arguments.twin_only:
        # BAXY's App inside the parts trusts the repository's keys, the installer the given ones: neither may be a test key.
        for keys in {PRODUCT_KEYS, arguments.keys}:
            refuse_test_keys(keys, f"{RELEASES}/")
    elif not arguments.twin_url:
        raise SystemExit("--twin-only builds a twin: give --twin-url")
    build_manifest(arguments.depot, arguments.output, arguments.version)
    if not arguments.twin_only:
        exe = build_installer(arguments.output, arguments.version, arguments.keys)
        name_installer(arguments.output, exe)
        sign(arguments.output / "release.json", arguments.keys, arguments.signing_key, arguments.signing_folder)
        print(exe)
    if arguments.twin_url:
        print(build_twin(arguments.output, arguments.version, arguments.twin_url, arguments.twin_keys,
                         arguments.twin_signing_key, arguments.twin_signing_folder or arguments.signing_folder))


if __name__ == "__main__":
    main()
