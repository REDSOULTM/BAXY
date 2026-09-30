"""Web: search, research a topic or an entity, navigate to a site, browser tabs. Readers moved from effect_intent (Fase 3.5).
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date
from typing import Iterable
from .display import _KNOWN_FOLDER_ENUM, _KNOWN_FOLDER_WORDS
from .grammar import _fold, _match, _has, _strip_request_envelope, _without_address, _request_head, _head_forms, _head_is, _negative_action_forms, _is_negative_effect_clause, _is_meta_or_tool_denial, _OPEN, _LIST, _READ, _SEARCH, _explicit_google_search_query, ARITHMETIC_EXPRESSION, _request_body_surface
from .intent import EffectIntent, _entity_key, _append, _append_all
from .catalog import ApplicationCatalogIndex, _application_name_key, build_application_catalog_index
from .temporal import (
    _BOUNDED_TEMPORAL_SELECTOR, _DAY, _LAST_WEEKEND, _MONTH, _PAST_WEEKDAY, _WEEKDAYS, is_window_phrase, spoken_date,
)
from .lexicon import GIVEN_NAMES, SOCIAL_NETWORK
from .notes import OWN_EVENT_NOUN, own_event_reference
from .windows import minimize_all_request
from .network import _direct_current_time_request
from .media import _youtube_search_query
from .normalize import fold as _reading_fold, fold_in_place


def _public_route_lookup_request(folded: str) -> bool:
    """Recognize a standalone request for directions to a public destination."""

    return (
        re.fullmatch(
            r"[^\w]*(?:"
            r"directions?\s+(?:to|from\s+.{1,80}\s+to)\s+\S.{0,120}|"
            r"direcciones?\s+(?:a|desde\s+.{1,80}\s+a)\s+\S.{0,120}|"
            r"indicaciones\s+para\s+llegar\s+a\s+\S.{0,120}"
            r")[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )


# A day of the calendar that is not today: a date («el veintitrés de abril», «april sixteenth»), a weekday placed
# by its neighbours («el próximo sábado», «last monday of this month») or a named day of the year.
_WEEKDAY_NAME = r"(?:" + "|".join(name for names in _WEEKDAYS for name in names) + r")"
_HOLIDAY = (
    r"(?:navidad|nochebuena|nochevieja|ano\s+nuevo|reyes|san\s+valentin|valentine'?s(?:\s+day)?|pascua|"
    r"semana\s+santa|easter|halloween|thanksgiving|accion\s+de\s+gracias|christmas(?:\s+eve)?|"
    r"new\s+year'?s(?:\s+(?:day|eve))?|dia\s+de\s+(?:la\s+madre|el\s+padre|los\s+muertos|todos\s+los\s+santos)|"
    r"mother'?s\s+day|father'?s\s+day|independence\s+day|labou?r\s+day|memorial\s+day)"
)
_CALENDAR_DAY = (
    rf"(?:(?:el|la|the)\s+)?(?:{_DAY}\s+(?:(?:de|of)\s+)?{_MONTH}|{_MONTH}\s+(?:the\s+)?{_DAY}|"
    rf"(?:proxim[oa]|siguiente|ultim[oa]|primer[oa]?|segund[oa]|tercer[oa]?|next|last|first|second|third|this|"
    rf"este|esta)\s+{_WEEKDAY_NAME}|{_WEEKDAY_NAME}\s+(?:proximo|que\s+viene)|{_HOLIDAY})"
    r"(?:\s+(?:de|del|of|in)\s+(?:este|el|this|the|next|el\s+proximo)\s+(?:mes|month|ano|year))?"
    r"(?:,?\s+(?:(?:de|del|of|in)\s+)?(?:\d{4}|(?:este|el\s+presente|this|next)\s+(?:ano|year)))?"
)
_CALENDAR_FACT_ASK = (
    r"(?:(?:dime|decime|digame|sabes|sabe|tell\s+me|do\s+you\s+know|(?:can|could)\s+you\s+tell\s+me|"
    r"(?:quiero|quisiera|necesito|me\s+gustaria)\s+saber|i\s+(?:want|need|would\s+like)(?:\s+to\s+know)?|"
    r"i'?d\s+like(?:\s+to\s+know)?|give\s+me|dame)\s+)?"
)


def _public_calendar_fact_lookup_request(folded: str) -> bool:
    """Recognize year-dependent public calendar facts outside local state.

    MASSIVE datetime_query (dev corpus 2026-09-24) «es el veintitrés de abril un sábado», «que fecha cae el próximo
    sábado», «what day does april sixteenth fall on», «i want the date of last monday of this month»: which weekday
    a date falls on, or which date a placed weekday is, was talked about from memory or asked back. This PC's clock
    reads only today; the calendar of another day is looked up."""

    return (
        re.fullmatch(
            rf"[^\w]*{_CALENDAR_FACT_ASK}(?:"
            rf"(?:en\s+)?(?:que|cual)\s+(?:dia(?:\s+de\s+la\s+semana)?|fecha)\s+(?:cae|caera|cayo|es|sera|fue|toca)\s+"
            rf"{_CALENDAR_DAY}|"
            rf"(?:es|sera|cae|caera|fue|cayo)\s+{_CALENDAR_DAY}\s+(?:un|en|el)\s+{_WEEKDAY_NAME}|"
            rf"{_CALENDAR_DAY}\s+(?:es|sera|cae|caera|fue|cayo)\s+(?:un|en|el)\s+{_WEEKDAY_NAME}|"
            rf"what\s+(?:day(?:\s+of\s+the\s+week)?|date|weekday)\s+(?:is|does|will|was|did)\s+{_CALENDAR_DAY}"
            r"(?:\s+(?:fall|be|land|fell)(?:\s+on)?)?(?:\s+on)?(?:\s+(?:this|next)\s+year|\s+(?:in\s+)?\d{4})?|"
            rf"(?:is|will|was)\s+{_CALENDAR_DAY}\s+(?:be\s+)?(?:on\s+)?an?\s+{_WEEKDAY_NAME}|"
            rf"(?:(?:what\s+is|what'?s)\s+)?(?:the\s+|la\s+)?(?:date|fecha|day|dia)\s+(?:of|de|del)\s+{_CALENDAR_DAY}"
            r")[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )


_WEATHER_WORDS = (
    r"\b(?:weather|forecast|rain|raining|clima|pronostico|lluvia|llueve|llover|"
    # WEATHER2023 «¿hace frío afuera?»: the cold or the heat outside is the weather too.
    r"llovera|llovio|temperature|temperatura|frio|fria|calor|cold|hot|caluroso|calurosa|"
    # Tanda 9 «is it humid?», «will it be hotter tomorrow?»: how the air feels, and its comparatives.
    r"humid|muggy|hotter|colder|warmer|chilly|"
    # Uso real 2026-09-23 (MASSIVE weather_query): «necesitaré protector solar», «nieve», «viento».
    r"nieve|nevar|nevara|nevando|snow|snowing|viento|wind|windy|humedad|humidity|soleado|sunny|"
    r"cloudy|tormenta|storm|granizo|paraguas|umbrella|protector\s+solar|sunscreen|lloviendo|"
    r"lluvias|precipitacion|precipitaciones|chubascos?|"
    # MASSIVE weather_query (dev corpus 2026-09-24) «va a estar ventoso el jueves», «is my golf game going to get
    # rained out»: the weather said by the adjective of the day, or by the rain calling something off.
    r"ventos[oa]|lluvios[oa]|nublad[oa]s?|despejad[oa]|rainy|stormy|foggy|niebla|neblina|heladas?|frost|"
    r"rain(?:ed)?\s+out|rainout|"
    # Uso real tanda 5 «¿qué pronostican tus aplicaciones del tiempo para mañana?»: the
    # forecast named by its adjective, and the weather app named by what it tells.
    r"meteorologic[oa]s?|(?:apps?|aplicacion(?:es)?)\s+del\s+tiempo)\b"
)
# The weather of the past has no live read («qué clima hacía en 1990», «did it rain yesterday»); rained out is not
# the past («is my game going to get rained out»).
_PAST_WEATHER = (
    r"\b(?:hacia|hizo|hubo|estuvo|estaba|fue|llovio|was|were|did|rained(?!\s+out))\b|"
    r"\b(?:19|20)\d\d\b|\b(?:ayer|anteayer|yesterday|la\s+semana\s+pasada|last\s+week)\b"
)
# Uso real 2026-09-23: «qué tiempo hace en santiago», «cómo va a estar el tiempo hoy
# en ñuñoa»: «el tiempo» is the weather inside a weather frame only; «cuánto
# tiempo», a cooking or travel time, or «hace tiempo» (long ago) are not.
# Tanda 9 «dime el tiempo de Madrid» read the clock and then pasted a weather page: «el tiempo de» a name said bare
# (no article, no possessive, no verb) is the weather there, as «el tiempo en Madrid» is. A span of something («el
# tiempo de vuelo», «de espera») is not; those nouns are listed in _NOT_WEATHER_TIEMPO.
_TIEMPO_OF_A_NAME = (
    r"de\s+(?!(?:la|el|los|las|lo|un|una|unos|unas|mi|mis|tu|tus|su|sus|nuestr[oa]s?|este|esta|estos|estas|ese|esa|"
    r"esos|esas|eso|esto|aquel|aquella|que|cuando|como|cada|todo|toda|ahi|alla|aqui)\b)"
    r"(?!\w+(?:ar|er|ir)(?:me|te|se|nos|lo|la|le)?\b)\w"
)
_WEATHER_TIEMPO = (
    r"\b(?:que|como)\s+(?:tiempo\s+(?:hace|hara|va\s+a\s+hacer)|"
    r"(?:esta|estara|sera|va\s+a\s+estar|va\s+a\s+ser|viene)\s+el\s+tiempo)\b|"
    # MASSIVE weather_query «mira el tiempo de la semana que viene»: a day or a week to come is a weather frame too.
    # Uso real tanda 5 «infórmanos del tiempo actual en Lugo»: «del tiempo» and the weather «actual» are the
    # same frame; «el tiempo en que vivías» is a time, not the weather.
    r"\b(?:el|del)\s+tiempo\s+(?:(?:de|para)\s+(?:hoy|manana|este|esta|el\s+fin|"
    r"(?:la|el)\s+(?:semana|proxim[oa]|siguiente|lunes|martes|miercoles|jueves|viernes|sabado|domingo))|"
    r"hoy|manana|ahora|actual|de\s+ahora|"
    r"este\s+\w+|esta\s+(?:tarde|noche|semana|manana)|en\s+(?!el\s+horno|la\s+olla|el\s+microondas|que\b)\w|"
    + _TIEMPO_OF_A_NAME + r")|"
    r"^\s*tiempo\s+(?:(?:en|para|hoy|manana|actual|de\s+(?:hoy|manana|ahora))\b|" + _TIEMPO_OF_A_NAME + ")"
)
_NOT_WEATHER_TIEMPO = (
    r"\b(?:cuanto|cuantos|mucho|poco|a|hace)\s+tiempo\b|\btiempo\s+(?:libre|de\s+(?:coccion|espera|viaje|carga|"
    r"respuesta|entrega|juego|pantalla|vuelo|vida|ejecucion|reaccion|descarga|duracion|uso|subida|bajada|trabajo|"
    r"estudio|sobra|calidad|ocio|descuento|silencio|recuperacion|entrenamiento|lectura|procesamiento|arranque|"
    r"encendido|compilacion|instalacion|conduccion|llegada|transito|envio|preparacion|reposo|horneado|hervor|"
    r"fermentacion|secado|exposicion|vigencia|validez|gracia|prueba|dios|guerra|paz|crisis|vacaciones|clase|"
    r"examen|partido|descanso|juventud|infancia|ninez|sueno|pausa|latencia))\b|"
    r"\b(?:horno|olla|microondas|coccion|cocinar|receta)\b"
)


# Uso real tanda 4c «Whats the air quality hoy?» searched US pages and answered nothing: the air of a place is
# read with its weather, from the same public service, so naming the air names the weather read.
AIR_QUALITY_WORDS = (
    r"\b(?:calidad\s+del\s+aire|air\s+quality|aqi|smog|air\s+pollution|pollution\s+levels?|polucion|"
    r"contaminacion\s+(?:del\s+aire|atmosferica|ambiental)|(?:nivel(?:es)?|indice)\s+de\s+(?:contaminacion|polucion)|"
    r"pm\s*2[.,]?5|pm\s*10|particulas\s+finas|"
    r"(?:contaminad[oa]|polluted|limpio|clean|sucio|dirty)\s+(?:esta\s+|is\s+)?(?:el\s+|the\s+)?(?:aire|air)|"
    r"(?:el\s+aire|the\s+air)\s+(?:esta\s+|is\s+)?(?:muy\s+|very\s+)?(?:contaminado|limpio|sucio|malo|polluted|clean|"
    r"dirty|bad)|(?:como\s+esta|how\s*'?s|how\s+is)\s+(?:el\s+aire|the\s+air))\b"
)
# «cómo reducir la contaminación del aire», «what causes air pollution», «noticias sobre el smog»: the air as a
# topic is looked up, not read.
_AIR_TOPIC = (
    r"\b(?:causa\w*|cause\w*|reduc\w*|evitar|prevenir|prevent\w*|combat\w*|efectos?|effects?|impact\w*|"
    r"por\s*que|why|definicion|definition|significa|means?|historia|history|noticias|news|articulos?|articles?|"
    r"estudios?|stud(?:y|ies)|ensayo|essay|tarea|homework|soluci\w*|solutions?|proteg\w*|protect\w*)\b"
)


_AIR_LEVEL = r"\b(?:nivel(?:es)?|level|levels|leve|cuanto|cuanta|how\s+(?:much|bad|good)|indice|index)\b"


def _asks_air(folded: str) -> bool:
    return _has(folded, AIR_QUALITY_WORDS) and not _has(folded, _AIR_TOPIC)


# Uso real tanda 6 «Dime el UV index», «¿Cómo esta el dew point ahora» went to pages that define them: the UV index
# and the dew point are readings of the same weather read. A UV lamp or a UV filter is not the sky, and what the
# index is, why it matters or how to protect oneself is a topic (``_AIR_TOPIC``), looked up, not read.
_SKY_MEASURE_WORDS = (
    r"\b(?:(?:indice|index|nivel(?:es)?|levels?|radiacion|radiation)\s+(?:de\s+(?:la\s+)?)?(?:uv|ultravioleta|ultraviolet)|"
    r"uv\s+(?:index|indice|level|nivel|hoy|today|ahora|now|forecast|pronostico)|uvi|"
    r"dew\s*points?|punto\s+de\s+rocio|temperatura\s+de\s+rocio)\b"
)


def _asks_sky_measure(folded: str) -> bool:
    return _has(folded, _SKY_MEASURE_WORDS) and not _has(folded, _AIR_TOPIC)


def _names_weather(folded: str) -> bool:
    """The weather is named: a weather word, the air, the UV index or the dew point, or «el tiempo» inside a
    weather frame."""

    return _has(folded, _WEATHER_WORDS) or _asks_air(folded) or _asks_sky_measure(folded) or (
        _has(folded, _WEATHER_TIEMPO) and not _has(folded, _NOT_WEATHER_TIEMPO)
    )


def weather_asks_air(text: str) -> bool:
    """The weather question asks about the air (its quality, smog, particles)."""

    return _asks_air(_fold(text))


# Uso real tanda 4c «i'd like to know my current location» got «I don't have access to your current location»,
# while the weather read of the same session said «Hoy en Curicó…»: the weather read locates this PC by its
# public address and its receipt names the place, so where the person is, asked as a whole question, is that read.
# «dónde estoy guardando esto», «comparte mi ubicación» or «en qué carpeta estoy» are not the place.
_OWN_PLACE_QUESTION = re.compile(
    r"(?:(?:cual|what)\s*(?:es|is|'?s)?\s+)?(?:mi|my)\s+(?:(?:current|actual|exact|exacta|approximate|present)\s+)?"
    r"(?:ubicacion|localizacion|location|posicion|position|ciudad|city)"
    r"(?:\s+(?:actual|exacta|aproximada|ahora|now|right\s+now|currently))*|"
    r"(?:en\s+)?(?:donde|where)\s+(?:estoy|me\s+encuentro|estamos|am\s+i|are\s+we|i\s+am|we\s+are)"
    r"(?:\s+(?:ahora|ahorita|ahora\s+mismo|en\s+este\s+momento|now|right\s+now|rn|located|currently))*|"
    r"(?:donde|where)\s+(?:esta|is)\s+(?:este|this)\s+(?:pc|equipo|computador|computadora|ordenador|computer)"
    r"(?:\s+(?:located|ubicad[oa]))?|"
    r"(?:en\s+)?(?:que|cual|what|which)\s+(?:ciudad|pais|region|comuna|lugar|city|country|town|state|place)\s+"
    r"(?:estoy|me\s+encuentro|estamos|am\s+i\s+in|are\s+we\s+in|is\s+this(?:\s+pc)?)"
    r"(?:\s+(?:ahora|now|right\s+now))*"
)


def asks_own_place(text: str) -> bool:
    """The whole request asks where the person (this PC) is (see above)."""

    body = _fold(public_query_body(text)).strip(" ¿?¡!.,;:")
    return _OWN_PLACE_QUESTION.fullmatch(body) is not None


# Uso real (MASSIVE weather_query, dev corpus 2026-09-23): the forecast asked with no asking verb in front.
# «la temperatura de mañana va a ser caliente sí o no», «la temperatura será más alta de cuarenta grados
# mañana» open on the weather noun itself; «¿tendremos este tiempo el resto del día?» asks whether the
# weather holds. A noun of this PC or of the kitchen («la temperatura de la cpu», «del horno») is not.
_WEATHER_SUBJECT_QUESTION = (
    r"^[¿¡\s]*(?:el|la|the)\s+(?:temperatura|temperature|clima|weather|pronostico|forecast|prevision)\b"
)
_WEATHER_HOLDS_QUESTION = (
    r"\b(?:tendremos|tendre|habra|seguira|continuara|durara|va\s+a\s+(?:seguir|durar))\s+"
    r"(?:este|ese|el\s+mismo|buen|mal)\s+tiempo\b"
)
_NOT_WEATHER_TEMPERATURE = (
    r"\b(?:cpu|gpu|procesador|processor|tarjeta|equipo|pc|computadora|computador|ordenador|laptop|notebook|"
    r"disco|bateria|battery|motor|agua|water|horno|oven|nevera|heladera|refrigerador|fridge|cuerpo|body|fiebre)\b"
)
# «me gustaría saber el tiempo en barcelona», «quisiera saber si va a llover»: wanting to know is the ask.
_KNOWLEDGE_LEAD_IN = (
    r"^[¿¡\s]*(?:(?:yo\s+)?(?:quiero|quisiera|necesito|me\s+gustaria)\s+(?:saber|conocer)|"
    r"i\s+(?:want|need|would\s+like|'d\s+like)\s+to\s+know)\s+(?:(?:si|if|whether)\s+)?"
)


# MASSIVE weather_query (dev corpus 2026-09-24) «will it be nice at the beach on friday»: how a day to come will be,
# said by the adjective of its weather («nice», «buen día»), asks the forecast.
_WEATHER_DAY_QUESTION = (
    r"^[¿¡\s]*(?:(?:will|is)\s+it\s+(?:going\s+to\s+)?be\s+(?:a\s+)?(?:nice|good|bad|beautiful|lovely|warm|chilly|"
    r"cool)(?:\s+(?:day|weather))?(?:\s+(?:out|outside))?"
    # «will it be a good idea to buy a car tomorrow» is not the weather: only a place or a time follows.
    r"(?=[\s.?!,]*$|\s+(?:at|in|on|by|this|next|tomorrow|today|tonight|around|near|over)\b)|"
    r"(?:va\s+a\s+(?:hacer|estar|ser)|hara|estara|sera)\s+(?:un\s+)?(?:buen|mal|bonito|lindo|feo)\s+(?:dia|tiempo)\b)"
)


# Uso real tanda 4f «¿el sábado podremos comer en una terraza en Sevilla?» searched pages about the food:
# whether a plan in the open air can be done on a day to come hangs on that day's weather, so it asks the forecast.
# Booking it, its price or whether a place opens is not the weather.
_OUTDOOR_SETTING = (
    r"\b(?:terrazas?|al\s+aire\s+libre|a\s+la\s+intemperie|afuera|playa|picnic|barbacoa|asado|parrillada|"
    r"piscina|patio|jardin|outside|outdoors|open\s+air|terrace|beach|barbecue|bbq|cookout|pool|garden)\b"
)
_PLAN_ASKED = (
    r"\b(?:podremos|podre|podra|podran|podriamos|se\s+podra|se\s+puede|sera\s+posible|da\s+para|"
    r"(?:can|could|will)\s+(?:we|i)(?:\s+be\s+able\s+to)?|should\s+(?:we|i))\b"
)
_PLAN_ELSEWHERE = (
    r"\b(?:reserv\w*|book\w*|abiert[oa]s?|abre|abren|cierra|cierran|open|opens|closed|closes|precio|price|cuesta|"
    r"costs?|entradas?|tickets?|horarios?|fumar|smoke|smoking|mascotas?|pets?|dogs?|perros?)\b"
)


def _outdoor_plan_question(folded: str) -> bool:
    """Whether a plan in the open air can be done on a day to come (see above)."""

    return (
        _has(folded, _OUTDOOR_SETTING)
        and _has(folded, _PLAN_ASKED)
        and (_has(folded, WEATHER_WHEN) or _has(folded, rf"\b{_WEEKDAY_NAME}\b"))
        and not _has(folded, _PLAN_ELSEWHERE)
    )


def _forecast_question(folded: str) -> bool:
    """The forecast asked by naming it as the subject of a time to come, whether the weather holds, or whether
    a plan in the open air can be done on a day to come."""

    if _has(folded, _NOT_WEATHER_TEMPERATURE):
        return False
    return (
        _outdoor_plan_question(folded)
        or (_has(folded, _WEATHER_SUBJECT_QUESTION) and _has(folded, WEATHER_WHEN))
        or _has(folded, _WEATHER_HOLDS_QUESTION)
        or (
            _has(folded, _WEATHER_DAY_QUESTION)
            and (_has(folded, WEATHER_WHEN) or _has(folded, rf"\b{_WEEKDAY_NAME}\b"))
        )
        # Tanda 4c «el aire está limpio hoy?»: the air said as the subject, asked without an asking word.
        or (_asks_air(folded) and _has(folded, r"^[¿¡\s]*(?:el|la|the)\b"))
        # Uso real tanda 5 «wat level of air pollution hay en downtown Houston»: the air asked by its
        # level or amount, whatever the asking word («wat level», «cuánto smog hay»).
        or (_asks_air(folded) and _has(folded, _AIR_LEVEL))
        # Uso real tanda 6: «el índice UV de hoy?», «radiación UV en Madrid hoy» name the UV index or the dew point
        # about a time, without an asking word.
        or (_asks_sky_measure(folded) and _has(folded, WEATHER_WHEN))
        # «weekly forecast», «the 7-day forecast»: the forecast named by its span.
        or _has(folded, r"^[¿¡\s]*(?:(?:the|a|el|la)\s+)?(?:weekly|extended|7[-\s]?day|seven[-\s]day)\s+"
                        r"(?:weather\s+)?forecast\b")
    )


# Uso real tanda 2 (2026-09-23): the weather asked through what it calls for, never by name. «¿Me llevo el
# chubasquero?», «¿Debo ponerme scarf esta noche?» ask whether to wear or carry something; «¿Cuántas pulgadas
# are we getting today?» asks an amount; «necesito el horario de la caída del sol para mañana» asks a sun time.
# All went to a web search of the whole sentence. Each is a weather read only inside the frame that asks it:
# gear with a decision to wear, carry or need it (buying, finding or recommending one is not the weather),
# asked as a question or about a time; a unit counted about a time; a sun time asked by its hour.
_WEATHER_GEAR = (
    r"\b(?:paraguas|sombrilla|umbrella|chubasquero|impermeable|capa\s+de\s+lluvia|poncho|rain\s*coat|rain\s+jacket|"
    r"bufanda|scarf|abrigo|chaqueta|chamarra|campera|casaca|parka|jacket|coat|sueter|sweater|jersey|poleron|"
    r"gorro|beanie|guantes|gloves|botas\s+de\s+(?:lluvia|agua)|rain\s+boots|protector\s+solar|bloqueador|"
    r"sunscreen|gafas\s+de\s+sol|lentes\s+de\s+sol|sunglasses|"
    # «¿debería ponerme sandalias o zapatos con calcetines?»: what the heat calls for is the weather too.
    r"sandalias|chanclas|ojotas|sandals|flip[\s-]?flops|shorts|bermudas|pantalon(?:es)?\s+cortos?|"
    r"manga\s+(?:corta|larga))\b"
)
# «qué chaqueta debería ponerme», «should I wear a coat»: a question said without its question mark
# opens on the asking word or the modal.
# MASSIVE weather_query (dev corpus 2026-09-24) «es necesario llevar paraguas para salir», «me puedo poner pantalones
# cortos hoy», «i need jacket after ten am or not»: whether it is needed, whether one may wear it, or the choice left
# open («or not», «sí o no») asks it as well.
_WEATHER_GEAR_ASKED = (
    r"^[¿¡\s]*(?:que|cual|cuales|deberia|deberiamos|debo|conviene|hace\s+falta|(?:es|sera)\s+necesario|"
    r"(?:me\s+)?puedo|can\s+i|should|do\s+i|will\s+i)\b|"
    r"\b(?:or\s+not|o\s+no|si\s+o\s+no|yes\s+or\s+no)[\s.!?]*$"
)
_WEATHER_GEAR_DECISION = (
    r"\b(?:llevo|llevar|llevarme|lleve|llevamos|pongo|poner|ponerme|ponga|me\s+abrigo|abrigarme|uso|usar|necesito|"
    r"necesitare|necesitamos|hace\s+falta|necesario|debo|deberia|conviene|tengo\s+que|should|need|bring|take|wear|"
    r"pack)\b"
)
# Buying or pricing the gear is not the weather («necesito comprar un paraguas»); shopping while wearing it is
# («me puedo poner pantalones cortos hoy mientras compramos»).
_WEATHER_GEAR_ELSEWHERE = (
    r"\b(?:compr\w*|buy\w*)\s+(?:\w+\s+){0,3}?" + _WEATHER_GEAR[2:] + "|"
    r"\b(?:nuev[oa]s?|new|recomienda\w*|recommend\w*|precio|price|cuesta|cost|tienda|store|shop|"
    r"donde|where|deje|perdi|lost|talla|size|lavar|wash|tintoreria)\b"
)
_WEATHER_AMOUNT = (
    r"\b(?:cuant[oa]s|how\s+(?:many|much))\s+"
    r"(?:pulgadas|milimetros|mm|centimetros|grados|inches|millimeters|centimeters|degrees)\b|"
    # MASSIVE weather_query «will it be over ninety degrees tomorrow»: a temperature bound asked about a day.
    r"\b(?:over|above|under|below|more\s+than|less\s+than|mas\s+de|menos\s+de|arriba\s+de|encima\s+de|"
    r"sobre|bajo|por\s+(?:encima|debajo)\s+de)\s+(?:\w+\s+){1,3}?(?:grados|degrees)\b"
)
# Tanda 6b «a la salida del sol mañana… ¿qué hora será?» was answered with tomorrow's sunset: which sun event is
# asked, the rising or the setting, is read apart.
_WEATHER_SUNRISE = (
    # Tanda 4c «la hora exacta de la puesta de sol en Badalona»: «de sol» says the same as «del sol».
    r"\b(?:salida\s+del?\s+sol|amanecer|amanece|amanezca|(?:sale|salga)\s+el\s+sol|sunrise|dawn|"
    r"(?:the\s+)?sun\s+(?:rise|comes?\s+up))\b"
)
_WEATHER_SUNSET = (
    r"\b(?:(?:puesta|caida|entrada)\s+del?\s+sol|atardecer|atardece|anochecer|anochece|"
    # Tanda 6 «cuando se ponga el sol mañana»: the subjunctive says the same sun time.
    r"ocaso|atardezca|anochezca|"
    # M79 (DEV-D v3m s054 «la hora en que comenzará a oscurecerse», s080 «¿a qué hora ya no habrá la luz del sol por
    # las calles hoy?»): the sunset read was answered with the temperature. Getting dark, in any form, and the
    # daylight that ends are the sunset; a screen or a picture that darkens is not.
    r"(?:se\s+)?(?:oscurec(?:e|er|erse|era|eria|iendo|ido|ida|a)|oscurezca)(?!\s+(?:(?:la|el|mi|tu|su|esta|este)\s+)?"
    r"(?:pantalla|monitor|screen|imagen|foto|fondo|ventana|habitacion|pieza|cuarto))|"
    r"se\s+(?:hace|hara|haga|pone|ponga)\s+de\s+noche|"
    r"(?:ya\s+)?no\s+(?:hay|habra|haya|queda|quedara|quede)\s+(?:mas\s+)?(?:la\s+)?luz(?:\s+(?:del?\s+)?(?:sol|dia)|"
    r"\s+natural)|hasta\s+(?:que\s+hora|cuando)\s+(?:hay|habra|queda|dura)\s+(?:la\s+)?luz|"
    r"se\s+(?:pone|ponga|oculta|oculte|esconde|esconda)\s+el\s+sol|sunset|sundown|dusk|nightfall|"
    r"(?:gets?|getting|goes|go|turns?)\s+dark|(?:no\s+more|last)\s+(?:day)?light|daylight\s+(?:ends?|is\s+over)|"
    r"(?:the\s+)?sun\s+(?:sets?|goes?\s+down))\b"
)
_WEATHER_SUN_TIME = f"(?:{_WEATHER_SUNRISE}|{_WEATHER_SUNSET})"
_WEATHER_SUN_ASK = r"\b(?:hora|horas|horario|cuando|when|time|times)\b"
# A time the forecast is asked about. Today and tomorrow are read; a later day is answered with what is read.
WEATHER_WHEN = (
    # Uso real tanda 6 «el weather de esta semana porfa»: the week to come is a time asked about too.
    r"\b(?:(?:esta|la\s+proxima|la\s+siguiente)\s+semana|this\s+week|next\s+week|(?:next|coming)\s+few\s+days|"
    r"hoy|today|tonight|ahora|now|esta\s+(?:noche|tarde|manana)|this\s+(?:morning|afternoon|evening|weekend)|"
    r"manana|tomorrow|pasado\s+manana|fin\s+de\s+semana|finde|weekend|(?:dentro\s+de|en|in)\s+\w+\s+(?:dias|days))\b"
)


def _asks_weather_indirectly(folded: str) -> bool:
    """The weather asked through the gear it calls for, an amount of it, or a sun time (see above)."""

    gear = (
        _has(folded, _WEATHER_GEAR)
        and _has(folded, _WEATHER_GEAR_DECISION)
        and ("?" in folded or _has(folded, WEATHER_WHEN) or _has(folded, _WEATHER_GEAR_ASKED))
        and not _has(folded, _WEATHER_GEAR_ELSEWHERE)
    )
    amount = (
        _has(folded, _WEATHER_AMOUNT)
        and _has(folded, WEATHER_WHEN + r"|\b(?:hace|hara|habra|afuera|outside|getting|expected|caer|caeran|fall)\b")
        # «¿la cpu va a pasar de noventa grados hoy?» is this PC's temperature.
        and not _has(folded, _NOT_WEATHER_TEMPERATURE)
    )
    sun_time = _has(folded, _WEATHER_SUN_TIME) and _has(folded, _WEATHER_SUN_ASK + "|" + WEATHER_WHEN)
    return gear or amount or sun_time


def weather_asks_sun_time(text: str) -> bool:
    """The weather question asks when the sun rises or sets («la caída del sol», «sunset»)."""

    return _has(_fold(text), _WEATHER_SUN_TIME)


def weather_sun_events_asked(text: str) -> frozenset[str]:
    """The sun events the question asks about: ``sunrise``, ``sunset``, both, or none."""

    folded = _fold(text)
    return frozenset(
        event for event, pattern in (("sunrise", _WEATHER_SUNRISE), ("sunset", _WEATHER_SUNSET))
        if _has(folded, pattern)
    )


# Owner 2026-09-24 «tiene que ser conciso… que te responda de una»; tanda-05 «¿Cuál es la tasa de humedad de hoy?»
# was answered with temperature, sky and humidity because the reply had to carry the temperature. One measure
# asked by its name is the answer; the rest of the read is not asked.
_WEATHER_MEASURES = (
    ("humidity", r"\b(?:humedad|humed[oa]|humidity|humid)\b"),
    ("wind", r"\b(?:viento|vientos|ventos[oa]|rachas?|wind|winds|windy|gusts?)\b"),
    ("apparent", r"\b(?:sensacion\s+termica|se\s+siente|feels?\s+like|real\s*feel|wind\s*chill)\b"),
    # Uso real tanda 6: the UV index and the dew point are measures of the same read.
    ("uv", r"\b(?:uv|uvi|ultravioleta|ultraviolet)\b"),
    ("dew_point", r"\b(?:dew\s*points?|punto\s+de\s+rocio|temperatura\s+de\s+rocio)\b"),
    ("temperature", r"\b(?:temperatura|temperature|grados|degrees|(?:que\s+tanto?|cuanto)\s+(?:frio|calor)|"
                    r"how\s+(?:hot|cold|warm|chilly))\b"),
)


def weather_asked_measures(text: str) -> frozenset[str]:
    """The measures of the weather read the question names («humedad», «wind», «sensación térmica», «grados»)."""

    folded = _fold(text)
    return frozenset(name for name, pattern in _WEATHER_MEASURES if _has(folded, pattern))


def weather_asks_later_day(text: str) -> bool:
    """The weather question is about a day after tomorrow («dentro de dos días», «el fin de semana»,
    «pasado mañana»)."""

    folded = _fold(text)
    if weather_asks_past(text):
        # M79 (DEV-D v3m s003): «el fin de semana pasado» is a weekend already gone, not a later day.
        return False
    if _has(folded, r"\b(?:pasado\s+manana|fin\s+de\s+semana|finde|weekend|next\s+week|(?:proxima|siguiente)\s+semana|"
                    r"semana\s+que\s+viene)\b"):
        return True
    counted = re.search(r"\b(?P<count>\w+)\s+(?:dias|days)\b", folded)
    return counted is not None and counted.group("count") not in {"un", "uno", "one", "a", "1"}


# Uso real tanda 6 «cuál es el pronóstico del tiempo para la semana» got today and tomorrow: the week, the coming
# days or a weekly forecast ask the days the read carries after tomorrow (``laterDays``).
_WEATHER_WEEK = (
    r"\b(?:(?:la|esta|toda\s+la|this|the|for\s+the)\s+semana(?!\s+(?:pasada|anterior))|semanal|weekly|"
    r"this\s+week|the\s+week|(?:next|coming)\s+(?:few\s+)?days|(?:proximos|siguientes)\s+dias|dias\s+que\s+vienen|"
    r"resto\s+de\s+la\s+semana|rest\s+of\s+the\s+week|(?:7|siete|seven)\s+(?:dias|days)|7[-\s]?day|"
    r"extended\s+forecast|pronostico\s+extendido|next\s+week|(?:proxima|siguiente)\s+semana|semana\s+que\s+viene)\b"
)


def weather_asks_week(text: str) -> bool:
    """The weather question asks the coming days as a whole («para la semana», «next few days», «weekly»)."""

    return _has(_fold(text), _WEATHER_WEEK)


def weather_asks_coming_days(text: str) -> bool:
    """The weather question is about the days after tomorrow: the week, a later day, or a day named by its
    weekday («¿el sábado podremos comer afuera?»)."""

    return not weather_asks_past(text) and (
        weather_asks_week(text)
        or weather_asks_later_day(text)
        or _has(_fold(text), rf"\b{_WEEKDAY_NAME}\b")
    )


# M79 (DEV-D v3m s003 «El finde pasado, ¿en qué cayó?» → «El fin de semana pasado en Curicó fue despejado con una
# máxima de 17.5 °C…», today's read told as last weekend's): a day already gone is no day of the forecast, which
# starts today. Folded.
_WEATHER_PAST_DAY = (
    r"\b(?:ayer|anteayer|antier|anoche|yesterday|last\s+night|(?:la\s+)?semana\s+pasada|(?:the\s+)?last\s+week|"
    r"hace\s+(?:\d{1,2}|dos|tres|cuatro|cinco|seis|siete|unos\s+dias)\s+dias|(?:\d{1,2}|two|three|four|five|six|seven)"
    r"\s+days\s+ago)\b|" + _LAST_WEEKEND + "|" + _PAST_WEEKDAY
)


def weather_asks_past(text: str) -> bool:
    """The weather question is about a day already gone: yesterday, last night, last weekend, a weekday «pasado»
    (M79)."""

    return _has(_fold(text), _WEATHER_PAST_DAY)


def weather_asked_date(text: str, today: date) -> date | None:
    """The calendar date a weather question names, read from ``today`` (the first day of the read); None when it
    names none.

    M78 (DEV-D v3l p20-t1 «I need weather info for the 1st of March», p20-t2 «…weather info for March 2nd», p21-t1
    «…for Marshall on the 5th»): today's weather was given, once as if it were March 2nd's. A date is a day of the
    forecast or a day it does not reach; either way it is the day asked, never today."""

    said = spoken_date(_fold(text))
    return None if said is None else said.on_or_after(today)


def weather_names_date(text: str) -> bool:
    """The weather question names a calendar date («the 1st of March», «el 5», «March 2nd») (M78)."""

    return spoken_date(_fold(text)) is not None


def weather_asks_later_time(text: str) -> bool:
    """The weather question asks about a time after today: tomorrow, a later day, a weekday, the week or a date
    (M78 DEV-D v3l s048 «Estara alto the air quality the next week?»)."""

    return _weather_asks_tomorrow(text) or weather_asks_coming_days(text) or weather_names_date(text)


_WHAT_IS_THE_WEATHER = (
    r"^[¿?¡!\s]*what\s+(?:is|are)\s+(?:the|today'?s|tomorrow'?s|tonight'?s)\s+(?:weather|forecast|temperature|"
    r"humidity|air\s+quality|air\s+pollution|aqi|pollution\s+levels?|wind|rain|chance\s+of\s+rain)\b"
)


def _weather_lookup_query(text: str) -> str | None:
    """WEB1445: the person's weather request without its request verbs, accents
    kept (the engine answers «va a llover mañana» and «clima hoy», not the folded
    or verb-laden forms); None when the request is not a live weather lookup.
    Tanda 4c: where the person is (``asks_own_place``) is the same read."""

    if asks_own_place(text):
        return text.strip(" \t\r\n¿?¡!.,;:")
    folded = _fold(text)
    indirect = _asks_weather_indirectly(folded) or _forecast_question(folded)
    if not _live_weather_request(folded):
        return None
    if _has(folded, r"^[¿?¡!\s]*(?:que|what)\s+(?:es|son|is|are|significa|means)\b") and not (
        # «what is the weather in Paris», «what is the air quality in Denver» ask it as «what's» does; «qué es el
        # clima», «what is air pollution» ask what the thing is, unless a time to come is named with it.
        _has(folded, _WHAT_IS_THE_WEATHER) or (_has(folded, WEATHER_WHEN) and not _has(folded, r"\b(?:significa|means)\b"))
    ):
        return None
    # WEATHER2023 boundary «qué clima hacía en Buenos Aires en 1990»: the past
    # (a past-tense verb or a year) has no live read; the turn says so instead
    # of reading today's weather.
    if _has(folded, _PAST_WEATHER):
        return None
    query = text.strip(" \t\r\n¿?¡!.,;:")
    query = re.sub(r"^(?:por favor|please)\s*[,:]?\s*", "", query, flags=re.IGNORECASE)
    query = re.sub(
        r"^(?:mostrame|muéstrame|muestrame|muestra|decime|dime|contame|cuéntame|cuentame|"
        r"busca|buscá|buscame|buscar|search|find|show\s+me|tell\s+me|dame|give\s+me|mira|mírame|mirame|fíjate|fijate|"
        r"averigua|chequea|"
        r"necesito|need|quiero|quisiera|me\s+gustaría|me\s+gustaria|i\s+want|i\s+would\s+like)\s+"
        r"(?:saber\s+|to\s+know\s+)?(?:el|la|the|los|las)?\s*",
        "", query, count=1, flags=re.IGNORECASE)
    query = re.sub(
        r"^(?:qué|que|what|cuál|cual|what's|cómo|como|how)\s+(?:es\s+|is\s+|está\s+|esta\s+|estará\s+|estara\s+|va\s+a\s+estar\s+)?"
        r"(?:el\s+|la\s+|the\s+)?"
        r"(?P<noun>clima|tiempo|weather|forecast|pronóstico|pronostico)\s*"
        # «qué tiempo hará en Madrid mañana»: the weather to come asked like the weather now.
        r"(?:hace|hay|hará|hara|va\s+a\s+hacer|habrá|habra|is\s+it\s+like|is\s+it|is|like)?\s*",
        lambda m: m.group("noun") + " ", query, count=1, flags=re.IGNORECASE)
    # «is it going to rain tomorrow» / «will it rain tomorrow»: the auxiliaries
    # never appear in a forecast page; the engine answers «rain tomorrow».
    query = re.sub(r"^(?:is\s+it\s+going\s+to|will\s+it|is\s+it|does\s+it)\s+", "", query, count=1, flags=re.IGNORECASE)
    # WEB1455 «busca en internet el clima»: the medium may precede the noun.
    query = re.sub(r"(?:^|\s+)(?:en|in|on)\s+(?:google|internet|la\s+web|the\s+web)\b\s*", " ", query, flags=re.IGNORECASE)
    query = re.sub(r"^\s*(?:el|la|los|las|the)\s+", "", query, count=1, flags=re.IGNORECASE)
    query = re.sub(r"\s+", " ", query).strip(" ?!.,;:")
    return query if query and (indirect or _names_weather(_fold(query))) else None


_TOPIC_RESEARCH = re.compile(
    r"^[¿?¡!\s]*(?:investiga|investigá|investigar|investigue|investigame|investígame|"
    r"research|look\s+into|look\s+up|"
    # Owner's mother 2026-09-21 «dame info de la migraña»: information about a
    # topic is the same public lookup.
    r"(?:dame|dáme|pasame|pásame|quiero|necesito|busca|buscá|buscame|búscame|give\s+me|find\s+me|i\s+want|i\s+need)\s+"
    r"(?:(?:un\s+poco\s+de|algo\s+de|mas|más|some|more)\s+)?(?:info|informacion|información|datos|information|data))\s+"
    r"(?:(?:en\s+internet|en\s+la\s+web|online|on\s+the\s+internet|on\s+the\s+web)\s+)?"
    r"(?:(?:sobre|acerca\s+de|about|a|de|del|on)\s+)?"
    r"(?P<topic>.+?)"
    r"(?:\s+(?:en\s+internet|en\s+la\s+web|online|on\s+the\s+internet|on\s+the\s+web))?"
    r"\s*[.!?]*$",
    re.IGNORECASE,
)


def _topic_research_query(text: str) -> str | None:
    """WEB1451 «Investiga Spider-Man»: the topic the person asked to research,
    with its own spelling; None when the request is not a research order or
    the topic is a question («investiga qué es…»), a local thing or empty."""

    match = _TOPIC_RESEARCH.match(text.strip())
    if match is None:
        return None
    topic = match.group("topic").strip(" \t\r\n.,;:")
    folded_topic = _fold(topic)
    if not folded_topic or len(topic.encode("utf-8")) > 200:
        return None
    subject = _research_question_subject(text)
    if subject is not None:
        # WEB1481 «Investiga en internet que es el h2o»: the topic is the
        # subject of the question, not the question's words.
        return subject
    if _has(folded_topic, r"^(?:que|quien|quienes|como|cual|cuales|donde|cuando|por\s+que|porque|what|who|how|which|where|when|why)\b"):
        return None
    if _has(folded_topic, r"\b(?:archivos?|files?|carpetas?|folders?|notas?|notes?|documentos?|documents?|mi\s+pc|my\s+pc|este\s+equipo)\b"):
        return None
    if _direct_current_time_request(folded_topic):
        # Tanda 5 «i need information on today's date»: today's date, month or hour is this PC's clock, not a topic.
        return None
    return topic


_RESEARCH_VERBS = (
    r"(?:investiga(?:r|me)?|research|look\s+(?:into|up)|busca(?:r|me)?|search|averigua(?:r|me)?|find\s+out|"
    # Tanda 4 2026-09-24 «find instructions on how to play taboo» was offered back as «Want me to show you…?».
    r"find(?:\s+me)?|encuentra(?:me)?|encontrar)"
)
# «instrucciones para jugar al tabú», «the rules of monopoly», «a tutorial on how to…»: how a thing is done,
# asked by the noun that names its instructions, is looked up like the question itself.
_INSTRUCTIONS_NOUN = (
    r"(?:(?:las|los|la|el|un|unas?|unos|some|the|an?)\s+)?"
    r"(?:instrucciones|instructions|indicaciones|gu[ií]as?|guides?|tutorial(?:es|s)?|pasos|steps|reglas|rules|"
    r"manual(?:es|s)?)\s+"
)
_INSTRUCTIONS_OF = r"(?:on|about|for|to|of|de|del|para|sobre|acerca\s+de)\s+"
_RESEARCH_WH = r"(?:por\s*que|porq\w*|why|como|how|que|what|cual(?:es)?|which|donde|where|cuando|when|quien(?:es)?|who)"


_RESEARCH_LEAD_IN = re.compile(
    r"^[¿?¡!\s]*(?:(?:muy\s+bien|bueno|buenas|mira|sabes|oye|oime|che|hola|ok|okay|escucha|a\s+ver)[,.!\s]+)*"
    r"(?P<lead>[^,.;?!]{3,140}?)\s*[,.;]\s*"
    r"(?:(?:me\s+|te\s+)?(?:puedes|podes|podrias|can\s+you|could\s+you|would\s+you|please)\s+)?"
    rf"(?P<request>{_RESEARCH_VERBS}\b.*)$",
    re.IGNORECASE,
)


_RESEARCH_QUESTION = re.compile(
    r"^[¿?¡!\s]*(?:(?:me\s+|te\s+)?(?:puedes|podes|podrias|can\s+you|could\s+you|would\s+you|please)\s+)?"
    rf"{_RESEARCH_VERBS}\s+"
    r"(?:(?:en\s+internet|en\s+la\s+web|en\s+google|online|on\s+the\s+internet|on\s+the\s+web|the\s+internet|the\s+web)\s+)?"
    r"(?:(?:for|sobre|acerca\s+de|about)\s+)?"
    rf"(?:{_INSTRUCTIONS_NOUN}(?:{_INSTRUCTIONS_OF})?(?={_RESEARCH_WH}\b))?"
    rf"(?P<question>{_RESEARCH_WH}\b.+?|{_INSTRUCTIONS_NOUN}{_INSTRUCTIONS_OF}.+?)\s*[.!?]*$",
    re.IGNORECASE,
)


_RESEARCH_FUNCTION_WORDS = (
    r"\b(?:por\s*que|porq\w*|why|como|how|que|what|cual|cuales|which|donde|where|cuando|when|quien|quienes|who|"
    r"suele|suelen|se|me|te|le|nos|lo|la|los|las|el|un|una|de|del|a|al|en|y|o|falla|fallar|fallan|cae|caer|pasa|pasar|"
    r"funciona|funcionar|anda|andar|no|si|es|esta|estan|hay|tanto|tan|mucho|siempre|does|do|is|are|it|keeps|keep|"
    r"failing|fails|fail|crashing|crashes|crash|working|work|the|so|much|always|often)\b"
)


def _research_question_query(text: str) -> str | None:
    """WEB1831 «me falla mucho whatsapp, puedes investigar en internet porqeu suele
    fallar», «Investigá en internet por qué falla WhatsApp.»: the question the person
    wants researched, in their own words, as the public search query; a
    conversational lead-in supplies the subject when the question names none.
    None for a who/what question (its subject is looked up instead) or a local thing."""

    raw = _strip_request_envelope(text).strip()
    lead = None
    opened = _RESEARCH_LEAD_IN.match(_fold(raw))
    if opened is not None:
        lead = opened.group("lead").strip()
        raw = raw[len(raw) - len(opened.group("request")):] if len(opened.group("request")) <= len(raw) else raw
    question_match = _RESEARCH_QUESTION.match(_fold(raw))
    if question_match is None or _research_question_subject(raw) is not None:
        return None
    folded_question = question_match.group("question").strip(" .!?,;")
    if not folded_question or len(folded_question.encode("utf-8")) > 300:
        return None
    if _has(folded_question, r"\b(?:archivos?|files?|carpetas?|folders?|documentos?|documents?|notas?|notes?|mi\s+pc|my\s+pc|este\s+equipo)\b"):
        return None
    # «averigua cómo quedó el audio del equipo», «find out how computer audio is
    # set»: the state of this machine is read here, not researched online; only
    # a question that names the internet keeps the public search.
    if not _has(_fold(raw), r"\b(?:internet|web|google|online)\b") and _has(
        folded_question,
        r"\b(?:audio|volumen|volume|sonido|sound|brillo|brightness|wifi|wi-fi|bateria|battery|"
        r"ventanas?|windows?|pantalla|screen|cpu|ram|memoria|memory|disco|disk|"
        r"equipo|computer|computadora|computador|ordenador|pc|laptop|notebook|"
        r"maquina|machine|cacharro|aparato|dispositivo|device|contraption|"
        r"(?:este|esta|this)\s+(?:trasto|chisme|bicho|thing|box|rig))\b",
    ):
        return None
    # The person's own spelling: the question as written in the request.
    start = _fold(raw).find(folded_question)
    question = raw[start:start + len(folded_question)].strip(" .!?,;") if start >= 0 and len(_fold(raw)) == len(raw) else folded_question
    content = re.sub(_RESEARCH_FUNCTION_WORDS, " ", folded_question)
    if lead is not None and not re.search(r"\b[a-z0-9]{3,}\b", content):
        # «me falla mucho whatsapp, … porqeu suele fallar»: the question names
        # no subject; the lead-in states it, in the person's words.
        lead_start = _fold(text).find(lead)
        lead_text = text[lead_start:lead_start + len(lead)] if lead_start >= 0 and len(_fold(text)) == len(text) else lead
        return f"{lead_text.strip()} {question}".strip()
    return question


_ENTITY_LOOKUP = re.compile(
    r"^[¿?¡!\s]*"
    # Fase 3.5 (layer C «quiero saber quién es Batman»): a knowledge lead-in before the question.
    r"(?:(?:quiero|quisiera|necesito|me\s+gustar[ií]a)\s+saber\s+|(?:sab[eé]s|sabes|me\s+dec[ií]s|me\s+dices|decime|dime|do\s+you\s+know)\s+|i\s+(?:want|need)\s+to\s+know\s+)?"
    r"(?:"
    r"(?:quien|quién|quienes|quiénes|who)\s+(?:es|fue|era|son|fueron|eran|is|was|are|were)|"
    r"(?:(?:dime|decime|explicame|explícame|contame|cuentame|cuéntame|tell\s+me)\s+)?(?:que|qué|what)\s+(?:es|fue|era|is|was)|"
    r"(?:hablame|háblame|hablarme|contame|cuentame|cuéntame|explicame|explícame|tell\s+me)\s+"
    r"(?:(?:un\s+poco|algo|mas|más|a\s+bit|a\s+little|more)\s+)?(?:de|sobre|acerca\s+de|about)|"
    # Tanda 7 «alexa dime todo lo que sabes sobre bob dean»: what he knows about a name asks who or what it is.
    r"(?:(?:dime|decime|cuentame|cuéntame|contame)\s+)?(?:todo\s+)?(?:lo\s+que|que|qué)\s+"
    r"(?:sabes|sab[eé]s|conoces|conoc[eé]s|me\s+puedes\s+(?:decir|contar))\s+(?:de|sobre|acerca\s+de)|"
    r"(?:tell\s+me\s+)?(?:everything|all|what)\s+(?:do\s+)?you\s+know\s+about|what\s+can\s+you\s+tell\s+me\s+about"
    r")\s+(?P<entity>[^?¿!¡]+?)\s*[.!?¿¡=\s]*$",
    re.IGNORECASE,
)


def _entity_lookup_query(text: str) -> str | None:
    """KNOWLEDGE1473 «¿Quién es Daredevil?», «Que es doom eternal=», «Hablame
    un poco de Marvel vs. Capcom.»: the named thing the person asks about, with
    its own spelling, when who or what it is can be looked up in public pages;
    None for a definition with an article («qué es una GPU»), the assistant or
    the person («quién eres», «quién es de verdad»), a possessed or pointed
    thing («quién es mi mamá», «qué es este archivo»), a word's meaning, a
    local thing, or a question folded into the name («…, quien gana?»)."""

    # «alexa, quién es…», «oye dime qué sabes de…»: an address before the question is not part of it.
    match = _ENTITY_LOOKUP.match(_without_address(text) or text.strip())
    if match is None:
        return None
    entity = match.group("entity").strip(" \t\r\n.,;:")
    # cien-39 073 «what is cache memory, one sentence»: the length the person
    # asks for is not part of the name. It travelled inside the entity, the
    # public search was made for that whole string, and the page found was a
    # grammar site about using the phrase in a sentence, cited as the source.
    entity = re.sub(
        r"[,;]?\s*(?:in|en)?\s*(?:one|a|1|una?)\s+(?:short\s+)?"
        r"(?:sentence|line|phrase|frase|linea|oracion)\s*[.!?]*$|"
        r"[,;]?\s*(?:briefly|brevemente|en\s+corto|nada\s+mas|solo\s+eso)\s*[.!?]*$",
        "",
        entity,
        flags=re.IGNORECASE,
    ).strip(" \t\r\n.,;:")
    folded_entity = _fold(entity)
    if not folded_entity or not re.search(r"[a-z]", folded_entity):
        return None
    if re.fullmatch(ARITHMETIC_EXPRESSION, folded_entity):
        # MASSIVE qa_maths «what is four plus five»: a sum is worked out, not looked up.
        return None
    if len(entity.encode("utf-8")) > 80 or len(folded_entity.split()) > 8:
        return None
    if _has(folded_entity, r"^(?:un|una|unos|unas|a|an|el|la|los|las|the|lo)\b"):
        return None
    if _has(
        folded_entity,
        # «tell me what is currently playing», «dime qué es lo que está sonando»:
        # a state of this PC, not a named thing to look up.
        r"^(?:currently|now|actualmente|ahora|playing|sonando|reproduciendo|open|abierto|abierta|"
        r"running|corriendo|going\s+on|happening|pasando|on|up|today|hoy|wrong|mal)\b",
    ):
        return None
    if _has(
        folded_entity,
        r"^(?:tu|vos|usted|ustedes|ti|yo|el|ella|ellos|ellas|nosotros|nosotras|you|yourself|myself|me|i|he|she|"
        r"they|it|esto|eso|esta|este|ese|esa|aquel|aquello|aquella|this|that|these|those|"
        r"mi|mis|tus|su|sus|nuestro|nuestra|nuestros|nuestras|my|your|his|her|their|our|"
        r"de\s+verdad|realmente|really|en\s+realidad)\b",
    ) or names_own_data(folded_entity):
        # Tanda 3 «quién es antonia»: someone of the person's own life is not in public pages.
        return None
    if _has(
        folded_entity,
        r"\b(?:que|quien|quienes|como|cual|cuales|donde|cuando|por\s+que|porque|"
        r"what|who|how|which|where|when|why)\b",
    ):
        return None
    # cien-36 032 «who is speaking»: a bare present participle after «who is»
    # is a predicate, not a name. Read as an entity it sent the turn to a
    # public page about the language skill «speaking», while the Spanish
    # «quién está hablando» answered with the assistant identity (089).
    if _has(
        folded_entity,
        r"^(?:speaking|talking|writing|typing|answering|replying|responding|"
        r"listening|calling|asking|reading|hablando|escribiendo|respondiendo|"
        r"contestando|escuchando|llamando|preguntando|leyendo)$",
    ):
        return None
    if _has(
        folded_entity,
        r"\b(?:bax[yi]|olly|alexa|siri|asistente|assistant|palabra|word|significa|"
        r"significado|definicion|define|definition|meaning|means|archivos?|files?|"
        r"carpetas?|folders?|notas?|notes?|documentos?|documents?|mi\s+pc|my\s+pc|"
        r"este\s+equipo|ventanas?|windows?|pantalla|screen|volumen|volume|brillo|"
        r"brightness|bluetooth|wifi|red|bateria|battery|procesos?|process(?:es)?|"
        r"programas?|apps?|aplicaci(?:on|ones)|calculadora|portapapeles|clipboard|"
        r"alarmas?|alarms?|timers?|temporizador|recordatorios?|reminders?|hora|fecha|"
        r"clima|tiempo|weather|noticias?|news)\b",
    ):
        return None
    return entity


# Fase 3.5 (owner test 2026-09-21 turns 23, 35, 58; real log): what people think of a public work
# and a record or dated fact are answered from public pages, never from the model's memory. A
# question about quality («¿la nueva peli de X es buena?», «¿X vale la pena?», «qué piensa la gente
# de X», «reseñas de X», «is X any good») looks up opinions of X; «cuál fue el primer libro de
# zombies», «cuándo sale X» looks up the question. Personal, deictic and local things are not public.
_TALK_OPENING = r"^[¿?¡!\s]*(?:(?:y|e|entonces|che|oye|oime|bueno|pero|ah|and|so|hey)[\s,]+)*"
# A lookup verb before the question asks for the same lookup («fijate cuándo sale…», «averiguá qué
# dijo la crítica de X»; held-out 14/16 after the dialogue slot names the topic). Tanda 4 2026-09-24
# «Hola, me podrías decir cuántas copas mundiales…»: a greeting or a courteous ask («¿me puedes
# decir…?», «quisiera saber», «do you know», «can you tell me») before the question asks the same
# question.
_ASK_LEAD = (
    r"^[¿¡\s]*(?:(?:hola|buenas|buenos\s+dias|buenas\s+(?:tardes|noches)|hi|hello|hey|oye|oiga|baxy|por\s+favor|porfa|"
    r"please|una\s+(?:pregunta|duda)|por\s+curiosidad|just\s+curious|quick\s+question)[\s,:;.!]+|"
    r"(?:(?:fijate|fijese|averigua|averiguame|investiga|investigame|busca|buscame|decime|dime|digame|"
    r"cuentame|contame|sabes|sabe|sabias|conoces|check|find\s+out|look\s+up|tell\s+me|let\s+me\s+know|"
    r"(?:me\s+)?(?:puedes|podes|podrias|podria|puede)\s+(?:decir(?:me)?|contar(?:me)?|explicar(?:me)?)|"
    r"(?:me\s+)?(?:dices|decis|dirias)|(?:quiero|quisiera|queria|me\s+gustaria|necesito)\s+saber|"
    r"(?:can|could|would)\s+you\s+(?:please\s+)?(?:tell\s+me|explain(?:\s+to\s+me)?)|do\s+you\s+know|"
    r"i\s+(?:want|would\s+like|need)\s+to\s+know|i['’]?d\s+like\s+to\s+know)"
    r"[\s,:]+(?:si\s+|if\s+|whether\s+)?))"
)


def _question_body(text: str) -> str:
    """The folded question without the talk and courtesy said before it."""

    folded = re.sub(_TALK_OPENING, "", _fold(text))
    for _ in range(4):
        stripped = re.sub(_ASK_LEAD, "", folded, count=1)
        if stripped == folded:
            break
        folded = stripped
    return folded.strip(" ¿?¡!.,")


# Tanda 4 2026-09-24 «Cuál es la edad promedio que vive un ser humano?» → «Eso no lo hago.»: a question for
# information is answered or looked up, never refused (00_IDENTIDAD: dice que no sólo a lo que no sabe hacer).
# Its form: an interrogative opens it once the talk and the courteous ask before it are set aside, or it is a
# yes/no question about how things are, or an order to tell or explain («dime…», «explícame…», «tell me…»).
_INFORMATION_HEAD = (
    r"^(?:que|cual|cuales|quien|quienes|cuando|donde|adonde|como|cuanto|cuanta|cuantos|cuantas|por\s*que|"
    r"para\s+que|de\s+(?:que|quien|donde)|en\s+que|a\s+que|desde\s+cuando|hace\s+cuanto|"
    r"esta|estan|is|are|what|what['’]s|which|who|who['’]s|whom|whose|when|where|how|why)\b"
)
_YES_NO_WORLD_HEAD = r"^(?:es|son|era|eran|fue|fueron|hay|habia|existe|existen|is|are|was|were|does|do|did|has|have)\b"
_TELL_ORDER = (
    r"^[¿¡\s]*(?:(?:hola|oye|hey|baxy|por\s+favor|please)[\s,:;.!]+)*"
    r"(?:dime|decime|digame|cuentame|contame|explicame|explica|define|definime|describe|describeme|"
    r"tell\s+me|explain|let\s+me\s+know)\b"
)


def asks_for_information(text: str) -> bool:
    """Whether the message asks for information (its form only; whose information it is is read elsewhere)."""

    body = _question_body(text)
    return (
        _has(body, _INFORMATION_HEAD)
        or (bool(re.search(r"[?¿]", text)) and _has(body, _YES_NO_WORLD_HEAD))
        or _has(_fold(text), _TELL_ORDER)
    )
_WORK_NOUN = (
    r"\b(?:peli|pelis|pelicula|peliculas|serie|series|libro|libros|novela|novelas|saga|juego|juegos|videojuego|"
    r"videojuegos|disco|album|temporada|documental|anime|manga|comic|obra|show|movie|movies|film|films|book|"
    r"books|novel|game|games|season|documentary|record)\b"
)
_NOT_PUBLIC_WORK = (
    r"^(?:mi|mis|tu|tus|su|sus|nuestro|nuestra|este|esta|estos|estas|ese|esa|eso|esto|aquel|aquella|lo|"
    r"my|your|our|this|that|these|those|it)\b|"
    r"\b(?:archivos?|carpetas?|notas?|tareas?|recordatorios?|ventanas?|pestanas?|descargas?|capturas?|mensajes?|"
    r"correos?|alarmas?|codigo|programa|pc|computadora|equipo|baxy|files?|folders?|notes?|windows?|tabs?|code)\b"
)
_ASKED_OPINION = (
    r"^(?:(?:crees|cree|pensas|piensas|te\s+parece|sabes|me\s+decis|me\s+dices)\s+(?:que|si)\s+|do\s+you\s+think\s+)"
)
# (form, needs a work noun, needs to be asked): «el juego es malo» is the person's own opinion.
_OPINION_FORMS = (
    # «la nueva peli de X es buena», «X es tan buena como dicen»: needs a work noun.
    (r"(?P<work>.+?)\s+(?:es|son|esta|estan|sera|seran|fue|salio)\s+(?:(?:muy|tan|re|bastante|igual\s+de)\s+)?"
     r"(?:buen[oa]s?|mal[oa]s?|recomendables?|decentes?|entretenid[oa]s?)(?:\s+(?:como\s+dicen|o\s+no))?", True, True),
    (r"(?P<work>.+?)\s+(?:vale|valen)\s+la\s+pena(?:\s+(?:verla|verlo|leerlo|leerla|jugarlo|jugarla|escucharlo))?",
     False, True),
    (r"vale\s+la\s+pena\s+(?:ver|leer|jugar|escuchar|mirar)\s+(?P<work>.+)", False, True),
    (r"(?:que|como)\s+(?:piensa|opina|dice|dicen|dijo|dijeron|opinan|piensan)\s+(?:la\s+gente|el\s+publico|"
     r"la\s+critica|los\s+criticos|los\s+fans)\s+(?:de|del|sobre|acerca\s+de)\s+(?P<work>.+)", False, False),
    (r"(?:resenas|criticas|opiniones|reviews)\s+(?:de|del|sobre|of|for|on)\s+(?P<work>.+)", False, False),
    (r"(?:is|are|was)\s+(?P<work>.+?)\s+(?:any\s+good|good|bad|worth\s+(?:it|watching|reading|playing|the\s+hype))",
     False, False),
    (r"what\s+do\s+(?:people|critics|fans)\s+(?:think|say)\s+(?:of|about)\s+(?P<work>.+)", False, False),
)


def _original_words(text: str, folded_part: str) -> str:
    folded_text = _fold(text)
    start = folded_text.find(folded_part)
    if start < 0 or len(folded_text) != len(text):
        return folded_part
    return text[start:start + len(folded_part)]


def public_opinion_query(text: str) -> str | None:
    """«¿La nueva peli de Resident Evil es buena?» → «nueva peli de Resident Evil opiniones»; None otherwise."""

    found = _public_opinion_work(text)
    if found is None:
        return None
    work, english = found
    return f"{work} {'reviews' if english else 'opiniones'}"


def public_opinion_subject(text: str) -> str | None:
    """The public work an opinion question is about, in the person's words («nueva peli de Resident Evil»)."""

    found = _public_opinion_work(text)
    return None if found is None else found[0]


