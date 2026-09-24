"""Messaging: messages, WhatsApp, Discord, email and notifications. Readers moved from effect_intent (Fase 3.5).
"""

from __future__ import annotations

import re
from .grammar import _fold, _has, _strip_request_envelope, _negative_action_forms
from .notes import _AGENDA_LISTING


_MSG_VERB = r"(?:m[aá]nd[aá](?:le|me|les)?|env[ií]a(?:le|me|les)?|envi[aá](?:le|me|les)?|escrib[ií](?:le|me)?|escr[ií]be(?:le|me)?|send|write|text|message)"


_MSG_OBJECT = r"(?:(?:un|una|el|a|an|the)\s+)?(?:mensaje|message|texto|text)"


_MSG_OBJECT_CHANNEL = r"(?:(?:un|una|el|a|an|the)\s+)?(?P<och>whatsapp|wsp|discord|correo(?:\s+electr[oó]nico)?|(?:e-?)?mail)(?:\s+(?:mensaje|message))?"


_MSG_CHANNEL = r"(?P<ch>whatsapp|wsp|discord|correo(?:\s+electr[oó]nico)?|(?:e-?)?mail)"


_MSG_CHANNEL_WORDS = r"(?:whatsapp|wsp|discord|correo|(?:e-?)?mail)"


def _message_channel_name(word: str) -> str:
    """The catalog channel for a client word: WhatsApp, Discord or email (owner
    decision 2026-09-18 §3: «correo», «mail», «email»)."""

    folded = _fold(word)
    if folded in {"whatsapp", "wsp"}:
        return "whatsapp"
    if folded.startswith(("correo", "mail", "email", "e-mail")):
        return "email"
    return folded


_MSG_TO = r"(?:a|al\s+grupo|al|para|to|en\s+el\s+grupo|en)"


_MSG_ON = r"(?:en|por|via|v[ií]a|on|through)"


_MSG_SEP = r"(?:que\s+diga|que\s+dice|diciendo(?:le)?|dici[eé]ndole|saying|that\s+says|que|that|:)"


_MSG_REC = r"(?P<rec>[^\s,:;][^,:;]{0,60}?)"


_MSG_BODY = r"(?P<body>.+?)"


_MSG_END = r"\s*[.!?]*$"


_MSG_DRAFT_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        # «manda un mensaje a Musica en whatsapp que diga hola», «Write to Musica on WhatsApp saying test»
        rf"^\s*{_MSG_VERB}\s+(?:{_MSG_OBJECT}\s+)?{_MSG_TO}\s+{_MSG_REC}\s+{_MSG_ON}\s+{_MSG_CHANNEL}\s+{_MSG_SEP}\s*{_MSG_BODY}{_MSG_END}",
        # «mándale un mensaje por discord a ShooterCock que diga hola»
        rf"^\s*{_MSG_VERB}\s+(?:{_MSG_OBJECT}\s+)?{_MSG_ON}\s+{_MSG_CHANNEL}\s+{_MSG_TO}\s+{_MSG_REC}\s+{_MSG_SEP}\s*{_MSG_BODY}{_MSG_END}",
        # «manda un mensaje a whatsapp a amor diciendo te amo»
        rf"^\s*{_MSG_VERB}\s+(?:{_MSG_OBJECT}\s+)?(?:a|to)\s+{_MSG_CHANNEL}\s+{_MSG_TO}\s+{_MSG_REC}\s+{_MSG_SEP}\s*{_MSG_BODY}{_MSG_END}",
        # «mandale un whatsapp a mamá diciendo que ya voy», «Send a WhatsApp message to Musica saying test»
        rf"^\s*{_MSG_VERB}\s+{_MSG_OBJECT_CHANNEL}\s+{_MSG_TO}\s+{_MSG_REC}\s+{_MSG_SEP}\s*{_MSG_BODY}{_MSG_END}",
        # «Escribe hola a musica en whatsapp», «mandale hola a Lucas por whatsapp», «Escribe hola en musica en whatsapp»
        rf"^\s*{_MSG_VERB}\s+{_MSG_BODY}\s+{_MSG_TO}\s+{_MSG_REC}\s+{_MSG_ON}\s+{_MSG_CHANNEL}{_MSG_END}",
        # «escribele a shootercock hola en discord»
        rf"^\s*{_MSG_VERB}\s+(?:a|to)\s+(?P<rec>[^\s,:;]+)\s+{_MSG_BODY}\s+{_MSG_ON}\s+{_MSG_CHANNEL}{_MSG_END}",
        # «Escribe hola en whatsapp en el grupo musica»
        rf"^\s*{_MSG_VERB}\s+{_MSG_BODY}\s+{_MSG_ON}\s+{_MSG_CHANNEL}\s+{_MSG_TO}\s+{_MSG_REC}{_MSG_END}",
    )
)


