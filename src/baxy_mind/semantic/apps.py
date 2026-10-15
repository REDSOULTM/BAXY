"""Applications: open, close, install and query installed programs. Readers moved from effect_intent (Fase 3.5).
"""

from __future__ import annotations

import re
from typing import Callable, Iterable
from . import lexicon
from .grammar import _fold, _match, _has, _strip_request_envelope, _KNOWN_APPLICATION, _OPEN, _LIST, _READ, _CREATE, _SEARCH
from .windows import _CLOSE_WINDOW_WRAPPER
from .intent import _is_negated_match
from .catalog import ApplicationCatalogIndex, build_application_catalog_index


# Owner's test 2026-09-21 (turns 210-213): «BAXY, cierra BAXY» / «cierra BAXY»
# went to window.close on an application named BAXY and ended «no tiene ventana
# abierta». The target is the assistant itself: a vocative before the order is
# not the target, the object after the verb is.
_SELF_CLOSE = re.compile(
    r"(?:^|[\s,;:.!¡¿?]+)"
    r"(?:(?:cierra|cerra|cerrá|cerrar|cerrame|cierrame|cerrate|cierrate|apaga|apagá|apagame|apagate|"
    r"desconecta|desconectate|termina|terminate|sal|salte|salí|close|quit|exit|shut\s+down|shut)\s+"
    r"(?:a\s+)?(?:baxy|la\s+app(?:licacion)?\s+(?:de\s+)?baxy|el\s+asistente|the\s+assistant|"
    r"ti\s+mism[ao]|vos\s+mism[ao]|yourself)"
    r"|(?:cierrate|cerrate|apagate|desconectate|salte|close\s+yourself|shut\s+yourself\s+down|quit\s+yourself))"
    r"(?=$|[\s,;:.!¡¿?])"
)


def self_close_request(text: str) -> bool:
    """«cierra BAXY», «BAXY, cerrate»: the assistant itself is the close target."""

    return _SELF_CLOSE.search(_fold(text)) is not None


_APPLICATION_TRAILING_REQUEST = re.compile(
    r"\s*[,;:]?\s+(?:por favor|please|para mi|for me|ahora|now|"
    r"dale|porfa|porfi|porfis|pls|plz)$",
    re.IGNORECASE,
)


def _application_target_forms(
    raw_target: str,
) -> tuple[tuple[str, int], ...]:
    """Return bounded exact-name candidates before stripping request wrappers."""

    punctuation_forms: list[str] = []
    candidate = raw_target.strip()
    if candidate:
        punctuation_forms.append(candidate)
    for _ in range(8):
        compact = candidate.rstrip()
        if not compact or compact[-1] not in "?!.":
            break
        candidate = compact[:-1].rstrip()
        if candidate and candidate not in punctuation_forms:
            punctuation_forms.append(candidate)
    without_punctuation = raw_target.rstrip(" ?!.")
    if without_punctuation and without_punctuation not in punctuation_forms:
        punctuation_forms.append(without_punctuation)

    execution_hint = re.compile(
        r"\s+(?:(?:con\s+)?maximo\s+\d+\s+intentos?|[0-2])$",
        re.IGNORECASE,
    )
    wrapper = re.compile(
        (
            r"^(?:(?:el|la|los|las|un|una|the|a|an)\s+)?"
            r"(?:(?:aplicacion|application|app|programa|program)\s+)?"
        ),
        re.IGNORECASE,
    )
    forms: list[tuple[str, int]] = []
    for punctuation_form in punctuation_forms:
        bases = [punctuation_form]
        without_trailing = _APPLICATION_TRAILING_REQUEST.sub("", punctuation_form).rstrip()
        if without_trailing and without_trailing != punctuation_form:
            bases.append(without_trailing)
        without_execution_hint = execution_hint.sub("", punctuation_form).rstrip()
        if (
            without_execution_hint
            and without_execution_hint != punctuation_form
            and without_execution_hint not in bases
        ):
            bases.append(without_execution_hint)
        for base in bases:
            if (base, 0) not in forms:
                forms.append((base, 0))
            wrapped = wrapper.match(base)
            if wrapped is None or wrapped.end() <= 0:
                continue
            unwrapped = base[wrapped.end() :].strip()
            if unwrapped and (unwrapped, wrapped.end()) not in forms:
                forms.append((unwrapped, wrapped.end()))
    return tuple(forms)


_CLOSE_TRAILING_COURTESY = re.compile(r"\s*[,;:]?\s+(?:pls|plis|porfa|porfis|for me|para mi)$", re.IGNORECASE)


