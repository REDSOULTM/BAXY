"""The dialogue slot: what the previous turns leave open for the next one.

A turn leaves at most one hole: the question BAXY just asked (with the request it
belongs to), or a referent the next message may point back to (the effect just
done, the entity or topic just named, one or two user turns back). A message that
depends on that hole — a bare answer, «sí», «no, en YouTube», a pronoun object
(«súbelo», «cerralo», «activalo», «investigala») or a research verb without its
topic — is rewritten into a self-contained request with words of the context, and
that request is classified by the ordinary path. Everything else is left alone:
talk stays talk whether or not a question is pending.

This module decides only *whether* the message depends on the context and
*whether* a proposed rewrite stays inside it. The rewrite itself is the model's
(``llm.rewrite_in_context``); it can never add an object, an effect or a name the
person and BAXY did not already say.

The shell holds the pending request (it asked); it sends it with the turn and uses
the rewritten request the mind returns. Neither side re-reads the other's text. A
question BAXY asked that the shell does not hold still belongs to the request before
it, and a yes or a value after it answers that request (``read_slot``).
"""

from __future__ import annotations

import functools
import json
import re
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Callable, Iterable

from . import lexicon
from . import messaging
from .claims import service_name
from .grammar import _COVERAGE_ACTION_HEAD, _GOOGLE_ENGINE, _RELATIVE_DURATION_PATTERN, _head_is, correction_phrases
from .grammar import _SEARCH, _compiled, _head_forms, _imperatives_of, _request_head
from .grammar import _cease_order_head, _clause_orders, correction_words, without_correction_interjection
from .levels import followup_antecedent
from .normalize import alternation, fold, spelled_out
from .notes import changed_entry_names, entry_name
from .patterns import datetime_followup_antecedent
from .temporal import (
    alarm_cancellation_request,
    moved_to_clock,
    moved_to_length,
    notification_retiming,
    offset_retiming,
    plural_alarm_cancellation,
    retimed_local_moment,
    spoken_clocks,
    _TASK_TIME,
)

_WORD = re.compile(r"[a-z0-9ñ]+")

# Object clitics fused to an imperative or an infinitive: «súbelo», «cerralo»,
# «activalo», «investigala», «prenderlo», «devolvele», «dímelo».
_ENCLITIC = re.compile(
    r"\b[a-zñ]{3,}(?:a|e|i|ar|er|ir|ando|iendo)(?:me|te|se|nos)?(?:lo|la|los|las|le|les)\b"
)
# The short imperatives with their clitic, for an object to be said in place of it: «ponlo al 50», «hazlo», «tenla»
# (review 2026-10-08 r2: «no, el brillo te dije, no el volumen. ponlo al 50» lost its 50).
_SHORT_IMPERATIVE_CLITIC = re.compile(r"(?:pon|haz|ten|di)(?:me|te|se|nos)?(?:lo|la|los|las|le|les)")
# A clitic before a finite verb at the start: «lo subís a 100», «la cerrás».
_PROCLITIC_START = re.compile(
    r"^(?:y\s+|ahora\s+|pues\s+)?(?:me\s+|te\s+)?(?:lo|la|los|las|le|les)\s+"
    r"[a-zñ]{2,}(?:as|es|is|o|amos|emos|imos|an|en)\b"
)
# A question word after the preposition asks a question of its own: «¿en qué lugar te hicieron?», «¿desde cuándo
# existes?», «in which year…» (tanda 9: a question about BAXY was read as a new destination for the topic before).
_NOT_ASKED = (
    r"(?!(?:que|quien|quienes|cual|cuales|cuando|donde|cuanto|cuanta|cuantos|cuantas|como|what|which|who|whom|whose|"
    r"when|where|how)\b)"
)
# «no, en YouTube», «mejor en Spotify», «en YouTube mejor», «por WhatsApp».
_DESTINATION_ONLY = re.compile(
    r"^(?:(?:no|nop|mejor|en\s+cambio|pero|y)\s*[,.]?\s*)*"
    rf"(?:en|por|con|desde|a|al|on|in|with)\s+{_NOT_ASKED}(?:el\s+|la\s+|mi\s+)?[a-z0-9ñ+ .'-]{{2,30}}?"
    r"(?:\s+(?:mejor|entonces|porfa|por\s+favor|please))?$"
)
# Verbs that look something up about a topic the person may have said before.
_RESEARCH_VERB = re.compile(
    r"\b(?:investig|averigu|busc|googl|fijate|fijese|chequea|chequear|revisa\s+(?:que|si|cuando|como)|"
    r"look\s+(?:it\s+)?up|search|find\s+out|check\s+(?:if|when|what|how))\w*"
)
# Bare assent: the whole message only says yes. Estabilización M (live identity check §3d: «Sí, estoy seguro» after
# «¿Estás seguro de que quieres actualizar ese recuerdo?» was read as the person talking about themselves, and the
# writer answered «Tu color favorito ahora es el verde.» with nothing done): being sure, said to a question, is a yes.
# Revisión M H5: the words are one list with the App's confirmation (data/assent_words.v1.json).
_ANSWER_WORDS = json.loads(
    (Path(__file__).resolve().parent.parent / "data" / "assent_words.v1.json").read_text(encoding="utf-8")
)
_ASSENT_WORDS = _ANSWER_WORDS["words"]


def _whole_answer(words: list[str]) -> re.Pattern[str]:
    """A message that only says these words (up to four, with commas or stops between them)."""

    alternatives = "|".join(re.escape(word).replace(r"\ ", r"\s+") for word in sorted(words, key=len, reverse=True))
    return re.compile(r"^(?:(?:" + alternatives + r")[\s,.!]*){1,4}$")


_ASSENT = _whole_answer(_ASSENT_WORDS)


def _says_yes(text: str) -> bool:
    """The whole message only says yes; a question mark makes it a doubt («¿seguro?», «¿sí?»: revisión M H6)."""

    raw = str(text or "")
    return "?" not in raw and "¿" not in raw and _ASSENT.fullmatch(_fold(raw).strip(" ¡!.,")) is not None


# A refusal: the whole message only declines («no, dejalo», «mejor no», «olvidalo», «no thanks»).
# It never completes the pending request; «no, en YouTube» carries a destination and is not one. Estabilización M2: the
# words are one list with the App's cancellation of a confirmation (data/assent_words.v1.json, declineWords).
_REFUSAL = _whole_answer(_ANSWER_WORDS["declineWords"])
# A prohibition is an instruction of its own, never the answer to a pending question (cien-99 097: «don't
# open the calculator» after «¿Qué quieres que abra?» was rearmed onto «ábreme eso» and answered in Spanish).
_PROHIBITION = re.compile(r"^(?:no|nunca|jamas|tampoco|don'?t|do\s+not|never)\s+(?:(?:me|te|lo|la|los|las|le|les|it)\s+)?[a-z]{3,}")
# A request whose only object is a demonstrative («haz eso», «ábreme eso porfa», «do that»).
_BARE_DEICTIC_REQUEST = re.compile(r"[a-z]+(?:\s+(?:me|lo|la))?\s+(?:eso|esto|aquello|that|this|it)(?:\s+(?:porfa|por\s+favor|please))?")
# Talk that never answers a slot, even with a question pending: the whole message is thanks, a reaction or a
# closing, with at most a filler around it. Tanda 8 «ah, y tomates» is an interjection before a request, not talk.
_SOCIAL_WORD = (
    r"(?:gracias|muchas\s+gracias|genial|perfecto|buenisimo|jaja\w*|jeje\w*|uf+|ah+|oh+|wow|"
    r"que\s+(?:bien|bueno|buena|genial|lindo|linda|risa|gracioso)|"
    # M65 (conv-v3g owner script t37 «Perfecto muy bien», t31 «Muy bien baxy»): praise said alone. A bare «bien»
    # stays out: after a yes/no question it can be the yes.
    r"muy\s+bien|bien\s+hecho|buen\s+trabajo|excelente|de\s+lujo|"
    r"thanks|thank\s+you|cool|nice|great|perfect|awesome|good\s+job|well\s+done|great\s+job|"
    # Tanda 7 «no that's all thank you»: closing the conversation continues nothing.
    r"that'?s\s+(?:all|it)|eso\s+es\s+todo|nada\s+mas|nothing\s+else)"
)
_SOCIAL = re.compile(
    rf"(?:(?:ok|okay|okey|vale|bueno|no|y|and|muy|mucho|so|very|much|really|baxy)\s*[,.!]*\s+)*{_SOCIAL_WORD}"
    rf"(?:\s*[,.!]*\s*(?:{_SOCIAL_WORD}|ok|okay|baxy|so\s+much|very\s+much|a\s+lot|entonces|then))*"
)
_NUMBER_WORDS = (
    "cero uno una dos tres cuatro cinco seis siete ocho nueve diez once doce trece catorce quince dieciseis "
    "diecisiete dieciocho diecinueve veinte veinticinco treinta cuarenta cincuenta sesenta setenta ochenta noventa "
    "cien one two three four five six seven eight nine ten fifteen twenty thirty forty fifty sixty seventy eighty "
    "ninety hundred"
).split()
_NUMBER_ANSWER = re.compile(
    r"^(?:(?:a|al|en|hasta|unos|unas|como|en\s+el|to|by|about)\s+)*(?:\d{1,3}|"
    + "|".join(_NUMBER_WORDS)
    + r")(?:\s*(?:%|por\s*ciento|percent|puntos|mas|menos|more|less))?[\s.!]*$"
)
_STOPWORDS = frozenset(
    """
    a al algo ante con de del el en entre es esa ese eso esta este esto hasta la las le les lo los me mi mis
    muy no o para pero por que se si sin su sus te tu tus un una uno unos y ya yo vos sobre acerca about
    the a an and or to of in on at for with it this that is are be my your me you
    """.split()
)
# The frame of a request, which names no object, amount or place: a verb that sets or tells and a question word.
# Tanda 8 «40 percent» after «the screen is way too bright» is «set the screen brightness to 40 percent»; the
# object still has to be one said, and a follow-up must still read the family it continues.
_FRAME_WORDS = frozenset(
    """
    set put make change turn tell show read give pon ponme poner pone cambia cambiar deja dejar dime decime muestra
    muestrame lee leeme dame what which who how when where cual cuales quien quienes como cuando donde cuanto
    cuanta cuantos cuantas have has got do does did tengo tiene hay
    """.split()
)


_fold = fold


def _words(text: str) -> list[str]:
    """The words of a text for the rewrite's check, short and chat forms in full («finde» → fin de semana)."""
    return _WORD.findall(spelled_out(_fold(text)))


@dataclass(frozen=True)
class DialogueSlot:
    """What the next message may depend on."""

    pending_request: str | None
    pending_question: str | None
    antecedents: tuple[str, ...]  # user requests, most recent first (at most two)
    last_reply: str | None
    held: bool = True  # the shell holds the pending request; False when it is only read from BAXY's question
    # The last exchanges as the person saw them, oldest first (speaker, text). Tanda 8 «vale, léemela otra vez»:
    # the list was named three exchanges back and BAXY's replies between were missing from what the rewrite saw.
    transcript: tuple[tuple[str, str], ...] = ()

    @property
    def has_context(self) -> bool:
        return bool(self.pending_request or self.antecedents)

    def context_lines(self) -> list[tuple[str, str]]:
        """Oldest first, as (speaker, text), for the rewrite prompt and its word check."""
        if self.transcript:
            lines = list(self.transcript)
            said = {text for speaker, text in lines if speaker == "persona"}
            if self.pending_request and self.pending_request not in said:
                lines.insert(len(lines) - 1 if lines and lines[-1][0] == "BAXY" else len(lines),
                             ("persona", self.pending_request))
            return lines
        lines = [("persona", text) for text in reversed(self.antecedents)]
        if self.pending_request and self.pending_request not in self.antecedents:
            lines.append(("persona", self.pending_request))
        if self.last_reply:
            lines.append(("BAXY", self.last_reply))
        return lines


def read_slot(message: dict, history: object, current: str) -> DialogueSlot:
    """Read the slot from the shell's pending request and the recent history.

    Tanda 8 («the screen is way too bright» → «Do you mean…?» → «40 percent»): when BAXY's last reply asked a
    question and the shell holds no request for it, the question still belongs to the person's request before it,
    as a person would hear it; the answer is read against that request. The rewrite it leads to is decided by the
    ordinary path, so the slot grants nothing by itself.
    """

    pending_request = str(message.get("pendingObjective") or "").strip() or None
    items = [item for item in history if isinstance(item, dict)] if isinstance(history, list) else []
    if items and items[-1].get("role") == "user" and str(items[-1].get("content") or "") == current:
        items = items[:-1]
    antecedents: list[str] = []
    last_reply = None
    transcript: list[tuple[str, str]] = []
    for item in reversed(items[-8:]):
        role, content = item.get("role"), str(item.get("content") or "").strip()
        if not content or role not in {"user", "assistant"}:
            continue
        transcript.insert(0, ("persona" if role == "user" else "BAXY", content[:400]))
        if role == "assistant" and last_reply is None and not antecedents:
            last_reply = content[:400]
        elif role == "user" and len(antecedents) < 2:
            antecedents.append(content[:400])
    asked = bool(last_reply and last_reply.rstrip().endswith("?"))
    held = pending_request is not None
    if not held and asked and antecedents:
        pending_request = antecedents[0]
    pending_question = last_reply if pending_request and asked else None
    return DialogueSlot(pending_request, pending_question, tuple(antecedents), last_reply, held, tuple(transcript))


# M85 (DEV-D v3o D-p09-t3 «never mind do not add barbells to my fitness list» right after «I've added barbells to your
# fitness list.», the same in v3f and v3m): the prohibition was closed as talk, and the reply «I did not add barbells
# to your fitness list.» denied what BAXY had just done. A prohibition of the very act BAXY's last reply reports done,
# on the same thing, takes that act back: it is about the last effect, never a standing rule to acknowledge.
_RETRACTION_LEAD = re.compile(
    r"^(?:(?:(?:never\s*mind|nevermind|forget\s+(?:it|that)|scratch\s+that|actually|wait|oh|"
    r"olvidalo|olvida\s+(?:eso|lo)|mejor|pensandolo\s+bien|no\s+importa|dejalo|espera|pera|ah|oye)\b[\s,.;:!]*)|"
    r"(?:no|nope)\s*[,.;:!]+\s*)+"
)
_RETRACTION_VERB = re.compile(
    r"^(?:(?P<es>no|nunca|jamas)\s+(?:(?:me|te|le|les|lo|la|los|las|nos)\s+)?|(?:don'?t|do\s+not|never)\s+)"
    r"(?P<verb>[a-z]+)\s+(?P<rest>.+)$"
)
_FAILED_REPORT = re.compile(
    r"\b(?:no\s+(?:pude|se\s+pudo|logre|encontre)|could\s*n[o']t|was\s*n[o']t\s+able|not\s+able|failed|"
    r"no\s+(?:he|ha)\s+\w+(?:ado|ido))\b"
)


# Uso real v3 t2 (c04-3 «no espera se ve muy grande, regresala como estaba» → «No hago ajustes de tamaño de ventana»):
# putting back what the last change changed, said with its verb and «como estaba / como antes / the way it was», or
# undoing it whole («deshazlo», «undo that»). Folded.
_UNDO_LAST = re.compile(
    # «vuelve a abrirlo como antes» does it again (volver a + infinitive), never undoes it.
    r"\b(?:regresa|devuelve|(?:vuelve|volve)(?!\s+a\s+[a-z]+(?:ar|er|ir)(?:l[oa]s?|me|te|se|le)?\b)|deja|pon|pone|"
    r"restaura|revierte|poner|dejar|regresar|devolver|restaurar|return|put|set|turn|change)"
    r"(?:la|lo|las|los|le|me|mela|melo|sela|selo)?\s+(?:[a-z]+\s+){0,3}?"
    r"(?:a\s+)?(?:como\s+(?:estaba|era|antes|lo\s+tenia|la\s+tenia)|a\s+lo\s+de\s+antes|al?\s+valor\s+(?:de\s+antes|anterior)|"
    r"(?:back\s+)?(?:the\s+way|how)\s+it\s+was|back\s+to\s+(?:how|what)\s+it\s+was|back\s+to\s+before)\b"
    r"|\b(?:deshaz|deshace|deshacelo|deshazlo|desace)(?:\s+(?:eso|el\s+cambio|lo\s+ultimo|lo\s+que\s+hiciste))?\b"
    r"|\b(?:undo|revert)\s+(?:that|it|this|the\s+(?:last\s+)?change|what\s+you\s+did)\b"
)
# What BAXY's last reply says when the act it was asked did not happen: a failure told, or a «no se/no hice».
_NOTHING_CHANGED_REPORT = re.compile(
    r"\b(?:no\s+(?:pude|se\s+pudo|logre|llegue\s+a|hice|cambie|se\s+cambio|se\s+(?:cerro|abrio|puso|aplico))|"
    r"could\s*n[o']t|was\s*n[o']t\s+able|not\s+able|failed|did\s*n[o']t\s+(?:change|do|apply))\b"
)


def asks_to_undo(text: str) -> bool:
    """«regrésala como estaba», «déjalo como antes», «deshazlo», «put it back the way it was», «undo that»: the person
    asks to put back what the conversation's last change changed. A question is not one («¿cómo estaba?»)."""

    folded = _fold(str(text or ""))
    return "?" not in folded and _UNDO_LAST.search(folded) is not None


# Revisión 4 de la ronda 24: what may close an undo without being another order («regrésala como estaba antes, porfa»,
# «undo that bro»), and what joins a second order to it («… y abre spotify», «…, then close chrome»).
_UNDO_TAIL = frozenset("antes before bro wey man mejor plis pls plz please".split())
_UNDO_JOIN = re.compile(r"^(?:[\s,.;:!]|\b(?:y|e|and|then|despues|luego|tambien|also|plus)\b)+")


def only_undoes(text: str) -> bool:
    """Revisión 4 de la ronda 24: an undo (``asks_to_undo``) is all the message says — nothing after it but what closes
    it (``_order_after``) and no clause before it that orders (``grammar._clause_orders``): «nah, déjalo como estaba y
    abre spotify», «undo that and open spotify», «deshazlo y borra el archivo notas.txt», «cierra chrome y después
    deshazlo» carry another order, which is never answered as an undo."""

    folded = _fold(str(text or ""))
    if "?" in folded:
        return False
    found = list(_UNDO_LAST.finditer(folded))
    if not found:
        return False
    # An order said before the undo («cierra chrome y después deshazlo») is another order too.
    before = re.split(r"[,;:.!¡]+|\s+(?:pero|but|y|and|then|luego|despues)\s+", folded[: found[0].start()])
    if any(_clause_orders(clause.strip()) for clause in before if clause.strip()):
        return False
    rest = _UNDO_JOIN.sub("", folded[found[-1].end():]).strip(" ¡!.,;:")
    words = [word for word in rest.replace(",", " ").split() if word not in _UNDO_TAIL]
    return not words or not _order_after(" ".join(words))


def undo_with_nothing_changed(text: str, last_reply: str | None) -> bool:
    """An undo (``asks_to_undo``) right after BAXY's reply told the act it was asked did not happen: there is nothing
    to put back, and saying so is the answer (uso real v3 t2, c04-3 after «No pude hacerlo en…»)."""

    reply = _fold(str(last_reply or ""))
    return bool(reply) and asks_to_undo(text) and _NOTHING_CHANGED_REPORT.search(reply) is not None


def retracts_the_last_effect(text: str, last_reply: str | None) -> bool:
    """«never mind, don't add barbells to my list» after «I've added barbells to your fitness list.»: the person takes
    back the effect BAXY's last reply reports as done (the same act, on the same thing). A question, a failure told
    or a reply about something else leaves the prohibition a prohibition."""

    reply = _fold(str(last_reply or ""))
    if not reply or "?" in reply or _FAILED_REPORT.search(reply) is not None:
        return False
    said = _RETRACTION_LEAD.sub("", _fold(str(text or "")).strip(" ¿?¡!.,")).strip()
    found = _RETRACTION_VERB.match(said)
    if found is None:
        return False
    verb = found.group("verb")
    # The act: the same stem in the report («add» → «added», «añadas» → «añadido», «pongas» → «puse» is left out).
    stem = verb[:4] if len(verb) > 5 else verb[:3]
    done = re.search(r"\b" + re.escape(stem) + r"[a-z]*\b", reply)
    # «El audio no está silenciado.» reports a state the act did not bring about.
    if done is None or re.search(r"\b(?:no|not|nunca|never|isn'?t|wasn'?t)\b(?:\s+\w+){0,2}\s*$", reply[:done.start()]):
        return False
    things = [
        word for word in _WORD.findall(found.group("rest"))
        if len(word) >= 4 and word not in _STOPWORDS and word not in _FRAME_WORDS
        and word not in {"list", "lista", "listas", "lists", "please", "porfa", "favor", "anymore", "ahora", "todavia"}
    ]
    return bool(things) and re.search(r"\b" + re.escape(things[0]) + r"\b", reply) is not None


# D59 §7 (owner, 2026-10-02): a turn that was not understood, and for which no valid question could be written, is
# asked about with the person's own words, a few of them, never answered with a fixed «no pude entender». The words
# are the message's, as written, without the fillers that open it and the function words a cut leaves at its end.
_FLOOR_WORDS = 6
_FLOOR_OPENING_FILLERS = frozenset({
    "y", "e", "o", "pero", "pues", "entonces", "oye", "oiga", "hey", "ey", "baxy", "ok", "okay", "vale", "bueno",
    "eh", "ah", "mmm", "um", "uh", "and", "so", "but", "well", "hmm", "please", "porfa",
})
_FLOOR_TRAILING_FUNCTION_WORDS = frozenset({
    "de", "del", "la", "el", "los", "las", "lo", "le", "que", "a", "al", "en", "y", "e", "o", "u", "con", "por",
    "para", "un", "una", "unos", "unas", "mi", "mis", "tu", "tus", "su", "sus", "se", "si", "no", "me", "te",
    "of", "the", "a", "an", "to", "and", "or", "in", "on", "with", "for", "at", "my", "your", "if", "that", "is",
})


@functools.lru_cache(maxsize=1)
def _words_floor_templates() -> dict[str, str]:
    """D59.7: the wording lives in data (no fixed visible prose in the source)."""

    path = Path(__file__).resolve().parent.parent / "data" / "words_floor_question.v1.json"
    return json.loads(path.read_text(encoding="utf-8"))


def words_floor_question(said: str, language: str) -> str:
    """«¿Qué quieres que haga con "si allá son las 10…"?», «What should I do with "the blue one"?»: the question of a
    turn not understood, built from the message (see above); "" when the message has no word to quote."""

    tokens = [
        token.strip("¿?¡!.,;:…\"'«»“”()[]")
        for token in re.sub(r"\s+", " ", str(said or "")).split(" ")
    ]
    tokens = [token for token in tokens if token]
    while len(tokens) > 1 and _fold(tokens[0]) in _FLOOR_OPENING_FILLERS:
        tokens.pop(0)
    if len(tokens) > 1 and _fold(" ".join(tokens[:2])) == "por favor":
        tokens = tokens[2:]
    while len(tokens) > 1 and _fold(tokens[-1]) in {"please", "porfa", "porfis", "gracias", "thanks"}:
        tokens.pop()
    if len(tokens) > 1 and _fold(" ".join(tokens[-2:])) == "por favor":
        tokens = tokens[:-2]
    cut = len(tokens) > _FLOOR_WORDS
    words = tokens[:_FLOOR_WORDS]
    if cut:
        while len(words) > 1 and _fold(words[-1]) in _FLOOR_TRAILING_FUNCTION_WORDS:
            words.pop()
    if not words:
        return ""
    quoted = " ".join(words) + ("…" if cut else "")
    templates = _words_floor_templates()
    return templates["en" if language == "en" else "es"].replace("{quoted}", quoted)


def understood_failure_line(language: str) -> str:
    """Estabilidad cu-v3 2026-10-08 (v2-v3-61): the short cause of a turn understood whose wording failed — never the
    person's words asked back (data: words_floor_question.v1.json «understood»)."""

    return _words_floor_templates()["understood"]["en" if language == "en" else "es"]


def says_the_message_back(question: str, said: str) -> bool:
    """M85 (DEV-D v3o D-p04-t1 «Dónde?» → «¿Dónde?»): a question that is the person's own message, word for word."""

    words = _WORD.findall(_fold(str(said or "")))
    return bool(words) and _WORD.findall(_fold(str(question or ""))) == words


# M93 (DEV-D v3u D-s053 «¿Miguel sigue viviendo en Arkansas?» → «¿Te refieres a Miguel o a alguien más?»): a question
# that offers back the one the person named, or «someone else», asks nothing the person has not said; which Miguel, or
# who he is, is the question. Folded.
_NAMED_OR_ANOTHER = re.compile(
    r"^\W*(?:te\s+refieres|hablas|me\s+hablas|preguntas|quieres\s+decir)\s+(?:a|de|por)\s+(?P<es>.+?)\s+o\s+"
    r"(?:a\s+|de\s+|por\s+)?(?:alguien|otra\s+persona|otro|otra|algun\s+otro|alguna\s+otra)\b|"
    r"^\W*(?:do\s+you\s+mean|are\s+you\s+(?:talking|asking)\s+about)\s+(?P<en>.+?)\s+or\s+"
    r"(?:someone|somebody|another|anyone|a\s+different)\b"
)


def offers_back_the_named_one(question: str, said: str) -> bool:
    """The question offers the person's own named one «or someone else» (see above)."""

    found = _NAMED_OR_ANOTHER.match(_fold(str(question or "")))
    if found is None:
        return False
    named = _WORD.findall(found.group("es") or found.group("en") or "")
    spoken = set(_WORD.findall(_fold(str(said or ""))))
    return bool(named) and all(word in spoken or word in {"el", "la", "the"} for word in named)


def _object_pronoun(folded: str) -> bool:
    """A verb with a fused object pronoun whose object is not said.

    «apagalo», «subila a 20»: the object is the pronoun. «devolvele el sonido», «mandale un
    mensaje»: «le» is the dative (to whom); the object («el sonido») is said, so the message
    stands on its own (held-out turn 9). «bajale un poco», «pausalo un toque»: an amount or a
    while is not an object.
    """

    for found in _ENCLITIC.finditer(folded):
        tail = _CLITIC_TAIL.search(found.group(0))
        if tail is None or not _verb_with_clitic(found.group(0), tail.group(0), folded[: found.start()]):
            continue
        rest = folded[found.end():].split()
        if tail.group("clitic") in {"le", "les"} and rest and (
            (rest[0] in _DETERMINERS and not (len(rest) > 1 and rest[1] in _DEGREE))
            or _DATIVE_OBJECT.match(" ".join(rest))
        ):
            continue
        return True
    return False


_DETERMINERS = frozenset({"el", "la", "los", "las", "un", "una", "unos", "unas", "mi", "mis", "su", "sus", "algo", "que"})
# How much or how long, said after the verb («bajale un poco», «pausalo un toque», «seguí un rato»): never its object.
_DEGREE = frozenset(
    """
    poco poquito poquitito toque toquecito cachito cacho chin pelin rato ratito momento momentito segundo tantito
    """.split()
)
# A verb stands first in its clause: after nothing, a pause, a connector or a filler («ok postealo», «y cerralo»).
_VERB_POSITION = re.compile(
    r"(?:^|[,;.!?]|\b(?:y|e|pero|luego|despues|entonces))\s*"
    r"(?:(?:ok|okay|okey|oye|che|bueno|pues|dale|ya|ahora|porfa|baxy|no|mejor|va|vale|orale|sale)\b[\s,.]*)*$"
)
_INFINITIVE_OR_GERUND_CLITIC = re.compile(r"(?:ar|er|ir|ando|iendo)(?:me|te|se|nos)?(?:lo|la|los|las|le|les)$")


def _verb_with_clitic(word: str, clitic: str, before: str) -> bool:
    """«pausalo», «cerralo», «postealo» are a verb and its pronoun; «chilaquiles», «internacionales» and «cancela» are
    not (tanda 9: «cómo se hacen los chilaquiles verdes» was rewritten with a place two turns before).

    An infinitive or a gerund with its clitic is a verb. Otherwise the word without the clitic must be an order the
    readers know («pausa», «baja»); a word that is itself such an order («cancela») carries no clitic; and a word
    neither says must stand where a verb stands, first in its clause.
    """

    if _INFINITIVE_OR_GERUND_CLITIC.search(word):
        return True
    if _head_is(word[: len(word) - len(clitic)], _COVERAGE_ACTION_HEAD):
        return True
    if _head_is(word, _COVERAGE_ACTION_HEAD):
        return False
    return _VERB_POSITION.search(before) is not None


