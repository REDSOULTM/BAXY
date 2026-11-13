"""Uso-125: where the projector runs is decided by the VRAM really free when the server starts, for any make."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from baxy_mind import llm_server

CUDA = "Available devices:\n  CUDA0: x (16379 MiB, 15235 MiB free)\n"
VULKAN = "Available devices:\n  Vulkan0: y (8176 MiB, 7420 MiB free)\n"
TIGHT = "Available devices:\n  CUDA0: z (4096 MiB, 3890 MiB free)\n"
# VRAM4: free memory that holds the automatic cells whole (llm_server.fit_card) and not the projector beside them.
NO_PROJECTOR = "Available devices:\n  CUDA0: w (6144 MiB, 4500 MiB free)\n"


def _start(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, devices: str | Exception,
           backend: str = "cuda") -> tuple[list[str], list[list[str]], llm_server.LlmServer]:
    projector = tmp_path / "mmproj.gguf"
    projector.write_bytes(b"GGUF")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setenv("BAXY_MIND_MMPROJ", str(projector))
    monkeypatch.delenv("BAXY_VISION_SLOT_DIR", raising=False)
    commands: list[list[str]] = []
    asked: list[list[str]] = []

    def run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        asked.append(command)
        if isinstance(devices, Exception):
            raise devices
        return subprocess.CompletedProcess(command, 0, devices, "")

    monkeypatch.setattr(llm_server.subprocess, "run", run)
    monkeypatch.setattr(llm_server.subprocess, "Popen", lambda command, **kw: commands.append(command) or object())
    monkeypatch.setattr(llm_server.LlmServer, "_wait_health", lambda self: None)
    server = llm_server.LlmServer("model.gguf", "llama-server.exe", backend=backend)
    server.start()
    return commands[0], asked, server


@pytest.mark.parametrize("devices", [CUDA, VULKAN])
def test_the_projector_goes_to_the_gpu_when_the_vram_free_holds_it_for_any_make(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, devices: str) -> None:
    monkeypatch.delenv("BAXY_VISION_OFFLOAD", raising=False)
    command, asked, _ = _start(tmp_path, monkeypatch, devices)
    assert "--mmproj-offload" in command and "--no-mmproj-offload" not in command
    assert asked == [["llama-server.exe", "--list-devices"]]  # the server's own count, not one make's tool


@pytest.mark.parametrize("devices", [TIGHT, "Available devices:\n", OSError("no such file"),
                                     subprocess.TimeoutExpired("llama-server.exe", 20)])
def test_the_projector_stays_on_the_cpu_when_the_vram_is_short_or_not_known(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, devices: str | Exception) -> None:
    monkeypatch.delenv("BAXY_VISION_OFFLOAD", raising=False)
    command, _, _ = _start(tmp_path, monkeypatch, devices)
    assert "--no-mmproj-offload" in command and "--mmproj-offload" not in command


def test_the_limit_is_the_model_with_the_projector_and_a_margin_not_a_make(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BAXY_VISION_OFFLOAD", raising=False)
    need = llm_server.VISION_GPU_NEEDS_MIB
    exactly = f"Available devices:\n  Vulkan0: x ({need + 200} MiB, {need} MiB free)\n"
    short = f"Available devices:\n  CUDA0: x ({need + 200} MiB, {need - 1} MiB free)\n"
    assert "--mmproj-offload" in _start(tmp_path, monkeypatch, exactly)[0]
    assert "--no-mmproj-offload" in _start(tmp_path, monkeypatch, short)[0]


def test_a_person_can_keep_the_projector_on_the_cpu_and_nothing_is_asked(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BAXY_VISION_OFFLOAD", "0")
    command, asked, _ = _start(tmp_path, monkeypatch, CUDA)
    # VRAM4: nothing for the projector; the one question left is the start's own, for its cells (test_mind_vram_libre).
    assert "--no-mmproj-offload" in command and asked == [["llama-server.exe", "--list-devices"]]


def test_a_server_without_a_gpu_backend_does_not_offload(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BAXY_VISION_OFFLOAD", raising=False)
    command, asked, _ = _start(tmp_path, monkeypatch, CUDA, backend="cpu")
    assert "--no-mmproj-offload" in command and asked == []


def test_where_the_projector_runs_is_not_in_the_prefix_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The slot's state does not depend on it: a day with less VRAM free does not throw away the kept prefix. (VRAM4:
    while the cells still fit whole; a card that no longer holds them starts with fewer, test_mind_vram_libre.)"""
    monkeypatch.delenv("BAXY_VISION_OFFLOAD", raising=False)
    _, _, on_gpu = _start(tmp_path, monkeypatch, CUDA)
    _, _, on_cpu = _start(tmp_path, monkeypatch, NO_PROJECTOR)
    assert on_gpu._settings == on_cpu._settings
    assert "--mmproj" in on_gpu._settings


def test_a_server_that_dies_with_the_projector_on_the_gpu_starts_again_with_it_on_the_cpu(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BAXY_VISION_OFFLOAD", raising=False)
    projector = tmp_path / "mmproj.gguf"
    projector.write_bytes(b"GGUF")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setenv("BAXY_MIND_MMPROJ", str(projector))
    monkeypatch.setattr(llm_server, "_free_vram_mib", lambda server: 15000)
    monkeypatch.setattr(llm_server.threading, "Thread", lambda **kw: type("T", (), {"start": lambda self: None})())
    commands: list[list[str]] = []

    class Exited:
        returncode = 1

        def poll(self) -> int:
            return 1

    monkeypatch.setattr(llm_server.subprocess, "Popen", lambda command, **kw: commands.append(command) or Exited())
    server = llm_server.LlmServer("model.gguf", "llama-server.exe")
    server.start()
    server._wait_health()
    assert "--mmproj-offload" in commands[0] and "--no-mmproj-offload" in commands[1] and len(commands) == 2
    # The second one failing is the start's failure, as it always was: no third.
    assert server._failure == "llama-server exited with 1"


def test_no_projector_no_question(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    command, asked, _ = _start(tmp_path, monkeypatch, CUDA)
    assert "--mmproj" in command
    monkeypatch.delenv("BAXY_MIND_MMPROJ")
    assert llm_server.projector_placement("llama-server.exe", "cuda") == []


def test_the_app_says_what_the_projector_needs_free_at_the_context_chosen(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Encargo del dueño 2026-11-08: with 131,072 cells chosen the server alone takes ~5.2 GB, so the fixed 5,316 MiB (the
    # default context's) would put the projector on a 6 GB card that cannot hold both. The App works it out from the
    # model's header (ModelMemory) and gives it here; without it, the default context's figure stands.
    monkeypatch.delenv("BAXY_VISION_OFFLOAD", raising=False)
    six = "Available devices:\n  CUDA0: x (6143 MiB, 5934 MiB free)\n"
    monkeypatch.setenv("BAXY_VISION_GPU_NEEDS_MIB", "6400")
    assert "--no-mmproj-offload" in _start(tmp_path, monkeypatch, six)[0]
    monkeypatch.delenv("BAXY_VISION_GPU_NEEDS_MIB")
    assert "--mmproj-offload" in _start(tmp_path, monkeypatch, six)[0]
