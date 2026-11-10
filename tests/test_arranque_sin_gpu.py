"""N9 (L5, 2026-11-06): a PC with no graphics card BAXY can use. Measured on a notebook with its RTX hidden from llama-server
(this GGUF, b11609, the prefix's 45,261 tokens): each token costs more the more were read. The CPU's first batches read at
59 tokens/s and at 45,000 tokens at 4; the integrated Radeon's at 50 and within 6,000 tokens at 8. Neither reads the prefix
in the 30 min of PREFIX_CEILING_S, and a start ran them to end as «tiempo»: nothing the person can read, and again from the
start, five times. The cost is the server's own (time_ms of its prompt progress): a read that will not fit the ceiling
says so once a fair part of it was read, with its figures, and the mind says when no GPU computes."""
import json
import subprocess
import tempfile
import threading
from pathlib import Path

import pytest

from baxy_mind import llm_server
from baxy_mind.llm_server import LlmServer, ReadTooSlow

TOTAL = 48500
PREFIX = 45261
# The seconds of each 2,048-token batch of the real prefix, read by the mind on its server (sonda_lectura.py, 2026-11-06).
CPU = [34.5, 43.2, 55.5, 71.6, 113.2, 134.3]
INTEGRATED = [41.1, 116.3, 254.6]
RTX = [0.83] * 4 + [0.94] * 6 + [1.05] * 4 + [1.18] * 4 + [1.31] * 4


def _chunk(processed: int, seconds: float, cache: int = 0, total: int = TOTAL) -> dict:
    # As b11609 fills it (server-context.cpp:2198-2201): processed counts the cached tokens too; time_ms is the slot's.
    return {"prompt_progress": {"total": total, "cache": cache, "processed": processed, "time_ms": int(seconds * 1000)}}


def _read(pace: float, batches: int, cache: int = 0, batch: int = 2048) -> None:
    watch = llm_server._Advance(LlmServer.PREFIX_STALL_S, LlmServer.PREFIX_CEILING_S, None)
    for step in range(1, batches + 1):
        watch(_chunk(cache + batch * step, batch * step / pace, cache))


def test_a_read_that_will_not_fit_the_ceiling_says_it_with_its_figures():
    with pytest.raises(ReadTooSlow) as raised:
        _read(pace=20.0, batches=8)
    assert raised.value.tokens_per_s == 20
    assert raised.value.need_s == pytest.approx(TOTAL / 20, rel=0.01)


def test_it_is_said_early_and_not_at_the_ceiling():
    watch = llm_server._Advance(LlmServer.PREFIX_STALL_S, LlmServer.PREFIX_CEILING_S, None)
    told_at = None
    for step in range(1, 24):
        try:
            watch(_chunk(2048 * step, 2048 * step / 20.0))
        except ReadTooSlow:
            told_at = 2048 * step / 20.0
            break
    assert told_at is not None and told_at < LlmServer.PREFIX_CEILING_S / 4


def _curve(batches: list[float]) -> llm_server._Advance:
    """The measured batches through a watch, until it ends the read."""
    watch = llm_server._Advance(LlmServer.PREFIX_STALL_S, LlmServer.PREFIX_CEILING_S, None)
    seconds = 0.0
    for step, batch in enumerate(batches, start=1):
        seconds += batch
        watch(_chunk(2048 * step, seconds, total=PREFIX))
    return watch


def test_the_cpus_measured_read_is_called_at_its_third_batch_and_not_by_its_mean():
    # Its mean there is 46 tokens/s: 16 min, inside the 30. It takes ~105 (232 ms a token at 45,000, sonda_turno.py).
    assert PREFIX / (2048 * 3 / sum(CPU[:3])) < LlmServer.PREFIX_CEILING_S
    with pytest.raises(ReadTooSlow) as raised:
        _curve(CPU)
    assert raised.value.tokens_per_s == 46
    assert raised.value.need_s > LlmServer.PREFIX_CEILING_S * 1.5


def test_the_integrated_gpus_measured_read_is_called_too():
    with pytest.raises(ReadTooSlow) as raised:
        _curve(INTEGRATED)
    assert raised.value.need_s > LlmServer.PREFIX_CEILING_S * 2


