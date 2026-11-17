"""VELX1 (15-11-2026): the engine's OpenMP threads sleep once their piece of a token is done, on a GPU.

The packaged llama-server (b11609) is built with OpenMP and ggml sets KMP_BLOCKTIME=200 when nobody did: its threads spun
200 ms after each piece of CPU work, and on a GPU a token has one every 30-60 ms, so they never slept and took the
processor from the view and the mind while the card worked (llm_server.GPU_BLOCKTIME)."""
from __future__ import annotations

import os

import pytest

from baxy_mind import llm_server


@pytest.mark.parametrize("backend", ["cuda", "vulkan"])
def test_on_a_gpu_the_engines_threads_sleep_when_their_work_is_done(monkeypatch, backend: str) -> None:
    monkeypatch.delenv("KMP_BLOCKTIME", raising=False)
    environment = llm_server.server_environment("k", backend)
    assert environment["KMP_BLOCKTIME"] == "0"
    assert "KMP_BLOCKTIME" not in os.environ  # only the server's copy


def test_on_the_processor_the_engine_keeps_its_own(monkeypatch) -> None:
    # Everything is CPU work there, one piece after another: nothing waits for a card.
    monkeypatch.delenv("KMP_BLOCKTIME", raising=False)
    assert "KMP_BLOCKTIME" not in llm_server.server_environment("k", "cpu")


@pytest.mark.parametrize("theirs", ["200", "5"])
def test_a_value_the_person_set_is_left_as_it_is(monkeypatch, theirs: str) -> None:
    monkeypatch.setenv("KMP_BLOCKTIME", theirs)
    assert llm_server.server_environment("k", "cuda")["KMP_BLOCKTIME"] == theirs
