"""BAXY's private memory asked for by name: remember this, what do you remember, forget it, show your memory.

Memory is the person's explicit request only (C03 memory instrument, MEMORY1245–1255: two-phase saves confirmed in the
App, ``NaturalMemoryRequestParser``). The contextual decider carries the memory operations in its catalog, as it was
trained (M114); this reading is what lets its choice of one stand (M118).
"""

from __future__ import annotations

import re

from .grammar import _fold, _strip_request_envelope

# «recuerda que me llamo Reta», «acordate que mi color favorito es el azul», «guardá que mi cumpleaños es el 5 de mayo»,
# «remember that I take my coffee black», «no olvides que soy alérgico», «quiero que recuerdes que…», «recuérdalo».
# «recuérdame / recuerda llamar a…» is a reminder, never memory: the order is followed by «que», «:», a pronoun of the
# thing said, or «en/in your memory».
_SAVE = re.compile(
    r"^(?:(?:por\s+favor|please)\s*,?\s*)?"
    r"(?:(?:quiero|necesito|quisiera|me\s+gustaria|i\s+want|i'?d\s+like)\s+(?:que\s+|you\s+to\s+)?)?"
    r"(?:recuerda|recorda|recuerdes|recordases|recordaras|acordate|acuerdate|guarda|guardes|memoriza|memorices|"
    r"anota\s+en\s+tu\s+memoria|"
    r"no\s+(?:te\s+)?olvides|ten\s+en\s+cuenta|remember|memorize|save|keep\s+in\s+mind|don'?t\s+forget|do\s+not\s+forget)"
    r"(?:\s+(?:que|that|de\s+que)\b|\s*:|\s+(?:en|in)\s+(?:tu|your)\s+(?:memoria|memory)\b)"
    r"|^(?:recuerdalo|recordalo|guardalo\s+en\s+tu\s+memoria|remember\s+(?:it|this|that))\b"
)
# «¿qué recuerdas de mí?», «¿te acuerdas de mi color favorito?», «what do you remember about my preferences»,
# «¿qué tienes guardado en tu memoria?», «¿recuerdas cómo me llamo?».
_RECALL = re.compile(
    r"\b(?:que|cual|cuales|what|which)\b.{0,40}\b(?:recuerdas|recordas|te\s+acuerdas|remember|tienes\s+guardad[oa]s?|"
    r"guardaste|saved|memorizaste)\b"
    r"|^(?:y\s+|and\s+)?(?:te\s+acuerdas|recuerdas|recordas|do\s+you\s+remember|you\s+remember)\b.{0,40}"
    r"\b(?:mi|mis|me|yo|my|i|i'?m)\b"
)
# «olvida que me llamo Reta», «borra eso de tu memoria», «forget my favorite color».
_FORGET = re.compile(
    r"^(?:(?:por\s+favor|please)\s*,?\s*)?(?:olvida|olvidate\s+de|forget)\b"
    r"|\b(?:borra|elimina|quita|delete|remove|erase|clear|limpia)\b.{0,40}\b(?:de|from)\s+(?:tu|your)\s+(?:memoria|memory)\b"
)
# «muéstrame tu memoria», «¿qué hay en tu memoria?», «activa tu memoria», «export your memory».
_MEMORY_NAMED = re.compile(r"\b(?:tu|tus|your)\s+(?:memoria|memory|memories|recuerdos)\b|\bmemoria\s+(?:de\s+)?baxy\b")
# M111 (DEV-F F-w10-t3 «save that in a note called home network»): what is saved in a note, a task, a list or a file
# goes to that record, never to BAXY's memory.
_RECORD_DESTINATION = re.compile(
    r"\b(?:en|in|as|como|to|into)\s+(?:(?:una|un|la|el|las|los|mis|mi|a|an|the|my)\s+)?(?:(?:nueva|new)\s+)?"
    r"(?:nota|notas|note|notes|tarea|tareas|task|tasks|lista|list|pendientes|to-?do|archivo|file|documento|document)\b"
)


# The verb asked with a letter misheard or mistyped («me gustaría que rercordases que me gusta esta canción», DEV-D
# D-s071): owner rule 2026-09-19, what was said wrong BAXY fixes.
_REMEMBER_FORMS = ("recordases", "recordaras", "recuerdes", "recuerda", "recorda", "acordate", "acuerdate", "remember")
# Words of the same verbs said right, never «corrected» into another form.
_REMEMBER_SAID = frozenset({
    *_REMEMBER_FORMS, "recuerdas", "recuerdo", "recordar", "recordas", "recordaste", "recordame", "recuerdame",
    "recordare", "recordara", "recordaria", "acordar", "acuerdas", "acuerdo", "acordaste", "remembers", "remembered",
    "recordando", "recordado", "acordando",
})


def _one_edit(word: str, form: str) -> bool:
    if abs(len(word) - len(form)) > 1 or word == form:
        return False
    if len(word) == len(form):
        return sum(a != b for a, b in zip(word, form)) == 1
    short, long = sorted((word, form), key=len)
    return any(long[:index] + long[index + 1:] == short for index in range(len(long)))


def _remember_misheard(body: str) -> str:
    """The message with a remember verb said one letter off written as the verb («rercordases que» → «recordases»)."""

    words = body.split()
    fixed = [
        word if word in _REMEMBER_SAID or len(word) < 7
        else next((form for form in _REMEMBER_FORMS if _one_edit(word, form)), word)
        for word in words
    ]
    return " ".join(fixed)


def explicit_memory_request(text: str) -> bool:
    """The message asks BAXY's private memory by name: to remember something, to say what it remembers, to forget,
    or to act on «tu memoria». A question about the person's contacts, plans or friends is not one, however personal
    (reserve v4g «mis contactos son mayormente masculinos…», «cuando se acerca el cumpleaños de mi amigo»)."""

    folded = _fold(str(text or ""))
    body = _remember_misheard(_strip_request_envelope(folded).strip(" ¿?¡!.,"))
    if _RECORD_DESTINATION.search(body) and not _MEMORY_NAMED.search(body):
        return False
    return bool(
        _SAVE.search(body)
        or _RECALL.search(body)
        or _FORGET.search(body)
        or _MEMORY_NAMED.search(body)
    )
