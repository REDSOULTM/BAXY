"""Finals said from the result without a draft: each operation's own sentence, the floor said first,
and the finals of searches and absent labels.
"""

from __future__ import annotations

import json
import re
import string
import urllib.error
import urllib.parse
import urllib.request
from datetime import timedelta

from . import operation_floor
from .semantic.normalize import _accent_folded_with_punctuation, fold
from .semantic import dialogue as dialogue_slot
from .semantic import claims as semantic_claims
from .semantic.web import weather_asked_measures, weather_asked_clock, searched_clause, news_lookup_query
from .semantic.temporal import clock_later_asked
from .semantic.request import fold as _reading_fold
from .semantic.conversation import asked_act_clause
from .semantic.notes import new_list_title
from .semantic.web import (
    _weather_asks_rain, _weather_asks_tomorrow, weather_asks_future, weather_asks_later_in_the_day,
    weather_asks_rain_now, weather_asks_whether_it_rains,
)
from .clock_facts import _local_now
from .compose_situation import (
    _cause_fact_key, _computer_use_mission, _decoded_reason, _has_cause_fact, _merged_observed, _situation_steps,
    _verified_notification_due,
)
from .device_facts import _capture_unmet_floor, _unreceived_floor
from .search_report import _places_inside_named_place, _search_results_of, _search_results_text
from .listing_facts import _closed_tabs_final, _page_read_final, _tab_listing_final
from .agenda_facts import _alarm_offer_final, _listed_task_titles, _offered_alarms
from .weather_facts import (
    _decimal_said, _forecast_day_said, _raining_now, _sky_said, _weather_date_said, _WEATHER_MONTHS,
    _weather_rain_final, _weather_weekday_said, _weekday_said,
)
from .compose_instructions import _ALREADY_SHOWN_AUTHORITY, _opened_search_in_navigation
from .computer_use_finals import _computer_use_floor, _UNCONFIRMED_ONLY_CODES, _unmatched_play


# A7 (goal v3 paso 5, «un resultado verificado siempre se puede decir»): when every draft was vetoed or the writer
# ran out of time, a verified result is still told, with its observed values copied into one short sentence per
# operation in the person's language. It passes the same publishable() gate as any draft and never states an effect
# the result did not verify. The typed failures say only the cause the result carries (M54 levels at their end, M60
# typed causes, M101 asked states already held); since M107 they live in data/operation_floor.v1.json, which the App's
# twin reads too, beside the plain clause of every operation that the floor of any other result is built from.
_DETERMINISTIC_FAILURES = operation_floor.failure_sentences()


def _spelled_as_read(clause: str, payload: dict) -> str:
    """M81 (DEV-D v3m D-w08-t1 «cuanto qedo el america anoche» → «No encontré cuánto qedo el america anoche»): a word
    of the not-found clause that no result writes, one letter away from a word the results write the same way
    otherwise, is the person's typo said back; the results' spelling is used (owner, 2026-09-19: what was misheard or
    mistyped BAXY fixes)."""

    written: dict[str, str] = {}
    for word in re.findall(r"[^\W\d_]{4,}", _search_results_text(payload) or ""):
        written.setdefault(_reading_fold(word), word.lower() if not word.isupper() else word)
    if not written:
        return clause

    def respelled(found: re.Match[str]) -> str:
        word = found.group(0)
        key = _reading_fold(word)
        if len(key) < 4 or key in written:
            return word
        # A letter left out inside the word («qedo» of «quedó»); a different or an added last letter is an inflection
        # («llueve» / «llueva», «casa» / «casas»), never a typo to fix.
        near = [
            seen for folded, seen in written.items()
            if len(folded) == len(key) + 1
            and any(folded[:index] + folded[index + 1:] == key for index in range(1, len(key)))
        ]
        return near[0] if len(near) == 1 else word

    return re.sub(r"[^\W\d_]+", respelled, clause)


def _asked_news_headlines_final(payload: dict, user_text: str, language: str) -> str:
    """M81: the first three headlines of a news read, quoted as read, when the person asked what is happening
    (``semantic.web.news_lookup_query``) and the news feed answered; empty otherwise."""

    seen = payload.get("seen") if isinstance(payload.get("seen"), dict) else {}
    if not str(seen.get("authority") or "").startswith("google_news") or news_lookup_query(user_text or "") is None:
        return ""
    titles = [
        re.sub(r"\s+", " ", str(item.get("title") or "")).strip(" «»\"")
        for item in _search_results_of(payload) if isinstance(item, dict)
    ]
    titles = [title for title in titles if title][:3]
    if not titles:
        return ""
    quoted = "; ".join(f"«{title}»" for title in titles)
    return f"Here are the headlines: {quoted}." if language == "en" else f"Estas son las noticias: {quoted}."


def _ran_out_of_time(error: BaseException) -> bool:
    """Revisión r19b: whether a writer that did not answer ran out of time (a timeout, also one urllib wraps) rather
    than losing its local connection; only the first is told as the time that ran out (_search_untold_finals)."""

    reason = error.reason if isinstance(error, urllib.error.URLError) else error
    return isinstance(reason, TimeoutError)


