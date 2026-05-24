"""verify_post_action — cierra el "click/type ciego" (Fase 1 computer-use).

PROBLEMA (medido, baseline Fase 0 2026-05-24): el tool `gui` despacha clicks/types
y reporta ok=True sin verificar que el SO cambió. En misiones multi-paso el 4B
"cree" que hizo algo que no hizo (falso-PASS 14.3% en el eval-set).

SOLUCIÓN (triangulada por la investigación, SIN VLM, cabe en vram4): tras la
acción, comparar el estado de la PANTALLA antes/después en una REGIÓN acotada
(ROI alrededor del punto de acción) + chequear el foreground. Si nada cambió y
encima se perdió el foco -> la acción probablemente no tuvo efecto.

Señales (las baratas que aplican a clicks por coordenada; UIA-delta requiere el
elemento, que el click ciego no tiene — se suma en Fase 2 con las macros):
  1. frame-diff de ROI con dHash 8x8 (Hamming). Trampa conocida: cursor/reloj/
     blink dan falsos -> por eso ROI acotado (no full-screen) + excluir esquina
     del reloj. ~5ms.
  2. foreground window (GetForegroundWindow). ~1ms.

Devuelve un dict honesto {state_changed: bool|None, signals, ...} que el tool
ANOTA en su result. NO decide PASS/FAIL del turno (eso lo hace mission_goal); solo
le da al agente y al honesty-guard la evidencia de si el efecto se materializó,
para que deje de afirmar acciones no realizadas.

Gate: GEMMA4_GUI_VERIFY=0 lo desactiva (vuelve al comportamiento ciego previo).
Best-effort: cualquier fallo -> state_changed=None (no rompe la acción).
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

# Hamming mínimo sobre 64 bits del dHash para considerar que el ROI CAMBIÓ.
# Medido: blink de cursor / reloj en un ROI acotado da <4; un click que abre
# menú/cambia estado da >=6. Conservador a 6 (la investigación lo respalda).
_DHASH_HAMMING_MIN = 6
# Margen alrededor del punto de acción para el ROI (px). Captura el botón + su
# contexto inmediato sin tragar el reloj/notificaciones del borde de pantalla.
_ROI_MARGIN = 120
# Settling: la UI necesita un instante para refrescar tras el input.
_SETTLE_S = 0.10


def _enabled() -> bool:
    return (os.environ.get("GEMMA4_GUI_VERIFY", "1").strip().lower()
            not in {"0", "false", "no", "off"})


@dataclass
class _Cap:
    """Una captura de ROI + hash, tomada antes/después de la acción."""
    hash: int | None
    fg_hwnd: int | None


def _foreground_hwnd() -> int | None:
    try:
        import win32gui
        return win32gui.GetForegroundWindow()
    except Exception:
        return None


def _dhash8(arr) -> int | None:
    """dHash 8x8 (64 bits) de un array RGB(A). None si falla."""
    try:
        import numpy as np
        from PIL import Image
        g = np.asarray(Image.fromarray(arr[:, :, :3]).convert("L").resize((9, 8)))
        diff = g[:, 1:] > g[:, :-1]
        return sum(1 << i for i, v in enumerate(diff.flatten()) if v)
    except Exception:
        return None


def _roi_bounds(x: int | None, y: int | None) -> dict | None:
    """Región alrededor de (x,y); si no hay punto, None (se usará full-screen
    acotado, peor señal pero algo)."""
    try:
        import mss
        with mss.MSS() as sct:
            virt = sct.monitors[0]
    except Exception:
        return None
    if x is None or y is None:
        return virt
    left = max(virt["left"], x - _ROI_MARGIN)
    top = max(virt["top"], y - _ROI_MARGIN)
    return {"left": left, "top": top, "width": _ROI_MARGIN * 2, "height": _ROI_MARGIN * 2}


def _capture(roi: dict | None) -> _Cap:
    h = None
    try:
        import mss
        import numpy as np
        if roi is not None:
            with mss.MSS() as sct:
                arr = np.array(sct.grab(roi))
            h = _dhash8(arr)
    except Exception:
        h = None
    return _Cap(hash=h, fg_hwnd=_foreground_hwnd())


def capture_before(x: int | None = None, y: int | None = None) -> dict[str, Any]:
    """Llamar JUSTO ANTES de la acción GUI. Devuelve un token opaco que se pasa
    a verify_after(). No lanza."""
    if not _enabled():
        return {"_off": True}
    roi = _roi_bounds(x, y)
    cap = _capture(roi)
    return {"roi": roi, "hash": cap.hash, "fg": cap.fg_hwnd, "x": x, "y": y}


def verify_after(before: dict[str, Any]) -> dict[str, Any]:
    """Llamar JUSTO DESPUÉS de la acción. Compara contra el token de
    capture_before(). Devuelve {state_changed, signals, ...}. No lanza."""
    if not before or before.get("_off"):
        return {"state_changed": None, "reason": "gui_verify_off"}
    time.sleep(_SETTLE_S)
    roi = before.get("roi")
    after = _capture(roi)
    h_before, h_after = before.get("hash"), after.hash

    # Señal 1: frame-diff ROI
    if h_before is None or h_after is None:
        px_signal = None  # no se pudo medir
        hamming = None
    else:
        hamming = bin(h_before ^ h_after).count("1")
        px_signal = hamming >= _DHASH_HAMMING_MIN

    # Señal 2: foreground
    fg_before, fg_after = before.get("fg"), after.fg_hwnd
    fg_changed = (fg_before is not None and fg_after is not None
                  and fg_before != fg_after)
    fg_lost = (fg_before is not None and fg_after is not None
               and fg_before != fg_after)  # cambió el foreground

    # Fusión honesta:
    #  - si el ROI cambió O el foreground cambió -> algo pasó (changed=True).
    #  - si NINGUNA señal medible cambió (y al menos una se pudo medir) -> False.
    #  - si nada medible -> None (honesto: no sabemos).
    if px_signal is True or fg_changed:
        state_changed: bool | None = True
    elif px_signal is False:
        state_changed = False  # pudimos medir el pixel y NO cambió
    else:
        state_changed = None

    return {
        "state_changed": state_changed,
        "signals": {"roi_hamming": hamming, "roi_changed": px_signal,
                    "fg_changed": fg_changed},
        "reason": _reason(state_changed, px_signal, fg_changed),
    }


def _reason(state_changed, px_signal, fg_changed) -> str:
    if state_changed is True:
        bits = []
        if px_signal:
            bits.append("región de pantalla cambió")
        if fg_changed:
            bits.append("cambió la ventana en foco")
        return "; ".join(bits) or "cambio detectado"
    if state_changed is False:
        return "la región objetivo NO cambió tras la acción (posible click sin efecto)"
    return "no se pudo medir el cambio (sin pantalla/lib)"
