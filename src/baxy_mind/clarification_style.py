"""The language and register of any clarification question, and the clarifications said without the
model.
"""

from __future__ import annotations

import re

from .semantic.normalize import fold
from .semantic.conversation import ambiguous_action_verb
from .request_intents import _looks_like_ambiguous_action, _message_response_language
from .llm_prompts import MIXED_RESPONSE_LANGUAGE_POLICY


# cien-41 y cien-45, turno 027: dentro de su bloque el modelo contesta el
# pedido ambiguo negando en vez de preguntar, los tres candidatos caen en el
# veto correcto y el turno termina sin respuesta. La lista de pedidos
# ambiguos es cerrada, asi que la pregunta se arma sin el modelo (el verbo lo
# lee semantic.conversation.ambiguous_action_verb).
_AMBIGUOUS_ACTION_QUESTIONS = {
    "open": ("What do you want me to open?", "¿Qué quieres que abra?"),
    "close": ("What do you want me to close?", "¿Qué quieres que cierre?"),
}


def _ambiguous_action_question(user_text: str, language: str) -> str:
    """La pregunta que le toca a un pedido sin objeto, sin pasar por el modelo."""

    if not _looks_like_ambiguous_action(user_text):
        return ""
    action = ambiguous_action_verb(user_text)
    if action is not None:
        english, spanish = _AMBIGUOUS_ACTION_QUESTIONS[action]
        return english if language == "en" else spanish
    return (
        "What exactly do you want me to do?"
        if language == "en"
        else "¿Qué quieres que haga exactamente?"
    )


_CLARIFICATION_LANGUAGE = {
    "es": "Idioma obligatorio de la pregunta: español.",
    "en": "Mandatory language for the question: English.",
    "mixed": MIXED_RESPONSE_LANGUAGE_POLICY,
}

# BAXY tutea (00_IDENTIDAD). Las preguntas de aclaración salían de usted y en
# el idioma que el modelo eligiera: «close that» se contestó en español y
# «qué no puedes hacer en este PC» con «¿… le gustaría …?».
_CLARIFICATION_STYLE = "Trata a la persona de tú, nunca de usted, y no la nombres."

# «abrí eso» read as the user's own past action («¿Qué es lo que abriste?»,
# DIALOGUE1277 H0531): second-person preterites of the request verbs.
_PAST_ACTION_ATTRIBUTED_TO_USER = re.compile(
    r"\b(?:abriste|cerraste|mandaste|enviaste|borraste|eliminaste|hiciste|"
    r"guardaste|pusiste|subiste|bajaste|aumentaste|redujiste|disminuiste|"
    r"you\s+(?:opened|closed|sent|deleted|did|raised|lowered|turned))\b",
    re.IGNORECASE,
)


_INVENTED_ACTION_VERB = re.compile(
    r"\b(?:abra|abrir|cierre|cerrar|mande|mandar|envie|enviar|borre|borrar|"
    r"elimine|eliminar|guarde|guardar|busque|buscar|reproduzca|reproducir|"
    r"open|close|send|delete|save|search|play)\b",
    re.IGNORECASE,
)


# The noise clarification must name what arrived («signos», «cifras», «una
# letra», «eso que escribiste») or say it sees no request in it.
_REFLEXIVE_COMPARISON = re.compile(
    r"\bte\s+(?:compar|parec|asemej)|\byourself\b|\bcompare\s+you\s+to\b"
)
def _cut_request_tail(text: str) -> str:
    """The last three words of a request that arrived cut (FILES H0426)."""

    words = re.findall(r"[^\s]+", str(text).strip())
    return " ".join(words[-3:])


def _bare_path_name(text: str) -> str:
    """The last segment of a pasted path (FILES H0299); the folders stay unsaid."""

    return re.split(r"[\\/]", str(text).strip().rstrip("\\/"))[-1].strip()


# UNRES1875 H0639 (a bare redaction placeholder): the reading of that text
# is English, so the mandatory clarification language is English, and the
# model answered that it saw only signs and redacted text and no clear
# request there. That is the acknowledgement this guard asks for, but its
# English half had neither "signs" nor "I don't see a request" while its
# Spanish half already took the same words; both attempts were rejected, the
# turn died and the generic recovery question was published instead. The two
# halves now carry the same vocabulary.
_NOISE_ACKNOWLEDGED = re.compile(
    r"\b(?:signos?|simbolos?|cifras?|digitos?|numeros?|letras?|emojis?|"
    r"caracter(?:es)?|interrogaci[oó]n|mensaje|escribiste|enviaste|mandaste|"
    r"llego|recib[ií]|no (?:veo|encuentro|logro|entiendo|reconozco)|"
    r"(?:no|ning[uú]n)\s+(?:\w+\s+){0,2}pedido|"
    r"con eso|con esto|de eso|de esto|"
    r"symbols?|signs?|digits?|numbers?|letters?|characters?|question marks?|"
    r"(?:do(?:es)?\s+not|don'?t|doesn'?t|cannot|can'?t)\s+"
    r"(?:see|find|read|understand|recognis|recogniz)\w*|"
    r"(?:no|any)\s+(?:\w+\s+){0,2}request|"
    r"you (?:sent|wrote|typed)|with that|with this)\b",
    re.IGNORECASE,
)


_fold_dialogue_text = fold  # the single normalization (semantic.normalize)


def _clarification_style_messages(text: str) -> list[dict[str, str]]:
    """Contrato de idioma y trato para cualquier pregunta de aclaración."""

    return [
        {
            "role": "system",
            "content": _CLARIFICATION_LANGUAGE[_message_response_language(text)],
        },
        {"role": "system", "content": _CLARIFICATION_STYLE},
    ]
