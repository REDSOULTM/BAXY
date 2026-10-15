"""BAXY's spoken voice: Piper (the es_MX voice of BAXY Definitivo) in one resident process, played on its own thread.

One piper.exe stays loaded and gets one JSON line per utterance (--json-input with output_file; it answers each line
with the path of the finished WAV, Piper's documented CLI). Measured on the notebook (2026-10-15, six phrases twice):
0.19 s p50 to synthesize a phrase, against 0.82 s starting one process per phrase as Definitivo did. An answer sounds
sentence by sentence: the first plays as soon as it is synthesized and the next is synthesized while it sounds (on the
PC the whole answer took 0.75 s p50 from voice.speak to the first sound, 2026-10-15). Opening the output takes 0.38 s
on the PC (its USB interface, under MME, DirectSound and WASAPI alike), so it opens when a turn starts, while the model
thinks (prepare), and closes after HOLD_S without sound, so the voice still follows the default output.

Paths (per PC): BAXY_RENEW_TTS_MODEL (the .onnx, with its .onnx.json beside it) and BAXY_RENEW_PIPER_DIR (piper.exe
with espeak-ng-data).
"""
from __future__ import annotations

import itertools
import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
import wave
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable

import numpy as np

MAX_CHARS = 8192
BLOCK_S = 0.03      # playback block: a cancel stops the sound within one block
TAIL_S = 0.55       # BAXY counts as speaking this long after the last block (Definitivo's measured tail grace)
HOLD_S = 20.0       # an open output with nothing to say closes after this long
_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+")


