"""The release assets that give the source of what the GPL covers in BAXY's package (licenses/FUENTES_GPL.md): eSpeak NG,
piper-phonemize and sherpa-onnx at the exact versions in the package, with BAXY's changes, and what sherpa-onnx compiles in
with them. GPL-3.0 sections 1 and 6 ask for the Corresponding Source, including the scripts that build it; section 6(d) lets
it be offered from the same place as the object code.

    py -3.12 scripts/build_source_assets.py --output <folder> --version 1.2.1 [--cache <folder>]

Each download is held to the SHA-256 that sherpa-onnx v1.13.4 pins in its cmake/ folder (for kissfft and kaldifst, the
kaldi-native-fbank and kaldi-decoder it pins), under the name its CMake looks for in Downloads. The list is what its CMake
configure resolves with the options of build_sherpa_runtime.py (measured 2026-11-06); googletest only builds its tests and ONNX
Runtime comes prebuilt."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
import urllib.request
import zipfile
from pathlib import Path

import build_sherpa_runtime as sherpa

REPOSITORY = Path(__file__).resolve().parent.parent
GITHUB = "https://github.com"
ESPEAK = (
    "espeak-ng-ed530aa-source.zip",
    f"{GITHUB}/csukuangfj/espeak-ng/archive/ed530aa113046142eb5115cf2fc9157854d0ffe1.zip",
    "e4e262cbe34f7fe21f91f1ba3397f2728e1f30eafbae7853f2b753a9ed13f0dd",
)
PIPER = (
    "piper-phonemize-f3ff95a-source.zip",
    f"{GITHUB}/csukuangfj/piper-phonemize/archive/f3ff95afc03640bc1399e113e83361192a2fafb4.zip",
    "d9cca4e2bdc7d6dd8dffb96a4668283dbd3f77a9c194a3e530c1e8eba9406a5d",
)
SHERPA_ASSET = "sherpa-onnx-1.13.4-baxy.2-source.zip"
DEPENDENCIES_ASSET = "sherpa-onnx-1.13.4-dependencies-source.zip"
DEPENDENCIES = (
    ("pybind11-3.0.0.tar.gz", f"{GITHUB}/pybind/pybind11/archive/refs/tags/v3.0.0.tar.gz",
     "453b1a3e2b266c3ae9da872411cadb6d693ac18063bd73226d96cfb7015a200c"),
    ("kaldi-native-fbank-1.22.3.tar.gz", f"{GITHUB}/csukuangfj/kaldi-native-fbank/archive/refs/tags/v1.22.3.tar.gz",
     "9176cc66fc7ce1edf85cf355b06e320c57db6297df74277f575183468893cf61"),
    ("kissfft-febd4caeed32e33ad8b2e0bb5ea77542c40f18ec.zip", f"{GITHUB}/mborgerding/kissfft/archive/febd4caeed32e33ad8b2e0bb5ea77542c40f18ec.zip",
     "497103e664168ebe39580b757adbe616f6cf85a16572af581ca7bc42d0ab13fd"),
    ("kaldi-decoder-0.3.0.tar.gz", f"{GITHUB}/k2-fsa/kaldi-decoder/archive/refs/tags/v0.3.0.tar.gz",
     "b9f34cfb4fd3b1344100eead79ef4d37aa15962274b9e3056de345021f76a1b0"),
    ("kaldifst-1.8.0.tar.gz", f"{GITHUB}/k2-fsa/kaldifst/archive/refs/tags/v1.8.0.tar.gz",
     "3f247b7e5a2409071202f5e2bc6200060f66728c0a3443c03923ad2723e040b3"),
    ("openfst-1.8.5-2026-04-11.tar.gz", f"{GITHUB}/csukuangfj/openfst/archive/refs/tags/v1.8.5-2026-04-11.tar.gz",
     "57fbc4b950ae81b1a0e1e298af15652da968a6723a592b7874e9b4027a80a5b4"),
    ("eigen-5.0.1.tar.gz", "https://gitlab.com/libeigen/eigen/-/archive/5.0.1/eigen-5.0.1.tar.gz",
     "e9c326dc8c05cd1e044c71f30f1b2e34a6161a3b6ecf445d56b53ff1669e3dec"),
    ("simple-sentencepiece-0.7.tar.gz", f"{GITHUB}/pkufool/simple-sentencepiece/archive/refs/tags/v0.7.tar.gz",
     "1748a822060a35baa9f6609f84efc8eb54dc0e74b9ece3d82367b7119fdc75af"),
    ("json-3.12.0.tar.gz", f"{GITHUB}/nlohmann/json/archive/refs/tags/v3.12.0.tar.gz",
     "4b92eb0c06d10683f7447ce9406cb97cd4b453be18d7279320f7b2f025c10187"),
    ("hclust-cpp-2026-02-25.tar.gz", f"{GITHUB}/csukuangfj/hclust-cpp/archive/refs/tags/2026-02-25.tar.gz",
     "8f14e024c709d73afb40ae69cb22de4b73dba67cbce40f2e518813da8139ab56"),
    ("googletest-1.13.0.tar.gz", f"{GITHUB}/google/googletest/archive/refs/tags/v1.13.0.tar.gz",
     "ad7fdba11ea011c1d925b3289cf4af2c66a352e18d4c7264392fead75e919363"),
)
FIXED_TIME = (2026, 11, 6, 0, 0, 0)
SHERPA_README = """BAXY's sherpa-onnx 1.13.4+baxy.2 / el sherpa-onnx 1.13.4+baxy.2 de BAXY

