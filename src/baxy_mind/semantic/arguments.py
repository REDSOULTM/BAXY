"""The argument binder: each operation's literal arguments read from the person's words.

It moved from ``__main__`` with the unification of the reading (owner, 2026-09-24: every reading of the request
lives in ``semantic/``). A value is returned only when the words say it; otherwise the binder abstains and the
turn asks the model or the person. ``__main__._ground_explicit_arguments`` checks what it returns against the
catalog schema; nothing here grants an operation.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, time as datetime_time, timedelta, timezone
from typing import Any
from urllib.parse import urlencode, urlsplit

from .. import effect_intent
from . import lexicon as semantic_lexicon
from .catalog import GameCatalogIndex, resolve_game_catalog_app_id
from .notes import agenda_event_request, said_repetition, stated_event_reminder
from .patterns import resolve_application_catalog_app_id, resolve_application_installed_name
from .temporal import SpokenClock, agenda_window, clock_elsewhere, spoken_date, spoken_window
from .web import news_lookup_query, public_query_body
from .windows import start_menu_request


def _explicit_system_status_scope(evidence: str) -> dict[str, object] | None:
    """Name the `system.status` scope only when the text says it unambiguously.

    The scope is a closed enum of the catalog descriptor, and the effect
    recognizer already decides which measurable domains the request names. When
    it names exactly one —or a pair the enum measures in a single reading— that
    value is a literal supported by the text, not an inference, so it can skip
    the model exactly like every other explicit argument.

    Every other case abstains and keeps the existing grounding: two scopes the
    enum cannot express, a GPU request that does not say whether it asks for
    identity or usage, and anything the domain veto already rejected. Core
    still validates the schema; this only avoids asking the model for a value
    the text already contains.
    """

    folded = effect_intent._fold(evidence)
    if not effect_intent._system_status_domain(folded):
        return None
    named = effect_intent._machine_status_scopes(folded)
    if not named:
        # «cómo anda la pc», «estado del sistema»: el equipo sin un alcance
        # concreto es exactamente el resumen del enum.
        return {"scope": "summary"}
    if named == {"cpu", "memory"}:
        return {"scope": "cpu_memory"}
    if named == {"os", "memory"}:
        return {"scope": "os_memory"}
    if len(named) != 1:
        return None
    only = next(iter(named))
    if only == "gpu":
        usage = effect_intent._has(
            folded,
            r"\b(?:uso|usa|usan|usando|usage|ocupad[oa]|llen[oa]|busy|"
            r"in\s+use|utili[sz]ation|load|tan\s+\w+)\b",
        )
        identity = effect_intent._has(
            folded,
            r"\b(?:que\s+gpu|cual|which|what\s+gpu|modelo|model|tarjeta|"
            r"placa|tengo|tiene|instalad[oa]|have)\b",
        )
        # «cuánto uso tiene la GPU» names usage; its «tiene» is the verb of
        # the usage question, not an identity cue. Abstaining here sent the
        # model to the summary scope, which carries no GPU (SYSTEM1169/005).
        identity_named = effect_intent._has(
            folded,
            r"\b(?:que\s+gpu|cual|which|what\s+gpu|modelo|model|tarjeta|"
            r"placa|instalad[oa])\b",
        )
        if usage and not identity_named:
            return {"scope": "gpu_usage"}
        if identity and not usage:
            return {"scope": "gpu_identity"}
        return None
    return {"scope": only} if only in _SYSTEM_STATUS_SCOPES else None


# Enum cerrado del descriptor `system.status` del catálogo.
_SYSTEM_STATUS_SCOPES = frozenset(
    {
        "battery",
        "cpu",
        "cpu_memory",
        "disk",
        "gpu_identity",
        "gpu_usage",
        "memory",
        "os",
        "os_memory",
        "summary",
    }
)


def _explicit_message_recipient_arguments(
    evidence: str,
) -> dict[str, object] | None:
    """Extract one supported channel and one literal recipient or abstain."""

    folded = effect_intent._fold(evidence)
    channels = {
        "whatsapp" if match in {"whatsapp", "wsp"} else "discord"
        for match in re.findall(r"\b(?:whatsapp|wsp|discord)\b", folded)
    }
    if len(channels) != 1:
        return None
    patterns = (
        (
            r"\b(?:por|en|via)\s+(?:whatsapp|wsp|discord)\s+"
            r"(?:hazle\s+llegar|cu[eé]ntale|dile|decile)\s+a\s+"
            r"(?P<recipient>[^,;.!?]{1,80}?)\s+"
            r"(?:que|(?:el|the)\s+(?:mensaje|message)|the\s+report)\b"
        ),
        (
            r"\b(?:through|on|via)\s+(?:whatsapp|discord)\s+"
            r"let\s+(?P<recipient>[^,;.!?]{1,80}?)\s+know\b"
        ),
        (
            r"\b(?:through|on|via)\s+(?:whatsapp|discord)\s+"
            r"get\s+(?:the\s+)?(?:note|message|update)\s+.+?\s+to\s+"
            r"(?P<recipient>[^,;.!?]{1,80})$"
        ),
        (
            r"\b(?:por|en|via)\s+(?:whatsapp|wsp|discord)\s+"
            r"(?:dile|decile)\s+a\s+"
            r"(?P<recipient>[^,;.!?\s]{1,80})\s+\S"
        ),
        (
            r"\b(?:escr[ií]be(?:le)?|write)\s+(?:en|on|via)\s+"
            r"(?:whatsapp|wsp|discord)\s+(?:a\s+|to\s+)?"
            r"(?P<recipient>[^,;.!?]{1,80}?)\s+(?:que|that)\b"
        ),
        (
            r"\b(?:escr[ií]be(?:le)?|write\s+to)\s+"
            r"(?:a\s+|to\s+)?(?P<recipient>[^,;.!?]{1,80}?)\s+"
            r"(?:en|on|via)\s+(?:whatsapp|wsp|discord)\s+(?:que|that)\b"
        ),
        (
            r"\bpasa\s+(?:por|via)\s+(?:whatsapp|wsp|discord)\s+a\s+"
            r"(?P<recipient>[^,;.!?]{1,80}?)\s+"
            r"(?:(?:el\s+)?(?:texto|mensaje)|que)\b"
        ),
        (
            r"\bpass\s+(?:to\s+)?(?P<recipient>[^,;.!?]{1,80}?)\s+"
            r"(?:the\s+)?message\b"
        ),
        (
            r"\b(?:dile|decile)\s+a\s+(?P<recipient>[^,;.!?]{1,80}?)\s+"
            r"(?:(?:en|por)\s+(?:whatsapp|wsp|discord)\s+)?que\b"
        ),
        (
            r"\btell\s+(?P<recipient>[^,;.!?]{1,80}?)\s+"
            r"(?:on\s+(?:whatsapp|discord)\s+)?that\b"
        ),
        (
            r"\bmessage\s+(?P<recipient>[^,;.!?]{1,80}?)\s+"
            r"(?:on\s+)?(?:whatsapp|discord)\s+(?:that|saying)\b"
        ),
        (
            r"\b(?:env[ií]a|manda|send)\s+(?:en|por|on|via)\s+"
            r"(?:whatsapp|wsp|discord)\s+(?:a\s+|to\s+)?"
            r"(?P<recipient>[^,;.!?]{1,80}?)\s+(?:que|that)\b"
        ),
        (
            r"\b(?:env[ií]a|manda)\s+(?:por\s+)?"
            r"(?:whatsapp|wsp|discord)\s+a\s+"
            r"(?P<recipient>[^,;.!?]{1,80}?)\s+"
            r"(?:el\s+)?mensaje\b"
        ),
        (
            r"\b(?:env[ií]a|manda|send)\s+(?:a\s+)?"
            r"(?P<recipient>[^,;.!?]{1,80}?)\s+"
            r"(?:(?:por|en|on)\s+)?(?:the\s+|el\s+)?"
            r"(?:whatsapp|wsp|discord)\s+"
            r"(?:(?:el|the)\s+)?(?:mensaje|message)\b"
        ),
    )
    recipients: list[str] = []
    for pattern in patterns:
        for match in re.finditer(pattern, evidence, re.IGNORECASE):
            recipient = match.group("recipient").strip(" \t\r\n,;:.!?\"'“”‘’«»")
            recipient_key = effect_intent._fold(recipient).strip()
            if (
                not recipient_key
                or re.search(r"\b(?:y|and)\b|[&,/]", recipient_key)
                or recipient_key
                in {
                    "ellos",
                    "ellas",
                    "les",
                    "them",
                    "recipient",
                    "destinatario",
                    "contact",
                    "contacto",
                }
            ):
                continue
            recipients.append(recipient)
    recipient_keys = {effect_intent._fold(value).strip() for value in recipients}
    if len(recipient_keys) != 1:
        return None
    return {
        "channel": next(iter(channels)),
        "recipient": recipients[0],
    }


def _explicit_local_reminder_title(evidence: str) -> str | None:
    """Preserve the original spelling of one explicitly named reminder."""

    nominal = re.match(
        r"^[^\w]*(?:reminders\s+(?:for|about)|"
        r"recordatorios\s+(?:de|para|sobre))\s+"
        r"(?P<title>.+?)[\s.!?]*$",
        evidence,
        re.IGNORECASE,
    )
    if (
        nominal is not None
        and effect_intent._nominal_reminder_lookup_title(evidence) is not None
    ):
        title = nominal.group("title").strip(" \t\r\n.,;:!?\"'“”‘’«»")
        return title or None
    repeated_lookup = re.match(
        r"^[^\w]*(?:can\s+i\s+|puedo\s+)?"
        r"(?:see|show|view|find|ver|ve|muestra|muestrame|ensena)\s+"
        r"(?:(?:me|i)\s+)?(?:(?:the|el|la)\s+)?"
        r"(?:reminder|recordatorio)\s+"
        r"(?:for|about|de|para|sobre)\s+"
        r"(?P<title>.+?)\s+(?:again|otra vez|de nuevo|nuevamente)[\s.!?]*$",
        evidence,
        re.IGNORECASE,
    )
    if repeated_lookup is not None:
        title = repeated_lookup.group("title").strip()
        return title or None
    if effect_intent._exact_local_reminder_title(evidence) is None:
        return None
    patterns = (
        (
            r"^[¿?¡!\s]*(?:(?:please|por favor)\s+)?"
            r"(?:delete|remove|cancel|erase|elimina|eliminar|borra|borrar|"
            r"quita|quitar|cancela|cancelar)\s+"
            r"(?:(?:the|a|an|el|la|un|una)\s+)?"
            r"(?:reminder|recordatorio)\s+"
            r"(?:(?:to|for|about|de|para|sobre)\s+)?"
            r"(?P<title>.+?)[\s.!?]*$"
        ),
        (
            r"^[¿?¡!\s]*(?:(?:the|el|la)\s+)?"
            r"(?:reminder|recordatorio)\s+"
            r"(?:(?:to|for|about|de|para|sobre)\s+)?"
            r"(?P<title>.+?)\s+"
            r"(?:needs?\s+to\s+be|has\s+to\s+be|"
            r"necesita\s+(?:ser\s+)?|se\s+(?:tiene|debe)\s+que\s+)"
            r"\s*"
            r"(?:deleted|removed|cancelled|canceled|eliminad[oa]|borrad[oa]|"
            r"cancelad[oa]|eliminar|borrar|cancelar)[\s.!?]*$"
        ),
        (
            r"^[¿?¡!\s]*(?:find|busca|buscar|encuentra|encontrar)\s+"
            r"(?:(?:the|el|la)\s+)?(?:reminder|recordatorio)\s+"
            r"(?:(?:to|for|about|de|para|sobre)\s+)?"
            r"(?P<title>.+?)\s+(?:and|y)\s+"
            r"(?:delete|remove|cancel|erase|elim[ií]nalo|borrarlo|quitarlo|"
            r"cancelarlo|remove\s+it|delete\s+it|cancel\s+it)[\s.!?]*$"
        ),
        (
            r"^[^\w]*(?:no necesito|i (?:do not|don't) need)\s+"
            r"(?P<title>.+?)[,;]\s*"
            r"(?:cancela|elimina|borra|cancel|delete|remove)\s+"
            r"(?:(?:este|el|this|the)\s+)?(?:recordatorio|reminder)[\s.!?]*$"
        ),
        (
            r"^[^\w]*(?P<title>.+?)\s+"
            r"(?:se\s+(?:cancel[oó]|cancelaron)|(?:was|were)\s+cancelled)\s+"
            r"(?:as[ií] que|por lo que|so)\s+"
            r"(?:(?:este|el|this|the)\s+)?(?:recordatorio|reminder)\s+"
            r"(?:se\s+(?:tiene|debe)\s+que\s+|needs?\s+to\s+be\s+)?"
            r"(?:eliminar|borrar|cancelar|deleted|removed|cancelled)[\s.!?]*$"
        ),
    )
    for pattern in patterns:
        match = re.match(pattern, evidence.strip(), re.IGNORECASE)
        if match is None:
            continue
        title = re.sub(
            r"(?:\s+please|\s+por favor)$",
            "",
            match.group("title").strip(" \t\r\n.,;:!?\"'“”‘’«»"),
            flags=re.IGNORECASE,
        ).strip()
        if title:
            return title
    return None


def _explicit_live_media_query_arguments(evidence: str) -> dict[str, object] | None:
    """Ground the bounded Spanish ``pon <music> en vivo`` request."""

    desired_music = effect_intent._desired_music_query(evidence)
    if desired_music is not None:
        return {"provider": "spotify", "query": desired_music}
    spoken_number_title = effect_intent._bare_spoken_number_media_query(evidence)
    if spoken_number_title is not None:
        return {"provider": "spotify", "query": spoken_number_title}

    match = re.match(
        r"^[^\w]*(?:(?:por favor|please)\s*[,;:]?\s*)?"
        r"(?:pon|ponme|pone|poneme)\s+(?P<query>.+?\s+en\s+vivo)"
        r"(?:\s+(?:por favor|please))?[\s.!?]*$",
        evidence,
        re.IGNORECASE,
    )
    if match is None:
        return None
    query = match.group("query").strip()
    if (
        not query
        or len(query.encode("utf-8")) > 1_024
        or not effect_intent._media_play_domain(effect_intent._fold(evidence))
    ):
        return None
    return {"provider": "spotify", "query": query}


def _explicit_location_search_arguments(evidence: str) -> dict[str, object] | None:
    """Preserve one standalone recommendation query without rewriting it."""

    folded = effect_intent._fold(evidence)
    if not effect_intent._location_recommendation_request(folded):
        return None
    query = evidence.strip(" \t\r\n¿?¡!.,;:\"'“”‘’«»")
    if not query or len(query.encode("utf-8")) > 2_000:
        return None
    return {"query": query}


_TEMPORAL_NUMBER_WORDS = effect_intent._TEMPORAL_NUMBER_WORDS


_TEMPORAL_NUMBER_PATTERN = effect_intent._TEMPORAL_NUMBER_PATTERN


def _temporal_number(token: str) -> int | None:
    folded = effect_intent._fold(token)
    if folded.isdigit():
        return int(folded)
    return _TEMPORAL_NUMBER_WORDS.get(folded)


def _explicit_browser_navigation_arguments(
    operation: str,
    evidence: str,
) -> dict[str, object] | None:
    """Canonicalize literal destinations and searches under public policy."""

    destination = effect_intent._symbolic_web_destination(evidence)
    if destination is not None and re.fullmatch(
        effect_intent._NAMED_PUBLIC_SITE, effect_intent._fold(destination)
    ) is None:
        # Its identity must come from the verified search, never a site-name map.
        # The closed public names below (youtube, gmail, github, chatgpt) are the
        # one exception the effect reader already relies on (WEB1257/1259).
        return None
    browser_music = effect_intent._named_browser_music_request(evidence)
    if browser_music is not None and browser_music[1] is not None:
        # MUSIC1827: YouTube's own results page with the person's literal
        # music words, confirmed as a complete URL in the named browser.
        if operation != "browser.navigate.named":
            return None
        browser, query = browser_music
        return {"browser": browser, "url": "https://www.youtube.com/results?" + urlencode({"search_query": query})}
    named_search = effect_intent._named_browser_search(evidence)
    if named_search is not None:
        if operation != "browser.navigate.named":
            return None
        browser, query = named_search
        # Bing is the product's public-search policy, not a claim about the
        # person's browser preferences. Confirm this complete URL and browser.
        return {"browser": browser, "url": "https://www.bing.com/search?" + urlencode({"q": query})}

    youtube_query = effect_intent._youtube_search_query(evidence)
    if youtube_query is not None:
        # WEB1481 «buscá videos de gatos en youtube»: YouTube's own results
        # page with the person's literal query, confirmed as a complete URL.
        if operation != "browser.navigate":
            return None
        return {"url": "https://www.youtube.com/results?" + urlencode({"search_query": youtube_query})}
    installed_query = effect_intent._installed_browser_search_query(evidence) or effect_intent._browser_search_query(evidence)
    if installed_query is not None:
        # WEB1455 «abre un navegador que tengas instalado y busca …»: the
        # product's public search page (Bing) with the person's literal query,
        # confirmed as a complete URL like the named-browser search.
        if operation != "browser.navigate":
            return None
        return {"url": "https://www.bing.com/search?" + urlencode({"q": installed_query})}
    google_query = effect_intent._explicit_google_search_query(evidence)
    if google_query is not None:
        # Named-browser clauses need their own authenticated browser evidence;
        # abstain here rather than silently opening the generic CDP session.
        if (
            operation != "browser.navigate"
            or effect_intent._named_browser(effect_intent._fold(evidence)) is not None
        ):
            return None
        return {"url": "https://www.google.com/search?" + urlencode({"q": google_query})}

    full_urls = [
        match.group(0).rstrip(".,;:!?)]}»”’")
        for match in re.finditer(r"https?://[^\s]+", evidence, re.IGNORECASE)
    ]
    bare_hosts = [
        match.group(0).rstrip(".,;:!?)]}»”’")
        for match in re.finditer(
            r"(?<![@\w])(?:www\.)?[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?"
            r"(?:\.[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?)+"
            r"(?:/[^\s]*)?",
            evidence,
            re.IGNORECASE,
        )
    ]
    destinations = list(dict.fromkeys(full_urls))
    destinations.extend(
        f"https://{host}"
        for host in bare_hosts
        if not any(host.casefold() in value.casefold() for value in full_urls)
    )
    folded = effect_intent._fold(evidence)
    if not destinations and re.search(r"\byoutube\b", folded):
        destinations.append("https://www.youtube.com/")
    if not destinations:
        named_public_sites = (
            (r"\bgmail\b", "https://mail.google.com/"),
            (r"\bgithub\b", "https://github.com/"),
            (r"\bchatgpt\b", "https://chatgpt.com/"),
            (r"\bwashington\s+post\b", "https://www.washingtonpost.com/"),
            (r"\bnew\s+york\s+times\b", "https://www.nytimes.com/"),
            (r"\bbbc\b", "https://www.bbc.com/"),
            (r"\bcnn\b", "https://www.cnn.com/"),
        )
        destinations.extend(
            url for pattern, url in named_public_sites if re.search(pattern, folded)
        )
    if len(destinations) != 1:
        return None
    arguments: dict[str, object] = {"url": destinations[0]}
    if operation == "browser.navigate.named":
        browser = effect_intent._named_browser(folded)
        if browser not in effect_intent.NAMED_CDP_BROWSERS:
            return None
        arguments["browser"] = browser
    return arguments


def _explicit_wifi_profile_arguments(evidence: str) -> dict[str, object] | None:
    """Preserve one explicitly named saved Wi-Fi profile."""

    place = effect_intent.wifi_place_request(evidence)
    if place is not None:
        # REOPEN1957 H0170/H0376: the place word travels as the name (a profile
        # literally called «Casa» still matches) and as the place to resolve.
        return {"profileName": place, "place": place}
    patterns = (
        (
            r"^[ż?Ą!\s]*(?:cambia|cambiar|change|switch)\s+"
            r"(?:(?:el|the)\s+)?wi[\s-]?fi\s+(?:a|to)\s+"
            r"(?P<profile>.+?)[\s?!.]*$"
        ),
        (
            r"^[ż?Ą!\s]*(?:conecta|conectar|conectame|con[eé]ctate|connect)\s+"
            r"(?:(?:al|a la|to|to the)\s+)?"
            r"(?:(?:red|network)\s+)?wi[\s-]?fi"
            r"(?:\s+(?:network|red))?\s+"
            r"(?:de|llamad[ao]|named|called)\s+"
            r"(?P<profile>.+?)[\s?!.]*$"
        ),
    )
    matches = [
        match
        for pattern in patterns
        if (match := re.match(pattern, evidence, re.IGNORECASE)) is not None
    ]
    if len(matches) != 1:
        return None
    profile = matches[0].group("profile").strip(" \t\r\n,;:.!?\"'“”‘’«»")
    folded = effect_intent._fold(profile)
    if (
        not folded
        or folded in {"it", "that", "eso", "esa", "esta", "wifi"}
        or re.search(r"\b(?:y|and|or|o)\b|[&,/\\]", folded)
        or len(profile.encode("utf-8")) > 256
    ):
        return None
    return {"profileName": profile}


def _explicit_notification_schedule_arguments(
    evidence: str,
) -> dict[str, object] | None:
    """Extract one audible alarm/timer with a single bounded time literal."""

    folded = effect_intent._fold(evidence)
    wake_request = effect_intent._wake_alarm_request(folded)
    count_request = effect_intent._count_down_request(folded)
    if not wake_request and not count_request and not re.search(
        r"\b(?:alarm|alarma|alerta|alert|timer|temporizador)\b", folded
    ):
        return None
    relative_pattern = (
        rf"\b(?P<duration>{effect_intent._RELATIVE_DURATION_PATTERN})\b"
    )
    # Time literals are read on the folded text: «9 de la mañana» carries an
    # ñ that the accent-free patterns never matched on the raw evidence
    # (TIME1193 probe). The title below still keeps the person's own words.
    relative = list(re.finditer(relative_pattern, folded, re.IGNORECASE))
    # One clock whose part of the day was said, after the hour or elsewhere
    # («esta tarde a las cinco»); the day is read from the whole request.
    clocks = effect_intent.spoken_clocks(folded)
    if len(relative) + len(clocks) != 1 or (clocks and not clocks[0].resolved):
        return None
    due_literal = (relative[0].group("duration") if relative else clocks[0].literal).strip()
    noun = re.search(
        r"\b(?:alarm|alarma|alerta|alert|timer|temporizador)\b", evidence, re.IGNORECASE
    )
    if noun is None and not wake_request and not count_request:
        return None
    title_start = noun.start() if noun is not None else 0
    if noun is None:
        return {
            "dueUtc": due_literal,
            "kind": "alarm",
            "title": evidence[title_start:].strip(),
        }
    title = evidence[noun.start() :].strip(" \t\r\n.,;:!?\"'“”‘’«»")
    if not title:
        return None
    return {
        "dueUtc": due_literal,
        "kind": "alarm",
        "title": title,
    }


# The words of a daily or hourly repetition, in the person's writing: the reminder they repeat is read without them.
_REPETITION_WORDS = re.compile(
    r"\b(?:(?:cada|todos\s+los|todas\s+las|every|each)\s+(?:d[ií]as?|ma[nñ]anas?|tardes?|noches?|horas?|days?|"
    r"mornings?|afternoons?|evenings?|nights?|hours?)|diariamente|a\s+diario|daily|hourly)\b",
    re.IGNORECASE,
)


def _explicit_relative_reminder_arguments(
    evidence: str,
) -> dict[str, object] | None:
    """Preserve one closed relative reminder's literal time and title."""

    duration = (
        rf"(?:(?:(?:en|in|dentro\s+de|within)\s+){effect_intent._RELATIVE_DURATION_PATTERN}|"
        rf"{effect_intent.CLOCK_PHRASE})"
    )
    # The person's own spelling reaches this reader: «recuérdame», «avísame».
    lead = r"^[¿?¡!\s]*(?:(?:por\s+favor|please)\s*,?\s+)?"
    remind = rf"(?:av[ií]same|record[aá]me|recu[eé]rdame|remind\s+me|{effect_intent.TASK_REMINDER_HEAD})"
    # Uso real 2026-09-24 «… a la una por la tarde», «… a las tres de la tarde mañana»: the day or the part
    # of it said after the clock belongs to the moment (the due reader reads it from the whole request).
    day_after = (
        r"(?:\s+(?:por\s+la\s+(?:ma[nñ]ana|tarde|noche)|esta\s+(?:ma[nñ]ana|tarde|noche)|pasado\s+ma[nñ]ana|"
        r"hoy|ma[nñ]ana|today|tonight|tomorrow|this\s+(?:morning|afternoon|evening)))?"
    )
    patterns = (
        rf"{lead}{remind}\s+"
        rf"(?P<due>{duration})\s+(?:(?:que|to|de)\s+)?(?P<title>.+?)[.!?]*$",
        rf"{lead}{remind}\s+"
        rf"(?:(?:que|to|de)\s+)?(?P<title>.+?)\s+(?P<due>{duration}){day_after}[.!?]*$",
        rf"{lead}(?P<due>{duration}),?\s+"
        rf"{remind}\s+"
        rf"(?:(?:que|to|de)\s+)?(?P<title>.+?)[.!?]*$",
        rf"{lead}(?:ponme|set)\s+(?:(?:un|a)\s+)?"
        rf"(?:recordatorio|reminder)\s+(?P<due>{duration})\s+"
        rf"(?:para|to)\s+(?P<title>.+?)[.!?]*$",
        rf"{lead}(?:recordatorio|reminder)\s+(?:de|to)\s+"
        rf"(?P<title>.+?)\s+(?P<due>{duration}){day_after}[.!?]*$",
        rf"{lead}(?:set\s+)?(?:a\s+)?reminder\s+to\s+"
        rf"(?P<title>.+?)\s+(?P<due>{duration}){day_after}[.!?]*$",
        # «dame una notificación de recordatorio para la reunión de mañana a las
        # diez a. m.», «ponme un recordatorio para sacar la basura a las ocho de
        # la noche», «send me a reminder to call mom at 6 pm»: the reminder asked
        # for as a thing, its subject, then its moment.
        rf"{lead}(?:dame|ponme|pon|creame|crea|hazme|haz|programa|programame|quiero|quisiera|necesito|"
        r"establece|establecer|fija|fijame|env[ií]ame|m[aá]ndame|create|give\s+me|send\s+me|set)\s+"
        r"(?:(?:un|una|a|an)\s+)?(?:(?:nuevo|new)\s+)?"
        r"(?:(?:notificaci[oó]n|aviso|alerta|notification|alert)\s+(?:de|of)\s+)?"
        r"(?:recordatorio|reminder|notificaci[oó]n|aviso|alerta|notification|alert)\s+"
        rf"(?:para|de|sobre|about|for|to)\s+(?P<title>.+?)\s+(?P<due>{duration}){day_after}[.!?]*$",
        # Uso real 2026-09-23 «add conference call at four p. m. to my reminders for today»: the
        # thing added to the reminders, then its moment.
        rf"{lead}(?:add|agrega|agregame|a[nñ]ade|a[nñ]ademe|pon|ponme)\s+(?P<title>.+?)\s+(?P<due>{duration})\s+"
        r"(?:to|a|en|in)\s+(?:(?:my|mis|the|los)\s+)?(?:reminders|recordatorios)"
        r"(?:\s+(?:for|para)\s+(?:today|tomorrow|hoy|ma[nñ]ana))?[.!?]*$",
    )
    # Two shapes may read the same request («set a reminder to …»); only readings that disagree abstain.
    readings = {
        (match.group("due").strip(), match.group("title").strip().rstrip(".!?").rstrip())
        for pattern in patterns
        if (match := re.fullmatch(pattern, evidence, re.IGNORECASE)) is not None
    }
    if len(readings) != 1:
        return None
    due, title = readings.pop()
    if not due or not title:
        return None
    return {"dueUtc": due, "title": title}


