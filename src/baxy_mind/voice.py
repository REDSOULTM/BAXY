"""Voice for BAXY Renew: the microphone, the k4 wake word and Parakeet Ultra (sherpa-onnx, CPU), and BAXY's voice
speaking (Supertonic, voice_output.py).

Only the connection: what the person says after «Baxy» reaches the App as voice.transcript, the same as a typed
message. The segmentation is WakewordBaxy/probar_baxy.py's, measured there with the owner's voice, with Silero VAD
telling voice from steady noise (Vad); the recognizer is TranscripcionBaxy's winner with its configuration. While BAXY
speaks the microphone is not heard, as in Definitivo, so its own voice («Hola, soy BAXY») never wakes it or enters a
request. What the PC plays (a song, a video) is taken out of each block before anything hears it (voice_echo.py).

Paths (per PC): BAXY_RENEW_WAKE_DIR (the baxy-wake-k4 package), BAXY_RENEW_WAKE_FAST_DIR (uso-79, on by default
since uso-93: k6r-alto, a low-latency package heard beside it, the first to fire telling «Baxy»; the App sets it, as the
wake's, from the registration's renew_wake_fast_dir; ``none`` turns it off), BAXY_RENEW_STT_DIR (parakeet-ultra-sherpa-int8-oli),
BAXY_RENEW_MIC (an input device index; otherwise Windows' default microphone of the moment, through the MME
sound mapper, as the voice's output). Benches: BAXY_RENEW_VOICE_FEED hears WAV files
in its place, in real time (voice_feed.py, scripts/voice/hablar.py). Development: BAXY_WAKE_LOG_DIR keeps each «Baxy»
heard there (WakeLog); without it nothing is written.
"""
from __future__ import annotations

import copy
import datetime
import difflib
import hashlib
import importlib.util
import json
import math
import os
import queue
import re
import sys
import tempfile
import threading
import time
import unicodedata
import wave
from pathlib import Path
from typing import Any, Callable, NamedTuple

import numpy as np

from . import stt_hotwords, voice_echo, voice_feed, voice_turn
from .voice_output import EAR_COMMIT_MB, NotEnoughMemory, Speech, default_follower, native_load

RATE = 16000
BLOCK = 1600            # 100 ms
BEFORE_S = 2.0          # audio before the trigger that goes into the transcription
VOICE_RMS = 0.012       # voice threshold of TranscripcionBaxy/probar_ultra.py
SPEECH_P = 0.5          # Silero's own speech threshold (0.3 and 0.7 closed the same requests within 0.1 s)
VAD_STEP = 512          # Silero's window at 16 kHz (32 ms); sherpa-onnx gives it the 64 samples before as context
# VOZ1: Silero is recurrent, and its state drifts on a long steady sound: after 30-120 s of BAXY's own alarm (Alarm01.wav
# through the simulated room of ALR1), a voice said over it was heard as speech in 0.0-0.3 of its windows on the
# microphone and 0.24-0.7 after the canceller, against 0.8-0.9 with the state freshly reset; a request said over a
# ringing alarm then had no voice and was dropped. Silero's authors: the model «isn't» stateless, reset_states() between
# streams (snakers4/silero-vad#538, 2024-09); Pipecat resets it once VAD_RESET_S of audio passed since the last reset
# and VAD_RESET_QUIET windows in a row were not speech (src/pipecat/audio/vad/silero.py, _maybe_reset_model;
# v0.0.90 reset it every 5 s). Measured with that rule: 0.78-0.87 over the alarm, a clean voice as before (0.88-0.90).
# Pipecat resets once the user's turn is over; here, only while no request is open (Vad.marks ``settle``): a reset in a
# 0.7 s pause inside one of the owner's requests heard his soft words after it too late, and the request was cut.
VAD_RESET_S = 2.0
VAD_RESET_QUIET = 5
END_SILENCE_S = 0.9     # silence that closes the request
# A request whose early transcript (palanca 2, decoded 0.2 s into the silence) is left hanging (a preposition, article,
# conjunction, filler or comma at its end) waits END_SLOW_S instead of END_SILENCE_S, so a slow speaker is not cut
# (real use, 2026-10-26). LiveKit's turn detector waits up to 2.5-3 s when the turn is not complete, Pipecat Smart Turn
# 3 s; Amazon (Maas et al. 2018) reads the last words («a transcript ending in a preposition means more is coming»).
# A shorter wait when the words look ended (0.4-0.75 s, as LiveKit's 0.3 s) was measured and left out: Ultra writes a
# period after any fragment, and on 57 synthetic requests with a 0.7 s pause inside, 35-47 % were cut there against
# ~10 % at 0.9 s, for 0.1-0.3 s less wait.
END_SLOW_S = 2.0
# Fin de turno (uso-74, scripts/voice/medir_fin_de_turno.py): with the turn model (voice_turn.py, Smart Turn v3.2),
# TURN_AT_S into a silence it hears the request so far, as Pipecat runs it after its VAD's 0.2 s stop. A turn it hears
# complete (TURN_P, Pipecat's threshold) closes after END_DONE_S; one it is sure is unfinished (under TURN_OPEN_P) after
# END_SLOW_S (Pipecat and LiveKit wait up to 3 s); in between, after END_UNSURE_S. It reads how the voice ends; words
# left hanging (above) still wait END_SLOW_S, the longer of the two. Measured on 440 synthetic requests (5 OneCore
# voices, pauses of 0.6/1.0/1.5 s inside) and 58 of the owner's requests: END_DONE_S 0.7 cut 30 % of the 0.6 s pauses,
# 0.8 cuts 7 % as the rule's 4-5 %. Two waits alone (0.8 / 2.0) cut fewer but kept 12 % of the owner's finished
# requests 2 s: the model heard short greetings and one-word orders unfinished, five of those seven between 0.1 and 0.5.
# The model alone cut 25.5 % of the pauses after hanging words (the rule, 9.2 %): hence the longer of the two (cut in
# a pause 27.5 → 21.4 % in a quiet room against the rule, 7.8 % after hanging words; the owner's p50 0.9 → 0.8 s). An
# unsure wait of 1.5 s cut no fewer than 1.2 s and waited longer. Asking it again later in the silence was left out:
# silence alone makes it say complete, mid-sentence too. Under steady noise (pink, 10 dB) it hears almost every pause
# complete: where the floor of the request is loud (loud_floor) the rule without it decides.
TURN_AT_S = 0.2
TURN_P = 0.5
TURN_OPEN_P = 0.1
END_DONE_S = 0.8
END_UNSURE_S = 1.2
HANGING_WORDS = frozenset(
    "el la los las un una unos unas lo al del a de en con por para sin sobre entre hasta desde hacia segun y e o u ni "
    "pero sino que porque si cuando como aunque donde mientras mi mis tu tus su sus nuestro me te se le les eh em mm "
    "este esto bueno pues tipo the an to of and but or so because um uh like my your".split())
HANGING_ENDS = frozenset({"o sea", "a ver", "voy a", "hay que", "es que", "i mean", "quiero que", "puedes"})
WORD_TAIL_S = 0.4       # voice in the first 0.4 s after the trigger is the end of «Baxy», not the request
# VOZ1 (DEP6, 2026-11-09: «Baxi, gracias» said in one breath gave no turn): the tail was set for k4, which fired a chunk
# after the word; v7a decides every 40 ms and fires 0.14 s p50 after it (its README), so a short request said with no
# pause lies wholly inside the tail (on BAXY's voice, its words began 0.0-0.24 s after the trigger) and was dropped
# untranscribed. Time alone cannot tell Silero's hold of «Baxy» from a word begun at the trigger; the recognizer can,
# with the same cut by time as every transcript (Voice._said_in_tail). Home Assistant keeps the audio around the
# detection for STT for the same reason («Wake-word-detection occurs *after* the wake word was actually spoken. Keeping
# audio right before detection allows the voice command to be spoken immediately after the wake word»,
# homeassistant/components/assist_pipeline/pipeline.py, 2025.6.0).
# The same where the room is loud by itself (Voice._noisy): loudness no longer trims Silero's hold of the word, which
# reached 0.5 s past the trigger at 10 dB and 0.7 s at 5 dB (0.2 s in a quiet room; 50 «Baxi» + request, OneCore).
NOISY_TAIL_S = 0.8
CALL_LEAD_S = 0.25      # a word that began this long before the trigger is the call (or came before it)
# Whose voice ends the request (real use, 2026-10-26: a TV or people talking behind kept requests open and went into the
# transcript, and soft voices on a notebook's microphone, under VOICE_RMS, waited for NO_COMMAND_S or were cut in their
# pauses): a block counts when Silero hears speech in it and it is no more than SPEAKER_DB under the level of the one
# who speaks (Voice._speaker_level). Maas et al., «Anchored speech detection» (Interspeech 2016), anchor on the wake
# word; Rhasspy's VAD_AND_RATIO and Pipecat's volume gate use a ratio too. On 57 synthetic requests in direct mode
# (2026-10-26): soft (-16 dB) closed 0.8 s after the voice instead of 4.3 s, with none cut; with other people talking
# 10-20 dB under it, as soon or sooner and with fewer stray words than VOICE_RMS (15 and 12 dB let more of them in);
# clean and pink noise as before.
SPEAKER_DB = 10.0
SPEAKER_FLOOR = 0.004   # under this nothing is voice, however soft the speaker
CALL_BACK_S = 1.0       # in wake mode the speaker's level is looked for from this long before the trigger: «Baxy»
MIN_VOICE_S = 0.1       # no block of voice after the call: noise or a false wake, nothing is transcribed
# A word whose least sure token is under this probability is told to the mind as unsure (Heard.unsure). Measured on the
# notebook (2026-10-27; beam with the hotwords, as here): 113 human recordings, 540 synthetic requests and 480 short
# replies (one to three words) in four OneCore voices, clean, pink noise at 10 and 5 dB and babble at 5 dB. Some word
# under 0.5 in 5 % of the human transcripts heard right against 25 % of those heard wrong (10 % and 44-46 % on the
# synthetic ones; 0.3 marks 2-7 % against 12-18 %); greedy, without hotwords, alike (5 % against 26 %). Hotword tokens
# score over 1 and count as sure. A wrong word heard sure stays unmarked: a greeting heard as another word in pink noise
# scored 0.62-0.78.
# Not used to drop a transcript: a one-syllable piece cut from a phrase is as sure as a short reply (under 0.3, 11 % of
# 476 pieces against 3 % of 226 replies heard right), so dropping by it loses replies without stopping the pieces.
UNSURE_P = 0.5
# F44: words of a request that are what the PC played over the same time (Heard.without_played). Three in a row is a
# phrase; two («abre la») a person can share with a video by chance.
PLAYED_RUN = 3
PLAYED_SAME_WORD = 0.7
# Ultra decodes on the thread that hears the blocks (0.4 s for 4 s of audio, 1.4-1.6 s for 14 s on the notebook,
# 2026-10-26), and a live caption decoded the whole request again every PARTIAL_S: the thread fell behind the microphone,
# so the end of the request and the next «Baxy» were heard seconds late. A caption waits while more than this many
# blocks wait (the early and the final transcripts, one per pause and one per request, do not).
BEHIND_BLOCKS = 1
NO_COMMAND_S = 4.0      # after the trigger, time for the request to start
DIRECT_WAIT_S = 6.0     # direct mode (microphone button): time for the request to start
MAX_S = 12.0
KEEP_S = 30.0
# An open microphone sends a block every 100 ms, BAXY speaking or not; one that sends nothing this long (unplugged, its
# driver gone) is opened again on the default microphone of the moment, and a failed opening turns the ear off, told.
STALL_S = 3.0
PARTIAL_S = 0.8         # while a request is heard, what was said so far is decoded again this often (live captions)
WAKE_COPIES = 4         # staggered copies (StaggeredWake): 0.28 s p50 after the word, 0.46 s at most (1 copy: 1.18, 1.36)
# The copies run one after another on the thread that hears the blocks, so a chunk's encoder run is part of the wait.
# Two threads per run (uso-68, 2026-11-03): a chunk 142 → 80 ms p50 (216 → 95 p90) on the notebook with the same CPU,
# 131-179 → 107-136 ms on the PC (+~25 % CPU); the same firings on the owner's real calls and the hard negatives
# (documentacion/APLAZADOS.md, uso-68). More copies were not taken: each adds a chunk's run to that one thread (6 copies:
# 69 % of a core on a quiet PC), and with a loaded PC's chunk it fell seconds behind.
WAKE_THREADS = 2
# The detector heard the microphone as it came, while Ultra hears it with probar_ultra's gain: in a room, a few metres
# from the notebook, «Baxi» peaked at 0.07 (real use, 2026-10-26) against ~0.96 in the owner's recordings the detector
# was trained on, and it never reached 0.1. What it hears is raised the same way (WAKE_TARGET over the peak of the last
# ~3 s, WAKE_PEAK_DECAY per block), up to WAKE_GAIN_CAP: on 80 of the owner's «Baxi» at a twentieth of their level,
# 60 → 77 heard; a cap of 8 heard the same and fired more on the recorded false fires of loud speech.
WAKE_TARGET = 0.45
WAKE_PEAK_DECAY = 0.97
WAKE_GAIN_CAP = 4.0
# The detector's feature extractor keeps every frame since its last reset (9.6 MB of the mind's memory per minute of
# audio, four copies; real use, 2026-10-26: +120 MB in 15 min without a request), and it was reset only when a request
# opened or BAXY spoke. With no request open, after WAKE_RESET_S of it and WAKE_QUIET_S without speech, it starts
# afresh, as it does when BAXY speaks: no word is cut.
WAKE_RESET_S = 60.0
WAKE_QUIET_S = 1.5


