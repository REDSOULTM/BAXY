"""C03: la lectura del pedido es única y el compositor no fabrica hechos.

Estas comprobaciones fallaban antes de la reparación de frontera:

* `Good afternoon` y `define DNS in one sentence` se leían como español en
  Python mientras el shell los trataba como inglés, así que el compositor
  recibía `greeting=hola` y su siguiente validador lo vetaba (disc-68/009).
* `hey, close Paint` y `hey, what can you do` perdían el pedido: el contenido
  de usuario se quedaba sólo con los hechos.
* El payload deducía `effect=closed` y `seen.window=true` del verbo del pedido
  y convertía una red sin lectura en `online=false`.
"""

import json
from pathlib import Path

import pytest

from baxy_mind import llm as llm_mod
from baxy_mind.llm import (
    _compose_situation_payload,
    _compose_user_content,
    _message_response_language,
    served_capability_families,
)
from baxy_mind import request_reading as reading_mod
from baxy_mind.request_reading import read_request

ROOT = Path(__file__).resolve().parents[1]
CASES = json.loads(
    (ROOT / "tests/data/request_reading_cases.json").read_text(encoding="utf-8")
)["cases"]


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["text"][:48])
def test_shared_corpus_pins_the_single_request_reading(case: dict) -> None:
    reading = read_request(case["text"])

    assert reading.language == case["language"]
    assert reading.greeting == case["greeting"]
    assert reading.ask == case["ask"]
    assert sorted(reading.intents) == case["intents"]


def test_english_greetings_and_definitions_are_not_spanish() -> None:
    assert _message_response_language("Good afternoon") == "en"
    assert _message_response_language("Good morning") == "en"
    assert _message_response_language("define DNS in one sentence") == "en"
    assert _message_response_language("Hi again") == "en"
    assert _message_response_language("¿Qué hora es?") == "es"
    assert _message_response_language("abre Spotify and pause") == "mixed"


def test_translation_and_explicit_language_win_over_the_text() -> None:
    assert _message_response_language("traduce buenos días al inglés") == "en"
    assert _message_response_language("translate good morning to spanish") == "es"


def test_conversation_language_only_decides_without_evidence() -> None:
    assert read_request("Deimos", conversation_language="en").language == "en"
    assert read_request("open Deimos", conversation_language="es").language == "en"


def test_a_greeting_with_a_request_keeps_the_request() -> None:
    for text, expected in (
        ("hey, close Paint", "close Paint"),
        ("hey, what can you do", "what can you do"),
        ("hola, ¿qué puedes hacer?", "¿qué puedes hacer?"),
    ):
        reading = read_request(text)
        assert reading.greeting == "leading"
        assert reading.ask == expected
        content = _compose_user_content(text, {}, "LANG", reading=reading)
        assert text in content

    only = read_request("Good afternoon")
    assert only.greeting_only
    assert "Good afternoon" not in _compose_user_content(
        "Good afternoon",
        {"situation": {"greeting": "hi"}},
        "LANG",
        reading=only,
    )


def test_the_payload_never_invents_an_effect_from_the_request_verb() -> None:
    closed = _compose_situation_payload(
        {"kind": "conversation", "polarity": "success"},
        "en",
        "close that",
    )

    assert "effect" not in closed
    assert "seen" not in closed


def test_an_unread_network_is_unknown_not_offline() -> None:
    unread = _compose_situation_payload(
        {
            "kind": "result",
            "polarity": "success",
            "operation": "network.status",
            "observed": {"interfaceCount": 2},
        },
        "en",
        "are you connected?",
    )
    read = _compose_situation_payload(
        {
            "kind": "result",
            "polarity": "success",
            "operation": "network.status",
            "observed": {"online": True, "interfaceCount": 2},
        },
        "en",
        "are you connected?",
    )

    assert "seen" not in unread
    assert read["seen"] == {"online": True}


def test_a_failure_keeps_its_polarity_in_the_payload() -> None:
    failure = _compose_situation_payload(
        {"kind": "failure", "polarity": "failure", "cause": "timeout"},
        "es",
        "abre Paint",
    )

    assert failure["outcome"] == "failed"


