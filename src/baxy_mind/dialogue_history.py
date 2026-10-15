"""The dialogue a reply is written from: the bounded history, and the replies that only say the person's
words back or repeat BAXY's last answer.
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

from .semantic import dialogue as dialogue_slot
from .semantic import listing as semantic_listing
from .semantic.request import read_request
from .semantic.conversation import asks_or_has_words_said, recall_asked
from .llm_settings import MAX_CHAT_HISTORY_CHARS, MAX_CHAT_HISTORY_MESSAGES


def _bounded_history(history: object) -> list[dict[str, str]]:
    """Keep only conversational turns that fit the fixed, private context.

    History is application input, not trusted instruction.  A system, tool, or
    malformed turn must never be able to change the system prompt, and an
    unbounded transcript must not grow the KV cache past the measured profile.
    """

    if not isinstance(history, list):
        return []
    selected: list[dict[str, str]] = []
    remaining = MAX_CHAT_HISTORY_CHARS
    for item in reversed(history[-MAX_CHAT_HISTORY_MESSAGES:]):
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = item.get("content")
        if role not in {"user", "assistant"} or not isinstance(content, str):
            continue
        content = content.strip()
        if not content:
            continue
        if remaining <= 0:
            break
        content = content[-remaining:]
        selected.append({"role": role, "content": content})
        remaining -= len(content)
    selected.reverse()
    return selected


def _normalized_dialogue_text(value: object) -> str:
    """Canonicalize dialogue only for duplicate/echo detection."""

    normalized = unicodedata.normalize("NFKC", str(value or ""))
    return " ".join(
        "".join(
            character.casefold() if character.isalnum() else " "
            for character in normalized
        ).split()
    )


# M85 (DEV-D v3o D-p27-t5 «Nope, that's a lot.» → «That is a lot.»): the person's statement said back, with its
# interjection dropped or a contraction spelled out, is still an echo.
_ECHO_INTERJECTION = frozenset(
    "nope no nah yeah yep yes ok okay oh ah well so si sí vale bueno pues ya uh hmm mm".split()
)
_ECHO_CONTRACTIONS = {"s": "is", "re": "are", "m": "am", "ll": "will", "ve": "have", "d": "would", "t": "not"}


def _echo_words(value: object) -> list[str]:
    words = _normalized_dialogue_text(value).split()
    spelled = [_ECHO_CONTRACTIONS.get(word, word) for word in words]
    while spelled and spelled[0] in _ECHO_INTERJECTION:
        spelled.pop(0)
    return spelled


def _says_the_person_back(reply: object, request: object) -> bool:
    """A short reply whose words are the person's own words (interjections and contractions aside)."""

    said, asked = _echo_words(reply), _echo_words(request)
    if not (0 < len(said) <= 8 and said == asked) and not _mirrors_the_person(said, asked, request):
        return False
    # A greeting, thanks or a goodbye is answered in kind («hola» → «¡Hola!»).
    return not (dialogue_slot.is_social(str(request or "")) or read_request(str(request or "")).greets)


# M103 (owner script t40 «No lo hiciste mentiroso, nose no lo vi» → «No lo hice mentiroso, pero no lo vi.»): the
# person's sentence turned to the first person, one filler swapped, is their words said back too. Asked to say or
# repeat something, or asked a question, a reply in their words is the answer (semantic.conversation).


def _same_word_stem(word: str, other: str) -> bool:
    """Equal, or one verb's two persons («hice»/«hiciste», «vi»/«viste»): a shared start of three letters."""

    return word == other or (min(len(word), len(other)) >= 4 and word[:3] == other[:3])


def _mirrors_the_person(said: list[str], asked: list[str], request: object) -> bool:
    if not 4 <= len(said) <= 12 or asks_or_has_words_said(request):
        return False
    theirs = [word for word in said if any(_same_word_stem(word, other) for other in asked)]
    return len(said) - len(theirs) <= 1 and len(theirs) >= 0.8 * len(asked)


