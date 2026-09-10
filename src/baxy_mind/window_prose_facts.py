"""Conserve typed window observations without treating processes as observed.

This is part of the existing prose contract, not a second narrator or model.
Checks bind predicates and quantities to their observed field; names and an
explicit admission of unknown process state are not process assertions.
"""
from __future__ import annotations

import re

from .effect_intent import _PERCENTAGE_WORD_VALUES, _strip_request_envelope, window_inventory_arguments
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
_FOCUS_STATE = r"active|inactive|activ[oa]s?|inactiv[oa]s?|en primer plano|in the foreground"
_FOCUS_COPULA = r"esta|estan|is|are|isn['’]t|aren['’]t"
_WINDOW_DISPLAY_STATE = r"maximized|maximizad[oa]s?|minimized|minimizad[oa]s?|visible|normal"
_FOCUS_ASSERTION = re.compile(
    rf"\b(?P<before>no\s+)?(?P<verb>{_FOCUS_COPULA})"
    rf"\s+(?P<after>not\s+)?(?P<state>{_FOCUS_STATE})\b|"
    rf"\b(?P<inverted_state>{_FOCUS_STATE})\s+(?P<inverted_before>no\s+)?"
    rf"(?P<inverted_verb>{_FOCUS_COPULA})\b(?:\s+(?P<inverted_after>not)\b)?|"
    r"\b(?P<focus_negative>no\s+|does not\s+|doesn['’]t\s+)?"
    r"(?:tiene|has|have)\s+(?:el\s+)?(?P<focus>foco|focus)\b"
)


