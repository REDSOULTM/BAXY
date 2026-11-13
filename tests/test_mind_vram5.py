"""VRAM5 (AUD1, 13-11-2026): the 4 GB rule past NVIDIA: the device measured, Vulkan's fit, a context given by hand,
integrated GPUs and a card that ran out of memory.

AUD1 found: F6 the mind read the first device of --list-devices, which on Vulkan may be an integrated GPU (on the PC the
integrated GPU comes before the NVIDIA card); F1 on Vulkan no fit at all (61,440 cells, «-np 3 -kvu»); F4 a context the person
gave skipped the fit and spilled in silence; F5 an integrated GPU started with no check, its memory being the PC's RAM;
F9 nothing said a card that ran out of memory.
"""
import pathlib

import pytest

from baxy_mind import llm_server
from test_mind_vram4b import COMPLETO, ESENCIAL, FACTORY

# The form the Vulkan llama-server of the package gives with «-v --list-devices» (b11609), its log and its list; figures invented.
PC_VULKAN = """0.00.198.875 D ggml_vulkan: Found 2 Vulkan devices:
0.00.202.489 D ggml_vulkan: 0 = Intel(R) UHD Graphics 730 (Intel Corporation) | uma: 1 | fp16: 1 | bf16: 0 | fp4: 0 | warp size: 32 | shared memory: 32768 | int dot: 1 | matrix cores: none
0.00.205.989 D ggml_vulkan: 1 = NVIDIA GeForce RTX 4070 (NVIDIA) | uma: 0 | fp16: 1 | bf16: 1 | fp4: 0 | warp size: 32 | shared memory: 49152 | int dot: 1 | matrix cores: NV_coopmat2v
Available devices:
  Vulkan0: Intel(R) UHD Graphics 730 (8131 MiB, 7702 MiB free)
  Vulkan1: NVIDIA GeForce RTX 4070 (12282 MiB, 11406 MiB free)
"""
# The same PC's iGPU before a 4 GB card (what AUD1 F6 feared): the integrated one lists more memory than the card.
IGPU_AND_4GB = PC_VULKAN.replace("NVIDIA GeForce RTX 4070 (12282 MiB, 11406 MiB free)",
                                    "AMD Radeon RX 6500 XT (4080 MiB, 3400 MiB free)")
ONE_CUDA = "Available devices:\n  CUDA0: NVIDIA GeForce RTX 4070 (12282 MiB, 11010 MiB free)\n"


def _launched(monkeypatch, tmp_path: pathlib.Path, listed: str | None = None, **kwargs):
    launched: list[list[str]] = []

    class Process:
        pid = 4242

        def __init__(self, command, **_kwargs) -> None:
            launched.append(command)

        def poll(self) -> None:
            return None

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(llm_server.subprocess, "Popen", Process)
    monkeypatch.setattr(llm_server.threading, "Thread", lambda **_k: type("T", (), {"start": lambda self: None})())
    monkeypatch.setattr(llm_server, "_free_port", lambda: 9165)
    if listed is not None:
        # The card answers through the server's own listing: the start's measure is the real one, not a test variable.
        monkeypatch.setattr(llm_server, "_listed_devices", lambda server: listed)
        monkeypatch.setattr(llm_server.LlmServer, "_card_free", lambda self: llm_server._free_vram_mib(self.server))
        monkeypatch.setattr(llm_server.LlmServer, "_card_total", lambda self: llm_server._LISTED_TOTAL.get(self.server))
    server = llm_server.LlmServer("model.gguf", f"llama-server-{tmp_path.name}.exe", **kwargs)
    server.start()
    return server, launched[0] if launched else None


def _measured(monkeypatch, free: int | None, total: int | None = None, integrated: str = "") -> None:
    monkeypatch.setattr(llm_server.LlmServer, "_card_free", lambda self: free, raising=False)
    monkeypatch.setattr(llm_server.LlmServer, "_card_total", lambda self: total, raising=False)
    monkeypatch.setenv("BAXY_TEST_VRAM_INTEGRATED", integrated)


def _given(command: list[str], flag: str) -> str | None:
    return command[command.index(flag) + 1] if flag in command else None


# F6: the device measured is the device used.

def test_the_integrated_gpu_listed_first_is_not_the_one_measured() -> None:
    devices = llm_server.listed_devices(PC_VULKAN)
    assert [(d.name, d.integrated) for d in devices] == [("Vulkan0", True), ("Vulkan1", False)]
    chosen = llm_server.chosen_device(devices)
    assert chosen is not None and (chosen.name, chosen.free, chosen.total) == ("Vulkan1", 11406, 12282)


