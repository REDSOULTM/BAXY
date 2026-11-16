"""MOD5 (2026-11-15): the mind's engine sizes the card by the model it runs, not by the factory's.

MOD2 §1, point 2: llm_server's line over the cells (CARD_FIXED_MIB, CARD_CELL_MIB; VULKAN_CARD_*) was measured with
Qwen3.5-4B alone, and any GGUF given to the engine was sized with it. A model whose cache is three times as wide was told
«cabe» and spilled; one smaller was refused. Now the GGUF's header moves the measured line by what differs (gguf_shape),
the factory's model keeps it byte for byte, and the automatic context never passes the model's own.
"""
import os
import pathlib
import struct

import pytest

from baxy_mind import gguf_shape, llm_server

COMPLETO, AVANZADO, DIARIO, ESENCIAL = 51450 + 3584, 49708 + 3584, 40035 + 3584, 26489 + 3584
FACTORY = f"{COMPLETO},{AVANZADO},{DIARIO},{ESENCIAL}"


def _text(value: str) -> bytes:
    data = value.encode()
    return struct.pack("<Q", len(data)) + data


def _gguf(path: pathlib.Path, keys: dict[str, object], tensors: list[tuple[str, list[int], int]], size: int) -> str:
    """A GGUF header of these keys (ints as u32, lists of ints as arrays of u32, texts) and tensors, padded to ``size``."""
    body = b""
    for key, value in keys.items():
        body += _text(key)
        if isinstance(value, str):
            body += struct.pack("<I", 8) + _text(value)
        elif isinstance(value, list):
            body += struct.pack("<II", 9, 4) + struct.pack("<Q", len(value)) + b"".join(struct.pack("<I", v) for v in value)
        else:
            body += struct.pack("<II", 4, value)
    for name, dims, kind in tensors:
        body += _text(name) + struct.pack("<I", len(dims)) + b"".join(struct.pack("<Q", d) for d in dims)
        body += struct.pack("<IQ", kind, 0)
    header = b"GGUF" + struct.pack("<IQQ", 3, len(tensors), len(keys)) + body
    with open(path, "wb") as file:
        file.write(header)
        file.truncate(size)
    return str(path)


def _llama_like(tmp_path: pathlib.Path, context: int = 131072, size: int = 2019377600, tools: bool = True) -> str:
    """A dense model of 28 layers and 8 KV heads of 128: 57,344 cache values a cell, 3.5 times the 4B's."""
    keys = {"general.architecture": "llama", "llama.block_count": 28, "llama.context_length": context,
            "llama.embedding_length": 3072, "llama.feed_forward_length": 8192, "llama.attention.head_count": 24,
            "llama.attention.head_count_kv": 8,
            "tokenizer.chat_template": "{% if tools %}{{ tools }}{% endif %}" if tools else "{{ messages }}"}
    return _gguf(tmp_path / "otro.gguf", keys, [("token_embd.weight", [3072, 128256], 14)], size)


def _started(monkeypatch, tmp_path: pathlib.Path, gguf: str, free: int | None, **kwargs) -> tuple[llm_server.LlmServer, list[list[str]]]:
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
    server = llm_server.LlmServer(gguf, "llama-server.exe", **kwargs)
    server.start()
    return server, launched


def test_the_header_is_read_as_the_apps_reader_reads_it(tmp_path: pathlib.Path) -> None:
    shape = gguf_shape.read(_llama_like(tmp_path))
    assert shape is not None
    assert (shape.architecture, shape.layers, shape.context_length) == ("llama", 28, 131072)
    assert shape.full_cell_values == 8 * 256 * 28 and shape.layer_cell_values == 8 * 256
    assert shape.token_embedding_bytes == 3072 * 128256 // 256 * 210 and shape.tied and shape.has_tools
    assert gguf_shape.read(str(tmp_path / "missing.gguf")) is None


def test_sliding_and_shared_cache_layers_keep_what_llama_cpp_gives_them(tmp_path: pathlib.Path) -> None:
    # Six layers, one of each three full; the last two read the cache of earlier ones; sliding layers' own widths.
    keys = {"general.architecture": "gemma4", "gemma4.block_count": 6, "gemma4.context_length": 131072,
            "gemma4.embedding_length": 2560, "gemma4.feed_forward_length": 10240, "gemma4.attention.head_count": 8,
            "gemma4.attention.head_count_kv": 2, "gemma4.attention.key_length": 512,
            "gemma4.attention.value_length": 512, "gemma4.attention.key_length_swa": 256,
            "gemma4.attention.value_length_swa": 256, "gemma4.attention.sliding_window": 512,
            "gemma4.attention.sliding_window_pattern": [1, 1, 0, 1, 1, 0], "gemma4.attention.shared_kv_layers": 2}
    shape = gguf_shape.read(_gguf(tmp_path / "g.gguf", keys, [("token_embd.weight", [2560, 1024], 12),
                                                                ("per_layer_token_embd.weight", [1536, 1024], 13)], 10 << 20))
    assert shape is not None
    assert shape.full_cell_values == 2 * 1024 and shape.sliding_cell_values == 3 * 2 * 512
    assert shape.input_bytes == shape.token_embedding_bytes + 1536 * 1024 // 256 * 176


