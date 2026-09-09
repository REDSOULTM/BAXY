"""Build the pinned Windows ASR extension and package its identified local wheel.

The upstream Python wrapper and licenses are retained; only the NeMo per-stream
decoder extension, package version and RECORD change. Users install the wheel,
not the compiler. Run with the registered Python 3.12 and VS2022 CMake.
"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import urllib.request
import zipfile


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "runtime_wheels"
VERSION = "1.13.4+baxy.1"
COMMIT = "142807252687d81b40d6315f23470a1512a00de3"
OWNER = "sherpa-onnx/csrc/offline-recognizer-transducer-nemo-impl.h"
PATCH_SHA256 = "591291b2aa961cbd57700a6e73f63da969811620ea294cedb0376164ad58a163"
UPSTREAM_URL = (
    "https://files.pythonhosted.org/packages/bb/bb/"
    "1e723ab703a1e354f390de19981ec0c347576f87be01915d826dc6fc9f41/"
    "sherpa_onnx-1.13.4-cp312-cp312-win_amd64.whl"
)
UPSTREAM_SHA256 = "b8436ffe2763b3fd522fbac8fe53f47d611721c84819c241acfb65d122403d7d"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run(*args: str) -> None:
    subprocess.run(args, check=True)


def build(work: Path, cmake: Path) -> Path:
    if sys.platform != "win32" or sys.version_info[:2] != (3, 12):
        raise RuntimeError("sherpa_build_requires_windows_python312")
    source = work / "source"
    native_build = work / "build"
    patch = ASSETS / "sherpa-nemo-stream-decoder.patch"
    if digest(patch.read_bytes()) != PATCH_SHA256:
        raise RuntimeError("sherpa_patch_hash_mismatch")
    if not source.exists():
        run("git", "clone", "--depth", "1", "--branch", "v1.13.4",
            "--single-branch", "https://github.com/k2-fsa/sherpa-onnx.git", str(source))
    head = subprocess.check_output(
        ["git", "-C", str(source), "rev-parse", "HEAD"], text=True,
    ).strip()
    if head != COMMIT:
        raise RuntimeError("sherpa_source_revision_mismatch")
    changed = subprocess.check_output(
        ["git", "-C", str(source), "diff", "--name-only", "HEAD"], text=True,
    ).splitlines()
    if not changed:
        run("git", "-C", str(source), "apply", "--check", str(patch))
        run("git", "-C", str(source), "apply", str(patch))
    elif changed != [OWNER]:
        raise RuntimeError("sherpa_source_has_other_changes")
    # Reverse-check proves this exact patch is present; no reset or overwrite.
    run("git", "-C", str(source), "apply", "--reverse", "--check", str(patch))
    actual_patch = subprocess.check_output(
        ["git", "-C", str(source), "diff", "--no-ext-diff", "HEAD", "--", OWNER]
    )
    if actual_patch.replace(b"\r\n", b"\n") != patch.read_bytes().replace(b"\r\n", b"\n"):
        raise RuntimeError("sherpa_source_patch_mismatch")
    run(str(cmake), "-S", str(source), "-B", str(native_build),
        "-G", "Visual Studio 17 2022", "-A", "x64",
        "-DSHERPA_ONNX_ENABLE_PYTHON=ON", f"-DPython_EXECUTABLE={sys.executable}",
        "-DSHERPA_ONNX_ENABLE_PORTAUDIO=OFF", "-DSHERPA_ONNX_ENABLE_WEBSOCKET=OFF",
        "-DSHERPA_ONNX_ENABLE_BINARY=OFF", "-DSHERPA_ONNX_ENABLE_C_API=OFF",
        "-DSHERPA_ONNX_BUILD_C_API_EXAMPLES=OFF",
        "-DSHERPA_ONNX_USE_PRE_INSTALLED_ONNXRUNTIME_IF_AVAILABLE=OFF")
    run(str(cmake), "--build", str(native_build), "--config", "Release",
        "--target", "_sherpa_onnx", "--parallel", "4")
    extension = native_build / "lib/Release/_sherpa_onnx.cp312-win_amd64.pyd"
    return package(extension, work)


def package(extension: Path, work: Path) -> Path:
    upstream = work / "sherpa_onnx-1.13.4-cp312-cp312-win_amd64.whl"
    if not upstream.exists():
        with urllib.request.urlopen(UPSTREAM_URL, timeout=60) as response:
            data = response.read(16 * 1024 * 1024)
        if digest(data) != UPSTREAM_SHA256:
            raise RuntimeError("sherpa_upstream_wheel_hash_mismatch")
        upstream.write_bytes(data)
    if digest(upstream.read_bytes()) != UPSTREAM_SHA256:
        raise RuntimeError("sherpa_upstream_wheel_hash_mismatch")
    old_info = "sherpa_onnx-1.13.4.dist-info"
    new_info = f"sherpa_onnx-{VERSION}.dist-info"
    members: dict[str, bytes] = {}
    with zipfile.ZipFile(upstream) as archive:
        for entry in archive.infolist():
            if entry.is_dir() or entry.filename == f"{old_info}/RECORD":
                continue
            members[entry.filename.replace(old_info, new_info)] = archive.read(entry)
    native_name = "sherpa_onnx/lib/_sherpa_onnx.cp312-win_amd64.pyd"
    if native_name not in members:
        raise RuntimeError("sherpa_upstream_extension_missing")
    members[native_name] = extension.read_bytes()
    metadata = f"{new_info}/METADATA"
    if members[metadata].count(b"\nVersion: 1.13.4") != 1:
        raise RuntimeError("sherpa_upstream_metadata_unexpected")
    members[metadata] = members[metadata].replace(
        b"\nVersion: 1.13.4", f"\nVersion: {VERSION}".encode(), 1,
    )
    initializer = "sherpa_onnx/__init__.py"
    old_version = b"__version__ = '1.13.4'"
    if members[initializer].count(old_version) != 1:
        raise RuntimeError("sherpa_upstream_version_unexpected")
    members[initializer] = members[initializer].replace(
        old_version, f"__version__ = '{VERSION}'".encode(),
    )
    notice = {
        "upstreamCommit": COMMIT, "upstreamWheelSha256": UPSTREAM_SHA256,
        "patchSha256": PATCH_SHA256, "extensionSha256": digest(members[native_name]),
        "change": "NeMo per-stream greedy decoder shares the configured model; contextual beam stays unchanged.",
        "profile": "Windows x64, CPython3.12, VS2022 Release, ONNX Runtime1.27.0 CPU",
    }
    members["sherpa_onnx/baxy_native_build.json"] = (
        json.dumps(notice, indent=2) + "\n"
    ).encode()
    members[f"{new_info}/BAXY-NOTICE.txt"] = (
        "BAXY modification of sherpa-onnx 1.13.4 (Apache-2.0).\n"
        "Adds explicit per-stream greedy decoding with the existing NeMo model.\n"
        "The upstream wrapper, licenses and dependency on official core remain.\n"
    ).encode()
    record = io.StringIO(newline="")
    writer = csv.writer(record, lineterminator="\n")
    for name, data in sorted(members.items()):
        encoded = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=")
        writer.writerow([name, "sha256=" + encoded.decode(), len(data)])
    writer.writerow([f"{new_info}/RECORD", "", ""])
    members[f"{new_info}/RECORD"] = record.getvalue().encode()
    output = ASSETS / f"sherpa_onnx-{VERSION}-cp312-cp312-win_amd64.whl"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(members.items()):
            entry = zipfile.ZipInfo(name, date_time=(2026, 9, 7, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, data, compresslevel=9)
    wheel = buffer.getvalue()
    if output.exists() and output.read_bytes() != wheel:
        raise RuntimeError("sherpa_existing_wheel_differs_use_new_version_after_review")
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
