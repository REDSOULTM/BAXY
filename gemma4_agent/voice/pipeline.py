"""Voice pipeline orchestrator.

Composes audio_io → VAD → wake → state machine → STT → corrector
into a working voice-mode loop. Single state machine, single thread
(the AudioPump from audio_io.py).

States:
  IDLE      — listening for wake. VAD-gated wake detector runs.
  CAPTURE   — wake fired. Buffering command audio until end-of-speech.
  TRANSCRIBE— audio buffer being transcribed (blocking; brief).
  COOLDOWN  — small wait after transcribe to avoid immediate re-wake.

Callback API (on_command):
  on_command(text: str, audio_secs: float, raw_text: str) — called when
  a command is fully captured + transcribed + corrected. text is the
  final corrected version, raw_text is the pre-corrector Whisper output
  for debugging/observability.
"""
from __future__ import annotations

import logging
import threading
import time
from collections import deque
from enum import Enum
from typing import Callable

import numpy as np

from .audio_io import AudioCapture, CHUNK_SAMPLES, SAMPLE_RATE
from .corrector import FuzzyCorrector
from .inventory import build_hotwords, build_initial_prompt, get_inventory
from .stt import STT
from .vad import SileroVAD
from .wake import WakeDetector

logger = logging.getLogger(__name__)


import os as _os

# Default state machine timings. All overridable by env var so the
# operator can tune responsiveness vs patience without a code change.
PREROLL_SECONDS = 0.5            # audio kept before the wake event

# Hard cap on how long a single command can be (from wake to forced cut).
COMMAND_TIMEOUT_S = float(_os.environ.get("GEMMA4_VOICE_COMMAND_TIMEOUT_S", "8.0"))

# Trailing silence required to end CAPTURE (= cuánto silencio DESPUÉS del
# comando antes de transcribir). Este es el delay percibido al terminar de
# hablar, así que se mantiene lo más bajo posible sin cortar a mitad de frase.
#
# La pausa POST-WAKE (micro-pausa entre 'hey gemma' y el comando) NO debe
# regularse acá: ya está protegida por MIN_CAPTURE_S (el EOS no puede disparar
# en el primer 1.0s de captura). Subir este valor solo agrega latencia al FINAL
# sin proteger esa pausa. La literatura de VAD para comandos cortos
# (faster-whisper VAD: min_silence ~300ms; pausas naturales intra-comando
# ~200-400ms) indica que 0.8s es de sobra para no cortar a mitad de frase.
# Tunable por env si alguien habla muy pausado.
END_OF_SPEECH_SILENCE_S = float(_os.environ.get("GEMMA4_VOICE_EOS_SILENCE_S", "0.8"))

# Minimum capture duration before end-of-speech can fire at all. Guards
# against an immediate post-wake micro-pause closing the window before
# the user has said anything. Capture always runs at least this long.
MIN_CAPTURE_S = float(_os.environ.get("GEMMA4_VOICE_MIN_CAPTURE_S", "1.0"))

COOLDOWN_S = 0.4                 # post-transcribe wait

# VAD thresholds.
WAKE_GATE_THRESHOLD = 0.3        # let speech-y audio reach wake; reject ambient
EOS_VAD_THRESHOLD = 0.5          # stricter for end-of-speech

# --- Silence gate before transcription -------------------------------------
# Whisper HALLUCINATES on silence/near-silence: trained on YouTube captions,
# it emits artifacts like "¡Suscríbete!" / "Gracias por ver el video" / "..."
# when fed a buffer with no real speech. Guard:
# require the captured audio to contain at least one short window whose energy
# exceeds a speech floor, else skip transcription entirely (no command emitted).
#
# We use PEAK windowed RMS (not whole-clip RMS) so a brief command surrounded
# by the trailing-silence padding (EOS, ~0.8s) isn't diluted below the floor.
# int16 reference levels (16 kHz mic): quiet room RMS ~50-250, ambient/typing
# ~200-500, normal speech peaks ~800-4000. Default floor 350 sits above room
# noise / fan / keyboard but well below conversational speech. Env-tunable so
# the operator can raise it in a loud room or lower it for a quiet mic.
MIN_CAPTURE_RMS = float(_os.environ.get("GEMMA4_VOICE_MIN_CAPTURE_RMS", "350"))
# Window over which peak RMS is measured (seconds). 0.20s ~ a syllable; long
# enough to be robust to single-sample spikes, short enough to catch one word.
_RMS_WINDOW_S = float(_os.environ.get("GEMMA4_VOICE_RMS_WINDOW_S", "0.20"))


