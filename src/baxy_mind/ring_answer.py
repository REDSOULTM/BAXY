"""ALR4: a short acknowledgement said while BAXY rings an alarm or a reminder stops or snoozes it, before the model.

**An exception to «no word lists» the owner authorized** (2026-11-09 ~01:00, literal: «para ciertas funciones puedes
hacer regex… una regla de regex que hardcodeada básicamente para cosas que son que el usuario sí o sí va a decir en torno
a las cosas de la aplicación»; and on 2026-11-08: «el usuario tendría que decir Baxi, gracias. O… Baxi para la alarma,
tipos como funcionan de Alexa»). ALR1-ALR3 measured the stock model answering «Baxy, gracias» with «¡De nada!» while the
alarm rang (0/3 in the bench, 0/4 live in DEP6), and every help in what it reads brought falsehoods («te he parado
ambas» with nothing called). documentacion/ACUSE_DE_ALARMA.md says the same and what it may never be used for.

It exists only while something of BAXY rings: Mind.decide asks it only with the App's ``ringing`` non-empty and no
confirmation or question of BAXY waiting for the person's words. ALR5 (M1): that is any question, also one in its last
words («¿Para qué hora?» → «Para las dos», «¿En cuántos minutos?» → «10 minutos» stopped and snoozed what rang): these
lists compare form, and after a question the same form is an answer to it, which only the model can read. The whole turn, folded (lower case, no accents or
signs), must be made only of pieces of the closed lists below, at most MOST_PIECES of them besides the name «Baxy», a
few fillers and «por favor»: acknowledgements («gracias», «ya voy», «ok»), orders to stop («para», «apágala») and orders
to snooze («pospón», «cinco minutos más»); a turn with both orders, a question, or anything else, even with «gracias» in
it, goes to the model as always. A match is schedule.alarms stop (or snooze) with no id, which answers every one ringing
(WindowsScheduledNotificationAdapter.AnswerRingAsync, ALR3), proposed as the model would and run by the kernel and the
adapter as any call; BAXY then says a fixed sentence built only from that call's receipt (`told`), and leaves any other
receipt to the model.

As a smart speaker answers a ringing alarm: «Stop», «Snooze», «Snooze for 10 minutes» (Google Nest Help, «Set and manage
alarms», support.google.com/googlehome/answer/7071598), «Snooze reminder for 10 minutes» (Amazon, «Get Reminder
Notifications From Alexa»); snooze's default is 10 minutes, as Android's clock and the adapter's (SnoozeMinutes).
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from typing import Any

# The pieces a turn that answers what rings is made of, folded as _folded leaves them («{n}»: a number of minutes, in
# digits or words, MINUTES). Spanish and English; the pieces both say («ok», «stop») take the interface's language.
ACK_ES = ("gracias", "muchas gracias", "mil gracias", "ya", "ya esta", "ya estuvo", "ya voy", "ya estoy", "ya me levante",
          "ya me levanto", "ya me estoy levantando", "me levanto", "voy", "ya estoy despierto", "ya estoy despierta",
          "ya desperte", "ya lo vi", "ya la vi", "ya los vi", "ya las vi", "ya lo se", "ya oi", "ya escuche",
          "ya te escucho", "ya la oi", "ya lo oi", "ya te oi", "ya la escuche", "ya lo escuche", "ya te escuche",
          "ya entendi", "listo", "ok", "okey", "okay", "vale", "dale", "sale", "orale", "va", "si", "de acuerdo",
          "esta bien", "entendido", "enterado", "recibido", "perfecto", "genial", "hecho")
ACK_EN = ("thanks", "thank you", "thanks a lot", "thank you very much", "thank you so much", "ok", "okay", "alright",
          "all right", "got it", "i got it", "i heard you", "i hear you", "heard you", "i m up", "im up", "i am up",
          "i m awake", "im awake", "i am awake", "yeah", "yes", "yep", "sure", "fine", "cool", "great", "perfect", "done")
STOP_ES = ("para", "parala", "paralo", "paralas", "para la alarma", "para el recordatorio", "para eso", "para todo",
           "para las dos", "apaga", "apagala", "apagalo", "apagalas", "apaga la alarma", "apaga el recordatorio",
           "apaga eso", "apaga todo", "apagalo todo", "apaga todo eso", "apaga las dos", "quitala", "quitalo",
           "quita la alarma", "quita el recordatorio", "quita eso", "corta", "cortala", "cortalo", "corta eso", "detente",
           "detenla", "silencio", "silenciala", "callate", "basta", "stop")
STOP_EN = ("stop", "stop it", "stop that", "stop the alarm", "stop the reminder", "stop alarm", "stop them", "stop both",
           "turn it off", "turn that off", "turn them off", "turn off the alarm", "turn off the reminder", "turn off",
           "shut it off", "switch it off", "dismiss", "dismiss it", "enough", "quiet", "shut up", "silence", "silence it")
SNOOZE_ES = ("pospon", "posponla", "posponlo", "posponlas", "pospone", "posponela", "posponelas", "pospon la alarma",
             "pospon el recordatorio", "pospon las dos", "pospone las dos", "{n} minutos", "{n} minutos mas",
             "dame {n} minutos mas", "dame {n} minutos", "otros {n} minutos", "en {n} minutos", "{n} min mas",
             "dame {n} min mas", "pospon {n} min", "mas tarde", "luego", "un rato mas", "un ratito mas",
             "recuerdamelo mas tarde", "recuerdamelo luego", "recuerdamelo en {n} minutos", "avisame mas tarde",
             "avisame en {n} minutos", "en un rato", "en un ratito", "recuerdamelo en un rato", "recuerdamelo en un ratito",
             "dejame dormir", "dejame dormir {n} minutos mas", "ahora no", "ahorita no", "snooze", "{n} min")
SNOOZE_EN = ("snooze", "snooze it", "snooze them", "snooze both", "snooze them both", "snooze the alarm",
             "snooze the reminder", "snooze {n} minutes", "snooze for {n} minutes", "for {n} minutes", "in {n} minutes",
             "{n} more minutes", "{n} minutes more", "{n} minutes", "give me {n} more minutes", "give me {n} minutes",
             "snooze {n} min", "snooze for {n} min", "{n} more min", "give me {n} more min", "{n} min", "later",
             "remind me later", "remind me in {n} minutes", "remind me again in {n} minutes", "not now", "let me sleep",
             "let me sleep {n} more minutes")
# The kind a piece names, by its words: «para el recordatorio» with an alarm ringing too answers only the reminder.
KINDS = {"alarma": "alarm", "alarm": "alarm", "recordatorio": "reminder", "reminder": "reminder"}
SAID = ("baxy", "baxi", "ay", "ah", "eh", "oh", "uf", "uy", "mm", "mmm", "um", "uh", "hmm", "bueno", "pues", "oye", "hey",
        "porfa", "por favor", "please", "pls", "po", "pe", "che", "chamo", "wey", "guey", "tio", "man")
MOST_PIECES = 4  # a short acknowledgement: «para, para, ya está» is three


def _pieces() -> dict[tuple[str, ...], tuple[str, str | None]]:
    """Each piece's words → (what it is: ack, stop, snooze or said; its language, None when both say it)."""
    pieces: dict[tuple[str, ...], tuple[str, str | None]] = {}
    for kind, spanish, english in (("ack", ACK_ES, ACK_EN), ("stop", STOP_ES, STOP_EN),
                                   ("snooze", SNOOZE_ES, SNOOZE_EN)):
        for lang, said in (("es", spanish), ("en", english)):
            for piece in said:
                words = tuple(piece.split())
                pieces[words] = (kind, None if words in pieces and pieces[words][1] != lang else lang)
    for piece in SAID:
        pieces[tuple(piece.split())] = ("said", None)
    return pieces


