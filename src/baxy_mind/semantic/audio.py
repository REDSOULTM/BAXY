"""Audio: system volume and mute, the microphone, per-application volume. Readers moved from effect_intent (Fase 3.5); the words come from semantic.lexicon.
"""

from __future__ import annotations

import re
from . import lexicon
from .grammar import _match, _has, _head_is, _is_past_or_hypothetical_state, _UNMUTE_VERB, _SET_VOLUME_VERB, _VOLUME_UP_VERB, _VOLUME_DOWN_VERB, _indirect_audio_mute_state_query, _PERCENTAGE_WORD_VALUES


_MICROPHONE_CLIENT = r"(?:discord|teams|zoom|skype|meet|google\s+meet|whatsapp|slack)"


def app_scoped_microphone_mute(folded: str) -> str | None:
    """Name the voice client of a microphone-mute order scoped to it, or nothing.

    «silencia mi micrófono en discord», «mutea el micrófono en discord», «Sí.
    Silencia mi micrófono en Discord», «en Discord apretá silenciar»: the
    person wants to be muted in a client whose controls BAXY does not
    operate. A bare «silencia mi micrófono» stays the system mute.
    """

    prefix = r"^[¿?¡!\s]*(?:(?:si|ok|bueno|dale|listo)[.,!]?\s+)?(?:(?:por\s+favor|please)[,]?\s+)?"
    mute = re.fullmatch(
        prefix
        + r"(?:silencia|silenciame|silencialo|mutea|muteame|mutealo|mute|apaga|apagame|desactiva|desactivame|turn\s+off)\s+"
        + r"(?:(?:mi|el|the|my|mis)\s+)?(?:microfono|micro|mic|microphone)\s+"
        + r"(?:en|in|on|de|del|of|dentro\s+de)\s+(?:(?:el|la|the)\s+)?(?P<client>" + _MICROPHONE_CLIENT + r")"
        + r"(?:\s+(?:por\s+favor|please))?[\s.!?]*",
        folded,
    )
    if mute is not None:
        return mute.group("client")
    press = re.fullmatch(
        prefix
        + r"(?:(?:en|in|on)\s+(?P<client_a>" + _MICROPHONE_CLIENT + r")[,]?\s+)?"
        + r"(?:apreta|apretale|apretalo|pulsa|pulsale|presiona|presionale|clickea|click|hace\s+clic\s+en|haz\s+clic\s+en|press|hit|toca)\s+"
        + r"(?:(?:el|la|the|en)\s+)?(?:boton\s+(?:de\s+)?)?(?:silenciar|silencio|silenciarme|mutear|mute|muteo)"
        + r"(?:\s+(?:el|mi|the|my)\s+(?:microfono|micro|mic|microphone))?"
        + r"(?:\s+(?:en|in|on)\s+(?P<client_b>" + _MICROPHONE_CLIENT + r"))?[\s.!?]*",
        folded,
    )
    if press is None:
        return None
    return press.group("client_a") or press.group("client_b")


_LOCAL_VOLUME_DEVICE = (
    r"(?:sistema|equipo|pc|compu|computador(?:a)?|ordenador|system|computer)"
)


_LOCAL_OUTPUT_VOLUME_OBJECT = (
    rf"(?:salida(?:\s+de\s+(?:audio|sonido))?\s+del?\s+{_LOCAL_VOLUME_DEVICE}|"
    rf"{_LOCAL_VOLUME_DEVICE}(?:'s)?\s+output|"
    r"nivel\s+(?:actual\s+)?de\s+salida)"
)


_VOLUME_OBJECT = (
    rf"(?:volumen|volume|sonido|sound|{_LOCAL_OUTPUT_VOLUME_OBJECT})"
    rf"(?:\s+(?:del?|of|on)\s+(?:(?:el|the|my)\s+)?{_LOCAL_VOLUME_DEVICE})?"
)


def _bare_music_volume_request(folded: str) -> bool:
    """AUDIO1461 «bajá la música», «subí la música»: a volume verb whose only
    object is the music, with no amount, player or level."""

    return _has(
        folded,
        rf"^[¿?¡!\s]*(?:{_VOLUME_UP_VERB}|{_VOLUME_DOWN_VERB})\s+"
        r"(?:un\s+poco\s+|un\s+poquito\s+|a\s+)?(?:la\s+|el\s+|the\s+)?(?:musica|music)\s*[.!?]*$",
    )


