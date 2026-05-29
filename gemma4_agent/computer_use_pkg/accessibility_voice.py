"""Activación por VOZ de los modos de accesibilidad — multilingüe, por embeddings.

CLAUDE.md prohíbe regex/keywords por idioma para clasificar intención. Igual que
intent_router.py, esto compara el embedding del turno contra CENTROIDES de anclas
en varios idiomas: una clase por cada switch ("activar modo no vidente",
"activar modo manos libres", "volver a normal") MÁS una clase `none` que captura
TODO lo demás (comandos, preguntas, charla). Sólo cambiamos de modo si una clase
de switch es el argmax, supera a `none` por un margen, y cruza un piso absoluto.

Por qué la clase `none` es crítica: sin ella, "abre el editor" se clasificaría
contra las 3 clases de switch y ganaría alguna por descarte, disparando un cambio
de modo espurio. `none` es el ancla que absorbe el uso normal -> el switch solo
ocurre cuando el usuario REALMENTE lo pide.

Reusa el encoder multilingüe ya cargado (semantic_router) — sin carga extra.
Fallback seguro: si el encoder no está, NO se cambia de modo (None) — nunca
adivinamos un switch con el router degradado.

API pública:
    detect_mode_switch(text) -> str | None   # nombre del modo a activar, o None
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from . import accessibility as _a11y


# Anclas por clase, en varios idiomas. El usuario PIDE explícitamente cambiar de
# modo; estas frases cubren las formas naturales de pedirlo. El encoder
# multilingüe generaliza al resto. NO son keywords a matchear — son ejemplos
# cuyo CENTROIDE (media) es el punto de comparación.
_ANCHORS: dict[str, list[str]] = {
    "no_vidente": [
        # español
        "activá el modo para personas no videntes",
        "poné el modo para ciegos", "modo para invidentes",
        "no puedo ver la pantalla, leémela", "soy ciego, narrame todo en voz",
        "describime todo lo que pasa porque no veo",
        "activa el lector de pantalla por voz",
        # inglés
        "turn on the mode for blind users", "enable screen reader voice mode",
        "i can't see the screen, read everything aloud",
        "i am blind, narrate everything to me",
        # pt / fr / de / it
        "ativar o modo para cegos", "active le mode pour aveugles",
        "aktiviere den modus fur blinde", "attiva la modalita per non vedenti",
        "non riesco a vedere lo schermo leggimelo",
        "sono cieco descrivimi tutto a voce",
    ],
    "movilidad": [
        # español
        "activá el modo manos libres", "modo para movilidad reducida",
        "no puedo usar las manos, controlá todo por voz",
        "no puedo mover los brazos, hacelo vos por mí",
        "modo para personas que no pueden usar teclado ni mouse",
        "controla la computadora por voz por mí",
        # inglés
        "turn on hands free mode", "enable mode for limited mobility",
        "i can't use my hands, control everything by voice",
        "i can't move my arms, do it all for me by voice",
        # pt / fr / de / it
        "ativar o modo maos livres", "active le mode mains libres",
        "aktiviere den freihandmodus", "attiva la modalita a mani libere",
    ],
    "normal": [
        # español
        "volvé al modo normal", "desactivá el modo de accesibilidad",
        "salí del modo para ciegos", "quitá el modo manos libres",
        "volvé a como estaba antes", "modo normal de nuevo",
        # inglés
        "go back to normal mode", "turn off accessibility mode",
        "disable the blind mode", "exit hands free mode",
        # pt / fr / de / it
        "voltar ao modo normal", "revenir au mode normal",
        "zuruck zum normalen modus", "torna alla modalita normale",
    ],
    # Clase basurero: TODO lo que NO es un pedido de cambiar de modo. Comandos,
    # preguntas, charla. Es la que debe ganar en el uso cotidiano -> sin esto,
    # el switch dispararía espuriamente.
    "none": [
        # comandos PC
        "abre el navegador", "pon música", "mandá un mensaje a juan",
        "cerrá la ventana", "sacá una captura", "open spotify",
        "play some music", "send a message", "close the window",
        # preguntas
        "qué es python", "quién ganó el mundial", "what time is it",
        "cuánto es dos más dos", "explicame la fotosintesis",
        # charla
        "hola", "gracias", "dale", "ok", "cómo estás", "thank you", "hello",
        # pedidos de acción genéricos que NO son sobre el modo
        "ayudame con esto", "hacé una búsqueda", "abrime el editor de texto",
    ],
}

# El switch debe GANARLE a `none` por este margen (coseno). Tuneado conservador:
# preferimos NO cambiar de modo ante la duda (un cambio espurio es molesto y
# desorienta a un usuario con discapacidad). Subir = más estricto.
_SWITCH_MARGIN = float(os.environ.get("GEMMA4_A11Y_SWITCH_MARGIN", "0.08"))
# Piso absoluto que la clase ganadora debe cruzar además de ser argmax. Evita
# que un turno ambiguo de baja señal active un modo.
_SWITCH_FLOOR = float(os.environ.get("GEMMA4_A11Y_SWITCH_FLOOR", "0.30"))


@dataclass
class _Centroids:
    by_class: dict[str, Any]
    ready: bool = False


_C = _Centroids(by_class={})


def _ensure_centroids() -> bool:
    if _C.ready:
        return bool(_C.by_class)
    try:
        from .. import semantic_router as sr
        if not sr._ensure_loaded():
            _C.ready = True
            return False
        import numpy as np
        model = sr._STATE.model

        def _centroid(anchors: list[str]) -> Any:
            e = model.encode(anchors, normalize_embeddings=True).mean(0)
            return np.asarray(e / (np.linalg.norm(e) or 1.0), dtype="float32")

        _C.by_class = {cls: _centroid(anchors) for cls, anchors in _ANCHORS.items()}
        _C.ready = True
        return True
    except Exception:
        _C.ready = True
        _C.by_class = {}
        return False


def detect_mode_switch(text: str) -> str | None:
    """Devuelve el nombre del modo a activar si el turno PIDE un cambio de modo
    de accesibilidad, o None si no (uso normal, o router degradado).

    Decisión 100% semántica (sin keywords): una clase de switch (no_vidente /
    movilidad / normal) debe ser el argmax sobre TODAS las clases (incluida
    `none`), superar a `none` por _SWITCH_MARGIN y cruzar _SWITCH_FLOOR. Si el
    encoder no cargó, devuelve None (nunca adivinamos un switch a ciegas).
    """
    if not text or not text.strip():
        return None
    if not _ensure_centroids() or not _C.by_class:
        return None
    try:
        from .. import semantic_router as sr
        import numpy as np
        qe = sr.embed(text)
        if qe is None:
            qe = sr._STATE.model.encode([text], normalize_embeddings=True)[0]
        qe = np.asarray(qe, dtype="float32")
        scores = {cls: float(qe @ cen) for cls, cen in _C.by_class.items()}
    except Exception:
        return None

    none_score = scores.get("none", 0.0)
    # argmax sobre las clases de SWITCH (sin contar none)
    switch_scores = {c: s for c, s in scores.items() if c != "none"}
    if not switch_scores:
        return None
    best_cls = max(switch_scores, key=lambda c: switch_scores[c])
    best = switch_scores[best_cls]
    # Debe ser el argmax GLOBAL (ganarle a none), cruzar el piso, y el margen.
    if best < _SWITCH_FLOOR:
        return None
    if (best - none_score) < _SWITCH_MARGIN:
        return None
    return best_cls


def maybe_switch_mode(text: str) -> _a11y.AccessibilityMode | None:
    """Si el turno pide un cambio de modo, lo aplica (persiste) y devuelve el
    nuevo modo. Si no, devuelve None y no toca nada. No-op si ya está en ese
    modo (evita reescribir el archivo y re-confirmar)."""
    target = detect_mode_switch(text)
    if target is None:
        return None
    current = _a11y.get_active_mode().name
    if target == current:
        return None
    try:
        return _a11y.set_active_mode(target)
    except ValueError:
        return None
