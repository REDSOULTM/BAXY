"""VUL1 (2026-11-09): what the mind says is left of the prefix's read («Preparando el modelo · N % · quedan unos X min»).
On an RX 7600 on Vulkan the window said «quedan unos 7 min» 9 s into a read that took 63 s (INFORME_AMD3.md §4): the
one stretch measured so far carried what the server does once. Nothing is promised until the read's own stretches can
leave one of them out (llm_server.PREFIX_TOLD_STRETCHES)."""
from __future__ import annotations

import pytest

from baxy_mind import llm_server
from baxy_mind.llm_server import LlmServer

PREFIX = 46822  # the tokens of the product's prefix on that card
BATCH = 1024  # llama-server's batch on Vulkan (llm_server.batch_size)
FIRST_S = 9.0  # its first batch there, with what the server does once
PACE = 1100.0  # tokens per second from the second batch on


def _chunk(processed: int, seconds: float) -> dict:
    return {"prompt_progress": {"total": PREFIX, "cache": 0, "processed": processed, "time_ms": int(seconds * 1000)}}


def _told(batches: int, first_s: float = FIRST_S) -> list[int | None]:
    """What is left, as told at each of the first ``batches`` batches of that read."""
    told: list[int | None] = []
    watch = llm_server._Advance(LlmServer.PREFIX_STALL_S, LlmServer.PREFIX_CEILING_S,
                                lambda _done, _total: told.append(watch.seconds_left))
    for step in range(1, batches + 1):
        watch(_chunk(BATCH * step, first_s + BATCH * (step - 1) / PACE))
    return told


def test_no_minutes_are_promised_from_the_first_stretch_alone():
    # By that stretch alone the rest would take 7 min, what the window said; it took under one.
    assert (PREFIX - BATCH) * (FIRST_S / BATCH) / 60 > 6
    assert _told(1) == [None]


def test_nor_from_two_when_one_of_them_is_the_servers_first():
    # Two stretches still say 3 to 4 min: their median is their mean.
    assert _told(2) == [None, None]


def test_from_the_third_stretch_what_is_left_is_the_reads_own_pace():
    told = _told(6)
    assert told[:2] == [None, None]
    for step, left in enumerate(told[2:], start=3):
        assert left == pytest.approx((PREFIX - BATCH * step) / PACE, rel=0.05)
    assert all(left < 60 for left in told[2:])  # «queda menos de 1 min», which was true


def test_a_read_with_no_slow_first_stretch_is_told_the_same_from_the_third():
    told = _told(4, first_s=BATCH / PACE)
    assert told[:2] == [None, None]
    assert told[3] == pytest.approx((PREFIX - BATCH * 4) / PACE, rel=0.02)


def test_the_slow_read_is_still_called_by_its_own_count_of_tokens():
    # ReadTooSlow never waited for a promise: it is raised by the tokens read (PREFIX_PACE_TOKENS), as before.
    watch = llm_server._Advance(LlmServer.PREFIX_STALL_S, LlmServer.PREFIX_CEILING_S, None)
    with pytest.raises(llm_server.ReadTooSlow):
        for step in range(1, 8):
            watch(_chunk(BATCH * step, BATCH * step / 20.0))
