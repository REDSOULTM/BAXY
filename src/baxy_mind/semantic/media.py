"""Media: play on YouTube, Spotify, Netflix, Disney+, music in a named browser, playback control. Readers moved from effect_intent (Fase 3.5).
"""

from __future__ import annotations

import re
from .grammar import (
    _fold, _has, _original_clause, _strip_request_envelope, _request_head, _head_is, _KNOWN_APPLICATION, _MEDIA_RESUME_VERB,
    _PERCENTAGE_WORD_VALUES,
)


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
    media_object = r"(?:podcast|episodio|episode|cancion|song|pista|track|tema)"
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
            rf"(?:(?:(?:pon|pone|ponme|reproduce|reproducir|play|toca|tocame)\s+)?{nominal}|"
            rf"{movement}\s+(?:(?:to|a)\s+{destination}|al\s+"
            rf"(?:{direction}\s+{media_object}|{media_object}\s+que\s+{relative}))|"
            rf"(?:go|skip)\s+{step_direction}\s+one\s+{media_object}"
            r"(?:\s+in\s+(?:the\s+)?(?:current\s+)?queue)?)"
            r"(?:\s*[,;:]?\s*(?:por favor|please))?[\s.!?]*$",
        ):
            return action
    return None


# Tanda 4c 2026-09-24 «pon cualquier cosa de mi playlist reciente» was asked what to play: what the person played
# last is their player's own session, and playing it is resuming that session (no operation opens their
# playlists; a search would find someone else's music).
_OWN_RECENT_LISTENING = (
    r"\b(?:(?:mi|mis)\s+(?:\S+\s+){0,2}?(?:playlists?|listas?|musica|canciones|temas|mix)\b(?:\s+\S+){0,3}?\s+"
    r"(?:recientes?|ultim[oa]s?)|"
    r"(?:mi|mis)\s+(?:ultim[oa]s?|recientes?)\s+(?:canciones|temas|playlists?|listas?|mix)|"
    r"(?:my\s+)?(?:recently|last)\s+played|my\s+(?:most\s+)?(?:recent|latest|last)\s+(?:playlists?|music|songs|tracks|mix)|"
    r"lo\s+(?:ultimo\s+)?que\s+(?:(?:estaba|estuve|he\s+estado)\s+)?(?:escuchando|escuche|oi|puse)|"
    r"what\s+i\s+(?:was\s+(?:listening\s+to|playing)|listened\s+to\s+last|last\s+(?:listened\s+to|played)|"
    r"played\s+last))\b"
)
_OWN_LISTENING_PLAY_HEAD = (
    r"(?:pon|pone|ponme|poneme|reproduce|reproducir|reproduci|reproducime|reproduzca|play|toca|tocame|put|start)"
)


def own_recent_listening_request(text: str) -> bool:
    """«pon mi playlist reciente», «play what I was listening to», «pon lo último que escuché»: the person's own
    recent listening asked to play, which resumes their player."""

    folded = _strip_request_envelope(_fold(text)).strip(" .!?¿¡")
    return _head_is(_request_head(folded), _OWN_LISTENING_PLAY_HEAD) and _has(folded, _OWN_RECENT_LISTENING)


def _resume_existing_media(text: str) -> bool:
    """Distinguish continuation of loaded media from selecting new content."""

    folded = _fold(text)
    head = _request_head(folded)
    if own_recent_listening_request(folded):
        return True
    return (
        _head_is(head, rf"(?:{_MEDIA_RESUME_VERB}|reproduce|reproducir|reproduzca|play)")
        and (
            _head_is(head, _MEDIA_RESUME_VERB)
            or _has(folded, r"\b(?:pausad[oa]|paused|en\s+pausa|detenid[oa]|stopped)\b")
        )
        and _has(
            folded,
            # Fase 3.5 (layer C «resume the video»): a video, film or series session resumes the same way.
            # Uso real 2026-09-24 «resume last played audiobook»: a podcast or an audiobook resumes the same way.
            r"\b(?:audio|media|musica|music|reproduccion|playback|cancion|song|pista|track|video|videos|peli|pelicula|serie|episodio|capitulo|movie|"
            r"episode|podcast|audiobook|audiolibro)\b",
        )
        and not _has(folded, r"\b(?:grabacion|recording|microfono|microphone|mic)\b")
    )