def _local_civil_utc(naive: datetime, local_zone: Any) -> datetime | None:
    """One unambiguous UTC instant for a local wall-clock time, or None across a DST fold or gap."""

    fold_zero = naive.replace(tzinfo=local_zone, fold=0).astimezone(timezone.utc)
    fold_one = naive.replace(tzinfo=local_zone, fold=1).astimezone(timezone.utc)
    if fold_zero != fold_one or fold_zero.astimezone(local_zone).replace(tzinfo=None) != naive:
        return None
    return fold_zero.replace(microsecond=0)


def _local_now(now_utc: datetime | None) -> datetime:
    if now_utc is None:
        return datetime.now().astimezone()
    if now_utc.tzinfo is None:
        raise ValueError("now_utc must carry timezone authority")
    return now_utc.astimezone(now_utc.tzinfo)


def _explicit_calendar_range_arguments(
    evidence: str,
    *,
    now_utc: datetime | None = None,
) -> dict[str, object] | None:
    """The window of an agenda read in local civil time (semantic.temporal.agenda_window), as UTC."""

    local_now = _local_now(now_utc)
    local_zone = local_now.tzinfo
    naive_now = local_now.replace(tzinfo=None, microsecond=0)
    window = agenda_window(effect_intent._fold(evidence), naive_now)
    if window is None or local_zone is None:
        return None
    start_utc = _local_civil_utc(window[0], local_zone)
    end_utc = _local_civil_utc(window[1], local_zone)
    if start_utc is None or end_utc is None or end_utc <= start_utc:
        return None
    return {
        "startUtc": start_utc.isoformat().replace("+00:00", "Z"),
        "endUtc": end_utc.isoformat().replace("+00:00", "Z"),
    }