# Tanda 7b «oye súbele al volumen po» was rewritten as «… al volumen please use whisper mode»: «le» doubles the object
# said after it with «a» («súbele al volumen», «dale a la música»); «súbele al 50» still leaves it out.
_DATIVE_OBJECT = re.compile(r"(?:al|a\s+(?:la|las|los|el|mi|mis|tu|tus))\s+(?!\d)[a-zñ]")


def dependency(text: str, slot: DialogueSlot) -> str | None:
    """Why this message needs the context to be understood, or None.

    ``answer``      a short answer or «sí» to the question BAXY just asked;
    ``destination`` «no, en YouTube»: only the destination of the last request changes;
    ``reference``   a pronoun object («súbelo», «cerralo», «pause it») or an order said without one («dale, seguí»);
    ``subject``     a person's age asked without the person («¿y cuántos años tiene?», «how old is he»);
    ``topic``       a lookup verb whose topic may have been named before («averiguá qué dijo la crítica»);
    ``followup``    anything else whose form leans on the turn before (``leans_on_context``): «¿y el finde?»,
                    «actually make it 9», «cómo se llama esta?», «is the entrance free».
    """

    if not slot.has_context:
        return None
    folded = _fold(text).strip(" ¿?¡!.,")
    if not folded or _SOCIAL.fullmatch(folded) or _REFUSAL.fullmatch(folded) or _PROHIBITION.match(folded):
        return None
    words = folded.split()
    if slot.pending_request:
        if _says_yes(text) and _BARE_DEICTIC_REQUEST.fullmatch(_fold(slot.pending_request).strip(" ¿?¡!.,")):
            # cien-99 049: «hazlo» after «haz eso» → «¿Qué es eso?». Agreeing to a request
            # with no object completes nothing; the message is read on its own.
            return None
        if _says_yes(text) or _NUMBER_ANSWER.fullmatch(folded) or followup(text).value:
            # Tanda 9 «It will be for 3:30 pm.» after BAXY asked what to do: a value answers the question.
            return "answer"
        # A question read only from BAXY's reply is answered by a yes or a value; any other message is read as usual.
        if slot.held and ((len(words) <= 5 and _DESTINATION_ONLY.fullmatch(folded)) or len(words) <= 4):
            return "answer"
    rest = followup(text).folded
    if (
        slot.antecedents
        and len(words) <= 6
        and _DESTINATION_ONLY.fullmatch(folded)
        # Tanda 7 «no, a las 8»: an hour or an amount is not where; the follow-up replaces the one said.
        and not (_TIME_FRAGMENT.fullmatch(rest) or _AMOUNT_FRAGMENT.fullmatch(rest) or _AGAIN_FRAGMENT.fullmatch(rest))
    ):
        return "destination"
    if len(words) > 16:
        return None
    if slot.antecedents and _SUBJECTLESS_PERSON_FACT.fullmatch(folded):
        return "subject"
    if (
        _object_pronoun(folded)
        or (len(words) <= 6 and _PROCLITIC_START.match(folded))
        or (slot.antecedents and _bare_order(followup(text).folded))
    ):
        return "reference"
    if slot.antecedents and _RESEARCH_VERB.search(folded):
        return "topic"
    if slot.antecedents and leans_on_context(text):
        return "followup"
    return None


# Tanda 9 «ok y tomorow va a hacer más calor?» → «y mañana va a hacer más calor?» and «is it humid?» → «… today»
# after «hoy» were rejected: a day said in the other language (or typed with its stem kept) is the same word in the
# language of the message. Into another language it is still a word the model brought (tanda 7 «what about sunday?»
# → «¿llueve el domingo?»). Stems (Spanish, English).
_SAME_DAY = (
    ("hoy", "toda"), ("mana", "tomo"), ("ayer", "yest"), ("lune", "mond"), ("mart", "tues"), ("mier", "wedn"),
    ("juev", "thur"), ("vier", "frid"), ("saba", "satu"), ("domi", "sund"), ("sema", "week"), ("noch", "toni"),
)


def rewrite_stays_in_context(
    rewrite: str, text: str, slot: DialogueSlot, verified: list[tuple[str, str]] | None = None,
) -> bool:
    """Every content word of the rewrite was said by the person or BAXY, or is in what was verified.

    A four-letter stem is enough for inflection («súbelo» → «sube», «prenderlo» →
    «prende»); anything else is a word the model brought in, and the rewrite is
    discarded — the message is then classified exactly as it arrived.
    """

    rewrite = str(rewrite or "").strip()
    if not rewrite or len(rewrite) > 600 or "\n" in rewrite:
        return False
    said = set()
    for source in (text, *(line for _, line in (*slot.context_lines(), *(verified or ())))):
        for word in _words(source):
            said.add(word[:4])
    in_spanish = spanish(text)
    said |= {spanish_day if in_spanish else english_day for spanish_day, english_day in _SAME_DAY
             if (english_day if in_spanish else spanish_day) in said}
    meaningful = [word for word in _words(rewrite) if word not in _STOPWORDS]
    if not meaningful:
        return False
    return all(word[:4] in said for word in meaningful if word not in _FRAME_WORDS and not word.isdigit())


def asks_for_the_reason(text: str) -> bool:
    """«¿por qué no puedes…?», «why can't you…»: the person asks for the reason (independent review B1)."""

    return re.search(r"\b(?:por\s*que|why)\b", _fold(text)) is not None


def restatement_was_said(restatement: str, lines: list[str]) -> bool:
    """Every content word of a model's restatement is in these lines (what the person and BAXY said).

    The same four-letter-stem test as ``rewrite_stays_in_context``, for the contextual decider's ``request``
    (Fase 3.5b M19): «ábreme eso porfa» after the time was restated «Abre el navegador» and a browser opened.
    """

    said_words = [_undiphthonged(word) for line in lines for word in _words(line)]
    said = {word[:4] for word in said_words}
    meaningful = [
        _undiphthonged(word)
        for word in _words(restatement)
        if word not in _STOPWORDS and word not in _FRAME_WORDS and not word.isdigit()
    ]
    if meaningful and meaningful[0][:3] in {word[:3] for word in said_words}:
        # M65 (conv-v3g held-out t11 «cerralo» restated «Cierra el Bloc de notas.» was asked again): the leading
        # verb is the person's own in another person or mood («abrí»/«abre», «cerrá»/«cierra»); the pointer's
        # object is what has to have been said.
        meaningful = meaningful[1:]
    return all(word[:4] in said for word in meaningful)


def _undiphthonged(word: str) -> str:
    """A Spanish stem with its stressed diphthong undone («cierra» → «cerra», «vuelve» → «volve»)."""

    return word.replace("ie", "e").replace("ue", "o")


_NUMBER_VALUES = {
    "cero": 0, "uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7, "ocho": 8,
    "nueve": 9, "diez": 10, "once": 11, "doce": 12, "trece": 13, "catorce": 14, "quince": 15, "dieciseis": 16,
    "diecisiete": 17, "dieciocho": 18, "diecinueve": 19, "veinte": 20, "veinticinco": 25, "treinta": 30,
    "cuarenta": 40, "cincuenta": 50, "sesenta": 60, "setenta": 70, "ochenta": 80, "noventa": 90, "cien": 100,
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "fifteen": 15, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80,
    "ninety": 90, "hundred": 100,
}
_LEADING_TURN = re.compile(r"^(?:(?:no|nop|mejor|en\s+cambio|pero|y|pues|bueno)\b[\s,.]*)+")
_TRAILING_TURN = re.compile(r"[\s,.]*\b(?:mejor|entonces|porfa|por\s+favor|please)[\s.!]*$")
_TRAILING_DESTINATION = re.compile(r"\s+(?P<prep>en|por|on|in)\s+(?:el\s+|la\s+|mi\s+)?[\w.+'-]+(?:\s+[\w.+'-]+)?$")


def differs(first: str, second: str) -> bool:
    return _fold(first).strip(" ¿?¡!.,") != _fold(second).strip(" ¿?¡!.,")


def joined_answer(pending_request: str, answer: str, *, percentage: bool = False) -> str | None:
    """The pending request completed by a short answer, in the person's words.

    A number (digits or words) is appended as the value the question asked for;
    a destination replaces the destination the request had («pon X en Spotify» +
    «no, en YouTube» → «pon X en YouTube»); a bare «sí» is the request itself.
    The ordinary readers still have to accept the result.
    """

    request = str(pending_request or "").strip().rstrip(" .!?")
    folded = _fold(answer).strip(" ¿?¡!.,")
    if not request or not folded:
        return None
    if _says_yes(answer):
        return request
    original = " ".join(str(answer).split()).strip(" ¿?¡!.,")
    value = _TRAILING_TURN.sub("", _LEADING_TURN.sub("", original)).strip(" ,.")
    if not value:
        return None
    if _NUMBER_ANSWER.fullmatch(_fold(value)):
        value = " ".join(str(_NUMBER_VALUES.get(word, word)) for word in _fold(value).split())
        if percentage and re.fullmatch(r"(?:(?:a|al|en|hasta|to)\s+)?\d{1,3}", value):
            value += "%"
        return f"{request} {value}"
    destination = _DESTINATION_ONLY.fullmatch(folded)
    if destination is not None:
        trailing = _TRAILING_DESTINATION.search(request)
        preposition = _fold(value).split()[0] if value.split() else ""
        if trailing is not None and trailing.group("prep") == preposition:
            request = request[: trailing.start()]
        return f"{request} {value}"
    return f"{request} {value}"


def is_assent(text: str) -> bool:
    """The whole message only says yes («sí», «dale», «ok, sí»)."""
    return _says_yes(text)


@functools.lru_cache(maxsize=1)
def _offer_assent_words() -> dict:
    return json.loads((Path(__file__).resolve().parent.parent / "data" / "offer_assent.v1.json").read_text(encoding="utf-8"))


def accepts_offer(text: str, act: str) -> bool:
    """D39 and estabilización B2: the whole message is an unequivocal yes to an offer that acts once accepted («sí»,
    «sí, cancélalas todas», «dale, mándalo», «yes, send it»; ``data/offer_assent.v1.json``, ``act`` its acts). A
    question («¿sí?», «yes?»), a doubt («bueno...») or a bare «ya», «bueno», «please» is not (revisión B2 H1)."""

    raw = str(text or "").strip()
    if not raw or re.search(r"[¿?…]|\.\.", raw):
        return False
    words = _offer_assent_words()
    accepting = set(words["yes"]) | set(words["acts"][act])
    tokens = re.sub(r"[,;.!¡]", " ", _fold(raw)).split()
    said, index = False, 0
    while index < len(tokens):
        size = next(
            (size for size in (4, 3, 2, 1) if " ".join(tokens[index:index + size]) in accepting | set(words["with"])),
            0,
        )
        if not size:
            return False
        said = said or " ".join(tokens[index:index + size]) in accepting
        index += size
    return said


def is_refusal(text: str) -> bool:
    """The whole message only says no («no», «mejor no», «no thanks»)."""
    return _REFUSAL.fullmatch(_fold(text).strip(" ¿?¡!.,")) is not None


def calls_off(text: str) -> bool:
    """Revisión adversarial 2 r19: the whole message only calls off what was asked or leaves things as they are — a
    verb of leaving, cancelling or forgetting (``lexicon.CALL_OFF_VERBS``), with nothing before it but a lead
    («no», «mejor», «espera»: ``lexicon.CALL_OFF_LEADS``) and nothing after it but a pronoun, a demonstrative or how
    things stay (``lexicon.CALL_OFF_MODIFIERS``): «no, déjalo así», «no, cancela eso», «dejalo como está nomás»,
    «no, leave it as it is», «forget about it». «deja la escala en 100» or «cancela la suscripción» say what to do."""

    folded = re.sub(r"\bnever\s+mind\b", "nevermind", _fold(text))
    words = re.findall(r"[a-z0-9]+", folded.replace("'", "").replace("’", ""))
    if len(words) == 1 and words[0] in lexicon.CALL_OFF_BARE_ORDERS:
        # Revisión adversarial 3: «cancelá», «leave» said alone may press a dialog's Cancel or leave a call.
        return False
    for index, word in enumerate(words):
        if word in lexicon.CALL_OFF_VERBS:
            return all(lead in lexicon.CALL_OFF_LEADS for lead in words[:index]) and all(
                after in lexicon.CALL_OFF_MODIFIERS or after in lexicon.CALL_OFF_VERBS for after in words[index + 1:]
            )
        if word not in lexicon.CALL_OFF_LEADS:
            return False
    return False


def is_social(text: str) -> bool:
    """The whole message is thanks, praise, a reaction or a closing («gracias», «perfecto muy bien», «that's all»).

    It answers no question and asks for nothing, whatever is pending: the rewrite never reads it as a dependency
    (``dependency``) and the contextual decider's action on it is not the person's (M65).
    """

    folded = _fold(text).strip(" ¿?¡!.,")
    return bool(folded) and _SOCIAL.fullmatch(folded) is not None


# M99 (reserva A6 «quieres netflix and chill» → Netflix opened): asking whether BAXY wants something («¿quieres un
# café?», «do you want pizza?») offers it to BAXY; it orders nothing. Wanting an act («¿quieres poner música?», «do you
# want to play some jazz?», «¿quieres que la ponga?») is the polite order and is left out.
_OFFER_TO_BAXY = re.compile(
    r"(?:(?:y|and|oye|hey|baxy)[\s,]+)*(?:tu\s+)?(?:quieres|queres|quisieras|te\s+gustaria|te\s+apetece|do\s+you\s+want|"
    r"would\s+you\s+like|wanna|you\s+want)\s+"
    r"(?!(?:que|to|me|te|le|nos|lo|la|los|las|if|si)\b)(?![a-z]+(?:ar|er|ir)(?:me|te|lo|la|le|nos|los|las|les)?\b)\S"
)


def offers_to_baxy(text: str) -> bool:
    """«¿quieres netflix and chill?», «do you want a coffee?»: something offered to BAXY, no order (see above)."""

    return _OFFER_TO_BAXY.match(_fold(text).strip(" ¿?¡!.,")) is not None


# M88 (DEV-D v3r D-p24-t5 «That is confirmed to proceed.» after «I could not play Hustlers on Netflix because the
# service requires a sign-in…», the third run in a row): a go-ahead — the person confirms, approves or tells BAXY to
# proceed with something — was answered in a turn that ran nothing («The plan is confirmed to proceed.», «Confirmed,
# the procedure will proceed.», «I confirm the action will proceed.»). The writer was never told that nothing ran and
# nothing was waiting for a yes, so it acknowledged the go-ahead; the vetoes on its wording chased each new phrasing.
# The go-ahead is read here, from the person's message: a word that approves proceeding, with nothing else said but
# fillers. A bare «sí», «ok», «dale» or «vale» is an answer or an acknowledgement, not read here, and neither is
# «sigue» (see below).
_GO_AHEAD_CORE = re.compile(
    r"\b(?:confirm\w*|proceed\w*|proced\w*|approv\w*|aprob\w*|aprueb\w*|autoriz\w*|authoriz\w*|adelante|"
    r"go\s+ahead|do\s+it|hazlo|hacelo|haganlo|hagalo|hagamoslo|let'?s\s+do\s+it|green\s+light|luz\s+verde)\b"
)
# «sigue», «continúa», «go on» are left out: after a story or an answer they ask for more of it, which is talk.
_GO_AHEAD_FILLER = frozenset(
    """
    yes yeah yep yup ok okay okey sure please si sip dale vale bueno claro porfa por favor entonces pues ya ahora
    that is thats it its it's everything all set to then so now you can may i we the action plan it's everything's
    for me with lo la eso esto todo esta esta todo con puedes podes puede pueden eso con el la este esta ahi
    right alright good fine just go let us let's
    """.split()
)


def gives_go_ahead(text: str) -> bool:
    """The whole message is a go-ahead: it confirms, approves or tells BAXY to proceed («That is confirmed to
    proceed.», «ok, hazlo», «adelante», «you may proceed»), and says nothing else (see above)."""

    folded = _fold(text).strip(" ¿?¡!.,")
    if not folded or "?" in str(text or "") or _GO_AHEAD_CORE.search(folded) is None:
        return False
    rest = _GO_AHEAD_CORE.sub(" ", folded)
    return all(word in _GO_AHEAD_FILLER for word in re.findall(r"[a-z']+", rest))


_DO_THAT = re.compile(
    r"^(?:(?:ya|bueno|entonces|pues|baxy|oye|ok|okay)[\s,]+)*"
    r"(?:haz|hace|has|hacer|do|just\s+do|go\s+do)\s+(?:eso|esto|aquello|that|this)"
    r"(?:[\s,]+(?:ya|ahora|porfa|por\s+favor|please|now|then|entonces))*$"
)


def do_that_with_nothing_named(text: str, last_reply: str | None) -> bool:
    """M118 (cien-113 048 «haz eso» after «keep chatting without opening apps», answered with a false limit): «do that»
    points at a thing to do; after a reply of BAXY's that offered or asked nothing, nothing to do was named, and what
    «eso» is gets asked."""

    folded = _fold(text).strip(" ¿?¡!.,")
    return _DO_THAT.match(folded) is not None and not str(last_reply or "").rstrip().endswith("?")


def remate_of_what_was_done(text: str, last_reply: str | None) -> bool:
    """M118 (owner script t57 «al volumen» right after «ahora subelo a 100» → «He puesto el volumen en 100…» was asked
    «¿Cuánto le subo?»): a short tail that only names what BAXY just reported done — no number, no word BAXY did not
    say — is a remate of it, never a new request whose amount is asked again."""

    reply = _fold(str(last_reply or "")).strip()
    folded = _fold(text).strip(" ¿?¡!.,")
    words = re.findall(r"[a-z0-9]+", folded)
    content = [word for word in words if len(word) >= 4]
    said = set(re.findall(r"[a-z0-9]+", reply))
    return bool(
        reply
        and not reply.endswith("?")
        and 1 <= len(words) <= 3
        and not any(word.isdigit() for word in words)
        and content
        and all(word in said for word in content)
    )


# Estabilización F3 (banco h1 c6: «sí» after «No pude escribir ni enviar el mensaje en Discord…» was answered «Sí, el
# mensaje "prueba BAXY C6" ya fue enviado…» with nothing run): BAXY's last reply told an act it did not get done.
_TOLD_NOT_DONE = re.compile(
    r"\b(?:no\s+(?:pude|logre|llegue|consegui|alcance)|intente|couldn'?t|could\s+not|i\s+tried|didn'?t\s+manage)\b"
)


def go_ahead_with_nothing_pending(text: str, last_reply: str | None) -> bool:
    """M88: a go-ahead (``gives_go_ahead``) after a reply of BAXY's that asked nothing: nothing is waiting for that yes.
    After a question, the go-ahead answers it and is read as usual. Estabilización F3: a bare yes («sí», «dale», «ok»)
    after a reply that told an act not done is one too; after any other reply it is talk (agreeing with what was
    said)."""

    last = str(last_reply or "").rstrip()
    if last.endswith("?"):
        return False
    return gives_go_ahead(text) or (_says_yes(text) and _TOLD_NOT_DONE.search(_fold(last)) is not None)


# What a reply says to tell that nothing was done (folded): a negation of doing or having done. «No problem» and
# «sin problema» agree to something and are not one.
_NOT_DONE = re.compile(r"\b(?:no|not|nothing|nada|nunca|never|todavia|aun|yet)\b|n'?t\b")
_AGREEING_NO = re.compile(
    r"\b(?:no\s+(?:problem|worries|hay\s+problema|importa|pasa\s+nada|te\s+preocupes)|not\s+a\s+problem|sin\s+problemas?|"
    r"why\s+not|por\s+que\s+no)\b"
)


def says_nothing_was_done(reply: str) -> bool:
    """M88: the reply says, in some words, that something was not (yet) done — the only true answer to a go-ahead
    that nothing was waiting for, in a turn that ran nothing."""

    folded = _AGREEING_NO.sub(" ", _fold(reply))
    return _NOT_DONE.search(folded) is not None


# M109 (DEV-D v4d D-p24-t4 «Yes, do it for me.» → «I have not done it yet because the service asks to sign in on this PC
# first.», the M88 answer, refused by the App as ambiguous_without_question; the turn asked «What specific detail is
# missing…?» and the next go-ahead had nothing to go on): «do it» with no object is asked about, unless the reply says
# it is not done and why — the answer M88 asks for. Folded. Twin: UserMessagePolicy.SaysNotDoneAndWhy.
_NOT_DONE_YET = re.compile(
    r"\b(?:i\s+(?:have\s+not|haven['’]?t|did\s+not|didn['’]?t)\s+(?:yet\s+)?(?:done|do|did)\s+(?:it|that|this|anything)|"
    r"(?:todavia|aun)\s+no\s+(?:lo\s+|la\s+|eso\s+)?(?:he\s+hecho|hice)|no\s+(?:lo|la|eso)\s+(?:he\s+hecho|hice))\b"
)
_NOT_DONE_REASON = re.compile(r"(?::|;|\bporque\b|\bya\s+que\b|\bpues\b|\bbecause\b|\bsince\b)\s*\S")


def says_not_done_and_why(reply: str) -> bool:
    """The reply says the act asked is not done (yet) and gives why («I have not done it yet because…», «No lo he
    hecho: …») — see above."""

    folded = _fold(reply)
    found = _NOT_DONE_YET.search(folded)
    return found is not None and _NOT_DONE_REASON.search(folded[found.end():]) is not None


_CLITIC_TAIL = re.compile(r"(?:me|te|se|nos)?(?P<clitic>los|las|lo|la|les|le)$")
_LEADING_FILLER = re.compile(r"^(?:(?:y|e|ahora|pues|bueno|oye|che|baxy|por\s+favor|porfa)\b[\s,]*)+", re.IGNORECASE)
_TRAILING_VALUE = re.compile(
    r"\s+(?:(?:a|al|en|hasta|un|por|de|to|at)\s+)?\d{1,3}\s*(?:%|por\s*ciento|percent)?(?:\s.*)?$", re.IGNORECASE
)
_TRAILING_POLITE = re.compile(r"[\s,]*(?:por\s+favor|porfa|please|ya|ahora)?[\s.!?¿¡]*$", re.IGNORECASE)


# Talk that asks nothing (Fase 3.5, guard class of the owner's test and the held-out): the person
# tells something about themselves, reacts, or comments on BAXY. Three forms, read at the start
# of the message after fillers; the caller also requires that no order or request is read.
_TALK_FILLER = r"^(?:(?:bueno|pues|y|e|che|oye|mira|la\s+verdad|no\s+se|nose|uf+|ah+|ay|jaja\w*|jeje\w*|"
_TALK_FILLER += r"por\s+dios|dios\s+mio|obvio(?:\s+que)?|ok|okay|si|no)[\s,.!]+)*"
_FIRST_PERSON_TALK = re.compile(
    _TALK_FILLER
    + r"(?:me\s+(?:gusta|gustan|gusto|gustaba|encanta|encantan|encanto|siento|senti|parece|pasa|pone|cae|"
    r"aburre|preocupa|cuesta|duele)|estoy|estaba|estuve|yo\s+\w+|anoche|ayer|esta\s+manana|hoy\s+(?:tuve|fue|"
    r"estuve|me)|a\s+veces|creo\s+que|pienso\s+que|siento\s+que|solo\s+estaba|no\s+te\s+pedi|no\s+era\s+un\s+"
    r"pedido|tuve|fui|vi|i\s+(?:like|love|feel|felt|was|think|had|saw)|yesterday|last\s+night|today\s+i)\b"
)
_FEEDBACK_TALK = re.compile(
    r"\b(?:fall(?:o|os|as|aste|aron|a|an|ó)|errores|no\s+funcion\w*|no\s+sirve\w*|no\s+(?:lo\s+|me\s+)?entend\w*|mentiros\w*|odio|"
    r"no\s+lo\s+hiciste|te\s+dije|no\s+quiero\s+hablar|deberias?\s+poder|baxy\s+debe\w*|el\s+agente|"
    r"tus\s+detectores|tu\s+respuesta|que\s+respuesta|respuesta\s+(?:mas\s+)?rara|you\s+(?:didn'?t|never|"
    r"don'?t)\s+(?:understand|do|listen)|i\s+hate\s+(?:this|these|that))\b"
)
# MASSIVE news_query «ayer mediodía en el centro de palma por qué fue la protesta»: a time said first is not a
# story told; the question after it, with the question mark the ear dropped, is what is asked.
_EMBEDDED_QUESTION = re.compile(
    r"\b(?:por\s+que|quien|quienes|donde|cuando|cuanto|cuantos|que\s+(?:paso|ocurrio|sucedio))\s+"
    r"(?:fue|fueron|es|son|era|hubo|hay|habra|sera|paso|ocurrio|sucedio|gano|ganaron|murio|empezo|termina|"
    r"termino|esta|estan)\b|"
    # M123 (D58, reserva en8308 «yesterday at noontime in times square what was the protest about» → talk that made
    # up there was no protest, where the isolated decider looked it up): the same question in English.
    r"\b(?:what|why|who|where|when|how\s+(?:much|many))\s+(?:was|were|is|are|did|happened|will|won|died)\b"
)
_REACTION_TALK = re.compile(r"^(?:jaja\w*|jeje\w*|jsjs\w*|lol|xd+|wow|uf+|que\s+(?:raro|bueno|lindo|loco|risa))\b")
# Tanda 8 «i don't really know» was looked up on the web: not knowing, said alone, tells something about the person
# and asks nothing. Only the whole message: «no sé cómo abrir Spotify» or «no sé qué hora es» still ask.
_NOT_KNOWING_TALK = re.compile(
    r"(?:(?:la\s+verdad|honestamente|sinceramente|pues|bueno|mm+|hm+|eh+|well|honestly|actually)[\s,]+)?"
    r"(?:no\s+(?:lo\s+)?se|nose|ni\s+idea|no\s+tengo\s+(?:ni\s+)?(?:idea|la\s+menor\s+idea)|no\s+estoy\s+segur[oa]|"
    r"i\s+(?:really\s+)?(?:don'?t|do\s+not)\s+(?:really\s+)?know|idk|dunno|(?:i'?m\s+)?not\s+(?:really\s+)?sure|"
    r"(?:i\s+have\s+)?no\s+idea)"
    r"(?:[\s,]+(?:la\s+verdad|bien|todavia|aun|exactamente|really|yet|exactly|honestly|tbh))*"
)


def talk_act(text: str) -> str | None:
    """«statement», «feedback» or «reaction» when the message is talk in form; None otherwise.

    «me gusta crear cosas como tú», «anoche vi Oppenheimer y me gustó», «no te pedí nada, solo estaba
    pensando en voz alta» (statement); «odio estos fallos», «no lo hiciste, mentiroso», «tus detectores
    no funcionan» (feedback); «jajaja qué respuesta más rara» (reaction). A question is not talk here.
    """

    raw = str(text or "")
    folded = _fold(raw).strip(" .!")
    if not folded or "?" in raw or "¿" in raw or len(folded.split()) > 80 or _ASSENT.fullmatch(folded):
        return None
    if _REACTION_TALK.match(folded):
        return "reaction"
    if _FEEDBACK_TALK.search(folded):
        return "feedback"
    if (
        _FIRST_PERSON_TALK.match(folded) and not _EMBEDDED_QUESTION.search(folded)
    ) or _NOT_KNOWING_TALK.fullmatch(folded):
        return "statement"
    return None


def asked_about(antecedent: str) -> str | None:
    """The public work or named thing a question was about («¿La nueva peli de Resident Evil es buena?» →
    «nueva peli de Resident Evil»), in the person's words; None when the turn was not such a question.

    Fase 3.5 (dueño turn 59, «investigala» after that question): the pronoun's antecedent is that thing.
    """

    from .web import _entity_lookup_query, public_opinion_subject

    text = str(antecedent or "")
    return public_opinion_subject(text) or _entity_lookup_query(text)


# Uso real 2026-09-23 «quién es el presidente de chile» → «cuántos años tiene» →
# an age recited from memory: the question names nobody, so the person asked
# about just before is its subject, and the completed question is looked up.
_SUBJECTLESS_PERSON_FACT = re.compile(
    r"(?:(?:y|e|and|pero|but)\s+)?(?:"
    r"(?:cuantos\s+anos|que\s+edad)\s+tiene(?:\s+(?:el|ella|ahora|actualmente|hoy))?|"
    r"(?:how\s+old|what\s+age)\s+is\s+(?:he|she|they|him|her)(?:\s+now)?|"
    r"how\s+old(?:\s+(?:is\s+)?(?:he|she))?"
    r")"
)


def subject_completed(text: str, antecedent: str) -> str | None:
    """«cuántos años tiene» after «¿quién es el presidente de Chile?» → «cuántos años tiene el
    presidente de Chile»; the subject is the public person the antecedent asked about, in the
    person's words. None when the antecedent asked about no such person."""

    from .web import person_fact_subject

    subject = person_fact_subject(antecedent) or asked_about(antecedent)
    if not subject:
        return None
    folded = _fold(text).strip(" ¿?¡!.,")
    folded = re.sub(r"^(?:(?:y|e|and|pero|but)\s+)", "", folded)
    if folded.startswith(("how", "what")):
        return f"how old is {subject}"
    return f"cuántos años tiene {subject}"