_REMOVABLE_MEDIA = (
    r"(?:pendrive|pen\s+drive|pen|usb|memoria\s+usb|memoria\s+externa|disco\s+externo|disco\s+usb|"
    r"unidad\s+externa|unidad\s+usb|usb\s+stick|flash\s+drive|thumb\s+drive|external\s+(?:drive|disk)|"
    r"removable\s+(?:drive|disk)|memory\s+stick)"
)


# Uso real tanda 2 (2026-09-23): a radio station is something to play. «pon kiss f. m. para mi», «qué música está
# poniendo actualmente novecientos noventa y nueve f. m.», «tune in to eight hundred and ninety seven f. m.»,
# «pon radio cooperativa»: the station, by its name or its dial with the band, plays in the local player; asking
# what it plays now is answered by playing it (the second went to a web search of the sentence). A dial said in
# words is the dial written in digits («novecientos noventa y nueve» → 99.9).
_RADIO_BAND = r"(?P<band>f\s*\.?\s*m|a\s*\.?\s*m)\.?"
# Uso real 2026-09-24 «toca bbc radio uno», «enciende el emisora novecientos cincuenta y uno», «abre los cuarenta
# estación rock»: a station is played by any verb that plays or switches on a radio.
_RADIO_PLAY = (
    r"(?:pon|ponme|pone|poneme|reproduce|reproduci|reproducir|play|start|inicia|sintoniza|sintonizame|sintonice|"
    r"sintonizar|toca|tocame|enciende|prende|activa|abre|abri|open|turn\s+on|put\s+on|"
    r"tune(?:\s+in)?(?:\s+to)?|(?:quiero\s+)?escuchar|listen\s+to|i\s+want\s+to\s+(?:listen\s+to|hear))"
)
# The nouns that name a station, wherever the station's name puts them («radio cooperativa», «bbc radio uno»).
_STATION_NOUN = r"(?:radio|emisora|estacion|station)"
_RADIO_ASK = (
    r"(?:que|what|whats|what\s+is|cual|which)\s+(?:(?:musica|cancion|canciones|tema|song|music|track)\s+)?"
    r"(?:(?:esta|estan|is|are)\s+)?(?:poniendo|sonando|tocando|pasando|suena|pone|toca|pasa|playing|on)"
    r"(?:\s+(?:actualmente|ahora|ahorita|now|right\s+now|currently))?(?:\s+(?:en|on|in))?"
)
_RADIO_COURTESY = r"(?:para\s+mi|for\s+me|por\s+favor|porfa|please|ahora|now|actualmente|currently|right\s+now)"
_RADIO_REQUEST = re.compile(
    rf"(?:{_RADIO_PLAY}|{_RADIO_ASK})\s+(?:(?:a|al|la|el|en|to|the)\s+)?(?P<station>.+?)"
    rf"(?:\s+{_RADIO_COURTESY})*"
)
_RADIO_NOT_A_STATION = r"\b(?:wifi|wi\s+fi|bluetooth|wireless|inalambrica|alarma|alarm|despertador)\b"
_SPOKEN_HUNDREDS = {
    "cien": 100, "ciento": 100, "doscientos": 200, "trescientos": 300, "cuatrocientos": 400, "quinientos": 500,
    "seiscientos": 600, "setecientos": 700, "ochocientos": 800, "novecientos": 900, "mil": 1000,
}


def _spoken_number(words: str) -> int | None:
    """«novecientos noventa y nueve» → 999, «eight hundred and ninety seven» → 897; None if not all number."""

    tokens = [token for token in words.replace("-", " ").split() if token != "and"]
    if not tokens:
        return None
    if all(token.isdigit() for token in tokens):
        return int("".join(tokens))
    total = 0
    if tokens[0] in _SPOKEN_HUNDREDS:
        total, tokens = _SPOKEN_HUNDREDS[tokens[0]], tokens[1:]
    elif len(tokens) > 1 and tokens[1] == "hundred" and tokens[0] in _PERCENTAGE_WORD_VALUES:
        total, tokens = _PERCENTAGE_WORD_VALUES[tokens[0]] * 100, tokens[2:]
    if not tokens:
        return total or None
    rest = _PERCENTAGE_WORD_VALUES.get(" ".join(tokens))
    return None if rest is None else total + rest


