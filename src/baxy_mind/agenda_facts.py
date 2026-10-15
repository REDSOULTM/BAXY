"""Alarms, timers, reminders, tasks and lists: their projections for the composer, the offers and finals said
from them, the titles of the records written, and the checks of a reply about them.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from typing import Iterable

from .semantic import dialogue as dialogue_slot
from .semantic.temporal import plural_alarm_cancellation, said_durations, spoken_clocks, spoken_date, spoken_day
from . import effect_intent
from .semantic.request import fold as _reading_fold
from .semantic.notes import new_list_title
from .clock_facts import _local_now, _parse_core_utc
from .compose_situation import _merged_observed, _situation_steps, _verified_notification_due
from .search_report import _search_results_of


def _local_today() -> date:
    """The local date the listing is told from (one place, so a recorded read can be judged on its own day)."""

    return _local_now().date()


def _project_notification_listing(observed: dict, language: str) -> dict:
    """AGENDA1435 «listá los timers»: kind, title and next run of each scheduled
    alarm or reminder, plus the count; the task identities stay out.

    Tanda 9 «Would you show me my alarms?» → «"alarm" at "2026-09-25 14:00", "alarm" at "2026-09-25 14:00"…»: the
    next run goes as the person hears it — its local clock, and its day only when it is not today («tomorrow» as
    the word, a later day as its date) — and equal entries go once with how many there are."""

    entries = observed.get("notifications")
    scheduled: list[dict] = []
    today = _local_today()
    for entry in (entries if isinstance(entries, list) else []):
        if not isinstance(entry, dict):
            continue
        kind = entry.get("kind")
        label = {
            "alarm": ("alarma", "alarm"),
            "reminder": ("recordatorio", "reminder"),
        }.get(str(kind), (str(kind), str(kind)))[1 if language == "en" else 0]
        item: dict = {"kind": label}
        if isinstance(entry.get("title"), str) and entry["title"].strip():
            item["title"] = entry["title"].strip()
        next_run = entry.get("nextRunUtc")
        if isinstance(next_run, str) and next_run:
            try:
                instant = datetime.fromisoformat(next_run.replace("Z", "+00:00"))
            except ValueError:
                instant = None
            if instant is None:
                item["nextRun"] = next_run
            else:
                local = (instant if instant.tzinfo else instant.replace(tzinfo=timezone.utc)).astimezone()
                item["time"] = f"{local:%H:%M}"
                if local.date() == today + timedelta(days=1):
                    item["day"] = "tomorrow" if language == "en" else "mañana"
                elif local.date() != today:
                    item["date"] = local.date().isoformat()
        same = next((earlier for earlier in scheduled if {k: v for k, v in earlier.items() if k != "howMany"} == item), None)
        if same is not None:
            same["howMany"] = same.get("howMany", 1) + 1
        else:
            scheduled.append(item)
    count = observed.get("count") if type(observed.get("count")) is int else len(scheduled)
    return {"count": count, "scheduled": scheduled}


def _rings_in(due: datetime, user_text: str, language: str) -> str | None:
    """M110 (DEV-F v4d F-w09-t4 «avisame en 15 minutes…», F-w45-t1 «gimme a 25 minute countdown»): how long until a
    verified notification rings, as the person said it when they gave a length (within two minutes of the verified
    due), or counted when they said no clock or day at all («go with 12» after «How long…?»); None otherwise, or a day
    or more ahead."""

    remaining = (due - _local_now()).total_seconds() / 60
    if not 0 < remaining < 24 * 60:
        return None
    said = next((literal for literal, minutes in said_durations(user_text) if abs(minutes - remaining) <= 2), None)
    if said is not None:
        return said
    folded = _reading_fold(user_text)
    if spoken_clocks(folded) or spoken_day(folded, 0) != (0, 1) or spoken_date(folded) is not None:
        return None
    hours, minutes = divmod(round(remaining), 60)
    english = language == "en"
    parts = []
    if hours:
        parts.append(f"{hours} {'hour' if english else 'hora'}{'' if hours == 1 else 's'}")
    if minutes or not hours:
        parts.append(f"{minutes} {'minute' if english else 'minuto'}{'' if minutes == 1 else 's'}")
    return (" and " if english else " y ").join(parts)


def _project_scheduled_notification(observed: dict, situation: dict, language: str, user_text: str = "") -> dict:
    """Tanda 5 «set 30 minute timer» died three times in missing_state: the receipt carried only UTC instants
    (dueUtc/nextRunUtc 16:57) and the drafts said 14:27, 16:57 and 17:27 for a timer due at 13:57 local. The person
    hears their own clock: the verified next run goes as local time (and its date when it is not today); the UTC
    instants, the task name and the authority stay with the checks. Tanda 6b: given «2026-09-25» at 21:55 on the
    24th, the drafts said «today» and «on 2026-09-25»; tomorrow goes as the word the person hears."""

    projected: dict = {}
    title = observed.get("title")
    if isinstance(title, str) and title.strip():
        projected["title"] = title.strip()
    due = _verified_notification_due(situation)
    if due is not None:
        local = due.astimezone()
        today = _local_now().date()
        projected["scheduledLocalTime"] = f"{local:%H:%M}"
        if local.date() == today + timedelta(days=1):
            projected["scheduledDay"] = "tomorrow" if language == "en" else "mañana"
        elif local.date() != today:
            projected["scheduledLocalDate"] = local.date().isoformat()
        rings_in = _rings_in(local, user_text, language)
        if rings_in is not None:
            projected["ringsIn"] = rings_in
    return projected


def _project_cancelled_notification(observed: dict, situation: dict, language: str) -> dict:
    """M110 (DEV-F v4d F-w21-t5 «quítame la de las 6:40», F-w35-t4 «quítame la de las 5 y 10» → «Cancelé la alarma.»):
    the cancelled alarm or reminder is told by its local time (and its day when it is not today), the one the
    verified absence read was about; the task name and the UTC instants stay with the checks."""

    projected: dict = {}
    if isinstance(observed.get("canceled"), bool):
        projected["canceled"] = observed["canceled"]
    kind = observed.get("kind")
    if kind in {"alarm", "reminder"}:
        projected["kind"] = {"alarm": ("alarma", "alarm"), "reminder": ("recordatorio", "reminder")}[kind][
            1 if language == "en" else 0
        ]
    clock = _cancelled_local_clock(observed)
    if clock is not None:
        projected["time"] = f"{clock:%H:%M}"
        today = _local_now().date()
        if clock.date() == today + timedelta(days=1):
            projected["day"] = "tomorrow" if language == "en" else "mañana"
        elif clock.date() != today:
            projected["date"] = clock.date().isoformat()
    elif type(observed.get("hour")) is int and 0 <= observed["hour"] <= 23:
        minute = observed.get("minute") if type(observed.get("minute")) is int else 0
        projected["time"] = f"{observed['hour']:02d}:{minute:02d}"
    return projected


def _cancelled_local_clock(observed: dict) -> datetime | None:
    """The local moment the cancelled notification was due, from the verified read (its expected next run)."""

    for key in ("expectedNextRunUtc", "nextRunUtc"):
        value = observed.get(key)
        if isinstance(value, str) and value:
            parsed = _parse_core_utc(value)
            if parsed is not None:
                return parsed.astimezone()
    return None


def _local_clock_text(iso_utc: str) -> str | None:
    """A UTC ISO instant as local «YYYY-MM-DD HH:MM»; None when unparsable."""

    try:
        instant = datetime.fromisoformat(iso_utc.replace("Z", "+00:00"))
    except ValueError:
        return None
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=timezone.utc)
    return instant.astimezone().strftime("%Y-%m-%d %H:%M")


def _observed_local_clocks(situation: dict) -> frozenset[str]:
    """Every local «HH:MM» a verified reading observed: the next run of each
    listed alarm or reminder, the sunrise and sunset of a weather read
    (Uso real tanda 2 «el horario de la caída del sol para mañana»: the
    observed 19:45 was refused as an invented clock), and the times the pages
    of a web search write."""

    if situation.get("verified") is not True or situation.get("succeeded") is not True:
        return frozenset()
    observed = _merged_observed(situation)
    if situation.get("operation") == "notification.cancel.at":
        # M110: the cancelled one is told by its time («Cancelé la alarma de las 6:40.»).
        projected = _project_cancelled_notification(observed, situation, "es")
        return frozenset({projected["time"]}) if "time" in projected else frozenset()
    if situation.get("operation") == "notification.list":
        entries = observed.get("notifications")
        return frozenset(
            local[-5:]
            for entry in (entries if isinstance(entries, list) else [])
            if isinstance(entry, dict)
            and isinstance(entry.get("nextRunUtc"), str)
            and (local := _local_clock_text(entry["nextRunUtc"])) is not None
        )
    if situation.get("operation") == "weather.current":
        return frozenset(
            clock
            for day in ("today", "tomorrow")
            if isinstance(block := observed.get(day), dict)
            for key in ("sunrise", "sunset")
            if isinstance(clock := block.get(key), str) and re.fullmatch(r"\d\d:\d\d", clock)
        )
    if situation.get("operation") == "web.search":
        # Uso real tanda 4f «¿el sábado podremos comer en una terraza en Sevilla?»: the three
        # drafts reported «entre las 12:00 y las 14:00» from a page and died as invented clocks, and the turn
        # ended in the bare list of titles. A time a page writes is the page's, reported as the page's.
        return frozenset(
            f"{int(hour):02d}:{minute}"
            for item in _search_results_of(situation)
            if isinstance(item, dict)
            for key in ("title", "snippet")
            for hour, minute in re.findall(r"(?<!\d)(\d{1,2}):(\d{2})(?!\d)", str(item.get(key) or ""))
        )
    if situation.get("operation") == "mission.computer.use":
        # Live 2026-10-07 (v2-v9 «en el Reloj andá a Reloj mundial» → «Ya estoy en Reloj mundial, que marca las 7:58.»;
        # v2-u7/v2-w1 «… andá a Alarma» → «… la alarma de las 7:00»): nine drafts died as invented clocks and the
        # turns ended in the floor. A clock the window wrote at the end of the mission is what the loop observed.
        from . import cu_projection as _cu_projection
        from . import cu_reply_checks as _cu_reply_checks

        return _cu_reply_checks.screen_clocks(_cu_projection.project_seen(observed, "es")) | (
            _clocks_written_in_observed_titles(observed)
        )
    return _clocks_written_in_observed_titles(observed)


# M134 (DEV-F v4l2 F-w59-t2 «yeah sure mañana at 6:30 pm» → task.create titled «comprar huevos, leche de avena y
# tortillas, mañana a las 18:30»): «He creado la tarea "…, mañana a las 18:30"» quoted the observed title and died as
# an invented clock (extra_claim) in all three drafts; the turn ended in ⚠. A clock written inside what a verified read
# or write observed as a name or a text is that title's words, not a reading of the PC's clock. Only those keys count:
# a timestamp («createdAtUtc») is UTC, never a local clock to say.
_TITLED_CLOCK_KEYS = frozenset({"title", "name", "text", "details"})


def _clocks_written_in_observed_titles(observed: object) -> frozenset[str]:
    clocks: set[str] = set()

    def walk(value: object, key: str = "", depth: int = 0) -> None:
        if depth > 6:
            return
        if isinstance(value, str):
            if key in _TITLED_CLOCK_KEYS:
                clocks.update(
                    f"{int(hour):02d}:{minute}"
                    for hour, minute in re.findall(r"(?<!\d)(\d{1,2}):(\d{2})(?!\d)", value)
                )
        elif isinstance(value, dict):
            for child_key, child in value.items():
                walk(child, str(child_key), depth + 1)
        elif isinstance(value, (list, tuple)):
            for child in value:
                walk(child, key, depth + 1)

    walk(observed)
    return frozenset(clocks)


def _known_listing_in_payload(payload: dict) -> dict | None:
    """The projected listing («seen» with names) of a verified known-folder listing."""

    if payload.get("operation") not in {"filesystem.known.list", "game.catalog.list"}:
        return None
    seen = payload.get("seen")
    if isinstance(seen, dict) and isinstance(seen.get("names"), list):
        return seen
    return None


def _listing_fact_defect(text: str, seen: dict) -> str:
    """A quoted name must be a listed name; a number must be one of the counts."""

    listed = {_reading_fold(str(name)) for name in seen.get("names") or []}
    for quoted in re.findall(r'[«"“]([^»"”]{1,4096})[»"”]', text):
        candidate = _reading_fold(quoted.strip().rstrip(".,;:"))
        if candidate and candidate not in listed:
            return "listing_unlisted_name"
    counts = {
        str(seen.get(key)) for key in ("count", "fileCount", "folderCount", "shownNames", "moreNotShown")
        if type(seen.get(key)) is int
    }
    prose = re.sub(r'[«"“][^»"”]{1,4096}[»"”]', " ", text)
    for number in re.findall(r"(?<![\w.-])\d+(?![\w.-])", prose):
        if number not in counts:
            return "listing_wrong_count"
    return ""


def _listed_task_titles(payload: dict) -> list[str]:
    """The distinct titles of the open tasks a verified task.list read, in order («ice cream» twice is one)."""

    if not isinstance(payload, dict) or payload.get("operation") != "task.list":
        return []
    seen = payload.get("seen")
    if not isinstance(seen, dict) or not isinstance(seen.get("tasks"), list):
        return []
    titles = [
        str(task.get("title")).strip()
        for task in seen["tasks"]
        if isinstance(task, dict) and isinstance(task.get("title"), str) and task.get("title").strip()
        and not task.get("completed") and not task.get("deleted")
    ]
    return list(dict.fromkeys(titles))


# M153: a task told as done (folded): «están completadas», «ya las terminaste», «marqué como hechas», «is completed»,
# «you've already finished», «all done». A clause that denies it («no», «ninguna», «sin», «not», «none», «yet») is not.
_TASK_DONE_CLAIM = re.compile(
    r"\b(?:esta|estan|quedo|quedaron|fue|fueron)\s+(?:ya\s+)?(?:todas\s+|todos\s+)?"
    r"(?:completad|terminad|hech|tachad|resuelt)[oa]s?\b|"
    r"\bya\s+(?:(?:las|la|los|lo)\s+)?(?:completaste|terminaste|hiciste|tachaste|marcaste|resolviste)\b|"
    r"\bmarque\s+como\s+(?:hech|complet|terminad)|"
    r"\b(?:is|are|was|were|been)\s+(?:all\s+|already\s+)?(?:completed|done|finished|(?:checked|crossed|ticked)\s+off)\b|"
    r"\byou(?:'ve|\s+have)?\s+(?:already\s+)?(?:completed|finished|(?:checked|crossed|ticked)\s+off)\b|"
    r"\ball\s+done\b|\bi\s+(?:marked|completed|(?:checked|crossed|ticked)\s+off)\b"
)
_TASK_DONE_DENIED = re.compile(
    r"\b(?:no|ni|ningun[ao]?|nada|nunca|sin|not|none|nothing|never|neither|yet)\b|n't\b"
)


def _says_tasks_done(folded: str) -> bool:
    return any(
        _TASK_DONE_CLAIM.search(clause) is not None and _TASK_DONE_DENIED.search(clause) is None
        for clause in re.split(r"[.;:!?¿¡\n]|\b(?:pero|but)\b", folded)
    )


_TASK_COUNT_WORDS = {
    "un": "1", "una": "1", "uno": "1", "one": "1", "another": "1", "otra": "1", "otro": "1", "dos": "2", "two": "2",
    "tres": "3", "three": "3", "cuatro": "4", "four": "4", "cinco": "5", "five": "5", "seis": "6", "six": "6",
    "siete": "7", "seven": "7", "ocho": "8", "eight": "8", "nueve": "9", "nine": "9", "diez": "10", "ten": "10",
}
_TASK_COUNT = r"(?P<n>\d+|" + "|".join(sorted(_TASK_COUNT_WORDS, key=len, reverse=True)) + r")"
_TASKS_MORE = re.compile(
    rf"\b{_TASK_COUNT}\s+(?:(?:tareas?|pendientes?|cosas?|tasks?|items?|things?)\s+)?(?:mas|more)\b"
)
_TASKS_TOTAL = re.compile(rf"\b(?:tienes|hay|you\s+have|there\s+are)\s+{_TASK_COUNT}\s+(?:tareas|pendientes|tasks)\b")


def _alarm_offer_seen(observed: dict, listing: dict) -> dict:
    """D39 and M62: what the offer for «cancela las alarmas» is said from — the alarms read, each clock once with how
    many ring at it, their number (reminders are not offered), and whether the yes can cancel them all (``offer``
    «all») or the person is asked which one (``offer`` «which»: an alarm shares its minute with another, there are
    more than a plan holds, or the read was cut; ``dialogue.offered_alarm_clocks``).

    v3e2-final F-s040: given the whole listing («count»: 38, reminders and alarms), the offer said «ocho alarmas» for
    six times over sixteen alarms read."""

    alarms = [
        {key: entry[key] for key in ("time", "day", "date", "howMany") if key in entry}
        for entry in listing.get("scheduled") or []
        if isinstance(entry, dict) and entry.get("kind") in {"alarma", "alarm"} and isinstance(entry.get("time"), str)
    ]
    seen: dict = {
        "alarmCount": sum(int(entry.get("howMany") or 1) for entry in alarms),
        "alarms": alarms,
        "offer": "all" if dialogue_slot.offered_alarm_clocks(observed) is not None else "which",
    }
    if observed.get("resultsMayBeTruncated") is True:
        seen["moreNotRead"] = True
    return seen


def _offered_alarms(payload: dict, user_text: str) -> dict | None:
    """D39: the offer's reading (``_alarm_offer_seen``) of a verified read for «cancela las alarmas», or None when the
    payload is not that read."""

    if not isinstance(payload, dict) or payload.get("operation") != "notification.list":
        return None
    seen = payload.get("seen")
    if not isinstance(seen, dict) or not isinstance(seen.get("alarms"), list) or not plural_alarm_cancellation(
        user_text or ""
    ):
        return None
    return seen


_ALARM_CANCEL_CLAIM = re.compile(
    r"\b(?:cancele|he\s+cancelado|(?:ya\s+)?(?:estan|quedaron|fueron)\s+(?:canceladas|borradas|eliminadas)|borre|"
    r"elimine|quite|apague|desactive|i\s+(?:cancell?ed|deleted|removed|turned\s+off)|(?:have|has|were|are)\s+been\s+"
    r"(?:cancell?ed|deleted|removed))\b"
)


def _alarm_offer_defect(text: str, payload: dict, user_text: str) -> str:
    """D39 (owner, 2026-09-29): «cancela las alarmas» is answered with the alarms read and the offer to cancel them
    («Tienes 3 alarmas (7:00, 8:30 y 12:00). ¿Las cancelo todas?»): nothing was cancelled yet, every time read is
    said, and with any alarm the reply asks."""

    offer = _offered_alarms(payload, user_text)
    if offer is None:
        return ""
    alarms = offer["alarms"]
    if _ALARM_CANCEL_CLAIM.search(_reading_fold(text)) is not None:
        return "effect_claim"
    if alarms and (
        "?" not in text
        or any(entry["time"] not in text and entry["time"].lstrip("0") not in text for entry in alarms)
    ):
        return "alarm_offer_missing"
    # M62 (v3e2-final F-s040 «Hay ocho alarmas a las 05:20, 06:00, 06:45, 08:30, 08:40 y 09:00»): how many alarms are
    # said is how many were read (seen.alarmCount), or how many times ring when each time is counted once.
    prose = _reading_fold(text)
    questions = " ".join(re.findall(r"¿[^?]*\?|[^.;:!?¿]*\?", prose))
    if offer.get("offer") == "which" and re.search(
        r"\bcancel(?:o|amos)\s+todas\b|\bcancel(?:arlas|alas)\s+todas\b|\bcancel\s+(?:them\s+)?all\b", questions,
    ):
        # The yes could not cancel them all (``_alarm_offer_seen``): it is not offered.
        return "alarm_offer_not_whole"
    for found in _ALARMS_TOTAL.finditer(prose):
        if _TASK_COUNT_WORDS.get(found.group("n"), found.group("n")) not in {
            str(offer["alarmCount"]), str(len(alarms)),
        }:
            return "alarm_count_wrong"
    return ""


_ALARMS_TOTAL = re.compile(
    rf"\b(?:tienes|hay|son|you\s+have|there\s+are)\s+(?:(?:un\s+total\s+de|in\s+total)\s+)?{_TASK_COUNT}\s+"
    r"(?:alarmas|alarms)\b"
)


def _alarm_offer_final(offer: dict, english: bool) -> str:
    """D39: the offer said from the read, when no draft could say it."""

    alarms = offer["alarms"]
    if not alarms:
        return "You have no alarms set." if english else "No tienes alarmas programadas."
    count = offer["alarmCount"]
    times = [
        entry["time"] + (f" {entry['day']}" if entry.get("day") else f" ({entry['date']})" if entry.get("date") else "")
        + (f" (×{entry['howMany']})" if int(entry.get("howMany") or 1) > 1 else "")
        for entry in alarms
    ]
    listed = times[0] if len(times) == 1 else ", ".join(times[:-1]) + (" and " if english else " y ") + times[-1]
    if offer.get("offer") == "which":
        # M62: the yes could not cancel them all (several at one time, more than a plan holds, or a cut read).
        return (
            f"You have {count} alarms ({listed}). Which one should I cancel?"
            if english
            else f"Tienes {count} alarmas ({listed}). ¿Cuál cancelo?"
        )
    if count == 1:
        return f"You have one alarm, at {listed}. Shall I cancel it?" if english else (
            f"Tienes una alarma, a las {listed}. ¿La cancelo?"
        )
    return f"You have {count} alarms ({listed}). Shall I cancel them all?" if english else (
        f"Tienes {count} alarmas ({listed}). ¿Las cancelo todas?"
    )


def _task_listing_defect(text: str, payload: dict) -> str:
    """A task list names its tasks by their titles, as written: at least the first five distinct ones."""

    titles = _listed_task_titles(payload)
    folded = _reading_fold(text)
    if any(_reading_fold(title) not in folded for title in titles[:5]):
        return "task_title_not_named"
    if titles and not any(
        isinstance(task, dict) and task.get("completed") for task in payload["seen"]["tasks"]
    ) and _says_tasks_done(_reading_fold(_without_record_titles(text, _record_titles("task.list", payload["seen"])))):
        # M153: with every task read still open, «Ya completaste todas: …», «All done: …» reverses the read; a done task
        # denied («ninguna está completada», «none of them is done yet») is the read itself.
        return "reversed_result"
    if titles:
        # M58 (v3d-final F-w05-t4): «Tienes pendientes "palta y pisco", "ice cream" (2 veces) y una tarea más» over a
        # read of three tasks, all named. How many more there are is how many the reply leaves unnamed; how many there
        # are is the read's count (with or without the repeated titles).
        open_titles = [
            str(task.get("title")).strip() for task in payload["seen"]["tasks"]
            if isinstance(task, dict) and isinstance(task.get("title"), str) and task.get("title").strip()
            and not task.get("completed") and not task.get("deleted")
        ]
        unnamed = [title for title in open_titles if _reading_fold(title) not in folded]
        more = {len(unnamed), len({_reading_fold(title) for title in unnamed})}
        total = {len(open_titles), len(titles)}
        prose = _reading_fold(re.sub(r'[«"“][^»"”]{1,400}[»"”]', " ", text))
        for said, pattern in ((more, _TASKS_MORE), (total, _TASKS_TOTAL)):
            for found in pattern.finditer(prose):
                if _TASK_COUNT_WORDS.get(found.group("n"), found.group("n")) not in {str(n) for n in said}:
                    return "listing_wrong_count"
    return ""


# «if not please add it» whose read found the entry: the add never ran; nothing went on the list.
_LIST_ADD_CLAIM = re.compile(
    r"\b(?:a[nñ]ad[ií]|agregu[eé]|puse|anot[eé]|apunt[eé]|sum[eé]|inclu[ií])\b|"
    r"\bse\s+(?:a[nñ]adi[oó]|agreg[oó]|anot[oó]|a[nñ]adir[aá]|agregar[aá]|anotar[aá])\b|"
    r"\b(?:est[aá]|qued[oó]|queda)\s+(?:a[nñ]adid|agregad|anotad|apuntad)|"
    r"\b(?:i(?:'ve|\s+have)?\s+(?:added|put)|(?:it|they)(?:'s|'re|\s+is|\s+are|\s+was|\s+were|\s+has\s+been|"
    r"\s+have\s+been|\s+will\s+be)\s+(?:now\s+)?added)\b",
    re.IGNORECASE,
)


def _guarded_add_not_run(user_text: str, situation: dict) -> object | None:
    """Tanda 4c «add flour to my shopping list if it's not already on it»: the add waits on the read of the list
    and the App publishes the read alone when it found the entry. The person's list read (entry, list), or None."""

    if situation.get("operation") != "task.search" or situation.get("verified") is not True:
        return None
    listed = effect_intent.list_read_request(user_text or "")
    return listed if listed is not None and listed.absent_clause and listed.entry else None


