"""Development corpus 2026-09-23, second set (MASSIVE email / contacts / social): what was still read by nobody.

- The address book is the person's own: finding, counting or reading an entry, or the address, number or mail of
  someone of their life («what is mom's email address», «cúal es la dirección para juan»), is a plain limit, never
  a web search and never an answer from memory. Public places and companies keep their lookup.
- Mail arrived that is checked, controlled, received or opened first is the mailbox read; «por mí» with its accent
  is the pronoun, not a cut message.
- Messages arrived with no mail named are the chats (a limit), never a lookup.
- Posting, a status, a complaint to a company, or anything asked of the person's own account on a network is the
  social limit; «pon un tuit» is never a song. Writing the complaint text is a draft.
Phrasings are written fresh (Spanish, English, spanglish), not copied from the corpus.
"""

from __future__ import annotations

import pytest

from baxy_mind.__main__ import _prepare_turn_result
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic import reading
from baxy_mind.semantic.guards import _unresolved_input_kind, cut_request_tail
from baxy_mind.semantic.messaging import contact_book_request, inbox_read_request, social_network_request
from baxy_mind.semantic.notes import agenda_read_request
from baxy_mind.semantic.patterns import (
    conversation_only_content_request,
    effect_request_is_authoritative,
    known_unsupported_effect_request,
    resolve_explicit_clarification_intent,
    resolve_explicit_effects,
)
from test_c03_pointless_questions import _NoEvidence, _tool

_OPS = (
    "email.latest.read", "email.latest.reply", "email.send", "message.send", "message.recipient.resolve",
    "message.draft", "calendar.event.list", "media.play.youtube", "media.status", "web.search", "app.open",
)


# --- the address book --------------------------------------------------------------------------------------------

_CONTACT_REQUESTS = [
    "cuántos contactos tengo guardados",
    "busca a pedro en mis contactos",
    "búscame un contacto",
    "abre la agenda de contactos y dime cuántos hay",
    "how many contacts are in my phone book",
    "find a contact called maria",
    "show me the details of that contact",
    "cuál es el número de teléfono de mi hermana",
    "dame el celular de mi jefe",
    "necesito la dirección de mi abuela",
    "pásame el correo de martín",
    "what's grandma's phone number",
    "what is my brother's address",
    "tell me the email address of my coworker",
    "is this the right area code for my dentist",
    "what's the number for alex",
    "dime el teléfono de paco",
    "give me lucas phone number",
    "busca el nuevo número de sara que guardé ayer",
    "find the email address for sam that i saved last week",
    "agrega a juan a mis contactos",
    "save this number to my contacts",
    "i'd like this new email to be added to my contacts",
    "añade a la ferretería a mis correos de contacto",
    "put this new email with my contact",
]


@pytest.mark.parametrize("text", _CONTACT_REQUESTS)
def test_the_address_book_and_the_data_of_the_persons_people_are_a_plain_limit(text: str) -> None:
    assert contact_book_request(text)
    assert known_unsupported_effect_request(text, _OPS)
    assert effect_request_is_authoritative(text)
    assert resolve_explicit_effects(text, _OPS) is None


@pytest.mark.parametrize(
    "text",
    [
        "cuál es la dirección de la casa blanca",
        "what's the phone number for dominos",
        "dame el teléfono de movistar",
        "información de contacto de apple",
        "contact information for the city council",
        "necesito lentes de contacto",
        "make eye contact",
        "me puse en contacto con el banco",
        "cuál es mi dirección ip",
        "manda un whatsapp a juan que diga hola",
        "escribe un correo a juan",
        "lee el correo de juan",
        "the number of planets in the solar system",
        "no busques el número de mi hermana",
        "el mail de rodrigo traía datos adjuntos",
        "dime la dirección de jennifer lopez",
        "do you know the phone number of michael jordan",
        "envía un correo a un nuevo contacto",
        "send an email to this contact",
        "hay algún correo nuevo de mis contactos",
    ],
)
def test_public_data_mail_and_other_contact_words_are_not_the_book(text: str) -> None:
    assert not contact_book_request(text)


@pytest.mark.parametrize(
    "text",
    ["cómo agrego un contacto en mi celular", "how do i add a contact on my phone", "ayer tuiteé sobre el partido"],
)
def test_how_to_and_a_story_grant_no_authority(text: str) -> None:
    assert not effect_request_is_authoritative(text)


