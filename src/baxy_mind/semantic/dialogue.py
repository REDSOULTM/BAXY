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

import re
from dataclasses import dataclass

from .grammar import _COVERAGE_ACTION_HEAD, _head_is
from .normalize import alternation, fold, spelled_out

_WORD = re.compile(r"[a-z0-9ñ]+")

# Object clitics fused to an imperative or an infinitive: «súbelo», «cerralo»,
# «activalo», «investigala», «prenderlo», «devolvele», «dímelo».
_ENCLITIC = re.compile(
    r"\b[a-zñ]{3,}(?:a|e|i|ar|er|ir|ando|iendo)(?:me|te|se|nos)?(?:lo|la|los|las|le|les)\b"
)
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
# Bare assent: the whole message only says yes.
_ASSENT = re.compile(
    r"^(?:(?:si|sip|sep|dale|ok|okay|okey|claro|confirmo|de\s+una|obvio|por\s+favor|porfa|bueno|va|vale|"
    r"hacelo|hazlo|adelante|yes|yeah|yep|sure|do\s+it|go\s+ahead|please)[\s,.!]*){1,4}$"
)
# A refusal: the whole message only declines («no, dejalo», «mejor no», «olvidalo», «no thanks»).
# It never completes the pending request; «no, en YouTube» carries a destination and is not one.
_REFUSAL = re.compile(
    r"^(?:(?:no|nop|nope|nah|nel|nada|mejor\s+no|no\s+gracias|no\s+hace\s+falta|ya\s+no|dejalo|deja|dejala|"
    r"dejemoslo|olvidalo|olvidate|olvida|cancela|cancelalo|cancelar|para|basta|ninguno|ninguna|tranqui|"
    r"no\s+thanks|never\s+mind|forget\s+it|cancel|stop|leave\s+it|no\s+need)[\s,.!]*){1,4}$"
)
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
    r"thanks|thank\s+you|cool|nice|great|"
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
    "poco poquito poquitito toque toquecito cachito cacho chin pelin rato ratito momento momentito segundo tantito"
    .split()
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
        if _ASSENT.fullmatch(folded) and _BARE_DEICTIC_REQUEST.fullmatch(_fold(slot.pending_request).strip(" ¿?¡!.,")):
            # cien-99 049: «hazlo» after «haz eso» → «¿Qué es eso?». Agreeing to a request
            # with no object completes nothing; the message is read on its own.
            return None
        if _ASSENT.fullmatch(folded) or _NUMBER_ANSWER.fullmatch(folded):
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
    if _ASSENT.fullmatch(folded):
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
    return _ASSENT.fullmatch(_fold(text).strip(" ¿?¡!.,")) is not None


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
    r"termino|esta|estan)\b"
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
    if not folded or "?" in raw or "¿" in raw or len(folded.split()) > 80:
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
        if not _ENCLITIC.fullmatch(_fold(bare)):
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
    r"mas\s+bien)\b[\s,.:]*)+"
)
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
# «a las 6 y cuarto», «a las 7 y media», «a las 8 y 20»: the minutes said in words are part of the hour.
_CLOCK_HOUR = (
    r"(?:a\s+las?|at|para\s+las?|by|around|como\s+a\s+las?)\s+\d{1,2}(?::\d{2}|\s+y\s+(?:cuarto|media|\d{1,2}))?"
)
_CLOCK_PERIOD = (
    r"\s*(?:am|pm|a\.?\s?m\.?|p\.?\s?m\.?|hs|horas|de\s+la\s+(?:manana|tarde|noche)|in\s+the\s+(?:morning|afternoon|"
    r"evening))"
)
_CLOCK = rf"{_CLOCK_HOUR}(?:{_CLOCK_PERIOD})?"
_TIME_FRAGMENT = re.compile(rf"^(?:{_DAY}|{_CLOCK})(?:\s+(?:y|and|o|or)\s+(?:{_DAY}|{_CLOCK}))?$")
_PLACE_FRAGMENT = re.compile(rf"^(?:en|in|at|para|for|on|por|desde|from)\s+{_NOT_ASKED}\S.*$")
# A place said as «allá» or «there»; «is there…», «there are…» only say that something exists.
_PLACE_ANAPHOR = re.compile(
    r"\b(?:alla|alli|aya|ahi)\b|(?<!is )(?<!are )(?<!was )(?<!were )(?<!be )\b(?:over\s+)?there\b"
    r"(?!\s+(?:is|are|was|were|will|be|'s)\b)"
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
    def replaces_last(self) -> bool:
        """It corrects what was just done («actually make it 9», «no, a las 8», «mejor 30», a bare «9»),
        rather than adding to it («y otro de 20», «and at 8 too»)."""

        if _AGAIN_FRAGMENT.fullmatch(self.folded):
            return False  # «otra vez», «más»: once more, not instead
        corrects = self.corrected or re.match(_CHANGE, self.folded) is not None or not self.continued
        adds = re.search(r"\b(?:otro|otra|another|also|too|tambien|ademas|second|segundo|segunda)\b", self.folded)
        return corrects and adds is None


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


def leans_on_context(text: str) -> bool:
    """The trigger: the message's form leans on the turn before (see the section comment). Talk never does."""

    said = followup(text)
    folded = said.folded
    if not folded or _SOCIAL.fullmatch(folded) or _REFUSAL.fullmatch(folded) or _PROHIBITION.match(folded):
        return False
    if said.fragment or refers_back(text) or _OWN_LISTING.fullmatch(folded):
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


def corrected_request(request: str | None, text: str) -> str | None:
    """«no, mejor a las 6:15» after «ponme una alarma a las 6 y media pa mañana» → «ponme una alarma a las 6:15 pa
    mañana»; «mejor que sean 6» after «un temporizador de 8 minutos» → «… de 6 minutos». None when the message is not
    such a correction or the request has no value of that kind."""

    said = followup(text)
    base = " ".join(str(request or "").split())
    if not base or "\n" in str(request) or not said.replaces_last:
        return None
    folded = _fold(base)
    if len(folded) != len(base):
        base = folded
    hour = re.fullmatch(rf"{_CLOCK_HOUR}(?P<period>{_CLOCK_PERIOD})?", said.folded)
    old = _SAID_HOUR.search(folded)
    if hour is not None and old is not None:
        # The part of the day said before stays unless the correction says another one.
        end = old.end() if hour.group("period") else old.end("hour")
        return base[: old.start()] + said.said + base[end:]
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


def _family(operation: str) -> str:
    return operation.split(".", 1)[0]


def same_family(operations: tuple[str, ...], frame: tuple[str, ...]) -> bool:
    """A rewrite reads no effect, or only effects of the family of the request it continues."""

    return not operations or (bool(frame) and {_family(op) for op in operations} <= {_family(op) for op in frame})


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

    def expect(self, request: str, operations: object) -> None:
        self.request = str(request or "").strip() or None
        self.intended = tuple(str(op) for op in operations) if isinstance(operations, (list, tuple)) else ()
        self.operations = ()
        self._facts.pop("request", None)

    def record(self, situation: object) -> None:
        if not isinstance(situation, dict) or self.request is None:
            return
        operation = str(situation.get("operation") or "")
        if (
            operation not in self.intended
            or situation.get("verified") is not True
            or situation.get("succeeded") is not True
        ):
            return
        request = self.request
        observed = situation.get("observed") if isinstance(situation.get("observed"), dict) else {}
        self.operations = tuple(dict.fromkeys((*self.operations, operation)))
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
        elif operation == "reminder.create":
            self._facts["reminder"] = str(observed.get("title") or request)
        elif operation == "web.search" and observed.get("query"):
            self._facts["topic"] = str(observed["query"])
        elif operation in {"audio.volume", "audio.volume.adjust"} and observed.get("level") is not None:
            self._facts["volume"] = str(observed["level"])
        elif operation.startswith("system.settings") and observed.get("setting") and observed.get("value") is not None:
            self._facts[str(observed["setting"])] = str(observed["value"])

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
        if not self.request or "\n" in self.request or not operation or operation not in self.intended:
            return user_text
        return self.request

    def lines(self) -> list[tuple[str, str]]:
        """What was verified, one line per kind, for the rewrite prompt and its word check."""

        return [("verificado", f"{label}: {self._facts[key]}") for key, label in self._LABELS if key in self._facts]

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