# REOPEN1993 grupo E (D24; H0019 «mandale a Música que ya voy», H0408, H0198 «mandale al
# grupo Musica: …», H0231, H0536, H0024 «escribile a Lucas que llego tarde»): a message for
# a named person or group with NO client named. The recipient is looked up in the clients
# (the remembered one, WhatsApp, Discord); unique → sent (confirmed in normal mode).
_MSG_ANY_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        # «manda un mensaje a Música que diga hola», «enviale un mensaje al grupo Musica que diga: prueba 2»
        rf"^\s*{_MSG_VERB}\s+{_MSG_OBJECT}\s+{_MSG_TO}\s+{_MSG_REC}\s+{_MSG_SEP}\s*{_MSG_BODY}{_MSG_END}",
        # «mandale a Música que ya voy», «mandale al grupo Musica: prueba 1», «escribile a Lucas que llego tarde», «text Lucas that I'm late»
        rf"^\s*{_MSG_VERB}\s+{_MSG_TO}\s+{_MSG_REC}\s*{_MSG_SEP}\s*{_MSG_BODY}{_MSG_END}",
        rf"^\s*(?:text|message)\s+{_MSG_REC}\s+{_MSG_SEP}\s*{_MSG_BODY}{_MSG_END}",
        # «send Lucas a message saying I'm late»
        rf"^\s*send\s+{_MSG_REC}\s+{_MSG_OBJECT}\s+{_MSG_SEP}\s*{_MSG_BODY}{_MSG_END}",
        # «dile a Lucas que llego tarde», «avisale a Música que ya voy», «hazle saber a Lucas que…», «contale a Ana que…»
        rf"^\s*(?:dile|decile|avisale|avisa|contale|cuentale|hazle\s+saber|hacele\s+saber|hazle\s+llegar)\s+(?:a|al\s+grupo|al)\s+{_MSG_REC}\s+(?:que|el\s+mensaje)\s*{_MSG_BODY}{_MSG_END}",
        # «let Lucas know that I'm late», «tell Lucas that I'm late»
        rf"^\s*let\s+{_MSG_REC}\s+know\s+(?:that\s+)?{_MSG_BODY}{_MSG_END}",
        rf"^\s*tell\s+{_MSG_REC}\s+that\s+{_MSG_BODY}{_MSG_END}",
    )
)


_MSG_PRONOUN_RECIPIENTS = frozenset({
    "me", "us", "him", "her", "them", "you", "yo", "mi", "nos", "le", "les", "el", "ella", "ellos", "ellas", "vos", "usted",
})


def message_request_named_client(text: str) -> tuple[str, str, str] | None:
    """(recipient, body, client) of a message for a named person or group in a
    NAMED chat client (WhatsApp or Discord): «mandale un mensaje a vicho por wsp
    diciéndole hola», «escribile a Lucas en whatsapp que llego tarde». None for
    mail, for a client without a person, or for a body without recipient."""

    draft = message_draft_request(text)
    if draft is None or draft[0] not in {"whatsapp", "discord"}:
        return None
    recipient = re.sub(r"^(?:el\s+grupo|la\s+|el\s+|the\s+group|the\s+)\s*", "", (draft[1] or "").strip(), flags=re.IGNORECASE).strip(" .")
    body = (draft[2] or "").strip()
    if not recipient or not body or _fold(recipient) in _MSG_PRONOUN_RECIPIENTS:
        return None
    if len(recipient.encode("utf-8")) > 512 or len(body.encode("utf-8")) > 16_384 or len(recipient.split()) > 6:
        return None
    return recipient, body, draft[0]


