"""Applications: open, close, install and query installed programs. Readers moved from effect_intent (Fase 3.5).
"""

from __future__ import annotations

import re
from typing import Iterable
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
    r"(?:the\s+)?window\s+(?:in\s+front|in\s+the\s+foreground|on\s+top)|"
    r"esto|eso|this|that|it"
    r")|"
    r"cierrala|cierralo|cerrala|cerralo|close\s+it"
    r")[\s?!.]*$",
    re.IGNORECASE,
)


def deictic_close_request(folded: str) -> bool:
    """«cerrá esta ventana», «cerrala», «close the active window»: close what is in front.

    The referent is the foreground window, which window.active observes and
    the reviewed confirmation names before anything closes. A referent from
    earlier dialogue («la que te mencioné antes») is not deictic here.
    """

    return _DEICTIC_CLOSE_REQUEST.match(folded) is not None


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
