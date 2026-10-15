"""Checks of the prose that says a request is not supported: it names the request, says the inability
in BAXY's voice and stays bounded.
"""

from __future__ import annotations

import re

from .semantic.normalize import _policy_guard_text
from . import effect_intent
from .semantic.request import read_request
from .semantic.conversation import coordinates_actions, names_a_current_public_office
from .reply_language_checks import (
    _HACER_WITH_A_CONJUGATED_FORM, _MALFORMED_MODAL_COMPLEMENT, _REDUNDANT_MODAL_AUXILIARY,
    limit_breaks_the_asked_verb, visible_reply_breaks_first_person, visible_reply_breaks_spanish_plural,
    visible_reply_breaks_word_case, visible_reply_invents_a_spanish_infinitive, visible_reply_is_a_fixed_stall,
    visible_reply_says_a_vulgarity,
)
from .limit_voice import _limit_changes_the_act, _unsupported_answer_has_inability, limit_voice_defect
from .conversation_shape import _UNSUPPORTED_ANCHOR_STOPWORDS


# The words of the limit itself: they name no part of the request.
_UNSUPPORTED_ANCHOR_LIMIT_WORDS = frozenset(
    """
    puedo puede hacerlo hago llevo manejo gestiono posible disponible cannot
    unable something pedido pediste pides pedir asked ahora mismo desde aqui
    """.split()
)


def _current_public_role_request(value: object) -> bool:
    return names_a_current_public_office(_policy_guard_text(value))


def _spanish_modal_is_malformed(value: object) -> bool:
    folded = _policy_guard_text(value)
    found = _MALFORMED_MODAL_COMPLEMENT.search(folded)
    if found is not None and not found.group("complement").endswith(("ar", "er", "ir")):
        return True
    if _REDUNDANT_MODAL_AUXILIARY.search(folded) is not None:
        return True
    conjugated = _HACER_WITH_A_CONJUGATED_FORM.search(folded)
    return conjugated is not None and not conjugated.group("complement").endswith(
        ("ar", "er", "ir")
    )


_SHORT_DEVICE_TOKENS = frozenset({"pc", "tv", "ip"})


def _singular_token(token: str) -> str:
    """A plural noun's singular, by its ending only («lecciones» → «leccion», «books» → «book»)."""

    if len(token) >= 6 and token.endswith("es") and token[-3] not in "aeiou":
        return token[:-2]
    return token[:-1] if len(token) >= 4 and token.endswith("s") and not token.endswith("ss") else token


def _unsupported_answer_mentions_request(value: object, request: object) -> bool:
    """Require one concrete request concept in bounded limitation prose.

    Presentation may legitimately translate a noun when the user mixes
    languages (``computer`` -> ``computador``).  Treat a small audited set of
    catalog-adjacent nouns as the same concept so the safety validator does not
    reject a grounded answer merely because it used the user's other language.
    """

    if _current_public_role_request(request) and _unsupported_answer_has_inability(
        value
    ):
        # A bounded refusal to answer a time-sensitive office-holder fact is
        # honest even when the small model says only "I cannot verify that".
        # The separate inability contract still rejects any asserted name.
        return True
    request_tokens = {
        token
        for token in _policy_guard_text(request).split()
        # NEGATIVE1429 «jamás apagues la pc»: the device acronym is the concept.
        if (len(token) >= 3 or token in _SHORT_DEVICE_TOKENS)
        and token not in _UNSUPPORTED_ANCHOR_STOPWORDS
    }
    if not request_tokens:
        return True
    answer_tokens = set(_policy_guard_text(value).split())
    if request_tokens & answer_tokens:
        return True
    # «llama un taxi» → «No llamo taxis», «start reading the book» → «I don't read books aloud»: the same
    # noun in the other number names the same thing.
    if {_singular_token(token) for token in request_tokens} & {_singular_token(token) for token in answer_tokens}:
        return True
    if read_request(str(request or "")).language == "mixed" and any(
        len(token) >= 5
        and token not in _UNSUPPORTED_ANCHOR_STOPWORDS
        and token not in _UNSUPPORTED_ANCHOR_LIMIT_WORDS
        for token in answer_tokens
    ):
        # Uso real 2026-09-23 «Stop listening por favor»: a spanglish request is
        # answered in Spanish, so its English words («listening») cannot appear
        # verbatim; the courtesy («favor») was the only shared token and the
        # published limit echoed it. A concrete content word names the request.
        return True
    # NEGATIVE1429: the acknowledgement conjugates the prohibited verb
    # («apagues» → «apagaré»); a shared five-letter stem is the same concept.
    if any(
        len(request_token) >= 5 and len(answer_token) >= 5
        and request_token[:5] == answer_token[:5]
        for request_token in request_tokens
        for answer_token in answer_tokens
    ):
        return True
    equivalent_concepts = (
        {"computer", "computador", "computadora", "equipo", "machine", "maquina"},
        {"browser", "navegador"},
        {"backup", "backups", "respaldo", "respaldos", "copia", "copias"},
        {"keyboard", "keyboards", "teclado", "teclados"},
        {
            "actual",
            "actualizada",
            "actualizado",
            "confirmar",
            "current",
            "currently",
            "latest",
            "updated",
            "verificar",
            "verificarlo",
            "verification",
            "verify",
        },
    )
    return any(
        bool(request_tokens & concept) and bool(answer_tokens & concept)
        for concept in equivalent_concepts
    )