def _close_target_forms(raw_target: str) -> tuple[tuple[str, int], ...]:
    """Bounded close-target forms: the open forms plus «la ventana de X» / «the X window».

    Offsets index the original target so trailing-courtesy checks stay exact.
    """
    forms = list(_application_target_forms(raw_target))
    stripped = raw_target.rstrip(" ?!.")
    courtesy = _CLOSE_TRAILING_COURTESY.search(stripped)
    if courtesy is not None:
        core = stripped[:courtesy.start()]
        forms.extend((form, offset) for form, offset in _application_target_forms(core))
    for form, offset in list(forms):
        wrapped = _CLOSE_WINDOW_WRAPPER.fullmatch(form)
        if wrapped is None:
            continue
        name = wrapped.group("name") or wrapped.group("name_before")
        start = wrapped.start("name") if wrapped.group("name") else wrapped.start("name_before")
        forms.extend((inner, offset + start + inner_offset) for inner, inner_offset in _application_target_forms(name))
    return tuple(dict.fromkeys(forms))


_DEICTIC_CLOSE_REQUEST = re.compile(
    r"^[¿?¡!\s]*(?:"
    r"(?:cierra|cerra|cerrar|cerrame|cierrame|close)\s+"
    r"(?:"
    r"(?:(?:la|the|esta|this|esa|that)\s+)?(?:ventana|window)\s+(?:activa|active|actual|current)|"
    r"(?:the\s+)?(?:active|current|foreground|front)\s+window|"
    r"(?:esta|this|esa|that)\s+(?:ventana|window)|"
    r"(?:la\s+)?ventana\s+(?:que\s+(?:esta|tengo)\s+)?(?:en\s+)?(?:primer\s+plano|adelante|al\s+frente)|"
    r"(?:the\s+)?window\s+(?:in\s+front|in\s+the\s+foreground|on\s+top)"
    r"))[\s?!.]*$",
    re.IGNORECASE,
)


def deictic_close_request(folded: str) -> bool:
    """«cerrá esta ventana», «close the active window»: close what is in front, named as such.

    The referent is the foreground window, which window.active observes and
    the reviewed confirmation names before anything closes. A referent from
    earlier dialogue («la que te mencioné antes») is not deictic here, and
    neither is a bare pronoun («cerrala», «cierra eso», «close it»): it points
    back at what the conversation named (``bare_close_pronoun``), else it is
    asked (Estabilización X2: read here, a first «ya ciérrala» was planned as
    the close of the window in front).
    """

    return _DEICTIC_CLOSE_REQUEST.match(folded) is not None


# M96 (held-out t11 «cerralo» right after «abrí el bloc de notas», 28/30 oscillating): the pronoun alone, with the
# fillers said around it (``lexicon.POINTER_LINK``, its view of the one list since r31). Never «esta ventana» or «the
# active window»: those name the window in front.
_BARE_CLOSE_PRONOUN = re.compile(
    rf"^[¿¡\s]*(?:{lexicon.POINTER_LINK}\b[\s,.;:!]*)*"
    r"(?:(?:puedes|podes|podrias|can\s+you|could\s+you|would\s+you)\s+)?"
    r"(?:(?:cierr|cerr)[ae](?:me|te)?(?:lo|la)|cerrarlo|cerrarla|"
    r"(?:cierra|cierre|cerra|cerrar)\s+(?:eso|esto|aquello)|"
    r"(?:lo|la)\s+(?:cierras|cerras|cierra|cierre)|"
    r"(?P<english>(?:close|shut|quit)\s+(?:it|that|this)(?:\s+(?:one|app|down))?))"
    r"(?:[\s,.;:!]+(?:ya|ahora|porfa|por\s+favor|please|now|then|entonces|tambien|too|nomas|pues))*"
    r"[\s?!.]*$"
)


_ACTIVE_WINDOW = re.compile(
    r"\b(?:(?:la\s+)?ventana\s+(?:activa|actual|en\s+primer\s+plano|de\s+adelante|del\s+frente|que\s+tengo\s+abierta)|"
    r"(?:the\s+)?(?:active|current|front|foreground|focused)\s+(?:window|app|application)|"
    r"(?:la\s+)?(?:app|aplicacion|programa)\s+(?:activa|actual|en\s+primer\s+plano))\b"
)


def names_the_active_window(text: str) -> bool:
    """M118: a request that names the window in front («Cierra la ventana activa.», «close the current window»)."""

    return _ACTIVE_WINDOW.search(_fold(str(text or ""))) is not None


# M145: «esta ventana», «this window» — the window noun pointed at here, never a window «de X» / «of X» another reader
# names. «esa ventana» / «that window» and a bare pronoun («ponla», «snap it», «cerralo») are not here: they may point
# back at something the conversation named (M96, M118).
_POINTED_WINDOW = re.compile(r"\b(?:esta|this)\s+(?:ventana|window)\b(?!\s+(?:de|del|of)\b)")