def test_the_book_named_agenda_is_not_the_calendar() -> None:
    assert not agenda_read_request("cuántos contactos tengo en mi agenda")
    assert agenda_read_request("qué tengo en mi agenda mañana")


# --- the mailbox -------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "controla mi correo por favor",
        "contrólame el mail",
        "did i receive any emails this morning",
        "did i get an email from my bank",
        "mira lo que marta me ha escrito en su correo",
        "qué me han mandado por email",
        "hay algún correo nuevo de mis contactos",
    ],
)
def test_mail_controlled_received_or_written_to_me_is_the_mailbox_read(text: str) -> None:
    assert inbox_read_request(text)
    intent = resolve_explicit_effects(text, _OPS)
    assert intent is not None and intent.operations == ("email.latest.read",)


@pytest.mark.parametrize(
    "text",
    [
        "abre mi correo y revisa si hay mensajes nuevos",
        "entra a mi bandeja de entrada y mira los correos nuevos",
        "open my email and check for new mail",
    ],
)
def test_opening_the_mailbox_to_look_at_what_arrived_is_the_read(text: str) -> None:
    got = reading.read(text, available_operations=_OPS)
    assert got.effects is not None and got.effects.operations == ("email.latest.read",)


@pytest.mark.parametrize(
    "text",
    [
        "carlos me ha escrito un correo, dile que mañana lo llamo",
        "di al correo que me ha mandado ana que ya pagué",
        "este correo nuevo agrégalo a mis contactos",
    ],
)
def test_answering_or_keeping_what_arrived_is_not_the_read(text: str) -> None:
    assert not inbox_read_request(text)


def test_opening_the_mailbox_then_another_order_keeps_its_compound() -> None:
    got = reading.read("abre mi correo y pon música", available_operations=_OPS)
    assert got.source != "mailbox_opened"


@pytest.mark.parametrize(
    "text",
    ["revisa mis correos nuevos por mí", "hazlo por mi ahora mismo por favor por mi", "lee los correos de hoy por mí"],
)
def test_por_mi_closes_the_request(text: str) -> None:
    assert cut_request_tail(text) is None
    assert _unresolved_input_kind(text) != "cut_request"


def test_a_possessive_cut_short_is_still_cut() -> None:
    assert cut_request_tail("guarda el archivo nuevo en la carpeta de mi") is not None


@pytest.mark.parametrize(
    "text",
    [
        "ayúdame a escribir un correo a chofin",
        "me ayudarías a mandar un mail a ricardo",
        "can you help me write an email to bob",
        "puedes escribir un correo a juan",
    ],
)
def test_help_to_write_a_mail_asks_the_address(text: str) -> None:
    intent = resolve_explicit_clarification_intent(text, _OPS)
    assert intent is not None and intent.operations == ("email.send",) and intent.missing_fields == ("to",)


# --- messages with no mail named ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "tengo mensajes sin leer",
        "cuántos mensajes nuevos tengo",
        "do i have any unread messages",
        "cuándo me llegó el mensaje de laura",
        "when did i receive that text from mike",
    ],
)
def test_messages_arrived_without_mail_are_the_chat_limit(text: str) -> None:
    assert known_unsupported_effect_request(text, _OPS)
    assert resolve_explicit_effects(text, _OPS) is None


@pytest.mark.parametrize(
    "text",
    [
        "tengo un mensaje de error en la consola",
        "manda un mensaje nuevo a juan",
        "tengo correos sin leer",
        "the error messages i received are weird",
    ],
)
def test_error_messages_sending_or_mail_are_not_the_chat_limit(text: str) -> None:
    from baxy_mind.semantic.patterns import chat_read_request
    from baxy_mind.semantic.normalize import fold

    assert not chat_read_request(fold(text))


# --- social networks ---------------------------------------------------------------------------------------------

_SOCIAL = [
    "pon un tuit a movistar quejándote del internet",
    "deja un tweet para nike diciendo que tardan mucho",
    "me atendieron fatal en el banco, quiero tuiteárselo",
    "necesito twittearles lo mal que funciona",
    "postea en tumblr que hoy es mi cumple",
    "sube una foto a snapchat",
    "estado de instagram: de vacaciones",
    "twitter status working from home",
    "qué hay de nuevo en mi facebook",
    "cuántos seguidores tengo en mi instagram",
    "how many followers does my tiktok have",
    "what's going on in my social media",
    "any new comments on my latest instagram post",
    "quéjate con samsung de que mi tele no enciende",
    "complaint to amazon about my late package",
    "what are my last photos on facebook",
]