def _public_opinion_work(text: str) -> tuple[str, bool] | None:
    folded = _question_body(text)
    asked = re.match(_ASKED_OPINION, folded) is not None or "?" in text or "¿" in text
    folded = re.sub(_ASKED_OPINION, "", folded)
    for form, needs_work_noun, needs_to_be_asked in _OPINION_FORMS:
        match = re.fullmatch(form, folded)
        if match is None:
            continue
        work = re.sub(r"^(?:el|la|los|las|the)\s+", "", match.group("work").strip(" ,.")).strip()
        if not work or len(work.split()) > 10 or _has(work, _NOT_PUBLIC_WORK) or (needs_to_be_asked and not asked):
            return None
        if needs_work_noun and not _has(work, _WORK_NOUN):
            return None
        if not re.sub(_WORK_NOUN, " ", work).strip():
            # «¿el juego es bueno?»: a bare noun names no work to look up.
            return None
        english = form.startswith((r"(?:is|are", r"what\s+do")) or folded.startswith("reviews")
        return _original_words(text, work).strip(), english
    return None


_RECORD_FACT = re.compile(
    r"(?:(?:cual|quien)\s+(?:fue|es|era)\s+(?:el|la)\s+(?:primer[oa]?|1er[oa]?|1ra|1°|ultim[oa]|mas\s+\w+|"
    r"mejor|peor)\s+\S.*|"
    r"cuando\s+(?:sale|salio|saldra|se\s+estrena|se\s+estreno|estrenan|estrenaron|lanzan|lanzaron|"
    r"sale\s+la\s+nueva|sale\s+el\s+nuevo)\s+\S.*|"
    r"(?:what|who|which)\s+(?:was|is)\s+the\s+(?:first|last|latest|newest|oldest|best|worst|most\s+\w+)\s+\S.*|"
    r"when\s+(?:does|did|will)\s+\S.*\s+(?:come\s+out|release|premiere|launch))"
)

