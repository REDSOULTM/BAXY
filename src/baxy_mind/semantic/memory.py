"""BAXY's private memory asked for by name: remember this, what do you remember, forget it, show your memory.

Memory is the person's explicit request only (C03 memory instrument, MEMORY1245–1255: two-phase saves confirmed in the
App, ``NaturalMemoryRequestParser``). The contextual decider carries the memory operations in its catalog, as it was
trained (M114); this reading is what lets its choice of one stand (M118).
"""

from __future__ import annotations

import functools
import hashlib
import json
import re
from pathlib import Path

from . import temporal
from .grammar import _COVERAGE_ACTION_HEAD, _fold, _head_is, _request_body_surface, _request_head, _strip_request_envelope
from .normalize import fold_in_place

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
    saved = _SAVE.search(body)
    rest = body[saved.end():] if saved is not None else ""
    if saved is not None and (_not_a_datum(rest, rest) or _carries_another_order(rest)):
        # Revisión M H3/H4: «acordate de que tengo que comprar pan», «recordá que mi turno es a las 10» ask for a task or
        # a moment, never a datum to keep: the reminder readers take it, or it is asked. H1: «… es verde y abrí
        # Spotify» joins another order, which never becomes part of a kept value.
        return False
    return bool(
        _SAVE.search(body)
        or _RECALL.search(body)
        or _FORGET.search(body)
        or _MEMORY_NAMED.search(body)
        or memory_request(text) is not None
    )


# Estabilización M (2026-10-11, comprobación en vivo de identidad §3c-§3d): «Recordá que mi color favorito de prueba es
# el turquesa» was asked back («¿Qué necesitas que haga BAXY con ese turquesa?») and «Corrige ese recuerdo: mi color
# favorito ya no es el turquesa, ahora es el verde» ran nothing: the App refused every memory operation the mind chose,
# and this gate did not know a correction. A save or a correction said whole is read here, with its datum: the
# operation and its typed arguments, so the App runs it on its private route (kernel, journal) without the model.
_SUBJECTS_FILE = Path(__file__).resolve().parent.parent / "data" / "memory_subjects.v1.json"


@functools.lru_cache(maxsize=1)
def _subjects() -> dict:
    return json.loads(_SUBJECTS_FILE.read_text(encoding="utf-8"))


def _subject_selectors() -> dict[str, str]:
    return {_fold(phrase): selector for selector, phrases in _subjects()["selectors"].items() for phrase in phrases}