def test_capabilities_come_from_the_served_catalog() -> None:
    families = served_capability_families(
        ["app.open", "app.close", "audio.status", "system.time", "web.search"]
    )
    payload = _compose_situation_payload(
        {"kind": "conversation", "polarity": "success"},
        "en",
        "what can you do",
        capabilities=families,
    )
    empty = _compose_situation_payload(
        {"kind": "conversation", "polarity": "success"},
        "en",
        "what can you do",
    )

    assert families == ["app", "audio", "system", "web"]
    assert payload["can"] == [
        "open and close apps",
        "read and set the audio",
        "read the clock and the PC state",
        "search the web",
    ]
    assert "beyond" not in payload
    assert "can" not in empty


def test_the_compose_prompt_no_longer_dictates_the_refusal_sentence() -> None:
    assert "I don't do that" not in llm_mod.GRANITE_OOC_EN_USER_MESSAGE_PROMPT
    assert "eso no lo hago" not in llm_mod.GRANITE_OOC_USER_MESSAGE_PROMPT
    assert "close_clip" not in Path(llm_mod.__file__).read_text(encoding="utf-8")


def test_an_english_greeting_reaches_granite_in_english() -> None:
    captured: list[dict] = []

    class FakeClient(llm_mod.LlmRuntime):
        def __init__(self) -> None:  # noqa: D107
            self._gguf = r"D:\BAXYRuntime\assets\models\granite-4.2-3b-Q4_K_M.gguf"

        def _post(self, payload):  # noqa: ANN001
            captured.append(payload)
            return {"choices": [{"message": {"content": "Hi, good to see you."}}]}

    text = FakeClient().compose_user_message(
        "Good afternoon",
        "welcome",
        {"situation": '{"kind":"welcome","polarity":"success"}'},
    )

    assert text == "Hi, good to see you."
    assert captured[0]["messages"][0]["content"] == (
        llm_mod.GRANITE_WELCOME_EN_USER_MESSAGE_PROMPT
    )
    assert '"greeting": "hi"' in captured[0]["messages"][1]["content"]
    assert "hola" not in captured[0]["messages"][1]["content"]


def test_a_spanish_greeting_for_an_english_request_is_still_rejected() -> None:
    assert llm_mod.compose_visible_defect(
        "Buenos días, compa.",
        "welcome",
        "Good afternoon",
        {"situation": '{"kind":"welcome","polarity":"success"}'},
    ) == "wrong_language"


# --- Seguimiento elíptico ---------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "¿por qué importa?",
        "why does it matter?",
        "¿y para qué sirve?",
        "and why does it matter?",
        "¿y para qué se usa?",
        "y cuándo conviene usarla",
        "y eso cómo se usa",
        "para qué lo usaría yo en casa",
        "para qué lo necesita el PC",
        "¿por qué sigue siendo útil?",
    ],
)
def test_a_question_without_its_own_subject_is_elliptical(text: str) -> None:
    assert reading_mod.is_elliptical_followup(text) is True


@pytest.mark.parametrize(
    "text",
    [
        "explain what a VPN is in one sentence",
        "explícame qué es la caché, una frase",
        "qué puedes hacer aquí en el PC",
        "¿Qué hora es?",
        "Buenas",
        "abre la calculadora",
        "no abras nada ahora",
        "define DNS in one sentence",
    ],
)
def test_a_question_that_names_its_subject_is_not_elliptical(text: str) -> None:
    assert reading_mod.is_elliptical_followup(text) is False


@pytest.mark.parametrize(
    ("text", "topic"),
    [
        ("explícame qué es la latencia de red en una frase", "latencia de red"),
        ("explain what DNS caching is in one sentence", "DNS caching"),
        ("qué es una VLAN, una frase", "VLAN"),
        ("define DNS in one sentence", "DNS"),
        ("¿Qué hora es?", None),
        ("abre la calculadora", None),
    ],
)
def test_the_topic_is_read_from_the_words_the_person_used(
    text: str,
    topic: str | None,
) -> None:
    assert reading_mod.request_topic(text) == topic


def test_the_followup_topic_comes_from_the_last_request_that_had_one() -> None:
    history = [
        "explícame qué es un proxy en una frase",
        "¿por qué importa?",
    ]
    assert reading_mod.followup_topic("¿y para qué sirve?", history) == "proxy"