def _radio_dial(name: str, band: str) -> str:
    """The station name with a spoken dial written as it is printed (99.9 FM, 1080 AM)."""

    parts = re.split(r"\s+(?:punto|point|coma|dot)\s+", name, maxsplit=1)
    whole, decimal = parts[0], (parts[1] if len(parts) > 1 else "")
    number = _spoken_number(whole)
    if number is None:
        return name
    fraction = _spoken_number(decimal) if decimal else None
    if band == "FM" and fraction is None and 875 <= number <= 1080:
        return f"{number // 10}.{number % 10}"
    if fraction is not None and 0 <= fraction <= 9:
        return f"{number}.{fraction}"
    return str(number)


def radio_station_query(text: str) -> str | None:
    """The radio station to play, as the local player searches it («99.9 FM en vivo»), or None."""

    folded = " ".join(re.sub(r"[¿?¡!,;:]", " ", _strip_request_envelope(_fold(text))).split()).strip(" .")
    found = _RADIO_REQUEST.fullmatch(folded)
    if found is None:
        return None
    station = found.group("station").strip(" .")
    banded = re.fullmatch(rf"(?P<name>.+?)\s*{_RADIO_BAND}", station)
    if banded is not None:
        band = "FM" if banded.group("band").startswith("f") else "AM"
        name = _radio_dial(banded.group("name").strip(" ."), band)
        # «a. m.» after anything but a dial is a clock («pon un recordatorio a las 9 a. m.»).
        if band == "AM" and not re.fullmatch(r"\d{3,4}", name):
            return None
        query = f"{name} {band}"
    else:
        named = re.fullmatch(
            rf"{_STATION_NOUN}\s+(?P<name>.+)|(?P<before>.+?)\s+radio|(?P<inside>.+?\s+{_STATION_NOUN}\s+.+)", station,
        )
        # «un canal de radio para…», «mi radio», «la estación de radio», «the radio station»: a station that is
        # not named by its name.
        if (
            named is None
            or re.match(r"(?:un|una|unos|unas|a|an|some|algun|alguna|cualquier|mi|mis|my|tu|your)\b", station)
            or not re.sub(rf"\b(?:{_STATION_NOUN}|canal|channel|de|del|of|la|el|the)\b", "", station).strip()
            # «pon a delilah en la radio del dormitorio»: the radio as the place something plays is a device.
            or re.search(rf"\b(?:en|in|on|a|al|to|por)\s+(?:(?:la|el|the|mi|my|tu|your)\s+)?{_STATION_NOUN}\b", station)
        ):
            return None
        inside = named.group("inside")
        if inside is not None:
            query = inside if re.search(r"\bradio\b", inside) else f"radio {inside}"
        else:
            query = f"radio {named.group('name') or named.group('before')}"
        # Uso real 2026-09-23 «vamos a escuchar la emisora ciento tres punto cinco»: a dial said without
        # its band is FM when it is an FM dial.
        dial = _radio_dial(named.group("name") or "", "FM")
        if re.fullmatch(r"\d{2,3}\.\d", dial) and 87.5 <= float(dial) <= 108.0:
            query = f"{dial} FM"
    if _has(query, _RADIO_NOT_A_STATION) or len(query.encode("utf-8")) > 200:
        return None
    return f"{query} en vivo"


# The kinds of music people name by kind (folded). A closed list of words for music, not of providers or apps.
MUSIC_GENRE = (
    r"(?:rap|hip\s+hop|rock|pop|jazz|blues|reggae|classical|clasica|metal|salsa|bachata|cumbia|reggaeton|country|"
    r"indie|folk|techno|house|trap|punk|soul|funk|gospel|flamenco|tango|bolero|boleros|rancheras?|corridos|merengue|"
    r"lofi|lo\s+fi|edm|electronica|electronic|k\s*pop|grunge|ska|dubstep|trance|r\s*&\s*b|rnb|"
    r"vallenato|cuarteto|samba|bossa\s+nova|swing|motown|ambient|chillout|hardstyle|dembow|"
    r"baladas?|ballads?)"
)
# A word that changes a genre said alone into something else than a kind of music («no rock», «mucho pop»).
_GENRE_NOT_A_MODIFIER = (
    r"(?:no|not|sin|without|odio|hate|me|i|you|tu|te|el|la|los|las|un|una|the|a|an|mi|my|muy|mas|more|menos|less|"
    r"mucho|poco|que|what|es|is|como|like|y|and|o|or|de|of|en|in)"
)
_SPOKEN_NOW = r"(?:ahora(?:\s+mismo)?|ya|now|right\s+now|please|por\s+favor|porfa)"
# A station said with a word that is not its name but its state («radio encendida»).
_STATION_STATE = r"(?:encendida|apagada|prendida|puesta|on|off|alta|baja|fuerte|bajita)"
# A thing named alone is not a remark about it («música muy fuerte», «canciones que me gustan»).
_NOT_NAMED_ALONE = (
    r"(?!.*\b(?:muy|mas|menos|tan|fuerte|alta|alto|baja|bajo|bajito|despacio|volumen|que|me|te|se|le|es|son|"
    r"esta|estan|estuvo|fue|era|suena|sonando)\b)"
)