def antecedent_object(antecedent: str) -> str | None:
    """The object of the previous order, in the person's words: «silencia mi micrófono» → «mi micrófono»,
    «pon el volumen a 20» → «el volumen». None when the antecedent is not a short order."""

    asked = asked_about(antecedent)
    if asked:
        return asked
    text = _LEADING_FILLER.sub("", " ".join(str(antecedent or "").split())).strip(" ¿?¡!.,")
    words = text.split()
    if len(words) < 2 or len(words) > 10 or "?" in str(antecedent):
        return None
    rest = _TRAILING_POLITE.sub("", _TRAILING_VALUE.sub("", " ".join(words[1:]))).strip(" ,.")
    return rest if rest and len(rest.split()) <= 6 else None


def substituted_reference(text: str, antecedent: str) -> str | None:
    """«activalo» after «silencia mi micrófono» → «activa mi micrófono»: the object left out is the antecedent's."""

    return with_object(text, antecedent_object(antecedent))


# M84 (DEV-D v3o D-p01-t3 «no, cancel» after «show christmas list» → «I do not cancel: canceling a list is not something
# I do.»; D-p14-t3 «Cancelar foto» after BAXY said it takes no slow-motion photos → «No cancelo la foto.»): taking back
# what was just asked is said to BAXY, whole («no, cancel», «olvídalo») or naming only what that request named.
_TAKE_BACK = re.compile(
    r"^(?:(?:no|nop|nah|mejor|bueno|ok|okay|oh)[\s,.!]+)*(?:cancela|cancelala|cancelalo|cancelar|cancel|anula|anular|"
    r"olvida|olvidate\s+de|olvidalo|forget(?:\s+about)?|never\s*mind|nevermind|deja|dejalo|dejala)"
    r"(?:\s+(?:el|la|los|las|lo|mi|the|my|that|this|it|eso|esa|ese))?(?:\s+(?P<object>[a-z]+(?:\s+[a-z]+){0,2}))?"
    r"[\s.!]*$"
)


def takes_back(text: str, antecedent: str | None) -> bool:
    """The whole message takes back the request before it (see above): a bare refusal, or a cancellation whose object
    words were all said in that request."""

    folded = _fold(text).strip(" ¿?¡!.,")
    if not folded or not antecedent:
        return False
    if _REFUSAL.fullmatch(folded):
        return True
    found = _TAKE_BACK.fullmatch(folded)
    if found is None:
        return False
    named = [word for word in _words(found.group("object") or "") if word not in _STOPWORDS]
    said = {word[:4] for word in _words(antecedent)}
    return all(word[:4] in said for word in named)


def place_substituted(text: str, antecedent: str | None) -> str | None:
    """M84 (DEV-D v3o D-w02-t2 «y si allá son las 10 de la mañana acá qué hora es» after «qué hora es en madrid» → a
    reply that failed): «allá», «there» is the place whose time the request before asked; it is said by its name
    («… si en Madrid son las 10 …»), in the person's words. None without that place."""

    from .temporal import clock_elsewhere

    if not antecedent:
        return None
    asked = clock_elsewhere(_fold(antecedent))
    said = " ".join(str(text or "").split())
    folded = _fold(said)
    found = _PLACE_ANAPHOR.search(folded)
    if asked is None or found is None or len(folded) != len(said) or len(_PLACE_ANAPHOR.findall(folded)) != 1:
        return None
    before = folded[: found.start()].split()
    preposition = "" if before and before[-1] in {"en", "in", "at", "de", "from"} else (
        "en " if spanish(said) else "in "
    )
    place = asked.said.title() if asked.said == asked.place else asked.said
    return said[: found.start()] + preposition + place + said[found.end():]


# How much, how long or how politely an order is said, never what it acts on («seguí un rato», «pause it now»).
_ORDER_TAIL = _DEGREE | frozenset(
    "un una ya ahora de nuevo otra vez porfa por favor please pls now again a bit for sec second moment nomas mas more "
    "rapido it".split()
)


def _bare_order(folded: str) -> bool:
    """An order the readers know said with no object, at most how much or how long: «seguí», «pausa un toque»,
    «pause it», «resume it now» (tanda 9: «dale, seguí» after a video was read alone and not understood)."""

    words = folded.split()
    return (
        0 < len(words) <= 5
        and _ENCLITIC.fullmatch(words[0]) is None
        and _head_is(words[0], _COVERAGE_ACTION_HEAD)
        and all(word in _ORDER_TAIL for word in words[1:])
    )


# What the last turn acted on, named as the readers name it, for an order that leaves it out right after (tanda 9:
# «pausalo un toque», «dale, seguí» after a video). What plays is a song or a video.
_THINGS_ACTED_ON = {"media": (("la canción", "el video"), ("the song", "the video"))}


def things_acted_on(operations: tuple[str, ...], in_spanish: bool) -> tuple[str, ...]:
    """The names of what ``operations`` acted on, the person's language first."""

    names: list[str] = []
    for family in dict.fromkeys(_family(op) for op in operations):
        spanish_names, english_names = _THINGS_ACTED_ON.get(family, ((), ()))
        names += [*spanish_names, *english_names] if in_spanish else [*english_names, *spanish_names]
    return tuple(names)


def with_object(text: str, obj: str | None) -> str | None:
    """The message with the object it leaves out said: the direct-object clitic fused to the verb is replaced by it
    («activalo» → «activa mi micrófono»), or it follows an order said without one («dale, seguí» → «seguí la
    canción», «pause it» → «pause the song»). «le» (indirect) is left to the model."""

    if not obj:
        return None
    words = str(text).split()
    for index, word in enumerate(words):
        bare = word.strip(" ¿?¡!.,")
        if not (_ENCLITIC.fullmatch(_fold(bare)) or _SHORT_IMPERATIVE_CLITIC.fullmatch(_fold(bare))):
            continue
        tail = _CLITIC_TAIL.search(_fold(bare))
        if tail is None or tail.group("clitic") in {"le", "les"}:
            return None
        verb = bare[: len(bare) - len(tail.group(0))]
        joined = " ".join([*words[:index], verb, obj, *words[index + 1:]]).strip(" .!?")
        # «pues investigala…» → «investiga …»: a talk filler is not part of the request («ahora» is).
        return re.sub(r"^(?:(?:pues|bueno|oye|che)\b[\s,]*)+", "", joined, flags=re.IGNORECASE).strip() or joined
    said = followup(text)
    if not _bare_order(said.folded):
        return None
    head, *rest = said.said.split()
    return " ".join([head, obj, *(word for word in rest if _fold(word) != "it")])


def asks_to_look_up(text: str) -> bool:
    """A lookup verb («investigala», «averiguá…»): its referent is a topic, not an object."""
    return _RESEARCH_VERB.search(_fold(text)) is not None


# ------------------------------------------------------------------ the follow-up and the dialogue state
#
# Tanda 7 (2026-09-25) and the owner's method of the same day (artifacts/comprobaciones/C03/
# PROPUESTA_METODO_COMPRENSION_2026-09-25.md). Half of real use is a conversation where each message leans on
# the one before: «¿y el finde?», «¿y en Mar del Plata?», «a qué hora sale el sol allá el sábado», «actually make
# it 9», «esa no, otra más movida», «cómo se llama esta?», «y quién fue el top scorer», «escríbeme un tweet sobre
# eso», «is the entrance free». Each was read alone and lost what it continued.
#
# Two pieces, and no reading of any one phrase:
# - The dialogue state: the last turn's request (whatever came of it: tanda 8) and the last thing of each kind this
#   conversation verified — the place a weather read reported and the day it was asked for, what the player says
#   is playing, the alarm and the reminder created (with the alarm's id), the topic searched, the level set. Only
#   verified results write the facts, never BAXY's text; BAXY's last reply reaches the rewrite as the conversation
#   the person saw (a number it computed, a place it named).
# - The trigger, by form: a connector or a correction first («y», «and», «actually», «mejor», «no, …»), a bare
#   part with no verb of its own (a day, a place, an amount, «otra»), a place or a thing said as «allá», «esta»,
#   «eso», «it», a question with no object («what have I got set?»), or a short question about something already
#   named. A complete new request never triggers.
# The model rewrites the message with the state and the previous turns (``llm.rewrite_in_context``); the rewrite
# keeps the existing check (only words the person, BAXY or the verified state said) and the readers must read it
# in the family of what it continues, or read no effect at all.

_CONTINUATION = re.compile(
    r"^(?:(?:y|e|and|pero|but|entonces|so|tambien|ademas|also|plus|(?:and\s+)?(?:what|how)\s+about|y\s+que\s+tal|"
    r"que\s+tal)\b[\s,.:]*)+"
)
# An address or a filler before anything («che, ¿va a llover hoy?», «ok, y en Rosario»): dropped, it continues
# nothing by itself. Tanda 9: an agreement said before a pause is a filler too («dale, seguí», «órale, y …»).
_FILLER = re.compile(
    r"^(?:(?:oye|che|bueno|ok|okay|okey|ah|oh|mira|hey|listen|baxy|(?:dale|orale|sale|va|vale|listo)(?=\s*,))\b"
    r"[\s,.:]*)+"
)
_CORRECTION = re.compile(
    r"^(?:(?:no|nop|nope|nah|mejor|actually|en\s+realidad|perdon|digo|o\s+sea|wait|espera|sorry|rather|instead|"
    # «que no, el lápiz»: a denial insisted on before a pause («que no se te olvide» asks something else).
    r"mas\s+bien|que\s+no(?=\s*[,.!;:]))\b[\s,.:]*)+"
)
# Uso real 2026-10-07 «si pero quiero buscar un top 3», «ok pero lo puedes buscar en google…» after the search: an
# agreement with «pero/but» right after it takes back part of what was just given; it corrects the last result, it
# does not add to it.
_ADVERSATIVE_CORRECTION = re.compile(
    r"^(?:si+|sip|ok|okay|okey|ya|vale|dale|bueno|claro|yes|yeah|yep|sure|right)\b[\s,.:]*(?:pero|but)\b[\s,.:]*"
)
# «y otro de 20», «and at 8 too», «ok pero además una a las 9»: adding to what was done, not instead of it.
_ADDITIVE = re.compile(r"\b(?:otro|otra|another|also|too|tambien|ademas|second|segundo|segunda)\b")
_COURTESY_TAIL = re.compile(r"(?:[\s,]+(?:mejor|entonces|then|instead|porfa|por\s+favor|please|pls))+$")
_EDGE = " ¿?¡!.,;:"
_UNIT = (
    r"(?:minutos?|minutes?|mins?|segundos?|seconds?|secs?|horas?|hours?|hrs?|%|por\s*ciento|percent|puntos|points)"
)
# «make it 9», «que sean 9», «cámbialo a 9», «unos 15», «9 minutes».
_CHANGE = (
    r"(?:(?:make|set|put|change|turn)\s+(?:it|that)(?:\s+(?:to|at|for|into))?|que\s+sean?(?:\s+de)?|"
    r"(?:hazlo|hacelo|ponlo|ponelo|ponle|dejalo|cambialo|cambiale|cambia)(?:\s+(?:a|de|en|con))?)"
)
_NUMBER = rf"(?:\d{{1,3}}|{alternation(frozenset(_NUMBER_WORDS))})"
_AMOUNT_FRAGMENT = re.compile(
    rf"^(?:{_CHANGE}\s+)?(?:(?:a|al|en|de|to|at|for|by|unos|unas|como|about|around|like)\s+)*{_NUMBER}(?:\s*{_UNIT})?$"
)
_WEEKDAY = r"(?:lunes|martes|miercoles|jueves|viernes|sabado|domingo|monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
_DAY = (
    r"(?:(?:el|este|the|this|next|on|para|pa|for|el\s+proximo|la\s+proxima|este\s+proximo)\s+)*"
    r"(?:pasado\s+manana|manana|hoy|ayer|anoche|anteayer|esta\s+(?:noche|tarde)|fin\s+de\s+semana|finde|"
    rf"semana\s+(?:que\s+viene|proxima)|today|tonight|tomorrow|yesterday|last\s+night|weekend|week|{_WEEKDAY})"
)
# «a las 6 y cuarto», «a las 7 y media», «a las 8 y 20»: the minutes said in words are part of the hour. Tanda 9
# «It will be for 3:30 pm», «afternoon 3:45»: an hour with no preposition is a clock by its own form (its minutes or
# am/pm), and the part of the day may come first.
_CLOCK_PREFIX = r"(?:a\s+las?|at|para\s+las?|by|around|como\s+a\s+las?)"
_AM_PM = r"(?:am|pm|a\.?\s?m\.?|p\.?\s?m\.?)"
_CLOCK_HOUR = (
    rf"(?:{_CLOCK_PREFIX}\s+\d{{1,2}}(?::\d{{2}}|\s+y\s+(?:cuarto|media|\d{{1,2}}))?|"
    rf"(?:(?:for|to)\s+)?\d{{1,2}}(?::\d{{2}}|(?=\s*{_AM_PM}(?![a-z]))))"
)
_CLOCK_PERIOD = (
    rf"\s*(?:{_AM_PM}|hs|horas|de\s+la\s+(?:manana|tarde|noche)|in\s+the\s+(?:morning|afternoon|evening))"
)
_PART_OF_DAY_FIRST = (
    r"(?:(?:(?:in\s+the|de\s+la|por\s+la)\s+)?(?:morning|afternoon|evening|night|tarde|noche)|(?:de\s+la|por\s+la)\s+manana)"
)
_CLOCK = rf"(?:{_PART_OF_DAY_FIRST}\s+)?{_CLOCK_HOUR}(?:{_CLOCK_PERIOD})?"
# «it will be for 3:30 pm», «it should be 9», «que sea a las 5», «debería ser mañana»: a copula before a value only
# says the value.
_VALUE_FRAME = re.compile(
    r"^(?:(?:it|that|this)\s+(?:(?:will|would|should|must|could|can)\s+)?be|it'?ll\s+be|it'?s|that'?s|"
    r"(?:que\s+)?sean?|sera|seria|(?:deberia|debe|tiene\s+que)\s+ser)\s+"
)
_TIME_FRAGMENT = re.compile(rf"^(?:{_DAY}|{_CLOCK})(?:\s+(?:y|and|o|or)\s+(?:{_DAY}|{_CLOCK}))?$")
_PLACE_FRAGMENT = re.compile(rf"^(?:en|in|at|para|for|on|por|desde|from)\s+{_NOT_ASKED}\S.*$")
# A place said as «allá» or «there»; «is there…», «there are…» only say that something exists.
_PLACE_ANAPHOR = re.compile(
    r"\b(?:alla|alli|aya|ahi)\b|(?<!is )(?<!are )(?<!was )(?<!were )(?<!be )\b(?:over\s+)?there\b"
    r"(?!\s+(?:is|are|was|were|will|be|'s)\b)"
)
# Ronda 20 P3 (pasada r18, v3-11 t2 «escribe ahí: comprar pan, leche y huevos» after «en onenote crea una pagina
# nueva» failed): a place said back to what the turn before was to leave — «ahí», «allá», «there», «en ella», «in it».
_PLACE_SAID_BACK = re.compile(
    r"\b(?:en|dentro\s+de|in|into|inside)\s+(?:ella|ellas|esa|esas|aquella|it)\b"
)


def points_back_to_a_place(text: str) -> bool:
    """Whether the message puts what it asks in a place it only points back to («escribe ahí: X», «ponelo en ella»,
    «type it in there»), never one it names («escribí hola en el Bloc de notas»)."""

    folded = _PLACE_FILLER.sub(" ", _fold(str(text or "")))
    return bool(_PLACE_ANAPHOR.search(folded) or _PLACE_SAID_BACK.search(folded))


def only_place_filler(text: str) -> bool:
    """Revisión 2 (hallazgo 2): whether a clause says nothing once its spoken «ahí» fillers are off («déjalo ahí»,
    «por ahí»): such a clause names no place a later «ahí» could point to."""

    return not re.search(r"\w", _PLACE_FILLER.sub(" ", _fold(str(text or ""))))


# Ronda 20 P3, revisión 1 (hallazgo 3): «ahí va», «ahí vamos», «ahí nomás» are a spoken filler, no place pointed to
# («ahí va, ahora cerrá spotify»). Revisión 2 (hallazgo 2a): so are the idioms a person says right after a failure —
# «déjalo ahí» (drop it), «por ahí» (somewhere, maybe), «hasta ahí» (that far) — and «ahí mismo» heading the message
# («ahí mismo escribí hola»: right away); after its verb («escribilo ahí mismo») it is a place («right there»). Folded.
_PLACE_FILLER = re.compile(
    r"\b(?:ahi|alli)\s+(?:va|vamos|nomas|noma)\b|\bdej\w*\s+(?:ahi|alli)\b|\b(?:por|hasta)\s+(?:ahi|alli)\b|"
    r"^[\s\W]*(?:(?:y|bueno|ok|entonces)\b[\s\W]*)?(?:ahi|alli)\s+mismo\b"
)


# «esa no, otra más movida», «another one», «not that one».
_ANOTHER_FRAGMENT = re.compile(
    r"^(?:(?:esa|esta|ese|este|eso|that|this)(?:\s+(?:one|cancion|song|tema|track))?\s+no\b|not\s+(?:that|this)\b|"
    r"(?:(?:pon(?:me|e|eme)?|pone|play|dame|give\s+me|quiero|i\s+want)\s+)?(?:otra|otro|another|something\s+else|"
    r"una\s+(?:distinta|diferente)|a\s+different\s+one))"
)
# «más», «un poco más», «otra vez», «again»: the last request once more (tanda 9 «más» after lowering the volume).
_AGAIN_FRAGMENT = re.compile(
    r"(?:(?:un\s+(?:poco|poquito|toque)|a\s+(?:bit|little)|algo)\s+)?(?:mas|more)|otro\s+poco|otra\s+vez|de\s+nuevo|"
    r"again|once\s+more|one\s+more\s+time"
)
# The thing just acted on or named, said as a demonstrative with no noun: «cómo se llama esta», «what's this
# called», «sobre eso».
_DEMONSTRATIVE = re.compile(
    r"\b(?:esta|este|esto|esa|ese|eso|aquello|this|that|it)(?:\s+one)?(?:\s+(?:called|se\s+llama))?$"
)
_QUESTION_WORD = re.compile(
    r"^(?:quien|quienes|que|cual|cuales|cuando|donde|como|cuanto|cuanta|cuantos|cuantas|por\s+que|who|whose|what|"
    r"which|when|where|why|how)\b"
)
# «is the entrance free», «¿está abierto el museo?»: a yes/no question about a thing already known.
_DEFINITE_QUESTION = re.compile(
    r"^(?:is|are|was|were|does|do|did|will|can|es|son|era|fue|esta|estan|hay|habra|sera|cuesta|cuestan)\s+"
    r"(?:the|it|they|this|that|el|la|los|las|eso|esto|ella|ellos)\b"
)
_ANAPHORIC_PRONOUN = re.compile(r"\b(?:it|its|they|them|their|he|she|him|his|her|ella|ellos|ellas|eso|esa|ese)\b")
# «what have I got set», «qué tengo programado», «¿qué llevo ya?» (tanda 8, after a shopping list): what the person
# has or holds, asked with no object named — the whole question is the verb and when.
_OWN_LISTING = re.compile(
    r"^(?:what|which|que|cuales|cuantos|cuantas|cuanto|cuanta)\s+(?:(?:have|do|did)\s+(?:i|we)(?:\s+(?:got|have))?|"
    r"(?:me\s+|nos\s+)?(?:tengo|tenemos|hay|quedan?|faltan?|llevo|llevamos|[a-zñ]{3,}o))"
    r"(?:\s+(?:set|scheduled|pending|programad[oa]s?|puest[oa]s?|pendientes?|activ[oa]s?|active|on|going|ya|"
    r"ahora|todavia|aun|hasta\s+ahora|already|so\s+far|right\s+now|now|en\s+total|in\s+total))*"
)
_SPANISH_WORD = re.compile(
    r"\b(?:que|quien|quienes|cual|cuales|como|donde|cuando|cuanto|el|la|los|las|es|fue|son|de|del|y|un|una|esta|"
    r"este|esa|ese|eso|otra|otro|mas|cancion|pon|ponme|sobre|para|tengo|hay|se|mejor|sean|hoy|manana)\b"
)
_SCHEDULED_NOUN = re.compile(r"\b(?:temporizador|alarma|aviso|timer|alarm)\b")


@dataclass(frozen=True)
class Followup:
    """A message split into the connector or correction it starts with and what it says after it."""

    said: str  # the person's words after the lead, edges and trailing courtesy trimmed
    folded: str  # the same, folded (same length)
    continued: bool  # «y», «and», «what about»
    corrected: bool  # «no», «mejor», «actually»

    @property
    def fragment(self) -> bool:
        """A bare part with no verb of its own: an amount, a day or an hour, a place, another item."""

        folded = self.folded
        return bool(
            _AMOUNT_FRAGMENT.fullmatch(folded)
            or _TIME_FRAGMENT.fullmatch(folded)
            or (_PLACE_FRAGMENT.fullmatch(folded) and len(folded.split()) <= 5)
            or _ANOTHER_FRAGMENT.match(folded)
            or _AGAIN_FRAGMENT.fullmatch(folded)
        )

    @property
    def value(self) -> bool:
        """Only a value: an amount, a day or an hour («for 3:30 pm», «9 minutes», «mañana»)."""

        return bool(_AMOUNT_FRAGMENT.fullmatch(self.folded) or _TIME_FRAGMENT.fullmatch(self.folded))

    @property
    def replaces_last(self) -> bool:
        """It corrects what was just done («actually make it 9», «no, a las 8», «mejor 30», a bare «9»),
        rather than adding to it («y otro de 20», «and at 8 too»)."""

        if _AGAIN_FRAGMENT.fullmatch(self.folded):
            return False  # «otra vez», «más»: once more, not instead
        corrects = self.corrected or re.match(_CHANGE, self.folded) is not None or not self.continued
        return corrects and _ADDITIVE.search(self.folded) is None


def _trimmed(said: str, folded: str) -> tuple[str, str]:
    start = len(folded) - len(folded.lstrip(_EDGE))
    end = len(folded.rstrip(_EDGE))
    return said[start:end], folded[start:end]


def followup(text: str) -> Followup:
    """«¿y en Mar del Plata?» → «en Mar del Plata», continued; «actually make it 9» → «make it 9», corrected."""

    said = " ".join(str(text or "").split())
    folded = _fold(said)
    if len(folded) != len(said):
        said = folded
    said, folded = _trimmed(said, folded)
    continued = corrected = False
    while folded:
        found = _ADVERSATIVE_CORRECTION.match(folded)
        if found is not None and found.end():
            # Revisión 2026-10-07 «ok pero además una a las 9»: «pero» before an addition adds, it does not correct
            # (the connector «además» is trimmed next, so it is looked for here).
            if _ADDITIVE.search(folded[found.end():]) is not None:
                continued = True
            else:
                corrected = True
            said, folded = _trimmed(said[found.end():], folded[found.end():])
            continue
        found = _FILLER.match(folded)
        if found is None or not found.end():
            found = _CONTINUATION.match(folded)
            if found is not None and found.end():
                continued = True
            else:
                found = _CORRECTION.match(folded)
                if found is None or not found.end():
                    break
                corrected = True
        said, folded = _trimmed(said[found.end():], folded[found.end():])
    tail = _COURTESY_TAIL.search(folded)
    if tail is not None:
        said, folded = _trimmed(said[: tail.start()], folded[: tail.start()])
    frame = _VALUE_FRAME.match(folded)
    if frame is not None and (
        _TIME_FRAGMENT.fullmatch(folded[frame.end():]) or _AMOUNT_FRAGMENT.fullmatch(folded[frame.end():])
    ):
        said, folded = said[frame.end():], folded[frame.end():]
    return Followup(said, folded, continued, corrected)


def refers_back(text: str) -> bool:
    """A place or a thing said as «allá», «esta», «eso», «it», or a value as «ese tiempo», «that long»."""

    folded = followup(text).folded
    return bool(_PLACE_ANAPHOR.search(folded) or _DEMONSTRATIVE.search(folded) or _VALUE_POINTER.search(folded))


# Tanda 9 «ponme un timer de ese tiempo» after BAXY said how long to boil something was asked «¿Cuál es la hora
# exacta?»: a value pointed at with a demonstrative («ese tiempo», «esa cantidad», «that long», «that amount») is the
# one BAXY's last answer gave. A time noun takes a duration; a level or a percentage takes a percent.
_VALUE_POINTER = re.compile(
    r"\b(?:(?:ese|esa|este|esta|that|this|the\s+same)\s+(?:(?P<time>tiempo|rato|duracion|time|duration)|"
    r"(?P<share>porcentaje|nivel|percentage|level)|cantidad|numero|valor|monto|amount|number|value)|"
    r"(?:that|this)\s+(?:(?P<long>long)|much|many))\b"
)
_TIME_UNIT = re.compile(r"(?:minutos?|minutes?|mins?|segundos?|seconds?|secs?|horas?|hours?|hrs?)$")
# A number with its unit, in digits as BAXY writes them; a range («8 a 10 minutos») names no one value.
_REPLY_AMOUNT = re.compile(rf"(?<![\d.,])(?P<number>\d{{1,3}}(?:[.,]\d+)?)(?P<unit>\s*{_UNIT})(?![a-z])")
_RANGE_BEFORE = re.compile(r"\d\s*(?:-|–|a|y|o|to|or|and)\s*$")
# A number with no unit, or none of another kind (°C, grados, km): «180 °C» is a temperature, «12» alone may be a time.
_BARE_NUMBER = re.compile(r"(?<![\d.,])\d{1,3}(?:[.,]\d+)?(?!\s*(?:°|º|grados|degrees|km|kg|g\b|ml|cm|[\d.,]))")


def value_from_reply(text: str, reply: str | None) -> str | None:
    """«ponme un timer de ese tiempo» after «… durante 35 minutos …» → «ponme un timer de 35 minutos»; None unless
    BAXY's last answer gave exactly one value of the kind pointed at."""

    said = " ".join(str(text or "").split())
    folded = _fold(said)
    pointer = _VALUE_POINTER.search(folded)
    if pointer is None or not reply or len(folded) != len(said):
        return None
    answer = " ".join(str(reply).split())
    folded_answer = _fold(answer)
    if len(folded_answer) != len(answer):
        answer = folded_answer
    if _BARE_NUMBER.search(_REPLY_AMOUNT.sub(" ", folded_answer)):
        return None  # «8 minutos si son chicos, 12 si son grandes»: another value said without its unit
    values = set()
    for found in _REPLY_AMOUNT.finditer(folded_answer):
        unit = found.group("unit").strip()
        if (pointer.group("time") or pointer.group("long")) and not _TIME_UNIT.match(unit):
            continue
        if pointer.group("share") and unit not in {"%", "por ciento", "porciento", "percent"}:
            continue
        if _RANGE_BEFORE.search(folded_answer[: found.start()]):
            return None
        values.add(answer[found.start(): found.end()].strip())
    if len(values) != 1:
        return None
    return said[: pointer.start()] + values.pop() + said[pointer.end():]


