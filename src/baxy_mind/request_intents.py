"""What the reading of the request says the turn is (a knowledge, capability or identity question, a
constraint, an ambiguous act, a greeting) and the turn's visible language. ``semantic.request`` reads; these only ask.
"""

from __future__ import annotations

import re
import unicodedata

from .semantic.request import (
    INTENT_AMBIGUOUS_ACTION, INTENT_CAPABILITY, INTENT_CONTINUE_CONSTRAINT, INTENT_IDENTITY, INTENT_KNOWLEDGE,
    INTENT_NEGATIVE_CONSTRAINT, INTENT_REFUSE, read_request,
)
from .semantic.conversation import translation_without_its_text


def _message_response_language(text: str) -> str:
    """Idioma visible del turno. La lectura del pedido es el único owner."""

    return read_request(text).language


def _starts_with_request_imperative(text: str) -> bool:
    folded = unicodedata.normalize("NFKD", text.casefold())
    folded = "".join(
        character for character in folded if not unicodedata.combining(character)
    )
    return (
        re.search(
            r"^\s*(?:(?:list|show|tell|open|create|set|mute|close|delete|send)\b|"
            r"(?:lista|muestra)\s+(?:el|la|los|las|un|una)\b|"
            r"(?:dime|abre|crea|pon|silencia|cierra|elimina|envia|guarda|"
            # AUDIO1239 H0465 «poné el volumen al 30» → final «Poné el volumen
            # al 30.»: the voseo and clitic forms of «pon» are the same echo.
            r"pone|poneme|ponme|ponelo|ponlo)\b)",
            folded,
        )
        is not None
    )


def _looks_like_knowledge_question(user_text: str) -> bool:
    return read_request(user_text).has(INTENT_KNOWLEDGE)


def _looks_like_greeting_ask(user_text: str) -> bool:
    """El pedido saluda. Puede traer además una petición: no se descarta."""

    return read_request(user_text).greets


def _looks_like_capability_question(user_text: str) -> bool:
    return read_request(user_text).has(INTENT_CAPABILITY)


def _knowledge_to_answer(user_text: str) -> bool:
    """A knowledge ask a clarification cannot stand in for. M75 (DEV-D v3l D-w15-t3 «traducelo al ingles que es para
    mi jefa»): a translation of something only pointed at has no text to translate, so asking which is the reply; all
    three questions died on knowledge_question and the turn ended in ⚠."""

    return _looks_like_knowledge_question(user_text) and not translation_without_its_text(user_text)


def _looks_like_ambiguous_action(user_text: str) -> bool:
    return read_request(user_text).has(INTENT_AMBIGUOUS_ACTION)


def _looks_like_continue_constraint(user_text: str) -> bool:
    return read_request(user_text).has(INTENT_CONTINUE_CONSTRAINT)


def _looks_like_negative_constraint(user_text: str) -> bool:
    return read_request(user_text).has(INTENT_NEGATIVE_CONSTRAINT)


def _looks_like_identity_question(user_text: str) -> bool:
    return read_request(user_text).has(INTENT_IDENTITY)


def _looks_like_refuse_question(user_text: str) -> bool:
    return read_request(user_text).has(INTENT_REFUSE)
