"""Splitter de comandos multi-intent — MULTILINGÜE (investigación 7, 2026-05-23).

"abrí Spotify y bajá el volumen" son DOS acciones. Un 4B causal colapsa el
multi-intent (MIDLM, COLING 2025: la atención causal no maneja multi-intent como
un 7B bidireccional). La cura NO es agrandar el modelo: es partir el enunciado en
cláusulas ANTES de que el LLM lo vea y rutear cada una como su propio turno.

UNIVERSAL (CLAUDE.md: la app la usa cualquier hablante; nada de regex es-only):
  - Capa 1 (rápida, español): regex de verbos imperativos. Atajo barato exacto.
  - Capa 2 (multilingüe): si la capa 1 no parte, intentar partir en una
    CONJUNCIÓN de cualquier idioma (y/and/e/und/et/o/or/oder...) y CONFIRMAR por
    EMBEDDINGS que lo que sigue es una ACCIÓN (no un sustantivo). Así
    "open Spotify and turn down the volume" parte, pero "Tom and Jerry" /
    "salt and pepper" / "music by the Beatles" NO (la parte tras la conjunción
    puntúa como sintagma nominal, no como acción). Mismo encoder multilingüe del
    router. Cabe en vram4 (un encode MiniLM ~<30ms, sólo si hay conjunción).

FALLBACK SEGURO: si el encoder no está, la capa 2 se apaga (sólo capa 1 español);
un multi-intent no detectado degrada ELEGANTEMENTE (el LLM ve el comando entero,
status quo). Conservador (Park et al. arXiv:2108.01812: no romper lo que anda).
"""
from __future__ import annotations

import os
import re

# Verbos imperativos español (es rioplatense/voseo + estándar) — CAPA 1 rápida.
# Formas con clítico (abrilo, ponelo...) van PRIMERO; SIN \b al final.
_IMPERATIVE = (
    r"abril[oa]|cerral[oa]|mostral[oa]|reprodu[cz]il[oa]|ponel[oa]|m[áa]ndalo|"
    r"mandalo|le[ée]lo|"
    r"abr[ií]|abrime|cerr[áa]|cierra|cerrame|ponel[ea]|pon[eé]|pon|ponme|"
    r"baj[áa]|baja|sub[íi]|sube|mand[áa]|manda|mandale|m[áa]ndale|"
    r"busc[áa]|busca|buscame|and[áa]|anda|reproduc[íie]|reproduce|"
    r"mut[eé]a?|silenci[áa]|mostr[áa]|muestra|mostrame|empez[áa]|empieza|"
    r"par[áa]|para|pausa|paus[áa]|reanud[áa]|reanuda|llam[áa]|llama|"
    r"escrib[íi]|escribe|crea|cre[áa]|apag[áa]|apaga|prend[ée]|prende|"
    r"enciend[ee]|cancel[áa]|cancela|borr[áa]|borra|elimin[áa]|elimina"
)

_SPLIT_RE = re.compile(
    r"\s*(?:"
    r";\s+(?=(?:" + _IMPERATIVE + r"))"
    r"|,?\s+(?:y|e|o)\s+(?:despu[ée]s\s+|luego\s+|tambi[ée]n\s+)?(?=(?:" + _IMPERATIVE + r"))"
    r"|\s+(?:despu[ée]s|luego)\s+(?=(?:" + _IMPERATIVE + r"))"
    r")",
    re.IGNORECASE,
)

# CAPA 2: conjunciones coordinantes multi-idioma (closed set, language-agnostic).
# Sólo conjunción entre espacios (no "Disney" partido). El "?" de "después/luego"
# español ya lo cubre la capa 1; acá conectores neutrales de varios idiomas.
# OJO: NO incluir "o" suelta — es artículo en portugués ("abre o Spotify") y
# disparaba splits espurios. Para disyunción usamos las formas largas
# (or/oder/ou/oppure). "e"/"y" sí ("and" en es/pt/it, rara vez artículo).
_CONJUNCTION_RE = re.compile(
    r"\s+(?:y|e|and|then|or|ou|et|puis|und|dann|oder|poi|oppure)\s+"
    r"(?:then\s+|after\s+that\s+|afterwards\s+|depois\s+|ensuite\s+|danach\s+)?",
    re.IGNORECASE,
)

# Clítico/anáfora español que indica dependencia de la cláusula previa. CAPA 1.
_DEP_RE = re.compile(
    r"\b(?:lo|la|los|las|le|les|eso|ese|esa|aquel)\b"
    r"|(?:abril[oa]|cerral[oa]|ci[ée]rral[oa]|cierral[oa]|mostral[oa]|"
    r"mu[ée]stral[oa]|reprodu[cz]il[oa]|ponel[oa]|m[áa]ndalo|mandalo|"
    r"le[ée]lo|leel[oa]|p[áa]usal[oa]|pausal[oa])",
    re.IGNORECASE,
)

MAX_CLAUSES = 3  # cap conservador (inv 7): si parte en más, probablemente ruido

# Margen mínimo (action - noun) para tratar una cláusula como ACCIÓN (medido:
# acciones multi-idioma ~+0.24..+0.51, sintagmas nominales ~-0.24..-0.33).
_ACTION_MARGIN = float(os.environ.get("GEMMA4_SPLIT_ACTION_MARGIN", "0.05"))

