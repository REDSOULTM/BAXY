"""VELX1 (15-11-2026; the owner: «Debes hacer que nos acerquemos al máximo en velocidad al modelo sin baxy»): the output
matrix in RAM only where the card does not hold it.

uso-51 kept it in RAM (-ot token_embd.weight=CPU) on every CUDA card, for 24k more cells inside 4 GB; on the GTX 1650 of
4 GB it costs 33.1 → 19.8 tokens/s with the engine alone (INFORME_C1650Y.md §3), and a card of 6 GB or more paid the
same with room to spare. The cells are chosen as before, with its line; they and the output matrix go on the card when
both fit there whole with the margin (LlmServer._output_to_card)."""
import dataclasses
from pathlib import Path

import pytest

from baxy_mind import llm_server

ESENCIAL = 26489 + 3584  # ToolProfile.MeasuredPrefix and a turn (LocalContext.TurnRoomTokens)
COMPLETO = 51450 + 3584
OUTPUT = llm_server.OUTPUT_ON_CPU


def _started(monkeypatch, tmp_path: Path, free: int | None, **kwargs) -> tuple[llm_server.LlmServer, list[str]]:
    launched: list[list[str]] = []

    class Process:
        def __init__(self, command, **_kwargs) -> None:
            launched.append(command)

        def poll(self) -> None:
            return None

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(llm_server.subprocess, "Popen", Process)
    monkeypatch.setattr(llm_server.threading, "Thread", lambda **_k: type("T", (), {"start": lambda self: None})())
    monkeypatch.setattr(llm_server, "_free_port", lambda: 9165)
    monkeypatch.setattr(llm_server.LlmServer, "_card_free", lambda self: free, raising=False)
    monkeypatch.setattr(llm_server.LlmServer, "_card_integrated", lambda self: False, raising=False)
    server = llm_server.LlmServer("model.gguf", "llama-server.exe", **kwargs)
    server.start()
    return server, (launched[0] if launched else [])


def _in_ram(command: list[str]) -> bool:
    return "-ot" in command and command[command.index("-ot") + 1] == OUTPUT


def _cells(command: list[str]) -> int:
    return int(command[command.index("-c") + 1])


def test_the_4_gb_card_keeps_its_command_byte_for_byte(tmp_path: Path, monkeypatch) -> None:
    # The GTX 1650: CUDA says 3,292 MiB free with the card empty, and Esencial takes 3,064 + 200 at 32,768 cells; with the
    # output matrix too, 3,562 + 200: it stays in RAM, the command as in 1.5.5.
    monkeypatch.setenv("BAXY_RENEW_CTX_NEEDS", f"{COMPLETO},{ESENCIAL}")
    server, command = _started(monkeypatch, tmp_path, 3292)
    assert _cells(command) == 32768 and _in_ram(command) and not server.output_on_card
    assert server._keyed_settings == server._settings


@pytest.mark.parametrize("free", [4800, 6000, 15000])
def test_a_card_that_holds_the_cells_and_the_output_matrix_keeps_both(tmp_path: Path, monkeypatch, free: int) -> None:
    # A card of 6 GB with a desktop (~4.8-5.4 GB free), one of 8 or 16: the same 77,824 cells, the output on the card.
    monkeypatch.setenv("BAXY_RENEW_CTX_NEEDS", str(COMPLETO))
    server, command = _started(monkeypatch, tmp_path, free)
    assert _cells(command) == 77824 and not _in_ram(command) and server.output_on_card
    assert llm_server.card_mib(77824) + llm_server.output_mib() + llm_server.CARD_MARGIN_MIB <= free


def test_cells_that_fit_only_with_the_output_in_ram_keep_it_there(tmp_path: Path, monkeypatch) -> None:
    # 4,400 free: 77,824 cells take 4,032 + 200 with the output in RAM, 4,530 + 200 with it: the cells win, as before.
    monkeypatch.setenv("BAXY_RENEW_CTX_NEEDS", str(COMPLETO))
    server, command = _started(monkeypatch, tmp_path, 4400)
    assert _cells(command) == 77824 and _in_ram(command) and not server.output_on_card


def test_the_cells_never_change_for_the_output_matrix(tmp_path: Path, monkeypatch) -> None:
    # Whatever the card has free, the cells are the ones 1.5.5 chose: what the model reads and how much history fits do not
    # move; only where the output matrix is.
    monkeypatch.setenv("BAXY_RENEW_CTX_NEEDS", f"{COMPLETO},{ESENCIAL}")
    for free in range(3000, 6200, 100):
        monkeypatch.setenv("BAXY_RENEW_OUTPUT_CPU", "1")
        held, kept = _started(monkeypatch, tmp_path, free)
        monkeypatch.delenv("BAXY_RENEW_OUTPUT_CPU")
        server, command = _started(monkeypatch, tmp_path, free)
        if not kept:  # not even the fewest cells fit: no server either way (VRAM4B)
            assert not command and not server.output_on_card, free
            continue
        assert _cells(command) == _cells(kept), free
        assert server._keyed_settings == held._settings, free  # the prefix's key: the same as with the output in RAM
        assert command == kept if not server.output_on_card else [a for a in kept if a not in ("-ot", OUTPUT)] == command


