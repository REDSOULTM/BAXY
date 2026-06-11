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

# EOS HÍBRIDO (2026-06-11): con audio de fondo (película/otras voces) el VAD ve
# speech CONTINUO y el fin-de-habla JAMÁS dispara — medido con el harness de
# cadena (scripts/voice_chain_eval.py): a SNR 5 dB, 75/84 capturas nunca
# cerraron → en prod, timeout de 8 s por comando + segundos de diálogo ajeno
# al LLM. La evidencia de que el USUARIO sigue hablando exige energía SOBRE el
# piso ambiente calibrado además del VAD: su voz sobre el fondo da ≥1.41× el
# piso incluso a SNR 0 (mezcla = √(1+10^(SNR/10))); cuando calla, el chunk
# vuelve a ≈1.0× piso aunque la peli siga. 1.25 separa ambos casos con margen.
# En sala silenciosa converge al comportamiento anterior (la voz supera el
# piso por mucho y el VAD ya decidía bien). Solo activo con piso calibrado.
_EOS_ENERGY_FACTOR = float(_os.environ.get("GEMMA4_VOICE_EOS_ENERGY_FACTOR", "1.25"))

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


def _energy_trim(audio: "np.ndarray", rms_threshold: float,
                 window_s: float = 0.05, pad_s: float = 0.15) -> "np.ndarray | None":
    """Recorta `audio` (int16) al sobre [primera..última] ventana cuyo RMS
    supera `rms_threshold`, con `pad_s` de margen a cada lado.

    Análogo a vad.trim_silence pero por ENERGÍA relativa al piso ambiente:
    funciona donde el VAD no puede (fondo hablado = todo es "speech" para el
    VAD, pero la voz del usuario es lo único que SUPERA el piso). None si
    ninguna ventana supera el umbral."""
    if audio is None or audio.size == 0:
        return None
    w = max(1, int(window_s * SAMPLE_RATE))
    n = audio.size // w
    if n == 0:
        return audio
    x = audio[: n * w].astype(np.float64).reshape(n, w)
    rms = np.sqrt(np.mean(x * x, axis=1))
    above = np.flatnonzero(rms > rms_threshold)
    if above.size == 0:
        return None
    pad = int(pad_s * SAMPLE_RATE)
    start = max(0, int(above[0]) * w - pad)
    end = min(audio.size, (int(above[-1]) + 1) * w + pad)
    return audio[start:end]


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
    def _whisper_disabled() -> bool:
        """True si Whisper está apagado (GEMMA4_STT_NO_FALLBACK / DISABLE_WHISPER):
        SOLO Parakeet, sin fallback. Si Parakeet no carga, la voz falla limpio en vez
        de caer a Whisper silenciosamente."""
        import os as _os_wd
        for _k in ("GEMMA4_STT_NO_FALLBACK", "GEMMA4_DISABLE_WHISPER"):
            if (_os_wd.environ.get(_k) or "").strip().lower() in {"1", "true", "yes", "on"}:
                return True
        return False

    # ----- rescate LID frase-corta (Parakeet v3) ------------------------
    # Palabras funcionales inglesas (clase cerrada) para detectar que la
    # SALIDA quedó en inglés. No es keyword-de-contenido: es la firma
    # estructural del idioma, igual que los marcadores fuertes es/pt/it del
    # agente. Conservador: exige ≥2 hits y CERO marcadores del idioma del
    # perfil para disparar.
    _EN_FUNCTION_WORDS = frozenset({
        "the", "is", "was", "are", "were", "it", "it's", "i", "i'm", "you",
        "let's", "don't", "isn't", "this", "that", "what", "what's", "really",
        "just", "up", "out", "worth", "see", "got", "we've", "guess",
    })
    # Marcadores del idioma objetivo (ortografía + funcionales cerradas).
    _TARGET_MARKERS = {
        # " en "/" sí " incluidos (2026-06-11): el caso code-switching MEDIDO
        # ("reproduce The Last of Us en HBO Max") conserva el conector "en" y
        # NO debe dispararse el rescate (whisper-es destruyó el título).
        "es": ("¿", "¡", "ñ", "á", "é", "í", "ó", "ú", " el ", " la ", " que ",
               " de ", " y ", " un ", " una ", " es ", " está ", " para ",
               " en ", " sí ", " con ", " mi "),
        "pt": ("ã", "õ", "ç", " o ", " a ", " que ", " de ", " é ", " um ",
               " uma ", " não ", " para "),
        "fr": (" le ", " la ", " est ", " je ", " tu ", " que ", " une ",
               " pas ", " c'est ", " à "),
        "de": ("ß", "ä", "ö", "ü", " der ", " die ", " das ", " ist ",
               " ich ", " du ", " nicht ", " ein "),
        "it": (" il ", " lo ", " la ", " è ", " che ", " di ", " un ",
               " una ", " non ", " per "),
    }

    def _looks_english_not_target(self, text: str) -> bool:
        """True si la transcripción parece INGLÉS y no tiene NI UN marcador
        del idioma del perfil — la firma del LID equivocado de Parakeet.
        Conservadora a propósito: el code-switching legítimo ("reproduce The
        Last of Us en HBO Max") conserva conectores del idioma ("en") y NO
        debe rescatarse — forzar es con Whisper destruye el título (MEDIDO
        2026-06-11 en el clip real: → "el ácido fós en HVOM")."""
        profile = getattr(self, "_lang_profile", None)
        if profile is None:
            return False
        low = f" {text.strip().lower()} "
        for marker in self._TARGET_MARKERS.get(profile.code, ()):
            if marker in low:
                return False
        words = [w.strip(".,;:!?\"'") for w in low.split()]
        hits = sum(1 for w in words if w in self._EN_FUNCTION_WORDS)
        return hits >= 2

    def _lid_rescue(self, audio: "np.ndarray", raw_text: str) -> str | None:
        """Re-transcribe con Whisper(language=fijo) cuando Parakeet cayó al
        inglés en una frase corta. Devuelve el texto rescatado o None.

        Gate GEMMA4_STT_LID_RESCUE=0 apaga. Whisper se carga LAZY al primer
        rescate (en el camino normal Parakeet carga solo) y queda residente.
        """
        import os as _os_lr
        if (_os_lr.environ.get("GEMMA4_STT_LID_RESCUE", "1") or "1").strip().lower() \
                in {"0", "false", "no", "off"}:
            return None
        # getattr defensivo: los tests construyen pipelines parciales sin estos
        # atributos — el rescate degrada a no-op, jamás rompe la transcripción.
        if getattr(self, "_stt_engine", "") != "parakeet":
            return None
        profile = getattr(self, "_lang_profile", None)
        if profile is None or profile.code == "en":
            return None  # el "fallo" sería el idioma correcto
        if not (raw_text or "").strip():
            return None
        try:
            max_s = float(_os_lr.environ.get("GEMMA4_STT_LID_RESCUE_MAX_S", "3.0"))
        except (TypeError, ValueError):
            max_s = 3.0
        if audio.size > int(max_s * SAMPLE_RATE):
            return None  # con contexto largo el LID de Parakeet es excelente
        if not self._looks_english_not_target(raw_text):
            return None
        t0 = time.time()
        mode = self._lid_rescue_mode()
        if mode == "subprocess":
            text = self._rescue_via_subprocess(audio)
        else:
            whisper = self._whisper_rescue_stt()
            if whisper is None:
                return None
            try:
                text = whisper.transcribe(
                    audio, initial_prompt=self._initial_prompt,
                    language=self._lang_profile.whisper_language,
                )
            except Exception as exc:
                logger.warning("lid_rescue transcribe failed: %s", exc)
                return None
        text = (text or "").strip()
        logger.info(
            "LID RESCUE [%s] (%.2fs extra): parakeet=%r -> whisper[%s]=%r",
            mode, time.time() - t0, raw_text[:60],
            self._lang_profile.whisper_language, text[:60],
        )
        self._persist_lid_rescue({
            "mode": mode,
            "extra_s": round(time.time() - t0, 2),
            "audio_s": round(audio.size / SAMPLE_RATE, 2),
            "lang": self._lang_profile.whisper_language,
            "parakeet": raw_text,
            "whisper": text or None,
        })
        return text or None

    @staticmethod
    def _persist_lid_rescue(payload: dict) -> None:
        """Evidencia PERSISTENTE de cada disparo del rescate. La línea de
        logging muere en la consola y full.log solo graba eventos del BUS,
        así que sin esto la zona del flip (que solo aparece en uso vivo) no
        deja rastro auditable. JSONL dedicado en el árbol de logs: sobrevive
        a todos los modos de ejecución (server, standalone) y el disparo es
        raro, así que el archivo queda diminuto. Nunca rompe la transcripción."""
        import datetime as _dt
        import json as _json
        import os as _os_p
        from pathlib import Path as _Path
        try:
            root = _os_p.environ.get("GEMMA4_AGENT_LOGS_DIR")
            base = (_Path(root).expanduser() if root
                    else _Path.home() / ".gemma4" / "logs")
            base.mkdir(parents=True, exist_ok=True)
            row = {"ts": _dt.datetime.now().isoformat(timespec="seconds"),
                   **payload}
            with (base / "stt_lid_rescue.jsonl").open("a", encoding="utf-8") as f:
                f.write(_json.dumps(row, ensure_ascii=False) + "\n")
        except Exception as exc:
            logger.debug("lid_rescue: no se pudo persistir evidencia: %s", exc)

    @staticmethod
    def _lid_rescue_mode() -> str:
        """resident | subprocess. El target de producto es 8 GB de RAM y
        Whisper-small residente cuesta ~686 MB (MEDIDO 2026-06-11; el unload
        in-process aún retiene ~418 MB en el allocator). `auto`: residente solo
        con RAM holgada; en el target, subproceso EFÍMERO (RAM permanente 0,
        ~5-7 s solo en el turno rescatado). Override GEMMA4_STT_LID_RESCUE_MODE.
        tiny DESCARTADO por medición: WER 0.897 en comandos reales (basura)."""
        import os as _os_m
        mode = (_os_m.environ.get("GEMMA4_STT_LID_RESCUE_MODE", "auto")
                or "auto").strip().lower()
        if mode in ("resident", "subprocess"):
            return mode
        try:
            import psutil
            total_gb = psutil.virtual_memory().total / 1e9
        except Exception:
            total_gb = 0.0
        try:
            floor = float(_os_m.environ.get("GEMMA4_STT_LID_RESIDENT_MIN_GB", "12"))
        except (TypeError, ValueError):
            floor = 12.0
        return "resident" if total_gb >= floor else "subprocess"

    def _rescue_via_subprocess(self, audio: "np.ndarray") -> str | None:
        """Transcribe el buffer en un worker efímero (_lid_rescue_worker.py):
        el SO recupera TODA la RAM al terminar. Para el target de 8 GB."""
        import subprocess
        import sys as _sys
        import tempfile
        import wave
        from pathlib import Path
        worker = Path(__file__).resolve().parent / "_lid_rescue_worker.py"
        tmp = None
        try:
            a16 = audio if audio.dtype == np.int16 else (
                np.clip(audio.astype(np.float32), -1.0, 1.0) * 32767).astype(np.int16)
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                tmp = Path(f.name)
            with wave.open(str(tmp), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(SAMPLE_RATE)
                w.writeframes(a16.tobytes())
            proc = subprocess.run(
                [_sys.executable, "-X", "utf8", str(worker), str(tmp),
                 self._lang_profile.whisper_language],
                capture_output=True, timeout=30,
            )
            if proc.returncode != 0:
                logger.warning("lid_rescue worker exit=%s stderr=%s",
                               proc.returncode,
                               proc.stderr.decode("utf-8", "replace")[:120])
                return None
            return proc.stdout.decode("utf-8", "replace").strip() or None
        except Exception as exc:
            logger.warning("lid_rescue subprocess falló: %s", exc)
            return None
        finally:
            try:
                if tmp is not None:
                    tmp.unlink(missing_ok=True)
            except Exception:
                pass

    def _whisper_rescue_stt(self):
        """Whisper-small residente para el rescate (solo modo resident:
        máquinas con RAM holgada), cargado LAZY al primer uso."""
        cached = getattr(self, "_whisper_rescue", None)
        if cached is not None:
            return cached if cached is not False else None
        try:
            t0 = time.time()
            w = STT()
            if not w.load():
                logger.warning("lid_rescue: Whisper no cargó (%s)", w.last_error)
                self._whisper_rescue = False
                return None
            logger.info("lid_rescue: Whisper cargado en %.1fs (residente)",
                        time.time() - t0)
            self._whisper_rescue = w
            return w
        except Exception as exc:
            logger.warning("lid_rescue: Whisper init falló: %s", exc)
            self._whisper_rescue = False
            return None

    @staticmethod
    def _build_stt(engine: str):
        """Construye el motor STT elegido. 'parakeet' -> ParakeetSTT; cualquier
        otra cosa -> Whisper STT. La carga (y el fallback) se hace en load()."""
        if engine == "parakeet":
            try:
                from .parakeet_stt import ParakeetSTT
                logger.info("STT engine: Parakeet-TDT-v3")
                return ParakeetSTT()
            except Exception as exc:  # import roto
                if VoicePipeline._whisper_disabled():
                    # Whisper apagado: NO caemos a Whisper, propagamos el fallo.
                    logger.error("ParakeetSTT no disponible (%s) y Whisper está "
                                 "DESHABILITADO (GEMMA4_STT_NO_FALLBACK)", exc)
                    raise
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
            # SALVO que Whisper esté apagado (GEMMA4_STT_NO_FALLBACK): entonces
            # falla limpio, SOLO Parakeet.
            if self._stt_engine == "parakeet" and not self._whisper_disabled():
                logger.warning(
                    "Parakeet STT no cargó (%s); fallback a Whisper-small",
                    self._stt.last_error,
                )
                self._stt = STT()
                self._stt_engine = "whisper"
            if not self._stt.load():
                self.last_error = (
                    f"STT load failed (Parakeet, Whisper deshabilitado): {self._stt.last_error}"
                    if self._whisper_disabled()
                    else f"STT load failed: {self._stt.last_error}")
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
        # AVISO si el mic default está MUTEADO en Windows: un mic silenciado a
        # nivel sistema captura ceros y parece STT roto. Solo avisamos; no podemos
        # desmutearlo sin tocar el audio del usuario. Best-effort (None si no se lee).
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
        # End-of-speech via trailing silence — TRI-ESTADO (2026-06-11).
        # Con fondo hablado (película/voces) el VAD oye "speech" para siempre y
        # el EOS binario jamás dispara (medido: 75/84 capturas atascadas a SNR 5
        # → timeout 8 s + diálogo ajeno al LLM). Decidimos contra el NIVEL
        # TÍPICO del fondo (p75-EMA del calibrador):
        #   - chunk QUIETO  (VAD-silencio  O  rms ≤ fondo×1.10): cuenta para EOS
        #   - evidencia de USUARIO (VAD-speech Y rms > fondo×1.25): resetea
        #   - zona GRIS (fluctuación del fondo): ni cuenta ni resetea — así una
        #     ráfaga de la película no reinicia el contador eternamente.
        # La voz sobre el fondo da ≥1.41× el nivel incluso a SNR 0; al callar,
        # el chunk vuelve a ~1.0×. En sala silenciosa el fondo es ínfimo y esto
        # converge al comportamiento clásico por VAD. Solo con auto-calibración.
        is_speech = self._vad.is_speech(chunk, threshold=EOS_VAD_THRESHOLD)
        _bg = None
        if not getattr(self, "_manual_rms_override", True):
            _cal = getattr(self, "_noise_cal", None)
            _bg = getattr(_cal, "background_level", None) if _cal is not None else None
        if _bg:
            _rms = _buffer_rms(chunk)
            quiet_chunk = (not is_speech) or _rms <= _bg * 1.10
            user_evidence = is_speech and _rms > _bg * _EOS_ENERGY_FACTOR
        else:
            quiet_chunk = not is_speech
            user_evidence = is_speech
        if quiet_chunk:
            self._eos_silence_count += 1
            if self._eos_silence_count >= self._eos_silence_chunks_needed:
                logger.info(
                    "command end-of-speech detected after %.2fs",
                    elapsed,
                )
                self._finish_capture(reason="eos_silence")
        elif user_evidence:
            self._eos_silence_count = 0
        # zona gris: el contador se mantiene (no suma ni resetea)

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
        # Cada wake nuevo trae su propia segunda-oportunidad (ver
        # _maybe_second_chance); el flag anti-loop se limpia acá.
        self._second_chance = False
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

        # ENERGY TRIM (2026-06-11): con fondo hablado (película/voces) el VAD no
        # puede recortar nada (todo el buffer es "speech") y el STT transcribe
        # también el diálogo ajeno ANTES y DESPUÉS de la voz del usuario que
        # quedó dentro de la ventana (preroll + cola EOS). La voz del usuario
        # vive donde la energía supera piso×factor — recortamos a ese sobre.
        # En sala silenciosa el piso es ínfimo y esto es no-op (el VAD trim de
        # abajo sigue haciendo su trabajo de siempre).
        if not getattr(self, "_manual_rms_override", True):
            _cal = getattr(self, "_noise_cal", None)
            _bg = getattr(_cal, "background_level", None) if _cal is not None else None
            if _bg:
                etrimmed = _energy_trim(audio, _bg * _EOS_ENERGY_FACTOR)
                if etrimmed is not None and \
                        etrimmed.size >= int(0.15 * SAMPLE_RATE) and \
                        etrimmed.size < audio.size:
                    logger.debug("energy trim: %.2fs -> %.2fs", dur,
                                 etrimmed.size / SAMPLE_RATE)
                    audio = etrimmed

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
        # RESCATE LID frase-corta (research 2026-06-10, implementado 2026-06-11):
        # el LID interno de Parakeet v3 NO se puede forzar y en frases cortas sin
        # contexto cae a INGLÉS (limitación OFICIAL de la model card: "not
        # recommended for word-for-word / incomplete sentences"). Si el perfil
        # del usuario es no-EN, el audio es corto y la salida parece inglés,
        # re-transcribimos ESE buffer con Whisper (que SÍ fija idioma). Paga
        # latencia solo en el caso malo; el 95% normal conserva Parakeet.
        rescued = self._lid_rescue(audio, raw_text)
        if rescued is not None:
            raw_text = rescued
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
        # Los drops de alucinación aplican solo a texto producido por WHISPER
        # (motor primario whisper o rescate LID): la lista viene de su modo de
        # fallo en silencio (YouTube-captions). Parakeet NO alucina en silencio
        # (medido, ver parakeet_stt.py) — con él, "gracias"/"okay" son palabras
        # REALES del usuario y deben llegar al LLM (regla de producto: el LLM
        # responde; descartarlas dejaba al usuario sin "de nada").
        whisper_text = (getattr(self, "_stt_engine", "whisper") != "parakeet"
                        or rescued is not None)
        try:
            if not corrected.strip():
                if self._maybe_second_chance(reason):
                    return
                logger.info("empty transcript, no command emitted")
            elif whisper_text and (
                    _is_silence_hallucination(raw_text)
                    or _is_silence_hallucination(corrected)):
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

    def _maybe_second_chance(self, finish_reason: str) -> bool:
        """SEGUNDA OPORTUNIDAD (2026-06-11, paridad Alexa): el usuario dijo solo
        "Baxy" y se quedó pensando — la captura cierra con transcript VACÍO tras
        el strip del wake y antes esto se descartaba EN SILENCIO (el usuario
        veía que el HUD volvía a idle sin escucharlo). Alexa mantiene la ventana
        de escucha abierta unos segundos. Reabrimos UNA vez la captura (flag
        anti-loop), re-emitimos el beep/estado LISTENING, y si tampoco dice nada
        la segunda ventana muere por gate de silencio como siempre. Solo para
        cierres por EOS (no para timeouts: ahí el usuario YA habló 8 s)."""
        if finish_reason != "eos_silence" or getattr(self, "_second_chance", False):
            self._second_chance = False
            return False
        self._second_chance = True
        with self._state_lock:
            self._state = State.CAPTURE
        self._capture_start_ts = time.monotonic()
        self._eos_silence_count = 0
        self._capture_buf = []
        logger.info("wake-solo: transcript vacío tras strip -> segunda "
                    "ventana de escucha")
        if self._on_wake_event is not None:
            try:
                self._on_wake_event()
            except Exception:
                pass
        self._emit_state("LISTENING")
        return True

    def _reset_to_idle(self, reason: str) -> None:
        with self._state_lock:
            self._state = State.IDLE
        self._preroll.clear()
        self._capture_buf = []
        self._eos_silence_count = 0
        logger.debug("-> IDLE (%s)", reason)
        self._emit_state("IDLE_LISTENING")
