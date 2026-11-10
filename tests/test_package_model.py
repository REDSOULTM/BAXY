"""QWB2 (documentacion/PLAN_QWEN_BASE.md §3): the package carries Qwen3.5-4B as Unsloth publishes it, pinned in the build
script, and offers BAXY's tuned model as a download the person asks for: its registration names that offer, the App and the
PowerShell schema accept it, and the license check refuses a package that carries the tuned model itself."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPOSITORY / "scripts"))

import check_package_licenses as check  # noqa: E402

LOCK = REPOSITORY / "pylock.runtime-win-x64.toml"
BUILD = REPOSITORY / "scripts" / "build_steam.ps1"
# unsloth/Qwen3.5-4B-GGUF at e87f176479d0855a907a41277aca2f8ee7a09523 (X-Linked-ETag and X-Linked-Size, 2026-11-07).
STOCK_FILE = "Qwen3.5-4B-Q4_K_M.gguf"
STOCK_SHA256 = "00fe7986ff5f6b463e62455821146049db6f9313603938a70800d1fb69ef11a4"
# REDSOULTM/BAXY-Qwen3.5-4B-GGUF at da66d8bbb0b90ae15fc54cb4386370a4a471d54f: the c4c2_1-sA of 1.3.x's packages.
TUNED_FILE = "BAXY-Qwen3.5-4B-c4-Q4_K_M.gguf"
TUNED_SHA256 = "2c445631782a5c27b9948369e9432309528688b9b761fce56586d796ea2f57c7"
TUNED_BYTES = 2740937440
TUNED_URL = ("https://huggingface.co/REDSOULTM/BAXY-Qwen3.5-4B-GGUF/resolve/da66d8bbb0b90ae15fc54cb4386370a4a471d54f/"
             + TUNED_FILE)


def _code_lines(path: Path) -> list[str]:
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if not line.strip().startswith("#")]


def test_the_build_pins_the_stock_model_and_not_the_one_this_machine_registered() -> None:
    lines = _code_lines(BUILD)
    assert f"$ModelFile = '{STOCK_FILE}'" in lines
    assert f"$ModelSha256 = '{STOCK_SHA256}'" in lines
    assert any(line.startswith("[Parameter(Mandatory = $true)][string]$Gguf") for line in lines)
    # The model this machine registered (the tuned one on the build machines) is never what the package takes.
    assert not any("$registered.gguf" in line for line in lines)
    # And another file given as -Gguf stops the build before anything is copied.
    check = lines.index("if ((Get-BaxySha256 -Path $Gguf) -ne $ModelSha256) {")
    assert check < lines.index("New-Item -ItemType Directory -Path $Output | Out-Null")


def test_the_build_writes_the_tuned_offer_pinned_to_its_commit() -> None:
    lines = _code_lines(BUILD)
    assert f"$TunedFile = '{TUNED_FILE}'" in lines
    assert f"$TunedSha256 = '{TUNED_SHA256}'" in lines
    assert f"$TunedBytes = {TUNED_BYTES}" in lines
    assert f"$TunedUrl = '{TUNED_URL}'" in lines
    assert "$TunedLicense = 'Apache-2.0'" in lines
    for key in ("tuned_gguf", "tuned_gguf_sha256", "tuned_gguf_bytes", "tuned_gguf_url", "tuned_gguf_license"):
        assert any(line.startswith(f"{key} = ") for line in lines), key


def test_the_check_knows_the_tuned_model_by_its_bytes() -> None:
    assert check.NOT_SHIPPED_MODELS == {(TUNED_BYTES, TUNED_SHA256): check.NOT_SHIPPED_MODELS[(TUNED_BYTES, TUNED_SHA256)]}
    assert "tuned" in check.NOT_SHIPPED_MODELS[(TUNED_BYTES, TUNED_SHA256)]


def test_a_package_carrying_the_tuned_model_is_refused_under_any_name(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    model = b"the tuned model"
    monkeypatch.setattr(check, "NOT_SHIPPED_MODELS", {(len(model), hashlib.sha256(model).hexdigest()): "BAXY's tuned model"})
    (tmp_path / "models").mkdir()
    (tmp_path / "models" / STOCK_FILE).write_bytes(model)
    (tmp_path / "models" / "otro.gguf").write_bytes(b"the tuned modeL")
    found = check.findings(tmp_path, LOCK)
    assert found == [f"models/{STOCK_FILE}: BAXY's tuned model"], found


def _status(registration: Path) -> dict:
    done = subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
         "[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false); . .\\scripts\\mind_runtime_manifest.ps1; "
         f"$s = Get-BaxyMindRuntimeStatus -ManifestPath '{registration}'; "
         "[ordered]@{ valid = $s.Valid; code = $s.Code } | ConvertTo-Json -Compress"],
        cwd=REPOSITORY, capture_output=True, text=True, encoding="utf-8", check=True, timeout=120)
    return json.loads(done.stdout)


def _registration(tmp_path: Path, **extra: object) -> Path:
    files = {"python": tmp_path / "python.exe", "gguf": tmp_path / STOCK_FILE, "llama_server": tmp_path / "llama-server.exe"}
    tmp_path.mkdir()
    for path in files.values():
        path.write_bytes(path.name.encode())
    (tmp_path / "mind" / "baxy_mind").mkdir(parents=True)
    (tmp_path / "mind" / "baxy_mind" / "__main__.py").write_text("", encoding="utf-8")
    document: dict[str, object] = {"schema": "baxy-mind-runtime-v1", "python_path": str(tmp_path / "mind"), "ngl": 99}
    for key, path in files.items():
        document[key] = str(path)
        document[key + "_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    document.update(extra)
    registration = tmp_path / "mind-runtime-v1.json"
    registration.write_text(json.dumps(document), encoding="utf-8")
    return registration


def test_the_powershell_schema_takes_a_registration_with_the_tuned_offer(tmp_path: Path) -> None:
    offer = {"tuned_gguf": TUNED_FILE, "tuned_gguf_sha256": TUNED_SHA256, "tuned_gguf_bytes": TUNED_BYTES,
             "tuned_gguf_url": TUNED_URL, "tuned_gguf_license": "Apache-2.0"}
    assert _status(_registration(tmp_path / "con", **offer)) == {"valid": True, "code": "ready"}
    assert _status(_registration(tmp_path / "sin")) == {"valid": True, "code": "ready"}
    assert _status(_registration(tmp_path / "otra", tuned_gguf_mirror="x"))["code"] == "runtime_manifest_schema_obsolete"
