"""Auto-calibración del piso de ruido del micrófono (2026-06-07).

Problema (reporte del user): el gate de silencio usaba un umbral FIJO
(MIN_CAPTURE_RMS=350) calibrado para UN micrófono. En otro mic con más ruido de
fondo, ese 350 queda por debajo del ambiente -> el pipeline "oye voces donde no
hay" (dispara con ventilador/ruido). En un mic muy silencioso, 350 es demasiado
alto -> ignora voz tenue. Un umbral fijo NO es universal.

Solución (lo que hacen Discord/Zoom: noise-gate auto-calibrado): medir el piso de
ruido REAL de cada micrófono y poner el umbral un poco por encima. Se adapta a
cada PC sola — universal, sin hardcodear un número por hardware.

Diseño:
  - El piso se estima con un PERCENTIL alto del RMS por ventana (no el máximo, que
    capturaría un golpe aislado; no la media, que un pico inflaría). Robusto.
  - umbral = piso × factor (factor ~2.5-3: la voz debe ser claramente más fuerte
    que el ambiente). Con pisos/techos de seguridad para no quedar en 0 ni ∞.
  - Re-ajuste lento (EMA) durante los silencios: si el ambiente cambia (prende el
    ventilador), el piso se actualiza solo, despacio, sin que el user lo note.

Puro (sin audio I/O) para ser testeable sin micrófono. El pipeline le pasa el RMS
ya medido de cada ventana.
"""
from __future__ import annotations

import os

import numpy as np

# Factor: cuánto más fuerte que el piso de ruido debe ser la voz para disparar.
# El umbral es RELATIVO al ruido de CADA mic (universal: no asume un nivel de
# hardware). MEDIDO 2026-06-07 en un mic de baja ganancia: ruido≈66, voz≈125
# (ratio ~1.9x). Un factor 2.8 dejaba el umbral (185) POR ENCIMA de la voz (125)
# -> la ignoraba. 1.6 cae JUSTO entre ruido y voz para ese mic, y para uno normal
# (ratio voz/ruido típico >=3-5x) sigue cómodo. Env-tunable.
_GATE_FACTOR = float(os.environ.get("GEMMA4_VOICE_GATE_FACTOR", "1.6"))
# Pisos/techos RELATIVOS, no absolutos (la solución debe servir a CUALQUIER mic,
# sin asumir su escala — pedido user 2026-06-07). FLOOR_MIN es solo un anti-cero
# ínfimo (un mic en silencio digital total no debe dejar el umbral en 0 y disparar
# con cualquier bit de ruido); deliberadamente BAJO para no ignorar mics de baja
# ganancia (el viejo 250 ignoraba una voz de 125). FLOOR_MAX es un techo amplio
# anti-runaway. El umbral REAL lo manda el factor × ruido medido, no estos límites.
_FLOOR_MIN = float(os.environ.get("GEMMA4_VOICE_GATE_FLOOR_MIN", "20"))
_FLOOR_MAX = float(os.environ.get("GEMMA4_VOICE_GATE_FLOOR_MAX", "6000"))
# Percentil del RMS por ventana que se toma como "piso de ruido" del ambiente.
# 75 = robusto a picos aislados (un golpe) pero representativo del ambiente real.
_NOISE_PERCENTILE = float(os.environ.get("GEMMA4_VOICE_NOISE_PCT", "75"))
# EMA para el re-ajuste lento en silencios: nuevo_piso = (1-α)·viejo + α·medido.
# α chico = se mueve despacio (no salta con un ruido puntual). 0.05 ~ ventana larga.
_EMA_ALPHA = float(os.environ.get("GEMMA4_VOICE_NOISE_EMA", "0.05"))


def threshold_from_floor(noise_floor: float) -> float:
    """umbral de captura = piso de ruido × factor, acotado a [FLOOR_MIN, FLOOR_MAX]."""
    raw = max(0.0, noise_floor) * _GATE_FACTOR
    return float(min(_FLOOR_MAX, max(_FLOOR_MIN, raw)))


def estimate_noise_floor(window_rms: list[float] | np.ndarray) -> float | None:
    """Estima el piso de ruido (percentil alto) de una lista de RMS por ventana
    de ambiente (asume que el user NO habló durante la medición). None si no hay
    datos suficientes."""
    arr = np.asarray([r for r in window_rms if r is not None and r >= 0.0],
                     dtype=np.float64)
    if arr.size < 3:
        return None
    return float(np.percentile(arr, _NOISE_PERCENTILE))


