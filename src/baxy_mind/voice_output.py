"""BAXY's spoken voice: Supertonic 3 (sherpa-onnx, CPU) with BAXY's own voice, resident and played on its own thread.

The voice (chosen by the owner by ear, 2026-10-17) is a blend of three of Supertonic's male styles built by
scripts/voice/make_baxy_voice.py into BAXY_RENEW_TTS_DIR, beside the model and baxy-voice.json, the rest of the recipe:
flow-matching steps, speed, a fixed seed (the same sentence always sounds the same), the silence after each sentence,
and «shift», a fraction of a semitone that makes the voice a little smaller (pitch and formants together: the engine
speaks that much slower and the take is resampled that much shorter, so the tempo stays). The text is first turned into
what is said (speech_text.py: numbers, dates, English names); every sentence is brought to the same loudness, since the
engine's level varies with the sentence.

An answer sounds sentence by sentence: the first plays as soon as it is synthesized and the next is synthesized while
it sounds; a loaded voice starts synthesizing an answer the moment it is given, while what is ahead of it still sounds.
The turn's notice (said when a turn has been silent for 2.5 s) is the phrase the model wrote at warm-up, which the mind
gives the voice with its catalog.ready (set_notice; al máximo 9.2a: it was «Un momento.», fixed in the code). It is
synthesized as soon as the voice has it and said from that audio only: a notice never takes the one synthesis an answer
needs (owner, 2026-10-20: an answer waited 3.6 s behind a notice synthesized like any sentence). It is dropped if an
answer was given before it began to sound: said then, it came right before the answer and held it back (owner,
2026-10-20: the notice cut in on what BAXY was about to say; answers waited up to 4.8 s behind it). Opening the output takes 0.38 s on the PC (its USB interface, under MME, DirectSound and WASAPI alike), so it
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
CLOSE_S = 2.0       # close() waits this long for the speech thread to close its output (a sentence being synthesized)
THREADS = 2         # sherpa-onnx CPU threads: first sentence 1.08 s with 2, 1.11 s with 4, 1.59 s with 8 (PC, 2026-10-17)
LOUDNESS = 0.11     # every sentence's RMS (about -19 dBFS) over its voice only, its peaks kept under PEAK
PEAK = 0.95
FADE_S = 0.015      # no click at a sentence's trimmed edges
# Supertonic leaves 0.35-0.67 s of near silence before and after each take: the pause BAXY played between sentences was
# 1.0-1.2 s, not its 0.2 s (measured 2026-10-20). Each take is cut to its voice (frames above -40 dB of its loudest,
# 30 ms before, 100 ms of decay after) and the pause is then BAXY's own: read Spanish pauses 391-482 ms on average
# (Schwab 2015); a question gets a little more.
SILENCE_DB = -40.0
LEAD_S, TAIL_S_KEPT = 0.03, 0.10
GAP_S, GAP_QUESTION_S = 0.35, 0.45
# The mouth follows the voice (owner, 2026-10-21: the avatar's speaking animation ended while BAXY still spoke): each
# take's loudness every LIP_STEP_S, from LIP_FLOOR_DB (closed) to LIP_TOP_DB (open), goes to the view with the wall
# clock time its first sample sounds, so the view moves the mouth with what is heard and not with the state.
LIP_STEP_S = 0.04
LIP_FLOOR_DB, LIP_TOP_DB = -45.0, -12.0
_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+")
_VOWELS = re.compile(r"[aeiouáéíóúü]+", re.IGNORECASE)
_MODEL_FILES = ("duration_predictor.int8.onnx", "text_encoder.int8.onnx", "vector_estimator.int8.onnx",
                "vocoder.int8.onnx", "tts.json", "unicode_indexer.bin", "voice.bin", "baxy-voice.json")


def _speed(text: str) -> float:
    """Supertonic predicts one length per call, so a short sentence came out rushed (7.9 syllables/s) and a long one
    slow (5.3); natural Spanish speeds up with the phrase's length (Schwab 2015): the recipe's speed is scaled by it."""
    syllables = len(_VOWELS.findall(text))
    return 0.94 if syllables <= 8 else 1.0 if syllables <= 20 else 1.06


def _trim(audio: np.ndarray, rate: int) -> np.ndarray:
    """The take cut to its voice: from 30 ms before the first 10 ms frame above -40 dB of its loudest to 100 ms after
    the last one."""
    hop = max(1, rate // 100)
    frames = audio[: audio.size // hop * hop].reshape(-1, hop)
    if not frames.size:
        return audio
    level = np.sqrt((frames ** 2).mean(axis=1))
    loud = np.flatnonzero(level >= level.max() * 10 ** (SILENCE_DB / 20))
    if not loud.size:
        return audio
    start = max(0, loud[0] * hop - int(rate * LEAD_S))
    end = min(audio.size, (loud[-1] + 1) * hop + int(rate * TAIL_S_KEPT))
    return audio[start:end]


def _default_follower(sd) -> int | None:
    """The MME sound mapper (WAVE_MAPPER, which PortAudio lists first among MME outputs), or PortAudio's default."""
    for api in sd.query_hostapis():
        if api["name"] == "MME":
            outputs = [index for index in api["devices"] if sd.query_devices(index)["max_output_channels"] > 0]
            return outputs[0] if outputs else None
    return None