def test_a_stall_of_the_integrated_gpu_at_its_third_batch_is_the_slow_read():
    # Its third batch took 254 s, past the 120 of the stall: the first two say enough.
    watch = _curve(INTEGRATED[:2])
    watch.moved -= LlmServer.PREFIX_STALL_S + 1
    with pytest.raises(ReadTooSlow):
        watch(None)


def test_the_rtxs_measured_read_goes_on_and_says_about_what_it_took():
    # 25 s in all, whatever the small growth of its batches.
    watch = _curve(RTX)
    assert watch.need_s == pytest.approx(25, abs=8)


def test_a_slow_gpu_that_fits_is_waited_for():
    # The RX 7600's 45,240 tokens in 167.5 s (uso 84), and five times slower than that.
    _read(pace=270.0, batches=23)
    _read(pace=54.0, batches=23)


def test_what_is_left_grows_with_the_curve_as_the_read_says_it():
    told: list[int | None] = []
    watch = llm_server._Advance(LlmServer.PREFIX_STALL_S, LlmServer.PREFIX_CEILING_S,
                                lambda _done, _total: told.append(watch.seconds_left))
    # A read that fits the ceiling and slows down as it goes: 20, 24 and 28 s its first batches of 2,048 tokens. What is
    # left is told from the third (VUL1, PREFIX_TOLD_STRETCHES: the CPU's own curve is called too slow at that batch).
    slowing = [20.0, 24.0, 28.0]
    for step in range(1, 4):
        watch(_chunk(2048 * step, sum(slowing[:step]), total=PREFIX))
    assert told[:2] == [None, None]
    # By the mean, the third batch says under 8 min; by the curve, past that.
    assert told[2] > (PREFIX - 6144) / (6144 / sum(slowing)) * 1.3


def test_one_slow_first_batch_does_not_decide():
    # A cold disk or a busy moment: 2,048 tokens at 18 tokens/s are too few to judge the read by.
    _read(pace=18.0, batches=1)


def test_a_batch_held_for_minutes_is_one_outlier():
    # And it is not a curve either: 290 tokens/s, the second batch held for 4 min, the third at 290 again.
    watch = llm_server._Advance(LlmServer.PREFIX_STALL_S, LlmServer.PREFIX_CEILING_S, None)
    seconds = 0.0
    for step, held in enumerate([0.0, 240.0, 0.0], start=1):
        seconds += 2048 / 290 + held
        watch(_chunk(2048 * step, seconds))
    assert watch.need_s < 300


def test_the_tokens_the_slot_already_held_do_not_count_as_read():
    # A prompt mostly in the cache: 40,000 cached tokens came at no cost, and they are not the pace.
    with pytest.raises(ReadTooSlow) as raised:
        _read(pace=4.0, batches=4, cache=40000, batch=2048)
    assert raised.value.tokens_per_s == 4
    assert raised.value.need_s == pytest.approx((TOTAL - 40000) / 4, rel=0.01)


def test_what_is_left_of_a_read_is_told_while_it_reads():
    told: list[int | None] = []
    watch = llm_server._Advance(LlmServer.PREFIX_STALL_S, LlmServer.PREFIX_CEILING_S,
                                lambda _done, _total: told.append(watch.seconds_left))
    watch(_chunk(0, 0.0))
    for step in range(1, 4):
        watch(_chunk(4096 * step, 100.0 * step))
    # VUL1: nothing is promised from one stretch or two (PREFIX_TOLD_STRETCHES, tests/test_plazo_arranque.py).
    assert told[:3] == [None, None, None]
    assert told[3] == pytest.approx((TOTAL - 4096 * 3) / 41, rel=0.02)


def test_a_stall_at_a_pace_that_does_not_fit_is_the_slow_read():
    watch = llm_server._Advance(-1.0, LlmServer.PREFIX_CEILING_S, None)
    with pytest.raises(ReadTooSlow) as raised:
        watch(_chunk(2048, 200.0))
    assert raised.value.tokens_per_s == 10


def test_a_gpu_that_hung_is_not_called_slow():
    # 300 tokens/s and a driver that hung inside a batch: the server still pings, nothing more is read. Its pace fits by far.
    watch = llm_server._Advance(-1.0, LlmServer.PREFIX_CEILING_S, None)
    with pytest.raises(TimeoutError) as raised:
        watch(_chunk(2048, 2048 / 300))
    assert not isinstance(raised.value, ReadTooSlow)