def _repeats_the_last_answer(reply: object, last_answer: object, request: object) -> bool:
    """M99 (DEV-D v3x D-p31-t3 «Gracias por tu aportación…» → BAXY's previous answer again, word for word): a reply that
    is BAXY's last message again, or a sentence-long piece of it, answers nothing of what the person says now. Asked to
    say it again («repite», «what did you say»), it is the answer."""

    said, last = _normalized_dialogue_text(reply), _normalized_dialogue_text(last_answer)
    if not said or not last or recall_asked(request) is not None:
        return False
    if said == last:
        return True
    # Ronda 24 (r23 t3-c17 t2 «no te pedi 4 po, me tiraste como 7, solo 4» → the three causes told plus the one
    # missing, vetoed as the last answer with a tail): after a correction that says a count, a list of another count
    # is another answer. Contracaso: «Ya te dije: <the last answer>» lists the same count and is still the same.
    # Revisión 2: only a correction that disputes the count (semantic.listing.count_disputed); a correction that only
    # names a number («no bro, la 3 está mal») keeps the last answer with a tail as a repeat. Revisión 3: read before
    # the piece-of-it check, since the first 4 of 7 items kept word for word are a piece of the last answer and the
    # count asked all the same.
    if dialogue_slot.corrects_or_insists(str(request or "")) and semantic_listing.count_disputed(str(request or "")):
        now, before = semantic_listing.counts_listed(str(reply or "")), semantic_listing.counts_listed(str(last_answer))
        if now and not set(now) & set(before):
            return False
    if len(said.split()) >= 6 and said in last:
        return True
    # Ronda 19 (t2-c03 T3 «no bro cerraste el que no era…» → the last answer «…en ese momento» again with «, por lo que
    # no se pudo realizar la acción» added; t3-c17/2 «los» for «las»): after a correction, the last answer with a tail
    # added, or with only an article, a demonstrative or a clitic changed, is still that answer. Both are a sentence
    # long and share 80 % of the longer one's words; a number or a name changed is another result («el brillo en 30»
    # after «en 50», «Discord no está abierto» after «Spotify no está abierto», «el clima en Curicó» after «en
    # Santiago»), never the same answer. Revisión de la ronda 19: any other turn keeps the word-for-word check alone
    # (no veto, no second call). Revisión adversarial 2: the word a correction changes is the verb or the polarity
    # («Bajé» after «Subí», «Cerré» after «Abrí», «down» after «up»): any changed word outside the neutral ones
    # (data: correction_words.v1.json, repeat_neutral) is another answer.
    if not dialogue_slot.corrects_or_insists(str(request or "")):
        return False
    if len(said.split()) >= 6 and len(last.split()) >= 6 and last in said:
        return True
    words, before = said.split(), last.split()
    if min(len(words), len(before)) < 6:
        return False
    if sorted(word for word in words if any(c.isdigit() for c in word)) != sorted(
        word for word in before if any(c.isdigit() for c in word)
    ):
        return False
    changed = set(words) ^ set(before)
    if changed & (_names_written(reply) | _names_written(last_answer)):
        return False
    if not changed <= _repeat_neutral_words():
        return False
    shared = sum(min(words.count(word), before.count(word)) for word in set(words))
    return shared >= 0.8 * max(len(words), len(before))


@lru_cache(maxsize=1)
def _repeat_neutral_words() -> frozenset[str]:
    from .semantic.grammar import correction_words

    return frozenset(_normalized_dialogue_text(word) for word in correction_words()["repeat_neutral"])


def _names_written(text: object) -> set[str]:
    """The words an answer writes capitalized inside a sentence (names: «Spotify», «Curicó», «París»), as
    ``_normalized_dialogue_text`` writes them; a sentence's first word is capitalized whatever it is."""

    names: set[str] = set()
    for sentence in re.split(r"[.!?¡¿:;\n«»\"“”]+", unicodedata.normalize("NFKC", str(text or ""))):
        for word in re.findall(r"[^\W_]+", sentence)[1:]:
            if word[0].isupper():
                names.add(_normalized_dialogue_text(word))
    return names