def _search_untold_finals(situation: dict, payload: dict, user_text: str, language: str) -> list[str]:
    """Ronda 19b (r17 t3-c14): the finals of a verified web search whose writer ran out of time before any draft, in
    order of preference: what was asked, in the person's words (else the query sent), then the bare one; each says
    the cause, the time that ran out (data: operation_floor «searchUntold»). Empty for anything else, or for a search
    that brought no result (its not-found is told from the pages, not from the time)."""

    if situation.get("operation") != "web.search" or situation.get("verified") is not True:
        return []
    if situation.get("succeeded") is False or not _search_results_of(payload):
        return []
    english = language == "en"
    words = operation_floor.floor_data().get("searchUntold", {}).get("en" if english else "es")
    if not isinstance(words, dict):
        return []
    observed = situation.get("observed") if isinstance(situation.get("observed"), dict) else {}
    finals: list[str] = []
    for source in dict.fromkeys((user_text, str(observed.get("query") or ""))):
        read = searched_clause(source, language)
        if read is not None:
            clause, asked = read
            finals.append(words["asked" if asked else "named"].format(clause=_spelled_as_read(clause, payload)))
    finals.append(words["bare"])
    return list(dict.fromkeys(finals))


def _held_fact_final(situation: dict, language: str) -> str:
    """Ronda 24 (r23 t4-c04, t2-c04 #3): the state's own fact when no draft could word a correction that already
    holds (``alreadyHolds``, by its kind) or an undo whose antecedent changed nothing (``undoNothing``), filled with
    what the state verified (data: operation_floor «heldFact»). A kind may list its sentences, the fullest first
    (encargo TZ-HOLD: «Ya está sonando «{title}» en {named}.», else without the title); the first whose facts the
    state carries is said. Empty when the situation carries neither, or no sentence of its kind has its facts."""

    words = operation_floor.floor_data().get("heldFact", {}).get("en" if language == "en" else "es", {})
    held = situation.get("alreadyHolds") if isinstance(situation, dict) else None
    if isinstance(held, dict):
        sentences, values = words.get(str(held.get("kind") or "")), held
    elif isinstance(situation, dict) and isinstance(situation.get("undoNothing"), dict):
        sentences, values = words.get("undoNothing"), situation["undoNothing"]
    else:
        return ""
    filled = {str(key): " ".join(str(value).split()) for key, value in values.items() if isinstance(value, str)}
    for sentence in [sentences] if isinstance(sentences, str) else sentences if isinstance(sentences, list) else []:
        try:
            if isinstance(sentence, str) and all(filled.get(key) for key in _template_fields(sentence)):
                return sentence.format(**filled)
        except (KeyError, IndexError, ValueError):
            continue
    return ""


def _template_fields(sentence: str) -> list[str]:
    return [field for _text, field, _spec, _conversion in string.Formatter().parse(sentence) if field]


def _deterministic_final(situation: dict, payload: dict, user_text: str, language: str) -> str:
    """The final of a result no draft could tell: its own sentence when the operation has one (_told_result_final),
    else the floor every action has (M107, operation_floor): the plain clause of the operation, done, failed or left
    uncertain, with what was observed — and for a mission, each step's."""

    held = _held_fact_final(situation, language)
    if held:
        return held
    told = (
        _told_result_final(situation, payload, user_text, language)
        or _absent_label_final(situation, language)
        or operation_floor.cancelled_final(situation, language == "en", _local_now())
    )
    final = (
        told
        or operation_floor.with_family_cause(
            operation_floor.floor_final(situation, language == "en", _local_now()), situation, language == "en",
        )
        or _not_understood_floor(situation, user_text, language)
    )
    # Revisión r22 (bloqueante 1): the place the capture could not be kept in is said beside what was done.
    unmet = " ".join(
        part for part in (_capture_unmet_floor(payload, language), _unreceived_floor(payload, language)) if part
    ) if final else ""
    return f"{final} {unmet}" if unmet else final


# Pasada r18 (v3-64): a click that found nothing called that told «no hay ningún elemento etiquetado como "tipo de
# inicio"» while the label looked for was «Ordenar por tipo de inicio» and the column header «Tipo de inicio» was on
# the screen. What a not-found click looked for is named only as it was looked for.
_ABSENT_LABEL_ERRORS = frozenset({"visible_button_not_found", "visible_control_label_mismatch"})
_QUOTED_SPAN = re.compile(r"[«\"“]([^«»\"“”\n]{1,160})[»\"”]")


def _plain_words(value: object) -> str:
    return " ".join(re.findall(r"\w+", _accent_folded_with_punctuation(value).casefold()))


def _absent_click(situation: dict) -> dict | None:
    """The failed click a turn tells whose label nothing on the screen carried (directly or as a failure's reason)."""

    if not isinstance(situation, dict):
        return None
    for record in (situation, _decoded_reason(situation)):
        if (
            isinstance(record, dict)
            and record.get("operation") == "input.visible.click"
            and record.get("succeeded") is not True
            and str(record.get("error") or "") in _ABSENT_LABEL_ERRORS
            and isinstance(record.get("attempted"), dict)
            and isinstance(record["attempted"].get("label"), str)
            and record["attempted"]["label"].strip()
        ):
            return record
    return None


def _absent_label_misquoted(text: str, situation: dict) -> bool:
    """A final of a not-found click that quotes, as what it looked for, anything but the label it looked for (or
    another fact of the attempt, such as its window). A final with no quote says nothing about the label's words."""

    record = _absent_click(situation)
    if record is None:
        return False
    allowed = {_plain_words(value) for value in record["attempted"].values() if isinstance(value, str)}
    # Revisión 3: a plan whose earlier steps were made tells each of them (the M107 floor counts every step); the
    # names those steps carry are facts of the turn, quoted as much as the label looked for.
    allowed |= {_plain_words(value) for value in _step_strings(_situation_steps(situation))}
    return any(_plain_words(span) not in allowed for span in _QUOTED_SPAN.findall(text or ""))