def test_a_4gb_card_behind_an_integrated_gpu_is_measured_as_4gb(tmp_path, monkeypatch) -> None:
    # Before: the first line, the iGPU's 15,497 MiB free of RAM, and every profile «fit».
    monkeypatch.setenv("BAXY_RENEW_CTX_NEEDS", FACTORY)
    server, command = _launched(monkeypatch, tmp_path, IGPU_AND_4GB, backend="vulkan")
    assert command is not None and _given(command, "-dev") == "Vulkan1"
    assert server.card_fit is not None and server.card_fit["freeMb"] == 3400 and server.card_fit["needs"] == ESENCIAL
    assert server.card_memory == {"totalMb": 4080, "short": True}


def test_of_two_dedicated_cards_the_larger_one() -> None:
    listed = ("Available devices:\n  CUDA0: NVIDIA GeForce GTX 1050 Ti (4096 MiB, 3300 MiB free)\n"
              "  CUDA1: NVIDIA GeForce RTX 3060 (12288 MiB, 11000 MiB free)\n")
    chosen = llm_server.chosen_device(llm_server.listed_devices(listed))
    assert chosen is not None and chosen.name == "CUDA1" and chosen.free == 11000


def test_one_device_keeps_the_command_as_it_was(tmp_path, monkeypatch) -> None:
    server, command = _launched(monkeypatch, tmp_path, ONE_CUDA)
    assert command is not None and "-dev" not in command and server.card_short is None


def test_without_the_engine_saying_which_is_integrated_the_least_free_and_no_dev(tmp_path, monkeypatch) -> None:
    # The blind review: without ggml-vulkan's «uma» lines a half-of-the-RAM iGPU could pass for the largest card.
    listed = PC_VULKAN.split("Available devices:")[1]
    chosen = llm_server.chosen_device(llm_server.listed_devices("Available devices:" + listed))
    assert chosen is not None and chosen.name == "Vulkan0"
    _, command = _launched(monkeypatch, tmp_path, "Available devices:" + listed, backend="vulkan")
    assert command is not None and "-dev" not in command


def test_only_integrated_gpus_are_used_as_llama_cpp_does() -> None:
    listed = ("ggml_vulkan: 0 = Intel(R) Iris(R) Xe Graphics (Intel Corporation) | uma: 1 | fp16: 1\n"
              "Available devices:\n  Vulkan0: Intel(R) Iris(R) Xe Graphics (8000 MiB, 7600 MiB free)\n")
    chosen = llm_server.chosen_device(llm_server.listed_devices(listed))
    assert chosen is not None and chosen.integrated


# F1: Vulkan fits its cells to the card too, with one slot.

def test_vulkan_has_its_own_line() -> None:
    # AMD3 §3 (RX 7600): 5,022 MiB at 61,440, 4,878 at 53,248, −277 with one slot, −862 with the projector on the CPU.
    assert llm_server.card_mib(61440, "vulkan") == 3883
    assert llm_server.card_mib(32768, "vulkan") == 3379
    assert llm_server.card_mib(77824) == 4032, "CUDA's line is as it was"


def test_an_8gb_amd_card_starts_as_before_but_with_one_slot(tmp_path, monkeypatch) -> None:
    _measured(monkeypatch, 7500, 8176)
    monkeypatch.setenv("BAXY_RENEW_CTX_NEEDS", FACTORY)
    server, command = _launched(monkeypatch, tmp_path, backend="vulkan")
    assert command is not None and _given(command, "-c") == "61440" and server.card_fit is None
    assert _given(command, "-np") == "1" and "-kvu" not in command
    assert server.card_memory == {"totalMb": 8176, "short": False}


@pytest.mark.parametrize(("free", "cells", "whole"), [(3600, "32768", True), (3400, "32768", False)])
def test_a_4gb_amd_card_starts_in_esencial(tmp_path, monkeypatch, free: int, cells: str, whole: bool) -> None:
    # Before: 61,440 cells and three slots, ~4.2 GB of the card asked in silence (AUD1 F1).
    _measured(monkeypatch, free, 4080)
    monkeypatch.setenv("BAXY_RENEW_CTX_NEEDS", FACTORY)
    server, command = _launched(monkeypatch, tmp_path, backend="vulkan")
    assert command is not None and _given(command, "-c") == cells
    assert server.card_fit is not None and server.card_fit["needs"] == ESENCIAL
    assert (server.card_short is None) is whole


def test_a_4gb_amd_card_with_less_free_launches_nothing(tmp_path, monkeypatch) -> None:
    _measured(monkeypatch, 3300, 4080)
    monkeypatch.setenv("BAXY_RENEW_CTX_NEEDS", FACTORY)
    server, command = _launched(monkeypatch, tmp_path, backend="vulkan")
    assert command is None and server.card_refused
    assert server.startup_failure()["cause"] == "vram_insuficiente"


# F4: a context given by hand is never changed, and never spills in silence.

