"""VRAM4B (2026-11-12): a new install on a card of 4 GB in all starts by itself.

VRAM4 left it open: the factory's tool profile, Completo, fits ~3,400 MiB free at no context, so the first start on that
card still went to the breakdown. The leader's decision («Listo para usar desde 4 GB de VRAM… sin configurar nada»; the
owner: «Tiene que caber en 4 GB»): when the person never chose a profile the App gives the needs of the smaller ready-made
ones too (BAXY_RENEW_CTX_NEEDS, largest first) and the start takes the first that fits whole, said to the App in the hello;
a profile chosen by hand that the card cannot hold launches no server and fails in seconds with what it found.
"""
import pathlib

import pytest

from baxy_mind import llm_server
from baxy_mind.mind import CARD_PROFILE_FACT, SYSTEM
from test_mind_final import _mind

COMPLETO, AVANZADO, DIARIO, ESENCIAL = 51450 + 3584, 49708 + 3584, 40035 + 3584, 26489 + 3584
FACTORY = f"{COMPLETO},{AVANZADO},{DIARIO},{ESENCIAL}"


def _started(monkeypatch, tmp_path: pathlib.Path, free: int | None) -> tuple[llm_server.LlmServer, list[list[str]]]:
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
    server = llm_server.LlmServer("model.gguf", "llama-server.exe")
    server.start()
    return server, launched


def test_a_new_install_on_the_friends_card_starts_in_the_profile_that_fits(tmp_path: pathlib.Path, monkeypatch) -> None:
    monkeypatch.setenv("BAXY_RENEW_CTX_NEEDS", FACTORY)
    server, launched = _started(monkeypatch, tmp_path, 3400)
    command = launched[0]
    assert command[command.index("-c") + 1] == "32768"
    # what was free, what the factory's profile takes, and the need served: the App maps it back to its profile
    assert server.card_fit == {"freeMb": 3400, "needMb": llm_server.card_mib(61440) + llm_server.CARD_MARGIN_MIB,
                               "needs": ESENCIAL, "context": 32768}
    assert server.card_short is None and not server.card_refused


@pytest.mark.parametrize(("free", "cells", "served"), [(3528, 45056, DIARIO), (3704, 53248, DIARIO), (3600, 45056, DIARIO), (3300, 32768, ESENCIAL)])
def test_the_largest_profile_the_card_holds_whole_is_the_one_taken(tmp_path, monkeypatch, free, cells, served) -> None:
    monkeypatch.setenv("BAXY_RENEW_CTX_NEEDS", FACTORY)
    server, launched = _started(monkeypatch, tmp_path, free)
    assert launched[0][launched[0].index("-c") + 1] == str(cells)
    assert server.card_fit is not None and server.card_fit["needs"] == served


@pytest.mark.parametrize("free", [None, 4232, 6000, 15000])
def test_where_the_card_has_room_the_list_changes_nothing(tmp_path, monkeypatch, free) -> None:
    monkeypatch.setenv("BAXY_RENEW_CTX_NEEDS", str(COMPLETO))
    _, alone = _started(monkeypatch, tmp_path / "a", free)
    monkeypatch.setenv("BAXY_RENEW_CTX_NEEDS", FACTORY)
    server, listed = _started(monkeypatch, tmp_path / "a", free)
    assert listed[0] == alone[0] and "77824" in listed[0]
    assert server.card_fit is None and server.card_short is None and not server.card_refused


def test_a_profile_chosen_by_hand_that_the_card_cannot_hold_launches_nothing(tmp_path, monkeypatch) -> None:
    # one need: the person's own choice. 61,440 cells take 3,680 MiB and 3,400 are free: the driver would spill the rest
    # into the PC's memory and the prefix would be read for half an hour. Nothing is launched and the failure says it.
    monkeypatch.setenv("BAXY_RENEW_CTX_NEEDS", str(COMPLETO))
    server, launched = _started(monkeypatch, tmp_path, 3400)
    assert launched == [] and server.card_refused and server.card_fit is None
    with pytest.raises(RuntimeError):
        server.wait_ready(5)
    assert server.startup_failure() == {"cause": "vram_insuficiente", "cardShort": {
        "freeMb": 3400, "needMb": llm_server.card_mib(61440) + llm_server.CARD_MARGIN_MIB, "context": 61440,
        "fitsContext": 32768}}


