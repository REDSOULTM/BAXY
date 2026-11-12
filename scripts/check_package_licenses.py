"""Whether BAXY's package carries what licenses/THIRD_PARTY_NOTICES.md says it left out in 1.3.0, a wake detector that left or
BAXY's tuned model (by their bytes). Metadata is not enough:
sherpa-onnx declared Apache-2.0 with eSpeak NG compiled in, and numpy BSD with libquadmath in its OpenBLAS. So this reads the
bytes of every binary, and takes as Python packages only those of the lock.

    <python> -X utf8 scripts/check_package_licenses.py --depot <package folder> --lock pylock.runtime-win-x64.toml

It looks for what left, by the marks it leaves, and for every text of the repository's licenses folder in the package's, byte for
byte. It also refuses what a run of the folder left in it (the hash cache and the bytecode, with this machine's paths inside) and
a package without the files of its store (scripts/package_channel.py: itch.io's manifest and agreement, Steam's uninstall
script). It does not see inside the compressed bundles of Baxy.exe and baxy-core.exe, nor judge what a license text says: that is for a
person.
The same guard for a program that ships sherpa-onnx: https://raw.githubusercontent.com/rootMonsteR/holdtospeak/main/THIRD-PARTY-NOTICES.md
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import re
import sys
import tomllib
from pathlib import Path

# The package's own interpreter runs this, and it is isolated (python312._pth): the folder of the script is not in its path.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import package_channel  # noqa: E402

LICENSES = Path(__file__).resolve().parent.parent / "licenses"
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
# The wake detectors that left, by their head.onnx (size, SHA-256): the same network under any name or folder. k6r-v7b learned
# from a TV series with no license through its teacher k5 (its README); k6r-v7a, the official one since 1.3.2, did not (its
# README and licenses/PALABRA_DE_ACTIVACION.md). v3_b2 was withdrawn with 1.2.0-1.3.0 over its license questions
# (THIRD_PARTY_NOTICES.md). Measured on 2026-11-07 in WakewordBaxy\models\final.
RETIRED_WAKE = {
    (106357952, "de79f68a0ce6fb4b48f62da0e07447d2d387f58ec68d73076be1e1db4f904276"):
        "the wake detector k6r-v7b (it learned from a TV series with no license)",
    (106357952, "7fb6bdeaea1b7fc1bf040221331987034b7e5be574b8f01333e8edd3395bf64e"):
        "the wake detector k6r-v3_b2 (withdrawn over its license questions)",
}
# BAXY's tuned model (c4c2_1-sA, REDSOULTM/BAXY-Qwen3.5-4B-GGUF's BAXY-Qwen3.5-4B-c4-Q4_K_M.gguf), by its size and SHA-256:
# since the owner's order of 2026-11-07 the package carries Qwen3.5-4B as Unsloth publishes it, and the tuned one is
# downloaded only when the person asks (build_steam.ps1, documentacion/PLAN_QWEN_BASE.md).
NOT_SHIPPED_MODELS = {
    (2740937440, "2c445631782a5c27b9948369e9432309528688b9b761fce56586d796ea2f57c7"):
        "BAXY's tuned model (downloaded only when the person asks, never in the package)",
}
# What a run of the folder leaves in it, never shipped: the App's cache of its files' hashes, beside the registration
# (RuntimeFileHashCache), and Python's bytecode. Both carry the paths of the machine that ran it. Steam's upload leaves the same
# two out (the FileExclusion lines of scripts/steam/app_build.vdf) and so do GitHub's archives (scripts/build_github_release.py).
RUN_LEFTOVERS = ("mind-runtime-v1.hash-cache.json", "*__pycache__*")


def normalized(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _sha256(path: Path) -> str:
    """By blocks: a model is 2.7 GB."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 22), b""):
            digest.update(block)
    return digest.hexdigest()


def locked(lock: Path) -> set[str]:
    with lock.open("rb") as stream:
        return {normalized(package["name"]) for package in tomllib.load(stream)["packages"]}


def findings(depot: Path, lock: Path) -> list[str]:
    found: list[str] = []
    known = RETIRED_WAKE | NOT_SHIPPED_MODELS
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
        size = path.stat().st_size
        if any(size == bytes_ for bytes_, _ in known):
            what = known.get((size, _sha256(path)))
            if what:
                found.append(f"{relative}: {what}")
    allowed = locked(lock) - LOCKED_BUT_NOT_SHIPPED
    site = depot / "python" / "Lib" / "site-packages"
    for info in site.glob("*.dist-info") if site.is_dir() else ():
        name = info.name.removesuffix(".dist-info").rsplit("-", 1)[0]
        if normalized(name) not in allowed:
            found.append(f"{info.relative_to(depot).as_posix()}: not in {lock.name}")
    return found


def missing_texts(depot: Path, texts: Path = LICENSES) -> list[str]:
    """The texts of ``texts`` that the package's licenses folder lacks or carries with other bytes."""
    missing = []
    for text in sorted(path for path in texts.iterdir() if path.is_file()):
        shipped = depot / "licenses" / text.name
        if not shipped.is_file():
            missing.append(f"licenses/{text.name}: not in the package")
        elif shipped.read_bytes() != text.read_bytes():
            missing.append(f"licenses/{text.name}: differs from the repository's")
    return missing


def is_run_leftover(relative: str) -> bool:
    """Whether the file at ``relative`` (with /) is one a run of the folder left."""
    return any(fnmatch.fnmatchcase(relative.lower(), pattern) for pattern in RUN_LEFTOVERS)


def run_leftovers(depot: Path) -> list[str]:
    return [
        f"{relative}: left by a run of this folder, with this machine's paths inside (delete it, or build the folder again)"
        for relative in sorted(path.relative_to(depot).as_posix() for path in depot.rglob("*") if path.is_file())
        if is_run_leftover(relative)
    ]


def published_by(depot: Path) -> str | None:
    """The store build_steam.ps1 wrote in the package's distribution.json; none without that file."""
    marker = depot / "distribution.json"
    if not marker.is_file():
        return None
    channel = json.loads(marker.read_text(encoding="utf-8")).get("channel")
    return channel if isinstance(channel, str) else None


def missing_channel_files(depot: Path) -> list[str]:
    """The files of the package's store (package_channel.files) it lacks or carries with other bytes."""
    channel = published_by(depot)
    if channel is None:
        return []
    missing = []
    for name, content in package_channel.files(channel).items():
        shipped = depot / name
        if not shipped.is_file():
            missing.append(f"{name}: not in the package (channel {channel})")
        elif shipped.read_bytes() != content:
            missing.append(f"{name}: differs from the repository's (channel {channel})")
        elif name == ".itch.toml":
            # itch.io's app starts what the manifest names, relative to the folder.
            for action in tomllib.loads(content.decode("utf-8")).get("actions", []):
                if not (depot / action["path"]).is_file():
                    missing.append(f"{name}: its action «{action['name']}» starts {action['path']}, which the package lacks")
    return missing


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--depot", required=True, type=Path)
    parser.add_argument("--lock", required=True, type=Path)
    arguments = parser.parse_args()
    found = (findings(arguments.depot, arguments.lock) + missing_texts(arguments.depot) + run_leftovers(arguments.depot)
             + missing_channel_files(arguments.depot))
    for line in found:
        print(line, file=sys.stderr)
    print(f"package_licenses: {len(found)} findings")
    return 1 if found else 0


if __name__ == "__main__":
    raise SystemExit(main())
