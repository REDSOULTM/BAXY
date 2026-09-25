"""Tanda 6 (2026-09-24, official window): conversation, content and limits.

- «Escribe un ejemplo de página HTML con ecuaciones matemáticas.» → «No escribo páginas HTML…»: writing a piece of
  code named with its language, or an example of anything, is text written in the chat, never a limit. Typing it
  somewhere, saving or sending it stays an effect.
- «que sabes sobre la el ángel caído» → a recital of BAXY's capabilities: what he knows or can tell about a named
  subject asks for that subject; only himself or what he does is a question about him.
- «¿Es posible la herencia múltiple en Java?» died as dumps_interfaces (shell policy; tested in
  C03UsoRealComposeTests): «interfaces» is ordinary vocabulary, the machine's interface list is not.
- «haz una carcajada cuando quieras» → a reply dragging two earlier turns; «ríete diabólicamente» → «te río de
  verdad 😈»: a laugh asked for is free content, written out on the spot.
- «debieras saber que me gusta el jazz» → «Gracias, ya lo tengo en cuenta. ¿Quieres que te recomiende…?»: a taste
  told (with a frame that only tells it, after earlier turns too) gets a listener's acknowledgement, never a
  claim that it was kept (saving needs the explicit request) nor an offer.
- «Abre el app para ver mis pics.» → «No se encontró la aplicación…»: a built-in app named by what it is for.
- «Activate el modo de privacy» 8.4 s, «stop la camera inteligente» 9.8 s: the unsupported contract rejected «No
  X. Eso no lo hago.» and «No tengo whisper mode.», so both drafts, a second whole decision and a recovery were
  paid. The plain limit restated passes, and a limit whose wording failed is not decided twice.

The phrasings below are not the tanda's: they are paraphrases (es/en/spanglish) the fix does not name, with
negative controls.
"""

from __future__ import annotations

import pytest

from baxy_mind import llm
from baxy_mind.__main__ import _retry_side_effect_free_turn
from baxy_mind.llm import ConversationReplyContractError
from baxy_mind.semantic.request import INTENT_CAPABILITY, INTENT_IDENTITY, read_request
from baxy_mind.semantic.patterns import (
    conversation_only_content_request,
    first_person_preference,
    resolve_application_catalog_app_id,
)
from test_c03_tanda03_served_surface import _RefusingLlm, _turn
from test_uso_real_tanda05_apps_media import ENGLISH_WINDOWS, SPANISH_WINDOWS, _opened

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


# ------------------------------------------------------------------ a laugh asked for is content


@pytest.mark.parametrize(
    "text",
    [
        "ríete como un villano",
        "suelta una risa malvada",
        "give me your best evil laugh",
        "laugh for me",
        "échate una carcajada, anda",
        "puedes reírte un poco?",
        "do a maniacal laugh",
        "haz una risotada cuando puedas",
    ],
)
@pytest.mark.parametrize("has_history", [False, True])
def test_a_laugh_asked_for_is_free_content_whatever_came_before(text: str, has_history: bool) -> None:
    assert llm._conversation_presentation_shape(text, conversation_kind="knowledge", has_history=has_history) == (
        "free_content"
    )


@pytest.mark.parametrize(
    "text", ["no te rías", "¿de qué te ríes?", "por qué te ríes tanto", "la risa es buena para la salud"],
)
def test_talk_about_laughing_is_not_a_laugh_asked_for(text: str) -> None:
    assert llm._conversation_presentation_shape(text, conversation_kind="knowledge", has_history=True) != (
        "free_content"
    )


def test_a_laugh_is_short_and_a_joke_is_not() -> None:
    violates = llm._shaped_conversation_answer_violates_contract
    assert not violates("¡Muajajaja!", "ríete como un villano", "free_content")
    assert violates("¡Ja!", "cuéntame un chiste", "free_content")
    # The laugh still ends without a question or a menu.
    assert violates("¡Jajaja! ¿Quieres otra?", "ríete como un villano", "free_content")


# ------------------------------------------------------------------ a taste told is acknowledged, never stored


@pytest.mark.parametrize(
    ("text", "thing"),
    [
        ("para que sepas, me encanta el rock", "el rock"),
        ("you should know that I love jazz", "jazz"),
        ("fyi I really like pizza", "pizza"),
        ("te cuento que odio el reguetón", "el regueton"),
        ("también me gusta el café", "el cafe"),
        ("deberías saber que prefiero el té", "el te"),
    ],
)
def test_a_taste_told_with_a_telling_frame_is_a_preference(text: str, thing: str) -> None:
    assert first_person_preference(text) == thing
    assert llm._conversation_presentation_shape(text, conversation_kind="social", has_history=True) == (
        "preference_ack"
    )


