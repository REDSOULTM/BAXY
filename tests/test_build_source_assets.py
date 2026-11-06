"""The source assets of what the GPL covers: exactly the pinned bytes, BAXY's changes beside them, and said in the notices."""
from __future__ import annotations

import hashlib
import sys
import zipfile
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPOSITORY / "scripts"))

import build_source_assets as assets  # noqa: E402


class _Answer:
    def __init__(self, data: bytes) -> None:
        self.data = data

    def __enter__(self) -> "_Answer":
        return self

    def __exit__(self, *_: object) -> None:
        pass

    def read(self) -> bytes:
        return self.data


def _serve(monkeypatch: pytest.MonkeyPatch, data: bytes) -> list[str]:
    asked: list[str] = []

    def answer(request, timeout: int) -> _Answer:  # noqa: ANN001, ARG001
        asked.append(request.full_url)
        return _Answer(data)

    monkeypatch.setattr(assets.urllib.request, "urlopen", answer)
    return asked


def test_bytes_that_are_not_the_pinned_ones_are_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _serve(monkeypatch, b"another thing")

    with pytest.raises(SystemExit):
        assets.fetch("https://example.test/x", hashlib.sha256(b"the pinned thing").hexdigest(), tmp_path)

    assert list(tmp_path.iterdir()) == []


def test_the_cache_is_held_to_the_hash_too(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pinned = hashlib.sha256(b"the pinned thing").hexdigest()
    (tmp_path / pinned).write_bytes(b"tampered")
    asked = _serve(monkeypatch, b"the pinned thing")

    with pytest.raises(SystemExit):
        assets.fetch("https://example.test/x", pinned, tmp_path)

    assert asked == []


def test_the_sherpa_asset_carries_its_tree_and_baxys_changes_unapplied(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def tree(target: Path, _work: Path) -> None:
        with zipfile.ZipFile(target, "w") as archive:
            archive.writestr("sherpa-onnx-1.13.4/CMakeLists.txt", "upstream")

    monkeypatch.setattr(assets, "sherpa_tree", tree)
    target = tmp_path / "s.zip"

    assets.build_sherpa(target, tmp_path)

    with zipfile.ZipFile(target) as archive:
        assert archive.read("sherpa-onnx-1.13.4/CMakeLists.txt") == b"upstream"
        for name in "sherpa-nemo-stream-decoder.patch", "sherpa-nemo-normalization.patch":
            assert archive.read(f"runtime_wheels/{name}") == (REPOSITORY / "runtime_wheels" / name).read_bytes()
        script = archive.read("scripts/build_sherpa_runtime.py")
        assert script == (REPOSITORY / "scripts" / "build_sherpa_runtime.py").read_bytes()
        assert assets.sherpa.COMMIT.encode() in archive.read("README-BAXY.txt")


def test_a_patch_that_is_not_the_one_the_script_applies_stops_the_asset(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def tree(target: Path, _work: Path) -> None:
        with zipfile.ZipFile(target, "w") as archive:
            archive.writestr("sherpa-onnx-1.13.4/CMakeLists.txt", "upstream")

    monkeypatch.setattr(assets, "sherpa_tree", tree)
    monkeypatch.setattr(assets.sherpa, "PATCH_SHA256", "0" * 64)

    with pytest.raises(SystemExit):
        assets.build_sherpa(tmp_path / "s.zip", tmp_path)


def test_the_licenses_asset_has_the_notices_and_every_text(tmp_path: Path) -> None:
    target = tmp_path / "l.zip"

    assets.build_licenses(target)

    with zipfile.ZipFile(target) as archive:
        names = set(archive.namelist())
    assert {"BAXY-LICENSE.txt", "THIRD_PARTY_NOTICES.md", "LICENSE-llama.cpp.txt"} <= names
    assert {path.name for path in (REPOSITORY / "licenses").iterdir()} <= names


def test_the_notice_names_each_source_asset_and_its_pin() -> None:
    sources = (REPOSITORY / "licenses" / "FUENTES_GPL.md").read_text(encoding="utf-8")
    for name, _url, sha256 in (assets.ESPEAK, assets.PIPER):
        assert name in sources
        assert sha256 in sources
    assert assets.SHERPA_ASSET in sources
    assert assets.DEPENDENCIES_ASSET in sources
    for name, _url, sha256 in assets.DEPENDENCIES:
        assert name in sources
        assert sha256 in sources


def test_the_notice_carries_the_written_offer_in_both_languages() -> None:
    sources = (REPOSITORY / "licenses" / "FUENTES_GPL.md").read_text(encoding="utf-8")
    assert "Written offer" in sources
    assert "Oferta escrita" in sources
    assert "three years" in sources
    assert "tres años" in sources
    assert "durable physical medium customarily used for software interchange" in sources
    assert "BAXY 1.2.0 or 1.2.1" in sources
    assert "`sherpa_onnx` wheels" in sources
    assert "outside this offer" in sources
    assert "as a whole, are conveyed under GPL-3.0-or-later" in sources
    assert "https://github.com/REDSOULTM/BAXY/releases/tag/v1.2.1" in sources
    assert "https://github.com/REDSOULTM/BAXY/issues" in sources


def test_the_package_puts_the_directions_next_to_the_binaries_that_carry_espeak() -> None:
    # GPL-3.0 section 6(d): «maintain clear directions next to the object code saying where to find the Corresponding Source».
    build = (REPOSITORY / "scripts" / "build_steam.ps1").read_text(encoding="utf-8")
    assert "'sherpa_onnx\\lib', 'Scripts'" in build
    assert "'FUENTES_GPL.md', 'GPL-3.0.txt'" in build