def names_the_window_in_front(text: str) -> bool:
    """M145 (DEV-G v4p G-s041 «pasame esta ventana a la mitad izquierda», G-s082, G-s102; DEV-H H-s028): a change of
    a window that names the one in front — «esta ventana», «this window», «la ventana activa», «the current window».
    Only for a change that loses nothing (snap, move, maximize, minimize, restore); a close keeps M118's rule."""

    folded = _fold(str(text or ""))
    return _ACTIVE_WINDOW.search(folded) is not None or _POINTED_WINDOW.search(folded) is not None


def bare_close_pronoun(folded: str) -> tuple[bool, bool]:
    """«cerralo», «ya, ciérrala», «ok close that»: (closes what a pronoun points at, said in English)."""

    found = _BARE_CLOSE_PRONOUN.match(folded)
    return found is not None, found is not None and found.group("english") is not None


def close_request_for_opened(opened: str, english: bool) -> str:
    """The close of what an open read named, in the person's words: «abre la calculadora» → «Cierra la calculadora»,
    «notepad» → «Close notepad». The open verb the reader may keep is replaced, never the application's name."""

    name = re.sub(rf"^\s*{_OPEN}(?:me)?\s+", "", opened.strip(), count=1, flags=re.IGNORECASE)
    name = re.sub(r"[\s,]+(?:por\s+favor|porfa|please)[\s.!]*$", "", name, flags=re.IGNORECASE).strip(" .,!")
    return f"{'Close' if english else 'Cierra'} {name}"


def _bounded_application_literal(candidate: str) -> str | None:
    """Keep literal presence queries bounded without asserting membership."""

    # A pronoun without catalog identity is not an application-name query.
    # Keep it unresolved rather than asking the provider about a literal "it".
    if _has(
        _fold(candidate),
        r"^(?:(?:esta|esa|aquella|this|that)\s+"
        r"(?:app|aplicacion|application|programa|program)|"
        r"esto|eso|esta|esa|aquella|it|this|that|them|esas|aquellas)$",
    ):
        return None
    # A relative clause or its subject still needs an antecedent; it is not
    # an unfamiliar literal identifier that a catalog can prove absent.
    if _has(
        _fold(candidate),
        r"^(?:(?:el|la|lo|los|las|the)\s+)?"
        r"(?:que|cual|cuales|quien|which|that|who|you|i|we|he|she|they)\b",
    ):
        return None

    # The provider's schema accepts at most 256 UTF-8 bytes and independently
    # verifies both presence and absence.  Reject clause syntax, control
    # characters and generic nouns so only one bounded literal reaches it.
    literal = candidate.strip(" \t\r\n\"'“”")
    if (
        not literal
        or len(literal.encode("utf-8")) > 256
        or any(ord(character) < 32 for character in literal)
        or _has(literal, r"(?:[;,]|\b(?:y|and|then|luego|despues)\b)")
        or _has(
            literal,
            r"^(?:app|application|aplicacion|program|programa|software|"
            r"installed\s+apps?|aplicaciones?\s+instaladas?)$",
        )
    ):
        return None
    return literal


def _authenticated_application_list(
    text: str,
    application_names: Iterable[str] | ApplicationCatalogIndex,
    *,
    installed_query: bool = False,
) -> tuple[tuple[int, str], ...]:
    """Recognize an exact coordinated list of authenticated app names."""

    occurrence_pattern = build_application_catalog_index(
        application_names,
    ).occurrence_pattern
    spans = (
        [
            (found.start(), found.end(), found.group("target"))
            for found in occurrence_pattern.finditer(text)
        ]
        if occurrence_pattern is not None
        else []
    )
    if len(spans) < 2:
        return ()
    connector = (
        r"\s*(?:"
        r",\s*(?:(?:y|and)(?:\s+(?:luego|despues|then|afterwards))?)?"
        r"|(?:y|and)(?:\s+(?:luego|despues|then|afterwards))?"
        r")\s*"
        r"(?:(?:el|la|los|las|the)\s+)?"
        r"(?:(?:aplicacion|application|app|programa|program)\s+)?"
    )
    if any(
        re.fullmatch(
            connector,
            text[prior[1] : later[0]],
            re.IGNORECASE,
        )
        is None
        for prior, later in zip(spans, spans[1:])
    ):
        return ()
    prefix = text[: spans[0][0]]
    suffix = text[spans[-1][1] :]
    if installed_query:
        prefix_first = _has(
            prefix,
            (
                r"^[¿?¡!\s]*(?:esta|estan|is|are)\s+"
                r"(?:instalad[oa]s?|installed)\s+"
                r"(?:(?:el|la|los|las|the)\s+)?$"
            ),
        ) and _has(suffix, r"^[\s?!.]*$")
        suffix_last = _has(
            prefix,
            r"^[¿?¡!\s]*(?:esta|estan|is|are)\s+$",
        ) and _has(
            suffix,
            r"^\s+(?:instalad[oa]s?|installed)[\s?!.]*$",
        )
        valid = prefix_first or suffix_last
    else:
        valid = _has(
            prefix,
            (
                r"^[¿?¡!\s]*(?:(?:por favor|please)\s*[,;:]?\s*|"
                r"(?:puedes|podrias|can you|could you|would you)\s+)?"
                rf"{_OPEN}\b\s+(?:(?:el|la|the)\s+)?"
                r"(?:(?:aplicacion|application|app|programa|program)\s+)?$"
            ),
        ) and _has(
            suffix,
            (
                r"^(?:\s+(?:por favor|please|para mi|for me|ahora|now))?"
                r"[\s?!.]*$"
            ),
        )
    if not valid:
        return ()
    return tuple((start, key) for start, _, key in spans)


