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
VAD_SILENCE_MS = 800        # endpoint RMS (post-debug: 400 cortaba muy rapido)
ABSOLUTE_TIMEOUT_S = 15.0   # techo de seguridad
SHORT_AUDIO_THRESHOLD_S = 3.0  # frontera modo comando vs dictado


# ---------------------------------------------------------------------------
# Prompting / biasing (informe sec. 2.2, 12.2.2)
# ---------------------------------------------------------------------------
# Repetir "Gemma" muchas veces sesga al decoder a esperar esa palabra
# (resuelve "Hey Kema!"). Las apps en grafia inglesa correcta sesgan
# contra "abre estimulo" -> "abre Steam". Texto en espanol natural con
# puntuacion (OpenAI Cookbook recomienda ese patron explicitamente).
INITIAL_PROMPT = (
    "Conversacion con el asistente Gemma. "
    "Hey Gemma, abre Steam. Gemma, abre Spotify y reproduce musica. "
    "Gemma, abre Discord, VS Code, Chrome, Firefox, YouTube, Netflix, "
    "Twitch, WhatsApp, Telegram, Visual Studio Code, Notepad, Explorer, OBS. "
    "Gemma, apaga la luz del salon. Gemma, enciende la luz de la cocina. "
    "Gemma, sube el volumen. Gemma, baja el volumen. Gemma, pausa la musica. "
    "Gemma, pon el temporizador a cinco minutos. Gemma, que hora es. "
    "Gemma, como esta el tiempo en Madrid. Gemma, busca en Google. "
    "Gemma, cierra la ventana. Gemma, minimiza la ventana. "
    "Comandos breves en espanol dirigidos al asistente Gemma."
)


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
    "[musica]",
    "[aplausos]",
    "musica",
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
    """Detecta repeticion patologica de n-gramas (informe sec. 9.2)."""
    words = text.lower().split()
    if len(words) < 6:
        return False
    for n in (2, 3):
        ngrams = [tuple(words[i:i + n]) for i in range(len(words) - n + 1)]
        if not ngrams:
            continue
        # Mas de 2 duplicados -> patologico
        if len(ngrams) - len(set(ngrams)) > 2:
            return True
    return False


# ---------------------------------------------------------------------------
# Preprocesado de audio (informe sec. 6.4)
# ---------------------------------------------------------------------------
# Lazy: construir el filtro al primer uso. scipy es opcional aunque ya esta
# en el entorno; si faltara, _preprocess degrada a solo conversion.
_HPF_SOS: Any = None


def _build_hpf() -> Any:
    """High-pass Butterworth orden 4 a 80 Hz. Elimina rumble/DC."""
    global _HPF_SOS
    if _HPF_SOS is not None:
        return _HPF_SOS
    try:
        from scipy.signal import butter
        _HPF_SOS = butter(4, 80, btype="highpass", fs=SAMPLE_RATE, output="sos")
    except Exception as exc:
        logger.info("scipy unavailable for high-pass (%s); skipping HPF", exc)
        _HPF_SOS = False
    return _HPF_SOS


def _preprocess(audio_int16: np.ndarray) -> np.ndarray:
    """int16 -> float32 [-1,1] con HPF 80 Hz + peak-normalize ligero."""
    audio = audio_int16.astype(np.float32) / 32768.0
    sos = _build_hpf()
    if sos is not False:
        try:
            from scipy.signal import sosfilt
            # sosfilt returns ndarray when zi is not provided, but the scipy
            # type stub declares the union shape — the cast keeps pyright
            # happy without changing runtime behaviour.
            filtered = np.asarray(sosfilt(sos, audio), dtype=np.float32)
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
    """Evento emitido por el iterator de transcripcion."""
    kind: Literal["partial", "final", "timeout", "error"]
    text: str = ""
    error: str = ""


# Tipo del iterator de audio: yields np.int16 arrays (cualquier longitud).
AudioIter = Iterator[np.ndarray]


