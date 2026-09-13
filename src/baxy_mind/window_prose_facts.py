"""Conserve typed window observations without treating processes as observed.

This is part of the existing prose contract, not a second narrator or model.
Checks bind predicates and quantities to their observed field; names and an
explicit admission of unknown process state are not process assertions.
"""
from __future__ import annotations

from collections import Counter
import re

from .effect_intent import _PERCENTAGE_WORD_VALUES, _strip_request_envelope, window_inventory_arguments
from .request_reading import fold


_CARDINALS = {**_PERCENTAGE_WORD_VALUES, "a": 1, "an": 1, "una": 1,
              "no": 0, "ninguna": 0, "ningunas": 0}
_NUMBER = r"(?:\d+|" + "|".join(
    re.escape(word).replace(r"\ ", r"[\s-]+")
    for word in sorted(_CARDINALS, key=len, reverse=True)
) + r")"
_NUMBER_WORD = re.compile(rf"\b{_NUMBER}\b")
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
_COUNT_QUESTION = re.compile(r"\b(?:cuantas|how\s+many|cuenta|count)\b")
# A 22-window desktop exhausted composition (WINDOWS1207/000-004): the
# narrator omitted the eight untitled explorer entries, and every retry was
# rejected for the same omission. The answer names a bounded subset, titled
# windows first, and states how many observed windows it does not name.
# Factual checks run on that projected page, so what is named is verified.
NAMED_WINDOWS_PER_ANSWER = 10
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


def window_fact_feedback(text: str, payload: dict, user_text: str = "") -> dict | None:
    """Preserve the factual cause when a window answer needs correction.

    Single-window focus coverage is checked only when explicitly requested.
    Unknown subjects and untyped fields stay unknown. Ambiguous conjunction
    negation does not establish a Boolean claim to contradict.
    """
    inventory = _inventory_seen(payload)
    if inventory is not None and _inventory_chronology_claim(text, inventory):
        return {
            "unsupported_claim": {"predicate": "window_opening_chronology", "observed": False},
            "rejected_draft": text,
        }
    if inventory is not None:
        expected, mentioned, grouped, _ = _inventory_identity_counts(text, inventory)
        excessive = {name: {"observed": count, "draft_claim": grouped[name]}
                     for name, count in expected.items() if grouped[name] > count}
        if excessive:
            return {"contradiction": {"predicate": "window_inventory_identity_counts", "identities": excessive},
                    "rejected_draft": text}
        identity_request = _inventory_identity_request(user_text)
        missing = {name: {"observed": count, "identified_in_draft": mentioned[name]}
                   for name, count in expected.items() if identity_request and mentioned[name] < count}
        if missing:
            return {"missing_answer": {"predicate": "window_inventory_identity_counts", "identities": missing},
                    "rejected_draft": text}
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


def _inventory_is_entire(seen: dict) -> bool | None:
    total = seen["totalCount"] if seen["complete"] else None
    return (
        seen["offset"] == 0 and seen["count"] == total if total is not None else
        False if seen["offset"] > 0 or seen["count"] < seen["observedCount"] else None
    )


def _inventory_identity_request(user_text: str) -> bool:
    """A list request names windows; a count request only counts them."""
    return window_inventory_arguments(user_text) is not None and not _COUNT_QUESTION.search(fold(user_text))


def _named_inventory_subset(windows: list) -> list:
    """Titled windows in enumeration order, capped; untitled ones only when no title exists.

    Untitled shell windows were paraphrased («Dos ventanas de Explorador de
    archivos sin título», «Two unnamed explorer windows», WINDOWS1211/006-007)
    and never matched their processName; they are counted, not named.
    """
    titled = [window for window in windows
              if isinstance(window, dict) and isinstance(window.get("title"), str) and window["title"].strip()]
    return (titled or windows)[:NAMED_WINDOWS_PER_ANSWER]


