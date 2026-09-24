"""The canonical surface: a message said with the words the readers read.

Tanda 3 (2026-09-24, official window). BAXY answered «no hago eso» to things the served catalog does, because
the person named them with words no reader knows: «Pausa el speaker.», «Inactivar el microphone and the camera.»,
«me apetece que hagas sonar algo alegre», «Muéstrame mi Gallery.», «añadir una nueva lista para material escolar».
The readers know «pausa el audio», «desactivar el micrófono», «pon algo alegre», «mi carpeta de imágenes» and
«crea una lista». 00_IDENTIDAD: BAXY says no only to what he cannot do.

``canonical`` rewrites only those words (their table is in ``lexicon``) and keeps every other word as it was said.
Like ``levels``, it decides no effect: the turn re-reads the rewrite with the ordinary readers and gates before it
publishes a limit (``__main__._served_surface_reread``). A rewrite nothing reads is nothing done.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Callable

from . import lexicon
from .normalize import alternation


def _fold_char(character: str) -> str:
    """One character folded to one character, so a match on the folded text is a span of the original."""

    decomposed = "".join(
        part for part in unicodedata.normalize("NFKD", character.casefold()) if not unicodedata.combining(part)
    )
    return decomposed if len(decomposed) == 1 else character


def _imperative(subjunctive: str) -> str | None:
    """The tú imperative of a tú present subjunctive («pauses» → «pausa», «abras» → «abre»), or None."""

    if subjunctive in lexicon.IRREGULAR_IMPERATIVES:
        return lexicon.IRREGULAR_IMPERATIVES[subjunctive]
    if len(subjunctive) < 5:
        return None
    for ending, imperative in (("ques", "ca"), ("gues", "ga"), ("ces", "za"), ("zcas", "ce"), ("es", "a"), ("as", "e")):
        if subjunctive.endswith(ending):
            return subjunctive[: -len(ending)] + imperative
    return None


_ENGLISH_DETERMINER = frozenset({"the", "my", "your", "this"})


def _audio(match: re.Match[str], _said: str) -> str:
    determiner = match.group("det")
    if determiner in _ENGLISH_DETERMINER:
        return "the audio"
    return "del audio" if determiner == "del" else "el audio"


def _gallery(match: re.Match[str], _said: str) -> str:
    determiner = match.group("det")
    if determiner in _ENGLISH_DETERMINER:
        return f"{determiner} pictures folder"
    if determiner == "del":
        return "de la carpeta de imagenes"
    return f"{determiner or 'la'} carpeta de imagenes"


def _desired_order(match: re.Match[str], said: str) -> str | None:
    imperative = _imperative(match.group("verb"))
    if imperative is None:
        return None
    return said[match.start("lead") : match.end("lead")] + imperative + (match.group("clitic") or "")


def _list_creation(match: re.Match[str], _said: str) -> str:
    if match.group("noun") == "list":
        return f"create a {match.group('kind')} list" if match.group("kind") else "create a list"
    return "crea una lista"


def _pause(match: re.Match[str], _said: str) -> str:
    return "pausa el" if match.group("to") == "al" else "pausa"


_DETERMINER = r"(?:(?P<det>el|la|los|las|del|mi|mis|tu|tus|este|esta|the|my|your|this)\s+)?"

# Applied in order to the folded message; each replaces only what it matched (None keeps it as said).
_REWRITES: tuple[tuple[re.Pattern[str], Callable[[re.Match[str], str], str | None]], ...] = (
    (
        # Not a thing that rings («haz sonar el timbre»): that is not something to play.
        re.compile(
            rf"\b(?P<verb>{alternation(frozenset(lexicon.MAKE_SOUND_FORMS))})\s+sonar\b"
            rf"(?!\s+(?:(?:el|la|los|las|mi|mis|tu|the|my)\s+)?{alternation(lexicon.RINGING_THINGS)}\b)"
        ),
        lambda match, _said: lexicon.MAKE_SOUND_FORMS[match.group("verb")],
    ),
    (
        re.compile(
            r"^(?P<lead>[\W_]*(?:(?:baxy|oye|hey|che|por\s+favor|porfa)[\W_]+)*)(?:yo\s+)?"
            rf"{alternation(lexicon.DESIRE_FRAMES)}\s+que\s+"
            r"(?:(?P<clitic>me|nos|lo|la|los|las|le|les)\s+)?(?P<verb>[a-z]+)\b"
        ),
        _desired_order,
    ),
    (
        re.compile(rf"\b{lexicon.INACTIVE_STEM}(?=(?:a|ar|ame|alo|ala|e|en|es|emos)\b)"),
        lambda _match, _said: "desactiv",
    ),
    (
        # «pon en pausa», «ponle pausa al …», «deja en pausa» are «pausa».
        re.compile(
            r"\b(?:pon|ponle|pone|ponele|poner|ponerle|dale|deja|dejalo|dejala|dejar)\s+(?:en\s+)?pausa\b"
            r"(?:\s+(?P<to>a\s+la|a\s+los|a\s+las|al|a)\b)?"
        ),
        _pause,
    ),
    (re.compile(rf"\b{_DETERMINER}{lexicon.SPEAKER_NOUN}\b"), _audio),
    (re.compile(rf"\b{_DETERMINER}{alternation(lexicon.GALLERY_NOUNS)}\b"), _gallery),
    (
        re.compile(
            rf"\b{alternation(lexicon.LIST_ADD_VERBS)}\s+(?:(?:una|un)\s+)?(?:nueva\s+)?(?P<es>lista)\b(?:\s+nueva\b)?|"
            rf"\b{alternation(lexicon.LIST_ADD_VERBS)}\s+(?:a|an)\s+(?:new\s+(?:(?P<kind>[a-z]+)\s+)?)?(?P<noun>list)\b"
        ),
        _list_creation,
    ),
)


def canonical(text: str) -> str | None:
    """The message with its colloquial and Spanglish words replaced by the ones the readers read, or None when
    nothing in it is said another way. Only the matched words change; the rest keeps its case and accents."""

    said = " ".join(unicodedata.normalize("NFC", str(text or "")).split())
    current = said
    for pattern, replacement in _REWRITES:
        folded = "".join(_fold_char(character) for character in current)
        pieces: list[str] = []
        position = 0
        for match in pattern.finditer(folded):
            rewritten = replacement(match, current)
            if rewritten is None:
                continue
            pieces.append(current[position : match.start()])
            pieces.append(rewritten)
            position = match.end()
        pieces.append(current[position:])
        current = "".join(pieces)
    return current if current != said else None
