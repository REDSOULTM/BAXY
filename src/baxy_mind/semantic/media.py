"""Media: play on YouTube, Spotify, Netflix, Disney+, music in a named browser, playback control. Readers moved from effect_intent (Fase 3.5).
"""

from __future__ import annotations

import re
from .grammar import _fold, _has, _strip_request_envelope, _request_head, _head_is, _KNOWN_APPLICATION, _MEDIA_RESUME_VERB, _PERCENTAGE_WORD_VALUES


_YOUTUBE_SEARCH = re.compile(
    r"^[¿?¡!\s]*(?:busca|buscá|buscar|buscame|buscáme|búscame|search(?:\s+for)?|find)\s+"
    r"(?:(?P<query>.+?)\s+(?:en|on)\s+youtube|(?:en|on)\s+youtube\s+(?P<query_after>.+?))\s*[.!?]*$",
    re.IGNORECASE,
)


def _youtube_search_query(text: str) -> str | None:
    """WEB1481 «buscá videos de gatos en youtube»: a search on YouTube is one
    reviewed navigation to YouTube's results page with the person's query,
    kept with its own spelling; None for any other shape, a playback request
    («reproduce … en youtube») or a query that names a local thing."""

    match = _YOUTUBE_SEARCH.match(text.strip())
    if match is None:
        return None
    query = (match.group("query") or match.group("query_after") or "").strip().strip("\"'“”«»").strip()
    folded_query = _fold(query)
    if (
        not query
        or len(query.encode("utf-8")) > 512
        or any(ord(character) < 32 for character in query)
        or _has(folded_query, r"\b(?:archivos?|files?|carpetas?|folders?|notas?|notes?|documentos?|documents?|mi\s+pc|my\s+pc|este\s+equipo)\b")
    ):
        return None
    return query


_YOUTUBE_PLAY = re.compile(
    r"^[¿?¡!\s]*(?:(?:por favor|please)\s*[,;:]?\s*)?"
    r"(?:pon|poné|pone|ponme|poneme|reproduce|reproducí|reproduci|reproducime|play|put on)\s+"
    r"(?:(?P<query>.+?)\s+(?:en|on|in|de|from)\s+youtube|(?:en|on|in)\s+youtube\s+(?P<query_after>.+?))"
    r"(?:\s*[,;:]?\s+(?:por favor|please|porfa|porfi|pls|plz|dale|ahora|now))?\s*[.!?]*$",
    re.IGNORECASE,
)


def youtube_play_query(text: str) -> str | None:
    """MUSIC1553 «pon un video de lofi en youtube», «pon una cancion de michael
    jackson en youtube»: the thing to play, in the person's own words with only
    a leading article dropped («video de lofi», «cancion de michael jackson»),
    as the search query for the local YouTube playback; None for any other shape,
    for a generic «pon youtube» and for a query that names a local thing."""

    match = _YOUTUBE_PLAY.match(text.strip())
    if match is None:
        return None
    query = (match.group("query") or match.group("query_after") or "").strip().strip("\"'“”«»").strip()
    query = re.sub(
        r"^(?:un|una|el|la|algun|alguna|algún|some|a|an|the)\s+(?=\S)",
        "",
        query,
        count=1,
        flags=re.IGNORECASE,
    ).strip()
    folded_query = _fold(query)
    if (
        not query
        or len(query.encode("utf-8")) > 512
        or any(ord(character) < 32 for character in query)
        or re.fullmatch(r"(?:algo|something|musica|music|videos?|a\s+video|cancion(?:es)?|songs?|temas?|un\s+tema)", folded_query)
        or _has(folded_query, r"\b(?:archivos?|files?|carpetas?|folders?|notas?|notes?|documentos?|documents?|mi\s+pc|my\s+pc|este\s+equipo)\b")
    ):
        return None
    return query


