"""STT via sherpa-onnx + Parakeet-TDT-0.6b-v3 (CPU, int8, greedy).

Motor candidato para reemplazar Whisper-small. Medido sobre VOZ REAL
(scripts/stt_real_voice_eval.py, 2026-05-23):
  - WER chileno (terceros)  : 0.044  vs Whisper 0.075  -> mejor base
  - WER comandos (RED, n=84): 0.335  vs Whisper 0.445  -> mejor base
  - latencia p50            : 71 ms  vs Whisper 1570 ms -> 20x más rápido
  - NO alucina en silencio   (debilidad crónica de Whisper-small)

Interfaz IDÉNTICA a stt.STT (load() + transcribe(audio_int16, ...)) para que
sea drop-in detrás de un flag. Igual que stt.STT: este módulo SOLO transcribe;
la corrección de fusiones de nombres propios ("Chrome"->"crumb", "GIMP"->"Kimp")
la hace DOWNSTREAM el corrector (corrector.py), no acá.

Optimizaciones Etapa 0 (plan_sherpa_parakeet_cpu_optimizacion.md §Axis 2):
  - num_threads = min(4, cores físicos): el speed-up se satura en 2-4 hilos
    físicos para encoders FastConformer en CPU (guía ORT). psutil si está.
  - feature_dim NO se fuerza: sherpa-onnx lo lee del modelo NeMo (128 mel-bins).
    VERIFICADO empíricamente 2026-05-23: pasar 80 vs 128 da WER IDÉNTICO
    (0.3708/0.0448) -> sherpa ignora el param para nemo_transducer. El "bug
    silencioso" que el plan temía NO existe en este path.
  - warm-up: primera inferencia ~85-115 ms en frío; warm-up con 0.5 s de
    silencio al cargar para que las p50 reales no la paguen.
  - thread spinning: sherpa-onnx no expone allow_spinning en from_transducer;
    se mitiga con OMP_NUM_THREADS y el techo de hilos (idle CPU bajo).

Restricciones (CLAUDE.md): CPU only (GPU es del LLM), OSS gratis, multi-usuario
(NO overfit a una voz), open-vocab. El modelo es CC-BY-4.0.
"""
from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000

# Resolución del bundle del modelo. PROD vive en ~/.gemma4/models (junto a
# whisper/piper/vosk); el bundle de eval del repo es el fallback para dev/A-B.
# Se elige el primero que exista -> prod no depende del checkout del repo.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_BUNDLE_NAME = "sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8"
PROD_MODEL_DIR = Path.home() / ".gemma4" / "models" / _BUNDLE_NAME
_EVAL_MODEL_DIR = _REPO_ROOT / "data" / "stt_eval" / "sherpa" / _BUNDLE_NAME


def _resolve_model_dir() -> Path:
    """Prod home primero, luego bundle de eval del repo."""
    if (PROD_MODEL_DIR / "encoder.int8.onnx").exists():
        return PROD_MODEL_DIR
    return _EVAL_MODEL_DIR


DEFAULT_MODEL_DIR = _resolve_model_dir()


def _blank_penalty() -> float:
    """Penalización positiva al token blank en greedy (resta del logit del blank).
    Combate el modo de fallo TDT de Parakeet: se SALTA sílabas/tokens y se come
    nombres cortos ("Zoom"->"su", "Outlook"->"o"). La research lo marca verificado
    y gratis (0 latencia/RAM); rango 0.5-1.0, >2.5 inserta. Env-tunable; 0 lo apaga.
    Fuente: parakeet_beam_nombres_propios_decoding.md (Issue #2605)."""
    try:
        v = float(os.environ.get("GEMMA4_PARAKEET_BLANK_PENALTY", "0.8"))
    except (TypeError, ValueError):
        v = 0.8
    return max(0.0, min(2.5, v))


def _optimal_threads() -> int:
    """min(4, cores físicos). El speed-up de FastConformer en CPU se satura
    entre 2-4 hilos físicos; los lógicos (hyperthread) degradan por contención
    de unidades vectoriales (guía ORT + medición del usuario: nt=4 óptimo)."""
    physical = None
    try:
        import psutil
        physical = psutil.cpu_count(logical=False)
    except Exception:
        pass
    if not physical:
        physical = os.cpu_count() or 2
    return max(1, min(4, physical))