# Revisión F (H4): «…», "…", “…”, ‘…’ and '…' standing as quotes (an apostrophe inside a word is no quote).
_ANY_QUOTED_SPAN = re.compile(r"[«\"“‘]([^«»\"“”‘’\n]{1,160})[»\"”’]|(?<!\w)'([^'\n]{1,160})'(?!\w)")


def _quotes_what_it_was_not_given(text: str, payload: dict, user_text: str, said: str | None) -> bool:
    """Estabilización F (tanda estab2 t2-c07 t1: over a message sent whose receipt carried only the text's hash, the
    final quoted «Llego en 10 min y llevo el cargador», words no fact held and the person never said that way): a final
    over an operation's result quotes, two words or more, only what its payload, the request or the person's own
    message write. Revisión F (H1, t3-c17 t4, t4-c02 t4): a query travels inside a URL, percent-encoded; it is read
    decoded. A paraphrase with no quotes is beyond this check."""

    if not any(key in payload for key in ("operation", "completedStepsInOrder", "reason")):
        return False
    written = [urllib.parse.unquote_plus(value) for value in _step_strings(payload)]
    given = f" {_plain_words(' '.join((*written, user_text or '', said or '')))} "
    return any(
        len(words := _plain_words(span).split()) >= 2 and f" {' '.join(words)} " not in given
        for span in (first or second for first, second in _ANY_QUOTED_SPAN.findall(text or ""))
    )


def _step_strings(value: object) -> list[str]:
    """Every string a mission's steps carry (their names, labels and observed facts), at any depth."""

    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [text for item in value.values() for text in _step_strings(item)]
    if isinstance(value, list):
        return [text for item in value for text in _step_strings(item)]
    return []


def _absent_label_final(situation: dict, language: str) -> str:
    """The data template of a not-found click (operation_floor.v1.json «computerUse.absentLabel»): its label, quoted."""

    record = _absent_click(situation)
    if record is None or _situation_steps(situation):
        # Revisión 3: «no pulsé nada» is true only of a turn with no step made; with earlier steps done, the M107 floor
        # tells each one (OperationFloor.ComputerUseMission asks the same of a mission's reason).
        return ""
    words = operation_floor.floor_data()["computerUse"]["absentLabel"]
    return words["en" if language == "en" else "es"].replace("{label}", record["attempted"]["label"].strip())


def _floor_first_final(situation: dict, payload: dict, user_text: str, language: str) -> str:
    """Estabilización F (owner, 2026-10-11: «Lo que el suelo determinista de frases sabe decir no lo redacta el modelo.
    Ningún final afirma algo no verificado»; tandas estab1/estab2: «Se le envió a Ron92 el mensaje…» and «No he enviado
    el mensaje…» over a send left unconfirmed, «No pude contarte cómo salió lo que pediste.», a sent text quoted as the
    writer made it up). A result the floor says (operation_floor.tells_first: failed, uncertain, cancelled, a state
    already there, a verified content) is said from the facts before any draft, as the last resort would say it
    (_deterministic_final); so is a play verified to be something else (its own sentence, _told_result_final). The
    writer keeps what the floor cannot say: a failure whose code carries a cause the sentence leaves out, the steps
    done before such a failure, any other verified result. "" leaves the turn to the writer."""

    if not isinstance(situation, dict) or _computer_use_mission(situation) is not None:
        return ""
    if _unmatched_play(situation):
        # Revisión 1 r24u (bloqueante 1): over a play not shown to be the query only the result's own sentence tells it.
        return _told_result_final(situation, payload, user_text, language)
    if not operation_floor.tells_first(situation):
        return ""
    cause = str(situation.get("cause") or "").strip().lower()
    failed = _decoded_reason(situation) if cause in {"mission_failed", "result_unverified"} else situation
    # The cause a failure's code carries for the writer: any code of a step not done (m134: «known_file_not_found»
    # reached the writer as «no está en Descargas»); of a step left uncertain, only a code with a fact of its own.
    uncertain = isinstance(failed, dict) and failed.get("effectUncertain") is True
    untold = (
        isinstance(failed, dict) and bool(failed.get("operation"))
        and not (failed.get("verified") is True and failed.get("succeeded") is True)
        and any(
            _has_cause_fact(code) or not uncertain for code in (failed.get("error"), failed.get("cause"))
            if isinstance(code, str) and code and code not in _UNCONFIRMED_ONLY_CODES
        )
    )
    plain = operation_floor.floor_final(situation, language == "en", _local_now())
    if _situation_steps(situation) and cause != "remaining_steps_cancelled":
        # A plan with steps made: only the floor's own sentence tells each of them (a typed sentence tells one step).
        return "" if untold else plain
    final = _deterministic_final(situation, payload, user_text, language)
    return "" if untold and plain and (final == plain or final.startswith(plain + " ")) else final


# D59 §7 (owner, 2026-10-02; supersedes the owner's review of M75 that left D-w02-t2 with no final): a turn not
# understood, or a question about it that no draft could write, is asked with the person's own words.
_NOT_UNDERSTOOD_CAUSES = frozenset({"turn_runtime_failure", "turn_contract_failure"})


def _not_understood_floor(situation: dict, user_text: str, language: str) -> str:
    kind = str(situation.get("kind") or "")
    cause = str(situation.get("cause") or "").strip().lower()
    if not (
        (kind == "failure" and cause in _NOT_UNDERSTOOD_CAUSES)
        # Only the plain «what do you mean»: a question for a missing value asks that value.
        or (kind == "clarification" and cause == "ambiguous_request" and not situation.get("requiredInput"))
    ):
        return ""
    if str(situation.get("understoodAs") or "").strip():
        # Estabilidad cu-v3 2026-10-08 (v2-v3-61, «¿Qué quieres que haga con "en seguridad de windows decime
        # cuándo…"?»): the turn was understood (the kind it was understood as travels) and only its wording failed;
        # the person's words are never asked back. A failure says its short cause (data: words_floor_question
        # «understood»); a question has nothing to ask.
        return dialogue_slot.understood_failure_line(language) if kind == "failure" else ""
    return dialogue_slot.words_floor_question(user_text, "en" if language == "en" else "es")