# A start said with no end and no duration: the event lasts an hour (uso real 2026-09-23 «añade una
# reunión con Tom a mi calendario para las nueve de la mañana» was asked how long it would last).
_DEFAULT_EVENT_MINUTES = 60


def _clock_literal(clock: SpokenClock) -> str:
    """One resolved clock written so the due reader reads it back unchanged («a las 9:00 a. m.»)."""

    return f"a las {clock.hour % 12 or 12}:{clock.minute:02d} {'a. m.' if clock.hour < 12 else 'p. m.'}"


def _explicit_calendar_event_arguments(
    evidence: str,
    *,
    now_utc: datetime | None = None,
) -> dict[str, object] | None:
    """Title, start and end of one event put on the agenda, as said (semantic.notes.agenda_event_request):
    a whole day for a marked date or span, otherwise the start said and the end said, the duration said
    or an hour. None when the moment has passed or cannot be one instant."""

    event = agenda_event_request(evidence)
    if event is None or event.missing:
        return None
    local_now = _local_now(now_utc)
    folded = effect_intent._fold(evidence)
    if event.whole_day:
        window = spoken_window(folded, local_now.replace(tzinfo=None, microsecond=0))
        if window is None or local_now.tzinfo is None:
            return None
        start_utc = _local_civil_utc(window[0], local_now.tzinfo)
        end_utc = _local_civil_utc(window[1], local_now.tzinfo)
    else:
        timing = event.timing
        assert timing.start is not None
        start_text = _canonical_due_utc(_clock_literal(timing.start), folded, now_utc=now_utc)
        start_utc = datetime.fromisoformat(start_text.replace("Z", "+00:00")) if start_text else None
        end_utc = None
        if start_utc is not None:
            if timing.end is not None and timing.end.resolved:
                local_start = start_utc.astimezone(local_now.tzinfo)
                local_end = local_start.replace(hour=timing.end.hour, minute=timing.end.minute)
                end_utc = _local_civil_utc(local_end.replace(tzinfo=None), local_now.tzinfo)
            elif timing.end is None:
                end_utc = start_utc + timedelta(minutes=timing.minutes or _DEFAULT_EVENT_MINUTES)
    if start_utc is None or end_utc is None or end_utc <= start_utc:
        return None
    return {
        "title": event.title,
        "startUtc": start_utc.isoformat().replace("+00:00", "Z"),
        "endUtc": end_utc.isoformat().replace("+00:00", "Z"),
    }


def _explicit_media_control_arguments(evidence: str) -> dict[str, object] | None:
    """Ground one literal playback command without interpreting a media query."""

    folded = effect_intent._fold(evidence)
    resuming = effect_intent._resume_existing_media(folded)
    transport = effect_intent._media_transport_action(folded)
    action_patterns = {
        "next": (
            r"\b(?:skip|salta|saltar|saltea|saltear)\b",
            r"\b(?:next|siguiente)\s+(?:artist|artista|song|cancion|track|pista|"
            r"podcast|episode|episodio)\b",
            (
                r"^[^\w]*(?:(?:por favor|please)\s*[,;:]?\s*)?"
                r"(?:cambia|cambiar|change|switch)\s+"
                r"(?:(?:el|la|the|current|actual)\s+)?(?:artista|artist)"
                r"(?:\s*[,;:]?\s*(?:por favor|please))?[\s.!?]*$"
            ),
        ),
        "previous": (
            r"\b(?:previous|prior)\s+(?:song|track|podcast|episode)\b",
            r"\b(?:cancion|pista|podcast|episodio)\s+anterior\b",
            r"\b(?:go|ve|vuelve)\s+(?:back|atras)\b",
        ),
        "pause": (
            # In a resume request, "en pausa" describes the loaded state.
            # A separate pause verb or leave-in-pause command still conflicts.
            r"(?<!en )\b(?:pause|pausa|pausar|pausalo|pausala|pausame)\b"
            if resuming else r"\b(?:pause|pausa|pausar|pausalo|pausala|pausame)\b",
            r"\b(?:deja|dejar)\s+en\s+pausa\b",
        ),
        "play": (
            rf"\b{effect_intent._MEDIA_RESUME_VERB}\b",
            r"\b(?:play|reproduce|reproducir)\b[^.;!?]*\b(?:paused|pausad[ao])\b",
        ),
        "stop": (r"\b(?:stop|deten|detener)\b",),
        "toggle": (r"\b(?:toggle|alternar)\b",),
    }
    actions = {
        action
        for action, patterns in action_patterns.items()
        if (transport is None or action not in {"next", "previous", "stop"})
        and any(re.search(pattern, folded, re.IGNORECASE) for pattern in patterns)
    }
    if transport is not None:
        actions.add(transport)
    if not actions and resuming:
        # Tanda 4c «pon mi playlist reciente»: resuming with no other verb is playing.
        actions.add("play")
    if len(actions) != 1:
        return None
    arguments: dict[str, object] = {"action": next(iter(actions))}
    if re.search(r"\bspotify\b", folded, re.IGNORECASE):
        # The optional source narrows SMTC selection to the session the person
        # actually named.  Without it, Windows' current session may belong to
        # a browser or another player even immediately after Spotify starts.
        arguments["sourceApp"] = "spotify"
    return arguments


def _presentation_title(topic: str) -> str:
    """«hablando de amor» → «Amor»: the topic with its first letter up."""

    cleaned = " ".join(topic.split())
    return cleaned[:1].upper() + cleaned[1:] if cleaned else "Presentación"


def _presentation_file_name(topic: str) -> str:
    """The .pptx name the presentation adapter derives from the title."""

    title = _presentation_title(topic)
    safe = "".join(character for character in title if character not in '<>:"/\\|?*').strip()
    return (safe or "Presentacion") + ".pptx"


def _presentation_arguments(
    llm_runtime: object,
    objective: str,
) -> dict[str, object] | None:
    """REOPEN1957 H0188: the slides are authored by the local model (one
    entry per slide: title line and bullet lines) for the topic and count the
    person asked; the title and the count come from the request, never from
    the model."""

    request = effect_intent.presentation_request(objective)
    if request is None:
        return None
    topic, count = request
    compose = getattr(llm_runtime, "compose_presentation_slides", None)
    if compose is None:
        return None
    slides = compose(topic, count)
    if not isinstance(slides, list) or len(slides) != count:
        return None
    cleaned: list[str] = []
    for slide in slides:
        if not isinstance(slide, str):
            return None
        lines = [line.strip() for line in slide.replace("\r\n", "\n").split("\n") if line.strip()]
        if not lines:
            return None
        cleaned.append("\n".join(lines[:9]))
    return {"title": _presentation_title(topic), "slides": cleaned, "folder": "documents"}