# Uso real 2026-09-23 (69 media rows): the thing to listen to was named and the turn still went to a
# refusal, a web search or a question, because the order was not said as «pon …». These are the ways
# people say it otherwise; each becomes the order «pon/play <what they named>» in their own words, and
# the ordinary reader decides from there (what it names plays, what names nothing is asked).
_SPOKEN_MEDIA_ORDER = re.compile(
    r"(?:"
    # Uso real 2026-09-24 «quiero algo de música qué tal si pones mi playlist de ejercicio»: a suggestion to
    # play is the order to play, whatever was said before it.
    r"(?:\S.{0,80}?\s+)?(?:que\s+tal\s+si|y\s+si|por\s+que\s+no)\s+(?:me\s+)?(?:pones|reproduces|tocas)\s+(?P<suggested>\S.*)|"
    # «solo reproduce canciones de mi lista», «just play some jazz»: the order with «just» in front.
    r"(?:solo|solamente|just|only)\s+(?P<just>(?:pon|ponme|reproduce|toca|tocame|play|put\s+on)\s+\S.*)|"
    # A desire or an invitation to listen: «quiero escuchar…», «mi deseo es escuchar…», «escuchemos…»,
    # «vamos a poner…», «déjame que escuche…».
    r"(?:(?:yo|che|bueno|y)\s+)?"
    r"(?:(?:quiero|quisiera|me\s+gustaria|me\s+encantaria|me\s+apetece|tengo\s+ganas\s+de|necesito|"
    # Uso real 2026-09-24 «puedo escuchar algo de rosalía»: asking leave to listen is asking to listen.
    r"puedo|podemos|podria|podriamos|"
    r"mi\s+deseo\s+es|vamos\s+a|dejame|deja\s+que)\s+(?:que\s+)?(?:escuchar|escuche|oir|oiga|poner|ponga)|"
    r"escuchemos|oigamos|pongamos)\s+(?P<listen>\S.*)"
    r"|(?:(?:yo|che|bueno|y)\s+)?(?:quiero|quisiera|me\s+gustaria|tengo\s+ganas\s+de|necesito)\s+"
    r"(?P<object>(?:una?\s+|el\s+|la\s+|algo\s+de\s+)?"
    r"(?:cancion|canciones|tema|temas|musica|playlist|video|videos|disco|podcasts?|audiolibros?)\b.*)"
    # The order in the infinitive: «tocar música reggae», «(podrías) ponerme música clásica».
    r"|(?:tocar|poner|reproducir)(?:me|nos)?\s+(?P<infinitive>\S.*)"
    # Starting a thing to listen to: «iniciar podcasts de nfl», «empieza la playlist».
    r"|(?:inicia|iniciar|empieza|empezar|comienza|comenzar|arranca)\s+(?P<start>(?:(?:el|la|los|las|un|una|mi|mis)\s+)?"
    r"(?:podcasts?|audiolibros?|musica|canciones|playlist|lista\s+de\s+reproduccion|radio|emisora|episodio|capitulo)\b.*)"
    # «enciende la música», «prende mis canciones»: switching the music on is asking for it.
    r"|(?:enciende|prende|activa)\s+(?P<switch_on>(?:(?:la|el|las|los|mi|mis|tu|tus)\s+)?"
    r"(?:musica|canciones|playlist|podcasts?)\b.*)"
    # The thing said first and the order after it: «podcast especial shadi reprodúcelo».
    r"|(?P<fronted>\S.{0,160}?)\s+(?:reproducelo|reproducela|ponlo|ponla|ponmelo|ponmela|tocalo|tocala)"
    # A thing to listen to named alone: «nueva música pop», «aleatorias canciones de coldplay»; never
    # a remark about it («música muy fuerte», «canciones que me gustan»).
    rf"|{_NOT_NAMED_ALONE}"
    r"(?P<nominal>(?:(?:nuev[ao]s?|aleatori[ao]s?)\s+)?(?:musica|canciones|podcasts?|audiolibros?)\s+\S+(?:\s+\S+){0,3})"
    # Uso real 2026-09-24 «radio tele taxi»: a station named alone after «radio/emisora»; never its state
    # («radio encendida»).
    rf"|{_NOT_NAMED_ALONE}(?!.*\b{_STATION_STATE}\b)"
    rf"(?P<station_alone>(?:(?:la|the)\s+)?(?:radio|emisora)\s+(?!{_SPOKEN_NOW}\b)\S+"
    rf"(?:\s+(?!{_SPOKEN_NOW}\b)\S+){{0,3}})(?:\s+{_SPOKEN_NOW})?"
    # «indie», «death metal ahora», «olly death metal now»: a kind of music named alone.
    rf"|(?P<genre_alone>(?:(?!{_GENRE_NOT_A_MODIFIER}\b)[a-z&'-]+\s+)?{MUSIC_GENRE}"
    rf"(?:\s+(?!{_GENRE_NOT_A_MODIFIER}\b|{_SPOKEN_NOW}\b)[a-z]+)?)(?:\s+{_SPOKEN_NOW})?"
    # The same in English.
    r"|(?:i\s+(?:want|need|would\s+like)\s+to|i'?d\s+like\s+to|i\s+wanna)\s+(?:listen\s+to|hear)"
    r"(?:\s+(?:listen\s+to|hear))?\s+(?P<english>\S.*)"
    r"|(?:let'?s|let\s+us|let\s+me|(?:can|could|shall|may)\s+(?:we|i))\s+(?:listen\s+to|hear)\s+(?P<english_we>\S.*)"
    r"|(?:start|begin)\s+(?P<english_start>(?:(?:the|a|my)\s+)?(?:(?:next|previous|last)\s+)?"
    r"(?:podcasts?|audiobooks?|music|songs|playlist|radio|station|episode)\b.*)"
    r"|(?P<english_fronted>\S.{0,160}?)\s+(?:play\s+it|put\s+it\s+on)"
    r"|(?:\S.{0,80}?\s+)?(?:how\s+about|what\s+about|why\s+not)\s+(?:playing|putting\s+on)\s+(?P<english_suggested>\S.*)"
    r"|(?:turn|switch|put)\s+on\s+(?P<english_switch_on>(?:(?:the|my|some)\s+)?(?:music|songs|playlist|podcasts?)\b.*)"
    # «reanuda el podcast» is an order about the podcast, not one named in English.
    r"|(?P<english_nominal>(?!(?:i|you|we|he|she|they|it|this|that|the|my|your|our|his|her|their)\b)"
    r"(?!.*\b(?:el|la|los|las|un|una|mi|mis|tu|tus|su|sus|del|de)\b)"
    r"(?:(?:new|some|random|good|latest)\s+)?[a-z0-9&'-]+(?:\s+[a-z0-9&'-]+)?\s+(?:music|songs|podcast|audiobook))"
    r")[\s.!?]*"
)


