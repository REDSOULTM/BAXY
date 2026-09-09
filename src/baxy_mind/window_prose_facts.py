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
_FOCUS_ASSERTION = re.compile(
    r"\b(?P<before>no\s+)?(?P<verb>esta|estan|is|are|isn['’]t|aren['’]t)"
    r"\s+(?P<after>not\s+)?(?P<state>active|inactive|activ[oa]s?|inactiv[oa]s?|"
    r"en primer plano|in the foreground)\b|"
    r"\b(?P<focus_negative>no\s+|does not\s+|doesn['’]t\s+)?"
    r"(?:tiene|has|have)\s+(?:el\s+)?(?P<focus>foco|focus)\b"
)


def _requests_window_focus(user_text: str, window: dict) -> bool:
    question = fold(user_text)
    names = {fold(window[key]) for key in ("title", "processName")
             if isinstance(window.get(key), str) and window[key]}
    for name in sorted(names, key=len, reverse=True):
        question = re.sub(rf"(?<!\w){re.escape(name)}(?!\w)", "selected_window", question, count=1)
    # "Is the active window maximized?" uses focus to identify the subject;
    # it asks about maximization, not about whether that subject has focus.
    question = re.sub(r"\b(?:active window|ventana activa)\b", "window", question)
    question = re.sub(r"\b(?:selected_window|the|el|la|window|ventana|it|currently|ahora|actualmente)\b", " ", question)
    question = re.sub(r"\s+", " ", question)
    return bool(_FOCUS_ASSERTION.search(question))


def window_focus_feedback(text: str, payload: dict, user_text: str = "") -> dict | None:
    """Bind explicit focus assertions to their window, never to display state.

    Single-window focus coverage is checked only when explicitly requested.
    Unknown subjects and untyped fields stay unknown. Ambiguous conjunction
    negation does not establish a Boolean claim to contradict.
    """
    seen = payload.get("seen")
    if not str(payload.get("operation", "")).startswith("window.") or not isinstance(seen, dict):
        return None
    windows = seen.get("windows")
    if not isinstance(windows, list):
        return None
    windows = [window for window in windows if isinstance(window, dict)]
    asserted = fold(text)
    answered_focus: set[int] = set()
    subjects: dict[str, set[int]] = {}
    for index, window in enumerate(windows):
        for field in ("title", "processName"):
            name = window.get(field)
            if isinstance(name, str) and name:
                subjects.setdefault(fold(name), set()).add(index)
    for name in sorted(subjects, key=len, reverse=True):
        indices = subjects[name]
        if len(indices) != 1:
            continue
        index = next(iter(indices))
        # Replace only a subject occurrence. A title called "Is Active"
        # must not erase the assertion in "Is Active is active".
        asserted = re.sub(
            rf"(?<!\w){re.escape(name)}(?!\w)"
            r"(?=[\"'»]*\s+(?:window|ventana|is|isn't|has|does|esta|no|tiene)\b)",
            f"window_subject_{index}", asserted,
        )
    clauses = (
        clause
        for sentence in re.findall(r"[^.;!?\n]+(?:[.;!?]|$)", asserted)
        if not sentence.rstrip().endswith("?") and "¿" not in sentence
        for clause in re.split(r"\b(?:but|pero)\b", sentence)
    )
    for clause in clauses:
        for match in _FOCUS_ASSERTION.finditer(clause):
            prefix = clause[:match.start()]
            if _UNCERTAINTY.search(prefix) or re.search(r"\b(?:if|si|whether)\s+", prefix):
                continue
            named = list(re.finditer(r"\bwindow_subject_(\d+)\b", prefix))
            if named:
                subject = named[-1]
                # A different intervening subject is not the named window.
                tail = prefix[subject.end():].strip(' ,\"\'')
                if tail not in {"", "window", "ventana"}:
                    continue
                index = int(subject[1])
            elif len(windows) == 1 and prefix.strip(' ,\"\'') in {
                "", "it", "the window", "la ventana", "no, la ventana", "si, la ventana",
            }:
                index = 0
            else:
                continue
            window = windows[index]
            focus = window.get("is_current_window_for_user_interaction", window.get("foreground"))
            if not isinstance(focus, bool):
                continue
            negative = bool(match["before"] or match["after"] or match["focus_negative"]
                            or (match["verb"] and "n't" in match["verb"].replace("’", "'")))
            if match["state"] and match["state"].startswith("inactiv"):
                negative = not negative
            # not(A and B) does not establish not(A). A later explicit
            # assertion can still be checked on its own.
            if negative and re.match(r"\s+and\b", clause[match.end():]):
                continue
            if (not negative) != focus:
                return {
                    "window_title": window.get("title") or window.get("processName"),
                    "contradiction": {"predicate": "is_active_window",
                                      "observed_value": focus, "draft_claim": not negative},
                    "rejected_draft": text,
                }
            answered_focus.add(index)
    if len(windows) == 1 and _requests_window_focus(user_text, windows[0]):
        window = windows[0]
        focus = window.get("is_current_window_for_user_interaction", window.get("foreground"))
        if not isinstance(focus, bool) or 0 in answered_focus:
            return None
        name = window.get("title") or window.get("processName")
        if isinstance(name, str) and name:
            identity = re.search(
                r"\b(?:active window|window in the foreground|window with focus|"
                r"ventana activa|ventana en primer plano)\s+(?:is|es)\s+[\"'«]*"
                + re.escape(fold(name)) + r"(?!\w)", fold(text),
            )
            if identity:
                if focus:
                    return None
                return {"window_title": name,
                        "contradiction": {"predicate": "is_active_window", "observed_value": False, "draft_claim": True},
                        "rejected_draft": text}
        return {"window_title": name,
                "missing_answer": {"predicate": "is_active_window", "observed_value": focus},
                "rejected_draft": text}
    return None


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


def window_fact_defect(text: str, payload: dict, user_text: str = "") -> str:
    feedback = window_focus_feedback(text, payload, user_text)
    if feedback is not None:
        return "reversed_result" if "contradiction" in feedback else "missing_fact"
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