class Speech:
    """speak() and cancel() only post to the speech thread, which owns Piper and the audio output."""

    def __init__(self, on_state: Callable[[bool], None], on_spoken: Callable[[float, float], None]) -> None:
        self._on_state = on_state            # speaking started (True) or ended (False)
        self._on_spoken = on_spoken          # (queued at, first sound at), monotonic seconds
        self._queue: queue.Queue[tuple[int, str | None, float]] = queue.Queue(maxsize=16)
        self._generation = 0                 # cancel() moves it on; older utterances are dropped
        self._ready = threading.Event()
        self.failure = ""
        self.speaking = False
        self._piper: subprocess.Popen | None = None
        self._dir = Path(os.environ.get("LOCALAPPDATA", ".")) / "BAXY" / "renew" / "speech"
        self._files = itertools.count()
        self._leftovers: list[Path] = []     # WAVs Piper still held when read; removed on the next phrase
        self._synthesis = ThreadPoolExecutor(1, thread_name_prefix="speech-synthesis")
        self._stream = None                  # the output, open from a turn's start until HOLD_S without sound
        self._stream_until = 0.0
        threading.Thread(target=self._run, name="speech", daemon=True).start()

    @property
    def ready(self) -> bool:
        return self._ready.is_set() and not self.failure

    def speak(self, text: str) -> bool:
        text = " ".join(str(text or "").split())[:MAX_CHARS]
        if not text or not self.ready:
            return False
        try:
            self._queue.put_nowait((self._generation, text, time.monotonic()))
        except queue.Full:
            return False
        return True

    def prepare(self) -> None:
        """A turn started: open the output now, so its answer does not wait for the device."""
        if self.ready:
            try:
                self._queue.put_nowait((self._generation, None, time.monotonic()))
            except queue.Full:
                pass

    def cancel(self) -> None:
        self._generation += 1

    def close(self) -> None:
        self.cancel()
        if self._piper is not None and self._piper.poll() is None:
            self._piper.kill()
        self._close_stream()
        for leftover in self._leftovers:
            leftover.unlink(missing_ok=True)

    # --- the speech thread ----------------------------------------------------------------------------------------

    def _run(self) -> None:
        try:
            self._start()
        except Exception as error:  # noqa: BLE001 - without a voice BAXY still answers on screen
            self.failure = repr(error)
            sys.stderr.write(f"baxy_mind_renew_speech: {self.failure}\n")
            sys.stderr.flush()
        finally:
            self._ready.set()
        while not self.failure:
            try:
                generation, text, queued = self._queue.get(timeout=1.0)
            except queue.Empty:
                if self._stream is not None and time.monotonic() > self._stream_until:
                    self._close_stream()
                continue
            try:
                if text is None:
                    self._open_stream()
                elif generation == self._generation:
                    self._play(self._sentences(text), generation, queued)
            except Exception as error:  # noqa: BLE001 - one failed phrase never ends the voice
                self._close_stream()
                sys.stderr.write(f"baxy_mind_renew_speech: {error!r}\n")
                sys.stderr.flush()

    def _open_stream(self):
        import sounddevice as sd

        if self._stream is None:
            # "low" latency: 91 ms against 183 ms on the notebook.
            self._stream = sd.OutputStream(samplerate=self.rate, channels=1, dtype="float32", latency="low")
            self._stream.start()
        self._stream_until = time.monotonic() + HOLD_S
        return self._stream

    def _close_stream(self) -> None:
        stream, self._stream = self._stream, None
        if stream is not None:
            try:
                stream.abort()
                stream.close()
            except Exception:  # noqa: BLE001 - a device already gone has nothing to close
                pass

    def _start(self) -> None:
        model = Path(os.environ.get("BAXY_RENEW_TTS_MODEL", ""))
        piper = Path(os.environ.get("BAXY_RENEW_PIPER_DIR", "")) / "piper.exe"
        if not model.is_file() or not model.with_suffix(".onnx.json").is_file():
            raise FileNotFoundError("BAXY_RENEW_TTS_MODEL has no Piper voice")
        if not piper.is_file():
            raise FileNotFoundError("BAXY_RENEW_PIPER_DIR has no piper.exe")
        config = json.loads(model.with_suffix(".onnx.json").read_text(encoding="utf-8"))
        self.rate = int(config["audio"]["sample_rate"])
        self._dir.mkdir(parents=True, exist_ok=True)
        self._piper = subprocess.Popen(
            [str(piper), "--model", str(model), "--espeak_data", str(piper.parent / "espeak-ng-data"),
             "--json-input", "--quiet"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self._synthesize("Hola.")  # loads the voice now, so the first answer does not wait for it

    def _sentences(self, text: str) -> Iterator[np.ndarray]:
        """Each sentence's audio in order: the first is already being synthesized (while the output opens), and each
        next one is synthesized while the previous one sounds."""
        sentences = [sentence for sentence in _SENTENCE_END.split(text) if sentence.strip()]
        first = self._synthesis.submit(self._synthesize, sentences[0])

        def audio() -> Iterator[np.ndarray]:
            pending = first
            for following in sentences[1:]:
                ready = pending.result()
                pending = self._synthesis.submit(self._synthesize, following)
                yield ready
            yield pending.result()

        return audio()

    def _synthesize(self, text: str) -> np.ndarray:
        assert self._piper is not None and self._piper.stdin is not None and self._piper.stdout is not None
        for leftover in list(self._leftovers):
            try:
                leftover.unlink(missing_ok=True)
                self._leftovers.remove(leftover)
            except OSError:
                pass
        target = self._dir / f"utterance-{next(self._files)}.wav"
        line = json.dumps({"text": text, "output_file": str(target)}, ensure_ascii=False) + "\n"
        self._piper.stdin.write(line.encode("utf-8"))
        self._piper.stdin.flush()
        done = self._piper.stdout.readline().decode("utf-8", "replace").strip()
        if not done:
            raise RuntimeError(f"piper exited with {self._piper.poll()}")
        try:
            with wave.open(str(target), "rb") as wav:
                pcm = wav.readframes(wav.getnframes())
        finally:
            # What BAXY says is the person's: nothing stays on disk. Piper may still hold the file when it answers
            # (measured on the PC: the unlink failed and the phrase was lost), so it goes on the next phrase.
            try:
                target.unlink(missing_ok=True)
            except OSError:
                self._leftovers.append(target)
        return np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768.0

    def _play(self, sentences: Iterator[np.ndarray], generation: int, queued: float) -> None:
        stream = self._open_stream()
        audio = next(sentences)
        if generation != self._generation:
            return
        block = int(self.rate * BLOCK_S)
        self.speaking = True
        self._on_state(True)
        try:
            # The first block sounds once the device's output latency has passed.
            self._on_spoken(queued, time.monotonic() + stream.latency)
            for audio in itertools.chain([audio], sentences):
                for at in range(0, len(audio), block):
                    if generation != self._generation:
                        self._close_stream()  # what was written is dropped at once
                        break
                    stream.write(audio[at:at + block].reshape(-1, 1))
                else:
                    continue
                break
            else:
                time.sleep(stream.latency)  # the blocks written are still in the device buffer
                self._stream_until = time.monotonic() + HOLD_S
            ends = time.monotonic() + TAIL_S
            while time.monotonic() < ends and generation == self._generation and self._queue.empty():
                time.sleep(0.05)
        finally:
            self.speaking = False
            self._on_state(False)