class Speech:
    """speak() and cancel() only post to the speech thread, which owns the voice and the audio output."""

    def __init__(self, on_state: Callable[[bool], None], on_spoken: Callable[[float, float], None],
                 on_lip: Callable[[dict], None] = lambda _lip: None) -> None:
        self._on_state = on_state            # speaking started (True) or ended (False)
        self._on_spoken = on_spoken          # (queued at, first sound at), monotonic seconds
        self._on_lip = on_lip                # a take's loudness and when it sounds, or when the sound was cut
        # (generation, text or None to open the output, queued at, for a notice the answers given before it, its audio
        # when its synthesis already started), or None to end the speech thread (close)
        self._queue: queue.Queue[tuple[int, str | None, float, int | None, Iterator[np.ndarray] | None] | None] = \
            queue.Queue(maxsize=16)
        # speak() (the reader) and prepare() (the request loop) share the queue; reentrant, since a notice whose
        # synthesis is already done keeps its audio from inside set_notice (add_done_callback runs it at once)
        self._posting = threading.RLock()
        self._generation = 0                 # cancel() moves it on; older utterances are dropped
        self._answers = 0                    # answers given so far: a notice with an answer after it is not said
        self._notice_text = ""               # the mind's notice phrase (set_notice), said only as a notice
        self._notice_audio: np.ndarray | None = None  # its audio, synthesized once, with no pause after it
        self._loaded = False                 # Supertonic is loaded: a notice given from now on is synthesized at once
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
        self._thread: threading.Thread | None = None
        # A voice whose files are not there fails now, not after the load: speak() never takes what will not sound.
        folder = Path(os.environ.get("BAXY_RENEW_TTS_DIR", ""))
        missing = [name for name in _MODEL_FILES if not (folder / name).is_file()]
        if missing:
            self.failure = repr(FileNotFoundError(f"BAXY_RENEW_TTS_DIR has no {', '.join(missing)}"))
            sys.stderr.write(f"baxy_mind_renew_speech: {self.failure}\n")
            sys.stderr.flush()
            self._ready.set()
            return
        self._thread = threading.Thread(target=self._run, name="speech", daemon=True)
        self._thread.start()

    @property
    def ready(self) -> bool:
        return self._ready.is_set() and not self.failure

    def speak(self, text: str, notice: bool = False) -> bool:
        # FT/proveedores goal (E001): while the voice still loads (about 26 s after the catalog on the notebook) the
        # answer waits in the queue and sounds once it is loaded; it was dropped, and the first answer after BAXY
        # started was never heard. Only a voice that failed refuses it.
        text = " ".join(str(text or "").split())[:MAX_CHARS]
        if not text or self.failure:
            return False
        with self._posting:
            # A refused answer leaves nothing behind: not counted (it would drop a notice) and not synthesized.
            if self._queue.full():
                return False
            audio = None
            if notice:
                # Only the mind's phrase, from its audio: ready at once and nothing to synthesize, it never holds the
                # synthesis an answer given now needs. With no audio yet (the voice still loads) it is not said.
                if text != self._notice_text or self._notice_audio is None:
                    return False
                audio = iter([self._notice_audio])
            else:
                self._answers += 1
            if audio is None and self.ready:
                try:
                    audio = self._sentences(text)
                except Exception:  # noqa: BLE001 - the speech thread synthesizes it then, and says what failed
                    audio = None
            self._queue.put_nowait((self._generation, text, time.monotonic(), self._answers if notice else None,
                                    audio))
        return True

    def set_notice(self, text: str) -> None:
        """The mind's notice phrase (its catalog.ready): synthesized now, or as soon as the voice has loaded; empty, no
        notice is said."""
        text = " ".join(str(text or "").split())[:MAX_CHARS]
        with self._posting:
            self._notice_text, self._notice_audio = text, None
            if text and self._loaded and not self.failure:
                self._synthesize_notice(text)

    def _synthesize_notice(self, text: str) -> None:
        """Called under _posting. Kept only while it is still the mind's phrase."""
        def keep(done) -> None:
            if done.exception() is None:
                with self._posting:
                    if self._notice_text == text:
                        self._notice_audio = done.result()
            else:
                sys.stderr.write(f"baxy_mind_renew_speech: notice: {done.exception()!r}\n")
                sys.stderr.flush()

        self._synthesis.submit(self._synthesize, text, False).add_done_callback(keep)

    def prepare(self) -> None:
        """A turn started: open the output now, so its answer does not wait for the device."""
        if self.ready:
            with self._posting:
                if not self._queue.full():
                    self._queue.put_nowait((self._generation, None, time.monotonic(), None, None))

    def cancel(self) -> None:
        self._generation += 1

    def close(self) -> None:
        """The speech thread closes its own output: closed from here it was aborted in the middle of a write."""
        self.cancel()
        if self._thread is None:
            return
        try:
            with self._posting:
                self._queue.put(None, timeout=CLOSE_S)
        except queue.Full:
            return
        self._thread.join(CLOSE_S)

    # --- the speech thread ----------------------------------------------------------------------------------------

    def _run(self) -> None:
        try:
            self._start()
            with self._posting:
                self._loaded = True
                if self._notice_text:
                    self._synthesize_notice(self._notice_text)
        except Exception as error:  # noqa: BLE001 - without a voice BAXY still answers on screen
            self.failure = repr(error)
            sys.stderr.write(f"baxy_mind_renew_speech: {self.failure}\n")
            sys.stderr.flush()
        finally:
            self._ready.set()
        while not self.failure:
            try:
                item = self._queue.get(timeout=1.0)
            except queue.Empty:
                if self._stream is not None and time.monotonic() > self._stream_until:
                    self._close_stream()
                continue
            if item is None:
                self._close_stream()
                return
            generation, text, queued, notice, audio = item
            try:
                if text is None:
                    self._open_stream()
                elif generation == self._generation and notice in (None, self._answers):
                    sentences = audio if audio is not None else self._sentences(text)
                    if notice is not None:
                        first = next(sentences, None)  # an answer given while the notice was synthesized drops it too
                        if first is None or notice != self._answers or generation != self._generation:
                            continue
                        sentences = itertools.chain([first], sentences)
                    self._play(sentences, generation, queued)
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
        # Loads the voice now, so the first answer does not wait for it.
        self._synthesize("Hola.", pause=False)

    def _sentences(self, text: str) -> Iterator[np.ndarray]:
        """Each sentence's audio in order: the first is already being synthesized (while the output opens), and each
        next one is synthesized while the previous one sounds."""
        said = spoken(text)
        sentences = [sentence for sentence in _SENTENCE_END.split(said) if sentence.strip()]
        # A reply that starts with a word or two («Listo.», «Hecho.») is one call: the very short utterance is
        # Supertonic's weak spot (issue #30). Any other first sentence is synthesized alone, so it sounds sooner: joining
        # every reply of up to 120 characters (84 % of them) cost 1 595 ms to the first audio against 989 ms for the first
        # sentence alone (p50 of 16 two-sentence replies, 10 steps, PC CPU, renew al máximo 9.3, 2026-10-22).
        if len(sentences) > 1 and len(sentences[0].split()) <= 3:
            sentences = [said]
        generation = self._generation

        def synthesize(sentence: str) -> np.ndarray:
            # What was cancelled before its turn to be synthesized is not: it held the one synthesis thread, and the
            # next turn's answer waited 2.8-5.7 s behind sentences nobody would hear (owner talking over BAXY,
            # 2026-10-20).
            return self._synthesize(sentence) if generation == self._generation else np.zeros(0, np.float32)

        first = self._synthesis.submit(synthesize, sentences[0])

        def audio() -> Iterator[np.ndarray]:
            pending = first
            for following in sentences[1:]:
                ready = pending.result()
                if generation != self._generation:
                    return
                pending = self._synthesis.submit(synthesize, following)
                yield ready
            yield pending.result()

        return audio()

    def _synthesize(self, text: str, pause: bool = True) -> np.ndarray:
        import sherpa_onnx
        from scipy.signal import resample_poly

        assert self._tts is not None
        config = sherpa_onnx.GenerationConfig()
        config.sid = 0
        config.num_steps = int(self._voice.get("steps", 8))
        config.speed = float(self._voice.get("speed", 1.0)) * _speed(text) / float(self._shift)
        # The whole map, never config.extra[key] = ...: pybind11 hands Python a copy of it and the keys were lost, so
        # BAXY spoke with Supertonic's default «en» tag and a new random seed every time (found 2026-10-20).
        config.extra = {"lang": str(self._voice.get("lang", "es")), "seed": str(self._voice.get("seed", 7))}
        audio = np.asarray(self._tts.generate(text, config).samples, dtype=np.float32)
        if self._shift != 1:
            audio = resample_poly(audio, self._shift.denominator, self._shift.numerator).astype(np.float32)
        audio = _trim(audio, self.rate).copy()
        rms = float(np.sqrt(np.mean(audio ** 2))) if audio.size else 0.0
        if rms > 0:
            audio *= min(LOUDNESS / rms, PEAK / float(np.max(np.abs(audio))))
        fade = min(int(self.rate * FADE_S), audio.size // 2)
        if fade:
            audio[:fade] *= np.linspace(0, 1, fade, dtype=np.float32)
            audio[-fade:] *= np.linspace(1, 0, fade, dtype=np.float32)
        if not pause:
            return audio
        gap = np.zeros(int(self.rate * (GAP_QUESTION_S if text.rstrip().endswith("?") else GAP_S)), dtype=np.float32)
        return np.concatenate([audio, gap])

    def _play(self, sentences: Iterator[np.ndarray], generation: int, queued: float) -> None:
        stream = self._open_stream()
        audio = next(sentences, None)  # none when it was cancelled before its first sentence was synthesized
        if audio is None or generation != self._generation:
            return
        block = int(self.rate * BLOCK_S)
        self.speaking = True
        self._on_state(True)
        heard_until = 0.0  # wall clock (s) when what was written so far ends sounding
        try:
            # The first block sounds once the device's output latency has passed.
            self._on_spoken(queued, time.monotonic() + stream.latency)
            for audio in itertools.chain([audio], sentences):
                # A take written right after the last one sounds right after it; one that waited for its synthesis
                # (the output ran dry) sounds once the device's latency has passed.
                starts = max(time.time() + stream.latency, heard_until)
                heard_until = starts + len(audio) / self.rate
                self._on_lip({"t0": round(starts * 1000), "step": round(LIP_STEP_S * 1000),
                              "env": lip_envelope(audio, self.rate)})
                for at in range(0, len(audio), block):
                    if generation != self._generation:
                        self._close_stream()  # what was written is dropped at once
                        self._on_lip({"stop": round(time.time() * 1000)})
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


def lip_envelope(audio: np.ndarray, rate: int) -> list[float]:
    """How open the mouth is every LIP_STEP_S of a take, 0 (closed) to 1, from its loudness in dB."""
    step = max(1, int(rate * LIP_STEP_S))
    count = len(audio) // step + (1 if len(audio) % step else 0)
    if not count:
        return []
    padded = np.zeros(count * step, np.float32)
    padded[:len(audio)] = audio
    rms = np.sqrt(np.mean(padded.reshape(count, step) ** 2, axis=1))
    db = 20 * np.log10(rms + 1e-9)
    level = np.clip((db - LIP_FLOOR_DB) / (LIP_TOP_DB - LIP_FLOOR_DB), 0.0, 1.0)
    return [round(float(v), 2) for v in level]