def _explicit_arguments_from_evidence(
    operation: str,
    evidence: str,
    application_names: tuple[str, ...] = (),
    game_catalog: GameCatalogIndex = GameCatalogIndex(),
) -> dict[str, object] | None:
    """Extract only unambiguous literals from one preserved effect fragment.

    Repeated effects cannot be grounded safely against the whole objective:
    for example, "mute ... then unmute" contains both Boolean cues.  The
    effect recognizer already supplies a bounded clause-local fragment for
    every preserved operation, so a very small extractor can retain those
    identities without asking the model to choose between sibling effects.
    All returned values still cross the authenticated JSON Schema and normal
    grounding boundary before they enter a plan.
    """

    folded = unicodedata.normalize("NFKD", evidence.casefold())
    folded = "".join(
        character for character in folded if not unicodedata.combining(character)
    )
    folded = " ".join(folded.split())
    numbers = [
        int(found.group(0))
        for found in re.finditer(
            r"(?<![0-9])(?:100|[0-9]{1,2})(?![0-9])",
            folded,
        )
    ]

    def clause_literal(value: str) -> str:
        """Remove unquoted clause punctuation that is not part of a literal."""

        return value.strip().rstrip(".!?").rstrip()

    if operation == "browser.control":
        return (effect_intent.browser_back_arguments(evidence)
                or effect_intent.browser_new_tab_arguments(evidence)
                or effect_intent.browser_close_all_tabs_arguments(evidence))

    if operation == "system.status":
        return _explicit_system_status_scope(evidence)

    if operation == "system.time":
        # The clock takes no argument; the time of another place or zone takes
        # that place, as said or as the zone the person named. Never asked of the
        # model: a place it guessed would be read as the person's.
        elsewhere = clock_elsewhere(folded)
        return {"place": elsewhere.place} if elsewhere is not None else {}

    if operation == "clipboard.write.text":
        # CLIPBOARD1359: the quoted or colon-introduced fragment is the
        # person's literal, case and accents preserved by the reader.
        literal = effect_intent.literal_clipboard_write_text(evidence)
        return {"text": literal} if literal is not None else None

    if operation == "window.close.all":
        # CLOSEALL1733: no argument; the order names every window.
        return {} if effect_intent.close_all_request(effect_intent._fold(evidence)) else None

    if operation == "window.minimize.all":
        # MINALL1687: no arguments; the order over every window is the whole request.
        return {} if effect_intent.minimize_all_request(effect_intent._fold(evidence)) else None

    if operation == "input.key.press" and start_menu_request(effect_intent._fold(evidence)):
        # Tanda 4 «abre el menú inicio», «open the start menu»: the Start menu opens with the Windows key.
        return {"key": "win"}

    if operation == "clipboard.read.text":
        # The read takes no literal; naming the clipboard is the whole request.
        return {} if re.search(r"\b(?:portapapeles|clipboard)\b", folded) else None

    if operation == "system.settings.status":
        # BRIGHT1283: the reader owns the setting enum; «brillo» is the literal.
        return {"setting": "brightness"} if effect_intent.brightness_status_request(evidence) else None

    if operation == "system.settings.adjust":
        adjustment = effect_intent._literal_brightness_adjustment(evidence)
        return {**adjustment, "setting": "brightness"} if adjustment is not None else None

    if operation == "system.settings.set":
        airplane = effect_intent.airplane_mode_request(evidence)
        if airplane is not None:
            return {"setting": "airplane_mode", "value": airplane}
        level = effect_intent._literal_brightness_level(evidence)
        return {"setting": "brightness", "value": level} if level is not None else None

    if operation == "system.settings.status" and effect_intent.airplane_mode_question(evidence):
        return {"setting": "airplane_mode"}

    if operation == "window.snap":
        # ARRANGE1781: the side is the person's literal; windowId comes from window.resolve.
        snap = effect_intent.resolve_application_snap(evidence, application_names)
        return {"side": snap[1]} if snap is not None else None

    if operation == "window.resolve":
        application_name = effect_intent.resolve_application_snap_name(
            evidence, application_names,
        ) or effect_intent.resolve_application_close_name(
            evidence, application_names,
        ) or effect_intent.resolve_application_focus_name(
            evidence, application_names,
        ) or effect_intent.resolve_application_minimize_name(
            evidence, application_names,
        ) or effect_intent.conditional_open_pause_app(
            evidence, application_names,
        )
        if application_name is not None:
            return {"applicationName": application_name}
        if effect_intent.other_window_switch_request(evidence):
            # REOPEN1993 H0263: every visible window, so the one behind the
            # foreground can be chosen from the verified reading.
            return {"process": "*", "byTitle": False, "limit": 50}
        inventory = effect_intent.window_inventory_arguments(evidence)
        if inventory is not None:
            return inventory
        title = effect_intent.explicit_window_title(evidence)
        return {"process": title, "byTitle": True} if title is not None else None

    if operation == "window.application.status":
        name = effect_intent.resolve_application_window_status_name(
            evidence, application_names,
        )
        return {"name": name} if name is not None else None

    if operation == "app.open":
        app_id = resolve_application_catalog_app_id(evidence, application_names)
        if app_id is None:
            # REOPEN1993 «abre Steel.»: the single installed near name is the
            # target the reader chose; ground it by its catalog name.
            near = effect_intent.near_single_open_candidate(evidence, application_names, game_catalog)
            if near is not None and near[0] == "app.open":
                app_id = resolve_application_catalog_app_id(near[1], application_names)
        return {"appId": app_id} if app_id is not None else None

    if operation == "input.visible.click":
        label = effect_intent._visible_click_label(folded, allow_navigate=True)
        return {"label": label} if label is not None else None

    if operation == "app.installed":
        name = effect_intent.installed_catalog_application_name(
            evidence, application_names,
        ) or resolve_application_installed_name(evidence, application_names)
        return {"name": name} if name is not None else None

    if operation == "client.channel.locate":
        # DISCORD1839: the client and the place are the person's literal.
        located = effect_intent.client_channel_request(evidence)
        return {"client": located[0], "name": located[1]} if located is not None else None

    if operation == "message.draft":
        # MSG1837: channel, recipient and text are the person's literal.
        draft = effect_intent.message_draft_request(evidence)
        return {"channel": draft[0], "recipient": draft[1], "text": draft[2]} if draft is not None else None

    if operation == "email.send":
        # Fase 7 (D4): the address, the text and the subject are the person's literals.
        mail = effect_intent.email_send_request(evidence)
        return dict(mail) if mail is not None else None

    if operation == "message.send.test":
        # MSG §6: channel, the requested recipient and text are the person's
        # literal; the adapter forces the real destination to the owner's test
        # channel, so the requested recipient is recorded but never targeted.
        draft = effect_intent.message_draft_request(evidence)
        return {"channel": draft[0], "requestedRecipient": draft[1], "text": draft[2]} if draft is not None else None

    if operation == "storage.removable.list":
        if effect_intent._removable_storage_request(evidence):
            return {}

    if operation == "software.python.package.status":
        # PIP1817: the package is the person's literal from the request.
        package = effect_intent._python_package_request(evidence)
        return {"package": package} if package is not None else None

    if operation == "game.entitlement.named":
        # INSTALL1617: the title is the person's literal from the request.
        title = effect_intent.steam_library_title(evidence)
        if title is None:
            return None
        # H0578: the store named after the title picks the library that is read.
        store = effect_intent.game_library_store(evidence)
        return {"title": title, "store": store} if store == "epic" else {"title": title}

    if operation == "game.installed.named":
        # APPS1613 H0275: the title is the clause's own literal; the provider
        # is the one the clause names, otherwise every manifest family.
        title = effect_intent.installed_game_title(evidence)
        if title is None:
            return None
        return {"provider": effect_intent.installed_game_provider(evidence), "title": title}

    if operation == "game.launch":
        app_id = resolve_game_catalog_app_id(evidence, game_catalog)
        if app_id is None:
            # REOPEN1993 «Ve a Mad de Rivals.»: the single installed near title.
            near = effect_intent.near_single_open_candidate(evidence, application_names, game_catalog)
            if near is not None and near[0] == "game.launch":
                app_id = resolve_game_catalog_app_id(near[1], game_catalog)
        return {"appId": app_id} if app_id is not None else None

    if operation in {
        "game.install.cancel",
        "game.install.prepare",
        "game.install.status",
    }:
        app_ids = {
            match.group("app_id")
            for match in re.finditer(
                r"\bapp\s*id\s*[:#-]?\s*(?P<app_id>[1-9][0-9]{0,15})\b",
                evidence,
                re.IGNORECASE,
            )
        }
        return {"appId": next(iter(app_ids))} if len(app_ids) == 1 else None

    if operation == "game.catalog.list":
        if re.search(r"\b(?:biblioteca|library)\b", folded) and not numbers:
            return {}
        return None

    if operation == "filesystem.explorer.count":
        extension = effect_intent.explorer_count_request(evidence)
        if extension is not None:
            return {"extension": extension}

    if operation == "system.power":
        # H0401/H0714: the transition is the verb the person used; nothing else
        # in the request names a power action.
        folded_power = effect_intent._strip_request_envelope(effect_intent._fold(evidence)).strip()
        if re.match(r"^(?:reinicia|reiniciame|reiniciar|reboot|restart)\b", folded_power):
            return {"action": "restart"}
        if re.match(r"^(?:apaga|apagame|apagar|shutdown|shut\s+down|turn\s+off|power\s+off|switch\s+off)\b", folded_power):
            return {"action": "shutdown"}

    if operation == "message.recipient.resolve":
        any_channel = effect_intent.message_request_any_channel(evidence)
        if any_channel is not None:
            # REOPEN1993 grupo E: no client named → looked up in the clients.
            return {"channel": any_channel[2] or "any", "recipient": any_channel[0]}
        named_client = effect_intent.message_request_named_client(evidence)
        if named_client is not None:
            # Owner 2026-09-21: the client named → the person is looked up there.
            return {"channel": named_client[2], "recipient": named_client[0]}

    if operation in {"document.text.read", "document.pdf.read"}:
        # REOPEN1957 H0299: the pasted path names the folder, the subfolder and the file.
        known_path = effect_intent.known_folder_file_path(evidence)
        if known_path is not None and known_path[0] == operation:
            return dict(known_path[1])

    if operation == "document.pdf.read":
        # PDF1689 «resumime informe.pdf»: the file name is the person's
        # literal; the folder is a catalog root, or every known folder when
        # none is named (the provider refuses an ambiguous name).
        pdf_match = effect_intent._pdf_summary_request(evidence)
        if pdf_match is None:
            return None
        pdf_name = pdf_match.group("name").strip().strip("\"'").rstrip(".!?,").strip()
        if (
            not pdf_name
            or re.search(r"[\\/:*?\"<>|]", pdf_name)
            or any(ord(character) < 32 for character in pdf_name)
            or len(pdf_name.encode("utf-8")) > 512
        ):
            return None
        pdf_folder = pdf_match.group("folder")
        return {
            "fileName": pdf_name,
            "folder": effect_intent._KNOWN_FOLDER_ENUM[effect_intent._fold(pdf_folder)]
            if pdf_folder else "all_known",
        }

    if operation == "filesystem.known.trash.named":
        # «borra el archivo hola.txt del escritorio»: the file name is the
        # person's literal; the folder is a catalog root, or every known folder
        # when none is named (the provider refuses an ambiguous name).
        trash_match = effect_intent._file_trash_request(evidence)
        if trash_match is None:
            return None
        file_name = trash_match.group("name").strip().strip("\"'").rstrip(".!?,").strip()
        if (
            not file_name
            or re.search(r"[\\/:*?\"<>|]", file_name)
            or any(ord(character) < 32 for character in file_name)
            or len(file_name.encode("utf-8")) > 512
        ):
            return None
        folder_word = trash_match.group("folder")
        return {
            "fileName": file_name,
            "folder": effect_intent._KNOWN_FOLDER_ENUM[effect_intent._fold(folder_word)]
            if folder_word else "all_known",
        }

    presentation = effect_intent.presentation_request(evidence)
    if presentation is not None and operation == "file.open":
        # REOPEN1957 H0188: the deck lands in Documents under its topic's name.
        return {"folder": "documents", "name": _presentation_file_name(presentation[0])}

    zip_mission_folder = effect_intent.folder_txt_zip_open_mission(evidence)
    if zip_mission_folder is not None and operation in {"filesystem.create.directory", "filesystem.write.text", "file.compress", "file.open"}:
        # REOPEN1957 H0542: Windows' own default names for the unnamed folder and file.
        folder_name = effect_intent._ZIP_MISSION_FOLDER
        file_name = effect_intent._ZIP_MISSION_FILE
        if operation == "filesystem.create.directory":
            return {"folder": zip_mission_folder, "relativePath": folder_name}
        if operation == "filesystem.write.text":
            return {"folder": zip_mission_folder, "relativePath": folder_name + "/" + file_name, "text": "", "expectedSha256": None}
        if operation == "file.compress":
            return {"folder": zip_mission_folder, "name": folder_name}
        return {"folder": zip_mission_folder, "name": folder_name + ".zip"}

    if operation == "filesystem.create.directory":
        # «crea una carpeta llamada CarterTest en el escritorio»: the name is
        # the person's, the folder is a catalog root (owner decision, point 2).
        directory_match = effect_intent._directory_creation_request(evidence)
        if directory_match is None:
            return None
        relative_path = directory_match.group("name").strip()
        if (
            len(relative_path) >= 2
            and relative_path[0] == relative_path[-1]
            and relative_path[0] in {'"', "'"}
        ):
            relative_path = relative_path[1:-1].strip()
        path_segments = re.split(r"[\\/]", relative_path)
        if not (
            relative_path
            and not re.match(r"^(?:[A-Za-z]:|[\\/]{1,2})", relative_path)
            and all(segment not in {"", ".", ".."} for segment in path_segments)
            and not any(ord(character) < 32 for character in relative_path)
            and len(relative_path.encode("utf-8")) <= 1_024
        ):
            return None
        folder_word = directory_match.group("folder_a") or directory_match.group("folder_b")
        arguments: dict[str, object] = {"relativePath": relative_path}
        if folder_word:
            arguments["folder"] = effect_intent._KNOWN_FOLDER_ENUM[
                effect_intent._fold(folder_word)
            ]
        return arguments

    if operation == "filesystem.write.text":
        write_match = effect_intent._file_creation_request(evidence) or re.fullmatch(
            r"[¿?¡!\s]*(?:"
            r"(?:crea|crear|guarda|guardar|escribe|escribir)\s+"
            r"(?:(?:un|el)\s+)?archivo|"
            r"(?:create|save|write)\s+(?:(?:a|the)\s+)?file"
            r")\s+"
            r"(?:(?:llamad[oa]|named|called)\s+)?"
            r"(?P<name>\"[^\"]+\"|'[^']+'|\S+?)\s+"
            r"(?:con(?:\s+(?:el\s+)?(?:contenido|texto))?|que\s+diga|"
            r"with(?:\s+(?:the\s+)?(?:content|text))?|containing|saying)\s+"
            r"(?P<content>.+?)[\s]*",
            evidence,
            re.IGNORECASE,
        )
        if write_match is not None:
            relative_path = write_match.group("name").strip()
            text = clause_literal(write_match.group("content"))
            folder_word = (
                write_match.groupdict().get("folder_a")
                or write_match.groupdict().get("folder_b")
            )
            if (
                len(relative_path) >= 2
                and relative_path[0] == relative_path[-1]
                and relative_path[0] in {'"', "'"}
            ):
                relative_path = relative_path[1:-1].strip()
            if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
                text = text[1:-1]
            path_segments = re.split(r"[\\/]", relative_path)
            safe_path = (
                bool(relative_path)
                and not re.match(r"^(?:[A-Za-z]:|[\\/]{1,2})", relative_path)
                and all(segment not in {"", ".", ".."} for segment in path_segments)
                and not any(ord(character) < 32 for character in relative_path)
                and len(relative_path.encode("utf-8")) <= 1_024
            )
            if safe_path and len(text.encode("utf-8")) <= 1_048_576:
                arguments = {"relativePath": relative_path, "text": text}
                if folder_word:
                    arguments["folder"] = effect_intent._KNOWN_FOLDER_ENUM[
                        effect_intent._fold(folder_word)
                    ]
                return arguments
        return None

    if operation == "wifi.connect.named":
        return _explicit_wifi_profile_arguments(evidence)

    if operation in {"browser.navigate", "browser.navigate.named"}:
        return _explicit_browser_navigation_arguments(operation, evidence)

    if operation == "streaming.navigate":
        navigation = _explicit_browser_navigation_arguments(
            "browser.navigate",
            evidence,
        )
        if navigation is None:
            return None
        resource_uri = navigation.get("url")
        if not isinstance(resource_uri, str):
            return None
        host = (urlsplit(resource_uri).hostname or "").casefold().rstrip(".")
        services = {
            service
            for service, suffixes in (
                ("netflix", ("netflix.com",)),
                ("prime_video", ("primevideo.com", "amazon.com")),
                ("youtube", ("youtube.com", "youtu.be")),
            )
            if any(host == suffix or host.endswith("." + suffix) for suffix in suffixes)
        }
        if len(services) == 1:
            return {
                "resourceUri": resource_uri,
                "service": next(iter(services)),
            }
        return None

    if operation == "streaming.play.named":
        # VIDEO1921: sin entrada aquí el planificador rellenaba service y title a
        # ciegas, y con «start Stranger Things on Netflix» o «… en nerflix» se
        # rendía y preguntaba qué servicio y qué título, con los dos escritos
        # delante. El servicio es siempre netflix aunque se escriba mal —lo más
        # probable es que lo escriba mal el oído de BAXY— y el título es lo que
        # hay entre el verbo y «en/on Netflix», tal cual: la búsqueda de Netflix
        # es difusa y el recibo dirá el título que de verdad se puso.
        named = re.search(
            r"^(?:(?:quiero|quisiera|i\s+want\s+to|i\s+wanna|i'd\s+like\s+to)\s+)?"
            r"(?:reproduc[eií]|play|pon[eé]?(?:me)?|ponme|put(?:\s+on)?|busc[aá]|find|"
            r"inici[aá]|start|encuentra|encuentras|localiza|locate|ver|watch)\s+"
            r"(?:(?:la|the)\s+(?:serie|series|pel[ií]cula|peli|movie|film)\s+)?"
            r"(?P<title>.+?)\s+"
            r"(?:en|in|on|desde|from|through|usando|using)\s+"
            r"(?:netflix|nerflix|netlix|netfix|netflis|neflix|"
            r"disney\s*\+|disney\s*plus|disneyplus|disney|dysney|disne|dinsey|dizney)\b",
            clause_literal(evidence),
            re.IGNORECASE,
        )
        if named is None:
            return None
        title = named.group("title").strip().strip("\"'«»“”").strip()
        if not title or len(title.encode("utf-8")) > 512:
            return None
        # VIDEO1947: the service is the one spelled after the title.
        streaming_arguments: dict[str, object] = {
            "service": effect_intent.streaming_service_named(evidence),
            "title": title,
        }
        return streaming_arguments

    if operation == "media.play.query":
        return _explicit_live_media_query_arguments(evidence)

    if operation == "media.play.youtube":
        # MUSIC1553: the person's own words name what to play; the provider
        # searches YouTube with them and the receipt carries the title played.
        youtube_query = effect_intent.youtube_play_query(evidence) or effect_intent.radio_station_query(evidence)
        if youtube_query is None and not re.search(r"\b(?:youtube|spotify)\b", folded):
            # MUSIC1559 «pon música de daft punk», «poneme algo de música tranqui»:
            # the named music, in the person's words, is the YouTube query.
            named = _explicit_live_media_query_arguments(evidence)
            if named is not None and isinstance(named.get("query"), str):
                youtube_query = re.sub(
                    r"^(?:algo\s+de|something\s+like|some)\s+", "", named["query"].strip(), flags=re.IGNORECASE,
                ).strip() or None
        return {"query": youtube_query} if youtube_query is not None else None

    if operation == "calendar.event.list":
        return _explicit_calendar_range_arguments(evidence)

    if operation == "calendar.event.create":
        return _explicit_calendar_event_arguments(evidence)

    if operation == "media.control":
        return _explicit_media_control_arguments(evidence)

    if operation == "web.search":
        # H0463 «… usando la API publica»: the declined means is not part of
        # the query (the query «el App ID de Doom Eternal en Steam usando la API
        # publica» still found SteamDB, but the words are the person's directive,
        # not what they are looking for).
        evidence = effect_intent._strip_trailing_means_directive(evidence)
        research_question = effect_intent._research_question_query(evidence)
        if research_question is not None:
            # WEB1831: the engine answers the question in the person's words
            # (the lead-in supplies the subject when the question names none).
            return {"query": research_question}
        opinion = effect_intent.public_opinion_query(evidence) or effect_intent.record_fact_query(evidence)
        if opinion is not None:
            # Fase 3.5: opinions of a public work («… opiniones») and a dated fact
            # (the question in the person's words) are looked up before answering.
            return {"query": opinion}
        destination = effect_intent._symbolic_web_destination(evidence)
        if destination is not None:
            return {"query": destination}
        named_site = effect_intent._named_browser_site_request(evidence)
        if named_site is not None:
            # H0081 «abre opera gx y entra a pivigames»: the site name alone is
            # the query; its URL is the first verified result.
            return {"query": named_site[1]}
        query = ""
        search_evidence = re.split(
            r"\s+(?:(?:y\s+)?(?:despu\S+s|luego)|and\s+then|then|afterwards)"
            r"\s+(?=(?:navega|navegar|abre|abrir|ve|llevame|ll\S+vame|"
            r"reproduce|reproducir|navigate|open|go|play|stream|launch)\b)",
            evidence,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0]
        location = _explicit_location_search_arguments(search_evidence)
        if location is not None:
            return location
        entity = effect_intent._entity_lookup_query(search_evidence)
        if entity is not None:
            # KNOWLEDGE1473 «¿Quién es Daredevil?»: the engine answers the bare
            # name; the question words around it return unrelated pages.
            return {"query": entity}
        curiosity_subject = effect_intent.curiosity_topic(search_evidence)
        if curiosity_subject is not None:
            # KNOWLEDGE1505 «decime una curiosidad»: the engine serves no pages
            # for the word «curiosidad»; it answers a well-known subject with
            # its public page, and the curiosity is what that page states.
            return {"query": curiosity_subject}
        topic = effect_intent._topic_research_query(search_evidence)
        if topic is not None:
            # WEB1451 «Investiga Spider-Man»: the engine answers the topic, not
            # the research verb («investiga» never appears in a result page).
            return {"query": topic}
        news_query = news_lookup_query(search_evidence)
        if news_query is not None:
            # WEB1451 «qué pasó hoy en el mundo», tanda 4 «dime que esta pasando en mi
            # ciudad»: the engine answers a news query with the person's scope words
            # («noticias de hoy en el mundo»); the question itself returns unrelated pages.
            return {"query": news_query}
        weather_query = effect_intent._weather_lookup_query(search_evidence)
        if weather_query is not None:
            # WEB1445 «qué clima hace hoy», «mostrame el clima», «va a llover
            # mañana»: the engine answers a weather query with the local forecast,
            # but the request verbs («mostrame», «hace») never appear in a result
            # and the relevance filter rejected every item. The query keeps only
            # the weather words the person said, in their order.
            return {"query": weather_query}
        search = list(
            re.finditer(
                (
                    rf"\b(?:{effect_intent._SEARCH}|buscá)(?:\s+for)?\b"
                    r"(?:\s+en\s+(?:google|internet|la\s+web|the\s+web))?"
                    r"\s*[:,-]?\s*(?P<query>.+?)"
                    r"(?=\s+(?:(?:y\s+)?(?:despu[eé]s|luego)|and\s+then|then|"
                    r"afterwards)\s+(?:navega|navegar|abre|abrir|ve|llevame|"
                    r"ll[eé]vame|reproduce|reproducir|navigate|open|go|play|"
                    r"stream|launch)\b|\s*$)"
                ),
                search_evidence,
                re.IGNORECASE,
            )
        )
        if search:
            query = clause_literal(search[-1].group("query"))
            query = re.sub(
                r"^(?:exactamente|exactly)\s+",
                "",
                query,
                count=1,
                flags=re.IGNORECASE,
            )
            query = re.sub(
                r"\s+(?:en\s+la\s+web|on\s+the\s+web)$",
                "",
                query,
                count=1,
                flags=re.IGNORECASE,
            )
            # SEARCH2011 «Buscá Transformers, porfa»: the courtesy is not part of the query.
            query = re.sub(
                r"\s*[,;]?\s*(?:por\s+favor|porfa|porfi|please|pls|plz|dale|gracias|thanks)\s*$",
                "",
                query,
                flags=re.IGNORECASE,
            ).strip(" \t.,;:!?")
        else:
            opened_page = re.match(
                (
                    r"^[Â¿?Â¡!\s]*(?:abre|abrir|open)\s+"
                    r"(?:(?:la|el|the|a)\s+)?(?P<query>.+?)\s*[.!?]*$"
                ),
                evidence,
                re.IGNORECASE,
            )
            # Tanda 4 «dime que esta pasando…» found the song «Dime»: the words asking to be told are
            # not looked up.
            query = (
                clause_literal(opened_page.group("query"))
                if opened_page is not None
                else public_query_body(evidence)
            )
        return {"query": query} if query and len(query.encode("utf-8")) <= 512 else None

    if operation == "input.text.type":
        quoted = re.search(
            r"[\"“](?P<text>[^\"”]{1,4096})[\"”]",
            evidence,
        )
        if quoted is not None:
            return {"text": quoted.group("text")}
        deictic = re.search(
            # REOPEN1993 H0097 «ponle hola»: the literal after the deictic head.
            r"(?i)^[\s¡!¿?]*(?:pon[eé]?le|ponele|pon[eé]?melo|put\s+on\s+it|write\s+on\s+it)\s+"
            r"(?!(?:a|al|por|para|que|en)\b)(?P<text>.+?)"
            r"(?:\s+(?:ahora|ya|now|please|por\s+favor|porfa))*[\s.!?]*$",
            evidence.strip(),
        )
        if deictic is not None:
            return {"text": deictic.group("text").strip()}
        typed = re.search(
            (
                r"\b(?:escribe|escrib[ií]|escribir|teclea|teclear|write|type)\b"
                r"\s+(?P<text>.+?)"
                r"(?=\s+en\s+(?:la|el|the)\s+(?:b[uú]squeda|search|campo|field|"
                r"cuadro|box)\b|\s*[.!?]*$)"
            ),
            evidence,
            re.IGNORECASE,
        )
        if typed is not None:
            text = clause_literal(typed.group("text"))
            return {"text": text} if text else None

    if operation == "message.recipient.resolve":
        return _explicit_message_recipient_arguments(evidence)

    if operation == "reminder.resolve.exact":
        title = _explicit_local_reminder_title(evidence)
        return {"title": title} if title is not None else None

    if operation == "task.resolve.exact" and (removal := effect_intent.list_removal_request(evidence)) is not None:
        # «take bathroom painting off the list»: the entry is the title it was put on the list with.
        return {"title": removal.entry} if removal.entry else None

    if operation == "note.create":
        # This closed form carries both required literals in one atomic effect
        # fragment. Preserve their original spelling and punctuation, then let
        # the authenticated schema and normal grounding boundary validate them.
        note_pattern = (
            r"\b(?:nota|note)\s+"
            r"(?:(?:titulad[ao]|llamad[ao]|titled|named|called)\s+)?"
            r"(?P<title>.+?)\s+"
            r"(?:con\s+(?:el\s+)?(?:contenido|texto)|que\s+diga|"
            r"with\s+(?:the\s+)?content|saying|containing)\s+"
            r"(?P<content>.+?)\s*$"
        )
        matches = list(re.finditer(note_pattern, evidence, re.IGNORECASE))
        if len(matches) == 1:
            title = clause_literal(matches[0].group("title"))
            content = clause_literal(matches[0].group("content"))
            if title and content:
                return {"title": title, "content": content}
        note_request = effect_intent._strip_request_envelope(evidence)
        desired = effect_intent._explicit_desire_request(note_request)
        if desired is not None:
            note_request = desired.group("body")
        shorthand = re.match(
            r"^[¿?¡!\s]*(?:"
            r"(?:anot[aá]|anotar|an[oó]tame|apunt[aá]|apuntar|ap[uú]ntame|note down|write down|jot down|"
            r"deja(?:r)?\s+(?:anotad[oa]|apuntad[oa]))\s*(?:(?:en una nota|in a note)\s*)?"
            r"(?:(?:que|that)\b|:|\s(?=[^\W\d_]+(?:ar|er|ir)\b))"
            # Twin of grammar._literal_note_payload_request (tanda 9 «apúntame una nota: …»).
            r"|(?:cre[aá]|crear|create|make|haz|hacer|guard[aá](?:me)?|guardar|"
            r"save|tom[aá](?:me)?|take|anot[aá]|anotar|an[oó]tame|apunt[aá]|apuntar|ap[uú]ntame|jot down)\s+"
            r"(?:(?:una?|a)\s+)?(?:nota|note)\s*"
            r"(?:(?:que\s+diga|that\s+says?|saying)\s*:?|:)"
            r"|(?:nota\s+nueva|nueva\s+nota|new\s+note)\s*:"
            r")\s*(?P<content>.+?)[\s.!?]*$",
            note_request,
            re.IGNORECASE,
        )
        if shorthand is not None:
            content = shorthand.group("content").strip()
            title = re.sub(
                r"^(?:tengo que|termine de|terminé de|i need to|i have to)\s+",
                "",
                content,
                count=1,
                flags=re.IGNORECASE,
            ).strip()
            if content and title and len(title.encode("utf-8")) <= 512:
                return {"title": title, "content": content}
        memo_content = effect_intent._literal_memo_payload(evidence)
        if memo_content is not None:
            content = clause_literal(memo_content)
            if content and len(content.encode("utf-8")) <= 512:
                return {"title": content, "content": content}

    if operation == "note.search" and effect_intent._historical_note_search_request(
        evidence
    ):
        query_match = re.search(
            r"\b(?:notas?|apuntes?)\s+(?P<query>.+?)"
            r"(?:\s+(?:del\s+)?pasado)?[\s.!?]*$",
            evidence,
            re.IGNORECASE,
        )
        if query_match is not None:
            query = clause_literal(query_match.group("query"))
            if query and len(query.encode("utf-8")) <= 512:
                return {"query": query}

    if operation == "note.search":
        stored_query = effect_intent._stored_note_search_query(evidence)
        if stored_query is not None:
            query = clause_literal(stored_query)
            if query and len(query.encode("utf-8")) <= 512:
                return {"query": query}

    if operation == "task.create" and (list_entry := effect_intent.list_entry_request(evidence)) is not None:
        # «añadir el brócoli a mi lista de la compra»: the entry is the title (its
        # article dropped) and the list it goes on is the details.
        entry, listed = list_entry
        title = re.sub(r"^(?:el|la|los|las|un|una|unos|unas|the|an?|some)\s+(?=\S)", "", entry, flags=re.IGNORECASE)
        return {"title": title, "details": listed}

    if (
        operation == "task.create"
        and (list_read := effect_intent.list_read_request(evidence)) is not None
        and list_read.absent_clause
        and list_read.entry
    ):
        # Tanda 4c «add flour to my shopping list if it's not already on it»: the add that waits on the read
        # puts the entry asked about on that list.
        return {"title": list_read.entry, "details": list_read.list_name}

    if operation == "task.search" and (list_read := effect_intent.list_read_request(evidence)) is not None:
        # «qué hay en mi lista de la compra» searches the list's name; «do i have
        # cheese on my shopping list» searches the entry asked about.
        return {"query": list_read.query} if list_read.query else None

    if operation == "task.create":
        task_pattern = (
            r"\b(?:tarea|task)(?:\s*:\s*|"
            r"\s+(?:llamad[oa]|titulad[oa]|named|called)\s+)"
            r"(?P<title>.+?)"
            r"(?:\s+(?:y|and)\s+(?:una?|an?)\s*)?[.!?]*$"
        )
        task = re.search(
            task_pattern,
            folded,
            re.IGNORECASE,
        )
        original_task = re.search(
            task_pattern,
            evidence,
            re.IGNORECASE,
        )
        if (
            task is not None
            and original_task is not None
            and original_task.group("title").strip()
        ):
            return {"title": clause_literal(original_task.group("title"))}
        alternate_task = re.search(
            (
                r"^[Â¿?Â¡!\s]*(?:crea|crear|create|agrega|agregar|add)\s+"
                r"(?P<title>.+?)\s+(?:como\s+(?:una?\s+)?tarea|"
                r"as\s+(?:a\s+)?task)[.!?]*$"
            ),
            evidence,
            re.IGNORECASE,
        )
        if alternate_task is not None:
            title = clause_literal(alternate_task.group("title"))
            if title:
                return {"title": title}

    if operation == "note.list":
        if numbers:
            return None
        scopes = {
            scope
            for scope, pattern in (
                ("all", r"\b(?:todas|todos|all)\b"),
                ("trashed", r"\b(?:papelera|eliminadas|trashed|deleted)\b"),
                ("active", r"\b(?:activas|active)\b"),
            )
            if re.search(pattern, folded)
        }
        return {"scope": next(iter(scopes))} if len(scopes) == 1 else {}

    if operation == "task.list":
        if numbers or re.search(r"\b(?:eliminadas|deleted|trashed)\b", folded):
            return None
        statuses = {
            status
            for status, pattern in (
                ("all", r"\b(?:todas|todos|all)\b"),
                ("completed", r"\b(?:completadas|terminadas|completed|done)\b"),
            )
            if re.search(pattern, folded)
        }
        return {"status": next(iter(statuses))} if len(statuses) == 1 else {}

    if operation == "system.process.list":
        return effect_intent.process_inventory_arguments(evidence)

    if operation == "reminder.create":
        relative_reminder = _explicit_relative_reminder_arguments(evidence)
        if relative_reminder is not None:
            return relative_reminder
        stated = stated_event_reminder(evidence)
        if stated is not None:
            return {"dueUtc": stated[1], "title": stated[0]}
        reminder = re.search(
            (
                r"\b(?:recordatorio|reminder)\s+"
                r"(?:llamad[oa]|titulad[oa]|named|called)\s+"
                r"(?P<title>.+?)(?=\s+(?:para|for)\s+"
                r"(?:manana|tomorrow)\b)"
            ),
            folded,
            re.IGNORECASE,
        )
        original_reminder = re.search(
            (
                r"\b(?:recordatorio|reminder)\s+"
                r"(?:llamad[oa]|titulad[oa]|named|called)\s+"
                r"(?P<title>.+?)(?=\s+(?:para|for)\s+"
                r"(?:mañana|manana|tomorrow)\b)"
            ),
            evidence,
            re.IGNORECASE,
        )
        clock = re.search(
            (
                r"\b(?:a las?|at)\s+(?P<hour>[0-2]?[0-9])"
                r"(?::(?P<minute>[0-5][0-9]))?\s*(?P<period>am|pm)?\b"
            ),
            folded,
            re.IGNORECASE,
        )
        if (
            reminder is not None
            and original_reminder is not None
            and clock is not None
            and re.search(r"\b(?:manana|tomorrow)\b", folded)
        ):
            hour = int(clock.group("hour"))
            minute = int(clock.group("minute") or "0")
            period = (clock.group("period") or "").casefold()
            if period and not 1 <= hour <= 12:
                return None
            if period == "am":
                hour %= 12
            elif period == "pm":
                hour = (hour % 12) + 12
            if not 0 <= hour <= 23:
                return None
            local_today = datetime.now().astimezone().date()
            local_due = datetime.combine(
                local_today + timedelta(days=1),
                datetime_time(hour, minute),
            )
            due_fold_zero = local_due.replace(fold=0).astimezone(timezone.utc)
            due_fold_one = local_due.replace(fold=1).astimezone(timezone.utc)
            if (
                due_fold_zero != due_fold_one
                or due_fold_zero.astimezone().replace(tzinfo=None) != local_due
            ):
                return None
            due_utc = (
                due_fold_zero.replace(microsecond=0).isoformat().replace("+00:00", "Z")
            )
            return {
                "title": original_reminder.group("title").strip(),
                "dueUtc": due_utc,
            }

    if operation == "notification.cancel.latest":
        # Tanda 7b «actually make it 9» → «cancel the last timer and …»: a timer is a scheduled alarm (419a7ddd), so
        # its kind is said by «timer» too; the plan asked «¿De qué tipo debe ser la alarma que se va a cancelar?».
        domain_kinds = {
            kind
            for kind, pattern in (
                ("alarm", r"\b(?:alarmas?|alarms?|temporizador(?:es)?|timers?)\b"),
                ("reminder", r"\b(?:recordatorios?|reminders?)\b"),
            )
            if re.search(pattern, folded)
        }
        return {"kind": next(iter(domain_kinds))} if len(domain_kinds) == 1 else None

    if operation == "notification.cancel.at":
        hour_words = {
            "cero": 0,
            "zero": 0,
            "una": 1,
            "uno": 1,
            "one": 1,
            "dos": 2,
            "two": 2,
            "tres": 3,
            "three": 3,
            "cuatro": 4,
            "four": 4,
            "cinco": 5,
            "five": 5,
            "seis": 6,
            "six": 6,
            "siete": 7,
            "seven": 7,
            "ocho": 8,
            "eight": 8,
            "nueve": 9,
            "nine": 9,
            "diez": 10,
            "ten": 10,
            "once": 11,
            "eleven": 11,
            "doce": 12,
            "twelve": 12,
        }
        clock_matches = list(
            re.finditer(
                (
                    r"\b(?P<hour>[0-2]?[0-9]|cero|zero|una|uno|one|dos|two|"
                    r"tres|three|cuatro|four|cinco|five|seis|six|siete|seven|"
                    r"ocho|eight|nueve|nine|diez|ten|once|eleven|doce|twelve)"
                    r"(?::(?P<minute>[0-5][0-9]))?\s*"
                    r"(?P<period>a\.?\s*m\.?|p\.?\s*m\.?|de la manana|"
                    r"de la tarde|de la noche|in the morning|in the afternoon|"
                    r"in the evening)?(?=\s|$|[,.?!])"
                ),
                folded,
                re.IGNORECASE,
            )
        )
        domain_kinds = {
            kind
            for kind, pattern in (
                ("alarm", r"\b(?:alarma|alarm)\b"),
                ("reminder", r"\b(?:recordatorio|reminder)\b"),
            )
            if re.search(pattern, folded)
        }
        if len(clock_matches) != 1 or len(domain_kinds) != 1:
            return None
        clock = clock_matches[0]
        hour_token = clock.group("hour")
        hour = int(hour_token) if hour_token.isdigit() else hour_words[hour_token]
        minute = int(clock.group("minute") or "0")
        raw_period = (clock.group("period") or "").replace(" ", "")
        if raw_period in {"am", "a.m."} or re.search(
            r"\b(?:de la manana|in the morning)\b",
            clock.group("period") or "",
        ):
            period = "am"
        elif raw_period in {"pm", "p.m."} or re.search(
            r"\b(?:de la tarde|de la noche|in the afternoon|in the evening)\b",
            clock.group("period") or "",
        ):
            period = "pm"
        else:
            period = None
        if not 0 <= hour <= 23 or period is not None and not 1 <= hour <= 12:
            return None
        arguments: dict[str, object] = {
            "hour": hour,
            "kind": next(iter(domain_kinds)),
        }
        if minute:
            arguments["minute"] = minute
        if period is not None:
            arguments["period"] = period
        return arguments

    if operation == "notification.schedule":
        repeated = agenda_event_request(evidence)
        if repeated is not None and repeated.repeat and not repeated.missing and repeated.timing.start is not None:
            # Uso real 2026-09-23 «poner el almuerzo todos los días a las doce y media»: the event
            # repeated daily is a repeating reminder of what was named, at the time said.
            return {
                "dueUtc": _clock_literal(repeated.timing.start),
                "kind": "reminder",
                "recurrence": repeated.repeat,
                "title": repeated.title,
            }
        # Uso real 2026-09-24 «recordarme que tengo que levantarme a las cinco de la mañana cada día»,
        # «despiértame todos los días a las siete»: the repetition said is scheduled, never dropped.
        repetition = said_repetition(evidence)
        if repetition == "unsupported":
            return None
        reminder = (
            _explicit_relative_reminder_arguments(" ".join(_REPETITION_WORDS.sub(" ", evidence).split()))
            if repetition is not None
            else None
        )
        if reminder is not None:
            return {**reminder, "kind": "reminder", "recurrence": repetition}
        alarm = _explicit_notification_schedule_arguments(evidence)
        return {**alarm, "recurrence": repetition} if alarm is not None and repetition is not None else alarm

    if operation == "audio.microphone.mute":
        # Owner's test 2026-09-21 (turn 205): «activa mi micrófono» was bound to
        # state=true through the radio grammar (activate = on) and muted an
        # already muted microphone, which then died as an unobserved effect.
        # For the microphone the state is «muted»: activating, enabling or
        # unmuting it is state=false; silencing, muting or turning it off is true.
        unmute_signal = bool(
            re.search(
                r"\b(?:activa|activá|reactiva|reactivá|enciende|encende|prende|prendé|habilita|habilitá|"
                r"desmutea|desmuteá|desilencia|dessilencia|unmute|enable|reactivate|activate|"
                r"turn\s+(?:it\s+)?(?:back\s+)?on)\w*\b",
                folded,
            )
        )
        mute_signal = bool(
            re.search(
                r"\b(?:mutea|muteá|silencia|silenciá|apaga|apagá|desactiva|desactivá|calla|callá|"
                r"deshabilita|deshabilitá|mute|silence|disable|turn\s+(?:it\s+)?off)\w*\b",
                folded,
            )
        )
        if mute_signal != unmute_signal:
            return {"state": mute_signal}

    if operation == "bluetooth.radio.set":
        false_signal = bool(
            re.search(
                r"\b(?:off|disable|desactiva|apaga|unmute|reactiva)\w*\b",
                folded,
            )
        )
        true_signal = bool(
            re.search(
                r"\b(?:on|enable|activa|enciende|encende|prende|mutea|silencia)\w*\b",
                folded,
            )
        )
        if true_signal != false_signal:
            return {"state": true_signal}

    if operation == "filesystem.file.open.latest":
        folders = {
            folder
            for folder, pattern in (
                ("desktop", r"\b(?:desktop|escritorio)\b"),
                ("documents", r"\b(?:documents|documentos)\b"),
                (
                    "downloads",
                    r"\b(?:downloads|downloaded|descargas|descargue|descargue)\b",
                ),
                ("pictures", r"\b(?:pictures|photos|imagenes|fotos)\b"),
            )
            if re.search(pattern, folded)
        }
        if len(folders) == 1:
            return {"folder": next(iter(folders))}

    if operation == "notification.list":
        if effect_intent._notification_listing_request(evidence):
            return {}

    if operation == "bluetooth.radio.status":
        if effect_intent._bluetooth_state_question(evidence):
            return {}

    if operation == "weather.current":
        if effect_intent._weather_lookup_query(evidence) is not None:
            return {"location": effect_intent._weather_location(evidence)}

    if operation in {"game.install.named", "game.uninstall.named"}:
        library_title = effect_intent.steam_library_title(evidence)
        library_verb = effect_intent.steam_library_verb(evidence)
        if library_title is not None and library_verb == ("uninstall" if operation == "game.uninstall.named" else "install"):
            # REOPEN1993 grupo S: the title as the person named it (the adapter
            # resolves it) and the store named after it.
            return {"title": library_title, "store": effect_intent.game_library_store(evidence)}
        if operation == "game.uninstall.named":
            software = effect_intent.software_package_request(evidence, application_names)
            if software is not None and software[0] == "uninstall" and not software[2]:
                installed = effect_intent._installed_game_named(software[1], game_catalog)
                if installed is not None:
                    return {"title": installed, "store": "steam"}

    if operation == "file.compress":
        compress = effect_intent.compress_named_request(evidence)
        if compress is not None:
            return {"folder": compress[0], "name": compress[1]}

    if operation == "file.open":
        opened = effect_intent.open_named_file_request(evidence)
        if opened is not None:
            return {"folder": opened[0], "name": opened[1]}

    if operation == "desktop.wallpaper.set":
        wallpaper = effect_intent.wallpaper_request(evidence)
        if wallpaper is not None:
            return dict(wallpaper)

    if operation == "web.download":
        download = effect_intent.web_download_request(evidence)
        if download is not None:
            return {"url": download["url"], "folder": download["folder"], "name": download["name"], "query": None}
        image = effect_intent.web_image_request(evidence)
        if image is not None and not image[1]:
            # REOPEN1957 H0069: the picture lands in Pictures under the noun asked.
            return {"url": None, "query": image[0], "folder": "pictures", "name": effect_intent.visual_content_noun(evidence) or "imagen"}

    if operation == "shell.command.run":
        shell = effect_intent.shell_command_request(evidence)
        if shell is not None:
            return {"command": shell[0], "cwd": shell[1]}

    if operation in {"package.install.prepare", "package.uninstall"}:
        software = effect_intent.software_package_request(evidence, application_names)
        if software is not None and (
            (operation == "package.uninstall") == (software[0] == "uninstall")
        ):
            # REOPEN1993 grupo G: the package is the name as the person wrote
            # it (or the catalog name when the catalog holds it); winget
            # resolves the exact id.
            return {"packageId": software[1]} if operation == "package.uninstall" else {"packageId": software[1], "version": None}

    if operation == "web.news.headlines":
        if effect_intent._news_headlines_request(evidence):
            return {"topic": effect_intent._news_topic(evidence), "limit": 5}

    if operation == "display.status":
        if effect_intent._display_status_question(evidence):
            return {}

    if operation == "software.python.status":
        if effect_intent._python_status_question(evidence):
            return {}

    if operation == "wifi.scan":
        if effect_intent._wifi_scan_question(evidence) or effect_intent._accepted_wifi_offer_evidence(evidence):
            return {}

    if operation == "wifi.radio.set":
        # NETWORK1737: the desired state comes from the order («prendé» / «apagá»)
        # or from the accepted offer to turn the radio on and scan.
        desired = effect_intent.wifi_radio_set_request(evidence)
        if desired is None and effect_intent._accepted_wifi_offer_evidence(evidence):
            desired = True
        return {"state": desired} if desired is not None else None

    if operation == "calculator.expression.evaluate":
        expression = effect_intent.calculator_expression_request(evidence)
        return {"expression": expression} if expression is not None else None

    if operation == "filesystem.known.list":
        recent_listing = effect_intent._known_folder_recent_listing(evidence)
        if recent_listing is not None:
            return {"folder": recent_listing[0], "limit": recent_listing[1], "order": "recent"}
        listed_folder = effect_intent._known_folder_listing_request(evidence)
        if listed_folder is not None:
            return {"folder": listed_folder, "limit": 100}

    if operation == "filesystem.known.search":
        literal_search = effect_intent._literal_known_file_search(evidence)
        if literal_search is not None:
            return literal_search
        query_match = re.search(
            r"\b(?:palabra|word)\s+[\"'“”‘’«»]?(?P<query>[^\"'“”‘’«».,;!?]+)",
            evidence,
            re.IGNORECASE,
        )
        if query_match is not None:
            query = query_match.group("query").strip()
            if query:
                return {"folder": "all_known", "query": query}

    if operation == "audio.volume":
        if (
            not effect_intent._volume_domain(folded)
            or effect_intent._is_negative_effect_clause(folded)
            or effect_intent._is_meta_or_tool_denial(folded)
        ):
            return None
        word_level = effect_intent._literal_percentage_word_value(folded)
        if word_level is not None:
            if numbers:
                return None
            return {"level": word_level}
        if len(numbers) != 1 or not 0 <= numbers[0] <= 100:
            return None
        level = re.search(
            (
                rf"\b{effect_intent._VOLUME_OBJECT}\b\s+"
                r"(?:a(?:l)?|en|to|at)\s*"
                r"(?P<level>100|[0-9]{1,2})(?![0-9])"
                r"(?:\s*(?:%|por\s+ciento|percent))?"
            ),
            folded,
        )
        if level is None:
            # The closed contextual reader retains the two authored surfaces
            # with a sentence boundary. Reprove that the earlier surface has
            # only a missing level and the answer is one numeric clause; a
            # nearby number, another object or an additional effect is not a
            # literal level for this step.
            prior, separator, answer = folded.rpartition(" . ")
            if (
                separator
                and len(effect_intent._request_clauses(answer)) == 1
                and effect_intent._completed_missing_volume_level_request(
                    answer, prior, ("audio.volume",),
                ) is not None
            ):
                return {"level": numbers[0]}
        if level is None or int(level.group("level")) != numbers[0]:
            return None
        return {"level": numbers[0]}

    if operation == "audio.volume.adjust":
        return effect_intent._literal_volume_adjustment(folded)

    if operation == "audio.app.volume.adjust":
        # AUDIO1787: the application, direction and amount are the person's literal.
        app_volume = effect_intent.app_volume_request(evidence, application_names)
        if app_volume is None or app_volume[2] is None:
            return None
        return {"app": app_volume[0], "amount": app_volume[2], "direction": app_volume[1]}

    if operation == "audio.app.volume.set":
        # Fase 8 (D18): the application and its absolute level are the person's literal.
        app_level = effect_intent.app_volume_set_request(evidence, application_names)
        if app_level is None:
            return None
        return {"app": app_level[0], "level": app_level[1]}

    if operation == "audio.mute":
        false_pattern = (
            rf"\b(?:{effect_intent._UNMUTE_VERB}|reactiva|reactivar)\b|"
            # Fase 3.5 (held-out turn 9 «devolvele el sonido»), uso real 2026-09-23 («vuelve el sonido»,
            # «Turn off silenciar»), tanda 4 («Enciende el sound»): the reader takes the sound coming back,
            # the mute switched off and the sound switched on from the shared lexicon; so does the argument.
            rf"\b(?:{semantic_lexicon.UNMUTE_WORDS})\b"
        )
        false_signal = bool(re.search(false_pattern, folded))
        # The noun ``mute`` inside "quita el mute" is evidence for the
        # unmute action, not a second request to enable mute. Remove complete
        # negative phrases before looking for an independent positive cue;
        # "mute and unmute" still retains the first cue and therefore remains
        # safely ambiguous.
        positive_surface = re.sub(false_pattern, " ", folded)
        true_signal = bool(
            # Tanda 5: «mutea el pc» is read by the same verbs as the reader (audio._MUTE_VERB).
            re.search(r"\b(?:mute|mutea|mutear|muteame|silencia|silenciar|silenciame)\b", positive_surface)
            or re.search(rf"\b{effect_intent._MUTE_PREDICATIVE_VERB}\b", positive_surface)
            or re.search(rf"\b(?:{semantic_lexicon.MUTE_WORDS})\b", positive_surface)
            or re.search(semantic_lexicon.BARE_SILENCE, positive_surface)
            or re.search(
                r"\b(?:pon(?:e|lo|elo|le|eme)?|ponlo|poner|deja(?:lo)?|dejar|leave|put)\b[^.;!?]{0,48}"
                r"\b(?:en|on)\s+(?:mute|mudo|silencio)\b",
                positive_surface,
            )
            or re.fullmatch(
                r"(?:de\s+ahora\s+en\s+adelante|from\s+now\s+on)\s+"
                r"(?:en\s+)?(?:mudo|mute|silent|silencio)[\s.!?]*",
                positive_surface,
                re.IGNORECASE,
            )
        )
        if true_signal == false_signal:
            return None
        return {"state": true_signal}

    return None


