"""Spanish Metaphone (Mosquera 2012) — codificación fonética para español.

Por qué hace falta: el corrector ya usa Double Metaphone INGLÉS (jellyfish),
que codifica bien anglicismos oídos en inglés. Pero Parakeet (multilingüe,
sesgo español) fusiona nombres ingleses a fonología ESPAÑOLA: "Chrome"->"crumb",
"Edge"->"echo", "Zoom"->"su". El Metaphone inglés no acerca esos códigos. El
Spanish Metaphone codifica según reglas del español, de modo que la salida
fonetizada al español y el target comparten clave.

Algoritmo: Mosquera, Lloret & Moreda, "Towards Facilitating the Accessibility
of Web 2.0 Texts through Text Normalisation", LREC NLP4ITA 2012, pp. 9-14.
Implementación portada de amsqr/Spanish-Metaphone (BSD) — sin dependencia de
abydos (GPL, incompatible). ~80 líneas, sin deps externas.

Uso:
    from gemma4_agent.voice.phonetic_es import spanish_metaphone
    spanish_metaphone("crumb")   # clave fonética española
"""
from __future__ import annotations

import unicodedata


def _strip_accents(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )


def spanish_metaphone(word: str, max_len: int = 6) -> str:
    """Código Metaphone-ES de una palabra. Vacío si la entrada es trivial.

    Reglas (Mosquera 2012), aplicadas sobre la palabra en mayúsculas sin
    acentos, manejando dígrafos españoles (LL, CH, QU, GU) y la equivalencia
    B/V, C/Z/S (seseo), Y/I, etc. — los mismos que confunde un ASR sesgado al
    español al oír un anglicismo."""
    if not word:
        return ""
    w = _strip_accents(word).upper()
    w = "".join(c for c in w if c.isalpha())
    if not w:
        return ""

    meta = []
    i = 0
    n = len(w)
    while i < n and len(meta) < max_len:
        c = w[i]
        nxt = w[i + 1] if i + 1 < n else ""

        # Dígrafos / reglas contextuales
        if c == "C":
            if nxt in ("E", "I"):           # CE/CI -> S (seseo)
                meta.append("S")
                i += 1
                continue
            if nxt == "H":                   # CH -> X (dígrafo)
                meta.append("X")
                i += 2
                continue
            meta.append("K")
            i += 1
            continue
        if c == "G":
            if nxt in ("E", "I"):           # GE/GI -> J (jota)
                meta.append("J")
                i += 1
                continue
            if nxt == "U" and (i + 2 < n) and w[i + 2] in ("E", "I"):
                meta.append("G")
                i += 2
                continue   # GUE/GUI -> G (U muda)
            meta.append("G")
            i += 1
            continue
        if c == "Q":                         # QU -> K (U muda)
            meta.append("K")
            i += 2 if nxt == "U" else 1
            continue
        if c == "L" and nxt == "L":          # LL -> Y
            meta.append("Y")
            i += 2
            continue
        if c == "R" and nxt == "R":          # RR -> R
            meta.append("R")
            i += 2
            continue
        if c == "H":                         # H muda
            i += 1
            continue
        if c in ("B", "V"):                  # B/V indistinguibles -> B
            meta.append("B")
            i += 1
            continue
        if c == "Z" or c == "S":             # Z/S seseo -> S
            meta.append("S")
            i += 1
            continue
        if c == "Y":                         # Y vocálica/consonántica -> I
            meta.append("I")
            i += 1
            continue
        if c == "W":                         # W (extranjerismos) -> B/U
            meta.append("U")
            i += 1
            continue
        if c == "X":                         # X -> KS aprox -> S
            meta.append("S")
            i += 1
            continue
        if c == "K":
            meta.append("K")
            i += 1
            continue
        if c == "J":
            meta.append("J")
            i += 1
            continue
        if c in "AEIOU":                      # vocales -> se conservan (clave abierta)
            meta.append(c)
            i += 1
            continue
        if c in ("D", "F", "M", "N", "P", "T"):
            meta.append(c)
            i += 1
            continue
        # cualquier otra (Ñ, etc.)
        if c == "Ñ":
            meta.append("N")
        i += 1

    return "".join(meta)