def project_window_inventory(payload: dict, user_text: str) -> dict:
    """Describe page scope without confusing enumeration completion with a full list.

    Keep the typed fields for factual checks. Only an identity/count request
    permits omitting unrequested per-window details from the narrator's copy.
    A list request names at most NAMED_WINDOWS_PER_ANSWER windows: the copy
    becomes that shorter page, still inside the same observed inventory, and
    declares how many observed windows it leaves unnamed. The App's page and
    its cursor are untouched. The provider records no opening time, so
    enumeration order is not recency.
    """
    seen = _inventory_seen(payload)
    if seen is None:
        return payload
    total = seen["totalCount"] if seen["complete"] else None
    projected = dict(seen)
    if window_inventory_arguments(user_text) is not None:
        projected["windows"] = [
            {key: value for key, value in window.items() if key in {"title", "processName"}}
            if isinstance(window, dict) else window
            for window in seen["windows"]
        ]
        named = _named_inventory_subset(projected["windows"]) if _inventory_identity_request(user_text) else None
        if named is not None and len(named) < len(projected["windows"]):
            projected["windows"] = named
            projected["count"] = len(named)
            projected["hasMore"] = True
            projected.pop("limit", None)
            projected.pop("nextOffset", None)
    projected["returnedPageScope"] = {
        "windowsListedOnThisPage": projected["count"],
        "totalWindowsInSelectedInventory": total,
        "thisListIncludesEveryWindowInSelectedInventory": _inventory_is_entire(projected),
        "windowOpeningTimesObserved": False,
    }
    if projected["count"] < seen["count"]:
        projected["returnedPageScope"]["windowsObservedButNotNamedHere"] = seen["observedCount"] - projected["count"]
    return {**payload, "seen": projected}


_PAGE_CONTEXT = re.compile(r"\b(?:pagina|page|lista|list|listad[oa]|listed|mostrad[oa]s?|shown|"
                           r"muestro|muestra|showing|displayed|devuelt[oa]s?|returned)\b")
_OBSERVATION_CONTEXT = re.compile(r"\b(?:observ(?:ad[oa]s?|a(?:n|mos|ron)?|o|e)|observed|encontrad[oa]s?|found|"
                                  r"detectad[oa]s?|detected|identificad[oa]s?|identified)\b")
_TOTAL_CONTEXT = re.compile(r"\b(?:en\s+total|in\s+total|total\s+of|total\s+de)\b")
# «Hay 12 ventanas más que no nombro» counts the observed windows outside the
# named page; it is neither the page nor the total.
_REMAINING_CONTEXT = re.compile(
    r"\b(?:mas|more|other|another|otras?|restantes?|remaining|adicionales|additional|"
    r"unnamed|unlisted|omitid[oa]s|excluid[oa]s|omitted|excluded|quedan|faltan|restan|"
    r"sin\s+(?:nombrar|listar|mencionar|enumerar|incluir|mostrar)|"
    r"fuera\s+de\s+(?:esta\s+|la\s+)?lista|(?:outside|beyond|not\s+in)\s+(?:this|the)\s+list|"
    r"no\s+(?:(?:estan|se|aparecen|figuran)\s+)?"
    r"(?:nombrad[oa]s|listad[oa]s|mencionad[oa]s|enumerad[oa]s|incluid[oa]s|mostrad[oa]s|"
    r"nombro|listo|menciono|enumero|incluyo|muestro|nombran|listan|mencionan|enumeran|incluyen|muestran|aparecen|figuran)|"
    r"not\s+(?:named|listed|mentioned|shown|included|displayed)|left\s+(?:out|unnamed|unlisted))\b"
)
_RELATIVE_LINK = re.compile(r"\s*(?:,\s*)?(?:que|which|that|de\s+las\s+cuales|of\s+which)?\s*$")
_INVENTORY_LIMIT = re.compile(r"\b(?:pagina|page|parcial|partial|limite|limited|"
                             r"al\s+menos|at\s+least|mas\s+ventanas|more\s+windows)\b")
