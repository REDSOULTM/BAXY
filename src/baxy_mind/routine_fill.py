"""RUT14: the fields of a routine the person is making are filled in by the model, from what they said.

The owner's case (2026-11-13, BAXY 1.5.2, a model by API): «quiero que todos los lunes, miércoles y viernes a las 10 10
de la mañana digas Buenos días…» → the model called baxy.routines (it carries nothing), the guide began at «¿Con una
palabra tuya o a una hora?» with the days, the hour and the text thrown away, and every answer was compared with fixed
words («No te entendí. Di «con una palabra» o «a una hora»…»): four turns, nothing saved. routine_guide.heard gives
None for that sentence, with or without the «10» the ear wrote twice.

So what the person said is read by the model, in one closed question apart from the conversation (Mind._routine_read,
LlmServer.ask_apart) whose answer is typed by a JSON schema: llama.cpp turns ``response_format`` into a grammar
(tools/server/README.md, «schema-constrained JSON»; grammars/README.md: «The JSON schema is only used to constrain the
model output and is not injected into the prompt», so the fields are described in the question itself), and a model by
API takes the same schema as its structured output (external_model). Every field is a closed list of values or a
text; no number and no list: Anthropic's structured outputs refuse ``minimum``/``maximum`` and array bounds
(platform.claude.com/docs/en/build-with-claude/structured-outputs, read 2026-11-13), and without bounds the 4B wrote
digits, or the same day, until the answer's tokens ran out (the owner's «10 10»: 320 tokens, unreadable, 8.7 s; RUT14's
first runs). The days are one short text («mon wed fri»): a yes/no per day cost 35 tokens of every answer, and each
token is 23 ms on the PC of the measurements. ``does`` goes last: what the words do is said after the fields are written (Tam et al., «Let Me Speak
Freely?», EMNLP 2024 Industry, arXiv 2408.02442: a strict format lowers reasoning; first, read as «other» what had
just given the kind of routine). Slot filling by a model with a typed output instead of rules: Li et al., «Large
Language Models as Zero-shot Dialogue State Tracker through Function Calling», ACL 2024 (arXiv 2402.10466); Hudeček &
Dušek, «Are LLMs All You Need for Task-Oriented Dialogue?», SIGDial 2023 (arXiv 2304.06556: the model's belief state
alone falls short of a checked one, hence the checks below and BAXY's question for what is missing).

What stays deterministic is form (``checked``): the hour exists and its number was said, the half of the day and the
days were said (routine_guide's tables, as validation: a value the person's words do not carry is «not said» and BAXY
asks it), the text BAXY will say or the order it will do is made of the person's own words. Nothing is saved here:
routine_guide.Guide repeats the whole routine and only their «sí» saves.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from . import routine_guide as forms
from .routines import fold

DOES = ("answer", "yes", "no", "cancel", "other")
REPEATS = ("daily", "days", "today", "tomorrow", "once")
# RUT15: every token the 4B writes costs ~44 ms on the RTX 3060 of the measurements (a decision's too: the output matrix
# is in RAM), and RUT14's ten fields of full names, all of them always, were ~100 tokens of every answer to the guide
# (4.4 s of 6.1). So each field is one letter, and only the fields the person's last words give or change are written:
# what is known stays as it is unless they change it («sí, dale» is {"x": "yes"}). The half of the day is the hour's
# own (0 to 23), still taken only when the person said that half (_when). ``x``, what the words do, is still written
# last (Tam et al., below): no field is required, as llama.cpp's grammar puts required properties before the optional
# ones (common/json-schema-to-grammar.cpp, _build_object_rule), and a reply without it reads as an answer.
FIELDS = {"k": "trigger", "h": "hour", "m": "minute", "r": "repeat", "d": "days", "p": "word", "t": "text", "x": "does"}
SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "k": {"type": "string", "enum": ["time", "word"]},
        "h": {"type": "string", "enum": [*map(str, range(24))]},
        "m": {"type": "string", "enum": [*map(str, range(60))]},
        "r": {"type": "string", "enum": list(REPEATS)},
        "d": {"type": "string"},
        "p": {"type": "string"},
        "t": {"type": "string"},
        "x": {"type": "string", "enum": list(DOES)},
    },
    "additionalProperties": False,
}
# RUT15: asked after the conversation the server already holds (Mind._routine_read), as one more message of the
# person's side: these words are the whole question. The examples are a text of their own, in the harness's language
# (harness_language: EXAMPLES has its English in data/harness.en.v1.json).
ASK = (
    "[BAXY is setting up a routine with the person: at an hour on some days BAXY says a text, or when the person says "
    "a word of theirs BAXY does an order. Reply with one JSON object with only the fields their last words give or "
    "change; leave out the rest (what is known stays). Values are the person's own words, copied word for word, never "
    "invented, completed or translated; when they point back to something they said, give what they said then.\n"
    "k: time (at an hour) | word (when the person says a word).\n"
    "h: the hour, 0-23 (afternoon, evening and night are 12-23). m: its minutes, left out when 0.\n"
    "r: daily | days | today | tomorrow | once (one time, no day said). d: with days, the days said: mon tue wed thu "
    "fri sat sun.\n"
    "p: with k word, the word or short phrase the person will say. t: with k time, the text BAXY will say, without the "
    "words asking for it; with k word, the order BAXY will do.\n"
    "x, always, last: answer (they give or correct something) | yes (they accept saving it as BAXY read it back) | no "
    "(they refuse it and change nothing) | cancel (they stop setting it up) | other (not about this routine).\n"
    "{examples}\n\n{said}\n\nKnown so far: {known}\n{asked}The person's last words: «{last}»\n{twice}]")
EXAMPLES = (
    "Examples:\n"
    "«los sábados y domingos a las seis y cuarto de la tarde avísame diciendo ya es hora de salir a correr» → "
    '{"k":"time","h":"18","m":"15","r":"days","d":"sat sun","t":"ya es hora de salir a correr","x":"answer"}\n'
    "«cuando yo diga llegó la visita quiero que pauses la música» → "
    '{"k":"word","p":"llegó la visita","t":"pauses la música","x":"answer"}\n'
    "Known text «arriba dormilón», last words «que digas eso mismo pero a las siete» → "
    '{"h":"7","x":"answer"}\n'
    "BAXY asked «¿La guardo?», last words «de acuerdo, así me sirve» → "
    '{"x":"yes"}')
ASKED = "BAXY just asked: «{asked}»\n"
# A datum for the model, by form only: the same number written twice in a row in their words (the ear does that).
TWICE = ("(Their words have the number «{number}» twice in a row: speech recognizers repeat a number by mistake, so it "
         "is «{number}» said once, an hour with no minutes (h {number}, no m), unless the two clearly are an hour and "
         "its minutes.)\n")
MOST_SAID = 2400    # characters of the conversation the question quotes (its end)
MOST_LINES = 12     # and lines of it: the person's and BAXY's
READ_TOKENS = 64    # RUT15: at most this, so a model by API answers it at its lowest effort (external_model.to_request)
MOST_TIME_WORDS = 16   # words of the longest time said together («que todos los lunes, miércoles y viernes a las 10 10…»)


@dataclass(frozen=True)
class Read:
    """What the model read, once checked against the person's words: ``does`` what their last words do; ``kind`` time,
    word or None; ``when`` the hour and the days said (None: none said or none stood the check); ``phrase`` and ``text``
    as said, or empty; ``fresh`` whether the model read the text in their last words (a text known is replaced only
    by one of those: «digas eso» points back, it gives no new text)."""
    does: str = "answer"
    kind: str | None = None
    when: forms.When | None = None
    phrase: str = ""
    text: str = ""
    fresh: bool = True   # the text is of their last words, not one they point back to
    bare: bool = False   # RUT14B: their last words alone carry nothing of a routine (no time, days, text nor word)


def known(guide: forms.Guide) -> str:
    """What the guide has so far, in the fields of the question (RUT15: only those it has)."""
    return json.dumps({key: value for key, value in _known(guide).items() if value}, ensure_ascii=False)


def _known(guide: forms.Guide) -> dict[str, str]:
    """What the guide has so far, in the reply's fields (one letter each); empty, what it does not have."""
    when = guide.when
    hour = when.hour24()
    repeat = {0: "today", 1: "tomorrow"}.get(when.offset if when.offset is not None else -1, when.repeat or "")
    return {"k": guide.kind or "", "h": "" if when.hour is None else str(hour if hour is not None else when.hour),
            "m": str(when.minute) if when.hour is not None and when.minute else "", "r": repeat,
            "d": " ".join(forms.DAYS[day] for day in when.days), "p": guide.phrase,
            "t": guide.say if guide.kind == "time" else guide.order}


