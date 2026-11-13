"""VRAM4 (2026-11-12): BAXY's own model starts on a card of 4 GB in all.

The owner: «Baxi debe de funcionar en un hardware de 4 GB… Tiene que caber en 4 GB». A friend's GTX 1050 Ti (4 GB, Windows 10)
got the automatic 77,824 cells and every layer (4,032 MiB of the server's own, measured on a 16 GB card), NVIDIA's driver
gave what did not fit from the system's memory, the prefix read at 62 → 47 tokens/s and the App gave up after 31-42 min
estimates. With the context left to the mind, the cells follow the VRAM free when the server starts (llm_server.fit_card).
"""
from pathlib import Path

import pytest

from baxy_mind import __main__ as sidecar, llm_server

ESENCIAL = 26489 + 3584  # ToolProfile.MeasuredPrefix and a turn (LocalContext.TurnRoomTokens)
COMPLETO = 51450 + 3584


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
    server = llm_server.LlmServer("model.gguf", "llama-server.exe", **kwargs)
    server.start()
    return server, launched[0]


def _given(command: list[str], flag: str) -> str:
    return command[command.index(flag) + 1]


def test_the_friends_card_starts_with_cells_that_fit_it(tmp_path: Path, monkeypatch) -> None:
    # 4 GB in all, Windows and a desktop open: ~3,400 MiB free. Esencial's prompt and a turn fit 32,768 cells whole.
    monkeypatch.setenv("BAXY_RENEW_CTX_NEEDS", str(ESENCIAL))
    server, command = _started(monkeypatch, tmp_path, 3400)
    assert int(_given(command, "-c")) < 77824
    assert int(_given(command, "-c")) >= ESENCIAL
    assert llm_server.card_mib(int(_given(command, "-c"))) < 3400
    assert _given(command, "-ngl") == "99"  # whole on the card
    assert server.context == int(_given(command, "-c")) and server.card_short is None
    assert sidecar.ready_facts(server, 26489)["context"] == server.context
    assert "cardShort" not in sidecar.ready_facts(server, 26489)


@pytest.mark.parametrize("free", [None, 4400, 6000, 15000])
def test_a_card_with_room_starts_as_before(tmp_path: Path, monkeypatch, free: int | None) -> None:
    # 4,032 MiB and the margin free, or a server that does not say: the same command, byte for byte.
    monkeypatch.setenv("BAXY_RENEW_CTX_NEEDS", str(COMPLETO))
    server, command = _started(monkeypatch, tmp_path, free)
    assert (_given(command, "-c"), _given(command, "-ngl")) == ("77824", "99")
    assert command == [
        "llama-server.exe", "-m", "model.gguf", "--host", "127.0.0.1", "--port", "9165", *server._settings]
    assert server._settings[:4] == ["-ngl", "99", "-c", "77824"] and "-fitt" not in command
    assert server.card_short is None and sidecar.ready_facts(server, 51450)["context"] == 77824


def test_the_most_cells_that_fit_and_never_fewer_than_the_profile_needs() -> None:
    margin = llm_server.CARD_MARGIN_MIB
    for free in range(3000, 4400, 50):
        for needs in (ESENCIAL, 43619, 53292, COMPLETO, None):
            cells, whole = llm_server.fit_card(free, 77824, needs)
            assert cells >= (needs or llm_server.CONTEXT) and cells <= 77824
            assert whole == (llm_server.card_mib(cells) + margin <= free)
            more = [c for c in llm_server.CARD_CONTEXTS if c > cells and llm_server.card_mib(c) + margin <= free]
            assert not (whole and more)
    assert llm_server.fit_card(None, 77824, ESENCIAL) == (77824, True)
    assert llm_server.card_mib(77824) == 4032 and llm_server.card_mib(53248) == 3504  # INFORME_51's two measures


