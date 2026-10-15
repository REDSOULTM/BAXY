"""Ronda 22 (uso real r18): where the person asks a capture to be kept.

t2-c16 «toma una captura de pantalla y guardala en mis imagenes», t3-c11 «hazme una captura de pantalla y guárdala en el
escritorio porfa» and t4-c09 «saca una captura de pantalla y guardala» were told «Hice la captura de pantalla.» or
«…la guardé de forma privada»: the capture took no destination and the part «guárdala en X» was lost in silence. The
capture operations now take an optional known ``folder`` (ProductCatalog ``capture.screenshot``,
``capture.active.window``); this reader says which, from the person's words only.

Revisión r22 (bloqueante 2): the keeping counts only when its object is the capture — a pronoun after the capture was
named («guárdala», «save it», «ponla», «déjala»), the capture itself («guárdame una captura», «save the screenshot»),
or a bare verb joined to the capture's clause and followed by a place or nothing («y guarda en descargas», «and
save»). «el diálogo de guardar como», «the save as window», «the save game menu», «guarda el archivo en el escritorio y
luego toma una captura» keep no capture; «guárdala en privado» / «keep it private» asks for what a capture already is,
and writes no file. Pictures when a verb of keeping names no place («guárdala»); «déjala» / «ponla» with no place keep
nothing.

Revisión r22 (bloqueante 1): every place asked that the operation cannot take is kept in ``CaptureSave.unmet`` — a place
that is no known folder («en mi pendrive», «en la carpeta proyectos», «en el portapapeles») and every known folder
after the first («en el escritorio y en documentos») — so the final says it was not done instead of losing it.
"""

from __future__ import annotations

import re
from typing import NamedTuple

from .display import _KNOWN_FOLDER_ENUM
from .normalize import fold_in_place

CAPTURE_OPERATIONS = frozenset({"capture.screenshot", "capture.active.window"})

# The file readers' known folders (semantic.display), and the person's pictures folder, which a capture is kept in.
_SAVE_FOLDERS: dict[str, str] = {
    **_KNOWN_FOLDER_ENUM,
    "mis documentos": "documents",
    "imagenes": "pictures", "pictures": "pictures", "fotos": "pictures", "photos": "pictures",
}
_FOLDER_WORD = re.compile(r"\b(?P<folder>" + "|".join(sorted(map(re.escape, _SAVE_FOLDERS), key=len, reverse=True)) + r")\b")

# What names the capture itself («una captura», «el screenshot», «la imagen», «pantallazo»).
_CAPTURE_NOUN = r"(?:captura|capturas|screenshot|screenshots|screen\s+shot|pantallazo|imagen|image|picture|capture|snapshot)"
_CAPTURE_WORD = re.compile(r"\b(?:captur\w*|screenshot\w*|screen\s+shot|pantallazo\w*|print\s*screen|snapshot\w*)\b")
_PREPOSITION = r"(?:en|in|into|to|on|onto|a|dentro\s+de|inside)"

# The verb of keeping with the capture as its object.
_KEEP_VERB = re.compile(
    r"\b(?:"
    # A pronoun for the capture glued to the verb or before it: guárdala, guardarla, guárdamela, la guardas, sálvala,
    # déjala, ponla, save it, keep it, put it, leave it, store it.
    r"(?P<pronoun>guard(?:alo|ala|arlo|arla|amelo|amela|atelo|atela|aselo|asela)"
    r"|(?:la|lo|me\s+la|me\s+lo|te\s+la|te\s+lo)\s+(?:guard|dej|pon|pong)(?:as|es|e|a|ais|o|go|gas|ga)"
    r"|salv(?:alo|ala|arlo|arla|amelo|amela)"
    r"|dej(?:alo|ala|arlo|arla|amelo|amela)"
    r"|(?:ponla|ponlo|ponerla|ponerlo|ponmela|ponmelo)"
    r"|(?:save|keep|store|put|leave|drop)\s+(?:it|that|this|them|a\s+copy)"
    r")"
    # The capture itself as the object: guárdame una captura, guarda la captura, save the screenshot.
    r"|(?P<noun>(?:guard(?:a|ar|ame|en)|salv(?:a|ar|ame)|save|store|keep)\s+(?:(?:una|la|el|un|the|a|my|mi|esa|esta|that|this)\s+)?"
    + _CAPTURE_NOUN + r")"
    # A bare verb joined to the capture's clause («…y guarda en descargas», «…and save»).
    r"|(?:(?<=\by\s)|(?<=\band\s)|(?<=,\s)|(?<=\btambien\s)|(?<=\balso\s)|(?<=\bluego\s)|(?<=\bthen\s))"
    r"(?P<bare>guarda|guardar|save|store)(?=\s+" + _PREPOSITION + r"\s|\s*(?:$|[.;!?,]|\s(?:porfa|por\s+favor|please|plis)\b))"
    r")"
)
# Verbs of placing keep the capture only where a place is said («déjala en el escritorio»); «déjala» alone keeps none.
_PLACING = re.compile(r"\b(?:dej\w*|pon\w*|(?:la|lo)\s+(?:dej|pon)\w*|put|leave|drop)\b")
_NEGATED_BEFORE = re.compile(r"\b(?:no|sin|nunca|ni|don'?t|do\s+not|never|without|not)\s+(?:\w+\s+){0,2}$")
# Keeping it private is what a capture already is: no file is written.
_PRIVATE = re.compile(r"\b(?:privad[oa]s?|privately|private|solo\s+para\s+mi|only\s+for\s+me|para\s+mi\s+nomas)\b")

