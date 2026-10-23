"""Spoken turns without a microphone, for benches (scripts/voice/hablar.py): the voice hears WAV files instead of the
microphone, in real time, in the same blocks, as if they were said into it. Nothing else of the voice changes: the wake
word, the end of the request, the early transcript and the transcript are the microphone's.

BAXY_RENEW_VOICE_FEED: a folder (its *.wav, in name order), a list file (one WAV per line, relative to the list; a tab
and a number after the path is that file's gap), one WAV, or WAVs joined by «;». Each file is 16 kHz mono 16-bit PCM.
Between them the voice hears silence: each file waits until BAXY answered the one before (an answer began to sound, not
the notice; or REPLY_WAIT_S passed without one), then for its gap (BAXY_RENEW_VOICE_FEED_GAP, GAP_S by default) with
BAXY silent and no request hearing voice; the first file waits only for its gap. Heard while BAXY speaks, a block is
dropped as the microphone's would be; heard while a turn runs, the App drops the words (voice_dropped_busy), so the gap
starts after the answer. While the voice is closed (stop, or a direct request done) the feed waits where it was.
BAXY_RENEW_VOICE_FEED_LOG: a JSON-lines file where each file's audio is written when it was heard (wall clock, as the
trace's ``t`` and ``sound_at``): its start, the end of its voice as voice.py hears it (loud and heard as speech), its
end; then «done» once the last one was answered.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import threading
import time
import wave
from pathlib import Path
from typing import Any, Callable

import numpy as np

GAP_S = 2.0          # silence before each file once BAXY answered the one before
REPLY_WAIT_S = 60.0  # a file waits this long for the answer to the one before; then only its gap


def now_iso(at: float | None = None) -> str:
    return _dt.datetime.fromtimestamp(time.time() if at is None else at).isoformat(timespec="milliseconds")


def read_wav(path: Path, rate: int) -> np.ndarray:
    with wave.open(str(path), "rb") as w:
        if (w.getframerate(), w.getnchannels(), w.getsampwidth()) != (rate, 1, 2):
            raise ValueError(f"{path}: {w.getframerate()} Hz, {w.getnchannels()} channels, {8 * w.getsampwidth()} "
                             f"bits; the feed hears {rate} Hz mono 16-bit (scripts/voice/hablar.py writes them so)")
        return np.frombuffer(w.readframes(w.getnframes()), "<i2").astype(np.float32) / 32768


def listed(spec: str) -> list[tuple[Path, float | None]]:
    """The files BAXY_RENEW_VOICE_FEED names, each with its own gap (None: the feed's)."""
    path = Path(spec)
    if path.is_dir():
        return [(file, None) for file in sorted(path.glob("*.wav"))]
    if path.suffix.lower() == ".wav" and path.is_file():
        return [(path, None)]
    if path.is_file():
        items: list[tuple[Path, float | None]] = []
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            name, _, gap = line.partition("\t")
            file = Path(name.strip())
            items.append((file if file.is_absolute() else path.parent / file, float(gap) if gap.strip() else None))
        return items
    return [(Path(part.strip()), None) for part in spec.split(";") if part.strip()]


class Feed:
    """In place of sounddevice's InputStream for Voice: start() hears (again), close() stops hearing; the files go on
    where they were. ``quiet``: BAXY silent and no request hearing voice. ``answered``: answers that began to sound."""

    pace = 1.0  # wall seconds per second of audio (the tests hear faster)

    def __init__(self, items: list[tuple[Path, float | None]], rate: int, block: int,
                 voiced: Callable[[np.ndarray], np.ndarray], quiet: Callable[[], bool], answered: Callable[[], int],
                 gap_s: float = GAP_S, log: Path | None = None) -> None:
        if not items:
            raise ValueError("BAXY_RENEW_VOICE_FEED names no WAV file")
        self._audio = [read_wav(path, rate) for path, _ in items]  # a missing or wrong file fails now, not mid-bench
        self._items = items
        self._rate, self._block, self._voiced = rate, block, voiced
        self._quiet, self._answered = quiet, answered
        self._gap_s = gap_s
        self._log = log
        self._callback: Callable[..., None] | None = None
        self._hearing = threading.Event()
        self._thread: threading.Thread | None = None
        self.done = threading.Event()

    # --- what Voice calls -----------------------------------------------------------------------------------------

    def open(self, callback: Callable[..., None]) -> "Feed":
        self._callback = callback
        return self

    def start(self) -> None:
        self._hearing.set()
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, name="voice-feed", daemon=True)
            self._thread.start()

    def close(self) -> None:
        self._hearing.clear()

    # --- the feed's own thread ------------------------------------------------------------------------------------

    def _run(self) -> None:
        clock = _Clock(self._block / self._rate * self.pace, self._hearing)
        silence = np.zeros(self._block, np.float32)
        answered_before: int | None = None   # answers counted when the last file ended (None before the first)
        ended_at = 0.0
        for index, ((path, gap), audio) in enumerate(zip(self._items, self._audio)):
            self._wait(clock, silence, answered_before, ended_at, self._gap_s if gap is None else gap)
            blocks = np.concatenate([audio, np.zeros(-len(audio) % self._block, np.float32)]).reshape(-1, self._block)
            started = None
            for block in blocks:
                delivered = clock.tick()
                started = delivered - clock.step if started is None else started  # a block is heard once it is whole
                self._deliver(block)
            answered_before, ended_at = self._answered(), time.monotonic()
            voice_end = self._voice_end(blocks)
            self._write({"event": "said", "index": index, "wav": str(path), "started_at": now_iso(clock.wall(started)),
                         "voice_end_at": None if voice_end is None else now_iso(clock.wall(started) + voice_end * clock.step),
                         "ended_at": now_iso(clock.wall(started) + len(blocks) * clock.step),
                         "audio_s": round(len(audio) / self._rate, 3)})
        self._wait(clock, silence, answered_before, ended_at, self._gap_s, last=True)
        self._write({"event": "done", "at": now_iso()})
        self.done.set()
        while True:
            clock.tick()
            self._deliver(silence)

    def _wait(self, clock: "_Clock", silence: np.ndarray, answered_before: int | None, ended_at: float,
              gap_s: float, last: bool = False) -> None:
        """Silence until the answer to the last file began to sound (or REPLY_WAIT_S), then ``gap_s`` of quiet. After
        the last file the voice may be closed (a direct request ends so): the wait goes on all the same."""
        quiet_since: float | None = None
        while True:
            clock.tick(hearing=not last)
            self._deliver(silence)
            now = time.monotonic()
            answered = answered_before is None or self._answered() > answered_before \
                or now - ended_at >= REPLY_WAIT_S * self.pace
            if not answered or not self._quiet():
                quiet_since = None
                continue
            quiet_since = now if quiet_since is None else quiet_since
            if now - quiet_since >= gap_s * self.pace:
                return

    def _voice_end(self, blocks: np.ndarray) -> int | None:
        """Blocks up to the end of the last one voice.py takes for voice, None when it has none."""
        voiced = np.flatnonzero(self._voiced(blocks.reshape(-1)))
        return int(voiced[-1]) + 1 if len(voiced) else None

    def _deliver(self, block: np.ndarray) -> None:
        if self._callback is not None and self._hearing.is_set():
            self._callback(block.reshape(-1, 1), len(block), None, None)

    def _write(self, row: dict[str, Any]) -> None:
        if self._log is None:
            return
        try:
            with self._log.open("a", encoding="utf-8") as out:
                out.write(json.dumps(row, ensure_ascii=False) + "\n")
        except OSError:
            pass  # a log that cannot be written never stops the voice


