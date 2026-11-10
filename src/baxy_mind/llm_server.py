"""The local model server: one llama-server process owned by the mind, one slot, its prompt prefix kept in cache and on disk."""
from __future__ import annotations

import hashlib
import http.client
import json
import math
import os
import re
import secrets
import select
import socket
import statistics
import subprocess
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

from .memory import free_memory_mb


# Uso 95 (F9, uso real 2026-11-04 12:06): how ggml says, in the server's log, that a buffer could not be reserved. The
# shape of the process's error only, never anything the person said. «failed/unable to allocate <buffer type> buffer»
# names the memory (ggml-alloc.c alloc_tensor_range and ggml_gallocr_reserve_n, ggml-backend.cpp
# ggml_backend_buft_alloc_buffer, llama-model.cpp «unable to allocate %s buffer»): a host type (CPU, CPU_Mapped,
# CPU_REPACK, CUDA_Host, Vulkan_Host) is the PC's RAM, any other (CUDA0, Vulkan0, ROCm0) the graphics card's.
_BUFFER_NAMED = re.compile(r"(?:failed|unable) to allocate (\S+) buffer")
_RAM_SHAPES = ("ggml_backend_cpu_buffer_type_alloc_buffer: failed to allocate",)
_VRAM_SHAPES = ("cudaMalloc failed: out of memory", "CUDA error: out of memory",
                "ggml_vulkan: Device memory allocation of size", "ErrorOutOfDeviceMemory")
# The assert that follows a buffer ggml could not reserve (ggml-backend.cpp, GGML_ASSERT(buffer) at b11609).
_ANY_MEMORY_SHAPES = ("GGML_ASSERT(buffer) failed",)
_BUFFER_SIZE = re.compile(r"(?:failed to allocate (?:\S+ )?buffer of size|Device memory allocation of size) (\d+)")
_LOG_TAIL_BYTES = 64 * 1024


def memory_failure(log: str) -> str | None:
    """The startup cause a server's log gives when it ran out of memory (MindStartupFailure.Causes): «ram_insuficiente»,
    «vram_insuficiente», «memoria_insuficiente» when it does not say which (or says both), or None."""
    kinds = {"ram" if name.startswith("CPU") or name.endswith("_Host") else "vram"
             for name in _BUFFER_NAMED.findall(log)}
    kinds |= {"ram"} if any(shape in log for shape in _RAM_SHAPES) else set()
    kinds |= {"vram"} if any(shape in log for shape in _VRAM_SHAPES) else set()
    if kinds == {"ram"}:
        return "ram_insuficiente"
    if kinds == {"vram"}:
        return "vram_insuficiente"
    return "memoria_insuficiente" if kinds or any(shape in log for shape in _ANY_MEMORY_SHAPES) else None


def buffer_size_mb(log: str) -> int | None:
    """uso-116 (N23): how big the buffer that did not fit was, the largest a server's log names as not reserved, or None."""
    sizes = [int(size) for size in _BUFFER_SIZE.findall(log)]
    return round(max(sizes) / (1024 * 1024)) if sizes else None


def model_file_failure(log: str) -> str | None:
    """The startup cause a server's log gives when it could not open or read the model's file (gguf.cpp at b11609)."""
    if "failed to open GGUF file" in log:
        return "modelo_ausente"
    return "modelo_danado" if "E gguf_init_from_reader:" in log else None


class _StreamBroken(Exception):
    """A streamed chat ended with an error after its first token, or its stream could not be read."""


class Yielded(Exception):
    """A read ahead (prefill) ended because a request was waiting (LlmServer.yields)."""


class ReadTooSlow(TimeoutError):
    """N9 (L5): the server will not read the prefix in time: at what pace it was reading (tokens per second) and what the
    whole prefix would take at that pace (seconds)."""

    def __init__(self, tokens_per_s: int, need_s: float) -> None:
        super().__init__(f"the prompt is being read at {tokens_per_s} tokens/s and would take {need_s} s")
        self.tokens_per_s, self.need_s = tokens_per_s, need_s


class _Advance:
    """Whether the server still advances through a prompt it streams (LlmServer.read_prefix, LlmServer.chat): each larger
    ``processed`` of its prompt progress, and any chunk after the prompt (what it writes), is an advance, told to
    ``on_moved``. ``stall`` seconds with none, or ``ceiling`` seconds in all, end the read (TimeoutError). N9 (L5): a
    ``paced`` read (the prefix's, LlmServer.read_prefix) whose cost will not fit the ceiling ends once PREFIX_PACE_TOKENS
    were read, instead of at the ceiling: the same outcome, said as what it is (ReadTooSlow). The cost is the server's own
    (time_ms and cache, server-context.cpp:2198-2201 at b11609), and not a mean: each token costs more the more were read
    (_read_cost). A stall whose read fits the ceiling is not slowness (a GPU's driver that hung reads nothing more at any
    pace): it stays a plain TimeoutError, which is relaunched. A turn's request (LlmServer.chat) is not paced: its cost was
    measured only for the prefix (INT2), so it ends as it did, at the stall or the ceiling."""

    def __init__(self, stall: float, ceiling: float, on_progress: Callable[[int, int], None] | None,
                 on_moved: Callable[[], None] | None = None, *, paced: bool = True) -> None:
        now = time.monotonic()
        self.started = self.moved = now
        self.stall, self.ceiling, self.on_progress, self.on_moved = stall, ceiling, on_progress, on_moved
        self.paced = paced
        self.processed = -1
        self.tokens_per_s: int | None = None
        self.need_s: float | None = None
        self.seconds_left: int | None = None
        self.mark = (0, 0)  # the tokens read and the server's ms at the last stretch's end
        self.stretches: list[tuple[float, float]] = []  # each stretch's middle (tokens in the slot) and its ms per token

    def _pace(self, progress: dict[str, Any], processed: int, total: int) -> None:
        cache = int(progress.get("cache") or 0)
        read, spent_ms = processed - cache, int(progress.get("time_ms") or 0)
        if read <= 0 or spent_ms <= 0:
            return
        self.tokens_per_s = round(read * 1000 / spent_ms)
        if read - self.mark[0] >= PREFIX_STRETCH_TOKENS and spent_ms > self.mark[1]:
            self.stretches.append((cache + (read + self.mark[0]) / 2, (spent_ms - self.mark[1]) / (read - self.mark[0])))
            self.mark = (read, spent_ms)
        base, growth = _read_cost(self.stretches, spent_ms / read)

        def seconds(start: int) -> float:
            return (base * (total - start) + growth * (total * total - start * start) / 2) / 1000

        self.need_s = seconds(cache)
        self.seconds_left = round(seconds(processed)) if len(self.stretches) >= PREFIX_TOLD_STRETCHES else None
        if read >= PREFIX_PACE_TOKENS and self.need_s > self.ceiling:
            raise ReadTooSlow(self.tokens_per_s, self.need_s)

    def __call__(self, chunk: dict[str, Any] | None) -> None:
        now = time.monotonic()
        progress = chunk.get("prompt_progress") if chunk is not None else None
        moved = chunk is not None and not isinstance(progress, dict)
        if isinstance(progress, dict):
            processed = int(progress.get("processed") or 0)
            if processed > self.processed:
                self.processed, moved = processed, True
                total = int(progress.get("total") or 0)
                if self.paced:
                    self._pace(progress, processed, total)
                if self.on_progress is not None:
                    self.on_progress(processed, total)
        if moved:
            self.moved = now
            if self.on_moved is not None:
                self.on_moved()
        over = now - self.started > self.ceiling
        if over or now - self.moved > self.stall:
            if self.tokens_per_s is not None and self.need_s is not None and (over or self.need_s > self.ceiling):
                raise ReadTooSlow(self.tokens_per_s, self.need_s)
            if now - self.moved > self.stall:
                raise TimeoutError(f"the server read nothing more of the prompt in {self.stall:.0f} s")
            raise TimeoutError(f"the prompt was not read in {self.ceiling:.0f} s")


# N9 (L5): the tokens read before a read's cost may end it, three of its batches (2,048 tokens by default, _Advance), and the
# least a stretch of the read needs to tell its cost by: the server's batches can end early (at a checkpoint).
PREFIX_PACE_TOKENS = 6144
PREFIX_STRETCH_TOKENS = 512
# VUL1 (2026-11-09): the stretches a read needs before the person is told what is left of it (seconds_left). The first
# one carries what the server does once (on an RX 7600 on Vulkan the first 1,024 tokens took ~9 s and the rest went at
# ~1,100 tokens/s: the window said «quedan unos 7 min» of a read that took 63 s, INFORME_AMD3.md §4). With two, that
# one still is half of the estimate (_read_cost's medians are then means); with three, the median leaves it out: a
# median of n values holds up to (n - 1) // 2 wrong ones (Rousseeuw & Leroy, «Robust Regression and Outlier
# Detection», 1987, ch. 1, breakdown point). ReadTooSlow does not wait for them: it has its own count of tokens.
PREFIX_TOLD_STRETCHES = 3


def _read_cost(stretches: list[tuple[float, float]], mean: float) -> tuple[float, float]:
    """What a token of the prompt costs (ms): ``base`` + ``growth`` × the tokens in the slot, from the read's stretches;
    ``mean`` alone with fewer than two. Measured with the prefix's 45,261 tokens, this GGUF, the product's arguments
    (the notebook, 2026-11-06), ms per token by 2,048-token batch: the CPU (Ryzen 7 5800H) 17, 21,
    27, 35, 55, 66, and 232 at 45,000 tokens, ~105 min in all where its first batches say 13; the integrated Radeon on
    Vulkan 20, 57, 124; the RTX 3060 0.41 to 0.70, 25 s in all. The attention of each token reads the whole cache
    (flash attention over its f16 copy: llm_server's KV notes). Theil-Sen (the median of the slopes of every pair, then of
    the bases: Sen 1968), so that a batch another program held for minutes is one outlier and not the curve."""
    if len(stretches) < 2:
        return mean, 0.0
    slopes = [(cost - earlier) / (middle - before)
              for index, (before, earlier) in enumerate(stretches) for middle, cost in stretches[index + 1:]]
    growth = max(0.0, statistics.median(slopes))
    return statistics.median(cost - growth * middle for middle, cost in stretches), growth


