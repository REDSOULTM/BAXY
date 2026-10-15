"""Revisión 2 de r22 (bloqueante 3): the parts of a request that the chosen operation cannot receive.

Uso real r18 t2-c16 «toma una captura de pantalla y guardala en mis imagenes» and t3-c11 «…y guárdala en el escritorio
porfa» were told «Hice la captura de pantalla.»: the operation's schema had no property for the part «guárdala en X»,
so the part was lost in silence. The same holds for any operation and any act on what it makes: «toma una captura y
mándala a mi jefe» (no recipient), «abre el informe y imprímelo» (no printer), «…guárdala en mi escritorio con el
nombre factura» (no name). Each act on the result is read here — a verb with the result as its object pronoun, joined
to the request after another part — and is received only when the operation's argument schema has a property for it
(data/acts_on_result.v1.json ``receivedBy``). What is not received is told as not done; how the final says it is data.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path
from typing import NamedTuple

from .normalize import fold_in_place

_DATA = Path(__file__).resolve().parent.parent / "data" / "acts_on_result.v1.json"

# The act's own clause ends where another begins.
_CLAUSE_END = re.compile(r"[.;!?]|\b(?:y|and|e|luego|then|despues|pero|but)\b")
_NEGATED_BEFORE = re.compile(r"\b(?:no|sin|nunca|ni|don'?t|do\s+not|never|without|not)\s+(?:\w+\s+){0,2}$")
# «keep it on for an hour», «guárdalo hasta mañana»: a time after the preposition is how long, never a place.
_NOT_A_PLACE = r"(?!(?:for|until|till|while|during|por|durante|hasta|mientras)\b)"
_PLACE_AFTER = re.compile(
    r"^\s+(?:\w+\s+){0,2}?(?:en|in|into|to|on|onto|dentro\s+de|inside)\s+" + _NOT_A_PLACE + r"\w"
)
# «súbela a la nube» is a destination; «súbelo al máximo», «súbela a 80» is a level (the volume, the brightness).
_DESTINATION_AFTER = re.compile(
    r"^\s+(?:\w+\s+){0,2}?(?:a|al|en|in|into|to|on|onto|para)\s+(?:(?:el|la|los|las|the|mi|mis|my)\s+)?"
    r"(?!(?:\d|max|min|tope|top|tod[oa]s?\b|full|cien|mitad|medio|nivel|volumen|brillo|fondo|lo\b))"
    + _NOT_A_PLACE + r"\w"
)
_NAME_AFTER = re.compile(
    r"\b(?:con\s+(?:el\s+)?nombre(?:\s+de)?|llamad[ao]|named|called|with\s+the\s+name|under\s+the\s+name)\s+"
    r"(?P<name>\S.*)$"
)
_POLITE_TAIL = re.compile(
    r"(?:\s*,?\s*\b(?:porfa|porfavor|por\s+favor|please|plis|pls|gracias|thanks|ahora|now|ya)\b\W*)+$"
)


class UnreceivedPart(NamedTuple):
    """One part of the request the operation's schema cannot receive: the act (data key) and the part as said."""

    act: str
    said: str


@lru_cache(maxsize=1)
def data() -> dict:
    return json.loads(_DATA.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _act_verbs() -> tuple[tuple[str, re.Pattern[str]], ...]:
    verbs = []
    for act, entry in data()["acts"].items():
        spanish = "|".join(sorted(map(re.escape, entry.get("es", ())), key=len, reverse=True))
        english = "|".join(sorted(map(re.escape, entry.get("en", ())), key=len, reverse=True))
        verbs.append((act, re.compile(
            # «mándala», «enviarla», «mándamela», «imprímela»: the result as an enclitic pronoun.
            r"\b(?:(?:" + spanish + r")(?:a|e|i|ar|er|ir)(?:me|te|se|nos)?(?:la|lo|las|los)"
            # «send it», «print that», «save them».
            + r"|(?:" + english + r")\s+(?:it|that|this|them))\b"
        )))
    return tuple(verbs)


def read_for(operation: object) -> bool:
    """Whether an act on the result is read for ``operation``: only an operation the data declares (``readFor``) as
    making or opening a result that it never sends, uploads, prints or keeps elsewhere itself. Any other operation may
    do the act as its own effect under another argument name (a reply sends its ``text``, a print takes a
    ``documentId``) or carry the whole request in its goal (computer use), so nothing is read for it."""

    return isinstance(operation, str) and operation in data()["readFor"]["operations"]


def _needs_destination(entry: dict, verb: str) -> bool:
    """A stem the data marks ``destinationFor`` («sub»: also raising the volume or the brightness) is the act only with
    a destination after it."""

    return any(verb.startswith(stem) for stem in entry.get("destinationFor", ()))


def _received(entry: dict, properties: frozenset[str]) -> bool:
    return any(name in properties for name in entry.get("receivedBy", ()))


def unreceived_parts(text: object, properties: Iterable[str]) -> tuple[UnreceivedPart, ...]:
    """Every act on the result in ``text`` that an operation whose argument schema has ``properties`` cannot receive,
    with the part as the person wrote it."""

    original = str(text or "")
    folded = fold_in_place(original)
    names = frozenset(properties)
    found: list[tuple[int, UnreceivedPart]] = []
    for act, verb_pattern in _act_verbs():
        entry = data()["acts"][act]
        for verb in verb_pattern.finditer(folded):
            before = folded[: verb.start()]
            if not re.search(r"\w", before) or _NEGATED_BEFORE.search(before):
                # The act alone is the whole request (no part of it was given to the operation), or it is refused.
                continue
            end = next((cut.start() for cut in _CLAUSE_END.finditer(folded, verb.end())), len(folded))
            clause = folded[verb.start(): end]
            if entry.get("needsPlace") and not _PLACE_AFTER.match(folded[verb.end(): end]):
                # «guárdala», «keep it» with no place: what keeping needs no argument for.
                continue
            if _needs_destination(entry, verb.group(0)) and not _DESTINATION_AFTER.match(folded[verb.end(): end]):
                # «el volumen está muy bajo, súbelo», «súbela al máximo»: raising a level, not an upload.
                continue
            said = _POLITE_TAIL.sub("", " ".join(original[verb.start(): end].split())).rstrip(" ,:")
            name = _NAME_AFTER.search(clause)
            if not _received(entry, names):
                found.append((verb.start(), UnreceivedPart(act, said)))
            elif name is not None and not _received(data()["name"], names):
                # «…guárdala en mi escritorio con el nombre factura»: kept where asked, but the name has no property.
                value = _POLITE_TAIL.sub("", " ".join(original[verb.start() + name.start("name"): end].split()))
                value = value.strip(" ,:«»\"'“”")
                if value:
                    found.append((verb.start(), UnreceivedPart("name", value)))
    return tuple(part for _, part in sorted(found, key=lambda item: item[0]))
