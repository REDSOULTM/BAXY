"""MSG1: the text BAXY sends or leaves written for someone is written by the model as the person would write it.

The owner's case (2026-11-14, 22:25): «si yo le digo, dile que llego a las 10, y el modelo literal escribe que llego a
las 10 … debería ser un mensaje más natural … sea lo mismo para Discord y también para correos». The model reads who and
what well; the text it put in the call was the order's own words (indirect speech: «que llego a las 10», «send me the
link to the game») or a twist of them («Llegué a las 10.»: hub/int36h, 2 of 3 seeds). A message is the person's own
words in direct speech: the reporting clause and its «que» go, and person, tense and deictics turn back to the sender's
(es.wikipedia.org/wiki/Estilo_indirecto: «por medio de la conjunción subordinada "que"», «dominados por la tercera
persona»; dictionary.cambridge.org/grammar/british-grammar/reported-speech-indirect-speech: «Indirect reports of
statements consist of a reporting clause and a that-clause»). Assistants write it so: Google Assistant's own example
is «Send a Telegram message to Hannah: "I'm on my way."» and it plays the message before «Send»
(support.google.com/assistant/answer/9984245); Gemini «compose[s] an email based on your instructions» and the person
reviews it before Send (support.google.com/gemini/answer/18741629). An email has «a specific subject line, an
appropriate greeting, a focused message … and a professional sign-off»
(grammarly.com/blog/emailing/how-to-write-a-professional-email, 2026-04-06); a chat message is short.

So the call's text is written again by the model in one closed question apart from the decision, asked after the
conversation as the server holds it (as routine_fill: SCHEMA as response_format, the same for a model by API), and the
decision's call carries what it wrote. A rewriting model adds names and quantities that the source does not have
(Nan et al., «Entity-level Factual Consistency of Abstractive Text Summarization», EACL 2021, arXiv 2102.09130; Zhao et
al., «Reducing Quantity Hallucinations in Abstractive Summarization», Findings of EMNLP 2020, arXiv 2009.13312: verify
«dates, numbers, sums of money» against the source). What stays deterministic is that form (``unsaid``): every number,
hour, date word, name and address of the text written is in the person's words or the conversation; one that is not
goes back to the model as data and it writes again, once; still there, the decision's own text goes, as before MSG1.
Words dictated as they are («exactamente…», «tal cual», a text in quotes) go as the decision wrote them: the model says
so (``e``), and a text in quotes that the call carries whole is that by form.
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from typing import Any

from . import routine_guide as forms
from .routines import fold

# The operations whose «text» is a message for someone, and how that kind of text is written.
CHAT = ("message.send", "message.draft", "message.send.test")
MAIL = ("email.send",)
REPLY = ("email.latest.reply",)
WRITES = CHAT + MAIL + REPLY
SCHEMA_CHAT: dict[str, Any] = {
    "type": "object",
    "properties": {"e": {"type": "string", "enum": ["yes", "no"]}, "c": {"type": "string"}, "t": {"type": "string"}},
    "required": ["e", "c", "t"],
    "additionalProperties": False,
}
SCHEMA_MAIL: dict[str, Any] = {
    "type": "object",
    "properties": {"e": {"type": "string", "enum": ["yes", "no"]}, "c": {"type": "string"}, "s": {"type": "string"},
                   "t": {"type": "string"}},
    "required": ["e", "c", "s", "t"],
    "additionalProperties": False,
}
# Asked after the conversation the server already holds (Mind._message_written), as one more message: these words are
# the whole question (llama.cpp does not put the schema in the prompt: grammars/README.md).
ASK = (
    "[BAXY is about to {act} for the person: {target}. Write that text as the person would write it themselves to "
    "the recipient. Take what they asked to say and turn their order to BAXY into their own message: the order "
    "goes («dile que», «pregúntale si», «avísale de que», «tell him that», «ask her if»); what they say of "
    "themselves stays in their first person and in their tense, word for word («que llego a las 10» → «Llego a "
    "las 10»; «that I'll be there at 10» → «I'll be there at 10»); what they say of the recipient is said to them, "
    "in «tú» or «you» («si viene mañana» → «¿Vienes mañana?»; «que no se preocupe» → «No te preocupes»; «to call "
    "me» → «Call me»). Add no fact, reason, time, place, apology, promise or wish they did not give; names, "
    "numbers, hours, dates and links exactly as they gave them. Write it in the language of their words, even when "
    "the conversation is in another. {style}\n"
    "Their words: «{said}»\nBAXY's first draft, which may still be their order: «{draft}»\n{again}"
    "Reply with one JSON object. e: yes only when they dictated the exact words to send («exactamente», «tal cual», "
    "«word for word», spelled out, or between quotes), then t is those words unchanged; otherwise no. {fields}]")
ACTS = {"message.send": "send a message", "message.draft": "leave a message written", "message.send.test":
        "send a test message", "email.send": "send an email", "email.latest.reply": "reply to the latest email"}
STYLE_CHAT = "It is a chat message: short and natural, as people write in chats, no greeting or sign-off they did not ask for."
STYLE_MAIL = ("It is an email: a greeting line, the body, and a short sign-off line with no name unless the conversation "
              "gives the person's; and a short subject.")
STYLE_REPLY = ("It is the reply to the latest email (the one BAXY read, if the conversation has it): a greeting line, "
               "the body, and a short sign-off line with no name unless the conversation gives the person's.")
FIELDS_CHAT = "c: what they asked to say, copied word for word from their words. t: that, as their own message."
FIELDS_MAIL = ("c: what they asked to say, copied word for word from their words. s: the subject. t: that, as "
               "their own email.")
AGAIN = ("Your last text had data that are neither in the person's words nor in the conversation: {unsaid}. Write it "
         "again without them, or as the person gave them.\n")
TOKENS_CHAT = 200    # a chat message, the words it comes from and its object; past this the reply is cut and unread
TOKENS_MAIL = 440    # an email's greeting, body, sign-off and subject, and the words it comes from
# Form tables, as validation only: the words of a date («jueves», «mañana», «tonight») a text must not bring unsaid.
DATE_WORDS = {*forms.DAY_WORDS, "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
              "septiembre", "setiembre", "octubre", "noviembre", "diciembre", "january", "february", "march", "april",
              "june", "july", "august", "september", "october", "november", "december", "hoy", "manana", "ayer",
              "anoche", "today", "tomorrow", "yesterday", "tonight"}
# Halves and quarters of an hour said in words («y media», «quarter past»): the minutes a clock written with digits has.
PARTS = {"media": 30, "cuarto": 15, "half": 30, "quarter": 15}
_QUOTED = re.compile(r"[«\"“](.+?)[»\"”]")
_ADDRESS = re.compile(r"(?:https?://|www\.)\S+|[\w.+-]+@[\w-]+(?:\.[\w-]+)+|\b[\w-]+(?:\.[\w-]+)*\.[a-z]{2,}/\S*",
                      re.IGNORECASE)
_CLOCK = re.compile(r"(?<![\d:])(\d{1,2})\s*:\s*(\d{2})(?![\d:])")
_NAME = re.compile(r"(?<![\w'’])([A-ZÁÉÍÓÚÑÜ]\w+(?:['’][a-z]+)?)")
_SENTENCE_START = re.compile(r"(?:^|[.!?¡¿:;\n«\"“(]\s*)$")


@dataclass(frozen=True)
class Written:
    """What the model wrote: ``exact`` whether the person dictated the words as they go; ``text`` and ``subject``."""
    exact: bool
    text: str
    subject: str = ""


def quoted(said: str, text: str) -> bool:
    """Whether the call's text is, whole, a text the person put between quotes: dictated as it goes, by form."""
    wanted = fold(text)
    return bool(wanted) and any(fold(found) == wanted for found in _QUOTED.findall(str(said or "")))