# A place said in the keeping's clause that is a container of files, a device or another store: «en mi pendrive», «en
# la carpeta proyectos», «to my USB drive», «en el portapapeles», or one said as the person's own («en mi pc»).
_PLACE_SAID = re.compile(
    r"\b" + _PREPOSITION + r"\s+(?P<place>(?:(?:el|la|los|las|the|a|an|una|un)\s+)*"
    r"(?:(?:carpeta|folder|directorio|directory|disco|drive|unidad|usb|pendrive|pen\s+drive|memoria|nube|cloud|"
    r"onedrive|dropbox|portapapeles|clipboard|subcarpeta|subfolder)\b|(?:mi|mis|my|tu|tus|your|nuestra|our)\s+\w).*)"
)
_POLITE_TAIL = re.compile(r"(?:\s*,?\s*\b(?:porfa|porfavor|por\s+favor|please|plis|gracias|thanks)\b\W*)+$")
# Revisión 2 de r22 (bloqueante 1, «save it to my desktop now» → unmet «my desktop now»): a known folder followed by a
# word that cannot continue a folder's name — when, how, why or under what name it is kept — is that folder; the rest
# is no part of the place. A path separator («documentos/proyectos») or any other word («la carpeta descargas viejas»)
# still names a place the operation cannot take.
_AFTER_PLACE = re.compile(
    r"\s*(?:$|[,.;:!?]|(?:ahora|ya|now|rapido|rapidito|quickly|asap|hoy|today|luego|later|despues|porfa|porfavor|"
    r"por\s+favor|please|plis|pls|gracias|thanks|con|with|para|for|como|as|llamad[ao]|named|called|bajo|under|sin|"
    r"without|right|mismo|nomas|tambien|also|too|igual)\b)"
)
_WHEN_TAIL = re.compile(
    r"\s+(?:ahora|ya|now|rapido|rapidito|quickly|asap|hoy|today|right\s+now|for\s+later|para\s+despues|porfavor|pls)\b.*$"
)
_SUBPATH = re.compile(r"\s*[\\/]\s*[^\s,.;!?]+(?:\s*[\\/]\s*[^\s,.;!?]+)*")
# The words that lead into the keeping's own clause («toma una captura, quiero guardarla…»): no other clause.
_LEAD_IN = re.compile(
    r"\s*(?:(?:yo|i|tambien|also|ademas|porfa|por\s+favor|please|que|quiero|quisiera|queria|necesito|me\s+gustaria|"
    r"podrias|puedes|podes|want\s+to|would\s+like\s+to|'?d\s+like\s+to|need\s+to|can\s+you|could\s+you)\s*)*"
)
_LEADING_ARTICLE = re.compile(r"^(?:(?:el|la|los|las|the|a|an|una|un)\s+)+")
# A container named by a known folder is that folder («la carpeta de descargas», «the downloads folder»).
_CONTAINER_OF_FOLDER = re.compile(
    r"^(?:(?:el|la|los|las|the|a|mi|mis|my|tu|tus|your)\s+)*"
    r"(?:(?:carpeta|folder)\s+(?:(?:de|del|de\s+la|de\s+mis|of|of\s+the|of\s+my|llamada|called)\s+)?(?:(?:mi|mis|my)\s+)?)?"
)

# The keeping's own clause ends where another begins («…y luego muéstrame el escritorio» names no destination); a
# further place joined to it («…en el escritorio y en documentos») is still asked of the keeping.
_CLAUSE_END = re.compile(r"[.;!?]|\b(?:y|and|e|luego|then|despues|pero|but)\b")
_BETWEEN_CLAUSES = re.compile(r"[,.;!?]|\b(?:y|and|e|luego|then|despues|pero|but|tambien|also)\b")
_MORE_PLACE = re.compile(r"^\s*(?:tambien\s+|also\s+|otra\s+(?:copia\s+)?)?" + _PREPOSITION + r"\s")


class CaptureSave(NamedTuple):
    """The keeping the person asked of a capture: the known folder it can take (None when no place asked is one), the
    place said for it, and every place asked that the operation cannot take (``unmet``), told as not done."""

    folder: str | None
    place_said: str
    unmet: tuple[str, ...] = ()