def test_a_new_question_with_its_own_subject_does_not_inherit_the_old_topic() -> None:
    # seguimiento-1/007: «explain what a VPN is» se contestó «¿Para qué sirve un
    # proxy?». Una pregunta que trae su tema no se ancla en el turno anterior.
    history = ["explícame qué es un proxy en una frase"]
    assert (
        reading_mod.followup_topic("explain what a VPN is in one sentence", history)
        is None
    )


def test_an_elliptical_followup_without_a_prior_topic_stays_unresolved() -> None:
    assert reading_mod.followup_topic("¿por qué importa?", []) is None
    assert reading_mod.followup_topic("¿por qué importa?", ["Buenas"]) is None


def test_the_followup_topic_reaches_the_presentation_as_data(monkeypatch) -> None:
    captured: list[dict] = []

    class FakeClient(llm_mod.LlmRuntime):
        def __init__(self) -> None:  # noqa: D107
            self._gguf = r"D:\BAXYRuntime\assets\models\granite-4.2-3b-Q4_K_M.gguf"

        def _post(self, payload, **kwargs):  # noqa: ANN001, ANN003
            captured.append(payload)
            return {
                "choices": [
                    {
                        "message": {
                            "content": (
                                "La caché importa porque guarda datos usados a "
                                "menudo y evita volver a buscarlos."
                            )
                        }
                    }
                ]
            }

    reply, _ = FakeClient().chat(
        "¿por qué importa?",
        history=[
            {"role": "user", "content": "explícame qué es la caché, una frase"},
            {"role": "assistant", "content": "La caché guarda datos ya usados."},
        ],
        conversation_kind="knowledge",
        response_language="es",
        temperature=0.0,
    )

    assert "caché" in reply
    systems = [
        message["content"]
        for message in captured[0]["messages"]
        if message["role"] == "system"
    ]
    assert any("caché" in content for content in systems)
    assert any("no una instrucción" in content for content in systems)


def test_the_composer_receives_the_topic_of_an_elliptical_followup() -> None:
    captured: list[dict] = []

    class FakeClient(llm_mod.LlmRuntime):
        def __init__(self) -> None:  # noqa: D107
            self._gguf = r"D:\BAXYRuntime\assets\models\granite-4.2-3b-Q4_K_M.gguf"

        def _post(self, payload):  # noqa: ANN001
            captured.append(payload)
            return {
                "choices": [
                    {
                        "message": {
                            "content": (
                                "La caché importa porque evita volver a "
                                "buscar los mismos datos."
                            )
                        }
                    }
                ]
            }

    text = FakeClient().compose_user_message(
        "¿por qué importa?",
        "conversation",
        {
            "situation": '{"kind":"conversation","polarity":"success"}',
            "priorRequests": ["explícame qué es la caché, una frase"],
        },
    )

    assert "caché" in text
    sent = captured[0]["messages"][-1]["content"]
    assert "«caché»" in sent
    assert "no una orden" in sent
    # El tema es contexto, no un hecho publicable: no entra en los hechos.
    assert "priorRequests" not in sent


def test_a_followup_answered_with_another_question_is_rejected() -> None:
    facts = {
        "situation": '{"kind":"conversation","polarity":"success"}',
        "priorRequests": ["qué es el kernel, una frase"],
    }
    assert llm_mod.compose_visible_defect(
        "¿Para qué necesita el PC ejecutar tareas específicas?",
        "conversation",
        "para qué lo necesita el PC",
        facts,
    ) == "answered_with_a_question"
    assert llm_mod.compose_visible_defect(
        "El PC necesita el kernel para gestionar sus recursos.",
        "conversation",
        "para qué lo necesita el PC",
        facts,
    ) == ""


def test_a_social_reply_may_still_end_in_a_question() -> None:
    assert llm_mod.compose_visible_defect(
        "Hola, ¿en qué te ayudo?",
        "conversation",
        "hola",
        {"situation": '{"kind":"conversation","polarity":"success"}'},
    ) == ""


