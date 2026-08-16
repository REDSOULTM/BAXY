"""Reference-independent Spanish numeric normalization for STT semantics."""

from __future__ import annotations

import re
import unicodedata


_ATOMS: dict[str, tuple[int, int]] = {
    "cero": (0, 1),
    "un": (1, 1),
    "uno": (1, 1),
    "una": (1, 1),
    "dos": (2, 1),
    "tres": (3, 1),
    "cuatro": (4, 1),
    "cinco": (5, 1),
    "seis": (6, 1),
    "siete": (7, 1),
    "ocho": (8, 1),
    "nueve": (9, 1),
    "diez": (10, 2),
    "once": (11, 2),
    "doce": (12, 2),
    "trece": (13, 2),
    "catorce": (14, 2),
    "quince": (15, 2),
    "dieciseis": (16, 2),
    "diecisiete": (17, 2),
    "dieciocho": (18, 2),
    "diecinueve": (19, 2),
    "veinte": (20, 2),
    "veintiuno": (21, 2),
    "veintiun": (21, 2),
    "veintiuna": (21, 2),
    "veintidos": (22, 2),
    "veintitres": (23, 2),
    "veinticuatro": (24, 2),
    "veinticinco": (25, 2),
    "veintiseis": (26, 2),
    "veintisiete": (27, 2),
    "veintiocho": (28, 2),
    "veintinueve": (29, 2),
    "treinta": (30, 2),
    "cuarenta": (40, 2),
    "cincuenta": (50, 2),
    "sesenta": (60, 2),
    "setenta": (70, 2),
    "ochenta": (80, 2),
    "noventa": (90, 2),
    "cien": (100, 3),
    "ciento": (100, 3),
    "doscientos": (200, 3),
    "doscientas": (200, 3),
    "trescientos": (300, 3),
    "trescientas": (300, 3),
    "cuatrocientos": (400, 3),
    "cuatrocientas": (400, 3),
    "quinientos": (500, 3),
    "quinientas": (500, 3),
    "seiscientos": (600, 3),
    "seiscientas": (600, 3),
    "setecientos": (700, 3),
    "setecientas": (700, 3),
    "ochocientos": (800, 3),
    "ochocientas": (800, 3),
    "novecientos": (900, 3),
    "novecientas": (900, 3),
    "primer": (1, 1),
    "primero": (1, 1),
    "primera": (1, 1),
    "segundo": (2, 1),
    "segunda": (2, 1),
    "tercer": (3, 1),
    "tercero": (3, 1),
    "tercera": (3, 1),
    "cuarto": (4, 1),
    "cuarta": (4, 1),
    "quinto": (5, 1),
    "quinta": (5, 1),
}
_TOKEN_PATTERN = re.compile(r"\d+|[a-z]+", re.IGNORECASE)


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(
        character
        for character in decomposed
        if not unicodedata.combining(character)
    )


def _parse_number(tokens: list[str], start: int) -> tuple[str, int] | None:
    first = tokens[start]
    if first not in _ATOMS and first != "mil":
        return None
    total = 0
    current = 0
    previous_rank = 4
    index = start
    consumed_atom = False
    while index < len(tokens):
        token = tokens[index]
        if token == "y":
            if (
                not consumed_atom
                or index + 1 >= len(tokens)
                or tokens[index + 1] not in _ATOMS
                or _ATOMS[tokens[index + 1]][1] >= previous_rank
            ):
                break
            index += 1
            continue
        if token == "mil":
            if previous_rank == 4 and not consumed_atom:
                current = 1
            total += max(1, current) * 1_000
            current = 0
            previous_rank = 4
            consumed_atom = True
            index += 1
            continue
        atom = _ATOMS.get(token)
        if atom is None:
            break
        value, rank = atom
        if consumed_atom and previous_rank != 4 and rank >= previous_rank:
            break
        current += value
        previous_rank = rank
        consumed_atom = True
        index += 1
    if not consumed_atom:
        return None
    return str(total + current), index


def semantic_tokens(text: str) -> list[str]:
    """Normalize written digits and spoken Spanish cardinals to equal tokens."""

    value = _fold(text)
    # A dot followed by exactly three digits is a Spanish thousands separator.
    value = re.sub(r"(?<=\d)\.(?=\d{3}(?:\D|$))", "", value)
    tokens = _TOKEN_PATTERN.findall(value)
    normalized: list[str] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token.isdigit():
            normalized.append(str(int(token)))
            index += 1
            continue
        parsed = _parse_number(tokens, index)
        if parsed is None:
            normalized.append(token)
            index += 1
            continue
        number, index = parsed
        normalized.append(number)
    return normalized
