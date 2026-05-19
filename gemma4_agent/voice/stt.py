"""Fase W — STT streaming con faster-whisper.

Reescrito 2026-05-15 segun el informe tecnico
docs/Optimizacion de faster-whisper small int8 CPU... (Gemma4 Voice Stack).md

Cambios clave vs version previa (resuelven "Hey Kema!", "abre estimulo",
"Aurestin!" y similares):

  1. initial_prompt saturado con "Gemma" y nombres de apps en espanol natural
     -> biasing fuerte para anglicismos OOV y para el nombre "Gemma".
  2. without_timestamps=False -> obliga al decoder a emitir timestamps,
     lo que lo "ancla" temporalmente y reduce alucinaciones (Sanchit Gandhi,
     HuggingFace; whisper-timestamped issue #105).
  3. Modo dual por duracion:
       - audio < 3 s (comando): beam=1, best_of=1, temperature=0.0
         (AGH 2501.11378 Tabla VI: greedy aluciona menos en clips cortos).
       - audio >= 3 s (dictado): beam=5, best_of=5, temperature=(0.0,0.2,0.4).
  4. Silero VAD trim previo (speech_pad_ms=100, NO los 400 default de
     faster-whisper). Si VAD no detecta speech -> rechazo total, no se llama
     a Whisper. Corta de raiz alucinaciones por silencio/ruido.
  5. Recorte de wake-word: el controller ya pasa solo el audio POST-wake
     como prefix_audio (patron A, estilo Alexa/Google). Aqui complementamos
     con strip regex del wake-word en post-procesado por defensa en
     profundidad.
  6. Quality check post-transcripcion con avg_logprob, no_speech_prob,
     compression_ratio, word-density y Bag of Hallucinations en espanol.
     Sin reintentos con temperatura distinta: la UX correcta es "no te he
     entendido" antes que ejecutar accion incorrecta.
  7. Postprocess: strip de wake-word residual + puntuacion sobrante.
  8. Preprocess: high-pass Butterworth 80 Hz (rumble/DC) + peak-normalize
     ligero a -1 dBFS solo si el audio esta bajito.
  9. cpu_threads = max(4, min(8, N_physical - 2)), OMP_NUM_THREADS sincronizado,
     warmup explicito tras carga.

CPU only. language="es" fijo.
"""
from __future__ import annotations

import logging
import os
import re
import time
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Literal

import numpy as np

logger = logging.getLogger(__name__)


WHISPER_MODEL_DIR = Path.home() / ".gemma4" / "models" / "whisper"
DEFAULT_MODEL_SIZE = "small"
SAMPLE_RATE = 16000
# Sprint P.2 2026-05-18: VAD_SILENCE_MS exposed via env var to
# allow A/B sweeps (500/700/800ms) without recompile. Default 500
# stays "Alexa-like" industry standard. The investigation post-N
# suggested 700ms; defer that calibration to a follow-up sprint
# with sweep data from real usage.
VAD_SILENCE_MS = int(os.environ.get("GEMMA4_VOICE_SILENCE_MS", "500"))
                            # endpoint RMS. 800ms se siente lento al usuario;
                            # 500ms es el "Alexa-like" estandar de la industria,
                            # y la grace de RMS+streak ya protege contra cortes
                            # prematuros mid-palabra (informe sec. 5.1).
ABSOLUTE_TIMEOUT_S = 15.0   # techo de seguridad
SHORT_AUDIO_THRESHOLD_S = 3.0  # frontera modo comando vs dictado


# ---------------------------------------------------------------------------
# Prompting / biasing (informe sec. 2.2, 12.2.2)
# ---------------------------------------------------------------------------
# El prompt dinamico se construye con apps reales del sistema via
# app_inventory.py. FALLBACK_INITIAL_PROMPT es la red de seguridad cuando
# el inventario no esta disponible (primer arranque sin cache + discovery
# fallo, sistema no Windows, AppResolver crasheo).
#
# Repetir "Gemma" muchas veces sesga al decoder a esperar esa palabra
# (resuelve "Hey Kema!"). Las apps en grafia inglesa correcta sesgan
# contra "abre estimulo" -> "abre Steam". Texto en espanol natural con
# puntuacion (OpenAI Cookbook recomienda ese patron explicitamente).
FALLBACK_INITIAL_PROMPT = (
    "Conversacion con el asistente Gemma. "
    "Hey Gemma, abre Steam. Hey Gemma, abre Spotify y reproduce musica. "
    "Hey Gemma, abre Discord, VS Code, Chrome, Firefox, YouTube, Netflix, "
    "Twitch, WhatsApp, Telegram, Visual Studio Code, Notepad, Explorer, OBS, "
    "Counter-Strike 2, GTA V. "
    "Hey Gemma, apaga la luz del salon. Hey Gemma, enciende la luz de la cocina. "
    "Hey Gemma, sube el volumen. Hey Gemma, baja el volumen. Hey Gemma, pausa la musica. "
    "Hey Gemma, pon el temporizador a cinco minutos. Hey Gemma, que hora es. "
    "Hey Gemma, como esta el tiempo en Madrid. Hey Gemma, busca en Google. "
    "Hey Gemma, cierra la ventana. Hey Gemma, minimiza la ventana. "
    # Sprint R3.1: messaging/search verbs that appeared in operator's
    # testaudio with high WER (e.g. 'mandale un mensaje a Juan',
    # 'buscame info sobre Benson Boone') -- give the decoder strong
    # priors for these specific command patterns.
    "Hey Gemma, mandale un mensaje a Juan por WhatsApp. "
    "Hey Gemma, mandale un mensaje a Maria. "
    "Hey Gemma, buscame info sobre Benson Boone. "
    "Hey Gemma, reproduce Bohemian Rhapsody. "
    "Hey Gemma, reproduce algo de los redonditos. "
    "Hey Gemma, ponme musica tranquila. "
    "Hey Gemma, cuando salio GTA V. "
    "Comandos breves en espanol rioplatense dirigidos al asistente Gemma."
)


