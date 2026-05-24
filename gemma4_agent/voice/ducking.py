"""Audio ducking: baja el volumen del PC mientras Gemma te escucha.

Cuando dispara el wake-word y se entra en CAPTURA, el volumen del sistema baja
(default ~20%) para que el STT escuche el comando limpio sobre la música/video.
Al dejar de hablar (transcribe / no-speech / idle) se RESTAURA al valor exacto
que tenías. Es el comportamiento clásico tipo Alexa que el operador recordaba.

Diseño robusto (CLAUDE.md: no dejar el PC en mal estado):
- RESTAURA SIEMPRE ante cualquier fallo. Si algo explota a mitad, el volumen
  vuelve; nunca te deja el PC mudo.
- Guarda el nivel previo SOLO al primer duck (idempotente): si ya está duckeado,
  no re-guarda el nivel bajo como "previo" (evita quedar trabado en 20%).
- pycaw + CoInitialize por-thread (el runner llama desde threads worker; sin
  CoInitialize, GetSpeakers() tira WinError -2147221008). Mismo patrón que
  tools._audio_endpoint_volume (commit a15105f).
- No-op si pycaw/comtypes no están o no hay endpoint de audio. Barato.

Gate: GEMMA4_VOICE_DUCKING=0 lo apaga. Nivel: GEMMA4_VOICE_DUCK_LEVEL (0..1).
"""
from __future__ import annotations

import logging
import os
import threading

logger = logging.getLogger(__name__)


def _duck_enabled() -> bool:
    raw = (os.environ.get("GEMMA4_VOICE_DUCKING") or "").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _duck_level() -> float:
    """Volumen objetivo mientras escucha (escalar 0..1). Default 0.20 (~20%)."""
    try:
        v = float(os.environ.get("GEMMA4_VOICE_DUCK_LEVEL", "0.20"))
    except (TypeError, ValueError):
        v = 0.20
    return max(0.0, min(1.0, v))


class AudioDucker:
    """Baja/restaura el volumen master del sistema. Thread-safe, idempotente."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._prev_scalar: float | None = None  # volumen antes de duckear
        self._ducked = False
        self._unavailable = False  # pycaw/endpoint ausente -> no-op permanente

    def _endpoint(self):
        """IAudioEndpointVolume COM pointer, o None si no disponible. Inicializa
        COM en este thread (los callbacks vienen de threads worker)."""
        if self._unavailable:
            return None
        try:
            from ctypes import POINTER, cast
            from comtypes import CLSCTX_ALL  # type: ignore[import-not-found]
            from pycaw.pycaw import (  # type: ignore[import-not-found]
                AudioUtilities, IAudioEndpointVolume,
            )
            try:
                from comtypes import CoInitialize  # type: ignore[import-not-found]
                CoInitialize()  # idempotente (S_FALSE si ya estaba)
            except Exception:
                pass
            device = AudioUtilities.GetSpeakers()
            if device is None:
                return None
            if hasattr(device, "EndpointVolume"):
                return device.EndpointVolume
            iface = device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            return cast(iface, POINTER(IAudioEndpointVolume))
        except Exception as exc:
            # Sin pycaw/comtypes o sin endpoint -> no-op permanente (no spamear).
            self._unavailable = True
            logger.debug("AudioDucker no disponible: %s", exc)
            return None

    def duck(self) -> None:
        """Baja el volumen al nivel de ducking, guardando el actual. Idempotente:
        si ya está duckeado, no hace nada (no re-guarda el nivel bajo)."""
        if not _duck_enabled():
            return
        with self._lock:
            if self._ducked:
                return
            ep = self._endpoint()
            if ep is None:
                return
            try:
                self._prev_scalar = float(ep.GetMasterVolumeLevelScalar())
                target = _duck_level()
                # No duckear si ya estás más bajo que el target (no SUBAS el vol).
                if self._prev_scalar <= target:
                    self._prev_scalar = None  # nada que restaurar
                    return
                ep.SetMasterVolumeLevelScalar(target, None)
                self._ducked = True
                logger.info("ducking: %.0f%% -> %.0f%% (escuchando)",
                            self._prev_scalar * 100, target * 100)
            except Exception as exc:
                # Si falló a mitad, intentar restaurar y limpiar estado.
                logger.debug("duck() falló: %s", exc)
                self._safe_restore_locked(ep)

    def restore(self) -> None:
        """Restaura el volumen previo. Seguro de llamar siempre (no-op si no se
        había duckeado)."""
        with self._lock:
            if not self._ducked or self._prev_scalar is None:
                self._ducked = False
                self._prev_scalar = None
                return
            ep = self._endpoint()
            self._safe_restore_locked(ep)

    def _safe_restore_locked(self, ep) -> None:
        """Restaura usando el endpoint dado (lock ya tomado). Nunca lanza."""
        prev = self._prev_scalar
        self._ducked = False
        self._prev_scalar = None
        if ep is None or prev is None:
            return
        try:
            ep.SetMasterVolumeLevelScalar(float(prev), None)
            logger.info("ducking: restaurado a %.0f%%", prev * 100)
        except Exception as exc:
            logger.debug("restore() falló: %s", exc)