_OPEN_STATE_CONDITION = (
    r"^[¿?¡!\s]*(?:si|if)\s+(?:(?:tengo|esta|hay|i\s+have|there\s+is|is)\s+)?"
    r"(?:(?:el|la|the)\s+)?(?P<app>[a-z0-9][a-z0-9 .+-]{1,30}?)\s+"
    r"(?:(?:esta|is)\s+)?(?:abiert[oa]|open|running|corriendo|prendid[oa]|activ[oa])\s*,?\s*"
)

# Ronda 19 (revisión 3): any condition on whether an application is there now, said anywhere in the request and with
# any of its leads —«si», «solo si», «only if», «en caso de que», «siempre que», «mientras», «as long as», «provided»,
# «in case», «while»— or with an inverted one —«unless», «a menos que», «salvo que», «excepto si»—. The predicate
# follows the lead within a few words of the same clause: an open state («si tengo el word abierto», «if word's open»,
# «if chrome is still up», «si el word está en pantalla»), a closed one («si está cerrado», «if it's closed») or plain
# presence («si hay una ventana de word», «if there's a word window», «si lo encontrás», «solo si lo tengo», «if it's
# there», «y si no está, nada»).
_PRESENT_STATE_LEADS = (
    r"(?:(?:solo|only|just)\s+)?(?:si|if)",
    r"en\s+caso\s+de(?:\s+que)?",
    r"siempre\s+(?:y\s+cuando|que)",
    r"mientras(?:\s+que)?",
    r"as\s+long\s+as",
    r"provided(?:\s+that)?",
    r"in\s+case",
    r"while",
)
# Leads that invert the predicate: «a menos que esté cerrado» is the condition that it is there.
_PRESENT_STATE_INVERTED_LEADS = (
    r"unless",
    r"a\s+menos\s+que",
    r"salvo\s+(?:que|si)",
    r"excepto\s+(?:que|si|cuando)",
    r"except\s+(?:if|when)",
)
# The predicate that the application is there now.
_PRESENT_STATE_WORDS = (
    r"abiert[oa]s?",
    r"opened",
    r"running",
    r"corriendo",
    r"prendid[oa]s?",
    r"activ[oa]s?",
    r"ejecutandose",
    r"en\s+ejecucion",
    r"en\s+pantalla",
    r"on\s+(?:the\s+)?screen",
    r"visible",
    r"up",
    r"there",
    r"ahi",
    r"alli",
    r"hay",
    r"existen?",
    r"exists?",
    r"ten(?:go|es|emos|er|ga|gas|gan)",
    r"tien(?:es|e|en)",
    r"have",
    r"has",
    r"encontr(?:as|es|aste|e)",
    r"encuentr(?:as|es|a|o|en)",
    r"find",
    r"found",
    r"ves",
    r"veo",
    r"sees?",
)
# «open» is the state only when no object follows it: «if you can open it» / «si podes, open the app» are the order.
_PRESENT_STATE_OPEN = r"open(?!\s+(?:it|them|the|a|an|my|up)(?![a-z]))"
# «está» / «is» closing the clause is presence too: «y si no está, nada», «if it isn't, skip it».
_PRESENT_STATE_CLAUSE_END = r"(?:esta|is|isn't)(?=\s*(?:[,;:.!?]|$))"
# The predicate that the application is not there.
_ABSENT_STATE_WORDS = (
    r"cerrad[oa]s?",
    r"closed",
    r"apagad[oa]s?",
    r"shut",
)
# Words of the clause that negate its predicate («si word no esta abierto», «if chrome isn't open», «if you don't have
# it», «si ya no tengo el chrome»); any word ending in «n't» negates too.
_PRESENT_STATE_REVERSERS = frozenset(("no", "not", "nunca", "never", "ni", "cannot"))
# A negation right after the predicate: «if there's no word window», «if there isn't one», «if you have none».
_PRESENT_STATE_NEGATED_AFTER = re.compile(r"(?:'s|\s+(?:is|are))?\s+(?:no|not|none|isn't|aren't)(?![a-z])")
_PRESENT_STATE_CONDITION = re.compile(
    r"(?:^|[\s,;:¿?¡!(])(?:(?P<inverted>" + "|".join(_PRESENT_STATE_INVERTED_LEADS) + r")|"
    + "|".join(_PRESENT_STATE_LEADS) + r")"
    r"(?P<between>(?:\s+[a-z0-9.+'-]+){0,6}?)"
    r"(?:\s+|'s\s+)(?:(?P<absent>" + "|".join(_ABSENT_STATE_WORDS) + r")|(?P<predicate>"
    + "|".join(_PRESENT_STATE_WORDS) + "|" + _PRESENT_STATE_OPEN + "|" + _PRESENT_STATE_CLAUSE_END + r"))(?![a-z])"
)