@pytest.mark.parametrize("backend", ["cuda", "vulkan"])
def test_the_factory_models_line_is_the_measured_one_byte_for_byte(backend: str) -> None:
    for cells in (*llm_server.CARD_CONTEXTS, 61440, 122880):
        measured = llm_server.card_mib(cells, backend)
        assert llm_server.card_mib(cells, backend, llm_server.MEASURED_SHAPE) == measured
        # the tuned model: the same tensors, a header a few bytes longer
        tuned = llm_server.MEASURED_SHAPE.__class__(**{**llm_server.MEASURED_SHAPE.__dict__, "file_bytes": 2740937440})
        assert llm_server.card_mib(cells, backend, tuned) == measured


def test_the_factory_gguf_on_this_pc_reads_as_the_measured_shape() -> None:
    path = pathlib.Path(os.environ.get("FACTORY_GGUF", "Qwen3.5-4B-Q4_K_M.gguf"))
    if not path.is_file():
        pytest.skip("the factory GGUF is not on this PC")
    assert gguf_shape.read(str(path)) == llm_server.MEASURED_SHAPE


def test_a_model_with_a_wider_cache_takes_more_of_the_card(tmp_path: pathlib.Path) -> None:
    shape = gguf_shape.read(_llama_like(tmp_path))
    # 3.5 times the 4B's cache a cell, and 1.4 GB less of weights on the card
    assert llm_server.card_mib(32768, "cuda", shape) > llm_server.card_mib(32768) + 700
    assert llm_server.card_mib(77824, "cuda", shape) > llm_server.card_mib(77824) + 2500


def test_on_a_card_the_factory_fits_whole_another_model_starts_in_the_profile_that_fits(tmp_path, monkeypatch) -> None:
    # 4,500 MiB free: the 4B runs Completo at 77,824 cells; this model holds Esencial's cells whole and no more.
    monkeypatch.setenv("BAXY_RENEW_CTX_NEEDS", FACTORY)
    server, launched = _started(monkeypatch, tmp_path, _llama_like(tmp_path), 4500)
    command = launched[0]
    assert command[command.index("-c") + 1] == "32768"
    assert server.card_fit is not None and server.card_fit["needs"] == ESENCIAL
    assert server.card_fit["needMb"] == llm_server.card_mib(61440, "cuda", server.shape) + llm_server.CARD_MARGIN_MIB
    assert server.card_short is None and not server.card_refused


def test_a_model_the_card_cannot_hold_launches_no_server_and_says_so(tmp_path, monkeypatch) -> None:
    # 3,600 MiB: the 4B starts in Diario; this model does not hold even Esencial's cells.
    monkeypatch.setenv("BAXY_RENEW_CTX_NEEDS", FACTORY)
    server, launched = _started(monkeypatch, tmp_path, _llama_like(tmp_path), 3600)
    assert launched == [] and server.card_refused
    failure = server.startup_failure()
    assert failure["cause"] == "vram_insuficiente"
    assert failure["cardShort"]["needMb"] == llm_server.card_mib(server.context, "cuda", server.shape) + llm_server.CARD_MARGIN_MIB
    assert llm_server.card_mib(32768, "cuda", server.shape) > 3600


def test_the_automatic_context_never_passes_the_models_own(tmp_path, monkeypatch) -> None:
    server, launched = _started(monkeypatch, tmp_path, _llama_like(tmp_path, context=40960), None)
    assert server.context == 40960
    assert launched[0][launched[0].index("-c") + 1] == "40960"
    # a context the person gave is theirs
    given, _ = _started(monkeypatch, tmp_path, _llama_like(tmp_path, context=40960), None, context=53248)
    assert given.context == 53248


def test_a_gguf_that_cannot_be_read_keeps_the_measured_line(tmp_path, monkeypatch) -> None:
    broken = tmp_path / "roto.gguf"
    broken.write_bytes(b"GGUF\x03\x00\x00\x00 not a header")
    monkeypatch.setenv("BAXY_RENEW_CTX_NEEDS", FACTORY)
    server, launched = _started(monkeypatch, tmp_path, str(broken), 3400)
    assert server.shape is None
    assert launched[0][launched[0].index("-c") + 1] == "32768" and server.card_fit["needs"] == ESENCIAL


@pytest.mark.parametrize("free", [None, 1500, 3300, 3400, 3528, 3600, 3704, 4000, 4232, 4500, 15000])
@pytest.mark.parametrize("needs", [FACTORY, str(COMPLETO), str(ESENCIAL)])
def test_with_the_factory_gguf_the_server_starts_with_the_same_command(tmp_path, monkeypatch, free, needs) -> None:
    path = pathlib.Path(os.environ.get("FACTORY_GGUF", "Qwen3.5-4B-Q4_K_M.gguf"))
    if not path.is_file():
        pytest.skip("the factory GGUF is not on this PC")
    monkeypatch.setenv("BAXY_RENEW_CTX_NEEDS", needs)
    real, launched = _started(monkeypatch, tmp_path, str(path), free)
    assert real.shape == llm_server.MEASURED_SHAPE
    monkeypatch.setattr(llm_server.gguf_shape, "read", lambda _path: None)  # as before MOD5: no header read
    before, launched_before = _started(monkeypatch, tmp_path, str(path), free)
    assert before.shape is None
    assert launched == launched_before
    assert (real.context, real.card_fit, real.card_short, real.card_refused) == (
        before.context, before.card_fit, before.card_short, before.card_refused)