def _buffer_rms(audio: "np.ndarray") -> float:
    """Whole-buffer RMS of int16 PCM, in float64 (no overflow). 0.0 if empty.

    Used as a coarse energy floor for the silence gate. For short commands
    buried in trailing EOS-silence, prefer `peak_window_rms` (it doesn't get
    diluted); `_buffer_rms` is the simple aggregate the echo-guard spec uses.
    """
    if audio is None or audio.size == 0:
        return 0.0
    x = audio.astype(np.float64)
    return float(np.sqrt(np.mean(x * x)))


# Whisper hallucination artifacts on silence (trained on YouTube captions). If
# the transcript is ONLY one of these (or trivially so), it's almost certainly
# a silent/near-silent capture, not a real command — drop it. Matched against
# the accent-folded, lowercased, punctuation-stripped transcript so "¡Suscríbete!"
# and "SUSCRÍBETE" both hit. Kept as whole-string equality (not substring) so a
# real command CONTAINING one of these words ("suscríbete a este canal",
# "gracias, ahora pon música") is NOT dropped.
# Lista ampliada con la "Bag-of-Hallucinations" publicada (Barański et al.,
# AGH Kraków, arXiv 2501.11378) + Calm-Whisper fig.1 + outros típicos de
# YouTube en es/en. Whole-string match (folded) para no tocar comandos que
# CONTENGAN una de estas palabras.
_SILENCE_HALLUCINATIONS = frozenset({
    # --- original ---
    "suscribete", "suscribete a", "gracias por ver", "gracias por ver el video",
    "gracias por ver el vídeo", "subtitulos realizados por la comunidad de amara org",
    "subtitulos por la comunidad de amara org", "thanks for watching", "subscribe",
    "you", "thank you", "gracias", "subtitulos", "amara org",
    "subtitles by the amara org community",
    # --- español: outros / subtítulos ---
    "no olvides darle like", "dale like", "hasta la proxima", "hasta el proximo video",
    "subtitulos creados por la comunidad", "subtitulado por", "subtitulos por aegisub",
    "aegisub", "hola a todos", "bienvenidos a este canal", "bienvenidos al canal",
    "que tal amigos", "buenos dias a todos", "musica", "aplausos", "risas",
    "gracias por su atencion", "nos vemos en el proximo video",
    # --- inglés ---
    "thanks for watching!", "please subscribe", "like and subscribe",
    "see you next time", "music", "applause", "laughter", "i",
    "bye", "okay", "the end",
})


def _fold_for_match(text: str) -> str:
    """Lowercase, strip accents, collapse punctuation/whitespace -> for matching."""
    import unicodedata
    t = unicodedata.normalize("NFKD", (text or "").casefold())
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    # keep letters/digits/spaces only; collapse runs of space
    t = "".join(ch if (ch.isalnum() or ch.isspace()) else " " for ch in t)
    return " ".join(t.split())


def _is_silence_hallucination(text: str) -> bool:
    """True if `text` is (only) a known Whisper-on-silence artifact.

    Empty/whitespace -> False (handled separately as 'empty transcript'). A real
    command that merely contains one of these words is NOT flagged."""
    folded = _fold_for_match(text)
    if not folded:
        return False
    return folded in _SILENCE_HALLUCINATIONS


def _is_nonlexical_vocalization_token(token: str) -> bool:
    """True for a token whose shape is only a filler vocalization.

    This is deliberately structural, not a command/intent keyword list: a real
    utterance survives as soon as any lexical token appears.
    """
    t = (token or "").strip()
    if not t or any(ch.isdigit() for ch in t):
        return False
    chars = set(t)

    # Nasal hums: "mm", "mmm", "mmh", "mhm", "hmm", "nnn".
    if chars <= {"m", "n", "h"} and any(ch in t for ch in ("m", "n")):
        return True

    # Breath/vowel fillers: "uh", "eh", "ah", "oh", plus "um"/"em"/"uhm".
    if len(t) >= 2 and t[0] in {"a", "e", "o", "u"}:
        rest = t[1:]
        if set(rest) <= {"h"}:
            return True
        if t[0] in {"e", "u"} and set(rest) <= {"m", "h"} and "m" in rest:
            return True

    return False


