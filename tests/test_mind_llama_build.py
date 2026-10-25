"""w11-llama (2026-10-25): the mind starts only a declared llama-server (data/llama_server.v1.json), by SHA-256."""
import hashlib
import json
import re
from pathlib import Path

import pytest

from baxy_mind import llm_server
from baxy_mind.llm_server import declared_build

ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / "scripts" / "llama" / "cache_tools_prefix.patch"
# What the patch rebuilds (scripts/llama/README.md, «Compilar»): every other declared file is b11609's.
PATCHED_FILES = {"llama-server.exe", "llama-server-impl.dll", "llama-common.dll"}


def _declaration() -> dict:
    return json.loads(llm_server.BUILDS.read_text(encoding="utf-8"))


def test_every_build_declares_each_file_by_sha256() -> None:
    declaration = _declaration()
    assert declaration["schema"] == "baxy.llama-server.v1"
    assert "llama-server.exe" in declaration["files"]
    for build in declaration["builds"].values():
        assert set(build["sha256"]) == set(declaration["files"])
        assert all(re.fullmatch(r"[0-9a-f]{64}", digest) for digest in build["sha256"].values())


def test_the_patched_build_is_b11609_but_the_three_files_the_patch_rebuilds() -> None:
    builds = _declaration()["builds"]
    stock, patched = builds["b11609"]["sha256"], builds["b11609-baxy-cache"]["sha256"]
    assert {name for name in stock if stock[name] != patched[name]} == PATCHED_FILES


def test_the_patched_build_declares_the_patch_in_the_repository() -> None:
    # A change to the patch is a new build: declared again, with its own files and measurement.
    declared = _declaration()["builds"]["b11609-baxy-cache"]["patch_sha256"]
    assert hashlib.sha256(PATCH.read_bytes()).hexdigest() == declared


def _folder(tmp_path: Path, name: str, contents: dict[str, bytes]) -> Path:
    folder = tmp_path / name
    folder.mkdir()
    for file, data in contents.items():
        (folder / file).write_bytes(data)
    return folder / "llama-server.exe"


@pytest.fixture
def builds(tmp_path: Path) -> Path:
    """Two builds of two files that share the second."""
    def sha(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    declaration = {"schema": "baxy.llama-server.v1", "files": ["llama-server.exe", "llama.dll"], "builds": {
        "stock": {"sha256": {"llama-server.exe": sha(b"stock"), "llama.dll": sha(b"model")}},
        "patched": {"sha256": {"llama-server.exe": sha(b"patched"), "llama.dll": sha(b"model")}},
    }}
    path = tmp_path / "llama_server.v1.json"
    path.write_text(json.dumps(declaration), encoding="utf-8")
    return path


def test_a_declared_folder_is_its_build(tmp_path: Path, builds: Path) -> None:
    stock = _folder(tmp_path, "stock", {"llama-server.exe": b"stock", "llama.dll": b"model", "ggml-cuda.dll": b"x"})
    patched = _folder(tmp_path, "patched", {"llama-server.exe": b"patched", "llama.dll": b"model"})
    assert declared_build(str(stock), builds) == "stock"
    assert declared_build(str(patched), builds) == "patched"


def test_an_undeclared_file_is_named(tmp_path: Path, builds: Path) -> None:
    server = _folder(tmp_path, "other", {"llama-server.exe": b"stock", "llama.dll": b"another model"})
    with pytest.raises(RuntimeError, match=r"not declared in llama_server\.v1\.json: .*\(llama\.dll [0-9a-f]{12}\)"):
        declared_build(str(server), builds)


def test_a_missing_file_is_named(tmp_path: Path, builds: Path) -> None:
    server = _folder(tmp_path, "partial", {"llama-server.exe": b"patched"})
    with pytest.raises(RuntimeError, match=r"\(llama\.dll missing\)"):
        declared_build(str(server), builds)


def test_a_folder_of_two_builds_is_not_either(tmp_path: Path, builds: Path) -> None:
    declaration = json.loads(builds.read_text(encoding="utf-8"))
    declaration["builds"]["patched"]["sha256"]["llama.dll"] = hashlib.sha256(b"patched model").hexdigest()
    builds.write_text(json.dumps(declaration), encoding="utf-8")
    server = _folder(tmp_path, "mixed", {"llama-server.exe": b"stock", "llama.dll": b"patched model"})
    with pytest.raises(RuntimeError, match="different builds"):
        declared_build(str(server), builds)


def test_only_a_llama_server_exe_is_a_server(tmp_path: Path, builds: Path) -> None:
    other = tmp_path / "server.exe"
    other.write_bytes(b"stock")
    with pytest.raises(RuntimeError, match="not a llama-server.exe"):
        declared_build(str(other), builds)


def test_the_mind_does_not_start_an_undeclared_server(tmp_path: Path, monkeypatch, capsys) -> None:
    from baxy_mind import __main__ as sidecar

    started: list[str] = []

    class Server:
        def __init__(self, *args, **kwargs) -> None:
            started.append("server")

    server = _folder(tmp_path, "unknown", {"llama-server.exe": b"unknown"})
    monkeypatch.setenv("BAXY_MIND_LLM_GGUF", "model.gguf")
    monkeypatch.setenv("BAXY_MIND_LLAMA_SERVER", str(server))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(sidecar, "LlmServer", Server)
    assert sidecar.main() == 2
    assert started == []
    error = capsys.readouterr().err
    assert error.startswith("baxy_mind_renew_failure: llama-server not declared in llama_server.v1.json")
    assert "llama-server.exe " in error and "llama-common.dll missing" in error
