"""BAXY's spoken voice: Supertonic 3 (sherpa-onnx, CPU) with BAXY's own voice, resident and played on its own thread.

The voice (chosen by the owner by ear, 2026-10-17) is a blend of three of Supertonic's male styles built by
scripts/voice/make_baxy_voice.py into BAXY_RENEW_TTS_DIR, beside the model and baxy-voice.json, the rest of the recipe:
flow-matching steps, speed, a fixed seed (the same sentence always sounds the same), the silence after each sentence,
and «shift», a fraction of a semitone that makes the voice a little smaller (pitch and formants together: the engine
speaks that much slower and the take is resampled that much shorter, so the tempo stays). The text is first turned into
what is said (speech_text.py: numbers, dates, English names); every sentence is brought to the same loudness, since the
engine's level varies with the sentence.

An answer sounds sentence by sentence: the first plays as soon as it is synthesized and the next is synthesized while
it sounds. Opening the output takes 0.38 s on the PC (its USB interface, under MME, DirectSound and WASAPI alike), so it
opens when a turn starts, while the model thinks (prepare), and closes after HOLD_S without sound, so the voice still
follows the default output.
"""
from __future__ import annotations

import itertools
import json
import os
import queue
import re
import sys
import threading
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction
from pathlib import Path
from typing import Callable

import numpy as np

from .speech_text import spoken

MAX_CHARS = 8192
BLOCK_S = 0.03      # playback block: a cancel stops the sound within one block
TAIL_S = 0.55       # BAXY counts as speaking this long after the last block (Definitivo's measured tail grace)
HOLD_S = 20.0       # an open output with nothing to say closes after this long
THREADS = 2         # sherpa-onnx CPU threads: first sentence 1.08 s with 2, 1.11 s with 4, 1.59 s with 8 (PC, 2026-10-17)
LOUDNESS = 0.11     # every sentence's RMS (about -19 dBFS), its peaks kept under PEAK
PEAK = 0.95
FADE_S = 0.005      # no click at a sentence's edges
_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+")
_MODEL_FILES = ("duration_predictor.int8.onnx", "text_encoder.int8.onnx", "vector_estimator.int8.onnx",
                "vocoder.int8.onnx", "tts.json", "unicode_indexer.bin", "voice.bin", "baxy-voice.json")


def _default_follower(sd) -> int | None:
    """The MME sound mapper (WAVE_MAPPER, which PortAudio lists first among MME outputs), or PortAudio's default."""
    for api in sd.query_hostapis():
        if api["name"] == "MME":
            outputs = [index for index in api["devices"] if sd.query_devices(index)["max_output_channels"] > 0]
            return outputs[0] if outputs else None
    return None


class Speech:
    """speak() and cancel() only post to the speech thread, which owns the voice and the audio output."""

    def __init__(self, on_state: Callable[[bool], None], on_spoken: Callable[[float, float], None]) -> None:
        self._on_state = on_state            # speaking started (True) or ended (False)
        self._on_spoken = on_spoken          # (queued at, first sound at), monotonic seconds
        self._queue: queue.Queue[tuple[int, str | None, float]] = queue.Queue(maxsize=16)
        self._generation = 0                 # cancel() moves it on; older utterances are dropped
        self._ready = threading.Event()
        self.failure = ""
        self.speaking = False
        self._tts = None
        self._voice: dict = {}
        self._shift = Fraction(1)            # baxy-voice.json's «shift» as a resampling ratio
        self.rate = 44100
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
        self._close_stream()

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
            # "low" latency: 91 ms against 183 ms on the notebook. PortAudio's default output is the device that was
            # Windows' default when it started (2026-10-17: the owner changed the default and heard nothing); the MME
            # sound mapper sends each stream to the default of the moment.
            self._stream = sd.OutputStream(samplerate=self.rate, channels=1, dtype="float32", latency="low",
                                           device=_default_follower(sd))
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
        import sherpa_onnx

        folder = Path(os.environ.get("BAXY_RENEW_TTS_DIR", ""))
        missing = [name for name in _MODEL_FILES if not (folder / name).is_file()]
        if missing:
            raise FileNotFoundError(f"BAXY_RENEW_TTS_DIR has no {', '.join(missing)}")
        self._voice = json.loads((folder / "baxy-voice.json").read_text(encoding="utf-8"))
        self._tts = sherpa_onnx.OfflineTts(sherpa_onnx.OfflineTtsConfig(model=sherpa_onnx.OfflineTtsModelConfig(
            supertonic=sherpa_onnx.OfflineTtsSupertonicModelConfig(
                duration_predictor=str(folder / "duration_predictor.int8.onnx"),
                text_encoder=str(folder / "text_encoder.int8.onnx"),
                vector_estimator=str(folder / "vector_estimator.int8.onnx"),
                vocoder=str(folder / "vocoder.int8.onnx"), tts_json=str(folder / "tts.json"),
                unicode_indexer=str(folder / "unicode_indexer.bin"), voice_style=str(folder / "voice.bin")),
            num_threads=THREADS, provider="cpu")))
        self.rate = int(self._tts.sample_rate)
        self._shift = Fraction(2 ** (float(self._voice.get("shift", 0)) / 12)).limit_denominator(100)
        self._synthesize("Hola.")  # loads the voice now, so the first answer does not wait for it

    def _sentences(self, text: str) -> Iterator[np.ndarray]:
        """Each sentence's audio in order: the first is already being synthesized (while the output opens), and each
        next one is synthesized while the previous one sounds."""
        sentences = [sentence for sentence in _SENTENCE_END.split(spoken(text)) if sentence.strip()]
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
        import sherpa_onnx
        from scipy.signal import resample_poly

        assert self._tts is not None
        config = sherpa_onnx.GenerationConfig()
        config.sid = 0
        config.num_steps = int(self._voice.get("steps", 8))
        config.speed = float(self._voice.get("speed", 1.0)) / float(self._shift)
        config.extra["lang"] = str(self._voice.get("lang", "es"))
        config.extra["seed"] = str(self._voice.get("seed", 7))
        audio = np.asarray(self._tts.generate(text, config).samples, dtype=np.float32)
        if self._shift != 1:
            audio = resample_poly(audio, self._shift.denominator, self._shift.numerator).astype(np.float32)
        rms = float(np.sqrt(np.mean(audio ** 2))) if audio.size else 0.0
        if rms > 0:
            audio *= min(LOUDNESS / rms, PEAK / float(np.max(np.abs(audio))))
        fade = min(int(self.rate * FADE_S), audio.size // 2)
        if fade:
            audio[:fade] *= np.linspace(0, 1, fade, dtype=np.float32)
            audio[-fade:] *= np.linspace(1, 0, fade, dtype=np.float32)
        gap = np.zeros(int(self.rate * float(self._voice.get("gap_s", 0.2))), dtype=np.float32)
        return np.concatenate([audio, gap])

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