def _is_filler_only_transcript(text: str) -> bool:
    """True when the whole transcript has no lexical content.

    Examples: "Mm-mm.", "mmh", "uh". False for "mm abre steam" or "no".
    """
    folded = _fold_for_match(text)
    if not folded:
        return False
    return all(_is_nonlexical_vocalization_token(tok) for tok in folded.split())


def peak_window_rms(audio: "np.ndarray", window_samples: int) -> float:
    """Return the maximum RMS over non-overlapping windows of `audio`.

    `audio` is int16 PCM. Returns 0.0 for empty input. Computed in float64 to
    avoid int16 overflow when squaring. A clip of pure silence -> ~0; a clip
    with one spoken word -> the RMS of that word's loudest 0.2s window.
    """
    if audio is None or audio.size == 0:
        return 0.0
    x = audio.astype(np.float64)
    w = max(1, int(window_samples))
    n_full = x.size // w
    peak = 0.0
    if n_full > 0:
        windows = x[: n_full * w].reshape(n_full, w)
        # RMS per window, then the max across windows.
        rms = np.sqrt(np.mean(windows * windows, axis=1))
        peak = float(rms.max())
    # Also consider the trailing partial window (a short command may not fill
    # a whole 0.2s window after the wake phrase is stripped).
    tail = x[n_full * w:]
    if tail.size:
        peak = max(peak, float(np.sqrt(np.mean(tail * tail))))
    return peak


class State(Enum):
    IDLE = "idle"
    CAPTURE = "capture"
    TRANSCRIBE = "transcribe"
    COOLDOWN = "cooldown"


CommandCallback = Callable[[str, float, str], None]