# --- What a reminder points at with «eso» -------------------------------------------
# M148 (DEV-F v4q F-w48-t4 «órale, pues recuérdame eso el domingo a las 3 de la tarde» after «El domingo en Zapopan: 23
# °C… en la tarde; mejor lleva paraguas.» → titled «Voy a estar en Zapopan el domingo.», another thing the person had
# said; DEV-D v4q D-w07-t4 «va, ahorita ponle un recordatorio el viernes a las 5 de la tarde que le devuelva eso a mi
# carnal» after «Redondeado hacia arriba, 265.» → titled «Devolverle eso a mi amigo.»; the isolated decider got neither):
# «eso» in a reminder is what the conversation last gave to do or to keep. When the whole reminder is «eso»
# («recuérdame eso», «recuérdamelo», «remind me about that»), it is the one thing BAXY's last reply advised doing; when
# «eso» is what something is done with («que le devuelva eso»), it is the one figure BAXY's last reply gave as its
# answer. The words of the reminder stay the decider's or the readers'; only what it points at is said.
_ADVICE = re.compile(
    r"(?:^|[.;:!?,]\s*|\b(?:y|asi\s+que|so|and)\s+)(?:(?:te\s+)?(?:conviene|recomiendo|sugiero)|mejor|no\s+olvides|"
    r"no\s+te\s+olvides\s+de|acuerdate\s+de|deberias|tendrias\s+que|(?:you'?d\s+)?better|"
    r"you\s+(?:should|might\s+want\s+to|may\s+want\s+to)|i'?d\s+(?:recommend|suggest)|i\s+(?:recommend|suggest)|"
    r"don'?t\s+forget\s+(?:to\s+)?|remember\s+to|make\s+sure\s+(?:to|you))\s+(?P<action>[a-z][^.;:!?,]*)"
)
# The order to remind, with «eso» or its clitic as all it is about.
_POINTED_REMINDER = re.compile(
    r"\b(?:(?:recuerd(?:a|ame|eme)|record(?:a|ame)|acord(?:ate|ame)|avis(?:a|ame))(?:\s+(?:de|con))?\s+"
    r"(?:eso|esto|aquello)|recuerd(?:amelo|amela|emelo)|record(?:amelo|amela)|acordamelo|avisamelo|"
    r"(?:recordatorio|aviso|alarma)\s+(?:de|para|con|sobre)\s+(?:eso|esto)|"
    r"(?:remind|ping)\s+me(?:\s+(?:of|about))?\s+(?:that|this|it)|"
    r"(?:reminder|alarm)\s+(?:for|about|of)\s+(?:that|this|it))\b"
)
# What may surround that order and say only when, how or to whom («órale, pues», «el domingo a las 3 de la tarde»).
_AROUND_A_POINTED_REMINDER = frozenset(
    """
    orale pues ok okay okey vale bueno dale va oye baxy porfa por favor please pls then entonces y and el la las los a
    al at on for para pa en in de del the this este esta ese esa hoy manana tomorrow today tonight tarde noche
    morning afternoon evening night ahorita luego later si yes yeah sure tambien also too ponme pon ponle set me un
    una a an same mismo misma hora time
    """.split()
)
# «eso» as what something is done with, in a reminder that says what is done; in English, what is paid, given, sent
# or returned («pay him that back»): «that» alone opens a clause as often as it points.
_POINTED_OBJECT = re.compile(
    r"\b(?:eso|esto|aquello)\b|\b(?:pay|give|send|return|transfer|lend|owe)\s+(?:(?:him|her|them|my\s+\w+|\w+)\s+)?"
    r"(?:that|it|this)\b"
)
_REMINDER_ORDER = re.compile(
    r"\b(?:recuerd\w*|record\w*|acord\w*|avis\w*|recordatorios?|remind(?:er)?s?|alarmas?|alarms?)\b"
)
_TITLE_POINTER = re.compile(r"\b(?:eso|esto|aquello|algo|that|this|it|something)\b")
_REPLY_FIGURE = re.compile(
    r"(?<![\d.,:])(?P<number>\d+(?:[.,]\d+)?)(?![\d:])(?P<unit>(?:\s+mil)?\s*(?:%|€|\$|(?:euros?|dolares|dollars|"
    r"pesos|soles|libras|pounds|bucks|lucas)\b)|\s+mil\b)?"
)


def advised_action(reply: str | None) -> str | None:
    """The one thing BAXY's ``reply`` advised doing, as written («mejor lleva paraguas» → «lleva paraguas», «you might
    want to bring an umbrella» → «bring an umbrella»); None with no advice or more than one."""

    said = " ".join(str(reply or "").split())
    folded = _fold(said)
    if len(folded) != len(said):
        said = folded
    found = [match for match in _ADVICE.finditer(folded) if len(match.group("action").split()) <= 8]
    if len(found) != 1:
        return None
    return said[found[0].start("action"):found[0].end("action")].strip()


def _reply_figure(reply: str, said_before: Iterable[str]) -> str | None:
    """The one number of a short ``reply`` nobody said before (its unit with it), when it says no clock."""

    answer = " ".join(str(reply or "").split())
    folded = _fold(answer)
    if len(folded) != len(answer):
        answer = folded
    if len(folded.split()) > 12 or spoken_clocks(folded):
        return None
    said = {
        found.group("number").replace(",", ".") for line in said_before for found in _REPLY_FIGURE.finditer(_fold(line))
    }
    new = {
        answer[found.start():found.end()].strip()
        for found in _REPLY_FIGURE.finditer(folded)
        if found.group("number").replace(",", ".") not in said
    }
    return new.pop() if len(new) == 1 else None


def _without_moment(folded: str) -> str:
    """``folded`` with its clocks, days and lengths taken out."""

    for clock in spoken_clocks(folded):
        folded = folded.replace(clock.literal, " ")
    return re.sub(rf"\b(?:{_DAY}|{_RELATIVE_DURATION_PATTERN})\b", " ", folded)


def _all_pointed(folded: str) -> bool:
    """The reminder is all «eso»: the order to remind of what is pointed at, and around it only when, how or to whom."""

    pointed = _POINTED_REMINDER.search(folded)
    if pointed is None:
        return False
    rest = _without_moment(folded[: pointed.start()] + " " + folded[pointed.end():])
    return all(word in _AROUND_A_POINTED_REMINDER for word in _WORD.findall(rest))


# M165 (DEV-F v4y F-w48-t4 «órale, pues recuérdame eso el domingo a las 3 de la tarde» after a forecast that failed →
# titled «Recuérdame el domingo a las 3 de la tarde.»; DEV-G v4y G-w19-t4, where the decider's «Recuérdame en 5:40 de
# la tarde.» stood over «recuérdame salir a las 17:40»): an order to remind or to ring and its moment, with nothing it
# is for, says no title. The words such an order is made of, beside those around a pointed reminder.
_REMINDER_ORDER_ONLY = frozenset(
    """
    recuerdame recuerda recordame recorda recuerdamelo recordamelo recuerdamela avisame avisa avisamelo acuerdame
    acordame acordamelo recordar avisar remind reminder reminders recordatorio recordatorios aviso alarma alarmas alarm
    alarms ping eso esto aquello that this it lo pone poneme crea creame programa programame haz hazme add create make
    about sobre que to enero febrero marzo abril mayo junio julio agosto septiembre setiembre octubre noviembre
    diciembre january february march april may june july august september october november december
    """.split()
)


def says_no_reminder_title(text: str) -> bool:
    """``text`` (a title, or a request) says only an order to remind or ring and when it rings: «Recuérdame el domingo
    a las 3 de la tarde.», «Recuérdame en 5:40 de la tarde.», «Remind me»; never what it is for."""

    words = _WORD.findall(_without_moment(_fold(" ".join(str(text or "").split()))))
    return all(word.isdecimal() or word in _AROUND_A_POINTED_REMINDER or word in _REMINDER_ORDER_ONLY for word in words)


def pointed_reminder_unsaid(text: str, reply: str | None, title: str) -> bool:
    """M165: the reminder ``text`` is all «eso», BAXY's last ``reply`` advised nothing it could point at, and the
    ``title`` read for it says only the order and its moment: what it is for is to be asked, never the order repeated
    as its title."""

    return _all_pointed(_fold(" ".join(str(text or "").split()))) and advised_action(reply) is None and (
        says_no_reminder_title(title)
    )


def pointed_reminder_title(
    text: str, reply: str | None, title: str, said_before: Iterable[str] = (),
) -> str | None:
    """The reminder's ``title`` with what ``text`` points at said (see above), or None when it already says it, the
    message points at nothing, or the conversation gives no one thing it points at."""

    folded = _fold(" ".join(str(text or "").split()))
    folded_title = _fold(title)
    if _all_pointed(folded):
        action = advised_action(reply)
        if action is None:
            return None
        words = [word for word in _WORD.findall(_fold(action)) if len(word) >= 4 and word not in _STOPWORDS]
        content = words[1:] or words
        if content and any(re.search(rf"\b{re.escape(word[:5])}", folded_title) for word in content):
            return None
        return action
    if not _REMINDER_ORDER.search(folded) or not _POINTED_OBJECT.search(folded):
        return None
    figure = _reply_figure(reply or "", [text, *said_before])
    pointers = list(_TITLE_POINTER.finditer(folded_title))
    if (
        figure is None
        or re.search(rf"(?<![\d.,]){re.escape(_fold(figure))}", folded_title)
        or len(pointers) != 1
        or len(folded_title) != len(title)
    ):
        return None
    return title[: pointers[0].start()] + figure + title[pointers[0].end():]


# M83 (DEV-D v3o D-p19-t3 «What's the genre?» right after the cast of «After the Wedding» was read): a question for an
# attribute with the definite article and no owner («what's the genre», «¿cuál es la trama?», «who's the director»)
# asks it of what the conversation just named. Alone it read as a definition, and «genre» was looked up.
_ATTRIBUTE_OF_THE_LAST = re.compile(
    r"(?:what|which|who|cual|cuales|quien|quienes|que)(?:'s|s|\s+(?:is|was|are|were|es|era|fue|son|eran|fueron))?\s+"
    r"(?:the|el|la|los|las|su|sus|its|their)\s+(?:main\s+|principal\s+)?"
    r"(?:genres?|plot|cast|rating|runtime|director|directora|author|autor|autora|score|ending|story|premise|budget|"
    r"soundtrack|title|release\s+date|actors|characters|lead|genero|generos|trama|reparto|final|argumento|sinopsis|"
    r"duracion|puntuacion|titulo|fecha\s+de\s+estreno|actores|personajes|protagonista|price|precio|address|direccion|"
    r"population|poblacion|capital)"
)


def asks_attribute_of_the_last(text: str) -> bool:
    """The whole message asks an attribute of something it does not name (see above)."""

    return _ATTRIBUTE_OF_THE_LAST.fullmatch(followup(text).folded) is not None


# Ronda 23 (r21 v3-50 t2 «decime cuántos archivos tiene adentro» after «en 7zip abrí el prueba.zip que está en
# baxy-prueba-v3»: read alone, «hay 7 archivos en la carpeta»): a holding verb asked with nothing after it («¿qué
# tiene?»). Its words are the lexicon's (``lexicon.BARE_HOLDING_VERBS``).
_BARE_HOLDING_QUESTION = re.compile(rf"que\s+{alternation(lexicon.BARE_HOLDING_VERBS)}")


def asks_the_inside_of_the_last(text: str) -> bool:
    """Ronda 23: the message asks the inside of what the turn before named, or what it holds, with no subject or place
    of its own («¿cuántos hay adentro?», «what is inside», «¿qué tiene?»; ``missions.anaphoric_question`` reads the
    inside and the holding with ``lexicon.ANAPHORIC_QUESTION``). «¿qué tiene adentro un huevo?», «cuántos archivos
    tiene la carpeta Descargas» and «¿qué hora es?» name their own or ask nothing of it."""

    from .missions import anaphoric_question

    return anaphoric_question(text) or _BARE_HOLDING_QUESTION.fullmatch(followup(text).folded) is not None


def leans_on_context(text: str) -> bool:
    """The trigger: the message's form leans on the turn before (see the section comment). Talk never does."""

    said = followup(text)
    folded = said.folded
    if not folded or _SOCIAL.fullmatch(folded) or _REFUSAL.fullmatch(folded) or _PROHIBITION.match(folded):
        return False
    if said.fragment or refers_back(text) or _OWN_LISTING.fullmatch(folded) or asks_attribute_of_the_last(text):
        return True
    if asks_the_inside_of_the_last(text):
        return True
    # A name of its own in a question («y quién ganó el Mundial?») is a new subject: that question is complete.
    names_something = re.search(r"\s(?!I\b)[A-ZÁÉÍÓÚÑ]", said.said) is not None or re.search(r"[\"«“]", said.said)
    if said.continued or said.corrected:
        return not (_QUESTION_WORD.match(folded) and names_something)
    # A short question about something already named: an unnamed yes/no subject («is the entrance free») or a
    # pronoun («how old is he»).
    return (
        len(folded.split()) <= 10
        and not names_something
        and (
            _DEFINITE_QUESTION.match(folded) is not None
            or (_QUESTION_WORD.match(folded) is not None and _ANAPHORIC_PRONOUN.search(folded) is not None)
        )
    )


# Tanda 7b «actually make it 9» after «set a timer for the pasta, 11 minutes»: the model wrote «make the timer for the
# pasta 9 minutes», which no reader reads. A correction that only says a new amount, hour or day is the last request
# with that value in place of the one it had, in the person's words, and it is read as that request was.
_SAID_AMOUNT = re.compile(rf"\b(?P<number>{_NUMBER})(?P<unit>\s*{_UNIT})(?![a-z])")
_SAID_HOUR = re.compile(rf"\b(?P<hour>{_CLOCK_HOUR})(?P<period>{_CLOCK_PERIOD})?(?![a-z0-9])")
_SAID_DAY = re.compile(rf"\b{_DAY}\b")


def _period_after(first: str, old_period: str | None, request: str) -> str:
    """«afternoon» said before the hour, as the request says a part of the day after it: « pm» next to «am/pm» or in
    English, « de la tarde» in Spanish."""

    morning = re.search(r"(?:morning|manana)$", first) is not None
    if (old_period and re.search(_AM_PM, old_period)) or (not old_period and not spanish(request)):
        return " am" if morning else " pm"
    return " de la mañana" if morning else " de la noche" if re.search(r"(?:night|noche)$", first) else " de la tarde"


# Uso real v3 tanda 4 c01-4 «no po, en spotify te dije, no en youtube» → restated «Pon una cumbia en YouTube.» (the
# service refused), c04-2 «joder que te he dicho brillo no volumen» after the brightness was set → an answer about the
# sound output: a contrastive correction says what the last request was about (X) and what it was not (Y) — «(en) X
# (te dije), no (en) Y», «X no Y», «no (en) Y, (sino) (en) X», «not Y, X». Only what it says to change is read: a
# prohibition without a replacement («no quiero spotify») and a bare destination («no, en YouTube») are not
# contrasts. Folded words; the cue words are the reader's data.
# Audit 2026-10-08 (t1-c02-2 «no, el brillo te dije, no el volumen. bajalo mas», t2-c04-4 «te dije la escala no el
# brillo, regresa la escala a 100», t3-c19-2 «que no, el lápiz, no el pincel»): the contrast is a run of the message's
# clauses, not its end; what follows it is the order about X.
@dataclass(frozen=True)
class Contrast:
    """``wanted`` (X) and ``refused`` (Y), folded single words, the preposition X was said with (or ""), the article X
    was said with (or "") and the order said after the contrast (folded, or "")."""

    wanted: str
    refused: str
    preposition: str
    article: str = ""
    rest: str = ""


_CONTRAST_PREPOSITION = r"(?:en|on|in|por|con|with|via|desde|from)"
_CONTRAST_ARTICLE = r"(?:(?:el|la|los|las|un|una|the|a|al)\s+)*"
_CONTRAST_TOLD = (
    r"(?:te\s+(?:dije|pedi|he\s+dicho|habia\s+dicho)|dije|pedi|i\s+(?:said|told\s+you|asked(?:\s+for)?)|told\s+you)"
)
_CONTRAST_TAG = r"(?:po|pues|pue|weon|wey|we|bro|man|dude|eh|oye|ok)"
_CONTRAST_WORD = r"[a-z0-9n][a-z0-9n'&+-]*"
_CONTRAST_X_THEN_Y = re.compile(
    rf"(?:^|\s)(?:(?P<px>{_CONTRAST_PREPOSITION})\s+)?(?P<ax>{_CONTRAST_ARTICLE})(?P<x>{_CONTRAST_WORD})"
    rf"(?:\s+{_CONTRAST_TOLD})?(?:\s+{_CONTRAST_TAG})?\s*[,;]?\s+(?:no|not|y\s+no|and\s+not|instead\s+of|en\s+vez\s+de|"
    rf"en\s+lugar\s+de)\s+(?:{_CONTRAST_PREPOSITION}\s+)?{_CONTRAST_ARTICLE}(?P<y>{_CONTRAST_WORD})\s*[.!?]*$"
)
_CONTRAST_Y_THEN_X = re.compile(
    rf"^(?:(?:{_CONTRAST_TAG}|no|nah|nope)\s*[,.]?\s+)*(?:no|not)\s+(?:{_CONTRAST_PREPOSITION}\s+)?{_CONTRAST_ARTICLE}"
    # Y and X are set apart by a pause or «sino»: «no cierres chrome», «no pongas reggaeton» are a prohibition of the
    # last request, never «chrome instead of cierres» (that repeated the request the person forbade).
    rf"(?P<y>{_CONTRAST_WORD})(?:\s*[,;]\s*(?:sino\s+(?:que\s+)?|but\s+|si\s+no\s+)?|\s+(?:sino\s+(?:que\s+)?|but\s+|si\s+no\s+))"
    rf"(?:(?P<px>{_CONTRAST_PREPOSITION})\s+)?(?P<ax>{_CONTRAST_ARTICLE})(?P<x>{_CONTRAST_WORD})"
    rf"(?:\s+{_CONTRAST_TOLD})?(?:\s+{_CONTRAST_TAG})?\s*[.!?]*$"
)
# A message that opens by denying («no, …», «que no, …», «nah …») says that what follows corrects the last result.
_CONTRAST_DENIAL = re.compile(r"(?:no|nah|nope|not|que\s+no)\b")
# The pauses that set a message's clauses apart. A point or a colon pauses only before a space or the end: inside an
# hour («10:30»), an amount («37.5») or an address («netflix.com») it is no pause (review 2026-10-08 r2).
_CONTRAST_PAUSE = re.compile(r"\s*(?:[,;!?]+|[.:]+(?=\s|$))[\s,;:.!?]*")
# A contrast is said in a few clauses (a denial, X, Y and a tag): longer runs are never tried, so a long message is
# read in linear time (review 2026-10-08 r2: all the runs of 120 clauses took 3 s).
_CONTRAST_SPAN = 4
# Words that are no thing to put in place of another: pointers, verbs of wanting or working, the cue words.
_NOT_CONTRASTED = frozenset(
    "no|not|si|yes|ya|que|eso|esto|esa|ese|lo|la|le|me|te|se|y|o|pero|mas|asi|tan|muy|nada|todo|eso|it|this|that|"
    "funciona|funcionaba|anda|sirve|suena|sono|quiero|queria|gusta|puedo|puedes|se|works|worked|plays|want|wanted|"
    "like|can|could|dije|dicho|pedi|said|told|asked|po|pues|weon|wey|bro|man|dude|ok|vale|joder|mierda|ahora|now|"
    "mejor|better|ahi|aqui|there|here|tampoco|either|nunca|never|otra|otro|other|vez|time|el|los|las|un|una|the|a|an|"
    "en|on|in|de|del|of|to|para|for".split("|")
)


def contrastive_correction(text: str) -> Contrast | None:
    """«no po, en spotify te dije, no en youtube» → Contrast(spotify, youtube, en); «te he dicho brillo no volumen» →
    Contrast(brillo, volumen, ""); «no en spotify, en youtube» → Contrast(youtube, spotify, en); «te dije la escala no
    el brillo, regresa la escala a 100» → Contrast(escala, brillo, rest «regresa la escala a 100»). None otherwise."""

    folded = spelled_out(_fold(text)).strip()
    if not folded:
        return None
    # The contrast is a run of the message's clauses: the interjections and reproaches before it («no po,», «joder
    # que te he dicho») are no part of it, and what follows it is the order said about X.
    clauses = [clause for clause in _CONTRAST_PAUSE.split(folded) if clause.strip()]
    told = re.search(rf"\b{_CONTRAST_TOLD}\b", folded) is not None
    denies = _CONTRAST_DENIAL.match(folded) is not None
    for first in range(len(clauses)):
        for last in range(min(len(clauses), first + _CONTRAST_SPAN), first, -1):
            candidate = ", ".join(clauses[first:last])
            for pattern, needs_cue in ((_CONTRAST_Y_THEN_X, False), (_CONTRAST_X_THEN_Y, True)):
                found = pattern.search(candidate)
                if found is None:
                    continue
                wanted, refused = found.group("x"), found.group("y")
                if (
                    wanted == refused
                    or wanted in _NOT_CONTRASTED
                    or refused in _NOT_CONTRASTED
                    # An hour, an amount or a day replaced is the readers' below; a bare number is no thing named.
                    or any(re.fullmatch(r"[\d:.,]+", word) for word in (wanted, refused))
                    # Review 2026-10-08 r2: «abre chrome, no firefox» after «cierra firefox» became «cierra chrome»;
                    # «el martes, no el lunes, recuerdamelo» took the order for X. X said with an order of its own (a
                    # verb in its clause) is a whole new request, never a correction of the last one; an order is no X.
                    or _head_is(wanted, _COVERAGE_ACTION_HEAD)
                    or any(
                        _head_is(word, _COVERAGE_ACTION_HEAD)
                        for word in candidate[: found.start("x")].rsplit(",", 1)[-1].split()
                    )
                    # «te había dicho que hoy no trabajo»: a bare word right after «que» opens a clause of its own,
                    # whose «no» denies its verb.
                    or (
                        not found.group("ax").strip()
                        and not found.group("px")
                        and re.search(r"\bque\s*$", candidate[: found.start("x")]) is not None
                    )
                ):
                    continue
                # «X no Y» alone is also how a sentence is said («spotify no anda»): it is a correction when the
                # person says they said it, when the message opens by denying («no, …», «que no, …»), or when the
                # whole message is «X, no Y» set apart by a pause and «no Y» is no courtesy («perfecto, no gracias»,
                # «bueno, no importa», «sure, not a problem»).
                paused = (
                    first == 0
                    and last == len(clauses)
                    and re.search(r",\s*(?:no|not)\s", candidate) is not None
                    and not is_social(clauses[-1])
                    and _AGREEING_NO.search(clauses[-1]) is None
                )
                if needs_cue and not (told or denies or paused):
                    continue
                return Contrast(
                    wanted, refused, found.group("px") or "", found.group("ax").strip(), ", ".join(clauses[last:]),
                )
    return None


def _order_after(rest: str) -> str:
    """What follows a contrast without what only closes it («gracias», «porfa», «dale», «ya»): "" when nothing else."""

    words = rest.replace(",", " ").split()
    if not words or is_social(rest) or gives_go_ahead(rest) or all(word in _ORDER_TAIL for word in words):
        return ""
    return rest


def _contrasted_request(base: str, contrast: Contrast) -> str | None:
    """The last request with the contrast applied: Y in it becomes X; a request that already names X (and not Y) is
    itself; one that names neither takes X with the preposition it was said with («… en spotify»)."""

    rest = _order_after(contrast.rest)
    if rest:
        # The order after the contrast is about X: said with X it is itself («regresa la escala a 100»), said with a
        # pronoun it takes X («bajalo mas» → «baja el brillo mas»); a second order joined by «y» follows the corrected
        # last request («… en spotify y sube el volumen»). Review 2026-10-08 r2: an order that cannot be told so is
        # never dropped for the last request (its value or its second order was lost): there is no corrected request.
        if re.search(rf"\b{re.escape(contrast.wanted)}\b", rest) is not None:
            return rest
        if followup(rest).continued:
            corrected = _contrasted_request(base, Contrast(contrast.wanted, contrast.refused, contrast.preposition))
            return f"{corrected.rstrip(' .!?')} {rest}" if corrected is not None else None
        # X said with a preposition is a place («en spotify»): «subelo» after it is about what plays there.
        if contrast.preposition:
            return None
        return with_object(rest, f"{contrast.article} {contrast.wanted}".strip())
    said = followup(base).said or base
    folded = _fold(said)
    if len(folded) != len(said):
        said = folded
    refused = re.search(rf"\b{re.escape(contrast.refused)}\b", folded)
    if refused is not None:
        return said[: refused.start()] + contrast.wanted + said[refused.end():]
    if re.search(rf"\b{re.escape(contrast.wanted)}\b", folded) is not None:
        return said
    if contrast.preposition:
        return f"{said.rstrip(' .!?')} {contrast.preposition} {contrast.wanted}"
    return None


def corrected_request(request: str | None, text: str) -> str | None:
    """«no, mejor a las 6:15» after «ponme una alarma a las 6 y media pa mañana» → «ponme una alarma a las 6:15 pa
    mañana»; «mejor que sean 6» after «un temporizador de 8 minutos» → «… de 6 minutos»; «en spotify te dije, no en
    youtube» after «ponme cumbia en youtube» → «ponme cumbia en spotify» (``contrastive_correction``). None when the
    message is not such a correction or the request has no value of that kind."""

    said = followup(text)
    base = " ".join(str(request or "").split())
    if not base or "\n" in str(request) or not said.replaces_last:
        return None
    contrast = contrastive_correction(text)
    if contrast is not None:
        return _contrasted_request(base, contrast)
    folded = _fold(base)
    if len(folded) != len(base):
        base = folded
    hour = re.fullmatch(rf"(?:(?P<first>{_PART_OF_DAY_FIRST})\s+)?(?P<hour>{_CLOCK_HOUR})(?P<period>{_CLOCK_PERIOD})?", said.folded)
    old = _SAID_HOUR.search(folded)
    if hour is not None and old is not None:
        # The part of the day said before stays unless the correction says another one; said first («afternoon
        # 3:45»), it goes after the hour as the request says it. The request's preposition stays unless the
        # correction says one.
        new = said.said[hour.start("hour"): hour.end("period") if hour.group("period") else hour.end("hour")]
        if hour.group("first"):
            new += _period_after(hour.group("first"), old.group("period"), base)
        start = old.start()
        if not re.match(rf"(?:{_CLOCK_PREFIX}|for|to)\s", hour.group("hour")):
            said_prefix = re.match(rf"(?:{_CLOCK_PREFIX}|for|to)\s+", old.group("hour"))
            if said_prefix is not None and said_prefix.group(0).split()[0] in {"for", "to"}:
                # «for 3:45» also names the alarm already set for then (a cancellation reads it so): the clock
                # that replaces one is said «at».
                new = "at " + new
            else:
                start += said_prefix.end() if said_prefix is not None else 0
        end = old.end() if hour.group("period") or hour.group("first") else old.end("hour")
        return base[:start] + new + base[end:]
    if _AMOUNT_FRAGMENT.fullmatch(said.folded):  # «at 7» after a timer of 10 minutes is its amount
        new = re.search(rf"\b(?P<number>{_NUMBER})(?P<unit>\s*{_UNIT})?$", said.folded)
        old = _SAID_AMOUNT.search(folded)
        if new is None or old is None:
            return None
        number = str(_NUMBER_VALUES.get(new.group("number"), new.group("number")))
        unit = said.said[new.start("unit"):new.end("unit")] if new.group("unit") else base[old.start("unit"):old.end("unit")]
        return base[: old.start()] + number + unit + base[old.end():]
    if re.fullmatch(_DAY, said.folded):
        old = _SAID_DAY.search(folded)
        return base[: old.start()] + said.said + base[old.end():] if old is not None else None
    return None


# Tanda 7b «cómo se llama esta?» after a music request was searched on the web as «cómo se llama esta de los
# bunkers»: in a question right after music, a bare «esta», «this», «it» is the song, and what plays is read
# (media.status says what plays, or that nothing does).
_BARE_POINTER = re.compile(r"\b(?:(?P<es>esta|este|esto|esa|ese|eso)|(?:this|that|it)(?:\s+one)?)\b")


def again(request: str | None, text: str) -> str | None:
    """«más» after «baja el volumen en 10» → «baja el volumen en 10»: the last request once more, as it was said.
    «¿y más?» asks for more of an answer, not the request again."""

    said, base = followup(text), " ".join(str(request or "").split())
    if not base or "\n" in str(request) or said.continued or not _AGAIN_FRAGMENT.fullmatch(said.folded):
        return None
    return base


def as_the_song(text: str) -> str | None:
    """«cómo se llama esta?» → «cómo se llama esta canción», «what's this called» → «what's this song called»."""

    said = followup(text)
    if _QUESTION_WORD.match(said.folded) is None or _DEMONSTRATIVE.search(said.folded) is None:
        return None
    if re.search(r"\b(?:cancion|tema|song|track|tune)\b", said.folded):
        return said.said  # «qué tema es este» already says it
    pointer = list(_BARE_POINTER.finditer(said.folded))[-1]
    noun = "esta canción" if pointer.group("es") else "this song"
    return said.said[: pointer.start()] + noun + said.said[pointer.end():]


def shape(text: str, dependency: str | None) -> str:
    """The form of a message that depends on the context: the dependency, or for a follow-up what it says — an
    amount, a time, another item, what the person holds, a place, a thing pointed at, an item added, a question."""

    if dependency != "followup":
        return dependency or ""
    folded = followup(text).folded
    for name, found in (
        ("again", _AGAIN_FRAGMENT.fullmatch(folded)),
        ("amount", _AMOUNT_FRAGMENT.fullmatch(folded)),
        ("time", _TIME_FRAGMENT.fullmatch(folded)),
        ("another", _ANOTHER_FRAGMENT.match(folded)),
        ("listing", _OWN_LISTING.fullmatch(folded)),
        ("place", _PLACE_ANAPHOR.search(folded) or _PLACE_FRAGMENT.fullmatch(folded)),
        ("pointer", _DEMONSTRATIVE.search(folded) or _BARE_POINTER.match(folded) or _VALUE_POINTER.search(folded)),
        ("question", _QUESTION_WORD.match(folded) or _DEFINITE_QUESTION.match(folded)),
    ):
        if found:
            return name
    return "item"