def _twice(last: str) -> str:
    """The number the person's last words have twice in a row («a las 10 10», «a las nueve nueve»), or nothing."""
    return _twice_in(forms._time_words(last))


def _twice_in(words: list[str]) -> str:
    """The number these words have twice in a row, or nothing."""
    for at in range(len(words) - 1):
        first, second = forms._number(words, at, 59), forms._number(words, at + 1, 59)
        if first is not None and second is not None and first[1] == at + 1 and first[0] == second[0]:
            return words[at]
    return ""


def body(said: list[tuple[str, str]], last: str, guide: forms.Guide, asked: str, seed: int) -> dict[str, Any]:
    """The closed question: the conversation's end (who said what), what is known, BAXY's question and their words.
    RUT15: one message, asked after the conversation the server holds (Mind._routine_read puts it there)."""
    lines = [f"{'Person' if who == 'user' else 'BAXY'}: «{' '.join(words.split())}»" for who, words in said[-MOST_LINES:]]
    quoted = "\n".join(lines)[-MOST_SAID:]
    number = _twice(last)
    note = ASK.format(examples=EXAMPLES,
                      said="Conversation since the last routine (oldest first):\n" + quoted if quoted
                      else "Conversation since the last routine: (nothing before)",
                      known=known(guide), asked=ASKED.format(asked=" ".join(asked.split())) if asked else "",
                      last=" ".join(str(last).split()), twice=TWICE.format(number=number) if number else "")
    return {"messages": [{"role": "user", "content": note}],
            "max_tokens": READ_TOKENS, "chat_template_kwargs": {"enable_thinking": False},
            "response_format": {"type": "json_schema", "json_schema": {"name": "rutina", "schema": SCHEMA}},
            "temperature": 0.0, "top_p": 0.8, "top_k": 20, "min_p": 0.0, "seed": seed}