def get_initial_prompt() -> str:
    """Devuelve el prompt dinamico si esta disponible, fallback si no.

    Se evalua en cada transcripcion (no en import-time) para que el
    refresh asincrono del inventario tome efecto sin reiniciar el proceso.
    """
    try:
        from gemma4_agent.voice.app_inventory import get_cached_prompt
        prompt = get_cached_prompt()
        if prompt and "Gemma" in prompt:
            return prompt
    except Exception as exc:
        logger.debug("dynamic prompt unavailable, using fallback: %s", exc)
    return FALLBACK_INITIAL_PROMPT


# ---------------------------------------------------------------------------
# Bag of Hallucinations en espanol (informe sec. 9.1)
# Frases tipicas que Whisper inyecta cuando ve silencio o audio ininteligible
# (priors del corpus YouTube en espanol).
# ---------------------------------------------------------------------------
SPANISH_HALLUCINATION_PHRASES = (
    "suscribete",
    "suscribete al canal",
    "no olvides darle like",
    "dale like",
    "gracias por ver",
    "gracias por ver el video",
    "hasta la proxima",
    "hasta el proximo video",
    "subtitulos realizados por la comunidad de amara.org",
    "subtitulos por la comunidad de amara",
    "subtitulos creados por la comunidad",
    "amara.org",
    "subtitulado por",
    "aegisub",
    "hola a todos",
    "bienvenidos a este canal",
    "bienvenidos al canal",
    "que tal amigos",
    # Sound-effect tags Whisper sometimes hallucinates in silence.
    # Keep only the bracketed/parenthesized forms; the standalone
    # word "musica" was removed 2026-05-18 (hotfix M) because it
    # falsely rejected legitimate user requests like "pon musica"
    # (7 silent rejects observed in real session 12:08 — diagnosed
    # via Sprint L recordings). See manifest at
    # ~/.gemma4/recordings/20260518_120744/manifest.jsonl.
    "[musica]",
    "(musica)",
    "[aplausos]",
    "(aplausos)",
    "[risas]",
    "(risas)",
)


def _strip_diacritics(text: str) -> str:
    """Normalizacion para BoH match: minusculas + sin tildes."""
    import unicodedata
    text = unicodedata.normalize("NFKD", text.casefold())
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def looks_like_hallucination(text: str) -> bool:
    """True si el texto matchea una frase tipica del Bag of Hallucinations.

    Logica conservadora: requiere que la frase aparezca completa Y que la
    transcripcion no sea mucho mas larga que la frase (informe sec. 9.1).
    Asi NO descartamos transcripciones legitimas donde "gracias" aparece
    como parte de una frase mas larga ("ok gracias por confirmar").
    """
    t = _strip_diacritics(text).strip().rstrip(".!?,;: ")
    if not t:
        return False
    for phrase in SPANISH_HALLUCINATION_PHRASES:
        p = _strip_diacritics(phrase)
        if p in t and len(t) < len(p) + 20:
            return True
    return False


