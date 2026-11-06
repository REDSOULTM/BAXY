"""Whether BAXY's package carries what licenses/THIRD_PARTY_NOTICES.md says it left out in 1.3.0. Metadata is not enough:
sherpa-onnx declared Apache-2.0 with eSpeak NG compiled in, and numpy BSD with libquadmath in its OpenBLAS. So this reads the
bytes of every binary, and takes as Python packages only those of the lock.

    <python> -X utf8 scripts/check_package_licenses.py --depot <package folder> --lock pylock.runtime-win-x64.toml

It only looks for what left, by the marks it leaves. It does not see inside the compressed bundles of Baxy.exe and baxy-core.exe, nor
read license texts: those are for a person.
The same guard for a program that ships sherpa-onnx: https://raw.githubusercontent.com/rootMonsteR/holdtospeak/main/THIRD-PARTY-NOTICES.md
"""
from __future__ import annotations

import argparse
import fnmatch
import re
import sys
import tomllib
from pathlib import Path

BINARIES = {".dll", ".pyd", ".exe"}
# In the lock because ONNX Runtime's metadata asks for it; build_steam.ps1 takes it out: its _message.pyd is built with GCC.
LOCKED_BUT_NOT_SHIPPED = {"protobuf"}
# What each of them leaves in a binary (measured in 1.2.0's: espeak_ng_Initialize, «Intel(R) oneAPI Math Kernel Library Version»...).
MARKERS = {
    b"espeak_": "eSpeak NG (GPL-3.0-or-later)",
    b"espeak-ng": "eSpeak NG (GPL-3.0-or-later)",
    b"phonemize_eSpeak": "piper-phonemize with eSpeak NG (GPL-3.0-or-later)",
    b"libquadmath": "libquadmath (LGPL-2.1-or-later)",
    b"libgfortran": "the gfortran runtime",
    b"Intel(R) oneAPI Math Kernel": "Intel oneMKL",
    b"Steinberg": "Steinberg's ASIO",
    b"GCC: (": "a binary built with GCC, with its runtime inside",
    b"ingw-w64": "a binary built with mingw-w64, with its runtime inside",
}
FILES = {
    "*asio*.dll": "Steinberg's ASIO",
    "libopenblas*": "OpenBLAS with the gfortran runtime and libquadmath",
    "libiomp*": "Intel OpenMP",
    "mkl_*.dll": "Intel oneMKL",
    "sherpa-onnx-c-api.dll": "eSpeak NG (GPL-3.0-or-later)",
}


def normalized(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def locked(lock: Path) -> set[str]:
    with lock.open("rb") as stream:
        return {normalized(package["name"]) for package in tomllib.load(stream)["packages"]}


def findings(depot: Path, lock: Path) -> list[str]:
    found: list[str] = []
    for path in depot.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(depot).as_posix()
        if "espeak-ng-data/" in relative:
            found.append(f"{relative}: eSpeak NG's data (GPL-3.0-or-later)")
        for pattern, what in FILES.items():
            if fnmatch.fnmatch(path.name.lower(), pattern):
                found.append(f"{relative}: {what}")
        if path.suffix.lower() in BINARIES:
            data = path.read_bytes()
            found += sorted({f"{relative}: {what}" for marker, what in MARKERS.items() if marker in data})
    allowed = locked(lock) - LOCKED_BUT_NOT_SHIPPED
    site = depot / "python" / "Lib" / "site-packages"
    for info in site.glob("*.dist-info") if site.is_dir() else ():
        name = info.name.removesuffix(".dist-info").rsplit("-", 1)[0]
        if normalized(name) not in allowed:
            found.append(f"{info.relative_to(depot).as_posix()}: not in {lock.name}")
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--depot", required=True, type=Path)
    parser.add_argument("--lock", required=True, type=Path)
    arguments = parser.parse_args()
    found = findings(arguments.depot, arguments.lock)
    for line in found:
        print(line, file=sys.stderr)
    print(f"package_licenses: {len(found)} findings")
    return 1 if found else 0


if __name__ == "__main__":
    raise SystemExit(main())