def spanish(text: str) -> bool:
    """The message is said in Spanish (for the words BAXY adds to a rewrite)."""

    return _SPANISH_WORD.search(_fold(text)) is not None


# M103 (owner script t25): an order to look something up the person says they already gave («te dije que investigues
# algo», «ya te pedí que lo buscaras», «I told you to look it up»), naming nothing new (a pronoun, «algo», «eso»), or
# their claim that it is a web search («eso debería ir a web search»). Never a «no» before the verb.
_REPORTED_SEARCH_ORDER = re.compile(
    r"\b(?:(?:ya\s+)?te\s+(?:dije|pedi|mande|lo\s+dije|lo\s+pedi)|i\s+(?:already\s+)?(?:told|asked)\s+you)\s+"
    r"(?:que\s+|to\s+)?(?:lo\s+|la\s+)?"
    r"(?:investig|busc|averigu|research|search|look\s+(?:it\s+|that\s+|this\s+)?up|google|find\s+out)\w*"
    r"(?:\s+(?:algo|eso|esto|lo|la|it|that|this|something|about\s+it|for\s+it|sobre\s+(?:eso|esto|ella|el)))?"
    r"(?=\s*(?:[,.;:!?]|$|\b(?:y|and|pero|but|porque|because)\b))"
)
_WEB_SEARCH_CLAIM = re.compile(
    r"\b(?:eso|esto|that|this|it)\s+(?:deberia|tendria\s+que|tiene\s+que|debe|should|must|has\s+to)\s+"
    r"(?:ir\s+a|ser|go\s+to|be)\s+(?:(?:un|una|a|an|la|el|the)\s+)?"
    r"(?:web\s*search|busqueda(?:\s+web|\s+en\s+(?:la\s+)?(?:web|internet))?|search|buscad[oa]|buscarse)\b"
)


def insists_on_searching(text: str) -> bool:
    """The person insists that what they asked to look up be looked up, naming nothing new to look up."""

    folded = _fold(str(text or ""))
    return _REPORTED_SEARCH_ORDER.search(folded) is not None or _WEB_SEARCH_CLAIM.search(folded) is not None


def _family(operation: str) -> str:
    return operation.split(".", 1)[0]


# Uso real 2026-10-07 «ok pero lo puedes buscar en google» after a web search: the same search, shown in the browser.
_SEARCH_SHOWN_IN_THE_BROWSER = frozenset({"browser.navigate", "browser.navigate.named"})


def same_family(operations: tuple[str, ...], frame: tuple[str, ...]) -> bool:
    """A rewrite reads no effect, or only effects of the family of the request it continues (a web search continues
    as its results page opened in the browser)."""

    if not operations:
        return True
    if not frame:
        return False
    families = {_family(op) for op in frame}
    return all(
        _family(op) in families or (op in _SEARCH_SHOWN_IN_THE_BROWSER and "web.search" in frame)
        for op in operations
    )


# Uso real 2026-10-07 «ok pero lo puedes buscar en google no me importa the ice»: the thing to look up said as a
# pronoun («lo», «eso», «it») and the search engine or the browser named as the place. What follows the place may be
# a comment on what was found («no me importa…»), never another thing to look up. A «no» before the verb forbids it
# («no me lo busques en Google»); a Google product is a place of its own («Google Drive»).
_PRONOUN_SEARCH_LEAD = (
    r"^(?:(?:y|e|entonces|mejor|ahora|pues|bueno|porfa|por\s+favor)\b[\s,]*)*"
    r"(?:(?:me\s+)?(?:puedes|podes|podrias|puede|podria|podrian|pueden|quiero\s+que|necesito\s+que)\s+)?"
)
_PRONOUN_SEARCH_FORBIDDEN = re.compile(
    r"^[\s¿?¡!]*(?:(?:ok|okay|bueno|pero|y|entonces|baxy)\b[\s,]*)*(?:no|nunca|jamas|don'?t|do\s+not|never)\s+(?![,.])"
)
_PRONOUN_SEARCH_VERB = (
    r"(?:(?:me\s+|te\s+)?(?:lo|la|los|las)\s+(?:(?:puedes|podes|podrias|puede|podria|podrian|pueden|quiero\s+que\s+|"
    r"me\s+)\s*)?(?:busca|buscas|buscar|busques|buscaras|buscarias|googleas|googlear|googlees)|"
    r"b[uú]sc[aá](?:me)?(?:lo|la|los|las)|b[uú]sc[aá]r(?:me|se|te)?(?:lo|la|los|las)|googlea(?:r)?(?:me)?(?:lo|la)|"
    r"(?:busca|buscar|buscame|googlea|googlear)\s+(?:eso|esto|aquello)|"
    r"(?:(?:can|could|would)\s+you\s+)?(?:search(?:\s+for)?|look\s+up|google)\s+(?:it|that|this)(?:\s+up)?)"
)
_PRONOUN_SEARCH_PLACE = re.compile(
    _PRONOUN_SEARCH_LEAD
    + _PRONOUN_SEARCH_VERB
    + rf"\s+(?:en|on|in)\s+(?:el\s+|the\s+|mi\s+|my\s+)?(?P<place>{_GOOGLE_ENGINE}|navegador|browser)"
    # Ronda 19 (r17 t3 c17/4 «buscalo en google pa poder citarlo»): what the search is for («pa…», «para…», «so I
    # can…») follows the place and names nothing to look up. Revisión adversarial 3 («búscalo en google para windows
    # 11», «para android»): only a purpose is no part of the search — «para» with an infinitive that goes on (a clitic
    # or more words) or with «que», «so» with who will do it, «to» with a verb; «para» with a name qualifies what is
    # searched and the turn stays with the decider.
    r"(?P<tail>(?:\s*[,.;!?]+\s*|\s+)(?:no|not|porque|because|que|ya|ahora|now|please|por\s+favor|porfa|gracias|thanks|"
    r"(?:pa|para)\s+(?:que|[a-z]*(?:ar|er|ir)(?:(?:me|te|se|lo|la|los|las|le|les|nos)+\b|(?=\s+\w)))|"
    r"so\s+(?:that|i|we|you|he|she|they|it|i'?ll|i'?d)|in\s+order\s+to|to\s+(?!the\b|a\b|an\b|my\b|your\b|this\b)[a-z]{2,})\b.*|"
    r"\s*(?:,?\s*(?:porfa|por\s+favor|please|pls|plis))?[\s.!?]*)$"
)
# Revisión 2026-10-07 «busca en google eso», «search on google for it»: the pronoun after the place.
_PRONOUN_AFTER_SEARCH_PLACE = re.compile(
    _PRONOUN_SEARCH_LEAD
    + r"(?:busca|buscar|buscame|buscanos|googlea|googlear|googleame|search(?:\s+for)?|look\s+up)"
    + rf"\s+(?:en|on|in)\s+(?:el\s+|the\s+|mi\s+|my\s+)?(?P<place>{_GOOGLE_ENGINE}|navegador|browser)"
    r"\s+(?:for\s+)?(?:eso|esto|lo\s+mismo|it|that|the\s+same(?:\s+thing)?)"
    r"\s*(?:,?\s*(?:porfa|por\s+favor|please|pls|plis))?[\s.!?]*$"
)


def pronoun_search_place(text: str) -> str | None:
    """«búscalo en Google», «ok pero lo puedes buscar en google no me importa X», «search it on Google» → «google»;
    «búscalo en el navegador» → «browser». None when the message names what to look up or forbids it."""

    if _PRONOUN_SEARCH_FORBIDDEN.match(_fold(str(text or ""))):
        return None
    folded = followup(text).folded
    found = _PRONOUN_SEARCH_PLACE.match(folded) or _PRONOUN_AFTER_SEARCH_PLACE.match(folded)
    if found is None:
        return None
    return "google" if found.group("place") == "google" else "browser"


def asks_to_search(text: str) -> bool:
    """Ronda 24, revisión 2 (r23 t3-c17 t4 «buscalo en google pa poder citarlo» → «¿Cuál es la URL exacta…?»): the
    message is an order to look something up — its head is a search verb (``grammar._SEARCH``: «busca», «búscalo»,
    «googlea», «search», «look up») or it searches a pronoun in a named place. A search verb never asks for an
    address; «abre la página del banco» or «ve a la web de la U» are no search."""

    return pronoun_search_place(text) is not None or _head_is(_request_head(str(text or "")), _SEARCH)


# Revisión 2026-10-07 «busca en google eso», «búscame en google lo que te dije», «googlea esa canción»: the words
# after the engine point back at something said before; they are no query of their own.
_QUERY_POINTS_BACK = re.compile(
    r"^(?:for\s+|sobre\s+|de\s+)?(?:"
    r"(?:ese|esa|esos|esas|aquel|aquella|aquellos|aquellas|that|those)\b.*|"
    r"(?:eso|esto|aquello|ello|it|that|this|them|lo\s+mismo|la\s+misma|lo\s+de\s+antes|the\s+same(?:\s+thing)?|"
    r"what\s+i\s+(?:said|told\s+you|asked)|lo\s+que\s+(?:te\s+|le\s+)?(?:dije|pedi|dijiste|encontraste|buscaste)\b.*|"
    r"(?:este|esta|estos|estas|this|these)\s+\S+)"
    r")$"
)


def query_points_back(query: str) -> bool:
    """The thing to look up is said as a pointer to something said before («eso», «lo mismo», «lo que te dije»,
    «esa canción», «it»); «el estreno de Dune» or «noticias de hoy» name their own."""

    folded = followup(query).folded
    return bool(folded) and _QUERY_POINTS_BACK.fullmatch(folded) is not None


@functools.lru_cache(maxsize=1)
def _order_said_back_words() -> dict[str, tuple[str, ...]]:
    path = Path(__file__).resolve().parent.parent / "data" / "order_said_back.v1.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        key: tuple(fold(str(word)) for word in data.get(key, ()))
        for key in ("yes_no_openers", "filler", "alternatives", "pointers", "takes_back")
    }


@functools.lru_cache(maxsize=4096)
def _order_heads(word: str) -> frozenset[str]:
    """The order heads a word is said as: itself, without its fused clitics, or the tú/voseo imperative of the
    «usted»/subjunctive form or infinitive it is (``grammar._head_forms``, ``grammar._imperatives_of``), kept only when
    the readers know it as an order head («abra» → «abre», «suba» → «sube», «ponga» → «pon», «súbele» → «sube»)."""

    heads = _compiled(_COVERAGE_ACTION_HEAD)
    candidates = (word, *_imperatives_of(word, _COVERAGE_ACTION_HEAD))
    return frozenset(form for candidate in candidates for form in _head_forms(candidate) if heads.fullmatch(form))


def _same_word(said_back: str, said: str) -> bool:
    # Revisión 2: a verb said back in another mood is the same order head («cierra» → «cierre», «abre» → «abra»,
    # «pon» → «ponga»); «descarga» → «descarte» or «cierra» → «cierro» are other words. Any other word is said as is.
    return said_back == said or bool(_order_heads(said_back) & _order_heads(said))


@dataclass(frozen=True)
class OrderSaidBack:
    """The request split where the question's saying back ends: ``said`` up to the last word the question repeats,
    ``rest`` what follows, both as the person wrote them."""

    said: str
    rest: str


def order_said_back(question: str, request: str) -> OrderSaidBack | None:
    """Ronda 24 (r23 t2-c03#2 «ya cierra configuracion…» → «¿Te gustaría que cierre la configuración ahora mismo?»,
    t4-c03 «ya cierra discord» → «¿Quieres que cierre Discord ahora mismo?»): a yes/no question (``yes_no_openers`` in
    ``data/order_said_back.v1.json``) whose every other word is the request's own or filler asks for no missing value:
    the order is said back. A question that names something the request did not («¿cierro Chrome o Word?»), offers a
    choice, points at a referent («¿Quieres que lo cierre?») or asks how much («¿cuánto lo subo?») is a real question
    (None). Where the request goes on after the words said back, ``rest`` keeps it for the caller to judge."""

    words = _order_said_back_words()
    folded = " ".join(re.findall(r"[a-z0-9]+", fold(str(question or ""))))
    opener = next(
        (opener for opener in sorted(words["yes_no_openers"], key=len, reverse=True)
         if folded == opener or folded.startswith(opener + " ")),
        None,
    )
    if opener is None:
        return None
    rest = [word for word in folded[len(opener):].split() if word not in words["filler"]]
    # Revisión 1: a word that points («lo», «eso», «it») asks about a referent not yet resolved («ciérralo» →
    # «¿Quieres que lo cierre?»): the question is real, whatever the request said.
    if not rest or any(word in words["alternatives"] or word in words["pointers"] for word in rest):
        return None
    request = str(request or "")
    tokens = [
        (found.end(), piece)
        for found in re.finditer(r"[^\W_]+", request)
        for piece in re.findall(r"[a-z0-9]+", fold(found.group()))
    ]
    end = 0
    for word in rest:
        ends = [token_end for token_end, said in tokens if _same_word(word, said)]
        if not ends:
            return None
        end = max(end, min(ends))
    return OrderSaidBack(request[:end], request[end:])


def question_only_says_the_order_back(question: str, request: str) -> bool:
    """The question says the request back (``order_said_back``), the whole of it or its start."""

    return order_said_back(question, request) is not None


def _rest_words(rest: str) -> str:
    # English negative contractions are one word without the apostrophe («don't» → «dont»).
    return " ".join(re.findall(r"[a-z0-9]+", re.sub(r"['’]", "", fold(str(rest or "")))))


# r31: each reader's view of the one list (``lexicon.REASON_OPENERS``).
_SAID_BACK_REASON = lexicon.reason_opening(lexicon.REASONS_SAID_BACK)
_WINDOW_ORDER_REASON = lexicon.reason_opening(lexicon.REASONS_OF_A_WINDOW_ORDER)


def _reason_opener(folded: str, opening: str = _SAID_BACK_REASON) -> str | None:
    found = _compiled(opening).match(folded)
    return found.group(0) if found is not None else None


def takes_the_order_back(rest: str, opening: str = _SAID_BACK_REASON) -> bool:
    """Revisión 3 de la ronda 24 («cierra discord que me esta laggeando o mejor no», «ya cierra discord que me esta
    laggeando el valorant bueno no mejor no», «cierra discord que me lo pidio mi mama pero no lo cierres todavia»,
    «close discord because it lags but not yet»): what follows the order said back takes it back or leaves it open — a
    refusal or a correction interjection (``refusals``, ``interjections`` of ``data/correction_words.v1.json``), an
    order to do nothing (``cease_orders``: «déjalo», «olvídalo») or a connective that opposes or offers another choice
    (``takes_back`` of ``data/order_said_back.v1.json``: «pero», «o», «but», «or»). Said by voice it comes without
    commas. The «no» of a reason opener is the reason's own («que ya no lo uso»)."""

    folded = _rest_words(rest)
    opener = _reason_opener(folded, opening)
    if opener is not None:
        folded = folded[len(opener):].strip()
    if not folded:
        return False
    words = correction_words()
    padded = f" {folded} "
    phrases = (
        *_order_said_back_words()["takes_back"],
        *(fold(str(word)) for word in words["refusals"]),
        *(fold(str(phrase)) for phrase in words["interjections"]),
    )
    if any(f" {phrase} " in padded for phrase in phrases):
        return True
    return any(_head_is(word, _cease_order_head()) for word in folded.split())


def only_gives_a_reason(rest: str, opening: str = _SAID_BACK_REASON) -> bool:
    """Revisión 2 de la ronda 24 (r23 t2-c03#2 «ya cierra configuracion que me esta laggeando el valorant»): what follows
    the order said back only tells why («que me está…», «porque…», «because…»; ``lexicon.REASONS_SAID_BACK``), or
    nothing follows. «…, bueno no, mejor no», «… y spotify» or «… que dice error»
    (which window) are more than a reason, and so is a reason that goes on to take the order back without a pause
    (revisión 3, ``takes_the_order_back``: «… que me laggea o mejor no», «… because it lags but not yet»)."""

    clauses = [" ".join(re.findall(r"[a-z0-9]+", part)) for part in re.split(r"[,;.:!?]+", fold(str(rest or "")))]
    said = [clause for clause in clauses if clause]
    if len(said) > 1:
        # «… que me laggea, bueno no, mejor no»: a clause after the reason may take the order back.
        return False
    folded = said[0] if said else ""
    if not folded:
        return True
    return _reason_opener(folded, opening) is not None and not takes_the_order_back(rest, opening)


def order_before_its_reason(request: str) -> str | None:
    """Tandas b2/c28u t2-c03 t2 «ya cierra configuracion que me esta laggeando el valorant»: the request up to its last
    clause that only tells why (``only_gives_a_reason`` over ``lexicon.REASONS_OF_A_WINDOW_ORDER``: «… que me está…»,
    «… porque…», «… cuz…»); None when it ends in none. One cut, the longest order: what it leaves is read as it is, never
    shortened again («cierra just cause 3 porque se pegó» is never «cierra just»). A clause is its conjunction and at
    least two words more, the first no number: «cause 3», «since dawn» are the rest of a name. A reason that goes on to
    take the order back is none, and what BAXY did for the person («que me abriste recién») says which one, not why."""

    request = str(request or "")
    for found in reversed(tuple(re.finditer(r"[^\W_]+", request))):
        rest = request[found.start():]
        words = _rest_words(rest).split()
        if (
            found.start() and len(words) >= 3 and not words[1].isdigit()
            and not (words[0] in {"que", "q", "k"} and words[1] in {"me", "nos"} and words[2].endswith(("aste", "iste")))
            and only_gives_a_reason(rest, _WINDOW_ORDER_REASON)
        ):
            return request[:found.start()].rstrip(" ,;:")
    return None


@functools.lru_cache(maxsize=1)
def _answer_subject_words() -> dict[str, tuple[str, ...]]:
    path = Path(__file__).resolve().parent.parent / "data" / "answer_subject.v1.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    words = {
        key: tuple(fold(str(word)) for word in data.get(key, ()))
        for key in (
            "copulas", "function_words", "first_person", "openers", "subordinators", "finite_verbs", "evaluative",
            "sentence_adverbs", "quantifiers", "generic_heads",
        )
    }
    words["refusals"] = tuple(fold(str(word)) for word in correction_words()["refusals"])
    return words


def _without_answer_opener(sentence: str) -> str:
    """Revisión 3: «Claro, la Primera Guerra Mundial fue…» → «la Primera Guerra Mundial fue…». An opener (``openers``)
    is dropped only when a comma or a mark follows it; «Claro de Luna de Debussy es…» keeps it."""

    openers = sorted(_answer_subject_words()["openers"], key=len, reverse=True)
    while True:
        tokens = list(re.finditer(r"[^\W_]+", sentence))
        folded = [fold(token.group()) for token in tokens]
        size = next(
            (len(opener.split()) for opener in openers
             if " ".join(folded[: len(opener.split())]) == opener and len(tokens) > len(opener.split())),
            0,
        )
        if not size:
            return sentence
        between = sentence[tokens[size - 1].end() : tokens[size].start()]
        if not re.fullmatch(r"\s*[,!¡:;—–-]+\s*", between):
            return sentence
        sentence = sentence[tokens[size].start() :]


def answer_subject(reply: str) -> str | None:
    """Ronda 24, revisión 2 (r23 t3-c17 t4): the thing BAXY's answer is about, as it wrote it — the words before the
    verb that says what it is or was in its first sentence («La invasión de Bélgica por Alemania fue la violación…» →
    «La invasión de Bélgica por Alemania»). None for a list, a short or empty subject, or one that speaks of BAXY or the
    person («Son las 17:26.», «Te di 3 elementos…», «La respuesta es 42», «Tu alarma es a las 7»).

    Revisión 3: an opening interjection is no part of it («Claro, la Primera Guerra Mundial fue…»), and words that say
    something instead of naming it leave no subject: a refusal («No estoy seguro de quién fue…», «No lo sé con
    certeza, pero creo que fue…»), a subordinate clause («Eso que preguntas es…») or a finite verb of the first or
    second person («Creo…», «tienes»).

    Revisión 4 («La causa más común es la falta de RAM…», «Una buena opción es…», «Lamentablemente esa información
    es…», «Ninguna aplicación es perfecta»): a subject that values, ranks or comments instead of naming leaves none —
    a word of degree or value, a sentence adverb, or an opening quantifier; a generic head («causa», «opción») is
    named only with what follows it («La causa de la Primera Guerra Mundial»). A word of a proper name is none of
    these («Buenos Aires es…»)."""

    words = _answer_subject_words()
    opened = _without_answer_opener(str(reply or "").strip())
    first = re.split(r"(?<=[^\d\s])[.!?;:](?:\s|$)|\n", opened, maxsplit=1)[0].strip()
    tokens = list(re.finditer(r"[^\W_]+", first))
    folded = [fold(token.group()) for token in tokens]
    if not tokens or folded[0].isdigit():
        return None
    says = {*words["first_person"], *words["refusals"], *words["subordinators"], *words["finite_verbs"]}
    for index in range(1, min(len(tokens), 12)):
        if any(" ".join(folded[index : index + len(copula.split())]) == copula for copula in words["copulas"]):
            subject = folded[:index]
            unnamed = {*words["function_words"], *words["generic_heads"]}
            named = [word for word in subject if word not in unnamed and not word.isdigit()]
            if len(named) < 2 or any(word in says for word in subject):
                return None
            # A word of a proper name is no value or quantifier («Buenos Aires», «Todos los Santos», «Best Buy»): a
            # capitalized word that is not the first, or the first when the second is capitalized too.
            def _named_part(position: int) -> bool:
                if not tokens[position].group()[:1].isupper():
                    return False
                return position > 0 or (index > 1 and tokens[1].group()[:1].isupper())

            plain = [word for position, word in enumerate(subject) if not _named_part(position)]
            joined = f" {' '.join(plain)} "
            if (
                (not _named_part(0) and subject[0] in words["quantifiers"])
                or any(word in words["evaluative"] for word in plain)
                or any(word.endswith("mente") and len(word) > 6 for word in plain)
                or any(f" {adverb} " in joined for adverb in words["sentence_adverbs"])
            ):
                return None
            return first[tokens[0].start() : tokens[index - 1].end()]
    return None


# «otra vez», «de nuevo», «inténtalo», «again», «try again»: doing it once more is asked, whatever leads it.
_ASKED_AGAIN = re.compile(
    r"\b(?:otra\s+vez|de\s+nuevo|nuevamente|intentalo|reintenta(?:lo|r)?|"
    r"again|once\s+more|one\s+more\s+time|retry)\b"
)
# Reads with no effect on the machine whose same result may come back again: only these are held to «not the same
# again». An effect (an app opened, a note created, the volume) is never swapped for a remark about the last one.
_PUBLIC_READS = frozenset({"web.search", "web.news.headlines"})


def corrects_or_insists(text: str) -> bool:
    """The message corrects the last result («no, …», «sí, pero…», «ok pero…») or insists on what was asked («te dije
    que lo buscaras», «búscalo en Google»). «otra vez» and «repítelo» ask for it again; «¿y ahora…?» goes on."""

    said = followup(text)
    if _AGAIN_FRAGMENT.fullmatch(said.folded) or _ASKED_AGAIN.search(_fold(str(text or ""))):
        # Revisión 2026-10-07 «no, búscalo de nuevo», «ok pero intenta otra vez»: a retry asked, anywhere in it.
        return False
    return (
        said.corrected
        or insists_on_searching(text)
        or pronoun_search_place(text) is not None
        or _REPROACH.search(said.folded) is not None
        or _REPROACH.search(_fold(str(text or ""))) is not None  # «pero te he dicho …»: the lead is part of it
        # «joder que te he dicho brillo no volumen» (t4-c04-2): a contrast with the last request reproaches it.
        or contrastive_correction(text) is not None
        # Ronda 19 (t3-c18 «esa no es la de programador wey, sigue en la estandar, cambiala»): the state left reproached.
        or reproaches_the_state(text)
    )


# Uso real v3 t2 («te dije la escala no el brillo, regresa la escala a 100», «…, te dije CHROME»): what the person
# said before, said back to BAXY at the head of a clause, reproaches the last result. «¿qué te dije ayer?» asks.
_REPROACH = re.compile(
    r"(?:^|[,;.]\s*)(?:(?:(?:pero|but|bro|che|wey|guey|loco)\s+)?"
    r"(?:te\s+(?:dije|pedi|estoy\s+diciendo)|ya\s+te\s+dije|i\s+(?:said|told\s+you|asked\s+(?:you\s+)?(?:for|to)))|"
    # «pero te he dicho que en spotify»: the perfect reproaches after a lead; alone it also tells a fact («te he dicho
    # que me gusta el rock», review 2026-10-08 r2). «joder que te he dicho brillo no volumen» (t4-c04-2) is a contrast.
    r"(?:pero|but|bro|che|wey|guey|loco|ya)\s+te\s+(?:he|habia)\s+dicho)\b"
)


# Revisión de la ronda 19: a reproach of the state is said in clauses of its own — a denial of the state left («esa no
# es la de programador»), a claim of the state still on («sigue en la estándar»), each naming one thing — and the
# other clauses only lead («no», «wey») or ask it changed («cambiala»). «eso no es urgente, pero abre chrome», «it's
# still early, play some music», «sigue en la página 3», «el que sigue en la lista, ábrelo» and «sigue siendo de noche,
# baja el brillo» are new requests (data: correction_words.v1.json).
@functools.lru_cache(maxsize=1)
def _state_clause() -> re.Pattern[str]:
    return re.compile(
        rf"(?:(?:{correction_phrases('state_leads')})\s+)*(?:(?P<denial>{correction_phrases('state_denials')})|"
        rf"(?P<claim>{correction_phrases('state_claims')}))\s+(?:(?:{correction_phrases('state_skips')})\s+)*"
        rf"(?P<word>[a-z0-9ñ][a-z0-9ñ'+-]*)(?:\s+(?:{correction_phrases('state_tags')}))*"
    )


@functools.lru_cache(maxsize=1)
def _state_aside() -> re.Pattern[str]:
    return re.compile(
        rf"(?:(?:{correction_phrases('state_leads')}|{correction_phrases('state_tags')})(?:\s+|$))+|"
        rf"(?:(?:{correction_phrases('state_leads')})\s+)*(?:{correction_phrases('state_change_orders')})(?:\s+(?:{correction_phrases('state_tags')}))*"
    )


@functools.lru_cache(maxsize=1)
def _asked_reproach() -> re.Pattern[str]:
    # At the head of a clause: «lo que te pedí ayer» names something asked, it says nothing back.
    return re.compile(
        rf"(?:(?:{correction_phrases('state_leads')})\s+)*(?:{correction_phrases('asked_reproaches')})(?!\w)"
        rf"(?![\s,]+(?:{correction_phrases('asked_reproach_negations')})(?!\w))"
    )


@dataclass(frozen=True)
class StateReproach:
    """The things a state reproach denies are on («esa no es la de programador») and claims are still on («sigue en
    la estándar»), folded single words."""

    denied: tuple[str, ...]
    claimed: tuple[str, ...]


def _clauses(folded: str) -> list[str]:
    return [clause.strip() for clause in _CONTRAST_PAUSE.split(folded) if clause.strip()]


def state_reproach(text: str) -> StateReproach | None:
    """Ronda 19 (t3-c18 «esa no es la de programador wey, sigue en la estandar, cambiala»): the person says the state
    the last turn left is not the one asked. Every clause is a denial or a claim naming one thing, a lead or an order
    to change it (``_state_clause``, ``_state_aside``). A question asks («¿sigue en pie la reunión?»); a clause of
    anything else is another request («eso no es urgente, pero abre chrome»). None otherwise."""

    raw = str(text or "")
    if "?" in raw or "¿" in raw:
        return None
    denied: list[str] = []
    claimed: list[str] = []
    for clause in _clauses(without_correction_interjection(_fold(" ".join(raw.split())))):
        found = _state_clause().fullmatch(clause)
        if found is not None:
            (denied if found.group("denial") else claimed).append(found.group("word"))
        elif _state_aside().fullmatch(clause) is None:
            return None
    return StateReproach(tuple(denied), tuple(claimed)) if denied or claimed else None


def reproaches_the_state(text: str) -> bool:
    """Ronda 19: ``state_reproach`` reads one («sigue en estándar», «that's not the programmer one»)."""

    return state_reproach(text) is not None


def reproaches_what_was_asked(text: str) -> bool:
    """Ronda 19 (t1-c03 «no wey te pedi 5 nomas, no me sueltes la lista entera»): the person says back what they asked
    («te pedí», «I asked for», data) at the head of a clause. «te pedí que no lo abrieras» forbids; «lo que te pedí
    ayer, ¿lo recuerdas?» asks. Whether it adds anything to what was asked is ``says_only_what_was_asked``."""

    raw = str(text or "")
    if "?" in raw or "¿" in raw:
        return False
    folded = without_correction_interjection(_fold(" ".join(raw.split())))
    return any(_asked_reproach().match(clause) is not None for clause in _clauses(folded))


