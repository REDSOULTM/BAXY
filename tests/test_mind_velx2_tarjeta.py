"""VELX2 (16-11-2026; the owner: «cualquier usuario pueda conectarle cualquier modelo que su PC pueda soportar… y que ese
modelo dé el 100 %»): what a card of 4 GB really holds.

The free memory BAXY fitted to was the listing's (llama-server --list-devices), and on Windows that is the budget the OS
gives the asking process less its own use, blind to every other process: on the GTX 1650 of 4 GB, 3,292 MiB where 3,900
are there (C1650Y), so models that fit were refused and the factory's output matrix stayed in RAM (18.9 tokens/s
against 30.4). Now the card's memory no process holds (memory.card_room_mb) bounds that figure, places the output matrix
and fits a model of its own; and a server once up that holds less on the card than its estimate is told short, or, with
the output matrix on it, started again with it in RAM."""
import dataclasses
from pathlib import Path

import pytest

from baxy_mind import llm_server, memory

ESENCIAL = 26489 + 3584  # ToolProfile.MeasuredPrefix and a turn (LocalContext.TurnRoomTokens)
COMPLETO = 51450 + 3584
OUTPUT = llm_server.OUTPUT_ON_CPU
GTX_1650_LISTED = 3292  # what --list-devices says on the GTX 1650 with the card empty (C1650Y)
GTX_1650_ROOM = 3900  # what nvidia-smi says free there (3,900-3,923)
MIB = 1024 * 1024
# Llama-3.2-3B-Instruct Q4_K_M and Granite-4.2-3B Q4_K_M as the mind's estimate gave them at 32,768 cells on that card
# (C1650Y §20: 3,875 and 3,646 MiB; alone they took 3,777 and 3,589): their difference to the factory's line.
LLAMA_DELTA = 3875 - 3064
GRANITE_DELTA = 3646 - 3064


def _started(monkeypatch, tmp_path: Path, free: int | None, room: int | None, delta: float = 0.0,
             **kwargs) -> tuple[llm_server.LlmServer, list[str]]:
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
    monkeypatch.setattr(llm_server.LlmServer, "_card_free", lambda self: free, raising=False)
    monkeypatch.setattr(llm_server.LlmServer, "_card_total", lambda self: 4096, raising=False)
    monkeypatch.setattr(llm_server.LlmServer, "_card_integrated", lambda self: False, raising=False)
    monkeypatch.setattr(llm_server.LlmServer, "_card_room", lambda self: room, raising=False)
    if delta:
        own = dataclasses.replace(llm_server.MEASURED_SHAPE, architecture="other", tied=False)
        monkeypatch.setattr(llm_server.gguf_shape, "read", lambda _path: own)
        monkeypatch.setattr(llm_server, "model_delta_mib", lambda _c, _b, shape: delta if shape is own else 0.0)
    server = llm_server.LlmServer("model.gguf", "llama-server.exe", **kwargs)
    server.start()
    return server, (launched[0] if launched else [])


def _in_ram(command: list[str]) -> bool:
    return "-ot" in command and command[command.index("-ot") + 1] == OUTPUT


def _cells(command: list[str]) -> int:
    return int(command[command.index("-c") + 1])


def test_on_the_gtx_1650_the_factory_model_writes_with_its_output_on_the_card(tmp_path: Path, monkeypatch) -> None:
    # Esencial at 32,768 cells, as in 1.5.5 (the listing's 3,292 chose it), and its output matrix beside it: 3,064 + 498
    # + 200 = 3,762 inside the 3,900 no process holds. The prefix's key is 1.5.5's (the settings with -ot).
    monkeypatch.setenv("BAXY_RENEW_CTX_NEEDS", f"{COMPLETO},{ESENCIAL}")
    before, kept = _started(monkeypatch, tmp_path, GTX_1650_LISTED, None)
    server, command = _started(monkeypatch, tmp_path, GTX_1650_LISTED, GTX_1650_ROOM)
    assert _cells(command) == _cells(kept) == 32768 and _in_ram(kept) and not _in_ram(command)
    assert server.output_on_card and server.card_fit == before.card_fit and server.card_short is None
    assert server._keyed_settings == before._settings
    assert [a for a in kept if a not in ("-ot", OUTPUT)] == command


