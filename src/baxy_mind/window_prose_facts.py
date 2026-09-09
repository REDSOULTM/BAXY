"""Conserve typed window observations without treating processes as observed.

This is part of the existing prose contract, not a second narrator or model.
Checks bind predicates and quantities to their observed field; names and an
explicit admission of unknown process state are not process assertions.
"""
from __future__ import annotations

import re

from .effect_intent import _PERCENTAGE_WORD_VALUES
from .request_reading import fold


_CARDINALS = {**_PERCENTAGE_WORD_VALUES, "a": 1, "an": 1, "una": 1,
              "no": 0, "ninguna": 0, "ningunas": 0}
_NUMBER = r"(?:\d+|" + "|".join(
    re.escape(word).replace(r"\ ", r"[\s-]+")
    for word in sorted(_CARDINALS, key=len, reverse=True)
) + r")"
_COUNT = re.compile(
    r"\b(?:(?P<bound>at least|at most|more than|less than|fewer than|"
    r"al menos|como maximo|mas de|menos de)\s+)?"
    rf"(?P<number>{_NUMBER})\s+(?:(?:visible|open|visibles?|abiertas?)\s+)?"
    r"(?:windows?|ventanas?)\b"
)
_INSTALLATION = re.compile(
    r"\b(?:(?P<negative>not|isn['’]t|isnt|hasn['’]t been|has not been|no)\s+)?"
    r"(?:(?:is|are|esta|estan|se encuentra|se encuentran)\s+)?"
    r"(?P<after>not\s+)?instal(?:led|ad[oa]s?)\b"
)
_NO_WINDOWS = re.compile(
    r"\b(?:no\s+(?:tiene|hay)|does\s+not\s+have|doesn't\s+have|without|sin)\s+"
    r"(?:(?:any|ninguna|ningunas|visible|visibles)\s+)*(?:windows?|ventanas?)\b"
)
_HAS_WINDOWS = re.compile(
    r"\b(?:has|have|tiene|hay)\s+(?:(?:visible|visibles|open|abiertas)\s+)?"
    r"(?:windows|ventanas)\b"
)
_PROCESS_STATE = re.compile(
    r"\b(?:is|isn['’]t|isnt|is not|are|aren['’]t|are not|"
    r"(?:it|that)['’]s|esta|no esta|estan|no estan|sigue|no sigue|and|y)\s+"
    r"(?:(?:not|currently|still|aun|todavia)\s+)*"
    r"(?:running|executing|ejecutandose|en ejecucion|en marcha|en segundo plano)\b|"
    r"\b(?:process(?:es)?|procesos?)\s+(?:no\s+)?(?:is|are|esta|estan)\s+(?:not\s+)?"
    r"(?:active|inactive|stopped|activ[oa]s?|inactiv[oa]s?|detenid[oa]s?)\b"
)
_UNCERTAINTY = re.compile(
    r"\b(?:(?:i\s+)?(?:cannot|can['’]t|can not)\s+(?:tell|confirm|determine|know)|"
    r"(?:i\s+)?(?:do not|don['’]t)\s+know|no\s+(?:se|comprobe|he comprobado)|"
    r"no\s+puedo\s+(?:saber|confirmar|determinar)|desconozco)\b"
)
_SEPARATORS = re.compile(r"([.;!?]|\b(?:but|pero|and|y)\b)")


def _seen(payload: dict) -> dict | None:
    seen = payload.get("seen")
    if (
        payload.get("operation") != "window.application.status"
        or not isinstance(seen, dict)
        or not isinstance(seen.get("installed"), bool)
        or type(seen.get("visibleWindowCount")) is not int
        or seen["visibleWindowCount"] < 0
    ):
        return None
    return seen


def window_status_assertions(
    text: str, payload: dict, *, require_window_answer: bool = False,
) -> str:
    """Only for validation: omit process uncertainty, retaining other clauses."""
    if _seen(payload) is None:
        return text
    parts = _SEPARATORS.split(fold(text))
    for index in range(0, len(parts), 2):
        clause = parts[index]
        uncertainty = _UNCERTAINTY.search(clause)
        if uncertainty is None:
            continue
        tail = clause[uncertainty.end():]
        if _PROCESS_STATE.search(tail) or re.search(r"\b(?:processes|procesos)\b", tail):
            parts[index] = clause[:uncertainty.start()]
    assertions = "".join(parts)
    if require_window_answer and not re.search(
        r"\b(?:windows?|ventanas?|open|closed|abiert[oa]s?|cerrad[oa]s?)\b", assertions,
    ):
        # An unknown process state alone does not answer a window-status
        # question. It must not bypass the existing incomplete/failure guard.
        return text
    return assertions


def window_fact_defect(text: str, payload: dict) -> str:
    seen = _seen(payload)
    if seen is None:
        return ""
    asserted = fold(window_status_assertions(text, payload))
    # A name can itself contain a state phrase. Mask its subject occurrence,
    # not every matching word (Running is running still asserts a process).
    for key in ("displayName", "requestedName"):
        name = seen.get(key)
        if isinstance(name, str) and name:
            asserted = re.sub(
                rf"(?<!\w){re.escape(fold(name))}(?!\w)"
                r"(?=\s+(?:is|isn't|has|esta|no esta|tiene)\b)",
                "app", asserted,
            )
    if _PROCESS_STATE.search(asserted):
        return "extra_claim"
    for match in _INSTALLATION.finditer(asserted):
        positive = not (match["negative"] or match["after"])
        if positive != seen["installed"]:
            return "reversed_result"
    observed_count = seen["visibleWindowCount"]
    for match in _COUNT.finditer(asserted):
        raw = re.sub(r"[\s-]+", " ", match["number"])
        count = int(raw) if raw.isdecimal() else _CARDINALS[raw]
        bound = match["bound"]
        valid = (
            observed_count >= count if bound in {"at least", "al menos"} else
            observed_count <= count if bound in {"at most", "como maximo"} else
            observed_count > count if bound in {"more than", "mas de"} else
            observed_count < count if bound in {"less than", "fewer than", "menos de"} else
            observed_count == count
        )
        if not valid:
            return "reversed_result"
    no_windows = _NO_WINDOWS.search(asserted)
    if no_windows and observed_count != 0:
        return "reversed_result"
    positive_text = _NO_WINDOWS.sub("", asserted)
    if _HAS_WINDOWS.search(positive_text) and observed_count == 0:
        return "reversed_result"
    return ""