PIECES = _pieces()
LONGEST = max(len(words) for words in PIECES)
MINUTES = {"un": 1, "uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7, "ocho": 8,
           "nueve": 9, "diez": 10, "quince": 15, "veinte": 20, "treinta": 30, "one": 1, "two": 2, "three": 3, "four": 4,
           "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "fifteen": 15, "twenty": 20, "thirty": 30}
UNITS = {"minuto": "minutos", "minutitos": "minutos", "minutito": "minutos", "minute": "minutes", "mins": "minutes"}
HOURS = {("media", "hora"): ("30", "minutos"), ("una", "hora"): ("60", "minutos"), ("half", "an", "hour"): ("30", "minutes"),
         ("an", "hour"): ("60", "minutes"), ("one", "hour"): ("60", "minutes")}
MOST_MINUTES = 1440  # the adapter's bound (AnswerRingAsync: inMinutes 1 to 1,440)


@dataclass(frozen=True)
class Answer:
    """What the words ask of what rings: ``action`` stop or snooze, ``minutes`` only when they said how many, ``lang``
    the language they are in («es», «en», or None when both say them) and ``kind`` the one they name, if any."""
    action: str
    minutes: int | None
    lang: str | None
    kind: str | None = None

    def arguments(self, ringing: list[dict[str, Any]]) -> dict[str, Any]:
        """schedule.alarms' arguments: no id, so it answers every one ringing (ALR3); of the kind named only when one of
        each rings (with one kind ringing, its name is how the person calls what rings)."""
        kinds = {str((ring or {}).get("kind")) for ring in ringing}
        named = {"kind": self.kind} if self.kind in kinds and len(kinds) > 1 else {}
        return {"action": self.action, **named, **({"inMinutes": self.minutes} if self.minutes is not None else {})}


def _folded(text: str) -> tuple[list[str], int | None] | None:
    """The turn's words, folded, with the minutes it says as «{n}» (and how many), or None when it says two."""
    folded = unicodedata.normalize("NFKD", text).casefold()
    words = [UNITS.get(word) or word
             for word in re.findall(r"[^\W_]+", "".join(ch for ch in folded if not unicodedata.combining(ch)))]
    for spoken, said in HOURS.items():  # «media hora», «an hour»: the minutes they are
        for i in range(len(words) - len(spoken) + 1):
            if tuple(words[i:i + len(spoken)]) == spoken:
                words[i:i + len(spoken)] = [said[0], said[1]]
    minutes = None
    for i, word in enumerate(words):
        count = int(word) if re.fullmatch("[0-9]+", word) else MINUTES.get(word)
        unit = (words[i + 1:i + 2] in (["minutos"], ["minutes"], ["min"])
                or words[i + 1:i + 3] in (["more", "minutes"], ["more", "min"]))
        if count is not None and unit:
            if minutes is not None or not 1 <= count <= MOST_MINUTES:
                return None
            minutes, words[i] = count, "{n}"
    return words, minutes


def _split(words: list[str]) -> list[tuple[tuple[str, ...], str, str | None]] | None:
    """The turn as pieces (words, kind, language; longest first), or None when some words are no piece."""
    found: dict[int, list[tuple[tuple[str, ...], str, str | None]] | None] = {len(words): []}
    for start in range(len(words) - 1, -1, -1):
        found[start] = None
        for size in range(min(LONGEST, len(words) - start), 0, -1):
            said, rest = tuple(words[start:start + size]), found[start + size]
            if said in PIECES and rest is not None:
                found[start] = [(said, *PIECES[said]), *rest]
                break
    return found[0]


def heard(text: str) -> Answer | None:
    """The answer to what rings these whole words are, or None: then they go to the model. A question («¿ya?») is never
    one."""
    if "?" in text or "¿" in text:
        return None
    folded = _folded(text)
    pieces = [piece for piece in (_split(folded[0]) if folded else None) or [] if piece[1] != "said"]
    # A piece said again right after itself («ya, ya», «ok ok») counts once.
    said = [(kind, lang) for i, (words, kind, lang) in enumerate(pieces) if i == 0 or words != pieces[i - 1][0]]
    kinds = {kind for kind, _ in said}
    named = {KINDS[word] for words, _, _ in pieces for word in words if word in KINDS}
    if not said or len(said) > MOST_PIECES or {"stop", "snooze"} <= kinds or len(named) > 1:
        return None
    langs = {lang for _, lang in said if lang}
    lang = langs.pop() if len(langs) == 1 else None
    kind = named.pop() if named else None
    if "snooze" in kinds:
        return Answer("snooze", folded[1], lang, kind)  # type: ignore[index]
    return Answer("stop", None, lang, kind)


def _clock(text: str) -> str:
    """«07:05» as said: «7:05»."""
    hour, _, minute = str(text).partition(":")
    return f"{int(hour)}:{minute}" if hour.isdigit() and minute else str(text)


def _named(ring: dict[str, Any], lang: str) -> str:
    clock, title = _clock(ring.get("clock") or ""), str(ring.get("title") or "").strip()
    if lang == "en":
        return f"the {clock} {'alarm' if ring.get('kind') == 'alarm' else 'reminder'}" + (f" «{title}»" if title else "")
    kind = "la alarma" if ring.get("kind") == "alarm" else "el recordatorio"
    at = "de la" if clock.startswith("1:") else "de las"
    return f"{kind}" + (f" «{title}»" if title else "") + f" {at} {clock}"


def _listed(items: list[str], lang: str) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + (" and " if lang == "en" else " y ") + items[-1]


def told(observation: str, action: str, lang: str) -> str | None:
    """The fixed sentence for a receipt that says each ring was answered (completed, every one stopped or snoozed and
    none still ringing), from that receipt only; None for any other, which the model reads as always."""
    try:
        facts = json.loads(observation)
    except (TypeError, ValueError):
        return None
    observed = facts.get("observed") if isinstance(facts, dict) and facts.get("status") == "completed" else None
    if not isinstance(observed, dict):
        return None
    rings = observed.get("rings") if isinstance(observed.get("rings"), list) else [observed]
    done = "stopped" if action == "stop" else "snoozed"
    if not rings or not all(isinstance(r, dict) and r.get(done) is True and r.get("ringing") is False
                            and r.get("clock") for r in rings):
        return None
    named = _listed([_named(r, lang) for r in rings], lang)
    if action == "stop":
        return f"Stopped {named}." if lang == "en" else f"Paré {named}."
    minutes = {r.get("inMinutes") for r in rings}
    due = {str(r.get("dueLocal") or "")[-5:] for r in rings}
    if len(minutes) != 1 or not isinstance(next(iter(minutes)), int):
        return None
    count = next(iter(minutes))
    again = _clock(next(iter(due))) if len(due) == 1 and "" not in due else ""
    tomorrow = all(r.get("scheduledFor") == "tomorrow" for r in rings)
    if lang == "en":
        return (f"Snoozed {named} for {count} minute{'s' if count != 1 else ''}"
                + (f"; {'it rings' if len(rings) == 1 else 'they ring'} again {'tomorrow ' if tomorrow else ''}at {again}"
                   if again else "") + ".")
    return (f"Pospuse {count} minuto{'s' if count != 1 else ''} {named}"
            + (f"; {'vuelve' if len(rings) == 1 else 'vuelven'} a sonar {'mañana ' if tomorrow else ''}"
               f"{'a la' if again.startswith('1:') else 'a las'} {again}" if again else "") + ".")
