"""Wake-word detection — LiveKit (preferred) with openWakeWord fallback.

LiveKit WakeWord is the preferred backend: the custom openWakeWord model
measured recall = 0.110 on the universal held-out (25 voices / 13
languages), while LiveKit's conv-attention head reports 60x lower AUT and
17% better recall vs OWW in their bench.

Backend selection (in order):
  (1) LiveKit: `gemma4_agent/voice/models/livekit/hey_gemma.onnx`
      Trained with LiveKit's pipeline on Piper LibriTTS (904 EN speakers
      × SLERP) + ACAV100M negatives + MIT RIRs. Stateless predict()
      taking ~2 s windows.
  (2) openWakeWord custom: `gemma4_agent/voice/models/oww/hey_gemma.onnx`
      Custom-trained model — kept as fallback (recall 0.110, see above).
  (3) openWakeWord stock "hey_jarvis": pretrained from upstream OWW
      catalog. Last-resort if neither custom model loads.

API contract (matches AudioCapture.on_chunk):
  - feed(chunk: np.ndarray): int16, mono, 16 kHz; ANY size accepted.
    Internal ring-buffer keeps the last LIVEKIT_WINDOW_SAMPLES for the
    LiveKit predictor; OWW uses its own 80 ms accumulator.
  - on_wake callback: (phrase: str, score: float).

Design:
  - NO debounce inside the detector. End-of-command handled by VAD.
  - SAME_PHRASE_COOLDOWN_S prevents repeated fires within a single
    utterance (~100 ms).
  - LiveKit prediction stride = 1 chunk (~32 ms). Each new chunk
    triggers one predict() over the trailing 2 s window.
"""
from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any, Callable

import numpy as np

logger = logging.getLogger(__name__)

# ----- shared timing -------------------------------------------------

# Min gap between two fires of the SAME wake; prevents same utterance
# triggering multiple times across consecutive frames.
SAME_PHRASE_COOLDOWN_S = 0.10

# ----- LiveKit backend -----------------------------------------------

# LiveKit predict() needs ~2 s audio to produce non-zero scores
# (16 mel embeddings; window 76 mel frames @ 10 ms hop, stride 8).
LIVEKIT_WINDOW_SECONDS = 2.0
LIVEKIT_SAMPLE_RATE = 16000
LIVEKIT_WINDOW_SAMPLES = int(LIVEKIT_WINDOW_SECONDS * LIVEKIT_SAMPLE_RATE)

# Predict throttle: the audio pump delivers 32 ms chunks (~31/s), and running
# the conv-attention ONNX model on the full 2 s window EVERY chunk is ~31
# inferences/second of continuous CPU while idle-listening — the dominant idle
# cost of the wake stage (ONNX-without-throttle clamps the CPU to 100% and can
# freeze Windows). A 2 s wake phrase does NOT need 31 Hz sampling: scoring the rolling
# window every Nth chunk still samples the phrase ~16 times. Decimate to ~8 Hz
# (every 4th chunk) -> ~75% less wake CPU, no measurable recall loss (the window
# is unchanged; we just score it less often). Env-tunable for tuning/measurement.
LIVEKIT_PREDICT_EVERY_N_CHUNKS = max(1, int(
    os.environ.get("GEMMA4_WAKE_PREDICT_EVERY_N", "4")))