_ACTION_ANCHORS = [
    "bajá el volumen", "abrí la calculadora", "poné música", "cerrá la ventana",
    "turn down the volume", "open the calculator", "play music", "close the window",
    "baixa o volume", "abre a calculadora", "mach das leiser", "öffne den rechner",
    "monte le son", "ouvre la calculatrice", "abbassa il volume", "apri la calcolatrice",
]
_NOUN_ANCHORS = [
    "sal y pimienta", "Tom y Jerry", "la lista de compras", "una banda llamada Queen",
    "salt and pepper", "the shopping list", "music by the Beatles", "a band called Queen",
    "sel et poivre", "Salz und Pfeffer", "sale e pepe", "uma lista de compras",
]


class _ActionCentroids:
    __slots__ = ("ready", "action", "noun")

    def __init__(self) -> None:
        self.ready = False
        self.action = None
        self.noun = None


_AC = _ActionCentroids()


def _ensure_action_centroids() -> bool:
    if _AC.ready:
        return _AC.action is not None
    try:
        from . import semantic_router as sr
        if not sr._ensure_loaded():
            _AC.ready = True
            return False
        import numpy as np
        model = sr._STATE.model

        def _centroid(anchors):
            e = model.encode(anchors, normalize_embeddings=True).mean(0)
            return np.asarray(e / (np.linalg.norm(e) or 1.0), dtype="float32")

        _AC.action = _centroid(_ACTION_ANCHORS)
        _AC.noun = _centroid(_NOUN_ANCHORS)
        _AC.ready = True
        return True
    except Exception:
        _AC.ready = True
        return False


def _is_action_clause(clause: str) -> bool:
    """True si la cláusula puntúa como ACCIÓN (no sintagma nominal), por
    embeddings multilingües. False si no hay encoder (capa 2 se apaga)."""
    if not _ensure_action_centroids() or _AC.action is None:
        return False
    try:
        from . import semantic_router as sr
        import numpy as np
        q = sr.embed(clause)
        if q is None:
            q = sr._STATE.model.encode([clause], normalize_embeddings=True)[0]
        q = np.asarray(q, dtype="float32")
        return float(q @ _AC.action) - float(q @ _AC.noun) >= _ACTION_MARGIN
    except Exception:
        return False


def _semantic_enabled() -> bool:
    raw = (os.environ.get("GEMMA4_SPLIT_MULTILANG") or "").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _split_multilingual(utterance: str) -> list[str]:
    """CAPA 2: parte en una conjunción multi-idioma SOLO si ambas partes
    puntúan como acción. Devuelve [utterance] si no hay split confiable."""
    if not _semantic_enabled():
        return [utterance]
    # candidatos de split: cada ocurrencia de una conjunción.
    matches = list(_CONJUNCTION_RE.finditer(utterance))
    if not matches:
        return [utterance]
    # Demasiadas conjunciones = probablemente ruido / lista; no confiar (cap).
    if len(matches) >= MAX_CLAUSES:
        return [utterance]
    # probar el PRIMER punto de conjunción que produzca dos cláusulas-acción.
    for mt in matches:
        left = utterance[:mt.start()].strip(" ,.;")
        right = utterance[mt.end():].strip(" ,.;")
        if len(left.split()) < 2 or len(right.split()) < 1:
            continue
        # ambas partes deben ser acción (la derecha es la clave: "Jerry" no lo es)
        if _is_action_clause(left) and _is_action_clause(right):
            # recursar sobre la derecha por si hay 3 acciones, respetando el cap
            rest = _split_multilingual(right)
            parts = [left, *rest]
            if len(parts) <= MAX_CLAUSES:
                return parts
            return [utterance]
    return [utterance]


def split_command(utterance: str) -> list[str]:
    """Parte un enunciado en cláusulas de acción. Devuelve [utterance] si no hay
    multi-intent claro (caso normal). Nunca lanza.

    Capa 1 (español, rápida) primero; si no parte, capa 2 (multilingüe semántica)."""
    if not utterance or not utterance.strip():
        return [utterance]
    # CAPA 1: regex español (exacta, barata, ya validada).
    parts = [p.strip(" ,.;") for p in _SPLIT_RE.split(utterance) if p and p.strip(" ,.;")]
    if len(parts) > 1:
        if len(parts) > MAX_CLAUSES:
            return [utterance]
        return parts
    # CAPA 2: multilingüe (solo si capa 1 no partió).
    return _split_multilingual(utterance)


def has_back_reference(clause: str) -> bool:
    """True si la cláusula tiene un clítico/deíctico que refiere a algo previo."""
    return bool(_DEP_RE.search(clause))


def plan_clauses(utterance: str) -> list[dict]:
    """Devuelve [{text, depends_on_prev}] por cláusula. depends_on_prev=True =>
    ejecutar serializado (el resultado de la anterior alimenta esta)."""
    clauses = split_command(utterance)
    return [{"text": c, "depends_on_prev": i > 0 and has_back_reference(c)}
            for i, c in enumerate(clauses)]
