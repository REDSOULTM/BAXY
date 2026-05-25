"""Computer-use OPCIÓN B — clasificador verbo->primitiva por EMBEDDINGS (para comparar
con la Opción A, el ejecutor de planes). Diseño: NO le pide un plan al 4B; clasifica
el OBJETIVO a UNA primitiva por similitud de embeddings multilingües (anclas), extrae
el argumento, ejecuta+verifica. Universal por idioma (embeddings, no regex es-only),
pero LIMITADO: una sola primitiva por comando (no compone multi-paso focus+open+type+
send). Sirve para medir el trade-off contra A.

Reusa el encoder del router (paraphrase-multilingual-MiniLM) y las MISMAS primitivas
atómicas del PlanExecutor (no duplica ejecución)."""
from __future__ import annotations

import re
import time
from typing import Any

# Anclas semánticas por primitiva, multi-idioma (NO listas exhaustivas: ejemplos
# que definen el CENTROIDE de cada acción; el embedding generaliza a otros fraseos).
_ANCHORS = {
    "open_url": [
        "andá a esta página web", "abrí esta url en el navegador", "entrá a este sitio",
        "go to this website", "open this url in the browser", "navigate to this page",
    ],
    "open_chat": [
        "abrí el chat de esta persona", "andá a la conversación con este contacto",
        "entrá al canal", "open the chat with this contact", "go to this channel",
    ],
    "type": [
        "escribí este texto", "tecleá esto", "poné este texto",
        "type this text", "write this", "enter this text",
    ],
    "click": [
        "clickeá este botón", "apretá este control", "tocá esta opción",
        "click this button", "press this control", "select this option",
    ],
    "keypress": [
        "apretá esta tecla", "presioná enter", "mandá un atajo de teclado",
        "press this key", "hit enter", "send a keyboard shortcut",
    ],
}

_centroids: dict[str, Any] | None = None


def _ensure_centroids() -> bool:
    global _centroids
    if _centroids is not None:
        return _centroids is not False
    try:
        from .semantic_router import embed
        import numpy as np
        cents = {}
        for prim, examples in _ANCHORS.items():
            vs = [embed(e) for e in examples]
            vs = [v for v in vs if v is not None]
            if not vs:
                _centroids = False
                return False
            cents[prim] = np.mean(np.array(vs), axis=0)
        _centroids = cents
        return True
    except Exception:
        _centroids = False
        return False


def classify_primitive(goal: str) -> tuple[str, float] | None:
    """Clasifica el objetivo a UNA primitiva por embeddings. Devuelve (primitiva,
    score) o None si no hay encoder. Fallback seguro: el caller decide el umbral."""
    if not _ensure_centroids():
        return None
    try:
        from .semantic_router import embed
        import numpy as np
        v = embed(goal)
        if v is None:
            return None
        v = np.array(v)
        best, bs = None, -1.0
        for prim, c in _centroids.items():  # type: ignore[union-attr]
            s = float(np.dot(v, c) / ((np.linalg.norm(v) * np.linalg.norm(c)) + 1e-9))
            if s > bs:
                best, bs = prim, s
        return (best, bs) if best else None
    except Exception:
        return None


# extracción de argumento por primitiva (reusa los extractores del splitter).
def extract_arg(prim: str, goal: str, app_hint: str = "") -> str:
    from .command_splitter import (extract_nav_target, extract_write_payload,
                                    extract_click_target)
    if prim == "open_chat":
        return extract_nav_target(goal, app_hint=app_hint) or ""
    if prim == "type":
        return extract_write_payload(goal) or ""
    if prim == "click":
        return extract_click_target(goal) or ""
    if prim == "open_url":
        m = re.search(r"([a-z0-9-]+\.[a-z]{2,}(?:/\S*)?)", goal, re.IGNORECASE)
        return m.group(1) if m else ""
    if prim == "keypress":
        m = re.search(r"\b(enter|escape|tab|ctrl\+\w|alt\+\w+|f\d{1,2})\b", goal, re.IGNORECASE)
        return m.group(1) if m else "enter"
    return ""


def run_single_primitive(agent: Any, goal: str, score_min: float = 0.30) -> dict | None:
    """OPCIÓN B: clasifica a UNA primitiva, extrae arg, ejecuta vía el PlanExecutor
    (1 paso). Antepone focus_app si hay una app abierta mencionada (lo mínimo para
    que la primitiva opere en la app correcta). None si no clasifica con confianza."""
    cl = classify_primitive(goal)
    if cl is None or cl[1] < score_min:
        return None
    prim, score = cl
    win = agent._window_title_in_text(goal) or ""
    arg = extract_arg(prim, goal, app_hint=win)
    if prim in ("open_chat", "type", "click", "open_url") and not arg:
        return None
    from .computer_use import PlanExecutor
    ex = PlanExecutor(agent)
    plan = []
    if win:
        plan.append({"op": "focus_app", "arg": win.split(" - ")[-1] or win})
    plan.append({"op": prim, "arg": arg})
    res = ex.execute(plan, "cub")
    res["primitive"] = prim
    res["score"] = round(score, 3)
    return res