# Fire threshold for LiveKit conv-attention output.
#
# RE-CALIBRADO 2026-06-17 (0.25 -> 0.50) tras reproducir falsos positivos graves
# en uso real. La calibración vieja (tabla abajo) sólo midió fp/hr sobre
# LibriSpeech con ventana deslizante — NUNCA midió "¿el habla normal del usuario
# dispara el wake?". Medido ahora (scripts/_diag/_wake_false_fire_test.py, voz
# real NO-Baxy del usuario + lazo acústico por altavoces):
#   thr 0.25: 64% del habla real NO-Baxy DISPARA el wake; recall Baxy 0.872
#   thr 0.35: 45% falsos
#   thr 0.45: 30% falsos
#   thr 0.50: ~20% falsos; recall Baxy 0.872 (es/en 1.00) — SIN pérdida de recall
#             (el "Baxy" limpio puntúa muy por encima de 0.5; los falsos del habla
#              de fondo se agrupan en 0.35-0.45, así que 0.5 los corta casi gratis)
#   thr 0.55: 15% falsos; recall ~0.86
#
# RE-CALIBRADO 2026-06-17 #2 (0.50 -> 0.65) con monitoreo EN VIVO (mic real, el
# usuario hablando + videos sin decir Baxy). A 0.50 los falsos seguían en
# ~1-2/min (scores observados 0.50-0.71). El análisis de TRAYECTORIA
# (scripts/_diag/_wake_trajectory_test.py) mostró que el modelo SÍ separa:
#   - Baxy real: peak p50=0.91 (banda 0.85-0.97)
#   - falsos (habla/video del usuario): peak ≤0.72
# El umbral 0.50 caía DENTRO de la banda de falsos. Tradeoff medido
# (_wake_false_fire_test, voz real del usuario):
#   thr 0.65: 6% falsos (bloquea ~80% de los falsos vivos ≤0.71); recall 0.833
#   thr 0.70: 6% falsos; recall 0.800
#   thr 0.75: bloquea todos los vivos; recall 0.717 (cae demasiado)
# 0.65 es el punto: ~80% menos falsos con recall 0.83. Descartados como palancas
# (medidos): trigger_level (el pico del Baxy es angosto, run 2-4, no separa) y el
# verificador STT post-wake (mata recall: 46-60% de Baxy reales sobreviven). Un
# residuo de falsos puntúa tan alto como un Baxy real (solape inherente) -> esos
# solo los cura el reentreno (ver _RUNBOOK_REENTRENO_WAKE). Sube/baja con
# GEMMA4_LIVEKIT_THRESHOLD (0.60 = más sensible, 0.70 = menos falsos).
# RE-CALIBRADO 2026-06-18 (0.65 -> 0.30): MODELO BASE REENTRENADO (el reentreno
# que el comentario de arriba anticipaba como única cura del solape de falsos).
# El nuevo base (medium, neg_w=1, + 169 falsos REALES capturados como
# hard-negatives + voces reales del usuario; receta = recipe probado de
# hey_gemma) tiene una distribución de scores CORRIDA HACIA ABAJO: el "baxy"
# real puntúa ~0.30-0.95 y los falsos quedan muy por debajo. Medido por PICO
# sobre las grabaciones reales (scripts/_diag/_eval_wake_combined.py), base+
# verificador:
#   base_thr 0.25: recall real 0.940, falsos 0.000, confusables 0.037
#   base_thr 0.30: recall real 0.933, falsos 0.000, confusables 0.029  <- elegido
#   base_thr 0.35: recall real 0.893, falsos 0.000, confusables 0.029
# vs el base ANTERIOR (prod) @0.65: recall 0.858, falsos 0.012, confus ~0.21.
# El reentreno ELIMINA los falsos (los hard-negatives reales curaron el solape)
# Y SUBE el recall. El verificador los lleva a 0 exacto. OJO: este umbral SOLO
# vale para el base nuevo; el base viejo @0.30 dispara con TODO (su banda de
# falsos llega a 1.0). Sube/baja con GEMMA4_LIVEKIT_THRESHOLD (el verificador
# mantiene falsos=0 en toda la banda 0.25-0.35, hay margen para subir recall).
# 2026-06-18 it.6 (0.30 -> 0.35): reentreno con silencio + falsos reales
# capturados como hard-negatives. Bajó el piso del modelo sobre silencio (clips
# que flotaban 0.5-0.81 ahora caen 0.14-0.28) y los "Yeah" fuertes a ~0.32. A
# 0.35 esos "Yeah" se rechazan y el recall real se mantiene en 0.94 (medido,
# _eval_wake_combined). El piso de energía (pipeline.py) cubre el ambiente bajo.
LIVEKIT_THRESHOLD = float(os.environ.get("GEMMA4_LIVEKIT_THRESHOLD", "0.35"))

