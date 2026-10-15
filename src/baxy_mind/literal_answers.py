"""Answers whose words are a literal: a value recalled from the dialogue, a random draw, a set phrase's
translation, and the check of a one-sentence reply around such a literal.
"""

from __future__ import annotations

import random
import re
import unicodedata

from .semantic.request import fold as _reading_fold
from .semantic.conversation import RandomDraw, quoted_literals, quoted_translation_phrase, recall_asked
from .dialogue_history import _bounded_history, _normalized_dialogue_text


def _literal_recall_reference(
    history: object,
    current: object,
) -> str | None:
    """Return one recent user literal for an explicit recall question.

    A quoted literal of the previous request, or the whole previous message
    (the person's or the assistant's) when that message is what is asked back.
    The value remains untrusted data.  This helper only grounds a conversational
    presentation path; it never selects an operation or grants effect authority.
    """

    asked = recall_asked(current)
    if asked is None:
        return None
    speaker = None if asked == "quoted" else asked
    prior_messages = _bounded_history(history)
    if (
        prior_messages
        and prior_messages[-1].get("role") == "user"
        and _normalized_dialogue_text(prior_messages[-1].get("content"))
        == _normalized_dialogue_text(current)
    ):
        prior_messages.pop()
    prior_said = next(
        (
            message["content"]
            for message in reversed(prior_messages)
            if message.get("role") == (speaker or "user")
        ),
        "",
    )
    if not prior_said:
        return None
    if speaker is not None:
        # A reply laid out in lines is said back as one run of its words.
        matches = [" ".join(prior_said.split())]
    else:
        matches = quoted_literals(prior_said)
    if len(matches) != 1:
        return None
    literal = matches[0]
    if (
        not literal
        or "[[R1]]" in literal
        or "```" in literal
        or any(
            unicodedata.category(character) in {"Cc", "Cf", "Cs"}
            for character in literal
        )
    ):
        return None
    return literal


_DRAW = random.SystemRandom()


def _repeats_prompt(text: str, prompt: str, window: int = 5) -> bool:
    """Whether ``text`` carries ``window`` consecutive words of the prompt it was written from."""

    prompt_words = re.findall(r"\w+", _reading_fold(prompt))
    spans = {" ".join(prompt_words[i:i + window]) for i in range(len(prompt_words) - window + 1)}
    words = re.findall(r"\w+", _reading_fold(text))
    return any(" ".join(words[i:i + window]) in spans for i in range(len(words) - window + 1))


def _literal_reply_defect(
    reply: str,
    *,
    current: str,
    literal: str,
    system: str,
    drawn: bool,
    allowed_numbers: frozenset[str],
) -> str:
    """Why a one-sentence reply around a grounded literal may not be published («» when it may)."""

    if not reply or "```" in reply or reply.rstrip().endswith(("?", "？")) or "[[" in reply:
        return "shape"
    found = re.search(
        r"\s+".join(re.escape(word) for word in literal.split()), reply, re.IGNORECASE,
    )
    if found is None:
        return "literal_missing"
    rest = reply[: found.start()] + " " + reply[found.end():]
    if _RECALL_REFUSAL.search(_reading_fold(rest)) or _repeats_prompt(rest, system):
        return "refusal_or_prompt"
    if len(re.findall(r"\w+", rest)) > 14:
        return "too_long"
    if drawn:
        other_numbers = set(re.findall(r"\d+", rest)) - set(re.findall(r"\d+", current)) - allowed_numbers
        if other_numbers:
            return "other_number"
        # A bare number is no sentence (the App refuses «4»); a coin face alone («Cruz.») is a word.
        if re.fullmatch(r"\d+(?:\s*(?:,|y|and)\s*\d+)*", literal) and not re.search(r"[^\W\d_]{2}", rest):
            return "bare_value"
    return ""


# A recall wording that refuses the very text it says back (folded, the marker removed).
_RECALL_REFUSAL = re.compile(
    r"\b(?:no\s+(?:puedo|pude|tengo|recuerdo|se|lo\s+se|es\s+posible)|sin\s+embargo|"
    r"can\s*not|can'?t|cannot|unable|(?:do\s+not|don'?t)\s+(?:have|remember|know))\b"
)


def _drawn_fact(draw: RandomDraw, value: str) -> str:
    """The draw as the fact of the turn, with its value (the model words it; it never chooses it)."""

    if draw.kind == "coin":
        return f"lanzaste una moneda y salió {value}."
    if draw.kind == "die":
        dice = "un dado" if draw.count == 1 else f"{draw.count} dados"
        return f"tiraste {dice} de {draw.high} caras y {'salió' if draw.count == 1 else 'salieron'} {value}."
    return f"sacaste al azar un número del {draw.low} al {draw.high} y salió {value}."


def _drawn_literal(draw: RandomDraw, language: str) -> str:
    """Draw the requested value now and write it as the literal of the reply."""

    if draw.kind == "coin":
        faces = draw.faces or (("heads", "tails") if language == "en" else ("cara", "cruz"))
        return _DRAW.choice(faces)
    values = [str(_DRAW.randint(draw.low, draw.high)) for _ in range(draw.count)]
    if len(values) == 1:
        return values[0]
    joiner = " and " if language == "en" else " y "
    return ", ".join(values[:-1]) + joiner + values[-1]


# cien-40 007 «traduce 'good evening' al español» → «Buenas tardes»: el inglés
# saluda a la noche donde el español saluda a la tarde. Son equivalencias fijas
# de cortesía, no traducciones que dependan del contexto, así que se le dan
# hechas al traductor. Lo que no esté aquí se traduce como siempre.
_SET_PHRASE_TRANSLATIONS = {
    "good morning": "buenos días",
    "good afternoon": "buenas tardes",
    "good evening": "buenas noches",
    "good night": "buenas noches",
    "see you": "nos vemos",
    "see you later": "hasta luego",
    "see you soon": "hasta pronto",
    "goodbye": "adiós",
    "thank you": "gracias",
    "you are welcome": "de nada",
    "excuse me": "perdón",
    "i am sorry": "lo siento",
}


def _set_phrase_translation(user_text: str) -> tuple[str, str] | None:
    """The quoted set phrase of a translation request and its fixed equivalent."""

    quoted = quoted_translation_phrase(user_text)
    if quoted is None:
        return None
    phrase = " ".join(quoted.strip(" .!?,;:").casefold().split())
    equivalent = _SET_PHRASE_TRANSLATIONS.get(phrase)
    return (quoted.strip(), equivalent) if equivalent else None
