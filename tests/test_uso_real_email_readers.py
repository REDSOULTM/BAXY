"""Uso real 2026-09-23 (MASSIVE email_query / email_sendemail): the person's mail.

- What arrived in the mail — new, any, from someone, since a time, the inbox checked — is the mailbox
  read (``email.latest.read``), never a web search and never «¿quieres que lea el último correo?».
- Writing, answering or organising mail is not that read.
- «email chelsea»: the verb «email» with a person is a mail whose address is what is missing.
- «let me know any new emails»: what BAXY is asked to tell the person is no message to anybody.
- A question about the person's received mail never leaves the PC as a web search.
"""

from __future__ import annotations

import pytest

from baxy_mind import __main__ as mind_main
from baxy_mind.__main__ import _prepare_turn_result
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic.messaging import inbox_read_request
from baxy_mind.semantic.patterns import (
    operation_domain_is_grounded,
    resolve_explicit_clarification_intent,
    resolve_explicit_effects,
)
from test_c03_pointless_questions import _NoEvidence, _tool
from test_c03_unknown_looked_up import _KnowledgeLlm

_MAIL = (
    "email.latest.read",
    "email.latest.reply",
    "email.send",
    "message.send",
    "message.recipient.resolve",
    "calendar.event.list",
    "note.read",
    "web.search",
)

# Phrasings the real run sent to a clarification or a web search; the ones after «unseen» were
# written fresh to check that the reading generalises.
_INBOX_READS = [
    "tengo algún correo nuevo de julio",
    "he recibido algún correo electrónico desde el mediodía",
    "hay algo nuevo en mi buzón",
    "dime si tengo algún correo electrónico nuevo sin leer",
    "por favor lee los nuevos correos",
    "muestra los correos electrónicos más recientes",
    "correos electrónicos en los últimos diez minutos",
    "notificaciónes de correo electrónico",
    "revisa correo sobre lo que sea de silvia",
    "recibí algún correo electrónico nuevo de roberto",
    "yo tengo correos electrónicos de este remitente",
    "check for new email",
    "check any mail from amazon",
    "have i received any emails from jeffrey burnette",
    "hey has john sent me any email lately",
    "tell me if i have any new messages in my inbox",
    "is there anything new in my mailbox",
    "let me know any new emails i've received",
    # unseen
    "me llegó algún mail de mi jefe?",
    "fijate si me escribieron al correo",
    "¿hay correos sin leer en la bandeja de entrada?",
    "did I get any new emails this morning",
    "any unread mail?",
    "check my inbox please",
    "i want to see my new emails",
]


@pytest.mark.parametrize("text", _INBOX_READS)
def test_what_arrived_in_the_mail_is_the_mailbox_read(text: str) -> None:
    assert inbox_read_request(text)
    intent = resolve_explicit_effects(text, _MAIL)
    assert intent is not None and intent.operations == ("email.latest.read",)
    # Nothing is asked first: the read is the answer.
    assert resolve_explicit_clarification_intent(text, _MAIL) is None
    # The model choosing the read is not vetoed by the domain gate either.
    assert operation_domain_is_grounded(text, "email.latest.read", ())


@pytest.mark.parametrize(
    "text",
    [
        # writing, answering, forwarding: not a read of what arrived
        "envíale un correo a ana diciendo que llego tarde",
        "responde el último correo diciendo que llego mañana",
        "reply to the latest email saying thanks",
        "reenvía el último correo a pedro",
        "crea un correo para mi colega con mis documentos recientes",
        "he enviado un correo a nicole sobre el tema del control de armas",
        "email mom and ask how the weather is there",
        # a phrase, an address, an account, voicemail
        "Lee la frase correo mas reciente",
        "cuál es la dirección de correo de marta",
        "what is my email address",
        "crea una cuenta de correo nueva",
        "tengo mensajes nuevos en el correo de voz?",
        # public knowledge about mail
        "quién inventó el correo electrónico",
        "horario de correos hoy",
    ],
)
def test_mail_that_is_not_the_inbox_read_is_not_read(text: str) -> None:
    assert not inbox_read_request(text)
    assert not operation_domain_is_grounded(text, "email.latest.read", ())