# Tanda 4 2026-09-24 «¿cuántas copas mundiales de fútbol tiene Argentina?» → «2» (they are 3). A tally of
# what is won or held (titles, cups, awards, medals, goals, followers), a population, a price, who holds a
# title or a record now, who won the last edition and what is the next one change with the calendar: the
# model's memory is stale by construction, so they are looked up like a release date. Arithmetic, units and
# the person's own things are not (``record_fact_query`` excludes them).
_WON_THING = (
    r"(?:copas?\s+(?:del\s+mundo|mundiales|america|libertadores|sudamericanas?|continentales|intercontinentales|"
    r"de\s+(?:europa|america|asia|africa|oro|campeones|la\s+liga|liga|el\s+rey|la\s+reina|confederaciones))|"
    r"mundiales|titulos|campeonatos|trofeos|premios|oscars?|oscares|grammys?|emmys?|globos\s+de\s+oro|"
    r"balones\s+de\s+oro|botas\s+de\s+oro|medallas(?:\s+(?:de\s+)?(?:oro|plata|bronce|olimpicas))?|goles|"
    r"asistencias|anillos|champions|ligas|libertadores|super\s*bowls?|finales|victorias|triunfos|records|"
    r"nominaciones|seguidores|suscriptores|habitantes|grand\s+slams?|podios|poles|"
    r"world\s+cups?|titles|championships|trophies|awards|golden\s+globes|ballon\s+d['’]?ors?|medals|"
    r"gold\s+medals|goals|assists|rings|wins|victories|nominations|followers|subscribers|inhabitants|majors|"
    r"podiums|pole\s+positions)"
)
_COMPETITION = (
    r"(?:(?<!guerra\s)mundial|copa\s+(?:del\s+mundo|mundial|america|libertadores|sudamericana|del\s+rey)|champions(?:\s+league)?|"
    r"liga|eurocopa|libertadores|super\s*bowl|nba|nfl|mlb|nhl|formula\s*(?:1|uno)|f1|motogp|tour\s+de\s+francia|"
    r"roland\s+garros|wimbledon|us\s+open|abierto\s+de\s+\w+|gran\s+premio(?:\s+de\s+\w+)?|oscars?|grammys?|"
    r"emmys?|balon\s+de\s+oro|premio\s+nobel|nobel(?:\s+de\s+\w+)?|eurovision|elecciones|clasico|final|"
    r"world\s+cup|champions\s+league|euro(?:s|\s+\d{4})?|stanley\s+cup|world\s+series|grand\s+prix|"
    r"ballon\s+d['’]?or|nobel\s+(?:prize|peace\s+prize)|election|elections|finals?|masters|tour\s+de\s+france)"
)
_CHANGING_FACT = re.compile(
    # A tally: «cuántas copas del mundo tiene Argentina», «how many Grammys has Beyoncé won».
    rf"(?:cuant[oa]s|how\s+many)\s+(?:de\s+)?{_WON_THING}\b\s*\S.*|"
    r"(?:cuantas\s+veces|how\s+many\s+times)\s+(?:\S+\s+){0,6}"
    r"(?:gano|ganado|ganaron|han\s+ganado|ha\s+ganado|fue\s+campeon|salio\s+campeon|won|win)\b.*|"
    r"cuantas\s+copas\s+(?:\S+\s+){0,4}(?:gano|ganado|ganaron|conquisto|levanto)\b.*|"
    # A population.
    r"(?:cuant[oa]s\s+(?:personas|habitantes)|cuanta\s+gente)\s+(?:viven|vive|hay|tiene)\s+\S.*|"
    r"(?:cual\s+es\s+|what\s+is\s+|what['’]?s\s+)?(?:la\s+poblacion|the\s+population)\s+(?:actual\s+|current\s+)?"
    r"(?:de|del|of)\s+\S.*|how\s+many\s+people\s+(?:live|are\s+there|are\s+living)\s+\S.*|"
    # A price.
    r"cuanto\s+(?:cuesta|cuestan|vale|valen)\s+(?!la\s+pena\b)(?:el|la|los|las|un|una|unos|unas)?\s*\S.*|"
    r"(?:cual\s+es\s+|what\s+is\s+|what['’]?s\s+)?(?:el\s+precio|the\s+(?:current\s+)?price)\s+(?:actual\s+)?"
    r"(?:de|del|of)\s+\S.*|"
    r"how\s+much\s+(?:does|do)\s+\S.*\s+cost|how\s+much\s+(?:is|are)\s+(?:a|an|the)\s+\S.*|"
    # Who holds a title or a record now, who won the last or a named edition, what is the next one.
    r"(?:quien|quienes|que\s+\w+)\s+(?:es|son|va|van)\s+(?:el|la|los|las)\s+"
    r"(?:(?:actual(?:es)?|vigente|reinante|nuev[oa])\s+\S.*|\S+(?:\s+\S+)?\s+(?:actual(?:es)?|vigente|reinante)\b.*)|"
    rf"(?:quien|quienes|que\s+\w+)\s+(?:gano|ganaron|se\s+llevo|se\s+llevaron|conquisto|ganara)\s+"
    rf"(?:el|la|los|las)\s+(?:ultim[oa]s?\s+|pasad[oa]s?\s+|mas\s+recientes?\s+)?(?:\w+\s+){{0,2}}{_COMPETITION}\b.*|"
    r"(?:quien|quienes|que\s+\w+)\s+(?:tiene|tienen|ostenta|posee|lleva|llevan)\s+(?:el\s+)?(?:record|mas|mayor)\b.*|"
    r"(?:quien|quienes|cual|cuales|que)\s+(?:es|son|fue|fueron)\s+(?:el|la|los|las)\s+(?:\w+\s+){1,3}"
    r"(?:mas|menos)\s+\w+\s+(?:del|de\s+la|de)\s+(?:mundo|historia|planeta|universo|pais)\b.*|"
    r"(?:quien|quienes)\s+(?:es|son|fue)\s+(?:el|la)\s+(?:maxim[oa]|mayor)\s+\w+.*|"
    r"(?:cual|cuando|donde|que)\s+(?:es|son|sera|seran|se\s+juega|juega|sale)\s+(?:el|la|los|las)\s+"
    r"(?:proxim[oa]s?|siguiente)\s+\S.*|"
    r"who(?:\s+is|['’]s|\s+are)\s+the\s+(?:current|reigning|present|sitting|incumbent|new)\s+\S.*|"
    rf"(?:who|which\s+\w+)\s+won\s+the\s+(?:last\s+|latest\s+|most\s+recent\s+|\d{{4}}\s+)?(?:\w+\s+){{0,2}}"
    rf"{_COMPETITION}\b.*|"
    r"who\s+(?:holds|has|owns)\s+the\s+(?:world\s+|all[\s-]time\s+)?record\b.*|who\s+has\s+(?:the\s+)?most\s+\S.*|"
    r"(?:who|what|which)(?:\s+(?:is|are|was)|['’]s)\s+the\s+(?:\w+\s+){0,2}(?:\w+est|most\s+\w+|best[\s-]selling)\s+"
    r"\S.*\b(?:in\s+the\s+world|ever|in\s+history|of\s+all\s+time|on\s+earth)\b.*|"
    r"when\s+is\s+the\s+next\s+\S.*|what\s+is\s+the\s+next\s+\S.*"
)
# Whose tally or price it is: the person's own («cuántos goles metí», «how many followers do I have»), in the first
# person, is theirs and never a lookup (``names_own_data`` reads the possessives).
_FIRST_PERSON_TALLY = (
    r"\b(?:tengo|tenemos|llevo|llevamos|meti|metimos|marque|marcamos|gane|ganamos|hice|hicimos|me|nos|"
    r"i|we|us)\b"
)
# Things of this PC and of BAXY's stores are read on the PC, never priced or counted on the web.
_LOCAL_THING = (
    r"\b(?:archivos?|carpetas?|notas?|tareas?|recordatorios?|ventanas?|pestanas?|descargas?|capturas?|mensajes?|"
    r"correos?|alarmas?|pc|computadora|ordenador|baxy|files?|folders?|notes?|tasks?|windows?|tabs?|emails?)\b"
)


# --- The person's own data (00_IDENTIDAD: information comes in, the person's content never goes out) ----------
# Tanda 3 2026-09-24 «es cierto que el cumpleaños de antonia es el primero de marzo» and «what do i have to do on
# january 1st» were sent to the web. What the person has, did, has to do or owns, the people of their own life and
# this PC are never a public lookup, whatever a guard reads. Five signals, each general:
# 1. first person possession or experience («mi», «my», «did i», «am i», «i have to», «tengo que», «qué tengo»,
#    «me toca», a first person past «hice», «dije», «fui»);
_FIRST_PERSON_OWN = (
    r"\b(?:mi|mis|mio|mia|mios|mias|my|mine|nuestr[oa]s?|our|ours)\b|"
    r"\bdid\s+i\b|\b(?:am|was)\s+i\b|\bwhat\s+(?:do|did|will)\s+i\s+have\b|"
    r"\bhave\s+i\s+(?:got|been|paid|sent|called|finished|done|booked|made|received|missed|scheduled|planned|saved)\b|"
    r"\bdo\s+i\s+have\s+(?:any|anything|something|plans?|meetings?|events?|appointments?|class(?:es)?|work|school|"
    r"homework|tasks?|reminders?|alarms?|a\s+(?:meeting|call|date|appointment|class|test|exam|reservation))\b|"
    r"\bi(?:\s+have|\s+had|['’]ve|\s+got)\s+(?:got\s+)?to\b|\bi\s+gotta\b|"
    r"\b(?:tengo|tenia|tuve|tenemos|teniamos|tendre)\s+que\b|\bque\s+(?:tengo|tenemos|tenia)\b|"
    r"\btengo\s+(?:algo|algun[oa]?|pendientes?|planes?|citas?|reuniones?|clases?|examen(?:es)?|turno|tareas?|"
    r"libre|hora)\b|\btengo[\s?.!]*$|\b(?:me|nos)\s+toca(?:ba)?\b|\b(?:estoy|estare)\s+(?:libre|ocupad[oa])\b|"
    r"\b(?:hice|dije|puse|tuve|fui|estuve|pedi|recibi|perdi|escribi|anote)\b|"
    # 742 H0604 «Como me llamo», H0173 «que me gusta tomar.» went to the web: who the person is and what they
    # like are theirs, never a page's.
    r"\b(?:como|cual)\s+me\s+llamo\b|\bque\s+me\s+gusta(?:n|ba|ria)?\b|\bwhat\s+do\s+i\s+(?:like|love|prefer)\b|"
    r"\b(?:donde|where)\s+(?:vivo|do\s+i\s+live)\b|\bcuantos\s+anos\s+tengo\b"
)
# 2. a relative, named as the person names their own («mom», «grandma's», «la abuela»), but not someone else's
#    («la mamá de Messi», «Taylor Swift's mom»);
_OWN_RELATIVE = (
    r"(?<!['’]s\s)\b(?:mom|mommy|mum|dad|daddy|grandma|grandpa|granny|mami|papi|abuelita|abuelito)\b"
    r"(?!\s+(?:de|del|of)\b)|"
    r"\b(?:el|la|los|las|al|del|the)\s+(?:abuel[oa]s?|suegr[oa]s?|tias?|tios?|cunad[oa]s?|sobrin[oa]s?|niet[oa]s?|"
    r"mama|novi[oa]|espos[oa]|marido|wife|husband|kids|grandma|grandpa|in-laws?)\b(?!\s+(?:de|del|of)\b)"
)
# M81 (DEV-D v3m D-s020 «It's going to rain en la casa de mamá?» → the whole sentence to the web): «mamá» and «papá»
# said bare, written with their accent, name the person's own mother or father («la casa de mamá», «llamé a papá»);
# folded they would be «mama» (a breast, «cáncer de mama») and «papa» (the pope, a potato), so they are read unfolded.
# Someone else's («la mamá de Messi») is not.
_OWN_PARENT_ACCENTED = r"\b(?:mamá|papá|mamita|papito)\b(?!\s+(?:de|del)\b)"
# 3. this PC or device;
_THIS_DEVICE = (
    r"\b(?:este|esta|this)\s+(?:pc|equipo|computador(?:a)?|ordenador|laptop|portatil|notebook|maquina|machine|"
    r"computer|device|dispositivo|celular|telefono|phone)\b"
)
# 4. someone named by a bare given name (lexicon.GIVEN_NAMES): not a full name («Jennifer Lopez», «Pedro de
#    Valdivia», «Juan Pablo II»), not after a title («el papa Francisco», «queen Elizabeth», «San Juan»), and not in
#    talk about public works or fame, where a name is a title or a character («quién escribió Romeo y Julieta»).
_NAME_TITLES = frozenset(
    "san santa santo saint st sor fray papa pope rey reina king queen principe princesa prince princess presidente "
    "presidenta president don dona sir lady lord emperador emperatriz emperor empress general capitan captain "
    "profeta prophet apostol virgen beato".split()
)
_SURNAME_PARTICLES = frozenset("de del da di van von le".split())
# M81 (DEV-D v3m D-s053 «¿Miguel sigue viviendo en Arkansas?» went to the web): whether someone still lives, works or
# goes somewhere («sigue», «anda», «keeps») is about a person of the person's life, like «vive» or «still».
_AFTER_A_BARE_NAME = frozenset(
    """
    es era fue sera esta estaba estuvo tiene tenia tuvo cumple cumplio vive vivia trabaja trabajo llamo llama llego
    llega viene vino dijo dice quiere queria puede va iba sale salio se casa caso muda mudo hizo hace regalo debe
    me te le les lo la los las nos y e o u ni que en a al con para por sin sobre hoy manana ayer ya no si mas tambien
    is was will would has had have does did do and or but of in on at to for with from by about today tomorrow
    yesterday said says called calls call told tells wants want can could should turns turned turn lives lived live
    works worked work got gets get coming came comes come moved married like likes think thinks need needs still also
    too really ever again not this that the a an my me him her say tell go send text ask know bring meet visit
    sigue seguia siguio anda andaba keeps kept
    """.split()
)
_WORK_OR_FAME = (
    r"\b(?:peli|pelis|pelicula|peliculas|serie|series|libro|libros|novela|cancion|canciones|song|songs|album|disco|"
    r"obra|show|movie|movies|film|films|book|books|novel|personaje|character|escribio|wrote|written|pinto|painted|"
    r"dirigio|directed|compuso|composed|canta|sings|sang|protagoniza|stars|starring|actor|actriz|actress|cantante|"
    r"singer|autor|autora|author|jugador|jugadora|player|futbolista|famos[oa]s?|famous|celebrity|youtuber|streamer|"
    r"influencer|rapper|rapero|banda|band)\b"
)
_WORD = re.compile(r"[a-z0-9]+(?:['’]s\b)?")
# 5. an event of the person's agenda (uso real 2026-09-24): named as theirs without «mi»
#    (``notes.own_event_reference``: «la reunión de ayer», «cuándo está programada la boda»), one they have or will
#    go to («tengo un vuelo el quince», «i have a birthday on monday», «quiero ir al cumpleaños de Sally»), or any
#    meeting said with an indefinite article («necesito prepararme para una reunión»), which no public page is about.
_OWN_EVENT_SAID = (
    r"\b(?:tengo|tenemos|tendre|tenia|i\s+have|we\s+have|i['’]?ve\s+got|i\s+had)\s+(?:(?:un|una|el|la|a|an|the)\s+)?"
    rf"(?:\w+\s+)?(?:{OWN_EVENT_NOUN}|vuelo|flight|viaje|trip)\b|"
    r"\b(?:quiero|voy\s+a|tengo\s+que|i\s+want\s+to|i['’]?m\s+going\s+to|i\s+need\s+to)\s+(?:ir|go)\s+"
    rf"(?:a|al|a\s+la|to)\s+(?:(?:the|la|el|mi|my)\s+)?(?:\w+\s+)?{OWN_EVENT_NOUN}\b|"
    r"\b(?:un|una|a|an)\s+(?:\w+\s+)?(?:reunion|meeting|appointment)\b"
)


def _bare_given_name(folded: str) -> bool:
    if _has(folded, _WORK_OR_FAME):
        return False
    words = _WORD.findall(folded)
    bare = [re.sub(r"['’]s$", "", word) for word in words]
    for index, name in enumerate(bare):
        if name not in GIVEN_NAMES or (index and (bare[index - 1] in _NAME_TITLES or bare[index - 1] in GIVEN_NAMES)):
            continue
        following = bare[index + 1] if index + 1 < len(bare) else None
        if words[index] != name or following is None:
            return True
        if following in GIVEN_NAMES:
            continue
        if following in _SURNAME_PARTICLES and index + 2 < len(bare) and bare[index + 2] not in _AFTER_A_BARE_NAME:
            continue
        if following in _AFTER_A_BARE_NAME or following in _SURNAME_PARTICLES:
            return True
    return False


def names_own_data(text: str) -> bool:
    """Whether a request asks about the person's own data: their things, plans or past, their relatives, a person of
    their life named by a given name, this PC, or an event of their agenda (see above). Where the person is («cerca
    de mí», «en mi zona», «near me») is not their data: a place near them is looked up
    (``_location_recommendation_request``)."""

    folded = re.sub(_NEAR_THE_PERSON, " ", _fold(text))
    # «what's grandma's birthday»: a contracted «is» is not a possessive.
    folded = re.sub(r"\b(what|that|it|who|where|when|how|there|here|he|she)['’]s\b", r"\1 is", folded)
    return (
        re.search(_OWN_PARENT_ACCENTED, unicodedata.normalize("NFC", str(text or "")).casefold()) is not None
        or _has(folded, _FIRST_PERSON_OWN)
        or _has(folded, _OWN_RELATIVE)
        or _has(folded, _THIS_DEVICE)
        or _bare_given_name(folded)
        or own_event_reference(folded)
        or _has(folded, _OWN_EVENT_SAID)
    )