@pytest.mark.parametrize("free", [None, 0])
def test_an_unread_card_keeps_the_output_in_ram(tmp_path: Path, monkeypatch, free: int | None) -> None:
    server, command = _started(monkeypatch, tmp_path, free)
    assert _in_ram(command) and not server.output_on_card


def test_the_output_kept_in_ram_by_hand_stays_there(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BAXY_RENEW_OUTPUT_CPU", "1")
    server, command = _started(monkeypatch, tmp_path, 15000)
    assert _in_ram(command) and not server.output_on_card


def test_an_integrated_gpu_keeps_the_output_in_ram(tmp_path: Path, monkeypatch) -> None:
    # Its memory is the PC's RAM: on it the output matrix would be a second copy beside the input's.
    monkeypatch.setattr(llm_server, "installed_memory_mb", lambda: 65536)
    launched: list[list[str]] = []
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(llm_server.subprocess, "Popen", lambda command, **_k: launched.append(command))
    monkeypatch.setattr(llm_server.threading, "Thread", lambda **_k: type("T", (), {"start": lambda self: None})())
    monkeypatch.setattr(llm_server.LlmServer, "_card_free", lambda self: 15000, raising=False)
    monkeypatch.setattr(llm_server.LlmServer, "_card_integrated", lambda self: True, raising=False)
    llm_server.LlmServer("model.gguf", "llama-server.exe").start()
    assert _in_ram(launched[0])


def test_the_projector_keeps_its_place_and_the_output_matrix_takes_what_is_left(tmp_path: Path, monkeypatch) -> None:
    # The projector reads an image in 0.5-1 s on the card against 8-16 s on the CPU (uso-125): it is placed as in 1.5.5,
    # and the output matrix goes on the card only with room left beside it and the server.
    projector = tmp_path / "mmproj.gguf"
    projector.write_bytes(b"GGUF")
    monkeypatch.setenv("BAXY_MIND_MMPROJ", str(projector))
    monkeypatch.setenv("BAXY_VISION_GPU_NEEDS_MIB", "5000")
    monkeypatch.setenv("BAXY_RENEW_CTX_NEEDS", str(COMPLETO))
    server, command = _started(monkeypatch, tmp_path, 5300)
    assert "--mmproj-offload" in command and _in_ram(command) and not server.output_on_card
    server, command = _started(monkeypatch, tmp_path, 5000 + llm_server.output_mib())
    assert "--mmproj-offload" in command and not _in_ram(command) and server.output_on_card
    server, command = _started(monkeypatch, tmp_path, 4900)  # the projector on the CPU: the output matrix fits
    assert "--no-mmproj-offload" in command and not _in_ram(command) and server.output_on_card


def test_vulkan_and_the_processor_are_as_they_were(tmp_path: Path, monkeypatch) -> None:
    for backend in ("vulkan", "cpu"):
        server, command = _started(monkeypatch, tmp_path, 15000, backend=backend)
        assert "-ot" not in command and not server.output_on_card


def test_the_output_matrix_is_the_tied_embedding_of_the_measured_model() -> None:
    # 521,472,000 bytes of Q6_K by the header: 498 MiB rounded up; 496 measured (INFORME_51.md, C1650Y §3).
    assert llm_server.output_mib() == 498
    untied = dataclasses.replace(llm_server.MEASURED_SHAPE, tied=False)
    assert llm_server.output_mib(untied) == 0


@pytest.mark.parametrize("with_projector", [False, True])
def test_a_server_that_dies_with_the_output_on_the_card_starts_again_as_before(
        tmp_path: Path, monkeypatch, with_projector: bool) -> None:
    # As with the projector (uso-125): the memory counted free went to something else. The second start is 1.5.5's,
    # the output matrix in RAM and the projector on the CPU at once; the second failing is the start's failure.
    if with_projector:
        projector = tmp_path / "mmproj.gguf"
        projector.write_bytes(b"GGUF")
        monkeypatch.setenv("BAXY_MIND_MMPROJ", str(projector))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(llm_server.LlmServer, "_card_free", lambda self: 15000, raising=False)
    monkeypatch.setattr(llm_server.LlmServer, "_card_integrated", lambda self: False, raising=False)
    monkeypatch.setattr(llm_server.threading, "Thread", lambda **_k: type("T", (), {"start": lambda self: None})())
    commands: list[list[str]] = []

    class Exited:
        returncode = 1

        def poll(self) -> int:
            return 1

    monkeypatch.setattr(llm_server.subprocess, "Popen", lambda command, **_k: commands.append(command) or Exited())
    server = llm_server.LlmServer("model.gguf", "llama-server.exe")
    server.start()
    server._wait_health()
    assert len(commands) == 2 and not _in_ram(commands[0]) and _in_ram(commands[1])
    assert ("--mmproj-offload" in commands[0] and "--no-mmproj-offload" in commands[1]) == with_projector
    assert server._failure == "llama-server exited with 1" and not server.output_on_card