_ARTICLE = r"(?:(?:el|la|los|las|un|una|the|a|an)\s+)?"
_IN_MEMORY = r"(?:en|in)\s+(?:tu|your)\s+(?:memoria|memory)"
# The save said whole: a remember verb (voseo and the «-me» form included), its «que»/«that»/«:», then the datum.
_SAVE_HEAD = re.compile(
    r"^(?:(?:por\s+favor|please)\s*,?\s*)?"
    r"(?:(?:quiero|necesito|quisiera|i\s+want|i'?d\s+like)\s+(?:que\s+|you\s+to\s+)?)?"
    r"(?:recuerda|recorda|recordame|recuerdame|recuerdes|acordate|acuerdate|guarda|guardes|guardame|memoriza|"
    r"memorices|no\s+(?:te\s+)?olvides|ten\s+en\s+cuenta|remember|memorize|keep\s+in\s+mind|"
    # «save that file as…» is the window's own Save As: «save» keeps a datum only said into the memory.
    rf"don'?t\s+forget|do\s+not\s+forget|(?:save|store|anota)(?=\s+{_IN_MEMORY}))"
    rf"(?:\s+{_IN_MEMORY})?(?:\s+(?:que|that|de\s+que)\b|\s*:)\s*"
)
# A correction: its verb, what is corrected when it is named («ese recuerdo», «lo que recordás de», «en tu memoria»),
# then the person's datum and its new value.
_CORRECT_HEAD = re.compile(
    r"^(?:(?:por\s+favor|please)\s*,?\s*)?"
    r"(?:cambia|cambie|cambiame|corrige|corregi|corregime|actualiza|actualice|actualizame|modifica|edita|"
    r"change|update|correct|fix|edit|modify)\b"
)
_CORRECTED_THING = re.compile(
    rf"^\s*(?:{_IN_MEMORY}\b|(?:ese|este|el|that|this|the)\s+(?:recuerdo|dato|memory|record|detail|fact)\b|"
    r"(?:lo\s+que\s+(?:recuerdas|recordas|sabes|tienes\s+guardado)|what\s+you\s+(?:remember|know|have\s+saved))"
    r"\s+(?:de|sobre|about|of)\b)\s*:?"
)
_TO_VALUE = re.compile(
    r"^(?P<subject>.+?)\s*(?:\s(?:a|al|por|to)|:)\s+(?:(?:ahora\s+|now\s+)?(?:es|son|is|are)\s+)?" + _ARTICLE
    + r"(?P<value>\S.*)$"
)
_NOW_VALUE = re.compile(
    r"^(?P<subject>.+?)(?:\s+ya\s+no\s+(?:es|son)\s+.+?,|\s+(?:is|are)\s+no\s+longer\s+.+?,)?"
    r"\s+(?:ahora\s+|now\s+)?(?:es|son|is|are)\s+(?:ahora\s+|now\s+)?" + _ARTICLE + r"(?P<value>\S.*)$"
)
_DATUM = re.compile(
    r"^(?:mi|mis|my)\s+(?P<subject>[a-z][a-z0-9' -]{0,60}?)\s+(?:ahora\s+|now\s+)?(?:es|son|is|are)\s+"
    + _ARTICLE + r"(?P<value>\S.*)$"
)
_TRAILING_MEMORY = re.compile(rf"\s+{_IN_MEMORY}\s*$")
# Revisión M H4: what the person has to do is a task or a reminder, never a datum about them.
_TASK = re.compile(
    r"\b(?:(?:tengo|tenes|tienes|tenemos|hay)\s+que|(?:debo|debes|deberia)\s+[a-z]+(?:ar|er|ir)|"
    r"i\s+(?:have|need|must|got)\s+to|i'?ve\s+got\s+to|i\s+should)\b"
)
# Revisión M H1: «… a verde y borrá la carpeta Descargas»: a second order joined to the value is never part of it.
_JOINED = re.compile(r"(?:,\s*|\s)(?:y|e|and|then|luego|despues)\s+(?=\S)")


def _not_a_datum(folded: str, said: str) -> bool:
    """Revisión M H3: the fact names a moment (a clock, a span from now, a day that is no date: the temporal readers
    read them), or a task. A date alone («mi cumpleaños es el 5 de mayo») is a datum."""

    folded = _fold(folded)
    if _TASK.search(folded) or temporal.spoken_clocks(folded) or temporal.said_durations(said):
        return True
    return bool(temporal.event_timing(folded).spans) and temporal.spoken_date(folded) is None


def _carries_another_order(folded: str) -> bool:
    return any(
        _head_is(_request_head(folded[joined.end():]), _COVERAGE_ACTION_HEAD) for joined in _JOINED.finditer(folded)
    )


_PREFERENCE = re.compile(r"(?:prefier|prefer|favorit|gusta|like|love|odio|hate)")


def _selector(subject: str) -> str:
    """The stored name of the datum: the App parser's own for the subjects it knows, else the subject's words."""

    folded = _fold(subject).strip(" ,.:")
    known = _subject_selectors().get(folded)
    if known is not None:
        return known
    return re.sub(r"[^a-z0-9]+", "_", folded).strip("_")[:64]