def _counts_of(text: str) -> set[int]:
    from .listing import counts_said

    return set(counts_said(spelled_out(_fold(str(text or "")))))


def _only_complains(words: list[str], extent: set[str], given: set[str]) -> bool:
    """Ronda 22: a clause that only complains of how much was told («me tiraste una lista enorme», «me tiraste como
    7»): every word is of the complaint (data: count_extent) or a number said after what BAXY handed over (count_given:
    the person's claim of how many, never a count asked). «dame 7», «de terror», «son 6» say something else."""

    handed = False
    for word in words:
        if _counts_of(word) or word.isdigit():
            if not handed:
                return False
        elif word in given:
            handed = True
        elif word not in extent:
            return False
    return True


def says_only_what_was_asked(text: str, request: object, *, counts: Iterable[int] = ()) -> bool:
    """Revisión de la ronda 19: a reproach of what was asked («no wey te pedi 5 nomas, no me sueltes la lista entera»)
    that says nothing the last request did not say — its clause names only the request's words, a count it said (or
    ``counts``) and a limiter («nomás», «only»); the other clauses only complain of how much was told. «te pedí 5 de
    terror, no de acción», «te pedí 5 pero en orden de recaudación», «I asked for 5 comedies not these», «te pedí un
    uber ayer y no llegó», «I asked my boss, now open teams» and «te pedí el bloc de notas» after «abre la
    calculadora» add a restriction or ask something else: never done or answered as the last request."""

    if not reproaches_what_was_asked(text):
        return False
    data = correction_words()
    asked = spelled_out(_fold(str(request or "")))
    allowed_counts = set(counts) | _counts_of(asked)
    known = set(_WORD.findall(asked)) | _NOT_NAMED | set(data["count_limiters"])
    extent = known | set(data["count_extent"])
    links = set(data["asked_reproach_links"])
    given = set(data["count_given"])
    joins = set(data["count_joins"])
    said = False
    for clause in _clauses(spelled_out(without_correction_interjection(_fold(" ".join(str(text or "").split()))))):
        found = None if said else _asked_reproach().match(clause)
        words = _WORD.findall(clause[found.end():] if found is not None else clause)
        # Ronda 22 (t4-c02 «no, te pedi 3 nomas y me tiraste una lista enorme»): a complaint joined to the reproach
        # without a pause is a clause of its own, read as one said apart.
        join = next((index for index, word in enumerate(words) if found is not None and word in joins), None)
        if join is not None:
            words, complaint = words[:join], words[join + 1:]
        else:
            complaint = []
        if complaint and not _only_complains(complaint, extent, given):
            return False
        for index, word in enumerate(words):
            number = _counts_of(word)
            if number or word.isdigit():
                if not number or not number <= allowed_counts:
                    # Ronda 22 (t3-c17 «…, me tiraste como 7, solo 4»): a number said apart is the count asked again,
                    # or what the person says BAXY handed over (``_only_complains``), never a new count asked.
                    if found is not None or not _only_complains(words, extent, given):
                        return False
            elif word in (known | links if found is not None else extent):
                continue
            # «te pedí que abrieras la calculadora» after «abre la calculadora»: the request's own verb, reported.
            elif not (
                found is not None
                and index > 0
                and words[index - 1] in links
                and any(len(other) >= 3 and word[:3] == other[:3] for other in _WORD.findall(asked))
            ):
                return False
        said = said or found is not None
    return said


def _asks_another(folded: str) -> bool:
    return bool(set(_WORD.findall(folded)) & set(correction_words()["another"]))


@dataclass(frozen=True)
class AlreadyHolds:
    """What the correction asks that the last turn already verified: ``kind`` (playing, provider, state, target,
    count) and the verified thing as the result wrote it (``named``: the service the operation reported, as it is
    written, the screen value read) or the number of items told (``count``). A held effect (every kind but count) is
    said with its sentence (data: operation_floor «heldFact»); only a held count is worded by the writer
    (``turn_followups._correction_already_held``)."""

    kind: str
    named: str = ""
    count: int = 0
    # Ronda 22 (kind target): the thing the person refused, which the last turn never touched, as they said it.
    untouched: str = ""
    # Encargo TZ-HOLD (tanda z6 t4-c01 t4): what the verified play reported playing (``observed.title``).
    title: str = ""

    @property
    def effect(self) -> bool:
        """Whether this is a fact the last turn's verified result read (every kind but a count of items told)."""

        return self.kind != "count"

    def facts(self) -> dict[str, str]:
        """The fact for the situation (``alreadyHolds``), strings only."""

        return {
            "kind": self.kind,
            **({"named": self.named} if self.named else {}),
            **({"count": str(self.count)} if self.count else {}),
            **({"untouched": self.untouched} if self.untouched else {}),
            **({"title": self.title} if self.title else {}),
        }


def opens_with_a_denial(reply: object) -> bool:
    """Ronda 24 (r23 t2-c03 #3 «No, cerré la ventana de Configuración que pediste.»): a reply whose first clause is a
    bare denial («No,», «Nope.»; data: correction_words.v1.json, refusals). «No había ventanas abiertas» opens with a
    sentence, never a bare denial."""

    clauses = _clauses(_fold(" ".join(str(reply or "").split())))
    return bool(clauses) and clauses[0] in set(correction_words()["refusals"])


def _refuses_where_named(folded: str, word: str) -> bool:
    """Revisión adversarial 2 de la ronda 19: a clause naming ``word`` that also refuses («no en YouTube», «YouTube
    no», «nunca en YouTube», «not on YouTube») refuses it; only a denial said apart («no, en YouTube») opens a
    correction that names it. Data: correction_words.v1.json, refusals."""

    refusals = set(correction_words()["refusals"])
    return any(
        word in words and bool(set(words) & refusals)
        for words in (_WORD.findall(clause) for clause in _clauses(folded))
    )


# Words of a correction that name no thing: the cue words of a contrast and the heads of a state reproach.
_NOT_NAMED = frozenset(_NOT_CONTRASTED | {"modo", "mode", "es", "sigue", "still", "nomas", "solo", "only", "just"})


def _content_words(folded: str) -> list[str]:
    return [word for word in _WORD.findall(folded) if word not in _NOT_NAMED and not word.isdigit()]


def _screen_parts(observed: dict) -> list[str]:
    """Every text the screen read after a mission showed: its title, its values, its numbers and its lines (ronda 22,
    t3-c18: the mode a window is in is often written as a line, «Calculadora | Programador», no value), as read.

    Revisión 2 de la ronda 22 (bloqueante 1): a line is read only when the excerpt says it is no control's label
    (``controlLines``, ComputerUseMission.ControlLines): «Modo de lectura» under the ribbon's button of that name stays
    written whether or not the mode changed, and the label clicked proves nothing. An excerpt that does not tell its
    labels apart gives no line."""

    screen = observed.get("screen") if isinstance(observed.get("screen"), dict) else {}
    parts: list[str] = [str(screen.get("title") or "")]
    for item in screen.get("values") or []:
        if isinstance(item, dict):
            parts += [str(item.get("name") or ""), str(item.get("value") or "")]
    parts += [str(item) for item in screen.get("numbers") or [] if isinstance(item, str)]
    labels = screen.get("controlLines")
    if isinstance(labels, list):
        marked = {index for index in labels if type(index) is int}
        lines = screen.get("lines") if isinstance(screen.get("lines"), list) else []
        parts += [line for index, line in enumerate(lines) if isinstance(line, str) and index not in marked]
    return [part for part in parts if part.strip()]


def _screen_words(observed: dict) -> set[str]:
    """Every word the screen read after a mission showed."""

    return set(_WORD.findall(_fold(" ".join(_screen_parts(observed)))))


def _shown_as(observed: dict, word: str) -> str:
    """The screen text that shows ``word`` (a folded word), as it was read; empty when none shows it."""

    for part in _screen_parts(observed):
        if word in _WORD.findall(_fold(part)):
            return " ".join(part.split())
    return ""


def correction_already_holds(
    previous: object,
    text: str,
    last_reply: object = None,
    request: object = None,
    *,
    delivered: bool = True,
    touched: Iterable[str] = (),
    acted: bool = False,
) -> AlreadyHolds | None:
    """Ronda 19 (t3-c16 «no, en YouTube» with YouTube already playing → played again; t3-c18 «esa no es la de
    programador wey, sigue en la estandar, cambiala» after the mission reached Programador → four random clicks; a
    «te pedí 5» after five items told): a correction whose thing the last turn's verified result already holds is
    answered with that fact, never done again. ``previous`` is that result (operation, verified, succeeded, observed);
    ``last_reply`` the words BAXY told of it, ``request`` what it was asked. Three facts are compared, each only as
    verified:

    - the provider it ran on (``observed.provider``) named as all the correction says («no, en YouTube»), unless the
      correction refuses it («no en YouTube, en Spotify», «no, en YouTube no», «no, not on YouTube»: a refusal in the
      clause that names it, ``_refuses_where_named``) or asks for another thing («no, otra en YouTube»); it is
      said playing only when ``observed.playbackStatus`` says so;
    - the state a reached mission verified (``observed.satisfiedBy``) denied by a state reproach («esa no es la de
      programador, sigue en la estándar», ``_verified_state_denied``), only when the screen read after it shows the
      denied state (a word of it read there or by the check) and not the claimed one. Revisión adversarial 2: a click
      receipt and the claimed word missing from the screen prove nothing; with no positive read the mission is done
      again (``DialogueState.denied_state_again``). A correction that asks for another state («…, ponla en
      científica») is no state reproach;
    - the number of items told (``listing.items_listed``) equal to the number the reproach says, when the reproach
      says nothing more than that number (``says_only_what_was_asked``).

    None otherwise: «no, en Spotify» after YouTube changes the service, «esa no es la de programador, sigue en la
    estándar» with Estándar on screen is done again, «te pedí 5 de terror» asks for others, «y ahora baja el brillo»
    goes on."""

    from .listing import counts_said, empty_items, given_counts, items_listed, opening_series

    if not corrects_or_insists(text):
        return None
    folded = without_correction_interjection(_fold(" ".join(str(text or "").split())))
    if _asks_another(folded):
        return None
    # Ronda 22 (t3-c17 «no te pedi 4 po, me tiraste como 7, solo 4» after four causes told in conversation, t4-c02 «no,
    # te pedi 3 nomas y me tiraste una lista enorme» after three titles in one sentence): the count told is read in
    # the last answer, whatever turn told it, an operation's or a conversation's. The count asked is the first number
    # that is not what the person says BAXY handed over («me tiraste como 7»).
    # Revisión 1 de la ronda 22: only a last answer that delivered — never a final that told a failure, nor a turn
    # whose operations verified none («Lo siento, no encontré libros y no puedo seguir.» is no three items told).
    claimed = set(given_counts(folded))
    count = next((said for said in counts_said(spelled_out(folded)) if said not in claimed), None)
    # Revisión 2 de la ronda 22: a list with an item that says nothing («1. 2. El bloqueo…») did not tell its count;
    # only items with content are told, so such a list holds no count.
    if count is not None and last_reply and delivered and not empty_items(str(last_reply)):
        told = items_listed(str(last_reply), counted=True) or opening_series(str(last_reply))
        if told == count and says_only_what_was_asked(text, request, counts=(count,)):
            return AlreadyHolds("count", count=count)
    if not isinstance(previous, dict) or previous.get("verified") is not True or previous.get("succeeded") is not True:
        return None
    observed = previous.get("observed") if isinstance(previous.get("observed"), dict) else {}
    words = _content_words(folded)
    contrast = contrastive_correction(text)
    provider = _fold(str(observed.get("provider") or "")).strip()
    if (
        provider
        and not _refuses_where_named(folded, provider)
        and (contrast is None or (contrast.refused != provider and not _order_after(contrast.rest)))
    ):
        if set(words) == {provider} or (contrast is not None and contrast.wanted == provider):
            playing = str(observed.get("playbackStatus") or "").lower() == "playing"
            # Encargo TZ-HOLD (tanda z6 t4-c01 t4): the service as it is written («Spotify») and what plays there.
            return AlreadyHolds(
                "playing" if playing else "provider",
                named=service_name(observed.get("provider")) or str(observed.get("provider")).strip(),
                title=" ".join(str(observed.get("title") or "").split()),
            )
    if acted and contrast is not None and not _order_after(contrast.rest):
        # Ronda 22 (t4-c04 «joder que te he dicho brillo no volumen» right after the brightness was set → set again,
        # and its final vetoed): the wanted thing is what the last turn acted on, and it never touched the refused one.
        # Revisión 1 de la ronda 22 («pon el brillo y el volumen al 40»): the refused thing must be in no step the turn
        # did or tried (``touched``), not only in its last verified result. Revisión 2: the wanted thing is held only by
        # an operation with an effect (``acted``: the catalog's risk of the last verified operation is no read) — a
        # status read of the brightness changed nothing, and the writer is told the turn changed it.
        done = _identity_of(previous) | {_fold(str(item)).strip() for item in touched if str(item).strip()}
        wanted, refused = _target_of(contrast.wanted), _target_of(contrast.refused)
        if wanted and refused and wanted in done and refused not in done:
            return AlreadyHolds("target", named=contrast.wanted, untouched=contrast.refused)
    denied = _verified_state_denied(observed, text)
    if denied is not None:
        claimed, word = denied
        screen = _screen_words(observed)
        read = _read_by_the_check(str(observed.get("satisfiedBy")))
        if not set(claimed) & screen and (word in screen or word in read):
            # Encargo TZ-CAL (tanda z2 t3-c18 t3): the state is named as the check read it on arrival (``arrivedAs``,
            # «Programador»), never the navigation entry that also shows it («Programador Calculadora»).
            arrived = str(observed.get("arrivedAs") or "").strip()
            named = arrived if word in _WORD.findall(_fold(arrived)) else _shown_as(observed, word) or read[word]
            return AlreadyHolds("state", named=named)
    return None


def _verified_state_denied(observed: dict, text: str) -> tuple[tuple[str, ...], str] | None:
    """Encargo TZ-CAL (tandas z1/z2 t3-c18 «esa no es la de programador wey, sigue en la estandar, cambiala» after a
    mission that reached Programador): a state reproach (``state_reproach``) that denies a word, of four letters or
    more, of what a reached mission's check verified (``satisfiedBy``) — as (the states it claims still on, that word).
    Whether the screen read after the mission holds it is ``correction_already_holds``'s; when it does not, the
    mission is done again (``DialogueState.denied_state_again``). None otherwise («ponla en científica» asks another
    state, «sigue en estándar» alone denies nothing verified)."""

    satisfied = observed.get("satisfiedBy")
    reproach = state_reproach(text)
    if observed.get("reached") is not True or not isinstance(satisfied, str) or reproach is None:
        return None
    verified = set(_WORD.findall(_fold(satisfied)))
    word = next((word for word in reproach.denied if len(word) >= 4 and word in verified), None)
    return (reproach.claimed, word) if word is not None else None


# The states of a ``control:`` atom that say the control is on (ComputerUseMission's control states).
_HELD_STATES = frozenset({"selected", "on"})
# The atoms that name a place read on the screen (ComputerUseSuccessCheck.ArrivedAs, less a click's receipt).
_READ_ATOMS = frozenset({"header", "page", "title", "mark"})


def _read_by_the_check(satisfied: str) -> dict[str, str]:
    """Estabilización G3 (tanda f2nb t3-c18 «esa no es la de programador wey, sigue en la estandar, cambiala» after
    «Listo, estoy en «Programador»», satisfied by ``header:programador``): the words the shell's check read on the
    screen itself — a place it read (``header:``, ``page:``, ``title:``, ``mark:``; encargo TZ-CAL, tanda z1:
    ``page:programador``) or a control on or selected (``control:X:selected|on``) — each with the name the atom read.
    The excerpt of the screen (``_screen_parts``) may not carry them (the Calculator's mode is a header no value
    repeats). A click's receipt (``stepDone:``) reads nothing on the screen and gives none."""

    read: dict[str, str] = {}
    for atom in re.split(r"[|&]", satisfied):
        kind, _, rest = atom.strip().partition(":")
        kind = kind.strip().lower()
        if kind == "control":
            name, _, state = rest.rpartition(":")
            if state.strip().lower() not in _HELD_STATES:
                continue
            rest = name
        elif kind not in _READ_ATOMS:
            continue
        name = rest.strip().lstrip("=").strip()
        for word in _WORD.findall(_fold(name)):
            read.setdefault(word, name)
    return read


def _same_answer(shown: str, told: str) -> bool:
    """Revisión 3 de la ronda 22: whether the answer the history shows is the final told, spacing aside (a history
    that keeps only the opening of a long answer still shows it)."""

    seen, said = " ".join(shown.split()), " ".join(told.split())
    return seen == said or (len(seen) >= 200 and said.startswith(seen))


def _attempt_of(situation: dict) -> tuple[str, dict[str, str]] | None:
    """The operation a failed result tried and the arguments it tried (``attempted``: provider, query…), read from
    the result or from the reason of a failed turn; None when it verified, or tried nothing it says."""

    for item in (situation, situation.get("reason")):
        if not isinstance(item, dict) or item.get("verified") is True:
            continue
        operation = str(item.get("operation") or "")
        tried = item.get("attempted")
        if operation and isinstance(tried, dict):
            arguments = {str(key): str(value) for key, value in tried.items() if isinstance(value, str) and value.strip()}
            if arguments:
                return operation, arguments
    return None


def _target_of(word: str) -> str:
    """The identity a person's word names a setting or a device part by (data: correction_words.v1.json,
    target_names): «brillo» → brightness, «volumen» → volume; "" when the word names none of them."""

    folded = _fold(str(word or "")).strip()
    for identity, names in correction_words()["target_names"].items():
        if folded in {_fold(str(name)).strip() for name in names}:
            return identity
    return ""


def _identity_of(previous: dict) -> set[str]:
    """What a verified result says it acted on: the setting, the provider and the application it observed, and the
    parts of its operation's name («audio.volume.set» → audio, volume, set), folded."""

    observed = previous.get("observed") if isinstance(previous.get("observed"), dict) else {}
    found = {_fold(str(observed.get(key) or "")).strip() for key in ("setting", "provider", "appId")}
    found |= {_fold(part).strip() for part in str(previous.get("operation") or "").split(".")}
    return {item for item in found if item}


# Revisión 2 de la ronda 24: the situations a final only asks or talks with (the shell's message.compose kinds).
_ASKING_OR_TALKING_KINDS = frozenset({"clarification", "confirmation", "conversation", "welcome"})


def only_asked_or_talked(situation: object) -> bool:
    """Revisión 2 de la ronda 24 (r23 t2-c04 #2: the shell composed «¿Qué escala específica necesitas en 125?» as
    ``{kind: clarification, polarity: pending}``): whether a final told of this situation ran nothing — a question, a
    confirmation asked, a talk, or anything still pending. Contracaso: an operation's result, done or failed, and a
    mission's, are acts."""

    if not isinstance(situation, dict):
        return False
    kind = str(situation.get("kind") or "").strip().lower()
    polarity = str(situation.get("polarity") or "").strip().lower()
    return kind in _ASKING_OR_TALKING_KINDS or polarity == "pending"


def _may_have_changed(item: dict) -> bool:
    """Revisión 1 de la ronda 24: whether a result, verified or not, may have changed something. Only a result that
    tells it took no step at all (``observed.stepCount`` 0) did not; one that does not tell counts as an act."""

    observed = item.get("observed") if isinstance(item.get("observed"), dict) else {}
    count = observed.get("stepCount")
    return not (isinstance(count, int) and not isinstance(count, bool) and count == 0)


def _normalized_request(request: str) -> str:
    return " ".join(_WORD.findall(_fold(request)))


# What changes between two reads of the same thing without it being another result (when, which receipt), by its
# whole name: «items», «lat», «noteId» or «queryTerms» are results (revisión 2026-10-07).
_VOLATILE_KEYS = frozenset(
    key.lower()
    for key in (
        "at", "utc", "timestamp", "observedAt", "observedAtUtc", "checkedAt", "checkedAtUtc", "retrievedAt",
        "retrievedAtUtc", "elapsedMs", "durationMs", "receiptId", "requestId", "traceId",
    )
)


def _stable(value: object) -> object:
    if isinstance(value, dict):
        return {key: _stable(item) for key, item in value.items() if str(key).lower() not in _VOLATILE_KEYS}
    if isinstance(value, list):
        return [_stable(item) for item in value]
    return value


_NAVIGATIONS = frozenset({"browser.navigate", "browser.navigate.named"})
_READS_OF_THE_PAGE_ON_SHOW = frozenset({"browser.page.read", "browser.tabs.list"})


def _search_words(value: str) -> frozenset[str]:
    """The words of a search, function words (one or two letters), accents and punctuation aside; numbers kept."""

    return frozenset(
        word for word in re.findall(r"[a-z0-9]+", fold(value)) if len(word) > 2 or word.isdigit()
    )


def same_page(left: str, right: str) -> bool:
    """Two addresses name the same page: the same site (``www.`` aside) and path, and every query parameter with the
    same words (``_search_words``)."""

    from urllib.parse import parse_qs, urlparse

    def parts(value: str) -> tuple[str, str, dict[str, frozenset[str]]] | None:
        try:
            parsed = urlparse(value if "://" in value else "https://" + value)
        except ValueError:
            return None
        host = (parsed.hostname or "").casefold()
        host = host[4:] if host.startswith("www.") else host
        query = {key: _search_words(" ".join(values)) for key, values in parse_qs(parsed.query).items()}
        return host, parsed.path.rstrip("/"), query

    one, other = parts(left), parts(right)
    return one is not None and other is not None and bool(one[0]) and one == other


def in_progress(situation: object) -> bool:
    """A progress notice of a turn still running (``cause: acting``), not a result nor a final of the turn."""

    return isinstance(situation, dict) and str(situation.get("cause") or "").strip().lower() == "acting"


def _result_signature(situation: object) -> tuple[str, str] | None:
    """(operation, what it observed) of a verified, succeeded operation result; None for anything else."""

    if not isinstance(situation, dict) or situation.get("verified") is not True or situation.get("succeeded") is not True:
        return None
    operation = str(situation.get("operation") or "")
    if operation not in _PUBLIC_READS:
        return None
    observed = situation.get("observed")
    if not operation or not isinstance(observed, dict) or not observed:
        return None
    return operation, json.dumps(_stable(observed), ensure_ascii=False, sort_keys=True)


def continues(operations: tuple[str, ...], frame: tuple[str, ...], state: DialogueState | None) -> bool:
    """A follow-up's rewrite adds no effect: it reads nothing, only the family it continues, or only lists of
    what this conversation verified («what have I got set?» after a timer and a reminder)."""

    if same_family(operations, frame):
        return True
    return (
        state is not None
        and all(op.endswith(".list") for op in operations)
        and {_family(op) for op in operations} <= state.families
    )


def _said_time(request: str) -> str | None:
    """The day or the hour the person said in a request, in their words («el finde», «a las 7:30»)."""

    said = " ".join(str(request or "").split())
    folded = _fold(said)
    if len(folded) != len(said):
        said = folded
    found = re.search(rf"\b(?:{_DAY}|{_CLOCK})\b", folded)
    return said[found.start(): found.end()] if found is not None else None


# M76 (DEV-D v3l D-w17-t2): «the first one», «el segundo», «la última tarea»: an item of the list just read, by its place.
_ORDINAL_INDEX = {
    r"first|1st|primer|primero|primera": 0,
    r"second|2nd|segundo|segunda": 1,
    r"third|3rd|tercer|tercero|tercera": 2,
    r"fourth|4th|cuarto|cuarta": 3,
    r"fifth|5th|quinto|quinta": 4,
    r"last|ultimo|ultima": -1,
}
_LISTED_POINTER = re.compile(
    r"\b(?:the|el|la|lo)\s+(?P<ordinal>" + "|".join(_ORDINAL_INDEX) + r")\b"
    r"(?!\s+(?:time|vez|day|dia|week|semana|hour|hora|minute|minuto|of\s+(?:the\s+)?month|de(?:l)?\s+mes))"
)


# M102: a move said with a bare number («actually make it 9», «no, mejor 10»), and the words that make a number a clock.
_BARE_RETIME_NUMBER = re.compile(r"(?:^|[\s,])(?:\d{1,2}|" + alternation(frozenset(_NUMBER_WORDS)) + r")[\s.!]*$")
# M148: an alarm set as a timer (named so, or set by a length of time), whose move may give it a new length.
_TIMER_SET = re.compile(
    r"\b(?:timers?|temporizador(?:es)?|countdowns?|count\s*downs?|cuentas?\s+(?:regresivas?|atras))\b|"
    + _RELATIVE_DURATION_PATTERN
)
_CLOCK_SAID = re.compile(r"\d:\d|\b(?:las?|at|am|pm|a\.\s?m|p\.\s?m|o'?clock|en\s+punto|de\s+la\s+(?:manana|tarde|noche))\b")


# M80: the writes whose verified result is the whole task (identity, version, title, details, due).
_TASK_WRITES = ("task.create", "task.update", "task.complete", "task.reopen", "task.restore")
# M160: the note results that say which note the conversation is on (made, read or changed), as verified.
_NOTE_RESULTS = ("note.create", "note.read", "note.update", "note.restore")


@dataclass(frozen=True)
class RetimedNotification:
    """M76: the notification just set, moved: its ``kind`` (the cancellation of the last one takes only it), the
    cancellation of the one at its old local clock as the readers of a cancellation read it, and the arguments of
    ``notification.schedule`` that set it again."""

    kind: str
    cancel_at_request: str | None
    schedule_arguments: dict[str, str]
    # The moment it was read at: the new time is checked to be ahead of that same clock, so one turn uses one «now»
    # (the M76 tests pinned 2026-09-29 and broke on 2026-09-30 against the machine's clock).
    read_at: datetime | None = None
    # M173: how it was set — an alarm or reminder of the Task Scheduler (``notification.schedule``, cancelled with
    # ``notification.cancel.*``) or a reminder of BAXY's own store (``reminder.create``, deleted by its exact title,
    # ``set_title``, and created again).
    set_by: str = "notification.schedule"
    set_title: str = ""
    # M173: when it was to ring, local: a move that names another notice by its clock is not of this one.
    set_at: datetime | None = None
    # r19b (t1-c04-2 «no, mejor a las nueve y media» → reminder_ambiguous): the id ``reminder.create`` verified, so
    # the move resolves that reminder and never another of the same title made elsewhere; "" when none was verified.
    set_id: str = ""

    @property
    def moving_operations(self) -> tuple[str, str]:
        """M173: the plan that moves it, by how it was set: the latest of its kind cancelled and set again, or the
        reminder of the store deleted and created again. Never another notice."""

        if self.set_by == "reminder.create":
            return ("reminder.delete", "reminder.create")
        return ("notification.cancel.latest", "notification.schedule")