@pytest.mark.parametrize("room", [3500, 3600, 3761])
def test_a_desktop_on_the_same_card_keeps_the_output_in_ram(tmp_path: Path, monkeypatch, room: int) -> None:
    # A desktop PC with one card of 4 GB: the desktop holds 300-500 MiB of it, and 3,762 do not fit what is left.
    monkeypatch.setenv("BAXY_RENEW_CTX_NEEDS", f"{COMPLETO},{ESENCIAL}")
    server, command = _started(monkeypatch, tmp_path, GTX_1650_LISTED, room)
    assert _cells(command) == 32768 and _in_ram(command) and not server.output_on_card


def test_the_factory_profile_and_cells_never_grow_with_the_room(tmp_path: Path, monkeypatch) -> None:
    # The room bounds the listing's figure, it never adds to it: where the listing says less than the card has, the
    # factory's model starts with the profile and cells of 1.5.5, whatever the room (its prefix does not move).
    monkeypatch.setenv("BAXY_RENEW_CTX_NEEDS", f"{COMPLETO},{ESENCIAL}")
    for listed in (GTX_1650_LISTED, 4400, 5130):
        _, kept = _started(monkeypatch, tmp_path, listed, None)
        for room in range(listed, listed + 2000, 100):
            server, command = _started(monkeypatch, tmp_path, listed, room)
            assert _cells(command) == _cells(kept), (listed, room)


def test_a_desktop_that_leaves_less_than_the_listing_says_is_counted(tmp_path: Path, monkeypatch) -> None:
    # The listing is blind to other processes (the PC, 05:45: 15,235 «free» with 3 GB held by another): a card whose
    # desktop leaves 3,100 MiB does not hold Esencial's 3,264 whole, whatever the listing says.
    monkeypatch.setenv("BAXY_RENEW_CTX_NEEDS", f"{COMPLETO},{ESENCIAL}")
    server, command = _started(monkeypatch, tmp_path, GTX_1650_LISTED, 3100)
    assert server.card_short is not None and server.card_short["freeMb"] == 3100 and _in_ram(command)


@pytest.mark.parametrize("delta", [LLAMA_DELTA, GRANITE_DELTA])
def test_a_model_of_its_own_that_fits_the_card_is_not_refused(tmp_path: Path, monkeypatch, delta: int) -> None:
    # Refused on the GTX 1650 by the listing's 3,292 («no cabe en la memoria libre de tu tarjeta gráfica»), both ran alone
    # at 32,768 cells inside the card. With the room they start in Esencial at 32,768.
    monkeypatch.setenv("BAXY_RENEW_CTX_NEEDS", str(ESENCIAL))
    refused, _ = _started(monkeypatch, tmp_path, GTX_1650_LISTED, None, delta)
    assert refused.card_refused
    server, command = _started(monkeypatch, tmp_path, GTX_1650_LISTED, GTX_1650_ROOM, delta)
    assert not server.card_refused and command and _cells(command) == 32768
    # Granite holds it with the margin (3,846 ≤ 3,900); Llama only without it (3,875): told short until it runs.
    assert (server.card_short is None) == (delta == GRANITE_DELTA)


