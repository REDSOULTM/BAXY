"""Build the two wheels that keep BAXY's runtime lock free of what it does not use, and package them identified.

numpy: the official Windows wheel carries OpenBLAS, the gfortran runtime and libquadmath (LGPL-2.1-or-later) in numpy.libs.
This builds the same 1.26.4 from its source without BLAS (allow-noblas, https://github.com/numpy/numpy/issues/24703), with
numpy's own LAPACK subset: BSD-3-Clause and what numpy bundles. Slower linear algebra is the known price; measured with the voice
in runtime_wheels/README.md.
silero-vad: voice.Vad only reads its silero_vad.onnx, without importing the package, but its metadata asks for torch and
torchaudio. The wheel is the official one, with those two requirements gone.

Windows x64, Python 3.12 and Visual Studio 2022's C++ tools:
    py -3.12 scripts/build_runtime_wheels.py --work-dir <folder> --vcvars <vcvars64.bat>
"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import io
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import urllib.request
import venv
import zipfile


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "runtime_wheels"
NUMPY_VERSION = "1.26.4"
NUMPY_LOCAL = "1.26.4+baxy.1"
NUMPY_SDIST_URL = (
    "https://files.pythonhosted.org/packages/65/6e/"
    "09db70a523a96d25e115e71cc56a6f9031e7b8cd166c1ac8438307c14058/numpy-1.26.4.tar.gz"
)
NUMPY_SDIST_SHA256 = "2a02aba9ed12e4ac4eb3ea9421c420301a0c6460d9830d74a9df87efa4912010"
SILERO_VERSION = "6.2.1"
SILERO_LOCAL = "6.2.1+baxy.1"
SILERO_URL = (
    "https://files.pythonhosted.org/packages/0b/2b/"
    "48566f29a8b53d856ceb1994f209122749b3fda0a733a07e82047257de7a/silero_vad-6.2.1-py3-none-any.whl"
)
SILERO_SHA256 = "09de93c4d874bb19c53e62a47dd38be5f163cedad2b5599583231f2a84ef79cb"
DATE = (2026, 11, 6, 0, 0, 0)
# numpy's pyproject.toml asks for ranges; these are the versions inside them this was built with.
BUILD_TOOLS = "meson-python==0.15.0\nCython==3.0.12\n"
# Their licenses say which notices of numpy's source apply to code in the wheel. tools/wheels/ describes the official wheels'
# OpenBLAS, gfortran and libquadmath, which are not in this one; the rest only build or document.
NOT_IN_THE_WHEEL = ("vendored-meson/", "tools/", ".spin/", "doc/")
# The first comment of each: dragon4.c's is its license; _pocketfft.c's points to a text the source does not carry (licenses/pocketfft-LICENSE.md).
NOTICE_IN_THE_SOURCE = ("numpy/core/src/multiarray/dragon4.c", "numpy/fft/_pocketfft.c")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def pinned(path: Path, url: str, sha256: str) -> bytes:
    if not path.exists():
        with urllib.request.urlopen(url, timeout=120) as response:
            path.write_bytes(response.read())
    data = path.read_bytes()
    if digest(data) != sha256:
        raise RuntimeError(f"{path.name}_hash_mismatch")
    return data


def relabel(
    wheel: bytes, name: str, version: str, local: str, notice: str,
    drop_requires: tuple[str, ...] = (), extra: dict[str, bytes] | None = None,
) -> bytes:
    """The same wheel under its local version, with what changed said inside it and a new RECORD."""
    old_info = f"{name}-{version}.dist-info"
    new_info = f"{name}-{local}.dist-info"
    members: dict[str, bytes] = {}
    with zipfile.ZipFile(io.BytesIO(wheel)) as archive:
        for entry in archive.infolist():
            if entry.is_dir() or entry.filename == f"{old_info}/RECORD":
                continue
            members[entry.filename.replace(old_info, new_info)] = archive.read(entry)
    metadata = members[f"{new_info}/METADATA"].replace(b"\r\n", b"\n")
    if metadata.count(f"\nVersion: {version}\n".encode()) != 1:
        raise RuntimeError("wheel_metadata_unexpected")
    metadata = metadata.replace(f"\nVersion: {version}\n".encode(), f"\nVersion: {local}\n".encode())
    for requirement in drop_requires:
        metadata, count = re.subn(rb"(?m)^Requires-Dist: " + requirement.encode() + rb"\b(?![^\n]*extra ==)[^\n]*\n", b"", metadata)
        if count != 1:
            raise RuntimeError("wheel_requirement_unexpected")
    members[f"{new_info}/METADATA"] = metadata
    members[f"{new_info}/BAXY-NOTICE.txt"] = notice.encode()
    for path, data in (extra or {}).items():
        members[f"{new_info}/{path}"] = data
    record = io.StringIO(newline="")
    writer = csv.writer(record, lineterminator="\n")
    for member, data in sorted(members.items()):
        encoded = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=")
        writer.writerow([member, "sha256=" + encoded.decode(), len(data)])
    writer.writerow([f"{new_info}/RECORD", "", ""])
    members[f"{new_info}/RECORD"] = record.getvalue().encode()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for member, data in sorted(members.items()):
            entry = zipfile.ZipInfo(member, date_time=DATE)
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, data, compresslevel=9)
    return buffer.getvalue()


def bundled_licenses(sdist: Path) -> dict[str, bytes]:
    """The notices of what numpy's source bundles, which its LICENSE.txt only points to. The vendored Meson only builds."""
    found: dict[str, bytes] = {}
    with tarfile.open(sdist) as archive:
        for member in archive.getmembers():
            inner = member.name.split("/", 1)[-1]
            reader = archive.extractfile(member) if member.isfile() else None
            if reader is None or inner == "LICENSE.txt" or inner.startswith(NOT_IN_THE_WHEEL):
                continue
            if re.match(r"LICEN[SC]E", Path(inner).name):
                found["bundled/" + inner.replace("/", "__")] = reader.read()
            elif inner in NOTICE_IN_THE_SOURCE:
                comment = re.match(rb"/\*.*?\*/", reader.read(), re.DOTALL)
                if comment is None:
                    raise RuntimeError(f"{inner}_notice_missing")
                found["bundled/" + inner.replace("/", "__") + ".NOTICE.txt"] = comment.group()
    return found