# Uso real 2026-09-23 «súbele un poco», «bájale»: the clitic with nothing else
# named is the everyday order for the volume. Without an amount it takes the
# relative-volume question (owner rule, H0027); with one it is the adjustment.
_BARE_CLITIC_VOLUME = r"^[¿?¡!\s]*(?:sub[ei]le|bajale|aumentale)"
_CLITIC_VOLUME_SOFTENER = r"(?:un\s+(?:poco|poquito)|mas|algo|(?:por\s+favor|porfa|please))"


def _bare_clitic_volume_request(folded: str) -> bool:
    """«súbele un poco», «bájale»: a clitic volume order with no amount."""

    return _has(folded, _BARE_CLITIC_VOLUME + rf"(?:\s*,?\s+{_CLITIC_VOLUME_SOFTENER})*\s*[.!?]*$")


def _volume_domain(text: str) -> bool:
    if _has_app_scoped_audio(text):
        return False
    if _bare_clitic_volume_request(text) or _has(
        text,
        _BARE_CLITIC_VOLUME + rf"(?:\s+{_CLITIC_VOLUME_SOFTENER})*"
        r"\s+(?:(?:un|a|al|en)\s+)?\d{1,3}\s*(?:%|por\s*ciento)?\s*[.!?]*$",
    ):
        return True
    if _has(text, r"\b(?:data\s+volume|volumen\s+de\s+datos)\b"):
        return False
    if _has(text, r"\b(?:audio|sonido|sound)\b"):
        return True
    if _has(text, rf"\b{_LOCAL_OUTPUT_VOLUME_OBJECT}\b") and _has(
        text, r"\b(?:nivel|level|volumen|volume|puntos?|points?|por ciento|percent)\b|%",
    ):
        return True
    if _has(
        text,
        r"\b(?:bajito|mas\s+bajo|turn\s+it\s+up|turn\s+it\s+down|"
        r"barely\s+hear)\b",
    ) and not _has(text, r"\b(?:brillo|brightness|luz\s+de\s+la\s+pantalla)\b"):
        return True
    if _has(text, r"\b(?:musica|music)\b"):
        # AUDIO1461 «bajá la música»: a bare volume verb with the music as its
        # only object is the everyday way of asking for less (or more) volume;
        # without an amount it takes the relative-volume clarification (H0027).
        if _bare_music_volume_request(text):
            return True
        # Music is primarily a media object. It denotes the global audio
        # level only when a local numeric level/adjustment construction says
        # so; decades, track numbers and genre names carry no volume authority.
        return _has(
            text,
            r"\b(?:musica|music)\b\s+(?:a(?:l)?|to|at)\s*\d{1,3}"
            r"\s*(?:%|por ciento|percent)?\b|"
            r"\b(?:sube|subir|baja|bajar|aumenta|reduce|increase|decrease|"
            r"raise|lower)\b.{0,48}\b(?:musica|music)\b.{0,24}"
            r"\b(?:en|by)\s*\d{1,3}\s*(?:%|por ciento|percent|puntos?|points?)\b",
        )
    volume = _match(text, r"\b(?:volumen|volume)\b")
    if volume is None:
        return False
    # A comma/semicolon separates the same modifiers already handled below;
    # it does not turn "volume, please" into an unknown non-audio domain.
    # Keep the modifier checks: "volumen, de ventas" is still not PC audio.
    suffix = text[volume.end() :].lstrip(" \t,;")
    if not suffix or re.match(r"^[?!.]", suffix):
        return True
    modifier = _match(
        suffix,
        (
            r"^(?:de|del|of)\s+"
            r"(?:(?:la|el|los|las|the|mi|mis|my|este|esta|this)\s+)?"
            r"(?P<object>[a-z]+)"
        ),
    )
    if modifier is not None:
        return modifier.group("object") in {
            "audio",
            "sonido",
            "salida",
            "sistema",
            "system",
            "equipo",
            "compu",
            "computador",
            "computadora",
            "computer",
            "notebook",
            "laptop",
            "maquina",
            "machine",
            "pc",
            "dispositivo",
            "device",
            *lexicon.SPEAKER_NOUNS,
            "auriculares",
            "headphones",
            "musica",
            "music",
        }
    # Continuaciones que mantienen «volumen» como el nivel de audio del
    # equipo. Una continuación desconocida se abstiene: el volumen de un
    # libro, de datos o de ventas no puede heredar autoridad de audio.
    return _has(
        suffix,
        (
            r"^(?:al?|en|hasta|esta|estan|actual|actualmente|ahora|ahorita|"
            r"quedo|puesto|configurado|tiene|tienes|tengo|hay|"
            r"to|at|by|up|down|level|is|are|now|currently|set|there|"
            r"\d{1,3}\s*(?:%|por ciento|percent|puntos?|points?)?|"
            rf"por favor|please|que\s+tenga\s+(?:ahora\s+)?(?:el\s+)?{_LOCAL_VOLUME_DEVICE})\b"
        ),
    )