def test_a_model_of_its_own_on_a_card_without_room_is_still_refused(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BAXY_RENEW_CTX_NEEDS", str(ESENCIAL))
    server, command = _started(monkeypatch, tmp_path, GTX_1650_LISTED, 3600, LLAMA_DELTA)
    assert server.card_refused and not command


def _health(monkeypatch, server: llm_server.LlmServer, held: list[int], commands: list[list[str]]) -> None:
    """Walk _wait_health with a server that answers at once and holds ``held`` MiB on the card, one figure a run."""
    figures = iter(held)

    class Alive:
        pid = 4242

        def __init__(self, command, **_kwargs) -> None:
            commands.append(command)

        def poll(self) -> None:
            return None

        def kill(self) -> None:
            commands.append(["killed"])

        def wait(self, _timeout: float) -> int:
            return 1

    class Reply:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_a) -> None:
            return None

    monkeypatch.setattr(llm_server.subprocess, "Popen", Alive)
    monkeypatch.setattr(llm_server.urllib.request, "urlopen", lambda *_a, **_k: Reply())
    monkeypatch.setattr(llm_server.LlmServer, "_held_on_card", lambda self: next(figures))
    server._launch(server._placement)
    server._wait_health()


def test_an_output_matrix_that_spilled_starts_again_in_ram(tmp_path: Path, monkeypatch) -> None:
    # Up with the output matrix on the card, the server holds 3,000 MiB there of its 3,562: the rest went to the PC's
    # memory. It is closed and started as 1.5.5 started it; that one holds its estimate and is ready.
    monkeypatch.setenv("BAXY_RENEW_CTX_NEEDS", f"{COMPLETO},{ESENCIAL}")
    server, _ = _started(monkeypatch, tmp_path, GTX_1650_LISTED, GTX_1650_ROOM)
    commands: list[list[str]] = []
    _health(monkeypatch, server, [3000, 2990], commands)
    assert not _in_ram(commands[0]) and commands[1] == ["killed"] and _in_ram(commands[2]) and len(commands) == 3
    assert server._ready.is_set() and not server.output_on_card and server.card_short is None