def body(operation: str, arguments: dict[str, Any], said: str, unsaid: list[str], seed: int) -> dict[str, Any]:
    """The closed question for a call of ``operation``: what it does and to whom, how that kind of text is written, and
    the person's words; with ``unsaid``, the data of the last text written that no source carries."""
    mail = operation in MAIL
    style = STYLE_MAIL if mail else STYLE_REPLY if operation in REPLY else STYLE_CHAT
    target = ", ".join(f"{key} «{value}»" for key, value in arguments.items()
                       if key in ("channel", "recipient", "requestedRecipient", "to") and isinstance(value, str))
    note = ASK.format(act=ACTS[operation], target=target or "the email being answered", style=style,
                      said=" ".join(str(said).split()), draft=" ".join(str(arguments.get("text") or "").split()),
                      again=AGAIN.format(unsaid=", ".join(f"«{item}»" for item in unsaid)) if unsaid else "",
                      fields=FIELDS_MAIL if mail else FIELDS_CHAT)
    schema = SCHEMA_MAIL if mail else SCHEMA_CHAT
    return {"messages": [{"role": "user", "content": note}],
            "max_tokens": TOKENS_CHAT if operation in CHAT else TOKENS_MAIL,
            "chat_template_kwargs": {"enable_thinking": False},
            "response_format": {"type": "json_schema", "json_schema": {"name": "mensaje", "schema": schema}},
            "temperature": 0.0, "top_p": 0.8, "top_k": 20, "min_p": 0.0, "seed": seed}