_MUTE_PREDICATIVE_VERB = r"(?:deja|dejar|pon|poner|ponle)\s+mudo"


_MUTE_VERB = (
    r"(?:silencia|silenciar|silenciame|silencialo|silenciala|mutea|mutear|muteame|"
    rf"mute|{_UNMUTE_VERB}|reactiva|reactivar|reactivalo|"
    rf"reactivala|apaga|apagar|activa|activar|{_MUTE_PREDICATIVE_VERB})"
)


# «apaga»/«activa» también gobiernan el equipo, la pantalla o la radio; solo
# valen para el silencio global con un objeto de audio literal. «apaga la
# música» detiene la reproducción y pertenece a media.control.
_STRICT_AUDIO_OBJECT_VERB = r"(?:apaga|apagar|activa|activar)"


def _audio_mute_domain(text: str) -> bool:
    if _has_app_scoped_audio(text):
        return False
    if _has(
        text,
        rf"\b{_STRICT_AUDIO_OBJECT_VERB}\s+"
        r"(?:(?:el|la|los|las|the|mi|my)\s+)?"
        r"(?:musica|music|cancion|song|video|pelicula|movie|"
        r"reproduccion|playback)\b",
    ):
        return False
    return _has(
        text,
        (
            rf"\b{_MUTE_VERB}\s+"
            r"(?:(?:el|la|los|las|the|mi|my)\s+)?"
            r"(?:(?:computador|computadora|computer|equipo|pc|sistema|"
            r"system|notebook|laptop)\s+)?"
            # «apaga los sonidos»: the plural is the same sound.
            r"(?:audio|sonidos?|sounds?|musica|music)\b|"
            rf"\b{_MUTE_VERB}\s+"
            r"(?:(?:el|la|los|las|the|mi|my)\s+)?"
            r"(?:(?:computador|computadora|computer|equipo|pc)\s+)?"
            rf"{lexicon.SPEAKER_NOUN}\b|"
            # Un objeto total («todo»/«everything») también nombra el audio
            # global: el fixture canónico de argumentos usa exactamente
            # «mute everything please» para audio.mute.
            r"\b(?:silencia|silenciar|mutea|mutear|mute)\s+"
            r"(?:todo|everything)(?:\s+(?:please|por favor))?\b|"
            # Fase 3.5 (layer C: «unmute the pc», «Silencia el PC»): the machine
            # itself as the object of a silence verb is its global audio. Only
            # silence verbs: «apaga el PC» shuts it down and is not this.
            rf"\b(?:silencia|silenciar|silenciame|mutea|mutear|muteame|mute|{_UNMUTE_VERB})\s+"
            r"(?:(?:el|la|the|mi|my|this|este|esta)\s+)?"
            r"(?:computador|computadora|computer|compu|equipo|pc|sistema|system|notebook|laptop)"
            r"(?:\s+(?:please|pls|por\s+favor|porfa))?[\s.!?]*$|"
            # The mute or the sound as a switch, the sound given back and a noise to stop (semantic.lexicon).
            rf"\b(?:{lexicon.UNMUTE_WORDS}|{lexicon.MUTE_WORDS})\b|"
            r"\b(?:pon|poner|ponle|deja|dejar|put|leave)\s+"
            r"(?:(?:el|la|the)\s+)?(?:\w+\s+){0,2}"
            r"(?:en|in|on)\s+(?:mudo|silencio|mute|silent)\b|"
            r"\bturn\s+(?:the\s+)?(?:audio|sound|volume)\s+back\s+on\b|"
            # Uso real 2026-09-23 «silencio»: the bare silence order is the global mute state.
            rf"{lexicon.BARE_SILENCE}|"
            # Órdenes elípticas inequívocas: sólo existe un silencio global.
            rf"^[¿?¡!\s]*{_UNMUTE_VERB}"
            r"(?:\s+(?:it|please|pls|plz|por favor|porfa|todo|everything|el audio|"
            r"the audio))?[\s?!.]*$"
        ),
    )


_APP_VOLUME_AMOUNT = (
    r"(?:\s+(?:en|by|a|al|to)\s+(?P<amount>\d{1,3})\s*(?:%|por\s+ciento|percent|puntos?|points?)?"
    r"|\s+(?P<amount2>\d{1,3})\s*(?:%|por\s+ciento|percent|puntos?|points?))?"
)