def message_request_any_channel(text: str) -> tuple[str, str, str | None] | None:
    """(recipient, body, client or None) of a message request whose client is
    not named before the text; None when a client leads (message_draft_request
    owns it), or without recipient or body. A client named at the END of the
    text («… por WhatsApp») is the client; «que dija» (H0408) is «que diga»."""

    raw = _strip_request_envelope(text).strip()
    if not raw or len(raw.encode("utf-8")) > 2048 or "aclaracion confiable del usuario:" in _fold(raw):
        return None
    if message_draft_request(text) is not None:
        return None
    if _negative_action_forms(_fold(raw)):
        return None
    raw = re.sub(r"\bque\s+dija\b", "que diga", raw, flags=re.IGNORECASE)
    for pattern in _MSG_ANY_PATTERNS:
        match = pattern.match(raw)
        if match is None:
            continue
        groups = match.groupdict()
        head = raw[: match.start("body")]
        if re.search(r"\b" + _MSG_CHANNEL_WORDS + r"\b", _fold(head)):
            # A client named before the text belongs to message_draft_request; a
            # client named INSIDE the text («prueba 1 de WhatsApp») is just words.
            continue
        recipient = re.sub(r"^(?:el\s+grupo|la\s+|el\s+|the\s+group|the\s+)\s*", "", (groups.get("rec") or "").strip(), flags=re.IGNORECASE).strip(" .")
        body = (groups.get("body") or "").strip().lstrip(":").strip()
        body = re.sub(
            r"^(?:que\s+diga\s+|que\s+dice\s+|diciendo(?:le)?\s+(?:que\s+)?|dici[eé]ndole\s+(?:que\s+)?|saying\s+|that\s+says\s+|que\s+|that\s+)",
            "", body, flags=re.IGNORECASE,
        ).strip()
        body = body.rstrip(" .!?") if len(body) > 1 else body
        if not recipient or not body or _fold(recipient) in {"mensaje", "message", "un mensaje", "a message"}:
            continue
        if _fold(recipient) in _MSG_PRONOUN_RECIPIENTS:
            continue
        if len(recipient.encode("utf-8")) > 512 or len(body.encode("utf-8")) > 16_384 or len(recipient.split()) > 6:
            continue
        channel: str | None = None
        trailing = re.search(r"\s+(?:por|en|via|v[ií]a|on|through)\s+(?P<ch>whatsapp|wsp|discord)\s*$", body, re.IGNORECASE)
        if trailing is not None:
            channel = _message_channel_name(trailing.group("ch"))
            body = body[: trailing.start()].rstrip(" ,")
            if not body:
                continue
        return recipient, body, channel
    return None


_MAIL_ADDRESS = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,63}$")


_MAIL_SUBJECT = re.compile(
    r"^(?P<rec>.+?)\s+(?:con\s+(?:el\s+)?asunto|asunto|with\s+(?:the\s+)?subject|subject)\s*:?\s*(?P<subject>.+)$",
    re.IGNORECASE,
)


def email_send_request(text: str) -> dict[str, str | None] | None:
    """Fase 7 (D4): a mail to a free address («mandale un correo a ana@gmail.com
    diciendo que llego tarde», «send an email to x@y.com saying hi», «… con
    asunto reunión que diga …»). Returns {to, text, subject}; None when the
    channel is not mail, or the recipient is not an address (the question asks
    it), or there is no text."""

    draft = message_draft_request(text)
    if draft is None or draft[0] != "email":
        return None
    recipient, body = draft[1].strip(), draft[2]
    subject: str | None = None
    with_subject = _MAIL_SUBJECT.match(recipient)
    if with_subject is not None:
        recipient, subject = with_subject.group("rec").strip(), with_subject.group("subject").strip(" .:")
    if _MAIL_ADDRESS.match(recipient) is None:
        return None
    return {"to": recipient, "text": body, "subject": subject or None}