def test_a_stall_with_nothing_read_tells_no_pace():
    watch = llm_server._Advance(-1.0, LlmServer.PREFIX_CEILING_S, None)
    with pytest.raises(TimeoutError) as raised:
        watch(None)
    assert not isinstance(raised.value, ReadTooSlow)


def test_a_read_past_the_ceiling_that_slowed_down_says_its_figures():
    watch = llm_server._Advance(LlmServer.PREFIX_STALL_S, -1.0, None)
    with pytest.raises(ReadTooSlow):
        watch(_chunk(2048, 2048 / 300))


def test_a_read_past_the_ceiling_with_nothing_said_of_it_is_a_timeout():
    watch = llm_server._Advance(LlmServer.PREFIX_STALL_S, -1.0, None)
    with pytest.raises(TimeoutError) as raised:
        watch(None)
    assert not isinstance(raised.value, ReadTooSlow)


def test_a_gpu_another_program_took_for_minutes_is_not_called_slow():
    # 290 tokens/s, then 4 min with the GPU taken inside a batch: the mean says ~24 tokens/s and 33 min. What is left takes 2.5.
    watch = llm_server._Advance(LlmServer.PREFIX_STALL_S, LlmServer.PREFIX_CEILING_S, None)
    seconds = 0.0
    for step in range(1, 24):
        seconds += 2048 / 290 + (240.0 if step == 2 else 0.0)
        watch(_chunk(2048 * step, seconds))
    assert watch.tokens_per_s is not None


def test_small_batches_are_counted_together():
    # A server that ends its batches early (at a checkpoint) still tells a pace, read by stretches of PREFIX_STRETCH_TOKENS.
    with pytest.raises(ReadTooSlow) as raised:
        _read(pace=20.0, batches=40, batch=256)
    assert raised.value.tokens_per_s == 20


def test_the_read_tells_the_processor_and_what_is_left_through_the_warm_up(monkeypatch):
    monkeypatch.setattr(llm_server.subprocess, "run", lambda *_a, **_k: subprocess.CompletedProcess(
        [], 0, stdout="Available devices:\n  (none)\n", stderr=""))
    server = LlmServer("model.gguf", "llama-server.exe")
    told: list[int | None] = []
    listed = threading.Event()
    device = server._read_device

    def read_device():
        device()
        listed.set()

    def stream(_body, _timeout, _on_text, watch):
        assert listed.wait(5)
        for step in range(1, 4):
            watch(_chunk(4096 * step, 100.0 * step))
        return {}

    server._ready.set()
    server._stream = stream
    server._read_device = read_device
    server.read_prefix({}, lambda _done, _total: told.append(server.prefix_left))
    assert told[-1] == pytest.approx((TOTAL - 4096 * 3) / 41, rel=0.02)
    assert server.on_processor is True


def test_a_kept_prefix_asks_nothing_of_the_device(monkeypatch):
    # A start that restores its prefix takes a second: no process more for it, and nothing to tell.
    def never(*_a, **_k):
        raise AssertionError("listed the devices at a start that read nothing")

    monkeypatch.setattr(llm_server.subprocess, "run", never)
    monkeypatch.setattr(llm_server.subprocess, "Popen", lambda *_a, **_k: type("P", (), {"poll": lambda self: None})())
    monkeypatch.setattr(LlmServer, "_wait_health", lambda self: None)
    monkeypatch.delenv("BAXY_MIND_MMPROJ", raising=False)
    server = LlmServer("model.gguf", "llama-server.exe")
    monkeypatch.setattr(server, "_log_path", lambda: Path(tempfile.mkdtemp()) / "llama-server.log")
    monkeypatch.setattr(server, "slot_dir", Path(tempfile.mkdtemp()))
    server.start()
    assert server.on_processor is None


def _alive(tmp_path, monkeypatch) -> LlmServer:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    class Alive:
        returncode = None

        def poll(self) -> None:
            return None

    server = LlmServer("model.gguf", "llama-server.exe")
    server._process = Alive()
    return server


def test_the_start_fails_with_the_slow_reads_cause_and_figures(tmp_path, monkeypatch):
    failure = _alive(tmp_path, monkeypatch).startup_failure(ReadTooSlow(tokens_per_s=20, need_s=2425.0))
    assert failure == {"cause": "lectura_lenta", "tokensPerS": 20, "needMinutes": 41}