@pytest.mark.parametrize(
    "text",
    ["recuerda que me gusta el jazz", "remember that I like jazz", "deberías saber que me gusta que me avisen"],
)
def test_asking_to_remember_a_taste_or_a_wish_is_not_a_preference_told(text: str) -> None:
    # Saving needs the explicit request, and it is the memory operation's, not an acknowledgement.
    assert first_person_preference(text) is None


@pytest.mark.parametrize("text", ["me gusta esa", "I like that one", "me gusta eso que dijiste"])
def test_a_taste_pointing_back_at_earlier_turns_keeps_the_dialogue(text: str) -> None:
    assert llm._conversation_presentation_shape(text, conversation_kind="social", has_history=True) != (
        "preference_ack"
    )


@pytest.mark.parametrize(
    "draft",
    [
        "Gracias, ya lo tengo en cuenta.",
        "Anotado: te gusta el jazz.",
        "Tomo nota de que te gusta el jazz.",
        "Noted, you love jazz.",
        "I'll keep that in mind: you love jazz.",
    ],
)
def test_an_acknowledgement_never_claims_to_keep_the_taste(draft: str) -> None:
    assert llm._shaped_conversation_answer_violates_contract(
        draft, "debieras saber que me gusta el jazz", "preference_ack",
    )


def test_an_acknowledgement_naming_the_taste_passes() -> None:
    assert not llm._shaped_conversation_answer_violates_contract(
        "Qué bien que te guste el jazz.", "debieras saber que me gusta el jazz", "preference_ack",
    )


# ------------------------------------------------------------------ the app named by what it is for


@pytest.mark.parametrize(
    ("text", "spanish", "english"),
    [
        ("open the app to look at my pictures", "Fotos", "Photos"),
        ("ábreme la aplicación de mis fotos", "Fotos", "Photos"),
        ("launch the app for viewing my photos", "Fotos", "Photos"),
        ("abre la app pa ver las fotos", "Fotos", "Photos"),
        ("abre el programa para sacar fotos", "Cámara", "Camera"),
        ("open the app for taking photos", "Cámara", "Camera"),
    ],
)
def test_a_built_in_app_named_by_what_it_is_for_opens(text: str, spanish: str, english: str) -> None:
    assert _opened(text, SPANISH_WINDOWS) == spanish
    assert _opened(text, ENGLISH_WINDOWS) == english


@pytest.mark.parametrize(
    "text", ["abre la app para ver películas", "abre el programa de radio", "open the app for my emails"],
)
def test_an_app_described_by_something_no_built_in_app_is_for_stays_unknown(text: str) -> None:
    assert resolve_application_catalog_app_id(text, SPANISH_WINDOWS) is None


# ------------------------------------------------------------------ a limit costs one decision


@pytest.mark.parametrize(
    ("draft", "asked"),
    [
        ("No detengo la cámara inteligente. Eso no lo hago.", "para la cámara inteligente"),
        ("No activo el modo avión. Eso no lo hago.", "turn on el airplane mode porfa"),
        ("I don't turn on airplane mode. That's not something I do.", "enable airplane mode"),
        ("No tengo modo susurro.", "activa el modo susurro"),
        ("I don't have a whisper mode.", "switch to whisper mode"),
    ],
)
def test_a_plain_limit_restated_or_a_missing_mode_is_a_limit(draft: str, asked: str) -> None:
    assert llm._unsupported_answer_contract_failure(draft, asked) == ""


@pytest.mark.parametrize(
    ("draft", "asked"),
    [
        ("No activo el modo avión. Pero puedo bajar el volumen.", "turn on el airplane mode porfa"),
        ("No activo el modo avión. Lo puedes hacer en la configuración de Windows.", "turn on el airplane mode"),
        ("No activo el modo avión. ¿Quieres otra cosa?", "turn on el airplane mode"),
        ("No tengo información sobre el modo avión.", "turn on el airplane mode"),
    ],
)
def test_what_follows_a_limit_is_still_only_the_limit(draft: str, asked: str) -> None:
    assert llm._unsupported_answer_contract_failure(draft, asked) != ""


def test_a_limit_whose_wording_failed_is_not_decided_twice() -> None:
    calls = 0

    def operation() -> dict:
        nonlocal calls
        calls += 1
        raise ConversationReplyContractError("unsupported_shape")

    with pytest.raises(ConversationReplyContractError):
        _retry_side_effect_free_turn(operation)
    # The same decision would write the same seeded drafts again; the recovery says the limit.
    assert calls == 1


def test_any_other_failed_attempt_is_still_retried_once() -> None:
    calls = 0

    def operation() -> dict:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ConversationReplyContractError("knowledge_not_answered")
        return {"type": "turn.result"}

    assert _retry_side_effect_free_turn(operation)["turn_attempts"] == 2