# Uso real 2026-09-23 «email chelsea», «email mom and ask how …»: «email» said as
# the verb, with the person right after it, is a mail to that person.
_EMAIL_VERB_TO_SOMEONE = (
    r"^(?:please\s+)?e-?mail\s+(?:to\s+)?"
    r"(?!(?:notifications?|alerts?|messages?|inbox|from|about|in|on|of|for|me|us|"
    r"address(?:es)?|accounts?|settings?|is|was|are|has|had|and|or|the\s+latest|"
    r"the\s+last|the\s+new)\b)[a-z]"
)


def email_request_without_address(text: str) -> bool:
    """«enviá un correo a juan», «escribile un mail a Lucas que diga hola»: mail
    asked for a name that is not an address → the address is what is missing."""

    if email_send_request(text) is not None:
        return False
    draft = message_draft_request(text)
    if draft is not None:
        return draft[0] == "email" and _MAIL_ADDRESS.match(draft[1].strip()) is None
    folded = _strip_request_envelope(_fold(text)).strip(" .!?")
    return (
        (
            _has(folded, r"^(?:" + _MSG_VERB + r")\s+(?:un\s+|una\s+|el\s+|a\s+|an\s+|the\s+)?(?:correo(?:\s+electronico)?|(?:e-?)?mail)\s+(?:a|al|para|to)\s+\S")
            or _has(folded, _EMAIL_VERB_TO_SOMEONE)
        )
        and "@" not in folded
    )


def message_draft_request(text: str) -> tuple[str, str, str] | None:
    """MSG1837 (owner decision 2026-09-17): a message for a named chat in a named
    desktop client (WhatsApp or Discord) is LEFT WRITTEN in the client's composer
    and never sent. Returns (channel, recipient, body) in the person's own words;
    None without a channel (the existing clarification asks it), a recipient or
    a body."""

    raw = _strip_request_envelope(text).strip()
    if not raw or len(raw.encode("utf-8")) > 2048:
        return None
    if "aclaracion confiable del usuario:" in _fold(raw):
        # MSGCLAR1851: a resumed objective «<request> <trusted prefix> <answer>»
        # is read as request plus answer by the completion, never as one draft
        # whose text would swallow the prefix.
        return None
    for pattern in _MSG_DRAFT_PATTERNS:
        match = pattern.match(raw)
        if match is None:
            continue
        groups = match.groupdict()
        channel = _message_channel_name(groups.get("ch") or groups.get("och") or "")
        recipient = re.sub(r"^(?:el\s+grupo|la\s+|el\s+|the\s+group|the\s+)\s*", "", (groups.get("rec") or "").strip(), flags=re.IGNORECASE).strip(" .")
        # MSGCLAR «que diga: prueba 2, todo OK»: the dictation colon after the
        # separator is punctuation, never part of the text.
        body = (groups.get("body") or "").strip().lstrip(":").strip()
        body = re.sub(
            r"^(?:que\s+diga\s+|que\s+dice\s+|diciendo(?:le)?\s+(?:que\s+)?|dici[eé]ndole\s+(?:que\s+)?|saying\s+|that\s+says\s+|que\s+|that\s+)",
            "", body, flags=re.IGNORECASE,
        ).strip()
        body = body.rstrip(" .!?") if len(body) > 1 else body
        if channel not in {"whatsapp", "discord", "email"} or not recipient or not body:
            continue
        if re.search(r"\b" + _MSG_CHANNEL_WORDS + r"\b", _fold(recipient)) or _fold(recipient) in {"mensaje", "message"}:
            continue
        if len(recipient.encode("utf-8")) > 512 or len(body.encode("utf-8")) > 16_384:
            continue
        return channel, recipient, body
    return None


_MAIL_NOUN = (
    r"\b(?:correos?(?:\s+electronicos?)?|e-?mails?|mails?|buzon|inbox|mailbox|"
    r"bandeja\s+de\s+entrada)\b"
)