def _fully_enumerated_note_create_arguments(
    objective: str,
) -> tuple[dict[str, str], ...]:
    """Extract every exact title/content pair from one complete note list."""

    requested_order = effect_intent.enumerated_note_dependency_order(objective)
    if not requested_order:
        return ()
    compact = " ".join(objective.split())
    header = re.search(
        r"\b(?:dos|two|tres|three|cuatro|four|cinco|five|seis|six|"
        r"siete|seven|ocho|eight|[2-8])\s+"
        r"(?:(?:private|local|privadas?|locales?)\s+)?(?:notas|notes)\s*:\s*",
        compact,
        re.IGNORECASE,
    )
    if header is None:
        return ()
    create_body = compact[header.end() :]
    boundary = re.search(
        r"[.!?]\s*(?:despu[eé]s|after)\b",
        create_body,
        re.IGNORECASE,
    )
    if boundary is not None:
        create_body = create_body[: boundary.start()]
    content_marker = (
        r"(?:con\s+(?:el\s+)?(?:contenido|texto)|"
        r"with\s+(?:the\s+)?content)"
    )
    item_pattern = re.compile(
        rf"(?:^|,\s*|\s+(?:y|and)\s+)"
        rf"(?P<title>[^,;]{{1,120}}?)\s+{content_marker}\s+"
        rf"(?P<content>.+?)"
        rf"(?=(?:,\s*|\s+(?:y|and)\s+)[^,;]{{1,120}}?\s+"
        rf"{content_marker}\s+|$)",
        re.IGNORECASE,
    )
    ordinal_prefix = re.compile(
        r"^(?:(?:la|el|the)\s+)?(?:primera|primer|first|segunda|second|"
        r"tercera|tercer|third|cuarta|cuarto|fourth|quinta|quinto|fifth|"
        r"sexta|sexto|sixth|septima|septimo|seventh|octava|octavo|eighth)\s+"
        r"(?:titulada|titulado|llamada|llamado|titled|named|called)\s+",
        re.IGNORECASE,
    )
    arguments: list[dict[str, str]] = []
    for found in item_pattern.finditer(create_body):
        title = ordinal_prefix.sub("", found.group("title")).strip(" ,.;:")
        content = found.group("content").strip(" ,.;:")
        if (
            not title
            or not content
            or len(title.encode("utf-8")) > 512
            or len(content.encode("utf-8")) > 512
        ):
            return ()
        arguments.append({"title": title, "content": content})
    if len(arguments) != len(requested_order) or len(
        {item["title"].casefold() for item in arguments}
    ) != len(arguments):
        return ()
    return tuple(arguments)