def _direct_media_discovery_or_play_request(folded: str) -> bool:
    """Recognize one requested audio title or bounded audio discovery query."""

    direct_listen = (
        re.fullmatch(
            r"i\s+(?:want|would\s+like)\s+to\s+(?:listen\s+to|hear)\s+"
            r"\S(?:.{0,180}?\S)?[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    rated_audio_discovery = (
        re.fullmatch(
            r"(?:show|find|recommend)(?:\s+me)?\s+(?:the\s+)?(?:best|top)\s+"
            r"(?:podcasts?|albums?|songs?|playlists?)\b\S?.{0,180}"
            r"(?:rating|rated|reviews?|good|popular)\b.{0,48}[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    return (direct_listen or rated_audio_discovery) and not _has(
        folded,
        r"\b(?:with|against|conmigo|contra\s+mi|juego|game|"
        r"jokes?|chistes?)\b",
    )


_MUSIC_BROWSER = r"(?:opera gx|opera|google chrome|chrome|microsoft edge|edge|brave)"


_MUSIC_PLAY_HEAD = r"(?:pone|poneme|pon|ponme|reproduci|reproduce|play|toca|tocame)"


_MUSIC_BROWSER_REQUEST = (
    re.compile(
        rf"^(?:abri|abre|abrime|open)\s+(?:el\s+|the\s+)?(?P<b>{_MUSIC_BROWSER})\s+(?:y|and)\s+{_MUSIC_PLAY_HEAD}\s+(?P<q>.+)$"
    ),
    re.compile(
        rf"^{_MUSIC_PLAY_HEAD}\s+(?P<q>.+?)\s+(?:en|in|usando|using|with|con)\s+(?:el\s+|the\s+)?(?P<b>{_MUSIC_BROWSER})$"
    ),
)


def _named_browser_music_request(text: str) -> tuple[str, str | None] | None:
    """MUSIC1827 «abrí chrome y poné música», «pon música de rock en chrome», «open
    Edge and play some music»: music asked of a named browser. Returns the
    browser and the music named (None when only «música» was said)."""

    folded = _strip_request_envelope(_fold(text)).strip(" .!?¿¡")
    match = next((m for m in (p.match(folded) for p in _MUSIC_BROWSER_REQUEST) if m is not None), None)
    if match is None:
        return None
    browser = {"opera gx": "opera_gx", "google chrome": "chrome", "microsoft edge": "edge"}.get(match.group("b"), match.group("b"))
    query = re.sub(r"^(?:algo\s+de\s+|un\s+poco\s+de\s+|some\s+|something\s+)", "", match.group("q").strip())
    if re.fullmatch(r"(?:musica|music|una\s+cancion|a\s+song|canciones|songs|algo|something)", query):
        return browser, None
    query = re.sub(r"^(?:musica\s+de|music\s+(?:by|of|from)|una\s+cancion\s+de|a\s+song\s+by)\s+", "", query).strip()
    if not query or len(query.encode("utf-8")) > 200 or "?" in query:
        return None
    return browser, query


# VIDEO1921 H0737: el nombre del servicio se escribe mal —o lo escribe mal el
# oído de BAXY, que es lo más probable— y eso no lo convierte en otro servicio.
# Alternancia corta y cerrada, no distancia de edición: el catálogo de servicios
# es cerrado y una tolerancia genérica leería «Netflix» donde se dijo otra cosa.
# VIDEO1947: Disney+ joins the closed streaming catalog; the same short, closed
# alternation of misspellings (the owner's ear, not another service).
_NETFLIX_SPELLED = (
    r"(?:netflix|nerflix|netlix|netfix|netflis|neflix|"
    r"disney\s*\+|disney\s*plus|disneyplus|disney|dysney|disne|dinsey|dizney|east\s*plus)"
)


def _underspecified_video_request(text: str) -> bool:
    """Recognize a bare content type with no source, title, or query."""

    return (
        re.fullmatch(
            (
                r"[¿?¡!\s]*(?:pon|pone|reproduce|play|put\s+on)\s+"
                r"(?:(?:un|uno|unos|el|los|the|some)\s+)?videos?[\s.!?]*"
            ),
            _fold(text),
            re.IGNORECASE,
        )
        is not None
    )


def _title_case_media_title(query: str) -> bool:
    """«Tom and Jerry», «Tom y Jerry», «Bad Bunny»: at least two capitalised
    words in the person's own writing, joined only by connectors; never a
    single word, a known application name or something with digits."""

    words = query.strip().strip("\"'“”«»").split()
    if len(words) < 2 or any(re.search(r"\d", word) for word in words):
        return False
    connectors = {"y", "and", "&", "the", "of", "de", "del", "la", "el", "los", "las", "a", "en", "in"}
    capitalised = [word for word in words if word[0].isupper()]
    if len(capitalised) < 2 or not words[0][0].isupper():
        return False
    if any(word[0].islower() and word.lower() not in connectors for word in words):
        return False
    if _has(_fold(query), rf"^(?:{_KNOWN_APPLICATION})$"):
        return False
    return True


def _media_transport_action(text: str) -> str | None:
    """Read one transport action from a complete request with an explicit media object."""

    folded = _fold(text)
    if not _request_head(folded):
        return None
    if _has(
        folded,
        r"^[^\w]*(?:(?:por favor|please)\s*[,;:]?\s*)?"
        r"(?:deten(?:e|er)?|para|parar|stop)\s+(?:(?:el|la|the)\s+)?"
        r"(?:current\s+)?(?:audio|musica|music|reproduccion|playback|cancion|song|pista|track)"
        r"(?:\s+actual)?(?:\s*[,;:]?\s*(?:por favor|please))?[\s.!?]*$",
    ):
        return "stop"
    media_object = r"(?:podcast|episodio|episode|cancion|song|pista|track)"
    for action, direction, movement, relative in (
        ("next", r"(?:siguiente|next)",
         r"(?:skip(?:\s+forward)?|salta|saltar|saltea|saltear|pasa|pasar)",
         r"(?:viene|sigue)"),
        ("previous", r"(?:anterior|previous)",
         r"(?:skip(?:\s+back)?|go\s+back|ve|vuelve|pasa|pasar)",
         r"(?:iba|estaba)\s+antes"),
    ):
        nominal = (
            rf"(?:(?:el|la|the)\s+)?(?:{direction}\s+{media_object}|"
            rf"{media_object}\s+{direction})"
        )
        step_direction = "forward" if action == "next" else "back"
        destination = rf"(?:{nominal}|(?:el|la)\s+{media_object}\s+que\s+{relative})"
        if _has(
            folded,
            r"^[^\w]*(?:(?:por favor|please)\s*[,;:]?\s*)?"
            rf"(?:(?:(?:pon|pone|ponme|reproduce|reproducir|play)\s+)?{nominal}|"
            rf"{movement}\s+(?:(?:to|a)\s+{destination}|al\s+"
            rf"(?:{direction}\s+{media_object}|{media_object}\s+que\s+{relative}))|"
            rf"(?:go|skip)\s+{step_direction}\s+one\s+{media_object}"
            r"(?:\s+in\s+(?:the\s+)?(?:current\s+)?queue)?)"
            r"(?:\s*[,;:]?\s*(?:por favor|please))?[\s.!?]*$",
        ):
            return action
    return None


def _resume_existing_media(text: str) -> bool:
    """Distinguish continuation of loaded media from selecting new content."""

    folded = _fold(text)
    head = _request_head(folded)
    return (
        _head_is(head, rf"(?:{_MEDIA_RESUME_VERB}|reproduce|reproducir|reproduzca|play)")
        and (
            _head_is(head, _MEDIA_RESUME_VERB)
            or _has(folded, r"\b(?:pausad[oa]|paused|en\s+pausa|detenid[oa]|stopped)\b")
        )
        and _has(
            folded,
            # Fase 3.5 (layer C «resume the video»): a video, film or series session resumes the same way.
            r"\b(?:audio|media|musica|music|reproduccion|playback|cancion|song|pista|track|video|videos|peli|pelicula|serie|episodio|capitulo|movie)\b",
        )
        and not _has(folded, r"\b(?:grabacion|recording|microfono|microphone|mic)\b")
    )


_REMOVABLE_MEDIA = (
    r"(?:pendrive|pen\s+drive|pen|usb|memoria\s+usb|memoria\s+externa|disco\s+externo|disco\s+usb|"
    r"unidad\s+externa|unidad\s+usb|usb\s+stick|flash\s+drive|thumb\s+drive|external\s+(?:drive|disk)|"
    r"removable\s+(?:drive|disk)|memory\s+stick)"
)


def _bare_spoken_number_media_query(text: str) -> str | None:
    """Preserve a word-valued media title without inventing volume context."""

    folded = _strip_request_envelope(_fold(text))
    match = re.fullmatch(
        r"(?:pon|ponme|pone|poneme|reproduce|reproducir|play)\s+"
        r"(?P<query>[a-z]+(?:\s+(?:y\s+)?[a-z]+)?)"
        r"(?:\s+(?:por favor|please))?[\s.!?]*",
        folded,
        re.IGNORECASE,
    )
    if match is None:
        return None
    query = match.group("query").strip()
    return query if query in _PERCENTAGE_WORD_VALUES else None
