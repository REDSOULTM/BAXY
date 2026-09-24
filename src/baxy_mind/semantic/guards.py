"""Input guards without a request (Fase 3.5): a cut message, overheard speech, noise, echoed words, a bare path, a dangling comparison or alternative. They say why a message holds no request for BAXY; the turn asks or answers accordingly. Moved from __main__.
"""

from __future__ import annotations

import re
from typing import Iterable
from .. import effect_intent
from .. import corrector
from .grammar import imperative_rewrites
from .reading import _OVERHEARD_ACTION_WORDS


_BARE_PATH = re.compile(
    r"^\s*(?:%[A-Za-z_][A-Za-z0-9_]*%|[A-Za-z]:|\\\\[^\\/:*?\"<>|\r\n]+)"
    r"(?:[\\/][^\\/:*?\"<>|\r\n]+)+\s*$"
)


def bare_path_file_name(objective: str) -> str | None:
    """FILES H0299 «%USERPROFILE%\\Desktop\\…\\ROADMAP.md»: a file path pasted
    alone, with no verb, names no request; the honest turn asks what to do
    with that file. Returns the file name (the last segment) or None."""

    text = objective.strip()
    if _BARE_PATH.match(text) is None or len(text) > 512:
        return None
    name = re.split(r"[\\/]", text.rstrip("\\/"))[-1].strip()
    if not name or "." not in name.strip(".") or re.search(r"\s{2,}", name):
        return None
    return name


_CUT_TAIL_WORDS = frozenset({
    "del", "de", "la", "el", "los", "las", "un", "una", "unos", "unas", "al",
    "y", "e", "o", "u", "con", "para", "por", "en", "que", "mi", "mis", "su",
    "sus", "tu", "tus", "the", "a", "an", "of", "and", "or", "with", "for", "my",
})


def cut_request_tail(objective: str) -> str | None:
    """FILES H0426 «…que contenga la fecha actual, el nombre del»: a request
    of six or more words that stops, without closing punctuation, on an
    article, preposition or conjunction arrived cut there. Returns the last
    three words (what the person will recognise) or None."""

    text = objective.strip()
    if not text or text[-1] in ".!?…»\")" or len(text) > 512:
        return None
    words = re.findall(r"[^\s]+", text)
    # UI1641 H0088 «Ve a Cotele en»: a go-to order whose destination stops on a
    # bare preposition arrived cut there even when short; four words suffice
    # under a go-to head, six otherwise (FILES H0426).
    go_to = re.match(
        r"^[¿?¡!\s]*(?:ve|anda|andate|entra|entrá|abre|abrí|llevame|llévame|navega|navegá|go|open|take\s+me)\s+(?:a|al|to)\b",
        effect_intent._fold(text),
    ) is not None
    if len(words) < (4 if go_to else 6):
        return None
    last = effect_intent._fold(words[-1]).strip(",;:")
    if last not in _CUT_TAIL_WORDS:
        return None
    # Uso real «pon kiss f. m. para mi»: «para mí», typed without its accent, is
    # the pronoun closing the request, and so is «por mí» («hazlo por mi»). After
    # «de», «a» or «en» a possessive may still be cut («la carpeta de mi…»).
    if last == "mi" and effect_intent._fold(words[-2]).strip(",;:") in {"para", "por"}:
        return None
    # Dev corpus 2026-09-23 «revisa mi bandeja de entrada por mí»: «mí» written with its accent is the pronoun,
    # never a possessive cut short.
    if words[-1].strip(",;:").casefold() == "mí":
        return None
    # MASSIVE «tiendas de ropa en un radio de cinco kilómetros de mi», «un bar cerca de mi»: after a place or a
    # distance, «de mí» is where the person is, not a possessive cut short.
    if last == "mi" and re.search(
        r"\b(?:cerca|alrededor|lejos|delante|detras|enfrente|kilometros?|km|metros?|millas?|cuadras?)\s+de\s+mi$",
        effect_intent._fold(" ".join(words[-3:])).strip(",;:"),
    ):
        return None
    return " ".join(words[-3:])