def _tell(on_text: Callable[[str | None, bool], bool], text: str | None, done: bool) -> bool:
    """What the model has written so far to the voice's look-ahead, which never fails the answer."""
    try:
        return bool(on_text(text, done))
    except Exception:  # noqa: BLE001 - a failing look-ahead is dropped
        return True


class LlmServer:
    # One slot (slot 0): every request (the person's turns and the heartbeat, which keeps the same tools and a system
    # text of its own) starts from the same cached tools. A second slot only served the composition and the forced arguments,
    # which the native loop no longer makes; it cost 950 MiB of VRAM (measured on the notebook, 2026-10-15). On a shared
    # remote server of several slots (measurement), the mind's one slot is BAXY_MIND_SLOT's (``slot``).

    # Review 2026-10-22: the App ends a turn's request at 30 s (MindSidecarClient.TurnRequestTimeout), and the mind waited
    # up to 120 s for a chat, 30 s for a fill and 10 s for a name, answering after the App had given up. Every call of
    # one request shares this budget (``deadline``, set per request by __main__; None for the warm-up and
    # session.load); spent, the request ends with an error, and the closed connection frees the slot.
    # Uso-124 (RX 7600 on Vulkan, ~100 tokens/s, 2026-11-05): a web.fetch's 2,850 tokens take ~29 s to read, and the turn
    # ended with nothing said while the server was still reading it. The budget is now what a request may go without the
    # server advancing: each advance gives it these seconds again (_advance), up to a ceiling in all (ceiling_s). A chat
    # that streams hears the server's own progress (return_progress, _Advance); one that cannot stream, because its token
    # probabilities are read (chat), looks at /slots (_answer). A hung server advances in neither: it fails as it did.
    # Revisión PCR1 (A2): the ceiling was 120 s, ~4,900 tokens at 50 tokens/s, and the RX 7600's first decision of a turn
    # read 7,369 tokens past its cache (147 s at that speed). It is now what this server may have to read, at the slowest
    # its window lets it go on (ceiling_s); REQUEST_CEILING_S only until the warm-up says what the server keeps (kept).
    # Both count from when the request arrived (__main__), as the App's own window and ceiling count from when it sent it.
    # A model behind an API takes longer than one second (ExternalModel); the App waits 6 s more (TurnRequestTimeout).
    # The ceiling is never shorter than that window (int-staging-1): a model on this PC behind the translator keeps its 294 s.
    REQUEST_SECONDS = float(os.environ.get("BAXY_MIND_TURN_SECONDS") or 30.0) - 6.0
    REQUEST_CEILING_S = max(120.0, REQUEST_SECONDS)
    # The longest ceiling the App takes from catalog.ready (MindSidecarClient.StartupCeiling, 45 min), less the margin
    # its own has over this one (TurnCeilingMargin, 6 s): past it the App keeps its own and gives up first.
    REQUEST_MOST_S = 45 * 60.0 - 6.0
    # What a request's answer may take past its read: DECISION_TOKENS (768, mind.py) at 13.5 tokens/s, the slowest
    # decode measured here (the output matrix in RAM on Vulkan, VULKAN_CONTEXT's note).
    ANSWER_S = 60.0
    # How often a chat that does not stream looks at /slots, and how long it waits for its answer: a decision that takes
    # less never asks. b11609 answers it while it decodes (below, _look).
    SLOTS_EVERY_S = 2.0
    SLOTS_LOOK_S = 1.0
    # A written answer advances at every token: the App is told at most this often.
    ADVANCE_TOLD_EVERY_S = 1.0
    # Uso real 2026-11-03 (F4): a turn's decision got an HTTP 500 from llama-server after 2.6 s and the turn ended with
    # nothing said; the same request 10 s later was answered. A 5xx is the server's own failure, not the request's (RFC
    # 9110 §15.6), and asking the model again has no effect on the PC, so it is asked again once, after a pause that
    # doubles per try (exponential backoff: Google Cloud «Retry strategy»; AWS Builders' Library «Timeouts, retries, and
    # backoff with jitter»), within the request's budget. Only at this one layer (the same sources: retries stacked at
    # several layers multiply); the mind's answer after it (Mind._next) is a different request, words only. One client
    # and one slot: no jitter, which spreads many clients.
    SERVER_ERROR_RETRIES = 1
    SERVER_ERROR_PAUSE_S = 0.5
    # Uso 84 (AMD RX 7600 on Vulkan, 2026-11-04): a cold start read its 45,240-token prefix at 298 tok/s in 167.5 s,
    # against a fixed 600 s here and 180 s in the App's conductor; a slower GPU (an integrated one) or a longer prefix
    # would have been taken for a failed start. The warm-up is waited for while the server advances through the prompt
    # (read_prefix), as it says itself: llama-server streams its progress per batch of the prompt it decodes
    # (return_progress, tools/server/README.md and server-context.cpp:3823 and 4313 at b11609; 2,048 tokens per batch
    # by default). It fails when no progress comes for PREFIX_STALL_S (one batch at ~17 tok/s, a sixth of what the AMD
    # GPU reads), or past PREFIX_CEILING_S in all (the prefix at ~25 tok/s), the safety ceiling.
    PREFIX_STALL_S = 120.0
    PREFIX_CEILING_S = 1800.0

    def __init__(self, gguf: str, server: str, gpu_layers: str = "99", context: int | None = None,
                 extra_args: list[str] | None = None, log_name: str = "llama-server.log",
                 kv: tuple[str, str] | None = None, backend: str = "cuda") -> None:
        self.took_s: float | None = None  # how long the last chat took (chat)
        self.gguf = gguf
        # The KV cache's types (K, V): BAXY_RENEW_KV when not given (kv_types), by default q8_0 and q8_0, and the flash
        # attention that goes with them (flash_attention). ``backend`` is the folder's (declared_backend). On CUDA the
        # output matrix is kept in RAM (OUTPUT_ON_CPU) unless BAXY_RENEW_OUTPUT_CPU=0; on Vulkan it stays on the GPU.
        self.kv = kv or kv_types(os.environ.get("BAXY_RENEW_KV", ""))
        self.flash = flash_attention(backend, self.kv)
        self.backend = backend
        self.output_cpu = os.environ.get("BAXY_RENEW_OUTPUT_CPU", "").strip() != "0" if backend == "cuda" else False
        self.extra_args = list(extra_args or [])
        self.log_name = log_name
        self.server = server
        self.gpu_layers = gpu_layers
        # The cells that fit the backend's budget with this cache (default_context) when not given.
        self.context = context or default_context(backend, self.kv, self.output_cpu)
        # The most history a cut may leave for the model to read again in one decision (Mind._fits): what this cache
        # reads in time on this backend (reread_tokens).
        self.reread_tokens = reread_tokens(backend, self.kv)
        # PLAN_GENERAL A5: a pinned port lets the click's vision stage (BAXY_VISION_ENDPOINT) reach this same server.
        # Measurement only (ft-c3, 2026-10-29): BAXY_MIND_LLAMA_REMOTE=<port> uses a llama-server another machine runs,
        # reached on this loopback port (an ssh -L tunnel), started with this class's same arguments; nothing is launched.
        self.remote = _remote_port()
        # PRV1 (PRIV-04): the key this server asks of every request (server_key), and each of the mind's carries it.
        self.key = server_key()
        # Encargo 11 (measurement only): BAXY_MIND_SLOT=<n> is the slot this mind takes on that shared remote server,
        # so several minds share one server of several slots (-np); 0 when unset, the one slot of the mind's own server.
        self.slot = _mind_slot(self.remote)
        self.port = self.remote or _pinned_port() or _free_port()
        self._process: subprocess.Popen | None = None
        self._placement: list[str] = []  # where this run's server keeps the projector (projector_placement)
        self._ready = threading.Event()
        self._failure: str | None = None
        self._deadline: float | None = None
        self._ceiling: float | None = None
        # The tokens of the prompt prefix the warm-up left in the server's cache (Mind.warm); 0 until it says.
        self.kept = 0
        # Told at each advance of the request under way (set by __main__, the App's window starts again), which lasts
        # while they come: a person's turn. None otherwise: anything else keeps its fixed budget.
        self.advanced: Callable[[], None] | None = None
        self._told = 0.0
        # Where the server writes a slot's state (--slot-save-path): the prompt prefix kept between starts (V1) and the
        # state a vision question sets aside (BAXY_VISION_SLOT_DIR, the same folder).
        self.slot_dir = _slot_dir()
        self._settings: list[str] = []  # the server's arguments but its address, set by start (part of the prefix key)
        # Al máximo, palancas 2 y 5 (early.py): the text the last prefill left in the slot, while no other call of this
        # mind has used the slot since; None otherwise. A prefill of that same text is not sent again: with the slot
        # already holding all of it, a hybrid model must go back to a checkpoint to read its last token again.
        self.resident: str | None = None
        # Whether a request waits for the mind (set by __main__): a read ahead gives way to it (prefill).
        self.yields: Callable[[], bool] = lambda: False
        # N9 (L5), told to the App (progress_facts): whether the processor computes, with no GPU the server can use
        # (computes_on_processor; None until known, and never asked when the prefix is restored: one process more at
        # every start for a start that takes a second), and the seconds left of the prefix being read (read_prefix).
        self.on_processor: bool | None = None
        self.prefix_left: int | None = None

    @property
    def name(self) -> str:
        return Path(self.gguf).name

    @property
    def deadline(self) -> float | None:
        """When the request under way ends if the server does not advance, None with no budget."""
        return self._deadline

    @deadline.setter
    def deadline(self, value: float | None) -> None:
        # Set once per request (__main__), one window from its start: its ceiling counts from that start too.
        self._deadline = value
        self._ceiling = None if value is None else value - self.REQUEST_SECONDS + self.ceiling_s

    @property
    def ceiling_s(self) -> float:
        """The most a request may last while the server advances (revisión PCR1, A2): what the context leaves past the
        prefix the server keeps, read at the slowest the window lets a server go on (one batch, batch_size, every
        REQUEST_SECONDS: it tells its progress once a batch), one batch more for a read that does not start on a batch's
        edge, and its answer (ANSWER_S). So the ceiling never ends a read the window would let go on: it only ends one
        that advances without end. On the RX 7600 (61,440 cells, 45,361 kept, batches of 1,024) it is 468 s.
        Never past what the App takes from it (REQUEST_MOST_S, int-staging-1): a model behind an API, 84 s a window and
        a context of 200,000, came to ~8,100 s, the App kept its own 126 s, and the mind went on after it gave up."""
        if self.kept <= 0:
            return self.REQUEST_CEILING_S
        batches = math.ceil(max(self.context - self.kept, 0) / batch_size(self.backend)) + 1
        return min(self.REQUEST_SECONDS * batches + self.ANSWER_S, self.REQUEST_MOST_S)

    def _advance(self) -> None:
        """The server advanced: the request has its window again, within its ceiling, and the App is told."""
        now = time.monotonic()
        if self._deadline is not None and self._ceiling is not None:
            self._deadline = max(self._deadline, min(now + self.REQUEST_SECONDS, self._ceiling))
        if self.advanced is not None and now - self._told >= self.ADVANCE_TOLD_EVERY_S:
            self._told = now
            self.advanced()

    def start(self) -> None:
        vision = _vision_args()
        self._settings = [
            "-ngl", self.gpu_layers, "-c", str(self.context), *slots(self.backend), *read_batch(self.backend),
            "-fa", self.flash,
            "-ctk", self.kv[0], "-ctv", self.kv[1], "--jinja", "--reasoning", "off", "--reasoning-budget", "0",
            # Read the GGUF into the GPU without mapping it: a mapped model keeps its pages in the working set after
            # they reach the GPU (measured on the PC 2026-10-15: RAM 3237 → 1132 MiB, same VRAM 3905 MiB and speed).
            "--load-mode", "none",
            # Al máximo 3.3 (2026-10-22): no prompt cache in RAM, and at most 10 context checkpoints instead of 32. The
            # cache (1,536 MiB) held nothing: it only takes a prompt the slot is losing over half of (f_keep < 0.5,
            # server-context.cpp:1751 at b11609), and no prompt with its state and checkpoints fit it
            # (server-task.cpp:1735). The checkpoints live in RAM (~50 MiB each): up to ~1.1 GB less in a long session
            # (the notebook's count, not yet measured). With the list full llama.cpp first drops the other tasks'
            # checkpoints closer than -cms to the one before, never the first, then the oldest
            # (server-context.cpp:2537-2563), so the one at the prefix's end stays. The two flags go together: with 10
            # checkpoints a prompt would fit the cache, and the RAM would grow instead. The spacing stays llama.cpp's
            # (every 512 tokens cost ~46 ms per decision and 55 MiB of VRAM, decision2 d6 vs d6b, 2026-10-15). Watch
            # «erasing old context checkpoint» with n_tokens ≈ the prefix in llama-server.log: it should stay at 0.
            "-cram", "0", "-ctxcp", "10",
        ] + (["-ot", OUTPUT_ON_CPU] if self.output_cpu else []) + vision +["--slot-save-path", str(self.slot_dir)] + self.extra_args
        if self.remote:
            # Only the kept prefix's facts are written here (restore_prefix): its state is on the server's disk.
            self.slot_dir.mkdir(parents=True, exist_ok=True)
            threading.Thread(target=self._wait_health, daemon=True).start()
            return
        # A state a vision question set aside and never put back holds the person's conversation: none is kept. The
        # kept prefix (PREFIX) is not one of them: it is saved before any turn (Mind.warm).
        self.slot_dir.mkdir(parents=True, exist_ok=True)
        self.forget_set_aside()
        self._launch(projector_placement(self.server, self.backend))
        threading.Thread(target=self._wait_health, daemon=True).start()

    def _launch(self, placement: list[str]) -> None:
        self._placement = placement
        command = [self.server, "-m", self.gguf, "--host", "127.0.0.1", "--port", str(self.port), *self._settings,
                   *placement]
        log_path = self._log_path()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        # Uso real 2026-11-03 (F4): each start wrote over the last run's log, and the cause of a 500 went with the
        # relaunch after it; the last run's log is kept beside it (.1), as the App keeps the mind's stderr.
        try:
            os.replace(log_path, log_path.with_name(log_path.name + ".1"))
        except FileNotFoundError:
            pass  # a first run
        except OSError:
            pass  # held by a server still closing: this run writes over it, as before
        # The server writes its log through its own inherited handle: the mind's copy is closed once it started.
        with open(log_path, "w", encoding="utf-8") as log:
            self._process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, creationflags=flags,
                                             env=server_environment(self.key, self.backend))

    def _log_path(self) -> Path:
        return Path(os.environ.get("LOCALAPPDATA", ".")) / "BAXY" / "renew" / self.log_name

    def _headers(self) -> dict[str, str]:
        """What every request to the server carries: its body's type and the server's key (PRV1, PRIV-04)."""
        return {"Content-Type": "application/json", **authorization(self.key)}

    def _get(self, path: str) -> urllib.request.Request:
        return urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", headers=authorization(self.key))

    def _wait_health(self) -> None:
        deadline = time.monotonic() + 600
        while time.monotonic() < deadline:
            if self._process is not None and self._process.poll() is not None:
                # Uso-125: the VRAM counted free went to something else, or the driver cannot run the projector: a
                # slower vision, not a BAXY that does not start.
                if self._placement == ["--mmproj-offload"]:
                    self._launch(["--no-mmproj-offload"])
                    continue
                self._failure = f"llama-server exited with {self._process.returncode}"
                return
            try:
                with urllib.request.urlopen(self._get("/health"), timeout=2) as reply:
                    if reply.status == 200:
                        self._failure = self._slot_missing()
                        if self._failure is None:
                            self._ready.set()
                        return
            except Exception:  # noqa: BLE001 - still loading
                time.sleep(0.3)
        self._failure = "llama-server did not become healthy"

    def _slot_missing(self) -> str | None:
        """Why a shared server cannot give this mind its slot (BAXY_MIND_SLOT), or None. llama-server takes a slot
        number modulo its slots (get_slot_by_id, server-context.cpp:1663 at b11609): one past them would be another
        mind's slot, in silence."""
        if not self.slot:
            return None
        with urllib.request.urlopen(self._get("/props"), timeout=10) as reply:
            total = int(json.loads(reply.read()).get("total_slots") or 1)
        return None if self.slot < total else f"BAXY_MIND_SLOT {self.slot}: the server has {total} slots (-np)"

    def wait_ready(self, timeout: float) -> None:
        deadline = time.monotonic() + timeout
        while not self._ready.wait(0.25):
            if self._failure is not None or time.monotonic() > deadline:
                raise RuntimeError(self._failure or "llama-server is not ready")

    def startup_failure(self, error: BaseException | None = None) -> dict[str, Any]:
        """The App's startup-failure shape (MindStartupFailure): why the model did not come up. A server that exited is
        «proceso_salio» unless its log says it ran out of memory (memory_failure); ``error``, what the start raised in
        the mind, is the PC's memory when it is a MemoryError (uso 95). A lack of memory goes with its figures where they
        are known (uso-116): needMb, the buffer that did not fit; freeMb, the PC's RAM free. The graphics card's free
        memory is not said: llama-server does not log it with the layers set by hand (b11609). A prefix this machine
        reads too slowly is «lectura_lenta» (N9): tokensPerS, its pace; needMinutes, what the whole of it would take."""
        code = self._process.poll() if self._process is not None else None
        log = self._log_tail()
        cause = memory_failure(log)
        # A server that said it ran out of memory may not have ended yet when the mind asks (uso-116: «tiempo»).
        if code is not None or cause:
            failure: dict[str, Any] = {"cause": cause or model_file_failure(log) or "proceso_salio"}
            if code is not None:
                failure["exitCode"] = code
            need = buffer_size_mb(log) if cause else None
            if need is not None:
                failure["needMb"] = need
                free = free_memory_mb() if cause == "ram_insuficiente" else None
                if free is not None:
                    failure["freeMb"] = free
            return failure
        if isinstance(error, MemoryError):
            return {"cause": "ram_insuficiente"}
        if isinstance(error, ReadTooSlow):
            return {"cause": "lectura_lenta", "tokensPerS": error.tokens_per_s,
                    "needMinutes": math.ceil(error.need_s / 60)}
        return {"cause": "tiempo"}

    def _log_tail(self) -> str:
        """The end of this run's server log, where an exit's cause is written last; empty when it cannot be read."""
        try:
            with open(self._log_path(), "rb") as log:
                log.seek(0, os.SEEK_END)
                log.seek(max(0, log.tell() - _LOG_TAIL_BYTES))
                return log.read().decode("utf-8", errors="replace")
        except OSError:
            return ""

    def _alive(self) -> None:
        """The model server died: the sidecar exits, so the App sees the mind close and relaunches it. Before every call
        to it (review 2026-10-22: only chat() checked, and the history's tokenize raised URLError first, so the mind
        stayed up without its model and was never relaunched)."""
        if self._process is not None and self._process.poll() is not None:
            os._exit(70)

    def _read_device(self) -> None:
        self.on_processor = computes_on_processor(self.server, self.backend, self.gpu_layers)

    def _within(self, timeout: float) -> float:
        """A call's timeout within the request's budget (REQUEST_SECONDS); spent, the request ends (TimeoutError)."""
        self._alive()
        if self.deadline is None:
            return timeout
        left = self.deadline - time.monotonic()
        if left <= 0:
            raise TimeoutError("the request's time budget is spent")
        return min(timeout, left)

    def chat(self, body: dict[str, Any], *, timeout: float = max(120.0, REQUEST_SECONDS),
             on_text: Callable[[str | None, bool], bool] | None = None, gives_way: bool = False) -> dict[str, Any]:
        """One chat completion on the one slot, whose prefix stays cached between turns. With ``on_text`` it streams
        (_stream) and returns the same reply, unless it asks for token probabilities (below). How long it took stays in
        ``took_s``: a server that says no timings (the translator) is weighed by it (Mind._next, a notice's budget).
        ``gives_way``: a chat nobody waits for (a closed conversation's name), ended as a read ahead is (_aside)."""
        began = time.perf_counter()
        reply = self._chat(body, timeout, on_text, gives_way)
        self.took_s = time.perf_counter() - began
        return reply

    def _chat(self, body: dict[str, Any], timeout: float, on_text: Callable[[str | None, bool], bool] | None,
              gives_way: bool = False) -> dict[str, Any]:
        self.wait_ready(self._within(timeout))
        self.resident = None
        if gives_way:
            request = urllib.request.Request(
                f"http://127.0.0.1:{self.port}/v1/chat/completions",
                data=json.dumps({**body, "id_slot": self.slot, "cache_prompt": True}).encode("utf-8"),
                headers=self._headers(),
            )
            with self._open(request, timeout, self._aside) as reply:
                return json.loads(reply.read())
        # Only a request someone waits for (``advanced``) lasts while the server advances, and not a call with a time of
        # its own, shorter than the request's (a notice).
        patient = self.advanced is not None and timeout > self.REQUEST_SECONDS
        # The doubt (doubt.read) reads every token's logprobs. Streamed, b11609 sends a token's logprobs only on a
        # chunk whose parse adds a difference (server-task.cpp:1136-1145; the first token's always, with the role):
        # the tokens of «<tool_call>», «<function=» and a name being parsed, and text the partial parser holds back,
        # add none, and their probabilities are never sent. A call that asks for them is not streamed.
        if on_text is not None and not body.get("logprobs"):
            try:
                return self._stream(body, timeout, on_text, self._waited() if patient else None)
            except _StreamBroken:
                # A stream can fail where the same request does not: compute_diffs throws when a partial parse saw a
                # call the final parse does not (common/chat.cpp:255-267; a malformed call the non-streamed reply
                # returns as text). Asked again without streaming, on the same budget: the same answer (fixed seed).
                _tell(on_text, None, True)
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/v1/chat/completions",
            data=json.dumps({**body, "id_slot": self.slot, "cache_prompt": True}).encode("utf-8"),
            headers=self._headers(),
        )
        with self._open(request, timeout, self._answer if patient else None) as reply:
            return json.loads(reply.read())

    def _waited(self) -> _Advance:
        """The watch of a turn's stream: its window (REQUEST_SECONDS) from each advance, within the request's ceiling. Not
        paced (_Advance): ReadTooSlow is the prefix's alone."""
        return _Advance(self.REQUEST_SECONDS, self.ceiling_s, None, self._advance, paced=False)

    def _answer(self, request: urllib.request.Request, timeout: float) -> Any:
        """The reply to a chat that does not stream, which says nothing until it ends: waited for while the server
        advances (_look), and its connection closed when the request's budget is spent, as a timeout does. It raises
        what ``urlopen`` raises for an error status, which the mind reads (a context overflow's 400, a 5xx)."""
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=self.REQUEST_SECONDS)
        try:
            connection.request("POST", request.selector, request.data, {**request.headers, "Connection": "close"})
            seen = None
            look = time.monotonic() + self.SLOTS_EVERY_S
            while not select.select([connection.sock], [], [], 0.05)[0]:
                self._within(timeout)
                if time.monotonic() >= look:
                    seen = self._look(seen)
                    look = time.monotonic() + self.SLOTS_EVERY_S
            response = connection.getresponse()
        except BaseException:
            connection.close()
            raise
        if response.status >= 400:
            raise urllib.error.HTTPError(request.full_url, response.status, response.reason, response.headers, response)
        return response

    def _aside(self, request: urllib.request.Request, timeout: float) -> Any:
        """The reply to a chat nobody waits for. Revisión total (M5, 2026-11-09): a closed conversation's name was asked
        on the request loop with up to TITLE_SECONDS of its own, and only looked at whether a request waited before it
        began; on a GPU that takes 20-60 s a turn (RX 7600 on Vulkan, AMD2) the first turn of the new conversation waited
        behind it. It gives way as a read ahead does (prefill): not sent with a request already waiting (``yields``), and
        its connection closed as soon as one waits, so llama-server cancels the task and the slot is the request's (at
        b11609 a reply that is not streamed is waited for with the connection's own «closed» as its stop, and a stop
        cancels the task: server-context.cpp:4874, server-http.cpp:685, server-queue.cpp:548-617). It raises Yielded
        then, and what ``urlopen`` raises for an error status, as _answer does."""
        if self.yields():
            raise Yielded("a request waits")
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=timeout)
        try:
            connection.request("POST", request.selector, request.data, {**request.headers, "Connection": "close"})
            until = time.monotonic() + timeout
            while not select.select([connection.sock], [], [], 0.05)[0]:
                if self.yields():
                    raise Yielded("a request waits")
                if time.monotonic() > until:
                    raise TimeoutError("the chat's time is spent")
            response = connection.getresponse()
        except BaseException:
            connection.close()
            raise
        if response.status >= 400:
            raise urllib.error.HTTPError(request.full_url, response.status, response.reason, response.headers, response)
        return response

    def _connect(self, request: urllib.request.Request, timeout: float,
                 connected: list[socket.socket]) -> http.client.HTTPResponse:
        """``request`` on a connection of its own, its socket kept in ``connected`` so that each read of the reply is given
        its own time (_stream). It raises what ``urlopen`` raises for an error status, as _answer does."""
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=timeout)
        try:
            connection.request("POST", request.selector, request.data, {**request.headers, "Connection": "close"})
            connected[:] = [connection.sock]
            response = connection.getresponse()
        except BaseException:
            connection.close()
            raise
        if response.status >= 400:
            raise urllib.error.HTTPError(request.full_url, response.status, response.reason, response.headers, response)
        return response

    def _look(self, seen: tuple | None) -> tuple | None:
        """This slot's count of what it has read and written, from /slots: a change from ``seen`` is an advance. At b11609
        n_prompt_tokens grows as each batch starts and n_decoded with each token written (server-context.cpp:746-755), and
        /slots is answered during a decode (server-context.cpp:4183-4189, yield_to_queue; process_single_task,
        server-context.cpp:2732), so a decode that never ends is told from one that goes on. No answer is no advance."""
        try:
            with urllib.request.urlopen(self._get("/slots"), timeout=self.SLOTS_LOOK_S) as reply:
                slots = json.loads(reply.read())
            slot = next(slot for slot in slots if slot.get("id") == self.slot)
            state = (slot.get("id_task"), slot.get("n_prompt_tokens"), slot["next_token"][0].get("n_decoded"))
        except (OSError, ValueError, http.client.HTTPException, AttributeError, KeyError, IndexError, StopIteration,
                TypeError):
            return seen
        if seen is not None and state != seen:
            self._advance()
        return state

    def read_prefix(self, body: dict[str, Any],
                    on_progress: Callable[[int, int], None] | None = None) -> dict[str, Any]:
        """The warm-up's chat (Mind.warm), its reply as chat's: streamed with the server's progress through the prompt,
        each advance told to ``on_progress`` (tokens read so far, the prompt's tokens), and waited for while it advances
        (_Advance, PREFIX_STALL_S and PREFIX_CEILING_S). A server that stops advancing ends it with a TimeoutError: a
        silent one at the socket's own timeout, one that only sends its SSE pings (every 30 s by default,
        sse_ping_interval, server-task.h:58 at b11609) at the stall."""
        self.wait_ready(self._within(self.PREFIX_STALL_S))
        self.resident = None
        if not self.remote:
            threading.Thread(target=self._read_device, daemon=True).start()

        def advanced(done: int, total: int) -> None:
            self.prefix_left = watch.seconds_left
            if on_progress is not None:
                on_progress(done, total)

        watch = _Advance(self.PREFIX_STALL_S, self.PREFIX_CEILING_S, advanced)
        return self._stream(body, self.PREFIX_STALL_S, lambda _text, _done: True, watch)

    def _open(self, request: urllib.request.Request, timeout: float, send: Callable[..., Any] | None = None) -> Any:
        """``urlopen`` of one request to the server (or ``send``'s), asked again after a 5xx (SERVER_ERROR_RETRIES), each
        try and each pause within the request's budget (_within). Any other failure, or a 5xx past the retries, is raised."""
        send = send or urllib.request.urlopen
        for attempt in range(self.SERVER_ERROR_RETRIES):
            try:
                return send(request, timeout=self._within(timeout))
            except urllib.error.HTTPError as error:
                if not 500 <= error.code < 600:
                    raise
                error.close()
                time.sleep(self._within(self.SERVER_ERROR_PAUSE_S * 2 ** attempt))
        return send(request, timeout=self._within(timeout))

    def _stream(self, body: dict[str, Any], timeout: float,
                on_text: Callable[[str | None, bool], bool],
                watch: _Advance | None = None) -> dict[str, Any]:
        """Al máximo 9.4 (2026-10-22): the chat streamed (SSE) and its reply built as the non-streamed one is
        (common_chat_msg::to_json_oaicompat, common/chat.cpp:156-235; to_json_oaicompat_chat, server-task.cpp:410-452):
        choices[0] with finish_reason, index and the message (role, content, reasoning_content, tool_calls), usage and
        timings. While the answer is words, its text so far goes to ``on_text`` after each delta (and once more, done,
        at the end) until it returns True; once a call starts (or the words are a call written as text), ``on_text``
        gets None, done: what it foresaw is dropped.

        At b11609 streaming only changes how the result is sent: sampling is the same (server-context.cpp:2020,
        send_partial_response after the same add_token), the final message is parsed from the same accumulated text
        (common_chat_session feed/finish, common/chat.cpp:1740-1759; server-task.h:408-410), and the deltas are its
        successive differences (compute_diffs, common/chat.cpp:236-299; server_chat_msg_diff_to_json_oaicompat,
        server-chat.cpp:621-649): content and arguments as suffixes (string_diff, chat.cpp:58-71), a call's id and name
        whole whenever they change (a name that grows comes whole again). The last chunk carries the timings and, with
        include_usage, the usage (server-task.cpp:454-509). An error before the first token still comes as an HTTP
        error (a context overflow's 400, server-context.cpp:4902-4914); one later is _StreamBroken.

        With ``watch`` the server also streams its progress through the prompt (return_progress, read_prefix and chat), and
        ``watch`` sees every line: each data chunk, and None for any other line (the SSE pings it sends while silent).
        For a turn (``advanced``) each line is waited for only what is left of the request's budget, which each advance
        gives its window again (revisión PCR1, A3: with a whole window per line the mind could give up 24 s past its
        ceiling, after the App)."""
        progress = {"return_progress": True} if watch is not None else {}
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/v1/chat/completions",
            data=json.dumps({**body, "stream": True, "stream_options": {"include_usage": True}, **progress,
                             "id_slot": self.slot, "cache_prompt": True}).encode("utf-8"),
            headers=self._headers(),
        )
        content, reasoning = "", ""
        calls: dict[int, dict[str, Any]] = {}
        head: dict[str, Any] = {}
        finish: Any = None
        index = 0
        telling = True
        window = watch.stall if watch is not None and self.advanced is not None else None
        connected: list[socket.socket] = []
        send = None if window is None else lambda asked, timeout: self._connect(asked, window, connected)
        with self._open(request, timeout, send) as reply:
            try:
                while True:
                    if connected:
                        connected[0].settimeout(self._within(window))
                    raw = reply.readline()
                    if not raw:
                        break
                    line = raw.decode("utf-8").strip()
                    if not line.startswith("data:"):
                        if watch is not None:
                            watch(None)
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    chunk = json.loads(data)
                    if "error" in chunk:
                        raise _StreamBroken(str(chunk["error"]))
                    if watch is not None:
                        watch(chunk)
                    head.update({key: chunk[key] for key in ("created", "id", "model", "system_fingerprint", "usage",
                                                             "timings") if key in chunk})
                    for choice in chunk.get("choices") or []:
                        index = choice.get("index", index)
                        finish = choice.get("finish_reason") or finish
                        delta = choice.get("delta") or {}
                        reasoning += delta.get("reasoning_content") or ""
                        for call in delta.get("tool_calls") or []:
                            held = calls.setdefault(int(call.get("index") or 0),
                                                    {"type": "function", "function": {"name": "", "arguments": ""}})
                            function = call.get("function") or {}
                            if call.get("id"):
                                held["id"] = call["id"]
                            if function.get("name"):
                                held["function"]["name"] = function["name"]
                            held["function"]["arguments"] += function.get("arguments") or ""
                            if telling:
                                _tell(on_text, None, True)  # a call: what was foreseen is dropped, nothing more told
                                telling = False
                        if delta.get("content"):
                            content += delta["content"]
                            if telling and ("<tool_call>" in content or "<function=" in content):
                                _tell(on_text, None, True)  # a call written as text: dropped as well
                                telling = False
                            elif telling:
                                telling = not _tell(on_text, content, False)
                    self._within(timeout)  # the request's budget holds while the answer is written
            except (ValueError, http.client.HTTPException, ConnectionError) as error:
                raise _StreamBroken(repr(error)) from error
        if telling:
            _tell(on_text, content, True)
        message: dict[str, Any] = {"role": "assistant", "content": content}
        if reasoning:
            message["reasoning_content"] = reasoning
        if calls:
            message["tool_calls"] = [calls[key] for key in sorted(calls)]
        return {"choices": [{"finish_reason": finish or "length", "index": index, "message": message}],
                **{key: head[key] for key in ("created", "id", "model", "system_fingerprint") if key in head},
                "object": "chat.completion", **{key: head[key] for key in ("usage", "timings") if key in head}}

    def template(self, body: dict[str, Any], timeout: float = 10.0) -> str:
        """The chat's own prompt as the server renders it (/apply-template). Al máximo V3 (2026-10-22): once per
        decision, for all of its rivals (complete_name); each rival rendered the whole prompt again (decisions with
        System One took 1.5-2.75 s against 1.1-1.4 s)."""
        self.wait_ready(self._within(timeout))
        return self._post("/apply-template", {k: body[k] for k in ("messages", "tools", "chat_template_kwargs")},
                          timeout)["prompt"]

    def complete_name(self, prompt: str, written: str, timeout: float = 10.0) -> str:
        """The rest of a tool name the model would write after `written` (its call so far), greedy, on the same slot:
        the chat's own prompt (template) plus that text, stopped at the name's end."""
        self.resident = None
        reply = self._post("/completion", {"prompt": prompt + written, "n_predict": 24, "temperature": 0.0,
                                           "stop": [">", "\n"], "cache_prompt": True, "id_slot": self.slot}, timeout)
        return str(reply.get("content", ""))

    def prefill(self, prompt: str, timeout: float = 60.0) -> dict[str, Any]:
        """``prompt`` (a chat's own text, as /apply-template renders it) read into the slot with nothing written: one
        token to predict, sampled and never decoded, so the slot then holds exactly the prompt's tokens (the warm-up's
        max_tokens 1 left n_tokens equal to its prompt's, llama-server.log). Tokenized as the chat's own prompt is
        (special tokens parsed, no BOS for this model). The text the slot already holds (``resident``) is not sent
        again: its reply then has no timings and says ``resident``.

        It gives way to any request that waits (``yields``; NB-R1, sesión larga en vivo 2026-10-27: one the server was
        slow to read, with the CPU at 90 %, ran out its 24 s budget while the person's turn waited behind it): it is not
        sent, or its connection closes as soon as one waits, so llama-server drops the task, and it raises Yielded."""
        self.wait_ready(self._within(timeout))
        if prompt == self.resident:
            return {"resident": True}
        self.resident = None
        if self.yields():
            raise Yielded("a request waits")
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=self._within(timeout))
        try:
            connection.request("POST", "/completion", json.dumps(
                {"prompt": prompt, "n_predict": 1, "temperature": 0.0, "cache_prompt": True,
                 "id_slot": self.slot}).encode("utf-8"), self._headers())
            until = time.monotonic() + self._within(timeout)
            while not select.select([connection.sock], [], [], 0.05)[0]:
                if self.yields():
                    raise Yielded("a request waits")
                if time.monotonic() > until:
                    raise TimeoutError("the read ahead's time is spent")
            response = connection.getresponse()
            if response.status != 200:
                raise http.client.HTTPException(f"/completion answered {response.status}")
            reply = json.loads(response.read())
        finally:
            connection.close()
        self.resident = prompt
        return reply

    def fill_call(self, body: dict[str, Any], wire: str, timeout: float = 30.0) -> dict[str, Any] | None:
        """The model's arguments for one tool another layer chose (System One, piece A): the same chat, with the call
        already started as the assistant's last message, so the prompt and its cached prefix stay the same and only the
        arguments are written. tool_choice «required» keeps the call grammar active from that prefix on, inside this
        tool's own parameters (llama.cpp b11609: common/sampling.cpp, common/chat.cpp, common/parsers/qwen3-coder.cpp).
        Returns the parsed call {"name", "arguments"} or None. Auditoría de la mente (w8): not the decision's token
        probabilities (logprobs, top_logprobs 10), which nothing reads of a fill; the server sorted the vocabulary at
        every argument token for them (al máximo 9.5's cost, −20 to −100 ms expected); greedy, the same arguments."""
        messages = [*body["messages"], {"role": "assistant", "content": f"<tool_call>\n<function={wire}>\n"}]
        request = {**{k: v for k, v in body.items()
                      if k not in ("logit_bias", "tool_choice", "max_tokens", "logprobs", "top_logprobs")},
                   "messages": messages, "tool_choice": "required", "parallel_tool_calls": False,
                   "continue_final_message": True, "add_generation_prompt": False, "max_tokens": 300,
                   "temperature": 0.0, "id_slot": self.slot, "cache_prompt": True}
        self.resident = None
        reply = self._post("/v1/chat/completions", request, timeout)
        calls = (reply.get("choices") or [{}])[0].get("message", {}).get("tool_calls") or []
        if not calls:
            return None
        call = calls[0].get("function") or {}
        try:
            arguments = json.loads(call.get("arguments") or "{}")
        except json.JSONDecodeError:
            return None
        return {"name": call.get("name"), "arguments": arguments if isinstance(arguments, dict) else {},
                "timings": reply.get("timings") or {}}

    def _post(self, path: str, body: dict[str, Any], timeout: float) -> dict[str, Any]:
        request = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=json.dumps(body).encode("utf-8"),
                                         headers=self._headers())
        with self._open(request, timeout) as reply:
            return json.loads(reply.read())

    def tokenize(self, text: str) -> list[int]:
        """The model's tokens for a text, special tokens included (<tool_call> is one)."""
        self.wait_ready(self._within(600))
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/tokenize",
            data=json.dumps({"content": text, "parse_special": True}).encode("utf-8"),
            headers=self._headers(),
        )
        with self._open(request, 30) as reply:
            return list(json.loads(reply.read())["tokens"])

    # ---- the prompt prefix kept between starts (al máximo V1) -------------------------------------------------------
    # Every start re-read the tools and the system prompt (~44,600 tokens, 18.3 s in llama-server.log) and the App was
    # ready at ~22-23 s. The slot's state after the warm-up is saved with the server's own slot save (the vision's:
    # 42,910 tokens restored in 0.74 s) under a key of everything that makes that state; the next start restores it.

    def prefix_key(self, warm: Any) -> str:
        """The key of the slot's state after the warm-up: the requests that make it (``warm``: the tools, the installed
        applications among them, and the system prompt), the server's arguments but its address (context, KV cache
        types, projector…), the GGUF and the server binary (size and time: hashing 2.7 GB costs what is saved), the GGUF's
        SHA-256 the App verified (BAXY_MIND_LLM_GGUF_SHA256: the stock and the tuned model differ by 448 bytes and share
        every shape, QWB2) and the server's build as it tells it. With a remote server (BAXY_MIND_LLAMA_REMOTE) the GGUF and the binary here are
        not the ones it runs: the model it serves and its slot's context, as its /props tells them, are in the key too."""
        self.wait_ready(self._within(600))
        try:
            with urllib.request.urlopen(self._get("/props"), timeout=self._within(10)) as reply:
                props = json.loads(reply.read())
        except (OSError, ValueError, http.client.HTTPException):
            props = {}
        props = props if isinstance(props, dict) else {}
        identity = {"settings": self._settings, "gguf": _stamp(self.gguf), "server": _stamp(self.server),
                    "gguf_sha256": os.environ.get("BAXY_MIND_LLM_GGUF_SHA256", "").strip(),
                    "build": str(props.get("build_info") or ""), "warm": warm}
        if self.remote:
            served = props.get("default_generation_settings")
            identity["served"] = {"model": props.get("model_path"),
                                  "n_ctx": served.get("n_ctx") if isinstance(served, dict) else None}
        return hashlib.sha256(json.dumps(identity, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:32]

    def restore_prefix(self, key: str) -> dict[str, Any] | None:
        """The slot back to the state saved under ``key``, and the facts kept beside it; None when there is none or the
        server could not restore it (the warm-up then runs as always).

        Encargo 27 (flota 03-11): a remote server (BAXY_MIND_LLAMA_REMOTE) writes the state in its own --slot-save-path,
        on the other machine, and only the facts are in this folder: its restore is asked for without the file here
        (POST /slots/{id}?action=restore takes a name in that folder; a missing one is an error, and the warm-up then
        saves it there again). llama-server checks the file's shape, not that it holds this prefix
        (llama_state_seq_load_file, server-context.cpp:2957-3000 at b11609): the name is the key, which with a remote
        server names the model it serves (prefix_key), and the tokens restored must be the ones saved (SLOT_TOKENS);
        another count is another state, which is erased from the slot."""
        state = self.slot_dir / f"{PREFIX}{key}.slot"
        try:
            facts = json.loads(state.with_suffix(".json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if not isinstance(facts, dict):
            return None
        saved = facts.pop(SLOT_TOKENS, None)
        if not (state.is_file() or (self.remote and isinstance(saved, int) and saved > 0)):
            return None
        self.resident = None
        try:
            reply = self._post(f"/slots/{self.slot}?action=restore", {"filename": state.name}, 120)
        except (OSError, ValueError, http.client.HTTPException):
            return None
        restored = int(reply.get("n_restored") or 0)
        if self.remote and restored > 0 and restored != saved:
            try:
                self._post(f"/slots/{self.slot}?action=erase", {}, 30)
            except (OSError, ValueError, http.client.HTTPException):
                pass  # the warm-up's prompt then differs from what the slot holds, and is read where it differs
            return None
        if restored <= 0:
            return None
        try:
            os.utime(state.with_suffix(".json"))  # the state used last: save_prefix keeps it (P0.9)
        except OSError:
            pass  # held this moment: the state was restored all the same
        return facts

    def save_prefix(self, key: str, facts: dict[str, Any]) -> bool:
        """The slot's state saved under ``key`` with ``facts`` beside it, and the state of one other key: the one saved
        or restored last; every other is removed (each is ~1 GB). Only the prefix may be in the slot: Mind.warm saves
        it before any turn. P0.9 (feria, 2026-10-27): with every other state removed, one start whose prefix had
        another key (its tools from a catalog that came late) cost the next usual start the whole prefix too (~30 s)."""
        state = self.slot_dir / f"{PREFIX}{key}.slot"
        kept = state.with_suffix(".json")
        # Saving only spares the next start the warm-up: a file of the folder another process holds this moment (a
        # scan of the state just written) never fails the warm-up itself (it was told to the App as a model that did
        # not start).
        try:
            kept.unlink(missing_ok=True)  # the facts are written last: a state cut halfway is never restored
            reply = self._post(f"/slots/{self.slot}?action=save", {"filename": state.name}, 120)
            tokens = int(reply.get("n_saved") or 0)
            saved = tokens > 0
            if saved:
                kept.write_text(json.dumps({**facts, SLOT_TOKENS: tokens}, ensure_ascii=False), encoding="utf-8")
        except (OSError, ValueError, http.client.HTTPException):
            saved = False
        keep = {state.name, kept.name} if saved else set()
        earlier = [other for other in self.slot_dir.glob(f"{PREFIX}*.json")
                   if other.name != kept.name and other.with_suffix(".slot").is_file()]
        if earlier:
            last = max(earlier, key=lambda other: (_stamp(str(other)) or [0, 0])[1])
            keep |= {last.name, last.with_suffix(".slot").name}
        for stale in self.slot_dir.glob(f"{PREFIX}*"):
            if stale.name not in keep:
                try:
                    stale.unlink(missing_ok=True)
                except OSError:
                    pass  # held this moment: the next save removes it
        return saved

    def forget_set_aside(self) -> bool:
        """Every slot state a vision question set aside (*.bin, which holds the person's conversation) is removed; the
        kept prefix (PREFIX, saved before any turn) stays. Whether none is left. At start, and when the person had BAXY
        forget everything or deleted every conversation (trace.forget): a question under way then loses its state and
        the next decision reads the conversation again."""
        left = False
        for stale in self.slot_dir.glob("*.bin"):
            try:
                stale.unlink(missing_ok=True)
            except OSError:
                left = True  # held by the server this moment
        return not left

    def forget_log(self) -> bool:
        """The last run's log (.1, kept at start), whose errors may quote the model's words, is removed on trace.forget;
        the running server's own log stays (its handle is open). Whether it is gone."""
        try:
            self._log_path().with_name(self.log_name + ".1").unlink(missing_ok=True)
        except OSError:
            return False
        return True

    def close(self) -> None:
        if self._process is not None and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(5)
            except subprocess.TimeoutExpired:
                self._process.kill()


# The kept prefix's files in the slot folder: its state (.slot, never *.bin: start() removes those) and its facts (.json).
PREFIX = "baxy_prefix_"
# Beside the facts: the tokens the server saved in the state (its n_saved), which a restore must give back (n_restored).
SLOT_TOKENS = "slot_tokens"

# w6-lat (2026-10-23): the KV cache's types, an option for an A/B over the default (q8_0 for K and V on every backend,
# see kv_types). BAXY_RENEW_KV is one type for both («q4_0») or «K,V» («q8_0,q4_0»).
# Qwen3.5-4B keeps K and V only in its 8 full-attention layers of 32 (4 KV heads × 256): 17 KiB per cell at q8_0, 9 at
# q4_0. uso-51 (2026-11-03, measured on the PC, INFORME_51.md): q4_0 reads and writes as fast as q8_0 and decided the
# same 30 practice cases with a 22k-token history (28 identical), but the decision gate (encargo 50) lost the close
# calls of «sin_cliente» with it: 11 of 25 right against 16 of q8_0, the same code, catalog and seeds, at 53,248 cells as
# at 86,016 (U33 5/5 → 0/5). llama.cpp measures K at 4 bits moving the output most (PR #7412: KL divergence 0.0365 for
# q4_0 K and V, 0.0010 for q8_0). So q8_0 stays. A mixed «q8_0,q4_0» cache has no fast kernel in this CUDA build
# (decode 27 → 15 tokens/s, with another load on the GPU).
KV_TYPES = ("f16", "q8_0", "q5_1", "q5_0", "q4_1", "q4_0")


# Encargo 8 (2026-11-02): on Vulkan (AMD and Intel GPUs) with 8 GB the KV cache was f16 with flash attention «auto»,
# because the q8_0 cache read the prefix 24 times slower than CUDA on an RX 7600. Two causes in ggml-vulkan.cpp at b11609:
# (1) «-fa on» forces flash attention, and a device that cannot run it (supports_op, FLASH_ATTN_EXT: no coopmat2 nor
# subgroup shuffle and vote) runs it on the CPU in silence; «auto» lets llama.cpp check it (llama-context.cpp
# resolve_fused_ops), which it can only do with an unquantized V (a quantized V forces it on, llama-context.cpp:4063);
# (2) a quantized K and V are dequantized inside the flash-attention shader for every block of queries on the paths AMD
# gets (scalar or coopmat1). uso-60 (2026-11-03, measured on that RX 7600 with -np 3 -kvu, INFORME_60.md): the f16 cache
# reads the history past the prefix at 527 tokens/s and q8_0 at 174, both decode at ~27, but the f16 one takes 4,460 MiB
# of the GPU at 53,248 cells, past the owner's 4 GB, and with the 48.8k-token prefix no f16 cache fits in them. So
# q8_0 on every backend (VULKAN_CONTEXT); f16 only when BAXY_RENEW_KV asks for it.


def kv_types(setting: str) -> tuple[str, str]:
    """The KV cache's (K, V) types from BAXY_RENEW_KV's text: empty, q8_0 and q8_0; one type, both; «K,V», each. Any
    other text fails the start with its cause (RuntimeError, as a pinned port in use)."""
    parts = [part.strip().lower() for part in setting.split(",")] if setting.strip() else ["q8_0"]
    if len(parts) == 1:
        parts *= 2
    if len(parts) != 2 or any(part not in KV_TYPES for part in parts):
        raise RuntimeError(f"BAXY_RENEW_KV {setting!r}: one of {', '.join(KV_TYPES)}, or two of them as «K,V»")
    return parts[0], parts[1]


def flash_attention(backend: str, kv: tuple[str, str]) -> str:
    """llama-server's «-fa»: «auto» on Vulkan with an f16 V, so llama.cpp checks the GPU runs the attention (kv_types);
    «on» otherwise (a quantized V needs it, and CUDA was measured so)."""
    return "auto" if backend == "vulkan" and kv[1] == "f16" else "on"


# uso-51 (2026-11-03, «aumentar el contexto»; the owner's budget: 4 GB of VRAM for all of BAXY, 4-5 GB of RAM): the
# prefix grew to 48,541 tokens (catalog of 2026-11-03), so 53,248 cells left the history ~1.1k tokens beside the turn.
# Measured on the PC (RTX 4060 Ti, b11609, this GGUF, the product's arguments; ft_v1/c5/INFORME_51.md): the server's
# dedicated memory is 4,000 MiB at 53,248 cells with q8_0; each cell more costs ~22 KiB with q8_0 and ~14 with q4_0
# (the cache, and ~4 KiB of compute buffer: flash attention reads a quantized cache through an f16 copy of one layer's K
# and V). The most cells inside 4 GB (4,096 MiB) for all of BAXY, the App's WebView2 included (~34 MiB of the GPU, as
# another WebView2 measured here), by cache and by where the output matrix is:
CUDA_CONTEXT = {("q8_0", True): 77824,    # 4,032 MiB: the default
                ("q8_0", False): 53248,   # 4,000 MiB with BAXY_RENEW_OUTPUT_CPU=0, as before
                ("q4_0", True): 122880,   # 4,040 MiB with BAXY_RENEW_KV=q4_0 (see KV_TYPES: not the default)
                ("q4_0", False): 86016}   # 4,032 MiB
# Qwen3.5-4B ties its output to the token embedding (token_embd.weight, Q6_K, 497 MiB): the input's copy is in RAM
# already, the output's was on the GPU. Kept on the CPU (llama.cpp's -ot/--override-tensor) it frees 496 MiB for 24k
# more cells: the RAM did not grow and the prompt reads as fast (prefix ~2,200-2,400 and history ~1,430 tokens/s), but
# each written token costs ~9 ms more (47 → 33 tokens/s at 70k with the GPU alone; the server had 8 logical processors).
# The decision gate stayed as with the output on the GPU (INFORME_51.md). The CPU keeps 53,248: not measured.
CONTEXT = 53248
OUTPUT_ON_CPU = r"token_embd\.weight=CPU"
# uso-60 (2026-11-03, measured on an RX 7600 8 GB, b11609 Vulkan, -np 3 -kvu, this GGUF; ft_v1/c5/INFORME_60.md): llama.cpp
# counts 2,604 MiB of weights, 151 of recurrent state (three slots) and ~140 of compute on the GPU, and 17 KiB per q8_0
# cell. 61,440 cells take 3,916 MiB (3,830 seen by Windows with 53.7k of them in use), 9.1k tokens of history beside the
# prefix and the turn. A q8_0 cache past 1 GiB (62,464 cells or more) runs ~4 times slower here (the prompt read 1,054 →
# 258 tokens/s and the decode 32 → 18, the GPU's dedicated memory falling as the shared one grows): the cause inside
# ggml-vulkan is not isolated. The output matrix stays on the GPU (output_cpu): in RAM, as on CUDA, it read the prefix at
# 231 tokens/s against 901 and decoded at 13.5 against 27. An f16 cache keeps the 53,248 cells it had (4,460 MiB).
VULKAN_CONTEXT = {("q8_0", False): 61440,
                  ("f16", False): 53248}


def default_context(backend: str, kv: tuple[str, str], output_cpu: bool = False) -> int:
    """The server's context when BAXY_RENEW_CTX does not say it: on CUDA and Vulkan the cells measured to fit 4 GB with
    this cache (CUDA_CONTEXT, VULKAN_CONTEXT; with another cache, CONTEXT), CONTEXT on the CPU."""
    measured = {"cuda": CUDA_CONTEXT, "vulkan": VULKAN_CONTEXT}.get(backend, {})
    return measured.get((kv[0], output_cpu), CONTEXT) if kv[0] == kv[1] else CONTEXT


# uso-51: a cut keeps at most this many tokens of history (Mind._fits), which the model re-reads in the decision that cut
# it (from the prefix's checkpoint on), inside the decision's REQUEST_SECONDS with its own reading and writing. Measured on
# the PC (b11609, history past the 48.5k-token prefix, INFORME_51.md): ~1,440 tokens/s with the GPU to itself (~4.3 s),
# 500-660 with another model on it (~10-12 s); the notebook's re-reads ran 1.1-1.6k tokens/s. uso-60 (the RX 7600,
# INFORME_60.md): 527 tokens/s on Vulkan with f16 and 174 with a quantized K, where 6,144 tokens would take ~35 s: 2,048
# there (~12 s).
REREAD_TOKENS = 6144
REREAD_TOKENS_SLOW = 2048


def reread_tokens(backend: str, kv: tuple[str, str]) -> int:
    """The most history a cut may leave on this backend with this cache (REREAD_TOKENS)."""
    return REREAD_TOKENS_SLOW if backend == "vulkan" and kv[0] != "f16" else REREAD_TOKENS


def slots(backend: str) -> list[str]:
    """llama-server's slots: one (the mind's, slot 0), but three on one unified cache on Vulkan. Measured on an RX 7600
    (b11609, 2026-11-03, ft_v1/c5/AMD_TUKIPC_0311.md): with one or two slots the ~45k-token prefix read at 244 tokens/s
    and the decode ran at 21; with three or more, at 946 and 33, the same 22 decisions, for +76 MiB (each slot keeps
    its recurrent state); the cause inside ggml-vulkan is not isolated. With «-kvu» every slot sees the whole context
    (n_ctx_seq = n_ctx, llama-context.cpp), so slot 0 alone keeps all of it; on CUDA it read no faster here (INFORME_51)."""
    return ["-np", "3", "-kvu"] if backend == "vulkan" else ["-np", "1"]


def batch_size(backend: str) -> int:
    """The tokens llama-server reads between two of its progress reports: its batch (-b; 2,048 by default, README.md:52 at
    b11609), 1,024 on Vulkan (read_batch)."""
    return 1024 if backend == "vulkan" else 2048


def read_batch(backend: str) -> list[str]:
    """llama-server's batch (-b) where a batch may take as long as a request may go without an advance (REQUEST_SECONDS):
    the server tells its progress once per batch (server-context.cpp:4313 at b11609), and 2,048 tokens, its default, take
    24 s at 85 tokens/s, what an RX 7600 on Vulkan reads with BAXY running beside it: a request still reading was given up
    on. At 1,024 the same run's requests and replies came out byte for byte the same, token probabilities included, in the
    same time (5 turns on the RX 7600, 2026-11-05): a batch is cut in ubatches of 512 either way (-ub, llama_decode), and
    context checkpoints depend on the ubatch and the messages, not on it (server-context.cpp:4008-4020). 512 cost time
    (1,918 tokens: 18 to 24 s against 16 s). On CUDA a batch takes under 2 s; the CPU is not measured."""
    return ["-b", str(batch_size(backend))] if backend == "vulkan" else []


# VUL1 (2026-11-09): ggml-vulkan asks first for video memory the processor can also see (DEVICE_LOCAL | HOST_VISIBLE |
# HOST_COHERENT), and only then for plain video memory (ggml_vk_create_buffer_device, ggml-vulkan-buffers.cpp:219-249 at
# b11609). That type is the whole VRAM only with Resizable BAR; without it, it is a 256 MiB window, and what AMD's
# driver gives on Windows to a buffer asked from it is system memory, counted to the process as «shared»
# (ggml-org/llama.cpp#30888, an RX 6950 XT, 2026-10-20; #27097, an RX 7900 XTX, 2026-08). Measured in the product on an
# RX 7600 without it (AMD3, INFORME_AMD3.md §2 and §4, the product's line and model): 1,161 MiB shared from the load,
# the 46,176-token prefix read at 274 → 118 tokens/s, 522 s the first start and 6-18 s a turn; with this variable 1,182
# → 531 tokens/s, 63 s and 1-5 s, the same reply. On an RTX 4060 Ti without it, on Vulkan (NVIDIA's driver; VUL1, 13
# rounds in turn, INFORME_VUL1.md §2), the variable moved neither the read (1,894 and 1,922 tokens/s at 46k) nor the
# memory (4,899 + 167 MiB both ways). With Resizable BAR on it is not measured. The engine reads it as set or not,
# whatever its value (getenv != nullptr, ggml-vulkan.cpp:4015-4016), and not at all on an integrated GPU (the «uma»
# branch comes first). From b12236 it looks for Resizable BAR itself, card by card (ggml-org/llama.cpp#31658, merged
# 2026-11-06): the variable goes out in the change that brings that engine, where it would still force every card.
VULKAN_PLAIN_VIDEO_MEMORY = "GGML_VK_DISABLE_HOST_VISIBLE_VIDMEM"


def server_environment(key: str, backend: str, environ: dict[str, str] | None = None) -> dict[str, str]:
    """The environment a llama-server of BAXY starts with (LlmServer._launch, external_model.Engine): this process's,
    and its key; on Vulkan also VULKAN_PLAIN_VIDEO_MEMORY, unless the person's environment already has it: theirs is
    left as it is."""
    environment = {**(os.environ if environ is None else environ), "LLAMA_API_KEY": key}
    if backend == "vulkan":
        environment.setdefault(VULKAN_PLAIN_VIDEO_MEMORY, "1")
    return environment


def _vision_args() -> list[str]:
    """PLAN_GENERAL A5 (measured 2026-10-21): the model's own projector, so the click's last stage can ask this server
    where a control is on a window without an accessible tree; the one slot's state is set aside meanwhile in the slot
    folder (_slot_dir). A question on the slot evicted the conversation, whose state (2 GB) the RAM prompt cache refused,
    and the next decision re-read it for 25 s; a second slot on a unified KV cache lost it too with this hybrid model
    (21 s). Saved and restored around the question: 1.35 s and 0.74 s for 42,910 tokens, then 17 tokens re-read. Where
    it runs is apart (projector_placement): it changes nothing in the slot's state, so it is not in the prefix's key."""
    projector = os.environ.get("BAXY_MIND_MMPROJ", "").strip()
    if not projector or not Path(projector).is_file():
        return []
    return ["--mmproj", projector]


# Uso-125 (2026-11-05): measured on the PC (RTX 4060 Ti, b11609 CUDA, c4c2 and its
# projector, 3840x2160 shrunk to 1280: 952 tokens): the image read in 0.5-1.0 s on the GPU against 8.4-16 s on the
# CPU, the same description quality by a blind judge (ft_v1/c5/tanda100/uso-125-vision.md). The projector takes 920 MiB
# of VRAM beside the server's 4,032 and leaves ~720 MiB of RAM. llama.cpp keeps it loaded for the server's life (it
# cannot be held on the GPU only while reading), so it goes there only where the VRAM free when the server starts holds
# both, with a margin: the most the server's cells take (CUDA_CONTEXT, VULKAN_CONTEXT, 4,096 MiB), the projector and
# 300 MiB. A 4 GB card keeps it on the CPU; 6 GB and up take it.
VISION_GPU_NEEDS_MIB = 4096 + 920 + 300
_DEVICE_MEMORY = re.compile(r"\((\d+) MiB, (\d+) MiB free\)")


def _listed_devices(server: str) -> str | None:
    """What the server says with --list-devices, the same for CUDA and Vulkan, whatever the make; None when it cannot."""
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        return subprocess.run([server, "--list-devices"], capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=20, creationflags=flags).stdout
    except (OSError, subprocess.SubprocessError):
        return None


def _free_vram_mib(server: str) -> int | None:
    """The VRAM free on the device the server would use, as the server itself counts it; None when it does not say."""
    found = _DEVICE_MEMORY.search(_listed_devices(server) or "")
    return int(found.group(2)) if found else None


def computes_on_processor(server: str, backend: str, layers: str) -> bool | None:
    """N9 (L5): whether the model runs on the processor: a folder with no GPU backend or no layers on the GPU, or a
    server that lists no device («(none)»: a CUDA folder on a PC with no NVIDIA, which runs on the CPU in silence). None
    when it does not say."""
    if backend == "cpu" or layers.strip() == "0":
        return True
    listed = _listed_devices(server)
    if listed is None or "Available devices" not in listed:
        return None
    return _DEVICE_MEMORY.search(listed) is None


def progress_facts(server: LlmServer) -> dict[str, Any]:
    """What a progress line says beside its tokens (uso 84), each only when known: the seconds left and the processor."""
    facts: dict[str, Any] = {}
    if server.prefix_left is not None:
        facts["secondsLeft"] = server.prefix_left
    if server.on_processor is not None:
        facts["onProcessor"] = server.on_processor
    return facts


def projector_placement(server: str, backend: str) -> list[str]:
    """Where the projector reads an image: on the GPU when the VRAM really free holds it (see VISION_GPU_NEEDS_MIB), on
    the CPU otherwise, or with BAXY_VISION_OFFLOAD=0; nothing without a projector."""
    if not _vision_args():
        return []
    if backend == "cpu" or os.environ.get("BAXY_VISION_OFFLOAD", "").strip() == "0":
        return ["--no-mmproj-offload"]
    free = _free_vram_mib(server)
    return ["--mmproj-offload"] if free is not None and free >= vision_gpu_needs_mib() else ["--no-mmproj-offload"]


def vision_gpu_needs_mib() -> int:
    """The VRAM free the projector needs beside the server: what the App works out for the context the server starts with
    (BAXY_VISION_GPU_NEEDS_MIB, LocalContext from ModelMemory: the server's estimate, the projector's and the same 300 MiB),
    or with nothing given, VISION_GPU_NEEDS_MIB, the default context's."""
    given = os.environ.get("BAXY_VISION_GPU_NEEDS_MIB", "").strip()
    return int(given) if given.isdigit() and int(given) > 0 else VISION_GPU_NEEDS_MIB


def _slot_dir() -> Path:
    """The server's --slot-save-path: BAXY_VISION_SLOT_DIR, where the App's vision sets the slot's state aside, or the
    same folder the App gives it (MindRuntimeDiscovery) when the vision is off."""
    held = os.environ.get("BAXY_VISION_SLOT_DIR", "").strip()
    return Path(held) if held else Path(os.environ.get("LOCALAPPDATA", ".")) / "BAXY" / "renew" / "slots"


def _stamp(path: str) -> list[int] | None:
    """A file's size and modification time, or None when it is not there."""
    try:
        status = os.stat(path)
    except OSError:
        return None
    return [status.st_size, status.st_mtime_ns]


# The llama-server builds the mind may start, by the SHA-256 of their files (00_IDENTIDAD: no piece changes in silence).
BUILDS = Path(__file__).with_name("data") / "llama_server.v1.json"


def declared_build(server: str, builds: Path = BUILDS) -> str:
    """The name of the declared build (data/llama_server.v1.json) that ``server`` is: each file the declaration names,
    in the folder of the given llama-server.exe, with that build's SHA-256. w11-llama (2026-10-25): the product ran
    whatever BAXY_MIND_LLAMA_SERVER named, unhashed; the registration's hash (MindRuntimeDiscovery) was of a server the
    launcher overrode, and of the 10 KB launcher only, while llama.cpp's code lives in its DLLs. RuntimeError names
    the files that match no build, or says the folder mixes builds."""
    declaration = json.loads(builds.read_text(encoding="utf-8"))
    path = Path(server)
    if path.name.lower() != "llama-server.exe":
        raise RuntimeError(f"BAXY_MIND_LLAMA_SERVER is not a llama-server.exe: {server}")
    actual: dict[str, str | None] = {}
    for name in declaration["files"]:
        try:
            actual[name] = hashlib.sha256((path.parent / name).read_bytes()).hexdigest()
        except OSError:
            actual[name] = None
    for build, entry in declaration["builds"].items():
        if entry["sha256"] == actual:
            return build
    unknown = [f"{name} {digest[:12] if digest else 'missing'}" for name, digest in actual.items()
               if digest is None or all(entry["sha256"][name] != digest for entry in declaration["builds"].values())]
    detail = ", ".join(unknown) if unknown else "its files belong to different builds"
    raise RuntimeError(f"llama-server not declared in {builds.name}: {server} ({detail})")


def declared_backend(server: str, build: str, builds: Path = BUILDS) -> str:
    """The GPU backend the folder of ``server`` computes on: the one of ``build``'s declared backends (data/
    llama_server.v1.json, «backends») whose DLL is there, with its SHA-256; «cpu» when none is. Encargo 8 (2026-11-02):
    the backend's DLL was not compared, and the settings (LlmServer) depend on it. A folder with two of them does not
    start: llama.cpp loads both and computes on the first that sees the GPU (CUDA's on NVIDIA, Vulkan's elsewhere), so
    the settings could be the other backend's."""
    declared = json.loads(builds.read_text(encoding="utf-8"))["builds"][build].get("backends", {})
    folder = Path(server).parent
    present: list[str] = []
    for name, files in declared.items():
        for file, digest in files.items():
            path = folder / file
            if not path.is_file():
                continue
            with open(path, "rb") as data:
                actual = hashlib.file_digest(data, "sha256").hexdigest()
            if actual != digest:
                raise RuntimeError(f"llama-server's {file} {actual[:12]} is not {build}'s: {server}")
            present.append(name)
    if len(present) > 1:
        raise RuntimeError(f"llama-server has two GPU backends ({', '.join(present)}), keep one: {server}")
    return present[0] if present else "cpu"


# PRV1 (revisión de privacidad 2026-11-09, PRIV-04): llama-server started with no key, on the loopback, and by default
# «the server reflects any Origin header back with credentials allowed» (llama.cpp, tools/server/README.md, «CORS»,
# read 2026-11-09): a page open in any browser of this PC, or another program, could ask the model, and read or erase
# the slot that holds the person's conversation (/slots, --slot-save-path). The server takes a key, «--api-key KEY: API
# key to use for authentication … (env: LLAMA_API_KEY)», and then answers 401 «Invalid API Key» to a request without
# it; only /health is public (the same README). One key at random for each start of BAXY: the App makes it and gives it
# to the mind and to its own vision calls (BAXY_MIND_LLAMA_KEY, MindRuntimeDiscovery); a mind started without the App
# makes its own. It reaches the server in its environment, never on its command line, which other programs can read.
KEY_VARIABLE = "BAXY_MIND_LLAMA_KEY"


def server_key(environ: dict[str, str] | None = None) -> str:
    source = os.environ if environ is None else environ
    return source.get(KEY_VARIABLE, "").strip() or secrets.token_urlsafe(32)


def authorization(key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}"}


def _pinned_port() -> int | None:
    """BAXY_MIND_LLAMA_PORT when set; None when not (a free port is taken). Review 2026-10-22: a pinned port in use
    fails the start with its cause; another port taken in silence left the core's vision pointing at the pinned one."""
    try:
        port = int(os.environ.get("BAXY_MIND_LLAMA_PORT", ""))
    except ValueError:
        return None
    with socket.socket() as probe:
        try:
            probe.bind(("127.0.0.1", port))
        except OSError as error:
            raise RuntimeError(f"BAXY_MIND_LLAMA_PORT {port} is in use on the loopback: {error}") from error
    return port


def _remote_port() -> int | None:
    """BAXY_MIND_LLAMA_REMOTE: the loopback port of a remote llama-server's tunnel (measurement only); None when unset."""
    value = os.environ.get("BAXY_MIND_LLAMA_REMOTE", "").strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError as error:
        raise RuntimeError(f"BAXY_MIND_LLAMA_REMOTE is not a port: {value}") from error


def _mind_slot(remote: int | None) -> int:
    """BAXY_MIND_SLOT: the mind's slot on a shared remote server (measurement only); 0 when unset. Another slot needs
    BAXY_MIND_LLAMA_REMOTE: the mind's own server has one (-np 1)."""
    value = os.environ.get("BAXY_MIND_SLOT", "").strip()
    if not value:
        return 0
    if not value.isdigit():
        raise RuntimeError(f"BAXY_MIND_SLOT is not a slot number: {value}")
    if int(value) and remote is None:
        raise RuntimeError(f"BAXY_MIND_SLOT {value} needs BAXY_MIND_LLAMA_REMOTE: the mind's own server has one slot")
    return int(value)


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]