# Ronda 19 (revisión 2): an order not to open what is absent —«no lo abras», «sin abrirlo», «don't open it»,
# «without opening it»—. Then the window read is again the only check: what is absent stays closed.
_OPENING_FORBIDDEN = re.compile(
    r"(?:^|[\s,;:¿?¡!(])(?:"
    r"no\s+(?:me\s+|te\s+)?(?:l[oa]s?\s+)?(?:re)?abr(?:as|a|an|ais|ir)"
    r"|sin\s+(?:re)?abrir(?:l[oa]s?)?"
    r"|nunca\s+(?:l[oa]s?\s+)?(?:re)?abras"
    r"|(?:don't|do\s+not|never)\s+(?:re)?open"
    r"|without\s+(?:re)?opening"
    r")(?![a-z])"
)

# Ronda 19 (revisión 3): an order to open or start what is absent —«abrilo», «ábrelo», «que se abra», «hay que abrirlo»,
# «prendelo», «open it», «, open word», «launch it», «start it»—: the opening is the consequence the person asked for.
_OPENING_ORDERED = re.compile(
    r"(?<![a-z])(?:re)?abr(?:i|e|a|ir)(?:l[oa]s?|me(?:l[oa])?)?(?![a-z])"
    r"|(?<![a-z])(?:lanz|ejecut|inici|arranc|prend)[ae]l[oa]s?(?![a-z])"
    r"|(?:^|[,;:.!?]\s*|(?<![a-z])(?:and|then|please|just|first|so|otherwise|else|but|y|pero|entonces|sino)\s+)"
    r"(?:re)?(?:open|launch|start)(?![a-z])"
    r"|(?<![a-z])(?:re)?(?:open|launch|start)\s+(?:it|them|up)(?![a-z])"
)

# Ronda 19 (revisión 3): the request says what to do when the condition fails —«si no», «sino», «otherwise», «else»,
# «if not», «de lo contrario», «if needed», «si hace falta»—: an order to open there is the opening the person wants;
# without it, an opening of another thing («si está abierto ponelo a la izquierda y abrí chrome») is not that one.
_CONDITION_FAILS = re.compile(
    r"(?<![a-z])(?:si\s+no|sino|if\s+not|otherwise|else|de\s+lo\s+contrario|(?:en\s+)?caso\s+contrario"
    r"|if\s+(?:needed|necessary)|si\s+(?:hace\s+falta|es\s+necesario)|de\s+ser\s+necesario)(?![a-z])"
)

# Ronda 19 (revisión 3): the person abstains when the condition fails —«no hagas nada», «dejalo», «olvidalo», «nada»,
# «never mind», «skip it», «leave it», «don't do anything»—.
_ABSTENTION = re.compile(
    r"(?<![a-z])(?:"
    r"no\s+(?:hagas|haga|hagan|haces|hace|hacer|toques|toque)(?:\s+nada)?"
    r"|nada|dejal[oa]s?|olvidal[oa]s?|olvidate|ignoral[oa]s?|saltal[oa]s?|saltealo"
    r"|no\s+importa|da\s+igual"
    r"|never\s*mind|skip(?:\s+it)?|leave\s+it|forget(?:\s+about)?\s+it|ignore\s+it"
    r"|(?:don't|do\s+not)\s+(?:do\s+anything|bother|touch)|do\s+nothing|nothing"
    r")(?![a-z])"
)


def _condition_holds_on_presence(match: re.Match[str]) -> bool:
    """Whether one condition read by ``_PRESENT_STATE_CONDITION`` holds when the application is there: its predicate,
    negated by a word of its clause («no», «not», «n't») and inverted by its lead («unless», «a menos que»)."""

    tokens = match.group("between").split()
    if match.group("predicate"):
        tokens.append(match.group("predicate"))
    holds = not any(token in _PRESENT_STATE_REVERSERS or token.endswith("n't") for token in tokens)
    if _PRESENT_STATE_NEGATED_AFTER.match(match.string, match.end()) is not None:
        holds = not holds
    if match.group("absent"):
        holds = not holds
    if match.group("inverted"):
        holds = not holds
    return holds


