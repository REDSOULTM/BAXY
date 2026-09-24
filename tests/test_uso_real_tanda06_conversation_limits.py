"""Tanda 6 (2026-09-24, official window): conversation, content and limits.

- «Escribe un ejemplo de página HTML con ecuaciones matemáticas.» → «No escribo páginas HTML…»: writing a piece of
  code named with its language, or an example of anything, is text written in the chat, never a limit. Typing it
  somewhere, saving or sending it stays an effect.
- «que sabes sobre la el ángel caído» → a recital of BAXY's capabilities: what he knows or can tell about a named
  subject asks for that subject; only himself or what he does is a question about him.

The phrasings below are not the tanda's: they are paraphrases (es/en/spanglish) the fix does not name, with
negative controls.
"""

from __future__ import annotations

import pytest

from baxy_mind.request_reading import INTENT_CAPABILITY, INTENT_IDENTITY, read_request
from baxy_mind.semantic.patterns import conversation_only_content_request
from test_c03_tanda03_served_surface import _RefusingLlm, _turn

# ------------------------------------------------------------------ code and examples are written in the chat


@pytest.mark.parametrize(
    "text",
    [
        "escríbeme una página html con un formulario de contacto",
        "hazme un ejemplo de consulta SQL que una dos tablas",
        "give me an example of a css grid layout",
        "can you write a sql query to count users by country",
        "dame un ejemplo de regex para validar correos",
        "write me a bash one-liner that counts lines",
        "escribe el código html de un botón",
        "dame tres ejemplos de metáforas",
        "write three examples of haiku about autumn",
        "genera un ejemplo de JSON con datos de usuarios",
        "quiero un ejemplo de página web en html y css",
        "necesito un ejemplo de código python que lea un csv",
        "show me an example of a markdown table",
        "Dame el código en LaTex de la fórmula de Bhaskara.",
    ],
)
def test_code_named_by_its_language_and_examples_are_drafted(text: str) -> None:
    assert conversation_only_content_request(text)


@pytest.mark.parametrize(
    "text",
    [
        "escribe hola en el bloc de notas",
        "escribe python en el buscador",
        "abre el ejemplo de html que guardé",
        "guarda un ejemplo de html en el escritorio",
        "crea un archivo html en el escritorio",
        "abre la página html de ejemplos",
        "dame el código del wifi",
        "ejecuta el script de python",
        "write hello in notepad",
        "type an example in the search box",
        "crea una nota con un ejemplo de lista",
        "open the html file",
        "busca ejemplos de html en google",
        "escribe un correo a Ana diciendo que llego tarde",
    ],
)
def test_typing_saving_opening_or_searching_code_is_not_a_draft(text: str) -> None:
    assert not conversation_only_content_request(text)


@pytest.mark.parametrize(
    "text",
    [
        "Escribe un ejemplo de página HTML con ecuaciones matemáticas.",
        "write an example html page with a table please",
        "hazme una consulta sql de ejemplo",
    ],
)
def test_a_drafted_piece_of_code_is_answered_never_refused(text: str) -> None:
    # The real run: the selector proposed a file operation, the strict checks refused it and the turn became
    # «No escribo páginas HTML… Eso no lo hago.» after 11.5 s. The draft is decided before the model.
    model = _RefusingLlm(proposal="filesystem.write.text")

    result = _turn(text, model)

    assert result["kind"] == "conversation"
    assert result["effectOperations"] == []
    assert result.get("conversationKind") != "unsupported"
    assert model.decided == []


# ------------------------------------------------------------------ what he knows about a topic is the topic


@pytest.mark.parametrize(
    "text",
    [
        "qué sabes de la revolución francesa",
        "what do you know about black holes",
        "what can you tell me about the roman empire",
        "qué me puedes decir sobre los agujeros negros",
        "que puedes contarme acerca de los vikingos",
        "tell me what you know about jazz",
        "dime todo lo que sabes sobre los perezosos",
    ],
)
def test_what_he_knows_about_a_named_topic_is_not_a_capability_question(text: str) -> None:
    assert INTENT_CAPABILITY not in read_request(text).intents


@pytest.mark.parametrize(
    ("text", "intent"),
    [
        ("que sabes hacer", INTENT_CAPABILITY),
        ("what can you do", INTENT_CAPABILITY),
        ("qué puedes hacer con la música", INTENT_CAPABILITY),
        ("qué me puedes contar de tus capacidades", INTENT_CAPABILITY),
        ("what can you tell me about what you do", INTENT_CAPABILITY),
        ("qué sabes sobre ti", INTENT_IDENTITY),
        ("what do you know about yourself", INTENT_IDENTITY),
    ],
)
def test_what_he_does_or_who_he_is_still_asks_about_him(text: str, intent: str) -> None:
    assert intent in read_request(text).intents