def wake_gain(peak: float, block: np.ndarray) -> tuple[float, np.ndarray]:
    """The recent peak with ``block`` heard, and ``block`` raised for the detector (WAKE_TARGET), never clipped."""
    peak = max(peak * WAKE_PEAK_DECAY, float(np.max(np.abs(block))) if len(block) else 0.0)
    return peak, block * min(WAKE_GAIN_CAP, WAKE_TARGET / max(peak, 1e-6))
NAMES_WAIT_S = 30.0     # the recognizer waits this long for catalog.configure's names (they come before voice.start)
HOTWORDS_PATHS = 4      # beam width when the names are hotwords
# Score per token of the names (scripts/voice/medir_hotwords.py, 1366 synthetic utterances, 2026-10-23): installed names
# heard 562 → 744 of 1012 (greedy → 1.5; 752 at 2, 767 at 3), WER 18.97 → 13.43 %, sentences without a name 2.96 →
# 3.41 % (spellings: «wifi» → «Wi-Fi»), names not installed 62 → 49 of 100, no name inserted, no empty result, decode
# p50 220 → 195 ms. 1.5 keeps almost all of the gain and costs less to the names not installed than 2 or 3.
HOTWORDS_SCORE = 1.5


# «Baxy» heard as a word of the request (real use, 2026-10-26): when the wake answered late the person called again, and
# «Baxi.», «Paksi.» or «Maxi, …» reached the mind as what they asked — the same greeting again, a site named Paksi
# opened, the person called Maxi. The call is how the request is addressed, never part of it: the words at its start
# that sound like it go, and a request that was only the call is not told.
CALL_WORDS = re.compile(r"^(?:[\W_]*[bpvm]a(?:x|ks|cs|k|c)s?[iíy]\b)+[\W_]*", re.IGNORECASE)


def without_call(text: str) -> str:
    """The request without the call at its start (CALL_WORDS)."""
    return CALL_WORDS.sub("", text).strip()


