"""Router de contexto multi-turno (investigación 4, punto 1) — MULTILINGÜE.

La mayoría de los comandos de voz son ATÓMICOS ("qué hora es", "abrí Spotify"):
el historial previo no aporta y sólo infla el tail del prompt (que SIEMPRE se
reprocesa; medido: el prefix-cache de b9090 SÍ funciona para Gemma 4 E4B, pero
el tail variable no se cachea). El historial sólo importa cuando el turno tiene
anáfora/deixis ("ábrelo", "open it", "abre isso", "mach das auf") o es una
continuación/corrección corta ("sí", "yes", "no, better at 11").

PRINCIPIO UNIVERSAL (CLAUDE.md): la app la usa cualquier hablante, en cualquier
idioma. Por eso la deixis NO se detecta con regex en español (rompería a un
angloparlante: "open it" no matchearía y se le droparía el historial, perdiendo
el referente). Se detecta por SIMILITUD SEMÁNTICA contra anclas multi-idioma,
con el MISMO encoder multilingüe del router (paraphrase-multilingual-MiniLM-L12-v2,
50+ idiomas). El regex queda SÓLO como atajo aditivo barato (si matchea, refuerza
'depende'), nunca como única fuente ni para idiomas que no cubre.

FALLBACK SEGURO: ante CUALQUIER duda — encoder no cargado, score ambiguo, texto
vacío — devolvemos el historial (FULL/LIGHT). NUNCA droppeamos por defecto. El
único caso de drop (none) es alta confianza de que el turno es autocontenido.

Modos:
  - none : autocontenido con alta confianza -> SYSTEM + turno actual.
  - light: deíctico/continuación/corto -> SYSTEM + cola corta reciente.
  - full : ambiguo / sin encoder / turno largo -> historial completo (status quo).

Cabe en vram4 (un encode MiniLM ~<30ms CPU, LRU-cacheado por turno).
"""
from __future__ import annotations

import os
import re

MODE_NONE = "none"
MODE_LIGHT = "light"
MODE_FULL = "full"

LIGHT_TAIL_MESSAGES = 4

# --- Anclas MULTI-IDIOMA de "este turno DEPENDE del anterior" --------------
# Anáfora/deixis + continuación + corrección/reformulación, en varios idiomas.
# El encoder generaliza a idiomas/frases no listados (es lo que lo hace
# universal, a diferencia de una lista de keywords).
_DEPENDENT_ANCHORS = [
    # español
    "ábrelo", "ciérralo", "súbelo un poco", "ponelo en pausa", "mostrámelo",
    "sí, dale", "no, mejor a las once", "en vez de eso poné otra",
    "ese", "el otro", "cambialo", "el segundo", "la verde",
    # inglés
    "open it", "close it", "turn it up", "pause it", "show me that one",
    "yes, do it", "no, better at eleven", "the other one", "change it",
    "the second one", "that one",
    # portugués
    "abre isso", "fecha isso", "aumenta", "esse", "o outro", "muda isso",
    # francés
    "ouvre-le", "ferme-le", "celui-là", "l'autre", "change ça",
    # alemán
    "mach das auf", "schließ das", "das andere", " änder das",
    # italiano
    "aprilo", "chiudilo", "quell'altro", "cambialo",
]

# --- Anclas MULTI-IDIOMA de "turno AUTOCONTENIDO" (nuevo comando/pregunta) --
_SELF_CONTAINED_ANCHORS = [
    # español
    "qué hora es", "abrí Spotify", "poné música de los Beatles",
    "subí el volumen al treinta", "cuánto falta para las tres", "abre Chrome",
    # inglés
    "what time is it", "open Spotify", "play music by the Beatles",
    "set the volume to thirty", "open Chrome", "what's the weather",
    # portugués
    "que horas são", "abre o Spotify", "toca música dos Beatles",
    # francés
    "quelle heure est-il", "ouvre Spotify", "mets de la musique",
    # alemán
    "wie spät ist es", "öffne Spotify", "spiel Musik",
    # italiano
    "che ore sono", "apri Spotify", "metti la musica",
]

# Margen mínimo (dependent - self_contained) para CONFIAR en que es
# autocontenido y droppear historial. Conservador: si el margen a favor de
# 'autocontenido' no es claro, NO droppeamos (full/light). Calibrable.
_SELF_CONTAINED_MARGIN = 0.06
# Si 'dependent' gana por este margen -> light (mandar cola corta).
_DEPENDENT_MARGIN = 0.02

