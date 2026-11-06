"""What the PC plays, taken out of what the microphone hears before the wake word, the VAD and the recognizer hear it
(acoustic echo cancellation).

Real use (2026-11-03): the owner listened to a song on the PC's speakers and its words went into the transcript. The
reference is what Windows sends to the default output device (WASAPI loopback, PyAudioWPatch), the canceller WebRTC's
AEC3 (pywebrtc-audio), both already pinned in the runtime lock; it runs in the microphone's own callback, so each block
is paired with the reference of the moment it arrived and nothing waits for the recognizer. The choice (AEC3 against
Windows' Voice Capture DSP, the Communications category, SpeexDSP and neural cancellers) and what was measured live in
documentacion/CANCELACION_DE_ECO.md.

Off with BAXY_ECHO_CANCEL=0, or the owner's switch (voice.start's ``echoCancel``). A PC without a loopback to hear, or
whose loopback does not open, hears the microphone as before, and says why on stderr.
"""
from __future__ import annotations

import os
import sys
import threading
from collections import deque
from fractions import Fraction
from typing import Any, Callable, NamedTuple

import numpy as np

from .resample import Polyphase, lowpass

FRAME = 160            # AEC3's 10 ms at 16 kHz; the microphone's blocks are a whole number of them
# The reference handed with a block is the oldest the loopback holds, so it leads the echo the block carries by the
# output and input latencies. Packets come every ~10 ms and the two devices' clocks drift (a USB microphone and another
# output): what is held over the block beyond SLACK_HIGH_S is dropped down to SLACK_LOW_S. AEC3's delay estimator
# follows the rest (it covers ~0.6 s).
SLACK_LOW_S = 0.02
SLACK_HIGH_S = 0.06
TAPS_PER_PHASE = 24     # the resampler's low-pass, per polyphase branch
# The loopback carries Windows' volume: at the owner's 8 % (loud speakers behind a USB interface) the song reached the
# reference at -61 dBFS while the microphone heard it 6 dB over the room, and AEC3 took out 0.7 dB of it: it does not
# adapt to a render quieter than its active_render_limit (100 in 16-bit units, -50 dBFS; echo_canceller3_config.h).
# The reference is raised to REF_TARGET over its peak of the last ~100 s (REF_PEAK_HOLD per block), up to REF_GAIN_CAP,
# never clipped; a steady gain is part of the echo path AEC3 learns, so it changes only when the sound gets louder.
REF_TARGET = 0.5
REF_PEAK_HOLD = 0.999
REF_GAIN_CAP = 100.0
# F44 (2026-11-04): the installer's spoken welcome said «Baxy» a second after minutes of silence, and BAXY answered it 4
# times out of 6, with the stage on: AEC3 counts as still learning for its first ~5 s of adapted audio (aec_state.cc), and
# took 3 dB out of that second. No canceller knows a room in a second, but what was played is known: voice.py asks the same
# detector about the reference (PLAYED_*) before a firing opens a request, as devices do on their playback path (US
# 11,004,453; US 10,832,671). Figures: documentacion/CANCELACION_DE_ECO.md.
PLAYED_KEEP_BLOCKS = 300    # the microphone's 100 ms blocks of what was played that are kept: a request's longest (MAX_S)
PLAYED_KEEP_S = PLAYED_KEEP_BLOCKS * 0.1
PLAYED_BACK_S = 4.0         # how much before a firing the reference is read: the detector needs the context
PLAYED_NEAR_S = 1.5         # a word on the reference this close to the firing is the same word (they differed 0.04-0.6 s)
# How long after the firing the reference is read: the package decides a candidate on the audio up to 0.5 s after it.
# 0.1 s heard 6 of 13 played words, 0.5 s 11, 1 s 12 (scripts/voice/medir_disparos.py). A package can ask for less in
# its config.json (played_hold_s, voice.load_wake): a causal detector has no candidate to decide later.
PLAYED_HOLD_S = 1.0


