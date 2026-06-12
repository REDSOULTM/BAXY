"""AEC — cancelación de eco acústico con señal de referencia (P1, 2026-06-12).

El truco de Alexa para "háblale encima de la música": el dispositivo CONOCE
lo que está reproduciendo (señal de referencia) y lo RESTA del micrófono.
No es el modelo de wake: es procesamiento de señal. Acá: referencia =
loopback WASAPI del PC (ver audio_io); cancelador = NLMS por bloques en
numpy puro (sin deps nativas: speexdsp no tiene wheels Windows y los
bindings de WebRTC-APM están muertos — research en
wake_ruido_fondo_2026-06-11.md). NLMS no es AEC3, pero 10-20 dB de
atenuación del eco convierten el caso "película MÁS fuerte que la voz"
(SNR<0, imposible para cualquier modelo) en uno fácil (SNR+10 o más).

Piezas:
  - DelayEstimator: el loopback llega ANTES que su eco en el mic (DAC →
    parlante → aire → mic ≈ 5-60 ms + buffers). Correlación cruzada sobre
    una ventana rodante; re-estima despacio (la deriva de reloj entre
    streams mueve el delay — EL problema duro del AEC software).
  - NlmsCanceller: filtro adaptativo w (len ~256 ms a 16 kHz) que predice
    el eco desde la referencia alineada y lo resta. Adaptación normalizada
    (estable ante cambios de volumen) con freeze-on-double-talk simple
    (si el error es grande vs eco predicho, hay voz local: no adaptar).

Todo float64 interno, int16 en los bordes. Sin estado global; el caller
(audio_io) alimenta pares (mic_chunk, ref_chunk) de 512 samples.
"""
from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
CHUNK = 512


class DelayEstimator:
    """Delay referencia→mic por correlación cruzada en ventana rodante."""

    def __init__(self, window_s: float = 1.5, max_delay_s: float = 0.25) -> None:
        self._n = int(window_s * SAMPLE_RATE)
        self._max = int(max_delay_s * SAMPLE_RATE)
        self._mic = np.zeros(self._n, dtype=np.float64)
        self._ref = np.zeros(self._n + self._max, dtype=np.float64)
        self.delay: int | None = None

    def push(self, mic: np.ndarray, ref: np.ndarray) -> None:
        m = mic.astype(np.float64)
        r = ref.astype(np.float64)
        self._mic = np.concatenate([self._mic[m.size:], m])
        self._ref = np.concatenate([self._ref[r.size:], r])

    def estimate(self) -> int | None:
        """Devuelve delay en samples (ref adelantada al mic) o None si no hay
        energía suficiente para confiar (silencio en la referencia)."""
        r = self._ref
        m = self._mic
        if float(np.sqrt(np.mean(r * r))) < 30.0:   # ref ~silencio: no estimar
            return self.delay
        # correlación de m contra r corrida k ∈ [0, max]: el eco en m ocurre
        # DESPUÉS de la ref → m[t] ~ r[t - k] con la ref bufferizada extra.
        best_k, best_c = None, 0.0
        rn = r / (np.sqrt(np.mean(r * r)) + 1e-9)
        mn = m / (np.sqrt(np.mean(m * m)) + 1e-9)
        for k in range(0, self._max, 32):           # paso 2 ms
            seg = rn[self._max - k: self._max - k + self._n]
            c = abs(float(np.dot(mn, seg))) / self._n
            if c > best_c:
                best_c, best_k = c, k
        if best_k is not None and best_c > 0.05:
            self.delay = best_k
        return self.delay


class NlmsCanceller:
    """NLMS por muestra sobre bloques de 512; filtro ~256 ms."""

    def __init__(self, filter_len: int = 4096, mu: float = 0.5) -> None:
        self._L = filter_len
        self._mu = mu
        self._w = np.zeros(filter_len, dtype=np.float64)
        self._xbuf = np.zeros(filter_len + CHUNK, dtype=np.float64)

    def process(self, mic: np.ndarray, ref_aligned: np.ndarray) -> np.ndarray:
        """Devuelve mic - eco_estimado (int16). Adapta salvo double-talk."""
        d = mic.astype(np.float64)
        x = ref_aligned.astype(np.float64)
        self._xbuf = np.concatenate([self._xbuf[CHUNK:], x])
        out = np.empty(CHUNK, dtype=np.float64)
        L = self._L
        w = self._w
        for i in range(CHUNK):
            # taps = los últimos L samples de referencia TERMINANDO en el
            # sample actual: _xbuf[L+i] es x[t] (el chunk vive en [L:L+CHUNK]).
            xi = self._xbuf[i + 1: i + 1 + L][::-1]
            y = float(np.dot(w, xi))
            e = d[i] - y
            out[i] = e
            # normalized update; freeze si |e| >> |y| (voz local dominante)
            p = float(np.dot(xi, xi)) + 1e3
            if abs(e) < 4.0 * (abs(y) + 50.0):
                w += (self._mu / p) * e * xi
        return np.clip(out, -32768, 32767).astype(np.int16)


class EchoCanceller:
    """Orquesta delay + NLMS para el pipeline. Par (mic, ref) por chunk."""

    def __init__(self) -> None:
        self._delay_est = DelayEstimator()
        self._nlms = NlmsCanceller()
        self._ref_hist = np.zeros(SAMPLE_RATE, dtype=np.int16)  # 1 s de ref
        self._chunks = 0

    def process(self, mic: np.ndarray, ref: np.ndarray) -> np.ndarray:
        self._ref_hist = np.concatenate([self._ref_hist[ref.size:], ref])
        self._delay_est.push(mic, ref)
        self._chunks += 1
        if self._chunks % 31 == 0:                  # re-estimar ~1 vez/s
            self._delay_est.estimate()
        delay = self._delay_est.delay
        if delay is None:
            return mic.astype(np.int16, copy=False)  # sin lock aún: pasar
        end = self._ref_hist.size
        if delay > 0:
            seg = self._ref_hist[end - CHUNK - delay: end - delay]
        else:
            seg = self._ref_hist[-CHUNK:]
        if seg.size != CHUNK:
            return mic.astype(np.int16, copy=False)
        return self._nlms.process(mic, seg)


__all__ = ["EchoCanceller", "DelayEstimator", "NlmsCanceller"]