def _canonical_due_utc(
    value: str,
    context: str = "",
    *,
    now_utc: datetime | None = None,
) -> str | None:
    """Convert one exact natural clock literal to an unambiguous future UTC."""

    if not isinstance(value, str) or not value.strip():
        return None
    now = now_utc or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("now_utc must carry timezone authority")
    now = now.astimezone(timezone.utc)
    raw = value.strip()
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        parsed = None
    if parsed is not None and parsed.tzinfo is not None:
        parsed_utc = parsed.astimezone(timezone.utc)
        if parsed_utc > now + timedelta(seconds=5):
            return parsed_utc.isoformat().replace("+00:00", "Z")
        return None

    folded_value = effect_intent._fold(raw)
    relative = re.fullmatch(
        rf"(?:(?:en|in|dentro de|within)\s+)?"
        r"(?:(?P<half>media\s+hora|half\s+an?\s+hour)|"
        rf"(?P<number>{_TEMPORAL_NUMBER_PATTERN})\s*"
        rf"(?P<unit>{effect_intent._RELATIVE_DURATION_UNIT}))"
        r"(?:\s+(?:from now|desde ahora))?",
        folded_value,
        re.IGNORECASE,
    )
    if relative is not None:
        if relative.group("half"):
            amount, unit = 30, "minutes"
        else:
            amount = _temporal_number(relative.group("number"))
            unit = relative.group("unit")
        if amount is None or not 1 <= amount <= 24 * 60:
            return None
        if unit.startswith(("day", "dia")):
            if amount > 365:
                return None
            delta = timedelta(days=amount)
        elif unit.startswith(("hour", "hora", "h")):
            delta = timedelta(hours=amount)
        else:
            delta = timedelta(minutes=amount)
        due = now + delta
        if due.microsecond:
            # The Windows Task Scheduler registers whole seconds only (TIME1139
            # probes: StartBoundary and NextRunTime lose fractions by cmdlet and
            # by XML). Publish the second the task will actually carry, never
            # earlier than the requested moment (owner decision 2026-09-13).
            due = due.replace(microsecond=0) + timedelta(seconds=1)
        return due.isoformat().replace("+00:00", "Z")

    folded_context = effect_intent._fold(context)
    # The literal comes first, so its clock is the one read; its part of the
    # day may be said elsewhere in the request («esta tarde a las cinco»).
    clock_source = f"{folded_value} {folded_context}".strip().replace("maniana", "manana")
    clock = effect_intent.spoken_clock(clock_source)
    if clock is None or not clock.resolved:
        return None
    hour, minute = clock.hour, clock.minute
    local_now = (
        datetime.now().astimezone()
        if now_utc is None
        else now.astimezone(now_utc.tzinfo)
    )
    # One date reader for every request (semantic.temporal.spoken_date): «el 4 de julio»,
    # «el cuatro de febrero», «march seven», «el veintiuno».
    said_date = spoken_date(clock_source)
    spoken_day = effect_intent.spoken_day(clock_source, local_now.weekday())
    if said_date is not None and spoken_day != (0, 1):
        # A date and another day word («mañana», «el lunes») disagree on the day.
        return None

    def materialize_date(local_date: date) -> datetime | None:
        naive = datetime.combine(local_date, datetime_time(hour, minute))
        if now_utc is None:
            fold_zero = naive.replace(fold=0).astimezone(timezone.utc)
            fold_one = naive.replace(fold=1).astimezone(timezone.utc)
            round_trip = fold_zero.astimezone().replace(tzinfo=None)
        else:
            local_zone = local_now.tzinfo
            if local_zone is None:
                return None
            fold_zero = naive.replace(tzinfo=local_zone, fold=0).astimezone(
                timezone.utc
            )
            fold_one = naive.replace(tzinfo=local_zone, fold=1).astimezone(timezone.utc)
            round_trip = fold_zero.astimezone(local_zone).replace(tzinfo=None)
        if fold_zero != fold_one or round_trip != naive:
            return None
        return fold_zero.replace(microsecond=0)

    if said_date is not None:
        first = said_date.on_or_after(local_now.date())
        due = materialize_date(first) if first is not None else None
        if (
            first is not None
            and (due is None or due <= now + timedelta(seconds=5))
            and said_date.year is None
            and not said_date.this_year
        ):
            # A date said without its year is the next one whose moment is still ahead.
            later = said_date.on_or_after(first + timedelta(days=1))
            due = materialize_date(later) if later is not None else None
        if due is None or due <= now + timedelta(seconds=5):
            return None
        return due.isoformat().replace("+00:00", "Z")

    if spoken_day is None:
        # «esta semana», «el lunes y el martes»: no one date holds the moment.
        return None
    days, roll = spoken_day

    def materialize(day_offset: int) -> datetime | None:
        return materialize_date(local_now.date() + timedelta(days=day_offset))

    due = materialize(days)
    if due is None:
        return None
    if roll and due <= now + timedelta(seconds=5):
        due = materialize(days + roll)
    if due is None or due <= now + timedelta(seconds=5):
        return None
    return due.isoformat().replace("+00:00", "Z")