class DialogueState:
    """What the conversation left for the next follow-up. The serve loop owns one and passes it in.

    Two parts, as a person keeps them. The last turn: the request it decided, in the person's words as completed,
    whatever came of it (an answer, a question, an effect), with the operations it was about and those of them
    verified. And the last thing of each kind any turn verified (place, day, what plays, the alarm and the
    reminder set, the topic searched, a level). Tanda 8: the state followed only verified turns, so after an answer
    or a question the last request was an older one («ábreme la calculadora» for «y eso por 12?») and a correction
    of the alarm still being asked for was judged against it.

    ``expect`` is told every turn's decided request and its operations (the effects, or those a question was
    about); ``record`` is given the situation of each composed result and keeps it only when the operation was one
    of the last turn's, verified and succeeded. Never written from BAXY's text. A new conversation starts it over
    (``reset``).
    """

    _LABELS = (
        ("request", "último pedido hecho (last request done)"),
        ("place", "lugar (place)"),
        ("day", "día u hora pedidos (day or time asked)"),
        ("playing", "canción sonando (song playing)"),
        ("asked_to_play", "música pedida (music asked for)"),
        ("alarm", "alarma o temporizador creado (alarm or timer set)"),
        ("reminder", "recordatorio creado (reminder set)"),
        ("topic", "tema buscado (topic searched)"),
        ("volume", "volumen (volume)"),
        ("brightness", "brillo (brightness)"),
    )

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.request: str | None = None  # the last turn's request
        self.intended: tuple[str, ...] = ()  # the operations the last turn was about
        self.operations: tuple[str, ...] = ()  # those of them verified
        self.families: set[str] = set()  # every family this conversation verified
        self._facts: dict[str, str] = {}
        self._alarm_offer: tuple[tuple[int, int], ...] = ()  # D39: the alarms read for «cancela las alarmas»
        self.previous_operations: tuple[str, ...] = ()  # M76: what the turn before the last one verified
        self._notification: dict[str, str] | None = None  # M76: the alarm, timer or reminder set, as verified
        self._listed: tuple[str, ...] = ()  # M76: the titles of the tasks read, in the order they were told
        self._task: dict[str, object] | None = None  # M80: the task last created or changed, as verified
        # M174: every task this conversation created or changed (an entry put on a list in a plan too), as verified.
        self._entries: dict[str, dict[str, object]] = {}
        self._note: str | None = None  # M160: the title of the note last made, read or changed, as verified
        self._headlines: tuple[str, ...] = ()  # M83: the headlines read, in the order they were told
        # M145: every alarm, timer or reminder this conversation set and has not cancelled, as verified, in order.
        self._own_notifications: list[dict[str, str]] = []
        # Uso real 2026-10-07: the last operation result told (operation, what it observed) and the words told of it.
        self._told: tuple[str, str, str] | None = None
        # Uso real v3 t2 (c03-2, c04-4): the words of the last final told, whatever its result.
        self._last_final: str | None = None
        # Ronda 20 P3 (v3-11 t2): whether the last final told was a failure (or a mission that did not reach its place),
        # and the window that same final observed. A new request clears both: its final is not told yet (revisión 1,
        # hallazgo 4: a window of a turn before is never named as the one the failed request left).
        self._last_final_failed = False
        self._last_window: str | None = None
        # Semilla fix2: the address the last verified navigation showed in the person's browser, until another act.
        self._on_show: str | None = None
        # The search on show this turn reads instead of opening it again (``reads_on_show``).
        self.reading_on_show: str | None = None
        # Ronda 19: the last turn's verified result, for a correction it already holds (``already_holds``).
        self._last_verified: dict | None = None
        # Ronda 22: the operation the last turn tried and could not verify, and the arguments it tried
        # (``attempted_again``).
        self._last_attempt: tuple[str, dict[str, str]] | None = None
        # Revisión 1 de la ronda 22: the identity of every step the last request did or tried (``_identity_of``), for a
        # correction that says what it did not touch (``already_holds``, kind target).
        self._touched: set[str] = set()
        # Revisión 1 de la ronda 24: every operation this conversation verified or tried that may have changed
        # something (``_may_have_changed``), whatever turn it was; ``undo_of_nothing`` never says nothing changed past
        # one of them. And the last request that was about an operation, the one an undo of nothing names.
        self._conversation_acts: set[str] = set()
        self._acting_request: str | None = None
        # Estabilización G3 (tanda f2nb t2-c04 #3): what the last request about an operation did or tried that may have
        # changed something, and what any turn verified that did; an undo of a request that did nothing is told so
        # past a request before it that only tried (``undo_of_nothing``).
        self._acting_did: set[str] = set()
        self._verified_changes: set[str] = set()
        # Revisión 3 de la ronda 22: whether ``_last_final`` is the final of the last request (``expect``), told of it
        # (``told``) or said by it in conversation (``said``); a final of a request before counts nothing told now.
        self._final_of_request = False
        # Ronda 24 (r23 t2-c03 #3 «no bro cerraste el que no era…» after a turn that only asked → «No, cerré…»):
        # whether ``_last_final`` told an operation's result (``told``), not a question or a talk (``said``).
        self._last_final_acted = False
        # Estabilización B2: the send a follow-up's draft may offer (recipient, words, client or None), the same once its
        # draft is verified (client, recipient, words), and once the final told it (the request a yes is, the question),
        # which only the next turn reads (``begin_turn``; revisión B2 H3).
        self._send_offer: tuple[str, str, str | None] | None = None
        self._send_ready: tuple[str, str, str] | None = None
        self._send_offered: tuple[str, str] | None = None
        self._send_now: tuple[str, str] | None = None
        # Encargo E (banco i1 c6): whether the last final told a send verified (``yes_after_a_send``).
        self._told_send = False

    def expect(self, request: str, operations: object) -> None:
        if self.operations and not set(self.operations) & set(_TASK_WRITES):
            # M80: another effect done after the task leaves «cámbialo» without that task; a question does not.
            self._task = None
        if self.operations and not set(self.operations) & set(_NOTE_RESULTS):
            # M160: as M80, another effect done after the note leaves «agrégale…» without that note.
            self._note = None
        self.previous_operations = self.operations
        self.request = str(request or "").strip() or None
        self.intended = tuple(str(op) for op in operations) if isinstance(operations, (list, tuple)) else ()
        if self.intended and self.request is not None:
            self._acting_request = self.request
            self._acting_did = set()
        self.operations = ()
        self._facts.pop("request", None)
        # D39: the offer to cancel the alarms read stands only for the turn right after it.
        self._alarm_offer = ()
        # Estabilización B2: as D39, the offer to send stands only for the turn right after the final that told it.
        self._send_offer = self._send_ready = self._send_offered = self._send_now = None
        self._told_send = False
        self._last_verified = None
        self._last_attempt = None
        self._touched = set()
        self._final_of_request = False
        self._last_final_failed = False
        self._last_window = None

    def record(self, situation: object) -> None:
        if not isinstance(situation, dict) or self.request is None:
            return
        for step in _verified_steps(situation):
            self._keep_own_notification(step)
            self._keep_entry(step)
        operation = str(situation.get("operation") or "")
        for item in (situation, situation.get("reason"), *(situation.get("steps") or () if isinstance(
            situation.get("steps"), list
        ) else ())):
            # Revisión 1 de la ronda 22: what the turn did or tried, verified or not, each step of a chain included.
            if isinstance(item, str):
                try:
                    item = json.loads(item)
                except json.JSONDecodeError:
                    continue
            if isinstance(item, dict) and item.get("operation"):
                self._touched |= _identity_of(item)
                if _may_have_changed(item):
                    self._conversation_acts.add(str(item.get("operation")))
                    self._acting_did.add(str(item.get("operation")))
                    if item.get("verified") is True and item.get("succeeded") is True:
                        self._verified_changes.add(str(item.get("operation")))
        attempt = _attempt_of(situation)
        if attempt is not None and attempt[0] in self.intended:
            # Ronda 22 (t4-c01): what the last request tried and could not verify, by its own arguments.
            self._last_attempt = attempt
        if (
            operation not in self.intended
            or situation.get("verified") is not True
            or situation.get("succeeded") is not True
        ):
            return
        request = self.request
        observed = situation.get("observed") if isinstance(situation.get("observed"), dict) else {}
        self.operations = tuple(dict.fromkeys((*self.operations, operation)))
        self._last_verified = situation
        self._facts["request"] = request
        family = _family(operation)
        self.families.add(family)
        said_time = _said_time(request)
        if family in {"weather", "notification", "reminder", "calendar"} and said_time:
            self._facts["day"] = said_time
        # Tanda 8 «y si allá son las 9 de la noche, qué hora es acá» after «qué hora es en Madrid» was rewritten with
        # Bilbao, a weather read two turns before: a clock read elsewhere names a place too, and the last one wins.
        seen = observed if family == "weather" else observed.get("place") if operation == "system.time" else None
        place = ", ".join(str(seen[key]) for key in ("location", "name", "region", "country") if seen.get(key)) if (
            isinstance(seen, dict)
        ) else ""
        if place:
            self._facts["place"] = place
        if family == "media":
            title, artist = str(observed.get("title") or "").strip(), str(observed.get("artist") or "").strip()
            if title:
                self._facts["playing"] = f"{title} — {artist}" if artist and artist not in title else title
            if observed.get("query"):
                self._facts["asked_to_play"] = str(observed["query"])
        elif operation == "notification.schedule":
            noun = _SCHEDULED_NOUN.search(_fold(request))
            parts = [str(observed.get("title") or request)]
            parts += [f"{observed['dueUtc']} UTC"] if observed.get("dueUtc") else []
            parts += [f"id {observed['taskName']}"] if observed.get("taskName") else []
            self._facts["alarm"] = ", ".join(parts)
            self._facts["alarm_noun"] = noun.group(0) if noun is not None else "alarm"
            if all(isinstance(observed.get(key), str) and observed[key] for key in ("kind", "title", "dueUtc")):
                self._notification = {key: observed[key] for key in ("kind", "title", "dueUtc")}
                # M113: the request that set it, for a later «mejor media hora antes» counted from the same moment.
                self._notification["request"] = request
                self._notification["set_by"] = operation
        elif operation == "reminder.create":
            self._facts["reminder"] = str(observed.get("title") or request)
            if (
                all(isinstance(observed.get(key), str) and observed[key].strip() for key in ("title", "dueUtc"))
                and not observed.get("deleted")
            ):
                # M173 (DEV-F v5c F-w55-t2 «no, mejor media hora antes, una hora es mucho», DEV-I v5c I-w04-t2 «actually
                # make it half three», each right after a reminder BAXY made with reminder.create → «¿A qué hora y qué
                # tipo de notificación…?»): the reminder of the store just made is the notice the conversation moves, as
                # an alarm set by notification.schedule is; it is moved by its own operations (deleted by its exact
                # title, created again), never by notification.cancel.*, which reads only the Task Scheduler.
                self._notification = {
                    "kind": "reminder", "title": observed["title"], "dueUtc": observed["dueUtc"], "request": request,
                    "set_by": operation,
                }
                if isinstance(observed.get("reminderId"), str) and observed["reminderId"].strip():
                    # r19b: the reminder made is that id, whatever other reminders share its title.
                    self._notification["id"] = observed["reminderId"]
        elif operation == "notification.list" and plural_alarm_cancellation(request):
            self._alarm_offer = _alarm_clocks(observed)
        elif operation == "message.draft" and self._send_offer is not None:
            # Estabilización B2: the draft left for the recipient the offer names, in its client, and in a client the
            # readers can send through again.
            recipient, words, client = self._send_offer
            channel = str(observed.get("channel") or "")
            if (
                fold(str(observed.get("displayName") or "")) == fold(recipient)
                and channel in {"discord", "whatsapp"}
                and client in {None, channel}
            ):
                self._send_ready = (channel, recipient, words)
        elif operation in _TASK_WRITES:
            # M80 (DEV-D v3m D-p06-t2, D-p08-t3): the task as the store verified it after the write, for a change of
            # it in the next turns that says only what changes.
            if (
                isinstance(observed.get("taskId"), str)
                and isinstance(observed.get("title"), str)
                and isinstance(observed.get("version"), int)
                and not observed.get("deleted")
            ):
                self._task = _verified_task(observed)
        elif operation in _NOTE_RESULTS:
            # M160 (DEV-G v4w G-w12-t2 «agrégale que quiero comprarle un ramo de flores» right after the note was made):
            # the note the conversation is on, by the title the store verified, for an addition that names no note.
            title = observed.get("title")
            self._note = title.strip() if isinstance(title, str) and title.strip() and not observed.get("isTrashed") else None
        elif operation in {"task.list", "task.search"} and isinstance(observed.get("tasks"), list):
            # M76 (DEV-D v3l D-w17-t2): the tasks read, in the order they were told, for «the first one».
            self._listed = tuple(
                str(task["title"]) for task in observed["tasks"]
                if isinstance(task, dict) and isinstance(task.get("title"), str) and task["title"].strip()
            )
        elif operation == "web.search" and observed.get("query"):
            self._facts["topic"] = str(observed["query"])
        elif operation == "web.news.headlines" and isinstance(observed.get("headlines"), list):
            # M83 (DEV-D v3o D-w17-t5 «tell me more about the second one»): the headlines read, in the order they
            # were told, for «the second one».
            self._headlines = tuple(
                str(item["title"]).strip() for item in observed["headlines"]
                if isinstance(item, dict) and isinstance(item.get("title"), str) and item["title"].strip()
            )
        elif operation in {"audio.volume", "audio.volume.adjust"} and observed.get("level") is not None:
            self._facts["volume"] = str(observed["level"])
        elif operation.startswith("system.settings") and observed.get("setting") and observed.get("value") is not None:
            self._facts[str(observed["setting"])] = str(observed["value"])

    def _keep_entry(self, step: dict) -> None:
        """M174: a task this conversation created or changed, alone or as a step of a plan, as the store verified it
        after the write; a task trashed is no entry any more."""

        operation = str(step.get("operation") or "")
        observed = step.get("observed") if isinstance(step.get("observed"), dict) else {}
        task_id = observed.get("taskId")
        if operation not in _TASK_WRITES + ("task.delete",) or not isinstance(task_id, str):
            return
        if observed.get("deleted") or operation == "task.delete":
            self._entries.pop(task_id, None)
            return
        if isinstance(observed.get("title"), str) and isinstance(observed.get("version"), int):
            self._entries.pop(task_id, None)
            self._entries[task_id] = _verified_task(observed)

    def _keep_own_notification(self, step: dict) -> None:
        """M145: a verified setting of an alarm, a timer or a reminder is this conversation's own; a verified cancel
        takes the one it names (its task) off. A cancel that does not say which one leaves nothing known as own."""

        operation = str(step.get("operation") or "")
        observed = step.get("observed") if isinstance(step.get("observed"), dict) else {}
        if operation == "notification.schedule":
            kind, due = observed.get("kind"), observed.get("dueUtc")
            if kind in {"alarm", "reminder"} and isinstance(due, str) and _instant(due) is not None:
                task = str(observed.get("taskName") or "")
                self._own_notifications = [
                    entry for entry in self._own_notifications
                    if not (task and entry["taskName"] == task)
                ] + [{"kind": kind, "dueUtc": due, "taskName": task}]
        elif operation.startswith("notification.cancel"):
            task = str(observed.get("taskName") or "")
            known = [entry for entry in self._own_notifications if entry["taskName"]]
            if task and len(known) == len(self._own_notifications):
                self._own_notifications = [entry for entry in known if entry["taskName"] != task]
            else:
                self._own_notifications = []

    def own_notification_at(
        self, kind: str, hour: int | None, minute: int = 0, period: str | None = None, *,
        now: datetime | None = None, zone: timezone | None = None,
    ) -> bool:
        """M145 (DEV-H v4p H-w29-t2 «no espera, mejor a las 7:30» after this conversation set its alarm at 19:00, H-w45-t4
        «cancel the 7 one»): whether the clock a cancellation names (as ``notification.cancel.at`` selects it: a clock
        without its part of the day is either one) is that of the alarm, timer or reminder of that kind this
        conversation set last, still to ring, and of no other one it set. Then that one is the latest BAXY set of its
        kind (``notification.cancel.latest``), and the others in the store at the same clock are not it. ``hour`` None:
        a move that names no clock («Cambia el recordatorio para el jueves a las 15:30») is of the last one set; it
        holds when that one is still to ring."""

        moment = now or datetime.now(timezone.utc)

        def pending_at(entry: dict[str, str]) -> bool:
            when = _instant(entry["dueUtc"])
            if when is None or when <= moment:
                return False
            if hour is None:
                return entry is own[-1]
            local = when.astimezone(zone)
            if period in {"am", "pm"}:
                wanted = hour % 12 + (12 if period == "pm" else 0)
                hour_holds = local.hour == wanted
            else:
                hour_holds = local.hour % 12 == hour % 12 if hour <= 12 else local.hour == hour
            return hour_holds and local.minute == minute

        own = [entry for entry in self._own_notifications if entry["kind"] == kind]
        return bool(own) and pending_at(own[-1]) and sum(pending_at(entry) for entry in own) == 1

    def understood(self, user_text: str, situation: object) -> str:
        """The request a composed result answers: the last turn's, as the mind understood it, when the result is
        of one of its operations; the person's text otherwise.

        Tanda 7b: «¿y el finde?» was decided as «che, ¿va a llover el finde?», but its weather read was worded
        against the bare fragment, so every draft about the weekend died on missing_state (⚠), and «¿y en Mar del
        Plata?» was answered with today's weather.
        """

        operation = str(situation.get("operation") or "") if isinstance(situation, dict) else ""
        # The joined form of an answer the model could not rewrite («…\nAclaración confiable del usuario: …») is
        # for the readers, not a request to word against.
        if not self.request or "\n" in self.request:
            return user_text
        if not operation and isinstance(situation, dict) and situation.get("cause") == "mission_failed" and self.intended:
            # M58 (v3d-final F-w06-t2 «no, al revés» → «No se pudo abrir Word ni Google Chrome»): a failed plan is the
            # mission this turn decided («Coloca la ventana de Word en la mitad derecha…»); its failure is told
            # against that request, which names the act asked, not against the bare correction.
            return self.request
        if not operation or operation not in self.intended:
            return user_text
        return self.request

    def insisted_search(self, text: str) -> str | None:
        """M103 (owner script t25 «…te dije que investigues algo, eso debería ir a web search…» after a search → «¿Qué
        tema … te gustaría que investiguemos?»): the person insisting that what they asked to look up be looked up,
        naming nothing new, asks for the topic this conversation last searched, as one request every reader reads.
        None with nothing searched, or when the message names something of its own to look up."""

        topic = self._facts.get("topic")
        if not topic or not insists_on_searching(text):
            return None
        return f"busca en la web {topic}" if spanish(text) else f"search the web for {topic}"

    def searched_topic(self) -> str | None:
        """M179: what this conversation last searched, as the search verified it; None with nothing searched."""

        return self._facts.get("topic")

    def searched_in_place(self, text: str) -> str | None:
        """Uso real 2026-10-07 («ok pero lo puedes buscar en google…» after a web search): the thing looked up said as
        a pronoun, with the engine or the browser named as the place, is what this conversation last searched, opened
        there, as one request every reader reads. None with nothing searched («búscalo en Google» alone asks what), or
        when the message names its own thing to look up or forbids the search."""

        place = pronoun_search_place(text)
        if place is None:
            return None
        # Ronda 24, revisión 2 (r23 t3-c17 t4 «buscalo en google pa poder citarlo» after an answer about «La invasión
        # de Bélgica por Alemania»): when the last request was answered in conversation (no operation), the pronoun
        # points at what that answer was about (``answer_subject``); otherwise at what this conversation last searched.
        answered = answer_subject(self._last_final or "") if self._final_of_request and not self.intended else None
        topic = answered or self._facts.get("topic")
        if not topic:
            return None
        # Spanglish («…no me importa the ice») and an English pronoun over a Spanish topic read in Spanish.
        in_spanish = spanish(text) or spanish(topic)
        if place == "google":
            return f"busca en google {topic}" if in_spanish else f"search on google for {topic}"
        return f"busca {topic} en mi navegador" if in_spanish else f"search for {topic} in my browser"

    def already_holds(
        self, text: str, *, risk_of: Callable[[str], str | None] | None = None, shown: object = None
    ) -> AlreadyHolds | None:
        """Ronda 19 (t3-c16 «no, en YouTube» with YouTube playing, t3-c18 «…sigue en la estandar, cambiala» with
        Programador read on screen): the fact that the correction already holds in what the last turn verified
        (``correction_already_holds``), never doing it again; a held effect is said with its sentence, a held count
        is worded by the writer. None when it does not hold or nothing was verified."""

        # Revisión 1 de la ronda 22: a count is held only by a last turn that delivered — its final told no failure and,
        # when it was about operations, one of them verified.
        delivered = not self._last_final_failed and (not self.intended or bool(self.operations))
        touched = self._touched | {
            part for operation in (*self.intended, *self.operations) for part in str(operation).split(".") if part
        }
        # Revisión 2 de la ronda 22: the last verified operation acted only when the catalog says its risk, and it is
        # no read (``risk_of``, the tools' risk); unknown, nothing is held as done.
        last = str((self._last_verified or {}).get("operation") or "")
        risk = risk_of(last) if risk_of is not None and last else None
        acted = isinstance(risk, str) and bool(risk) and risk != "read_only"
        # Revisión 3 de la ronda 22: the count is read only in the final of the last request, and only when it is what
        # the person last saw (``shown``: the last answer of the history, when the turn carries one) — a final of a
        # request before, or one the shell did not publish, counts nothing.
        reply = self._last_final if self._final_of_request else None
        if reply and isinstance(shown, str) and shown.strip() and not _same_answer(shown, reply):
            reply = None
        return correction_already_holds(
            self._last_verified, text, reply, self.request, delivered=delivered, touched=touched,
            acted=acted,
        )

    def denied_state_again(self, text: str) -> str | None:
        """Encargo TZ-CAL (tanda z1 t3-c18 «esa no es la de programador wey, sigue en la estandar, cambiala»: the engine
        got the reproach's own words as its goal and pressed «Operadores estándar»): a state reproach that denies what
        the last turn's reached mission verified (``_verified_state_denied``), when the screen read after it does not
        hold it (``already_holds`` is asked first), is that mission's request done again — the engine reads the window
        and tells whether the state is on. None otherwise."""

        previous = self._last_verified
        if not self.request or not isinstance(previous, dict) or previous.get("succeeded") is not True:
            return None
        observed = previous.get("observed") if isinstance(previous.get("observed"), dict) else {}
        return self.request if previous.get("verified") is True and _verified_state_denied(observed, text) else None

    def attempted_again(self, text: str) -> tuple[str, str, tuple[tuple[str, str], ...]] | None:
        """Ronda 22 (t4-c01 «no po, en spotify te dije, no en youtube» after «ponme cumbia» was tried in Spotify and
        could not be verified → tried again with «cumbia mientras»): a correction that names, as all it asks, the
        provider the last request already tried is that same try again — the request as this conversation understood
        it, its operation and the arguments it tried — never the person's raw words rebuilt. None when nothing was
        tried, when the correction refuses that provider («no en Spotify, en YouTube»), names another one («no, en
        YouTube» after Spotify) or asks for something else («otra en Spotify»)."""

        if self._last_attempt is None or not self.request or not corrects_or_insists(text):
            return None
        operation, tried = self._last_attempt
        provider = _fold(tried.get("provider", "")).strip()
        folded = without_correction_interjection(_fold(" ".join(str(text or "").split())))
        if not provider or _asks_another(folded) or _refuses_where_named(folded, provider):
            return None
        contrast = contrastive_correction(text)
        if contrast is not None:
            if contrast.wanted != provider or contrast.refused == provider or _order_after(contrast.rest):
                return None
        elif set(_content_words(folded)) != {provider}:
            return None
        return self.request, operation, tuple(sorted(tried.items()))

    def undelivered_reproach(self, text: str) -> tuple[str, str] | None:
        """Ronda 19 (t1-c03 «no wey te pedi 5 nomas…» after «No lo encontré.» → «¿Podrías decirme solo los 5
        títulos…?»): the person says back what they asked of a last turn that failed or did not deliver it; that turn
        is done again, as (its one operation, its request), instead of asking them for it. Not delivered: none of
        its operations verified, or a count asked that the last final did not list. None otherwise («te pedí que no
        lo abrieras» forbids; after five items told, «te pedí 5» already holds). Revisión de la ronda 19: only a
        reproach that says nothing the request did not («te pedí el bloc de notas, no la calculadora» after «abre la
        calculadora», «te pedí un uber ayer y no llegó»): the request done again would lose what it adds
        (``says_only_what_was_asked``)."""

        from .listing import count_said, items_listed, listing_asked

        if not self.request or len(self.intended) != 1 or not says_only_what_was_asked(text, self.request):
            return None
        if self.operations:
            asked = listing_asked(self.request)
            count = asked.count if asked is not None and asked.count is not None else count_said(_fold(text))
            if count is None or (items_listed(self._last_final or "") or 0) >= count:
                return None
        return self.intended[0], self.request

    def repeats_the_last_plan(self, operations: object, request: object, text: str) -> bool:
        """Uso real 2026-10-07 («si pero quiero buscar un top 3» → the same search, the same result, the same words): a
        correction or an insistence decided as exactly what the last turn did — the same operations on the same request
        — is not done again. «otra vez» asks for it again and is not a correction; «sí, dale» to an offer is not either."""

        decided = tuple(str(op) for op in operations) if isinstance(operations, (list, tuple)) else ()
        if not decided or not set(decided) <= _PUBLIC_READS:
            # Revisión 2026-10-07: «no, te dije que abras el bloc de notas» after it opened is done, not remarked on.
            return False
        if not self.operations or set(decided) != set(self.operations) or not self.request:
            return False
        if not corrects_or_insists(text):
            return False
        return _normalized_request(str(request or "")) == _normalized_request(self.request)

    def same_result_again(self, situation: object, text: str) -> str | None:
        """Uso real 2026-10-07: the words BAXY told of the last result, when this result is the same operation with the
        same observation and the person was correcting or insisting; the writer must not tell it again in those words
        (``sameResultAgain``). None otherwise: «¿y ahora cuánto está el dólar?» may get the same figure again."""

        told = self._told
        signature = _result_signature(situation)
        if told is None or signature is None or signature != told[:2] or not corrects_or_insists(text):
            return None
        return told[2]

    def told(self, situation: object, reply: str) -> None:
        """The words told of an operation result, kept beside what it observed for ``same_result_again``. A progress
        notice worded while the operation still runs («Estoy trabajando en la solicitud.») is no final: semilla r8 t3
        repeated t2's final word for word because t3's own notice had taken its place as the last final."""

        if in_progress(situation):
            return
        self._keep_on_show(situation)
        self._keep_final_outcome(situation)
        signature = _result_signature(situation)
        if signature is not None and str(reply or "").strip():
            self._told = (*signature, str(reply).strip())
        if str(reply or "").strip():
            self._last_final = str(reply).strip()
            self._final_of_request = True
            # Revisión 2 de la ronda 24 (r23 t2-c04 #2 «¿Qué escala específica necesitas en 125?» composed by the
            # shell as {kind: clarification, polarity: pending}): a question or a talk told is no act.
            self._last_final_acted = not only_asked_or_talked(situation)
            self._told_send = messaging.verified_send(situation)

    def said(self, reply: object) -> None:
        """Revisión 3 de la ronda 22: the reply a conversation turn carries is published by the shell as it is, never
        through message.compose (``told``); it is the last final of its request all the same («dame 3 chistes» after a
        list of games: a later «te pedí 3 nomás» is about the jokes, never the games). Ronda 24: a question the turn
        asked instead of acting is its final too (r23 t2-c03 #2 «¿Te gustaría que cierre la configuración…?»)."""

        if str(reply or "").strip():
            self._last_final = str(reply).strip()
            self._final_of_request = True
            self._last_final_acted = False
            self._told_send = False

    def last_final_acted(self) -> bool:
        """Ronda 24: whether the last final told an operation's result (done or failed); False after a question or a
        talk, which ran nothing."""

        return self._last_final_acted

    def undo_of_nothing(self, text: str, *, risk_of: Callable[[str], str | None] | None = None) -> str | None:
        """Ronda 24 (r23 t2-c04 #3 «no espera se ve muy grande, regresala como estaba» after a turn that only asked
        «¿Qué escala…?» → eleven blind clicks in 29,5 s): an undo (``asks_to_undo``) whose antecedent changed nothing —
        the last request verified no operation with an effect and tried none, and the request before it verified none
        either — is answered with that fact; nothing is put back. Returns the last request (what changed nothing), or
        None. Contracaso: after a verified brightness change («sube el brillo» → «regrésalo como estaba»), or a change
        two turns back with a read between, the undo is decided as before. An operation whose risk the catalog does
        not tell (``risk_of``) counts as an effect. Revisión 1 de la ronda 24: any turn of the conversation counts, not
        only the last two (a change three turns back, a mission that clicked without verifying before a talk), and
        what changed nothing is the last request about an operation, never a «gracias» said after it. Revisión 4 de la
        ronda 24: only an undo that is all the message says (``only_undoes``; «deshazlo y abre spotify» is decided as
        before, its order never lost), and only after a request about an operation (``_acting_request``): after a
        «hola» alone there is nothing of BAXY's to put back, and nothing is said unverified."""

        if self._acting_request is None or not only_undoes(text) or self._touched:
            return None

        def effect(operation: str) -> bool:
            risk = risk_of(operation) if risk_of is not None else None
            return not (isinstance(risk, str) and risk == "read_only")

        if not any(
            effect(str(operation))
            for operation in (*self.operations, *self.previous_operations, *sorted(self._conversation_acts))
        ):
            return self._acting_request
        # Estabilización G3 (tanda f2nb t2-c04 #3: «abre configuracion y ve a pantalla» failed after unverified clicks,
        # «ahi ponle la escala en 125» was only asked about, and the undo went to the engine, which pressed the theme
        # «Windows (oscuro)» twice): the undo is of the last request about an operation; when that one did and tried
        # nothing (a question, a failure without a step) and no turn verified a change, there is nothing of it to put
        # back. A request before it that only tried is no change this undo names.
        if self._acting_did or any(
            effect(str(operation))
            for operation in (*self.operations, *self.previous_operations, *sorted(self._verified_changes))
        ):
            return None
        return self._acting_request

    def _keep_final_outcome(self, situation: object) -> None:
        """Ronda 20 P3: whether this final told a failure (``polarity: failure``, or a mission whose ``reached`` is
        false) and the window its own observation named (none when it observed none), kept for ``antecedent_failed``."""

        if not isinstance(situation, dict):
            return
        observed = situation.get("observed") if isinstance(situation.get("observed"), dict) else {}
        reason = situation.get("reason") if isinstance(situation.get("reason"), dict) else {}
        self._last_final_failed = (
            str(situation.get("polarity") or "").strip().lower() == "failure"
            or situation.get("succeeded") is False
            or observed.get("reached") is False
        )
        self._last_window = None
        for seen in (observed, reason.get("observed") if isinstance(reason.get("observed"), dict) else {}):
            window = next(
                (str(seen[key]).strip() for key in ("windowTitle", "application") if str(seen.get(key) or "").strip()),
                None,
            )
            if window is not None:
                self._last_window = window[:120]
                break

    def antecedent_failed(self, text: str, slot: DialogueSlot) -> str | None:
        """Ronda 20 P3 (pasada r18, v3-11 t2: «escribe ahí: comprar pan, leche y huevos» after «en onenote crea una
        pagina nueva» was told as failed, and the text went into the title of a page that already existed): the
        person's request before, when this message puts what it asks in a place it only points back to
        (``points_back_to_a_place``) and the last final told of that request was a failure. That place is the
        product of a request that never made it; whatever window is open is no answer to «ahí». None otherwise: after
        «Listo, creé la página» the same words act, and a first message has no request before."""

        if not self._last_final_failed or not slot.antecedents or not points_back_to_a_place(text):
            return None
        return slot.antecedents[0]

    def last_window(self) -> str | None:
        """The window the last final observed (its title, else its application), or None: never one of a turn before."""

        return self._last_window

    def _keep_on_show(self, situation: object) -> None:
        """A verified navigation leaves its address on show; any other act (a read of it aside) may have changed what
        the browser shows, so nothing is held on show after it."""

        if not isinstance(situation, dict):
            return
        operation = str(situation.get("operation") or "")
        observed = situation.get("observed") if isinstance(situation.get("observed"), dict) else {}
        if (
            operation in _NAVIGATIONS
            and situation.get("verified") is True
            and situation.get("succeeded") is True
            and isinstance(address := observed.get("requestedUrl") or observed.get("finalUrl"), str)
        ):
            self._on_show = address
        elif operation and operation not in _READS_OF_THE_PAGE_ON_SHOW:
            self._on_show = None
        elif not operation:
            reason = situation.get("reason") if isinstance(situation.get("reason"), dict) else {}
            steps = situation.get("steps") if isinstance(situation.get("steps"), list) else []
            acted = {str(item.get("operation") or "") for item in (reason, *steps) if isinstance(item, dict)} - {""}
            if acted - _READS_OF_THE_PAGE_ON_SHOW:
                self._on_show = None

    def on_show(self, address: object) -> str | None:
        """Semilla fix2 («si pero quiero buscar un top 3», «ok pero lo puedes buscar en google…» after that search was
        opened and verified): the address on show, when ``address`` is the same page — the same site and path, and a
        search with the same words (function words, accents and punctuation aside). None otherwise."""

        if self._on_show is None or not isinstance(address, str):
            return None
        return self._on_show if same_page(address, self._on_show) else None

    def final_before_correction(self, situation: object, text: str) -> str | None:
        """Uso real v3 t2 (c03-2 «no bro cerraste el que no era, te dije CHROME» → «No se cerró Chrome porque no tenía
        ninguna ventana abierta.» again; c04-4 the same mission failure again): the words of the last final told, when
        the person corrects or reproaches it and this result is not the same read found again (``same_result_again``
        tells that one). The writer must answer the correction, never tell those words again. None otherwise: a
        follow-up that goes on («y ahora baja el brillo») may get any words."""

        if self._last_final is None or not corrects_or_insists(text) or self.same_result_again(situation, text):
            return None
        return self._last_final

    def last_final(self) -> str | None:
        """The last final BAXY told, whatever it was of (``already_holds`` gives it to the writer not to repeat)."""

        return self._last_final

    def last_told(self) -> str | None:
        """The words BAXY told of the last operation result; None before any."""

        return self._told[2] if self._told is not None else None

    def accepted_alarm_cancellation(self, text: str) -> str | None:
        """D39 (owner, 2026-09-29): after «cancela las alarmas» BAXY read the alarms and asked whether to cancel them
        all; a yes is the cancellation of each alarm read (its verified local clock), as one request the readers read.
        None for anything else, with no alarm read, or with more than a plan holds."""

        if not self._alarm_offer or self.request is None or not accepts_offer(text, "alarms"):
            return None
        return alarm_cancellation_request(self._alarm_offer, english=not spanish(self.request))

    def offer_send(self, offer: tuple[str, str, str | None] | None) -> None:
        """Estabilización B2: the send this turn's draft may offer (``semantic.messaging.offered_send``)."""

        self._send_offer = offer

    def send_offer_question(self, english: bool, readers_send: Callable[[str], bool]) -> str | None:
        """The offer to send the verified draft's message in the person's words, told now at the end of its final;
        None when there is nothing to offer, or when ``readers_send`` says the readers alone would not send it on the
        yes. Only an offer told is accepted (``accepted_send``)."""

        if self._send_ready is None:
            return None
        channel, recipient, words = self._send_ready
        self._send_ready = None
        request = messaging.accepted_send_request(recipient, words, channel, english)
        if request is None or not readers_send(request):
            return None
        question = messaging.send_offer_question(recipient, words, english)
        self._send_offered = (request, question)
        return question

    def begin_turn(self) -> None:
        """Revisión B2 H3: each turn.decide starts here, whatever comes of it; an offer told in the last final is read
        only by this turn, never by a later one (a failed turn in between, a final the shell replaced)."""

        self._send_now, self._send_offered = self._send_offered, None

    def accepted_send(self, text: str, history: object) -> str | None:
        """Estabilización B2: a yes right after the offer is the send it named, as one request the readers read (the
        recipient in its client, the person's words); None for anything else, which leaves the draft as it is.
        Revisión B2 H3: only when BAXY's message right before the yes, as the shell sent it, ends with that offer."""

        if self._send_now is None or not accepts_offer(text, "send") or not isinstance(history, list):
            return None
        said = [item for item in history if isinstance(item, dict)]
        if said and said[-1].get("role") == "user" and said[-1].get("content") == text:
            said = said[:-1]
        request, question = self._send_now
        last = said[-1] if said else {}
        if last.get("role") != "assistant" or not str(last.get("content") or "").rstrip().endswith(question):
            return None
        return request

    def yes_after_a_send(self, text: str, history: object) -> bool:
        """Encargo E (banco i1 c6, bypass: «sí» after «Escribí "prueba BAXY C6" en el chat con Ron92…», a send BAXY had
        made and verified, was answered «Sí, lo enviaste.»): a whole yes right after a final that told a verified send,
        with nothing asked in BAXY's message before it as the shell sent it. Nothing waits for that yes; the send is
        BAXY's, already done, and is said so from data (``already_sent``), never drafted with another actor."""

        if not self._told_send or not accepts_offer(text, "send") or not isinstance(history, list):
            return False
        said = [item for item in history if isinstance(item, dict)]
        if said and said[-1].get("role") == "user" and said[-1].get("content") == text:
            said = said[:-1]
        last = said[-1] if said else {}
        return last.get("role") == "assistant" and not re.search(r"[¿?]", str(last.get("content") or ""))

    def lines(self) -> list[tuple[str, str]]:
        """What was verified, one line per kind, for the rewrite prompt and its word check."""

        return [("verificado", f"{label}: {self._facts[key]}") for key, label in self._LABELS if key in self._facts]

    def retimed_notification(
        self, text: str, *, now: datetime | None = None, zone: timezone | None = None, deciding: bool = False,
        moving: bool = False,
    ) -> "RetimedNotification | None":
        """M76 (DEV-D v3l D-w16-t2, D-w04-t4, D-w18-t5): «Actually, make it 6:30.» right after the turn that set an
        alarm, a timer or a reminder moves that one (``temporal.notification_retiming``): it is cancelled and set
        again at the new time with its kind and what it was for, as verified. A clock keeps the day of the old time
        and, when it says no part of the day, the part nearer the old time. None unless the turn before verified
        setting one. ``deciding``: read while this turn is decided, before ``expect`` made the turn that set it the
        one before. ``moving``: the turn is already decided as moving it, so its new time may be said anywhere in the
        message (``temporal.moved_to_clock``)."""

        retiming = notification_retiming(text)
        set_by = self.operations if deciding else self.previous_operations
        # M173: or the reminder of the store the last turn made (``reminder.create``).
        if self._notification is None or self._notification.get("set_by", "notification.schedule") not in set_by:
            return None
        # M113 (DEV-F v4d F-w55-t2 «no, mejor media hora antes, una hora es mucho» after «…a las 10…, recordámelo una
        # hora antes»): a new count before or after the same moment moves the notification by the difference.
        shift = (
            offset_retiming(text, self._notification.get("request") or "") if retiming is None else None
        )
        if retiming is None and shift is None and not moving:
            return None
        english = not spanish(text)
        kind, title = self._notification["kind"], self._notification["title"]
        if _TASK_TIME.search(_fold(title)) or spoken_clocks(_fold(title)):
            # «alarm for 6:45 tomorrow morning, please»: a title that says the old time would say it again.
            title = {("alarm", True): "alarm", ("alarm", False): "alarma",
                     ("reminder", True): "reminder", ("reminder", False): "recordatorio"}[(kind, english)]
        try:
            old = datetime.fromisoformat(self._notification["dueUtc"].replace("Z", "+00:00")).astimezone(zone)
        except ValueError:
            return None
        if retiming is None and shift is None:
            retiming = moved_to_clock(text, old)
            if retiming is None and kind == "alarm" and _TIMER_SET.search(
                _fold(f"{self._notification['title']} {self._notification.get('request') or ''}")
            ):
                # M148 (DEV-F v4q F-w45-t3 «go with 12…» after «I have set a 25-minute countdown for the garlic knots»,
                # planned «Change the garlic knots countdown to 12 minutes.» → «¿Qué tipo de alarma…?»): a timer moved
                # to a new length rings that long from now (``temporal.moved_to_length``).
                retiming = moved_to_length(text)
            if retiming is None:
                return None
        cancel_at = alarm_cancellation_request(((old.hour, old.minute),), english)
        if retiming is None:
            shifted = old + timedelta(minutes=shift or 0)
            if shifted <= (now or datetime.now(old.tzinfo)):
                return None
            due = shifted.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        elif retiming.duration is not None:
            due = f"{'in' if english else 'en'} {retiming.duration}"
        else:
            moment = retimed_local_moment(retiming, old, now)
            if moment is None:
                return None
            due = moment.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        return RetimedNotification(
            kind, cancel_at, {"dueUtc": due, "kind": kind, "title": title}, now,
            set_by=self._notification.get("set_by", "notification.schedule"), set_title=self._notification["title"],
            set_at=old, set_id=self._notification.get("id", ""),
        )

    def moved_notification_request(
        self, text: str, *, now: datetime | None = None, zone: timezone | None = None,
    ) -> str | None:
        """M102 (DEV-D v3z D-w18-t5 «wait no, make it una hora» after «remind me en 45 minutes to take a break»): the
        decider restated it as «Recuerda tomar un descanso a las 04:12.», one more reminder an hour after the first and
        never the first cancelled. A move of the notification the last turn set is decided here, as the request the
        plan carries (cancel the one set, set it again); the plan takes its arguments from ``retimed_notification``.
        None unless the message moves the notification the last turn verified setting."""

        moved = self.retimed_notification(text, now=now, zone=zone, deciding=True)
        if moved is None or self._notification is None:
            return None
        said = _fold(text)
        if (
            not moved.schedule_arguments["dueUtc"].startswith(("in ", "en "))
            and _BARE_RETIME_NUMBER.search(said) is not None
            and _CLOCK_SAID.search(said) is None
            and re.search(_RELATIVE_DURATION_PATTERN, _fold(self.request or "")) is not None
        ):
            # Tanda 7 «actually make it 9» after a timer of 5 minutes: a bare number after a notification set by a
            # duration may be the minutes as much as the clock; the decider reads it with the conversation.
            return None
        try:
            old = datetime.fromisoformat(self._notification["dueUtc"].replace("Z", "+00:00")).astimezone(zone)
        except ValueError:
            return None
        english = not spanish(text)
        due = moved.schedule_arguments["dueUtc"]
        if due.startswith(("in ", "en ")):
            when = due
        else:
            new = datetime.fromisoformat(due.replace("Z", "+00:00")).astimezone(zone)
            when = f"at {new:%H:%M}" if english else f"a las {new:%H:%M}"
        title = moved.schedule_arguments["title"]
        # M173: a reminder of the store is deleted (to its recoverable trash) and made again, never «cancelled».
        made = moved.set_by == "reminder.create"
        if english:
            verb = "delete" if made else "cancel"
            return f"{verb} the {moved.kind} «{title}» set for {old:%H:%M} and set it again {when}"
        noun, pronoun = ("el recordatorio", "lo") if moved.kind == "reminder" else ("la alarma", "la")
        return f"{'borra' if made else 'cancela'} {noun} «{title}» de las {old:%H:%M} y vuelve a poner{pronoun} {when}"

    def moving_operations(self) -> tuple[str, str]:
        """M173: the plan that moves the notice this conversation last set
        (``RetimedNotification.moving_operations``)."""

        made = self._notification.get("set_by") if self._notification is not None else None
        return RetimedNotification("reminder", None, {}, set_by=made or "notification.schedule").moving_operations

    def pointed_listed_title(self, text: str) -> str | None:
        """M76 (DEV-D v3l D-w17-t2 «mark the first one done» after «You have 13 tasks on your list, including
        "tomates", …» → «Which task ID and expected version…?»): the title of the task an ordinal points at in the list
        the turn before read. None unless that turn read the tasks and the message points at exactly one of them."""

        if not self._listed or not {"task.list", "task.search"} & set(self.previous_operations):
            return None
        pointed = {found.group("ordinal") for found in _LISTED_POINTER.finditer(_fold(text))}
        if len(pointed) != 1:
            return None
        ordinal = pointed.pop()
        index = next(value for words, value in _ORDINAL_INDEX.items() if re.fullmatch(words, ordinal))
        return self._listed[index] if -len(self._listed) <= index < len(self._listed) else None

    def pointed_headline(self, text: str) -> str | None:
        """M83 (DEV-D v3o D-w17-t5 «tell me more about the second one» after three Chilean headlines → the search
        «more about the unemployment headline» read United States figures): the headline an ordinal points at in the
        news the turn before read, as it was written; what more is asked of it is looked up by it. None unless that
        turn read headlines and the message points at exactly one of them."""

        if not self._headlines or "web.news.headlines" not in self.previous_operations:
            return None
        pointed = {found.group("ordinal") for found in _LISTED_POINTER.finditer(_fold(text))}
        if len(pointed) != 1:
            return None
        ordinal = pointed.pop()
        index = next(value for words, value in _ORDINAL_INDEX.items() if re.fullmatch(words, ordinal))
        return self._headlines[index] if -len(self._headlines) <= index < len(self._headlines) else None

    def edited_task(self) -> dict[str, object] | None:
        """M80 (DEV-D v3m D-p06-t2 «Change to that eggs. Add to the Walmart list.», D-p06-t3, D-p08-t3 «No, cámbialo a
        la lista Comida» → «¿Cuál es el título de la tarea y cuál es la fecha límite?»): the task this conversation
        last created or changed, as the store verified it (identity, version, title, details, due), while no other
        effect came after it. A change of it keeps every field the person did not change. None when there is none."""

        return dict(self._task) if self._task is not None else None

    def changed_entry(self, *texts: str) -> dict[str, object] | None:
        """M174 (DEV-H v5c H-w04-t3 «espera, el jamón no, mejor queso» after «apunta ahí pan, leche y jamón» → the
        list's own task updated with nothing changed): the one task of this conversation a change names by its old
        name («el jamón no, mejor queso», «cambia el jamón por queso»), as the store verified it; None when the change
        names none of them, or more than one by that name."""

        for text in texts:
            for name in changed_entry_names(text):
                found = [entry for entry in self._entries.values() if entry_name(str(entry["title"])) == name]
                if len(found) == 1:
                    return dict(found[0])
        return None

    def edited_note_title(self) -> str | None:
        """M160: the title of the note this conversation last made, read or changed, as the store verified it, while no
        other effect came after it; None when there is none."""

        return self._note

    def cancel_last_alarm(self, in_spanish: bool) -> str | None:
        """«cancela el último temporizador» / «cancel the last timer» when the last turn set an alarm or a timer: a
        correction of it («actually make it 9») replaces it instead of setting a second one. A correction of an
        alarm still being asked for («no, mejor a las 6:15» after «¿a qué hora…?») has nothing to replace."""

        if "notification.schedule" not in self.operations:
            return None
        timer = self._facts.get("alarm_noun") in {"timer", "temporizador"}
        if in_spanish:
            return "cancela el último temporizador" if timer else "cancela la última alarma"
        return f"cancel the last {'timer' if timer else 'alarm'}"

    # Tanda 7b «what have I got set right now?» after a timer and a reminder: the model kept it, and the question
    # names no kind, so no reader read it. Right after an alarm, a timer or a reminder, what the person holds is
    # the kinds this conversation set, named in the question.
    _SET_KINDS = (("notification", ("alarmas", "temporizadores"), ("alarms", "timers")),
                  ("reminder", ("recordatorios",), ("reminders",)))

    def listing_request(self, text: str) -> str | None:
        """«¿y qué tengo puesto?» → «qué alarmas, temporizadores y recordatorios tengo puesto»; None unless the last
        turn was about an alarm, a timer or a reminder and the message asks what the person holds."""

        said = followup(text)
        asked = re.match(r"(?:(?P<es>que|cuales)|what|which)\b", said.folded)
        kinds = [kind for kind in self._SET_KINDS if kind[0] in self.families]
        if asked is None or not _OWN_LISTING.fullmatch(said.folded) or not (
            {_family(op) for op in self.intended} & {kind[0] for kind in kinds}
        ):
            return None
        nouns = [noun for kind in kinds for noun in kind[1 if asked.group("es") else 2]]
        named = ", ".join(nouns[:-1]) + (" y " if asked.group("es") else " and ") + nouns[-1] if len(nouns) > 1 else nouns[0]
        return f"{said.said[: asked.end()]} {named}{said.said[asked.end():]}"