def parsed(reply: Any, guide: forms.Guide | None = None) -> dict[str, Any] | None:
    """The fields the model wrote, by their full names, or None when its reply is not the object asked (in doubt nothing
    is read). RUT15: a field it left out is the guide's as known (``given`` lists the ones it wrote), and a reply
    without ``x`` that wrote any field is an answer."""
    try:
        content = str(reply["choices"][0]["message"].get("content") or "").strip()
        start, end = content.find("{"), content.rfind("}")
        written = json.loads(content[start:end + 1]) if start >= 0 and end > start else None
    except (KeyError, IndexError, TypeError, ValueError, AttributeError):
        return None
    if not isinstance(written, dict) or not written or set(written) - set(FIELDS):
        return None
    does = written.get("x", "answer")
    if does not in DOES:
        return None
    fields: dict[str, Any] = {FIELDS[key]: value for key, value in (_known(guide) if guide is not None else {}).items()
                              if value}
    fields.update({FIELDS[key]: value for key, value in written.items()})
    if "h" in written and "m" not in written:
        fields["minute"] = "0"   # an hour said anew is said with its minutes: «mejor a las nueve» after 10:30 is 9:00
    fields["does"], fields["given"] = does, sorted(FIELDS[key] for key in written if key != "x")
    return fields


def _without(words: list[str], piece: str) -> list[str]:
    """These words without the first run of ``piece``'s (the text or the word the model read: a time inside them,
    «dime que no llegue tarde», «toma 2 pastillas», is not the routine's)."""
    cut = forms._time_words(piece) if piece else []
    for at in range(len(words) - len(cut) + 1 if cut else 0):
        if words[at:at + len(cut)] == cut:
            return words[:at] + words[at + len(cut):]
    return words