def _unsupported_request_anchor_token(request: object) -> str:
    """Select one inert literal token the presentation must preserve.

    The unsupported-answer validator requires a concrete request anchor. A
    small local model can otherwise paraphrase every noun away on both bounded
    presentation attempts. Keep one normalized token, or two bounded title
    tokens for an explicit game request, so untrusted prose never becomes a
    system instruction. Otherwise prefer the final content token because
    corrections place their intended target last.
    """

    guarded = _policy_guard_text(request)
    game_request = re.match(
        (
            r"^(?:(?:vamos\s+a\s+)?(?:juega|jugar|juguemos|play))\s+"
            r"(?:(?:al|el|the)\s+)?(?P<title>[a-z0-9][a-z0-9 -]{1,64}?)"
            r"(?:\s+(?:modo|mode)\s+(?:multijugador|multiplayer))?$"
        ),
        guarded,
        re.IGNORECASE,
    )
    if game_request is not None:
        title_tokens = [
            token
            for token in game_request.group("title").split()
            if token not in _UNSUPPORTED_ANCHOR_STOPWORDS
            and re.fullmatch(r"[a-z0-9][a-z0-9-]{1,31}", token) is not None
        ]
        if title_tokens:
            return " ".join(title_tokens[:2])
    candidates = [
        token
        for token in guarded.split()
        if len(token) >= 3
        and token not in _UNSUPPORTED_ANCHOR_STOPWORDS
        and re.fullmatch(r"[a-z0-9][a-z0-9-]{2,31}", token) is not None
    ]
    return candidates[-1] if candidates else ""


