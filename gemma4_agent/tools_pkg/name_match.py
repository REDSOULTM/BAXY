"""Matching difuso de nombres (fold + score), extraído de tools.py (split del
archivo-dios, 2026-06-19). `_fold` normaliza (casefold + sin acentos + solo
alfanumérico); `_score` puntúa la similitud query<->candidato para resolver apps
/ juegos por nombre. Puro, solo stdlib; sin dependencias del paquete, así que no
cicla con tools.py (que lo re-exporta para sus métodos y para app_resolver).
"""
from __future__ import annotations

import re
import unicodedata


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.casefold())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


# Connective words that must NOT count as a meaningful name overlap (else
# "League of Legends" ~ "Sea of Thieves" via "of"). ES + EN.
_APP_NAME_STOPWORDS = frozenset({
    "of", "the", "a", "an", "and", "in", "on", "for", "to",
    "de", "del", "la", "el", "los", "las", "y", "e", "en", "un", "una",
})


def _score(query: str, candidate: str) -> int:
    q = _fold(query)
    c = _fold(candidate)
    if not q or not c:
        return 0
    if q == c:
        return 100
    if c.startswith(q):
        return 90
    # QUERY empieza con CANDIDATO ("calculadora" -> exe "calc"): nombre largo vs
    # nombre corto del .exe, misma app. Candidato >=4 chars y query de 1 palabra
    # (evita "ch"->chrome y "hola mundo..."->app espuria).
    if len(c) >= 4 and " " not in q and q.startswith(c):
        return 88
    if q in c:
        return 75
    q_words = set(q.split())
    c_words = set(c.split())
    if not q_words:
        return 0
    # Exclude stopwords from the "meaningful overlap" count.
    # "League of Legends" vs "Sea of Thieves" shared only "of" and scored 50,
    # so "Call of Duty" could resolve to "God of War" when the real game
    # isn't installed. A shared connective word is not a real app match.
    overlap_words = (q_words & c_words) - _APP_NAME_STOPWORDS
    overlap = len(overlap_words)
    if overlap:
        # Normalize against the query's CONTENT words (non-stopwords), so a
        # 1-of-1 content match still scores high.
        q_content = q_words - _APP_NAME_STOPWORDS
        denom = len(q_content) or len(q_words)
        return 40 + int(30 * overlap / denom)
    # Fuzzy fallback: el usuario puede haber dictado mal por voz
    # ("Saint Rose" en vez de "Saints Row") o con typos. Usamos difflib
    # SequenceMatcher.ratio() sobre la frase completa Y sobre cada par
    # de words. Si alguna coincidencia parcial supera el umbral, devolvemos
    # un score bajo pero positivo para que el candidato no se descarte.
    import difflib
    full_ratio = difflib.SequenceMatcher(None, q, c).ratio()
    # First-character guard. Short near-anagrams ("teams" vs
    # "steam", ratio ~0.8) were fuzzy-matching and "abre Teams" opened Steam.
    # A real typo almost always keeps the first letter ("spotfy"->"spotify",
    # "calculadra"->"calculadora"); a different first letter on a short query
    # is a different word. Only gate the SHORT single-token case so multi-word
    # / longer queries keep their fuzzy tolerance.
    short_single_token = len(q_words) <= 1 and len(q) <= 7
    if short_single_token and q[:1] != c[:1]:
        full_ratio = 0.0
    if full_ratio >= 0.7:
        # Mapeo lineal: 0.7 -> 35, 1.0 -> 70. Suficiente para entrar al
        # ranking pero no para vencer un startswith/contiene del 75-90.
        return int(35 + (full_ratio - 0.7) * (70 - 35) / 0.3)
    # Word-pair fuzzy: si cualquier word del query tiene una similar
    # (>=0.75) en el candidato, sumamos credito. "saint" vs "saints" = 0.91;
    # "rose" vs "row" = 0.57 (no califica solo). Pero si AL MENOS UN word
    # del query encuentra match difuso, devolvemos un score modesto.
    matched_words = 0
    for qw in q_words:
        if len(qw) < 3:
            continue
        for cw in c_words:
            if len(cw) < 3:
                continue
            # Same first-char guard as above: "teams"~"steam" (ratio ~0.8)
            # is a near-anagram, NOT a typo. A real per-word typo keeps the
            # first letter. This is what made "abre Teams" open Steam.
            if qw[:1] != cw[:1]:
                continue
            if difflib.SequenceMatcher(None, qw, cw).ratio() >= 0.75:
                matched_words += 1
                break
    if matched_words:
        return 20 + int(20 * matched_words / max(1, len(q_words)))
    return 0