def spoken_media_order(text: str) -> str | None:
    """The order «pon …»/«play …» a request to listen said another way stands for, in the person's
    words («escuchemos a Soda Stereo» → «pon Soda Stereo»), or None when it is not one of those ways.

    After a listening verb a bare name is its music («escuchar cumbia» → «pon música de cumbia»), and
    the personal «a» is not part of what to play."""

    folded = _strip_request_envelope(_fold(text)).strip(" .!?¿¡")
    if "?" in text:
        return None
    found = _SPOKEN_MEDIA_ORDER.fullmatch(folded)
    if found is None:
        return None
    kind, rest = next((name, value) for name, value in found.groupdict().items() if value is not None)
    rest = _original_clause(text, rest.strip())
    if kind == "just":
        return rest
    verb ="play" if kind.startswith("english") or (kind == "genre_alone" and _has(folded, r"\b(?:now|please)\b")) else "pon"
    if kind == "listen":
        rest = re.sub(r"^a\s+", "", rest, flags=re.IGNORECASE)
        if not re.match(
            r"(?:algo|una?|el|la|los|las|mi|tu)\b|.*\b(?:canci[oó]n|canciones|tema|temas|m[uú]sica|playlist|disco|"
            r"album|video|podcasts?|audiolibros?|radio|emisora)\b",
            rest, re.IGNORECASE,
        ):
            rest = "música de " + rest
    return f"{verb} {rest}" if rest else None


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
