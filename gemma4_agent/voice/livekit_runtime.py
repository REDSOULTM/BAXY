"""Pure-onnxruntime LiveKit wake-word inference for Python 3.10.

The trained LiveKit model lives as 3 ONNX graphs. The
`livekit-wakeword` PyPI package requires Python 3.11, but
the Gemma 4 runtime is 3.10. This module reimplements LiveKit's
inference pipeline using ONLY onnxruntime + numpy, so it loads in 3.10.

Pipeline (mirrors livekit.wakeword.inference.WakeWordModel exactly):
  audio (16 kHz, ~2 s) -> melspectrogram.onnx -> (T, 32) dB mel
                       -> mel/10 + 2  (openWakeWord normalization)
                       -> 76-frame windows, stride 8 -> embedding.onnx
                       -> (96,) per window
                       -> last 16 embeddings -> hey_gemma.onnx -> score

Models expected under models_dir:
  melspectrogram.onnx   (bundled, copied from livekit package)
  embedding_model.onnx  (bundled, copied from livekit package)
  hey_gemma.onnx        (our trained classifier)

Threading: we cap onnxruntime to a small thread count and disable
busy-wait spinning so live mic inference does not saturate the CPU
(see scripts/_ort_throttle.py for the lesson learned during eval).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
EMBEDDING_WINDOW = 76   # mel frames per embedding
EMBEDDING_STRIDE = 8    # mel frames between embeddings
MIN_EMBEDDINGS = 16     # classifier input length
# A 2 s window at 16 kHz yields exactly 16 embeddings.
WINDOW_SAMPLES = 32000

# Keep inference light so it never starves the foreground app.
INTRA_OP_THREADS = 2


class LiveKitWakeRuntime:
    """Stateless LiveKit wake-word scorer (pure onnxruntime).

    Usage:
        rt = LiveKitWakeRuntime(models_dir, classifier="hey_gemma")
        rt.load()
        score = rt.predict(audio_2s_int16)  # float 0..1
    """

    def __init__(self, models_dir: Path, classifier_stem: str = "hey_gemma") -> None:
        self._dir = Path(models_dir)
        self._classifier_stem = classifier_stem
        self._mel: Any = None
        self._mel_input: str = ""
        self._emb: Any = None
        self._emb_input: str = ""
        self._clf: Any = None
        self._clf_input: str = ""
        # Clasificadores EXTRA (fusión dual): stem -> (session, input_name).
        self._extra_clfs: dict[str, tuple[Any, str]] = {}
        # VERIFICADOR opcional (openWakeWord custom_verifier): regresión logística
        # sobre el MISMO embedding (1,16,96). Filtra los falsos del modelo base
        # (entrenado con los fakes reales + Baxy real/sintético). Si carga, predict
        # devuelve también su score para que wake.py gatee el disparo.
        self._verif_coef: np.ndarray | None = None
        self._verif_intercept: float = 0.0
        self.verifier_threshold: float = 0.5
        self.last_verifier_score: float = 1.0
        self._loaded = False
        self.last_error: str | None = None

    def _make_session(self, path: Path) -> Any:
        import onnxruntime as ort
        so = ort.SessionOptions()
        so.intra_op_num_threads = INTRA_OP_THREADS
        so.inter_op_num_threads = 1
        so.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        try:
            so.add_session_config_entry("session.intra_op.allow_spinning", "0")
        except Exception:
            pass
        return ort.InferenceSession(
            str(path), sess_options=so, providers=["CPUExecutionProvider"],
        )

    def load(self) -> bool:
        if self._loaded:
            return True
        mel_p = self._dir / "melspectrogram.onnx"
        emb_p = self._dir / "embedding_model.onnx"
        clf_p = self._dir / f"{self._classifier_stem}.onnx"
        for p in (mel_p, emb_p, clf_p):
            if not p.exists():
                self.last_error = f"missing ONNX: {p}"
                logger.error(self.last_error)
                return False
        try:
            self._mel = self._make_session(mel_p)
            self._mel_input = self._mel.get_inputs()[0].name
            self._emb = self._make_session(emb_p)
            self._emb_input = self._emb.get_inputs()[0].name
            self._clf = self._make_session(clf_p)
            self._clf_input = self._clf.get_inputs()[0].name
            self._load_verifier()
            self._loaded = True
            logger.info(
                "LiveKitWakeRuntime loaded (classifier=%s)",
                self._classifier_stem,
            )
            return True
        except Exception as exc:
            self.last_error = f"LiveKitWakeRuntime load failed: {exc}"
            logger.error(self.last_error)
            return False

    def _mel_features(self, audio_f32: np.ndarray) -> np.ndarray:
        """audio (samples,) float32 -> (T, 32) normalized mel."""
        inp = audio_f32[np.newaxis, :].astype(np.float32)
        out = self._mel.run(None, {self._mel_input: inp})[0]
        # (batch, time, 32) or (batch, 1, time, 32)
        if out.ndim == 4:
            out = out[:, 0, :, :]
        mel = out[0]  # (T, 32)
        # openWakeWord normalization (matches LiveKit feature_extractor).
        return mel / 10.0 + 2.0

    def add_classifier(self, stem: str) -> bool:
        """Carga un clasificador EXTRA que comparte el frontend mel+embedding.

        Fusión dual (2026-06-12): el costo de inferencia lo domina el
        frontend; una cabeza extra agrega solo su pasada (~sub-ms). Permite
        correr el modelo limpio Y el modelo robusto-a-ruido en paralelo y
        disparar por OR con umbrales independientes (ver wake.py)."""
        try:
            sess = self._make_session(self._dir / f"{stem}.onnx")
            self._extra_clfs[stem] = (sess, sess.get_inputs()[0].name)
            logger.info("LiveKitWakeRuntime: clasificador extra '%s' cargado", stem)
            return True
        except Exception as exc:
            logger.warning("clasificador extra '%s' no cargó: %s", stem, exc)
            return False

    def _classifier_input(self, audio_chunk: np.ndarray) -> "np.ndarray | None":
        """audio (~2 s) -> tensor (1,16,96) para los clasificadores, o None
        si la ventana es corta. UNA pasada de mel+embedding para N cabezas."""
        if audio_chunk.dtype == np.int16:
            audio = audio_chunk.astype(np.float32) / 32768.0
        else:
            audio = audio_chunk.astype(np.float32)
        audio = audio.flatten()

        mel = self._mel_features(audio)
        if mel.shape[0] < EMBEDDING_WINDOW:
            return None

        embeddings = []
        for start in range(0, mel.shape[0] - EMBEDDING_WINDOW + 1, EMBEDDING_STRIDE):
            window = mel[start : start + EMBEDDING_WINDOW]  # (76, 32)
            inp = window[np.newaxis, :, :, np.newaxis].astype(np.float32)  # (1,76,32,1)
            emb = self._emb.run(None, {self._emb_input: inp})[0]
            embeddings.append(emb.squeeze())  # (96,)

        if len(embeddings) < MIN_EMBEDDINGS:
            return None
        emb_seq = np.stack(embeddings[-MIN_EMBEDDINGS:], axis=0)
        return emb_seq[np.newaxis, :, :].astype(np.float32)  # (1,16,96)

    def predict(self, audio_chunk: np.ndarray) -> float:
        """Score a ~2 s audio chunk. Returns float 0..1.

        Accepts int16 or float32. Shorter-than-window chunks return 0.0.
        """
        if not self._loaded:
            return 0.0
        clf_in = self._classifier_input(audio_chunk)
        if clf_in is None:
            return 0.0
        out = self._clf.run(None, {self._clf_input: clf_in})[0]
        # Verificador (si cargó): puntúa el MISMO embedding. wake.py lo lee de
        # last_verifier_score para gatear el disparo (filtra falsos del base).
        if self._verif_coef is not None:
            z = float(np.dot(self._verif_coef, clf_in.reshape(-1))
                      + self._verif_intercept)
            self.last_verifier_score = 1.0 / (1.0 + np.exp(-z))
        return float(out[0, 0])

    def _load_verifier(self) -> None:
        """Carga el verificador (baxy_verifier.json) si existe: regresión
        logística sobre el embedding (1536). Sin archivo -> sin verificador
        (no-op, el wake funciona como siempre)."""
        import json
        vp = self._dir / "baxy_verifier.json"
        if not vp.exists():
            return
        try:
            d = json.loads(vp.read_text(encoding="utf-8"))
            self._verif_coef = np.asarray(d["coef"], dtype=np.float64)
            self._verif_intercept = float(d["intercept"])
            self.verifier_threshold = float(d.get("threshold", 0.5))
            import os as _os
            _env = (_os.environ.get("GEMMA4_WAKE_VERIFIER_THRESHOLD") or "").strip()
            if _env:   # override para calibrar end-to-end sin re-entrenar
                self.verifier_threshold = float(_env)
            logger.info("LiveKit verificador cargado (thr=%.2f, dim=%d)",
                        self.verifier_threshold, self._verif_coef.size)
        except Exception as exc:
            logger.warning("verificador no cargó: %s", exc)
            self._verif_coef = None

    def predict_multi(self, audio_chunk: np.ndarray) -> dict[str, float]:
        """Scores de TODOS los clasificadores (primario + extras) con UNA
        pasada de frontend. Claves: stem de cada clasificador."""
        if not self._loaded:
            return {}
        clf_in = self._classifier_input(audio_chunk)
        if clf_in is None:
            return {}
        scores = {self._classifier_stem: float(
            self._clf.run(None, {self._clf_input: clf_in})[0][0, 0])}
        for stem, (sess, inp_name) in self._extra_clfs.items():
            try:
                scores[stem] = float(sess.run(None, {inp_name: clf_in})[0][0, 0])
            except Exception as exc:
                logger.debug("clf extra %s falló: %s", stem, exc)
        return scores