# ---------------------------------------------------------------------------
# Configuracion modo dual (informe sec. 12.2.5)
# ---------------------------------------------------------------------------
# Base comun. NO se ponen aqui parametros que cambian entre corto/largo.
_BASE_KWARGS = dict(
    language="es",
    task="transcribe",
    patience=1.0,
    length_penalty=1.0,
    compression_ratio_threshold=2.4,
    log_prob_threshold=-1.0,
    no_speech_threshold=0.6,
    condition_on_previous_text=False,
    initial_prompt=INITIAL_PROMPT,
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


def _detect_command_verb(text: str) -> str | None:
    """Devuelve el verbo (lowercase) si el texto empieza por uno de los
    verbos de comando conocidos, tras strip de wake-word y puntuacion."""
    if not text:
        return None
    # Reaprovechar postprocess para limpiar wake-word residual + puntuacion.
    cleaned = _postprocess_text(text).lower().lstrip()
    if not cleaned:
        return None
    first = cleaned.split(None, 1)[0].rstrip(",.!?;:¡¿")
    return first if first in COMMAND_VERBS_ES else None


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

    def _transcribe_buffer(self, audio_int16: np.ndarray) -> str:
        """Pipeline completo: preprocess -> VAD trim -> Whisper -> quality -> postprocess.

        Devuelve "" si el quality_check rechaza o el VAD no detecta speech.
        En modo SHORT, si el resultado original parece un comando ("abre X",
        etc.) o si quality_check falla, re-intenta UNA vez con prefix=<verbo>
        para anclar al decoder (Plan B / skill-prefix biasing, informe 8.4).
        """
        if self._whisper is None or audio_int16.size == 0:
            return ""

        # 1. Preprocess (int16 -> float32, HPF 80 Hz, normalize ligero)
        audio = _preprocess(audio_int16)

        # 2. VAD trim. None => rechazo total, no llamar a Whisper.
        trimmed = self._vad.trim(audio)
        if trimmed is None:
            logger.info("VAD: no speech detected, rejecting transcription")
            return ""
        if trimmed.size < int(0.3 * SAMPLE_RATE):
            logger.info("VAD: speech too short (<0.3s), rejecting")
            return ""

        duration_s = trimmed.size / float(SAMPLE_RATE)
        is_short = duration_s < SHORT_AUDIO_THRESHOLD_S

        # 3. Whisper, primera pasada
        segs, text, ok, reason, avg_lp = self._run_whisper(trimmed, duration_s)
        logger.debug(
            "transcribe pass1: dur=%.2fs mode=%s ok=%s reason=%s text=%r avg_lp=%.2f",
            duration_s, "short" if is_short else "long", ok, reason, text[:80], avg_lp,
        )

        # 4. Plan B: solo en modo SHORT. Disparar si:
        #    (a) ok=False (quality_check rechazo), o
        #    (b) ok=True pero detectamos verbo de comando y texto <8 palabras
        #    (sugiere comando con anglicismo mal reconocido tipo "Abrastim").
        verb: str | None = None
        retry_reason: str | None = None
        if is_short:
            if not ok:
                # Intentar inferir verbo del texto fallido (puede no haberlo).
                verb = _detect_command_verb(text)
                if verb is not None:
                    retry_reason = f"quality_failed:{reason}"
            else:
                v = _detect_command_verb(text)
                if v is not None and len(text.split()) < 8:
                    verb = v
                    retry_reason = "short_command_anchor"

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
            return ""

        return _postprocess_text(text)

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
                    text = self._transcribe_buffer(buffer)
                    yield STTEvent(kind="final", text=text)
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

            if chunk_rms > SPEECH_RMS_THRESHOLD:
                speech_streak += 1
                if speech_streak >= SPEECH_MIN_CHUNKS:
                    if first_speech_t is None:
                        first_speech_t = now
                        logger.info(
                            "transcribe_stream: SPEECH confirmed (rms=%.0f, streak=%d)",
                            chunk_rms, speech_streak,
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
                    text = self._transcribe_buffer(buffer)
                    elapsed = time.monotonic() - t0
                    logger.info(
                        "transcribe_stream: final transcribe %.2fs for %.2fs audio (RTF %.2f), text=%r",
                        elapsed, buffer.size / SAMPLE_RATE,
                        elapsed / max(0.01, buffer.size / SAMPLE_RATE),
                        text[:80],
                    )
                    yield STTEvent(kind="final", text=text)
                    return

        # Iterator cerrado sin endpoint
        if first_speech_t is not None:
            text = self._transcribe_buffer(buffer)
            yield STTEvent(kind="final", text=text)
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