# Uso real 2026-09-23 «cuantos años tiene jennifer lopez» → «53 años en 2024»,
# «quién es el presidente de chile» → a president out of office: a person's age
# and who holds an office today change with the calendar, so the model's memory
# is stale by construction. Both are looked up, like a record or a release date.
_PERSON_FACT = re.compile(
    r"(?:cuantos\s+anos\s+tiene|que\s+edad\s+tiene|cual\s+es\s+la\s+edad\s+de|"
    r"how\s+old\s+is|what\s+age\s+is|what(?:\s+is|'s|’s)\s+the\s+age\s+of)\s+(?P<person>\S.*)|"
    r"(?:quien|who)\s+(?:es|is|son|are)\s+"
    r"(?P<office>(?:(?:el|la|los|las|the)\s+)?(?:actual(?:es)?\s+|current\s+)?"
    r"(?:presidente|presidenta|president|vicepresidente|vicepresidenta|vice\s+president|"
    r"primer\s+ministro|primera\s+ministra|prime\s+minister|rey|reina|king|queen|papa|pope|canciller|"
    r"chancellor|gobernador|gobernadora|governor|alcalde|alcaldesa|mayor|ceo|jefe\s+de\s+estado|"
    r"head\s+of\s+state|dueno|duena|owner|entrenador|entrenadora|coach|dt|campeon|campeona|champion)"
    r"(?:\s+actual)?\s+(?:de|del|of|en)\s+\S.*)"
)
# Who the age is asked of: nobody named («él», «she») or BAXY is not a public person; nor is anyone of the
# person's own life (``names_own_data``: «mi hijo», «antonia»).
_NOT_A_PUBLIC_PERSON = (
    r"^(?:el|ella|ellos|ellas|usted|he|she|him|her|they|them|it|eso|esto|that|this)$|"
    r"^(?:tu|tus|your)\b|\b(?:bax[yi]|asistente|assistant|ia|ai)$"
)


def person_fact_subject(text: str) -> str | None:
    """«cuántos años tiene Jennifer López» → «Jennifer López»; «quién es el presidente de
    Chile» → «el presidente de Chile»; None when the question is not about a public person."""

    folded = _question_body(text)
    match = _PERSON_FACT.fullmatch(folded)
    if match is None or len(folded.split()) > 16:
        return None
    subject = (match.group("person") or match.group("office") or "").strip(" ,.")
    if (
        not subject
        or _has(subject, _NOT_A_PUBLIC_PERSON)
        or _has(subject, _NOT_PUBLIC_WORK)
        or names_own_data(subject)
    ):
        return None
    return _original_words(text, subject).strip()


def record_fact_query(text: str) -> str | None:
    """«Entonces cuál fue el 1er libro de zombies» → the question as the search query; None otherwise.

    A first, last, best or release date is a dated fact: looked up before it is stated;
    so is a public person's age or who holds an office now, and a tally, a population, a
    price, a current holder, a record or the next edition (``_CHANGING_FACT``)."""

    folded = _question_body(text)
    if person_fact_subject(text) is not None:
        return _original_words(text, folded).strip()
    if (
        _CHANGING_FACT.fullmatch(folded) is not None
        and len(folded.split()) <= 20
        and not names_own_data(folded)
        and not _has(folded, _FIRST_PERSON_TALLY)
        and not _has(folded, _LOCAL_THING)
        and re.search(ARITHMETIC_EXPRESSION, folded) is None
    ):
        return _original_words(text, folded).strip()
    if _RECORD_FACT.fullmatch(folded) is None or len(folded.split()) > 16:
        return None
    subject = re.sub(r"^(?:cual|quien|cuando|what|who|which|when)\s+\S+\s+", "", folded)
    if _has(subject, _NOT_PUBLIC_WORK) or _has(folded, r"\b(?:dije|dijiste|hice|hiciste|te\s+pedi|said|asked)\b"):
        return None
    return _original_words(text, folded).strip()


_RESEARCH_QUESTION_SUBJECT = re.compile(
    r"^[¿?¡!\s]*(?:que|qué|quien|quién|what|who)\s+(?:es|son|fue|era|is|are|was)\s+"
    r"(?:(?:el|la|los|las|the|un|una|unos|unas|a|an)\s+)?(?P<subject>[^?¿!¡]+?)\s*[.!?¿¡=\s]*$",
    re.IGNORECASE,
)


def _research_question_subject(text: str) -> str | None:
    """WEB1481 «Investiga en internet que es el h2o»: the subject of the
    who/what question that a research order carries («h2o»), with its own
    spelling; None when the order carries no such question, or the subject is
    the assistant, a pointed or possessed thing, a word's meaning or a local
    thing (the same exclusions as _entity_lookup_query)."""

    order = _TOPIC_RESEARCH.match(text.strip())
    if order is None:
        return None
    question = _RESEARCH_QUESTION_SUBJECT.match(order.group("topic").strip(" \t\r\n.,;:"))
    if question is None:
        return None
    subject = question.group("subject").strip(" \t\r\n.,;:")
    if not subject or len(subject.encode("utf-8")) > 80 or len(subject.split()) > 8:
        return None
    if _entity_lookup_query("quién es " + subject) is None:
        return None
    return subject


# MASSIVE transport_traffic (dev corpus 2026-09-24) «cómo está el tráfico cerca de mí», «el trafico ahora», «i would
# like to know the traffic condition»: the traffic of streets and roads is live public information; the model read
# «tráfico» as this PC's listening ports. The traffic of a network, of data or of a site is not the road's.
_ROAD_TRAFFIC = (
    r"\b(?:trafico|traffic|atascos?|embotellamientos?|trancones?|congestion(?:amiento)?(?:\s+vehicular)?|"
    r"traffic\s+jams?)\b"
)
_NOT_ROAD_TRAFFIC = (
    r"\b(?:red|redes|network|networks|internet|wi[\s-]?fi|ethernet|datos|data|puertos?|ports?|bytes?|kb|mb|gb|"
    r"paquetes|packets|ancho\s+de\s+banda|bandwidth|web|sitio|site|pagina|page|servidor|server|tcp|udp|ip|"
    r"drogas?|drugs?|personas|humans?|armas|weapons|influencias)\b"
)


# «odio lo largos que son los atascos»: how the person feels about the traffic is talk, not a lookup.
_FEELING_ABOUT = (
    r"^(?:yo\s+)?(?:odio|detesto|amo|me\s+(?:molesta|molestan|encanta|encantan|gusta|gustan|cansa|cansan|estresa|"
    r"estresan)|estoy\s+(?:hart[oa]|cansad[oa])|i\s+(?:hate|love|like|can'?t\s+stand)|i'?m\s+(?:tired|sick)\s+of)\b"
)


def _road_traffic_request(folded: str) -> bool:
    """How the road traffic is (see above); an order to open or play something, or a feeling, is not asking it."""

    return (
        _has(folded, _ROAD_TRAFFIC)
        and not _has(folded, _NOT_ROAD_TRAFFIC)
        and not _has(folded, _FEELING_ABOUT)
        and not _head_is(_request_head(folded), _OPEN)
    )


# The heads that ask for the weather when the sentence names it («dime el clima», «va a llover»).
_WEATHER_HEADS = frozenset(
    {
        "are",
        # WEATHER2023 «¿hace frío afuera?», «hace calor hoy?»
        "hace",
        "busca",
        "buscame",
        "buscar",
        "clima",
        "como",
        "cual",
        "decime",
        "dime",
        "find",
        "mostrame",
        "muestra",
        "muestrame",
        "que",
        "search",
        "do",
        "does",
        "forecast",
        "how",
        "is",
        "llovera",
        "llueve",
        "necesito",
        "need",
        "pronostico",
        "reporte",
        "temperature",
        "va",
        "weather",
        "what",
        # Tanda 4c «Whats the air quality hoy?»: the apostrophe the keyboard left out, and the air named first.
        "whats",
        "air",
        "calidad",
        "aqi",
        "esta",
        "will",
        "voy",
        "yes",
        # Uso real 2026-09-23: «cuándo va a llover», «necesitaré protector solar»,
        # «tengo que llevarme gafas de sol», «report weather for …».
        "cuando",
        "when",
        "necesitare",
        "tengo",
        "hara",
        "habra",
        # MASSIVE weather_query «estará despejado mañana», «será un día lluvioso»
        "estara",
        "sera",
        "report",
        "i",
        # Uso real 2026-09-23 «Dígame el weather para San Valentín», «tell me the
        # weather in Paris»: the formal and English asking heads went to a web
        # search of the whole sentence instead of the weather read.
        "digame",
        "diganme",
        "dame",
        "deme",
        "tell",
        "give",
        "check",
        "show",
        "revisa",
        "consulta",
        # «hay alguna previsión de lluvia o nieve esta semana»
        "hay",
        # MASSIVE weather_query «mira el tiempo de la semana que viene por mi»: looking it up for the person.
        "mira",
        "mirame",
        "fijate",
        "averigua",
        "chequea",
        # Uso real tanda 5 «infórmanos del tiempo actual en Lugo»: informing the person of it («cuéntame»
        # stays out: «cuéntame un chiste del clima» tells a joke).
        "informa",
        "inform",
        "update",
    }
)
# WEB1453 «¿Qué es un pronóstico del tiempo?»: what a forecast is (indefinite article) asks for a definition; «what
# is the weather» keeps its article and stays a lookup.
_DEFINITION_QUESTION = r"^[¿?¡!\s]*(?:que|what)\s+(?:es|son|is|are)\s+(?:un|una|unos|unas|a|an)\s+"
# A file, note or document named after the weather, or a question about the word itself («¿qué significa la palabra
# clima?»), is not a live lookup.
_ABOUT_THE_WORD_OR_A_FILE = (
    r"\b(?:archivos?|files?|carpetas?|folders?|notas?|notes?|documentos?|"
    r"documents?|txt|pdf|docx|significa|significado|definicion|define|"
    r"definition|meaning|means)\b"
)


_LEADING_CONNECTOR_OR_DAY = (
    rf"^[¿¡\s]*(?:(?:(?:y|e|and|pero|but|ok|okay|entonces|so)\b|(?:(?:el|este|the|this)\s+)?{WEATHER_WHEN})[\s,]*)+"
)


def _live_weather_request(folded: str) -> bool:
    """The weather asked as a live read: named after an asking head, asked through what it calls for, or asked
    about a time to come. Shared by the live lookup and the weather query, so a sentence that is another lookup
    and only mentions a weather word («actualización sobre el gorila copito de nieve») is not the weather.
    Tanda 9 «y mañana va a hacer más calor?»: a connector or the day said first is not the asking head."""

    head = _request_head(re.sub(_LEADING_CONNECTOR_OR_DAY, "", folded))
    vocative_weather = re.match(
        r"^(?:olly|bax[yi])\s+(?P<head>[a-z]+)\b",
        folded,
        re.IGNORECASE,
    )
    weather_head = (
        # Uso real tanda 5 «infórmanos del tiempo actual en Lugo»: a head with its clitic («infórmanos»,
        # «dímelo») is the same head.
        any(form in _WEATHER_HEADS for form in _head_forms(head))
        or (vocative_weather is not None and vocative_weather.group("head") in _WEATHER_HEADS)
        or _has(folded, _KNOWLEDGE_LEAD_IN)
    )
    # «i wish to know the weather in san francisco»: an unambiguous weather noun
    # names the lookup when the sentence has no other order head («escribe …
    # clima» types words, it does not look anything up).
    weather_noun = not head and (
        _has(folded, r"\b(?:weather|forecast|pronostico|clima)\b") or _asks_air(folded) or _asks_sky_measure(folded)
    ) and not _has(
        folded, r"\bclima\s+(?:laboral|politico|social|economico|de\s+trabajo|organizacional|familiar)\b"
    )
    weather = (
        weather_head and _names_weather(folded)
        or weather_noun
        or _asks_weather_indirectly(folded)
        or _forecast_question(folded)
    ) and not (
        # r7/r9 «dame una receta de sopa para una noche fría»: the weather is what the recipe is for.
        _has(folded, r"\b(?:recetas?|recipes?)\b")
    ) and not _has(
        # WEATHER2023 boundary: the weather of the past is no live lookup.
        folded,
        _PAST_WEATHER,
    )
    return (
        weather
        and re.match(_DEFINITION_QUESTION, folded, re.IGNORECASE) is None
        and not _has(folded, _ABOUT_THE_WORD_OR_A_FILE)
    )


