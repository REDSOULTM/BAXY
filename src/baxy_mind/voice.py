"""Voice for BAXY Renew: the microphone, the k4 wake word and Parakeet Ultra (sherpa-onnx, CPU), and BAXY's voice
speaking (Supertonic, voice_output.py).

Only the connection: what the person says after «Baxy» reaches the App as voice.transcript, the same as a typed
message. The segmentation is WakewordBaxy/probar_baxy.py's, measured there with the owner's voice, with Silero VAD
telling voice from steady noise (Vad); the recognizer is TranscripcionBaxy's winner with its configuration. While BAXY
speaks the microphone is not heard, as in Definitivo, so its own voice («Hola, soy BAXY») never wakes it or enters a
request.

Paths (per PC): BAXY_RENEW_WAKE_DIR (the baxy-wake-k4 package), BAXY_RENEW_STT_DIR (parakeet-ultra-sherpa-int8-oli),
BAXY_RENEW_MIC (an input device index; otherwise Windows' default microphone of the moment, through the MME
sound mapper, as the voice's output). Benches: BAXY_RENEW_VOICE_FEED hears WAV files
in its place, in real time (voice_feed.py, scripts/voice/hablar.py).
"""
from __future__ import annotations

import copy
import importlib.util
import json
import os
import queue
import re
import sys
import tempfile
import threading
import unicodedata
from pathlib import Path
from typing import Any, Callable

from . import stt_hotwords, voice_feed
from .voice_output import Speech, default_follower

for _var in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_var, "1")

import numpy as np  # noqa: E402

RATE = 16000
BLOCK = 1600            # 100 ms
BEFORE_S = 2.0          # audio before the trigger that goes into the transcription
VOICE_RMS = 0.012       # voice threshold of TranscripcionBaxy/probar_ultra.py
SPEECH_P = 0.5          # Silero's own speech threshold (0.3 and 0.7 closed the same requests within 0.1 s)
VAD_STEP = 512          # Silero's window at 16 kHz (32 ms); sherpa-onnx gives it the 64 samples before as context
END_SILENCE_S = 0.9     # silence that closes the request
# A request whose early transcript (palanca 2, decoded 0.2 s into the silence) is left hanging (a preposition, article,
# conjunction, filler or comma at its end) waits END_SLOW_S instead of END_SILENCE_S, so a slow speaker is not cut
# (real use, 2026-10-26). LiveKit's turn detector waits up to 2.5-3 s when the turn is not complete, Pipecat Smart Turn
# 3 s; Amazon (Maas et al. 2018) reads the last words («a transcript ending in a preposition means more is coming»).
# A shorter wait when the words look ended (0.4-0.75 s, as LiveKit's 0.3 s) was measured and left out: Ultra writes a
# period after any fragment, and on 57 synthetic requests with a 0.7 s pause inside, 35-47 % were cut there against
# ~10 % at 0.9 s, for 0.1-0.3 s less wait.
END_SLOW_S = 2.0
HANGING_WORDS = frozenset(
    "el la los las un una unos unas lo al del a de en con por para sin sobre entre hasta desde hacia segun y e o u ni "
    "pero sino que porque si cuando como aunque donde mientras mi mis tu tus su sus nuestro me te se le les eh em mm "
    "este esto bueno pues tipo the an to of and but or so because um uh like my your".split())
HANGING_ENDS = frozenset({"o sea", "a ver", "voy a", "hay que", "es que", "i mean", "quiero que", "puedes"})
WORD_TAIL_S = 0.4       # voice in the first 0.4 s after the trigger is the end of «Baxy», not the request
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

    def marks(self, block: np.ndarray) -> np.ndarray:
        """One per sample of ``block``: True at the last sample of each window heard as speech, so a window counts for
        the block in which it was heard whole."""
        behind = len(self._pending) - (self._size - VAD_STEP)  # samples of the blocks before not yet in a window
        self._pending = np.concatenate([self._pending, block])
        marks = np.zeros(len(block), bool)
        at = 0
        while len(self._pending) - at >= self._size:
            if self._model.is_speech(self._pending[at:at + self._size]):
                marks[at + VAD_STEP - 1 - behind] = True
            at += VAD_STEP
        self._pending = self._pending[at:]
        return marks