The binaries built from this, with eSpeak NG inside, go as a whole under GPL-3.0-or-later (GPL-3.0.txt in BAXY's licenses folder).
BAXY's changes date from no later than 2026-09-08. / Los binarios compilados de esto, con eSpeak NG dentro, van como obra entera bajo
GPL-3.0-or-later (GPL-3.0.txt en la carpeta licenses de BAXY). Los cambios de BAXY son de, a más tardar, el 2026-09-08.

sherpa-onnx-1.13.4/ is the tree of tag v1.13.4, commit {commit}, unchanged.
BAXY changes it with the two patches in runtime_wheels/, and builds its extension (_sherpa_onnx.cp312-win_amd64.pyd) with
scripts/build_sherpa_runtime.py. It needs Windows x64, Python 3.12, Git and Visual Studio 2022's CMake:

    py -3.12 scripts/build_sherpa_runtime.py --work-dir <folder> --cmake <cmake.exe>

That script clones the tag again, downloads what sherpa-onnx's CMake pins, and takes the rest of the wheel from the official
sherpa-onnx 1.13.4 wheel. Without those servers, to build the extension from this tree:

1. Put in %USERPROFILE%\\Downloads the archives of {dependencies}, and the eSpeak NG and piper-phonemize assets renamed
   espeak-ng-ed530aa113046142eb5115cf2fc9157854d0ffe1.zip and piper-phonemize-f3ff95afc03640bc1399e113e83361192a2fafb4.zip:
   sherpa-onnx's CMake takes them from there. Set HOME to %USERPROFILE% if it is not set.
2. Apply the patches: cd sherpa-onnx-1.13.4, then patch -p1 < ../runtime_wheels/<each>.patch (or git apply).
3. Configure and build with the options in scripts/build_sherpa_runtime.py (the "run(str(cmake)" lines).

CMake also asks for a prebuilt ONNX Runtime 1.27.0 (MIT), which is not in these assets: put
onnxruntime-win-x64-MT-Release-1.27.0.tar.bz2 in Downloads too, from
https://github.com/csukuangfj/onnxruntime-libs/releases/tag/v1.27.0. Its source is at
https://github.com/microsoft/onnxruntime/tree/v1.27.0.

The rebuilt binary is not promised to be identical byte by byte across compilers or folders.
sherpa-onnx-c-api.dll and the rest of sherpa-onnx-core come unchanged from the project's official wheel of the same version.

sherpa-onnx-1.13.4/ es el árbol del tag v1.13.4, sin cambios. BAXY lo cambia con los dos parches de runtime_wheels/ y compila su
extensión con scripts/build_sherpa_runtime.py, con la orden de arriba, que necesita Windows x64, Python 3.12, Git, el CMake de Visual
Studio 2022 y esos servidores; sin ellos, con los tres
pasos de arriba y además onnxruntime-win-x64-MT-Release-1.27.0.tar.bz2 (MIT) en Downloads, que no va en estos activos: se baja de
https://github.com/csukuangfj/onnxruntime-libs/releases/tag/v1.27.0, y su fuente está en
https://github.com/microsoft/onnxruntime/tree/v1.27.0. No se promete que el binario salga idéntico byte a byte con otro compilador u otra carpeta. sherpa-onnx-c-api.dll y lo demás de
sherpa-onnx-core vienen sin cambios de la rueda oficial de esa versión.
"""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch(url: str, sha256: str, cache: Path) -> bytes:
    """The bytes at ``url``, only when they are the pinned ones; the cache is by hash, so it cannot serve others."""
    kept = cache / sha256
    if kept.is_file():
        data = kept.read_bytes()
    else:
        request = urllib.request.Request(url, headers={"User-Agent": "BAXY-release"})
        with urllib.request.urlopen(request, timeout=300) as response:
            data = response.read()
    if _sha256(data) != sha256:
        raise SystemExit(f"{url} is not what was pinned: {_sha256(data)}")
    cache.mkdir(parents=True, exist_ok=True)
    kept.write_bytes(data)
    return data


def sherpa_tree(target: Path, work: Path) -> None:
    """The tree of sherpa-onnx's pinned commit as a zip, with the bytes of the commit whatever Git's line-ending settings."""
    source = work / "sherpa-onnx"
    subprocess.run(
        ["git", "clone", "-q", "--depth", "1", "--branch", "v1.13.4", "--single-branch",
         "https://github.com/k2-fsa/sherpa-onnx.git", str(source)],
        check=True,
    )
    head = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    if head != sherpa.COMMIT:
        raise SystemExit(f"sherpa-onnx v1.13.4 is {head}, not {sherpa.COMMIT}")
    subprocess.run(
        ["git", "-c", "core.autocrlf=false", "-C", str(source), "archive", "--format=zip",
         "--prefix=sherpa-onnx-1.13.4/", f"--output={target}", sherpa.COMMIT],
        check=True,
    )


def _add(archive: zipfile.ZipFile, name: str, data: bytes, method: int = zipfile.ZIP_DEFLATED) -> None:
    entry = zipfile.ZipInfo(name, date_time=FIXED_TIME)
    entry.compress_type = method
    archive.writestr(entry, data)


def build_sherpa(target: Path, work: Path) -> None:
    """sherpa-onnx's tree with BAXY's changes beside it, unapplied: the patches, and the script with its folder layout."""
    sherpa_tree(target, work)
    assets = REPOSITORY / "runtime_wheels"
    patches = (
        ("sherpa-nemo-stream-decoder.patch", sherpa.PATCH_SHA256),
        ("sherpa-nemo-normalization.patch", sherpa.NORMALIZATION_PATCH_SHA256),
    )
    readme = SHERPA_README.format(commit=sherpa.COMMIT, dependencies=DEPENDENCIES_ASSET)
    with zipfile.ZipFile(target, "a", zipfile.ZIP_DEFLATED) as archive:
        _add(archive, "README-BAXY.txt", readme.encode())
        for name, pinned in patches:
            patch = (assets / name).read_bytes()
            if _sha256(patch) != pinned:
                raise SystemExit(f"{name} is not the patch the build script applies")
            _add(archive, f"runtime_wheels/{name}", patch)
        _add(archive, "scripts/build_sherpa_runtime.py", (REPOSITORY / "scripts" / "build_sherpa_runtime.py").read_bytes())


def build_dependencies(target: Path, cache: Path) -> None:
    """What sherpa-onnx's CMake compiles into the binaries with eSpeak NG, as it downloads them. They do not compress."""
    lines = [
        "What sherpa-onnx v1.13.4 compiles into its binaries beside eSpeak NG and piper-phonemize, as its CMake downloads it.",
        "Lo que sherpa-onnx v1.13.4 compila en sus binarios junto a eSpeak NG y piper-phonemize, tal como lo baja su CMake.",
        "",
        "googletest only builds the tests of the build script / googletest sólo compila las pruebas del script.",
        "Not here / no está aquí: ONNX Runtime 1.27.0, which the package carries prebuilt:",
        "https://github.com/microsoft/onnxruntime/tree/v1.27.0",
        "",
    ]
    with zipfile.ZipFile(target, "w", zipfile.ZIP_STORED) as archive:
        for name, url, sha256 in DEPENDENCIES:
            _add(archive, name, fetch(url, sha256, cache), zipfile.ZIP_STORED)
            lines.append(f"{name}  {url}  SHA-256 {sha256}")
        _add(archive, "README-BAXY.txt", ("\n".join(lines) + "\n").encode(), zipfile.ZIP_DEFLATED)


def build_licenses(target: Path) -> None:
    """The notices and the license texts of licenses/, for whoever wants to read them without installing."""
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        _add(archive, "BAXY-LICENSE.txt", (REPOSITORY / "LICENSE").read_bytes())
        _add(archive, "THIRD_PARTY_NOTICES.md", (REPOSITORY / "THIRD_PARTY_NOTICES.md").read_bytes())
        _add(archive, "LICENSE-llama.cpp.txt", (REPOSITORY / "scripts" / "llama" / "LICENSE-llama.cpp.txt").read_bytes())
        for path in sorted((REPOSITORY / "licenses").iterdir()):
            _add(archive, path.name, path.read_bytes())


def build_assets(output: Path, version: str, cache: Path) -> dict[str, str]:
    output.mkdir(parents=True, exist_ok=True)
    for name, url, sha256 in (ESPEAK, PIPER):
        (output / name).write_bytes(fetch(url, sha256, cache))
    with tempfile.TemporaryDirectory(prefix="baxy-sources-") as work:
        build_sherpa(output / SHERPA_ASSET, Path(work))
    build_dependencies(output / DEPENDENCIES_ASSET, cache)
    licenses = f"baxy-{version}-licenses.zip"
    build_licenses(output / licenses)
    names = [ESPEAK[0], PIPER[0], SHERPA_ASSET, DEPENDENCIES_ASSET, licenses]
    return {name: _sha256((output / name).read_bytes()) for name in names}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--cache", type=Path)
    arguments = parser.parse_args()
    print(json.dumps(build_assets(arguments.output, arguments.version, arguments.cache or arguments.output.parent / "source-cache"), indent=1))


if __name__ == "__main__":
    main()