def _new_empty_list(user_text: str, situation: dict) -> str | None:
    """D59.5 (owner, 2026-10-02): the title of the new list a verified task.create made empty for «crea una lista de la
    compra», «make a packing list» (``semantic.notes.new_list_title``), or None for any other result."""

    if (
        situation.get("operation") != "task.create"
        or situation.get("verified") is not True
        or situation.get("succeeded") is not True
        or new_list_title(user_text or "") is None
    ):
        return None
    seen = _merged_observed(situation)
    title = seen.get("title") if isinstance(seen, dict) else None
    return str(title).strip() if isinstance(title, str) and title.strip() else new_list_title(user_text or "")


# The writes of a task or a note: their verified result names the item by its title, the person's own words.
_TITLED_ITEM_WRITES = frozenset({
    "note.create", "note.update", "note.trash", "note.restore",
    "task.create", "task.update", "task.delete", "task.complete", "task.reopen", "task.restore",
    # M101b (DEV-D v4a D-w08-t3): a reminder is named by its title too («Creé el recordatorio «Partido»»); the
    # rule wanted the word «título» from it, so no report of a read reminder record could pass.
    "reminder.create",
})


def _record_titles(operation: object, observed: object) -> list[str]:
    """M153 (sealed set, v4r→v4s metadata: four task.list reads of 7 open tasks and one notification.schedule ended in
    no_response, every draft and the floor refused): the titles a verified record carries are the person's own words
    read back — a task's or a note's, a reminder's or an alarm's, each task of a list read. Quoted in a reply they are
    data, not BAXY's claims: «Te recordaré a las 22:00 poner el celular en silencio» died three times as a mute claimed
    (extra_claim), a list holding «hago la cena» as a first-person change (reversed_result), and the floor quoting the
    same titles died with them, so the turn had no final. Titles of three characters or more; nothing else of the
    record is masked."""

    if not isinstance(observed, dict):
        return []
    titles: list[object] = []
    if operation in _TITLED_ITEM_WRITES or operation == "notification.schedule":
        titles.append(observed.get("title"))
    if operation == "task.list" and isinstance(observed.get("tasks"), list):
        titles.extend(task.get("title") for task in observed["tasks"] if isinstance(task, dict))
    return [
        title.strip() for title in titles if isinstance(title, str) and 3 <= len(title.strip()) <= 400
    ]


def _without_record_titles(text: str, titles: Iterable[str]) -> str:
    """The text with each whole occurrence of an observed record title blanked (longest first), for the lexical claim
    checks only; the published text keeps every word."""

    for title in sorted(set(titles), key=len, reverse=True):
        text = re.sub(rf"(?<!\w){re.escape(title)}(?!\w)", " ", text, flags=re.IGNORECASE)
    return text


def _situation_record_titles(situation: dict) -> list[str]:
    """``_record_titles`` of a verified result, alone or of each verified step of a mission."""

    return [
        title
        for node in [situation, *_situation_steps(situation)]
        if isinstance(node, dict) and node.get("verified") is True and node.get("succeeded") is True
        for title in _record_titles(node.get("operation"), node.get("observed"))
    ]