_APP_VOLUME_SPANISH = re.compile(
    rf"^[¿?¡!\s]*(?:(?:necesito|quiero|queria|quisiera|podes|podrias|podria|me\s+(?:podes|podrias|podria))\s+(?:que\s+)?)?"
    rf"(?P<verb>{_VOLUME_UP_VERB}|{_VOLUME_DOWN_VERB})\s+(?:me\s+)?(?:un\s+poco\s+|un\s+toque\s+|a\s+little\s+)?"
    r"(?:el\s+|la\s+|the\s+)?(?:volumen|volume|sonido|sound|audio)\s+(?:de|del|of|en|in|on)\s+(?:la\s+|el\s+|the\s+)?(?:app\s+|aplicacion\s+|application\s+)?"
    rf"(?P<app>[a-z0-9][a-z0-9 .+_-]{{0,60}}?)(?:\s+(?:un\s+poco|un\s+toque|un\s+poquito|a\s+bit|a\s+little))?{_APP_VOLUME_AMOUNT}(?:\s*,?\s*(?:please|por\s+favor|porfa))?[\s.!?]*$",
)


_APP_VOLUME_ENGLISH = re.compile(
    r"^[¿?¡!\s]*(?:(?:please|can\s+you|could\s+you|i\s+need\s+you\s+to|i\s+want\s+you\s+to)\s+)?"
    r"(?P<verb>turn\s+up|turn\s+down|raise|lower|increase|decrease|bump\s+up|crank\s+up)\s+(?:the\s+)?"
    rf"(?P<app>[a-z0-9][a-z0-9 .+_-]{{0,60}}?)(?:'s)?\s+(?:volume|audio|sound)(?:\s+(?:level|a\s+bit|a\s+little))?{_APP_VOLUME_AMOUNT}(?:\s*,?\s*please)?[\s.!?]*$",
)


_APP_VOLUME_ENGLISH_SPLIT = re.compile(
    r"^[¿?¡!\s]*(?:(?:please|can\s+you|could\s+you)\s+)?turn\s+(?:the\s+)?"
    rf"(?P<app>[a-z0-9][a-z0-9 .+_-]{{0,60}}?)(?:'s)?\s+(?:volume|audio|sound)\s+(?P<verb>up|down)(?:\s+(?:a\s+bit|a\s+little))?{_APP_VOLUME_AMOUNT}(?:\s*,?\s*please)?[\s.!?]*$",
)


_APP_VOLUME_SET_LEVEL = (
    r"(?P<level>100|[0-9]{1,2})\s*(?:%|por\s+ciento|percent|puntos?|points?)?"
    r"|(?P<word>maximo|max|tope|full|minimo|min|cero|zero|mitad|half)"
)


_APP_VOLUME_SET_SPANISH = re.compile(
    rf"^[¿?¡!\s]*(?:(?:necesito|quiero|queria|quisiera|podes|podrias|podria|me\s+(?:podes|podrias|podria))\s+(?:que\s+)?)?"
    rf"(?:{_SET_VOLUME_VERB})\s+(?:me\s+)?"
    r"(?:(?:el\s+|la\s+)?(?:volumen|sonido|audio)\s+(?:de|del|en)\s+)?(?:la\s+|el\s+)?(?:app\s+|aplicacion\s+)?"
    r"(?P<app>[a-z0-9][a-z0-9 .+_-]{0,60}?)"
    r"(?:\s+(?:el\s+|la\s+)?(?:volumen|sonido|audio))?"
    rf"\s+(?:a|al|en)\s+(?:la\s+|el\s+)?(?:{_APP_VOLUME_SET_LEVEL})(?:\s*,?\s*(?:please|por\s+favor|porfa))?[\s.!?]*$",
)


_APP_VOLUME_SET_ENGLISH = re.compile(
    r"^[¿?¡!\s]*(?:(?:please|can\s+you|could\s+you|i\s+need\s+you\s+to|i\s+want\s+you\s+to)\s+)?"
    r"(?:set|put|leave|change|adjust|fix)\s+(?:the\s+)?"
    r"(?:(?:volume|audio|sound)\s+(?:of|on|in)\s+(?:the\s+)?)?(?:app\s+)?"
    r"(?P<app>[a-z0-9][a-z0-9 .+_-]{0,60}?)(?:'s)?"
    r"(?:\s+(?:volume|audio|sound)(?:\s+level)?)?"
    rf"\s+(?:to|at)\s+(?:{_APP_VOLUME_SET_LEVEL})(?:\s*,?\s*please)?[\s.!?]*$",
)