def _select_referenced_predecessor(
    candidate_indexes: list[int],
    evidence: str,
) -> int:
    """Resolve bounded ordinal coreference; otherwise prefer the latest result."""

    folded = effect_intent._fold(evidence)
    if re.search(
        r"\b(?:(?:la|the)\s+)?(?:primera|primer|first)\s+"
        r"(?:nota|note|documento|document|resultado|result|una|one)\b",
        folded,
    ):
        return candidate_indexes[0]
    if len(candidate_indexes) >= 2 and re.search(
        r"\b(?:(?:la|the)\s+)?(?:segunda|segundo|second)\s+"
        r"(?:nota|note|documento|document|resultado|result|una|one)\b",
        folded,
    ):
        return candidate_indexes[1]
    if re.search(
        r"\b(?:(?:la|the)\s+)?(?:ultima|ultimo|last|latest)\s+"
        r"(?:nota|note|documento|document|resultado|result|una|one)\b",
        folded,
    ):
        return candidate_indexes[-1]
    return candidate_indexes[-1]


def literal_ocr_language(objective: str) -> str | None:
    """The OCR language the person spelled literally («idioma literal "spa"», «exact language eng»), or None."""

    language = re.search(
        r"\b(?:idioma|language)\s+(?:literal(?:mente)?|exact(?:o|a|ly)?)\s+"
        r"[\"'\u201c\u201d]?([a-z][a-z0-9-]{1,31})[\"'\u201c\u201d]?",
        objective,
        re.IGNORECASE,
    )
    return language.group(1) if language is not None else None


