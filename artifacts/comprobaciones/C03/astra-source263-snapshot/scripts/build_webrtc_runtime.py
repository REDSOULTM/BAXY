"""Build BAXY's pinned AEC3 linear-output extension for Windows/Python 3.12.

Only the binding exports an additional signal; the vendored DSP is unchanged.
The MSVC runtime is linked statically. Consumers need the wheel, not a compiler.
"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tarfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "runtime_wheels"
VERSION = "0.2.0+baxy.1"
OWNER = "bindings/webrtc_audio_bindings.cpp"
PATCH_SHA256 = "548763188c319936ae00475b03885e75bf986d1917b8bba8b86ed1746f0fe020"
PATCHED_OWNER_SHA256 = "21cefa8d2f7f94e2044316226555502ba647747edce056f0f1af6bd14da9fdf0"
SOURCE = (
    "pywebrtc_audio-0.2.0.tar.gz",
    "https://files.pythonhosted.org/packages/d8/b0/8d9e93083ac412cc758003d5e216d44f69b50619cdd0cfc7897e576eb90c/pywebrtc_audio-0.2.0.tar.gz",
    "cdc47c063439b033bdd6110d2e1119fd6e36c6e007ed824bc369c9a5e3cb307a",
)
UPSTREAM_WHEEL = (
    "pywebrtc_audio-0.2.0-cp312-cp312-win_amd64.whl",
    "https://files.pythonhosted.org/packages/33/3e/1b9dee1fa750e744a128289c9d8fa991fffc8a2ff89b3285b238b275eb3c/pywebrtc_audio-0.2.0-cp312-cp312-win_amd64.whl",
    "0dabbdadd5d7fd7dcb88323266e5e14d46aaa136c58fa0573c4b0323b683c80b",
)
PYBIND11 = (
    "pybind11-3.0.1-py3-none-any.whl",
    "https://files.pythonhosted.org/packages/cd/8a/37362fc2b949d5f733a8b0f2ff51ba423914cabefe69f1d1b6aab710f5fe/pybind11-3.0.1-py3-none-any.whl",
    "aa8f0aa6e0a94d3b64adfc38f560f33f15e589be2175e103c0a33c6bce55ee89",
)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch(work: Path, asset: tuple[str, str, str]) -> Path:
    name, url, expected = asset
    path = work / name
    if not path.exists():
        with urllib.request.urlopen(url, timeout=60) as response:
            data = response.read(16 * 1024 * 1024)
        if digest(data) != expected:
            raise RuntimeError(f"webrtc_download_hash_mismatch:{name}")
        path.write_bytes(data)
    if digest(path.read_bytes()) != expected:
        raise RuntimeError(f"webrtc_asset_hash_mismatch:{name}")
    return path


def materialize(root: Path, files: dict[str, bytes]) -> None:
    """Write a fresh tree or verify an existing one without replacing edits."""
    for name in files:
        parts = PurePosixPath(name).parts
        if "\\" in name or not parts or any(part in {"..", "."} or ":" in part for part in parts):
            raise ValueError("webrtc_archive_path_invalid")
        if PurePosixPath(name).is_absolute():
            raise ValueError("webrtc_archive_path_invalid")
    if root.exists():
        actual_names = {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}
        if actual_names != set(files):
            raise RuntimeError("webrtc_source_tree_differs")
        for name, data in files.items():
            if (root / name).is_symlink() or (root / name).read_bytes() != data:
                raise RuntimeError(f"webrtc_source_file_differs:{name}")
        return
    root.mkdir(parents=True)
    for name, data in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def build(work: Path, cmake: Path) -> Path:
    if sys.platform != "win32" or sys.version_info[:2] != (3, 12):
        raise RuntimeError("webrtc_build_requires_windows_python312")
    work.mkdir(parents=True, exist_ok=True)
    patch = ASSETS / "webrtc-linear-output.patch"
    if digest(patch.read_bytes()) != PATCH_SHA256:
        raise RuntimeError("webrtc_patch_hash_mismatch")
    archive_path = fetch(work, SOURCE)
    upstream = fetch(work, UPSTREAM_WHEEL)
    pybind = fetch(work, PYBIND11)
    source_files = {}
    with tarfile.open(archive_path) as archive:
        for entry in archive.getmembers():
            if entry.isdir():
                continue
            if not entry.isfile() or not entry.name.startswith("pywebrtc_audio-0.2.0/"):
                raise RuntimeError("webrtc_source_archive_invalid")
            source_files[entry.name.split("/", 1)[1]] = archive.extractfile(entry).read()
    source = work / "source"
    owner = source / OWNER
    if owner.exists():
        normalized = owner.read_bytes().replace(b"\r\n", b"\n")
        if digest(normalized) == PATCHED_OWNER_SHA256:
            owner.write_bytes(normalized)
    # Check the existing patched file separately, then verify every source byte.
    if source.exists() and digest((source / OWNER).read_bytes()) == PATCHED_OWNER_SHA256:
        source_files[OWNER] = (source / OWNER).read_bytes()
    materialize(source, source_files)
    if digest((source / OWNER).read_bytes()) != PATCHED_OWNER_SHA256:
        subprocess.run(["git", "-c", "core.autocrlf=false", "apply", "--check", str(patch)], cwd=source, check=True)
        subprocess.run(["git", "-c", "core.autocrlf=false", "apply", str(patch)], cwd=source, check=True)
    if digest((source / OWNER).read_bytes()) != PATCHED_OWNER_SHA256:
        raise RuntimeError("webrtc_patched_source_mismatch")
    with zipfile.ZipFile(pybind) as archive:
        materialize(work / "pybind11", {
            entry.filename: archive.read(entry)
            for entry in archive.infolist() if not entry.is_dir()
        })
    native_build = work / "build"
    subprocess.run([
        str(cmake), "-S", str(source), "-B", str(native_build),
        "-G", "Visual Studio 17 2022", "-A", "x64",
        f"-DPYTHON_EXECUTABLE={sys.executable}",
        f"-Dpybind11_DIR={work / 'pybind11/pybind11/share/cmake/pybind11'}",
        "-DCMAKE_POLICY_DEFAULT_CMP0091=NEW", "-DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreaded",
    ], check=True)
    subprocess.run([
        str(cmake), "--build", str(native_build), "--config", "Release",
        "--target", "_webrtc_audio", "--parallel", "4",
    ], check=True)
    extension = native_build / "Release/_webrtc_audio.cp312-win_amd64.pyd"
    profile = {
        "python": sys.version,
        "cmake": subprocess.check_output([str(cmake), "--version"], text=True).splitlines()[0],
        "compiler": "Visual Studio 17 2022, x64, Release, static MSVC runtime (/MT)",
    }
    return package(extension, source, upstream, profile)


def package(extension: Path, source: Path, upstream: Path, profile: dict) -> Path:
    old_info = "pywebrtc_audio-0.2.0.dist-info"
    new_info = f"pywebrtc_audio-{VERSION}.dist-info"
    members = {}
    with zipfile.ZipFile(upstream) as archive:
        for entry in archive.infolist():
            name = entry.filename
            if entry.is_dir() or name.startswith("pywebrtc_audio.libs/"):
                continue
            if name in {f"{old_info}/RECORD", f"{old_info}/DELVEWHEEL"}:
                continue
            members[name.replace(old_info, new_info)] = archive.read(entry)
    native_name = "pywebrtc_audio/_webrtc_audio.cp312-win_amd64.pyd"
    members[native_name] = extension.read_bytes()
    # Static CRT needs no delvewheel DLL loader; restore the original source wrapper.
    members["pywebrtc_audio/__init__.py"] = (source / "src/pywebrtc_audio/__init__.py").read_bytes()
    stub = members["pywebrtc_audio/_webrtc_audio.pyi"]
    marker = b"    def reset(self) -> None:"
    stub = stub.replace(marker, (
        b"    def last_linear_frame(self) -> npt.NDArray[np.float32]:\n"
        b'        """Latest 10 ms of linear AEC output at 16 kHz, interleaved channels."""\n'
        b"        ...\n" + marker
    ), 1)
    members["pywebrtc_audio/_webrtc_audio.pyi"] = stub
    metadata = f"{new_info}/METADATA"
    if members[metadata].count(b"\nVersion: 0.2.0\n") != 1:
        raise RuntimeError("webrtc_metadata_unexpected")
    members[metadata] = members[metadata].replace(b"\nVersion: 0.2.0\n", f"\nVersion: {VERSION}\n".encode())
    notice = {
        "version": VERSION, "sourceUrl": SOURCE[1], "sourceSha256": SOURCE[2],
        "upstreamWheelSha256": UPSTREAM_WHEEL[2], "pybind11Sha256": PYBIND11[2],
        "patchSha256": PATCH_SHA256, "extensionSha256": digest(members[native_name]),
        "profile": profile,
        "change": "Export the last linear AEC3 frame. Original DSP/configuration otherwise unchanged; no diagnostic metrics.",
    }
    members["pywebrtc_audio/baxy_native_build.json"] = (json.dumps(notice, indent=2) + "\n").encode()
    members[f"{new_info}/BAXY-NOTICE.txt"] = (
        "BAXY modification of pywebrtc-audio 0.2.0 (Apache-2.0).\n"
        "Exports AEC3's linear signal alongside the original suppressed output.\n"
        "The original bundled third-party licenses and copyright notices are retained.\n"
        "The DSP implementation is unchanged. Built with static MSVC runtime.\n"
    ).encode()
    members[f"{new_info}/licenses/WEBRTC-PATENTS"] = (source / "vendor/webrtc_audio/PATENTS").read_bytes()
    record = io.StringIO(newline="")
    writer = csv.writer(record, lineterminator="\n")
    for name, data in sorted(members.items()):
        encoded = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=")
        writer.writerow([name, "sha256=" + encoded.decode(), len(data)])
    writer.writerow([f"{new_info}/RECORD", "", ""])
    members[f"{new_info}/RECORD"] = record.getvalue().encode()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(members.items()):
            entry = zipfile.ZipInfo(name, date_time=(2026, 9, 7, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, data, compresslevel=9)
    output = ASSETS / f"pywebrtc_audio-{VERSION}-cp312-cp312-win_amd64.whl"
    wheel = buffer.getvalue()
    if output.exists() and output.read_bytes() != wheel:
        raise RuntimeError("webrtc_existing_wheel_differs_use_new_version_after_review")
    output.write_bytes(wheel)
    print(json.dumps({"wheel": str(output), "sha256": digest(wheel), **notice}))
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", required=True, type=Path)
    parser.add_argument("--cmake", required=True, type=Path)
    args = parser.parse_args()
    build(args.work_dir.resolve(), args.cmake.resolve())


if __name__ == "__main__":
    main()