def present_state_condition(text: str) -> bool:
    """Ronda 19 (MUSIC1675, CLOSE1371, revisiones 2 y 3): the request is conditioned on an application being there now,
    or forbids opening it, so the window read IS the check and no window means nothing is done: what is absent is never
    opened to satisfy it.

    - An order not to open it: «pon word a la izquierda sin abrirlo», «put word on the left, don't open it».
    - Otherwise an order to open it when the condition fails makes the opening the consequence: «si no está abierto,
      abrilo», «if word is closed, open it and snap it left», «si está abierto ponelo a la izquierda, si no abrilo» are
      not this condition; an opening of another thing («si está abierto ponelo a la izquierda y abrí chrome») keeps it.
    - A condition that it is there: «si tengo word abierto», «only if chrome is open», «si hay una ventana de word»,
      «if you find it», «snap word left unless it is closed», «pon word a la izquierda salvo que esté cerrado».
    - A condition that it is not there with the person abstaining: «si no está abierto no hagas nada», «if it's not
      running, skip it», «if word is closed don't do anything, otherwise snap it left». Without the abstention («snap
      chrome to the right if it isn't open») the request does not forbid the opening.
    """

    folded = _strip_request_envelope(_fold(text or "")).replace("’", "'").replace("‘", "'")
    if _OPENING_FORBIDDEN.search(folded) is not None:
        return True
    conditions = tuple(_PRESENT_STATE_CONDITION.finditer(folded))
    if not conditions:
        return False
    on_presence = tuple(_condition_holds_on_presence(match) for match in conditions)
    opening_ordered = _OPENING_ORDERED.search(folded) is not None
    if opening_ordered and (not all(on_presence) or _CONDITION_FAILS.search(folded) is not None):
        return False
    return any(on_presence) or _ABSTENTION.search(folded) is not None


_CLOSE_ALL_REQUEST = re.compile(
    r"^[¿?¡!\s]*(?:(?:por\s+favor|please)\s*[,;:]?\s*)?"
    r"(?:cierra|cerra|cerrar|cerrame|cierrame|close)\s+(?:me\s+)?"
    r"(?:todas\s+(?:las\s+)?(?:ventanas|apps|aplicaciones|cosas)|todo|todo\s+lo\s+que\s+(?:esta|tengo)\s+abierto|"
    r"all(?:\s+(?:the|my|of\s+the))?(?:\s+(?:windows|apps|applications))?|everything(?:\s+(?:that\s+is\s+)?open)?)"
    r"(?:\s+(?:abiertas|abierto|open))?(?:\s*,?\s*(?:por\s+favor|please))?[\s.!?]*$"
)


def close_all_request(folded: str) -> bool:
    """CLOSEALL1733 «cerrame todo», «cerrá todas las ventanas», «close everything»:
    one order over every desktop window (never a named one, never tabs)."""

    return _CLOSE_ALL_REQUEST.match(_strip_request_envelope(folded)) is not None


def _has_multiple_installed_entities(text: str) -> bool:
    return (
        _has(text, r"\b(?:instalad[oa]s?|installed)\b")
        and _has(text, r"\b(?:en|on)\s+steam\b")
        and _has(text, r"\b(?:y|and)\b")
        and not _has(text, r"\b(?:juegos|games)\b")
    )


def _append_domain_actions(
    matches: list[tuple[int, int, str]],
    text: str,
    action_pattern: str,
    operation_by_domain: dict[str, str],
) -> int:
    """Bind an action to each explicitly coordinated local-data domain."""

    domain_patterns = {
        "note": r"\b(?:nota|notas|note|notes|memo|memos)\b",
        "task": r"\b(?:tarea|tareas|task|tasks|pendiente|pendientes)\b",
        "reminder": r"\b(?:recordatorio|recordatorios|reminder|reminders)\b",
        "routine": r"\b(?:rutina|rutinas|routine|routines)\b",
    }
    next_action = (
        rf"(?:{_CREATE}|{_SEARCH}|{_LIST}|{_READ}|{_OPEN}|"
        r"maximiza|minimiza|restaura|navigate|navega)"
    )
    boundary_pattern = (
        rf"[,;.!?]|\b(?:despues|luego|then|and then|y despues|y luego)\b|"
        rf"\by\s+(?={next_action}\b)"
    )
    appended = 0
    for action in re.finditer(rf"\b{action_pattern}\b", text, re.IGNORECASE):
        if _is_negated_match(text, action):
            continue
        suffix = text[action.end() :]
        boundary = re.search(boundary_pattern, suffix, re.IGNORECASE)
        fragment = suffix[: boundary.start()] if boundary is not None else suffix[:160]
        candidates: list[tuple[int, int, str]] = []
        for domain, noun_pattern in domain_patterns.items():
            if domain not in operation_by_domain:
                continue
            for noun in re.finditer(noun_pattern, fragment, re.IGNORECASE):
                candidates.append((noun.start(), noun.end(), domain))
        if not candidates:
            continue
        candidates.sort(key=lambda item: item[0])
        first_start, first_end, first_domain = candidates[0]
        selected = [(first_start, first_end, first_domain)]
        seen_domains = {first_domain}
        previous_end = first_end
        for start, end, domain in candidates[1:]:
            if domain in seen_domains:
                continue
            connector = fragment[previous_end:start]
            plain_coordination = _has(
                connector,
                (
                    r"^\s*(?:,\s*)?(?:y|and)\s+"
                    r"(?:(?:una?|an?|el|la|los|las|the|mis?|my)\s+)*$"
                ),
            )
            labeled_coordination = action_pattern == _CREATE and _has(
                connector,
                (
                    r"^\s+(?:llamad[oa]|titulad[oa]|named|called)\s+"
                    r"[^,;.!?]{1,80}\s+(?:y|and)\s+"
                    r"(?:(?:una?|an?|el|la|los|las|the|mis?|my)\s+)*$"
                ),
            )
            if not (plain_coordination or labeled_coordination):
                break
            selected.append((start, end, domain))
            seen_domains.add(domain)
            previous_end = end
        for index, (start, _, domain) in enumerate(selected):
            matches.append(
                (
                    action.start() if index == 0 else action.end() + start,
                    0,
                    operation_by_domain[domain],
                )
            )
            appended += 1
    return appended