def _correction(low: str) -> tuple[str, int, int, bool] | None:
    """(subject, value start, value end, memory named) of a correction in a folded body, or None."""

    head = _CORRECT_HEAD.match(low)
    if head is None:
        return None
    rest_start = head.end()
    named = False
    thing = _CORRECTED_THING.match(low[rest_start:])
    if thing is not None:
        named = True
        rest_start += thing.end()
    rest_end = len(low.rstrip(" .!?"))
    trailing = _TRAILING_MEMORY.search(low[:rest_end])
    if trailing is not None:
        named = True
        rest_end = trailing.start()
    while rest_start < rest_end and low[rest_start] in " :,":
        rest_start += 1
    rest = low[rest_start:rest_end]
    owner = re.match(r"(?:mi|mis|my)\s+", rest)
    if owner is None:
        return None
    clause = rest[owner.end():]
    # The new value follows the datum's name: «… a verde», «… to green», «…: ahora es Ana», «… ya no es X, ahora es Y».
    # Of the two forms, the one that leaves the shorter name is the datum («mi nombre a Ana, que es más corto»).
    readings = [found for found in (_NOW_VALUE.match(clause), _TO_VALUE.match(clause)) if found is not None]
    if not readings:
        return None
    found = min(readings, key=lambda reading: len(reading.group("subject")))
    subject = found.group("subject").strip(" ,:")
    if not named and _subject_selectors().get(_fold(subject)) not in _subjects()["withoutNamingMemory"]:
        # «cambia mi fondo de pantalla a azul», «actualizá mi proyecto a la versión 2», «fix my project to build»: an
        # order about a thing is no memory. Without naming the memory, only a datum that is nothing but a remembered
        # fact about the person is one (revisión M H1).
        return None
    offset = rest_start + owner.end()
    return subject, offset + found.start("value"), offset + found.end("value"), named


# Estabilización M2 (identity live check 2026-10-11: «Olvidá mi color favorito» and «Borra de tu memoria mi color
# favorito» reached the arguments step and were asked back for internal fields): forgetting one datum, or everything,
# said whole. «olvidá / olvidate de / forget / no te acuerdes de» a datum the memory knows by name; «borrá / eliminá /
# delete …» only with the memory named («de tu memoria», «from your memory»), since a thing of the PC is erased too.
_FORGET_HEAD = re.compile(
    r"^(?:(?:por\s+favor|please)\s*,?\s*)?(?:(?P<forget>olvida|olvidate(?:\s+de)?|forget(?:\s+about)?|"
    r"no\s+te\s+acuerdes\s+(?:mas\s+)?de|deja\s+de\s+recordar)|(?P<erase>borra|borres|elimina|quita|saca|delete|"
    r"remove|erase|clear))\b"
)
_FROM_MEMORY = re.compile(r"^\s*(?:de|from)\s+(?:tu|your)\s+(?:memoria|memory)\b|\s+(?:de|from)\s+(?:tu|your)\s+(?:memoria|memory)\s*$")
_FORGOTTEN_DATUM = re.compile(
    r"^(?P<owned>(?:(?:lo|eso)\s+del?\s+|el\s+dato\s+de\s+)?(?:(?:mi|mis|my)\s+)?)(?P<subject>[a-z][a-z0-9' -]{0,60})$"
)
_EVERYTHING = re.compile(
    r"^(?:todo|todos\s+tus\s+recuerdos|toda\s+tu\s+memoria|everything|all\s+your\s+memories)"
    r"(?:\s+(?:lo\s+que\s+(?:sabes|recuerdas|recordas|tienes\s+guardado)|you\s+(?:know|remember)))?"
    r"(?:\s+(?:de|sobre|about)\s+(?:mi|me))?$"
)