def write_wheel(output: Path, wheel: bytes) -> Path:
    if output.exists() and output.read_bytes() != wheel:
        raise RuntimeError("wheel_differs_use_new_version_after_review")
    output.write_bytes(wheel)
    print(output.name, digest(wheel))
    return output


def build_numpy(work: Path, vcvars: Path) -> Path:
    sdist = work / "numpy-1.26.4.tar.gz"
    pinned(sdist, NUMPY_SDIST_URL, NUMPY_SDIST_SHA256)
    builder = work / "builder"
    if not builder.exists():
        venv.create(builder, with_pip=True)
    out = work / "wheel"
    out.mkdir(exist_ok=True)
    built = out / f"numpy-{NUMPY_VERSION}-cp312-cp312-win_amd64.whl"
    if not built.exists():
        temporary = work / "tmp"
        temporary.mkdir(exist_ok=True)
        tools = work / "build-tools.txt"
        tools.write_text(BUILD_TOOLS, encoding="utf-8")
        environment = dict(os.environ, TMP=str(temporary), TEMP=str(temporary), PIP_NO_CACHE_DIR="1", PIP_CONSTRAINT=str(tools))
        subprocess.run(
            f'"{vcvars}" >nul && "{builder / "Scripts" / "python.exe"}" -X utf8 -m pip wheel '
            f'--disable-pip-version-check --no-deps --no-binary numpy "{sdist}" -w "{out}" '
            "-Csetup-args=-Dallow-noblas=true -Csetup-args=-Dblas=none -Csetup-args=-Dlapack=none",
            shell=True, check=True, env=environment,
        )
    wheel = relabel(
        built.read_bytes(), "numpy", NUMPY_VERSION, NUMPY_LOCAL,
        "BAXY build of numpy 1.26.4 (BSD-3-Clause) from its unchanged source, with no BLAS: no OpenBLAS, no gfortran\n"
        "runtime, no libquadmath. Options: allow-noblas=true, blas=none, lapack=none.\n"
        f"Source: {NUMPY_SDIST_URL} (SHA-256 {NUMPY_SDIST_SHA256}).\n",
        extra=bundled_licenses(sdist),
    )
    return write_wheel(ASSETS / f"numpy-{NUMPY_LOCAL}-cp312-cp312-win_amd64.whl", wheel)


def build_silero(work: Path) -> Path:
    official = pinned(work / f"silero_vad-{SILERO_VERSION}-py3-none-any.whl", SILERO_URL, SILERO_SHA256)
    wheel = relabel(
        official, "silero_vad", SILERO_VERSION, SILERO_LOCAL,
        "The official silero-vad 6.2.1 wheel (MIT), every file unchanged, without its requirements on torch and torchaudio:\n"
        "BAXY reads data/silero_vad.onnx and never imports the package.\n"
        f"Source: {SILERO_URL} (SHA-256 {SILERO_SHA256}).\n",
        drop_requires=("torch", "torchaudio"),
    )
    return write_wheel(ASSETS / f"silero_vad-{SILERO_LOCAL}-py3-none-any.whl", wheel)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", required=True, type=Path)
    parser.add_argument("--vcvars", required=True, type=Path)
    args = parser.parse_args()
    if sys.platform != "win32" or sys.version_info[:2] != (3, 12):
        raise RuntimeError("runtime_wheels_build_requires_windows_python312")
    work = args.work_dir.resolve()
    work.mkdir(parents=True, exist_ok=True)
    build_numpy(work, args.vcvars)
    build_silero(work)


if __name__ == "__main__":
    main()
