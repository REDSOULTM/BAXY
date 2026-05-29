"""Watchdog de VRAM pre-turno — previene el OOM que petaría el programa (inv 6).

El peligro real en vram4 NO es que el modelo no cargue (eso lo cubre
vram_calculator), sino el OOM en RUNTIME: llama-server NO recupera de un OOM CUDA
(queda zombie: responde /v1/models pero /completion cuelga, issue #13085). La
única defensa robusta es DETECTAR la presión de VRAM ANTES de despachar el turno
y degradar con gracia (descargar visión, bajar ctx) en vez de matar.

Diseño (informe 6): muestrear VRAM libre con bajo costo y exponer un NIVEL:
  - ok       : VRAM libre cómoda -> seguir normal.
  - warn     : libre bajando -> log, preparar degradación.
  - degrade  : libre escasa -> descargar mmproj (visión), bajar ctx target.
  - critical : libre crítica -> rechazar lo pesado (visión), avisar al user.

NUESTRO entorno: pynvml NO está instalado -> usamos nvidia-smi (ya validado en la
detección de GPU). Sin GPU NVIDIA -> el watchdog es no-op (nivel ok siempre), no
rompe nada. Muestreo con TTL para no spamear nvidia-smi. Todo barato, cabe en vram4.
"""
from __future__ import annotations

import logging
import subprocess
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Umbrales en MiB de VRAM LIBRE (medimos free, no used). Conservadores para
# vram4: el mmproj de Gemma 4 E4B pesa ~946 MiB, el compute buffer ~500 MiB.
# Si queda menos que 'degrade', cargar visión arriesga OOM.
_WARN_FREE_MIB = 1200
_DEGRADE_FREE_MIB = 800
_CRITICAL_FREE_MIB = 400

_SAMPLE_TTL_S = 2.0  # no consultar nvidia-smi más seguido que esto

LEVEL_OK = "ok"
LEVEL_WARN = "warn"
LEVEL_DEGRADE = "degrade"
LEVEL_CRITICAL = "critical"
_LEVEL_ORDER = {LEVEL_OK: 0, LEVEL_WARN: 1, LEVEL_DEGRADE: 2, LEVEL_CRITICAL: 3}


@dataclass
class VRAMSnapshot:
    free_mib: float
    used_mib: float
    total_mib: float
    level: str
    available: bool  # False si no hay GPU NVIDIA / nvidia-smi


def _query_nvidia_smi() -> tuple[float, float, float] | None:
    """(free, used, total) en MiB vía nvidia-smi, o None si no hay GPU/falla."""
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.free,memory.used,memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=4)
        line = (out.stdout or "").strip().splitlines()[0] if out.stdout.strip() else ""
        if not line:
            return None
        parts = [p.strip() for p in line.split(",")]
        return float(parts[0]), float(parts[1]), float(parts[2])
    except Exception:
        return None


def _level_for(free_mib: float) -> str:
    if free_mib < _CRITICAL_FREE_MIB:
        return LEVEL_CRITICAL
    if free_mib < _DEGRADE_FREE_MIB:
        return LEVEL_DEGRADE
    if free_mib < _WARN_FREE_MIB:
        return LEVEL_WARN
    return LEVEL_OK


class VRAMWatchdog:
    """Muestrea VRAM libre con TTL y expone el nivel de presión. Sin GPU NVIDIA
    es no-op (siempre ok)."""

    def __init__(self) -> None:
        self._last_snap: VRAMSnapshot | None = None
        self._last_t: float = 0.0
        self._gpu_absent: bool = False

    def snapshot(self, *, force: bool = False) -> VRAMSnapshot:
        now = time.time()
        if (not force and self._last_snap is not None
                and now - self._last_t < _SAMPLE_TTL_S):
            return self._last_snap
        if self._gpu_absent:
            snap = VRAMSnapshot(0, 0, 0, LEVEL_OK, available=False)
            self._last_snap, self._last_t = snap, now
            return snap
        q = _query_nvidia_smi()
        if q is None:
            self._gpu_absent = True  # no reintentar cada vez
            snap = VRAMSnapshot(0, 0, 0, LEVEL_OK, available=False)
        else:
            free, used, total = q
            snap = VRAMSnapshot(free, used, total, _level_for(free), available=True)
        self._last_snap, self._last_t = snap, now
        return snap

    def level(self) -> str:
        return self.snapshot().level

    def vision_safe(self) -> bool:
        """¿Hay VRAM libre para cargar el mmproj (~946 MiB) sin arriesgar OOM?
        Si no hay GPU detectable, asumimos sí (no bloquear sin evidencia)."""
        snap = self.snapshot()
        if not snap.available:
            return True
        return snap.free_mib >= (_DEGRADE_FREE_MIB + 950)

    def should_degrade(self) -> bool:
        return self.snapshot().level in (LEVEL_DEGRADE, LEVEL_CRITICAL)