def _open_application_spans(text: str) -> tuple[tuple[int, str], ...]:
    request = _match(
        text,
        (
            r"^[¿?¡!\s]*(?:(?:por favor|please)\s*[,;:]?\s*|"
            r"(?:puedes|podrias|can you|could you|would you)\s+)?"
            rf"(?:{_OPEN}|necesito|quiero|i\s+need|i\s+want)\b(?:\s+(?:el|la|the|un|una|a))?\s+"
            rf"(?:(?:aplicacion|application|app|programa|program)\s+)?"
            rf"(?P<body>{_KNOWN_APPLICATION}"
            rf"(?:\s*,\s*(?:el|la|the)?\s*{_KNOWN_APPLICATION})*)"
            r"(?:,?\s+(?:por favor|please|ahora|now))?[\s?!.]*$"
        ),
    )
    if request is None or _is_negated_match(text, request):
        return ()
    body = request.group("body")
    base = request.start("body")
    applications: list[tuple[int, str]] = []
    for found in re.finditer(_KNOWN_APPLICATION, body, re.IGNORECASE):
        app = found.group(0).casefold()
        app = {
            "opera gx": "opera_gx",
            "google chrome": "chrome",
            "microsoft edge": "edge",
        }.get(app, app)
        applications.append((base + found.start(), app))
    return tuple(applications)


_CATALOG_INSTALL_VERB = (
    r"(?:instala|instalar|instalame|instalate|install|descarga|descargar|descargame|download|baja|bajar|bajame|"
    r"desinstala|desinstalar|desinstalame|desinstalate|uninstall|"
    # «quitá 7-Zip», «sacá VLC», «eliminá 7-Zip», «remove 7zip»: the same removal.
    r"quita|quitar|quitame|saca|sacar|sacame|elimina|eliminar|eliminame|remove|remueve)"
)


def _opened_applications(text: str) -> tuple[str, ...]:
    applications = [application for _, application in _open_application_spans(text)]
    return tuple(applications)


def asks_to_close(user_text: str | None, *, voseo: bool = False) -> bool:
    """«cierra…», «close…» (and with ``voseo`` the imperative «cerrá»): the request asked to close something.

    The composer's check reads «cierr/close» and its hint also «cerrá»; both readings are kept as they were."""

    pattern = r"\bcierr|\bcerr[aá]\b|\bclose\b" if voseo else r"\bcierr|\bclose\b"
    return re.search(pattern, (user_text or "").casefold()) is not None


def object_asked_to_close(user_text: str | None) -> str | None:
    """The word right after the close verb («cierra Opera» → «opera»), folded, or None."""

    found = re.search(
        r"\b(?:cierr[ae]|cerr[aá]|close|quit)\s+(?:el|la|los|las|the|a)?\s*([a-záéíóúñ0-9][\w+.-]*)",
        _fold(user_text or ""),
    )
    return found.group(1) if found is not None else None


def asks_to_install_or_remove(user_text: str | None) -> bool:
    """Installing, uninstalling or downloading a program was asked (INSTALL1625)."""

    return re.search(
        r"\b(?:instal|install|desinstal|uninstall|descarg|download|baj[aá])",
        (user_text or "").casefold(),
    ) is not None


def wants_to_work_in_it(user_text: str | None) -> bool:
    """«quiero editar una foto en photoshop»: working in a program, not opening it (APPS1671)."""

    folded = (user_text or "").casefold()
    return bool(
        re.search(r"\b(?:editar|retocar|usar|trabajar|edit|retouch|use|work)\b", folded)
        and not re.search(r"\b(?:abr[ií]|abre|open)", folded)
    )


