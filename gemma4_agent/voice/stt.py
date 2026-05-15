"""Fase W — STT streaming con faster-whisper.

Diseno (post-auditoria docs oficiales + runtime):
- Audio entra como chunks de 32ms int16 16kHz (via audio_io.AudioCapture,
  512 samples alineado con Silero VAD v5).
- transcribe_stream acepta `prefix_audio` opcional (acoustic snapshot estilo
  Alexa: el controller corta el audio justo donde Vosk dice que termino
  "gemma" y nos lo pasa como semilla). Sin prefix: gracia pre-speech 200ms.
- Acumula audio en buffer y detecta endpoint con RMS: voz si chunk_rms > 200
  sostenido 2 chunks (~60ms); silencio si rms cae por VAD_SILENCE_MS (800ms).
- Una sola transcripcion al final con beam=5 + thresholds default + temp
  fallback + without_timestamps=True (recomendado para audio corto, evita
  alucinaciones tipo "Suscribete").

CPU only. language="es" fijo.
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Literal

import numpy as np

logger = logging.getLogger(__name__)


WHISPER_MODEL_DIR = Path.home() / ".gemma4" / "models" / "whisper"
DEFAULT_MODEL_SIZE = "small"
SAMPLE_RATE = 16000
VAD_SILENCE_MS = 800        # endpoint (post-debug: 400 cortaba muy rapido)
ABSOLUTE_TIMEOUT_S = 15.0   # techo de seguridad


@dataclass(frozen=True)
class STTEvent:
    """Evento emitido por el iterator de transcripcion."""
    kind: Literal["partial", "final", "timeout", "error"]
    text: str = ""
    error: str = ""


# Tipo del iterator de audio: yields np.int16 arrays (cualquier longitud).
AudioIter = Iterator[np.ndarray]


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

    def load(self) -> bool:
        """Carga faster-whisper. Lazy. Silero VAD ya no se usa (RMS gate)."""
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            self.last_error = f"faster-whisper not installed: {exc}"
            return False
        WHISPER_MODEL_DIR.mkdir(parents=True, exist_ok=True)
        try:
            # int8 en CPU es el sweet spot RTF ~0.2 segun INFORME
            self._whisper = WhisperModel(
                self._model_size,
                device="cpu",
                compute_type="int8",
                download_root=str(WHISPER_MODEL_DIR),
            )
        except Exception as exc:
            self.last_error = f"whisper init failed ({self._model_size}): {type(exc).__name__}: {exc}"
            logger.error(self.last_error)
            return False
        self._loaded = True
        self.last_error = None
        logger.info("StreamingSTT loaded (model=%s, device=cpu, int8)", self._model_size)
        return True

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
        logger.warning("StreamingSTT falling back from %s to base (slow CPU)", self._model_size)
        self._model_size = "base"
        os.environ["GEMMA4_VOICE_STT_MODEL"] = "base"
        self._whisper = None
        self._loaded = False
        if self.load():
            return True
        # Fallback fallo -> restaurar
        logger.warning("fallback to base failed, restoring %s", prior_size)
        self._model_size = prior_size
        os.environ["GEMMA4_VOICE_STT_MODEL"] = prior_size
        self._whisper = prior_whisper
        self._loaded = prior_whisper is not None
        return False

    def _transcribe_buffer(self, audio_int16: np.ndarray, beam: int = 5) -> str:
        """Llama a faster-whisper sobre un buffer crudo int16 -> texto.

        Post-auditoria docs oficiales (faster-whisper #621 + #349):
        - vad_filter=False: nuestro pipeline ya filtra con RMS+endpoint.
        - condition_on_previous_text=False: anti-loop ("Suscribete" repetido).
        - **THRESHOLDS A DEFAULT**: la version anterior usaba 0.45/-0.8 mas
          agresivos -> docs confirman que AMBOS thresholds aplicados a la
          vez sobre audio corto (1-3s) produce string vacio con audio bueno.
          Volvemos a 0.6/-1.0 (defaults).
        - temperature fallback (0.0, 0.2, 0.4): permite UN reintento si el
          primer pass falla compression_ratio/log_prob. Mejor que temp=0.0
          fijo (que alucina sin posibilidad de reintento).
        - without_timestamps=True: recomendado por docs para audio corto.
          El modelo no "rellena" para alcanzar timestamps -> menos alucinacion.
        - Padding 0.3s de silencio al final: ayuda a Whisper a cerrar
          segmento sin alucinar (discussion #349).
        """
        if self._whisper is None or audio_int16.size == 0:
            return ""
        audio = audio_int16.astype(np.float32) / 32768.0
        padding = np.zeros(int(SAMPLE_RATE * 0.3), dtype=np.float32)
        audio = np.concatenate([audio, padding])
        try:
            segments, info = self._whisper.transcribe(
                audio,
                language="es",
                beam_size=beam,
                condition_on_previous_text=False,
                vad_filter=False,
                temperature=(0.0, 0.2, 0.4),
                no_speech_threshold=0.6,
                log_prob_threshold=-1.0,
                compression_ratio_threshold=2.4,
                without_timestamps=True,
            )
            text = " ".join(seg.text.strip() for seg in segments).strip()
            logger.debug(
                "transcribe info: lang=%s lang_prob=%.2f duration=%.2fs text_len=%d",
                info.language, info.language_probability, info.duration, len(text),
            )
            return text
        except Exception as exc:
            logger.warning("transcribe failed: %s", exc)
            return ""

    def transcribe_stream(
        self,
        audio_iter: AudioIter,
        prefix_audio: np.ndarray | None = None,
    ) -> Iterator[STTEvent]:
        """Consume chunks de audio y emite Partial/Final/Timeout.

        Estrategia post-bug-G (snapshot estilo Alexa):
        - prefix_audio: si se pasa, el controller capturo audio POST-wake
          (acoustic snapshot tipo Alexa). Lo USAMOS directamente como semilla
          del buffer y saltamos la gracia pre-speech (porque ese audio ya
          es DESPUES del wake, no la cola del wake).
        - Si prefix_audio es None: comportamiento clasico con gracia 200ms.

        - Speech detectado por RMS > 200 sostenido al menos 2 chunks (60ms).
        - Endpoint: VAD_SILENCE_MS de silencio sostenido tras ver speech.
        - Una sola transcripcion al final con beam=5 + anti-hallucination.
        """
        if not self._loaded:
            logger.warning("transcribe_stream called but STT not loaded (last_error=%s)", self.last_error)
            yield STTEvent(kind="error", error=self.last_error or "stt not loaded")
            return

        # Si hay prefix de snapshot, no necesitamos gracia: ese audio ya es
        # POST-wake y queremos procesarlo. Si no hay prefix, conservamos 200ms
        # de gracia para amortiguar el beep que pueda filtrarse al mic.
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
            # Si el snapshot ya tiene speech audible, marcamos first_speech
            # asi el endpoint funciona despues de los chunks nuevos.
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
                    text = self._transcribe_buffer(buffer, beam=5)
                    yield STTEvent(kind="final", text=text)
                else:
                    yield STTEvent(kind="timeout")
                return

            # Pre-speech grace: descartar chunk, no agregar al buffer
            if elapsed_total < PRE_SPEECH_GRACE_S:
                chunks_in_grace += 1
                continue

            if chunks_in_grace > 0:
                logger.info(
                    "transcribe_stream: pre-speech grace ended (%d chunks discarded)",
                    chunks_in_grace,
                )
                chunks_in_grace = 0

            # Acumular en buffer real
            buffer = np.concatenate([buffer, chunk])

            # RMS del chunk actual
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
                    text = self._transcribe_buffer(buffer, beam=5)
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
            text = self._transcribe_buffer(buffer, beam=5)
            yield STTEvent(kind="final", text=text)
        else:
            yield STTEvent(kind="timeout")

    def unload(self) -> None:
        """Libera modelos de RAM (al pasar a LIGHT/STANDBY)."""
        self._whisper = None
        self._loaded = False
