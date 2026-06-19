"""Detección deíctica MULTILINGÜE + entity ring.

Cuando el usuario dice "abrilo / ponelo / open it / abre isso", se refiere a algo
del turno anterior (un archivo, una URL, un id). El 4B sufre "lost in the middle":
el referente debe inyectarse LITERAL al final del prompt, junto al pronombre.

⚠️ TRAMPA EVITADA: un regex hardcoded de español (\\b(eso|esa|ábrelo|súbelo|
bórralo)\\b) VIOLA la ley de producto ("nada de listas de keywords por idioma"):
un usuario en EN/PT/FR/DE/IT no dispararía. Acá la detección es por EMBEDDINGS
multilingües: comparamos el turno contra ~12 frases deícticas de referencia en 6
idiomas; el encoder (paraphrase-multilingual-MiniLM) generaliza a 50+ idiomas.
Las frases son EJEMPLOS SEMÁNTICOS, no un whitelist. Fallback seguro: sin encoder
-> False (degrada al inherit-tools actual, nunca rompe).

El ENTITY RING (deque) guarda los últimos identificadores ÚTILES extraídos de los
tool_results (paths/urls/ids) — extracción ESTRUCTURAL (mide la FORMA, permitida),
no por idioma. En un turno deíctico se inyecta el más reciente.

GATING: GEMMA4_DEICTIC (default on; kill-switch GEMMA4_DEICTIC=0).
"""
from __future__ import annotations

import os
import re
from collections import deque
from typing import Any


def deictic_enabled() -> bool:
    # DEFAULT ON desde 2026-05-29: validado EN VIVO (3/3 idiomas es/en/pt detectan
    # el deíctico Y el referente del ring se inyecta correcto). Discriminador de 2
    # clases (recall 17/17 en 6 idiomas, 0 falsos positivos) + fallback seguro
    # (sin encoder -> False, no rompe). Inyección condicional (0 tokens si no
    # dispara). Kill-switch GEMMA4_DEICTIC=0.
    return (os.environ.get("GEMMA4_DEICTIC", "1") or "1").strip().lower() not in {
        "0", "false", "no", "off"}


# Discriminación de DOS clases por embeddings (no umbral absoluto, que solapa
# saludos con deícticos — MEDIDO 2026-05-29). Comparamos el turno contra un pool
# POSITIVO (imperativo + pronombre clítico "lo/it/le" = referencia a algo previo)
# y un pool NEGATIVO (saludos/confirmaciones/preguntas cortas que NO refieren a
# nada). Deíctico = más cerca del positivo que del negativo, con margen. Ejemplos
# SEMÁNTICOS en 6+ idiomas; el encoder multilingüe generaliza a 50+ idiomas.
_DEICTIC_POS = [
    # es — verbo imperativo + clítico
    "abrilo", "ábrelo", "ciérralo", "léelo", "reprodúcelo", "súbelo", "bórralo",
    "mándalo", "envíalo", "guárdalo", "cancélalo", "ponelo eso",
    # en
    "open it", "close it", "read it", "play it", "send it", "delete it",
    "save it", "do it with that",
    # pt
    "abre isso", "fecha isso", "manda isso", "apaga isso",
    # fr
    "ouvre-le", "ferme-le", "envoie-le", "supprime-le",
    # de
    "öffne es", "schließe es", "sende es", "lösche es",
    # it
    "aprilo", "chiudilo", "mandalo", "eliminalo",
]
_DEICTIC_NEG = [
    # saludos
    "hola", "hello", "hi", "buenas", "oi", "salut", "ciao", "hallo",
    # confirmaciones / cortesía
    "ok", "okay", "vale", "dale", "gracias", "thanks", "sí", "yes", "no",
    "perfecto", "genial", "está bien", "de nada",
    # preguntas cortas no-deícticas
    "qué hora es", "cómo estás", "what time is it", "who are you",
]

_DEICTIC_MARGIN = float(os.environ.get("GEMMA4_DEICTIC_MARGIN", "0.04"))
_MAX_DEICTIC_TOKENS = 4  # heurística agnóstica de idioma: continuación corta

_pos_emb_cache: Any = None
_neg_emb_cache: Any = None