def parsed(reply: Any, operation: str) -> Written | None:
    """What the model wrote, or None when its reply is not the object asked (cut, or something else): then nothing of
    it is taken."""
    try:
        if reply["choices"][0].get("finish_reason") == "length":
            return None
        content = str(reply["choices"][0]["message"].get("content") or "").strip()
        start, end = content.find("{"), content.rfind("}")
        written = json.loads(content[start:end + 1]) if start >= 0 and end > start else None
    except (KeyError, IndexError, TypeError, ValueError, AttributeError):
        return None
    if not isinstance(written, dict) or written.get("e") not in ("yes", "no"):
        return None
    text, subject = written.get("t"), written.get("s", "")
    if not isinstance(text, str) or not text.strip() or not isinstance(subject, str):
        return None
    if operation in MAIL and not subject.strip():
        return None
    return Written(written["e"] == "yes", text.strip(), " ".join(subject.split()))


def _numbers(text: str) -> set[int]:
    """The numbers a text gives, with digits or in words («diez», «treinta y cinco», «forty five»)."""
    found = {int(digits) for digits in re.findall(r"\d+", text)}
    words = forms._time_words(text)
    found |= {forms.NUMBERS[word] for word in words if word in forms.NUMBERS}
    for at in range(len(words)):
        number = forms._number(words, at, 59)
        if number is not None:
            found.add(number[0])
    found |= {value for word, value in PARTS.items() if word in words}
    return found


def unsaid(written: str, sources: list[str]) -> list[str]:
    """The concrete data of ``written`` that no source carries: an address or link, a number or an hour, a date word, or
    a name (a word with a capital that starts no sentence); each as written, once. Empty: all of them were given."""
    source = "\n".join(str(text or "") for text in sources)
    plain = fold(source)
    words = set(plain.split())
    numbers = _numbers(source)
    missing: list[str] = []
    for address in _ADDRESS.findall(written):
        if fold(address) not in plain:
            missing.append(address)
    rest = _ADDRESS.sub(" ", written)
    for hour, minutes in _CLOCK.findall(rest):
        value = int(hour)
        if not ({value, value - 12, value + 12} & numbers and (minutes == "00" or int(minutes) in numbers)):
            missing.append(f"{hour}:{minutes}")
    for digits in re.findall(r"\d+", _CLOCK.sub(" ", rest)):
        if int(digits) not in numbers:
            missing.append(digits)
    for word in fold(rest).split():
        if word in DATE_WORDS and word not in words:
            missing.append(word)
    for match in _NAME.finditer(rest):
        if _SENTENCE_START.search(rest[:match.start()]):
            continue
        name = match.group(1)
        if not set(fold(name).split()) <= words:
            missing.append(name)
    return list(dict.fromkeys(missing))


def theirs(arguments: dict[str, Any]) -> list[str]:
    """The call's own values that come from the person's words (who it goes to): a source of the data written."""
    return [value for key, value in arguments.items()
            if key in ("recipient", "requestedRecipient", "to") and isinstance(value, str)]


def normalized(text: str) -> str:
    """The text as a check compares it: NFC, single spaces."""
    return " ".join(unicodedata.normalize("NFC", text).split())