class NoiseFloorCalibrator:
    """Mantiene el piso de ruido estimado y el umbral derivado, con re-ajuste EMA.

    Uso en el pipeline:
        cal = NoiseFloorCalibrator()
        cal.calibrate(initial_window_rms)   # 1 vez al arrancar (1.5s ambiente)
        ...
        if cal.threshold and peak_rms < cal.threshold: skip   # gate
        ...
        cal.observe(window_rms)             # cada chunk IDLE: re-ajuste robusto
    """

    def __init__(self) -> None:
        self._floor: float | None = None
        self._bg: float | None = None     # nivel típico del fondo (p75-EMA)
        self.threshold: float | None = None
        self.calibrated: bool = False
        # Ventana rodante de RMS por chunk para la estimación ROBUSTA del piso
        # (~5 s a 31 chunks/s). Ver observe().
        from collections import deque
        self._recent: deque[float] = deque(maxlen=int(
            os.environ.get("GEMMA4_VOICE_NOISE_WIN_CHUNKS", "150") or 150))

    def calibrate(self, window_rms: list[float] | np.ndarray) -> bool:
        """Calibración inicial desde una ventana de ambiente. True si calibró."""
        floor = estimate_noise_floor(window_rms)
        if floor is None:
            return False
        self._floor = floor
        self.threshold = threshold_from_floor(floor)
        self.calibrated = True
        return True

    def observe(self, window_rms: float) -> None:
        """Re-ajuste lento del piso con TODOS los chunks IDLE, robusto a ráfagas
        de habla (2026-06-11). El EMA directo sobre cada chunk era un BUG: la
        propia frase de wake (~20 chunks de voz, α=0.05) movía el piso ~64%
        hacia el nivel de voz → el gate del wake y el EOS-híbrido quedaban
        calibrados contra la VOZ, no contra el ambiente (medido con el harness
        de cadena: cortes a mitad de comando en sala silenciosa). El piso real
        es el PERCENTIL BAJO de una ventana rodante (~5 s): el habla es a
        ráfagas y los huecos entre ellas SÍ son ambiente — p25 los encuentra
        aunque el VAD diga "speech" continuo (película de fondo: p25 ≈ sus
        momentos quietos, que es el piso correcto para detectar la voz del
        usuario POR ENCIMA)."""
        if window_rms is None or window_rms < 0:
            return
        self._recent.append(float(window_rms))
        if self._floor is None or len(self._recent) < 24:   # ~0.75 s mínimo
            return
        arr = np.asarray(self._recent)
        target = float(np.percentile(arr, 25))
        self._floor = (1.0 - _EMA_ALPHA) * self._floor + _EMA_ALPHA * target
        self.threshold = threshold_from_floor(self._floor)
        # Nivel TÍPICO del fondo (p75): el estadístico para el EOS-híbrido.
        # p25 (piso) y p75 (nivel) son trabajos distintos: el gate anti-falso
        # quiere el ambiente entre ráfagas; "el usuario dejó de hablar" se
        # decide contra lo que el fondo SUELE medir (una película promedia
        # mucho más que sus huecos).
        bg_target = float(np.percentile(arr, 75))
        if self._bg is None:
            self._bg = bg_target
        else:
            self._bg = (1.0 - _EMA_ALPHA) * self._bg + _EMA_ALPHA * bg_target

    def observe_silence(self, window_rms: float) -> None:
        """Compat: delega en observe() (la versión robusta a ráfagas de habla).
        El nombre histórico asumía que el caller solo pasaba silencios — en la
        práctica recibía TODOS los chunks IDLE, ver observe()."""
        self.observe(window_rms)

    @property
    def noise_floor(self) -> float | None:
        return self._floor

    @property
    def background_level(self) -> float | None:
        """Nivel típico (p75-EMA) del fondo reciente. None hasta tener ventana."""
        return self._bg


def microphone_muted() -> bool | None:
    """¿El micrófono de captura DEFAULT del sistema está muteado en Windows?

    Causa real (2026-06-07): el user reportó "no oye" y el mic default estaba
    silenciado a nivel sistema (ícono tachado en Sonido>Entrada) -> captura ceros
    en silencio total, parece que el STT está roto. Lo detectamos para AVISAR en
    vez de quedar mudo sin explicación. Usa pycaw (ya es dep). Returns:
      True  = mic default muteado;  False = no muteado;  None = no se pudo leer
      (no-Windows / pycaw ausente / sin mic) -> el llamador NO debe alarmar."""
    try:
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume  # type: ignore
        # COM debe estar inicializado EN ESTE HILO o pycaw crashea al liberar el
        # puntero COM (access violation en comtypes __del__). Idempotente. Mismo
        # patrón que tools.py para GetSpeakers. (Fix 2026-06-07.)
        try:
            from comtypes import CoInitialize  # type: ignore
            CoInitialize()
        except Exception:
            pass
        mic = AudioUtilities.GetMicrophone()
        if mic is None:
            return None
        interface = mic.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        vol = cast(interface, POINTER(IAudioEndpointVolume))
        return bool(vol.GetMute())
    except Exception:
        return None


__all__ = [
    "NoiseFloorCalibrator", "estimate_noise_floor", "threshold_from_floor",
    "microphone_muted",
]