def _unsupported_answer_contract_failure(
    value: object,
    request: object = None,
) -> str:
    """Return one bounded reason for rejecting unsupported prose."""

    content = str(value or "").strip()
    # Owner's test 2026-09-21 (turns 210-213): the self-close limit says how
    # BAXY is closed in a second sentence («… se cierra con la X de su ventana
    # o con Alt+F4»); ctx-dueno-07 killed every such draft as unsupported_shape.
    sentence_breaks = len(re.findall(r"[.!…]\s+\S", content))
    # Tandas 5e/6 «No detengo la cámara inteligente. Eso no lo hago.», «No activo el modo de privacy. Eso no lo
    # hago.»: the limit named and then said plainly is the owner's own wording; rejecting it cost both drafts,
    # a whole second decision and a recovery (8-10 s per limit). A short second sentence that is itself the plain
    # inability is allowed; anything else after the limit (a suggestion, an explanation) still is not.
    sentences = re.split(r"(?<=[.!…])\s+(?=\S)", content)
    restated_limit = (
        len(sentences) == 2
        and len(content.split()) <= 20
        and _unsupported_answer_has_inability(sentences[1])
    )
    allowed_breaks = 1 if restated_limit or effect_intent.self_close_request(str(request or "")) else 0
    if (
        not content
        or "\n" in content
        or "\r" in content
        or any(marker in content for marker in ("?", "¿", "？"))
        or sentence_breaks > allowed_breaks
    ):
        return "unsupported_shape"
    # A small local model sometimes stutters ("No puedo puedo encargar..."),
    # which reads as broken product rather than a person speaking. The turn
    # boundary retries instead of publishing it.
    if re.search(r"\b(\w+)\s+\1\b", content, re.IGNORECASE | re.UNICODE) is not None:
        return "unsupported_repeated_word"
    if _spanish_modal_is_malformed(content):
        return "unsupported_malformed_modal"
    if visible_reply_invents_a_spanish_infinitive(content):
        return "unsupported_invented_infinitive"
    if (
        visible_reply_breaks_first_person(content)
        or limit_breaks_the_asked_verb(content, request)
        or visible_reply_says_a_vulgarity(content, request)
    ):
        return "unsupported_broken_person"
    if _limit_changes_the_act(content, request):
        # v3a-final F-w11-t1: ordering tacos is not preparing them. M54 (v3b-devD D-s042 «quiero pastel de camote de
        # una panadería local» → «No preparo el pastel…»): making is denied only when making was asked.
        return "unsupported_changed_act"
    if visible_reply_breaks_word_case(content, request):
        return "unsupported_broken_case"
    if visible_reply_breaks_spanish_plural(content, request):
        # M93 (DEV-D v3u D-s042 «No encargo pastels…»).
        return "unsupported_broken_plural"
    if visible_reply_is_a_fixed_stall(content):
        return "unsupported_fixed_stall"
    normalized = _policy_guard_text(content)
    # LIMITS1699 «Puedes ver tu propio código y analizar si hay alguna
    # falla.»: when the request itself coordinates two actions with «y»/«and»,
    # a denial that mirrors them («no puedo ver ni analizar…») is one plain
    # limit, not a list of partial refusals; the «ni»/«nor» rule steps aside.
    request_coordinates = coordinates_actions(request)
    coordinated_denial = (
        ""
        if request_coordinates
        else r"no puedo\b.{1,160}\bni\b|i cannot\b.{1,160}\b(?:nor|or)\b|"
    )
    forbidden = (
        re.search(
            (
                r"\b(?:"
                + coordinated_denial
                + r"si (?:tienes|necesitas|quieres|deseas)\b|"
                r"no dudes en\b|puedo ayudar(?:te)?\b|estoy aqui para\b|"
                r"avisame\b|avísame\b|"
                r"puedes intentar\b|podrias intentar\b|"
                r"te (?:sugiero|recomiendo)\b|"
                r"if you (?:have|need|want|would like)\b|"
                r"let me know\b|feel free\b|i can help\b|happy to help\b|"
                r"you (?:can|could) try\b|i (?:suggest|recommend)\b"
                r"|please (?:ensure|try)\b|try again\b|"
                r"por favor (?:asegurate|intenta)\b|intenta de nuevo\b|"
                r"no tengo (?:acceso|la capacidad)\b|"
                r"i (?:do not|don t) have (?:access|the capability)\b|"
                r"no puedo (?:interactuar con|controlar) (?:la|el|tu|the|your) "
                r"(?:computadora|computer|sistema operativo|operating system|interfaz|interface)\b|"
                r"(?:access to|acceso a) (?:the |your |tu |el |la )?"
                r"(?:computer|computadora|ordenador|system settings|configuracion del sistema)\b|"
                r"(?:ability|capacidad) (?:to|de) (?:modify|modificar) "
                r"(?:system configurations?|configuraciones? del sistema)\b|"
                r"(?:mis|my) (?:funciones|functions|capacidades|capabilities) "
                r"(?:estan|are) (?:limitadas|limited)\b|"
                r"(?:solo|only) (?:puedo|can) (?:conversar|chat|ayudar con escritura)\b|"
                r"no puedo\b.{1,160}\bno puedo\b|"
                r"i cannot\b.{1,160}\bi cannot\b|"
                r"manualmente\b|manual(?:ly)?\b|you (?:ll|will) need to\b|"
                r"mi funcion es\b|my function is\b|"
                r"variante (?:exacta|solicitada)\b|exact variant\b|"
                r"exactamente la variante\b|combinacion exacta\b|"
                r"exact combination\b|frontera previa\b|previous boundary\b|"
                r"(?:resultado|secuencia) solicitad[oa]\b|"
                r"requested (?:result|sequence)\b|"
                r"debido a (?:la|una) limitacion\b|due to (?:the|a) limitation\b|"
                r"efecto no soportado\b|unsupported effect\b|catalogo activo\b|"
                r"active catalog\b|herramientas disponibles\b|available tools\b|"
                r"politica interna\b|internal policy\b|no hagas preguntas\b|"
                r"do not ask questions\b|no ofrezcas\b|do not offer\b|"
                # «No puedo detener el escuchado por favor»: the request's own
                # courtesy closing the limit is an echo, not BAXY speaking.
                r"(?:por favor|please)\s*$"
                r")"
            ),
            normalized,
            re.IGNORECASE,
        )
        is not None
    )
    if forbidden:
        return "unsupported_forbidden"
    voice = limit_voice_defect(content, request)
    if voice:
        return "unsupported_" + voice
    if request is not None and not _unsupported_answer_mentions_request(
        content,
        request,
    ):
        return "unsupported_missing_anchor"
    # A syntactically tidy answer can still hallucinate the requested artifact
    # instead of stating the bounded limitation (for example, drafting an
    # email that this contract cannot compose). Require an explicit inability.
    has_inability = _unsupported_answer_has_inability(content)
    return "" if has_inability else "unsupported_missing_inability"


def _unsupported_answer_violates_contract(
    value: object,
    request: object = None,
) -> bool:
    """Reject unsafe, internal, or overbroad unsupported prose."""

    return bool(_unsupported_answer_contract_failure(value, request))


def _unsupported_language_answer_violates_contract(value: object) -> bool:
    """Require a model-authored request to repeat in a supported language."""

    content = str(value or "")
    if (
        not content
        or "\n" in content
        or "\r" in content
        or any(marker in content for marker in ("?", "¿", "？"))
        or re.search(r"[.!…]\s+\S", content) is not None
    ):
        return True
    normalized = _policy_guard_text(content)
    mentions_spanish = (
        re.search(
            r"\b(?:espanol|spanish)\b",
            normalized,
        )
        is not None
    )
    mentions_english = (
        re.search(
            r"\b(?:ingles|english)\b",
            normalized,
        )
        is not None
    )
    return not (mentions_spanish and mentions_english)
