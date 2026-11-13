"""VRAM5B (REV19, 13-11-2026): what the blind review of vram5 left open in the mind.

V-6: without ggml-vulkan's «uma» lines the mind measured the first device listed, which on a PC with integrated graphics
is the integrated one (its «free» is the PC's RAM), while llama.cpp ran on the dedicated card: measured ≠ used again.
V-4: a slow read on a card left with less free than the margin was told as a full card whatever the server shared, and a
server that fits already shares some 706 MiB (CUDA) or 618-648 (Vulkan): a false «the card ran out of memory».
"""
from baxy_mind import llm_server
from test_mind_vram4b import FACTORY
from test_mind_vram5 import IGPU_AND_4GB, _launched, _measured


def _without_uma(listed: str) -> str:
    return "Available devices:" + listed.split("Available devices:")[1]


# V-6: the device of unknown kind.

def test_without_uma_lines_the_device_with_least_free_is_measured() -> None:
    chosen = llm_server.chosen_device(llm_server.listed_devices(_without_uma(IGPU_AND_4GB)))
    assert chosen is not None and (chosen.name, chosen.free) == ("Vulkan1", 3400)


def test_without_uma_lines_no_dev_and_the_4_gb_card_fitted(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BAXY_RENEW_CTX_NEEDS", FACTORY)
    server, command = _launched(monkeypatch, tmp_path, _without_uma(IGPU_AND_4GB), backend="vulkan")
    assert command is not None and "-dev" not in command
    assert not llm_server.device_integrated(server.server)
    assert int(command[command.index("-c") + 1]) <= 32768


def test_with_uma_lines_the_dedicated_card_as_before() -> None:
    chosen = llm_server.chosen_device(llm_server.listed_devices(IGPU_AND_4GB))
    assert chosen is not None and (chosen.name, chosen.free) == ("Vulkan1", 3400)


# V-4: what a server that fits shares is no full card.

def _slow_read_failure(tmp_path, monkeypatch, shared: int | None, backend: str = "cuda") -> dict:
    _measured(monkeypatch, 3400, 4096)
    monkeypatch.setenv("BAXY_RENEW_CTX_NEEDS", FACTORY)
    server, command = _launched(monkeypatch, tmp_path, backend=backend)
    assert command is not None
    monkeypatch.setattr(llm_server.LlmServer, "_card_free", lambda self: 40)
    monkeypatch.setattr(llm_server, "gpu_shared_mb", lambda pid: shared, raising=False)
    return server.startup_failure(llm_server.ReadTooSlow(47, 1900.0))


def test_a_fitting_cuda_servers_shared_memory_is_no_full_card(tmp_path, monkeypatch) -> None:
    assert "cardFull" not in _slow_read_failure(tmp_path, monkeypatch, 706)


def test_a_fitting_vulkan_servers_shared_memory_is_no_full_card(tmp_path, monkeypatch) -> None:
    assert "cardFull" not in _slow_read_failure(tmp_path, monkeypatch, 648, backend="vulkan")


def test_shared_memory_unread_is_no_full_card(tmp_path, monkeypatch) -> None:
    assert "cardFull" not in _slow_read_failure(tmp_path, monkeypatch, None)


def test_a_spill_past_what_a_fitting_server_shares_is_a_full_card(tmp_path, monkeypatch) -> None:
    failure = _slow_read_failure(tmp_path, monkeypatch, 1298, backend="vulkan")
    assert failure["cardFull"] == {"freeMb": 40, "sharedMb": 1298}


# The blind review of vram5b.

def test_a_given_context_offers_no_cells_below_what_the_profile_needs(tmp_path, monkeypatch) -> None:
    # Completo chosen (one need): «Automático» never goes below what it needs, so 32,768 is no way out
    free = llm_server.card_mib(45056) + llm_server.CARD_MARGIN_MIB - 1
    _measured(monkeypatch, free, 4096)
    monkeypatch.setenv("BAXY_RENEW_CTX_NEEDS", "55034")
    server, _ = _launched(monkeypatch, tmp_path, context=77824)
    assert server.card_short is not None and server.card_short["given"] and "fitsContext" not in server.card_short


def test_a_given_context_with_the_factory_profiles_offers_the_cells_the_smallest_one_holds(tmp_path, monkeypatch) -> None:
    free = llm_server.card_mib(45056) + llm_server.CARD_MARGIN_MIB - 1
    _measured(monkeypatch, free, 4096)
    monkeypatch.setenv("BAXY_RENEW_CTX_NEEDS", FACTORY)
    server, _ = _launched(monkeypatch, tmp_path, context=77824)
    assert server.card_short is not None and server.card_short.get("fitsContext") == 32768


def test_a_slow_read_on_an_integrated_gpu_is_no_full_card(tmp_path, monkeypatch) -> None:
    _measured(monkeypatch, 15000, 16000, integrated="1")
    monkeypatch.setattr(llm_server, "installed_memory_mb", lambda: 32768)
    server, command = _launched(monkeypatch, tmp_path, backend="vulkan")
    monkeypatch.setattr(llm_server.LlmServer, "_card_free", lambda self: 40)
    monkeypatch.setattr(llm_server, "gpu_shared_mb", lambda pid: 4000, raising=False)
    assert "cardFull" not in server.startup_failure(llm_server.ReadTooSlow(47, 1900.0))


def test_without_uma_lines_the_total_is_the_least_too() -> None:
    listed = ("Available devices:\n  Vulkan0: Intel(R) UHD Graphics 730 (16000 MiB, 3000 MiB free)\n"
              "  Vulkan1: AMD Radeon RX 6500 XT (4080 MiB, 3500 MiB free)\n")
    chosen = llm_server.chosen_device(llm_server.listed_devices(listed))
    assert chosen is not None and (chosen.free, chosen.total) == (3000, 4080)