# --- Atajo regex ADITIVO (no autoritativo) ---------------------------------
# Sólo refuerza 'depende' cuando matchea; su ausencia NO implica autocontenido
# (eso lo decide el encoder, que es multilingüe). Clíticos enclíticos español +
# demostrativos; barato, primer filtro.
_REGEX_DEPENDENT_HINT = re.compile(
    r"(?:[a-záéíóúñ]+(?:l[oa]s?|[mt]el[oa]s?|sel[oa]s?))\b"
    r"|\b(?:eso|esa|ese|esto|esta|este|aquello|aquel|aquella|"
    r"el\s+otro|la\s+otra|el\s+mismo|el\s+anterior)\b"
    r"|^\s*(?:s[ií]|no|dale|vale|ok|okay|yes|yeah|nope|oui|non|ja|nein|sim|não)\b",
    re.IGNORECASE,
)


def _enabled() -> bool:
    raw = (os.environ.get("GEMMA4_CONTEXT_ROUTER") or "").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _cold_load_enabled() -> bool:
    raw = (
        os.environ.get("GEMMA4_CONTEXT_COLD_LOAD")
        or os.environ.get("GEMMA4_SEMANTIC_COLD_LOAD")
        or "0"
    ).strip().casefold()
    return raw in {"1", "true", "yes", "on"}


def _semantic_ready(sr) -> bool:
    try:
        return bool(sr.status().get("model_loaded")) or _cold_load_enabled()
    except Exception:
        return _cold_load_enabled()


class _Centroids:
    __slots__ = ("ready", "dependent", "self_contained")

    def __init__(self) -> None:
        self.ready = False
        self.dependent = None
        self.self_contained = None


_C = _Centroids()


def _ensure_centroids() -> bool:
    """Construye los centroides multilingües una vez. Reusa el encoder del
    semantic_router (mismo modelo, LRU-cacheado). False si no hay encoder."""
    if _C.ready:
        return _C.dependent is not None
    try:
        from . import semantic_router as sr
        if not _semantic_ready(sr):
            return False
        if not sr._ensure_loaded():
            _C.ready = True
            return False
        import numpy as np
        model = sr._STATE.model

        def _centroid(anchors: list[str]):
            e = model.encode(anchors, normalize_embeddings=True).mean(0)
            return np.asarray(e / (np.linalg.norm(e) or 1.0), dtype="float32")

        _C.dependent = _centroid(_DEPENDENT_ANCHORS)
        _C.self_contained = _centroid(_SELF_CONTAINED_ANCHORS)
        _C.ready = True
        return True
    except Exception:
        _C.ready = True
        return False


def _semantic_mode(txt: str) -> str | None:
    """Decide por embeddings multilingües. None si no hay encoder (-> fallback)."""
    if not _ensure_centroids() or _C.dependent is None:
        return None
    try:
        from . import semantic_router as sr
        import numpy as np
        qe = sr.embed(txt)
        if qe is None:
            qe = sr._STATE.model.encode([txt], normalize_embeddings=True)[0]
        qe = np.asarray(qe, dtype="float32")
        dep = float(qe @ _C.dependent)
        sc = float(qe @ _C.self_contained)
        if dep - sc >= _DEPENDENT_MARGIN:
            return MODE_LIGHT          # depende del previo -> cola corta
        if sc - dep >= _SELF_CONTAINED_MARGIN:
            return MODE_NONE           # autocontenido con confianza -> sin historial
        return MODE_FULL               # ambiguo -> seguro, historial completo
    except Exception:
        return None


def needs_history(user_text: str, *, has_history: bool,
                  has_open_toolcall: bool = False) -> str:
    """Decide cuánto historial mandar. Multilingüe (encoder) + fallback seguro.

    Returns 'none' | 'light' | 'full'. Default seguro = 'full' (nunca droppea
    ante la duda: no romper anáfora de NINGÚN idioma)."""
    if not _enabled() or not has_history:
        return MODE_FULL if has_history else MODE_NONE
    if has_open_toolcall:
        return MODE_FULL  # cadena de tools en curso: el contexto importa
    txt = (user_text or "").strip()
    if not txt:
        return MODE_FULL

    # 1) Atajo regex ADITIVO: si matchea un hint de dependencia, es light. Su
    #    AUSENCIA no decide nada (el encoder, multilingüe, manda).
    if _REGEX_DEPENDENT_HINT.search(txt):
        return MODE_LIGHT

    # 2) Decisión semántica multilingüe.
    sem = _semantic_mode(txt)
    if sem is not None:
        # Turno largo: aunque el encoder diga autocontenido, ante un dictado
        # largo preferimos conservar contexto (puede continuar algo). Cota suave.
        if sem == MODE_NONE and len(txt.split()) > 30:
            return MODE_FULL
        return sem

    # 3) FALLBACK SEGURO: sin encoder -> historial completo. NUNCA droppear a
    #    ciegas (romper a un hablante de un idioma sin regex es peor que perder
    #    la optimización de latencia).
    return MODE_FULL


def select_history(history: list, mode: str) -> list:
    """Devuelve la porción de historial a enviar según el modo. Pura."""
    if mode == MODE_NONE:
        return []
    if mode == MODE_LIGHT:
        return history[-LIGHT_TAIL_MESSAGES:]
    return history