def _folded(word: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", word.casefold()) if c.isalnum())


def _same_word(ours: str, theirs: str) -> bool:
    """The same word, or one the recognizer wrote a little differently from the two sides of a canceller («Paxi», «Baxi»)."""
    if ours == theirs:
        return True
    return min(len(ours), len(theirs)) >= 4 and difflib.SequenceMatcher(None, ours, theirs).ratio() >= PLAYED_SAME_WORD


def _words_in_order(ours: list[str], theirs: list[str]) -> list[int]:
    """The indices of ``ours`` in the longest common subsequence with ``theirs``."""
    best = [[0] * (len(theirs) + 1) for _ in range(len(ours) + 1)]
    for i in range(len(ours) - 1, -1, -1):
        for j in range(len(theirs) - 1, -1, -1):
            best[i][j] = (best[i + 1][j + 1] + 1 if _same_word(ours[i], theirs[j])
                          else max(best[i + 1][j], best[i][j + 1]))
    found, i, j = [], 0, 0
    while i < len(ours) and j < len(theirs):
        if _same_word(ours[i], theirs[j]):
            found.append(i)
            i, j = i + 1, j + 1
        elif best[i + 1][j] >= best[i][j + 1]:
            i += 1
        else:
            j += 1
    return found


def _runs(indices: list[int]) -> list[list[int]]:
    runs: list[list[int]] = []
    for index in indices:
        if runs and runs[-1][-1] == index - 1:
            runs[-1].append(index)
        else:
            runs.append([index])
    return runs


class Heard(NamedTuple):
    """A transcript and how sure Parakeet was of each of its words: per word of ``text`` (split on spaces), the
    probability of its least sure token with a letter or digit (ys_log_probs; 1.0 for bare punctuation). No words when
    the recognizer gave no probabilities or they do not match the words of ``text``: nothing is said of it then."""
    text: str
    words: tuple[tuple[str, float], ...] = ()

    @classmethod
    def of(cls, text: str, tokens: list[str], log_probs: list[float]) -> Heard:
        """``text`` as Parakeet wrote it from ``tokens`` (each word begins with a space), sure as ``log_probs`` say."""
        words: list[list[Any]] = []
        for token, log_p in zip(tokens, log_probs):
            p = math.exp(log_p) if re.search(r"[^\W_]", token) else 1.0
            if token.startswith(" ") or not words:
                words.append([token, p])
            else:
                words[-1][0] += token
                words[-1][1] = min(words[-1][1], p)
        words = [[word.strip(), p] for word, p in words if word.strip()]
        aligned = len(log_probs) == len(tokens) and [word for word, _ in words] == text.split()
        return cls(text, tuple((word, p) for word, p in words) if aligned else ())

    def unsure(self) -> list[tuple[str, float]]:
        """The words the ear is not sure of (UNSURE_P), as the mind is told them."""
        return [(word, p) for word, p in self.words if p < UNSURE_P]

    def without_call(self) -> Heard:
        """The request without the call at its start (CALL_WORDS), its words with it."""
        text = without_call(self.text)
        words = self.words[len(self.words) - len(text.split()):] if text else ()
        return Heard(text, words if [word for word, _ in words] == text.split() else ())

    def without_played(self, played: str) -> Heard:
        """F44: this request without what the PC was saying meanwhile: a person called and a video went on «apaga el
        computador»; the canceller left it all, and the mind would have obeyed the video. ``played``: the recognizer on
        what was played over the same time. Taken out: the runs of PLAYED_RUN words or more found in it in order, or the
        whole request if it is all there. Only form: the words are compared, nobody reads what they ask."""
        ours, theirs = self.text.split(), played.split()
        if not ours or not theirs:
            return self
        found = _words_in_order([_folded(word) for word in ours], [_folded(word) for word in theirs])
        drop = set(found) if len(found) == len(ours) else {i for run in _runs(found) if len(run) >= PLAYED_RUN for i in run}
        if not drop:
            return self
        sys.stderr.write(f"baxy_mind_renew_voice: {len(drop)} of {len(ours)} words of a request were what the PC played\n")
        sys.stderr.flush()
        kept = [i for i in range(len(ours)) if i not in drop]
        return Heard(" ".join(ours[i] for i in kept),
                     tuple(self.words[i] for i in kept) if len(self.words) == len(ours) else ())


def end_silence(early: str | None) -> float:
    """The silence that closes the request after these early words: END_SLOW_S when they are left hanging."""
    text = (early or "").strip()
    folded = "".join(c for c in unicodedata.normalize("NFKD", text.casefold()) if not unicodedata.combining(c))
    words = re.findall(r"[^\W\d_]+", folded)
    if not words:
        return END_SILENCE_S
    if (text.endswith((",", "…", ":", "...")) or words[-1] in HANGING_WORDS or words[-1] in HANGING_ENDS
            or " ".join(words[-2:]) in HANGING_ENDS):
        return END_SLOW_S
    return END_SILENCE_S


def hotwords_score() -> float:
    """The score per token of the names as hotwords (BAXY_RENEW_STT_HOTWORDS); 0 is the greedy recognizer alone."""
    try:
        return max(0.0, float(os.environ.get("BAXY_RENEW_STT_HOTWORDS", HOTWORDS_SCORE)))
    except ValueError:
        return HOTWORDS_SCORE


class StaggeredWake:
    """The k4 detector heard «Baxy» only when its encoder finished a 1.28 s chunk: 1.18 s p50 (1.36 s at most) after the
    word ended (owner, 2026-10-20: «suena después y ya perdí lo que le iba a decir»). Several copies, each a fraction of
    a chunk behind the one before, finish a chunk that much more often; each is the same detector on the same audio, and
    a firing of any of them counts once (the package's own re-arm, 2 s). Times are the audio's own, as the package's.

    Only the first copy is built: the others are shallow copies of it, so all of them run the same ONNX sessions (an
    encoder session holds no audio, its state goes in and out with each chunk) and each has its own state from reset().
    Four own sessions held 845 MiB of the mind's private memory, shared ones 254 MiB, with the same firings at the same
    times (CPU probe on synthetic requests, renew al máximo, 2026-10-23)."""

    def __init__(self, make: Callable[[], Any], copies: int, rearm_s: float) -> None:
        first = make()
        self._copies = [first] + [copy.copy(first) for _ in range(copies - 1)]
        chunk_s = self._copies[0].shift * 0.01   # fbank frames of 10 ms
        self._lead = [k * chunk_s / copies for k in range(copies)]
        self._rearm_s = rearm_s
        self.reset()

    def twin(self) -> StaggeredWake:
        """The same detector with a state of its own (its ONNX sessions shared, so no memory beyond that state): F44,
        what the PC played is heard apart from the microphone."""
        other = copy.copy(self)
        other._copies = [copy.copy(detector) for detector in self._copies]
        other.reset()
        return other

    def reset(self) -> None:
        self._last = -1e9
        for detector, lead in zip(self._copies, self._lead):
            detector.reset()
            if lead:
                detector.accept(np.zeros(int(lead * RATE), np.float32))

    def accept(self, block: np.ndarray) -> list[Any]:
        heard = []
        for detector, lead in zip(self._copies, self._lead):
            for detection in detector.accept(block):
                detection.time_s -= lead
                if detection.time_s - self._last >= self._rearm_s:
                    self._last = detection.time_s
                    heard.append(detection)
        return heard

    def scores(self) -> list[tuple[float, float]]:
        """(time, probability) of each frame the first copy scored since the last call, when its detector keeps them
        (the package's ``trace``, which reset() turns off); from this call on it keeps them. The first copy has no lead,
        so its times are the audio's own; the others score the same audio."""
        first = self._copies[0]
        scored = getattr(first, "trace", None) or []
        first.trace = []
        return list(scored)


class _IdleThreadsSleep:
    """The wake package's onnxruntime with one change: its sessions' idle intra-op threads sleep instead of spinning
    (session.intra_op.allow_spinning, on by default; https://onnxruntime.ai/docs/performance/tune-performance/
    threading.html). Two spinning threads tripled a copy's CPU (0.108 → 0.334 of a core) for the same chunk time."""

    def __init__(self, ort: Any) -> None:
        self._ort = ort

    def __getattr__(self, name: str) -> Any:
        return getattr(self._ort, name)

    def SessionOptions(self) -> Any:  # noqa: N802 - onnxruntime's own name
        options = self._ort.SessionOptions()
        options.add_session_config_entry("session.intra_op.allow_spinning", "0")
        return options


def wake_threads() -> int:
    """The wake encoder's threads (BAXY_RENEW_WAKE_THREADS; 1 is the detector as before uso-68)."""
    value = os.environ.get("BAXY_RENEW_WAKE_THREADS", "")
    try:
        return max(1, int(value)) if value else WAKE_THREADS
    except ValueError:
        return WAKE_THREADS


def load_wake(wake: Path) -> StaggeredWake:
    """The wake package of ``wake`` (BAXY_RENEW_WAKE_DIR) as StaggeredWake: WAKE_COPIES copies of its detector, its
    encoder on wake_threads() threads that sleep when idle. A package whose config.json names its ``copies`` and
    ``threads`` gets those (uso-79, k6r: one copy on one thread, as it was measured; it decides every 40 ms), and
    ``played_hold_s`` is how long F44 holds its firings (voice_echo.PLAYED_HOLD_S when it names none)."""
    spec = importlib.util.spec_from_file_location("baxy_wake_k4", wake / "baxy_wake_runtime.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["baxy_wake_k4"] = module
    spec.loader.exec_module(module)
    module.ort = _IdleThreadsSleep(module.ort)
    config = json.loads((wake / "config.json").read_bytes())  # JSON is UTF-8 (RFC 8259)
    threads = int(config.get("threads") or wake_threads())
    loaded = StaggeredWake(lambda: module.BaxyWakeDetector(
        wake / config["encoder"]["file"], wake / config["head"]["file"], threshold=config["threshold"],
        debounce_s=config["debounce_s"], threads=threads), int(config.get("copies") or WAKE_COPIES),
        float(config["debounce_s"]))
    loaded.played_hold_s = float(config.get("played_hold_s") or voice_echo.PLAYED_HOLD_S)
    return loaded


class _HeldCall(NamedTuple):
    """F44: a firing with the PC playing: when the word was, its detection and when to check it (seconds heard)."""
    start: float
    detection: Any
    due: float


class EitherWake:
    """uso-79: k5 (StaggeredWake) and the low-latency package of BAXY_RENEW_WAKE_FAST_DIR hear the same blocks, and a
    «Baxy» is told by whichever fires first, once: a firing within the re-arm of the last one told, before or after it,
    is the same word. k5 is as without it, and its frames are the ones scored (scores, the wake log's near misses).
    k6r at its package threshold (logit 9.137) fired first on 58 of the owner's 73 calls that k5 heard, and heard none
    k5 missed: p50 0.135 s after the word (k5 alone 0.349), p90 0.345 (0.969); no firing of its own in 138 h of dev
    streams nor in the room (WakewordBaxy/PLAN_K6_RAPIDO.md, informe 79 de c5)."""

    def __init__(self, main: StaggeredWake, fast: StaggeredWake) -> None:
        self._main = main
        self._fast = fast
        self._rearm_s = main._rearm_s
        self.played_hold_s = getattr(main, "played_hold_s", voice_echo.PLAYED_HOLD_S)  # its twin is k5's: k5's hold
        self._last = -1e9

    def twin(self) -> StaggeredWake:
        """F44: k5 alone hears what the PC played: on the same clean words k6r heard 13 of 44, and added none to k5's 37."""
        return self._main.twin()

    def reset(self) -> None:
        self._last = -1e9
        self._main.reset()
        self._fast.reset()

    def accept(self, block: np.ndarray) -> list[Any]:
        heard = []
        for detection in sorted(self._main.accept(block) + self._fast.accept(block), key=lambda d: d.time_s):
            if abs(detection.time_s - self._last) >= self._rearm_s:
                self._last = detection.time_s
                heard.append(detection)
        return heard

    def scores(self) -> list[tuple[float, float]]:
        return self._main.scores()


def load_fast_wake() -> StaggeredWake | None:
    """uso-79: the package of BAXY_RENEW_WAKE_FAST_DIR (k6r, a causal detector that fires at the word's end instead of
    a chunk later), heard beside k5's (EitherWake). uso-93: on by default, the App giving the registered package. None
    when it is not set (a machine without the package), is ``none`` (a bench, or whoever wants it off), or does not
    load (told on stderr): k5 is heard alone, as before."""
    folder = os.environ.get("BAXY_RENEW_WAKE_FAST_DIR", "").strip()
    if not folder or folder.lower() == "none":
        return None
    try:
        fast = load_wake(Path(folder))
        sys.stderr.write(f"baxy_mind_renew_voice: BAXY_RENEW_WAKE_FAST_DIR: {Path(folder).name} heard beside the "
                         "wake word\n")
        sys.stderr.flush()
        return fast
    except Exception as error:  # noqa: BLE001 - k5 is heard alone
        sys.stderr.write(f"baxy_mind_renew_voice: BAXY_RENEW_WAKE_FAST_DIR: {error!r}; k5 is heard alone\n")
        sys.stderr.flush()
        return None


# Development only (WakeLog, BAXY_WAKE_LOG_DIR): the clip kept of each «Baxy», this long before the trigger and after
# it; and the near misses, frames scored from NEAR_MISS_P up to under NEAR_MISS_TOP (the package's threshold), at most one
# in NEAR_MISS_GAP_S and none that near a firing. A near miss is kept once no firing can still come for it: a copy tells a
# firing up to a chunk and the lookahead (1.28 + 0.155 s) after its frame.
WAKE_LOG_S = 4.0
NEAR_MISS_P = 0.2
NEAR_MISS_TOP = 0.5
NEAR_MISS_GAP_S = 2.0
NEAR_MISS_LATE_S = 1.5
WAKE_LOG_RECENT_S = 12.0  # the audio kept for a clip's start: WAKE_LOG_S before a near miss told this late


def package_sha256(folder: Path) -> str | None:
    """A folder's SHA-256 as the App's MindRuntimeDiscovery.DirectorySha256 (the registration's renew_wake_sha256): of
    the UTF-8 lines «name:sha256», one per file directly in it by ordinal name, each ending in a line feed; None for a
    folder with no file."""
    lines = []
    for path in sorted((p for p in folder.iterdir() if p.is_file()), key=lambda p: p.name):
        digest = hashlib.sha256()
        with path.open("rb") as file:
            for chunk in iter(lambda: file.read(1 << 20), b""):
                digest.update(chunk)
        lines.append(f"{path.name}:{digest.hexdigest()}\n")
    return hashlib.sha256("".join(lines).encode("utf-8")).hexdigest() if lines else None


class WakeLog:
    """Encargo 15, development only: with BAXY_WAKE_LOG_DIR naming a folder, each «Baxy» heard leaves in it, under the
    day (<folder>/<YYYY-MM-DD>/), a WAV (16 kHz mono PCM16) of WAKE_LOG_S before the trigger and WAKE_LOG_S after it, and
    a JSON beside it: when (local ISO time), the machine, the detector's probability, the wake package's SHA-256
    (package_sha256), and, once the request ends, its transcript and whether it went on with one. Near misses
    (NEAR_MISS_P) too, with ``near_miss`` true. Nothing is sent anywhere. The voice's thread only keeps the blocks; a
    thread of its own writes, and a failure to write is told on stderr and the voice goes on. A clip that the
    microphone closes before WAKE_LOG_S after the trigger keeps what was heard. Every method is called under the
    voice's lock."""

    def __init__(self, folder: Path, wake_dir: Path) -> None:
        self._folder = folder
        self._recent = np.zeros(0, np.float32)
        self._clock = 0                       # samples heard since the log began
        self._clips: list[dict[str, Any]] = []  # open clips: their key, first and last sample, and the blocks so far
        self._near: tuple[float, float] | None = None  # the near miss that may still be kept: its time and probability
        self._near_last = self._hot = -1e9    # the last near miss kept and the last firing (or frame at the threshold)
        self._jobs: queue.Queue[Callable[[], None]] = queue.Queue()
        self._records: dict[str, tuple[Path, dict[str, Any]]] = {}  # the writer's own
        self._sha: str | None = None
        self._put(lambda: self._package(wake_dir))
        threading.Thread(target=self._write, name="voice-wake-log", daemon=True).start()

    @classmethod
    def from_env(cls) -> WakeLog | None:
        folder = os.environ.get("BAXY_WAKE_LOG_DIR", "").strip()
        return cls(Path(folder), Path(os.environ.get("BAXY_RENEW_WAKE_DIR", ""))) if folder else None

    def hear(self, block: np.ndarray) -> None:
        """A block from the microphone, BAXY speaking or not: it goes into the open clips, and is kept for the next. A
        near miss is kept once no firing can still come near it (NEAR_MISS_LATE_S), whether the detector hears or not
        (it does not while BAXY speaks)."""
        self._clock += len(block)
        self._recent = np.concatenate([self._recent, block])[-int(WAKE_LOG_RECENT_S * RATE):]
        for clip in list(self._clips):
            clip["blocks"].append(block)
            if self._clock >= clip["end"]:
                self._save(clip)
        if self._near is not None and self._clock / RATE - self._near[0] >= NEAR_MISS_GAP_S + NEAR_MISS_LATE_S:
            at, p = self._near
            self._near, self._near_last = None, at
            self.mark(self._clock / RATE - at, p, near_miss=True)

    def mark(self, lag_s: float, probability: float | None, near_miss: bool = False) -> str | None:
        """«Baxy» heard ``lag_s`` before the last block (or a near miss): its clip opens and its JSON is written. The key
        returned is the one turn() takes; None for a trigger older than the audio kept, which leaves nothing."""
        trigger = self._clock - int(round(lag_s * RATE))
        first = self._clock - len(self._recent)
        if trigger < first:
            return None
        begin = max(first, trigger - int(WAKE_LOG_S * RATE))
        when = datetime.datetime.now().astimezone() - datetime.timedelta(seconds=lag_s)
        key = when.strftime("%H%M%S-%f")[:-3] + ("-near" if near_miss else "")
        clip = {"key": key, "begin": begin, "trigger": trigger, "end": trigger + int(WAKE_LOG_S * RATE),
                "blocks": [self._recent[begin - first:]]}
        record = {"time": when.isoformat(timespec="milliseconds"), "machine": os.environ.get("COMPUTERNAME", ""),
                  "near_miss": near_miss, "probability": None if probability is None else round(float(probability), 4),
                  "renew_wake_sha256": None, "wav": f"{key}.wav", "before_s": None, "after_s": None,
                  "transcript": None, "continued": None, "empty": None}
        day = self._folder / when.strftime("%Y-%m-%d")
        self._put(lambda: self._start(key, day, record))
        self._clips.append(clip)
        if self._clock >= clip["end"]:
            self._save(clip)
        return key

    def turn(self, key: str, text: str, voiced: bool) -> None:
        """The request that followed ``key``'s «Baxy» ended: what it said, and whether it went on with one (when not,
        ``empty`` says whether there was no voice or no text in it)."""
        self._put(lambda: self._update(key, {"transcript": text, "continued": bool(text),
                                             "empty": None if text else "no_text" if voiced else "no_voice"}))

    def scores(self, scored: list[tuple[float, float]], fired: list[float]) -> None:
        """The detector's frames (each its lag before the last block and its probability) and its firings (lags) of
        the last block: the near miss that may be kept (hear keeps it)."""
        now = self._clock / RATE
        for lag in fired:
            self._hot = max(self._hot, now - lag)
            if self._near is not None and abs(self._near[0] - (now - lag)) < NEAR_MISS_GAP_S:
                self._near = None
        for lag, p in scored:
            at = now - lag
            if p >= NEAR_MISS_TOP:
                self._hot = max(self._hot, at)
                if self._near is not None and abs(self._near[0] - at) < NEAR_MISS_GAP_S:
                    self._near = None
            elif (p >= NEAR_MISS_P and at - self._hot >= NEAR_MISS_GAP_S and at - self._near_last >= NEAR_MISS_GAP_S
                  and (self._near is None or p > self._near[1])):
                self._near = (at, p)

    def stop(self) -> None:
        """The microphone closed: the open clips keep what was heard, and the next one starts afresh."""
        for clip in list(self._clips):
            self._save(clip)
        self._recent = np.zeros(0, np.float32)
        self._near = None

    def _save(self, clip: dict[str, Any]) -> None:
        self._clips.remove(clip)
        audio = np.concatenate(clip["blocks"])[:clip["end"] - clip["begin"]]
        before = (clip["trigger"] - clip["begin"]) / RATE
        key = clip["key"]
        self._put(lambda: self._wav(key, audio, before))

    # --- the writer's thread --------------------------------------------------------------------------------------

    def _put(self, job: Callable[[], None]) -> None:
        self._jobs.put(job)

    def _write(self) -> None:
        while True:
            job = self._jobs.get()
            try:
                job()
            except Exception as error:  # noqa: BLE001 - a log that cannot be written never stops the voice
                sys.stderr.write(f"baxy_mind_renew_voice: wake log: {error!r}\n")
                sys.stderr.flush()

    def _package(self, wake_dir: Path) -> None:
        self._sha = package_sha256(wake_dir)

    def _start(self, key: str, day: Path, record: dict[str, Any]) -> None:
        record["renew_wake_sha256"] = self._sha
        self._records[key] = (day, record)
        day.mkdir(parents=True, exist_ok=True)
        self._json(key)

    def _update(self, key: str, fields: dict[str, Any]) -> None:
        self._records[key][1].update(fields)
        self._json(key)

    def _wav(self, key: str, audio: np.ndarray, before_s: float) -> None:
        day, record = self._records[key]
        with wave.open(str(day / record["wav"]), "wb") as file:
            file.setnchannels(1)
            file.setsampwidth(2)
            file.setframerate(RATE)
            file.writeframes(np.round(np.clip(audio, -1.0, 1.0) * 32767).astype("<i2").tobytes())
        self._update(key, {"before_s": round(before_s, 3), "after_s": round(len(audio) / RATE - before_s, 3)})

    def _json(self, key: str) -> None:
        day, record = self._records[key]
        path = day / f"{key}.json"
        partial = path.with_suffix(".json.tmp")
        partial.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
        for wait in (0.05, 0.1, 0.2, 0.4, None):
            try:
                os.replace(partial, path)   # whole or not at all for whoever reads it
                return
            except PermissionError:
                if wait is None:            # Windows refuses it while the old one is open elsewhere
                    raise
                time.sleep(wait)


class Vad:
    """Which samples were heard as speech: Silero VAD v6 (silero_vad.onnx of the runtime's silero_vad package) run by
    sherpa-onnx on CPU, one window at a time as the audio comes: 0.4 ms of one core per 100 ms block, 15 MiB of private
    memory beside Ultra.

    A block is voice when it is loud (VOICE_RMS) and Silero heard speech in it (voiced). Loudness alone never heard the
    silence under steady noise: with pink noise at 10 dB SNR the floor is above VOICE_RMS in 99.6 % of the synthetic set,
    so every request ran to MAX_S (12 s), transcribing the noise too. Measured on its 683 utterances in direct mode
    (scripts/voice/medir_anticipada.py, early_s 0.2, 2026-10-23): in the clean set every request closes as before, the
    same transcripts and early transcripts; at 10 and 5 dB all close, 1.2 s p50 and 1.3 s p90 after the voice (before:
    none, at 10.3 s), none inside it, with the early transcript the request's own in 81.8 and 74.1 %; at 20 dB 19 close
    sooner than before (stray loud noise blocks no longer count), none later. In wake mode («Baxi» + request, 50,
    NOISY_TAIL_S) the same: clean as before, at 10 and 5 dB all close 1.2-1.3 s after the voice (before: none). Silero
    alone closes the clean ones 0.3 s later. An adaptive floor (k × a low percentile of the RMS heard) closed them at 10 dB with k 2 but cut 36-60 at 5 dB
    in a pause, and with k 1.5 left some to MAX_S: a direct request has no noise heard before it to learn the floor."""

    def __init__(self, sherpa_onnx: Any) -> None:
        # Al máximo (notebook, 2026-10-24): the file is found where the package lives, without running it — its
        # __init__ imports torch, 149 MiB of the mind for a path (importlib.resources.files imported it).
        spec = importlib.util.find_spec("silero_vad")
        if spec is None or not spec.submodule_search_locations:
            raise ModuleNotFoundError("silero_vad")
        model = Path(next(iter(spec.submodule_search_locations))) / "data" / "silero_vad.onnx"
        self._model = sherpa_onnx.VadModel.create(sherpa_onnx.VadModelConfig(
            silero_vad=sherpa_onnx.SileroVadModelConfig(model=str(model), threshold=SPEECH_P, min_silence_duration=0.05,
                                                        min_speech_duration=0.05, window_size=VAD_STEP),
            sample_rate=RATE, num_threads=1, provider="cpu"))
        self._size = self._model.window_size()  # VAD_STEP and its context
        self.reset()

    def reset(self) -> None:
        self._model.reset()
        self._pending = np.zeros(self._size - VAD_STEP, np.float32)  # silence as the first window's context
        self._since_reset = 0  # windows heard since the model's state was reset
        self._quiet = 0        # windows in a row not heard as speech

    def marks(self, block: np.ndarray, settle: bool = False) -> np.ndarray:
        """One per sample of ``block``: True at the last sample of each window heard as speech, so a window counts for
        the block in which it was heard whole. ``settle``: no request is open, so the model's state may be reset in the
        quiet (VAD_RESET_S)."""
        behind = len(self._pending) - (self._size - VAD_STEP)  # samples of the blocks before not yet in a window
        self._pending = np.concatenate([self._pending, block])
        marks = np.zeros(len(block), bool)
        at = 0
        while len(self._pending) - at >= self._size:
            if self._model.is_speech(self._pending[at:at + self._size]):
                marks[at + VAD_STEP - 1 - behind] = True
                self._quiet = 0
            else:
                self._quiet += 1
            self._since_reset += 1
            if settle and self._since_reset * VAD_STEP >= VAD_RESET_S * RATE and self._quiet >= VAD_RESET_QUIET:
                self._model.reset()  # its state only: the next window keeps the context before it (VAD_RESET_S)
                self._since_reset = 0
            at += VAD_STEP
        self._pending = self._pending[at:]
        return marks


def voiced(audio: np.ndarray, marks: np.ndarray) -> np.ndarray:
    """Which BLOCKs of ``audio`` are voice: loud and heard as speech (``marks``: Vad.marks of the same samples)."""
    n = len(audio) // BLOCK * BLOCK
    loud = np.sqrt((audio[:n].reshape(-1, BLOCK) ** 2).mean(axis=1)) >= VOICE_RMS
    return loud & marks[:n].reshape(-1, BLOCK).any(axis=1)


class Recent:
    """The last ``keep`` samples heard and their Silero marks, in buffers allocated once (twice ``keep`` and two
    blocks): each block is copied in, and ``audio``/``speech`` are views of the last ``keep``. Real use, 2026-11-03:
    joining the 30 s window again for every 100 ms block failed with MemoryError((481600,), float32) when the PC was
    short of memory, the block was lost, and a request was transcribed from the middle of the sentence."""

    def __init__(self, keep: int) -> None:
        self._keep = keep
        self._audio = np.zeros(2 * keep + 2 * BLOCK, np.float32)
        self._speech = np.zeros(len(self._audio), bool)
        self._end = 0

    def clear(self) -> None:
        self._end = 0

    def add(self, block: np.ndarray, marks: np.ndarray) -> None:
        if self._end + len(block) > len(self._audio):  # the last keep - len(block) samples move to the front
            kept = self._keep - len(block)              # (never overlapping: they start past keep + 2 blocks)
            self._audio[:kept] = self._audio[self._end - kept:self._end]
            self._speech[:kept] = self._speech[self._end - kept:self._end]
            self._end = kept
        self._audio[self._end:self._end + len(block)] = block
        self._speech[self._end:self._end + len(block)] = marks
        self._end += len(block)

    @property
    def audio(self) -> np.ndarray:
        return self._audio[max(0, self._end - self._keep):self._end]

    @property
    def speech(self) -> np.ndarray:
        return self._speech[max(0, self._end - self._keep):self._end]


def loud_floor(audio: np.ndarray) -> bool:
    """The room is loud by itself: four in five of the BLOCKs of ``audio`` are above VOICE_RMS (none heard is quiet).
    Steady noise fills every pause; in the request window it separated pink noise at 10 dB (97.9 % of the turn model's
    looks) from a quiet room (1.4 % of the synthetic set, 2.4 % of the owner's requests)."""
    whole = audio[len(audio) % BLOCK:].reshape(-1, BLOCK)
    return len(whole) > 0 and float(np.percentile(np.sqrt((whole ** 2).mean(axis=1)), 20)) >= VOICE_RMS


def _blocks(audio: np.ndarray, marks: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Each whole BLOCK of ``audio``: its RMS and whether Silero heard speech in it (``marks``)."""
    n = len(audio) // BLOCK * BLOCK
    return np.sqrt((audio[:n].reshape(-1, BLOCK) ** 2).mean(axis=1)), marks[:n].reshape(-1, BLOCK).any(axis=1)


# Uso 95: the waits between the deferred recognizer's own tries (Voice._retry_until_loaded), as StartupRetries waits.
STT_RETRY_WAITS_S = (10.0, 20.0, 40.0, 60.0)


class Voice:
    """Listens on its own thread; the mind's request loop only starts, stops and reads it."""

    _wake_log: WakeLog | None = None  # development only (BAXY_WAKE_LOG_DIR)
    _wake_logged: str | None = None   # the wake log's key of the open request's «Baxy»
    _turn: voice_turn.Turn | None = None  # the turn model (_load_turn); without it the hanging words set the wait
    _turn_heard: tuple[float, float | None] | None = None  # the end of voice the turn model heard, and its verdict
    _recent: Recent | None = None     # what is kept of what was heard (built on the first reset)
    _echo: voice_echo.Stage | None = None  # the echo cancellation with the microphone open (voice_echo.py)
    _lost_at: float | None = None     # F17: when, of the audio heard, a block was last lost
    _played_span: np.ndarray | None = None  # F44: what was played over the request just finished, to be decoded
    _played_said = ""                 # F44: what the recognizer heard in it
    _tail_said: tuple[float, Heard] | None = None  # VOZ1: the end of the voice in the call's tail, and its words

    def __init__(self, write: Callable[[dict[str, Any]], None],
                 on_spoken: Callable[[float, float, bool], None] = lambda *_spoken: None,
                 on_early: Callable[[int, str | None], None] | None = None, early_s: float = 0.0,
                 on_wake: Callable[[], None] | None = None) -> None:
        self._write = write
        # Al máximo, palancas 2 y 5 (early.py): what was said, told to the mind once the person has been silent
        # ``early_s`` (an early transcript, numbered; None takes it back when they go on), and «Baxy» heard. Neither
        # reaches the App: the request still ends after END_SILENCE_S with its own transcript, as before.
        self._on_early = on_early if early_s > 0 else None
        self._early_s = early_s
        self._on_wake = on_wake
        self._early_seq = 0
        self._early_at: float | None = None   # the end of the voice the last early transcript heard
        self._loaded = threading.Event()
        self._lock = threading.Lock()
        self._detector: Any = None
        self._vad: Vad | None = None
        self._recognizer: Any = None
        self._hotwords = ""             # the stream hotwords of the names the recognizer was built with
        self._names: list[str] | None = None
        self._named = threading.Event()
        self._input = False
        self._wav_feed: voice_feed.Feed | None = None  # WAV files heard instead of the microphone (benches)
        self._answered = 0              # answers that began to sound (not notices): the feed waits for them
        self.failure = ""
        # Encargo 10 (punto 6): why the ear is not loaded yet when it is not a failure (too little memory to commit when
        # the recognizer was built); retried on the next start() and on its own (uso 95). The App says it.
        self.deferred = ""
        self._stt_tries = 0
        self._stt_retry: Callable[[], None] | None = None
        # Uso 95: the figures of the last load that did not fit (NotEnoughMemory), for the App; one retry at a time.
        self._stt_memory: dict[str, int] | None = None
        self._stt_lock = threading.Lock()
        self._stt_retrying = False
        self._mode = "off"
        self._resume = "off"            # the mode a direct request returns to
        self._stream: Any = None
        # The echo cancellation (voice_echo.py): wanted by the owner's switch (voice.start), asked when the open
        # microphone was opened, and the stage with its closing while it runs.
        self._echo_wanted = voice_echo.wanted(True)
        self._echo_asked = self._echo_wanted
        self._played_twin: Any = None   # F44: the detector that hears what the PC played, built on its first use
        self._blocks: queue.Queue[np.ndarray] = queue.Queue()
        self._heard = 0                 # moved on by every reset and stop
        self._wake_peak = WAKE_TARGET   # the recent peak the detector's gain follows (wake_gain)
        self._told = Heard("")          # the last transcript told to the App, until the mind takes it (unsure)
        self._wake_log = WakeLog.from_env()
        self._reset()
        self._on_spoken = on_spoken
        self.speech = Speech(self._speaking, self._sounding, self._lip)
        threading.Thread(target=self._load, name="voice-load", daemon=True).start()
        threading.Thread(target=self._listen, name="voice", daemon=True).start()

    # --- requests -------------------------------------------------------------------------------------------------

    def status(self) -> dict[str, Any]:
        stt = self._recognizer is not None
        # What the App reads of it (MindSidecarClient): whether the ear works and whether it is still loading.
        return {"available": stt and self._input, "input": self._input, "stt": stt,
                "wake": self._detector is not None, "tts": self.speech.ready,
                "pending": not self._loaded.is_set(), "echo": self._echo is not None,
                # Encargo 10 (punto 6): the ear or the voice is not loaded for want of memory, and will be retried.
                "deferred": bool(self.deferred or self.speech.deferred),
                # Uso 95: what the ear needs and found left to commit while it waits for memory (the App says it).
                "memory": self._stt_memory if self.deferred else None}

    def unsure(self, text: str) -> list[tuple[str, float]]:
        """The words the ear was not sure of when ``text`` is the transcript it told last (taken once): the App's
        turn.decide carries only the words, typed or heard."""
        with self._lock:
            told, self._told = self._told, Heard("")
        return told.unsure() if told.text and told.text == text.strip() else []

    def start(self, mode: str, echo_cancel: bool = True) -> bool:
        """``echo_cancel``: the owner's switch for taking out what the PC plays (voice_echo.py); a start with the
        microphone open and the switch changed opens it again with or without the stage."""
        self._loaded.wait(60)
        self._retry_recognizer()
        if mode not in ("wake", "direct") or self._recognizer is None or not self._input \
                or (mode == "wake" and self._detector is None):
            return False
        with self._lock:
            self._echo_wanted = voice_echo.wanted(echo_cancel)
            if mode == "direct":
                self._resume = "wake" if self._mode == "wake" else self._resume if self._mode == "direct" else "off"
            self._mode = mode
            self._reset()
            try:
                self._open()
            except Exception as error:  # noqa: BLE001 - a microphone that does not open is told as a failed start
                self.failure = f"microphone: {error!r}"
                self._mode = "off"
                return False
        self._state()
        return True

    def release(self) -> None:
        """Push-to-talk let go: a direct request ends now instead of after its silence."""
        with self._lock:
            if self._mode == "direct" and self._start is not None:
                self._released = True

    def stop(self) -> None:
        with self._lock:
            self._mode = self._resume = "off"
            self._heard += 1
            self._early_back()
            self._close()
        self._state()

    def _speaking(self, speaking: bool) -> None:
        if speaking:
            with self._lock:
                self._reset()  # what was heard up to now is not mixed with what is said after BAXY speaks
        self._state()

    # --- loading --------------------------------------------------------------------------------------------------

    def _load(self) -> None:
        try:
            import sherpa_onnx
            self._vad = Vad(sherpa_onnx)
            self._hear_from(lambda: Vad(sherpa_onnx))
            self._load_turn()
            # V132: none given (the App names none when the product's is gone or changed) is no wake word, never the
            # current folder that Path("") is.
            folder = os.environ.get("BAXY_RENEW_WAKE_DIR", "").strip()
            wake = Path(folder) if folder else None
            if wake is not None and (wake / "config.json").is_file():
                detector = load_wake(wake)
                fast = load_fast_wake()
                self._detector = detector if fast is None else EitherWake(detector, fast)
            else:
                self.failure = self.failure or "BAXY_RENEW_WAKE_DIR has no wake word"
            stt = Path(os.environ.get("BAXY_RENEW_STT_DIR", ""))
            if (stt / "tokens.txt").is_file():
                self._load_recognizer(sherpa_onnx, stt)
            else:
                self.failure = "BAXY_RENEW_STT_DIR has no recognizer"
        except Exception as error:  # noqa: BLE001 - voice is optional: the mind serves turns without it
            self.failure = repr(error)
        finally:
            if self.failure:
                sys.stderr.write(f"baxy_mind_renew_voice: {self.failure}\n")
                sys.stderr.flush()
            self._loaded.set()

    def _load_turn(self) -> None:
        """The turn model (voice_turn.model_path; BAXY_RENEW_TURN=0 turns it off). One that does not load is told on
        stderr and the request closes as without it: by the hanging words."""
        path = voice_turn.model_path()
        if path is None:
            return
        try:
            self._turn = voice_turn.Turn(path)
        except Exception as error:  # noqa: BLE001 - the ear works without it, with the fixed silence
            sys.stderr.write(f"baxy_mind_renew_voice: turn model: {error!r}\n")
            sys.stderr.flush()

    def _load_recognizer(self, sherpa_onnx: Any, stt: Path) -> None:
        """Encargo 10 (punto 6): the recognizer, built now; a low-memory moment does not turn the ear off for the
        session but defers it, to be retried on the next start() (``_retry_recognizer``) and, uso 95, on its own with a
        growing wait while the mind runs (``_retry_until_loaded``), until memory is freed."""
        try:
            self._recognize(sherpa_onnx, stt)
            self.deferred = ""
        except MemoryError as error:
            self._stt_retry = lambda: self._recognize(sherpa_onnx, stt)
            self._deferred_for(error)
            threading.Thread(target=self._retry_until_loaded, name="voice-retry", daemon=True).start()

    def _deferred_for(self, error: MemoryError) -> None:
        self._stt_tries += 1
        self.deferred = repr(error)
        self._stt_memory = ({"needMb": error.need_mb, "leftMb": error.left_mb}
                            if isinstance(error, NotEnoughMemory) else None)
        sys.stderr.write(f"baxy_mind_renew_voice: deferred ({self._stt_tries}): {self.deferred}\n")
        sys.stderr.flush()

    def _retry_recognizer(self) -> None:
        """Encargo 10 (punto 6): a recognizer the first load could not fit in memory is built again on this use, until
        it loads (then nothing is deferred). Uso 95 (uso real 2026-11-04 13:19): it is never a failure for want of
        memory any more: three tries at start found no room, memory was freed later and the ear never came back."""
        with self._stt_lock:
            retry = self._stt_retry
            if retry is None or self._recognizer is not None:
                return
            try:
                retry()
                self.deferred, self._stt_retry, self._stt_memory = "", None, None
            except MemoryError as error:
                self._deferred_for(error)
            except Exception as error:  # noqa: BLE001 - uso-116: not memory: it will not load by waiting, and it is said
                self.failure, self.deferred, self._stt_retry, self._stt_memory = repr(error), "", None, None
                sys.stderr.write(f"baxy_mind_renew_voice: recognizer: {self.failure}\n")
                sys.stderr.flush()

    def _retry_until_loaded(self) -> None:
        """Uso 95: the deferred recognizer tried again on its own, waiting longer each time (STT_RETRY_WAITS_S, then its
        last wait for ever: a sleep, no CPU), until it loads; then the App is told (voice_ready) so it reads the voice
        state again."""
        for attempt in range(1_000_000):
            time.sleep(STT_RETRY_WAITS_S[min(attempt, len(STT_RETRY_WAITS_S) - 1)])
            self._retry_recognizer()
            if self._recognizer is not None:
                self._event("voice_ready")
                return
            if self._stt_retry is None:
                return

    def _hear_from(self, vad: Callable[[], Vad]) -> None:
        """The input: the feed BAXY_RENEW_VOICE_FEED names (then the microphone is never opened), or the microphone.
        The feed tells where each file's voice ended as the voice hears it, with a fresh ``vad()`` for each file."""
        try:
            self._wav_feed = voice_feed.from_env(RATE, BLOCK, lambda audio: voiced(audio, vad().marks(audio)),
                                                 self._quiet, lambda: self._answered)
        except Exception as error:  # noqa: BLE001 - a feed that cannot be heard is told as the missing input
            self.failure = f"voice feed: {error!r}"
            return
        if self._wav_feed is not None:
            self._input = True
            return
        import sounddevice as sd
        try:
            sd.query_devices(self._device(), kind="input")
            self._input = True
        except Exception as error:  # noqa: BLE001
            self.failure = f"microphone: {error!r}"

    def hear_names(self, names: list[str]) -> None:
        """The installed applications and games the model is shown (catalog.configure, which the App sends before any
        voice.start): the recognizer waits for them and is built with them as hotwords. The App configures once per
        mind; names that come after the recognizer was built are not heard as hotwords."""
        if not self._named.is_set():
            self._names = [str(name) for name in names]
            self._named.set()

    def _recognize(self, sherpa_onnx: Any, stt: Path) -> None:
        """Parakeet Ultra, greedy as TranscripcionBaxy chose it; with the names as hotwords, its beam search with them
        (stt_hotwords.py; measured in scripts/voice/medir_hotwords.py)."""
        files = dict(encoder=str(stt / "encoder.int8.onnx"), decoder=str(stt / "decoder.int8.onnx"),
                     joiner=str(stt / "joiner.int8.onnx"), tokens=str(stt / "tokens.txt"), num_threads=4,
                     model_type="nemo_transducer", feature_dim=128, provider="cpu")
        score = hotwords_score()
        forms: list[str] = []
        if score > 0 and self._named.wait(NAMES_WAIT_S) and self._names:
            forms, vocab = stt_hotwords.compile_hotwords(self._names, (stt / "tokens.txt").read_text(encoding="utf-8"))
        if not forms:
            with native_load(EAR_COMMIT_MB, "recognizer"):
                self._recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(**files,
                                                                                 decoding_method="greedy_search")
            return
        with tempfile.TemporaryDirectory(prefix="baxy-stt-") as folder, native_load(EAR_COMMIT_MB, "recognizer"):
            path = Path(folder) / "bpe.vocab"  # sherpa reads it by path, once, while it builds the recognizer
            path.write_text(vocab, encoding="utf-8")
            self._recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
                **files, decoding_method="modified_beam_search", max_active_paths=HOTWORDS_PATHS, modeling_unit="bpe",
                bpe_vocab=str(path))
        self._hotwords = stt_hotwords.stream_hotwords(forms, score)

    def _device(self) -> int | None:
        value = os.environ.get("BAXY_RENEW_MIC", "")
        if value.strip().isdigit():
            return int(value)
        import sounddevice as sd
        return default_follower(sd, "input")

    # --- microphone -----------------------------------------------------------------------------------------------

    def _open(self) -> None:
        if self._stream is not None and self._echo_asked == self._echo_wanted:
            return
        if self._stream is not None:
            self._close()  # the owner switched the echo cancellation while the microphone was open
        # What the PC plays is taken out of each block before anything hears it (voice_echo.py); a feed has no echo.
        echo = voice_echo.open_stage(RATE) if self._echo_wanted and self._wav_feed is None else None
        cancel = echo.cancel if echo is not None else None

        def callback(indata, _frames, _when, _status) -> None:
            block = np.array(indata[:, 0], dtype=np.float32, copy=True)  # the buffer is only valid here
            self._blocks.put(cancel(block) if cancel is not None else block)

        try:
            if self._wav_feed is not None:
                stream = self._wav_feed.open(callback)
            else:
                import sounddevice as sd
                stream = sd.InputStream(device=self._device(), samplerate=RATE, channels=1, dtype="float32",
                                        blocksize=BLOCK, callback=callback)
            # Built, the stream is already open: one whose start fails is closed, never kept as the open microphone
            # (the next start found it there and said the ear was on while it heard nothing).
            try:
                stream.start()
            except BaseException:
                stream.close()
                raise
        except BaseException:
            if echo is not None:
                echo.close()
            raise
        self._stream, self._echo, self._echo_asked = stream, echo, self._echo_wanted

    def _revive(self) -> None:
        """No block for STALL_S from an open microphone: it is opened again (STALL_S)."""
        with self._lock:
            if self._stream is None or self._mode == "off":
                return
            sys.stderr.write("baxy_mind_renew_voice: the microphone sent nothing; opening it again\n")
            sys.stderr.flush()
            self._close()
            self._reset()
            try:
                self._open()
                return
            except Exception as error:  # noqa: BLE001 - no microphone now: the ear is off, and the App is told so
                self.failure = f"microphone: {error!r}"
                self._mode = self._resume = "off"
        self._event("error")
        self._state()

    def _close(self) -> None:
        if self._wake_log is not None:
            self._wake_log.stop()
        if self._stream is not None:
            self._stream.close()
            self._stream = None
        if self._echo is not None:
            self._echo.close()          # after the microphone: its callback no longer asks for the reference
            self._echo = None
        while not self._blocks.empty():
            self._blocks.get_nowait()

    def _reset(self) -> None:
        self._heard += 1                # a transcription of what was heard before is not told
        self._early_back()
        if self._recent is None:
            self._recent = Recent(int(KEEP_S * RATE))
        self._recent.clear()
        self._audio, self._speech = self._recent.audio, self._recent.speech  # Vad.marks of self._audio
        self._first = 0                 # absolute index of self._audio[0]
        self._total = 0                 # samples heard since the mode started
        self._start: float | None = 0.0 if self._mode == "direct" else None  # the request window's opening
        self._released = False          # push-to-talk let go (direct mode)
        self._partial_at = 0.0          # when what was said so far was last decoded
        self._partial = ""
        self._turn_heard = None
        self._tail_said = None
        self._held_call: _HeldCall | None = None  # F44: a firing waiting to know whether the PC played the word
        self._lost_at = None
        self._played_span, self._played_said = None, ""
        self._wake_at = 0.0            # when the detector was last reset (its times count from there)
        self._wake_logged = None
        if self._detector is not None:
            self._detector.reset()
        if self._vad is not None:
            self._vad.reset()

    # --- listening ------------------------------------------------------------------------------------------------

    def _listen(self) -> None:
        """Ultra decodes outside the lock (up to MAX_S of audio, and every PARTIAL_S in a request): a release, a stop,
        a start or BAXY starting to speak never wait for it, and what they leave behind is not told."""
        while True:
            try:
                block = self._blocks.get(timeout=STALL_S)
            except queue.Empty:
                self._revive()
                continue
            total = self._total
            try:
                with self._lock:
                    heard = self._heard
                    if self._wake_log is not None:
                        self._wake_log.hear(block)
                    job = self._feed(block) if self._mode != "off" and not self.speech.speaking else None
                    call = self._call_to_check()
                    span, self._played_span = self._played_span, None
                if call is not None:
                    played = self._played_it(*call)  # up to a second or two, once per firing: never under the lock
                    with self._lock:
                        if heard == self._heard:
                            self._settle_call(played)
                if job is not None:
                    audio, wake_at, then = job
                    played = ""
                    try:
                        transcript = self._transcribe(audio, wake_at)
                        if span is not None:
                            played = self._transcribe(span * np.float32(0.45 / float(np.max(np.abs(span)))), None).text
                    except Exception as error:  # noqa: BLE001 - told; a request ends as one nothing was heard of
                        self._not_heard(len(audio), error)
                        transcript = Heard("")
                    with self._lock:
                        if heard == self._heard:
                            self._played_said = played
                            then(transcript)
            except Exception as error:  # noqa: BLE001 - one bad block never ends the voice
                with self._lock:
                    if self._total == total:  # F17: this block was not kept, so a request around it has a hole
                        self._lost_at = total / RATE
                self._not_heard(len(block), error)

    def _not_heard(self, samples: int, error: Exception) -> None:
        sys.stderr.write(f"baxy_mind_renew_voice: {datetime.datetime.now().isoformat(timespec='milliseconds')}"
                         f" a block of {samples * 1000 // RATE} ms was not heard: {error!r}\n")
        sys.stderr.flush()
        self._event("error")

    def _call_to_check(self) -> tuple[np.ndarray, float] | None:
        """F44: what the PC played around a firing, and where in it the firing was, once the moment to check it has come
        (the reference leads the echo, so it holds the word by then; blocks still waiting to be heard are newer)."""
        held = self._held_call
        if held is None or self._echo is None or self._total / RATE < held.due:
            return None
        waiting_s = self._blocks.qsize() * BLOCK / RATE
        far = self._echo.played(voice_echo.PLAYED_BACK_S + self._played_hold() + waiting_s)
        return far, len(far) / RATE - waiting_s - (self._total / RATE - held.start)

    def _played_hold(self) -> float:
        """How long a firing waits for F44's check: what its package asked for (load_wake). A detector that decides as
        it hears finds the word on the reference at once; one that decides by chunks needs the second."""
        return getattr(self._detector, "played_hold_s", voice_echo.PLAYED_HOLD_S)

    def _played_it(self, far: np.ndarray, word_at: float) -> bool:
        """F44: whether the word is in what the PC played when the microphone heard it (``word_at``, seconds into ``far``,
        PLAYED_NEAR_S around it: not BAXY's own «soy Baxy» or a video's a moment earlier, with the person answering):
        the detector on the reference, level brought to the detector's own (the loopback carries Windows' volume), the
        whole of it at once. A check that fails lets the call through: a call lost is worse than a word answered that
        the person sees was not theirs."""
        try:
            if self._played_twin is None:
                self._played_twin = self._detector.twin()
            twin = self._played_twin
            twin.reset()
            peak = float(np.max(np.abs(far)))
            raised = far * np.float32(WAKE_TARGET / max(peak, 1e-9))
            return any(abs(detection.time_s - word_at) <= voice_echo.PLAYED_NEAR_S
                       for at in range(0, len(raised) - BLOCK + 1, BLOCK)
                       for detection in twin.accept(raised[at:at + BLOCK]))
        except Exception as error:  # noqa: BLE001
            sys.stderr.write(f"baxy_mind_renew_voice: the wake word could not be looked for in what was played: "
                             f"{error!r}\n")
            sys.stderr.flush()
            return False

    def _settle_call(self, played: bool) -> None:
        call, self._held_call = self._held_call, None
        if call is None:
            return
        if played:
            self._told_wake(call.detection, self._total / RATE - call.start, " played by the PC")
        else:
            self._open_call(call.start, call.detection)

    def _heard_call(self, start: float, detection: Any) -> None:
        """A firing while nothing is open. With what the PC plays in the last moments it waits to be checked (F44);
        with the PC silent, or no stage, it opens the request now."""
        far = self._echo.played(voice_echo.PLAYED_BACK_S) if self._echo is not None else None
        if far is None or not far.any():
            self._open_call(start, detection)
            return
        self._held_call = _HeldCall(start, detection, self._total / RATE + self._played_hold())

    def _open_call(self, start: float, detection: Any) -> None:
        lag = self._total / RATE - start
        self._start = start
        self._partial = ""  # a new request's live caption is told even when it repeats the last one
        if self._wake_log is not None:
            self._wake_logged = self._wake_log.mark(lag, getattr(detection, "probability", None))
        self._event("wake_detected")
        self._told_wake(detection, lag)
        if self._on_wake is not None:
            self._on_wake()

    def _feed(self, block: np.ndarray) -> tuple[np.ndarray, float | None, Callable[[Heard], None]] | None:
        self._recent.add(block, self._vad.marks(block, settle=self._start is None and self._held_call is None))
        self._audio, self._speech = self._recent.audio, self._recent.speech
        self._total += len(block)
        self._first = self._total - len(self._audio)
        if self._mode == "wake":
            # The detector keeps hearing during the request too, as in probar_baxy.py.
            now = self._total / RATE
            if (self._start is None and now - self._wake_at >= WAKE_RESET_S
                    and not self._speech[-int(WAKE_QUIET_S * RATE):].any()):
                self._detector.reset()
                self._wake_at = (self._total - len(block)) / RATE  # it hears from this block on
            self._wake_peak, raised = wake_gain(self._wake_peak, block)
            detections = self._detector.accept(raised)
            if self._wake_log is not None:
                self._wake_log.scores([(now - self._wake_at - t, p) for t, p in self._detector.scores()],
                                      [now - self._wake_at - d.time_s for d in detections])
            if self._start is None and self._held_call is None and detections:
                self._heard_call(self._wake_at + detections[0].time_s, detections[0])
        start = self._start
        if start is not None and self._over(start):
            return self._finish(start)
        if start is not None:
            return self._early(start) or self._said_in_tail(start) or self._live(start)
        return None

    def _told_wake(self, detection: Any, lag_s: float, how: str = "") -> None:
        """Each «Baxy» heard, on stderr (the App keeps it in mind-stderr.log): when, the detector's probability, how
        long after the word it was told, and whether the stage was on; no audio and no words, so a request transcribed
        from the middle of a sentence can be told from a wake that fired there (uso-74, 2026-11-03: the installed BAXY
        keeps no wake log), and a word the PC played from a call (F44)."""
        p = getattr(detection, "probability", None)
        sys.stderr.write(f"baxy_mind_renew_voice: wake {datetime.datetime.now().isoformat(timespec='milliseconds')}"
                         f" p={'-' if p is None else f'{float(p):.3f}'} lag={lag_s:.2f}s"
                         f" echo={'on' if self._echo is not None else 'off'}{how}\n")
        sys.stderr.flush()

    def _live(self, start: float) -> tuple[np.ndarray, float | None, Callable[[Heard], None]] | None:
        """Live captions: the request heard so far, decoded again every PARTIAL_S with the same recognizer and the same
        cut of the call as the final transcript; only a changed text is sent, and it starts nothing."""
        now = self._total / RATE
        if now - self._partial_at < PARTIAL_S or now - start < WORD_TAIL_S + PARTIAL_S or self._early_at is not None:
            return None  # an early transcript is the caption of the silence after it
        if self._blocks.qsize() > BEHIND_BLOCKS:
            return None  # behind the microphone: the caption waits for the blocks (BEHIND_BLOCKS)
        self._partial_at = now
        wake = self._mode == "wake"
        begin = max(0.0, start - BEFORE_S) if wake else 0.0

        def then(transcript: Heard) -> None:
            text = transcript.text
            if text and text != self._partial:
                self._partial = text
                self._write({"type": "voice.event", "event": "partial", "mode": self._mode, "text": text})

        return self._segment(begin, now), start - begin if wake else None, then

    def _at(self, s: float) -> int:
        return max(0, int(s * RATE) - self._first)

    def _segment(self, start_s: float, stop_s: float) -> np.ndarray:
        a = self._at(start_s)
        return self._audio[a:max(a, self._at(stop_s))]

    def _voice_end(self, start: float) -> float | None:
        """When the last block of voice of the request ended (the end of «Baxy» left out), or None before any. VOZ1: a
        request all inside the call's tail ends where its voice ended, once the recognizer heard words in it."""
        blocks = self._request_voice(start)
        if blocks:
            return start + (blocks[-1] + 1) * BLOCK / RATE
        said = self._tail_said
        return said[0] if said is not None and said[1].text and said[0] == self._tail_end(start) else None

    def _tail_end(self, start: float) -> float | None:
        """When the voice heard in the call's tail (the first WORD_TAIL_S after the trigger) ended, or None."""
        blocks = self._request_voice(start, tail=False)
        return start + (blocks[-1] + 1) * BLOCK / RATE if blocks else None

    def _request_voice(self, start: float, tail: bool = True) -> list[int]:
        """The blocks from ``start`` that are the speaker's voice (SPEAKER_DB), the end of «Baxy» left out (``tail``)."""
        a = self._at(start)
        wake = self._mode == "wake"
        level = self._speaker_level(self._at(start - CALL_BACK_S) if wake else a)
        if level is None:
            return []
        rms, speech = _blocks(self._audio[a:], self._speech[a:])
        voice_blocks = speech & (rms >= max(SPEAKER_FLOOR, level * 10 ** (-SPEAKER_DB / 20)))
        cut = (NOISY_TAIL_S if self._noisy(a) else WORD_TAIL_S) if wake and tail else 0.0
        return [int(i) for i in np.flatnonzero(voice_blocks) if i * BLOCK / RATE >= cut]

    def _speaker_level(self, r: int) -> float | None:
        """The level of the one who speaks: the 80th percentile of the blocks of speech heard from ``r`` (None before
        any), so the nearest voice sets it even when a farther one spoke first."""
        rms, speech = _blocks(self._audio[r:], self._speech[r:])
        return float(np.percentile(rms[speech], 80)) if speech.any() else None

    def _noisy(self, a: int) -> bool:
        """Four in five blocks heard before the call (up to 1 s before the request opens at ``a``) are loud: the noise
        alone is above VOICE_RMS."""
        return loud_floor(self._audio[:max(0, a - RATE)])

    def _quiet(self) -> bool:
        """For the feed: BAXY is silent and no request is hearing voice (one waiting for its words is quiet)."""
        with self._lock:
            return not self.speech.speaking and (self._start is None or self._voice_end(self._start) is None)

    def _over(self, start: float) -> bool:
        if self._released:
            return True
        now = self._total / RATE
        if now - start >= MAX_S:
            return True
        end = self._voice_end(start)
        if end is None:
            return now - start >= (NO_COMMAND_S if self._mode == "wake" else DIRECT_WAIT_S)
        early = self._early_heard if self._early_at == end else None
        rule = end_silence(early.text) if early is not None else END_SILENCE_S
        if not self._request_voice(start):
            # VOZ1: words only in the call's tail (_said_in_tail) may be the end of «Baxy» misheard: on the owner's real
            # calls with a pause after it, Ultra wrote its last syllable as «see.» or «seat.», begun at the trigger, and
            # the usual wait ended the request on it before the words said after the pause (0.5-1.9 s; 2 of 181 calls
            # paused longer than 2 s). They wait as words left hanging do.
            rule = END_SLOW_S
        heard = self._turn_wait(start, end, now)
        # Words left hanging keep their long wait whatever the model heard (it only sets how long to wait).
        wait = rule if heard is None else max(heard, rule) if rule > END_SILENCE_S else heard
        # 1e-6: in direct mode 2.4 - 1.5 is 0.8999…, and 48 of 120 requests waited one block (100 ms) more
        return now - end >= wait - 1e-6

    def _turn_wait(self, start: float, end: float, now: float) -> float | None:
        """The silence the turn model sets after the voice that ended at ``end``: once TURN_AT_S of it passed, it hears
        the request up to now (the audio its transcript is decoded from, at most voice_turn.TURN_S), once per end of
        voice; END_DONE_S if it heard the turn complete, END_SLOW_S if it is sure it is not, END_UNSURE_S in between.
        None (the rule without it decides) with no model, before TURN_AT_S, or in a loud room (loud_floor)."""
        if self._turn is None or now - end < TURN_AT_S - 1e-6:
            return None
        if self._turn_heard is None or self._turn_heard[0] != end:
            audio = self._segment(max(0.0, start - BEFORE_S) if self._mode == "wake" else 0.0, now)
            heard = None if loud_floor(audio) else self._turn.complete(audio[-voice_turn.TURN_S * RATE:])
            self._turn_heard = (end, heard)
        heard = self._turn_heard[1]
        if heard is None:
            return None
        return END_DONE_S if heard >= TURN_P else END_UNSURE_S if heard >= TURN_OPEN_P else END_SLOW_S

    def _early(self, start: float) -> tuple[np.ndarray, float | None, Callable[[Heard], None]] | None:
        """Palanca 2 (early.py): ``early_s`` into the silence that may end the request, what was said is decoded with
        the same recognizer and cut as the final transcript, and told to the mind (and as the caption). If the person
        goes on, it is taken back; the request ends as always, with a transcript of its own."""
        if self._on_early is None or self._released:
            return None
        end = self._voice_end(start)
        if end is None:
            return None
        if self._early_at is not None:
            if end <= self._early_at:
                return None
            self._early_back()  # the person went on after it
        now = self._total / RATE
        if now - end < self._early_s - 1e-6:  # times are sums of 0.1 s blocks
            return None
        self._early_at, self._early_seq = end, self._early_seq + 1
        seq = self._early_seq
        wake = self._mode == "wake"
        begin = max(0.0, start - BEFORE_S) if wake else 0.0

        def then(transcript: Heard) -> None:
            text = transcript.text
            if text and text != self._partial:
                self._partial = text
                self._write({"type": "voice.event", "event": "partial", "mode": self._mode, "text": text})
            if text and self._on_early is not None and self._early_seq == seq and self._early_at == end:
                self._early_heard = transcript
                self._on_early(seq, text)

        return self._segment(begin, now), start - begin if wake else None, then

    def _said_in_tail(self, start: float) -> tuple[np.ndarray, float | None, Callable[[Heard], None]] | None:
        """VOZ1: when all the voice after the trigger is in the call's tail, TURN_AT_S into the silence after it (as the
        turn model listens), the request so far is decoded once with the call cut by time (_transcribe): words left are a
        request said in one breath («Baxi, gracias»), and it ends after END_SLOW_S of silence (_voice_end, _over); none,
        or words the ear is unsure of (UNSURE_P, or with no probabilities from Ultra), and it was the end of «Baxy»: the
        request waits for its words as before. On the owner's real calls with a pause after «Baxi», its last syllable misheard as a word («see.»,
        «seat.», «to.») was unsure in the ones that cut a request (0.33-0.50); the requests said in one breath were sure
        (0.54 and over, BAXY's voice and Sabina, 36 decoded)."""
        if self._mode != "wake" or self._request_voice(start):
            return None
        end = self._tail_end(start)
        now = self._total / RATE
        if end is None or now - end < TURN_AT_S - 1e-6 or (self._tail_said is not None and self._tail_said[0] == end):
            return None
        self._tail_said = (end, Heard(""))  # asked once for this end of voice
        begin = max(0.0, start - BEFORE_S)

        def then(transcript: Heard) -> None:
            if self._tail_said is not None and self._tail_said[0] == end:
                said = transcript.without_call()
                self._tail_said = (end, said if said.words and not said.unsure() else Heard(""))

        return self._segment(begin, now), start - begin, then

    def _early_back(self) -> None:
        """The last early transcript no longer stands for the request (the person went on, or what was heard is
        dropped)."""
        if getattr(self, "_early_at", None) is not None and self._on_early is not None:
            self._on_early(self._early_seq, None)
        self._early_at = None
        self._early_heard: Heard | None = None  # the early transcript of the voice up to _early_at, once decoded

    def _finish(self, start: float) -> tuple[np.ndarray, float | None, Callable[[Heard], None]]:
        # No voice after the early transcript: it was decoded from the same words with less silence after them, so it is
        # the request's transcript and nothing is decoded again (Deepgram Flux's EagerEndOfTurn without TurnResumed).
        end = self._voice_end(start)
        early = self._early_heard if self._early_at is not None and self._early_at == end else None
        voiced_enough = len(self._request_voice(start)) * BLOCK / RATE >= MIN_VOICE_S
        if not voiced_enough and end is not None:
            # VOZ1: the request was all in the call's tail, and its words were heard (_said_in_tail): they are its
            # transcript, from the same audio with less silence after it, as an early one.
            voiced_enough = True
            early = early or self._tail_said[1]
        self._start = None
        self._early_at = None  # the request's own transcript says whether the early one stands (early.py)
        wake = self._mode == "wake"
        begin = max(0.0, start - BEFORE_S) if wake else 0.0
        stop = self._total / RATE if voiced_enough and early is None else begin
        logged, self._wake_logged = self._wake_logged, None
        self._event("transcribing")
        # F44: what the PC played over the request is decoded too, only when it played something (_listen).
        far = self._echo.played(self._total / RATE - begin) if self._echo is not None and voiced_enough else None
        self._played_span = far if far is not None and far.any() else None

        def then(transcript: Heard) -> None:
            heard = (early if early is not None and voiced_enough else transcript).without_call()
            heard = heard.without_played(self._played_said)
            if self._lost_at is not None and self._lost_at >= begin:
                # F17: audio of the request was lost (the PC out of memory, 2026-11-03: a request reached the mind with
                # its beginning gone), so what is left is not what was said. Told so in a note of its own, the model
                # still acted on 5 of 30, and asked about the pieces in the rest: nothing goes to it, and the person has
                # the failure already (_not_heard: the App's chime and «Falló la escucha»).
                heard = Heard("")
            if logged is not None and self._wake_log is not None:
                self._wake_log.turn(logged, heard.text, voiced_enough)
            if heard.text:
                self._told = heard
                self._write({"type": "voice.transcript", "text": heard.text})
            if not wake:
                # A direct request is one utterance; the voice goes back to what it was doing before.
                self._mode = self._resume
                self._resume = "off"
                if self._mode == "off":
                    self._close()
                self._reset()
            self._state()

        return self._segment(begin, stop), start - begin if wake else None, then

    def _transcribe(self, audio: np.ndarray, wake_at: float | None) -> Heard:
        peak = float(np.max(np.abs(audio))) if len(audio) else 0.0
        if peak < 0.008:
            return Heard("")
        audio = audio * min(8.0, 0.45 / peak)  # the gain of probar_ultra.preparar
        stream = self._recognizer.create_stream(self._hotwords) if self._hotwords else self._recognizer.create_stream()
        stream.accept_waveform(RATE, np.ascontiguousarray(audio, dtype=np.float32))
        self._recognizer.decode_stream(stream)
        result = stream.result
        if wake_at is None:
            return Heard.of(result.text.strip(), result.tokens, result.ys_log_probs)
        # The call is cut by time, whatever Ultra wrote for it: the words that began more than CALL_LEAD_S before the
        # trigger are «Baxy» and what was said before it. Measured on the owner's recordings (TranscripcionBaxy/corpus/
        # grabaciones): «Baxy» begins 0.5-0.75 s before the trigger and the request after it, so «Baxi, abre Steam.»
        # gives «abre Steam.», «Hola. Maxi. Abre Spotify» gives «Abre Spotify», and a bare «Baxi» gives nothing.
        tokens, log_probs = list(result.tokens), list(result.ys_log_probs)
        words: list[list[Any]] = []
        for index, (token, at) in enumerate(zip(tokens, result.timestamps)):
            if token.startswith(" ") or not words:
                words.append([at, []])
            words[-1][1].append(index)
        kept = [index for at, indices in words if at >= wake_at - CALL_LEAD_S for index in indices]
        return Heard.of("".join(tokens[i] for i in kept).strip(), [tokens[i] for i in kept],
                        [log_probs[i] for i in kept] if len(log_probs) == len(tokens) else [])

    # --- events ---------------------------------------------------------------------------------------------------

    def _event(self, name: str) -> None:
        self._write({"type": "voice.event", "event": name, "mode": self._mode})

    def _sounding(self, queued: float, sounded: float, notice: bool) -> None:
        """An utterance's first sound: the App's notice of a silent turn counts until its answer is heard (al máximo
        9.2b), so it is told whether this one is the notice."""
        self._write({"type": "voice.event", "event": "sound", "mode": self._mode, "notice": notice})
        if not notice:
            self._answered += 1
        self._on_spoken(queued, sounded, notice)

    def _lip(self, lip: dict[str, Any]) -> None:
        self._write({"type": "voice.event", "event": "lip", "mode": self._mode, **lip})

    def _state(self) -> None:
        self._write({"type": "voice.event", "event": "state", "mode": self._mode,
                     "speaking": self.speech.speaking})