class VoicePipeline:
    """Voice-mode loop.

    Usage:
        pipe = VoicePipeline(on_command=lambda text, dur, raw: print(text))
        pipe.start()        # blocks until pipe.stop() called elsewhere
        ...
        pipe.stop()
    """

    def __init__(
        self,
        on_command: CommandCallback,
        on_state: Callable[[str], None] | None = None,
        on_wake_event: Callable[[], None] | None = None,
    ) -> None:
        self._on_command = on_command
        # Optional UI hooks: on_state(state_name) fires on every
        # state transition so the HUD can animate idle→listening→thinking;
        # on_wake_event() fires the instant the wake word triggers (for the
        # beep / "I heard you" feedback).
        self._on_state = on_state
        self._on_wake_event = on_wake_event
        self._vad = SileroVAD()
        self._wake = WakeDetector(on_wake=self._on_wake)
        # Motor STT por env GEMMA4_STT_ENGINE. DEFAULT: parakeet (sherpa-onnx
        # Parakeet-TDT-v3). MEDIDO sobre voz real: Parakeet+corrector EntRecall
        # comandos 81% [70,89] vs Whisper 70%, WER 0.26 vs 0.90, p50 78ms vs
        # 1593ms (21x), 0 regresión en voz de terceros, robusto a música de
        # fondo (88% @20dB SNR). Ambos exponen load()+transcribe(int16,...) ->
        # drop-in. GEMMA4_STT_ENGINE=whisper fuerza el motor viejo. La carga real
        # (con fallback a Whisper si el modelo Parakeet falta/falla) ocurre en
        # load() -> voz nunca queda rota.
        import os as _os
        self._stt_engine = _os.environ.get("GEMMA4_STT_ENGINE", "parakeet").lower()
        self._stt = self._build_stt(self._stt_engine)
        inv = get_inventory()
        self._corrector = FuzzyCorrector(inv)
        # Idioma-matriz del STT (env GEMMA4_VOICE_LANG, default 'es'). El prompt
        # y el `language` de Whisper se derivan del MISMO perfil para que un
        # usuario en otro idioma no quede con config española. Ver lang_profiles.
        from .lang_profiles import get_profile
        self._lang_profile = get_profile()
        self._initial_prompt = build_initial_prompt(inv, lang=self._lang_profile.code)
        self._hotwords = build_hotwords(inv)
        self._audio: AudioCapture | None = None

        # State machine state.
        self._state: State = State.IDLE
        self._state_lock = threading.Lock()

        # Optional: callable that returns True while the agent is
        # speaking (TTS busy). When set and returns True, wake detection
        # is paused to avoid self-triggering on Piper output going out
        # of the same speaker as the mic input. Software-mute path: pause
        # the wake detector instead of running acoustic echo cancellation.
        self._tts_busy_fn: Callable[[], bool] | None = None
        # True while wake detection is paused because TTS is speaking. Tracked
        # so the pause/resume is logged ONCE per transition (not per audio
        # chunk, which would spam ~12 lines/sec) — gives a single log line per
        # echo-gate fire/release instead of a flood.
        self._wake_paused_for_tts: bool = False

        # Pre-wake ring buffer (PREROLL_SECONDS worth of chunks).
        preroll_chunks = int(PREROLL_SECONDS * SAMPLE_RATE / CHUNK_SAMPLES)
        self._preroll: deque[np.ndarray] = deque(maxlen=preroll_chunks)

        # Command capture buffer (cleared on each capture start).
        self._capture_buf: list[np.ndarray] = []
        self._capture_start_ts: float = 0.0

        # End-of-speech detector: trailing silence accumulator.
        self._eos_silence_chunks_needed = int(
            END_OF_SPEECH_SILENCE_S * SAMPLE_RATE / CHUNK_SAMPLES
        )
        self._eos_silence_count: int = 0

        # Cooldown timer (set when entering COOLDOWN state).
        self._cooldown_until: float = 0.0

        # AUTO-CALIBRACIÓN del piso de ruido del micrófono (2026-06-07). El gate de
        # silencio fijo (MIN_CAPTURE_RMS=350) no es universal: en un mic ruidoso
        # queda por debajo del ambiente -> "oye voces donde no hay". Calibramos el
        # umbral al ruido REAL de cada mic (como Discord). Si el user fijó
        # GEMMA4_VOICE_MIN_CAPTURE_RMS a mano, lo RESPETAMOS y no calibramos.
        from .noise_calibration import NoiseFloorCalibrator
        self._noise_cal = NoiseFloorCalibrator()
        self._cal_window_rms: list[float] = []   # RMS de chunks IDLE para calibrar
        self._manual_rms_override = "GEMMA4_VOICE_MIN_CAPTURE_RMS" in _os.environ
        # nº de ventanas de ambiente a juntar antes de la 1ª calibración (~1.5s).
        self._cal_target = max(8, int(1.5 * SAMPLE_RATE / CHUNK_SAMPLES))

        self._loaded: bool = False
        self.last_error: str | None = None

    # ----- internal helpers --------------------------------------------

    @staticmethod
    def _build_stt(engine: str):
        """Construye el motor STT elegido. 'parakeet' -> ParakeetSTT; cualquier
        otra cosa -> Whisper STT. La carga (y el fallback) se hace en load()."""
        if engine == "parakeet":
            try:
                from .parakeet_stt import ParakeetSTT
                logger.info("STT engine: Parakeet-TDT-v3")
                return ParakeetSTT()
            except Exception as exc:  # import roto -> Whisper
                logger.warning("ParakeetSTT no disponible (%s); usando Whisper", exc)
        return STT()

    # ----- public API --------------------------------------------------

    def load(self) -> bool:
        if self._loaded:
            return True
        logger.info("VoicePipeline: loading components")
        if not self._vad.load():
            self.last_error = f"VAD load failed: {self._vad.last_error}"
            logger.warning(self.last_error)
            # Continue: VAD is optional (gate falls open if unavailable).
        if not self._wake.load():
            self.last_error = f"Wake load failed: {self._wake.last_error}"
            logger.error(self.last_error)
            return False
        if not self._stt.load():
            # FALLBACK: si Parakeet no carga (modelo ausente en esta máquina),
            # caemos a Whisper para que la voz NUNCA quede rota: el código
            # garantiza sus precondiciones, sin descargar setup en el usuario.
            if self._stt_engine == "parakeet":
                logger.warning(
                    "Parakeet STT no cargó (%s); fallback a Whisper-small",
                    self._stt.last_error,
                )
                self._stt = STT()
                self._stt_engine = "whisper"
            if not self._stt.load():
                self.last_error = f"STT load failed: {self._stt.last_error}"
                logger.error(self.last_error)
                return False
        self._loaded = True
        logger.info(
            "VoicePipeline ready: wake=%s, model=%s",
            "custom" if self._wake.using_custom_model else "stock_hey_jarvis",
            getattr(self._stt, "_model_size", type(self._stt).__name__),
        )
        return True

    def start(self) -> bool:
        if not self._loaded:
            if not self.load():
                return False
        self._audio = AudioCapture(on_chunk=self._on_chunk)
        ok = self._audio.start()
        if not ok:
            self.last_error = f"Audio start failed: {self._audio.last_error}"
            return False
        # AVISO si el mic default está MUTEADO en Windows (causa real 2026-06-07:
        # el user reportó "no oye" y su mic estaba silenciado a nivel sistema ->
        # captura ceros y parece STT roto). Solo avisamos; no podemos desmutearlo
        # sin tocar el audio del user. Best-effort (None si no se puede leer).
        try:
            from .noise_calibration import microphone_muted
            if microphone_muted() is True:
                logger.warning(
                    "MICRÓFONO DEFAULT MUTEADO en Windows: Baxy no oirá nada hasta "
                    "que lo desmutees (Sonido > Entrada > Volumen).")
                self._emit_state("MIC_MUTED")
        except Exception:
            pass
        logger.info("VoicePipeline started (state=IDLE)")
        return True

    def stop(self) -> None:
        if self._audio is not None:
            self._audio.stop()
            self._audio = None
        # Reset the state machine so a later start() (the UI toggles voice
        # off/on, reusing this SAME pipeline instance) resumes cleanly in IDLE.
        # Without this, a stop() mid-CAPTURE leaves _state=CAPTURE + a stale
        # _capture_buf; the next start()'s first chunk appends to that stale
        # buffer and can fire _finish_capture -> a phantom command transcribed
        # from the PREVIOUS session's audio.
        with self._state_lock:
            self._state = State.IDLE
        self._capture_buf = []
        self._eos_silence_count = 0
        self._preroll.clear()
        try:
            self._wake.reset()
            self._vad.reset()
        except Exception:
            pass
        logger.info("VoicePipeline stopped")

    @property
    def state(self) -> State:
        return self._state

    def set_tts_busy_fn(self, fn: Callable[[], bool] | None) -> None:
        """Register a callable that returns True while TTS is playing.
        The wake detector pauses while this returns True (software-mute
        echo avoidance: no acoustic echo cancellation needed).
        """
        self._tts_busy_fn = fn

    # ----- audio chunk handler (runs in AudioPump thread) -------------

    def _on_chunk(self, chunk: np.ndarray) -> None:
        """Single entry point from audio_io. Dispatches based on state."""
        with self._state_lock:
            st = self._state
        try:
            if st == State.IDLE:
                self._handle_idle(chunk)
            elif st == State.CAPTURE:
                self._handle_capture(chunk)
            elif st == State.COOLDOWN:
                self._handle_cooldown(chunk)
            # TRANSCRIBE: do nothing here; the transcribe runs synchronously
            # in the same thread before transitioning out.
        except Exception as exc:
            logger.exception("on_chunk handler crashed: %s", exc)

    def _handle_idle(self, chunk: np.ndarray) -> None:
        """In IDLE, keep preroll updated and run wake detection.

        Do NOT VAD-gate the wake input: the wake detector accumulates
        80 ms windows internally; if we drop chunks via a VAD gate
        upstream, we destroy that continuity and the wake never sees
        a complete window. Measured: a VAD gate upstream dropped recall
        from 7/105 to 0/105 on a held-out recording.

        So: feed wake EVERY chunk. The wake model's own threshold +
        the same_phrase_cooldown handle ambient-noise FP rejection
        adequately. The VAD is still used DOWNstream (end-of-speech
        detection during CAPTURE) where it belongs.
        """
        self._preroll.append(chunk)
        # AUTO-CALIBRACIÓN: en IDLE no hay comando activo -> los chunks son AMBIENTE.
        # Acumulamos su RMS para estimar el piso de ruido del mic. La 1ª calibración
        # ocurre tras juntar ~1.5s; luego, cada chunk IDLE re-ajusta lento (EMA) por
        # si el ambiente cambia. No toca el chunk (solo lo mide) -> no afecta al wake.
        # Se omite si el user fijó el umbral a mano (override explícito). getattr con
        # default seguro: tests que construyen el pipeline por __new__ (sin __init__)
        # no tienen estos atributos -> se comportan como antes (gate fijo).
        if not getattr(self, "_manual_rms_override", True) and \
                getattr(self, "_noise_cal", None) is not None:
            try:
                _rms = _buffer_rms(chunk)
                if not self._noise_cal.calibrated:
                    self._cal_window_rms.append(_rms)
                    if len(self._cal_window_rms) >= self._cal_target:
                        if self._noise_cal.calibrate(self._cal_window_rms):
                            logger.info(
                                "noise-floor calibrado: piso=%.0f -> umbral=%.0f "
                                "(mic auto-cal; era fijo %.0f)",
                                self._noise_cal.noise_floor or 0,
                                self._noise_cal.threshold or 0, MIN_CAPTURE_RMS)
                else:
                    self._noise_cal.observe_silence(_rms)
            except Exception:
                pass  # calibración best-effort: nunca rompe la escucha
        # Software-mute: pause wake detection while TTS is speaking.
        # Without echo cancellation, hearing 'gemma' in TTS output
        # would self-trigger via the mic. Logged on TRANSITION (not per
        # chunk) so each echo-gate fire/release is one log line, not a flood.
        if self._tts_busy_fn is not None:
            try:
                busy = bool(self._tts_busy_fn())
            except Exception:
                busy = False
            if busy:
                if not self._wake_paused_for_tts:
                    self._wake_paused_for_tts = True
                    logger.info("wake paused (Gemma hablando — anti-eco)")
                return
            if self._wake_paused_for_tts:
                self._wake_paused_for_tts = False
                logger.info("wake reanudado (TTS terminó)")
        # Feed wake unconditionally — no VAD gate. See docstring.
        self._wake.feed(chunk)

    def _handle_capture(self, chunk: np.ndarray) -> None:
        """In CAPTURE, buffer audio. Detect end-of-speech via VAD silence."""
        self._capture_buf.append(chunk)
        # Hard timeout check.
        elapsed = time.monotonic() - self._capture_start_ts
        if elapsed > COMMAND_TIMEOUT_S:
            logger.info("command capture timeout @ %.2fs", elapsed)
            self._finish_capture(reason="timeout")
            return
        # Don't allow end-of-speech to close the window before the
        # minimum capture time — protects against the natural micro-pause
        # right after "hey gemma" cutting off before the command is said.
        if elapsed < MIN_CAPTURE_S:
            return
        # End-of-speech via trailing silence.
        is_speech = self._vad.is_speech(chunk, threshold=EOS_VAD_THRESHOLD)
        if not is_speech:
            self._eos_silence_count += 1
            if self._eos_silence_count >= self._eos_silence_chunks_needed:
                logger.info(
                    "command end-of-speech detected after %.2fs",
                    elapsed,
                )
                self._finish_capture(reason="eos_silence")
        else:
            self._eos_silence_count = 0

    def _handle_cooldown(self, chunk: np.ndarray) -> None:
        """In COOLDOWN, just keep preroll updated. No wake detection."""
        self._preroll.append(chunk)
        if time.monotonic() >= self._cooldown_until:
            self._reset_to_idle("cooldown_done")

    # ----- state transitions ------------------------------------------

    def _emit_state(self, name: str) -> None:
        """Notify the UI of a state transition (best-effort)."""
        cb = self._on_state
        if cb is None:
            return
        try:
            cb(name)
        except Exception as exc:
            logger.debug("on_state callback raised: %s", exc)

    def _on_wake(self, phrase: str, score: float) -> None:
        """Wake fired. Transition IDLE -> CAPTURE.

        Runs inside _handle_idle via wake._predict_window; we hold no
        lock here (the caller is single-threaded by design).
        """
        # GATE DE ENERGÍA ANTI-FALSO-WAKE (2026-06-07): el wake recibe TODOS los
        # chunks sin gate (para no perder recall), y su threshold 0.25 a veces
        # dispara en SILENCIO/ruido (bug medido: transcribió 'Yeah'/'We've got' sin
        # que el user hablara). Decir "Baxy" SIEMPRE produce energía; el silencio
        # NUNCA. Validamos que el preroll (que contiene la frase de wake) tenga
        # energía sobre el piso calibrado del mic. Si no -> es un falso positivo:
        # rechazar el wake, seguir en IDLE. NO baja el recall (un wake real tiene
        # energía); mata los falsos en silencio. Universal (usa el piso por-mic).
        try:
            if self._preroll:
                _wake_rms = peak_window_rms(
                    np.concatenate(list(self._preroll)),
                    int(_RMS_WINDOW_S * SAMPLE_RATE))
                _gate = MIN_CAPTURE_RMS
                _cal = getattr(self, "_noise_cal", None)
                if not getattr(self, "_manual_rms_override", True) and \
                        _cal is not None and _cal.threshold is not None:
                    _gate = _cal.threshold
                if _wake_rms < _gate:
                    logger.info(
                        "wake RECHAZADO: preroll peak_rms=%.0f < %.0f -> falso "
                        "positivo en silencio (phrase=%s score=%.3f)",
                        _wake_rms, _gate, phrase, score)
                    self._wake.reset()
                    return
        except Exception:
            pass  # gate best-effort: ante error, dejar pasar (no romper el wake)
        with self._state_lock:
            if self._state != State.IDLE:
                logger.debug("wake during state=%s, ignoring", self._state.value)
                return
            self._state = State.CAPTURE
        self._capture_start_ts = time.monotonic()
        self._eos_silence_count = 0
        # Seed capture buffer with preroll (so we don't lose the wake
        # phrase itself + any tail leakage).
        self._capture_buf = list(self._preroll)
        logger.info(
            "wake -> CAPTURE (phrase=%s score=%.3f preroll_chunks=%d)",
            phrase, score, len(self._capture_buf),
        )
        # UI feedback: beep + "listening" animation the instant we wake.
        if self._on_wake_event is not None:
            try:
                self._on_wake_event()
            except Exception as exc:
                logger.debug("on_wake_event raised: %s", exc)
        self._emit_state("LISTENING")

    def _finish_capture(self, reason: str) -> None:
        """Transition CAPTURE -> TRANSCRIBE -> COOLDOWN."""
        with self._state_lock:
            if self._state != State.CAPTURE:
                return
            self._state = State.TRANSCRIBE
        self._emit_state("TRANSCRIBING")
        audio = (np.concatenate(self._capture_buf)
                 if self._capture_buf else np.zeros(0, dtype=np.int16))
        dur = audio.size / SAMPLE_RATE
        self._capture_buf = []

        # SILENCE GATE: skip Whisper entirely if the buffer has no real speech
        # energy. Prevents the "¡Suscríbete!" hallucination on silent captures
        # (woke on noise, or user said nothing). Measured as peak windowed RMS
        # so the trailing EOS-silence padding doesn't dilute a short command.
        peak_rms = peak_window_rms(audio, int(_RMS_WINDOW_S * SAMPLE_RATE))
        # Umbral EFECTIVO: el auto-calibrado al mic si calibró (y no hay override
        # manual), si no el fijo MIN_CAPTURE_RMS. Así el gate se adapta al ruido real.
        _gate = MIN_CAPTURE_RMS
        _cal = getattr(self, "_noise_cal", None)
        if not getattr(self, "_manual_rms_override", True) and \
                _cal is not None and _cal.threshold is not None:
            _gate = _cal.threshold
        if peak_rms < _gate:
            logger.info(
                "silence gate: peak_rms=%.0f < %.0f -> skip transcribe "
                "(reason=%s dur=%.2fs)", peak_rms, _gate, reason, dur,
            )
            # Tell the UI we heard nothing usable, so a user who DID try to speak
            # gets feedback instead of the HUD silently dropping back to idle
            # ("the mic ignored me"). NO_SPEECH -> brief cue, then idle.
            self._emit_state("NO_SPEECH")
            self._cooldown_until = time.monotonic() + COOLDOWN_S
            with self._state_lock:
                self._state = State.COOLDOWN
            self._wake.reset()
            self._vad.reset()
            self._emit_state("IDLE_LISTENING")
            return

        # VAD TRIM: recortar silencio lateral antes de Whisper.
        # El silencio al inicio/final es la causa #1 de alucinación en clips
        # cortos. Reseteamos el estado RNN del VAD (la detección de EOS ya lo
        # consumió) para un escaneo limpio. Si el VAD no está o falla, devuelve
        # el audio intacto (nunca rompe). El silence-gate de arriba ya garantizó
        # que hay energía de speech, así que trim no debería devolver None aquí.
        self._vad.reset()
        trimmed = self._vad.trim_silence(audio)
        if trimmed is not None and trimmed.size >= int(0.08 * SAMPLE_RATE):
            if trimmed.size < audio.size:
                logger.debug(
                    "vad trim: %.2fs -> %.2fs", dur, trimmed.size / SAMPLE_RATE,
                )
            audio = trimmed

        logger.info(
            "TRANSCRIBE start (reason=%s dur=%.2fs peak_rms=%.0f)",
            reason, audio.size / SAMPLE_RATE, peak_rms,
        )
        t0 = time.time()
        raw_text = self._stt.transcribe(
            audio, initial_prompt=self._initial_prompt,
            language=self._lang_profile.whisper_language,
            hotwords=self._hotwords,
        )
        # Strip wake phrase + fuzzy correct.
        stripped = self._corrector.strip_wake_phrase(raw_text)
        corrected = self._corrector.correct(stripped)
        elapsed = time.time() - t0
        logger.info(
            "TRANSCRIBE done in %.2fs: raw=%r -> final=%r",
            elapsed, raw_text[:80], corrected[:80],
        )
        # Enter cooldown BEFORE the callback so a fast re-wake from the
        # LLM/TTS path doesn't race us.
        self._cooldown_until = time.monotonic() + COOLDOWN_S
        with self._state_lock:
            self._state = State.COOLDOWN
        # Reset wake buffer so leftover audio doesn't immediately re-fire.
        self._wake.reset()
        self._vad.reset()
        # Emit the command (callback may do heavy work; we're already
        # in COOLDOWN so re-wakes are gated until it completes).
        try:
            if not corrected.strip():
                logger.info("empty transcript, no command emitted")
            elif _is_silence_hallucination(raw_text) or _is_silence_hallucination(corrected):
                # Audio passed the RMS gate but Whisper still produced one of its
                # canonical silence artifacts ("¡Suscríbete!", "Gracias por ver
                # el video", "you"...). Drop it — it is not a real command.
                logger.info(
                    "silence hallucination dropped: raw=%r corrected=%r",
                    raw_text[:60], corrected[:60],
                )
                self._emit_state("NO_SPEECH")
            elif (
                _is_filler_only_transcript(raw_text)
                or _is_filler_only_transcript(corrected)
            ):
                # Voiced non-speech passes the energy gate and can be
                # transcribed as "Mm-mm."; it is still not a command.
                logger.info(
                    "filler-only transcript dropped: raw=%r corrected=%r",
                    raw_text[:60], corrected[:60],
                )
                self._emit_state("NO_SPEECH")
            else:
                self._on_command(corrected, dur, raw_text)
        except Exception as exc:
            logger.exception("on_command callback raised: %s", exc)

    def _reset_to_idle(self, reason: str) -> None:
        with self._state_lock:
            self._state = State.IDLE
        self._preroll.clear()
        self._capture_buf = []
        self._eos_silence_count = 0
        logger.debug("-> IDLE (%s)", reason)
        self._emit_state("IDLE_LISTENING")