def asks_new_document(
    text: str | None,
    names_the_application: Callable[[str], bool] | None = None,
    names_another_application: Callable[[str], bool] | None = None,
    nouns: frozenset[str] | None = None,
) -> bool:
    """«un bloc de notas nuevo», «abre un documento nuevo de word», «crea un blank workbook», «otro documento»: the
    person asked for a new document of what is opened, never one of theirs already open (uso real t4-r6 c14, c06). A
    marker (``lexicon.NEW_DOCUMENT_MARKERS``) right next to a document noun (``lexicon.DOCUMENT_NOUNS``) or to the
    application's own name (``names_the_application``: whether some words name the application opened), led by a word
    that asks for one that does not exist yet (``lexicon.NEW_DOCUMENT_INDEFINITE``; review of cu-v3-documento-nuevo,
    finding 3: «el documento nuevo que hice», «mi nota nueva», «el nuevo outlook» point at what is there). A noun is the
    opened application's document unless the text names another application, or this one only as where something comes
    from (``names_another_application``), and no
    «de/en X» ties the document to this one (finding 2: «copia de chrome y pegalo en un bloc de notas nuevo» asks
    nothing new of Chrome). «abrí el bloc de notas», «pegá en mi nota de compras» and «abre de nuevo el bloc de notas»
    ask for none. ``nouns``: the document kinds that count (``lexicon.DOCUMENT_NOUNS`` by default; revisión 2 de r24b,
    B1: ``lexicon.WHOLE_DOCUMENT_NOUNS`` where a part of a document or a folder's item must not count)."""

    tokens = re.findall(r"[a-z0-9]+", _fold(text or ""))
    grammar = lexicon.NEW_DOCUMENT_GRAMMAR_WORDS
    kinds = lexicon.DOCUMENT_NOUNS if nouns is None else nouns

    def names_application(span: list[str]) -> bool:
        return (
            bool(span) and span[0] not in grammar and span[-1] not in grammar
            and names_the_application is not None and names_the_application(" ".join(span))
        )

    def phrase_at(position: int) -> bool:
        return tuple(tokens[position:position + 2]) in lexicon.NEW_DOCUMENT_AFTER_PHRASES

    def lead_allows(position: int, plain: bool) -> bool:
        lead = tokens[position] if position >= 0 else ""
        if lead in lexicon.NEW_DOCUMENT_THEIRS:
            return False
        return lead in lexicon.NEW_DOCUMENT_INDEFINITE or lead in lexicon.NEW_DOCUMENT_BEFORE_ONLY or plain

    def of_this_application(after: int) -> bool:
        """A document said by its kind is the opened application's: «de/en X» right after it names this one, or the
        text names no other."""

        if after < len(tokens) and tokens[after] in lexicon.NEW_DOCUMENT_OF:
            rest = tokens[after + 1:after + 5]
            if any(names_application(rest[:size]) for size in range(1, len(rest) + 1)):
                return True
        return names_another_application is None or not names_another_application(text or "")

    for index, token in enumerate(tokens):
        after_phrase = phrase_at(index)
        marker = token in lexicon.NEW_DOCUMENT_MARKERS
        before_only = token in lexicon.NEW_DOCUMENT_BEFORE_ONLY
        if not (marker or after_phrase or before_only):
            continue
        if marker and index > 0 and tokens[index - 1] in lexicon.NEW_DOCUMENT_AGAIN_LEAD:
            continue
        said = "en blanco" if after_phrase else token
        if not after_phrase:
            # Said before the document: «un nuevo documento», «a new blank document», «otro bloc de notas».
            plain = said in lexicon.NEW_DOCUMENT_PLAIN_MARKERS
            start = index + 1
            while start < len(tokens) and (tokens[start] in lexicon.NEW_DOCUMENT_MARKERS or phrase_at(start)):
                plain = plain or tokens[start] in lexicon.NEW_DOCUMENT_PLAIN_MARKERS or phrase_at(start)
                start += 2 if phrase_at(start) else 1
            led = (
                index == 0 or tokens[index - 1] not in lexicon.NEW_DOCUMENT_THEIRS
                if before_only
                else lead_allows(index - 1, plain)
            )
            if led:
                if start < len(tokens) and tokens[start] in kinds and of_this_application(start + 1):
                    return True
                if any(names_application(tokens[start:start + size]) for size in range(1, 5)):
                    return True
        if marker or after_phrase:
            # Said after the document: «un bloc de notas nuevo», «un excel en blanco».
            end = index + (2 if after_phrase else 1)
            plain = said in lexicon.NEW_DOCUMENT_PLAIN_MARKERS
            for size in range(1, min(4, index) + 1):
                span = tokens[index - size:index]
                if span[0] in grammar or not lead_allows(index - size - 1, plain):
                    continue
                if size == 1 and span[0] in kinds:
                    if of_this_application(end):
                        return True
                    continue
                if names_application(span):
                    return True
    return False