def _echoed_words(folded: str) -> bool:
    """CONVERSATION1150 H0410 «Artiro, artiro. Estimado, estimado.»: every
    word arrives at least twice and nothing else does; no assent, negation,
    question or request head. Words alone, however familiar, are not a
    request; the honest turn says so and asks what the person needs."""

    words = re.findall(r"[a-z]{2,}", folded)
    if not 4 <= len(words) <= 12 or len(set(words)) > 4:
        return False
    if any(words.count(word) < 2 for word in set(words)):
        return False
    if re.search(r"\d|[?¿]", folded):
        return False
    if any(
        word in {"si", "no", "dale", "ok", "okay", "bueno", "claro", "vale", "listo",
                 "yes", "yeah", "nope", "never", "nunca", "jamas", "hola", "hello", "baxy"}
        for word in words
    ):
        return False
    return not any(
        effect_intent._head_is(word, effect_intent._COVERAGE_ACTION_HEAD) for word in set(words)
    )


def _unresolved_input_kind(
    objective: str,
    known_names: Iterable[str] = (),
) -> str | None:
    """Name an input that carries no readable request at all.

    DIALOGUE1277 (H0287 «????», H0570 «1234567890», H0581 «a», H0181 «No.»,
    H0336 «no no no…»): with nothing to read, the model answered a generic
    help greeting, refused the letter as outside the catalog, or claimed a
    failure to understand a plain «no». ``"noise"`` is text without a single
    word of two letters; ``"bare_negation"`` is only negation tokens. Both
    are answered by a clarification composed for that situation, never by
    a guess at the meaning. A pending clarification keeps its own answer.
    """

    folded = effect_intent._fold(objective).strip()
    if not folded:
        return None
    names_folded = {
        token.casefold()
        for name in known_names
        if isinstance(name, str)
        for token in (name, *re.findall(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ][A-Za-zÁÉÍÓÚÜÑáéíóúüñ'’-]*", name))
    }
    if (
        re.fullmatch(
            # DIALOGUE1491 H0393 «Ve a portal una.», H0541 «Ve Portal 2 UN»: a
            # go-to order whose destination ends in a bare article or
            # preposition is a message the transcription cut off; the owner
            # asks to understand it from context or to ask. With nothing to
            # complete it, the honest turn asks which portal or site.
            r"[\s¡!¿?]*(?:ve|anda|andate|entra|abre|abri|ir|llevame|navega|go|open|take\s+me)\s+"
            r"(?:(?:a|al|to)\s+)?(?:(?:el|la|the)\s+)?"
            r"(?:portal|pagina|sitio|web|site|page)\b[^.!?]{0,40}?"
            r"\s(?:un|una|unos|unas|el|la|los|las|de|del|en|al|a|y|con|para|por|the|to|of|and|at)"
            r"[\s.!?¿¡]*",
            folded,
        )
        is not None
    ):
        return "cut_destination"
    if (
        re.fullmatch(
            # DIALOGUE1487/1489 H0528 «Quiero que lo veas y de que se trata?»,
            # «Miralo y decime de qué se trata»: a request to look at
            # «it/this/that» and say what it is, with nothing named, has no
            # object to look at; the generic referent clarifier asked back
            # «¿De qué se trata?» or «¿Qué es eso que miraste?», so this kind
            # gets its own question: what should BAXY look at.
            r"[\s¡!¿?]*(?:"
            r"(?:quiero|necesito|quisiera)\s+que\s+(?:lo|la|los|las)\s+(?:veas|mires|revises|leas|chequees)|"
            r"(?:mira|miralo|mirala|ve|velo|vela|fijate|revisa|revisalo|revisala|chequea|chequealo|lee|leelo|leela)"
            r"(?:\s+(?:en\s+)?(?:eso|esto|lo|la|aquello))?|"
            r"(?:look\s+at|check(?:\s+out)?|see|read)\s+(?:it|this|that)(?:\s+out)?"
            r")"
            r"(?:\s*(?:,|y|and)\s*(?:me\s+)?(?:digas|decime|dime|contame|cuentame|tell\s+me)?\s*"
            r"(?:de\s+)?(?:que|what)\s+(?:se\s+trata|es|dice|it(?:'s|\s+is)(?:\s+about)?|it\s+says))?"
            r"[\s.!?¿¡]*",
            folded,
        )
        is not None
    ):
        return "deictic_look"
    if (
        re.fullmatch(
            # AUDIO1375 H0439 «Ponlo a 100 ahora», H0713 «devuelvelo a 100»: a
            # level for «lo» with nothing named before it; the only honest
            # answer asks what to set (volume, brightness…).
            r"[\s¡!¿?]*(?:pon[eé]?lo|ponla|pon[eé]?melo|pon[eé]?mela|dejalo|dejala|dejamelo|"
            r"devolvelo|devuelvelo|devolvela|devuelvela|subilo|subila|subimelo|bajalo|bajala|"
            r"bajamelo|llevalo|llevala|set\s+it|put\s+it|turn\s+it|leave\s+it|bring\s+it)\s+"
            r"(?:a|al|en|to|at|on|back\s+to)\s+(?:el\s+|the\s+)?\d{1,3}\s*(?:%|por\s+ciento|percent)?"
            r"(?:\s+(?:ahora|ya|now|de\s+nuevo|otra\s+vez|again|please|por\s+favor|porfa))*[\s.!?]*",
            folded,
        )
        is not None
    ):
        return "deictic_level"
    if (
        re.fullmatch(
            # UI1643 H0097 «ponle hola»: a text to put «to it» with nothing
            # named before it — no window, field, file or chat; the honest
            # turn asks where to write it.
            r"[\s¡!¿?]*(?:pon[eé]?le|ponele|pon[eé]?melo|put\s+on\s+it|write\s+on\s+it)\s+"
            r"(?!(?:a|al|por|para|que|en)\b)(?P<text>[¿?¡!\w][^.!?]{0,60}?)"
            r"(?:\s+(?:ahora|ya|now|please|por\s+favor|porfa))*[\s.!?]*",
            folded,
        )
        is not None
        and not re.search(
            r"\b(?:en|a|al|del|de)\s+(?:el|la|los|las|mi|mis|tu|tus|un|una|the|my|a)?\s*"
            r"(?:ventana|archivo|nota|chat|grupo|mensaje|correo|mail|documento|campo|titulo|"
            r"nombre|whatsapp|discord|telegram|window|file|note|chat|message|document|field)\b",
            folded,
        )
    ):
        return "deictic_text"
    if (
        re.fullmatch(
            r"[\s¡!¿?.,]*(?:no|nop|nope|nah|nunca|jamas)"
            r"(?:[\s,.!¡]+(?:no|nop|nope|nah|nunca|jamas))*[\s.!?]*",
            folded,
        )
        is not None
    ):
        return "bare_negation"
    if (
        re.search(r"[a-z]{2,}", folded) is None
        # «5+5» or «10*3» is an arithmetic expression, not noise.
        and re.search(r"\d\s*[-+*/x×÷=^%]\s*\d", folded) is None
    ):
        return "noise"
    if re.fullmatch(r"[\[(<][a-z0-9_. -]{1,60}[\])>][\s.!?]*", folded) is not None:
        # UNRES1855 H0639: the whole message is one bracketed token; whatever it
        # stands for, nothing in it is a request (a pasted placeholder, the
        # survey's «[PHONE_REDACTED]»). A shape rule for SHORT text in general
        # was measured and rejected: with no vocabulary it cannot tell
        # «¡Habristín!» from «pausá», «silencio» or «repetí», which the readers
        # do not resolve either and which the model answers correctly today.
        return "noise"
    if _overheard_speech(folded):
        return "overheard_speech"
    if re.fullmatch(r"[¿?¡!\s]*(?:hable|habla|hablame|hableme|hablanos|hablenos|hablalo|hablelo|speak|talk|tell)\s+(?:(?:de|sobre|about|of|me)\s+)?(?:de\s+)?(?:est[aeo]s?|es[aeo]s?|aquell[ao]s?|it|this|that|these|those)[.!?\s]*", folded) is not None:
        # UNRES1945 H0404 «Hable este.»: a speak/talk verb with a bare
        # demonstrative and nothing before it — nothing names what to talk
        # about; the honest turn asks that, never a chat opener.
        return "deictic_speak"
    _bare = re.fullmatch(r"[¿?¡!\s]*(?P<phrase>[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÜÑáéíóúüñ'’-]+(?:\s+[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÜÑáéíóúüñ'’-]+){0,2})\s*\?[\s.!?]*", str(objective).strip())
    if (
        _bare is not None
        # cien-83 091 «¿Estás?»: a sentence-initial capital is not a name. Two
        # words at least, none of them a Spanish word («Hola Baxy?», «Buenos
        # Días?» stay conversation) and not an English question opener.
        and len(_bare.group("phrase").split()) >= 2
        and not any(corrector.known_spanish(token) for token in _bare.group("phrase").split())
        and _bare.group("phrase").split()[0].casefold() not in {
            "are", "is", "do", "does", "did", "can", "could", "will", "would", "should", "what",
            "who", "where", "when", "why", "how", "which", "still", "you", "anything", "ready",
            "hello", "hi", "hey", "thanks", "thank", "good", "ok", "okay", "any", "got", "all",
            # «And Spotify?»: a conjunction opens a follow-up on the previous
            # question, which the scoped readers resolve; it is not a bare name.
            "and", "or", "but",
        }
        and not corrector.unknown_words(objective, known_names)
        # «Steam?», «Spotify?» name a catalog application on their own and
        # keep today's path; «Calendar Devil?» only shares a word with one.
        and _bare.group("phrase").casefold() not in names_folded
        and not (
            len(_bare.group("phrase").split()) == 1
            and _bare.group("phrase").casefold() in names_folded
        )
    ):
        # UNRES1945 H0160 «Calendar Devil?»: one to three capitalised words
        # and a question mark, no verb, no catalog name, real words in some
        # language; the model answered as if it were a question about BAXY.
        # The honest turn says it does not know what that refers to and asks.
        return "bare_phrase_question"
    if corrector.unintelligible_input(objective, known_names):
        # UNRES1941 H0210 «¡Habristín!»: every content word of the message is
        # unknown to the Spanish and English dictionaries, the catalog and the
        # product's own terms. The honest turn says that word did not come
        # through and asks to repeat it, never a greeting that fakes
        # understanding. Absent lexicon → never this kind.
        return "unknown_word"
    if _echoed_words(folded):
        return "echoed_words"
    if bare_path_file_name(objective) is not None:
        return "bare_path"
    if cut_request_tail(objective) is not None and _OVERHEARD_ACTION_WORDS.search(folded) is not None:
        # Fase 3.5 (owner 2026-09-21, turn 116 «me gusta crear cosas como tu»):
        # only a *request* can arrive cut; talk ending on «tu» («como tú», the
        # accent dropped) is talk. H0088 and H0426 keep their order head.
        return "cut_request"
    if (
        effect_intent.INDETERMINATE_WINDOW_CLAUSE.fullmatch(folded) is not None
        # REOPEN1993 H0263: «la otra/anterior/siguiente» is the window behind
        # the foreground one and switches; only «la mejor» and the like ask.
        and not effect_intent.other_window_switch_request(objective)
    ):
        # WINDOWS1537 H0392 «enfocá la mejor»: a window named only by «la
        # mejor» with nothing before it; the honest turn asks which.
        return "indeterminate_window"
    if (
        re.fullmatch(
            # KNOWLEDGE1523 H0424 «¿Cuál es su identidad secreta?», H0645
            # «¿Quién es de verdad?»: the real identity or name of someone
            # never named, with nothing before it; the honest turn asks whom.
            r"[\s¡!¿?]*(?:"
            r"(?:cual|cuales)\s+es\s+su\s+(?:identidad(?:\s+secreta|\s+real|\s+verdadera)?|"
            r"(?:verdadero|verdadera|autentico|autentica)\s+(?:nombre|identidad)|nombre\s+(?:real|verdadero|de\s+verdad))|"
            r"quien\s+es\s+(?:de\s+verdad|realmente|en\s+realidad|en\s+verdad|de\s+veras)|"
            r"what(?:'s|\s+is)\s+(?:his|her|their)\s+(?:secret\s+identity|real\s+(?:name|identity))|"
            r"who\s+(?:is|are)\s+(?:he|she|they)\s+really"
            r")[\s.!?¿¡]*",
            folded,
        )
        is not None
    ):
        return "missing_person_referent"
    if (
        re.fullmatch(
            # DIALOGUE1515 H0562 «Si hazlo»: agreement to do something when
            # nothing was proposed or asked; the honest turn says nothing is
            # pending and asks what to do (DIALOGUE1281: «¿Qué haces?»).
            r"[\s¡!¿?.,]*(?:(?:si|dale|ok|okay|bueno|claro|de\s+acuerdo|yes|yeah|yep|sure|obvio|vale)[\s,.!]*)?"
            r"(?:hazlo|hacelo|hacela|hazla|haz\s+lo|hace\s+lo|procede|do\s+it|go\s+ahead)"
            r"(?:\s+(?:ya|ahora|nomas|now|please|por\s+favor|porfa))*[\s.!?]*",
            folded,
        )
        is not None
    ):
        return "bare_confirmation"
    if (
        re.fullmatch(
            # DIALOGUE1515 H0205 «o en la de siempre.»: the tail of a sentence,
            # an alternative with nothing before it and no request inside;
            # the honest turn says only that part arrived and asks what it
            # refers to (DIALOGUE1281: a greeting).
            r"[\s¡!¿?]*(?:o|u|y|e|pero|sino|ni)\s+"
            r"(?:en|a|al|con|de|del|para|por|sin|sobre|desde|hasta)\s+"
            r"(?:la|el|los|las|lo|una|un|mi|tu|su|esa|ese|esta|este|aquella|aquel)\s+"
            r"[a-z][a-z0-9 ]{0,40}[\s.!?]*",
            folded,
        )
        is not None
        # «y con la calculadora abre algo» carries an order; only a fragment
        # without any order verb is a dangling alternative.
        and re.search(
            r"\b(?:abre|abri|abris|abrir|abrime|pone|pon|poneme|poner|busca|buscame|buscar|cierra|cerra|cerrar|"
            r"reproduce|manda|envia|escribe|crea|guarda|recuerda|recorda|sube|subi|baja|silencia|apaga|prende|"
            r"enciende|lanza|inicia|muestra|mostrame|dime|decime|contame|explica|lee|copia|pega|borra|elimina|"
            r"instala|descarga|toma|saca|captura|open|play|search|close|send|write|set|turn|show|tell|launch|"
            r"start|stop|find|take|click)\b",
            folded,
        )
        is None
    ):
        return "dangling_alternative"
    if (
        re.fullmatch(
            # IDENTITY1323 H0296 «Tú eres como eso»: compared with something
            # never named; the only honest answer asks what «eso» is.
            r"[\s¡!¿?]*(?:(?:tu|vos|usted)\s+)?(?:eres|sos|eri|es)\s+"
            r"(?:como|igual\s+(?:a|que)|parecid[oa]\s+a|lo\s+mismo\s+que)\s+"
            r"(?:eso|esto|aquello|ese|esa|aquel|aquella)[\s.!?]*|"
            r"[\s¡!¿?]*(?:you\s+are|you'?re|u\s+r|ur)\s+(?:just\s+)?"
            r"(?:like|the\s+same\s+as|similar\s+to)\s+(?:that|this|it|those)[\s.!?]*",
            folded,
        )
        is not None
    ):
        return "dangling_comparison"
    return None


def _conversation_in_progress(history: object) -> bool:
    """BAXY spoke in the last exchange: the next message is addressed to it."""

    if not isinstance(history, list):
        return False
    recent = [item for item in history[-3:] if isinstance(item, dict)]
    return any(
        item.get("role") == "assistant" and str(item.get("content") or "").strip()
        for item in recent
    )


# Only the openers that are questions and nothing else: «que», «como», «cuando» also open talk («que te digo»). MASSIVE
# cooking_recipe (dev corpus 2026-09-24) «por cuánto tiempo tengo que poner la pizza en el horno…»: the question word
# may come after its preposition.
_ADDRESSED_OPENING = (
    r"[\s¡!]*(?:(?:por|para|de|desde|hasta|en|a|con|sobre|durante|segun|for|in|to|from|at|with|about|since|until|"
    r"during)\s+)?"
    r"(?:cual|cuales|cuanto|cuanta|cuantos|cuantas|quien|quienes|por\s+que|"
    r"what|which|who|whom|where|when|why|how)\b"
)
# MASSIVE qa_factoid «con toda la información que pueda recopilar en internet podría proporcionarme la mejor
# explicación…»: a request put to the listener (you could, can you) is said to BAXY wherever it sits.
_ADDRESSED_REQUEST = (
    r"\b(?:podria|podrias|puedes|podes|puede|pudieras|pudiera)\s+(?:usted\s+|tu\s+|vos\s+)?"
    r"(?:\w+(?:rme|rnos|rle|rles)|me\s+\w+r|nos\s+\w+r)\b|"
    r"\b(?:could|can|would|will)\s+you\s+\w+"
)


def _overheard_speech(folded: str) -> bool:
    """DIALOGUE1513: a long stretch of talk with no request for BAXY.

    H0006, H0139, H0332, H0372, H0429, H0441, H0483, H0735: the microphone
    caught other people's conversation or a broadcast (fifteen words or more,
    no question, no order verb, no vocative). Nothing in it is addressed to
    the assistant; DIALOGUE1281 measured the model reconstructing the
    fragment or answering it as if it were. The honest turn says it finds no
    request for it in what arrived and asks whether the person needs
    something."""

    if "?" in folded or "¿" in folded:
        return False
    words = re.findall(r"[a-z0-9]+", folded)
    if len(words) < 15:
        return False
    if (
        re.match(_ADDRESSED_OPENING, folded) is not None
        or re.search(_ADDRESSED_REQUEST, folded) is not None
        or any(
            effect_intent._head_is(effect_intent._request_head(said), effect_intent._COVERAGE_ACTION_HEAD)
            # «envíeme un recordatorio…», «establecer un recordatorio…»: an order said with «usted» or as an
            # infinitive opens ordering too (grammar.imperative_rewrites).
            for said in (folded, *imperative_rewrites(folded))
        )
    ):
        # MASSIVE (dev corpus 2026-09-23) «cuáles son las predicciones de las votaciones…», «muéstrame la
        # respuesta a este problema…», «chequea en los cines…»: the ear drops the question mark; a message that
        # opens asking or ordering is said to BAXY, however long.
        return False
    return _OVERHEARD_ACTION_WORDS.search(folded) is None and "baxy" not in folded