def test_a_profile_the_card_does_not_hold_whole_is_told(tmp_path: Path, monkeypatch) -> None:
    # Completo's prompt and a turn take 55,034 cells: on 3,700 MiB free no context that holds it fits whole with its margin (VRAM4B: with ~3,400 none fits at all, test_mind_vram4b). The fewest
    # that hold it, and the ready line says what was free and what it takes, for the App to say it.
    monkeypatch.setenv("BAXY_RENEW_CTX_NEEDS", str(COMPLETO))
    server, command = _started(monkeypatch, tmp_path, 3700)
    assert _given(command, "-c") == "61440"
    assert server.card_short == {"freeMb": 3700, "needMb": llm_server.card_mib(61440) + llm_server.CARD_MARGIN_MIB,
                                 "context": 61440, "fitsContext": 45056}
    assert sidecar.ready_facts(server, 51450)["cardShort"] == server.card_short


def test_a_start_that_fails_on_a_short_card_says_what_it_found(tmp_path: Path, monkeypatch) -> None:
    # The friend's breakdown said «este equipo lee el modelo demasiado lento… necesita 4 GB libres». What the start found
    # goes with the failure, for the App to say the profile that does not fit and the one that does.
    monkeypatch.setenv("BAXY_RENEW_CTX_NEEDS", str(COMPLETO))
    server, _ = _started(monkeypatch, tmp_path, 3700)
    failure = server.startup_failure(llm_server.ReadTooSlow(47, 1900))
    assert failure["cause"] == "lectura_lenta" and failure["needMinutes"] == 32
    assert failure["cardShort"] == server.card_short and failure["cardShort"]["fitsContext"] == 45056
    roomy, _ = _started(monkeypatch, tmp_path, 15000)
    assert roomy.startup_failure(llm_server.ReadTooSlow(47, 1900)) == {
        "cause": "lectura_lenta", "tokensPerS": 47, "needMinutes": 32}


def test_with_no_need_said_every_profile_still_fits_the_cells(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_RENEW_CTX_NEEDS", raising=False)
    server, command = _started(monkeypatch, tmp_path, 3900)
    assert _given(command, "-c") == "61440" and server.card_short is None  # CONTEXT, which holds every profile


def test_a_context_the_person_chose_is_theirs(tmp_path: Path, monkeypatch) -> None:
    # Settings → Model → Context (BAXY_RENEW_CTX): as chosen, on a card that holds it, with nothing to say.
    server, command = _started(monkeypatch, tmp_path, 9000, context=77824)
    assert _given(command, "-c") == "77824" and server.card_short is None


@pytest.mark.parametrize("backend", ["cpu"])
def test_only_the_measured_backend_follows_the_card(tmp_path: Path, monkeypatch, backend: str) -> None:
    # The line of video memory over the cells was measured on CUDA (INFORME_51) and, VRAM5, on Vulkan (test_mind_vram5):
    # the processor starts as before.
    server, command = _started(monkeypatch, tmp_path, 3400, backend=backend)
    assert int(_given(command, "-c")) == llm_server.default_context(backend, ("q8_0", "q8_0"), False)
    assert server.card_short is None


def test_the_card_is_asked_once_for_the_cells_and_the_projector(tmp_path: Path, monkeypatch) -> None:
    projector = tmp_path / "mmproj.gguf"
    projector.write_bytes(b"gguf")
    monkeypatch.setenv("BAXY_MIND_MMPROJ", str(projector))
    asked: list[str] = []
    monkeypatch.setattr(llm_server, "_free_vram_mib", lambda server: asked.append(server) or 15000)
    _, command = _started(monkeypatch, tmp_path, 15000)
    assert "--mmproj-offload" in command and not asked
    monkeypatch.setenv("BAXY_RENEW_CTX_NEEDS", str(ESENCIAL))  # VRAM4B: a card that holds no cells launches nothing
    _, command = _started(monkeypatch, tmp_path, 3400)
    assert "--no-mmproj-offload" in command and not asked
