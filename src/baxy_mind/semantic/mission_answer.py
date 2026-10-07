"""What a computer-use final owes the person beyond the place reached (cu-r17, 2026-10-07).

Live 2026-10-07 (v2 voice audit): the 4B composer wrote «Abrí Configuración.» when Configuración was already running
(every app.open of the mission said alreadyRunning true: it was brought to the front, nothing was opened) and when
the person had asked «decime el volumen» (the answer the window showed was never said). These readers judge the
reply's wording only; the facts they compare it with come from the mission.
"""

from __future__ import annotations

import re

from .normalize import fold

# A first person (or impersonal «se abrió») claim of opening something, folded (no accents, lower case).
_OPEN_CLAIM = re.compile(
    r"\b(?:(?:ya\s+)?(?:te\s+|lo\s+|la\s+|se\s+)?(?:abri|abrio|reabri|he\s+abierto|deje\s+abiert[oa])"
    r"|i\s+(?:just\s+)?(?:opened|reopened|launched|started)|(?:opened|launched))\b"
)
# The generic name of the app a claim of opening may use instead of its own name.
_GENERIC_APP = re.compile(r"\b(?:la\s+)?(?:aplicacion|app|programa|ventana|application|program|window)\b")
# «no lo pude ver», «no se ve», «couldn't see it»: the final says the window did not show the answer.
_NOT_SEEN = re.compile(
    r"\bno\s+(?:\w+\s+){0,2}(?:pude|logre|alcance)\s+(?:\w+\s+){0,2}(?:ver|leer|encontrar)\b|"
    r"\bno\s+(?:se\s+)?(?:ve|veia|muestra|mostraba|aparece|aparecia|vi|encontre|lei)\b|"
    r"\b(?:couldn'?t|could\s+not|can'?t|cannot|didn'?t|did\s+not)\s+(?:\w+\s+){0,2}(?:see|read|find)\b|"
    r"\b(?:isn'?t|is\s+not|wasn'?t|was\s+not)\s+(?:shown|visible|written)\b"
)
_TOKEN = re.compile(r"[a-z0-9]+")
_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
# Content words shorter than this are function words in both languages.
_MIN_WORD = 4


def claims_opening(reply: str, app_names: list[str]) -> bool:
    """True when the reply says it opened the app (by one of ``app_names`` or as «la aplicación») within the words
    that follow the verb."""

    folded = fold(reply)
    names = [fold(name) for name in app_names if isinstance(name, str) and fold(name).strip()]
    for claim in _OPEN_CLAIM.finditer(folded):
        after = folded[claim.end():claim.end() + 60]
        if _GENERIC_APP.match(after.lstrip()) or any(after.lstrip().startswith(prefix + name) for name in names
                                                     for prefix in ("", "el ", "la ", "los ", "las ", "the ")):
            return True
    return False


def says_not_seen(reply: str) -> bool:
    """True when the reply says the window did not show (or BAXY could not read) what was asked."""

    return _NOT_SEEN.search(fold(reply)) is not None


def _words(text: object) -> set[str]:
    return {word for word in _TOKEN.findall(fold(text)) if len(word) >= _MIN_WORD and not word.isdigit()}


# cu-r18 (live v2-c5 «decime si el modo es claro u oscuro» → «El modo es Oscuro.» refused): the words a question
# offers as its answer — the options of «X o Y» and a state asked by «si está activado» — are answers when the window
# shows them, not words already known. A clause that only repeats the question («para ver si es claro u oscuro»)
# answers nothing.
_OPTIONS = re.compile(r"\b([a-z0-9]+)\s+(?:o|u|or)\s+([a-z0-9]+)\b")
_STATE = re.compile(
    r"\b(?:(?:des)?activad[oa]s?|activ[oa]s?|inactiv[oa]s?|encendid[oa]s?|apagad[oa]s?|prendid[oa]s?|"
    r"(?:des)?habilitad[oa]s?|(?:des)?conectad[oa]s?|silenciad[oa]s?|enabled|disabled|active|inactive|"
    r"(?:dis)?connected|muted|turned\s+(?:on|off))\b"
)
_YES_NO_QUESTION = re.compile(r"\b(?:si|if|whether|is|are)\b")
_YES_NO_REPLY = re.compile(r"^\W*(?:si|no|yes)\b\s*[,.;:!]")
_RESTATED = re.compile(
    r"\b(?:(?:ver|saber|revisar|comprobar|mirar|fijarme|confirmar|chequear|averiguar|consultar|decirte)\s+si|"
    r"whether|(?:see|check|know|find\s+out|tell\s+you)\s+if)\b[^.;:!?]*"
)
# A switch's state the window writes as the value's state («on», «off») rather than as text.
_SHOWN_STATES = frozenset({"on", "off", "checked", "unchecked"})


def _question_slots(question: str) -> tuple[list[set[str]], set[str]]:
    """The option groups of «X o Y» and the state words a yes/no question asks about, folded."""

    folded = fold(question)
    groups = [{left, right} for left, right in _OPTIONS.findall(folded) if len(left) >= 3 and len(right) >= 3]
    states = {found.group(0) for found in _STATE.finditer(folded)}
    return groups, states


def gives_an_answer(
    reply: str, shown: list[str], known: list[str], question: str = "", states: list[str] | None = None,
) -> bool | None:
    """Whether the reply says something the window showed that is not merely the place or the app already known.

    ``shown``: every text the window showed at the end; ``known``: the goal, the app, the window title and the clicked
    labels (saying them answers nothing); ``question``: what the person asked — its words are known too, except the
    options and the state it asks about, which answer it when the window shows them; ``states``: the states the
    window's controls showed («on», «off»). None when the window showed nothing beyond the known words (no answer to
    demand)."""

    groups, asked_states = _question_slots(question) if question else ([], set())
    shown_words = set().union(*(_words(text) for text in shown)) if shown else set()
    slots = {word for group in groups for word in group} & shown_words
    shows_a_state = bool(_SHOWN_STATES & {fold(state) for state in states or ()}) or bool(
        _STATE.search(fold(" ".join(shown)))
    )
    if asked_states and shows_a_state:
        slots |= asked_states
    known_words = set().union(*(_words(text) for text in [*known, question])) if known or question else set()
    numbers = {fold(number).replace(",", ".") for text in shown for number in _NUMBER.findall(fold(text))}
    answers = (shown_words - known_words) | slots
    if not numbers and not answers:
        return None
    folded = _RESTATED.sub(" ", fold(reply))
    said = _words(folded) | {found.group(0) for found in _STATE.finditer(folded)}
    for group in groups:
        if group <= said:
            said -= group
    if asked_states and shows_a_state and _YES_NO_REPLY.match(folded) and _YES_NO_QUESTION.search(fold(question)):
        return True
    said_numbers = {number.replace(",", ".") for number in _NUMBER.findall(folded)}
    return bool(said_numbers & numbers) or bool(said & answers)
