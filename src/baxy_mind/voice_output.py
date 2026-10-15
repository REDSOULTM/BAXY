"""BAXY's spoken voice: Piper (the es_MX voice of BAXY Definitivo) in one resident process, played on its own thread.

One piper.exe stays loaded and gets one JSON line per utterance (--json-input with output_file; it answers each line
with the path of the finished WAV, Piper's documented CLI). Measured on the notebook (2026-10-15, six phrases twice):
0.19 s p50 to synthesize a phrase, against 0.82 s starting one process per phrase as Definitivo did.

Paths (per PC): BAXY_RENEW_TTS_MODEL (the .onnx, with its .onnx.json beside it) and BAXY_RENEW_PIPER_DIR (piper.exe
with espeak-ng-data).
"""
from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import time
import wave
from pathlib import Path
from typing import Callable

import numpy as np

MAX_CHARS = 8192
BLOCK_S = 0.03      # playback block: a cancel stops the sound within one block
TAIL_S = 0.55       # BAXY counts as speaking this long after the last block (Definitivo's measured tail grace)


class Speech:
    """speak() and cancel() only post to the speech thread, which owns Piper and the audio output."""

    def __init__(self, on_state: Callable[[bool], None], on_spoken: Callable[[float, float], None]) -> None:
        self._on_state = on_state            # speaking started (True) or ended (False)
        self._on_spoken = on_spoken          # (queued at, first sound at), monotonic seconds
        self._queue: queue.Queue[tuple[int, str, float]] = queue.Queue(maxsize=16)
        self._generation = 0                 # cancel() moves it on; older utterances are dropped
        self._ready = threading.Event()
        self.failure = ""
        self.speaking = False
        self._piper: subprocess.Popen | None = None
        self._dir = Path(os.environ.get("LOCALAPPDATA", ".")) / "BAXY" / "renew" / "speech"
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

    def cancel(self) -> None:
        self._generation += 1

    def close(self) -> None:
        self.cancel()
        if self._piper is not None and self._piper.poll() is None:
            self._piper.kill()

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
            generation, text, queued = self._queue.get()
            if generation != self._generation:
                continue
            try:
                audio = self._synthesize(text)
                if generation == self._generation:
                    self._play(audio, generation, queued)
            except Exception as error:  # noqa: BLE001 - one failed phrase never ends the voice
                sys.stderr.write(f"baxy_mind_renew_speech: {error!r}\n")
                sys.stderr.flush()

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

    def _synthesize(self, text: str) -> np.ndarray:
        assert self._piper is not None and self._piper.stdin is not None and self._piper.stdout is not None
        target = self._dir / "utterance.wav"
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
            target.unlink(missing_ok=True)  # what BAXY says is the person's; nothing stays on disk
        return np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768.0

    def _play(self, audio: np.ndarray, generation: int, queued: float) -> None:
        import sounddevice as sd

        block = int(self.rate * BLOCK_S)
        self.speaking = True
        self._on_state(True)
        try:
            # Opened per phrase so the voice follows the default output; "low" latency: 91 ms against 183 ms here.
            with sd.OutputStream(samplerate=self.rate, channels=1, dtype="float32", latency="low") as stream:
                # The first block sounds once the device's output latency has passed.
                self._on_spoken(queued, time.monotonic() + stream.latency)
                for at in range(0, len(audio), block):
                    if generation != self._generation:
                        stream.abort()
                        break
                    stream.write(audio[at:at + block].reshape(-1, 1))
                else:
                    time.sleep(stream.latency)  # the blocks written are still in the device buffer
            ends = time.monotonic() + TAIL_S
            while time.monotonic() < ends and generation == self._generation and self._queue.empty():
                time.sleep(0.05)
        finally:
            self.speaking = False
            self._on_state(False)