@pytest.mark.parametrize("text", _SOCIAL)
def test_posting_complaining_or_asking_of_the_own_account_is_the_social_limit(text: str) -> None:
    assert social_network_request(text)
    assert known_unsupported_effect_request(text, _OPS)
    assert effect_request_is_authoritative(text)
    assert resolve_explicit_effects(text, _OPS) is None


@pytest.mark.parametrize(
    "text",
    [
        "abre mi instagram",
        "cierra mi facebook",
        "mis redes sociales favoritas son instagram y tiktok",
        "qué son las redes sociales",
        "what is social media",
        "is facebook down",
        "escribe una queja para la municipalidad",
        "me quejo de ti",
    ],
)
def test_navigation_talk_and_definitions_are_not_the_social_limit(text: str) -> None:
    assert not social_network_request(text)


def test_social_media_is_not_what_plays() -> None:
    assert resolve_explicit_effects("tell me what happened on my social media", _OPS) is None


@pytest.mark.parametrize(
    "text", ["por favor escribe una queja para mi casero", "redacta un reclamo para la aerolínea"],
)
def test_writing_the_complaint_is_a_draft(text: str) -> None:
    assert conversation_only_content_request(text)
    assert not social_network_request(text)


# --- the whole turn ----------------------------------------------------------------------------------------------


class _ShapeSaysNoEffectLlm:
    """A model whose only word here is the shape verifier's «no effect»; it must not be asked to decide."""

    def __init__(self) -> None:
        self.chat_kinds: list[str] = []

    @staticmethod
    def decide_turn(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise AssertionError("the readers close this turn before the model decides")

    def chat(self, _text: str, **kwargs: object) -> tuple[str, list[object]]:
        self.chat_kinds.append(str(kwargs.get("conversation_kind")))
        return "Eso no lo hago.", []

    @staticmethod
    def public_lookup_requested(_text: str) -> bool:
        return True

    @staticmethod
    def _verify_semantic_effect_shape(_text: str) -> tuple[str, str]:
        return "no_effect", "zero"

    @staticmethod
    def detect_response_language(_text: str) -> str:
        return "es"

    @staticmethod
    def consume_deferred_response_language(_text: str) -> tuple[bool, str | None]:
        return True, "es"

    @staticmethod
    def retire_deferred_response_language(_text: str) -> None:
        return None


def _turn(text: str, llm: object) -> dict[str, object]:
    tools = {
        name: _tool(name, required=required)
        for name, required in (
            ("web.search", ("query",)),
            ("email.latest.read", ()),
            ("media.play.youtube", ("query",)),
            ("media.status", ()),
            ("calendar.event.list", ()),
        )
    }
    return _prepare_turn_result(
        {"id": "turn-email-contacts-social", "text": text},
        llm=llm,
        planner_catalog=PlannerCatalog(list(tools.values())),
        turn_evidence=_NoEvidence(),
        encoder=lambda _texts: (),
        tool_by_name=tools,
    )


@pytest.mark.parametrize(
    "text",
    [
        "what is dad's cell number",
        "what's the address for my landlord",
        "cuál es el correo de mi profe",
        "cuántos contactos tengo en mi agenda",
        "what are the newest posts on my facebook account",
        "pon un tuit a movistar quejándote del internet",
        "cuántos mensajes sin leer tengo",
    ],
)
def test_the_turn_is_a_plain_limit_never_a_lookup_or_an_answer_from_memory(text: str) -> None:
    llm = _ShapeSaysNoEffectLlm()
    result = _turn(text, llm)

    assert result["kind"] == "conversation"
    assert result["conversationKind"] == "unsupported"
    assert result["effectOperations"] == []
    assert "web.search" not in result["intentOperations"]
    assert llm.chat_kinds == ["unsupported"]


@pytest.mark.parametrize(
    "text",
    ["controla mi correo", "revisa mi bandeja de entrada por mí", "abre mi cuenta de email y mira los correos nuevos"],
)
def test_the_turn_reads_the_mailbox(text: str) -> None:
    result = _turn(text, _ShapeSaysNoEffectLlm())

    assert result["kind"] == "action"
    assert result["operation"] == "email.latest.read"
