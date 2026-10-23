"""Voice for BAXY Renew: the microphone, the k4 wake word and Parakeet Ultra (sherpa-onnx, CPU), and BAXY's voice
speaking (Supertonic, voice_output.py).

Only the connection: what the person says after «Baxy» reaches the App as voice.transcript, the same as a typed
message. The segmentation is WakewordBaxy/probar_baxy.py's, measured there with the owner's voice; the recognizer is
TranscripcionBaxy's winner with its configuration. While BAXY speaks the microphone is not heard, as in Definitivo,
so its own voice («Hola, soy BAXY») never wakes it or enters a request.

Paths (per PC): BAXY_RENEW_WAKE_DIR (the baxy-wake-k4 package), BAXY_RENEW_STT_DIR (parakeet-ultra-sherpa-int8-oli),
BAXY_RENEW_MIC (an input device index; the default microphone otherwise).
"""
from __future__ import annotations

import importlib.util
import json
import os
import queue
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any, Callable

from . import stt_hotwords
from .voice_output import Speech

for _var in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_var, "1")

import numpy as np  # noqa: E402

RATE = 16000
BLOCK = 1600            # 100 ms
BEFORE_S = 2.0          # audio before the trigger that goes into the transcription
VOICE_RMS = 0.012       # voice threshold of TranscripcionBaxy/probar_ultra.py
END_SILENCE_S = 0.9     # silence that closes the request
WORD_TAIL_S = 0.4       # voice in the first 0.4 s after the trigger is the end of «Baxy», not the request
CALL_LEAD_S = 0.25      # a word that began this long before the trigger is the call (or came before it)
NO_COMMAND_S = 4.0      # after the trigger, time for the request to start
DIRECT_WAIT_S = 6.0     # direct mode (microphone button): time for the request to start
MAX_S = 12.0
KEEP_S = 30.0
PARTIAL_S = 0.8         # while a request is heard, what was said so far is decoded again this often (live captions)
WAKE_COPIES = 4         # staggered copies (StaggeredWake): 0.28 s p50 after the word, 0.46 s at most (1 copy: 1.18, 1.36)
NAMES_WAIT_S = 30.0     # the recognizer waits this long for catalog.configure's names (they come before voice.start)
HOTWORDS_PATHS = 4      # beam width when the names are hotwords
# Score per token of the names (scripts/voice/medir_hotwords.py, 1366 synthetic utterances, 2026-10-23): installed names
# heard 562 → 744 of 1012 (greedy → 1.5; 752 at 2, 767 at 3), WER 18.97 → 13.43 %, sentences without a name 2.96 →
# 3.41 % (spellings: «wifi» → «Wi-Fi»), names not installed 62 → 49 of 100, no name inserted, no empty result, decode
# p50 220 → 195 ms. 1.5 keeps almost all of the gain and costs less to the names not installed than 2 or 3.
HOTWORDS_SCORE = 1.5


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
    a firing of any of them counts once (the package's own re-arm, 2 s). Times are the audio's own, as the package's."""

    def __init__(self, make: Callable[[], Any], copies: int, rearm_s: float) -> None:
        self._copies = [make() for _ in range(copies)]
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
        self._recognizer: Any = None
        self._hotwords = ""             # the stream hotwords of the names the recognizer was built with
        self._names: list[str] | None = None
        self._named = threading.Event()
        self._input = False
        self.failure = ""
        self._mode = "off"
        self._resume = "off"            # the mode a direct request returns to
        self._stream: Any = None
        self._blocks: queue.Queue[np.ndarray] = queue.Queue()
        self._heard = 0                 # moved on by every reset and stop
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
            import sounddevice as sd
            try:
                sd.query_devices(self._device(), kind="input")
                self._input = True
            except Exception as error:  # noqa: BLE001
                self.failure = f"microphone: {error!r}"
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
        return int(value) if value.strip().isdigit() else None

    # --- microphone -----------------------------------------------------------------------------------------------

    def _open(self) -> None:
        if self._stream is not None:
            return
        import sounddevice as sd

        def callback(indata, _frames, _when, _status) -> None:
            self._blocks.put(np.array(indata[:, 0], dtype=np.float32, copy=True))  # the buffer is only valid here

        self._stream = sd.InputStream(device=self._device(), samplerate=RATE, channels=1, dtype="float32",
                                      blocksize=BLOCK, callback=callback)
        self._stream.start()

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
        self._first = 0                 # absolute index of self._audio[0]
        self._total = 0                 # samples heard since the mode started
        self._start: float | None = 0.0 if self._mode == "direct" else None  # the request window's opening
        self._released = False          # push-to-talk let go (direct mode)
        self._partial_at = 0.0          # when what was said so far was last decoded
        self._partial = ""
        if self._detector is not None:
            self._detector.reset()

    # --- listening ------------------------------------------------------------------------------------------------

    def _listen(self) -> None:
        """Ultra decodes outside the lock (up to MAX_S of audio, and every PARTIAL_S in a request): a release, a stop,
        a start or BAXY starting to speak never wait for it, and what they leave behind is not told."""
        while True:
            block = self._blocks.get()
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
        self._total += len(block)
        if len(self._audio) > KEEP_S * RATE:
            cut = len(self._audio) - int(KEEP_S * RATE)
            self._audio, self._first = self._audio[cut:], self._first + cut
        if self._mode == "wake":
            # The detector keeps hearing during the request too, as in probar_baxy.py.
            detections = self._detector.accept(block)
            if self._start is None and detections:
                self._start = detections[0].time_s
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
        self._partial_at = now
        wake = self._mode == "wake"
        begin = max(0.0, start - BEFORE_S) if wake else 0.0

        def then(text: str) -> None:
            if text and text != self._partial:
                self._partial = text
                self._write({"type": "voice.event", "event": "partial", "mode": self._mode, "text": text})

        return self._segment(begin, now), start - begin if wake else None, then

    def _segment(self, start_s: float, stop_s: float) -> np.ndarray:
        a = max(0, int(start_s * RATE) - self._first)
        b = max(a, int(stop_s * RATE) - self._first)
        return self._audio[a:b]

    def _voice_end(self, start: float) -> float | None:
        """When the last block of voice of the request ended (the end of «Baxy» left out), or None before any."""
        after = self._segment(start, self._total / RATE)
        frames = after[: len(after) // BLOCK * BLOCK].reshape(-1, BLOCK)
        voiced = np.flatnonzero(np.sqrt((frames ** 2).mean(axis=1)) >= VOICE_RMS) if len(frames) else []
        tail = WORD_TAIL_S if self._mode == "wake" else 0.0
        voiced = [i for i in voiced if i * BLOCK / RATE >= tail]
        return start + (voiced[-1] + 1) * BLOCK / RATE if voiced else None

    def _over(self, start: float) -> bool:
        if self._released:
            return True
        now = self._total / RATE
        if now - start >= MAX_S:
            return True
        end = self._voice_end(start)
        if end is None:
            return now - start >= (NO_COMMAND_S if self._mode == "wake" else DIRECT_WAIT_S)
        return now - end >= END_SILENCE_S

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
                self._on_early(seq, text)

        return self._segment(begin, now), start - begin if wake else None, then

    def _early_back(self) -> None:
        """The last early transcript no longer stands for the request (the person went on, or what was heard is
        dropped)."""
        if getattr(self, "_early_at", None) is not None and self._on_early is not None:
            self._on_early(self._early_seq, None)
        self._early_at = None

    def _finish(self, start: float) -> tuple[np.ndarray, float | None, Callable[[str], None]]:
        self._start = None
        self._early_at = None  # the request's own transcript says whether the early one stands (early.py)
        wake = self._mode == "wake"
        begin = max(0.0, start - BEFORE_S) if wake else 0.0
        self._event("transcribing")

        def then(text: str) -> None:
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

        return self._segment(begin, self._total / RATE), start - begin if wake else None, then

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
        self._on_spoken(queued, sounded, notice)

    def _lip(self, lip: dict[str, Any]) -> None:
        self._write({"type": "voice.event", "event": "lip", "mode": self._mode, **lip})

    def _state(self) -> None:
        self._write({"type": "voice.event", "event": "state", "mode": self._mode,
                     "speaking": self.speech.speaking})
