"""Checks of a conversation reply: machine vocabulary, a served capability denied, the request handed
back, questions only and offers nobody asked for.
"""

from __future__ import annotations

import re

from .semantic.normalize import _policy_guard_text
from .semantic.request import fold as _reading_fold
from .limit_voice import _unsupported_answer_has_inability


# Vocabulary that belongs to the machinery, never to the person. A clarify
# question asked "¿Qué acción se debe realizar en la sesión SMTC seleccionada?",
# which is the catalogue's own wording leaking onto the screen. Operation ids
# are matched structurally because they are open-ended.
_VISIBLE_INTERNAL_VOCABULARY = re.compile(
    r"\b(?:smtc|wmi|json|schema|esquema|endpoint|sidecar|router|shortlist|payload|"
    r"manifest|manifiesto|sha256|kernel|provider|proveedor|"
    r"catalogo\s+(?:activo|tipado)|catalog\s+(?:entry|operation)|"
    r"knn|embedding|token|prompt|runtime|deserializ\w*|serializ\w*|"
    r"stacktrace|traceback|exception|nullptr|"
    r"parametro\s+requerido|required\s+parameter)\b"
    r"|\b[a-z][a-z0-9]*\.[a-z][a-z0-9.]*\b",
    re.IGNORECASE,
)


def visible_text_leaks_internal_vocabulary(value: object) -> bool:
    """Reject machine vocabulary in anything a person will read."""

    text = str(value or "")
    if not text.strip():
        return False
    # A sentence-ending period is not an operation id.
    candidate = re.sub(r"(?<=[a-z])\.(?=\s|$)", " ", text, flags=re.IGNORECASE)
    return _VISIBLE_INTERNAL_VOCABULARY.search(candidate) is not None


_CAPABILITY_DENIAL = re.compile(
    r"\b(?:"
    r"no\s+puedo\s+(?:ver|revisar|comprobar|consultar|capturar|mostrar|"
    r"decirte|decir|leer|dar|proporcionar|saber|acceder)|"
    r"no\s+tengo\s+(?:acceso|forma|manera|capacidad)|"
    r"no\s+s[eé]\s+(?:qu[eé]|cu[aá]l|cu[aá]les)|"
    # The guard text folds an apostrophe to a space, so "don't" arrives as
    # "don t". Matching only the written form let two of the five V1 denials
    # through.
    r"i\s+(?:do\s+not|don\s*'?\s*t)\s+have\s+(?:the\s+)?"
    r"(?:capability|ability|access|way)|"
    r"i\s+(?:cannot|can\s*'?\s*t|can\s+not)\s+(?:see|check|access|read|tell|"
    r"capture|show|know)|"
    r"i\s+(?:do\s+not|don\s*'?\s*t)\s+know\s+what"
    r")\b",
    re.IGNORECASE,
)
_DENIED_MACHINE_SUBJECT = re.compile(
    r"\b(?:pantalla|screen|escritorio|desktop|volumen|volume|audio|sonido|"
    r"sound|dispositivos?|devices?|perifericos?|peripherals?|aparatos?|"
    r"gadgets?|red|network|wifi|wi-fi|conexion|connection|bluetooth|"
    r"procesos?|processes|sistema|system|maquina|machine|equipo|computador|"
    r"computadora|ordenador|automatismos?|automations?|rutinas?|routines?|"
    r"notas?|notes?|juegos?|games?|portapapeles|clipboard|copias?|backups?|"
    r"salud|health|estado|status|hora|reloj|clock|time|utc)\b",
    re.IGNORECASE,
)


def visible_reply_denies_a_served_capability(
    value: object,
    *,
    authenticated_operations: tuple[str, ...] = (),
) -> bool:
    """Reject a conversation reply that says it cannot do what the catalog does.

    On veto-reach V1 five of twenty-nine served requests were answered with a
    denial: "I don't have the capability to check the health of a machine"
    (``system.status`` exists), "No puedo capturar el estado actual de la
    pantalla" (``capture.screenshot`` exists), "No puedo ver qué dispositivos
    están conectados" (``peripheral.list`` exists), and so on. A conversation
    turn attempted nothing, so it has no verified basis for any claim about its
    own inability -- that is the same rule as "assert nothing unverified",
    applied to self-report.

    The rule is deliberately narrow. Abstaining from something genuinely
    outside the catalog must stay possible, and cut D depends on it, so a
    denial is only rejected when its subject is one of the machine domains the
    catalog actually serves. "No puedo regar el limonero" is untouched; "no
    puedo ver los dispositivos conectados" is not.
    """

    text = str(value or "").strip()
    if not text:
        return False
    if authenticated_operations and _unsupported_answer_has_inability(text):
        return True
    folded = _policy_guard_text(text)
    match = _CAPABILITY_DENIAL.search(folded)
    if match is None:
        return False
    # Only the clause the denial governs counts. A denial about the garden that
    # later mentions a screen is still a denial about the garden.
    clause = folded[match.start() : match.start() + 120]
    return _DENIED_MACHINE_SUBJECT.search(clause) is not None


