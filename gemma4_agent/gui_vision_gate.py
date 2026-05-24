"""Gate de visión para la cascada GUI (Fase 8 computer-use).

La visión (Gemma 4 + mmproj ~990 MiB) es el ÚLTIMO recurso de la cascada
UIA→OCR→visión: solo cuando UIA y OCR fallaron en localizar el objetivo. Es
costosa (compite por la VRAM del LLM en el target de 6 GB) y poco fiable para
grounding de píxeles (ni un VLM dedicado como UI-TARS-7B pasa ~50% en UIs
difíciles). Por eso NO clickea por visión a ciegas: ESCALA a un screenshot que
el agente razona con su visión nativa para (a) localizar de otra forma o (b)
reportar honestamente qué ve, en vez de fallar en silencio.

Dos gates duros (umbral del roadmap: "vision calls/misión >2 → cascada rota"):
 1. PRESUPUESTO por misión: ≤ N escalaciones de visión (default 2). Evita el
    loop de visión y mantiene la latencia/VRAM acotadas.
 2. VRAM: solo si hay sitio para el mmproj sin arriesgar OOM (VRAMWatchdog).

Gate por env: GEMMA4_GUI_VISION_GATE=0 lo desactiva (la cascada termina en OCR).
GEMMA4_GUI_VISION_BUDGET (default 2) = escalaciones por misión.

Best-effort: cualquier fallo de medición -> NO escala (lado seguro: no cargar
visión si no estamos seguros de que entra).
"""
from __future__ import annotations

import os
import time
from typing import Any

# Watchdog VRAM compartido (TTL-cacheado, no-op sin GPU NVIDIA). Lazy singleton.
_watchdog = None


def _get_watchdog():
    global _watchdog
    if _watchdog is None:
        try:
            from .vram_watchdog import VRAMWatchdog
            _watchdog = VRAMWatchdog()
        except Exception:
            _watchdog = False  # marcar no disponible
    return _watchdog or None


def _enabled() -> bool:
    return os.environ.get("GEMMA4_GUI_VISION_GATE", "1").strip().lower() \
        not in {"0", "false", "no", "off"}


def _budget() -> int:
    try:
        return max(0, int(os.environ.get("GEMMA4_GUI_VISION_BUDGET", "2")))
    except ValueError:
        return 2


# Presupuesto POR MISIÓN. La "misión" es una ventana de tiempo/contador que el
# orquestador resetea al empezar una misión (reset_budget). Si nadie lo resetea,
# usamos un reset por inactividad (si pasó mucho desde la última escalación,
# asumimos misión nueva) para no quedar bloqueados para siempre.
_used: int = 0
_last_use_ts: float = 0.0
_MISSION_IDLE_RESET_S = 120.0


def reset_budget() -> None:
    """Resetea el presupuesto de visión (llamar al empezar una misión)."""
    global _used, _last_use_ts
    _used = 0
    _last_use_ts = 0.0


def _maybe_idle_reset() -> None:
    global _used
    if _last_use_ts and (time.time() - _last_use_ts) > _MISSION_IDLE_RESET_S:
        _used = 0


def can_escalate() -> tuple[bool, str]:
    """¿Se puede escalar a visión ahora? Devuelve (ok, motivo). Chequea gate,
    presupuesto y VRAM. NO consume presupuesto (eso lo hace note_escalation)."""
    if not _enabled():
        return False, "vision_gate_off"
    _maybe_idle_reset()
    if _used >= _budget():
        return False, f"vision_budget_exhausted ({_used}/{_budget()})"
    wd = _get_watchdog()
    if wd is not None:
        try:
            if not wd.vision_safe():
                snap = wd.snapshot()
                return False, f"vram_unsafe (free={snap.free_mib:.0f}MiB)"
        except Exception:
            pass  # sin medición fiable -> no bloquear por VRAM
    return True, "ok"


def note_escalation() -> None:
    """Consume una unidad del presupuesto de visión de la misión."""
    global _used, _last_use_ts
    _used += 1
    _last_use_ts = time.time()


def budget_state() -> dict[str, Any]:
    return {"used": _used, "budget": _budget(), "enabled": _enabled()}