def _times(said: list[str], pieces: list[str]) -> list[tuple[forms.When, bool]]:
    """RUT14B: the times the person's words say whole, each as routine_guide.spoken reads the longest run of them it
    understands («todos los lunes… a las 10 10 de la mañana», «mañana a las 8»), never a word of one alone: «de la
    mañana» is no «mañana», «a las once» no «once», «ocho» of «ocho y media» no 8:00 (a blind review of RUT14 found
    those read from loose words). With each, whether its words have a number twice in a row (the ear's «10 10»)."""
    found: list[tuple[forms.When, bool]] = []
    for turn in said:
        words = forms._time_words(turn)
        for piece in pieces:
            words = _without(words, piece)
        twice = bool(_twice_in(words))
        runs: list[tuple[int, int, forms.When]] = []
        for at in range(len(words)):
            for end in range(min(len(words), at + MOST_TIME_WORDS), at, -1):
                when = forms.spoken(" ".join(words[at:end]))
                if when is not None and (when.hour is not None or when.meridiem or when.repeat or when.offset is not None):
                    runs.append((at, end, when))
                    break
        found += [(when, twice) for at, end, when in runs
                  if not any(first <= at and end <= last and (first, last) != (at, end) for first, last, _ in runs)]
    return found


def _days_said(words: list[str]) -> set[int]:
    """The days of the week these words name, one by one, as a span («de lunes a jueves») or as a group."""
    found: set[int] = set()
    for at, word in enumerate(words):
        if forms._seq(words, at, forms.WEEKDAYS):
            found.update(range(5))
        if forms._seq(words, at, forms.WEEKEND):
            found.update((5, 6))
        if word in forms.DAY_WORDS:
            found.add(forms.DAY_WORDS[word])
            last = (words[at + 2] if words[at + 1:at + 2] in (["a"], ["al"], ["to"], ["through"], ["hasta"])
                    and at + 2 < len(words) else "")   # RUT14B: «de lunes a» at the end of what was heard
            if last in forms.DAY_WORDS:
                first = forms.DAY_WORDS[word]
                found.update((first + i) % 7 for i in range((forms.DAY_WORDS[last] - first) % 7 + 1))
    return found


def _anywhere(words: list[str], pieces: tuple[str, ...]) -> bool:
    return any(forms._seq(words, at, pieces) for at in range(len(words)))


SINGULAR_ENDS_S = ("lunes", "martes", "miercoles", "jueves", "viernes")


def _weekly(words: list[str]) -> bool:
    """DIAX20: whether these words name days of the week as every week, by their form: a day after «los», «cada» or
    «every» («todos los lunes», «cada martes»), a plural day («los sábados», «on Mondays») or a group of days («de lunes
    a viernes», «los fines de semana»); «el lunes» is one day."""
    for at, word in enumerate(words):
        if word in forms.DAY_WORDS and ((at and words[at - 1] in ("los", "cada", "every"))
                                        or (word.endswith("s") and word not in SINGULAR_ENDS_S)):
            return True
    return _anywhere(words, forms.WEEKDAYS) or _anywhere(words, forms.WEEKEND)


def _count(value: Any, most: int) -> int | None:
    """A number of the reply (its digits, or a number), when it is one from 0 to ``most``."""
    written = str(value).strip() if isinstance(value, (str, int)) and not isinstance(value, bool) else ""
    return int(written) if written.isdigit() and len(written) <= 2 and int(written) <= most else None


def _days_read(written: Any) -> set[int]:
    """The days the reply names in its ``days`` text: their codes (mon…sun) or their names in words."""
    words = fold(written).split()
    return {forms.DAYS.index(word) for word in words if word in forms.DAYS} | _days_said(words)


def _days_may_be(said: list[str], known: tuple[int, ...]) -> list[set[int]]:
    """The sets of days the person's words allow: the days named in the last of their turns that names any; with days
    already known, those and these («también los sábados»), those without these («los lunes no») or these without
    those («los sábados no, los domingos»); and every day but
    these when that turn also says every day («todos los días menos el domingo»). Any other set read is not theirs."""
    for turn in reversed(said):
        words = forms._time_words(turn)
        named = _days_said(words)
        if named:
            # RUT15: and these without those known («los sábados no, los domingos» with Saturday known: Sunday)
            may = [named, *([set(known) | named, set(known) - named, named - set(known)] if known else [])]
            if _anywhere(words, forms.DAILY):
                may.append(set(range(7)) - named)
            return [days for days in may if days]
    return []