def test_an_output_matrix_that_fits_stays_on_the_card(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BAXY_RENEW_CTX_NEEDS", f"{COMPLETO},{ESENCIAL}")
    server, _ = _started(monkeypatch, tmp_path, GTX_1650_LISTED, GTX_1650_ROOM)
    commands: list[list[str]] = []
    _health(monkeypatch, server, [3493], commands)  # C1650Y §16, M0: 3,493 MiB
    assert len(commands) == 1 and server._ready.is_set() and server.output_on_card


@pytest.mark.parametrize("held, short", [(3700, False), (3000, True)])
def test_a_model_of_its_own_is_told_short_only_when_it_does_not_hold_it(
        tmp_path: Path, monkeypatch, held: int, short: bool) -> None:
    # Llama started without the margin (card_short at start). Up, it holds 3,700 of its 3,875 estimate: all of it, so it
    # is not short (the App would say «irá a la memoria compartida»); holding 3,000 it is, and it runs, as before.
    monkeypatch.setenv("BAXY_RENEW_CTX_NEEDS", str(ESENCIAL))
    server, _ = _started(monkeypatch, tmp_path, GTX_1650_LISTED, GTX_1650_ROOM, LLAMA_DELTA)
    assert server.card_short is not None
    commands: list[list[str]] = []
    _health(monkeypatch, server, [held], commands)
    assert len(commands) == 1 and server._ready.is_set() and (server.card_short is not None) == short


def test_an_unread_card_is_as_before(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BAXY_RENEW_CTX_NEEDS", f"{COMPLETO},{ESENCIAL}")
    server, command = _started(monkeypatch, tmp_path, GTX_1650_LISTED, None)
    commands: list[list[str]] = []
    _health(monkeypatch, server, [100], commands)  # whatever it held: start did not read the card, nothing is judged
    assert _in_ram(command) and len(commands) == 1 and server._ready.is_set() and server.card_short is None


def test_the_room_is_the_dedicated_memory_less_what_every_process_holds(monkeypatch) -> None:
    adapters = [("NVIDIA GeForce GTX 1650", 3935 * MIB, "luid_0x00000000_0x0000abcd"),
                ("Intel(R) UHD Graphics 630", 128 * MIB, "luid_0x00000000_0x00001234"),
                ("NVIDIA GeForce GTX 1650", 3935 * MIB, "luid_0x00000000_0x0000ffff")]  # listed again, no counters
    used = {"luid_0x00000000_0x0000ABCD_phys_0": 35 * MIB, "luid_0x00000000_0x00001234_phys_0": 0}
    monkeypatch.setattr(memory, "_adapters", lambda: adapters)
    monkeypatch.setattr(memory, "_gpu_counter", lambda _path: used)
    assert memory.card_room_mb("NVIDIA GeForce GTX 1650") == 3900
    assert memory.card_room_mb("AMD Radeon RX 7600") is None
    monkeypatch.setattr(memory, "_gpu_counter", lambda _path: None)
    assert memory.card_room_mb("NVIDIA GeForce GTX 1650") is None


def test_the_listing_keeps_each_device_description() -> None:
    listed = "Available devices:\n  CUDA0: NVIDIA GeForce GTX 1650 (4095 MiB, 3292 MiB free)\n"
    assert llm_server.listed_devices(listed)[0].description == "NVIDIA GeForce GTX 1650"


def test_a_mind_closing_starts_no_server_again(tmp_path: Path, monkeypatch) -> None:
    # close() ran while the server came up: the one that spilled is left to close(), and none other is started after it.
    monkeypatch.setenv("BAXY_RENEW_CTX_NEEDS", f"{COMPLETO},{ESENCIAL}")
    server, _ = _started(monkeypatch, tmp_path, GTX_1650_LISTED, GTX_1650_ROOM)
    server._closing = True
    commands: list[list[str]] = []
    _health(monkeypatch, server, [3000], commands)
    assert len(commands) == 1


def test_on_vulkan_the_estimate_is_not_judged(tmp_path: Path, monkeypatch) -> None:
    # Its line was measured on one card, not against what Windows counts for the process at every size: as before.
    server, _ = _started(monkeypatch, tmp_path, 8000, 7000, backend="vulkan")
    commands: list[list[str]] = []
    _health(monkeypatch, server, [100], commands)
    assert len(commands) == 1 and server.card_short is None and server._ready.is_set()


def test_a_second_spill_is_told_with_its_own_figure(tmp_path: Path, monkeypatch) -> None:
    # Started again with the output matrix in RAM, it still holds less than its estimate: the App is told what this run
    # needs (3,064 + 200), not the first one's with the output matrix.
    monkeypatch.setenv("BAXY_RENEW_CTX_NEEDS", f"{COMPLETO},{ESENCIAL}")
    server, _ = _started(monkeypatch, tmp_path, GTX_1650_LISTED, GTX_1650_ROOM)
    commands: list[list[str]] = []
    _health(monkeypatch, server, [3000, 2500], commands)
    assert server.card_short is not None
    assert server.card_short["needMb"] == llm_server.card_mib(32768) + llm_server.CARD_MARGIN_MIB


@pytest.mark.parametrize("listed, room", [(2963, 3500), (2763, 3300)])
def test_a_card_filled_by_others_starts_the_profile_it_holds(tmp_path: Path, monkeypatch, listed: int, room: int) -> None:
    # C1650Y, step 3 of velx2_motor: with 400 and 600 MiB held by another process the listing fell to 2,963 and 2,763, and
    # Esencial with its output matrix in RAM ran whole in both (17.3 tokens/s), while without it 146 and 310 MiB spilled.
    # 1.5.5 found no profile in the listing and started none; now Esencial, whole, with the output matrix in RAM.
    monkeypatch.setenv("BAXY_RENEW_CTX_NEEDS", f"{COMPLETO},{ESENCIAL}")
    before, _ = _started(monkeypatch, tmp_path, listed, None)
    assert before.card_refused
    server, command = _started(monkeypatch, tmp_path, listed, room)
    assert not server.card_refused and _cells(command) == 32768 and _in_ram(command) and server.card_short is None


def test_a_context_given_on_a_card_filled_by_others_is_judged_by_what_is_there(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BAXY_RENEW_CTX_NEEDS", str(ESENCIAL))
    server, command = _started(monkeypatch, tmp_path, 2763, 3300, context=32768)
    assert not server.card_refused and server.card_short is None and _in_ram(command)