def _clause_places(folded: str, start: int) -> list[tuple[int, str]]:
    """The keeping's clause and every further place joined to it, one (offset, text) per place asked."""

    bounds = [start, *(cut for match in _CLAUSE_END.finditer(folded, start) for cut in (match.start(), match.end()))]
    bounds.append(len(folded))
    parts = [(bounds[i], folded[bounds[i]:bounds[i + 1]]) for i in range(0, len(bounds) - 1, 2)]
    places = [parts[0]]
    for part in parts[1:]:
        if not _MORE_PLACE.match(part[1]):
            break
        places.append(part)
    return places


def _place(segment: str) -> tuple[str | None, int, int] | None:
    """(the known folder or None, and the span of the place as said) of one place asked, or None when the segment
    names no place."""

    container = _PLACE_SAID.search(segment)
    named = _FOLDER_WORD.search(segment)
    if container is not None and (named is None or container.start("place") < named.start()):
        said = _POLITE_TAIL.sub("", container.group("place")).rstrip(" ,.;:")
        stripped = _CONTAINER_OF_FOLDER.sub("", said)
        rest = re.sub(r"\s+(?:folder|carpeta)$", "", stripped)
        whole = _FOLDER_WORD.fullmatch(rest.strip(" ,.;:"))
        if whole is None and (lead := _FOLDER_WORD.match(rest)) is not None:
            # «my desktop now», «mis imágenes ahora», «mi escritorio con el nombre factura»: the folder, then words
            # that are no part of its name (the name asked is the request's other part, told as not received).
            after = re.sub(r"^\s+(?:folder|carpeta)\b", "", rest[lead.end():])
            whole = lead if _AFTER_PLACE.match(after) else None
        if whole is not None:
            # The offset of what the container's words left (the trailing «folder» is cut after it, never before).
            at = container.start("place") + len(said) - len(stripped)
            return _SAVE_FOLDERS[whole.group("folder")], at + whole.start("folder"), at + whole.end("folder")
        # The place not taken is quoted without the words of when it was asked («mi pendrive ahora» → «mi pendrive»).
        said = _WHEN_TAIL.sub("", said)
        article = _LEADING_ARTICLE.match(said)
        begin = container.start("place") + (article.end() if article else 0)
        return None, begin, container.start("place") + len(said)
    if named is not None:
        path = _SUBPATH.match(segment, named.end())
        if path is not None:
            # «en documentos/proyectos»: a folder inside the known one is a place the operation cannot take.
            return None, named.start("folder"), path.end()
        return _SAVE_FOLDERS[named.group("folder")], named.start("folder"), named.end("folder")
    return None


def capture_save(text: str) -> CaptureSave | None:
    """The keeping asked of the capture in ``text``, or None when the person did not ask to keep it in a file. The
    places are given as the person wrote them (revisión r21 bloqueante 3: never quoted folded)."""

    original = str(text or "")
    # One character for one, so a place found in it is the same span of what the person wrote.
    folded = fold_in_place(original)
    for verb in _KEEP_VERB.finditer(folded):
        if _NEGATED_BEFORE.search(folded[: verb.start()]):
            continue
        if verb.group("noun") is None:
            named = [*_CAPTURE_WORD.finditer(folded[: verb.start()])]
            if not named:
                # «guarda el archivo en el escritorio y luego toma una captura»: no capture named before the pronoun or
                # the bare verb, so what it keeps is something else.
                continue
            between = _BETWEEN_CLAUSES.split(folded[named[-1].end(): verb.start()])
            # Revisión 2 de r22 (bloqueante 3, «toma una captura, quiero guardarla en el escritorio»): the words that
            # lead into the keeping's own clause («quiero», «I want to») are no other clause.
            if any(re.search(r"\w", part) for part in between[1:-1]) or (
                len(between) > 1 and _LEAD_IN.fullmatch(between[-1]) is None
            ):
                # «toma una captura, abre el bloc de notas y guárdalo en el escritorio»: another clause stands between
                # the capture and the pronoun, which keeps what that clause made.
                continue
        segments = _clause_places(folded, verb.end())
        if _PRIVATE.search(segments[0][1]):
            return None
        places = [
            (place[0], " ".join(original[offset + place[1]: offset + place[2]].split()))
            for offset, segment in segments if (place := _place(segment)) is not None
        ]
        if not places:
            if _PLACING.search(verb.group(0)):
                # «déjala», «ponla» with no place: no keeping asked.
                continue
            return CaptureSave("pictures", "")
        known = next((place for place in places if place[0] is not None), None)
        unmet = tuple(place[1] for place in places if place is not known)
        if known is None:
            return CaptureSave(None, places[0][1], unmet)
        return CaptureSave(known[0], known[1], unmet)
    return None


def capture_save_arguments(text: str) -> dict[str, object]:
    """The capture's arguments read from the person's words: the folder to keep it in, or none (it stays private)."""

    save = capture_save(text)
    return {"folder": save.folder} if save is not None and save.folder is not None else {}


def capture_unmet_places(text: str) -> tuple[str, ...]:
    """Every place the person asked the capture to be kept in that the operation cannot take, as said."""

    save = capture_save(text)
    return save.unmet if save is not None else ()
