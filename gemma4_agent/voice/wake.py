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
# Calibrated on the universal held-out
# (500 clips / 25 voices / 13 languages + 7.7h LibriSpeech negatives):
#   thr 0.50: recall 0.550, fp/hr 0.000
#   thr 0.40: recall 0.636, fp/hr 0.000
#   thr 0.30: recall 0.708, fp/hr 0.000
#   thr 0.25: recall 0.744, fp/hr 0.000   <- chosen
#   thr 0.20: recall 0.764, fp/hr 0.000
# FP rate is 0.000 even at 0.20, so we pick 0.25 for max recall with a
# small safety margin. 7x the custom-OWW baseline (0.110) at zero false fires.
LIVEKIT_THRESHOLD = float(os.environ.get("GEMMA4_LIVEKIT_THRESHOLD", "0.25"))

# Stem del modelo LiveKit, configurable por env. Wake word = "Baxy" (el nombre del
# asistente). El modelo baxy.onnx PASÓ el gate: recall held-out 0.872 global, 1.00 en
# es/en/it/fr (medido 2026-06-04). Reemplazó a hey_gemma porque "Baxy" (sin /r/, vocal
# final) generaliza cross-idioma, mientras que "carter" (con /r/ rótica) colapsaba en
# idiomas no-ingleses (0.28). Override con GEMMA4_LIVEKIT_MODEL_STEM si hace falta.
LIVEKIT_MODEL_STEM = os.environ.get("GEMMA4_LIVEKIT_MODEL_STEM", "baxy")
LIVEKIT_MODEL_PATH = (
    Path(__file__).resolve().parent / "models" / "livekit" / f"{LIVEKIT_MODEL_STEM}.onnx"
)

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

    def feed(self, chunk: np.ndarray) -> None:
        """Append `chunk` (int16, mono, 16 kHz, any size) and predict."""
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
            self._feed_livekit(chunk_i16)
        else:
            self._feed_oww(chunk_i16)

    # ----- LiveKit path -----------------------------------------------

    def _feed_livekit(self, chunk: np.ndarray) -> None:
        # Maintain rolling 2-second buffer. IMPORTANT: append EVERY chunk so the
        # window is always current — only the predict() CALL is throttled below.
        self._lk_ring = np.concatenate([self._lk_ring, chunk])
        if self._lk_ring.size > LIVEKIT_WINDOW_SAMPLES:
            self._lk_ring = self._lk_ring[-LIVEKIT_WINDOW_SAMPLES:]
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
        try:
            # LiveKitWakeRuntime.predict() returns a float directly.
            score = float(self._livekit_model.predict(self._lk_ring))
        except Exception as exc:
            logger.warning("LiveKit predict failed: %s", exc)
            return
        self._evaluate_score(score, backend="livekit",
                             threshold=LIVEKIT_THRESHOLD,
                             partial=LIVEKIT_THRESHOLD * 0.5)

    # ----- OWW path ---------------------------------------------------

    def _feed_oww(self, chunk: np.ndarray) -> None:
        if self._oww_model is None:
            return
        self._oww_buf = np.concatenate([self._oww_buf, chunk])
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