def literal_vision_prompt(objective: str) -> str | None:
    """The exact quoted prompt the person gave for describing the screen, or None."""

    prompt = re.search(
        r"\b(?:prompt\s+exact[oa]|exact\s+prompt)\s*"
        r"[\"\u201c]([^\"\u201d]{1,2000})[\"\u201d]",
        objective,
        re.IGNORECASE,
    )
    return prompt.group(1) if prompt is not None else None


def reminder_title_without_que(title: str) -> str:
    """A reminder title said as «que …» / «that …» is the task itself: «que llame a mamá» → «llame a mamá»."""

    return re.sub(
        r"^\s*(?:que|that)\s+",
        "",
        title,
        count=1,
        flags=re.IGNORECASE,
    ).strip()


def names_spotify(clause: str) -> bool:
    """The clause names Spotify (a control after ``media.play.exact`` keeps that player)."""

    return re.search(r"\bspotify\b", clause, re.IGNORECASE) is not None


def closes_the_active_window(clause: str) -> bool:
    """«cierra la ventana activa», «close it», «cerralo»: the close acts on the active window, read first."""

    return bool(
        re.search(
            r"\b(?:activa|active|actual|current|cierralo|cierrala|"
            r"close it|cerrala|cerralo)\b",
            effect_intent._fold(clause),
        )
        or effect_intent.deictic_close_request(
            effect_intent._strip_request_envelope(effect_intent._fold(clause))
        )
    )