def voiced(audio: np.ndarray, marks: np.ndarray) -> np.ndarray:
    """Which BLOCKs of ``audio`` are voice: loud and heard as speech (``marks``: Vad.marks of the same samples)."""
    n = len(audio) // BLOCK * BLOCK
    loud = np.sqrt((audio[:n].reshape(-1, BLOCK) ** 2).mean(axis=1)) >= VOICE_RMS
    return loud & marks[:n].reshape(-1, BLOCK).any(axis=1)


def _blocks(audio: np.ndarray, marks: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Each whole BLOCK of ``audio``: its RMS and whether Silero heard speech in it (``marks``)."""
    n = len(audio) // BLOCK * BLOCK
    return np.sqrt((audio[:n].reshape(-1, BLOCK) ** 2).mean(axis=1)), marks[:n].reshape(-1, BLOCK).any(axis=1)


class Voice:
    """Listens on its own thread; the mind's request loop only starts, stops and reads it."""

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
        self._mode = "off"
        self._resume = "off"            # the mode a direct request returns to
        self._stream: Any = None
        self._blocks: queue.Queue[np.ndarray] = queue.Queue()
        self._heard = 0                 # moved on by every reset and stop
        self._wake_peak = WAKE_TARGET   # the recent peak the detector's gain follows (wake_gain)
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
                "pending": not self._loaded.is_set()}

    def start(self, mode: str) -> bool:
        self._loaded.wait(60)
        if mode not in ("wake", "direct") or self._recognizer is None or not self._input \
                or (mode == "wake" and self._detector is None):
            return False
        with self._lock:
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
            wake = Path(os.environ.get("BAXY_RENEW_WAKE_DIR", ""))
            if (wake / "config.json").is_file():
                spec = importlib.util.spec_from_file_location("baxy_wake_k4", wake / "baxy_wake_runtime.py")
                assert spec is not None and spec.loader is not None
                module = importlib.util.module_from_spec(spec)
                sys.modules["baxy_wake_k4"] = module
                spec.loader.exec_module(module)
                config = json.loads((wake / "config.json").read_text(encoding="utf-8"))
                self._detector = StaggeredWake(lambda: module.BaxyWakeDetector(
                    wake / config["encoder"]["file"], wake / config["head"]["file"], threshold=config["threshold"],
                    debounce_s=config["debounce_s"], threads=1), WAKE_COPIES, float(config["debounce_s"]))
            else:
                self.failure = self.failure or "BAXY_RENEW_WAKE_DIR has no wake word"
            stt = Path(os.environ.get("BAXY_RENEW_STT_DIR", ""))
            if (stt / "tokens.txt").is_file():
                self._recognize(sherpa_onnx, stt)
            else:
                self.failure = "BAXY_RENEW_STT_DIR has no recognizer"
        except Exception as error:  # noqa: BLE001 - voice is optional: the mind serves turns without it
            self.failure = repr(error)
        finally:
            if self.failure:
                sys.stderr.write(f"baxy_mind_renew_voice: {self.failure}\n")
                sys.stderr.flush()
            self._loaded.set()

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
            self._recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(**files, decoding_method="greedy_search")
            return
        with tempfile.TemporaryDirectory(prefix="baxy-stt-") as folder:
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
        if self._stream is not None:
            return

        def callback(indata, _frames, _when, _status) -> None:
            self._blocks.put(np.array(indata[:, 0], dtype=np.float32, copy=True))  # the buffer is only valid here

        if self._wav_feed is not None:
            stream = self._wav_feed.open(callback)
        else:
            import sounddevice as sd
            stream = sd.InputStream(device=self._device(), samplerate=RATE, channels=1, dtype="float32",
                                    blocksize=BLOCK, callback=callback)
        # Built, the stream is already open: one whose start fails is closed, never kept as the open microphone (the
        # next start found it there and said the ear was on while it heard nothing).
        try:
            stream.start()
        except BaseException:
            stream.close()
            raise
        self._stream = stream

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
        if self._stream is not None:
            self._stream.close()
            self._stream = None
        while not self._blocks.empty():
            self._blocks.get_nowait()

    def _reset(self) -> None:
        self._heard += 1                # a transcription of what was heard before is not told
        self._early_back()
        self._audio = np.zeros(0, np.float32)
        self._speech = np.zeros(0, bool)  # Vad.marks of self._audio
        self._first = 0                 # absolute index of self._audio[0]
        self._total = 0                 # samples heard since the mode started
        self._start: float | None = 0.0 if self._mode == "direct" else None  # the request window's opening
        self._released = False          # push-to-talk let go (direct mode)
        self._partial_at = 0.0          # when what was said so far was last decoded
        self._partial = ""
        self._wake_at = 0.0             # when the detector was last reset (its times count from there)
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
            try:
                with self._lock:
                    heard = self._heard
                    job = self._feed(block) if self._mode != "off" and not self.speech.speaking else None
                if job is not None:
                    audio, wake_at, then = job
                    text = self._transcribe(audio, wake_at)
                    with self._lock:
                        if heard == self._heard:
                            then(text)
            except Exception as error:  # noqa: BLE001 - one bad block never ends the voice
                sys.stderr.write(f"baxy_mind_renew_voice: {error!r}\n")
                sys.stderr.flush()
                self._event("error")

    def _feed(self, block: np.ndarray) -> tuple[np.ndarray, float | None, Callable[[str], None]] | None:
        self._audio = np.concatenate([self._audio, block])
        self._speech = np.concatenate([self._speech, self._vad.marks(block)])
        self._total += len(block)
        if len(self._audio) > KEEP_S * RATE:
            cut = len(self._audio) - int(KEEP_S * RATE)
            self._audio, self._speech, self._first = self._audio[cut:], self._speech[cut:], self._first + cut
        if self._mode == "wake":
            # The detector keeps hearing during the request too, as in probar_baxy.py.
            now = self._total / RATE
            if (self._start is None and now - self._wake_at >= WAKE_RESET_S
                    and not self._speech[-int(WAKE_QUIET_S * RATE):].any()):
                self._detector.reset()
                self._wake_at = (self._total - len(block)) / RATE  # it hears from this block on
            self._wake_peak, raised = wake_gain(self._wake_peak, block)
            detections = self._detector.accept(raised)
            if self._start is None and detections:
                self._start = self._wake_at + detections[0].time_s
                self._partial = ""  # a new request's live caption is told even when it repeats the last one
                self._event("wake_detected")
                if self._on_wake is not None:
                    self._on_wake()
        start = self._start
        if start is not None and self._over(start):
            return self._finish(start)
        if start is not None:
            return self._early(start) or self._live(start)
        return None

    def _live(self, start: float) -> tuple[np.ndarray, float | None, Callable[[str], None]] | None:
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

        def then(text: str) -> None:
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
        """When the last block of voice of the request ended (the end of «Baxy» left out), or None before any."""
        blocks = self._request_voice(start)
        return start + (blocks[-1] + 1) * BLOCK / RATE if blocks else None

    def _request_voice(self, start: float) -> list[int]:
        """The blocks from ``start`` that are the speaker's voice (SPEAKER_DB), the end of «Baxy» left out."""
        a = self._at(start)
        wake = self._mode == "wake"
        level = self._speaker_level(self._at(start - CALL_BACK_S) if wake else a)
        if level is None:
            return []
        rms, speech = _blocks(self._audio[a:], self._speech[a:])
        voice_blocks = speech & (rms >= max(SPEAKER_FLOOR, level * 10 ** (-SPEAKER_DB / 20)))
        tail = (NOISY_TAIL_S if self._noisy(a) else WORD_TAIL_S) if wake else 0.0
        return [int(i) for i in np.flatnonzero(voice_blocks) if i * BLOCK / RATE >= tail]

    def _speaker_level(self, r: int) -> float | None:
        """The level of the one who speaks: the 80th percentile of the blocks of speech heard from ``r`` (None before
        any), so the nearest voice sets it even when a farther one spoke first."""
        rms, speech = _blocks(self._audio[r:], self._speech[r:])
        return float(np.percentile(rms[speech], 80)) if speech.any() else None

    def _noisy(self, a: int) -> bool:
        """Four in five blocks heard before the call (up to 1 s before the request opens at ``a``) are loud: the noise
        alone is above VOICE_RMS."""
        before = self._audio[:max(0, a - RATE)]
        before = before[len(before) % BLOCK:].reshape(-1, BLOCK)
        return len(before) > 0 and float(np.percentile(np.sqrt((before ** 2).mean(axis=1)), 20)) >= VOICE_RMS

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
        wait = end_silence(self._early_text) if self._early_text is not None and self._early_at == end else END_SILENCE_S
        # 1e-6: in direct mode 2.4 - 1.5 is 0.8999…, and 48 of 120 requests waited one block (100 ms) more
        return now - end >= wait - 1e-6

    def _early(self, start: float) -> tuple[np.ndarray, float | None, Callable[[str], None]] | None:
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

        def then(text: str) -> None:
            if text and text != self._partial:
                self._partial = text
                self._write({"type": "voice.event", "event": "partial", "mode": self._mode, "text": text})
            if text and self._on_early is not None and self._early_seq == seq and self._early_at == end:
                self._early_text = text
                self._on_early(seq, text)

        return self._segment(begin, now), start - begin if wake else None, then

    def _early_back(self) -> None:
        """The last early transcript no longer stands for the request (the person went on, or what was heard is
        dropped)."""
        if getattr(self, "_early_at", None) is not None and self._on_early is not None:
            self._on_early(self._early_seq, None)
        self._early_at = None
        self._early_text: str | None = None  # the early transcript of the voice up to _early_at, once decoded

    def _finish(self, start: float) -> tuple[np.ndarray, float | None, Callable[[str], None]]:
        # No voice after the early transcript: it was decoded from the same words with less silence after them, so it is
        # the request's transcript and nothing is decoded again (Deepgram Flux's EagerEndOfTurn without TurnResumed).
        early = self._early_text if self._early_at is not None and self._early_at == self._voice_end(start) else None
        self._start = None
        self._early_at = None  # the request's own transcript says whether the early one stands (early.py)
        wake = self._mode == "wake"
        begin = max(0.0, start - BEFORE_S) if wake else 0.0
        voiced_enough = len(self._request_voice(start)) * BLOCK / RATE >= MIN_VOICE_S
        stop = self._total / RATE if voiced_enough and early is None else begin
        self._event("transcribing")

        def then(text: str) -> None:
            text = without_call(early if early is not None and voiced_enough else text)
            if text:
                self._write({"type": "voice.transcript", "text": text})
            if not wake:
                # A direct request is one utterance; the voice goes back to what it was doing before.
                self._mode = self._resume
                self._resume = "off"
                if self._mode == "off":
                    self._close()
                self._reset()
            self._state()

        return self._segment(begin, stop), start - begin if wake else None, then

    def _transcribe(self, audio: np.ndarray, wake_at: float | None) -> str:
        peak = float(np.max(np.abs(audio))) if len(audio) else 0.0
        if peak < 0.008:
            return ""
        audio = audio * min(8.0, 0.45 / peak)  # the gain of probar_ultra.preparar
        stream = self._recognizer.create_stream(self._hotwords) if self._hotwords else self._recognizer.create_stream()
        stream.accept_waveform(RATE, np.ascontiguousarray(audio, dtype=np.float32))
        self._recognizer.decode_stream(stream)
        result = stream.result
        if wake_at is None:
            return result.text.strip()
        # The call is cut by time, whatever Ultra wrote for it: the words that began more than CALL_LEAD_S before the
        # trigger are «Baxy» and what was said before it. Measured on the owner's recordings (TranscripcionBaxy/corpus/
        # grabaciones): «Baxy» begins 0.5-0.75 s before the trigger and the request after it, so «Baxi, abre Steam.»
        # gives «abre Steam.», «Hola. Maxi. Abre Spotify» gives «Abre Spotify», and a bare «Baxi» gives nothing.
        words: list[list[Any]] = []
        for token, at in zip(result.tokens, result.timestamps):
            if token.startswith(" ") or not words:
                words.append([at, token])
            else:
                words[-1][1] += token
        words = [word for word in words if word[0] >= wake_at - CALL_LEAD_S]
        return "".join(word for _, word in words).strip()

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