_RESTATEMENT_OPENING = re.compile(
    r"^(?:"
    r"i\s+notice\s+(?:that\s+)?you\s*(?:'|\s)?re\s+asking|"
    r"i\s+see\s+(?:that\s+)?you\s*(?:'|\s)?re\s+asking|"
    r"you\s*(?:'|\s)?re\s+asking|"
    r"i\s+mention\s+that|"
    r"i\s+sense\s+(?:that\s+)?you|"
    r"mencionas\s+que|"
    r"est[aá]s\s+(?:diciendo|preguntando)\s+que|"
    r"entiendo\s+que\s+(?:preguntas|dices)|"
    r"veo\s+que\s+(?:preguntas|dices)|"
    r"te\s+refieres\s+a\s+si"
    r")\b",
    re.IGNORECASE,
)


def visible_reply_is_only_questions(value: object) -> bool:
    """Check question scope, independently of answer relevance or truth.

    A final question does not consume the content before its opening mark.
    Preserve the existing sentence-boundary rule for text without that mark;
    punctuation and emoji left outside questions are not an answer.
    """

    reply = str(value or "").strip()
    if not reply.endswith(("?", "？")):
        return False
    if re.search(r"[.!][\"'»]?\s", reply) is not None:
        return False
    if "¿" not in reply:
        return True
    outside_questions = re.sub(
        r"¿[^¿?？]*[?？]|[^.!?！？¿\n]*[?？]", "", reply
    )
    return not any(character.isalnum() for character in outside_questions)


# Tanda 7 «¿podemos estar un rato en silencio?» → «Claro, está bien. Solo respira y escucha. ¿Quieres que hablemos
# de algo específico mientras pasa el tiempo?»: a question that offers something more is the offer USER_MESSAGE_PROMPT
# already forbids («sin ofertas»); the owner's D3 asks back only for a missing datum.
_OFFER_QUESTION = re.compile(
    r"\b(?:quieres|queres|quisieras|deseas|te\s+gustaria|prefieres|preferis|te\s+apetece|"
    r"want\s+me\s+to|would\s+you\s+like|do\s+you\s+want|shall\s+i|should\s+i)\b"
)


# Verification 2026-09-25 (owner script turn 3 «Me gusta crear cosas, como tu» → «Interesante, ¿qué tipo de cosas te
# gustaría crear?» rejected twice, then a recovery question): a question that starts with a question word asks about
# the person («¿qué te gustaría crear?», «what would you like to build?»); it offers nothing.
_WH_QUESTION_START = re.compile(
    r"^(?:y\s+|and\s+)?(?:que|cual|cuales|como|donde|cuando|cuanto|cuanta|cuantos|cuantas|quien|quienes|por\s+que|"
    r"what|which|how|where|when|who|whom|why)\b"
)


def visible_reply_offers_more(value: object) -> bool:
    """A question of the reply offers something the person did not ask for."""

    for sentence in re.split(r"(?<=[.!?…])\s+", str(value or "").strip()):
        if "?" not in sentence and "¿" not in sentence:
            continue
        asked = sentence[sentence.index("¿") + 1:] if "¿" in sentence else sentence
        folded = _reading_fold(asked).strip(" ,;:¡!")
        if _WH_QUESTION_START.match(folded) is None and _OFFER_QUESTION.search(folded) is not None:
            return True
    return False


def visible_reply_restates_the_request(value: object, request: object) -> bool:
    """Reject a conversation reply that hands the question back.

    Seven of twenty-nine served requests on veto-reach V1 came back this way, in
    two shapes. One echoes the question outright -- "what words am i holding
    ready to drop" answered with "What words are you holding ready to drop?" --
    and the other narrates that a question was asked: "I notice you're asking
    if the House Signal is still active", "Mencionas que hay una posibilidad de
    que estés incomunicado".

    Neither is an answer, and neither is a clarification either: a clarification
    asks for the detail that is missing, and these ask for nothing. This guard
    runs on the conversation path only, so genuine clarifying questions are
    untouched.
    """

    reply = str(value or "").strip()
    if not reply:
        return False
    folded_reply = _policy_guard_text(reply)
    if _RESTATEMENT_OPENING.search(folded_reply) is not None:
        return True
    if not any(marker in reply for marker in ("?", "¿", "？")):
        return False
    # A question that carries the request back almost word for word is the
    # request, not a reply to it.
    asked = {word for word in _policy_guard_text(request).split() if len(word) > 3}
    if len(asked) < 3:
        return False
    # Half the content words, not more. "Que aparatos tengo enchufados ahora"
    # answered with "¿Cuáles aparatos tienes enchufados en este momento?" shares
    # only the two nouns, because Spanish inflects the verb and swaps the adverb
    # for a phrase. A question that is a question and reuses half the asker's
    # content words is a restatement; the clarifications this must not touch --
    # "¿Por qué canal quieres que se lo mande?" -- share none.
    # Count only the individual question. An answer followed by a distinct
    # question can legitimately reuse the requested content: "Hola Emmanuel,
    # ¿cómo estás?" answers the requested greeting. Pooling the whole reply
    # rejected that answer and also combined unrelated questions into an echo.
    for question in re.findall(r"[^.!?！？¿\n]*[?？]", reply):
        echoed = {
            word for word in _policy_guard_text(question).split() if len(word) > 3
        }
        if len(asked & echoed) / len(asked) >= 0.5:
            return True
    return False