def _when(fields: dict[str, Any], said: list[str], pieces: list[str], known: tuple[int, ...]) -> forms.When | None:
    """The hour and the days of the reply that the person's words carry; what they do not carry is left unsaid.
    RUT14B: the hour, its minutes, its half of the day and a day said («mañana», «hoy», «una vez») are those of a time
    the person said whole (_times), outside the text and the word read (``pieces``); the half of the day of an hour
    said without one is the reply's only if they said that half in some time of theirs («no, mejor a las nueve» after
    «a las diez de la mañana»), and never assumed (an hour 1-12 read as 13-23 with no half said is asked)."""
    hour, minute = _count(fields.get("hour"), 23), _count(fields.get("minute"), 59) or 0
    written_hour = hour if hour is not None else 0
    times = _times(said, pieces)
    told: forms.When | None = None
    if hour is not None:
        same = {hour, hour - 12 if hour > 12 else hour + 12, 12 if hour == 0 else hour, 0 if hour == 12 else hour}
        told = next((when for when, twice in times if when.hour in same and (
            when.minute == minute or (twice and minute == 0 and when.minute == when.hour))), None)
    hour = told.hour if told is not None else None   # as they said it; an hour nobody said (nor its minutes) is asked
    meridiem: str | None = None
    fixed = False
    if told is not None and hour is not None:
        halves = {when.meridiem for when, _ in times if when.meridiem}
        # RUT15: the half of the day is the hour the model wrote (0 to 23), taken only when the person said that half
        half = fields.get("half") or ("am" if written_hour < 12 else "pm")
        if told.meridiem is not None or told.fixed or hour >= 13 or hour == 0:
            meridiem, fixed = told.meridiem, told.fixed or hour >= 13 or hour == 0
        elif half == "am" and "am" in halves:
            meridiem = "am"
        elif half == "pm" and halves & {"pm", "night", "noon"}:
            meridiem = "pm" if "pm" in halves else "night" if "night" in halves else "noon"
    repeat = fields.get("repeat")
    days: tuple[int, ...] = ()
    offset: int | None = None
    if repeat == "daily":
        # «todos los días» said as a time, or «todos» / «siempre» said whole to «¿Qué días?»: never the «todos» of
        # «todos los lunes»
        every = any(when.repeat == "daily" for when, _ in times) or any(forms._core(turn) in forms.ALL_DAYS for turn in said)
        repeat = "daily" if every else None
    elif repeat == "days":
        given = _days_read(fields.get("days"))
        # the days read are the days they named (the 4B read «martes» as mon, or left one out): if not, they are asked
        days = tuple(sorted(given)) if given in _days_may_be(said, known) else ()
        repeat = "days" if days else None
    elif repeat in ("today", "tomorrow", "once"):
        offset = {"today": 0, "tomorrow": 1}.get(str(repeat))
        offset = offset if offset is not None and any(when.offset == offset for when, _ in times) else None
        once = any(when.repeat == "once" and when.offset is None for when, _ in times)
        repeat = "once" if offset is not None or (repeat == "once" and once) else None
    else:
        repeat = None
    if hour is None and repeat is None:
        return None
    found = forms.When(hour, minute if hour is not None else 0, meridiem, fixed, repeat, days, offset)
    if hour is not None and meridiem is not None and found.hour24() is None:
        found = forms.When(hour, minute, None, False, repeat, days, offset)   # «15 de la mañana»: the half is asked
    return found


def _theirs(text: Any, words: set[str]) -> str:
    """A text of the reply, kept as written, when every word of it is one the person said; else nothing."""
    kept = forms._kept(text)
    said = fold(kept).split()
    return kept if said and all(word in words for word in said) else ""