@pytest.mark.parametrize(
    "text",
    ["still there?", "¿sigues ahí?", "¿está bien?", "¿todo bien?"],
)
def test_a_presence_check_does_not_inherit_the_previous_topic(text: str) -> None:
    # Es armazón entera, pero no pregunta por el tema: pregunta por quien
    # contesta. Heredar «DNS caching» aquí sería inventar de qué se habla.
    assert reading_mod.is_elliptical_followup(text) is False
    assert (
        reading_mod.followup_topic(text, ["explain what DNS caching is"]) is None
    )


@pytest.mark.parametrize(
    "text",
    [
        "what are your limits on this PC",
        "hi, what do you handle on this PC",
        "qué no puedes hacer en este PC",
        "what can you do here",
    ],
)
def test_a_demonstrative_with_its_noun_is_not_a_reference_back(text: str) -> None:
    # panel-opus-13/051: «what are your limits on this PC» se contestó con la
    # definición de máscara de subred del turno anterior. «this» ahí es el
    # determinante de «PC».
    assert reading_mod.is_elliptical_followup(text) is False
    assert (
        reading_mod.followup_topic(text, ["what is a subnet mask in one sentence"])
        is None
    )


@pytest.mark.parametrize("text", ["close that", "ábreme eso", "open it"])
def test_a_deictic_order_is_not_an_elliptical_followup(text: str) -> None:
    # Son encargos con un referente sin resolver, no preguntas de seguimiento:
    # los resuelve la aclaración deíctica, no el tema del turno anterior.
    assert reading_mod.is_elliptical_followup(text) is False


# --- El encargo del turno no se publica ------------------------------------


def test_the_visible_text_never_names_the_instruction_it_was_given() -> None:
    # panel-opus-13/044: «The capital of Peru is Lima. (Note: I'm responding in
    # English as per the internal language policy.)». No es una copia sino una
    # cita del rótulo, y salía igual a pantalla.
    instructions = [
        "Internal language policy: answer exclusively in English.",
        "Política interna de idioma: responde exclusivamente en español.",
    ]
    assert llm_mod.repeats_a_sent_instruction(
        "The capital of Peru is Lima.\n\n(Note: I'm responding in English as "
        "per the internal language policy.)",
        instructions,
    )
    assert llm_mod.repeats_a_sent_instruction(
        "Según la política interna de idioma, contesto en español.",
        instructions,
    )


@pytest.mark.parametrize(
    "reply",
    [
        "The capital of Peru is Lima.",
        "La capital de Perú es Lima.",
        "Un router enruta el tráfico entre dispositivos de una red.",
        "La latencia de red importa porque afecta el tiempo de respuesta.",
        "I can open and close apps, move windows, and read the clock.",
    ],
)
def test_an_answer_that_only_answers_is_not_taken_for_a_leak(reply: str) -> None:
    assert not llm_mod.repeats_a_sent_instruction(
        reply,
        [
            "Internal language policy: answer exclusively in English.",
            "Política interna del turno: conocimiento o explicación. Responde "
            "directamente con la información útil disponible.",
        ],
    )


def test_the_rule_needs_no_list_of_forbidden_phrases() -> None:
    # La garantía se deriva de lo enviado: cambiar la instrucción cambia lo
    # que se veta, sin tocar ninguna lista.
    assert llm_mod.repeats_a_sent_instruction(
        "Contesto según la regla inventada de hoy.",
        ["Regla inventada de hoy: contesta en una frase."],
    )
    assert not llm_mod.repeats_a_sent_instruction(
        "Contesto según la regla inventada de hoy.",
        ["Otra regla distinta: contesta en una frase."],
    )


# --- Capacidades y límites --------------------------------------------------


@pytest.mark.parametrize(
    ("text", "intent"),
    [
        ("cuáles son tus límites aquí", "refuse"),
        ("what are your limits on this PC", "refuse"),
        ("qué te niegas a hacer aquí", "refuse"),
        ("qué no puedes hacer en este PC", "refuse"),
        ("what do you not do here", "refuse"),
        ("hi, what do you handle on this PC", "capability"),
        ("en qué me puedes ayudar", "capability"),
        ("what can you do here", "capability"),
    ],
)
def test_asking_what_the_product_does_is_read_by_its_shape(
    text: str,
    intent: str,
) -> None:
    # La lista de frases enteras dejaba fuera «cuáles son tus límites aquí» y
    # «what do you handle», y esas preguntas se contestaban con una aclaración
    # construida con vocabulario del planificador (panel-opus-13/038, /052).
    assert intent in reading_mod.read_request(text).intents