class _Clock:
    """One block every ``step`` wall seconds, as a microphone delivers them; while the voice is closed it waits (and
    starts again from that moment, so no block is delivered late in a burst)."""

    def __init__(self, step: float, hearing: threading.Event) -> None:
        self.step = step
        self._hearing = hearing
        self._next = time.monotonic()
        self._offset = time.time() - time.monotonic()

    def tick(self, hearing: bool = True) -> float:
        """Waits for the next block's moment and returns it (monotonic); ``hearing``: first, for the voice to be open."""
        if hearing and not self._hearing.is_set():
            self._hearing.wait()
            self._next = time.monotonic()
        self._next += self.step
        delay = self._next - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        elif delay < -self.step:
            self._next = time.monotonic()  # fell behind (a stalled process): the microphone does not catch up either
        return self._next

    def wall(self, at: float) -> float:
        return at + self._offset


def from_env(rate: int, block: int, voiced: Callable[[np.ndarray], np.ndarray], quiet: Callable[[], bool],
             answered: Callable[[], int]) -> Feed | None:
    """The feed BAXY_RENEW_VOICE_FEED asks for, or None (the microphone). ``voiced``: which blocks of a file's audio are
    voice, as voice.py decides it. A bad setting raises: the voice says so."""
    spec = os.environ.get("BAXY_RENEW_VOICE_FEED", "").strip()
    if not spec:
        return None
    gap = float(os.environ.get("BAXY_RENEW_VOICE_FEED_GAP", "").strip() or GAP_S)
    log = os.environ.get("BAXY_RENEW_VOICE_FEED_LOG", "").strip()
    return Feed(listed(spec), rate, block, voiced, quiet, answered, gap, Path(log) if log else None)