def _forget(low: str) -> dict[str, object] | None:
    """The arguments of a forget said whole in a folded body, or None."""

    head = _FORGET_HEAD.match(low)
    if head is None:
        return None
    rest = low[head.end():].strip(" ,.:!?")
    named = False
    while (found := _FROM_MEMORY.search(rest)) is not None:
        named = True
        rest = (rest[:found.start()] + rest[found.end():]).strip(" ,.:")
    if _EVERYTHING.fullmatch(rest) and (named or rest.endswith((" mi", " me"))):
        # «olvida todo» alone may be this conversation (the App asks which); of the person, or of the memory, is all.
        return {"version": 1, "scope": "all", "selector": None, "confirmationRequired": True}
    said = re.match(r"(?:que\s+)", rest)
    datum = _DATUM.match(rest[said.end():]) if said is not None else None
    subject = datum.group("subject") if datum is not None else None
    if subject is None:
        found = _FORGOTTEN_DATUM.fullmatch(rest)
        # «olvida eso», «forget it» name nothing of the person's: a datum is theirs («mi …», «lo del …») or one the
        # memory knows by name.
        if found is not None and (found.group("owned") or found.group("subject").strip() in _subject_selectors()):
            subject = found.group("subject").strip()
    if not subject:
        return None
    if head.group("erase") and not named or _not_a_datum(subject, subject):
        # «borrá mi cumpleaños» may be a thing of the PC; «olvidá mi reunión de mañana» names a moment, never a datum.
        return None
    # Estabilización M3 (live 2026-10-12: «Olvidá mi color favorito de prueba» was asked «¿Qué alcance deseas
    # eliminar…: todo, exacto, tipo o tema?»): a datum of any length is named as the save named it (``_selector``);
    # the App resolves it against the keys the memory holds before anything is confirmed (MemoryPanel.Candidates).
    return {"version": 1, "scope": "exact", "selector": _selector(subject), "confirmationRequired": True}


def memory_request(text: str) -> tuple[str, dict[str, object]] | None:
    """The save, the correction or the forgetting of a datum said whole, as (operation, arguments); None for anything
    else. «Olvidá mi color favorito», «Borra de tu memoria mi color favorito», «forget everything about me» →
    ``memory.forget`` (the App confirms it before it runs).

    «Recordá que mi color favorito de prueba es el turquesa», «recordame que mi bebida favorita es el mate», «remember
    that my favorite color is teal» → ``memory.save``; «cambiá mi color favorito a verde», «actualizá lo que recordás de
    mi nombre: ahora es Ana», «Corrige ese recuerdo: mi color favorito ya no es el turquesa, ahora es el verde»,
    «update my favorite color to green» → ``memory.correct``. A datum with a moment in it, a secret, or a save of «esto»
    is not read here (the reminder readers, the App's sensitive route, the question).
    """

    body = _request_body_surface(str(text or "")).strip().rstrip(" .!?")
    low = fold_in_place(body)
    if not low.strip():
        return None
    # A secret or a grant of permissions is refused by the App's own value filters (NaturalMemoryRequestParser;
    # revisión M H2: one source), which judge whatever this reader or the model hands it.
    forgotten = _forget(low)
    if forgotten is not None:
        return "memory.forget", forgotten
    corrected = _correction(low)
    if corrected is not None:
        subject, start, end, _named = corrected
        value = body[start:end].strip(" ,.;:!?¿¡«»\"'")
        if not value or _not_a_datum(low[start:end], value) or _carries_another_order(low[start:end]):
            return None
        return "memory.correct", {"selector": _selector(subject), "value": value, "retention": "persistent",
                                  "version": 1}
    head = _SAVE_HEAD.match(low)
    if head is None:
        return None
    fact = body[head.end():].strip(" ,.;:!?¿¡«»\"'")
    fact_low = fold_in_place(fact)
    if (
        not fact or _not_a_datum(fact_low, fact) or _carries_another_order(fact_low)
        or re.fullmatch(r"(?:esto|eso|this|that|it)", fact_low)
    ):
        return None
    datum = _DATUM.match(fact_low)
    if datum is not None:
        selector = _selector(datum.group("subject"))
        value = fact[datum.start("value"):datum.end("value")].strip(" ,.;:!?¿¡«»\"'")
    elif low.startswith(("recordame", "recuerdame")):
        # «recordame que llame a mi mamá» is a reminder: the «-me» form keeps only a datum («mi X es Y»).
        return None
    else:
        selector = "historical_fact_" + hashlib.sha256(_fold(fact).encode("utf-8")).hexdigest()[:16]
        value = fact
    if not value:
        return None
    return "memory.save", {
        "selector": selector, "value": value,
        "kind": "preference" if _PREFERENCE.search(fact_low) else "fact",
        "retention": "persistent", "sensitivity": "normal", "tags": [], "version": 1,
    }
