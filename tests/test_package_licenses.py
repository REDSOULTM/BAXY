"""What the notices of 1.3.0 say left the package stays out: in the lock, in the wheels of the repository and in the armed folder."""
from __future__ import annotations

import ast
import hashlib
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


def _with_texts(depot: Path) -> Path:
    (depot / "licenses").mkdir(parents=True)
    for text in (REPOSITORY / "licenses").iterdir():
        (depot / "licenses" / text.name).write_bytes(text.read_bytes())
    return depot


def test_a_package_with_every_text_of_the_repository_misses_none(tmp_path: Path) -> None:
    assert check.missing_texts(_with_texts(tmp_path)) == []


@pytest.mark.parametrize(
    "name", ["xxHash-LICENSE.txt", "Microsoft-VisualCpp-Redistributable.txt", "HACL-star-LICENSE.txt", "Windows-SDK-License.rtf"]
)
def test_a_text_the_package_lost_or_changed_is_seen(tmp_path: Path, name: str) -> None:
    depot = _with_texts(tmp_path)
    (depot / "licenses" / name).unlink()
    (depot / "licenses" / "Zlib.txt").write_bytes(b"another text")

    missing = check.missing_texts(depot)

    assert [line for line in missing if name in line]
    assert [line for line in missing if "Zlib.txt" in line]


def test_the_check_fails_on_a_package_without_its_texts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.setattr(sys, "argv", ["check_package_licenses.py", "--depot", str(tmp_path), "--lock", str(LOCK)])

    assert check.main() == 1
    assert "licenses/xxHash-LICENSE.txt" in capsys.readouterr().err


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


# DET1: the owner made baxy-wake-k6r-v7a the official detector on 2026-11-07 («sin la serie»): its folder's hash, and the head.onnx of
# the detectors that learned from the TV series through their teacher k5 (v7b, v3_b2).
V7A_FOLDER = "1b7cad869499037e901cb17d862cdfdd6074040ef50d1bf7fd89b0b1b54f083a"
V7B_FOLDER = "48a02e8fbedfb2f9fd57e90af6f06c8814e361791bc4d5b0e3a4baecd264b8ac"
V7A_HEAD = "f8bc7ad059c972415399702c36bb780eedbe6063ce0779c6806f31969cd31599"
RETIRED_HEADS = {
    "de79f68a0ce6fb4b48f62da0e07447d2d387f58ec68d73076be1e1db4f904276": "k6r-v7b",
    "7fb6bdeaea1b7fc1bf040221331987034b7e5be574b8f01333e8edd3395bf64e": "k6r-v3_b2",
}


def test_the_package_takes_the_wake_detector_without_the_series() -> None:
    build = (REPOSITORY / "scripts" / "build_steam.ps1").read_text(encoding="utf-8")
    assert f"$WakeSha256 = '{V7A_FOLDER}'" in build
    assert "baxy-wake-k6r-v7a" in build
    assert V7B_FOLDER not in build
    assert "k6r-v7b" not in build


def test_the_check_knows_the_retired_wake_detectors_and_not_v7a() -> None:
    known = {sha256: what for (_, sha256), what in check.RETIRED_WAKE.items()}
    assert set(known) == set(RETIRED_HEADS)
    for sha256, name in RETIRED_HEADS.items():
        assert name in known[sha256]
    assert V7A_HEAD not in known


def test_a_retired_wake_detector_is_seen_by_its_bytes_under_any_name(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    head = b"a retired head"
    monkeypatch.setattr(check, "RETIRED_WAKE", {(len(head), hashlib.sha256(head).hexdigest()): "the wake detector k6r-v7b"})
    (tmp_path / "wake").mkdir()
    (tmp_path / "wake" / "otro.bin").write_bytes(head)
    (tmp_path / "wake" / "head.onnx").write_bytes(b"a retired heaD")
    found = check.findings(tmp_path, LOCK)
    assert found == ["wake/otro.bin: the wake detector k6r-v7b"], found