_INVENTORY_REFERENCE_COUNT = re.compile(rf"\b(?P<number>{_NUMBER})\s+(?:of\s+them|de\s+ellas)\b")
_ALL_WINDOWS = re.compile(
    r"\b(?:todas\s+las\s+ventanas|all\s+(?:the\s+)?windows|"
    r"son\s+todas|all\s+of\s+them|no\s+hay\s+mas\s+ventanas|no\s+other\s+windows)\b"
)
_NEGATED_INVENTORY_INCLUSION = re.compile(
    r"\b(?:no|not|isn['’]t|aren['’]t|doesn['’]t|don['’]t)\s+"
    r"(?:(?:incluy[ea]n?|contien[ea]n?|muestr[ae]n?|enumer[ae]n?|represent[ae]n?|abarc[ae]n?|"
    r"inclu(?:de|des)|contain(?:s)?|show(?:s)?|list(?:s)?|represent(?:s)?|cover(?:s)?|have|has)\s+)?$"
)
_INVENTORY_FRACTION = re.compile(
    rf"\b(?P<page>{_NUMBER})\s*"
    r"(?:(?:open\s+|visible\s+)?(?:windows?|ventanas?)\s+)?"
    r"(?:de|of|out\s+of)\s+(?:(?:las|the|un\s+total\s+de|a\s+total\s+of)\s+)?"
    rf"(?P<total>{_NUMBER})(?:\s+(?:open\s+|visible\s+)?"
    r"(?P<observed_before>observed\s+|observadas?\s+)?(?:windows?|ventanas?))?"
    r"(?P<observed_after>\s+(?:observed|observadas?))?\b"
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


def _inventory_quantity_scope(clause: str, start: int, end: int) -> str:
    """Bind a quantity to its nearby noun/modifier, not a remote list heading.

    A restrictive clause right after the quantity («14 ventanas que no están
    incluidas») binds tighter than the verb before it («se observaron»).
    """
    contexts = []
    for scope, pattern in (
        ("page", _PAGE_CONTEXT), ("observed", _OBSERVATION_CONTEXT), ("total", _TOTAL_CONTEXT),
        ("remaining", _REMAINING_CONTEXT),
    ):
        for match in pattern.finditer(clause):
            distance = max(start - match.end(), match.start() - end, 0)
            between = clause[end:match.start()]
            if scope == "remaining" and match.start() >= end and (
                _RELATIVE_LINK.fullmatch(between)
                # «18 windows were observed but not named»: a short verb phrase
                # without another quantity or list/total modifier still binds
                # the negation to this quantity.
                or (len(between.split()) <= 4 and not re.search(r"\d", between)
                    and not _PAGE_CONTEXT.search(between) and not _TOTAL_CONTEXT.search(between)
                    and not _NUMBER_WORD.search(between))
            ):
                distance = 0
            contexts.append((distance, 0 if match.start() >= end else 1, scope))
    return min(contexts)[2] if contexts else ""


def _inventory_identity_counts(text: str, seen: dict) -> tuple[Counter, Counter, Counter, str]:
    """Bind explicit group cardinalities to opaque observed names.

    Repeating an entry or stating its group size can convey multiplicity.
    A quantity attached to a title is not a quantity of the whole inventory.
    The returned text is for factual checks only; the draft is never rewritten.
    """
    expected: Counter = Counter()
    processes: dict[str, set[str]] = {}
    for window in seen["windows"]:
        if not isinstance(window, dict):
            continue
        name = window.get("title")
        if not isinstance(name, str) or not name.strip():
            name = window.get("processName")
        if isinstance(name, str) and name.strip():
            name = fold(name)
            expected[name] += 1
            process = window.get("processName")
            if isinstance(process, str) and process.strip():
                processes.setdefault(name, set()).add(fold(process))
    asserted = "\n".join(fold(line) for line in text.splitlines())
    if not expected:
        return expected, Counter(), Counter(), asserted
    prefix = "window_identity_"
    while prefix in asserted:
        prefix += "_"
    names = sorted(expected, key=len, reverse=True)
    tokens = {name: prefix + str(index) for index, name in enumerate(names)}
    identifiers = {value: name for name, value in tokens.items()}
    asserted = re.sub(r"(?<!\w)(?:" + "|".join(re.escape(name) for name in names) + r")(?!\w)",
                      lambda match: tokens[match[0]], asserted)
    # Longest-name matching keeps Atlas 2 from also counting as Atlas.
    # Retain quotes and prose punctuation for the other factual checks.
    identity = re.escape(prefix) + r"\d+\b"
    quoted_identity = rf"[\"'«»“”‘’*]*{identity}[\"'«»“”‘’*]*"

    def process_annotation(match: re.Match) -> str:
        owner = identifiers[match["owner"]]
        content = re.sub(
            identity,
            lambda token: "window_process_annotation" if identifiers[token[0]] in processes.get(owner, set()) else token[0],
            match["content"],
        )
        start, end = match.start("content") - match.start(), match.end("content") - match.start()
        return match[0][:start] + content + match[0][end:]

    # A known process in its window's annotation identifies that window's
    # process; it is not a separate entry for another window without a title.
    asserted = re.sub(
        rf"(?P<owner>{identity})[\"'«»“”‘’*]*\s*(?:[—–-]\s*)?\((?P<content>[^()]*)\)",
        process_annotation, asserted,
    )
    unit = r"(?:windows?|ventanas?|instances?|instancias?)"
    number = rf"(?P<number>{_NUMBER})"
    group_names = rf"(?P<names>{quoted_identity}(?:\s*(?:,\s*(?:(?:and|y)\s+)?|\b(?:and|y)\b\s*){quoted_identity})*)"
    single_name = rf"(?P<names>{quoted_identity})"
    # A quantity binds to a name on the same line; a bullet on the next line
    # («- Program Manager\n- Dos ventanas…», WINDOWS1211/006) is a new entry.
    separator = r"[ \t]*(?:[:(—–-][ \t]*)?"
    patterns = [
        # The explicit distributive quantifier applies to every named title.
        group_names + separator + number + rf"\s+{unit}\s+(?:each|cada\s+una|de\s+cada\s+titulo)\b\)?",
        single_name + separator + r"[x×]\s*" + number + r"\b",
        single_name + separator + number + rf"\s+{unit}\b\)?",
        number + rf"\s+{unit}\s+(?:de|of|named|titled|llamadas?)\s+{single_name}",
        number + rf"\s+(?:(?:unnamed|untitled|open|visible|abiertas|visibles)\s+)?{single_name}\s+{unit}\b",
        number + rf"\s*[x×]\s*{single_name}",
    ]
    grouped: Counter = Counter()

    def bind(match: re.Match) -> str:
        raw = re.sub(r"[\s-]+", " ", match["number"])
        value = int(raw) if raw.isdecimal() else _CARDINALS[raw]
        for token in re.findall(identity, match["names"]):
            grouped[identifiers[token]] += value
        return "inventory_identity_group"

    for pattern in patterns:
        asserted = re.sub(pattern, bind, asserted)
    mentioned = grouped.copy()
    for clause in re.split(r"[,;\n]|[.!?](?=\s|$)|\b(?:and|y)\b", asserted):
        # Separate list entries count separately; a descriptive reference
        # such as "Atlas is active" is not another instance of Atlas.
        entry = re.search(rf"(?P<name>{identity})[\"'«»“”‘’*]*\s*(?:\([^()]*\))?\s*[.!]?\s*$", clause)
        if entry:
            mentioned[identifiers[entry["name"]]] += 1
    for token in re.findall(identity, asserted):
        name = identifiers[token]
        if expected[name] == 1:
            mentioned[name] = max(mentioned[name], 1)
    asserted = re.sub(identity, lambda match: identifiers[match[0]], asserted)
    return expected, mentioned, grouped, asserted


def _inventory_fact_defect(text: str, payload: dict, user_text: str) -> str:
    seen = _inventory_seen(payload)
    if seen is None:
        return ""
    if _inventory_chronology_claim(text, seen):
        return "extra_claim"
    # Keep line breaks: a list entry ends its line, and fold() would otherwise
    # glue «- Program Manager» to the next bullet's «Dos ventanas».
    asserted = "\n".join(fold(line) for line in window_status_assertions(text, payload).splitlines())
    identities, _, _, asserted = _inventory_identity_counts(asserted, seen)
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
    entire_inventory = _inventory_is_entire(seen)
    partial_page = entire_inventory is not True
    count_question = _COUNT_QUESTION.search(fold(user_text))
    stated_subset = False
    stated_page_count = False
    stated_inventory_count = False
    # «18 windows were observed but not named» is one quantity with one scope;
    # a conjunction followed by a negation does not start a new clause.
    for clause in re.split(r"[,;.!?\n]|\b(?:pero|but|and|y)\b(?!\s+(?:not|no|sin)\b)", asserted):
        if _UNCERTAINTY.search(clause) or re.search(r"^\s*(?:si|if)\b", clause):
            continue
        for fraction in reversed(list(_INVENTORY_FRACTION.finditer(clause))):
            if not re.search(r"\b(?:windows?|ventanas?)\b", fraction[0]):
                continue
            numbers = [re.sub(r"[\s-]+", " ", fraction[key]) for key in ("page", "total")]
            page_value, total_value = [int(n) if n.isdecimal() else _CARDINALS[n] for n in numbers]
            if page_value != seen["count"]:
                return "reversed_result"
            denominator = (
                seen["observedCount"]
                if fraction["observed_before"] or fraction["observed_after"] else total
            )
            if denominator is None:
                return "extra_claim"
            if total_value != denominator:
                return "reversed_result"
            stated_subset = True
            clause = clause[:fraction.start()] + "window_subset" + clause[fraction.end():]
        value = (total if _TOTAL_CONTEXT.search(clause) else
                 seen["count"] if _PAGE_CONTEXT.search(clause) else
                 seen["observedCount"] if _OBSERVATION_CONTEXT.search(clause) else total)
        quantities = list(_COUNT.finditer(clause))
        if _PAGE_CONTEXT.search(clause):
            quantities.extend(_INVENTORY_REFERENCE_COUNT.finditer(clause))
        for match in quantities:
            quantity_scope = _inventory_quantity_scope(clause, match.start(), match.end())
            if not quantity_scope:
                # A colon followed by an observed identity introduces the
                # enumerated page. Explicit total/observation modifiers above
                # still win; a later list cannot rebind an earlier total.
                enumeration = re.match(
                    r"\s*(?:(?:abiertas?|visibles?|open|visible)\s*)?:\s*[\"'«]?(.+)",
                    clause[match.end():],
                )
                named_entry = enumeration and re.match(
                    r"(?:" + "|".join(["window_name", *(re.escape(name) for name in identities)]) + r")(?!\w)",
                    enumeration[1],
                )
                quantity_scope = "page" if named_entry else "total"
            quantity_value = {
                "page": seen["count"], "observed": seen["observedCount"], "total": total,
                "remaining": seen["observedCount"] - seen["offset"] - seen["count"],
            }[quantity_scope]
            raw = re.sub(r"[\s-]+", " ", match["number"])
            number = int(raw) if raw.isdecimal() else _CARDINALS[raw]
            bound = match.groupdict().get("bound")
            if quantity_value is None:
                valid = (
                    seen["observedCount"] >= number if bound in {"at least", "al menos"} else
                    seen["observedCount"] > number if bound in {"more than", "mas de"} else False
                )
            else:
                valid = (
                    quantity_value >= number if bound in {"at least", "al menos"} else
                    quantity_value <= number if bound in {"at most", "como maximo"} else
                    quantity_value > number if bound in {"more than", "mas de"} else
                    quantity_value < number if bound in {"less than", "fewer than", "menos de"} else
                    quantity_value == number
                )
            if not valid:
                return "extra_claim" if quantity_value is None else "reversed_result"
            if bound is None:
                stated_page_count |= quantity_scope == "page"
                stated_inventory_count |= quantity_scope in {"observed", "total"}
                # Counting the windows left outside the list discloses the subset.
                stated_subset |= quantity_scope == "remaining" and number > 0
        if _NO_WINDOWS.search(clause) and value != 0:
            return "extra_claim" if value is None else "reversed_result"
        if _HAS_WINDOWS.search(_NO_WINDOWS.sub("", clause)) and value == 0:
            return "reversed_result"
        for claim in _ALL_WINDOWS.finditer(clause):
            # "All windows shown on this page" quantifies the returned page;
            # a page as the subject does not restrict "contains all windows".
            if _PAGE_CONTEXT.search(clause[claim.end():]):
                continue
            negative = bool(_NEGATED_INVENTORY_INCLUSION.search(clause[:claim.start()]))
            if entire_inventory is None:
                return "extra_claim"
            if (not negative) != entire_inventory:
                return "reversed_result" if negative else "extra_claim"
            if negative:
                stated_subset = True
    # Reporting both the smaller page and the larger observed/known inventory
    # explicitly discloses the subset, even without the adjective "partial".
    stated_subset |= stated_page_count and stated_inventory_count and seen["count"] < seen["observedCount"]
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
    parts = _SEPARATORS.split("\n".join(fold(line) for line in text.splitlines()))
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
    feedback = window_fact_feedback(text, payload, user_text)
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