# Stem del modelo LiveKit, configurable por env. Wake word = "Baxy" (el nombre del
# asistente). El modelo baxy.onnx PASÓ el gate: recall held-out 0.872 global, 1.00 en
# es/en/it/fr (medido 2026-06-04). Reemplazó a hey_gemma porque "Baxy" (sin /r/, vocal
# final) generaliza cross-idioma, mientras que "carter" (con /r/ rótica) colapsaba en
# idiomas no-ingleses (0.28). Override con GEMMA4_LIVEKIT_MODEL_STEM si hace falta.
LIVEKIT_MODEL_STEM = os.environ.get("GEMMA4_LIVEKIT_MODEL_STEM", "baxy")
LIVEKIT_MODEL_PATH = (
    Path(__file__).resolve().parent / "models" / "livekit" / f"{LIVEKIT_MODEL_STEM}.onnx"
)

# FUSIÓN DUAL (2026-06-12): segunda cabeza clasificadora opcional sobre el
# MISMO frontend (mel+embedding compartidos → costo extra ~0). Diseño: el
# modelo limpio (recall 0.820 en silencio) + el robusto-a-ruido (entrenado
# con MUSAN) corren en paralelo; dispara el OR con umbrales INDEPENDIENTES.
# El umbral de la cabeza de ruido se calibra con scripts/wake_dual_or_eval.py
# (sweep de pares vs recall/confusables/fp-hr). Apagado por defecto hasta
# fijar el par medido: GEMMA4_LIVEKIT_NOISE_STEM=baxy_noise +
# GEMMA4_LIVEKIT_NOISE_THRESHOLD=<medido>.
LIVEKIT_NOISE_STEM = (os.environ.get("GEMMA4_LIVEKIT_NOISE_STEM", "") or "").strip()
LIVEKIT_NOISE_THRESHOLD = float(
    os.environ.get("GEMMA4_LIVEKIT_NOISE_THRESHOLD", "0.5"))

# Verificador post-disparo (openWakeWord custom_verifier): filtra los falsos del
# modelo base con un clasificador entrenado sobre los falsos REALES + Baxy
# real/sintético (models/livekit/baxy_verifier.json). Default ON; se apaga con
# GEMMA4_WAKE_VERIFIER=0. Si el archivo del verificador no existe, es no-op.
_VERIFIER_ENABLED = (os.environ.get("GEMMA4_WAKE_VERIFIER", "1") or "1").strip().lower() \
    not in {"0", "false", "no", "off"}

# ----- openWakeWord backend (fallback) -------------------------------

OWW_WINDOW_SAMPLES = 1280   # 80 ms @ 16 kHz
OWW_THRESHOLD = float(os.environ.get("GEMMA4_OWW_THRESHOLD", "0.3"))
OWW_PARTIAL_THRESHOLD = float(os.environ.get("GEMMA4_OWW_PARTIAL", "0.15"))

OWW_CUSTOM_MODEL_PATH = (
    Path(__file__).resolve().parent / "models" / "oww" / "hey_gemma.onnx"
)
OWW_STOCK_MODEL_NAME = "hey_jarvis"

# Back-compat aliases — callers (tests, pipeline) import these names.
CUSTOM_MODEL_PATH = OWW_CUSTOM_MODEL_PATH
STOCK_MODEL_NAME = OWW_STOCK_MODEL_NAME


WakeCallback = Callable[[str, float], None]