def checked(fields: dict[str, Any], said: list[str], days: tuple[int, ...] = ()) -> Read:
    """The reply's fields against the person's words in the conversation (``said``, theirs only, the last ones last;
    ``days`` the days the routine already has): what they do not carry is not read, and BAXY asks it. A text read as
    of their last words has to be in those."""
    whole = " ".join(said)
    theirs = set(fold(whole).split())
    kind = fields.get("trigger") if fields.get("trigger") in ("time", "word") else None
    # RUT15: a text the model wrote now is of their last words when every word of it is among those (a text pointed
    # back to, «digas eso», is of their words before, and replaces no text known); one it left out is the known one
    last_words = set(fold(said[-1]).split()) if said else set()
    written = "text" in fields.get("given", ())
    fresh = written and bool(_theirs(fields.get("text"), last_words))
    text = _theirs(fields.get("text"), last_words if fresh else theirs)
    pieces = [str(fields.get(key) or "") for key in ("text", "word")]
    phrase = forms._plain(_theirs(fields.get("word"), theirs))
    # RUT14B: whether their last words alone carry anything of a routine (by form: a time said, a text of theirs, the
    # word among them): «sí, dale» carries nothing, «los viernes… digas eso a las diez» carries a time
    # RUT15: and the model wrote no field for them: «no, Mete el pollo en el horno.» read as the text it had («meta…»,
    # not of their last words) passed for bare, SIS3 read «now» and the routine was saved with no «sí» (held-out w09)
    last = last_words
    bare = not fields.get("given") and (not said or _when(fields, said[-1:], pieces, days) is None) and not (
        fresh and text) and not (phrase and set(fold(phrase).split()) <= last)
    return Read(does=str(fields.get("does")), kind=kind, when=_when(fields, said, pieces, days),
                phrase=phrase, text=text, fresh=fresh, bare=bare)


# INT36G (VIVO21, 14-11, 2 of 2: «borra la de las 10:00», said of a routine just made, opened the making of a new one in
# ~70 s). The model's own call of baxy.routines carries nothing (RUT7; INT33D took rut11's arguments out: the gate went
# down) and opens the guide of a new routine. When the person has routines, their words are read first in a closed
# question of their own, with those routines listed by what the person knows of them (time, days, word, what each says
# or does, routine_guide._item) after their names: whether they ask for a new one or something of one they have, and
# which. The model decides; BAXY asks before it acts, saying which routine (Mind._routine_have). The routine is written by
# its name, a closed list of values of this question (numbered keys: the 4B wrote the time, «10:00», 10 of 10 in Esencial);
# «more than one» when the words may mean several. Anthropic's structured outputs take an enum of strings
# (platform.claude.com/docs/en/build-with-claude/structured-outputs, read 2026-11-13 by RUT14); llama.cpp puts the
# required ``a`` first. INT37B (the App, a new conversation: BAXY asked «¿Quieres que la borre?», the person said «No.»,
# the model called baxy_routines and this read took «No.» for turn_off 5 of 5, «¿Desactivo esta rutina…?»): a no to
# what BAXY asked has a value of its own, and BAXY leaves their routines as they are (Mind._routine_have).
HAVE_ACTS = ("new", "delete", "turn_off", "turn_on", "change", "list", "no", "other")
HAVE_SEVERAL = "more than one"
HAVE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"a": {"type": "string", "enum": list(HAVE_ACTS)}, "r": {"type": "string"}},
    "required": ["a"],
    "additionalProperties": False,
}
HAVE_ASK = (
    "[BAXY's routines tool was called on the person's last words. The routines the person has now, each after its "
    "name:\n{items}\n"
    "Reply with one JSON object.\n"
    "a: what their last words ask: new (set up a new routine) | delete (one they have) | turn_off | turn_on | change "
    "(its time, days, word, or what it says or does) | list (which routines they have) | no (they say no to what "
    "BAXY asked, or want nothing done to their routines) | other.\n"
    "r: with delete, turn_off, turn_on or change, the name of the routine their words mean, by anything they say of it "
    "(its time, its days, its word, what it says or does), or «more than one» when they could mean more than one.\n"
    "The person's last words: «{last}»]")
HAVE_TOKENS = 32
MOST_HAVE = 20   # routines listed (RoutinesHandler keeps few; a longer list is cut, and BAXY asks which)