# What makes a mail mention the person's received mail: how new it is, whether
# something arrived or is there, or an order to look at it. Uso real 2026-09-23
# (MASSIVE email_query): «tengo algún correo nuevo», «check for new email»,
# «hay algo nuevo en mi buzón», «have i received any emails from X».
_INBOX_RECENCY = (
    r"\b(?:recientes?|recent(?:ly)?|latest|ultim[oa]s?|last|newest|lately|"
    r"nuev[oa]s?|new|sin\s+leer|unread|no\s+leid[oa]s?|notificacion(?:es)?|"
    r"notifications?|newly\s+arrived|just\s+arrived|just\s+received|"
    r"acaba\s+de\s+llegar|recien\s+llego|nullier\s+i[dt]|era\s+(?:y|ive)\s+blast)\b"
)


_INBOX_ARRIVAL = (
    r"\b(?:tengo|tenemos|hay|llego|llegaron|llegado|recibi|recibido|recibimos|"
    r"me\s+(?:escribio|escribieron|mando|mandaron|envio|enviaron)|"
    r"received|gotten|got|have\s+i|do\s+i\s+have|is\s+there|are\s+there|"
    r"sent\s+me|wrote\s+me|emailed\s+me|came\s+in|arrived)\b"
)


_INBOX_LOOK = (
    r"\b(?:revisa|revisame|revisar|revises|chequea|checa|checkea|check|consulta|"
    r"consultar|mira|mirame|fijate|lee|leeme|leer|read|muestra|muestrame|mostrame|"
    r"show|dime|decime|tell\s+me|let\s+me\s+know|hazme\s+saber|avisame|look)\b"
)


# A mail mentioned for something other than reading what arrived: a phrase
# quoted about mail, voicemail, an address or an account.
_NOT_THE_INBOX = (
    r"\b(?:frase|phrase|palabras?|words?|texto|text)\b.{0,80}\b(?:correo|email|mail)\b|"
    r"\b(?:correo\s+de\s+voz|voice\s*mail)\b|"
    r"\bdirecci(?:on|ones)\s+de\s+(?:correo|e-?mail)\b|\b(?:e-?mail|mail)\s+address(?:es)?\b|"
    r"\bcuenta\s+de\s+(?:correo|e-?mail)\b|\b(?:e-?mail|mail)\s+account\b"
)


# Writing mail instead of reading what arrived: sending, answering, forwarding,
# composing; «me envió», «sent me» (somebody else's sending) is what arrived.
_MAIL_WRITING = (
    r"\b(?:envi\w*|mand(?:a|ale|ar|e|es)|escrib\w*|redact\w*|respond\w*|contest\w*|"
    r"reenvi\w*|crea|crear|creame|"
    r"send|sent|write|compose|draft|reply|respond|answer|forward|create|emailed)\b"
)


_OTHERS_SENDING = (
    r"\bme\s+(?:mando|mandaron|envio|enviaron|escribio|escribieron)\b|"
    r"\b(?:sent|emailed|wrote|written)\s+me\b"
)


def _latest_email_domain(text: str) -> bool:
    """The person's received mail is what the text is about (folded text)."""

    return (
        _has(text, _MAIL_NOUN)
        and (
            _has(text, _INBOX_RECENCY)
            or _has(text, _INBOX_ARRIVAL)
            or _has(text, _INBOX_LOOK)
        )
        and not _has(text, _NOT_THE_INBOX)
        and not _has(re.sub(_OTHERS_SENDING, " ", text), _MAIL_WRITING)
        and not _has(_strip_request_envelope(text), _EMAIL_VERB_TO_SOMEONE)
    )


# Handling mail rather than reading it: deleting, filing, marking, opening the
# client or setting it up.
_MAIL_HANDLING = (
    r"\b(?:borr\w*|elimin\w*|archiv\w*|marc\w*|muev\w*|mover|bloque\w*|"
    r"configur\w*|abre|abrir|abreme|delete|remove|archive|mark|move|block|set\s+up|open)\b"
)


