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
from datetime import datetime, timezone

from .grammar import _COVERAGE_ACTION_HEAD, _head_is
from .levels import followup_antecedent
from .normalize import alternation, fold, spelled_out
from .patterns import datetime_followup_antecedent
from .temporal import (
    alarm_cancellation_request,
    assents_to_alarm_offer,
    notification_retiming,
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


def says_the_message_back(question: str, said: str) -> bool:
    """M85 (DEV-D v3o D-p04-t1 «Dónde?» → «¿Dónde?»): a question that is the person's own message, word for word."""

    words = _WORD.findall(_fold(str(said or "")))
    return bool(words) and _WORD.findall(_fold(str(question or ""))) == words


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
        if _ASSENT.fullmatch(folded) and _BARE_DEICTIC_REQUEST.fullmatch(_fold(slot.pending_request).strip(" ¿?¡!.,")):
            # cien-99 049: «hazlo» after «haz eso» → «¿Qué es eso?». Agreeing to a request
            # with no object completes nothing; the message is read on its own.
            return None
        if _ASSENT.fullmatch(folded) or _NUMBER_ANSWER.fullmatch(folded) or followup(text).value:
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


def is_social(text: str) -> bool:
    """The whole message is thanks, praise, a reaction or a closing («gracias», «perfecto muy bien», «that's all»).

    It answers no question and asks for nothing, whatever is pending: the rewrite never reads it as a dependency
    (``dependency``) and the contextual decider's action on it is not the person's (M65).
    """

    folded = _fold(text).strip(" ¿?¡!.,")
    return bool(folded) and _SOCIAL.fullmatch(folded) is not None


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


def go_ahead_with_nothing_pending(text: str, last_reply: str | None) -> bool:
    """M88: a go-ahead (``gives_go_ahead``) after a reply of BAXY's that asked nothing: nothing is waiting for that yes.
    After a question, the go-ahead answers it and is read as usual."""

    return gives_go_ahead(text) and not str(last_reply or "").rstrip().endswith("?")


# What a reply says to tell that nothing was done (folded): a negation of doing or having done. «No problem» and
# «sin problema» agree to something and are not one.
_NOT_DONE = re.compile(r"\b(?:no|not|nothing|nada|nunca|never|todavia|aun|yet)\b|n'?t\b")
_AGREEING_NO = re.compile(r"\b(?:no\s+(?:problem|worries|hay\s+problema)|sin\s+problemas?|why\s+not|por\s+que\s+no)\b")


def says_nothing_was_done(reply: str) -> bool:
    """M88: the reply says, in some words, that something was not (yet) done — the only true answer to a go-ahead
    that nothing was waiting for, in a turn that ran nothing."""

    folded = _AGREEING_NO.sub(" ", _fold(reply))
    return _NOT_DONE.search(folded) is not None


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


def leans_on_context(text: str) -> bool:
    """The trigger: the message's form leans on the turn before (see the section comment). Talk never does."""

    said = followup(text)
    folded = said.folded
    if not folded or _SOCIAL.fullmatch(folded) or _REFUSAL.fullmatch(folded) or _PROHIBITION.match(folded):
        return False
    if said.fragment or refers_back(text) or _OWN_LISTING.fullmatch(folded) or asks_attribute_of_the_last(text):
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


# M80: the writes whose verified result is the whole task (identity, version, title, details, due).
_TASK_WRITES = ("task.create", "task.update", "task.complete", "task.reopen", "task.restore")


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
        self._headlines: tuple[str, ...] = ()  # M83: the headlines read, in the order they were told

    def expect(self, request: str, operations: object) -> None:
        if self.operations and not set(self.operations) & set(_TASK_WRITES):
            # M80: another effect done after the task leaves «cámbialo» without that task; a question does not.
            self._task = None
        self.previous_operations = self.operations
        self.request = str(request or "").strip() or None
        self.intended = tuple(str(op) for op in operations) if isinstance(operations, (list, tuple)) else ()
        self.operations = ()
        self._facts.pop("request", None)
        # D39: the offer to cancel the alarms read stands only for the turn right after it.
        self._alarm_offer = ()

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
            if all(isinstance(observed.get(key), str) and observed[key] for key in ("kind", "title", "dueUtc")):
                self._notification = {key: observed[key] for key in ("kind", "title", "dueUtc")}
        elif operation == "reminder.create":
            self._facts["reminder"] = str(observed.get("title") or request)
        elif operation == "notification.list" and plural_alarm_cancellation(request):
            self._alarm_offer = _alarm_clocks(observed)
        elif operation in _TASK_WRITES:
            # M80 (DEV-D v3m D-p06-t2, D-p08-t3): the task as the store verified it after the write, for a change of
            # it in the next turns that says only what changes.
            if (
                isinstance(observed.get("taskId"), str)
                and isinstance(observed.get("title"), str)
                and isinstance(observed.get("version"), int)
                and not observed.get("deleted")
            ):
                self._task = {
                    "taskId": observed["taskId"],
                    "expectedVersion": observed["version"],
                    "title": observed["title"],
                    "details": str(observed.get("details") or ""),
                    "due": observed.get("dueUtc") if isinstance(observed.get("dueUtc"), str) else None,
                }
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

    def accepted_alarm_cancellation(self, text: str) -> str | None:
        """D39 (owner, 2026-09-29): after «cancela las alarmas» BAXY read the alarms and asked whether to cancel them
        all; a yes is the cancellation of each alarm read (its verified local clock), as one request the readers read.
        None for anything else, with no alarm read, or with more than a plan holds."""

        if not self._alarm_offer or self.request is None or not assents_to_alarm_offer(text):
            return None
        return alarm_cancellation_request(self._alarm_offer, english=not spanish(self.request))

    def lines(self) -> list[tuple[str, str]]:
        """What was verified, one line per kind, for the rewrite prompt and its word check."""

        return [("verificado", f"{label}: {self._facts[key]}") for key, label in self._LABELS if key in self._facts]

    def retimed_notification(
        self, text: str, *, now: datetime | None = None, zone: timezone | None = None,
    ) -> "RetimedNotification | None":
        """M76 (DEV-D v3l D-w16-t2, D-w04-t4, D-w18-t5): «Actually, make it 6:30.» right after the turn that set an
        alarm, a timer or a reminder moves that one (``temporal.notification_retiming``): it is cancelled and set
        again at the new time with its kind and what it was for, as verified. A clock keeps the day of the old time
        and, when it says no part of the day, the part nearer the old time. None unless the turn before verified
        setting one."""

        retiming = notification_retiming(text)
        if retiming is None or self._notification is None or "notification.schedule" not in self.previous_operations:
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
        cancel_at = alarm_cancellation_request(((old.hour, old.minute),), english)
        if retiming.duration is not None:
            due = f"{'in' if english else 'en'} {retiming.duration}"
        else:
            moment = retimed_local_moment(retiming, old, now)
            if moment is None:
                return None
            due = moment.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        return RetimedNotification(kind, cancel_at, {"dueUtc": due, "kind": kind, "title": title}, now)

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