def _open_search_final(situation: dict, open_search: dict, english: bool) -> str:
    """Semilla fix2/fix3: the search already open in the person's browser, read instead of opened again, when no draft
    told what was asked of it (the page was an error, or every draft was refused): it is still where they see it, and
    reading it to them is offered. A read that failed says so. After a correction the words told last are never told
    again (``correctedFinal``): the second wording is used then."""

    site, query = str(open_search.get("site") or ""), open_search["query"]
    read = situation.get("verified") is True and situation.get("succeeded") is True
    # Review r10a finding 7: the wording is data (operation_floor «webSearch»), not prose in code.
    said = operation_floor.floor_data()["webSearch"]["en" if english else "es"]
    if isinstance(situation.get("searchOutOfView"), dict):
        # Review r10a finding 2: the page in front was not the search; nothing of it is told.
        first, second = said["outOfView"], said["outOfViewAgain"]
    else:
        first, second = said["openRead"] if read else said["openUnread"], said["openAgain"]
    first, second = first.format(site=site, query=query), second.format(site=site, query=query)
    corrected = situation.get("correctedFinal")
    previous = corrected.get("previousReply") if isinstance(corrected, dict) else None
    return second if isinstance(previous, str) and " ".join(previous.split()) == first else first


def _told_result_final(situation: dict, payload: dict, user_text: str, language: str) -> str:
    english = language == "en"
    operation = str(situation.get("operation") or payload.get("operation") or "")
    seen = payload.get("seen") if isinstance(payload.get("seen"), dict) else {}
    mission_final = _computer_use_floor(situation, english)
    if mission_final:
        return mission_final
    open_search = situation.get("openSearch")
    if not isinstance(open_search, dict):
        # Review r10a finding 2: the read found another page in front; the search is said out of view.
        open_search = situation.get("searchOutOfView")
    if (
        isinstance(open_search, dict)
        and isinstance(open_search.get("query"), str)
        and "«" not in open_search["query"] and "»" not in open_search["query"]
    ):
        return _open_search_final(situation, open_search, english)
    if (
        operation == "browser.page.read"
        and situation.get("verified") is True
        and situation.get("succeeded") is True
        and (page_final := _page_read_final(seen, english))
    ):
        return page_final
    if (
        operation in {"browser.navigate", "browser.navigate.named"}
        and situation.get("verified") is True
        and situation.get("succeeded") is True
        and (opened_search := _opened_search_in_navigation(situation)) is not None
        and "«" not in opened_search[1] and "»" not in opened_search[1]
    ):
        # Semilla fix2 t1: every draft ran out of time and the floor said only «Abrí la página.»; a results page
        # verified open is told as the search it is.
        # Review r10a: the wording is data (finding 7), and a page that was already on show before the link, with no
        # window seen to open (authority «user_browser_front_already_showed»), is said as already open (finding 6).
        site, query = opened_search
        said = operation_floor.floor_data()["webSearch"]["en" if english else "es"]
        already = _merged_observed(situation).get("authority") == _ALREADY_SHOWN_AUTHORITY
        return said["alreadyOpen" if already else "opened"].format(site=site, query=query)
    if (
        operation == "browser.tabs.list"
        and situation.get("verified") is True
        and situation.get("succeeded") is True
        and (tabs_final := _tab_listing_final(seen, english))
    ):
        return tabs_final
    if (
        operation == "browser.control"
        and situation.get("verified") is True
        and situation.get("succeeded") is True
        and seen.get("action") == "close_all"
        and (closed_final := _closed_tabs_final(seen, english))
    ):
        return closed_final
    if (
        operation == "browser.control"
        and situation.get("succeeded") is not True
        and seen.get("action") == "close_all"
        and type(seen.get("closedTabs")) is int
        and seen["closedTabs"] > 0
    ):
        closed = seen["closedTabs"]
        if english:
            return f"I closed {closed} {'tab' if closed == 1 else 'tabs'}; I couldn't close the rest, they're still open."
        return f"Cerré {closed} {'pestaña' if closed == 1 else 'pestañas'}; no pude cerrar las demás, siguen abiertas."
    if situation.get("verified") is not True or situation.get("succeeded") is not True:
        reason = situation.get("reason")
        if isinstance(reason, str) and reason.lstrip().startswith("{"):
            try:
                reason = json.loads(reason)
            except json.JSONDecodeError:
                reason = None
        codes = [situation.get("error"), situation.get("cause")]
        if isinstance(reason, dict):
            codes[:0] = [reason.get("error"), reason.get("cause")]
        for code in codes:
            if isinstance(code, str) and code in _DETERMINISTIC_FAILURES:
                spanish, english_text = _DETERMINISTIC_FAILURES[code]
                return english_text if english else spanish
        stopped_step = reason if isinstance(reason, dict) and reason.get("operation") else situation
        for code in codes:
            # Uso real t2-r4 c01-1: a play stopped because the person used the PC (input_user_interrupted) ended in
            # «No pude confirmar el resultado con…»; the stop causes the floor knows (computerUse.causes) are said.
            if isinstance(code, str) and (stopped := operation_floor.stopped_final(stopped_step, code, english)):
                return stopped
        if any(code in {"out_of_catalog", "out-of-catalog"} for code in codes if isinstance(code, str)):
            # M101 (DEV-D v3z D-s037, D-s042): a decided limit is said in BAXY's own words with the thing asked as the
            # person said it, or as the plain limit when it cannot be said that way; never no final.
            opening = "I don't do that" if english else "Eso no lo hago"
            asked = asked_act_clause(user_text, "en" if english else "es")
            return f"{opening}: {asked}." if asked else f"{opening}."
        unverified = reason if isinstance(reason, dict) else situation
        target = str(unverified.get("target") or situation.get("target") or "").strip()
        if target and len(target) <= 200 and "«" not in target and "»" not in target:
            # M101 (DEV-D v3z D-w10-t4 «ponme música tropical en YouTube»): the page opened and playback was not
            # confirmed; three honest drafts died and the turn ended with no final. The unverified effect is reported
            # naming its target, never as done.
            # Uso real t2-r4 c01-2: the same for a video or a page opened in the person's own browser
            # (user_browser_*_unconfirmed), which ended in the generic sentence below. Data: «openedUnconfirmed».
            opened = operation_floor.floor_data()["openedUnconfirmed"]
            for code in codes:
                family = _cause_fact_key(code) if isinstance(code, str) else None
                if family and family != "source" and isinstance(opened.get(family), dict):
                    return opened[family]["en" if english else "es"].format(target=f"«{target}»")
        reminder = reason if isinstance(reason, dict) and reason.get("operation") else situation
        if str(reminder.get("operation") or operation) == "reminder.create":
            # M101b (DEV-D v4a D-w08-t3): a reminder that was not created is said with the cause its code carries.
            if "verification_failed" in codes or reminder.get("effectUncertain") is True:
                return (
                    "I couldn't confirm that the reminder was created."
                    if english
                    else "No pude confirmar que el recordatorio quedara creado."
                )
            if "invalid_reminder" in codes:
                return (
                    "I couldn't create the reminder: the time given has already passed or isn't valid."
                    if english
                    else "No pude crear el recordatorio: la hora indicada ya pasó o no es válida."
                )
            return "I couldn't create the reminder." if english else "No pude crear el recordatorio."
        return ""
    if operation == "system.time" and isinstance(payload.get("clockAt"), str):
        # M85 (DEV-D v3o D-w02-t2): another place's clock, or a said time converted between here and there, is told
        # with the figures _place_clock_facts computed; the hours apart and the zone stay the writer's.
        clock, given = payload.get("clock"), payload.get("given")
        if (
            not isinstance(clock, str) or not re.fullmatch(r"\d{2}:\d{2}", clock)
            or (given is not None and not (isinstance(given, str) and re.fullmatch(r"\d{2}:\d{2}", given)))
            or set(payload) - {"clock", "clockAt", "given", "givenAt", "place", "country", "day", "operation", "kind"}
        ):
            return ""
        here = "here" if english else "aquí"

        def at(place: object) -> str:
            name = str(place or "").strip()
            return here if name == here else (f"in {name}" if english else f"en {name}")

        day = str(payload.get("day") or "").strip()
        if english:
            then = f"it's {clock} {at(payload['clockAt'])}" + (f", {day}" if day else "")
            return (f"If it's {given} {at(payload.get('givenAt'))}, {then}." if given else then[:1].upper() + then[1:] + ".")
        then = f"{at(payload['clockAt'])} son las {clock}" + (f" {re.sub(r'^el ', 'del ', day)}" if day else "")
        return f"Si {at(payload.get('givenAt'))} son las {given}, {then}." if given else then[:1].upper() + then[1:] + "."
    if operation == "system.time" and not set(payload) - {
        "weekday", "until", "days_until", "hours_until", "operation", "kind",
    } and _reading_fold(str(payload.get("until") or "")) in {"finde", "fin de semana", "weekend"}:
        # M87 (DEV-D v3r D-s001 «¿cuántas horas quedan para el finde?»): three drafts refused and no final; the days or
        # hours left until the weekend are counted by _calendar_facts, and this states them with today's weekday.
        weekday, days, hours = payload.get("weekday"), payload.get("days_until"), payload.get("hours_until")
        if not isinstance(weekday, str) or not weekday or type(days) is not int:
            return ""
        if days == 0:
            return f"Today is {weekday}: it's the weekend." if english else f"Hoy es {weekday}: ya es fin de semana."
        left = str(hours) if isinstance(hours, str) and hours else (
            f"{days} day{'s' if days != 1 else ''}" if english else f"{days} día{'s' if days != 1 else ''}"
        )
        if english:
            return f"Today is {weekday}; {left} left until the weekend."
        return f"Hoy es {weekday}; {'queda' if left.startswith('1 ') else 'quedan'} {left} para el fin de semana."
    if operation == "system.time":
        clock = payload.get("clock")
        if not isinstance(clock, str) or not re.fullmatch(r"\d{2}:\d{2}", clock) or set(payload) - {
            "clock", "operation", "kind",
        }:
            return ""
        if clock_later_asked(user_text) is not None:
            return f"It will be {clock}." if english else f"Serán las {clock}."
        return f"It's {clock}." if english else f"Son las {clock}."
    observed = situation.get("observed") if isinstance(situation.get("observed"), dict) else {}
    if operation == "reminder.create":
        # M101b (DEV-D v4a D-w08-t3 «ponme recordatorio una ora antes d ese partido»): the verified reminder carried no
        # observed record and the three drafts died (extra_claim) on a date the facts did not hold; the final says what
        # was verified — the reminder created, with its title when the record was read — and no time it did not read.
        title = str(observed.get("title") or "").strip()
        named = f" «{title}»" if title and len(title) <= 120 and "«" not in title and "»" not in title else ""
        # M106: once the record reaches the mind its verified due is said at the person's clock, as an alarm's is.
        due = _verified_notification_due(situation)
        when = ""
        if due is not None:
            local = due.astimezone()
            today = _local_now().date()
            clock = f"{'la' if local.hour == 1 else 'las'} {local:%H:%M}"
            spanish_month, english_month = _WEATHER_MONTHS[local.month - 1]
            if english:
                day = (
                    "" if local.date() == today
                    else "tomorrow at " if local.date() == today + timedelta(days=1)
                    else f"{english_month} {local.day} at "
                )
                when = f" for {day}{local:%H:%M}"
            else:
                day = (
                    "" if local.date() == today
                    else "mañana a " if local.date() == today + timedelta(days=1)
                    else f"el {local.day} de {spanish_month} a "
                )
                when = f" para {day}{clock}"
        return f"I created the reminder{named}{when}." if english else f"Creé el recordatorio{named}{when}."
    if operation == "audio.microphone.mute" and type(observed.get("muted")) is bool:
        # M101 (owner script v3z2): a verified microphone change is told with the state read after it.
        if observed["muted"]:
            return "The microphone is muted." if english else "El micrófono está silenciado."
        return "The microphone is on." if english else "El micrófono está activo."
    if operation in {"audio.volume", "audio.volume.adjust"} and type(seen.get("level")) is int:
        # The master output only; an application's own level is another read.
        level = seen["level"]
        direction = seen.get("direction")
        muted = seen.get("muted") is True
        if english:
            head = (
                f"I turned the volume {'down' if direction == 'down' else 'up'} to {level}%"
                if direction in {"down", "up"}
                else f"The volume is at {level}%"
            )
            return head + ("; it is muted." if muted else ".")
        head = (
            f"{'Bajé' if direction == 'down' else 'Subí'} el volumen a {level} %"
            if direction in {"down", "up"}
            else f"El volumen está en {level} %"
        )
        return head + ("; está silenciado." if muted else ".")
    if operation in {"media.status", "media.control"} and seen.get("playbackStatus") in {"playing", "paused"}:
        # v3a DEV-A s009/s034/s054: a verified read or control of the session that was playing had its three drafts
        # vetoed; what was observed is the session's title, artist and state after the call.
        title = str(seen.get("title") or "").strip()
        if not title:
            return ""
        artist = str(seen.get("artist") or "").strip()
        playing = seen["playbackStatus"] == "playing"
        if english:
            by = f" by {artist}" if artist else ""
            return f"Now playing «{title}»{by}." if playing else f"«{title}»{by} is paused."
        by = f" de {artist}" if artist else ""
        return f"Está sonando «{title}»{by}." if playing else f"Está en pausa «{title}»{by}."
    if (
        operation in semantic_claims.service_operations()
        and seen.get("playbackStatus") == "playing"
        and semantic_claims.service_of(operation, seen.get("provider"))
    ):
        # Uso real tanda 1 (t1-c01, t1-c07): what was put on is told with the service it plays in.
        title = str(seen.get("title") or "").strip()
        if not title or seen.get("titleObserved") is False:
            return ""
        service = semantic_claims.service_of(operation, seen.get("provider"))
        where = "" if fold(title).endswith(fold(service)) else semantic_claims.service_place(service, english)
        # Revisión 1 r24u (bloqueante 1): what plays was not shown to be the query; it is said as what plays, with
        # that fact beside it, never as the request done.
        unmatched = semantic_claims.unmatched_play_clause(semantic_claims.unmatched_play(operation, seen), english)
        return f"Now playing «{title}»{where}{unmatched}." if english else f"Está sonando «{title}»{where}{unmatched}."
    if operation == "weather.current" and isinstance(seen.get("location"), str):
        out_of_reach = seen.get("outOfReach")
        if isinstance(out_of_reach, dict):
            # M78: the limit of the read, said with the dates it has (_weather_asked_reach).
            if out_of_reach.get("read") == "airQuality":
                return (
                    "The air quality is only read as it is now, not for a later time."
                    if english
                    else "La calidad del aire sólo se lee como está ahora, no para más adelante."
                )
            if out_of_reach.get("askedTime") == "past":
                # M79 (DEV-D v3m s003): a day already gone is before the read.
                return (
                    f"I only read the weather in {seen['location']} from today on, not past days."
                    if english
                    else f"El tiempo de {seen['location']} sólo lo leo desde hoy, no el de días pasados."
                )
            asked = _weather_date_said(out_of_reach.get("askedDate"), english)
            until = _weather_date_said(out_of_reach.get("readUntil"), english)
            if not asked or not until:
                return ""
            return (
                f"The forecast for {seen['location']} only goes up to {until}; {asked} is beyond it."
                if english
                else f"El pronóstico de {seen['location']} llega sólo hasta el {until}; el {asked} queda fuera."
            )
        if isinstance(seen.get("askedDay"), dict):
            said = _forecast_day_said(seen["askedDay"], english)
            when = _weather_date_said(seen["askedDay"].get("date"), english)
            if not said or not when:
                return ""
            return f"In {seen['location']}, {when}: {said}." if english else f"En {seen['location']}, el {when}: {said}."
        if isinstance(seen.get("askedDays"), list) and seen["askedDays"]:
            # Uso real v3 tanda 1 «this weekend»: each day of the span asked, by its weekday; today and tomorrow asked
            # beside it («mañana y el finde») by their own names.
            observed = situation.get("observed") if isinstance(situation.get("observed"), dict) else {}
            relative = {
                str(block.get("date")): names
                for key, names in (("today", ("hoy", "today")), ("tomorrow", ("mañana", "tomorrow")))
                if isinstance(block := observed.get(key), dict) and block.get("date")
            }
            labelled = [
                (
                    relative[str(day.get("date"))][0] if str(day.get("date")) in relative
                    else f"el {_weather_weekday_said(day, False)}",
                    relative[str(day.get("date"))][1] if str(day.get("date")) in relative
                    else _weather_weekday_said(day, True),
                    day,
                )
                for day in seen["askedDays"] if isinstance(day, dict)
            ]
            if weather_asks_whether_it_rains(user_text or "") and not weather_asks_rain_now(user_text or ""):
                answer = _weather_rain_final(seen["location"], labelled, english)
                if answer:
                    return answer
            parts = []
            for spanish, english_name, day in labelled:
                said = _forecast_day_said(day, english)
                if not said or spanish == "el " or not english_name:
                    return ""
                parts.append(f"{english_name}: {said}" if english else f"{spanish}: {said}")
            return f"In {seen['location']}, {'; '.join(parts)}." if english else f"En {seen['location']}, {'; '.join(parts)}."
        folded_request = fold(user_text or "")
        day: dict | None = None
        day_name = ""
        for block in seen.get("laterDays") or []:
            weekday = str(block.get("weekday") or "") if isinstance(block, dict) else ""
            if weekday and re.search(rf"\b{re.escape(fold(weekday))}\b", folded_request):
                day, day_name = block, weekday
                break
        if day is None and _weather_asks_tomorrow(user_text or "") and isinstance(seen.get("tomorrow"), dict):
            day, day_name = seen["tomorrow"], ("tomorrow" if english else "mañana")
        if weather_asks_whether_it_rains(user_text or "") and not weather_asks_rain_now(user_text or ""):
            # M63 (v3f-final F-w01-t6): «¿va a llover?» (today or tomorrow) is answered plainly, not with the day's
            # figures beside a sky its own chance contradicts.
            if day is not None:
                rain_days = [("mañana", "tomorrow", day)]
            else:
                rain_days = [("hoy", "today", seen.get("today"))]
                if weather_asks_future(user_text or ""):
                    rain_days.append(("mañana", "tomorrow", seen.get("tomorrow")))
            answer = _weather_rain_final(seen["location"], rain_days, english)
            if answer:
                return answer
        if day is None:
            if not isinstance(seen.get("temperatureC"), (int, float)) or not isinstance(seen.get("condition"), str):
                return ""
            temperature = _decimal_said(seen["temperatureC"], english)
            now = (
                f"In {seen['location']} it is {temperature} °C now, {_sky_said(seen['condition'], True)}"
                if english
                else f"En {seen['location']} hay {temperature} °C ahora, {seen['condition']}"
            )
            today_rain = (seen.get("today") or {}).get("rainProbabilityPercent") if isinstance(
                seen.get("today"), dict
            ) else None
            if weather_asks_rain_now(user_text or "") and isinstance(seen.get("precipitationMm"), (int, float)):
                # M60 (DEV-D w11-t1): the rain asked now is the rain read now.
                raining = _raining_now(seen)
                now += (
                    ("; it is raining now" if raining else "; it isn't raining now")
                    if english
                    else ("; está lloviendo" if raining else "; no llueve ahora")
                )
            elif _weather_asks_rain(user_text or "") and isinstance(today_rain, (int, float)) and not (
                weather_asks_future(user_text or "")
            ):
                # The rain asked for today, with no hour, is today's probability.
                said = _decimal_said(today_rain, english)
                now += f"; {said}% chance of rain today" if english else f"; hoy, {said} % de lluvia"
            today = seen.get("today")
            if weather_asked_clock(user_text or "") is not None and not (
                weather_asked_measures(user_text or "") - {"temperature"}
            ) and isinstance(today, dict) and all(
                isinstance(today.get(key), (int, float)) for key in ("minC", "maxC", "rainProbabilityPercent")
            ):
                # M97 (DEV-D v3x D-s014 «¿qué previsión de tiempo hay para las cuatro?»): the hour asked is not in the
                # read; the day it falls in is, and the reply says the read is not by the hour.
                low, high, rain = (
                    _decimal_said(today[key], english) for key in ("minC", "maxC", "rainProbabilityPercent")
                )
                return (
                    f"I don't read the forecast by the hour; today in {seen['location']}: {low} to {high} °C, "
                    f"{rain}% chance of rain."
                    if english
                    else f"El pronóstico no lo leo por horas; hoy en {seen['location']}: de {low} a {high} °C, "
                    f"{rain} % de lluvia."
                )
            if weather_asks_later_in_the_day(user_text or "") and not _weather_asks_rain(user_text or "") and not (
                weather_asked_measures(user_text or "") - {"temperature"}
            ) and isinstance(today, dict) and all(
                isinstance(today.get(key), (int, float)) for key in ("minC", "maxC", "rainProbabilityPercent")
            ):
                # M62 (v3e2-final F-p07-t1 «…later today»): a later part of today is today's read too.
                low, high, rain = (
                    _decimal_said(today[key], english) for key in ("minC", "maxC", "rainProbabilityPercent")
                )
                return (
                    f"{now}; today: {low} to {high} °C, {rain}% chance of rain."
                    if english
                    else f"{now}; hoy: de {low} a {high} °C, {rain} % de lluvia."
                )
            coming = seen.get("tomorrow") if weather_asks_future(user_text or "") else None
            said = _forecast_day_said(coming, english) if isinstance(coming, dict) else ""
            if said:
                # M58 (v3d-final F-s066): asked in the future with no day, what is coming is tomorrow's read too.
                return f"{now}; tomorrow: {said}." if english else f"{now}; mañana: {said}."
            return f"{now}."
        said = _forecast_day_said(day, english)
        if not said:
            return ""
        return (
            f"In {seen['location']}, {_weekday_said(day_name, True)}: {said}."
            if english
            else f"En {seen['location']}, el {day_name}: {said}."
            if day_name != "mañana"
            else f"En {seen['location']}, mañana: {said}."
        )
    if operation == "notification.list" and (offer := _offered_alarms(payload, user_text)) is not None:
        return _alarm_offer_final(offer, english)
    if operation == "task.list" and _listed_task_titles(payload):
        # M58 (v3d-final F-w05-t4): the open tasks read, each title once with how many times it is there.
        open_titles = [
            str(task.get("title")).strip() for task in seen.get("tasks") or []
            if isinstance(task, dict) and isinstance(task.get("title"), str) and task.get("title").strip()
            and not task.get("completed") and not task.get("deleted")
        ]
        named = []
        for title in _listed_task_titles(payload):
            times = open_titles.count(title)
            again = "" if times == 1 else (f" ({times} times)" if english else f" ({times} veces)")
            named.append(f"«{title}»{again}")
        listed = ", ".join(named[:-1]) + (" and " if english else " y ") + named[-1] if len(named) > 1 else named[0]
        return f"Pending: {listed}." if english else f"Tienes pendientes {listed}."
    if operation == "window.resolve" and isinstance(seen.get("windows"), list):
        names: list[str] = []
        for window in seen["windows"]:
            if not isinstance(window, dict):
                continue
            name = str(window.get("title") or window.get("processName") or "").strip()
            if name and name not in names:
                names.append(name)
        if not names:
            return ""
        total = seen.get("totalCount") if seen.get("complete") is True else seen.get("observedCount")
        listed = seen.get("count")
        partial = type(total) is int and type(listed) is int and listed < total
        if english:
            head = f"There are {total} windows; this page lists {listed}: " if partial else "Open windows: "
        else:
            head = f"Hay {total} ventanas; en esta página van {listed}: " if partial else "Ventanas abiertas: "
        return head + ", ".join(names) + "."
    if operation == "web.search" and seen.get("authority") == "openstreetmap_nominatim":
        # M54 (v3b-final F-p06-t3): the places OpenStreetMap returned inside the asked place are the answer, so they
        # are told by their names and streets as the read writes them (the nearest first), never as not found.
        places: list[str] = []
        for item in _places_inside_named_place(payload)[:3]:
            title = str(item.get("title") or "").strip()
            parts = [part.strip() for part in str(item.get("snippet") or "").split(",") if part.strip()]
            if parts and _reading_fold(parts[0]) == _reading_fold(title):
                parts = parts[1:]
            # A house number is not a street («8, Calle de Hernán Cortés»).
            street = next((part for part in parts if not part.isdigit()), "")
            # A place without a name is titled by its OpenStreetMap type, in lower case («parking»): its street names it.
            generic = not title or title.islower()
            place = street if generic else (f"{title} ({street})" if street else title)
            # M62 (v3e2-final F-p05-t1): how far each is from the named place.
            meters = item.get("distanceMeters")
            if place and isinstance(meters, int) and not isinstance(meters, bool):
                away = f"{meters} m" if meters < 1000 else _decimal_said(round(meters / 1000, 1), english) + " km"
                place = f"{place} ({'' if english else 'a '}{away}{' away' if english else ''})"
            if place and place not in places:
                places.append(place)
        if not places:
            return ""
        listed = ", ".join(places[:-1]) + (" and " if english else " y ") + places[-1] if len(places) > 1 else places[0]
        return f"I found: {listed}." if english else f"Encontré: {listed}."
    if operation == "web.news.headlines" and isinstance(seen.get("headlines"), list):
        # M60 (DEV-D s032 q4): the headlines read are the answer, quoted as the feed wrote them (three at most).
        titles = [
            str(item.get("title")).strip(" :;,.-–—|")
            for item in seen["headlines"]
            if isinstance(item, dict) and isinstance(item.get("title"), str) and item.get("title").strip(" :;,.-–—|")
        ][:3]
        if not titles:
            return ""
        quoted = "; ".join(f"«{title}»" for title in titles)
        topic = str(seen.get("topic") or "").strip()
        if english:
            return f"Headlines about {topic}: {quoted}." if topic else f"Headlines: {quoted}."
        return f"Titulares sobre {topic}: {quoted}." if topic else f"Titulares: {quoted}."
    if operation in {"task.create", "task.delete", "task.complete"} and isinstance(seen.get("title"), str):
        # M60 (DEV-D s067 q4 «Pon patatas y patatas y huevos en la lista de deseos»): the item written is named by
        # the title the store verified, the person's own words.
        title = seen["title"].strip()
        if not title:
            return ""
        verbs = {
            # D59.5: a new list asked for empty is created, nothing is added to it.
            "task.create": ("Creé la lista", "I created the list") if new_list_title(user_text or "") else (
                "Añadí", "I added"),
            "task.delete": ("Quité", "I removed"),
            "task.complete": ("Marqué como hecho", "I marked as done"),
        }[operation]
        return f"{verbs[1]} «{title}»." if english else f"{verbs[0]} «{title}»."
    return ""
