"""Splitter determinista de comandos multi-intent (investigación 7, 2026-05-23).

"abrí Spotify y bajá el volumen" son DOS acciones. Un 4B causal colapsa el
multi-intent (MIDLM, COLING 2025: la atención causal no maneja multi-intent como
un 7B bidireccional). La cura NO es agrandar el modelo: es partir el enunciado en
cláusulas con REGEX (28000× más rápido que un LLM) ANTES de que el LLM lo vea, y
rutear cada cláusula como su propio turno.

Conservador a propósito (Park et al. arXiv:2108.01812: no "arreglar" lo que no
está roto). Solo parte en " y/e/o <VERBO-IMPERATIVO>" o ";" — un "y" entre
sustantivos ("sal y pimienta", "Tom y Jerry") NO parte. Cabe en vram4 (regex).
"""
from __future__ import annotations

import re

# Verbos imperativos (es rioplatense/voseo + estándar) que indican una acción
# nueva tras un conector. Si el "y" va seguido de uno de estos, es multi-intent.
# Formas con clítico (abrilo, ponelo...) van PRIMERO en la alternación para que
# matcheen antes que su raíz; SIN \b al final (el clítico rompe el límite, p.ej.
# "abrilo" no tiene \b tras "abri").
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

# Parte en: ", y/e/o <verbo>" | "; <verbo>" | " y/e/o <verbo>" | " y después/luego <verbo>"
# El lookahead usa (?=...) seguido de [a-záéíóú]* para tolerar clíticos sin \b.
_SPLIT_RE = re.compile(
    r"\s*(?:"
    r";\s+(?=(?:" + _IMPERATIVE + r"))"
    r"|,?\s+(?:y|e|o)\s+(?:despu[ée]s\s+|luego\s+|tambi[ée]n\s+)?(?=(?:" + _IMPERATIVE + r"))"
    r"|\s+(?:despu[ée]s|luego)\s+(?=(?:" + _IMPERATIVE + r"))"
    r")",
    re.IGNORECASE,
)

# Clitico/anáfora que indica que la cláusula DEPENDE del resultado de la anterior
# ("buscá un Word y abrilo" -> "abrilo" refiere al Word).
_DEP_RE = re.compile(
    r"\b(?:lo|la|los|las|le|les|eso|ese|esa|aquel)\b"
    r"|(?:abril[oa]|cerral[oa]|ci[ée]rral[oa]|cierral[oa]|mostral[oa]|"
    r"mu[ée]stral[oa]|reprodu[cz]il[oa]|ponel[oa]|m[áa]ndalo|mandalo|"
    r"le[ée]lo|leel[oa]|p[áa]usal[oa]|pausal[oa])",
    re.IGNORECASE,
)

MAX_CLAUSES = 3  # cap conservador (inv 7): si parte en más, probablemente es ruido


def split_command(utterance: str) -> list[str]:
    """Parte un enunciado en cláusulas de acción. Devuelve [utterance] si no hay
    multi-intent claro (caso normal). Nunca lanza."""
    if not utterance or not utterance.strip():
        return [utterance]
    parts = [p.strip(" ,.;") for p in _SPLIT_RE.split(utterance) if p and p.strip(" ,.;")]
    if len(parts) <= 1:
        return [utterance]
    # cap: si partió en demasiadas, no confiamos -> tratar como un solo comando
    if len(parts) > MAX_CLAUSES:
        return [utterance]
    return parts


def has_back_reference(clause: str) -> bool:
    """True si la cláusula tiene un clítico/deíctico que refiere a algo previo."""
    return bool(_DEP_RE.search(clause))


def plan_clauses(utterance: str) -> list[dict]:
    """Devuelve [{text, depends_on_prev}] por cláusula. depends_on_prev=True =>
    ejecutar serializado (el resultado de la anterior alimenta esta)."""
    clauses = split_command(utterance)
    return [{"text": c, "depends_on_prev": i > 0 and has_back_reference(c)}
            for i, c in enumerate(clauses)]