class WakeDetector:
    """Wake-word detector supporting LiveKit (preferred) + openWakeWord.

    Lifecycle:
        det = WakeDetector(on_wake=fn)
        ok = det.load()
        det.feed(chunk)
        det.reset()
    """

    def __init__(self, on_wake: WakeCallback) -> None:
        self._on_wake = on_wake
        self._loaded: bool = False
        self.last_error: str | None = None

        # Which backend is active. One of: "livekit", "oww_custom", "oww_stock".
        self._backend: str = ""

        # ---- LiveKit state ----
        self._livekit_model: Any = None
        self._livekit_score_key: str = "hey_gemma"
        # Ring buffer of last LIVEKIT_WINDOW_SAMPLES samples (int16).
        self._lk_ring: np.ndarray = np.zeros(0, dtype=np.int16)
        # Predict-throttle counter (see LIVEKIT_PREDICT_EVERY_N_CHUNKS).
        self._lk_chunk_count: int = 0

        # ---- OWW state ----
        self._oww_model: Any = None
        self._oww_score_key: str = ""
        self._oww_buf: np.ndarray = np.zeros(0, dtype=np.int16)

        # ---- cooldowns ----
        self._last_fire_at: float = 0.0
        self._last_partial_at: float = 0.0

        # Public flag (kept for back-compat with pipeline.py / tests).
        self.using_custom_model: bool = False

    # ----- lifecycle ---------------------------------------------------

    def load(self) -> bool:
        if self._loaded:
            return True

        # Try LiveKit first — via the pure-onnxruntime runtime (works on
        # Python 3.10; does NOT import the livekit-wakeword package which
        # requires 3.11). Needs melspectrogram.onnx + embedding_model.onnx
        # + hey_gemma.onnx side by side in models/livekit/.
        if LIVEKIT_MODEL_PATH.exists():
            try:
                from .livekit_runtime import LiveKitWakeRuntime
                rt = LiveKitWakeRuntime(
                    LIVEKIT_MODEL_PATH.parent, LIVEKIT_MODEL_PATH.stem,
                )
                if rt.load():
                    self._livekit_model = rt
                    self._livekit_score_key = LIVEKIT_MODEL_PATH.stem
                    # Cabeza dual opcional (ver LIVEKIT_NOISE_STEM arriba).
                    self._noise_head = ""
                    if LIVEKIT_NOISE_STEM and \
                            LIVEKIT_NOISE_STEM != LIVEKIT_MODEL_PATH.stem:
                        if rt.add_classifier(LIVEKIT_NOISE_STEM):
                            self._noise_head = LIVEKIT_NOISE_STEM
                            logger.info(
                                "WakeDetector dual: %s@%.2f OR %s@%.2f",
                                LIVEKIT_MODEL_PATH.stem, LIVEKIT_THRESHOLD,
                                LIVEKIT_NOISE_STEM, LIVEKIT_NOISE_THRESHOLD)
                    self._backend = "livekit"
                    self.using_custom_model = True
                    self._loaded = True
                    logger.info(
                        "WakeDetector ready (LiveKit pure-ORT %s)",
                        LIVEKIT_MODEL_PATH,
                    )
                    return True
                logger.warning(
                    "LiveKit runtime load failed (%s), falling back to OWW",
                    rt.last_error,
                )
            except Exception as exc:
                logger.warning(
                    "LiveKit runtime import/load failed (%s), falling back to OWW",
                    exc,
                )

        # Try OWW custom (custom-trained fallback model).
        try:
            from openwakeword import Model
            from openwakeword.utils import download_models
        except Exception as exc:
            self.last_error = f"openwakeword unavailable: {exc}"
            logger.error(self.last_error)
            return False

        try:
            if OWW_CUSTOM_MODEL_PATH.exists():
                self._oww_model = Model(
                    wakeword_models=[str(OWW_CUSTOM_MODEL_PATH)],
                    inference_framework="onnx",
                )
                self._oww_score_key = OWW_CUSTOM_MODEL_PATH.stem
                self._backend = "oww_custom"
                self.using_custom_model = True
                self._loaded = True
                logger.info("WakeDetector ready (OWW custom %s)", OWW_CUSTOM_MODEL_PATH)
                return True
        except Exception as exc:
            logger.warning("OWW custom load failed, falling back to stock: %s", exc)

        # Stock hey_jarvis.
        try:
            download_models()
            self._oww_model = Model(
                wakeword_models=[OWW_STOCK_MODEL_NAME],
                inference_framework="onnx",
            )
            self._oww_score_key = OWW_STOCK_MODEL_NAME
            self._backend = "oww_stock"
            self.using_custom_model = False
            self._loaded = True
            logger.warning(
                "WakeDetector ready (FALLBACK to OWW stock '%s')",
                OWW_STOCK_MODEL_NAME,
            )
            return True
        except Exception as exc:
            self.last_error = f"WakeDetector init failed: {type(exc).__name__}: {exc}"
            logger.error(self.last_error)
            self._loaded = False
            return False

    def reset(self) -> None:
        """Clear buffers and cooldowns."""
        self._lk_ring = np.zeros(0, dtype=np.int16)
        self._oww_buf = np.zeros(0, dtype=np.int16)
        self._lk_chunk_count = 0
        self._last_fire_at = 0.0
        self._last_partial_at = 0.0
        if self._oww_model is not None:
            try:
                self._oww_model.reset()
            except Exception:
                pass

    # ----- inference ---------------------------------------------------

    def feed(self, chunk: np.ndarray, predict: bool = True) -> None:
        """Append `chunk` (int16, mono, 16 kHz, any size) and (si predict) puntúa.

        predict=False mantiene el ring rodante de 2 s CALIENTE sin puntuar ni
        disparar. Lo usa el pipeline durante el TTS (anti-eco): si en vez de
        DEJAR DE alimentar el wake mientras Gemma habla, lo alimentamos sin
        disparar, el ring queda lleno al terminar el TTS y el siguiente "Baxy"
        se detecta de inmediato — sin el hueco muerto de ~2 s + duración-TTS que
        hacía "tras decir Baxy varias veces deja de funcionar" (medido 2026-06-17,
        scripts/_diag/_wake_repeated_test.py: 7/15 -> 15/15)."""
        if not self._loaded:
            return
        try:
            chunk_i16 = np.asarray(chunk, dtype=np.int16)
        except Exception as exc:
            logger.warning("WakeDetector.feed: coercion failed: %s", exc)
            return
        if chunk_i16.size == 0:
            return

        if self._backend == "livekit":
            self._feed_livekit(chunk_i16, predict=predict)
        else:
            self._feed_oww(chunk_i16, predict=predict)

    # ----- LiveKit path -----------------------------------------------

    def _feed_livekit(self, chunk: np.ndarray, predict: bool = True) -> None:
        # Maintain rolling 2-second buffer. IMPORTANT: append EVERY chunk so the
        # window is always current — only the predict() CALL is throttled below.
        self._lk_ring = np.concatenate([self._lk_ring, chunk])
        if self._lk_ring.size > LIVEKIT_WINDOW_SAMPLES:
            self._lk_ring = self._lk_ring[-LIVEKIT_WINDOW_SAMPLES:]
        # predict=False: ring caliente, sin puntuar ni disparar (anti-eco TTS).
        if not predict:
            return
        # Wait until we have enough audio for a meaningful score.
        if self._lk_ring.size < LIVEKIT_WINDOW_SAMPLES:
            return
        # Throttle: score the rolling window only every Nth chunk. At 32ms/chunk
        # this drops ~31 Hz -> ~8 Hz of ONNX inference (~75% less idle CPU) while
        # still sampling a 2s phrase ~16 times. The buffer above stays fresh, so
        # when we DO predict it's on the latest audio.
        self._lk_chunk_count += 1
        if self._lk_chunk_count % LIVEKIT_PREDICT_EVERY_N_CHUNKS != 0:
            return
        noise_head = getattr(self, "_noise_head", "")
        try:
            if noise_head:
                # FUSIÓN DUAL: una pasada de frontend, dos cabezas. Dispara
                # el OR: cada cabeza contra SU umbral. Normalizamos el score
                # al margen sobre su umbral para que _evaluate_score (que
                # compara contra LIVEKIT_THRESHOLD) decida con una sola vara.
                scores = self._livekit_model.predict_multi(self._lk_ring)
                s_main = scores.get(self._livekit_score_key, 0.0)
                s_noise = scores.get(noise_head, 0.0)
                ratio = max(
                    s_main / max(1e-6, LIVEKIT_THRESHOLD),
                    s_noise / max(1e-6, LIVEKIT_NOISE_THRESHOLD),
                )
                score = ratio * LIVEKIT_THRESHOLD
            else:
                # LiveKitWakeRuntime.predict() returns a float directly.
                score = float(self._livekit_model.predict(self._lk_ring))
        except Exception as exc:
            logger.warning("LiveKit predict failed: %s", exc)
            return
        # VERIFICADOR (openWakeWord custom_verifier, 2026-06-18): si el base
        # dispararía pero el verificador —regresión logística sobre el mismo
        # embedding, entrenada con los falsos REALES capturados + Baxy real (5
        # voces ES) + sintético ES, con features extraídas igual que el runtime
        # (ventana de pico)— dice "no es Baxy", se SUPRIME. MEDIDO end-to-end:
        # falsos de video reales 8.1%->1.2% (~85% menos) SIN tocar el recall de
        # las voces reales (0.858 con y sin). Es ES-céntrico (foco actual del
        # producto); rechaza voces no entrenadas/no-ES. Solo single-head;
        # gated GEMMA4_WAKE_VERIFIER (default ON si cargó el verificador).
        if (_VERIFIER_ENABLED and not noise_head
                and score >= LIVEKIT_THRESHOLD
                and getattr(self._livekit_model, "_verif_coef", None) is not None):
            vs = float(getattr(self._livekit_model, "last_verifier_score", 1.0))
            if vs < self._livekit_model.verifier_threshold:
                now = time.monotonic()
                if now - self._last_partial_at >= SAME_PHRASE_COOLDOWN_S:
                    self._last_partial_at = now
                    logger.info("wake VERIFICADOR rechazó falso: base=%.3f "
                                "verif=%.3f < %.2f", score, vs,
                                self._livekit_model.verifier_threshold)
                return
        self._evaluate_score(score, backend="livekit",
                             threshold=LIVEKIT_THRESHOLD,
                             partial=LIVEKIT_THRESHOLD * 0.5)

    # ----- OWW path ---------------------------------------------------

    def _feed_oww(self, chunk: np.ndarray, predict: bool = True) -> None:
        if self._oww_model is None:
            return
        self._oww_buf = np.concatenate([self._oww_buf, chunk])
        # predict=False: drenar el buffer SIN puntuar (mantener acotado durante
        # el TTS, sin disparar). Conserva solo la última ventana.
        if not predict:
            if self._oww_buf.size > OWW_WINDOW_SAMPLES:
                self._oww_buf = self._oww_buf[-OWW_WINDOW_SAMPLES:]
            return
        while self._oww_buf.size >= OWW_WINDOW_SAMPLES:
            window = self._oww_buf[:OWW_WINDOW_SAMPLES]
            self._oww_buf = self._oww_buf[OWW_WINDOW_SAMPLES:]
            try:
                scores = self._oww_model.predict(window)
            except Exception as exc:
                logger.warning("OWW predict failed: %s", exc)
                continue
            score = float(scores.get(self._oww_score_key, 0.0))
            self._evaluate_score(score, backend=self._backend,
                                 threshold=OWW_THRESHOLD,
                                 partial=OWW_PARTIAL_THRESHOLD)

    # ----- shared scoring ---------------------------------------------

    def _evaluate_score(
        self,
        score: float,
        *,
        backend: str,
        threshold: float,
        partial: float,
    ) -> None:
        if score < partial:
            return
        now = time.monotonic()
        if score < threshold:
            if now - self._last_partial_at >= SAME_PHRASE_COOLDOWN_S:
                self._last_partial_at = now
                logger.info(
                    "wake_word_partial score=%.3f threshold=%.3f backend=%s",
                    score, threshold, backend,
                )
            return
        if now - self._last_fire_at < SAME_PHRASE_COOLDOWN_S:
            return
        self._last_fire_at = now
        phrase = (
            "hey gemma" if self.using_custom_model else "hey jarvis"
        )
        logger.info(
            "wake_word_fired phrase=%s score=%.3f threshold=%.3f backend=%s",
            phrase, score, threshold, backend,
        )
        try:
            self._on_wake(phrase, score)
        except Exception as exc:
            logger.warning("on_wake callback raised: %s", exc)
