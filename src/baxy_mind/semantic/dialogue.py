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
the rewritten request the mind returns. Neither side re-reads the other's text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .normalize import alternation, fold

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
# «no, en YouTube», «mejor en Spotify», «en YouTube mejor», «por WhatsApp».
_DESTINATION_ONLY = re.compile(
    r"^(?:(?:no|nop|mejor|en\s+cambio|pero|y)\s*[,.]?\s*)*"
    r"(?:en|por|con|desde|a|al|on|in|with)\s+(?:el\s+|la\s+|mi\s+)?[a-z0-9ñ+ .'-]{2,30}?"
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
# Talk that never answers a slot, even with a question pending.
_SOCIAL = re.compile(
    r"^(?:gracias|muchas\s+gracias|genial|perfecto|buenisimo|jaja\w*|uf+|ah+|oh+|wow|que\s+bien|"
    r"thanks|thank\s+you|cool|nice|great|"
    # Tanda 7 «no that's all thank you»: closing the conversation continues nothing.
    r"that'?s\s+(?:all|it)|eso\s+es\s+todo|nada\s+mas|nothing\s+else)\b"
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


_fold = fold


def _words(text: str) -> list[str]:
    return _WORD.findall(_fold(text))


@dataclass(frozen=True)
class DialogueSlot:
    """What the next message may depend on."""

    pending_request: str | None
    pending_question: str | None
    antecedents: tuple[str, ...]  # user requests, most recent first (at most two)
    last_reply: str | None

    @property
    def has_context(self) -> bool:
        return bool(self.pending_request or self.antecedents)

    def context_lines(self) -> list[tuple[str, str]]:
        """Oldest first, as (speaker, text), for the rewrite prompt."""
        lines: list[tuple[str, str]] = [("persona", text) for text in reversed(self.antecedents)]
        if self.pending_request and self.pending_request not in self.antecedents:
            lines.append(("persona", self.pending_request))
        if self.last_reply:
            lines.append(("BAXY", self.last_reply))
        return lines


def read_slot(message: dict, history: object, current: str) -> DialogueSlot:
    """Read the slot from the shell's pending request and the recent history."""

    pending_request = str(message.get("pendingObjective") or "").strip() or None
    items = [item for item in history if isinstance(item, dict)] if isinstance(history, list) else []
    if items and items[-1].get("role") == "user" and str(items[-1].get("content") or "") == current:
        items = items[:-1]
    antecedents: list[str] = []
    last_reply = None
    for item in reversed(items[-8:]):
        role, content = item.get("role"), str(item.get("content") or "").strip()
        if not content:
            continue
        if role == "assistant" and last_reply is None and not antecedents:
            last_reply = content[:400]
        elif role == "user" and len(antecedents) < 2:
            antecedents.append(content[:400])
    pending_question = last_reply if pending_request and last_reply and last_reply.rstrip().endswith("?") else None
    return DialogueSlot(pending_request, pending_question, tuple(antecedents), last_reply)


def _object_pronoun(folded: str) -> bool:
    """A verb with a fused object pronoun whose object is not said.

    «apagalo», «subila a 20»: the object is the pronoun. «devolvele el sonido», «mandale un
    mensaje»: «le» is the dative (to whom); the object («el sonido») is said, so the message
    stands on its own (held-out turn 9).
    """

    for found in _ENCLITIC.finditer(folded):
        tail = _CLITIC_TAIL.search(found.group(0))
        rest = folded[found.end():].split()
        if tail is not None and tail.group("clitic") in {"le", "les"} and rest and rest[0] in {
            "el", "la", "los", "las", "un", "una", "unos", "unas", "mi", "mis", "su", "sus", "algo", "que",
        }:
            continue
        return True
    return False


def dependency(text: str, slot: DialogueSlot) -> str | None:
    """Why this message needs the context to be understood, or None.

    ``answer``      a short answer or «sí» to the question BAXY just asked;
    ``destination`` «no, en YouTube»: only the destination of the last request changes;
    ``reference``   a pronoun object («súbelo», «cerralo»);
    ``subject``     a person's age asked without the person («¿y cuántos años tiene?», «how old is he»);
    ``topic``       a lookup verb whose topic may have been named before («averiguá qué dijo la crítica»);
    ``followup``    anything else whose form leans on the turn before (``leans_on_context``): «¿y el finde?»,
                    «actually make it 9», «cómo se llama esta?», «is the entrance free».
    """

    if not slot.has_context:
        return None
    folded = _fold(text).strip(" ¿?¡!.,")
    if not folded or _SOCIAL.match(folded) or _REFUSAL.fullmatch(folded) or _PROHIBITION.match(folded):
        return None
    words = folded.split()
    if slot.pending_request:
        if _ASSENT.fullmatch(folded) and _BARE_DEICTIC_REQUEST.fullmatch(_fold(slot.pending_request).strip(" ¿?¡!.,")):
            # cien-99 049: «hazlo» after «haz eso» → «¿Qué es eso?». Agreeing to a request
            # with no object completes nothing; the message is read on its own.
            return None
        if _ASSENT.fullmatch(folded) or _NUMBER_ANSWER.fullmatch(folded):
            return "answer"
        if len(words) <= 5 and _DESTINATION_ONLY.fullmatch(folded):
            return "answer"
        if len(words) <= 4:
            return "answer"
    rest = followup(text).folded
    if (
        slot.antecedents
        and len(words) <= 6
        and _DESTINATION_ONLY.fullmatch(folded)
        # Tanda 7 «no, a las 8»: an hour or an amount is not where; the follow-up replaces the one said.
        and not (_TIME_FRAGMENT.fullmatch(rest) or _AMOUNT_FRAGMENT.fullmatch(rest))
    ):
        return "destination"
    if len(words) > 16:
        return None
    if slot.antecedents and _SUBJECTLESS_PERSON_FACT.fullmatch(folded):
        return "subject"
    if _object_pronoun(folded) or (len(words) <= 6 and _PROCLITIC_START.match(folded)):
        return "reference"
    if slot.antecedents and _RESEARCH_VERB.search(folded):
        return "topic"
    if slot.antecedents and leans_on_context(text):
        return "followup"
    return None


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
    content = [word for word in _words(rewrite) if word not in _STOPWORDS and not word.isdigit()]
    if not content:
        return False
    return all(word[:4] in said for word in content)


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
    """«activalo» after «silencia mi micrófono» → «activa mi micrófono»: the direct-object clitic
    fused to the verb is replaced by the antecedent's object. «le» (indirect) is left to the model."""

    obj = antecedent_object(antecedent)
    if obj is None:
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
    return None


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
# - The dialogue state: the last thing of each kind this conversation verified — the place a weather read
#   reported and the day it was asked for, what the player says is playing, the alarm and the reminder created
#   (with the alarm's id), the topic searched, the level set, and the last request that ran. Only verified
#   results write it, never BAXY's text.
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
# nothing by itself.
_FILLER = re.compile(r"^(?:(?:oye|che|bueno|ok|okay|okey|ah|oh|mira|hey|listen|baxy)\b[\s,.:]*)+")
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
_AMOUNT_FRAGMENT = re.compile(
    rf"^(?:{_CHANGE}\s+)?(?:(?:a|al|en|de|to|at|for|by|unos|unas|como|about|around|like)\s+)*"
    rf"(?:\d{{1,3}}|{alternation(frozenset(_NUMBER_WORDS))})(?:\s*{_UNIT})?$"
)
_WEEKDAY = r"(?:lunes|martes|miercoles|jueves|viernes|sabado|domingo|monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
_DAY = (
    r"(?:(?:el|este|the|this|next|on|para|pa|for|el\s+proximo|la\s+proxima|este\s+proximo)\s+)*"
    r"(?:pasado\s+manana|manana|hoy|ayer|anoche|anteayer|esta\s+(?:noche|tarde)|fin\s+de\s+semana|finde|"
    rf"semana\s+(?:que\s+viene|proxima)|today|tonight|tomorrow|yesterday|last\s+night|weekend|week|{_WEEKDAY})"
)
_CLOCK = (
    r"(?:a\s+las?|at|para\s+las?|by|around|como\s+a\s+las?)\s+\d{1,2}(?::\d{2})?"
    r"(?:\s*(?:am|pm|a\.?\s?m\.?|p\.?\s?m\.?|hs|horas|de\s+la\s+(?:manana|tarde|noche)|in\s+the\s+(?:morning|afternoon|"
    r"evening)))?"
)
_TIME_FRAGMENT = re.compile(rf"^(?:{_DAY}|{_CLOCK})(?:\s+(?:y|and|o|or)\s+(?:{_DAY}|{_CLOCK}))?$")
_PLACE_FRAGMENT = re.compile(r"^(?:en|in|at|para|for|on|por|desde|from)\s+\S.*$")
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
# «what have I got set», «qué tengo programado»: what the person has, with no object named.
_OWN_LISTING = re.compile(
    r"^(?:what|which|que|cuales|cuantos|cuantas)\s+(?:(?:have|do|did)\s+(?:i|we)\s+(?:got\s+|have\s+)?|"
    r"(?:tengo|tenemos|hay|me\s+quedan?)\s+)(?:set|scheduled|pending|programad[oa]s?|puest[oa]s?|pendientes?|"
    r"activ[oa]s?|active|on|going)\b"
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
        )

    @property
    def replaces_last(self) -> bool:
        """It corrects what was just done («actually make it 9», «no, a las 8», «mejor 30», a bare «9»),
        rather than adding to it («y otro de 20», «and at 8 too»)."""

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
    """A place or a thing said as «allá», «esta», «eso», «it» in the message."""

    folded = followup(text).folded
    return bool(_PLACE_ANAPHOR.search(folded) or _DEMONSTRATIVE.search(folded))


def leans_on_context(text: str) -> bool:
    """The trigger: the message's form leans on the turn before (see the section comment). Talk never does."""

    said = followup(text)
    folded = said.folded
    if not folded or _SOCIAL.match(folded) or _REFUSAL.fullmatch(folded) or _PROHIBITION.match(folded):
        return False
    if said.fragment or refers_back(text) or _OWN_LISTING.match(folded):
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
    """The last thing of each kind this conversation verified. The serve loop owns one and passes it in.

    ``expect`` is told the request a turn decided and its operations; ``record`` is given the situation of each
    composed result and keeps it only when the operation was one of those, verified and succeeded. A new
    conversation starts it over (``reset``).
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
        self._expected: tuple[str, tuple[str, ...]] | None = None
        self._facts: dict[str, str] = {}
        self.operations: tuple[str, ...] = ()  # the last verified request's operations
        self.families: set[str] = set()  # every family this conversation verified

    def reset(self) -> None:
        self._expected = None
        self._facts = {}
        self.operations = ()
        self.families = set()

    @property
    def request(self) -> str | None:
        """The last request whose result was verified, in the person's words as completed."""

        return self._facts.get("request")

    def expect(self, request: str, operations: object) -> None:
        names = tuple(str(op) for op in operations) if isinstance(operations, (list, tuple)) else ()
        self._expected = (str(request or "").strip(), names) if names else None

    def record(self, situation: object) -> None:
        if not isinstance(situation, dict) or self._expected is None:
            return
        operation = str(situation.get("operation") or "")
        request, expected = self._expected
        if operation not in expected or situation.get("verified") is not True or situation.get("succeeded") is not True:
            return
        observed = situation.get("observed") if isinstance(situation.get("observed"), dict) else {}
        self.operations = (
            tuple(dict.fromkeys((*self.operations, operation))) if self._facts.get("request") == request
            else (operation,)
        )
        self._facts["request"] = request
        family = _family(operation)
        self.families.add(family)
        said_time = _said_time(request)
        if family in {"weather", "notification", "reminder", "calendar"} and said_time:
            self._facts["day"] = said_time
        if family == "weather":
            place = ", ".join(str(observed[key]) for key in ("location", "region", "country") if observed.get(key))
            if place:
                self._facts["place"] = place
        elif family == "media":
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

    def lines(self) -> list[tuple[str, str]]:
        """What was verified, one line per kind, for the rewrite prompt and its word check."""

        return [("verificado", f"{label}: {self._facts[key]}") for key, label in self._LABELS if key in self._facts]

    def cancel_last_alarm(self, in_spanish: bool) -> str | None:
        """«cancela el último temporizador» / «cancel the last timer» when this conversation set an alarm or a
        timer: a correction of it («actually make it 9») replaces it instead of setting a second one."""

        if "alarm" not in self._facts:
            return None
        timer = self._facts.get("alarm_noun") in {"timer", "temporizador"}
        if in_spanish:
            return "cancela el último temporizador" if timer else "cancela la última alarma"
        return f"cancel the last {'timer' if timer else 'alarm'}"