def test_asking_both_what_it_does_and_what_it_does_not_is_a_capability_ask() -> None:
    reading = reading_mod.read_request(
        "Explícame con calma qué puedes hacer en este PC y qué no haces, "
        "sin abrir nada."
    )
    assert "capability" in reading.intents
    assert "refuse" not in reading.intents


@pytest.mark.parametrize(
    "text",
    [
        "keep talking without launching anything",
        "keep chatting without opening apps",
        "sigue charlando sin abrir programas",
        "continue without opening apps",
    ],
)
def test_continuing_without_apps_is_read_by_the_verb(text: str) -> None:
    assert "continue_constraint" in reading_mod.read_request(text).intents


@pytest.mark.parametrize(
    "text",
    ["keep the volume at 20", "sigue así", "abre la calculadora"],
)
def test_a_bare_continue_verb_does_not_carry_the_constraint(text: str) -> None:
    assert "continue_constraint" not in reading_mod.read_request(text).intents


@pytest.mark.parametrize(
    ("reply", "asked"),
    [
        ("¿Cuáles son los límites de esta PC?", "cuáles son tus límites aquí"),
        (
            "¿Qué específicamente no puedes hacer en este PC?",
            "qué no puedes hacer en este PC",
        ),
        (
            "Can you tell me what you'd like to do on this PC?",
            "hi, what do you handle on this PC",
        ),
    ],
)
def test_a_catalog_answerable_ask_is_never_answered_with_a_question(
    reply: str,
    asked: str,
) -> None:
    assert llm_mod.compose_visible_defect(
        reply,
        "conversation",
        asked,
        {"situation": '{"kind":"conversation","polarity":"success"}'},
    )


def test_the_catalog_answer_itself_passes() -> None:
    assert (
        llm_mod.compose_visible_defect(
            "Solo hago el trabajo de este PC y nada más.",
            "conversation",
            "cuáles son tus límites aquí",
            {"situation": '{"kind":"conversation","polarity":"success"}'},
        )
        == ""
    )


def test_the_persons_own_words_are_not_a_copied_instruction() -> None:
    # limites-19/009: contestar «keep talking without launching anything» es
    # decir «I will keep talking without launching anything», y vetarlo agotó
    # el turno seis veces. Misma exención que los términos prohibidos.
    instructions = ["keep talking without launching anything. Una frase."]
    assert not llm_mod.repeats_a_sent_instruction(
        "I will keep talking without launching anything.",
        instructions,
        "keep talking without launching anything",
    )
    assert llm_mod.repeats_a_sent_instruction(
        "I will keep talking without launching anything.",
        instructions,
        "hola",
    )


@pytest.mark.parametrize(
    ("reply", "asked"),
    [
        (
            "I'll keep talking without launching anything.",
            "keep talking without launching anything",
        ),
        (
            "I will keep chatting without opening any apps.",
            "keep chatting without opening apps",
        ),
    ],
)
def test_answering_with_the_words_of_the_request_is_not_prompt_vocabulary(
    reply: str,
    asked: str,
) -> None:
    # «keep talking» está en la lista de vocabulario del encargo, así que la
    # respuesta correcta se vetaba y el turno se agotaba (limites-21/009).
    assert (
        llm_mod.compose_visible_defect(
            reply,
            "conversation",
            asked,
            {"situation": '{"kind":"conversation","polarity":"success"}'},
        )
        == ""
    )


@pytest.mark.parametrize(
    "reply",
    ["Keep talking, one short sentence.", "Name the local clock."],
)
def test_prompt_vocabulary_the_person_never_used_is_still_vetoed(reply: str) -> None:
    assert (
        llm_mod.compose_visible_defect(
            reply,
            "conversation",
            "hola",
            {"situation": '{"kind":"conversation","polarity":"success"}'},
        )
        == "copied_instruction"
    )