# Another of the person's things named with the mail: that one is the object
# («lee mi nota sobre el correo más reciente»); or the mail of another device
# («the latest inbox message from my phone»), which this PC does not read.
_OTHER_OWN_OBJECT = (
    r"\b(?:notas?|notes?|calendari[oa]s?|calendars?|agenda|reuniones|meetings?|"
    r"recordatorios?|reminders?|tareas?|tasks?|listas?|lists?|archivos?|files?|"
    r"documentos?|documents?|carpetas?|folders?|portapapeles|clipboard|pantalla|screen|"
    r"whatsapp|discord|telefono|celular|movil|phone|smartphone|tablet|reloj|watch)\b"
)


# «I read the latest email yesterday»: an English sentence that opens on its
# subject tells what the person did; asking inverts («have i», «did i»).
_FIRST_PERSON_ACCOUNT = r"^i\s+(?!(?:want|wanna|need|would|'d)\b)"


def inbox_read_request(text: str) -> bool:
    """Uso real 2026-09-23: the person asks what arrived in their mail — to look
    at it («revisa mis correos nuevos», «check any mail from amazon»), whether
    there is any («tengo algún correo nuevo de julio», «have i received any
    emails from X») or the newest by name («notificaciones de correo»). The one
    mailbox read the catalog has is the latest message, and it answers every one
    of them with what it reads (sender, subject, time); a filter the read cannot
    apply is the composer's to say, never a web search of private mail."""

    folded = _strip_request_envelope(_fold(text)).strip(" .!?¿¡")
    return (
        bool(folded)
        and len(folded) <= 400
        and _latest_email_domain(folded)
        and not _negative_action_forms(folded)
        and not _has(folded, _FIRST_PERSON_ACCOUNT)
        and not _has(folded, _MAIL_HANDLING)
        and not _has(folded, _OTHER_OWN_OBJECT)
    )


_NOTIFICATION_LISTING = (
    r"^[¿?¡!\s]*(?:(?:por favor|please)\s*[,;:]?\s*)?"
    r"(?:(?:lista|listame|list|enumera|enumerame|mostrame|muestrame|muestra|show me|show|decime|dime|"
    r"contame|cuentame|tell me)\s+(?:me\s+)?(?:cuales\s+son\s+|which\s+are\s+|what\s+are\s+)?"
    r"(?:los|las|mis|my|the|todos los|todas las|all my|all the|all)?\s*|"
    r"(?:cuales|which|what)\s+(?:son\s+)?(?:los|las|mis|my|the)?\s*|"
    r"(?:que|what)\s+)"
    r"(?:(?:programad[oa]s?|activ[oa]s?|scheduled|active)\s+)?"
    r"(?:timers?|temporizadores?|alarmas?|alarms?|cuentas?\s+(?:atras|regresivas?)|countdowns?)"
    r"(?:\s+(?:y|and)\s+(?:timers?|temporizadores?|alarmas?|alarms?|recordatorios?|reminders?))?"
    r"(?:\s+(?:programad[oa]s?|activ[oa]s?|pendientes|scheduled|active|set))?"
    r"(?:\s+(?:que\s+)?(?:tengo|hay|do i have|are (?:there|set)|i have))?"
    r"(?:\s+(?:programad[oa]s?|activ[oa]s?|pendientes|scheduled|active|set))?[\s?!.]*$"
)


def _notification_listing_request(text: str) -> bool:
    """AGENDA1435 «listá los timers», «qué alarmas tengo»: the scheduled
    alarms and reminders, never the due ones (those keep notification.list.due)."""

    folded = _fold(text)
    if _has(folded, r"\b(?:vencid[oa]s?|due|overdue|expired|pendientes\s+de\s+descartar)\b"):
        return False
    if re.match(_AGENDA_LISTING, folded) is not None:
        # AGENDA1669 H0660 «qué tengo agendado para hoy»: what BAXY has on
        # the agenda is what it scheduled (alarms, reminders); there is no
        # calendar, and the listing says so by what it contains.
        return True
    return re.match(_NOTIFICATION_LISTING, folded) is not None