def test_a_card_that_holds_no_profile_launches_nothing_either(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BAXY_RENEW_CTX_NEEDS", FACTORY)
    server, launched = _started(monkeypatch, tmp_path, 2500)
    assert launched == [] and server.card_refused and server.card_fit is None
    assert server.startup_failure()["cardShort"] == {
        "freeMb": 2500, "needMb": llm_server.card_mib(61440) + llm_server.CARD_MARGIN_MIB, "context": 61440}


def test_a_profile_that_fits_only_without_the_margin_still_starts_and_says_so(tmp_path, monkeypatch) -> None:
    # Esencial's 32,768 cells take 3,064 MiB: with 3,100 free it fits, not with the margin. It starts, as VRAM4 left it.
    monkeypatch.setenv("BAXY_RENEW_CTX_NEEDS", FACTORY)
    server, launched = _started(monkeypatch, tmp_path, 3100)
    assert launched[0][launched[0].index("-c") + 1] == "32768" and not server.card_refused
    assert server.card_fit is not None and server.card_fit["needs"] == ESENCIAL
    assert server.card_short is not None and server.card_short["context"] == 32768


def test_the_free_memory_a_test_says_stands_for_the_cards(tmp_path, monkeypatch) -> None:
    asked: list[str] = []
    monkeypatch.setattr(llm_server, "_free_vram_mib", lambda server: asked.append(server) or 15000)
    server = llm_server.LlmServer("model.gguf", "llama-server.exe")
    monkeypatch.undo()
    monkeypatch.setattr(llm_server, "_free_vram_mib", lambda server: asked.append(server) or 15000)
    assert llm_server.LlmServer._card_free(server) == 15000
    monkeypatch.setenv("BAXY_TEST_VRAM_FREE_MIB", "3400")
    assert llm_server.LlmServer._card_free(server) == 3400 and len(asked) == 1
    monkeypatch.setenv("BAXY_TEST_VRAM_FREE_MIB", "muchos")
    assert llm_server.LlmServer._card_free(server) == 15000


def test_the_needs_are_read_as_a_list_or_not_at_all() -> None:
    assert llm_server.context_needs_all({"BAXY_RENEW_CTX_NEEDS": FACTORY}) == [COMPLETO, AVANZADO, DIARIO, ESENCIAL]
    assert llm_server.context_needs({"BAXY_RENEW_CTX_NEEDS": FACTORY}) == COMPLETO
    assert llm_server.context_needs_all({"BAXY_RENEW_CTX_NEEDS": "55034"}) == [55034]
    for unusable in ("", "55034,", "a,b", "55034,-1", "0"):
        assert llm_server.context_needs_all({"BAXY_RENEW_CTX_NEEDS": unusable}) == []


OPEN = {"name": "app.open", "description": "Abre una app.", "argumentsSchema": {"type": "object", "properties": {}},
        "risk": "low_reversible", "confirms": []}


def test_the_profile_the_card_gave_is_a_fact_of_the_system_text(tmp_path: pathlib.Path) -> None:
    # «¿Por qué estás en Esencial?»: the model reads what the start measured, never a guess.
    mind, _ = _mind(tmp_path, [])
    mind.configure({"capabilities": [OPEN], "cardProfile": {"profile": "Esencial", "factory": "Completo", "freeMb": 3400,
                                                             "needMb": 3880}})
    said = CARD_PROFILE_FACT.format(profile="Esencial", factory="Completo", free="3,3", need="3,8")
    assert said in mind.system and "3,3 GB" in said and "unos 3,8 GB" in said


def test_the_fact_says_the_profile_is_kept_and_how_to_change_it(tmp_path: pathlib.Path) -> None:
    # VRAM4C (the leader: «esa elección se queda fija… no vuelve sola a Completo aunque otro día haya memoria»): the profile
    # is BAXY's choice for this PC, kept, and the ways out are the person's: another model, free memory and ask for it.
    said = CARD_PROFILE_FACT.format(profile="Esencial", factory="Completo", free="3,3", need="3,8")
    assert "de fábrica de BAXY es Completo" in said and "eligió por su cuenta el perfil Esencial" in said
    assert "aunque otro día haya más memoria libre" in said
    assert "sólo cambia si la persona lo pide" in said and "pedir el perfil Completo" in said
    assert "otro modelo" in said and "liberar memoria" in said
    assert "volver a abrir" not in said, "opening BAXY again changes nothing: it is kept"


def test_without_it_the_system_text_is_the_one_of_before(tmp_path: pathlib.Path) -> None:
    plain, _ = _mind(tmp_path / "plain", [])
    plain.configure({"capabilities": [OPEN]})
    for at, card in enumerate((None, {}, "esencial", {"profile": "Esencial"}, {"profile": "Esencial", "factory": "Completo",
                                                                               "freeMb": "3400", "needMb": 3880})):
        mind, _ = _mind(tmp_path / str(at), [])
        mind.configure({"capabilities": [OPEN], "cardProfile": card})
        assert mind.system == plain.system
    assert CARD_PROFILE_FACT.split("{")[0] not in SYSTEM