_APP_VOLUME_LEVEL_WORDS = {"maximo": 100, "max": 100, "tope": 100, "full": 100, "minimo": 0, "min": 0, "cero": 0, "zero": 0, "mitad": 50, "half": 50}


# Señales de que se pregunta por el nivel actual de audio, no por cambiarlo.
_AUDIO_LEVEL_CUE = (
    r"\b(?:en que|a que|cuanto|cuanta|estado|status|actual|current|"
    r"nivel|level|quedo|how much)\b|"
    r"\b(?:que|what|cual|which)\s+(?:volumen|volume)\b"
)


def _is_audio_mute_state_query(text: str, head: str) -> bool:
    """Recognize a question about the current mute state, never an order.

    ``audio.status`` already reports mute together with the level, so a
    "is the sound muted?" question is the same read-only observation as
    "how loud is it?".  An imperative head, a microphone target, an
    application scope or a report about someone else stays out.
    """

    if _indirect_audio_mute_state_query(text):
        return True
    if _has_app_scoped_audio(text) or _is_past_or_hypothetical_state(text):
        return False
    if _head_is(
        head,
        (
            r"(?:silencia|silenciar|silencialo|silenciala|mute|unmute|"
            r"desmutea|mutea|reactiva|reactivar|reactivalo|reactivala|"
            r"quita|quitar|pon|poner|apaga|apagar|activa|activar)"
        ),
    ):
        return False
    if not _head_is(
        head,
        (
            r"(?:esta|estan|is|are|como|how|que|what|cual|which|"
            r"dime|decime|muestra|muestrame|mostrame|show|ver|"
            r"revisa|revisar|chequea|checa|verifica|fijate|mira|check|"
            r"audio|sonido|sound|volumen|volume|estado|status)"
        ),
    ):
        return False
    if _has(
        text,
        r"\b(?:microfono|microphone|mic|micro|camara|camera|tele|tv)\b",
    ):
        return False
    # Un reporte sobre terceros («me silenciaron», «le puse mute a la tele»)
    # describe un hecho pasado y no solicita una observación del equipo.
    if _has(
        text,
        (
            r"\b(?:silenciaron|silencie|silencio yo|mutearon|mutee|"
            r"puse|pusieron|apreté|apreto|toque|di al)\b"
        ),
    ):
        return False
    return _has(
        text,
        (
            r"\b(?:silenciad[oa]s?|mutead[oa]s?|muted|en\s+mudo|"
            r"en\s+silencio)\b|"
            r"\b(?:esta|estan|is|are)\s+(?:el\s+|la\s+|the\s+)?"
            r"(?:audio|sonido|sound|volumen|volume)?\s*"
            r"(?:mute|mudo|silencio)\b"
        ),
    )


_AUDIO_APPLICATION_SCOPE = (
    r"(?:spotify|chrome|opera|edge|firefox|discord|zoom|teams|youtube|"
    r"netflix|video|pelicula|movie|juego|game|navegador|browser|"
    r"aplicacion|application|app|pestana|tab|notificacion|notificaciones|"
    r"notification|notifications|llamada|call|reunion|meeting|tele|tv|"
    r"microfono|microphone|mic)"
)


def _has_app_scoped_audio(text: str) -> bool:
    return _has(
        text,
        (
            rf"\b(?:audio|sonido|sound|musica|music|volumen|volume)\s+"
            rf"(?:a|al|de|del|of|to)\s+(?:la\s+|el\s+|the\s+|mi\s+|my\s+)?"
            rf"{_AUDIO_APPLICATION_SCOPE}\b|"
            rf"\b(?:en|on)\s+(?:spotify|chrome|opera|edge|firefox|discord|"
            rf"zoom|teams|youtube|netflix)\b|"
            rf"\b(?:the\s+|la\s+|el\s+|mi\s+|my\s+)?{_AUDIO_APPLICATION_SCOPE}"
            rf"\s+(?:audio|sonido|sound|volumen|volume)\b|"
            rf"\b{_AUDIO_APPLICATION_SCOPE}\s+(?:only|solamente|nada mas|"
            rf"nomas|unicamente)\b"
        ),
    )


_PERCENTAGE_WORD_PATTERN = (
    "(?:"
    + "|".join(
        re.escape(value)
        for value in sorted(_PERCENTAGE_WORD_VALUES, key=len, reverse=True)
    )
    + ")"
)
