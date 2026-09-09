from __future__ import annotations

import base64
import csv
from email.parser import BytesParser
import hashlib
import io
import json
from pathlib import Path
import zipfile

from scripts.verify_python_runtime_lock import load_constraints


ROOT = Path(__file__).resolve().parents[1]


def test_bundled_sherpa_wheel_has_consistent_identity_and_complete_hashes() -> None:
    version = load_constraints(ROOT / "constraints-runtime-win-x64.txt")["sherpa-onnx"]
    wheel = ROOT / "runtime_wheels" / f"sherpa_onnx-{version}-cp312-cp312-win_amd64.whl"
    info = f"sherpa_onnx-{version}.dist-info"
    with zipfile.ZipFile(wheel) as archive:
        metadata = BytesParser().parsebytes(archive.read(f"{info}/METADATA"))
        assert metadata["Version"] == version
        assert metadata["Name"].replace("_", "-") == "sherpa-onnx"
        assert "sherpa-onnx-core==1.13.4" in metadata.get_all("Requires-Dist")
        assert b"Tag: cp312-cp312-win_amd64" in archive.read(f"{info}/WHEEL")
        assert f"__version__ = '{version}'".encode() in archive.read("sherpa_onnx/__init__.py")
        assert any(name.endswith("/LICENSE") for name in archive.namelist())
        record = list(csv.reader(io.StringIO(archive.read(f"{info}/RECORD").decode())))
        assert {row[0] for row in record} == set(archive.namelist())
        for name, checksum, size in record:
            if name == f"{info}/RECORD":
                assert checksum == size == ""
                continue
            data = archive.read(name)
            encoded = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=")
            assert checksum == "sha256=" + encoded.decode()
            assert int(size) == len(data)
        notice = json.loads(archive.read("sherpa_onnx/baxy_native_build.json"))
        native = archive.read("sherpa_onnx/lib/_sherpa_onnx.cp312-win_amd64.pyd")
        assert hashlib.sha256(native).hexdigest() == notice["extensionSha256"]
        patch = (ROOT / "runtime_wheels/sherpa-nemo-stream-decoder.patch").read_bytes()
        assert hashlib.sha256(patch).hexdigest() == notice["patchSha256"]
        normalization = (ROOT / "runtime_wheels/sherpa-nemo-normalization.patch").read_bytes()
        assert hashlib.sha256(normalization).hexdigest() == notice["normalizationPatchSha256"]
        assert notice["normalizationUpstreamCommit"] == "0967a08db705d8eec9cf5cef962c8ec57c16e4a8"
