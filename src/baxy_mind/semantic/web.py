"""Web: search, research a topic or an entity, navigate to a site, browser tabs. Readers moved from effect_intent (Fase 3.5).
"""

from __future__ import annotations

import re
from typing import Iterable
from .grammar import _fold, _match, _has, _strip_request_envelope, _request_head, _head_is, _negative_action_forms, _is_negative_effect_clause, _is_meta_or_tool_denial, _OPEN, _LIST, _READ, _SEARCH, _explicit_google_search_query
from .intent import EffectIntent, _entity_key, _append, _append_all
from .catalog import ApplicationCatalogIndex, _application_name_key, build_application_catalog_index
from .temporal import _BOUNDED_TEMPORAL_SELECTOR
from .media import _youtube_search_query


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


def _public_calendar_fact_lookup_request(folded: str) -> bool:
    """Recognize year-dependent public calendar facts outside local state."""

    return (
        re.fullmatch(
            r"[^\w]*(?:"
            r"(?:que|cual)\s+dia\s+de\s+la\s+semana\s+cae\s+"
            r"\S.{0,96}\s+(?:este|el\s+presente)\s+ano|"
            r"what\s+day\s+of\s+the\s+week\s+(?:is|does)\s+"
            r"\S.{0,96}\s+(?:fall\s+on\s+)?this\s+year"
            r")[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )


_WEATHER_WORDS = (
    r"\b(?:weather|forecast|rain|raining|clima|pronostico|lluvia|llueve|llover|"
    # WEATHER2023 «¿hace frío afuera?»: the cold or the heat outside is the weather too.
    r"llovera|llovio|temperature|temperatura|frio|fria|calor|cold|hot|caluroso|calurosa)\b"
)


def _weather_lookup_query(text: str) -> str | None:
    """WEB1445: the person's weather request without its request verbs, accents
    kept (the engine answers «va a llover mañana» and «clima hoy», not the folded
    or verb-laden forms); None when the request is not a live weather lookup."""

    folded = _fold(text)
    if not _public_live_lookup_request(folded) or not _has(folded, _WEATHER_WORDS):
        return None
    if _has(folded, r"^[¿?¡!\s]*(?:que|what)\s+(?:es|son|is|are|significa|means)\b"):
        return None
    # WEATHER2023 boundary «qué clima hacía en Buenos Aires en 1990»: the past
    # (a past-tense verb or a year) has no live read; the turn says so instead
    # of reading today's weather.
    if _has(
        folded,
        r"\b(?:hacia|hizo|hubo|estuvo|estaba|fue|llovio|was|were|did|rained)\b|"
        r"\b(?:19|20)\d\d\b|\b(?:ayer|anteayer|yesterday|la\s+semana\s+pasada|last\s+week)\b",
    ):
        return None
    query = text.strip(" \t\r\n¿?¡!.,;:")
    query = re.sub(r"^(?:por favor|please)\s*[,:]?\s*", "", query, flags=re.IGNORECASE)
    query = re.sub(
        r"^(?:mostrame|muéstrame|muestrame|muestra|decime|dime|contame|cuéntame|cuentame|"
        r"busca|buscá|buscame|buscar|search|find|show\s+me|tell\s+me|dame|give\s+me|"
        r"necesito|need|quiero|i\s+want)\s+(?:saber\s+|to\s+know\s+)?(?:el|la|the|los|las)?\s*",
        "", query, count=1, flags=re.IGNORECASE)
    query = re.sub(
        r"^(?:qué|que|what|cuál|cual|what's|cómo|como|how)\s+(?:es\s+|is\s+|está\s+|esta\s+|estará\s+|estara\s+|va\s+a\s+estar\s+)?"
        r"(?:el\s+|la\s+|the\s+)?"
        r"(?P<noun>clima|tiempo|weather|forecast|pronóstico|pronostico)\s*"
        r"(?:hace|hay|is\s+it\s+like|is\s+it|is|like)?\s*",
        lambda m: m.group("noun") + " ", query, count=1, flags=re.IGNORECASE)
    # «is it going to rain tomorrow» / «will it rain tomorrow»: the auxiliaries
    # never appear in a forecast page; the engine answers «rain tomorrow».
    query = re.sub(r"^(?:is\s+it\s+going\s+to|will\s+it|is\s+it|does\s+it)\s+", "", query, count=1, flags=re.IGNORECASE)
    # WEB1455 «busca en internet el clima»: the medium may precede the noun.
    query = re.sub(r"(?:^|\s+)(?:en|in|on)\s+(?:google|internet|la\s+web|the\s+web)\b\s*", " ", query, flags=re.IGNORECASE)
    query = re.sub(r"^\s*(?:el|la|los|las|the)\s+", "", query, count=1, flags=re.IGNORECASE)
    query = re.sub(r"\s+", " ", query).strip(" ?!.,;:")
    return query if query and _has(_fold(query), _WEATHER_WORDS) else None


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
    return topic


_RESEARCH_VERBS = (
    r"(?:investiga(?:r|me)?|research|look\s+(?:into|up)|busca(?:r|me)?|search|averigua(?:r|me)?|find\s+out)"
)


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
    r"(?P<question>(?:por\s*que|porq\w*|why|como|how|que|what|cual(?:es)?|which|donde|where|cuando|when|quien(?:es)?|who)\b.+?)\s*[.!?]*$",
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
    r"^[¿?¡!\s]*(?:"
    r"(?:quien|quién|quienes|quiénes|who)\s+(?:es|fue|era|son|fueron|eran|is|was|are|were)|"
    r"(?:(?:dime|decime|explicame|explícame|contame|cuentame|cuéntame|tell\s+me)\s+)?(?:que|qué|what)\s+(?:es|fue|era|is|was)|"
    r"(?:hablame|háblame|hablarme|contame|cuentame|cuéntame|explicame|explícame|tell\s+me)\s+"
    r"(?:(?:un\s+poco|algo|mas|más|a\s+bit|a\s+little|more)\s+)?(?:de|sobre|acerca\s+de|about)"
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

    match = _ENTITY_LOOKUP.match(text.strip())
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
        r"^(?:tu|vos|usted|ustedes|ti|yo|el|ella|ellos|ellas|nosotros|nosotras|you|me|i|he|she|"
        r"they|it|esto|eso|esta|este|ese|esa|aquel|aquello|aquella|this|that|these|those|"
        r"mi|mis|tus|su|sus|nuestro|nuestra|nuestros|nuestras|my|your|his|her|their|our|"
        r"de\s+verdad|realmente|really|en\s+realidad)\b",
    ):
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

    folded = re.sub(_TALK_OPENING, "", _fold(text)).strip(" ¿?¡!.,")
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
        return f"{_original_words(text, work).strip()} {'reviews' if english else 'opiniones'}"
    return None


_RECORD_FACT = re.compile(
    r"(?:(?:cual|quien)\s+(?:fue|es|era)\s+(?:el|la)\s+(?:primer[oa]?|1er[oa]?|1ra|1°|ultim[oa]|mas\s+\w+|"
    r"mejor|peor)\s+\S.*|"
    r"cuando\s+(?:sale|salio|saldra|se\s+estrena|se\s+estreno|estrenan|estrenaron|lanzan|lanzaron|"
    r"sale\s+la\s+nueva|sale\s+el\s+nuevo)\s+\S.*|"
    r"(?:what|who|which)\s+(?:was|is)\s+the\s+(?:first|last|latest|newest|oldest|best|worst|most\s+\w+)\s+\S.*|"
    r"when\s+(?:does|did|will)\s+\S.*\s+(?:come\s+out|release|premiere|launch))"
)


def record_fact_query(text: str) -> str | None:
    """«Entonces cuál fue el 1er libro de zombies» → the question as the search query; None otherwise.

    A first, last, best or release date is a dated fact: looked up before it is stated."""

    folded = re.sub(_TALK_OPENING, "", _fold(text)).strip(" ¿?¡!.,")
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


def _public_live_lookup_request(folded: str) -> bool:
    """Recognize live feeds that require a public lookup to answer."""

    head = _request_head(folded)
    weather_heads = {
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
        "will",
        "voy",
        "yes",
    }
    news_consumption = (
        re.match(
            (
                r"^(?:(?:alexa|olly|bax[yi])\s+)?(?:"
                r"i\s+(?:want|would\s+like)\s+to\s+(?:hear|know|see)|"
                r"(?:pon|ponme|muestra|muestrame|show|play|"
                r"busca|buscame|buscar|search|find|dame|decime|dime|investiga)\b"
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
    vocative_weather = re.match(
        r"^(?:olly|bax[yi])\s+(?P<head>[a-z]+)\b",
        folded,
        re.IGNORECASE,
    )
    weather_head = head in weather_heads or (
        vocative_weather is not None and vocative_weather.group("head") in weather_heads
    )
    weather = weather_head and _has(
        folded,
        r"\b(?:weather|forecast|rain|raining|clima|pronostico|lluvia|llueve|llover|"
        r"umbrella|paraguas|temperature|temperatura|hot|caluroso|calurosa|"
        r"cold|frio|fria|calor)\b",
    ) and not _has(
        # WEATHER2023 boundary: the weather of the past is no live lookup.
        folded,
        r"\b(?:hacia|hizo|hubo|estuvo|estaba|fue|llovio|was|were|did|rained)\b|"
        r"\b(?:19|20)\d\d\b|\b(?:ayer|anteayer|yesterday|la\s+semana\s+pasada|last\s+week)\b",
    )
    # WEB1451 «qué pasó hoy en el mundo»: what happened today is the news.
    todays_events = (
        re.match(
            r"^[¿?¡!\s]*(?:que|what)\s+"
            r"(?:paso|pasa|ha\s+pasado|esta\s+pasando|ocurrio|ocurre|sucedio|"
            r"happened|is\s+happening|has\s+happened)\s+(?:hoy|today)\b",
            folded,
            re.IGNORECASE,
        )
        is not None
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
    # WEB1453 «¿Qué es un pronóstico del tiempo?»: a question about what a
    # forecast, a news item or the weather is (indefinite article) asks for a
    # definition; «what is the weather» keeps its article and stays a lookup.
    definition_question = (
        re.match(
            r"^[¿?¡!\s]*(?:que|what)\s+(?:es|son|is|are)\s+(?:un|una|unos|unas|a|an)\s+",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    if definition_question:
        weather = False
        news = False
        todays_events = False
        topic_research = False
        entity_lookup = False
    # A file, note or document named after the weather, or a question about the
    # word itself («¿qué significa la palabra clima?»), is not a live lookup.
    if (weather or news or todays_events or topic_research or entity_lookup) and _has(
        folded,
        r"\b(?:archivos?|files?|carpetas?|folders?|notas?|notes?|documentos?|"
        r"documents?|txt|pdf|docx|significa|significado|definicion|define|"
        r"definition|meaning|means)\b",
    ):
        weather = False
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
    business_delivery = (
        re.match(
            (
                r"^(?:hace|ofrece|tiene|does|do|is)\b.{0,96}"
                r"\b(?:envios?|entregas?|delivery|deliver)\b.{0,48}"
                r"\b(?:domicilio|home|nearby|disponible|available)?\b"
            ),
            folded,
            re.IGNORECASE,
        )
        is not None
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
            r"(?:list|show|find|search|lista|muestra|busca)\b.{0,80}"
            r"\b(?:train\s+times?|train\s+schedules?|horarios?\s+de\s+trenes?)\b"
            r".{0,96}[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
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


_CURIOSITY_REQUEST = re.compile(
    r"^(?:baxy\s*[,:]?\s*)?(?:(?:contame|cuentame|conta|cuenta|decime|dime|tirame|tira|explicame|explica|"
    r"tell\s+me|give\s+me)\s+"
    r"(?:(?:un|una|algun|alguna|otra|otro|a|an|another|some)\s+)?"
    r"(?:curiosidad|curiosidades|dato\s+curioso|datos\s+curiosos|fun\s+fact|fun\s+facts|"
    r"interesting\s+fact|random\s+fact|algo|something)"
    r"(?:\s+(?:interesante|curioso|curiosa|nuevo|nueva|interesting|curious|cool|random|new))?"
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
# 2026-09-13, point 2). The name and the content stay the person's words.
_KNOWN_FOLDER_WORDS = r"escritorio|desktop|documentos|documents|descargas|downloads"


_KNOWN_FOLDER_ENUM = {
    "escritorio": "desktop", "desktop": "desktop",
    "documentos": "documents", "documents": "documents",
    "descargas": "downloads", "downloads": "downloads",
}


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


def _location_recommendation_request(text: str) -> bool:
    """Recognize a standalone request for public place recommendations."""

    return _has(
        text,
        r"^[^\w]*(?:lugares?|sitios?)\s+(?:para|a\s+donde)\s+"
        r"(?:ir|salir|comer|visitar)\b.+|"
        r"^[^\w]*(?:places?|restaurants?|things?)\s+to\s+"
        r"(?:go|visit|eat|do)\b.+",
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
                    r"\b(?:lugares?|sitios?|places?|restaurants?|things?)\b"
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