def _has_pathological_ngram_repetition(text: str) -> bool:
    """Detecta repeticion patologica de n-gramas (informe sec. 9.2).

    Sprint O 2026-05-18 calibration: the previous absolute threshold
    (`dups > 2`) rejected legitimate operator rapid-fire ("Gemma X.
    Gemma X. Gemma Y. Gemma Y.") on 3/6 testaudio turns -- those are
    real speech, not Whisper hallucinations, and contained natural
    duplicate n-grams from the user repeating commands.

    The fix is length-scaled: a longer turn can afford more
    duplicates before looking pathological. Threshold becomes
    `dups > max(2, len(ngrams) // 2)`. Whisper hallucination loops
    ("gracias por ver el video" repeated 10x) still hit ~0.9 ratio
    and trip the gate; natural human repetition hits ~0.3-0.4 and
    passes.
    """
    words = text.lower().split()
    if len(words) < 6:
        return False
    for n in (2, 3):
        ngrams = [tuple(words[i:i + n]) for i in range(len(words) - n + 1)]
        if not ngrams:
            continue
        dups = len(ngrams) - len(set(ngrams))
        threshold = max(2, len(ngrams) // 2)
        if dups > threshold:
            return True
    return False


# ---------------------------------------------------------------------------
# Preprocesado de audio (informe sec. 6.4)
# ---------------------------------------------------------------------------
# scipy import en module-level (NO lazy): el "lazy" hacia `from scipy.signal
# import sosfilt` dentro de _preprocess, lo que paga ~470ms de cold-import en
# la PRIMERA transcripcion (critical path: usuario espera el texto). Como
# _preprocess se llama siempre que se transcribe, no hay ahorro real con lazy
# - solo penalizacion al usuario. Movido a top-level. Si scipy falta, _HPF_SOS
# queda None y _preprocess salta el filtro silenciosamente.
try:
    from scipy.signal import butter as _butter, sosfilt as _sosfilt
    _HPF_SOS: Any = _butter(4, 80, btype="highpass", fs=SAMPLE_RATE, output="sos")
except Exception as _exc:  # pragma: no cover - scipy esta en requirements
    logger.info("scipy unavailable for high-pass (%s); skipping HPF", _exc)
    _HPF_SOS = None
    _sosfilt = None  # type: ignore[assignment]


def _preprocess(audio_int16: np.ndarray) -> np.ndarray:
    """int16 -> float32 [-1,1] con HPF 80 Hz + peak-normalize ligero."""
    audio = audio_int16.astype(np.float32) / 32768.0
    if _HPF_SOS is not None and _sosfilt is not None:
        try:
            filtered = np.asarray(_sosfilt(_HPF_SOS, audio), dtype=np.float32)
            audio = filtered
        except Exception as exc:
            logger.debug("sosfilt failed (%s); skipping HPF", exc)
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    # Solo subir audio bajito; no comprimir audio normal/alto (riesgo clipping).
    if 0 < peak < 0.5:
        audio = audio * (0.89 / peak)  # ~-1 dBFS
    return audio


# ---------------------------------------------------------------------------
# Silero VAD trim (informe sec. 5, 12.2.4)
# ---------------------------------------------------------------------------
class _SileroVAD:
    """Wrapper lazy de silero-vad. ONNX en CPU procesa 1s en ~15ms.

    Devolvemos None si la lib no esta o si la carga falla: el caller
    se salta el trim y pasa el audio crudo a Whisper (degradacion suave).
    """

    def __init__(self) -> None:
        self._model: Any = None
        self._get_speech_timestamps: Any = None
        self._loaded: bool = False
        self._failed: bool = False

    def load(self) -> bool:
        if self._loaded:
            return True
        if self._failed:
            return False
        try:
            import torch
            from silero_vad import get_speech_timestamps, load_silero_vad
        except Exception as exc:
            logger.warning("silero-vad unavailable: %s", exc)
            self._failed = True
            return False
        try:
            # torch.set_num_threads exists at runtime but isn't in the
            # public re-exports torch declares for the stub, so pyright
            # flags it as a private import; suppress is correct here.
            torch.set_num_threads(1)  # type: ignore[attr-defined]  # importante en CPU (informe 5.4)
            self._model = load_silero_vad(onnx=True)
            self._get_speech_timestamps = get_speech_timestamps
            self._loaded = True
            logger.info("Silero VAD loaded (onnx)")
            return True
        except Exception as exc:
            logger.warning("Silero VAD init failed: %s", exc)
            self._failed = True
            return False

    def trim(self, audio_f32: np.ndarray) -> np.ndarray | None:
        """Devuelve audio recortado a chunks de speech o None si no hay speech.

        speech_pad_ms=100 (NO los 400 del default de faster-whisper, que
        anaden ~800 ms totales y matan latencia). min_silence_duration_ms=300
        permite cortar pausas naturales en comandos cortos.
        """
        if not self._loaded:
            return audio_f32  # no se cargo -> pasar audio crudo
        try:
            ts = self._get_speech_timestamps(
                audio_f32,
                self._model,
                sampling_rate=SAMPLE_RATE,
                threshold=0.5,
                min_speech_duration_ms=200,
                min_silence_duration_ms=300,
                speech_pad_ms=100,
            )
        except Exception as exc:
            logger.warning("silero get_speech_timestamps failed: %s", exc)
            return audio_f32
        if not ts:
            return None  # rechazar: no speech detectado
        start = int(ts[0]["start"])
        end = int(ts[-1]["end"])
        return audio_f32[start:end]

    def predict_chunk(self, chunk: np.ndarray) -> float:
        """Return speech probability (0.0 to 1.0) for a single 32ms
        chunk (CHUNK_SAMPLES=512 at SAMPLE_RATE=16kHz).

        Returns 0.0 if Silero is not loaded or if the model raised
        (e.g. wrong chunk size, transient torch error) — the caller
        is responsible for falling back to RMS.

        Sprint P.2 2026-05-18: exposed for use as endpoint detection
        signal in transcribe_stream. Previously the model was used
        only for pre-Whisper trim via .trim().
        """
        if not self._loaded or self._model is None:
            return 0.0
        try:
            import torch
            chunk_f32 = chunk.astype(np.float32) / 32768.0
            tensor = torch.from_numpy(chunk_f32)
            with torch.no_grad():
                prob = self._model(tensor, SAMPLE_RATE).item()
            return float(prob)
        except Exception as exc:
            logger.debug("silero predict_chunk failed: %s", exc)
            return 0.0

    def unload(self) -> None:
        """Libera el modelo ONNX de RAM pero respeta el flag _failed.

        Si el primer load() fallo (silero-vad no instalado o init crashed),
        _failed=True persiste asi un unload/reload no reintenta cargas que
        sabemos que fallan. Si _failed es False, dejamos el wrapper listo
        para un reload limpio.
        """
        self._model = None
        self._get_speech_timestamps = None
        self._loaded = False


@dataclass(frozen=True)
class STTEvent:
    """Evento emitido por el iterator de transcripcion.

    Hotfix M.1.3 2026-05-18: `reject_reason` carries the specific
    rejection reason ('BoH_match' / 'low_logprob' / 'no_speech' /
    'too_short' / etc) when `kind=='final'` and `text==''`. Allows
    the recorder manifest to log the diagnostic reason instead of
    a generic placeholder.

    Hotfix M.2.3 2026-05-18: `raw_text` carries what Whisper
    produced BEFORE the quality_check killed it. Equal to `text`
    when `reason='ok'`; populated on reject so post-hoc diagnosis
    doesn't require re-running Whisper on the recorded WAV.
    Empty when there was no Whisper text at all (no_speech /
    too_short pre-Whisper rejects).
    """
    kind: Literal["partial", "final", "timeout", "error"]
    text: str = ""
    error: str = ""
    reject_reason: str = ""
    raw_text: str = ""


# Tipo del iterator de audio: yields np.int16 arrays (cualquier longitud).
AudioIter = Iterator[np.ndarray]


# ---------------------------------------------------------------------------
# Configuracion modo dual (informe sec. 12.2.5)
# ---------------------------------------------------------------------------
# Base comun. NO se ponen aqui parametros que cambian entre corto/largo.
# initial_prompt NO va aqui: se inyecta en _run_whisper via get_initial_prompt()
# para que el prompt dinamico (app_inventory) tome efecto sin reimportar.
_BASE_KWARGS = dict(
    language="es",
    task="transcribe",
    patience=1.0,
    length_penalty=1.0,
    compression_ratio_threshold=2.4,
    log_prob_threshold=-1.0,
    no_speech_threshold=0.6,
    condition_on_previous_text=False,
    suppress_blank=True,
    suppress_tokens=[-1],         # default no-speech tokens; filtrado de BoH
                                  # se hace por texto (informe 2.4: suprimir
                                  # ids individuales rompe casos legitimos).
    without_timestamps=False,     # CAMBIO CLAVE: anclar al decoder
    vad_filter=False,             # VAD manual via _SileroVAD pre-Whisper
)

SHORT_KWARGS = {
    **_BASE_KWARGS,
    "beam_size": 1,
    "best_of": 1,
    "temperature": 0.0,
}

LONG_KWARGS = {
    **_BASE_KWARGS,
    "beam_size": 5,
    "best_of": 5,
    "temperature": (0.0, 0.2, 0.4),
}


def _get_transcribe_kwargs(duration_s: float) -> dict:
    return SHORT_KWARGS if duration_s < SHORT_AUDIO_THRESHOLD_S else LONG_KWARGS


# ---------------------------------------------------------------------------
# Plan B: skill-prefix biasing (informe sec. 8.4)
# ---------------------------------------------------------------------------
# Cuando el modo SHORT con beam=1 no logra reconocer un anglicismo
# tras el verbo (ej: "abre Steam" -> "Abrastim"), un re-intento con
# prefix="abre " fuerza al decoder a empezar con esos tokens y reconoce
# mejor el resto. Solo se aplica una vez y solo en modo corto.
COMMAND_VERBS_ES = (
    "abre", "cierra", "apaga", "enciende", "sube", "baja",
    "pausa", "reproduce", "busca", "minimiza", "maximiza", "abrir",
)


# Prefijo unico mas corto que distingue cada verbo. Usado para detectar
# casos donde Whisper pega el verbo al sustantivo OOV ("Abrastim" =
# "abre" + "stim/Steam"). Sin esto, Plan B nunca se dispara para audios
# cortos sin pausa entre verbo y nombre.
_VERB_PREFIXES = {
    "abr": "abre",
    "cie": "cierra",
    "apa": "apaga",
    "enc": "enciende",
    "sub": "sube",
    "baj": "baja",
    "pau": "pausa",
    "rep": "reproduce",
    "bus": "busca",
    "min": "minimiza",
    "max": "maximiza",
}


def _detect_command_verb(text: str) -> str | None:
    """Devuelve el verbo de comando si el texto parece empezar por uno.

    Dos modos:
      1. EXACT: texto empieza por verbo seguido de space/puntuacion
         ("abre Steam", "Cierra Chrome.")
      2. SUBSTRING: texto empieza por prefijo de 3-letras de un verbo
         pero NO es un word separado ("Abrastim" -> "abre"). Esto pasa
         cuando Whisper pega verbo + sustantivo OOV en una sola palabra,
         que es exactamente el caso que Plan B existe para resolver.
    """
    if not text:
        return None
    cleaned = _postprocess_text(text).lower().lstrip()
    if not cleaned:
        return None
    # Modo 1: verbo separado (caso comun, audio claro)
    first = cleaned.split(None, 1)[0].rstrip(",.!?;:¡¿")
    if first in COMMAND_VERBS_ES:
        return first
    # Modo 2: verbo pegado al siguiente token. Aplicamos solo si el primer
    # token es UNA sola palabra >5 chars (caso "Abrastim"). Si el texto ya
    # tiene multiples palabras, confiamos en el modo 1.
    if len(cleaned.split()) == 1 and len(first) >= 5:
        for prefix, verb in _VERB_PREFIXES.items():
            if first.startswith(prefix):
                return verb
    return None


# Regex para strip de wake-word residual al inicio. Defensa en profundidad:
# el controller ya corta el wake-word antes (patron A), pero si Vosk reporta
# un end inexacto puede quedar una cola fonetica que Whisper transcriba como
# "gemma", "hey gemma", "tema", "kema". Solo eliminamos las dos primeras
# (no "tema" porque puede ser palabra legitima).
_WAKE_PREFIX_RE = re.compile(r"^\s*(hey\s+)?gemma[\s,!.¡¿]*", re.IGNORECASE)


def _postprocess_text(text: str) -> str:
    """Limpieza final: strip wake-word residual + puntuacion sobrante."""
    if not text:
        return text
    text = _WAKE_PREFIX_RE.sub("", text)
    text = text.strip(" ,.!?¡¿;:")
    return text


class StreamingSTT:
    """Mantiene state de transcripcion para una sesion (un wake -> un final).

    Uso:
        stt = StreamingSTT()
        if stt.load():
            for ev in stt.transcribe_stream(audio_iter):
                if ev.kind == "partial": ...
                if ev.kind == "final": break
    """

    def __init__(self, model_size: str | None = None) -> None:
        env_model = (os.environ.get("GEMMA4_VOICE_STT_MODEL") or "").strip().lower()
        self._model_size = model_size or env_model or DEFAULT_MODEL_SIZE
        self._whisper = None  # type: ignore[assignment]
        self._loaded: bool = False
        self.last_error: str | None = None
        self._vad = _SileroVAD()
        self._warmed_up: bool = False

    def load(self) -> bool:
        """Carga faster-whisper + Silero VAD. Lazy.

        Configura cpu_threads = max(4, min(8, N_physical - 2)) y sincroniza
        OMP_NUM_THREADS (informe sec. 10.1, 10.7).

        ============================================================
        DEFERRED — item 2.3 del optimization_roadmap.md:
        NVIDIA Parakeet-TDT-0.6B-v3 como backend STT alternativo.
        Pros: RTF muy alto, multilingue nativo (25 idiomas eu, español
        incluido), modelo RNN-T optimizado streaming.
        Cons:
          - Requiere dep nueva pesada (nemo-toolkit ~1 GB de wheels),
            ROMPE la restriccion "cero deps pesadas" del brief.
          - Licencia NVIDIA Community Model License: requiere revision
            legal del dev antes de usar comercialmente.
          - WER es-MX no medido contra Common Voice 17.
        Decision: DEFERRED hasta que (a) dev acepte la dep, (b) revise
        licencia, (c) tenga set de A/B con jiwer contra Whisper-small.
        Mientras tanto Whisper-small int8 CPU sigue como STT primario.
        ============================================================
        """
        # Serialize the heavy import against NLI/transformers warmup running
        # on another thread. Without this lock, an interleaved import of
        # huggingface_hub from two threads can surface as
        # "cannot import name 'logging' from huggingface_hub" on STT init.
        try:
            from .._ml_import_lock import ml_imports
        except ImportError:
            # Fallback no-op if the helper is unavailable for some reason.
            from contextlib import contextmanager
            @contextmanager
            def ml_imports():  # type: ignore[no-redef]
                yield
        try:
            with ml_imports():
                import huggingface_hub  # noqa: F401
                from huggingface_hub import logging as _hf_logging  # noqa: F401
                from faster_whisper import WhisperModel
        except ImportError as exc:
            self.last_error = f"faster-whisper not installed: {exc}"
            return False
        WHISPER_MODEL_DIR.mkdir(parents=True, exist_ok=True)

        # cpu_threads tuning para no pelearse con Gemma en GPU/CPU.
        try:
            import psutil
            n_phys = psutil.cpu_count(logical=False) or 4
        except Exception:
            n_phys = 4
        cpu_threads = max(4, min(8, n_phys - 2))
        # OMP afecta a numpy/scipy/oneDNN auxiliares; sincronizarlo evita
        # over-subscription cuando preprocess/VAD corren en paralelo a whisper.
        os.environ.setdefault("OMP_NUM_THREADS", str(cpu_threads))

        try:
            self._whisper = WhisperModel(
                self._model_size,
                device="cpu",
                compute_type="int8",
                cpu_threads=cpu_threads,
                num_workers=1,
                download_root=str(WHISPER_MODEL_DIR),
            )
        except Exception as exc:
            self.last_error = f"whisper init failed ({self._model_size}): {type(exc).__name__}: {exc}"
            logger.error(self.last_error)
            return False

        # VAD es opcional: si falla, seguimos sin trim previo (degradacion).
        self._vad.load()

        self._loaded = True
        self.last_error = None
        logger.info(
            "StreamingSTT loaded (model=%s, device=cpu, int8, threads=%d, vad=%s)",
            self._model_size, cpu_threads, self._vad._loaded,
        )

        # Warmup: 1s de silencio para inicializar kernels JIT/oneDNN.
        self._warmup()

        # App inventory para el INITIAL_PROMPT dinamico (sec. 2.2 informe).
        # Si ya hay cache se carga inmediato; si no, bloqueo acotado a 3s
        # (primer arranque). El refresh asincrono mantiene el cache fresco.
        try:
            from gemma4_agent.voice.app_inventory import ensure_prompt_available
            prompt = ensure_prompt_available(sync_timeout_s=3.0)
            if prompt is None:
                logger.info("StreamingSTT: no dynamic prompt, using fallback")
            else:
                logger.info(
                    "StreamingSTT: dynamic prompt ready (%d chars)", len(prompt),
                )
        except Exception as exc:
            logger.warning("StreamingSTT: app_inventory unavailable: %s", exc)

        return True

    def _warmup(self) -> None:
        """Primera transcripcion es 2-3x mas lenta. Forzar paths habituales."""
        if self._warmed_up or self._whisper is None:
            return
        try:
            dummy = np.zeros(SAMPLE_RATE, dtype=np.float32)
            t0 = time.monotonic()
            segments, _ = self._whisper.transcribe(
                dummy,
                language="es",
                beam_size=1,
                temperature=0.0,
                without_timestamps=False,
                vad_filter=False,
                condition_on_previous_text=False,
            )
            # faster-whisper devuelve un generator; consumirlo fuerza la ejecucion.
            list(segments)
            elapsed = time.monotonic() - t0
            self._warmed_up = True
            logger.info("StreamingSTT warmup OK (%.2fs)", elapsed)
        except Exception as exc:
            logger.warning("StreamingSTT warmup failed (non-fatal): %s", exc)

    def is_loaded(self) -> bool:
        return self._loaded

    def model_size(self) -> str:
        return self._model_size

    def fallback_to_base(self) -> bool:
        """Recarga con model=base. Persiste para futuras sesiones.

        Si el fallback falla (ej: 'base' no esta bajado), restaura el
        modelo previo en lugar de dejar StreamingSTT roto. Asi una
        deteccion erronea de 'CPU lento' no rompe la sesion.
        """
        if self._model_size == "base":
            return False
        prior_size = self._model_size
        prior_whisper = self._whisper
        prior_warmed = self._warmed_up
        logger.warning("StreamingSTT falling back from %s to base (slow CPU)", self._model_size)
        self._model_size = "base"
        os.environ["GEMMA4_VOICE_STT_MODEL"] = "base"
        self._whisper = None
        self._loaded = False
        self._warmed_up = False
        if self.load():
            return True
        # Fallback fallo -> restaurar
        logger.warning("fallback to base failed, restoring %s", prior_size)
        self._model_size = prior_size
        os.environ["GEMMA4_VOICE_STT_MODEL"] = prior_size
        self._whisper = prior_whisper
        self._loaded = prior_whisper is not None
        self._warmed_up = prior_warmed
        return False

    def _quality_check(
        self,
        segments: list,
        text: str,
        audio_duration_s: float,
    ) -> tuple[bool, str]:
        """Heuristicas anti-alucinacion post-transcripcion (informe sec. 9.2).

        Devuelve (passed, reason). Sin reintentos con otra temperatura
        (informe sec. 9.3 opcion B): la UX correcta es "no te he entendido"
        en lugar de multiplicar latencia.
        """
        if not text or len(text) < 2:
            return False, "empty_or_too_short"

        n_words = len(text.split())
        # Word density vs duracion (informe sec. 9.2.4)
        if audio_duration_s < 0.7 and n_words > 4:
            return False, f"too_many_words_for_duration ({n_words} in {audio_duration_s:.2f}s)"
        if audio_duration_s < 1.5 and n_words > 8:
            return False, f"too_many_words_for_duration ({n_words} in {audio_duration_s:.2f}s)"

        for s in segments:
            avg_lp = getattr(s, "avg_logprob", None)
            if avg_lp is not None and avg_lp < -1.0:
                return False, f"low_logprob ({avg_lp:.2f})"
            nsp = getattr(s, "no_speech_prob", None)
            if nsp is not None and nsp > 0.6:
                return False, f"no_speech_prob ({nsp:.2f})"
            cr = getattr(s, "compression_ratio", None)
            if cr is not None and cr > 2.4:
                return False, f"compression_ratio ({cr:.2f})"

        # Bag of Hallucinations en espanol
        if looks_like_hallucination(text):
            return False, "BoH_match"

        # n-gram repetition patologica
        if _has_pathological_ngram_repetition(text):
            return False, "ngram_repetition"

        # Compression ratio a nivel de texto crudo (defensa adicional)
        try:
            data = text.encode("utf-8")
            if data:
                ratio = len(data) / max(1, len(zlib.compress(data)))
                if ratio > 2.4 and len(text) > 30:
                    return False, f"text_compression_ratio ({ratio:.2f})"
        except Exception:
            pass

        return True, "ok"

    def _run_whisper(
        self,
        audio_f32: np.ndarray,
        duration_s: float,
        prefix: str | None = None,
    ) -> tuple[list, str, bool, str, float]:
        """Una sola llamada a Whisper. Devuelve (segments, text, ok, reason, avg_lp).

        - segments: lista de Segment de faster-whisper.
        - text: texto crudo concatenado (sin postprocess).
        - ok / reason: resultado del quality_check.
        - avg_lp: media de avg_logprob a traves de los segmentos (NaN si no aplicable).
        """
        kwargs = dict(_get_transcribe_kwargs(duration_s))
        kwargs["initial_prompt"] = get_initial_prompt()
        if prefix is not None:
            kwargs["prefix"] = prefix
        if self._whisper is None:
            return [], "", False, "model_not_loaded", float("nan")
        try:
            segments_gen, _info = self._whisper.transcribe(audio_f32, **kwargs)
            segments = list(segments_gen)
        except Exception as exc:
            logger.warning("transcribe failed (prefix=%r): %s", prefix, exc)
            return [], "", False, "transcribe_exception", float("nan")
        text = " ".join(seg.text.strip() for seg in segments).strip()
        ok, reason = self._quality_check(segments, text, duration_s)
        # avg_logprob promedio para comparar runs
        avg_lps = [getattr(s, "avg_logprob", None) for s in segments]
        avg_lps = [x for x in avg_lps if x is not None]
        avg_lp = float(np.mean(avg_lps)) if avg_lps else float("nan")
        return segments, text, ok, reason, avg_lp

    def _transcribe_buffer(self, audio_int16: np.ndarray) -> tuple[str, str, str]:
        """Pipeline completo: preprocess -> VAD trim -> Whisper -> quality -> postprocess.

        Returns (text, reason, raw_text):
          - text: post-filter clean transcription, "" on rejection.
          - reason: 'ok' on pass, or specific rejection reason
            ('BoH_match', 'low_logprob', 'no_speech', 'too_short',
            'ngram_repetition', 'no_speech_prob', 'compression_ratio',
            'empty_or_too_short', 'too_many_words_for_duration',
            'empty_input', 'quality_check_rejected').
          - raw_text: what Whisper actually produced. Equal to `text`
            when reason='ok'. For rejected turns, this is the text
            the quality_check killed — used for offline diagnosis
            without re-running Whisper.

        Hotfix M.1.3 2026-05-18: changed return shape from `str` to
        `tuple[str, str]` so the controller can annotate the recorder
        with the specific reject reason instead of a generic
        placeholder.

        Hotfix M.2.3 2026-05-18: extended to 3-tuple to include
        raw_text. Lets the operator inspect Whisper's pre-filter
        output from the manifest alone, no Whisper re-run needed.

        En modo SHORT, si el resultado original parece un comando ("abre X",
        etc.) o si quality_check falla, re-intenta UNA vez con prefix=<verbo>
        para anclar al decoder (Plan B / skill-prefix biasing, informe 8.4).
        """
        if self._whisper is None or audio_int16.size == 0:
            return "", "empty_input", ""

        # 1. Preprocess (int16 -> float32, HPF 80 Hz, normalize ligero)
        audio = _preprocess(audio_int16)

        # 2. VAD trim. None => rechazo total, no llamar a Whisper.
        trimmed = self._vad.trim(audio)
        if trimmed is None:
            logger.warning(
                "voice_silent_reject reason=no_speech orig_duration_s=%.3f",
                audio.size / float(SAMPLE_RATE),
            )
            return "", "no_speech", ""
        if trimmed.size < int(0.3 * SAMPLE_RATE):
            logger.warning(
                "voice_silent_reject reason=too_short "
                "trimmed_duration_s=%.3f orig_duration_s=%.3f",
                trimmed.size / float(SAMPLE_RATE),
                audio.size / float(SAMPLE_RATE),
            )
            return "", "too_short", ""

        duration_s = trimmed.size / float(SAMPLE_RATE)
        is_short = duration_s < SHORT_AUDIO_THRESHOLD_S

        # 3. Whisper, primera pasada
        segs, text, ok, reason, avg_lp = self._run_whisper(trimmed, duration_s)
        logger.debug(
            "transcribe pass1: dur=%.2fs mode=%s ok=%s reason=%s text=%r avg_lp=%.2f",
            duration_s, "short" if is_short else "long", ok, reason, text[:80], avg_lp,
        )

        # 4. Plan B: solo en modo SHORT. Disparar si:
        #    (a) ok=False (quality_check rechazo) y hay verbo detectable, o
        #    (b) ok=True PERO confidence marginal (avg_lp en [-1.0, -0.5]) y
        #        hay verbo detectado y texto <8 palabras.
        # Caso (b) refinado vs version anterior: antes disparabamos Plan B
        # siempre que el texto pareciera un comando con verbo, anadiendo
        # ~1500ms incluso cuando la transcripcion ya era buena. Ahora solo
        # repetimos si la confidence sugiere que merece la pena. Calibracion
        # empirica: "Abrastim" pass-1 da avg_lp ~-0.47, asi que el umbral
        # debe estar arriba para rescatar ese caso. Buenas transcripciones
        # tipicas dan avg_lp > -0.3.
        PLAN_B_LOW_CONF_THRESHOLD = -0.4
        verb: str | None = None
        retry_reason: str | None = None
        if is_short:
            if not ok:
                # Intentar inferir verbo del texto fallido (puede no haberlo).
                verb = _detect_command_verb(text)
                if verb is not None:
                    retry_reason = f"quality_failed:{reason}"
            else:
                # Pass-1 OK: solo Plan B si la confidence es marginal.
                if (np.isfinite(avg_lp) and avg_lp < PLAN_B_LOW_CONF_THRESHOLD
                        and len(text.split()) < 8):
                    v = _detect_command_verb(text)
                    if v is not None:
                        verb = v
                        retry_reason = f"low_confidence:{avg_lp:.2f}"

        if verb is not None:
            logger.info(
                "Plan B retry with prefix=%r (reason=%s, original=%r avg_lp=%.2f)",
                verb, retry_reason, text[:60], avg_lp,
            )
            segs2, text2, ok2, reason2, avg_lp2 = self._run_whisper(
                trimmed, duration_s, prefix=f"{verb} ",
            )
            logger.info(
                "Plan B pass2: ok=%s reason=%s text=%r avg_lp=%.2f",
                ok2, reason2, text2[:80], avg_lp2,
            )
            # Aceptar el reintento si:
            #  - pasaba quality y mejora avg_logprob, o
            #  - el original no pasaba y el reintento si pasa.
            accept_retry = False
            if ok2 and not ok:
                accept_retry = True
            elif ok2 and ok:
                # Comparar confidence (cuidado con NaN).
                if (np.isfinite(avg_lp2) and np.isfinite(avg_lp)
                        and avg_lp2 > avg_lp):
                    accept_retry = True
            if accept_retry:
                segs, text, ok, reason = segs2, text2, ok2, reason2
                logger.info("Plan B accepted retry")
            else:
                logger.info("Plan B retry not better, keeping original")

        if not ok:
            logger.info("quality_check rejected (%s): text=%r", reason, text[:80])
            # Hotfix M.1.3 2026-05-18: propagate the specific
            # quality_check reason so the recorder manifest can
            # show 'BoH_match' / 'low_logprob' / etc instead of
            # the generic placeholder.
            # Hotfix M.2.3 2026-05-18: also expose `text` as
            # raw_text so the operator can see what Whisper
            # actually produced before the filter killed it.
            return "", reason or "quality_check_rejected", text

        clean = _postprocess_text(text)
        return clean, "ok", clean

    def transcribe_stream(
        self,
        audio_iter: AudioIter,
        prefix_audio: np.ndarray | None = None,
    ) -> Iterator[STTEvent]:
        """Consume chunks de audio y emite Partial/Final/Timeout.

        prefix_audio: snapshot POST-wake (patron A estilo Alexa) que el
        controller calcula a partir de los timestamps de Vosk. Si viene,
        se siembra el buffer y se salta la gracia pre-speech.
        """
        if not self._loaded:
            logger.warning("transcribe_stream called but STT not loaded (last_error=%s)", self.last_error)
            yield STTEvent(kind="error", error=self.last_error or "stt not loaded")
            return

        PRE_SPEECH_GRACE_S = 0.0 if (prefix_audio is not None and prefix_audio.size > 0) else 0.2
        SPEECH_RMS_THRESHOLD = 200  # voz clara segun test de mic (rms ~3500)
        SPEECH_MIN_CHUNKS = 2  # 60ms de voz sostenida para confirmar

        # Sembrar buffer con el snapshot si lo hay
        if prefix_audio is not None and prefix_audio.size > 0:
            buffer = prefix_audio.astype(np.int16, copy=False).copy()
            logger.info(
                "transcribe_stream: seeded with %d samples (%.2fs) of snapshot",
                buffer.size, buffer.size / SAMPLE_RATE,
            )
            try:
                prefix_rms = float(np.sqrt(np.mean(buffer.astype(np.float32) ** 2)))
            except Exception:
                prefix_rms = 0.0
            if prefix_rms > SPEECH_RMS_THRESHOLD:
                first_speech_t: float | None = time.monotonic()
                last_speech_t: float | None = first_speech_t
                logger.info(
                    "transcribe_stream: snapshot has speech (rms=%.0f), first_speech_t set",
                    prefix_rms,
                )
                partial_emitted = True
                yield STTEvent(kind="partial", text="...")
            else:
                first_speech_t = None
                last_speech_t = None
                partial_emitted = False
        else:
            buffer = np.zeros(0, dtype=np.int16)
            first_speech_t = None
            last_speech_t = None
            partial_emitted = False

        start_t = time.monotonic()
        speech_streak = 0
        chunks_consumed = 0
        chunks_in_grace = 0
        logger.info(
            "transcribe_stream: entering main loop (grace=%.2fs, endpoint=%dms, rms_thresh=%d, prefix=%d samples)",
            PRE_SPEECH_GRACE_S, VAD_SILENCE_MS, SPEECH_RMS_THRESHOLD,
            buffer.size,
        )

        for chunk in audio_iter:
            chunks_consumed += 1
            now = time.monotonic()
            elapsed_total = now - start_t

            if chunks_consumed == 1:
                logger.info("transcribe_stream: first chunk arrived, size=%d", chunk.size)
            elif chunks_consumed % 100 == 0:
                logger.info(
                    "transcribe_stream: %d chunks, %.2fs elapsed, speech_seen=%s, buffer=%.2fs",
                    chunks_consumed, elapsed_total,
                    first_speech_t is not None, buffer.size / SAMPLE_RATE,
                )

            # Absolute timeout
            if elapsed_total > ABSOLUTE_TIMEOUT_S:
                logger.info("transcribe_stream: absolute timeout 15s")
                if first_speech_t is not None:
                    text, reason, raw = self._transcribe_buffer(buffer)
                    yield STTEvent(
                        kind="final", text=text,
                        reject_reason=reason, raw_text=raw,
                    )
                else:
                    yield STTEvent(kind="timeout")
                return

            # Pre-speech grace
            if elapsed_total < PRE_SPEECH_GRACE_S:
                chunks_in_grace += 1
                continue

            if chunks_in_grace > 0:
                logger.info(
                    "transcribe_stream: pre-speech grace ended (%d chunks discarded)",
                    chunks_in_grace,
                )
                chunks_in_grace = 0

            buffer = np.concatenate([buffer, chunk])

            try:
                chunk_rms = float(np.sqrt(np.mean(chunk.astype(np.float32) ** 2)))
            except Exception:
                chunk_rms = 0.0

            # Sprint P.2 2026-05-18: prefer Silero VAD's per-chunk speech
            # probability over the bare RMS threshold. Silero is robust
            # against sustained noise (fan/AC/music) where RMS gives a
            # false-positive, and catches murmured tails where RMS gives
            # a false-silence. Fallback to pure RMS if Silero unavailable.
            # Safety-net: very clear RMS speech (5x threshold) is accepted
            # regardless of Silero's opinion.
            silero_prob = self._vad.predict_chunk(chunk)
            speech_detected = (
                silero_prob >= 0.5
                or chunk_rms > SPEECH_RMS_THRESHOLD * 5
                or (silero_prob == 0.0 and not self._vad._loaded
                    and chunk_rms > SPEECH_RMS_THRESHOLD)
            )
            if speech_detected:
                speech_streak += 1
                if speech_streak >= SPEECH_MIN_CHUNKS:
                    if first_speech_t is None:
                        first_speech_t = now
                        logger.info(
                            "transcribe_stream: SPEECH confirmed (rms=%.0f, silero=%.2f, streak=%d)",
                            chunk_rms, silero_prob, speech_streak,
                        )
                    last_speech_t = now
                    if not partial_emitted:
                        partial_emitted = True
                        yield STTEvent(kind="partial", text="...")
            else:
                speech_streak = 0

            # Endpoint
            if first_speech_t is not None and last_speech_t is not None:
                silence_ms = (now - last_speech_t) * 1000
                if silence_ms >= VAD_SILENCE_MS:
                    logger.info(
                        "transcribe_stream: endpoint (silence=%dms, buffer=%.2fs)",
                        silence_ms, buffer.size / SAMPLE_RATE,
                    )
                    t0 = time.monotonic()
                    text, reason, raw = self._transcribe_buffer(buffer)
                    elapsed = time.monotonic() - t0
                    logger.info(
                        "transcribe_stream: final transcribe %.2fs for %.2fs audio (RTF %.2f), text=%r reason=%s",
                        elapsed, buffer.size / SAMPLE_RATE,
                        elapsed / max(0.01, buffer.size / SAMPLE_RATE),
                        text[:80], reason,
                    )
                    yield STTEvent(
                        kind="final", text=text,
                        reject_reason=reason, raw_text=raw,
                    )
                    return

        # Iterator cerrado sin endpoint
        if first_speech_t is not None:
            text, reason, raw = self._transcribe_buffer(buffer)
            yield STTEvent(
                kind="final", text=text,
                reject_reason=reason, raw_text=raw,
            )
        else:
            yield STTEvent(kind="timeout")

    def unload(self) -> None:
        """Libera modelos de RAM (al pasar a LIGHT/STANDBY).

        Idempotente: llamar dos veces o intercalar load()/unload() es seguro.
        Tambien resetea el VAD para que un reload posterior lo recargue.
        """
        self._whisper = None
        self._loaded = False
        self._warmed_up = False
        self._vad.unload()
