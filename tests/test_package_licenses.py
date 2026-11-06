"""What the notices of 1.3.0 say left the package stays out: in the lock, in the wheels of the repository and in the armed folder."""
from __future__ import annotations

import ast
import sys
import tomllib
import zipfile
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPOSITORY / "scripts"))

import check_package_licenses as check  # noqa: E402

LOCK = REPOSITORY / "pylock.runtime-win-x64.toml"
OUT_OF_THE_PACKAGE = {
    "torch", "torchaudio", "transformers", "sentence-transformers", "tokenizers", "safetensors", "scipy", "scikit-learn", "setuptools",
    "certifi", "tqdm", "sherpa-onnx-core", "huggingface-hub", "hf-xet", "httpx", "httpcore",
}


def _depot(tmp_path: Path, name: str, data: bytes = b"nothing here") -> Path:
    target = tmp_path / "python" / "Lib" / "site-packages" / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return tmp_path


def test_the_lock_keeps_out_what_the_notices_say_left() -> None:
    assert check.locked(LOCK).isdisjoint(OUT_OF_THE_PACKAGE)


def test_every_import_of_the_mind_is_in_the_lock() -> None:
    # A lazy import outside the lock fails only where it runs. pyaudiowpatch and pywebrtc_audio are the echo canceller's: they left the
    # lock in 22b470dd0, and voice_echo says «echo cancellation off» without them.
    known_gap = {"pyaudiowpatch", "pywebrtc_audio"}
    imported: set[str] = set()
    for path in (REPOSITORY / "src" / "baxy_mind").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                imported |= {alias.name.split(".")[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                imported.add(node.module.split(".")[0])
    third_party = imported - set(sys.stdlib_module_names) - {"baxy_mind"}
    assert {check.normalized(name) for name in third_party - known_gap} <= check.locked(LOCK)
    assert known_gap <= third_party


def test_a_clean_package_has_no_findings(tmp_path: Path) -> None:
    assert check.findings(_depot(tmp_path, "good.pyd"), LOCK) == []


@pytest.mark.parametrize(
    ("name", "data", "what"),
    [
        ("_sherpa_onnx.cp312-win_amd64.pyd", b"..espeak_ng_Initialize..", "eSpeak NG"),
        ("_sherpa_onnx.cp312-win_amd64.pyd", b"..phonemize_eSpeak..", "piper-phonemize"),
        ("torch_cpu.dll", b"Intel(R) oneAPI Math Kernel Library Version", "Intel oneMKL"),
        ("x.dll", b"libquadmath", "libquadmath"),
        ("libportaudio64bit-asio.dll", b"", "ASIO"),
        ("libopenblas64__v0.3.23.dll", b"", "OpenBLAS"),
        ("libiomp5md.dll", b"", "Intel OpenMP"),
        ("sherpa-onnx-c-api.dll", b"", "eSpeak NG"),
        ("_message.pyd", b"GCC: (GNU) 10-win32", "GCC"),
        ("_message2.pyd", b"mingw-w64-crt", "mingw-w64"),
    ],
)
def test_each_piece_that_left_is_seen_in_the_bytes_or_by_its_name(tmp_path: Path, name: str, data: bytes, what: str) -> None:
    found = check.findings(_depot(tmp_path, name, data), LOCK)
    assert any(what in line for line in found), found


def test_speaker_is_not_espeak(tmp_path: Path) -> None:
    assert check.findings(_depot(tmp_path, "x.pyd", b"offlinespeakerdiarization wespeaker 3d-speaker"), LOCK) == []


def test_a_python_package_outside_the_lock_is_seen(tmp_path: Path) -> None:
    (tmp_path / "python" / "Lib" / "site-packages" / "torch-2.13.0.dist-info").mkdir(parents=True)
    assert any("torch-2.13.0.dist-info" in line for line in check.findings(tmp_path, LOCK))


def test_espeaks_data_is_seen_by_its_folder(tmp_path: Path) -> None:
    (tmp_path / "espeak-ng-data").mkdir()
    (tmp_path / "espeak-ng-data" / "phontab").write_bytes(b"x")
    assert any("eSpeak NG's data" in line for line in check.findings(tmp_path, LOCK))


def test_the_package_runs_the_check_and_drops_asio_and_protobuf() -> None:
    build = (REPOSITORY / "scripts" / "build_steam.ps1").read_text(encoding="utf-8")
    lines = [line.strip() for line in build.splitlines() if not line.strip().startswith("#")]
    assert any("check_package_licenses.py" in line for line in lines)
    assert any(line.startswith("Remove-Item") and "libportaudio64bit-asio.dll" in line for line in lines)
    assert any(line.startswith("Remove-Item") and "'google'" in line for line in lines)
    assert any("protobuf-*.dist-info" in line and "Remove-Item" in line for line in lines)


def test_protobuf_coming_back_is_seen_although_the_lock_names_it(tmp_path: Path) -> None:
    (tmp_path / "python" / "Lib" / "site-packages" / "protobuf-7.35.1.dist-info").mkdir(parents=True)
    assert "protobuf" in check.locked(LOCK)
    assert any("protobuf-7.35.1.dist-info" in line for line in check.findings(tmp_path, LOCK))


def test_numpys_notices_are_of_this_wheel() -> None:
    wheel = REPOSITORY / "runtime_wheels" / "numpy-1.26.4+baxy.1-cp312-cp312-win_amd64.whl"
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
    bundled = [name for name in names if "/bundled/" in name]
    assert not [name for name in bundled if "tools__wheels" in name or ".spin" in name or "doc__" in name]
    for notice in ("dragon4.c.NOTICE", "_pocketfft.c.NOTICE", "lapack_lite__LICENSE", "libdivide__LICENSE", "LICENSES_bundled"):
        assert any(notice in name for name in bundled), notice


@pytest.mark.parametrize("package", ["sherpa-onnx", "numpy", "silero-vad"])
def test_the_wheels_of_the_repository_are_the_locked_ones_and_clean(package: str) -> None:
    with LOCK.open("rb") as stream:
        entry = next(p for p in tomllib.load(stream)["packages"] if p["name"] == package)
    wheel = REPOSITORY / entry["wheels"][0]["path"]
    assert "+baxy." in entry["version"]
    with zipfile.ZipFile(wheel) as archive:
        for name in archive.namelist():
            assert not name.startswith(("numpy.libs/", "Scripts/")), name
            if name.endswith((".pyd", ".dll")):
                data = archive.read(name)
                assert not [marker for marker in check.MARKERS if marker in data], name


def test_no_wheel_with_espeak_stays_in_the_tree() -> None:
    wheels = {path.name for path in (REPOSITORY / "runtime_wheels").glob("sherpa_onnx-*.whl")}
    assert wheels == {"sherpa_onnx-1.13.4+baxy.3-cp312-cp312-win_amd64.whl"}


def test_silero_keeps_the_model_the_voice_reads_and_asks_for_no_torch() -> None:
    wheel = REPOSITORY / "runtime_wheels" / "silero_vad-6.2.1+baxy.1-py3-none-any.whl"
    with zipfile.ZipFile(wheel) as archive:
        assert "silero_vad/data/silero_vad.onnx" in archive.namelist()
        metadata = archive.read("silero_vad-6.2.1+baxy.1.dist-info/METADATA").decode()
    required = [line for line in metadata.splitlines() if line.startswith("Requires-Dist:") and "extra ==" not in line]
    assert required == ["Requires-Dist: packaging"]