def wanted(setting: bool) -> bool:
    """The owner's switch, unless BAXY_ECHO_CANCEL=0 turns the stage off on this PC."""
    return setting and os.environ.get("BAXY_ECHO_CANCEL", "1").strip() != "0"


class Resampler:
    """A stream at ``rate_in`` as ``rate_out`` (polyphase FIR, linear phase), chunk after chunk without seams."""

    def __init__(self, rate_in: int, rate_out: int) -> None:
        ratio = Fraction(rate_out, rate_in).limit_denominator(1000)
        self._up, self._down = ratio.numerator, ratio.denominator
        width = max(self._up, self._down)
        taps = TAPS_PER_PHASE * width + 1
        self._filter = Polyphase(lowpass(taps, 0.9 / width, np.hamming(taps)) * self._up, self._up, self._down)
        # Input kept for the filter's support; dropped only a whole ``down`` at a time, so the output phase holds.
        self._keep = -(-taps // self._up) + self._down
        self._history = np.zeros(self._keep, np.float32)
        self._next = -(-(taps - 1) // self._down)  # the first output whose support is all real input

    def __call__(self, chunk: np.ndarray) -> np.ndarray:
        audio = np.concatenate([self._history, chunk.astype(np.float32, copy=False)])
        last = (len(audio) * self._up - 1) // self._down
        out = self._filter(audio)[self._next:last + 1]
        drop = max(0, (len(audio) - self._keep) // self._down * self._down)
        self._history = audio[drop:]
        self._next = last + 1 - drop * self._up // self._down
        return out


class Loopback:
    """What the default output device plays, as mono at ``rate``; silence when nothing plays (WASAPI sends nothing)."""

    def __init__(self, rate: int) -> None:
        import pyaudiowpatch as pa
        self._lock = threading.Lock()
        self._held: deque[np.ndarray] = deque()
        self._samples = 0
        self._rate = rate
        self.trimmed = 0                # samples dropped to keep the lead (SLACK_HIGH_S); measured, never used to decide
        self._audio = pa.PyAudio()
        try:
            device = self._audio.get_default_wasapi_loopback()
            source = int(device["defaultSampleRate"])
            self._channels = int(device["maxInputChannels"])
            self._resample = Resampler(source, rate)
            self._stream = self._audio.open(format=pa.paFloat32, channels=self._channels, rate=source, input=True,
                                            input_device_index=device["index"], frames_per_buffer=source // 100,
                                            stream_callback=self._heard)
            self.name = str(device["name"])
        except BaseException:
            self._audio.terminate()
            raise
        self._continue = pa.paContinue

    def _heard(self, data: bytes, _frames: int, _time: Any, _status: int) -> tuple[None, int]:
        audio = np.frombuffer(data, np.float32).reshape(-1, self._channels).mean(axis=1)
        out = self._resample(audio)
        with self._lock:
            self._held.append(out)
            self._samples += len(out)
        return None, self._continue

    def take(self, count: int) -> np.ndarray:
        """The ``count`` oldest samples held, after dropping what makes the lead too long; zeros before what came when
        less is held (a song that just started)."""
        with self._lock:
            if self._samples > count + SLACK_HIGH_S * self._rate:
                self._drop(self._samples - count - int(SLACK_LOW_S * self._rate))
            parts: list[np.ndarray] = []
            need = count
            while need and self._held:
                head = self._held[0]
                if len(head) <= need:
                    parts.append(self._held.popleft())
                    need -= len(head)
                else:
                    parts.append(head[:need])
                    self._held[0] = head[need:]
                    need = 0
            self._samples -= count - need
        return np.concatenate([np.zeros(need, np.float32), *parts])

    def _drop(self, count: int) -> None:
        self.trimmed += count
        self._samples -= count
        while count:
            head = self._held[0]
            if len(head) <= count:
                self._held.popleft()
                count -= len(head)
            else:
                self._held[0] = head[count:]
                count = 0

    def close(self) -> None:
        try:
            self._stream.close()
        finally:
            self._audio.terminate()


class ReferenceGain:
    """The reference raised to REF_TARGET over its recent peak (REF_PEAK_HOLD), at most REF_GAIN_CAP. The peak ages only
    while something plays: the gain is part of the path AEC3 learned, and a silence is no reason to change it."""

    def __init__(self) -> None:
        self._peak = 0.0

    def __call__(self, reference: np.ndarray) -> np.ndarray:
        if len(reference) and reference.any():
            self._peak = max(self._peak * REF_PEAK_HOLD, float(np.max(np.abs(reference))))
        return reference * np.float32(min(REF_GAIN_CAP, REF_TARGET / max(self._peak, 1e-9)))


class EchoCanceller:
    """AEC3 on the microphone's blocks (a whole number of FRAMEs), each with the loopback's reference taken as it
    arrives; what is heard is its linear output (the echo path's estimate subtracted), not its final one, whose
    suppressor also takes the person's voice when both sound: with a song under them, 40 Chilean requests were
    transcribed with 19.5 % of words wrong from the linear output, 34.8 % from the final one, 31.2 % without AEC
    (scripts/voice/medir_eco.py, 2026-11-03). runtime_wheels' pywebrtc-audio exposes it (last_linear_frame), as BAXY
    Definitivo chose it for recognition. Called from one thread at a time (the microphone's callback), as AEC3 asks."""

    def __init__(self, rate: int, reference: Callable[[int], np.ndarray]) -> None:
        from pywebrtc_audio import EchoCanceller as Aec3
        self._aec = Aec3(rate, 1, 0)
        self._reference = reference
        self._gain = ReferenceGain()
        self._rate = rate
        self._kept: deque[np.ndarray] = deque(maxlen=PLAYED_KEEP_BLOCKS)

    def __call__(self, block: np.ndarray) -> np.ndarray:
        played = self._reference(len(block))
        self._kept.append(played)
        far = self._gain(played)
        out = np.empty_like(block)
        for at in range(0, len(block), FRAME):
            self._aec.process(block[at:at + FRAME], far[at:at + FRAME])
            out[at:at + FRAME] = self._aec.last_linear_frame()
        return out

    def played(self, seconds: float) -> np.ndarray:
        """The last ``seconds`` the PC played, as the loopback gave them (all zeros when nothing played). Any thread:
        the microphone's callback only appends."""
        kept = list(self._kept)
        audio = np.concatenate(kept) if kept else np.zeros(0, np.float32)
        return audio[-int(seconds * self._rate):]


class Stage(NamedTuple):
    """What the microphone's opening holds: each block through the canceller, the closing, and what was played."""
    cancel: Callable[[np.ndarray], np.ndarray]
    close: Callable[[], None]
    played: Callable[[float], np.ndarray]


def open_stage(rate: int) -> Stage | None:
    """The stage for a microphone opened now; None (said on stderr) when the loopback does not open: the microphone is
    heard as before."""
    try:
        loopback = Loopback(rate)
    except Exception as error:  # noqa: BLE001 - no loopback (no output device, no WASAPI): the ear works without it
        sys.stderr.write(f"baxy_mind_renew_voice: echo cancellation off: {error!r}\n")
        sys.stderr.flush()
        return None
    try:
        canceller = EchoCanceller(rate, loopback.take)
    except Exception as error:  # noqa: BLE001 - AEC3 missing from the runtime: the same
        loopback.close()
        sys.stderr.write(f"baxy_mind_renew_voice: echo cancellation off: {error!r}\n")
        sys.stderr.flush()
        return None
    sys.stderr.write(f"baxy_mind_renew_voice: echo cancellation on: {loopback.name}\n")
    sys.stderr.flush()
    return Stage(canceller, loopback.close, canceller.played)