def _window_focus_question(user_text: str, window: dict) -> str | None:
    question = _strip_request_envelope(fold(user_text))
    names = {fold(window[key]) for key in ("title", "processName")
             if isinstance(window.get(key), str) and window[key]}
    for name in sorted(names, key=len, reverse=True):
        def replace_subject(match: re.Match) -> str:
            # A process named "Is Active" must not erase the predicate in
            # "Which window is active?". Quoting or a surrounding predicate
            # can instead establish that the occurrence is the subject.
            if _FOCUS_ASSERTION.fullmatch(name) and not (
                re.search(r"(?:\b(?:is|are|esta|estan|does|do|tiene|has|of|de|named|titled)|[\"'«])\s*$",
                          question[:match.start()])
                or re.search(rf"\b(?:is|are|esta|estan)\s+(?:{_WINDOW_DISPLAY_STATE})\s+$",
                             question[:match.start()])
                or re.match(r"[\"'»]|\s+(?:window|ventana|is|are|esta|estan|has|tiene)\b",
                            question[match.end():])
            ):
                return match[0]
            return "selected_window"

        question = re.sub(rf"(?<!\w){re.escape(name)}(?!\w)", replace_subject, question, count=1)
    # A relative clause identifies the subject: asking its name does not
    # also ask whether it has focus. Removing just that clause preserves
    # the main predicate in "Is the window that is maximized active?".
    question = re.sub(
        r"\b(window|ventana)\s+(?:that|which|que)\s+"
        rf"(?:(?:is|esta)\s+(?:{_FOCUS_STATE}|{_WINDOW_DISPLAY_STATE})|"
        r"(?:has|tiene)\s+(?:el\s+)?(?:focus|foco))\b",
        r"\1", question,
    )
    # "Is the active window maximized?" uses focus to identify the subject;
    # it asks about maximization, not about whether that subject has focus.
    question = re.sub(r"\b(?:active window|ventana activa)\b", "window", question)
    question = re.sub(r"\b(?:selected_window|the|el|la|window|ventana|it|currently|ahora|actualmente)\b", " ", question)
    question = re.sub(r"\s+", " ", question)
    predicate = _FOCUS_ASSERTION.search(question)
    if predicate is None:
        return None
    prefix = question[:predicate.start()].strip(" ¿?¡!,")
    if re.fullmatch(r"(?:(?:y|and)\s+)?(?:que|cual|what|which)(?:\s+one)?", prefix) and re.fullmatch(
        r"(?:\s*(?:[?.!]|now|right now|at (?:this|the) moment|en este momento|please|por favor))*",
        question[predicate.end():],
    ):
        return "identity"
    return "state"


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
    identified_focus: set[int] = set()
    subjects: dict[str, set[int]] = {}
    for index, window in enumerate(windows):
        for field in ("title", "processName"):
            name = window.get(field)
            if isinstance(name, str) and name:
                subjects.setdefault(fold(name), set()).add(index)
    bare_identity = {
        index for name, indices in subjects.items() for index in indices
        if len(indices) == 1 and re.fullmatch(r"[\s\"'«]*" + re.escape(name) + r"[\"'»]*[.!]?[\s]*", asserted)
    }
    # A title such as "Is Active" is an identity, not a Boolean assertion.
    if bare_identity:
        asserted = ""
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
        # Quoted titles are opaque identifiers. Their punctuation must not
        # split a factual sentence (for example a title containing .txt).
        asserted = re.sub(
            r"[\"'«]" + re.escape(name) + r"[\"'»]", f"window_subject_{index}", asserted,
        )

    def window_subject(phrase: str, *, complete: bool = False) -> int | None:
        noun_prefix = (
            r"\s*(?:(?:la ventana|the window)\s+(?:(?:de|of)\s+)?|"
            r"(?:el|la|the)\s+)?"
        )
        for name in sorted(subjects, key=len, reverse=True):
            indices = subjects[name]
            if len(indices) != 1:
                continue
            index = next(iter(indices))
            identity = rf"(?:{re.escape(name)}|window_subject_{index})(?!\w)"
            apposition = re.match(
                noun_prefix + r"(?P<label>[^()]+?)\s*\(\s*[\"'«]*"
                + identity + r"[\"'»]*\s*\)", phrase,
            )
            subject = apposition or re.match(noun_prefix + r"[\"'«]*" + identity, phrase)
            if subject is None:
                continue
            if apposition:
                # The parenthesis must name this observed subject, and its
                # display label must occur in this same window's observation.
                # Do not invent a translated app alias or accept a different one.
                label = apposition["label"].strip(' \"\'«»')
                if not label or (label != f"window_subject_{index}" and not any(
                    isinstance(windows[index].get(field), str)
                    and re.search(rf"(?<!\w){re.escape(label)}(?!\w)", fold(windows[index][field]))
                    for field in ("title", "processName")
                )):
                    continue
            tail = phrase[subject.end():].lstrip(' \"\'»')
            if tail.startswith("("):
                # A conflicting parenthetical identity is not decoration.
                continue
            if complete and tail not in {"", "window", "ventana"}:
                continue
            if re.match(r"(?:titulada|titled|named)\b", tail):
                title = windows[index].get("title")
                if not isinstance(title, str) or not re.match(
                    r"(?:titulada|titled|named)\s+[\"'«]*"
                    + rf"(?:{re.escape(fold(title))}|window_subject_{index})(?!\w)", tail,
                ):
                    continue
            return index
        return None

    clauses = (
        clause
        for sentence in re.findall(r"[^.;!?\n]+(?:[.;!?]|$)", asserted)
        if not sentence.rstrip().endswith("?") and "¿" not in sentence
        for clause in re.split(r"\b(?:but|pero)\b", sentence)
    )
    for clause in clauses:
        # Nominal focus descriptions identify a window through the same
        # observed name, independent of whether the question repeats a verb.
        for name, indices in subjects.items():
            if len(indices) != 1:
                continue
            index = next(iter(indices))
            identity = re.search(
                r"\b(?:active window|window in the foreground|window with focus|"
                r"ventana activa|ventana en primer plano|ventana con (?:el )?(?:foco|enfoque))"
                r"\s+(?:is|es|se llama)\s+[\"'«]*"
                + rf"(?:{re.escape(name)}|window_subject_{index})(?!\w)", clause,
            )
            if identity is None:
                continue
            prefix = clause[:identity.start()]
            if _UNCERTAINTY.search(prefix) or re.search(r"\b(?:if|si|whether)\s+", prefix):
                continue
            window = windows[index]
            focus = window.get("is_current_window_for_user_interaction", window.get("foreground"))
            if not isinstance(focus, bool):
                continue
            if not focus:
                return {"window_title": window.get("title") or window.get("processName"),
                        "contradiction": {"predicate": "is_active_window", "observed_value": False, "draft_claim": True},
                        "rejected_draft": text}
            answered_focus.add(index)
            identified_focus.add(index)
        for match in _FOCUS_ASSERTION.finditer(clause):
            prefix = clause[:match.start()]
            if _UNCERTAINTY.search(prefix) or re.search(r"\b(?:if|si|whether)\s+", prefix):
                continue
            named = list(re.finditer(r"\bwindow_subject_(\d+)\b", prefix))
            identified = False
            plain_prefix = re.sub(r"\b(?:ahora|actualmente|currently|now)\b", "", prefix).strip(' ,\"\'')
            if "(" in prefix or ")" in prefix:
                index = window_subject(plain_prefix, complete=True)
                if index is None:
                    continue
                identified = True
            elif named:
                subject = named[-1]
                # A different intervening subject is not the named window.
                tail = prefix[subject.end():].strip(' ,\"\'')
                if tail not in {"", "window", "ventana"}:
                    continue
                index = int(subject[1])
                identified = True
            else:
                suffix = clause[match.end():]
                index = window_subject(suffix) if not plain_prefix else None
                identified = index is not None
                if index is None:
                    if len(windows) == 1 and plain_prefix in {
                        "", "it", "the window", "la ventana", "no, la ventana", "si, la ventana",
                    } and re.match(r"\s*(?:[.,;!?]|$|(?:and|y|ni)\b)", suffix):
                        index = 0
                    else:
                        continue
            window = windows[index]
            focus = window.get("is_current_window_for_user_interaction", window.get("foreground"))
            if not isinstance(focus, bool):
                continue
            verb = match["verb"] or match["inverted_verb"]
            state = match["state"] or match["inverted_state"]
            negative = bool(match["before"] or match["after"] or match["focus_negative"]
                            or match["inverted_before"] or match["inverted_after"]
                            or (verb and "n't" in verb.replace("’", "'")))
            if state and state.startswith("inactiv"):
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
            if identified:
                identified_focus.add(index)
    question_kind = _window_focus_question(user_text, windows[0]) if len(windows) == 1 else None
    if question_kind is not None:
        window = windows[0]
        focus = window.get("is_current_window_for_user_interaction", window.get("foreground"))
        if not isinstance(focus, bool) or (0 in answered_focus and (question_kind != "identity" or 0 in identified_focus)):
            return None
        name = window.get("title") or window.get("processName")
        if question_kind == "identity" and 0 in bare_identity:
            if focus:
                return None
            return {"window_title": name,
                    "contradiction": {"predicate": "is_active_window", "observed_value": False, "draft_claim": True},
                    "rejected_draft": text}
        return {"window_title": name,
                "missing_answer": {"predicate": "active_window_identity" if question_kind == "identity" else "is_active_window",
                                   "observed_value": name if question_kind == "identity" else focus},
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


def _inventory_seen(payload: dict) -> dict | None:
    seen = payload.get("seen")
    if (
        payload.get("operation") != "window.resolve" or not isinstance(seen, dict)
        or not isinstance(seen.get("windows"), list)
        or not isinstance(seen.get("complete"), bool)
        or any(type(seen.get(key)) is not int or seen[key] < 0
               for key in ("count", "observedCount", "offset"))
        or seen["count"] != len(seen["windows"])
        or seen["count"] > seen["observedCount"]
        or (seen["complete"] and (
            type(seen.get("totalCount")) is not int
            or seen["totalCount"] != seen["observedCount"]
        ))
        or (not seen["complete"] and seen.get("totalCount") is not None)
    ):
        return None
    return seen


def project_window_inventory(payload: dict, user_text: str) -> dict:
    """Describe page scope without confusing enumeration completion with a full list.

    Keep the typed fields for factual checks. Only an identity/count request
    permits omitting unrequested per-window details from the narrator's copy.
    The provider records no opening time, so enumeration order is not recency.
    """
    seen = _inventory_seen(payload)
    if seen is None:
        return payload
    total = seen["totalCount"] if seen["complete"] else None
    entire_inventory = (
        seen["offset"] == 0 and seen["count"] == total if total is not None else
        False if seen["offset"] > 0 or seen["count"] < seen["observedCount"] else None
    )
    projected = dict(seen)
    projected["returnedPageScope"] = {
        "windowsListedOnThisPage": seen["count"],
        "totalWindowsInSelectedInventory": total,
        "thisListIncludesEveryWindowInSelectedInventory": entire_inventory,
        "windowOpeningTimesObserved": False,
    }
    if window_inventory_arguments(user_text) is not None:
        projected["windows"] = [
            {key: value for key, value in window.items() if key in {"title", "processName"}}
            if isinstance(window, dict) else window
            for window in seen["windows"]
        ]
    return {**payload, "seen": projected}


_PAGE_CONTEXT = re.compile(r"\b(?:pagina|page|listad[oa]|listed|mostrad[oa]s?|shown|"
                           r"muestro|muestra|showing|displayed|devuelt[oa]s?|returned)\b")
_OBSERVATION_CONTEXT = re.compile(r"\b(?:observad[oa]s?|observed|encontrad[oa]s?|found|"
                                  r"detectad[oa]s?|detected|identificad[oa]s?|identified)\b")
_TOTAL_CONTEXT = re.compile(r"\b(?:en\s+total|in\s+total|total\s+of|total\s+de)\b")
_INVENTORY_LIMIT = re.compile(r"\b(?:pagina|page|parcial|partial|limite|limited|"
                             r"al\s+menos|at\s+least|mas\s+ventanas|more\s+windows)\b")
_INVENTORY_FRACTION = re.compile(
    rf"\b(?P<page>{_NUMBER})\s*"
    r"(?:(?:open\s+|visible\s+)?(?:windows?|ventanas?)\s+)?"
    r"(?:de|of|out\s+of)\s+(?:(?:las|the|un\s+total\s+de|a\s+total\s+of)\s+)?"
    rf"(?P<total>{_NUMBER})(?:\s+(?:open\s+|visible\s+)?(?:windows?|ventanas?))?\b"
)
_WINDOW_CHRONOLOGY = re.compile(
    r"\b(?:(?:mas|menos)\s+(?:recientes?|nuev[oa]s?|antigu[oa]s?)|"
    r"(?:most|least|more|less)\s+recent|newest|oldest|latest|newer|older|"
    r"(?:recien|recently|last|first)\s+(?:abiert[oa]s?|opened)|"
    r"(?:primeras|ultimas)\s+(?:en\s+)?(?:abrirse|abiertas)|"
    r"(?:orden(?:adas?|ados)?|order(?:ed)?|sort(?:ed)?)\s+(?:por|by|of)\s+"
    r"(?:fecha|antiguedad|recencia|apertura|age|recency|opening|creation)|"
    r"cronologic[oa]s?|chronological(?:ly)?)\b"
)


def _inventory_chronology_claim(text: str, seen: dict) -> bool:
    # Quoted names and standalone list entries are identities, even if their
    # titles contain words such as "Latest". Never change the actual reply.
    text = "\n".join(fold(line) for line in text.splitlines())
    for window in seen["windows"]:
        if not isinstance(window, dict):
            continue
        for key in ("title", "processName"):
            name = window.get(key)
            if not isinstance(name, str) or not name:
                continue
            literal = re.escape(fold(name))
            text = re.sub(r"[\"'«]" + literal + r"[\"'»]", "window_name", text)
            text = re.sub(r"(?m)^\s*(?:[-*]|\d+[.)])?\s*" + literal + r"\s*$", "window_name", text)
    if seen.get("pageConsistency") == "fresh_enumeration_per_request":
        # Freshness of the reading is known; it says nothing about the age of
        # the windows. Bind those modifiers to their observation noun.
        text = re.sub(
            r"\b(?:latest|most recent|newest)\s+(?:observation|reading|snapshot|enumeration)\b|"
            r"\b(?:observacion|lectura|enumeracion)\s+mas\s+reciente\b", "fresh_reading", text,
        )
    for clause in re.split(r"[,;.!?]|\b(?:but|pero|and|y)\b", text):
        if _UNCERTAINTY.search(clause):
            continue
        for claim in _WINDOW_CHRONOLOGY.finditer(clause):
            if re.match(
                r"\s+(?:(?:is|are|esta|estan)\s+)?(?:unknown|unverified|not\s+(?:known|observed|checked))\b|"
                r"\s+no\s+(?:esta|estan|se\s+ha|se\s+han)\s+(?:observad[oa]s?|comprobad[oa]s?|verificad[oa]s?)\b",
                clause[claim.end():],
            ):
                continue
            return True
    return False


def _inventory_fact_defect(text: str, payload: dict, user_text: str) -> str:
    seen = _inventory_seen(payload)
    if seen is None:
        return ""
    if _inventory_chronology_claim(text, seen):
        return "extra_claim"
    asserted = fold(window_status_assertions(text, payload))
    # Quoted observed names are data, including names containing cardinality
    # or punctuation. Keep the original draft and observation untouched.
    for window in seen["windows"]:
        if not isinstance(window, dict):
            continue
        for key in ("title", "processName"):
            name = window.get(key)
            if isinstance(name, str) and name:
                asserted = re.sub(r"[\"'«]" + re.escape(fold(name)) + r"[\"'»]", "window_name", asserted)
    if _PROCESS_STATE.search(asserted):
        return "extra_claim"
    total = seen["totalCount"] if seen["complete"] else None
    partial_page = total is None or seen["count"] < total
    count_question = re.search(r"\b(?:cuantas|how\s+many|cuenta|count)\b", fold(user_text))
    stated_subset = False
    for clause in re.split(r"[,;.!?]|\b(?:pero|but|and|y)\b", asserted):
        if _UNCERTAINTY.search(clause) or re.search(r"^\s*(?:si|if)\b", clause):
            continue
        for fraction in reversed(list(_INVENTORY_FRACTION.finditer(clause))):
            if not re.search(r"\b(?:windows?|ventanas?)\b", fraction[0]):
                continue
            numbers = [re.sub(r"[\s-]+", " ", fraction[key]) for key in ("page", "total")]
            page_value, total_value = [int(n) if n.isdecimal() else _CARDINALS[n] for n in numbers]
            if page_value != seen["count"]:
                return "reversed_result"
            if total is None:
                return "extra_claim"
            if total_value != total:
                return "reversed_result"
            stated_subset = True
            clause = clause[:fraction.start()] + "window_subset" + clause[fraction.end():]
        value = (total if _TOTAL_CONTEXT.search(clause) else
                 seen["count"] if _PAGE_CONTEXT.search(clause) else
                 seen["observedCount"] if _OBSERVATION_CONTEXT.search(clause) else total)
        for match in _COUNT.finditer(clause):
            raw = re.sub(r"[\s-]+", " ", match["number"])
            number = int(raw) if raw.isdecimal() else _CARDINALS[raw]
            bound = match["bound"]
            if value is None:
                valid = (
                    seen["observedCount"] >= number if bound in {"at least", "al menos"} else
                    seen["observedCount"] > number if bound in {"more than", "mas de"} else False
                )
            else:
                valid = (
                    value >= number if bound in {"at least", "al menos"} else
                    value <= number if bound in {"at most", "como maximo"} else
                    value > number if bound in {"more than", "mas de"} else
                    value < number if bound in {"less than", "fewer than", "menos de"} else
                    value == number
                )
            if not valid:
                return "extra_claim" if value is None else "reversed_result"
        if _NO_WINDOWS.search(clause) and value != 0:
            return "extra_claim" if value is None else "reversed_result"
        if _HAS_WINDOWS.search(_NO_WINDOWS.sub("", clause)) and value == 0:
            return "reversed_result"
        if partial_page and not _PAGE_CONTEXT.search(clause) and re.search(
            r"\b(?:todas\s+las\s+ventanas|all\s+(?:the\s+)?windows|"
            r"son\s+todas|all\s+of\s+them|no\s+hay\s+mas\s+ventanas|no\s+other\s+windows)\b", clause,
        ):
            return "extra_claim"
    if partial_page and not (count_question and total is not None) and not (
        stated_subset or _INVENTORY_LIMIT.search(asserted) or _UNCERTAINTY.search(asserted)
    ):
        return "missing_fact"
    return ""


def window_status_assertions(
    text: str, payload: dict, *, require_window_answer: bool = False,
) -> str:
    """Only for validation: omit process uncertainty, retaining other clauses."""
    if _seen(payload) is None and _inventory_seen(payload) is None:
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
    inventory_defect = _inventory_fact_defect(text, payload, user_text)
    if inventory_defect:
        return inventory_defect
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