def test_a_context_given_that_does_not_fit_is_said_and_not_launched(tmp_path, monkeypatch) -> None:
    _measured(monkeypatch, 3400, 4096)
    # VRAM5B: the App's needs (the factory's profiles) are what «Automático» may go down to (fitsContext)
    monkeypatch.setenv("BAXY_RENEW_CTX_NEEDS", FACTORY)
    server, command = _launched(monkeypatch, tmp_path, context=77824)
    assert command is None and server.context == 77824 and server.card_refused
    failure = server.startup_failure()
    assert failure["cause"] == "vram_insuficiente"
    assert failure["cardShort"] == {"freeMb": 3400, "needMb": 4232, "context": 77824, "given": True,
                                    "fitsContext": 32768}


def test_a_context_given_that_fits_only_without_the_margin_starts_and_says_it(tmp_path, monkeypatch) -> None:
    _measured(monkeypatch, 3700, 4096)
    server, command = _launched(monkeypatch, tmp_path, context=61440)
    assert command is not None and _given(command, "-c") == "61440" and not server.card_refused
    assert server.card_short is not None and server.card_short["given"] is True


def test_a_context_given_on_a_card_with_room_says_nothing(tmp_path, monkeypatch) -> None:
    _measured(monkeypatch, 9000, 16380)
    server, command = _launched(monkeypatch, tmp_path, context=131072)
    assert command is not None and _given(command, "-c") == "131072" and server.card_short is None


# F5: an integrated GPU holds the PC's RAM: what is left past Windows and the rest of BAXY.

@pytest.mark.parametrize(("installed", "launched", "cells"), [(8192, False, None), (12288, True, "61440"),
                                                             (16384, True, "61440")])
def test_an_integrated_gpu_takes_what_the_ram_leaves(tmp_path, monkeypatch, installed: int, launched: bool,
                                                     cells: str | None) -> None:
    _measured(monkeypatch, 15000, 16000, integrated="1")
    monkeypatch.setattr(llm_server, "installed_memory_mb", lambda: installed, raising=False)
    monkeypatch.setenv("BAXY_RENEW_CTX_NEEDS", FACTORY)
    server, command = _launched(monkeypatch, tmp_path, backend="vulkan")
    assert (command is not None) is launched
    if command is not None:
        assert _given(command, "-c") == cells
    else:
        failure = server.startup_failure()
        assert failure["cause"] == "vram_insuficiente" and failure["cardShort"]["integrated"] is True
        assert failure["cardShort"]["freeMb"] == 8192 - 4096 - 3748


def test_the_room_of_an_integrated_gpu() -> None:
    assert llm_server.integrated_room(None) is None
    assert llm_server.WINDOWS_RAM_MIB == 4096 and llm_server.BAXY_RAM_MIB == 3748


# F9: a read too slow on a card left without memory says so.

def test_a_slow_read_on_a_full_card_says_the_card_ran_out(tmp_path, monkeypatch) -> None:
    _measured(monkeypatch, 3400, 4096)
    monkeypatch.setenv("BAXY_RENEW_CTX_NEEDS", FACTORY)
    server, command = _launched(monkeypatch, tmp_path)
    assert command is not None
    monkeypatch.setattr(llm_server.LlmServer, "_card_free", lambda self: 40)
    monkeypatch.setattr(llm_server, "gpu_shared_mb", lambda pid: 1298 if pid == 4242 else None, raising=False)
    failure = server.startup_failure(llm_server.ReadTooSlow(47, 1900.0))
    assert failure["cause"] == "lectura_lenta" and failure["cardFull"] == {"freeMb": 40, "sharedMb": 1298}


def test_a_slow_read_with_the_card_not_full_says_nothing_of_it(tmp_path, monkeypatch) -> None:
    _measured(monkeypatch, 9000, 16380)
    server, command = _launched(monkeypatch, tmp_path)
    monkeypatch.setattr(llm_server, "gpu_shared_mb", lambda pid: 706, raising=False)
    failure = server.startup_failure(llm_server.ReadTooSlow(47, 1900.0))
    assert failure["cause"] == "lectura_lenta" and "cardFull" not in failure


# NVIDIA with memory to spare: the same command as before.

def test_nvidia_with_room_has_the_same_command(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BAXY_RENEW_CTX_NEEDS", FACTORY)
    _, command = _launched(monkeypatch, tmp_path, ONE_CUDA)
    assert command is not None
    assert command[command.index("-ngl"):] == [
        "-ngl", "99", "-c", "77824", "-np", "1", "-fa", "on", "-ctk", "q8_0", "-ctv", "q8_0", "--jinja",
        "--reasoning", "off", "--reasoning-budget", "0", "--load-mode", "none", "-cram", "0", "-ctxcp", "10",
        "-ot", r"token_embd\.weight=CPU", "--slot-save-path", str(tmp_path / "BAXY" / "renew" / "slots")]
    assert COMPLETO < 77824
