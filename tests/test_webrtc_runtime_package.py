from __future__ import annotations

import base64
import csv
from email.parser import BytesParser
import hashlib
import io
import json
from pathlib import Path
import zipfile

import pytest

from scripts import build_webrtc_runtime as recipe


def test_aec_wheel_identity_provenance_licenses_and_record() -> None:
    wheel = recipe.ASSETS / f"pywebrtc_audio-{recipe.VERSION}-cp312-cp312-win_amd64.whl"
    info = f"pywebrtc_audio-{recipe.VERSION}.dist-info"
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
        metadata = BytesParser().parsebytes(archive.read(f"{info}/METADATA"))
        assert metadata["Version"] == recipe.VERSION
        assert metadata["Name"] == "pywebrtc-audio"
        assert metadata.get_all("Requires-Dist")[0] == "numpy>=1.24"
        assert b"Tag: cp312-cp312-win_amd64" in archive.read(f"{info}/WHEEL")
        license_text = archive.read(f"{info}/licenses/LICENSE")
        for owner in (b"Apache License", b"WebRTC", b"JsonCpp", b"rnnoise", b"PFFFT"):
            assert owner in license_text
        assert archive.read(f"{info}/licenses/NOTICE")
        assert archive.read(f"{info}/licenses/WEBRTC-PATENTS")
        assert archive.read(f"{info}/BAXY-NOTICE.txt")
        assert not any("DELVEWHEEL" in name or ".libs/" in name for name in names)
        assert b"delvewheel" not in archive.read("pywebrtc_audio/__init__.py")
        assert b"last_linear_frame" in archive.read("pywebrtc_audio/_webrtc_audio.pyi")
        notice = json.loads(archive.read("pywebrtc_audio/baxy_native_build.json"))
        assert notice["version"] == recipe.VERSION
        assert notice["sourceSha256"] == recipe.SOURCE[2]
        assert notice["patchSha256"] == recipe.digest((recipe.ASSETS / "webrtc-linear-output.patch").read_bytes())
        native = archive.read("pywebrtc_audio/_webrtc_audio.cp312-win_amd64.pyd")
        assert recipe.digest(native) == notice["extensionSha256"]
        record = list(csv.reader(io.StringIO(archive.read(f"{info}/RECORD").decode())))
        assert {row[0] for row in record} == names
        for name, checksum, size in record:
            if name == f"{info}/RECORD":
                assert checksum == size == ""
                continue
            data = archive.read(name)
            encoded = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=")
            assert checksum == "sha256=" + encoded.decode()
            assert int(size) == len(data)


def test_build_reuse_rejects_changed_or_added_source_without_overwriting(tmp_path: Path) -> None:
    root = tmp_path / "source"
    files = {"a/b.cpp": b"original"}
    recipe.materialize(root, files)
    recipe.materialize(root, files)
    (root / "a/b.cpp").write_bytes(b"existing edit")
    with pytest.raises(RuntimeError, match="file_differs"):
        recipe.materialize(root, files)
    assert (root / "a/b.cpp").read_bytes() == b"existing edit"
    (root / "new.cpp").write_bytes(b"new file")
    with pytest.raises(RuntimeError, match="tree_differs"):
        recipe.materialize(root, files)
    assert (root / "new.cpp").read_bytes() == b"new file"


@pytest.mark.parametrize("name", ["../escape", "/absolute", "C:/escape", "..\\escape"])
def test_build_rejects_unsafe_archive_names_before_writing(tmp_path: Path, name: str) -> None:
    root = tmp_path / "source"
    with pytest.raises(ValueError, match="path_invalid"):
        recipe.materialize(root, {name: b"x"})
    assert not root.exists()