def _verified_task(observed: dict) -> dict[str, object]:
    """M80: a task as the store verified it after a write: identity, version and every editable field."""

    return {
        "taskId": observed["taskId"],
        "expectedVersion": observed["version"],
        "title": observed["title"],
        "details": str(observed.get("details") or ""),
        "due": observed.get("dueUtc") if isinstance(observed.get("dueUtc"), str) else None,
    }


def _verified_steps(situation: dict) -> list[dict]:
    """M145: the verified results a composed situation carries — itself, or each step of a mission (its ``steps``, as
    the App sends them: objects or their JSON text)."""

    steps: list[dict] = [situation] if situation.get("operation") else []
    for raw in situation.get("steps") or () if isinstance(situation.get("steps"), list) else ():
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except json.JSONDecodeError:
                continue
        if isinstance(raw, dict):
            steps.append(raw)
    return [step for step in steps if step.get("verified") is True and step.get("succeeded") is True]


def _instant(stamp: str) -> datetime | None:
    """A UTC stamp as the Core writes it («2026-10-03T22:00:00+00:00», «…Z», up to seven fractions), or None."""

    found = re.fullmatch(r"(\d{4}-\d\d-\d\dT\d\d:\d\d(?::\d\d)?)(?:\.\d+)?(Z|[+-]\d\d:\d\d)", stamp.strip())
    if found is None:
        return None
    try:
        return datetime.fromisoformat(found.group(1) + ("+00:00" if found.group(2) == "Z" else found.group(2)))
    except ValueError:
        return None


def _previous_user_request(history: list[object], current_request: str) -> str | None:
    """Read the user antecedent, preserving contiguous clock continuations."""
    previous = history
    if (
        history
        and isinstance(history[-1], dict)
        and history[-1].get("role") == "user"
        and history[-1].get("content") == current_request
    ):
        previous = history[:-1]
    requests = [
        str(item.get("content") or "")
        for item in reversed(previous)
        if isinstance(item, dict) and item.get("role") == "user"
    ]
    if not requests:
        return None
    return (
        datetime_followup_antecedent(current_request, requests)
        or followup_antecedent(current_request, requests)
        or requests[0]
    )


def _history_has_pending_clarification(
    history: object,
    pending_clarification: bool | None = None,
) -> bool:
    """Use shell state; punctuation is only a legacy history-only hint."""

    if isinstance(pending_clarification, bool):
        return pending_clarification

    if not isinstance(history, list):
        return False
    for item in reversed(history):
        if (
            not isinstance(item, dict)
            or item.get("role") != "assistant"
            or not isinstance(item.get("content"), str)
        ):
            continue
        content = str(item["content"]).strip()
        return bool(content) and content.rstrip().endswith("?")
    return False


def _alarm_clocks(observed: dict) -> tuple[tuple[int, int], ...]:
    """D39: the local (hour, minute) of each alarm a verified notification.list read, once each, in order."""

    clocks = offered_alarm_clocks(observed)
    return clocks if clocks is not None else ()


def offered_alarm_clocks(observed: dict) -> tuple[tuple[int, int], ...] | None:
    """D39 and M62: the local (hour, minute) of each alarm a yes to «¿las cancelo todas?» cancels, in order; None when
    the read cannot be offered whole.

    v3e2-final F-s040 «Cancela las alarmas, por favor.» → «Hay ocho alarmas a las 05:20, 06:00, 06:45, 08:30, 08:40 y
    09:00; ¿las cancelo todas?» over a read of 20 of 38 notifications with 16 alarms, several at the same minute: the
    yes cancels each alarm by its clock (notification.cancel.at), which picks exactly one alarm at that clock and
    refuses to choose among several; a plan holds eight steps; and a cut read does not hold every alarm. So the offer
    of all of them is made only when each alarm read has its own clock, there are eight at most and the read is whole;
    otherwise the person is asked which one."""

    from datetime import datetime, timezone

    if not isinstance(observed, dict) or observed.get("resultsMayBeTruncated") is True:
        return None
    clocks: list[tuple[int, int]] = []
    for entry in observed.get("notifications") or []:
        if not isinstance(entry, dict) or entry.get("kind") != "alarm" or not isinstance(entry.get("nextRunUtc"), str):
            continue
        try:
            instant = datetime.fromisoformat(entry["nextRunUtc"].replace("Z", "+00:00"))
        except ValueError:
            return None
        local = (instant if instant.tzinfo else instant.replace(tzinfo=timezone.utc)).astimezone()
        if (local.hour, local.minute) in clocks:
            return None
        clocks.append((local.hour, local.minute))
    return tuple(clocks) if len(clocks) <= 8 else None


# Ronda 23 (r21 v3-50 t2): what a request names as its object — a file with its extension («prueba.zip») or a name
# said in quotes («Informe final»). Original case. A capitalised word is no such object: «para el paseo a Santa Marta»,
# «450 dólares a Euros» say a place or a complement the restatement may leave to the readers (m174, m154 contracasos).
_NAMED_FILE = re.compile(
    rf"(?<![\w.-])[\w-]+(?:\.[\w-]+)*\.{alternation(lexicon.FILE_EXTENSIONS)}(?![\w])(?!\.\w)", re.IGNORECASE
)
_QUOTED_NAME = re.compile(r"[«“\"]([^«»“”\"\n]{1,80})[»”\"]")


# The application a restatement is framed in, before the request itself («en 7-Zip File Manager, decime …»).
_APPLICATION_FRAME = re.compile(r"(?:en|in)\s+([^,]{1,80}),\s*", re.IGNORECASE)

# A place said by its kind («la carpeta Descargas») or by a path («C:\fotos», «docs/2024»).
_NAMED_PLACE = re.compile(rf"\b{alternation(lexicon.PLACE_NOUNS)}\b|\\|\b[a-z]{{2,}}/[a-z]")
# Revisión 2 de r23: a question for what the thing says or shows («¿qué dice?», «what does it show»); every other
# question ``asks_the_inside_of_the_last`` reads asks what it holds.
_ASKS_WHAT_IT_SAYS = re.compile(
    rf"\b(?:que|what)\s+(?:(?:does|do)\s+(?:it|that|this)\s+)?{alternation(lexicon.SAYS_WORDS)}[\s¿?¡!.,;:]*$"
)


def _is_container(name: str) -> bool:
    """Revisión 2 de r23: a file that holds others (``lexicon.CONTAINER_EXTENSIONS``)."""

    return "." in name and fold(name).rsplit(".", 1)[-1] in lexicon.CONTAINER_EXTENSIONS


def named_objects(text: str) -> tuple[str, ...]:
    """The objects a request names (see above), in the order said; none for one that only points («¿qué tiene?»)."""

    said = " ".join(str(text or "").split())
    found = [*_NAMED_FILE.finditer(said), *_QUOTED_NAME.finditer(said)]
    names: dict[str, str] = {}
    for match in sorted(found, key=lambda m: m.start()):
        name = (match.group(1) if match.re is _QUOTED_NAME else match.group(0)).strip(" .,;:")
        if name and not any(fold(name) in fold(kept) for kept in names.values()):
            names[fold(name)] = name
    return tuple(names.values())


def files_acted_on(text: str) -> tuple[str, ...]:
    """Revisión 3 de r23 (revisión 2 left out only the quote of a verb of writing, so «en el bloc de notas poné «hola
    mundo»» → «¿qué dice?» still sent «… (hola mundo)», and so did «pegá», «mandale «hola» a Ana» and «buscá «Hollow
    Knight»»): the objects a later question can ask of are the files a request names by their extension, said outside
    any quote. A quote says text — what the turn wrote, pasted, sent, searched or played, whatever its verb — and that
    text is what the screen will then show: carried into the objective it is the expected answer, unverified, never an
    object."""

    said = _QUOTED_NAME.sub(" ", " ".join(str(text or "").split()))
    names: dict[str, str] = {}
    for match in _NAMED_FILE.finditer(said):
        name = match.group(0).strip(" .,;:")
        if name and fold(name) not in names:
            names[fold(name)] = name
    return tuple(names.values())


def objective_with_the_antecedent_object(
    objective: str, said: str, antecedent: str | None, *, is_application: Callable[[str], bool] = lambda _name: False,
) -> str | None:
    """Ronda 23 (r21 v3-50 t2 «decime cuántos archivos tiene adentro» after «en 7zip abrí el prueba.zip que está en
    baxy-prueba-v3» was restated «en 7-Zip File Manager, decime cuántos archivos tiene adentro»: the engine counted the
    folder and BAXY said «hay 7 archivos en la carpeta»). The restatement of a message that leans on the turn before
    (the caller checks ``dependency``) and names nothing itself must keep what that turn named: a file it acted on
    (``files_acted_on``; never a quote) that is not an application (the restatement frames those itself). When it kept none of them, the
    objective is repaired with them, as said; None when there is nothing to repair («¿qué tiene?» after «abrí
    Spotify», a restatement that kept «prueba.zip», a message that names its own object). Revisión 1: only a message
    that asks the inside of what came before (``asks_the_inside_of_the_last``) is repaired, never a new order or a
    question that depends some other way («buscá el clima de mañana», «dale, seguí», «en la calculadora calculá
    37*12»), and never a restatement that gave it an object or a place of its own."""

    if not antecedent or named_objects(said) or not asks_the_inside_of_the_last(said):
        return None
    # Revisión 2 (r23): a turn before that named a place of its own («abrí la carpeta Descargas y seleccioná foto.jpg»)
    # leaves the inside asked between that place and a file in it; the restatement is not repaired. A question for what
    # something holds («¿cuántos hay adentro?», «¿qué tiene?») asks it only of a file that holds others (an archive, a
    # disk image), never of a picture, a document or a quoted name; one for what it says («¿qué dice?») of any of them.
    if _NAMED_PLACE.search(fold(antecedent)):
        return None
    holds = _ASKS_WHAT_IT_SAYS.search(followup(said).folded) is None
    objects = [
        name for name in files_acted_on(antecedent)
        if not is_application(name) and (not holds or _is_container(name))
    ]
    restated = " ".join(str(objective or "").split())
    if not objects or not restated or any(fold(name) in fold(restated) for name in objects):
        return None
    # Revisión 1 (r23): a restatement that gave the question an object or a place of its own («qué tiene la carpeta
    # Descargas» for «¿qué tiene?») is the decider's reading and stays; only one that still asks the bare inside, past
    # the application it is framed in («en 7-Zip File Manager, …»), lost the object.
    frame = _APPLICATION_FRAME.match(restated)
    asked = restated[frame.end():] if frame is not None and is_application(frame.group(1)) else restated
    if not asks_the_inside_of_the_last(asked):
        return None
    return f"{restated.rstrip(' .')} ({', '.join(objects)})"
