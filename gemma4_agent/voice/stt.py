"""STT via faster-whisper (CTranslate2, CPU, int8).

Clean STT after the v1 prompt-biasing approach proved too brittle
for anglicisms. The new design
shifts most of the correction burden OUT of the model and into a
deterministic RapidFuzz post-corrector (see corrector.py).

Whisper config (per the research report):
  - model: small (244 M params, ~480 MB disk, ~900 MB inference RAM)
  - compute_type: int8 on CPU (~600-900 ms for 2 s clips on a 4-core x86)
  - language: "es" by default (operator's matrix language)
    Why fixed and not None: short clips (1-3 s) can't be reliably
    autodetected; pinning ES preserves the matrix language and lets
    embedded English nouns flow through via tokenizer subwords.
  - beam_size: 1 (greedy) for command-mode latency
  - temperature: 0.0 for determinism
  - condition_on_previous_text: False (commands are independent)
  - initial_prompt: dynamic, built from domain inventory by inventory.py

This module just transcribes. Correction of anglicism mistranscriptions
('Aurekrom' -> 'Chrome', 'Benson Mould' -> 'Benson Boone') is done
DOWNSTREAM by corrector.py.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
DEFAULT_MODEL_SIZE = "small"
WHISPER_MODEL_DIR = Path.home() / ".gemma4" / "models" / "whisper"

# Decoding kwargs (per research report recommendation).
# `language` se fija DINAMICAMENTE por turno desde el perfil de idioma
# (lang_profiles.py). Para code-switching (español con apps en inglés) FIJAR el
# idioma-matriz es lo correcto — autodetect flipea de idioma a mitad de frase y
# no vuelve (openai/whisper #2009). El default 'es' queda como fallback.
DECODE_KWARGS = dict(
    language="es",
    task="transcribe",
    beam_size=1,
    best_of=1,
    temperature=0.0,
    condition_on_previous_text=False,
    vad_filter=False,           # we do VAD ourselves upstream
    # without_timestamps=False (STT Tier-1, 2026-05-22): forzar al decoder a
    # EMITIR timestamps reduce alucinaciones — es el cambio aislado de mayor
    # impacto según Sanchit Gandhi (mantenedor de Whisper en HF transformers):
    # "forcing the model to predict timestamps is contradictory to
    # hallucinations". Confirmado por whisper.cpp (suprimir <|notimestamps|>
    # elimina alucinaciones en no-speech) y linto-ai/whisper-timestamped #105.
    # Costo <5% latencia con beam=1. No usamos los timestamps, solo que existan.
    without_timestamps=False,
)


class STT:
    """faster-whisper wrapper, CPU int8.

    Lifecycle:
        stt = STT()
        stt.load()           # downloads model on first call (~480 MB)
        text = stt.transcribe(audio_int16, initial_prompt=...)
    """

    def __init__(
        self,
        model_size: str = DEFAULT_MODEL_SIZE,
        device: str = "cpu",
        compute_type: str = "int8",
        cpu_threads: int = 4,
    ) -> None:
        self._model_size = model_size
        self._device = device
        self._compute_type = compute_type
        self._cpu_threads = cpu_threads
        self._model: Any = None
        self._loaded: bool = False
        self.last_error: str | None = None

    def load(self) -> bool:
        if self._loaded:
            return True
        try:
            from faster_whisper import WhisperModel
        except Exception as exc:
            self.last_error = f"faster-whisper unavailable: {exc}"
            logger.error(self.last_error)
            return False
        try:
            WHISPER_MODEL_DIR.mkdir(parents=True, exist_ok=True)
            t0 = time.time()
            self._model = WhisperModel(
                self._model_size,
                device=self._device,
                compute_type=self._compute_type,
                cpu_threads=self._cpu_threads,
                download_root=str(WHISPER_MODEL_DIR),
            )
            elapsed = time.time() - t0
            self._loaded = True
            logger.info(
                "STT loaded: %s (%s/%s, %d threads, %.2fs)",
                self._model_size, self._device, self._compute_type,
                self._cpu_threads, elapsed,
            )
            return True
        except Exception as exc:
            self.last_error = f"STT init failed: {type(exc).__name__}: {exc}"
            logger.error(self.last_error)
            self._loaded = False
            return False

    def transcribe(
        self,
        audio: np.ndarray,
        initial_prompt: str | None = None,
        language: str | None = None,
        hotwords: str | None = None,
    ) -> str:
        """Transcribe an int16 mono 16 kHz audio buffer.

        `language`: código ISO del idioma-matriz a fijar (ver lang_profiles).
        `hotwords`: lista de nombres propios (apps/servicios) separados por
        espacio para sesgar el decoder hacia ellos. MEDIDO 2026-05-22 sobre eval
        real+sintético: rescata casos que el prompt no ("te liera"->Telegram) y
        NO daña habla real (WER real igual con/sin). Se combina con initial_prompt.

        Returns the raw text (post-corrector should be applied by the
        pipeline orchestrator, NOT here, to keep this module pure).
        """
        if not self._loaded or self._model is None:
            return ""
        # Defense-in-depth: never hand Whisper an empty/degenerate buffer. The
        # pipeline's silence gate already filters silent captures, but a direct
        # caller (tests, future paths) must not be able to make the model
        # transcribe nothing (undefined behaviour / wasted decode). 80ms floor.
        if audio is None or audio.size < int(0.08 * SAMPLE_RATE):
            return ""
        if audio.dtype != np.int16:
            audio = audio.astype(np.int16, copy=False)
        # faster-whisper accepts float32 in [-1, 1] or wraps it itself
        # for ndarray int16; we normalize explicitly for clarity.
        audio_f32 = audio.astype(np.float32) / 32768.0
        kwargs = dict(DECODE_KWARGS)
        if language:
            kwargs["language"] = language
        if initial_prompt:
            kwargs["initial_prompt"] = initial_prompt
        if hotwords:
            kwargs["hotwords"] = hotwords
        try:
            segments, info = self._model.transcribe(audio_f32, **kwargs)
            text = " ".join(s.text.strip() for s in segments).strip()
            logger.debug(
                "stt_done dur=%.2fs lang=%s text=%r",
                audio.size / SAMPLE_RATE,
                getattr(info, "language", "?"),
                text[:80],
            )
            return text
        except Exception as exc:
            logger.warning("stt transcribe failed: %s", exc)
            return ""
