"""The floor of an action: the final said from the turn's facts alone when no draft could be published.

M107 (DEV-D unseen run, 2026-10-01): twelve actions ended with no visible final («composition_failed:
no_response;retry_exhausted») — every draft was refused and the last resort had nothing for their operation — and two
more on the M102 path that moves a notification (notification.cancel.latest then notification.schedule). An action's
result can always be said: the operation, whether it was verified, failed or left uncertain, and what was observed
(the name of what was acted on, a list read, a state read after). Every word comes from data/operation_floor.v1.json —
one plain clause per catalog operation — and from the observation; nothing the result did not hold is stated. The App
reads the same data (Baxy.App.OperationFloor) and builds the same sentence when the mind returned none.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

_DATA = Path(__file__).resolve().parent / "data" / "operation_floor.v1.json"
_MISSION_CAUSES = frozenset({"mission_completed", "mission_failed"})
_LONGEST_NAME = 120
_LONGEST_CONTENT = 200
_LISTED_NAMES = 3


@lru_cache(maxsize=1)
def floor_data() -> dict:
    return json.loads(_DATA.read_text(encoding="utf-8"))


def failure_sentences() -> dict[str, tuple[str, str]]:
    """The typed failures whose cause is said whole: code -> (Spanish, English)."""

    return {code: (texts["es"], texts["en"]) for code, texts in floor_data()["failures"].items()}


def floor_final(situation: dict, english: bool, now: datetime | None = None) -> str:
    """The sentence for one operation result or one mission, or "" when the facts carry no action to tell."""

    if not isinstance(situation, dict):
        return ""
    templates = floor_data()["templates"]["en" if english else "es"]
    cause = str(situation.get("cause") or "").strip().lower()
    if cause in _MISSION_CAUSES:
        return _sentence(_mission(situation, cause, english, templates, now))
    if situation.get("kind") != "operation":
        # Progress, questions, conversation, a turn not understood: no action named to tell. A sentence with no
        # operation in it would be a fixed reply (owner's review of M75: the ⚠ stays there).
        return ""
    return _sentence(_step(situation, english, templates, now))


def _mission(situation: dict, cause: str, english: bool, templates: dict, now: datetime | None) -> str:
    steps = _decoded_steps(situation.get("steps"))
    told = [
        clause for step in steps
        if not (len(steps) > 1 and _entry(step).get("quiet"))
        and (clause := _step(step, english, templates, now))
    ]
    if cause == "mission_completed":
        return _joined(told, templates)
    reason = _decoded(situation.get("reason"))
    failed = _step(reason, english, templates, now) if isinstance(reason, dict) and reason.get("operation") else ""
    if not told:
        # Nothing done before: the failed step is the whole report, or there is no action to name.
        return failed
    failed = failed or templates["rest"]
    # An uncertain step already carries its own «but» («intenté…, pero no pude confirmar…»).
    uncertain = isinstance(reason, dict) and _uncertain(reason)
    return _joined(told, templates) + templates["and" if uncertain else "but"] + failed


def _step(step: dict, english: bool, templates: dict, now: datetime | None) -> str:
    entry = _entry(step)
    if not entry:
        return ""
    language = "en" if english else "es"
    observed = _observed(step)
    if step.get("verified") is True and step.get("succeeded") is True:
        if entry.get("noSuccessFloor"):
            return ""
        unchanged = entry.get("unchanged")
        if isinstance(unchanged, dict) and observed.get(unchanged["key"]) is False:
            said = unchanged["values"].get(str(observed.get("kind") or "")) or unchanged["values"][""]
            return said[language]
        variant = _variant(entry, observed)
        clause = (variant or entry)[language][1] + _object(entry, observed, language, templates)
        if entry.get("when"):
            clause += _when(step, observed, templates, now)
        return templates["done"].format(clause=clause + _detail(entry, variant, observed, language, templates))
    if str(step.get("polarity") or "") == "pending":
        # A confirmation still owed is asked, not told.
        return ""
    # Only a verified result picks its variant by what it observed (muted, on, the kind set): a state read beside a
    # failure is the one that held, not the one asked.
    clause = entry[language][0] + _object(entry, observed, language, templates, step.get("target"))
    return templates["uncertain" if _uncertain(step) else "failed"].format(clause=clause)


def _uncertain(step: dict) -> bool:
    """The effect may have happened and was not confirmed: neither done nor failed."""

    return step.get("effectUncertain") is True or (step.get("succeeded") is True and step.get("verified") is not True)


def _entry(step: object) -> dict:
    if not isinstance(step, dict) or step.get("kind", "operation") != "operation":
        return {}
    return floor_data()["operations"].get(str(step.get("operation") or ""), {})


def _variant(entry: dict, observed: dict) -> dict | None:
    """The variant of the operation the observation names (muted or not, on or off, the kind set), if any."""

    variants = entry.get("variants")
    if not isinstance(variants, dict):
        return None
    value = observed.get(variants["key"])
    key = ("true" if value else "false") if isinstance(value, bool) else str(value or "")
    return variants["values"].get(key)


def _usable(value: object, longest: int = _LONGEST_NAME) -> str:
    text = " ".join(value.split()) if isinstance(value, str) else ""
    if not text or len(text) > longest or "«" in text or "»" in text:
        return ""
    return text


def _named(value: object, templates: dict) -> str:
    text = _usable(value)
    return " " + templates["quote"].format(value=text) if text else ""


def _object(entry: dict, observed: dict, language: str, templates: dict, target: object = None) -> str:
    """What was acted on: the step's target when it names one, else the first identifying field observed, and who
    made it when the read names them. Nothing for an operation whose target is no name to say (a search query, a
    folder key)."""

    if entry.get("anonymous"):
        return ""
    data = floor_data()
    keys = [None] if isinstance(target, str) else data["identity"]
    for key in keys:
        named = _named(target if key is None else observed.get(key), templates)
        if named:
            word = (entry.get("objectWord") or {}).get(language)
            byline = _usable(observed.get(data["byline"]["key"]))
            by = data["byline"][language].format(value=byline) if byline else ""
            return (f" {word}{named}" if word else named) + by
    return ""


def _when(step: dict, observed: dict, templates: dict, now: datetime | None) -> str:
    """The verified time of a scheduled notification, at this PC's clock: the next run Windows read back for an alarm
    (both the due and the next run observed), the stored due of a reminder record."""

    due = _utc(observed.get("dueUtc"))
    if step.get("operation") == "notification.schedule":
        due = _utc(observed.get("nextRunUtc")) if due is not None else None
    if due is None:
        return ""
    local = due.astimezone()
    today = (now or datetime.now().astimezone()).astimezone().date()
    article = templates["articleOne" if local.hour == 1 else "article"]
    clock = f"{local:%H:%M}"
    if local.date() == today:
        said = templates["whenToday"]
    elif local.date() == today + timedelta(days=1):
        said = templates["whenTomorrow"]
    else:
        said = templates["whenDate"]
    said = said.format(article=article, clock=clock, day=local.day, month=templates["months"][local.month - 1])
    return " " + " ".join(said.split())


def _utc(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    stamp = value.strip().replace("Z", "+00:00")
    head, dot, rest = stamp.partition(".")
    if dot:
        digits = len(rest) - len(rest.lstrip("0123456789"))
        stamp = f"{head}.{rest[:min(digits, 6)]}{rest[digits:]}"
    try:
        parsed = datetime.fromisoformat(stamp)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _detail(entry: dict, variant: dict | None, observed: dict, language: str, templates: dict) -> str:
    specs = [*(entry.get("facts") or []), *((variant or {}).get("facts") or []), *floor_data()["facts"]]
    facts = [said for fact in specs if (said := _fact(fact, observed, language))]
    content = _content(entry, observed, templates)
    if content:
        facts.append(content)
    if facts:
        return templates["detail"] + templates["list"].join(facts)
    listed = _listing(observed, templates)
    return templates["listDetail"] + listed if listed else ""


def _fact(fact: dict, observed: dict, language: str) -> str:
    value = observed.get(fact["key"])
    if "values" in fact:
        said = fact["values"].get(value) if isinstance(value, str) else None
        return said[language] if said else ""
    texts = fact[language]
    if isinstance(value, bool):
        return texts[0 if value else 1] if len(texts) == 2 else ""
    if isinstance(value, (int, float)):
        return texts[0].format(value=f"{value:g}" if isinstance(value, float) else value)
    text = _usable(value)
    return texts[0].format(value=text) if text and len(texts) == 1 else ""


def _content(entry: dict, observed: dict, templates: dict) -> str:
    if not entry.get("content"):
        return ""
    for key in floor_data()["content"]:
        text = _usable(observed.get(key), _LONGEST_CONTENT)
        if text:
            return templates["content"].format(value=templates["quote"].format(value=text))
    return ""


def _listing(observed: dict, templates: dict) -> str:
    """How many items a read listed and the first names, as the read wrote them; nothing when no list was read."""

    data = floor_data()
    count = next((observed[key] for key in data["listCounts"] if type(observed.get(key)) is int), None)
    for key, value in observed.items():
        if not isinstance(value, list):
            continue
        names: list[str] = []
        for item in value:
            name = _usable(item) if isinstance(item, str) else next(
                (said for field in data["listNames"] if isinstance(item, dict) and (said := _usable(item.get(field)))),
                "",
            )
            if name and name not in names:
                names.append(name)
        if not names:
            # An empty list beside others («failures»: []) is not the read's answer; only its count says nothing.
            continue
        total = count if count is not None else observed.get(f"{key}Count")
        total = total if type(total) is int else len(value)
        quoted = [templates["quote"].format(value=name) for name in names[:_LISTED_NAMES]]
        listed = _joined(quoted, templates)
        return templates["countOne" if total == 1 else "countNamed"].format(count=total, names=listed)
    if count == 0:
        return templates["none"]
    return templates["count"].format(count=count) if count is not None else ""


def _joined(parts: list[str], templates: dict) -> str:
    if len(parts) <= 1:
        return "".join(parts)
    return templates["list"].join(parts[:-1]) + templates["and"] + parts[-1]


def _sentence(text: str) -> str:
    text = text.strip()
    if not text:
        return ""
    lead = len(text) - len(text.lstrip("«¿¡\"'"))
    text = text[:lead] + text[lead].upper() + text[lead + 1:]
    return text if text.endswith((".", "!", "?")) else text + "."


def _decoded(value: object) -> object:
    if isinstance(value, str) and value.lstrip().startswith("{"):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None
    return value


def _decoded_steps(steps: object) -> list[dict]:
    return [step for raw in (steps if isinstance(steps, list) else []) if isinstance(step := _decoded(raw), dict)]


def _observed(step: dict) -> dict:
    """The observation of a result with its read-back state lifted (``state``/``final``: muted, level), as
    llm._lift_observed_blob reads it."""

    observed = step.get("observed")
    if not isinstance(observed, dict):
        return {}
    lifted = dict(observed)
    state = observed.get("state") if isinstance(observed.get("state"), dict) else observed.get("final")
    if isinstance(state, dict):
        if "muted" in state:
            lifted["muted"] = state["muted"]
        level = state.get("volumePercent", state.get("level"))
        if level is not None and "level" not in observed:
            lifted["level"] = level
    return lifted