def _public_live_lookup_request(folded: str) -> bool:
    """Recognize live feeds that require a public lookup to answer."""

    head = _request_head(folded)
    news_consumption = (
        re.match(
            (
                r"^(?:(?:alexa|olly|bax[yi])\s+)?(?:"
                r"i\s+(?:want|would\s+like)\s+to\s+(?:hear|know|see)|"
                r"(?:pon|ponme|muestra|muestrame|show|play|"
                r"busca|buscame|buscar|search|find|dame|decime|dime|investiga|"
                # MASSIVE news_query «saca el artículo sobre cuidador de perro en las noticias de la mañana».
                r"saca|sacame|lee|leeme|read|trae|traeme|pull\s+up|"
                # Uso real tanda 5e «¿podrías poner las notícias mundiales?» searched portals: after «podrías»,
                # «puedes», «could you» the order is its infinitive, and the news are put on as they are played.
                r"poner|ponerme|mostrar|mostrarme|dar|darme|decir|decirme|leer|leerme|traer|traerme|buscarme|put)\b"
                r")"
            ),
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    news = (
        head
        in {
            "headlines",
            "news",
            "noticias",
            "titulares",
            # NEWS2027 «qué noticias hay de tecnología», «top news today»,
            # «what's the news», «cuáles son los titulares», «últimas noticias»
            "que",
            "cuales",
            "what",
            "which",
            "top",
            "latest",
            "ultimas",
            "hay",
            "any",
        }
        or news_consumption
    ) and _has(
        folded,
        r"\b(?:news|headlines|noticias|titulares|breaking\s+news)\b",
    )
    weather = _live_weather_request(folded)
    # WEB1451 «qué pasó hoy en el mundo», tanda 4 «dime que esta pasando en mi ciudad», MASSIVE recommendation_events
    # «que esta pasando alrededor mio»: what happens today, or in a place, is the news of it (``news_lookup_query``).
    # MASSIVE news_query «actualización sobre el gorila copito de nieve»: an update about a subject is its news; the
    # person's own tasks or orders are not.
    todays_events = news_lookup_query(folded) is not None or (
        _has(
            folded,
            r"^(?:(?:alguna?s?|any|the|las?|ultimas?|latest)\s+)*(?:actualizacion(?:es)?|novedad(?:es)?|updates?)\s+"
            r"(?:sobre|acerca\s+de|on|about)\s+\S",
        )
        and not _has(folded, r"\b(?:mi|mis|my|nuestr[oa]s?|our|tareas?|tasks?|pedidos?|orders?)\b")
    )
    # WEB1451 «Investiga Spider-Man»: a research order about a named topic
    # is a public lookup of that topic.
    topic_research = _topic_research_query(folded) is not None
    # KNOWLEDGE1473 «¿Quién es Daredevil?»: who or what a named thing is gets
    # looked up in public pages instead of recited from the model's memory.
    entity_lookup = _entity_lookup_query(folded) is not None
    # KNOWLEDGE1505 «decime una curiosidad»: a curiosity with no topic is
    # looked up about a subject BAXY picks, never invented (KNOWLEDGE1353).
    curiosity = curiosity_request(folded)
    # WEB1453: what a news item is asks for a definition (``_DEFINITION_QUESTION``).
    if re.match(_DEFINITION_QUESTION, folded, re.IGNORECASE) is not None:
        news = False
        todays_events = False
        topic_research = False
        entity_lookup = False
    if (news or todays_events or topic_research or entity_lookup) and _has(folded, _ABOUT_THE_WORD_OR_A_FILE):
        news = False
        todays_events = False
        topic_research = False
        entity_lookup = False
    market_direction = (
        re.match(
            (
                r"^(?:are|did|do|how|is|was|were|esta|estaba|estaban|estan|"
                r"subieron|bajaron)\b.{0,96}"
                r"\b(?:stocks?|shares?|stock\s+market|acciones|bolsa|"
                r"mercado\s+bursatil)\b.{0,96}"
                r"\b(?:up|down|rising|falling|rise|fall|subiendo|bajando|"
                r"subieron|bajaron|alza|baja)\b"
            ),
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    market_price = (
        re.match(
            (
                r"^(?:averigua|averigue|consulta|consultar|busca|buscar|"
                r"find\s+out|look\s+up|check)\b.{0,96}"
                r"\b(?:precio|price|cotizacion|quote)\b.{0,96}"
                r"\b(?:acciones|stocks?|shares?)\b"
            ),
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    local_events = (
        re.match(
            (
                r"^(?:anything\s+(?:interesting\s+)?(?:going\s+on|happening)|"
                r"what(?:'s|\s+is)\s+(?:going\s+on|happening)|"
                r"what\s+events?\s+are\s+happening|"
                r"hay\s+algo\s+(?:interesante\s+)?(?:pasando|ocurriendo))"
                r"\b.{0,80}\b(?:in|near|around|en|cerca\s+de)\b\s+\S"
            ),
            folded,
            re.IGNORECASE,
        )
        is not None
        # «what's going on in my social media» is the person's account (messaging.social_network_request).
        and not _has(folded, SOCIAL_NETWORK)
    )
    local_fair = (
        re.match(
            (
                r"^(?:hay|habra|existen?)\s+(?:ferias?|mercados?|eventos?)\b"
                r".{0,96}\b(?:en|cerca\s+de|por)\s+(?:esta|mi|la)\s+"
                r"(?:zona|area|barrio|ciudad)\b"
            ),
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    nearest_public_place = (
        re.match(
            (
                r"^(?:cual|donde)\b.{0,48}\b(?:zoo|zoologico|hospital|farmacia|"
                r"gasolinera|parking|aparcamiento|estacionamiento|restaurant)\b"
                r".{0,96}\b(?:mas\s+cercan[oa]|cerca\s+de|donde\s+(?:yo\s+)?estoy)\b|"
                r"^(?:where|what)\b.{0,48}\b(?:nearest|closest)\b.{0,48}"
                r"\b(?:zoo|hospital|pharmacy|parking|gas station|restaurant)\b"
            ),
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    parking_lookup = (
        re.match(
            (
                r"^(?:donde|where)\s+(?:puedo|can\s+i)\s+"
                r"(?:aparcar|estacionar|park)\b.{0,120}\b(?:cerca|near)\b\s+\S"
            ),
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    trending_public_articles = (
        re.match(
            (
                r"^(?:cuales|which|what)\b.{0,48}"
                r"\b(?:articulos?|articles?)\b.{0,48}"
                r"\b(?:tendencia|trending|populares?|popular)\b"
            ),
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    underspecified_market_price = (
        re.match(
            (
                r"^(?:mas\s+)?(?:precio|precios|cotizacion|cotizaciones)\b.{0,48}"
                r"\b(?:acciones|stocks?|shares?)\b|"
                r"^(?:mas\s+)?(?:acciones|stocks?|shares?)\b.{0,48}"
                r"\b(?:precio|precios|price|prices|quote|quotes)\b"
            ),
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    nearby_store = (
        re.match(
            (
                r"^(?:(?:solo\s+)?(?:estoy\s+)?buscando|busco|encuentra|"
                r"puedes\s+encontrar|i(?:'m|\s+am)\s+(?:just\s+)?looking|"
                r"find|show)\b.{0,160}"
                r"\b(?:tiendas?|stores?|shops?)\b.{0,96}"
                r"\b(?:dentro\s+de|a|within|near|nearby)\b.{0,32}"
                r"\b(?:milla|millas|mile|miles|km|kilometros?)\b"
            ),
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    nearby_weekend_event = (
        re.match(
            (
                r"^(?:hay|habra|is\s+there|are\s+there)\b.{0,80}"
                r"\b(?:evento|eventos|event|events)\b.{0,96}"
                r"\b(?:cerca\s+de\s+mi|near\s+me|nearby|en\s+mi\s+zona)\b"
                r".{0,80}\b(?:fin\s+de\s+semana|weekend)\b"
            ),
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    # MASSIVE takeaway_query «alexa el rodilla hace envíos», «pizza hut tiene para llevar», «i need to know if mr.
    # pizza delivers»: whether a business delivers or sells to take away, however the business is named first. The
    # person's own order («¿cuándo llega mi pedido?») is theirs, not public.
    business_delivery = (
        _has(
            folded,
            # MASSIVE takeaway_query (dev corpus 2026-09-24) «el restaurante manolo entrega comida para llevar», «el
            # rosario's acepta pedidos para llevar»: delivering or accepting the order asks the same.
            r"\b(?:hace|hacen|ofrece|ofrecen|tiene|tienen|entrega|entregan|acepta|aceptan|toma|toman|does|do|is|are|"
            r"accepts?|offers?|takes?)\b.{0,96}"
            r"\b(?:envios?|entregas?|delivery|deliver|reparto|a\s+domicilio|para\s+llevar|take\s*-?out|takeaway|"
            r"carry\s*-?out)\b|\b(?:delivers|reparte|reparten)\b",
        )
        and not _has(folded, r"\b(?:mi|mis|my)\s+(?:pedidos?|orders?|comida|food|paquetes?|packages?|compras?)\b")
    )
    public_events = public_event_subject(folded) and not _has(folded, _CALENDAR_SYSTEM)
    # MASSIVE qa_currency / qa_stock «cuantos euros es un dólar estadounidense ahora», «let me know about the
    # exchange rate of rupee to dirham», «cuál es el aumento en el valor de las acciones durante la última semana de
    # disney»: a rate or a share value moves every day; it was recited from memory. «acciones» alone is also the
    # quick actions of Windows, so it counts with a word of the market.
    # MASSIVE news_query «cuáles son las predicciones de las votaciones de r. t. v. e. para las próximas elecciones
    # españolas»: polls and elections are the news, asked about.
    election_news = _has(
        folded, r"\b(?:elecciones|electoral(?:es)?|encuestas?\s+electorales?|sondeos?|votaciones|comicios|elections?|polls?)\b"
    ) and _has(folded, r"^(?:que|cual|cuales|quien|quienes|como|cuando|what|which|who|how|when|dime|decime|tell|busca|search)\b")
    market_data = (
        _has(folded, r"\b(?:tipos?|tasas?)\s+de\s+cambio\b|\bexchange\s+rates?\b|\bconversion\s+rates?\b")
        or (
            _has(folded, rf"\b(?:cuant[oa]s?|how\s+(?:many|much))\b.{{0,40}}{_CURRENCY}.{{0,60}}{_CURRENCY}")
            # «cuánto es 5 euros más 3 euros» is a sum.
            and not _has(folded, r"\b(?:mas|menos|plus|minus)\b")
        )
        or (
            _has(folded, r"\bacciones\b")
            and _has(
                folded,
                r"\b(?:precios?|valor|cotiza\w*|bolsa|mercado|subiendo|bajando|subieron|bajaron|cayeron|cayendo|alza|"
                r"aumento|subida|caida|bajada|rendimiento)\b",
            )
        )
    )
    takeaway_availability = (
        re.fullmatch(
            (
                r"(?:(?:can|could)\s+i|puedo|podria)\b.{0,96}"
                r"\b(?:carry\s+out|take\s+out|takeaway|takeout|para\s+llevar)\b"
                r".{0,96}\b(?:restaurant|restaurante)\b.{0,32}[\s.!?]*|"
                r"(?:does|do|is|hace|ofrece|tiene)\b.{0,96}"
                r"\b(?:restaurant|restaurante)\b.{0,96}"
                r"\b(?:carry\s*out|take\s*out|takeaway|takeout|para\s+llevar)\b"
                r".{0,32}[\s.!?]*"
            ),
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    publisher_top_stories = (
        re.match(
            (
                r"^(?:cuales|which|what)\b.{0,48}"
                r"\b(?:historias?|stories|titulares?|headlines|noticias?)\b"
                r".{0,48}\b(?:principales|top|latest|recientes)\b|"
                r"^(?:cuales|which|what)\b.{0,48}\b(?:principales|top|latest)\b"
                r".{0,48}\b(?:historias?|stories|titulares?|headlines|noticias?)\b"
            ),
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    attributed_parking = (
        re.match(
            (
                r"^(?:muestra|muestrame|show|find|encuentra|quiero\s+encontrar|"
                r"i\s+want\s+to\s+find)\b.{0,96}"
                r"\b(?:parking|aparcamiento|estacionamiento|valet\s+parking)\b"
                r".{0,120}\b(?:en|in|near|by|cerca\s+de|con|with)\b\s+\S"
            ),
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    generic_parking_discovery = (
        re.fullmatch(
            (
                r"(?:(?:i\s+)?(?:want|would\s+like)\s+to\s+find|find|show|"
                r"busca|encuentra|muestra|usa\s+[a-z0-9._-]+\s+para\s+encontrar)"
                r"\b.{0,120}\b(?:garage\s+parking|parking|aparcamientos?|"
                r"estacionamientos?)\b.{0,120}[\s.!?]*"
            ),
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    retail_recommendation = (
        re.fullmatch(
            r"(?:(?:me\s+)?recomiendas?|recommend(?:\s+me)?)\s+"
            r"(?:(?:un|una|some|a|an)\s+)?(?:paraguas|umbrella)"
            r"[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    culinary_discovery = (
        re.fullmatch(
            r"(?:muestra|muestrame|show)(?:\s+me)?\s+"
            r"(?:(?:las|the|some)\s+)?(?:recetas|recipes)\s+"
            r"(?:famosas|populares|famous|popular|best|mejores)\b.{0,160}"
            r"[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    transit_schedule = (
        re.fullmatch(
            # MASSIVE transport_query (dev corpus 2026-09-24) «cuáles son los horarios de los trenes de san francisco
            # a nueva york»: the timetable asked, not only listed. «what are the train times for» is cut before its
            # route and is asked, not looked up.
            r"(?:list|show|find|search|lista|muestra|busca|dime|decime|dame|tell\s+me|give\s+me|"
            r"cuales|cual|que|what|which|when|cuando)\b.{0,80}"
            r"\b(?:(?:train|bus|flight|ferry|subway)\s+(?:times?|schedules?)|"
            r"horarios?\s+de(?:\s+(?:los|las))?\s+(?:trenes?|autobuses|buses|micros|vuelos|metro|ferris?|barcos?))\b"
            r"(?:.{0,96}\S)?(?<!\bfor)(?<!\bpara)(?<!\bde)(?<!\bto)[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
        and not _has(folded, r"\b(?:mi|mis|my)\s+(?:tren|autobus|bus|vuelo|avion|train|flight|plane)\b")
        # MASSIVE transport_query «puedes decirme a qué hora sale el tren a chicago»: when a public service leaves
        # or arrives. The person's own trip («mi vuelo») is theirs.
        or (
            _has(
                folded,
                r"\b(?:a\s+que\s+hora|cuando|what\s+time|when)\s+(?:sale|salen|llega|llegan|parte|parten|pasa|pasan|"
                r"does|do|is|are)\b.{0,40}\b(?:tren|trenes|autobus|autobuses|bus|buses|micro|vuelo|vuelos|avion|metro|"
                r"ferry|barco|train|trains|flight|flights|plane|subway)\b",
            )
            and not _has(folded, r"\b(?:mi|mis|my)\s+(?:tren|autobus|bus|vuelo|avion|train|flight|plane)\b")
        )
    )
    weekly_weather_report = (
        re.fullmatch(
            r"(?:(?:weekly|semanal)\s+(?:weather|clima|tiempo)\s+(?:report|reporte)|"
            r"(?:weather|clima|tiempo)\s+(?:report|reporte)\s+(?:weekly|semanal)|"
            r"reporte\s+del\s+tiempo\s+semanal)[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    future_clothing_weather = (
        re.fullmatch(
            r"(?:voy\s+a\s+necesitar|necesitare|will\s+i\s+need|do\s+i\s+need)\b"
            r".{0,96}\b(?:chaqueta|abrigo|jacket|coat|paraguas|umbrella)\b"
            r".{0,96}\b(?:hoy|today|manana|tomorrow|next|proximo|proxima|"
            r"lunes|martes|miercoles|jueves|viernes|sabado|domingo|"
            r"monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b"
            r".{0,48}[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    public_parking_discovery = (
        _has(
            folded,
            r"\b(?:parking|aparcamiento|estacionamiento)\b",
        )
        and _has(
            folded,
            r"\b(?:localiza|localizar|localizaras|encuentra|encontrar|find|"
            r"donde|where|cerca|near|nearby|ubicacion|location|gratis|"
            r"gratuito|adaptado|accessible)\b",
        )
        and not _has(folded, r"\b(?:paga|pagar|pay|tarjeta|card|visa|bizum)\b")
    )
    retailer_product_discovery = (
        _has(
            folded,
            r"\b(?:walmart|amazon|oysho|safeway|target|costco|ikea)\b",
        )
        # H0646: «quiero ver The Boys en Amazon Prime» names the streaming
        # service, not the store; the Prime Video limit answers it.
        and not _has(folded, r"\bamazon\s+prime\b|\bprime\s*video\b")
        and _has(
            folded,
            r"^(?:i\s+need|i\s+want|let(?:'s|\s+us)\s+get|necesito|quiero|"
            r"voy\s+a\s+necesitar)\b|\b(?:deliver|delivery|envio|entrega)\b",
        )
        and not _has(folded, r"\b(?:paga|pagar|pay|tarjeta|card|visa|bizum)\b")
    )
    return any(
        (
            news,
            weather,
            todays_events,
            topic_research,
            entity_lookup,
            curiosity,
            market_direction,
            market_price,
            local_events,
            local_fair,
            nearest_public_place,
            parking_lookup,
            trending_public_articles,
            underspecified_market_price,
            nearby_store,
            nearby_weekend_event,
            business_delivery,
            public_events,
            election_news,
            market_data,
            takeaway_availability,
            publisher_top_stories,
            attributed_parking,
            generic_parking_discovery,
            retail_recommendation,
            culinary_discovery,
            transit_schedule,
            weekly_weather_report,
            future_clothing_weather,
            public_parking_discovery,
            retailer_product_discovery,
            _road_traffic_request(folded),
            cinema_listing(folded),
        )
    )


def _public_product_correction_lookup_request(folded: str) -> bool:
    """Recognize a corrected nominal product request as a safe public lookup."""

    nominal_request = (
        re.match(
            (
                r"^(?:"
                r"(?:quiero|necesito|busco)\s+(?:un|una|unos|unas|algo)\b|"
                r"voy\s+a\s+(?:obtener|conseguir|buscar)\s+\S|"
                r"i\s+(?:want|need)\s+(?:(?:to\s+get)\s+)?(?:a|an|some)\b|"
                r"i(?:'m|\s+am)\s+going\s+to\s+(?:get|find|pick\s+up)\s+\S|"
                r"(?:get|find|pick\s+up)\s+(?:me\s+)?(?:a|an|some)\b"
                r")"
            ),
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    correction = _has(
        folded,
        (
            r"(?:[.;!?]|\b(?:bueno|well)\b)[^.;!?]{0,48}"
            r"\b(?:mejor|quiero\s+decir|i\s+mean|make\s+that)\b|"
            r"\bno\b\s*,?\s*(?:quiero\s+decir|mejor|i\s+mean|make\s+that)\b|"
            r"\b(?:quiero\s+decir|i\s+mean|make\s+that)\b\s+\S"
        ),
    )
    transactional = _has(
        folded,
        (
            r"\b(?:compra|comprar|buy|purchase|order|ordena|paga|pagar|pay|"
            r"tarjeta|card|visa|mastercard|bizum|cash|efectivo|deliver|"
            r"delivery|entrega|envia|enviar|send)\b"
        ),
    )
    return nominal_request and correction and not transactional


def _public_commerce_lookup_request(folded: str) -> bool:
    """Recognize read-only restaurant and delivered-product discovery."""

    takeaway = (
        re.match(
            (
                r"^(?:can|could)\s+i\s+(?:get|order)\s+"
                r"(?:take-?out|takeaway|delivery)\s+from\s+\S|"
                r"^(?:puedo|podria)\s+(?:pedir|obtener)\s+"
                r"(?:comida\s+para\s+llevar|delivery)\s+de\s+\S"
            ),
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    delivered_product = (
        re.match(
            (
                r"^(?:quiero|necesito|busco)\s+(?:un|una|unos|unas)\s+"
                r"\S.{0,120}\b(?:envien|envio|entrega)\b.{0,32}"
                r"\b(?:casa|domicilio)\b|"
                r"^i\s+(?:want|need|am\s+looking\s+for)\s+(?:a|an|some)\s+"
                r"\S.{0,120}\b(?:delivered|delivery)\b.{0,32}\bhome\b"
            ),
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    gift_discovery = (
        re.match(
            (
                r"^i\s+(?:need|want)\s+to\s+(?:find|look\s+for)\s+"
                r"(?:a\s+)?(?:present|gift)\s+for\s+\S|"
                r"^(?:necesito|quiero)\s+(?:encontrar|buscar)\s+"
                r"(?:un\s+)?regalo\s+para\s+\S"
            ),
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    payment = _has(
        folded,
        r"\b(?:paga|pagar|pay|checkout|tarjeta|card|visa|mastercard|bizum)\b",
    )
    return (takeaway or delivered_product or gift_discovery) and not payment


_FILESYSTEM_OBJECT_NOUN = (
    r"\b(?:archivos?|file|files|fichero|ficheros|carpetas?|folders?|"
    r"directorios?|directory|directories|ruta|rutas|path|paths|"
    r"documento|documentos|document|documents|sandbox|papelera|trash|"
    r"recycle|escritorio|desktop|descargas|downloads|imagenes|pictures|"
    r"copia|copias|backup|backups|respaldo|respaldos|"
    r"txt|csv|json|pdf|docx|xlsx|md|log)\b"
    r"|(?:^|\s)[a-z]:[\\/]|\.[a-z0-9]{2,4}\b"
)


def operation_identity_is_a_near_miss(text: str, operation: str) -> bool:
    """True when the spoken request names a different effect than this leaf.

    Domain grounding is one-sided and lexical: False both when the person
    paraphrased a real catalogue effect and when they asked for a nearby
    substitute. The identity verifier may revive the paraphrase. Publishing
    the substitute as ``intent_operations`` would execute it if they say yes
    — a taxi is not ``task.create``, a PDF conversion is not a blank Office
    document. This is the contradiction side of that split.
    """

    folded = _fold(text)
    # Physical errands this machine cannot do: any leaf is a substitute.
    if _has(folded, r"\b(?:taxi|uber|cab|lyft)\b") and not _has(
        folded,
        r"\b(?:tarea|task|to-do|todo|pendiente)\b",
    ):
        return True
    if _has(
        folded,
        r"\b(?:riega|regar|watering|plantas?|plants?)\b",
    ) and not _has(folded, r"\b(?:rutina|routine|automation)\b"):
        return True
    if operation == "media.play.youtube":
        return _has(
            folded,
            r"\b(?:upload|sube|subir|subime|publica|publicar|publish)\b",
        ) and not _has(
            folded,
            r"\b(?:reproduce|reproducir|play|pon|poner)\b",
        )
    if operation.startswith("capture."):
        return (
            _has(
                folded,
                r"\b(?:graba|grabar|grabame|record|recording|filma|filmar)\b",
            )
            and _has(folded, r"\b(?:pantalla|screen|video)\b")
            and not _has(
                folded,
                r"\b(?:captura de pantalla|screenshot|pantallazo|"
                r"window capture|captura (?:de )?(?:la )?ventana)\b",
            )
        )
    if operation in {
        "wifi.connect.named",
        "wifi.connect",
        "wifi.ensure.connected",
    }:
        return _has(folded, r"\b(?:vpn|virtual\s+private)\b") and not _has(
            folded,
            r"\b(?:wi[\s-]?fi|red\s+inalambrica|wireless)\b",
        )
    if operation.startswith("filesystem."):
        return (
            (
                _has(folded, r"\b(?:clon(?:a|ar|ame)|clone)\b")
                and _has(folded, r"\b(?:disco|disk|drive|hdd|ssd)\b")
                and not _has(folded, _FILESYSTEM_OBJECT_NOUN)
            )
            or (
                operation in {"filesystem.trash.restore", "filesystem.trash.commit"}
                and _has(folded, r"\b(?:desfragmenta|desfragmentar|defrag)\b")
            )
            or (
                operation == "filesystem.write.text"
                and _has(folded, r"\b(?:formatea|formatear|format)\b")
                and _has(folded, r"\b(?:pendrive|usb|disco|disk)\b")
            )
        )
    if operation in {"media.seek.relative", "media.control"}:
        return _has(
            folded,
            r"\b(?:edita|editar|editame|edit|recorta|recortar|trim|"
            r"corta|cortar|cut|quita|quitar|quitale)\b",
        ) and not _has(
            folded,
            r"\b(?:adelanta|atrasa|retrocede|rewind|forward|jump|skip|seek)\b",
        )
    if operation == "office.document.create":
        return _has(
            folded,
            r"\b(?:convierte|convertir|convierteme|convert|conversion)\b",
        ) or (
            _has(folded, r"\bpdf\b")
            and _has(
                folded,
                r"\b(?:word|docx|excel|documento|document)\b",
            )
            and not _has(
                folded,
                r"\b(?:crea|crear|creame|create|nuevo|new|blanco|blank)\b",
            )
        )
    if operation == "system.power":
        return _has(
            folded,
            r"\b(?:telefono|movil|celular|phone|smartphone|iphone|tablet)\b",
        ) and not _has(
            folded,
            r"\b(?:equipo|pc|compu|computador(?:a)?|computer|"
            r"maquina|machine|windows)\b",
        )
    if operation.startswith("peripheral."):
        return _has(
            folded,
            r"\b(?:3d|tres\s+dimensiones|tridimensional|three[\s-]?d)\b",
        )
    if operation in {"game.install.cancel.active", "game.install.cancel"}:
        return _has(
            folded,
            r"\b(?:torrent|series|pelicula|movie)\b",
        ) and not _has(folded, r"\b(?:steam|juego|game)\b")
    if operation.startswith("game.purchase"):
        return _has(
            folded,
            r"\b(?:pizza|comida|food|hamburguesa|burger|"
            r"dolares?|dollars?|transfer(?:e|ir|iere)?|transfiere)\b",
        ) and not _has(folded, r"\b(?:steam|juego|game)\b")
    if operation == "note.create":
        return (
            _has(
                folded,
                r"\b(?:call|llama|llamame|phone)\b",
            )
            and _has(
                folded,
                r"\b(?:madre|mother|mom|papa|father|dad)\b",
            )
            and not _has(folded, r"\b(?:nota|note|notas|notes)\b")
        )
    if operation == "system.status":
        return _has(folded, r"\b(?:antivirus|virus)\b") and not _has(
            folded,
            r"\b(?:estado|status|salud|health)\b",
        )
    if operation == "system.settings.set":
        return _has(
            folded,
            r"\b(?:fondo de escritorio|wallpaper|desktop background)\b",
        ) and not _has(
            folded,
            r"\b(?:brillo|brightness|luz nocturna|night light|"
            r"no molestar|do not disturb|dnd)\b",
        )
    if operation in {"message.send", "message.recipient.resolve"}:
        return _has(
            folded,
            r"\b(?:flores?|flowers?|plomero|plumber|madre|mother|"
            r"taxi|pizza)\b",
        ) and not _has(
            folded,
            r"\b(?:mensaje|message|whatsapp|discord|sms|chat|"
            r"correo|email)\b",
        )
    if operation.startswith("backup."):
        return _has(
            folded,
            r"\b(?:particion|partition|fondo de escritorio|wallpaper|"
            r"desktop background)\b",
        )
    if operation.startswith(("game.install", "package.install")):
        return _has(folded, r"\b(?:git|github|gitlab)\b") and _has(
            folded,
            r"\b(?:commit|push|pull|clone)\b",
        )
    return False


_VISUAL_CONTENT_REQUEST = re.compile(
    r"^[\s¿?¡!]*(?:(?:oye|che|baxy)\s*,?\s+)?"
    r"(?:(?:tienes|tenes|tendras|tendrias|hay|tenis|do\s+you\s+have|got|have\s+you\s+got|"
    r"(?:me\s+)?(?:mandas|manda|mandame|mandame|envias|envia|enviame|pasas|pasa|pasame|muestras|muestra|muestrame|mostras|mostrame|das|da|dame|tiras|tirame)|"
    r"(?:can|could)\s+you\s+(?:send|show|give)(?:\s+me)?|send(?:\s+me)?|show(?:\s+me)?|give(?:\s+me)?)\s+"
    r"(?:(?:un|una|unos|unas|algun|alguna|algunos|algunas|el|la|los|las|a|an|any|some|the|me)\s+)*"
    r"(?:\w+\s+){0,2}?(?:meme|memes|imagen|imagenes|foto|fotos|gif|gifs|sticker|stickers|dibujo|dibujos|picture|pictures|image|images|photo|photos)\b"
    r".{0,40}$)"
)


# Uso real 2026-09-23 (tanda 2) «cuéntame un artículo random» was answered with an
# invented discovery «en 2023, un equipo de científicos…»: a random article, a fact or
# page picked at random, is the same curiosity with no topic, looked up and never made up.
_CURIOSITY_ADJECTIVE = (
    r"(?:interesante|curios[oa]|nuev[oa]|random|aleatori[oa]|al\s+azar|cualquiera|interesting|curious|cool|new)"
)
_CURIOSITY_REQUEST = re.compile(
    r"^(?:baxy\s*[,:]?\s*)?(?:(?:contame|cuentame|conta|cuenta|decime|dime|tirame|tira|explicame|explica|"
    r"dame|da|compart[ie]me|comparte|leeme|lee|ensename|muestrame|mostrame|"
    r"tell\s+me|give\s+me|share|read\s+me|show\s+me)\s+"
    r"(?:(?:un|una|algun|alguna|otra|otro|a|an|another|some)\s+)?"
    r"(?:(?:curiosidad|curiosidades|dato\s+curioso|datos\s+curiosos|fun\s+fact|fun\s+facts|"
    r"interesting\s+fact|random\s+fact)"
    rf"(?:\s+{_CURIOSITY_ADJECTIVE})?"
    r"|(?:algo|something)" + rf"\s+{_CURIOSITY_ADJECTIVE}"
    r"|(?:articulos?|articles?|paginas?|pages?|temas?|topics?|datos?|facts?)"
    rf"(?:\s+(?:de|from|on)\s+wikipedia)?\s+{_CURIOSITY_ADJECTIVE}(?:\s+(?:de|from|on)\s+wikipedia)?"
    r"|(?:random|interesting|curious)\s+(?:wikipedia\s+)?(?:articles?|pages?|topics?|facts?)"
    r"(?:\s+(?:from|on)\s+wikipedia)?)"
    r"(?:\s*,?\s*(?:por\s+favor|porfa|please))?[\s.!?]*$"
    r"|^(?:baxy\s*[,:]?\s*)?(?:contame|cuentame|conta|cuenta|decime|dime|tirame|tira|explicame|explica|"
    r"tell\s+me|give\s+me)\s+(?:algo|something)"
    r"(?:\s*,?\s*(?:por\s+favor|porfa|please))?[\s.!?]*$"
    r"|^(?:sorprendeme|surprise\s+me)(?:\s+(?:con|with)\s+(?:algo|something)(?:\s+" + _CURIOSITY_ADJECTIVE + r")?)?"
    r"(?:\s*,?\s*(?:por\s+favor|porfa|please))?[\s.!?]*$"
    r"|^(?:estoy|ando|me\s+siento)\s+(?:re\s+|muy\s+|super\s+)?aburrid[oa][\s.!?]*$"
    r"|^i(?:'?m|\s+am)\s+(?:so\s+)?bored[\s.!?]*$)",
    re.IGNORECASE,
)


def curiosity_request(text: str) -> bool:
    """KNOWLEDGE1505 «decime una curiosidad», «contame algo», «estoy aburrido»: a curiosity with no topic."""

    return _CURIOSITY_REQUEST.match(_strip_request_envelope(_fold(text)).strip()) is not None


def visual_content_request(text: str) -> bool:
    """CONVERSATION1150 H0069 «Tienes algun meme?»: memes and images cannot be shown here.

    A request to have, send or show visual content is answered as an honest
    boundary of this PC, never with a promised meme.
    """

    return _VISUAL_CONTENT_REQUEST.match(_strip_request_envelope(_fold(text)).strip()) is not None


_WEB_IMAGE_NOUN = r"(?:meme|memes|imagen|imagenes|foto|fotos|gif|gifs|sticker|stickers|dibujo|dibujos|picture|pictures|image|images|photo|photos)"


def web_image_request(text: str) -> tuple[str, bool] | None:
    """REOPEN1957 H0069 «Tienes algun meme?» (D11): a meme or an image of the
    web is searched, downloaded to Pictures and opened with the viewer.
    Returns (image query, subject missing). A meme needs no subject; an
    image or a photo without one («tienes alguna foto?») is asked about."""

    if not visual_content_request(text):
        return None
    folded = _strip_request_envelope(_fold(text)).strip(" ¿?¡!.")
    if _negative_action_forms(folded):
        return None
    if re.search(
        rf"\b(?:carpetas?|folders?|directorio|galerias?|gallery)\b|\b(?:mi|mis|my)\s+{_WEB_IMAGE_NOUN}\b", folded,
    ):
        # Tanda 3 2026-09-24: «muéstrame la carpeta de imágenes», «muéstrame mis fotos» are the pictures of
        # this PC, never an image downloaded from the web.
        return None
    match = re.search(
        rf"(?:(?P<before>(?:[a-z]+\s+){{0,2}}?))\b(?P<noun>{_WEB_IMAGE_NOUN})\b"
        rf"(?:\s+(?P<subject>(?:de|del|de\s+la|de\s+los|de\s+las|of|about|sobre|con|with)\s+.+?))?\s*$",
        folded,
    )
    if match is None:
        return None
    noun = match.group("noun")
    subject = (match.group("subject") or "").strip()
    before = " ".join(
        word for word in (match.group("before") or "").split()
        if word not in {"un", "una", "unos", "unas", "algun", "alguna", "algunos", "algunas", "el", "la", "los", "las", "a", "an", "any", "some", "the", "me", "mandame", "pasame", "mostrame", "muestrame", "dame", "tirame", "enviame", "tienes", "tenes", "hay", "tendras", "tendrias", "send", "show", "give", "you", "got", "have"}
    )
    query = " ".join(part for part in (before, noun, subject) if part)
    meme_like = noun in {"meme", "memes", "gif", "gifs", "sticker", "stickers"}
    return query, not (meme_like or subject or before)


_NAVIGATION_CLIENT = r"(?:discord|whatsapp|teams|telegram|slack|skype|zoom|signal|messenger)"


def client_navigation_target(folded: str) -> str | None:
    """Name the messaging client of a go-to-a-place order scoped to it, or nothing."""

    found = re.fullmatch(
        r"[¿?¡!\s]*(?:(?:por\s+favor|please)[,]?\s+)?"
        r"(?:(?:en|in|on)\s+(?P<client_a>" + _NAVIGATION_CLIENT + r")[,]?\s+)?"
        r"(?:ve|anda|andate|entra|entrale|metete|navega|llevame|go|navigate|switch|cambia|cambiate|take\s+me)\s+"
        r"(?:a(?:l)?|to|hacia|into)\s+(?P<place>\S.{0,60}?)"
        r"(?:\s+(?:en|in|on|de|del|of)\s+(?:el\s+)?(?P<client_b>" + _NAVIGATION_CLIENT + r"))?"
        r"(?:\s+(?:por\s+favor|please))?[\s.!?]*",
        folded,
    )
    if found is None:
        return None
    client = found.group("client_a") or found.group("client_b")
    if client is None or _has(found.group("place"), r"https?://|\b(?:[a-z0-9-]+\.)+[a-z]{2,63}\b"):
        return None
    return client


# «crea un archivo llamado hola.txt en el escritorio con el texto Hola Mundo»,
# «Crea una carpeta en el escritorio llamada CarterTest»: literal file and
# folder creation, in the sandbox or in a known folder (owner decision
# 2026-09-13, point 2). The known-folder words are display's (one definition).


def _authenticated_application_identity_conflict(
    text: str,
    application_names: Iterable[str] | ApplicationCatalogIndex,
) -> bool:
    """Detect a request that token-collides with, but is not, an exact name."""

    raw_targets: list[str] = []
    open_request = _match(
        text,
        (
            r"^[¿?¡!\s]*(?:(?:por favor|please)\s*[,;:]?\s*|"
            r"(?:puedes|podrias|can you|could you|would you)\s+)?"
            rf"{_OPEN}\b\s+(?P<target>.+?)"
            r"(?:\s+(?:por favor|please|para mi|for me|ahora|now))?"
            r"[\s?!.]*$"
        ),
    )
    if open_request is not None:
        raw_targets.append(open_request.group("target"))
    for pattern in (
        (
            r"^[¿?¡!\s]*(?:esta|estan|is|are)\s+"
            r"(?:instalad[oa]s?|installed)\s+"
            r"(?P<target>.+?)[\s?!.]*$"
        ),
        (
            r"^[¿?¡!\s]*(?:esta|estan|is|are)\s+"
            r"(?P<target>.+?)\s+"
            r"(?:instalad[oa]s?|installed)[\s?!.]*$"
        ),
    ):
        installed_request = _match(text, pattern)
        if installed_request is not None:
            raw_targets.append(installed_request.group("target"))

    wrappers = re.compile(
        (
            r"^(?:(?:el|la|los|las|the)\s+)?"
            r"(?:(?:aplicacion|application|app|programa|program)\s+)?"
        ),
        re.IGNORECASE,
    )
    separator = re.compile(
        (
            r"\s*(?:,\s*(?:(?:y|and)(?:\s+(?:luego|despues|then|afterwards))?)?"
            r"|(?:y|and)(?:\s+(?:luego|despues|then|afterwards))?)\s*"
        ),
        re.IGNORECASE,
    )
    catalog_identities = build_application_catalog_index(
        application_names,
    ).entity_identities
    for raw_target in raw_targets:
        for item in separator.split(raw_target):
            candidate = wrappers.sub("", item.strip(), count=1)
            candidate_key = _application_name_key(candidate)
            candidate_entity = _entity_key(candidate)
            if not candidate_key or not candidate_entity:
                continue
            if any(
                candidate_entity == entity and candidate_key != name_key
                for entity, name_key in catalog_identities
            ):
                return True
    return False


def _browser_page_domain(text: str) -> bool:
    if not _has(text, r"\b(?:pagina|page)\b"):
        return False
    document_domain = _has(
        text,
        (
            r"\b(?:documento|document|libro|book|revista|magazine|excel|"
            r"word|pdf|manual|novela|novel|hoja de calculo|spreadsheet|"
            r"presentacion|presentation|powerpoint|archivo|file)\b"
        ),
    )
    explicit_browser = _has(
        text,
        r"\b(?:navegador|browser|sitio|site|web)\b|https?://",
    )
    return not document_domain or explicit_browser


def browser_back_arguments(text: str) -> dict[str, str] | None:
    """Ground one complete browser-history request, preserving its full scope.

    The closed grammar supplies the enum identity, not rewritten user text.
    Quotes, prohibitions, document pages, extra effects and deferred requests
    do not match; their existing interpretation and conservation remain.
    """

    # Keep the complete speech act. Broad request envelopes are not needed
    # for this closed grammar and must not erase qualifiers or conditions.
    if not text or len(text) > 16_384:
        return None
    folded = _fold(text).strip(" ¿?¡!. ")
    if not _browser_page_domain(folded):
        return None
    spanish_head = (
        r"(?:regresa|regrese|vuelve|volve|retrocede|"
        r"(?:quiero|necesito)\s+(?:volver|regresar|retroceder))"
    )
    spanish_target = (
        r"(?:a\s+)?(?:la\s+)?pagina\s+(?:anterior|previa|de\s+antes)|"
        r"(?:una|1)\s+pagina"
    )
    english_request = (
        r"(?:go|move)\s+back\s+(?:(?:one|a(?:\s+single)?)\s+page|"
        r"to\s+the\s+(?:previous|prior)\s+page)|"
        r"return\s+to\s+the\s+(?:previous|prior)\s+page"
    )
    context = (
        r"(?:\s+(?:en\s+(?:el|este)\s+navegador|"
        r"in\s+(?:the|this|current)\s+(?:browser|tab)))?"
    )
    prefix = r"(?:(?:por\s+favor|please)\s*[,;:]?\s+)?"
    courtesy = r"(?:\s*,?\s*(?:por\s+favor|please))?"
    if re.fullmatch(
        rf"{prefix}(?:{spanish_head}\s+(?:{spanish_target})|{english_request})"
        rf"{context}{courtesy}",
        folded,
    ) is None:
        return None
    return {"action": "back"}


def browser_new_tab_arguments(text: str) -> dict[str, str] | None:
    """BROWSER1493 «abrí una pestaña nueva», «abre una nueva pestaña», «open a
    new tab»: one complete new-tab request in the product's browser; None for
    anything else (a named browser, a URL, a tab to close, a deferred or
    prohibited request keep their own reading)."""

    if not text or len(text) > 16_384:
        return None
    folded = _fold(text).strip(" ¿?¡!. ")
    if _has(folded, r"\b(?:chrome|opera|edge|firefox|brave|no\b|nunca|jamas|never|don't|do\s+not|cierra|cerra|close)\b|https?://|www\."):
        return None
    prefix = r"(?:(?:por\s+favor|please)\s*[,;:]?\s+)?(?:(?:podes|puedes|podrias|can\s+you|could\s+you)\s+)?"
    courtesy = r"(?:\s*,?\s*(?:por\s+favor|please|porfa))?"
    spanish = (
        r"(?:abri|abre|abrime|abreme|abrir|crea|creame|creá|nueva)\s+"
        r"(?:(?:una|otra)\s+)?(?:(?:nueva|otra)\s+)?pestana(?:\s+nueva)?"
        r"(?:\s+(?:en\s+(?:el|este)\s+navegador))?"
    )
    english = (
        r"open\s+(?:a\s+)?(?:new|another)\s+tab(?:\s+in\s+(?:the|this)\s+browser)?|new\s+tab"
    )
    if re.fullmatch(rf"{prefix}(?:{spanish}|{english}){courtesy}", folded) is None:
        return None
    return {"action": "new_tab"}


def browser_close_all_tabs_arguments(text: str) -> dict[str, str] | None:
    """H0444 «cerrá todas las pestañas de chrome», «close all tabs»: close every
    open tab in the product's own browser (owner decision 2026-09-17: on the tabs
    the tanda itself opened, never the owner's own sessions).  None for a single
    tab, for closing the browser application, for a prohibition or a quoted
    literal; the named browser is the person's word, the product uses its own
    controlled browser."""

    if not text or len(text) > 16_384:
        return None
    folded = _fold(text).strip(" ¿?¡!. ")
    if _has(folded, r"\bno\b|\bnunca\b|\bjamas\b|\bnever\b|don't|do\s+not"):
        return None
    prefix = r"(?:(?:por\s+favor|please)\s*[,;:]?\s+)?(?:(?:podes|puedes|podrias|can\s+you|could\s+you)\s+)?"
    courtesy = r"(?:\s*,?\s*(?:por\s+favor|please|porfa))?"
    named = r"(?:\s+(?:de|del|of|in)\s+(?:el\s+|the\s+|mi\s+|my\s+)?(?:navegador|browser|chrome|opera(?:\s*gx)?|edge|brave|firefox))?"
    spanish = (
        r"(?:cierra|cierre|cerra|cerrame|cierrame|cerrar)\s+"
        r"(?:todas\s+)?(?:las\s+)?pestanas(?:\s+abiertas)?" + named
    )
    english = (
        r"close\s+(?:all\s+)?(?:the\s+|my\s+)?(?:open\s+)?tabs" + named
    )
    if re.fullmatch(rf"{prefix}(?:{spanish}|{english}){courtesy}", folded) is None:
        return None
    return {"action": "close_all"}


def _historical_note_search_request(text: str) -> bool:
    """Recognize a request to retrieve old/overdue notes by their topic."""

    folded = _strip_request_envelope(_fold(text))
    return (
        re.fullmatch(
            r"(?:puedes\s+)?(?:tomar|traer|buscar|encuentra)\s+"
            r"(?:mis\s+)?(?:notas?|apuntes?)\s+\S.{0,120}"
            r"\b(?:atrasad[oa]s?|antigu[oa]s?|pasad[oa]s?)\b.{0,80}"
            r"\b(?:pasado|anteriores?|antes)\b[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )


def _stored_note_search_query(text: str) -> str | None:
    """Return the literal title/topic of one explicitly stored note lookup."""

    folded = _strip_request_envelope(_fold(text))
    match = re.fullmatch(
        r"(?:sacar|saca|traer|trae|recuperar|recupera|retrieve|get|find)\s+"
        r"(?:(?:la|the)\s+)?(?:nota|note)\s+"
        r"(?P<query>\S(?:.{0,160}?\S)?)\s+"
        r"(?:que\s+(?:tengo|esta)\s+guardad[oa]|that\s+i\s+saved|saved)"
        r"[\s.!?]*",
        folded,
        re.IGNORECASE,
    )
    return match.group("query").strip() if match is not None else None


def _nominal_reminder_lookup_title(text: str) -> str | None:
    """Return the topic in a standalone plural reminder lookup."""

    folded = _fold(text).strip()
    if _has(folded, _BOUNDED_TEMPORAL_SELECTOR):
        return None
    found = re.match(
        r"^[^\w]*(?:reminders\s+(?:for|about)|"
        r"recordatorios\s+(?:de|para|sobre))\s+"
        r"(?P<title>.+?)[\s.!?]*$",
        folded,
    )
    if found is None:
        return None
    title = found.group("title").strip(" \t\r\n.,;:!?\"'")
    return title if title and len(title.encode("utf-8")) <= 1_024 else None


def _literal_known_file_search(text: str) -> dict[str, object] | None:
    """Bind a direct file-name request to the existing known-folder scopes."""
    body = _strip_request_envelope(text).strip()
    if _is_negative_effect_clause(_fold(body)) or _is_meta_or_tool_denial(_fold(body)):
        return None
    found = re.fullmatch(
        rf"{_SEARCH}\s+(?:(?:el|un|the|a)\s+)?(?:archivo|file)\s+"
        r"(?:(?:llamado|named)\s+)?"
        r"(?P<query>[^\s\"'“”‘’«»<>:/\\|?*;,]+\.[\w-]+)"
        r"(?:\s+(?:en|in)\s+(?:(?:el|la|las|mis|the|my)\s+)?"
        r"(?P<scope>(?:usual\s+)?Windows\s+folders|carpetas\s+(?:habituales\s+de\s+)?Windows|"
        r"documents?(?:\s+folder)?|documentos|downloads?(?:\s+folder)?|descargas|"
        r"desktop(?:\s+folder)?|escritorio))?"
        r"(?:,?\s+(?:por\s+favor|please))?[.!]?",
        body,
        re.IGNORECASE,
    )
    if found is None:
        return None
    scope = _fold(found.group("scope") or "")
    folder = "all_known"
    for canonical, pattern in (
        ("documents", r"(?:documents?(?: folder)?|documentos)"),
        ("downloads", r"(?:downloads?(?: folder)?|descargas)"),
        ("desktop", r"(?:desktop(?: folder)?|escritorio)"),
    ):
        if re.fullmatch(pattern, scope):
            folder = canonical
            break
    return {"folder": folder, "query": found.group("query")}


# MASSIVE recommendation_locations / recommendation_movies (dev corpus 2026-09-23): «dónde hay un buen bar de
# vinos cerca de mí», «me gustaría saber cuáles son los pubs mejor valorados de la zona», «show me reviews of my
# nearest location food court», «recomendar una película en mi área». A kind of public place sought near the
# person or by its rating, or what the cinemas near them show, is the public world: it is looked up, never asked
# back («¿pubs con buena reputación o con más reseñas?») nor refused. «Near me» sends nothing of the person's.
_PUBLIC_PLACE = (
    r"\b(?:pubs?|bar|bares|bars|restaurantes?|restaurants?|panaderias?|bakery|bakeries|tiendas?|stores?|shops?|"
    r"cines?|cinemas?|movie\s+theaters?|cafeterias?|coffee\s+shops?|farmacias?|pharmacy|pharmacies|hoteles?|"
    r"hotels?|gasolineras?|gas\s+stations?|supermercados?|supermarkets?|gimnasios?|gyms?|pizzerias?|"
    r"food\s+courts?|museos?|museums?|discotecas?|nightclubs?|librerias?|bookstores?|heladerias?|"
    r"cajeros?|atms?|lavanderias?|laundromats?|peluquerias?|barber\s+shops?|"
    # Tanda 3 paraphrases «top rated pizza places near me», «best tacos near me», «busca un café cerca de mi casa»:
    # a place said by its kind or by the food it serves.
    r"places?|lugar(?:es)?|spots?|cafes?|tacos|taquerias?|sushi|pizzas?|hamburguesas?|burgers?|comida|food|"
    r"hospitales?|hospitals?|clinicas?|clinics?|bancos?|banks?|parques?|parks?|veterinarias?|"
    # MASSIVE recommendation_locations (dev corpus 2026-09-24) «tiendas de comestibles», «patio de comidas».
    r"comestibles|groceries|grocery\s+stores?|patios?\s+de\s+comidas?)\b"
)
# Tanda 3 paraphrases of «busca un restaurante en mi zona»: «gasolineras cercanas», «farmacias abiertas cerca», «por
# aquí», «around here», «close to me» say the same nearness.
_NEAR_THE_PERSON = (
    r"\b(?:cerca\s+de\s+(?:mi|aqui|aca|donde\s+estoy)|cerca(?=[\s.!?]*$)|cercan[oa]s?|near\s+(?:me|here|by)|nearby|"
    r"nearest|closest|close\s+(?:to\s+me|by)|por\s+(?:aqui|aca)|around\s+(?:here|me|town)|in\s+town|"
    # MASSIVE recommendation_locations / takeaway_query (dev corpus 2026-09-24) «qué bares hay a mi alrededor», «en mi
    # vecindario», «más cercano a mi ubicación», «alrededor del centro», «holidays in my location».
    r"a\s+mi\s+alrededor|alrededor\s+(?:mio|mia|de\s+(?:mi|aqui|aca)|del\s+centro)|"
    r"(?:en|de|a)\s+(?:mi|la|esta|este)\s+(?:zona|area|ciudad|barrio|comuna|pueblo|region|provincia|pais|vecindario|"
    r"ubicacion|localidad|sector)|"
    r"(?:in|around)\s+(?:my|the|this)\s+(?:local\s+)?(?:area|city|neighbou?rhood|town|region|country|location)|"
    r"near\s+my\s+location|local\s+area|"
    r"en\s+un\s+radio\s+de|within\s+(?:a\s+)?\w+\s+(?:miles?|km|kilometers?|kilometres?))\b"
)
_PLACE_RATED = (
    r"\b(?:mejor(?:es)?\s+valorad[oa]s?|mejores|best|top|(?:highly|best|top)[\s-]rated|rating|ratings|"
    r"reviews?|resenas?|opiniones|recomendad[oa]s?|recommended)\b"
)
_SHOWING_FILMS = r"\b(?:peliculas?|pelis?|movies?|films?|estrenos?|cartelera|showtimes?)\b"
_IN_THEATERS = r"\b(?:cines?|cinemas?|(?:movie\s+)?theat(?:er|re)s?|at\s+the\s+movies|cartelera)\b"
# MASSIVE recommendation_locations «hay algún lugar chino en malasaña»: whether a kind of place is in a place named.
_PLACE_IN_A_PLACE = (
    r"^[¿¡\s]*(?:hay|habra|existe|existen|is\s+there|are\s+there)\s+"
    r"(?:(?:algun|alguna|algunos|algunas|un|una|unos|unas|any|an?|some)\s+)?(?:\w+\s+){0,2}?"
    + _PUBLIC_PLACE[2:]
    + r".{0,40}\b(?:en|in|near|cerca\s+de|around)\s+\w"
)


def cinema_listing(text: str) -> bool:
    """MASSIVE recommendation_movies «what movies are playing at the movies tonight», «movies that are playing near
    me»: what the cinemas show, never what this PC plays."""

    return _has(text, _SHOWING_FILMS) and (_has(text, _NEAR_THE_PERSON) or _has(text, _IN_THEATERS))


# Uso real tanda 4c «en qué lugares puedo pedir comida para llevar cerca» and «dime que esta pasando en mi ciudad»
# were searched without the place and found portals and news of another country. Near the person is near this
# PC: the search carries this PC's city (``nearby``; only the city name leaves, read from the PC's public
# address like the weather's). A request that names another place near which to look («cercanos al aeropuerto
# de Santiago», «en Madrid», «la ciudad de Nueva York») is about that place, never the person's.
_NEAR_ELSEWHERE = (
    r"\b(?:cerca\s+del?|cercan[oa]s?\s+(?:a|al|de|del)|mas\s+cerca\s+del?|near(?:est)?\s+to|closest\s+to|"
    r"close\s+to|near)\s+(?!(?:mi|me|mio|mia|aqui|aca|here|by|donde\s+estoy|where\s+i)\b)|"
    r"\b(?:ciudad|region|provincia|pais|zona|barrio|comuna|estado|pueblo|city|country|state|town|area)\s+"
    r"(?:de|of)\s+(?!(?:mi|my|aqui|here)\b)"
)
_PLACE_AFTER_IN = re.compile(r"\b(?:en|in|at)\s+(?P<word>[a-z][\w']*)")
_NOT_A_PLACE_WORD = frozenset(
    {
        "mi", "mis", "my", "la", "el", "los", "las", "lo", "un", "una", "unos", "unas", "the", "a", "an", "this",
        "these", "that", "esta", "este", "estos", "estas", "ese", "esa", "eso", "su", "sus", "your", "our",
        "nuestro", "nuestra", "que", "cual", "cuales", "donde", "what", "which", "where", "how", "linea",
        "online", "internet", "google", "casa", "home", "town", "general", "vivo", "persona", "person",
        "efectivo", "cash", "serio", "realidad", "total", "todo", "todos", "todas", "caso", "order",
    }
)


def near_the_person(text: str) -> bool:
    """The request looks for something near the person, and names no other place to look near (see above)."""

    folded = _fold(text)
    if not _has(folded, _NEAR_THE_PERSON) or _has(folded, _NEAR_ELSEWHERE):
        return False
    rest = re.sub(_NEAR_THE_PERSON, " ", folded)
    for found in _PLACE_AFTER_IN.finditer(rest):
        if found.group("word") not in _NOT_A_PLACE_WORD and not is_window_phrase(rest[found.start():]):
            return False
    return True


def _location_recommendation_request(text: str) -> bool:
    """Recognize a standalone request for public place recommendations."""

    return _has(
        text,
        r"^[^\w]*(?:lugar(?:es)?|sitios?)\s+(?:para|a\s+donde)\s+"
        r"(?:ir|salir|comer|visitar)\b.+|"
        r"^[^\w]*(?:places?|restaurants?|things?)\s+to\s+"
        r"(?:go|visit|eat|do)\b.+",
    ) or (
        (_has(text, _PUBLIC_PLACE) and (_has(text, _NEAR_THE_PERSON) or _has(text, _PLACE_RATED)))
        or _has(text, _PLACE_IN_A_PLACE)
        or cinema_listing(text)
    )


# Tanda 4 «dime que esta pasando en mi ciudad» was searched as the whole sentence and found the song «Dime»: the
# words that ask to be told («dime», «decime», «dígame», «cuéntame», «tell me», «can you tell me», «quiero
# saber», «i'd like to know», «do you know») are the request, never what is looked up.
_INFORMATION_ASK = re.compile(
    r"(?:(?:(?:me\s+)?(?:puedes|podes|podrias|podria|puede)\s+)?(?:decir|contar|explicar|hablar)(?:me|nos)|"
    r"(?:can|could|would|will)\s+you\s+(?:tell|show)\s+(?:me|us)|"
    r"dime|decime|digame|diganme|dinos|decinos|cuentame|contame|cuentanos|explicame|explicanos|hablame|"
    r"tell\s+(?:me|us)|let\s+me\s+know|"
    r"(?:quiero|quisiera|necesito|me\s+gustaria)\s+saber|i\s+(?:want|need|would\s+like)\s+to\s+know|i'?d\s+like\s+to\s+know|"
    r"sabes|sabe|do\s+you\s+know)\s*[,:]?\s+"
    # What is asked about, not the preposition or the «whether» that introduces it.
    r"(?:(?:about|sobre|acerca\s+de|de|si|if|whether)\s+)?(?P<body>\S.*)"
)


def _last_words(surface: str, folded_tail: str) -> str:
    """The last words of ``surface``, as the person wrote them, that ``folded_tail`` (its folded end) counts."""

    count = len(folded_tail.split())
    return " ".join(surface.split()[-count:]) if count else ""


def public_query_body(text: str) -> str:
    """The request without its envelope and the words that ask to be told (see above), in the person's writing."""

    surface = _request_body_surface(text).strip()
    asked = _INFORMATION_ASK.fullmatch(_fold(surface).strip())
    if asked is None:
        return surface
    return _last_words(surface, asked.group("body")).strip(" ¿?¡!.,;:")


# WEB1451 «qué pasó hoy en el mundo», tanda 4 «qué está pasando en mi ciudad»: what happens today, or in a place,
# is the news of it. The place near the person («mi ciudad», «around here», «near me») is said the way an engine
# reads nearness, «noticias locales» / «local news»: the search already runs from this PC, and nothing of the
# person's is sent.
_HAPPENING = re.compile(
    r"^(?:que|what)\s+(?:paso|pasa|ha\s+pasado|esta\s+pasando|ocurrio|ocurre|sucedio|sucede|hay\s+de\s+nuevo|"
    r"happened|is\s+happening|'?s\s+happening|has\s+happened|is\s+going\s+on|'?s\s+going\s+on|is\s+new|'?s\s+new)"
    r"\s+(?P<scope>(?:hoy|today)\b.*|(?:en|in|around|near|por|alrededor|cerca)\s+\S.*|a\s+mi\s+alrededor\b.*)$"
)
# «que esta pasando en la»: a scope cut before its place is asked, not looked up. «qué pasa en mi pc», «what happens
# in the episode»: this PC, the person's own things or a story are not a place with news.
_CUT_SCOPE = r"^(?:en|in|around|near|por|alrededor|cerca)(?:\s+(?:el|la|los|las|the|a|an|mi|my|de|del|of))?$"
_NOT_A_NEWS_PLACE = (
    r"^(?:en|in)\s+(?:mi|mis|my)\b|\b(?:pc|computador(?:a)?|computer|equipo|ordenador|laptop|pantalla|screen|archivos?|"
    r"files?|carpetas?|folders?|windows|apps?|aplicacion(?:es)?|programas?|juegos?|games?|chat|grupo|group|"
    r"servidor|server|series?|peliculas?|movies?|libros?|books?|capitulos?|episodios?|episodes?|canciones?|songs?|"
    # «que pasó en la reunión de ayer»: the person's own meeting, class or home.
    r"reunion(?:es)?|meetings?|clases?|class(?:es)?|llamadas?|calls?|fiestas?|party|trabajo|work|oficina|office|"
    r"casa|home)\b"
)


def news_lookup_query(text: str) -> str | None:
    """The news query of a what-is-happening question (see above), or None."""

    body = public_query_body(text).strip(" ¿?¡!.")
    found = _HAPPENING.match(re.sub(r"^whats\b|^what's\b", "what 's", _fold(body)))
    if found is None or _has(found.group("scope").strip(), _CUT_SCOPE):
        return None
    if _has(found.group("scope"), SOCIAL_NETWORK):
        # «qué pasa en mis redes sociales» is the person's account, not news (lexicon.SOCIAL_NETWORK).
        return None
    if _has(found.group("scope"), _NOT_A_NEWS_PLACE) and not _has(found.group("scope"), _NEAR_THE_PERSON):
        return None
    if _has(found.group("scope"), rf"^(?:en|in|on)\s+(?:(?:el|la|the)\s+)?(?:{_HOLIDAY}|{_MONTH}|{_WEEKDAY_NAME})\b"):
        # «qué sucede en Año Nuevo» asks for a day of the calendar (the agenda), not for a place's news.
        return None
    english = _has(_fold(body), r"^what\b")
    scope = found.group("scope")
    # «around town» is near; «around the world» is not, nor «en la ciudad de Nueva York» (tanda 4c).
    if near_the_person(scope):
        return "local news" if english else "noticias locales"
    written = _last_words(body, scope)
    if english:
        return "news " + written
    return "noticias de " + written if _has(scope, r"^(?:hoy|today)\b") else "noticias " + written


# MASSIVE recommendation_events / qa_factoid (dev corpus 2026-09-23): «hay algún evento deportivo mañana en
# chicago», «show me nearby musical events», «cuál es la diferencia entre el calendario romano y el gregoriano».
# The person's calendar holds their own events; an event of a public kind or near them, and a calendar system,
# belong to the public world. Only «mi calendario», «tengo…» ask for their own.
_PUBLIC_EVENT = (
    r"\b(?:eventos?|events?)\s+(?:deportiv[oa]s?|musicales?|culturales?|publicos?|gratuitos?|gratis|emocionantes?|"
    r"interesantes?|locales?|sports?|music(?:al)?|cultural|public|free|local|exciting|interesting)\b|"
    r"\b(?:sports?|music(?:al)?|cultural|local|live|free)\s+events?\b"
)
_CALENDAR_SYSTEM = (
    r"\b(?:calendarios?|calendars?)\s+(?:romano|gregoriano|juliano|chino|lunar|maya|azteca|hebreo|judio|islamico|"
    r"musulman|escolar|academico|laboral|deportivo|roman|gregorian|julian|chinese|mayan|aztec|hebrew|jewish|"
    r"islamic|school|academic)\b|\b(?:diferencias?\s+entre|difference\s+between)\b"
)
_OWN_AGENDA = r"\b(?:mi|mis|my)\s+(?:calendario|calendar|agenda|eventos?|events?)\b|\b(?:tengo|tenemos|i\s+have|do\s+i\s+have)\b"


_CURRENCY = (
    r"\b(?:euros?|dolar(?:es)?|dollars?|pesos?|yen(?:es)?|libras?|pounds?|rupias?|rupees?|dirhams?|dirhames|"
    r"francos?|francs?|reales|reais|yuan(?:es)?|soles|bolivares|bitcoins?|libras?\s+esterlinas?)\b"
)


# MASSIVE recommendation_events (dev corpus 2026-09-24) «dime todos los eventos que ocurren en milán», «hay
# exposiciones caninas cerca de la ciudad de nueva york»: gatherings in a place named are the public world's too. A
# time after «en» («eventos en junio», «en la tarde») or an agenda («en mi calendario») is not a place.
_EVENT_KIND = (
    r"\b(?:eventos?|events?|exposicion(?:es)?|exhibicion(?:es)?|exhibitions?|ferias?|fairs?|festivales?|festivals?|"
    r"conciertos?|concerts?|espectaculos?|feriados?|festivos?|holidays?)\b"
)
_EVENT_PLACE = (
    r"\b(?:en|in|near|cerca\s+de|around|por)\s+(?!favor\b|(?:mi|mis|my|tu|tus|your|nuestr[oa]s?|our)\b)"
    r"(?!(?:(?:el|la|los|las|the|this|next|este|esta)\s+)?"
    rf"(?:hoy|manana|today|tomorrow|tonight|semana|week|weekend|fin|mes|month|ano|year|verano|invierno|otono|"
    rf"primavera|summer|winter|spring|noche|tarde|night|evening|morning|futuro|future|pasado|past|agenda|calendario|"
    rf"calendar|outlook|lista|list|{_MONTH}|{_WEEKDAY_NAME}|\d))\w"
)
# «añade un evento que empiece a las tres en sevilla», «por favor borra ese evento»: an order on the agenda is the
# person's own event, wherever it happens.
_AGENDA_ORDER = (
    r"\b(?:anad\w*|agreg\w*|crea|crear|creame|agenda|agendar|agendame|anota\w*|apunta\w*|programa\w*|reserva\w*|"
    r"cancela\w*|borra\w*|elimina\w*|recuerda\w*|recordar\w*|recordame|mueve|mover|cambia\w*|pon|ponme|add|create|"
    r"schedule|book|cancel|delete|remove|remind|move|reschedule|set\s+up|put)\b"
)


def public_event_subject(folded: str) -> bool:
    """Events of a public kind, near the person or in a place, or a calendar system: not the person's agenda."""

    if _has(folded, _OWN_AGENDA):
        return False
    return (
        _has(folded, _PUBLIC_EVENT)
        or (
            _has(folded, _EVENT_KIND)
            and (_has(folded, _NEAR_THE_PERSON) or _has(folded, _EVENT_PLACE))
            and not _has(folded, _AGENDA_ORDER)
        )
        or _has(folded, _CALENDAR_SYSTEM)
    )


# H0081 «Toma control de mi pc, quiero que abras opera gx y entras a pivigames»
# (WEB1883/1885 la dejaron abierta: el destino llega sin dominio, no hay URL que
# fundamentar y el turno preguntaba «¿Quieres que abra Opera GX y entre en
# pivigames?» en vez de entrar). Un sitio nombrado con una sola palabra sin
# punto, en un navegador nombrado, se resuelve como el destino simbólico sin
# navegador: la búsqueda verificada da la URL y la navegación nombrada la abre
# (CHAIN1931 ya fundamenta browser.navigate.named con el primer resultado
# verificado). Formas: «abre <navegador> y entra a <sitio>», «quiero que abras
# <navegador> y entres a <sitio>», «entra a <sitio> en <navegador>», «open
# <browser> and go to <site>». Un dominio, una URL, un nombre público cerrado
# (youtube, gmail…) o una aplicación del catálogo no pasan por aquí.
_NAMED_BROWSER_SITE_BROWSER = (
    r"(?:el\s+|the\s+)?(?:navegador\s+|browser\s+)?"
    r"(?P<browser>opera\s*gx|opera|google\s+chrome|chrome|microsoft\s+edge|edge|brave)"
)


_NAMED_BROWSER_SITE_ENTRY = (
    r"(?:entr(?:a|as|e|es|ale|ate|ame)|entrar|ve|anda|andate|andá|navega|navegar|"
    r"metete|meteme|llevame|go|navigate|take\s+me|head)\s+(?:a|al|to|en|into|over\s+to)\s+"
    r"(?:la\s+pagina\s+(?:de\s+)?|the\s+(?:site|page)\s+(?:of\s+)?)?"
    r"(?P<site>[a-z0-9][a-z0-9_-]{2,40})"
)


_NAMED_BROWSER_SITE_HEAD = (
    r"^[¿?¡!\s]*(?:(?:por\s+favor|please)\s*[,;:]?\s*)?"
    r"(?:(?:quiero|necesito|quisiera|i\s+want|i\s+need|i'd\s+like)\s+"
    r"(?:que\s+|you\s+to\s+)?)?(?:me\s+)?"
)


_NAMED_BROWSER_SITE_REQUEST = re.compile(
    _NAMED_BROWSER_SITE_HEAD
    + r"(?:abr(?:e|i|as|is|ime|ir|a|an)|open|launch)\s+" + _NAMED_BROWSER_SITE_BROWSER
    + r"\s*(?:,|;|\s+y\s+(?:luego\s+|despues\s+)?(?:que\s+)?|\s+and\s+(?:then\s+)?|\s+luego\s+|\s+then\s+)\s*"
    + _NAMED_BROWSER_SITE_ENTRY + r"[\s.!?]*$"
    + r"|" + _NAMED_BROWSER_SITE_HEAD + _NAMED_BROWSER_SITE_ENTRY.replace("(?P<site>", "(?P<site2>")
    + r"\s+(?:en|in|con|with|usando|using)\s+" + _NAMED_BROWSER_SITE_BROWSER.replace("(?P<browser>", "(?P<browser2>")
    + r"[\s.!?]*$",
    re.IGNORECASE,
)


_INSTALLED_BROWSER_SEARCH = re.compile(
    r"^[¿?¡!\s]*(?:abre|abrí|abri|abrir|open)\s+(?:un|el|a|the|any)\s+(?:navegador|browser)"
    r"(?:\s+(?:que\s+tengas(?:\s+instalado)?|que\s+tengas\s+a\s+mano|instalado|cualquiera|"
    r"(?:that\s+)?(?:you\s+have\s+)?installed|you\s+have))?"
    r"\s*(?:,\s*|\s+(?:y|and)\s+)(?:busca|buscá|buscar|search(?:\s+for)?)\s+(?P<query>.+?)\s*[.!?]*$",
    re.IGNORECASE,
)


def _installed_browser_search_query(text: str) -> str | None:
    """WEB1455 «Abre un navegador que tengas instalado y busca Windows 11 settings»:
    the person asks for any installed browser and a search in it; the query keeps
    its own spelling (quotation marks removed). None for any other shape."""

    match = _INSTALLED_BROWSER_SEARCH.match(text.strip())
    if match is None:
        return None
    query = match.group("query").strip().strip("\"'“”«»").strip()
    if (
        not query
        or len(query.encode("utf-8")) > 512
        or any(ord(character) < 32 for character in query)
        or _has(_fold(query), r"\b(?:en|on)\s+(?:google|opera|chrome|edge|firefox|brave)\b")
    ):
        return None
    return query


_BROWSER_SEARCH_IN_BROWSER = re.compile(
    r"^[¿?¡!\s]*(?:(?:por\s+favor|please|podes|podrias|puedes|can\s+you|could\s+you)\s*,?\s*)?"
    r"(?:"
    # «abrí una búsqueda de X en mi navegador», «open a search for X in my browser»
    r"(?:abre|abrí|abri|abrir|abrime|open)\s+(?:una|la|a|the)\s+(?:busqueda|búsqueda|search)\s+(?:de|sobre|for|of|on)\s+(?P<q1>.+?)|"
    # «buscá X en mi navegador», «search X in the browser»
    r"(?:busca|buscá|buscar|buscame|buscáme|search(?:\s+for)?|look\s+up)\s+(?P<q2>.+?)|"
    # «abrí X en mi navegador» (a topic, not a site: sites keep their own reader)
    r"(?:abre|abrí|abri|abrir|abrime|open)\s+(?P<q3>.+?)"
    r")"
    r"\s+(?:en|in|on)\s+(?:mi|el|tu|the|my|your|un|a)\s+(?:navegador|browser)"
    r"(?:\s*,?\s*(?:por\s+favor|please))?\s*[.!?]*$",
    re.IGNORECASE,
)


_BROWSER_SEARCH_PRONOUN = re.compile(
    r"^[¿?¡!\s]*(?:.*?\b(?:o\s+mejor|mejor|or\s+better|or)\s+)?"
    r"(?:abrelo|ábrelo|abrilo|abrila|abrela|ábrela|abre\s+eso|abrí\s+eso|abre\s+esto|open\s+it|open\s+that|buscalo|búscalo|buscala|búscala|search\s+it|search\s+that|look\s+it\s+up)"
    r"\s+(?:en|in|on)\s+(?:mi|el|tu|the|my|your|un|a)\s+(?:navegador|browser)"
    r"(?:\s*,?\s*(?:por\s+favor|please))?\s*[.!?]*$",
    re.IGNORECASE,
)


def _browser_search_query(text: str) -> str | None:
    """Owner session 2026-09-21 «abre una busqueda de power automate en mi
    navegador»: a search the person wants in their own browser is the reviewed
    navigation to the public search page with that query (as the installed-
    browser shape of WEB1455). The query keeps its spelling; a URL, a bare site
    or a named browser keep their own readers; None for any other shape."""

    match = _BROWSER_SEARCH_IN_BROWSER.match(text.strip())
    if match is None:
        return None
    query = (match.group("q1") or match.group("q2") or match.group("q3") or "").strip().strip("\"'“”«»").strip()
    folded = _fold(query)
    if (
        not query
        or len(query.encode("utf-8")) > 200
        or any(ord(character) < 32 for character in query)
        or _has(folded, r"https?://|www\.|\.(?:com|net|org|es|cl|ar|io|gov|edu)\b")
        or _has(folded, r"\b(?:google|opera|chrome|edge|firefox|brave|youtube|gmail|github|chatgpt)\b")
        or _has(folded, r"^(?:lo|la|los|las|eso|esto|it|that|this|algo|something|nada|nothing|una\s+pestana|una\s+pestaña|a\s+tab|un\s+link|a\s+link)$")
        or (match.group("q3") and _has(folded, r"^(?:el|la|los|las|un|una|the|a|an)\s+(?:navegador|browser|link|enlace|pagina|página|page|pestana|pestaña|tab)\b"))
    ):
        return None
    return query


def _browser_search_pronoun_request(text: str) -> bool:
    """«pasame un link para verlo yo mismo, o mejor abrelo en mi navegador»,
    «abrilo en mi navegador»: the thing to open in the browser is what the
    conversation was about; the caller supplies it from the previous turn."""

    return _BROWSER_SEARCH_PRONOUN.match(text.strip()) is not None


def _completed_browser_search_pronoun_request(
    text: str, previous_user_text: str | Iterable[str] | None,
) -> str | None:
    """The pronoun form completed with the entity of the last question about a
    thing («Dime que es power automate» → «buscá power automate en mi
    navegador»); `previous_user_text` may be the last user text or the recent
    user texts, most recent first (the entity may sit two turns back)."""

    if not previous_user_text or not _browser_search_pronoun_request(text):
        return None
    candidates = [previous_user_text] if isinstance(previous_user_text, str) else list(previous_user_text)
    for candidate in candidates[:4]:
        entity = _entity_lookup_query(str(candidate))
        if entity is not None:
            return "buscá " + entity + " en mi navegador"
    return None


def browser_search_pronoun_intent(text: str, history: object, available_operations: Iterable[str]) -> EffectIntent | None:
    """«abrelo en mi navegador» read against the recent user turns of the history."""

    if "browser.navigate" not in frozenset(available_operations) or not isinstance(history, list):
        return None
    items = [item for item in history if isinstance(item, dict)]
    if items and items[-1].get("role") == "user" and items[-1].get("content") == text:
        items = items[:-1]
    recent = [str(item.get("content") or "") for item in reversed(items) if item.get("role") == "user"]
    completed = _completed_browser_search_pronoun_request(text, recent)
    return EffectIntent(("browser.navigate",), (completed,)) if completed is not None else None


# Public web services whose canonical destination the argument builder knows
# (`_explicit_browser_navigation_arguments`). A closed list, never a guess.
_NAMED_PUBLIC_SITE = r"(?:youtube|gmail|github|chatgpt)"


def _review_web_and_browser_effects(
    matches: list[tuple[int, int, str]],
    folded: str,
    head: str,
    *,
    context_browser: str | None,
    web_search_requested: bool,
) -> None:
    """Append explicit web-search, navigation, page, and tab effects."""

    if _installed_browser_search_query(folded) is not None and context_browser is None:
        # WEB1455: any installed browser and a search in it is one reviewed
        # navigation to the product's public search page with that query.
        if _append(matches, folded, "browser.navigate", r"\b(?:abre|abri|abrir|open)\b"):
            _, priority, operation = matches[-1]
            matches[-1] = (0, priority, operation)
        return
    if _browser_search_query(folded) is not None and context_browser is None:
        # Owner 2026-09-21 «abre una busqueda de power automate en mi navegador»,
        # «buscá X en mi navegador»: the same reviewed navigation to the search page.
        if _append(matches, folded, "browser.navigate", r"\b(?:abre|abri|abrir|abrime|open|busca|buscar|buscame|search|look)\b"):
            _, priority, operation = matches[-1]
            matches[-1] = (0, priority, operation)
        return
    if _youtube_search_query(folded) is not None and context_browser is None:
        # WEB1481 «buscá videos de gatos en youtube»: one reviewed navigation
        # to YouTube's results page with that query.
        if _append(matches, folded, "browser.navigate", r"\b(?:busca|buscar|buscame|search|find)\b"):
            _, priority, operation = matches[-1]
            matches[-1] = (0, priority, operation)
        return
    if _explicit_google_search_query(folded) is not None:
        browser = _named_browser(folded) or context_browser
        if browser is None or browser in NAMED_CDP_BROWSERS:
            if _append(
                matches,
                folded,
                "browser.navigate.named" if browser else "browser.navigate",
                rf"\b{_SEARCH}\b",
            ):
                # Check negation at the real verb before retaining the Google
                # heading as part of the same evidence clause.
                _, priority, operation = matches[-1]
                matches[-1] = (0, priority, operation)
        # A named browser has no generic substitute. Do not fall through to
        # Bing RSS when the public navigation contract cannot represent it.
        return

    explicit_public_lookup = (
        _head_is(head, _SEARCH)
        and _has(folded, rf"\b{_SEARCH}\b")
        and _has(
            folded,
            r"\b(?:api\s+publica|public\s+api|app\s*id|steam\s+store|"
            r"en\s+internet|on\s+the\s+internet)\b",
        )
        and not _has(folded, r"\b(?:archivos?|files?|boton|button)\b")
    )
    entertainment_lookup = (
        _head_is(head, r"(?:donde|where|hablame)")
        and _has(folded, r"\b(?:pelicula|peliculas|movie|movies|film)\b")
        and _has(
            folded,
            r"\b(?:ver|watch|stream|hablame|about|buena|good|donde|where)\b",
        )
    )
    location_recommendation = _location_recommendation_request(folded)
    if (
        (explicit_public_lookup and not web_search_requested)
        or entertainment_lookup
        or location_recommendation
    ):
        _append(
            matches,
            folded,
            "web.search",
            (
                rf"\b{_SEARCH}\b"
                if explicit_public_lookup
                else (
                    r"\b(?:lugar(?:es)?|sitios?|places?|restaurants?|things?)\b"
                    if location_recommendation
                    else r"\b(?:donde|where|hablame)\b"
                )
            ),
        )

    google_search_in_open_browser = (
        context_browser is not None
        and _head_is(head, _SEARCH)
        and _has(folded, rf"\b{_SEARCH}\b")
        and _has(folded, r"\b(?:en|on)\s+google\b")
    )
    browser_search = (
        context_browser is not None
        and _head_is(head, _SEARCH)
        and _has(folded, rf"\b{_SEARCH}\b")
        and not _has(
            folded,
            r"\b(?:spotify|notas?|notes?|tareas?|tasks?|archivos?|files?)\b",
        )
    )
    if (
        web_search_requested or google_search_in_open_browser or browser_search
    ) and _has(folded, rf"\b{_SEARCH}\b"):
        _append(matches, folded, "web.search", rf"\b{_SEARCH}\b")
        if browser_search:
            _append(
                matches,
                folded,
                (
                    "browser.navigate.named"
                    if context_browser in NAMED_CDP_BROWSERS
                    else "browser.navigate"
                ),
                rf"\b{_SEARCH}\b",
                priority=1,
            )
    has_url = _has(folded, r"https?://\S+")
    has_bare_domain = _has(
        folded,
        r"\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
        r"[a-z]{2,63}(?:/\S*)?\b",
    ) and not _has(
        folded,
        r"\b(?:archivo|file|carpeta|folder|escritorio|desktop|"
        r"documentos|documents|descargas|downloads)\b",
    )
    navigation_verbs = rf"(?:{_OPEN}|navega|navegar|navigate|ve|go|llevame|anda|andar|entra|entrar|vete)"
    navigate = _head_is(
        head,
        navigation_verbs,
    ) and _has(
        folded,
        rf"\b{navigation_verbs}\b",
    )
    named_browser = _named_browser(folded) is not None or context_browser is not None
    if has_url and navigate:
        streaming_url = _has(
            folded,
            r"https?://(?:www\.)?(?:youtube\.com|youtu\.be|netflix\.com|primevideo\.com)(?:[/?:#]|$)",
        )
        _append_all(
            matches,
            folded,
            (
                "streaming.navigate"
                if streaming_url
                else "browser.navigate.named"
                if named_browser
                else "browser.navigate"
            ),
            (
                rf"\b{navigation_verbs}\b"
                r"(?:(?!https?://)[^,;\r\n]){0,160}https?://\S+"
            ),
        )
    elif has_bare_domain and navigate:
        _append(
            matches,
            folded,
            "browser.navigate.named" if named_browser else "browser.navigate",
            rf"\b{navigation_verbs}\b",
        )
    elif (
        navigate
        and _has(folded, r"\b(?:pagina|page|sitio|site|website)\b")
        and _has(
            folded,
            r"\b(?:pagina|page|sitio|site|website)\b.{1,120}\S",
        )
        # Tanda 3 «Go to página de inicio»: the start page alone is the PC's desktop.
        and not minimize_all_request(folded)
    ):
        _append(
            matches,
            folded,
            "web.search",
            rf"\b{navigation_verbs}\b",
        )
        _append(
            matches,
            folded,
            "browser.navigate.named" if named_browser else "browser.navigate",
            rf"\b{navigation_verbs}\b",
            priority=1,
        )
    elif (
        navigate
        and _has(folded, r"\b(?:youtube)\b")
        and _has(folded, r"\b(?:navegador|browser|web)\b")
    ):
        _append(
            matches,
            folded,
            "browser.navigate",
            rf"\b{navigation_verbs}\b",
        )
    elif (
        _head_is(head, r"(?:llevame|take|ve|go|navega|navigate)")
        and _has(folded, r"\bwikipedia\b")
        and not _has(folded, r"\b(?:archivo|file|carpeta|folder)\b")
    ):
        _append(
            matches,
            folded,
            "browser.navigate",
            r"\bwikipedia\b",
        )
    elif (
        navigate
        and _has(folded, rf"\b{navigation_verbs}\s+(?:a\s+|al\s+|to\s+)?{_NAMED_PUBLIC_SITE}\b")
        and not _has(
            folded,
            r"\b(?:archivo|file|carpeta|folder|nota|note|app|aplicacion|application|"
            r"programa|program|video|videos|cancion|song|musica|music)\b",
        )
    ):
        # WEB1257: «Abre youtube», «abrí gmail», «andá a github.com» name a public
        # web service, not an installed application; the argument builder owns
        # the closed canonical destination for each name. WEB1745 «abre youtube
        # en Chrome»: when the person names the browser, it is the named navigation.
        _append(
            matches,
            folded,
            "browser.navigate.named" if named_browser else "browser.navigate",
            rf"\b{navigation_verbs}\b",
        )
    browser_page_context = context_browser is not None or _has(
        folded,
        r"\b(?:actual|current|navegador|browser|web|sitio|site)\b",
    )
    browser_page_grounded = _browser_page_domain(folded)
    if (
        _head_is(head, _READ)
        and browser_page_context
        and browser_page_grounded
        and _has(folded, r"\b(?:pagina|page)\b")
        and _has(folded, rf"\b{_READ}\b")
    ):
        _append(
            matches,
            folded,
            "browser.page.read",
            r"\b(?:lee|leer|read)\b",
            priority=1,
        )
    # WEB1539 H0561 «resumime esta página», H0738 «resumime la página actual»:
    # summarizing this or the current page is reading the page open in the
    # browser session; «esta página» without a document word is that page.
    summary_heads = r"(?:resume|resumeme|resumime|resumi|resumir|resumelo|resumela|summarize|summarise|sum\s+up)"
    if (
        _head_is(head, summary_heads)
        and browser_page_grounded
        and _has(
            folded,
            r"\b(?:esta|this|the|la)\s+(?:pagina|page)\b"
            r"(?:\s+(?:actual|current|abierta|open|de\s+ahora))?",
        )
        and not _has(folded, r"\b(?:pdf|docx?|archivo|file|libro|book|documento|document)\b")
    ):
        _append(
            matches,
            folded,
            "browser.page.read",
            rf"\b{summary_heads}\b",
            priority=1,
        )
    if (
        _head_is(head, _LIST)
        and _has(folded, r"\b(?:pestanas|tabs)\b")
        and _has(folded, rf"\b{_LIST}\b")
    ):
        _append(matches, folded, "browser.tabs.list", r"\b(?:pestanas|tabs)\b")
    if (
        _head_is(head, r"(?:recarga|recargar|reload|refresh)")
        and browser_page_grounded
        and _has(folded, r"\b(?:recarga|recargar|reload|refresh)\b")
        and _has(folded, r"\b(?:pagina|page)\b")
    ):
        _append(
            matches,
            folded,
            "browser.control",
            r"\b(?:recarga|recargar|reload|refresh)\b",
        )


def web_download_request(text: str) -> dict[str, str | None] | None:
    """REOPEN1957 H0077 «descarga la imagen de portada de wikipedia.org y
    guardala en el escritorio»: the address (a host counts) and the known
    folder named as destination (Downloads when none)."""

    raw = _strip_request_envelope(str(text).strip()).rstrip(".!?")
    folded = _fold(raw)
    if _is_negative_effect_clause(folded) or _is_meta_or_tool_denial(folded):
        return None
    if not _has(folded, r"^[¿?¡!\s]*(?:descarga|descargar|descargame|baja|bajar|bajame|download|guarda|guardar|save)\b"):
        return None
    if _has(folded, r"\b(?:steam|epic|juego|game|app|aplicacion|programa|winget)\b"):
        return None
    address = re.search(
        r"(?P<url>https?://[^\s\"'<>]+|(?:[a-z0-9-]+\.)+(?:com|org|net|edu|gov|io|es|cl|ar|mx|info|wiki|dev|app)(?:/[^\s\"'<>]*)?)",
        raw,
        re.IGNORECASE,
    )
    if address is None:
        return None
    destination = re.search(
        rf"\b(?:en|on|in|a|to)\s+(?:(?:el|la|mi|my|the)\s+)?(?P<folder>{_KNOWN_FOLDER_WORDS}|imagenes|pictures)\b",
        folded,
    )
    folder = _KNOWN_FOLDER_ENUM.get(destination.group("folder"), "pictures") if destination is not None else None
    return {"url": address.group("url"), "folder": folder, "name": None}


# WEB1739: the browsers browser.navigate.named can drive over CDP (Chromium family). Firefox is
# recognised as a name but has no CDP endpoint, so it never becomes a named navigation.
NAMED_CDP_BROWSERS = frozenset({"opera", "opera_gx", "chrome", "edge", "brave"})


def _named_browser_match(text: str) -> re.Match[str] | None:
    browser = r"(?:opera gx|opera|google chrome|chrome|microsoft edge|edge|brave|firefox)"
    return _match(
        text,
        (
            # H0516 «Abre Opera GX, busca una receta …»: abrir un navegador por
            # su nombre al frente de la misión lo nombra igual que «navega con».
            rf"^[¿?¡!\s]*(?:navega|navegar|navigate|ve|go|abre|abri|abrime|abrí|open|launch)\s+"
            rf"(?:el|la|the)?\s*(?P<leading>{browser})\b|"
            rf"\b(?:usando|mediante|via|with|using)\s+"
            rf"(?:el|la|the)?\s*(?P<instrument>{browser})\b|"
            rf"\b(?:en|in)\s+(?:el|la|the)?\s*"
            rf"(?P<located>{browser})\b[\s?!.]*$"
        ),
    )


def _named_browser(text: str) -> str | None:
    found = _named_browser_match(text)
    if found is None:
        return None
    name = next(
        group
        for group in (
            found.group("leading"),
            found.group("instrument"),
            found.group("located"),
        )
        if group is not None
    )
    return {
        "opera gx": "opera_gx",
        "google chrome": "chrome",
        "microsoft edge": "edge",
    }.get(name.casefold(), name.casefold())


_VISIBLE_CLICK_NAVIGATE = (
    # UI1731 «Abre Steam y luego navega por la gui hasta biblioteca», «Abre Epic
    # Games y navega hasta la biblioteca»: walking the open client's interface
    # to a named section is a verified click on that visible label.
    r"(?:ve\s+a|vete\s+a|anda\s+a|andate\s+a|entra\s+(?:a|en)|metete\s+en|go\s+to|go\s+into|"
    r"navega(?:\s+por\s+(?:la\s+|el\s+|los\s+)?(?:gui|interfaz|interface|menu|menus|pantalla|ventana|app|aplicacion))?\s+(?:a|hacia|hasta)|"
    r"navigate(?:\s+(?:through|via)\s+the\s+(?:gui|interface|menus?))?\s+to)"
)


_VISIBLE_CLICK_WEB_DESTINATION = re.compile(
    r"wikipedia|https?://|www\.|\.com\b|\.org\b|\.net\b|\.io\b",
    re.IGNORECASE,
)


def _weather_asks_rain(user_text: str) -> bool:
    """The weather question asks about rain, rain gear or an amount of it
    («¿lloverá?», «¿me llevo el paraguas?», «how many inches»)."""

    return re.search(
        r"\b(?:llov\w*|lluvi\w*|llueve|rain\w*|paraguas|umbrella|chubasquero|impermeable|"
        r"pulgadas|inches|milimetros|millimeters)\b",
        _reading_fold(user_text),
    ) is not None


def weather_asks_whether_it_rains(user_text: str) -> bool:
    """M63 (v3f-final F-w01-t6 «¿va a llover donde vive mi hermana?» → «en ñuñoa»): whether it rains today or
    tomorrow, asked yes or no («¿va a llover?», «¿lloverá mañana?», «will it rain»), is answered plainly before its
    chance. Asked for the chance or an amount («¿qué probabilidad de lluvia hay?», «how many inches»), for rain gear
    («¿me llevo el chubasquero?») or for later days («el fin de semana», «el martes») the figures are the answer
    (uso real tandas 2, 6 and 8)."""

    folded = _reading_fold(user_text)
    return (
        re.search(r"\b(?:llov\w*|llueve|llueva|rain|raining|rains)\b", folded) is not None
        and re.search(
            r"\b(?:cuant\w*|how\s+(?:much|many)|pulgadas|inches|milimetros|millimeters|probabilidad\w*|"
            r"probabilit\w*|chances?|porcentaje|percent\w*)\b",
            folded,
        ) is None
        and not weather_asks_coming_days(user_text)
    )


def _weather_asks_tomorrow(user_text: str) -> bool:
    """The weather question is about tomorrow or a later day."""

    return weather_asks_later_day(user_text) or re.search(
        r"(?<!esta )\b(?:manana|tomorrow)\b", _reading_fold(user_text)
    ) is not None


# M58 (v3d-final F-s066 «¿hará bueno para San Juan?» → «En San Juan hay 28,5 °C ahora, despejado.», leaving out the
# drizzle at 94 % read for tomorrow): the weather asked in the future tense with no day named asks what is coming, so
# the answer carries the next day's read besides now. A day said («hoy», «esta tarde», «later today», a weekday) is
# that day's question.
_WEATHER_FUTURE = (
    r"\b(?:hara|llovera|nevara|estara|habra|saldra|va\s+a\s+(?:hacer|llover|nevar|estar|haber)|"
    r"will\s+(?:it|there)\b|(?:is|it'?s)\s+(?:it\s+)?going\s+to)\b"
)
_WEATHER_TODAY = r"\b(?:hoy|today|tonight|esta\s+(?:manana|tarde|noche)|later|mas\s+tarde|ahora|now)\b"


# M62 (v3e2-final F-p07-t1 «I must verify the weather in Foster City later today.» → «It is 11.7°C and clear…», the
# temperature at 00:45 with a maximum of 30 °C read for the day): a later part of today asks today's read (its maximum,
# minimum and rain), not only the weather now. Tomorrow or a later day is its own question.
_WEATHER_LATER_TODAY = (
    r"\b(?:later(?:\s+(?:on|today|tonight))?|this\s+(?:afternoon|evening)|tonight|mas\s+tarde|luego|"
    r"esta\s+(?:tarde|noche)|(?:hoy\s+)?(?:por|en)\s+la\s+(?:tarde|noche)|a\s+la\s+tarde|en\s+un\s+rato)\b"
)


def weather_asks_later_in_the_day(user_text: str) -> bool:
    """The weather is asked for a later part of today (``_WEATHER_LATER_TODAY``), not for tomorrow or a later day.
    What to wear or carry then («¿Debo ponerme scarf esta noche?») is its own question, answered from the
    temperature (uso real tanda 2)."""

    folded = _reading_fold(user_text)
    return (
        re.search(_WEATHER_LATER_TODAY, folded) is not None
        and not _weather_asks_tomorrow(user_text)
        and not weather_asks_coming_days(user_text)
        and re.search(_WEATHER_GEAR, folded) is None
    )


def weather_asks_future(user_text: str) -> bool:
    """The weather is asked in the future tense and no day is named (``_WEATHER_FUTURE``)."""

    folded = _reading_fold(user_text)
    return (
        re.search(_WEATHER_FUTURE, folded) is not None
        and re.search(_WEATHER_TODAY, folded) is None
        and not weather_asks_coming_days(user_text)
    )


# M60 (DEV-D w11-t1 «¿sabes si allá está lloviendo ahorita?», decided «¿Está lloviendo en Medellín ahora?»): rain
# asked in the present, in the progressive («está lloviendo», «is it raining») or with «now» («¿llueve ahora?»), is
# answered by the rain read now; the day's probability is another question. A later part of the day, tomorrow or a
# later day asks what is coming.
_WEATHER_RAIN_NOW = (
    r"\b(?:esta|estan)\s+(?:lloviendo|lloviznando|garuando)\b|\b(?:is\s+it|it\s+is|it'?s)\s+raining\b|"
    r"\bllueve\b[^.?!]{0,40}\b(?:ahora|ahorita|en\s+este\s+momento)\b|"
    r"\b(?:ahora|ahorita|en\s+este\s+momento)\b[^.?!]{0,40}\bllueve\b|\braining\s+(?:right\s+)?now\b"
)


def weather_asks_rain_now(user_text: str) -> bool:
    """The rain is asked now (``_WEATHER_RAIN_NOW``), not later today, tomorrow or on a later day."""

    folded = _reading_fold(user_text)
    return (
        re.search(_WEATHER_RAIN_NOW, folded) is not None
        and re.search(r"\b(?:tonight|esta\s+(?:noche|tarde)|mas\s+tarde|later)\b", folded) is None
        and not _weather_asks_tomorrow(user_text)
        and not weather_asks_coming_days(user_text)
    )


# What is never a public search, whatever the guard reads: the person's own
# data (semantic.web.names_own_data) and what is playing (the words would leave
# the PC; 00_IDENTIDAD: information comes in, content does not go out); someone
# pointed at and not named; a level for this PC; a sentence cut off before its
# object («hora actual en», «hay algún concierto próximo de») — that one is
# asked, not guessed.
_NOT_A_PUBLIC_LOOKUP = re.compile(
    r"\b(?:este|esta|this)\s+(?:cancion|tema|song|track|artista|artist|disco|album|video|podcast)\b|"
    r"\b(?:that|this)\s+(?:person|guy|man|woman)\b|\b(?:esa|esta|aquella)\s+persona\b|"
    r"\d\s*%|\bpor\s*ciento\b|\bpercent\b|"
    # Verification 2026-09-25 (layer A, real log «De donde sacaste esa info?»): where BAXY got what he just said,
    # or whether he made it up, is asked of BAXY, never of a page.
    r"\b(?:de\s+donde|donde)\s+(?:sacaste|sacas|encontraste|leiste)\b|\bwhere\s+did\s+you\s+(?:get|find|read)\b|"
    r"\b(?:lo\s+|la\s+|eso\s+)?(?:imaginaste|inventaste)\b|\bdid\s+you\s+make\s+(?:it|that|this)\s+up\b|"
    r"\b(?:de|del|en|a|al|el|la|los|las|un|una|para|con|por|sobre|entre|"
    r"the|of|in|at|to|for|on|with|about|a|an)[\s?.!¿¡]*$"
)


# M81 (DEV-D v3m D-p34-t3 «¿Cómo podría encontrar un listado de cápsulas del tiempo conocidas?» → «No encontré…»
# while the read held Wikipedia's category of them): where to find something is answered by naming where it is.
_WHERE_TO_FIND = re.compile(
    r"\b(?:como|donde|en\s+donde|de\s+donde)\s+(?:(?:lo|la|los|las|me)\s+)?(?:podria|puedo|podemos|se\s+puede|"
    r"puede|podre|pudiera)\s+(?:encontrar|conseguir|hallar|ver|leer|consultar|buscar)\b|"
    r"\b(?:where|how)\s+(?:can|could|do|would|should)\s+(?:i|we|one|you)\s+(?:find|get|see|read|look\s+up|access)\b|"
    r"\bwhere\s+(?:is|are)\s+(?:there\s+)?(?:a|an|the)\s+(?:list|listing|database|catalog|index|archive)\b"
)


def asks_where_to_find(text: str) -> bool:
    """The person asks where or how they could find something themselves (``_WHERE_TO_FIND``)."""

    return _WHERE_TO_FIND.search(_reading_fold(str(text or ""))) is not None


def question_names(text: str) -> set[str]:
    """The words a question writes with a capital that are not a sentence's first word (English «I» apart): the
    subject a search report must be about. Folded, without the quotes around them or an English possessive.

    M81 (DEV-D v3m D-p19-t2): «Yes, that's right. Who's in it?» made «Who's», the head of its second sentence, a name
    no page carries, and «…'After the Wedding'?» made «Wedding'» one with its closing quote; every faithful report of
    the cast died as off subject."""

    names: set[str] = set()
    opening = True
    for raw in str(text or "").split():
        word = raw.strip("¿¡?!.,;:\"'«»()“”‘’")
        if word and not opening and word[:1].isupper() and word != "I":
            name = _reading_fold(re.sub(r"['’]s$", "", word))
            if len(name) >= 2:
                names.add(name)
        opening = raw.rstrip("\"'»”’)")[-1:] in {".", "?", "!", ":"}
    return names


def not_a_public_lookup(objective: str) -> bool:
    """What the public-lookup guard never sends to the web (moved from ``__main__._names_own_data``)."""

    from .conversation import asks_for_code  # conversation reads web: imported when used
    from .messaging import _latest_email_domain  # messaging reads web's own-data words: imported when used

    folded = _fold(objective)
    # Uso real 2026-09-23 «he recibido algún correo desde el mediodía», «check
    # any mail from amazon» went to web.search: the person's received mail is
    # theirs, and a question about it never leaves the PC.
    return (
        _NOT_A_PUBLIC_LOOKUP.search(folded) is not None
        # M81: unfolded, so «mamá» keeps the accent that tells it from «mama».
        or names_own_data(str(objective or ""))
        or _latest_email_domain(folded)
        # M56 (v3c-final F-w14-t1 «escribeme un query de sql q me saque los users activos del ultimo mes» → the
        # guard read public_lookup, web.search failed): code asked for is written by the model, never looked up.
        or asks_for_code(objective)
    )


# M56 (v3c-final F-p06-t2 «aparcamiento en la Plaza de las Salesas en Madrid» → car parks of Cartagena told as
# Madrid's): the places a place search names its place to be in, read as the provider reads the query
# (OpenStreetMapPlaceSource.PlaceOf): after «en / in / cerca de / near», the parts after the first one.
_PLACE_LINK = re.compile(r"\b(?:cerca\s+del?|near|around|alrededor\s+del?|en|in|at)\s+(?P<place>[^?!.;]+)")
_PLACE_PART_SPLIT = re.compile(r"\s+(?:en|in)\s+|\s*,\s*")


def place_containers(query: str) -> tuple[frozenset[str], ...]:
    """The words of each place the searched place is said to be in («…en la Plaza de las Salesas en Madrid» →
    ({"madrid"},)); empty when the query names one place only."""

    found = _PLACE_LINK.search(_reading_fold(str(query or "")))
    if found is None:
        return ()
    parts = _PLACE_PART_SPLIT.split(found.group("place").strip(" ,:"))
    containers = (
        frozenset(word for word in re.findall(r"[a-z0-9]+", part) if len(word) >= 3 and word not in _PLACE_ARTICLES)
        for part in parts[1:]
    )
    return tuple(words for words in containers if words)


_PLACE_ARTICLES = frozenset({"del", "los", "las", "the"})


# M58 (v3d-final F-p05-t3 «Perdón, encuéntrame cerca de La Puntilla» after «… cerca de La Puntilla, El Puerto» → a car
# park of San Juan, Puerto Rico; F-p06-t3 «Mejor en calle Génova» in a conversation about Madrid): the town or region
# the conversation already fixed goes with a place the message names alone. Only for the same place said before with
# its town, or for a street or a square (never a town), and only the last town said; a place named with its own town
# keeps it. The person's writing is kept: the provider reads the capitals.
_SAID_PLACE = re.compile(r"\b(?:cerca\s+del?|near|around|alrededor\s+del?|en|in|at)\s+(?P<place>[^?!.;]+)", re.IGNORECASE)
_SAID_PLACE_PARTS = re.compile(r"\s+(?:en|in)\s+|\s*,\s*", re.IGNORECASE)
_STREET_OR_SQUARE = re.compile(
    r"^(?:(?:la|el|the)\s+)?(?:calle|c/|avenida|avda\.?|plaza|plazuela|paseo|pasaje|camino|ronda|glorieta|callejon|"
    r"street|st\.?|avenue|ave\.?|road|rd\.?|square|boulevard|blvd\.?|lane)\b"
)
_TRAILING_COURTESY = re.compile(r"(?:\s+(?:hoy|today|ahora|now|por\s+favor|porfa|please))+$", re.IGNORECASE)


def _without_article(place: str) -> str:
    return re.sub(r"^(?:la|el|los|las|the)\s+", "", _fold(place))


def _said_place_parts(text: str) -> tuple[str, ...]:
    """The place a message names after «en / cerca de / near» and the towns it says that place is in, as written
    («… cerca de La Puntilla, El Puerto» → («La Puntilla», «El Puerto»))."""

    found = _SAID_PLACE.search(str(text or ""))
    if found is None:
        return ()
    place = _TRAILING_COURTESY.sub("", found.group("place").strip(" ,:"))
    return tuple(part.strip(" ,:") for part in _SAID_PLACE_PARTS.split(place) if part.strip(" ,:"))


def place_fixed_by_conversation(place: str, said_before: Iterable[str]) -> str | None:
    """The town the conversation fixed for ``place`` (named alone), from the person's earlier messages, newest first;
    None when the last town said does not fit it or ``place`` already names its own."""

    place = " ".join(str(place or "").split())
    if not place or "," in place:
        return None
    for text in said_before:
        parts = _said_place_parts(text)
        if len(parts) < 2 or not parts[-1][:1].isupper():
            continue
        town = parts[-1]
        same_place = _without_article(parts[0]) == _without_article(place)
        if _fold(town) in _fold(place) or not (same_place or _STREET_OR_SQUARE.match(_fold(place))):
            return None
        return town
    return None


def place_query_in_conversation(query: str, said_before: Iterable[str]) -> str | None:
    """``query`` with the town the conversation fixed written after the place it names alone («Encuéntrame
    aparcamiento cerca de La Puntilla» → «Encuéntrame aparcamiento cerca de La Puntilla, El Puerto»); None when
    nothing is added."""

    query = str(query or "")
    found = _SAID_PLACE.search(query)
    parts = _said_place_parts(query)
    if found is None or len(parts) != 1:
        return None
    town = place_fixed_by_conversation(parts[0], said_before)
    if town is None:
        return None
    end = found.start("place") + query[found.start("place"):].find(parts[0]) + len(parts[0])
    return f"{query[:end]}, {town}{query[end:]}"


def weather_asks_today(asks: str, today_weekday: str) -> bool:
    """The weather question is about today: «hoy», «now», or today's weekday named (folded words)."""

    return re.search(r"\b(?:hoy|today|ahora|now)\b", asks) is not None or (
        bool(today_weekday) and re.search(r"\b" + re.escape(today_weekday) + r"\b", asks) is not None
    )


def weather_asks_later_today(asks: str) -> bool:
    """«hoy», «tonight», «esta tarde / noche / mañana»: the rain asked is today's (folded words)."""

    return re.search(r"\b(?:hoy|today|tonight|esta\s+(?:noche|tarde|manana))\b", asks) is not None


# M64 (v3f-final F-w12-t4 → t5): three drafts of «¿Cuánto está el dólar blue hoy?» fell, the last resort said «No lo
# encontré.», and «Anotame ese valor en una nota» lost what had been looked up. The not-found names what was looked up,
# in the person's own words: the question as an indirect one («cuánto está el dólar blue hoy», «si va a llover mañana»,
# «what the latest song from Ne-Yo is») or the thing asked for with its article («el horario del Líder de Ñuñoa»). A
# phrase without one may begin with a verb («Get train schedules to Manchester…»), and is left to the plain not-found.
_SEARCHED_LEAD = re.compile(
    r"^(?:[\s,¿¡]*(?:y|e|and|pero|but|ok|vale|bueno|entonces|so|then|oye|hey|che|ya|pucha|baxy)\b)*[\s,¿¡]*"
)
_SEARCHED_VERB = re.compile(
    r"^(?:buscame|busca|buscar|averiguame|averigua|investiga|consulta|dime|decime|dame|fijate\s+en|revisa|muestrame|"
    r"encuentrame|encuentra|get|show\s+me|give\s+me|"
    r"(?:me\s+)?(?:sabes|sabrias|puedes\s+decirme|podrias\s+decirme|dices|puedes\s+decir|podrias\s+decir)|"
    r"search\s+for|search|look\s+up|find\s+out|find|tell\s+me|check|(?:do\s+you\s+know|can\s+you\s+tell\s+me|"
    r"could\s+you\s+tell\s+me))\b(?:\s+(?:en|on)\s+(?:internet|google|la\s+web|the\s+web))?[\s,]*"
)
_SEARCHED_TAIL = re.compile(r"(?:[\s,]*\b(?:por\s+favor|porfa|please|eh|po|pues)\b)*[\s?!.…,]*$")
_SEARCHED_WH_ES = {
    "que": "qué", "cual": "cuál", "cuales": "cuáles", "cuanto": "cuánto", "cuanta": "cuánta", "cuantos": "cuántos",
    "cuantas": "cuántas", "quien": "quién", "quienes": "quiénes", "donde": "dónde", "cuando": "cuándo", "como": "cómo",
    "adonde": "adónde",
}
_SEARCHED_WH_EN = frozenset({"what", "who", "where", "when", "which", "why", "whose", "how"})
_SEARCHED_COPULA_EN = frozenset({"is", "are", "was", "were"})
_SEARCHED_PLACE_PREPOSITION_EN = frozenset({"in", "on", "at", "inside", "behind", "near", "under", "with", "from"})
_SEARCHED_AUXILIARY_EN = frozenset(
    {"do", "does", "did", "can", "could", "will", "would", "should", "has", "have", "had", "may", "might", "am"}
)
_SEARCHED_PHRASE_START = frozenset(
    {"el", "la", "los", "las", "un", "una", "unos", "unas", "lo", "algun", "alguna", "algunos", "algunas", "the", "a",
     "an", "any", "some"}
)
# Who speaks and whom a pointer points at cannot be turned into BAXY's words by swapping «me» for «te»: the person's
# own verbs, BAXY addressed, and «eso» with its antecedent elsewhere leave the plain «No lo encontré».
_SEARCHED_NOT_BAXYS = frozenset(
    {"yo", "nos", "nuestro", "nuestra", "nuestros", "nuestras", "conmigo", "tengo", "puedo", "necesito", "debo",
     "quiero", "estoy", "voy", "soy", "hago", "busco", "llevo", "pago", "vivo", "trabajo", "compro", "uso", "i", "we",
     "our", "ours", "us", "im", "tu", "tus", "usted", "puedes", "sabes", "tienes", "podrias", "quieres", "recomiendas",
     "crees", "piensas", "you", "your", "yours", "eso", "esto", "ese", "esa", "esos", "esas", "it"}
)
_SEARCHED_PREPOSITION = frozenset({"a", "de", "en", "por", "para", "con", "desde", "hasta"})
_SEARCHED_SECOND_PERSON = {"es": {"me": "te", "mi": "tu", "mis": "tus"}, "en": {"my": "your", "me": "you"}}


# M79 (DEV-D v3m p19-t2 «Who's in the movie 'After the Wedding'?» → «I couldn't find out who in the movie 'After the
# Wedding' is.»): when «who» or «what» is the subject and «is» joins it to a place, a gerund or an adverb («who is in
# the movie», «what's playing», «what's new»), the indirect question keeps that order; only a noun after «is» is the
# subject that «is» follows («what the capital of Peru is»).
_SUBJECT_PREDICATE_EN = frozenset(
    {"in", "on", "at", "with", "from", "behind", "by", "near", "inside", "under", "up", "new", "next", "there",
     "here", "open", "available", "better", "best", "worse", "happening", "wrong", "going", "coming", "playing",
     "showing", "running", "starring"}
)


def _asks_for_the_subject(wh: str, following: list[str]) -> bool:
    word = following[0] if following else ""
    return wh in {"who", "what", "which"} and (word in _SUBJECT_PREDICATE_EN or word.endswith("ing"))


def searched_clause(text: str, language: str) -> tuple[str, bool] | None:
    """What a search looked for, said by BAXY after «No encontré» / «I couldn't find»: (the clause, whether it is an
    indirect question, «find out» in English). None when the text is not one plain question or lookup in
    ``language`` («¿y cuánto sale…? el mistral de 35», keywords, a question English inverts)."""

    said = " ".join(str(text or "").replace("’", "'").split())
    if not said or len(said) > 200 or language not in _SEARCHED_SECOND_PERSON:
        return None
    question = "?" in said
    for pattern in (_SEARCHED_LEAD, _SEARCHED_VERB):
        lead = pattern.match(fold_in_place(said))
        said = said[lead.end():] if lead else said
    tail = _SEARCHED_TAIL.search(fold_in_place(said))
    said = said[: tail.start()] if tail else said
    if re.search(r"[?!;¿¡\n]|\.\s+[a-záéíóúñü]", said):
        return None
    words = said.split(" ")
    keys = [_reading_fold(word).strip(".,:") for word in words]
    # M70 (held-out v3h t16 «¿Cuándo sale la próxima temporada de The Last of Us?»): the «Us» of a title is part of a
    # name, not the person's «us», and the not-found fell to the bare «No lo encontré». A capitalised word inside the
    # text (English «I» apart) belongs to a name and is neither a pronoun nor shifted to BAXY's voice.
    named = [index > 0 and word[:1].isupper() and key != "i" for index, (word, key) in enumerate(zip(words, keys))]
    if not 2 <= len(words) <= 16 or _SEARCHED_NOT_BAXYS & {key for key, name in zip(keys, named) if not name}:
        return None
    shift = _SEARCHED_SECOND_PERSON[language]
    words = [word if name else shift.get(key, word) for word, key, name in zip(words, keys, named)]
    if language == "es":
        head = 1 if keys[0] in _SEARCHED_PREPOSITION and keys[1] in _SEARCHED_WH_ES else 0
        if keys[head] in _SEARCHED_WH_ES:
            return " ".join([*(key for key in keys[:head]), _SEARCHED_WH_ES[keys[head]], *words[head + 1:]]), True
        if question:
            first = words[0] if words[0][1:2].isupper() or words[1][:1].isupper() else words[0][:1].lower() + words[0][1:]
            return " ".join(["si", first, *words[1:]]), True
    else:
        wh, _, contracted = keys[0].partition("'")
        if wh in _SEARCHED_WH_EN:
            span = 2 if wh == "how" and keys[1] in {"much", "many"} else 1
            lead = " ".join([wh, *keys[1:span]])
            rest = words[span:]
            if contracted in {"s", "re"}:
                copula = "is" if contracted == "s" else "are"
                if _asks_for_the_subject(wh, keys[span:span + 1]) or (
                    keys[span:span + 1] and keys[span] in _SEARCHED_PLACE_PREPOSITION_EN
                ):
                    # M79/M81 (DEV-D v3m D-p19-t2 «Who's in the movie 'After the Wedding'?» → «…who in the movie …
                    # is»): the subject is the one asked about; «in …» is where, and the copula stays with it.
                    return " ".join([lead, copula, *rest]), True
                return " ".join([lead, *rest, copula]), True
            following = keys[span] if len(keys) > span else ""
            if following in _SEARCHED_AUXILIARY_EN or not rest:
                return None
            if following in _SEARCHED_COPULA_EN:
                if _asks_for_the_subject(wh, keys[span + 1:span + 2]):
                    return " ".join([lead, following, *rest[1:]]), True
                return " ".join([lead, *rest[1:], following]), True
            return " ".join([lead, *rest]), True
        if question:
            return None
    if keys[0] not in _SEARCHED_PHRASE_START:
        return None
    return " ".join([words[0][:1].lower() + words[0][1:], *words[1:]]), False


# M70 (held-out v3h t16 «fijate cuándo sale la próxima temporada»): the pages were about the next season's cast and
# none gave a date; «No hay fecha de estreno confirmada…» and «…sin confirmar una fecha de estreno» died as invented
# claims on «fecha» and «confirmada». A question of when asks for a date, a day or a time; of where, a place; of how
# much, a price or an amount: that word is part of what was asked, and saying it is missing or unconfirmed reports what
# was not found. Folded words.
_ASKED_DIMENSIONS = (
    (
        re.compile(r"\b(?:cuando|when)\b"),
        frozenset({"fecha", "fechas", "dia", "dias", "hora", "horas", "horario", "date", "dates", "day", "days", "time",
                   "hour", "hours"}),
    ),
    (
        re.compile(r"\b(?:donde|adonde|where)\b"),
        frozenset({"lugar", "lugares", "sitio", "ubicacion", "direccion", "place", "location", "address"}),
    ),
    (
        re.compile(r"\b(?:cuanto|cuanta|cuantos|cuantas|how\s+(?:much|many))\b"),
        frozenset({"precio", "precios", "costo", "coste", "valor", "cantidad", "cifra", "numero", "price", "cost",
                   "value", "amount", "number", "figure"}),
    ),
)
# How a report says the asked thing is not known yet: unconfirmed, unannounced, not official, not set.
ASKED_UNCONFIRMED_WORDS = frozenset(
    {"confirmado", "confirmada", "confirmados", "confirmadas", "confirmar", "anunciado", "anunciada", "anunciar",
     "oficial", "oficiales", "definido", "definida", "definir", "concreta", "concreto", "exacta", "exacto", "precisa",
     "preciso", "confirmed", "confirm", "announced", "official", "exact", "precise"}
)


def asked_dimension_words(text: str) -> frozenset[str]:
    """The folded words that name what a question of when, where or how much asks for («¿Cuándo sale…?» → «fecha»,
    «día», «hora»…); empty when the text asks none of them."""

    folded = _reading_fold(text)
    words: set[str] = set()
    for asks, named in _ASKED_DIMENSIONS:
        if asks.search(folded) is not None:
            words |= named
    return frozenset(words)


# M71 (held-out v3j t14): after «anoche vi Oppenheimer y me gustó bastante», «averiguá qué dijo la crítica» was
# understood as «Buscá qué dijo la crítica sobre Oppenheimer.», and the report «Una crítica de un científico de Infobae
# se menciona y John Carpenter no se subió a los elogios de la película.» never said which film: the person, who did
# not name it in this message, cannot tell what the report is about. A name the understood request or the query writes
# (a capitalised word inside the text, joined with the next by «of», «de», «the»…: «The Last of Us») that the person's
# own message does not write is the subject the conversation carried, and the report names it.
_NAME_JOINERS = frozenset({"of", "the", "de", "del", "la", "las", "los", "el"})
_NAME_WHERE_TO_LOOK = frozenset({"google", "bing", "duckduckgo", "internet", "web", "wikipedia", "youtube", "baxy"})
_NAME_OPENERS = "¿¡\"'«(“‘"
_NAME_CLOSERS = ".,;:!?»\")”’…"


def _written_names(text: str) -> list[str]:
    """The names a text writes, as it writes them: runs of capitalised words that do not open a sentence (English
    «I» apart), joined across «of», «de», «the»… only when another capitalised word follows."""

    names: list[str] = []
    run: list[str] = []
    joiners: list[str] = []
    opening = True
    for raw in str(text or "").split():
        word = raw.lstrip(_NAME_OPENERS)
        bare = word.rstrip(_NAME_CLOSERS)
        if not bare:
            continue
        if bare[:1].isupper() and not opening and bare != "I":
            run.extend([*joiners, bare])
            joiners = []
        elif run and bare == word and _reading_fold(bare) in _NAME_JOINERS:
            joiners.append(bare)
        elif run:
            names.append(" ".join(run))
            run, joiners = [], []
        if bare != word and run:
            names.append(" ".join(run))
            run, joiners = [], []
        opening = word[-1] in ".?!:"
    if run:
        names.append(" ".join(run))
    return names


def _name_words(name: str) -> frozenset[str]:
    """The folded words that identify a name («The Last of Us» → «last»; «James Cameron» → «james», «cameron»)."""

    return frozenset(
        word for word in re.findall(r"[a-z0-9]+", _reading_fold(name))
        if len(word) >= 3 and word not in _NAME_JOINERS and word != "us"
    )


def carried_subjects(understood: str, query: str, said: str) -> tuple[str, ...]:
    """The names of the understood request and of the query that the person's own message (``said``) does not write:
    the subject this turn took from the conversation. Empty when the person named it, or nothing names one."""

    said_words = set(re.findall(r"[a-z0-9]+", _reading_fold(said)))
    subjects: list[str] = []
    for name in [*_written_names(understood), *_written_names(query)]:
        words = _name_words(name)
        if (
            not words
            or words <= _NAME_WHERE_TO_LOOK
            or words & said_words
            or any(words & _name_words(subject) for subject in subjects)
        ):
            continue
        subjects.append(name)
    return tuple(subjects)


def names_subject(text: str, subject: str) -> bool:
    """The text names the subject: one of its identifying words, in any case or accent («Last of Us» names «The Last
    of Us», «Nolan» names «Christopher Nolan»)."""

    return bool(_name_words(subject) & set(re.findall(r"[a-z0-9]+", _reading_fold(text))))


# M77 (DEV-D v3l D-p16-t1/t2/t3 «valet parking at the Kenzi Rose Garden»): OpenStreetMap reads a class of site
# («parking»), never what the person qualified it with («valet»). The words that name the class read (twin of
# OpenStreetMapPlaceSource.Kinds and PairedKinds), folded.
PLACE_KIND_WORDS = frozenset(
    {
        "aparcamiento", "aparcamientos", "estacionamiento", "estacionamientos", "parqueadero", "parqueaderos",
        "parking", "car", "park", "parks", "gasolinera", "gasolineras", "bencinera", "bencineras", "fuel", "gas",
        "petrol", "station", "stations", "farmacia", "farmacias", "pharmacy", "pharmacies", "drugstore", "drugstores",
        "hospital", "hospitales", "hospitals", "clinica", "clinicas", "clinic", "clinics", "cajero", "cajeros", "atm",
        "atms", "hotel", "hoteles", "hotels", "hostal", "hostales", "hostel", "hostels", "supermercado",
        "supermercados", "supermarket", "supermarkets", "restaurante", "restaurantes", "restaurant", "restaurants",
        "taqueria", "taquerias", "cafeteria", "cafeterias", "cafe", "cafes", "panaderia", "panaderias", "bakery",
        "bakeries", "comisaria", "comisarias", "veterinaria", "veterinarias", "veterinario", "museo", "museos",
        "museum", "museums", "biblioteca", "bibliotecas", "library", "libraries", "cine", "cines", "cinema",
        "cinemas", "dentista", "dentistas", "dentist", "dentists",
    }
)


def request_common_words(text: str) -> frozenset[str]:
    """The folded words of four letters or more that the person wrote in lower case: what they asked for and how they
    qualified it, not the names they wrote («valet» and «parking» of «valet parking at the Kenzi Rose Garden»)."""

    words: set[str] = set()
    for raw in str(text or "").split():
        bare = raw.strip("¿¡?!.,;:\"'«»()“”‘’")
        if bare[:1].islower():
            words |= {word for word in re.findall(r"[a-z0-9]+", _reading_fold(bare)) if len(word) >= 4}
    return frozenset(words)


# M77 (DEV-D v3l D-w14-t1 «¿quién ha ganado la Vuelta este año?» → «Jonas Vingegaard conquistó la Vuelta a España
# 2025»): a question about this year, this season or the one under way asks for the current year's.
_THIS_YEAR = re.compile(
    r"\b(?:este|esta|this)\s+(?:ano|temporada|season|year)\b|\b(?:ano|temporada)\s+(?:actual|en\s+curso)\b|"
    r"\b(?:current|present)\s+(?:year|season)\b|\ben\s+lo\s+que\s+va\s+del\s+ano\b"
)


def asks_this_year(text: str) -> bool:
    """The request asks about the current year or season («este año», «esta temporada», «this year»)."""

    return _THIS_YEAR.search(_reading_fold(text)) is not None


# M77 (DEV-D v3l D-p19-t3 «What's the genre?» after a film, D-p23-t2 «Look for a drama film.», D-w17-t5 «tell me more
# about the second one» → the query «more about the second headline»): the search found the encyclopedia's article on
# the word itself, and the reply defined «genre», «drama film», «headline». A word the person used for an attribute
# of something («the genre», «su trama»), for one of a series («the second headline», «el segundo titular») or for the
# kind of thing they want found («look for a drama film», «busca una película de terror») does not ask what that word
# means. Folded phrases, one to three words.
_ATTRIBUTE_NOUN = (
    r"(?:genre|genres|plot|cast|rating|runtime|director|author|score|ending|headline|title|story|premise|budget|"
    r"soundtrack|genero|trama|reparto|autor|autora|final|titular|titulo|argumento|sinopsis|duracion|puntuacion)"
)
_UNDEFINED_ASKED = (
    re.compile(r"\b(?:the|its|their|his|her|el|la|su|sus)\s+(?P<phrase>" + _ATTRIBUTE_NOUN + r")\b"),
    re.compile(
        r"\b(?:the|el|la|los|las)\s+(?P<phrase>(?:first|second|third|fourth|fifth|last|next|previous|primer|primero|"
        r"primera|segundo|segunda|tercer|tercero|tercera|cuarto|cuarta|quinto|quinta|ultimo|ultima|siguiente|"
        r"anterior)\s+[a-z]+)"
    ),
    re.compile(
        r"\b(?:look(?:ing)?\s+for|search(?:ing)?\s+for|find(?:\s+me)?|recommend(?:\s+me)?|suggest|buscame|busca(?:me)?|"
        r"encuentrame|encuentra(?:me)?|recomiendame|recomienda(?:me)?|sugiereme|sugiere)\s+"
        r"(?:(?:a|an|some|any|un|una|unos|unas|algun|alguna|algunos|algunas)\s+)?"
        r"(?P<phrase>[a-z]+(?:\s+[a-z]+){0,2})"
    ),
)


def undefined_asked_phrases(text: str) -> tuple[str, ...]:
    """The folded phrases the request uses for an attribute, one of a series, or the kind of thing to find: words
    whose meaning it does not ask («the genre», «the second headline», «a drama film»)."""

    folded = _reading_fold(text)
    return tuple(
        found.group("phrase") for pattern in _UNDEFINED_ASKED for found in pattern.finditer(folded)
    )


# M83 (DEV-D v3o D-p24-t1 «…a nice Fantasy Movie like Elijah Wood» → «I could not find a movie like Elijah Wood», D-s111
# «¿Cuál es la distancia de Barcelona a París?» → «No encontré…», D-p34-t1 the famous time capsules, D-p31-t1 the
# presidents since 1983): D35 (owner, 2026-09-28) «sin fuente, BAXY responde de memoria y lo avisa en corto; no se calla».
# What memory may answer is what an encyclopedia keeps: nothing that changes with the day or the hour, nothing near the
# person, nothing of theirs, no opinion. Twin of WikipediaSearchSource.IsEncyclopedic (its time-bound and opinion
# words), plus the readers of the mind for changing facts, the person's own data, what is near and what comes next.
_TIME_BOUND_WORDS = (
    r"\b(?:hoy|ahora|actual|actualmente|anoche|ayer|manana|noticias?|precios?|cuesta|cuestan|cotiza\w*|horarios?|abre|"
    r"cierra|marcador|cerca|comprar|ofertas?|clima|pronostico|cartelera|estrenos?|today|now|current|currently|tonight|"
    r"yesterday|tomorrow|latest|news|prices?|costs?|schedules?|hours|opens|closes|scores?|near|nearby|buy|deals?|"
    r"weather|forecast|showtimes|loto|loteria|sorteos?|lottery|lotto|sale|stocks?|shares|trending|tendencias?|"
    r"opinion|opiniones|opina|opinan|critica|criticas|criticos|resenas?|reviews?|ratings?|worth|recomendable|"
    r"(?:cuanto|cuantos|lo\s+que)\s+valen?(?!\s+la\s+pena)|"
    # What goes on now, on the roads or online, and what a place offers today (DEV-D v3m/v3o D-s021 «qué está pasando
    # por el mundo», D-s063 a traffic update, D-p16 valet parking at a hotel, D-p23-t1 online movies).
    r"pasando|sucediendo|ocurriendo|happening|going\s+on|traffic|trafico|transito|atascos?|congestion|"
    r"(?:online|en\s+linea|streaming)\s+(?:movies?|films?|shows?|series|stores?|shops?)|"
    r"(?:peliculas?|pelis?|series|tiendas?)\s+(?:online|en\s+linea)|"
    r"parking|aparcamiento|estacionamiento|valet|disponibles?|available|"
    # «tell me more about the second one»: an item of what was just read, which memory never saw (D-w17-t5).
    r"(?:the|el|la|lo)\s+(?:first|second|third|fourth|fifth|last|primer[oa]?|segund[oa]|tercer[oa]?|cuart[oa]|"
    r"quint[oa]|ultim[oa])(?:\s+(?:one|uno|una))?(?=\s*[?.!]*$|\s+(?:one|uno|una)\b))\b"
)
# «movies in Santa Rosa», «películas en Ñuñoa»: what the cinemas of a town show (DEV-D v3o D-p26-t2, D-p28-t2).
_SHOWING_IN_A_PLACE = re.compile(
    r"\b(?:movies?|films?|pel[ií]culas?|pelis?|cartelera|showtimes?|shows?)\s+(?:in|en|at|near)\s+"
    r"(?:(?:the|el|la)\s+)?[A-ZÁÉÍÓÚÑ]"
)
# «¿y cuándo juega el siguiente?», «the next episode», «the upcoming release»: an event still to come.
_UPCOMING = (
    r"\b(?:siguientes?|proxim[oa]s?|que\s+viene|next|upcoming|coming\s+up|"
    r"cuando\s+(?:juega|juegan|jugara|jugaran|toca|se\s+juega)|when\s+(?:do|does|will)\s+\S+(?:\s+\S+){0,3}\s+play)\b"
)


def asks_upcoming(text: str) -> bool:
    """M83 (DEV-D v3o D-w08-t2 «y cuando juega el sigiente»): the request asks about an event still to come (the next
    one, the upcoming one, when a team plays)."""

    return _has(_fold(text), _UPCOMING)


def memory_may_answer(text: str) -> bool:
    """Whether what the request asks is kept by memory as an encyclopedia keeps it (see above): None of it changes
    with the day, is near the person, is theirs, is an opinion or is still to come."""

    folded = _fold(text)
    if not folded.strip(" ¿?¡!.,"):
        return False
    return not (
        _has(folded, _TIME_BOUND_WORDS)
        or _has(folded, _UPCOMING)
        or _has(folded, _NEAR_THE_PERSON)
        or asks_this_year(text)
        or names_own_data(text)
        or record_fact_query(text) is not None
        or public_opinion_query(text) is not None
        or news_lookup_query(text) is not None
        or _names_weather(folded)
        or _road_traffic_request(folded)
        or cinema_listing(text)
        or asks_where_to_find(text)
        or _SHOWING_IN_A_PLACE.search(str(text or "")) is not None
        # «a cuánto está el yen frente al peso chileno»: a rate moves every day.
        or _has(folded, rf"{_CURRENCY}.{{0,60}}{_CURRENCY}|\b(?:tipos?|tasas?)\s+de\s+cambio\b|\bexchange\s+rates?\b")
        or _has(folded, r"\ba\s+(?:cuanto|como)\s+(?:esta|estan|anda|andan|va|van)\b")
    )
