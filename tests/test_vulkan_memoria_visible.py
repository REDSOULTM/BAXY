"""VUL1: on Vulkan the mind's llama-server starts with GGML_VK_DISABLE_HOST_VISIBLE_VIDMEM in its environment, so ggml
keeps its buffers in video memory on a card without Resizable BAR (llm_server.server_environment). Doubles only: what
each start hands to subprocess.Popen."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

from baxy_mind import external_model, llm_server

VARIABLE = "GGML_VK_DISABLE_HOST_VISIBLE_VIDMEM"


def _launched(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, backend: str) -> dict[str, Any]:
    """What subprocess.Popen was given by the start of the mind's server on ``backend``."""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.delenv("BAXY_MIND_MMPROJ", raising=False)
    monkeypatch.delenv("BAXY_VISION_SLOT_DIR", raising=False)
    monkeypatch.delenv("BAXY_MIND_LLAMA_REMOTE", raising=False)
    given: list[dict[str, Any]] = []
    monkeypatch.setattr(llm_server.subprocess, "Popen", lambda command, **options: given.append(options) or object())
    monkeypatch.setattr(llm_server.LlmServer, "_wait_health", lambda self: None)
    llm_server.LlmServer("model.gguf", "llama-server.exe", backend=backend).start()
    assert len(given) == 1
    return given[0]


def test_on_vulkan_the_server_is_told_to_keep_its_buffers_out_of_host_visible_video_memory(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(VARIABLE, raising=False)
    monkeypatch.setenv("BAXY_VUL1_PROBE", "kept")
    environment = _launched(tmp_path, monkeypatch, "vulkan")["env"]
    assert environment[VARIABLE] == "1"
    # The rest of the mind's environment goes with it: the server's own settings and the PC's paths.
    assert environment["BAXY_VUL1_PROBE"] == "kept" and environment["LOCALAPPDATA"] == str(tmp_path)
    assert VARIABLE not in os.environ  # the mind's own environment is not written: only the server's copy


@pytest.mark.parametrize("backend", ["cuda", "cpu"])
def test_a_server_that_does_not_compute_on_vulkan_gets_the_minds_environment_as_it_is(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, backend: str) -> None:
    monkeypatch.delenv(VARIABLE, raising=False)
    # Since PRV1 (PRIV-04) every server gets a copy with its key; besides the key it is the mind's environment as it is.
    environment = _launched(tmp_path, monkeypatch, backend)["env"]
    assert VARIABLE not in environment
    assert {name: value for name, value in environment.items() if name != "LLAMA_API_KEY"} == dict(os.environ)


@pytest.mark.parametrize("theirs", ["0", "1", "si"])
def test_a_value_the_person_already_set_is_left_as_it_is(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, theirs: str) -> None:
    monkeypatch.setenv(VARIABLE, theirs)
    assert _launched(tmp_path, monkeypatch, "vulkan")["env"][VARIABLE] == theirs


def test_the_start_again_with_the_projector_on_the_cpu_keeps_the_same_environment(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(VARIABLE, raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    given: list[dict[str, Any]] = []
    monkeypatch.setattr(llm_server.subprocess, "Popen", lambda command, **options: given.append(options) or object())
    server = llm_server.LlmServer("model.gguf", "llama-server.exe", backend="vulkan")
    server._launch(["--mmproj-offload"])
    server._launch(["--no-mmproj-offload"])  # what _wait_health does when the first one exits
    assert [options["env"][VARIABLE] for options in given] == ["1", "1"]


@pytest.mark.parametrize(("backend", "expected"), [("vulkan", "1"), ("cuda", None), ("cpu", None)])
def test_the_engine_of_a_model_the_person_chose_starts_as_the_minds_own_server_does(
        monkeypatch: pytest.MonkeyPatch, backend: str, expected: str | None) -> None:
    monkeypatch.delenv(VARIABLE, raising=False)
    given: list[dict[str, Any]] = []

    class Exited:
        def poll(self) -> int:
            return 1

    monkeypatch.setattr(external_model.subprocess, "Popen", lambda command, **options: given.append(options) or Exited())
    monkeypatch.setattr(external_model, "_end_with_this_process", lambda process: None)
    monkeypatch.setattr(external_model.Engine, "arguments", lambda self, backend: [])
    monkeypatch.setattr(llm_server, "declared_backend", lambda *a, **k: backend)
    monkeypatch.setattr(llm_server, "declared_build", lambda *a, **k: "x")
    assert external_model.Engine("llama-server.exe", {}, "qwen3:8b", 8192).start() is None
    environment = given[0]["env"]
    assert environment.get(VARIABLE) == expected and "LLAMA_API_KEY" in environment