def _embed_pool(pool, cache_name):
    g = globals()
    if g.get(cache_name) is not None:
        return g[cache_name]
    try:
        from . import semantic_router as SR
        import numpy as np
        embs = [SR.encode_text(p) for p in pool]
        embs = [e for e in embs if e is not None]
        if not embs:
            return None
        g[cache_name] = np.asarray(embs, dtype=np.float32)
        return g[cache_name]
    except Exception:
        return None


def needs_deictic_context(user_text: str) -> bool:
    """¿El turno es una referencia deíctica corta a algo previo?

    Discriminación de 2 clases por embeddings multilingües (NO regex por idioma,
    NO umbral absoluto): ¿el turno está más cerca del pool DEÍCTICO que del pool
    de SALUDOS/CONFIRMACIONES, con margen? Fallback seguro: sin encoder -> False
    (no inyecta nada, degrada al comportamiento actual)."""
    if not deictic_enabled():
        return False
    text = (user_text or "").strip()
    if not text:
        return False
    # Heurística barata primero: solo continuaciones CORTAS son deícticas.
    if len(text.split()) > _MAX_DEICTIC_TOKENS:
        return False
    try:
        from . import semantic_router as SR
        import numpy as np
        q = SR.encode_text(text)
        pos = _embed_pool(_DEICTIC_POS, "_pos_emb_cache")
        neg = _embed_pool(_DEICTIC_NEG, "_neg_emb_cache")
        if q is None or pos is None or neg is None:
            return False  # fallback seguro
        qa = np.asarray(q, dtype=np.float32)
        pos_sim = float(np.max(pos @ qa))
        neg_sim = float(np.max(neg @ qa))
        # Deíctico si está MÁS cerca del pool positivo que del negativo, con margen.
        return bool(pos_sim - neg_sim >= _DEICTIC_MARGIN)
    except Exception:
        return False


# --- Entity ring: identificadores útiles de los tool_results ----------------
# Extracción ESTRUCTURAL (FORMA, no idioma): paths Windows, URLs, y un fallback a
# un campo 'path'/'url'/'id' del result dict.
_RX_WIN_PATH = re.compile(r"[A-Za-z]:\\[^\s\"'<>|]+")
_RX_URL = re.compile(r"https?://[^\s\"'<>]+")


class EntityRing:
    """deque(maxlen=5) de (entity_type, ident, label) — el último útil primero."""

    def __init__(self, maxlen: int = 5) -> None:
        self._ring: deque[tuple[str, str, str]] = deque(maxlen=maxlen)

    def push_from_result(self, tool_name: str, result: dict[str, Any]) -> None:
        """Extrae un identificador estructural del result y lo empuja al ring.
        Best-effort: si no hay nada extraíble, no hace nada."""
        if not isinstance(result, dict):
            return
        # 1) campos estructurados explícitos del result.
        for key, etype in (("path", "path"), ("url", "url"), ("file", "path"),
                           ("image_path", "path"), ("opened", "path")):
            val = result.get(key)
            if isinstance(val, str) and val.strip():
                self._ring.appendleft((etype, val.strip(), val.strip()))
                return
        # 2) fallback: buscar una FORMA (path/url) en el blob del result.
        blob = " ".join(str(v) for v in result.values() if isinstance(v, (str, int, float)))
        m = _RX_WIN_PATH.search(blob) or _RX_URL.search(blob)
        if m:
            ident = m.group(0)
            etype = "url" if ident.lower().startswith("http") else "path"
            self._ring.appendleft((etype, ident, ident))

    def most_recent(self) -> tuple[str, str, str] | None:
        return self._ring[0] if self._ring else None

    def is_empty(self) -> bool:
        return len(self._ring) == 0

    def clear(self) -> None:
        self._ring.clear()


def deictic_context_block(ring: EntityRing) -> str:
    """Bloque corto para inyectar al final del prompt cuando el turno es deíctico
    y el ring tiene algo. ~30 tokens. '' si no hay nada."""
    ent = ring.most_recent()
    if ent is None:
        return ""
    etype, ident, _label = ent
    return (f"\n[CONTEXTO RECIENTE] El último {etype} útil fue: {ident}\n"
            f"Si el usuario se refiere a 'eso/lo/it' usá ESTE valor literal.")
