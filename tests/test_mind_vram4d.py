"""VRAM4D (REV18 R18-2, 13-11-2026): only a card short of memory in all keeps BAXY's choice of profile.

VRAM4C kept the profile a start took for the card (byCard) whatever the card: a card of 6-8 GB that started once while
a game held its memory stayed in Esencial or Diario for good. The leader's decision: the card is short when the factory's
profile does not fit whole even in the card's whole memory less what Windows and the desktop keep (card_short), which
--list-devices already says beside the free memory; on any other card the fit serves that start only, and a choice of
BAXY's kept from before (BAXY_RENEW_CTX_KEPT) is not kept there: the start tries the factory's profile again.
"""
import pathlib

import pytest

from baxy_mind import llm_server
from test_mind_vram4b import COMPLETO, ESENCIAL, FACTORY


def _started(monkeypatch, tmp_path: pathlib.Path, free: int | None, total: int | None):
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
    monkeypatch.setattr(llm_server.LlmServer, "_card_total", lambda self: total, raising=False)
    server = llm_server.LlmServer("model.gguf", "llama-server.exe")
    server.start()
    return server, launched[0] if launched else None


def _cells(command: list[str]) -> str:
    return command[command.index("-c") + 1]


@pytest.mark.parametrize(("total", "short"), [(4096, True), (4095, True), (6144, False), (8192, False), (16380, False),
                                              (None, None)])
def test_a_card_is_short_by_its_whole_memory_not_by_what_is_free(total, short) -> None:
    assert llm_server.card_short(total, 77824, COMPLETO) is short
    assert llm_server.card_short(total, 77824, None) is None


def test_a_game_on_a_card_with_room_fits_that_start_only(tmp_path, monkeypatch) -> None:
    # R18-2 as REV18 tells it: a card of 8 GB, a game open, 3,400 MiB free at this start.
    monkeypatch.setenv("BAXY_RENEW_CTX_NEEDS", FACTORY)
    server, command = _started(monkeypatch, tmp_path, 3400, 8192)
    assert _cells(command) == "32768" and server.card_fit is not None and server.card_fit["needs"] == ESENCIAL
    assert server.card_memory == {"totalMb": 8192, "short": False}, "the App keeps nothing: the card has room"


def test_the_friends_card_is_short(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BAXY_RENEW_CTX_NEEDS", FACTORY)
    server, command = _started(monkeypatch, tmp_path, 3400, 4096)
    assert _cells(command) == "32768" and server.card_fit is not None and server.card_fit["needs"] == ESENCIAL
    assert server.card_memory == {"totalMb": 4096, "short": True}


@pytest.mark.parametrize("free", [3400, 3700, 15000])
def test_baxys_choice_kept_on_a_short_card_goes_alone(tmp_path, monkeypatch, free) -> None:
    # The same command as when the App gave only its need (VRAM4C): another day's free memory changes nothing.
    monkeypatch.setenv("BAXY_RENEW_CTX_NEEDS", str(ESENCIAL))
    _, alone = _started(monkeypatch, tmp_path, free, 4096)
    monkeypatch.setenv("BAXY_RENEW_CTX_NEEDS", FACTORY)
    monkeypatch.setenv("BAXY_RENEW_CTX_KEPT", str(ESENCIAL))
    server, kept = _started(monkeypatch, tmp_path, free, 4096)
    assert kept == alone and server.card_fit is None


def test_baxys_choice_kept_on_a_card_with_room_tries_the_factorys_again(tmp_path, monkeypatch) -> None:
    # A byCard of the 1.5.1 on a card of 8 GB: with the card free, the factory's profile, as a new install's.
    monkeypatch.setenv("BAXY_RENEW_CTX_NEEDS", FACTORY)
    monkeypatch.setenv("BAXY_RENEW_CTX_KEPT", str(ESENCIAL))
    server, command = _started(monkeypatch, tmp_path, 7000, 8192)
    assert _cells(command) == "77824" and server.card_fit is None
    assert server.card_memory == {"totalMb": 8192, "short": False}


def test_with_the_whole_memory_unknown_the_kept_choice_stays(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BAXY_RENEW_CTX_NEEDS", FACTORY)
    monkeypatch.setenv("BAXY_RENEW_CTX_KEPT", str(ESENCIAL))
    server, command = _started(monkeypatch, tmp_path, 7000, None)
    assert server.card_fit is None and server.card_memory is None
    monkeypatch.setenv("BAXY_RENEW_CTX_NEEDS", str(ESENCIAL))
    monkeypatch.delenv("BAXY_RENEW_CTX_KEPT")
    _, alone = _started(monkeypatch, tmp_path, 7000, None)
    assert command == alone


@pytest.mark.parametrize("free", [0, 9000])
def test_a_free_memory_that_cannot_be_is_not_taken(tmp_path, monkeypatch, free) -> None:
    # R18-15: none free, or more free than the card has, is no measure: the start is the one with nothing measured.
    monkeypatch.setenv("BAXY_RENEW_CTX_NEEDS", FACTORY)
    server, command = _started(monkeypatch, tmp_path, free, 8192)
    assert _cells(command) == "77824" and server.card_fit is None and server.card_short is None
    assert not server.card_refused


def test_where_the_card_has_room_nothing_changes(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BAXY_RENEW_CTX_NEEDS", FACTORY)
    _, before = _started(monkeypatch, tmp_path, 15000, None)
    server, now = _started(monkeypatch, tmp_path, 15000, 16380)
    assert now == before and server.card_fit is None and server.card_short is None


def test_the_whole_memory_comes_from_the_same_listing_or_a_test(monkeypatch) -> None:
    listed = "Available devices:\n  CUDA0: NVIDIA GeForce GTX 1050 Ti (4095 MiB, 3400 MiB free)\n"
    asked: list[str] = []
    monkeypatch.setattr(llm_server, "_listed_devices", lambda server: asked.append(server) or listed)
    monkeypatch.undo()
    monkeypatch.setattr(llm_server, "_listed_devices", lambda server: asked.append(server) or listed)
    server = llm_server.LlmServer("model.gguf", "llama-server.exe")
    assert server._card_free() == 3400 and server._card_total() == 4095 and len(asked) == 1
    monkeypatch.setenv("BAXY_TEST_VRAM_TOTAL_MIB", "8192")
    assert server._card_total() == 8192