class ParakeetSTT:
    """sherpa-onnx + Parakeet-TDT-0.6b-v3 int8, CPU. Drop-in de stt.STT.

    Lifecycle:
        stt = ParakeetSTT()
        stt.load()
        text = stt.transcribe(audio_int16)
    """

    def __init__(
        self,
        model_dir: Path | str = DEFAULT_MODEL_DIR,
        num_threads: int | None = None,
    ) -> None:
        self._model_dir = Path(model_dir)
        self._num_threads = num_threads or _optimal_threads()
        self._rec: Any = None
        self._loaded: bool = False
        self.last_error: str | None = None

    def load(self) -> bool:
        if self._loaded:
            return True
        try:
            import sherpa_onnx
        except Exception as exc:
            self.last_error = f"sherpa-onnx unavailable: {exc}"
            logger.error(self.last_error)
            return False
        md = self._model_dir
        missing = [f for f in ("encoder.int8.onnx", "decoder.int8.onnx",
                               "joiner.int8.onnx", "tokens.txt")
                   if not (md / f).exists()]
        if missing:
            self.last_error = f"Parakeet model files missing in {md}: {missing}"
            logger.error(self.last_error)
            return False
        # Hilos consistentes para ORT/OpenMP (idle CPU bajo entre comandos).
        os.environ.setdefault("OMP_NUM_THREADS", str(self._num_threads))
        try:
            t0 = time.time()
            self._rec = sherpa_onnx.OfflineRecognizer.from_transducer(
                encoder=str(md / "encoder.int8.onnx"),
                decoder=str(md / "decoder.int8.onnx"),
                joiner=str(md / "joiner.int8.onnx"),
                tokens=str(md / "tokens.txt"),
                num_threads=self._num_threads,
                model_type="nemo_transducer",
                decoding_method="greedy_search",
                blank_penalty=_blank_penalty(),
            )
            elapsed = time.time() - t0
            self._loaded = True
            self._warmup()
            logger.info(
                "ParakeetSTT loaded: %s (%d threads, %.2fs)",
                md.name, self._num_threads, elapsed,
            )
            return True
        except Exception as exc:
            self.last_error = f"ParakeetSTT init failed: {type(exc).__name__}: {exc}"
            logger.error(self.last_error)
            self._loaded = False
            return False

    def _warmup(self) -> None:
        """Primera inferencia en frío cuesta ~85-115 ms; la pagamos al cargar
        con 0.5 s de silencio para que la p50 real del usuario no la incluya."""
        try:
            silence = np.zeros(int(0.5 * SAMPLE_RATE), dtype=np.float32)
            s = self._rec.create_stream()
            s.accept_waveform(SAMPLE_RATE, silence)
            self._rec.decode_stream(s)
        except Exception:
            pass

    def transcribe(
        self,
        audio: np.ndarray,
        initial_prompt: str | None = None,   # ignorado (compat con STT)
        language: str | None = None,         # ignorado (Parakeet es multilingüe)
        hotwords: str | None = None,         # ignorado en greedy (ver Etapa 2)
    ) -> str:
        """Transcribe un buffer int16 mono 16 kHz. Devuelve texto crudo.

        Acepta los kwargs de stt.STT por compatibilidad de interfaz, pero
        Parakeet greedy no los usa (es multilingüe sin prompt, y hotwords
        requiere modified_beam_search — ver Etapa 2 del plan). El corrector se
        aplica DOWNSTREAM, igual que con Whisper."""
        if not self._loaded or self._rec is None:
            return ""
        if audio is None or audio.size < int(0.08 * SAMPLE_RATE):
            return ""
        if audio.dtype == np.int16:
            audio_f32 = audio.astype(np.float32) / 32768.0
        else:
            audio_f32 = audio.astype(np.float32)
            if np.max(np.abs(audio_f32)) > 1.5:
                audio_f32 = audio_f32 / 32768.0
        try:
            s = self._rec.create_stream()
            s.accept_waveform(SAMPLE_RATE, audio_f32)
            self._rec.decode_stream(s)
            text = s.result.text.strip()
            logger.debug("parakeet_done dur=%.2fs text=%r",
                         audio.size / SAMPLE_RATE, text[:80])
            return text
        except Exception as exc:
            logger.warning("parakeet transcribe failed: %s", exc)
            return ""