def have_body(routines: list[dict[str, Any]], last: str, lang: str, seed: int) -> dict[str, Any]:
    """The closed question of which routine the person's words are about, each written by its name (an enum)."""
    kept = routines[:MOST_HAVE]
    names = [forms._named(routine) for routine in kept]
    items = "\n".join(f"«{name}»: {forms._item(routine, lang)}" for name, routine in zip(names, kept))
    note = HAVE_ASK.format(items=items, last=" ".join(str(last).split()))
    schema = json.loads(json.dumps(HAVE_SCHEMA))
    schema["properties"]["r"]["enum"] = [*dict.fromkeys(names), HAVE_SEVERAL]
    return {"messages": [{"role": "user", "content": note}],
            "max_tokens": HAVE_TOKENS, "chat_template_kwargs": {"enable_thinking": False},
            "response_format": {"type": "json_schema", "json_schema": {"name": "rutinas", "schema": schema}},
            "temperature": 0.0, "top_p": 0.8, "top_k": 20, "min_p": 0.0, "seed": seed}


def have_parsed(reply: Any, names: list[str]) -> tuple[str, list[int]] | None:
    """(what their words ask, the index of the routine they mean among ``names``, or none: «more than one», or none
    written) or None when the reply is not the object asked."""
    try:
        content = str(reply["choices"][0]["message"].get("content") or "").strip()
        start, end = content.find("{"), content.rfind("}")
        written = json.loads(content[start:end + 1]) if start >= 0 and end > start else None
    except (KeyError, IndexError, TypeError, ValueError, AttributeError):
        return None
    if not isinstance(written, dict) or written.get("a") not in HAVE_ACTS or set(written) - {"a", "r"}:
        return None
    named = str(written.get("r") or "")
    return str(written["a"]), [names.index(named)] if named in names[:MOST_HAVE] else []


# RUT17 (VIVO22: «Borra la rutina de las diez de la mañana.» → «No tengo ninguna rutina «diez de la mañana».», while with
# «10:00» it was found): a name said in a fixed order that is none of their routines' by form may be a time said in
# words. The model writes the time those words say in a closed object (each value an enum, as HAVE_SCHEMA), and the mind
# compares it with each routine's own clock (Mind._clock_named): no list of words reads the time.
CLOCK_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"h": {"type": "string", "enum": ["none", *map(str, range(24))]},
                   "m": {"type": "string", "enum": [*map(str, range(60))]}},
    "required": ["h"],
    "additionalProperties": False,
}
CLOCK_ASK = (
    "[The person named one of their routines by «{name}». If these words say a time of day, reply with it in one JSON "
    'object: h, the hour 0-23 (afternoon, evening and night are 12-23), and m, its minutes (left out when 0). If they '
    'say no time, reply {{"h": "none"}}.]')
CLOCK_TOKENS = 16


def clock_body(name: str, seed: int) -> dict[str, Any]:
    """The closed question of the time a name said is."""
    return {"messages": [{"role": "user", "content": CLOCK_ASK.format(name=" ".join(str(name).split()))}],
            "max_tokens": CLOCK_TOKENS, "chat_template_kwargs": {"enable_thinking": False},
            "response_format": {"type": "json_schema", "json_schema": {"name": "hora", "schema": CLOCK_SCHEMA}},
            "temperature": 0.0, "top_p": 0.8, "top_k": 20, "min_p": 0.0, "seed": seed}


def clock_parsed(reply: Any) -> str | None:
    """The clock written («HH:MM»), or None: no time, or the reply is not the object asked."""
    try:
        content = str(reply["choices"][0]["message"].get("content") or "").strip()
        start, end = content.find("{"), content.rfind("}")
        written = json.loads(content[start:end + 1]) if start >= 0 and end > start else None
    except (KeyError, IndexError, TypeError, ValueError, AttributeError):
        return None
    if not isinstance(written, dict) or set(written) - {"h", "m"}:
        return None
    hour, minute = str(written.get("h") or ""), str(written.get("m") or "0")
    if not hour.isdigit() or not minute.isdigit() or int(hour) > 23 or int(minute) > 59:
        return None
    return f"{int(hour):02d}:{int(minute):02d}"