@pytest.mark.parametrize(
    "text",
    [
        "borra el último correo",
        "marca como leídos los correos nuevos",
        "abre mi correo nuevo en outlook",
        "lee mi nota sobre el correo más reciente",
        "consulta el calendario de reuniones en el correo de hoy",
        "no revises mi correo nuevo",
        # what the person tells, and another device's mail
        "I read the latest email yesterday",
        "I got a new email from ana this morning",
        "Read the latest inbox message from my phone",
        "tengo correos nuevos en el celular?",
    ],
)
def test_handling_mail_or_another_object_is_not_the_reader_s_read(text: str) -> None:
    assert not inbox_read_request(text)


@pytest.mark.parametrize(
    "text",
    ["email chelsea", "email mom and ask how the weather is there", "please email the landlord about the rent"],
)
def test_email_said_as_the_verb_asks_the_address(text: str) -> None:
    clarification = resolve_explicit_clarification_intent(text, _MAIL)
    assert clarification is not None
    assert clarification.operations == ("email.send",)
    assert clarification.missing_fields == ("to",)


@pytest.mark.parametrize(
    "text", ["email notifications", "email from amazon", "email me the report", "email address of the embassy"],
)
def test_email_as_a_noun_or_to_me_asks_no_address(text: str) -> None:
    clarification = resolve_explicit_clarification_intent(text, _MAIL)
    assert clarification is None or clarification.operations != ("email.send",)


def test_let_me_know_is_no_message_but_let_someone_know_still_is() -> None:
    assert resolve_explicit_clarification_intent("let me know any new emails i've received", _MAIL) is None
    ask = resolve_explicit_clarification_intent("let lucas know the meeting moved", ("message.send", "web.search"))
    assert ask is not None and ask.operations == ("message.send",)


class _GuardSaysPublic:
    @staticmethod
    def public_lookup_requested(_text: str) -> bool:
        return True


_PRIVATE_MAIL_QUESTIONS = [
    "he recibido algún correo electrónico desde el mediodía",
    "correos electrónicos en los últimos diez minutos",
    "check any mail from amazon",
    "have i received any emails from jeffrey burnette",
    "qué pasa con el nuevo correo",
]


@pytest.mark.parametrize("text", _PRIVATE_MAIL_QUESTIONS)
def test_received_mail_never_leaves_as_a_web_search(text: str) -> None:
    catalog = PlannerCatalog([_tool("web.search", required=("query",))])
    assert not mind_main._public_lookup_applies(text, text, _GuardSaysPublic(), ("web.search",), catalog)
    # The same guard reading still searches public information about mail.
    assert mind_main._public_lookup_applies(
        "quién inventó el correo electrónico", "quién inventó el correo electrónico",
        _GuardSaysPublic(), ("web.search",), catalog,
    )


def _turn(text: str) -> dict[str, object]:
    tools = {
        name: _tool(name, required=required)
        for name, required in (
            ("web.search", ("query",)),
            ("email.latest.read", ()),
        )
    }
    return _prepare_turn_result(
        {"id": "turn-mail", "text": text},
        llm=_KnowledgeLlm("No tengo acceso a tu correo."),
        planner_catalog=PlannerCatalog(list(tools.values())),
        turn_evidence=_NoEvidence(),
        encoder=lambda _texts: (),
        tool_by_name=tools,
    )


@pytest.mark.parametrize(
    "text",
    [
        "is there anything new in my mailbox",
        "please check for new emails",
        "have i received any emails from jeffrey burnette",
        "yo tengo algún correo nuevo en la última hora",
    ],
)
def test_the_turn_reads_the_mailbox_where_the_model_talked(text: str) -> None:
    result = _turn(text)

    assert result["kind"] == "action"
    assert result["operation"] == "email.latest.read"