def test_a_lack_of_memory_in_the_log_still_names_the_memory(tmp_path, monkeypatch):
    server = _alive(tmp_path, monkeypatch)
    path = server._log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("alloc_tensor_range: failed to allocate Vulkan0 buffer of size 2202009600\n", encoding="utf-8")
    assert server.startup_failure(ReadTooSlow(tokens_per_s=20, need_s=2425.0))["cause"] == "vram_insuficiente"


def test_another_failure_of_the_start_stays_the_time_it_ran_out_of(tmp_path, monkeypatch):
    assert _alive(tmp_path, monkeypatch).startup_failure(TimeoutError("not healthy")) == {"cause": "tiempo"}


@pytest.mark.parametrize(("listed", "expected"), [
    ("Available devices:\n  (none)\n", True),
    ("Available devices:\n  CUDA0: NVIDIA GeForce RTX 3060 Laptop GPU (6143 MiB, 5130 MiB free)\n", False),
    ("Available devices:\n  Vulkan0: AMD Radeon(TM) Graphics (8140 MiB, 7733 MiB free)\n", False),
    ("something else\n", None),
])
def test_whether_the_processor_computes_is_what_the_server_lists(monkeypatch, listed, expected):
    monkeypatch.setattr(llm_server.subprocess, "run",
                        lambda *_a, **_k: subprocess.CompletedProcess([], 0, stdout=listed, stderr=""))
    assert llm_server.computes_on_processor("llama-server.exe", "cuda", "99") is expected


def test_a_listing_that_fails_says_nothing(monkeypatch):
    def fail(*_a, **_k):
        raise OSError("gone")

    monkeypatch.setattr(llm_server.subprocess, "run", fail)
    assert llm_server.computes_on_processor("llama-server.exe", "cuda", "99") is None


@pytest.mark.parametrize(("backend", "layers"), [("cpu", "99"), ("cuda", "0"), ("vulkan", "0")])
def test_a_folder_with_no_gpu_or_no_layers_on_it_computes_on_the_processor_with_nothing_run(monkeypatch, backend, layers):
    def never(*_a, **_k):
        raise AssertionError("no process to list what is known")

    monkeypatch.setattr(llm_server.subprocess, "run", never)
    assert llm_server.computes_on_processor("llama-server.exe", backend, layers) is True


def test_the_progress_line_says_what_is_left_and_the_processor():
    # __main__'s progress line, as a message: told as json with nothing of the person's in it.
    server = LlmServer("model.gguf", "llama-server.exe")
    server.on_processor = True
    server.prefix_left = 600
    line = llm_server.progress_facts(server)
    assert json.dumps(line) == '{"secondsLeft": 600, "onProcessor": true}'


def test_what_is_not_known_is_left_out_of_the_progress():
    server = LlmServer("model.gguf", "llama-server.exe")
    assert llm_server.progress_facts(server) == {}


def test_a_turns_request_is_not_paced_and_ends_as_it_did():
    # int-staging-2 (L4 with L5): a turn's request watches its stream with the same _Advance (LlmServer._waited), and its
    # ends are L4's, at the stall or the ceiling. ReadTooSlow is the prefix's: its cost was measured only there. The same
    # slow read of 16,384 tokens past a kept prefix ends the prefix's read early, and not the turn's.
    server = LlmServer("model.gguf", "llama-server.exe")
    total = PREFIX + 16384
    chunks = [_chunk(PREFIX + 2048 * step, 2048 * step / 20.0, PREFIX, total) for step in range(1, 8)]
    turn = server._waited()
    for chunk in chunks:
        turn(chunk)
    assert turn.need_s is None
    turn.moved -= server.REQUEST_SECONDS + 1  # then it stalls: L4's own end, a plain TimeoutError
    with pytest.raises(TimeoutError, match="read nothing more") as stalled:
        turn(None)
    assert not isinstance(stalled.value, ReadTooSlow)
    prefix = llm_server._Advance(LlmServer.PREFIX_STALL_S, server.ceiling_s, None)
    with pytest.raises(ReadTooSlow):
        for chunk in chunks:
            prefix(chunk)
