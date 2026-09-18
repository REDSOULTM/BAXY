"""Conservative, compositional recognition of explicit public effects.

This module is deliberately smaller than a language model and less permissive
than semantic retrieval.  It does not extract arguments, grant authority, or
execute anything.  It only preserves an unambiguous operation-level effect
when the request contains both an action/state cue and its domain object.
Arguments still cross the schema-grounding boundary and every effect still
crosses the core's risk, confirmation, execution, and verification gates.

The recognizer is operation-oriented rather than sentence-oriented: patterns
describe verb/object families and can therefore cover ordinary paraphrases,
punctuation, accents, English, Spanish, and compound requests without an
allow-list of audited sentences.
"""

from __future__ import annotations

import hashlib
import random
import re
import time
import unicodedata
from dataclasses import dataclass, field
from typing import Iterable, Iterator

from .catalog_operation_aliases import exact_catalog_operation_plan


MAX_APPLICATION_CATALOG_ENTRIES = 2_048
MAX_APPLICATION_CATALOG_PATTERN_CHARS = 1_048_576
MAX_GAME_CATALOG_ENTRIES = 4_096


@dataclass(frozen=True, slots=True)
class EffectIntent:
    operations: tuple[str, ...]
    evidence: tuple[str, ...] = ()

    @property
    def kind(self) -> str:
        return "action" if len(self.operations) == 1 else "plan"


@dataclass(frozen=True, slots=True)
class ClarificationIntent:
    """One incomplete request whose operation identity is still certain."""

    operations: tuple[str, ...]
    missing_fields: tuple[str, ...]

    @property
    def operation(self) -> str:
        """Compatibility accessor for callers that only accept one operation."""

        if len(self.operations) != 1:
            raise ValueError("compound clarification has no single operation")
        return self.operations[0]


@dataclass(frozen=True, slots=True)
class CompoundEffectContract:
    minimum_effects: int
    required_clause_sequences: tuple[tuple[str, ...], ...]
    # Positive clauses in source order. An empty operation tuple marks the
    # one clause whose identity still needs independent verification. Special
    # fail-closed contracts (negation, correction, deferral, identity conflict)
    # deliberately leave this empty and therefore can never grant authority.
    clause_requirements: tuple[tuple[str, tuple[str, ...]], ...] = ()


@dataclass(frozen=True, slots=True)
class ApplicationCatalogIndex:
    """Bounded, reusable view of one authenticated application snapshot."""

    entries: tuple[tuple[str, str], ...]
    keys: frozenset[str] = field(repr=False)
    entity_identities: tuple[tuple[str, str], ...] = field(repr=False)
    occurrence_pattern: re.Pattern[str] | None = field(
        repr=False,
        compare=False,
    )

    def __iter__(self) -> Iterator[str]:
        return (name for name, _ in self.entries)

    def __len__(self) -> int:
        return len(self.entries)


@dataclass(frozen=True, slots=True)
class GameCatalogIndex:
    """Bounded authenticated identities for locally installed games."""

    # normalized name, provider, app id, display name
    entries: tuple[tuple[str, str, str, str], ...] = ()


_EXPLICIT_EFFECTS_NOT_RESOLVED = object()


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
    r"llovera|temperature|temperatura)\b"
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
    r"research|look\s+into|look\s+up)\s+"
    r"(?:(?:en\s+internet|en\s+la\s+web|online|on\s+the\s+internet|on\s+the\s+web)\s+)?"
    r"(?:(?:sobre|acerca\s+de|about|a)\s+)?"
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
    r"(?:que|qué|what)\s+(?:es|fue|era|is|was)|"
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
    folded_entity = _fold(entity)
    if not folded_entity or not re.search(r"[a-z]", folded_entity):
        return None
    if len(entity.encode("utf-8")) > 80 or len(folded_entity.split()) > 8:
        return None
    if _has(folded_entity, r"^(?:un|una|unos|unas|a|an|el|la|los|las|the|lo)\b"):
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


def _public_live_lookup_request(folded: str) -> bool:
    """Recognize live feeds that require a public lookup to answer."""

    head = _request_head(folded)
    weather_heads = {
        "are",
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
        r"cold|frio|fria)\b",
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


def _nominal_datetime_query(folded: str) -> bool:
    return re.fullmatch(
        r"(?:(?:y|and)\s+)?(?:(?:la|el|the)\s+)?"
        r"(?:hora|fecha|time|date)[\s?!.]*",
        folded.lstrip("¿¡ "),
    ) is not None


_CLOCK_READ_HEAD = (
    r"(?:dime|decime|decir(?:me)?|muestra(?:me)?|mostra(?:r)?(?:me)?|"
    r"ensena(?:r)?(?:me)?|pasa(?:r)?(?:me)?|dame|dar(?:me)?|"
    r"indica(?:r)?(?:me)?|consulta(?:r)?|comprueba|comprobar|revisa(?:r)?|"
    r"tell\s+me|show(?:\s+me)?|give\s+me|check)"
)


_COUNTDOWN_HOUR_WORDS = {
    "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7, "ocho": 8,
    "nueve": 9, "diez": 10, "once": 11, "doce": 12, "one": 1, "two": 2, "three": 3, "four": 4,
    "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
}
_COUNTDOWN_TARGET = re.compile(
    r"^(?:cuanto\s+(?:tiempo\s+)?(?:falta|queda|resta)\s+(?:para|hasta)|"
    r"how\s+(?:long|much\s+time)\s+(?:until|till|before|to|is\s+left\s+(?:until|till|before)))\s+"
    r"(?:(?:el|la|las|the)\s+)?"
    r"(?:(?P<noon>mediodia|noon|midday)|(?P<midnight>medianoche|midnight)|"
    r"(?P<hour>\d{1,2}|" + "|".join(sorted(_COUNTDOWN_HOUR_WORDS, key=len, reverse=True)) + r")"
    r"(?:[:.h](?P<minute>\d{2}))?"
    r"(?:\s+(?:y\s+(?P<spoken_minute>media|cuarto|\d{1,2}))?)?"
    r"(?:\s*(?P<ampm>[ap])\.?\s*m\.?|\s+(?:de\s+la\s+|en\s+la\s+|in\s+the\s+|)"
    r"(?P<part>manana|madrugada|tarde|noche|morning|afternoon|evening|night))?"
    r"(?:\s+(?:de\s+hoy|today|hoy))?"
    r")\s*$"
)


def countdown_target(text: str) -> str | None:
    """«cuánto falta para las 3 de la tarde» → «15:00»: the clock time asked about.

    CLOCK1327 H0399: a countdown resolves by reading the clock; the
    remaining time is computed by the mind, never by the narrator.
    """

    folded = _strip_request_envelope(_fold(text)).strip(" ¿?¡!.,")
    match = _COUNTDOWN_TARGET.match(folded)
    if match is None:
        return None
    if match.group("noon"):
        return "12:00"
    if match.group("midnight"):
        return "00:00"
    raw_hour = match.group("hour")
    hour = int(raw_hour) if raw_hour.isdecimal() else _COUNTDOWN_HOUR_WORDS[raw_hour]
    minute = int(match.group("minute") or 0)
    spoken = match.group("spoken_minute")
    if spoken == "media":
        minute = 30
    elif spoken == "cuarto":
        minute = 15
    elif spoken and spoken.isdecimal():
        minute = int(spoken)
    part = match.group("part") or ""
    ampm = match.group("ampm") or ""
    if hour > 23 or minute > 59:
        return None
    if ampm == "p" or part in {"tarde", "noche", "afternoon", "evening", "night"}:
        if hour < 12:
            hour += 12
    elif ampm == "a" or part in {"manana", "madrugada", "morning"}:
        if hour == 12:
            hour = 0
    return f"{hour:02d}:{minute:02d}"


def _direct_current_time_request(folded: str) -> bool:
    """Recognize a whole request for the local clock, shared by all three gates.

    Only present/local modifiers belong to this reading. Event dates, elapsed
    CPU time, other places and literal content must not match a trailing noun.
    """

    if countdown_target(folded) is not None:
        return True
    # CLOCK1327 H0054/H0312 «Tiempo»/«tiempo»: the bare word asks for the
    # time; the weather is not something this PC reads.
    if re.fullmatch(r"(?:el\s+)?tiempo(?:\s*,?\s*(?:por\s+favor|porfa|please))?",
                    _strip_request_envelope(folded).strip(" ¿?¡!.,")):
        return True
    current = r"(?:actual|local|(?:de\s+)?hoy|ahora(?:\s+mismo)?|(?:right\s+)?now)"
    nominal = (
        r"(?:(?:la|el|the)\s+)?"
        r"(?:(?:current|local)\s+){0,2}(?:hora|fecha|time|date)"
        rf"(?:\s+{current}){{0,2}}|today(?:['’]s)?\s+date"
    )
    observation = (
        rf"(?:{_CLOCK_READ_HEAD}|"
        r"(?:necesito|quiero|quisiera)\s+saber|"
        r"(?:i\s+)?(?:need|want)\s+to\s+know)"
    )
    return re.fullmatch(
        rf"(?:{observation}\s+(?:{nominal})|"
        rf"(?:what(?:\s+is|'s|’s|s)\s+(?=(?:the|current|local|today)\b)|"
        rf"(?:que|cual)\s+es\s+)(?:{nominal})|"
        rf"(?:{observation}\s+)?(?:"
        r"(?:que|qe)\s+(?:hora|ora|fecha|dia)\s+es(?:\s+(?:ahora|hoy|ya))?|"
        r"what\s+(?:time|date|day)\s+is\s+it(?:\s+(?:(?:right\s+)?now|today))?)|"
        rf"(?:hora|fecha)\s+{current}|(?:current|local)\s+(?:local\s+)?(?:time|date)|"
        rf"today(?:['’]s)?\s+date|(?:{observation}\s+)?"
        r"(?:the\s+)?time\s+(?:right\s+now|now)"
        r"(?:\s*[,;:]?\s*what\s+is\s+it)?|"
        r"que\s+hora\s+(?:marca|muestra|tiene)\s+(?:este|el|mi)\s+"
        r"(?:computador|equipo|pc)|"
        r"what\s+time\s+does\s+(?:this|the|my)\s+(?:computer|pc)\s+(?:show|display)|"
        r"(?:search|look|busca)\s+(?:to\s+)?(?:find|encontrar)\s+"
        r"(?:(?:the|la)\s+)?(?:current|actual)\s+(?:local\s+)?"
        r"(?:time|hora)(?:\s+(?:and|y)\s+(?:time\s+zone|zona\s+horaria))?)",
        _strip_request_envelope(folded).strip(" ¿?¡!."),
        re.IGNORECASE,
    ) is not None


def datetime_followup_antecedent(
    text: str, previous_requests: Iterable[str],
) -> str | None:
    """Find a clock antecedent through contiguous human ellipses, newest first.

    A change of subject ends the chain. Assistant responses and remembered
    clock values are deliberately absent: the next turn still needs a read.
    """
    if not _nominal_datetime_query(_strip_request_envelope(_fold(text))):
        return None
    for request in previous_requests:
        folded = _strip_request_envelope(_fold(request))
        if _nominal_datetime_query(folded):
            continue
        return request if _direct_current_time_request(folded) else None
    return None


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


def _relative_calendar_read_request(folded: str) -> bool:
    """Recognize a read-only calendar query with a relative bounded range."""

    return (
        re.fullmatch(
            r"(?:is|are)\s+there\s+(?:any\s+)?(?:events?|meetings?|appointments?)\s+"
            r"(?:planned|scheduled|booked)\s+(?:for|in|over)\s+the\s+next\s+"
            r"(?:\d+|one|two|three|four|five|six|several|few)\s+"
            r"(?:days?|weeks?|months?)[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
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


def operation_domain_is_grounded(
    text: str,
    operation: str,
    application_names: Iterable[str] | ApplicationCatalogIndex = (),
    *,
    previous_user_text: str | None = None,
    available_operations: Iterable[str] = (),
) -> bool | None:
    """Apply the curated one-sided family gates.

    A catalogue-derived gate was measured here and rejected. It gave each
    operation the words distinctive to it and vetoed a request naming none of
    them, which looked free: zero over-veto against R2 and eight of eleven
    known near-miss collisions caught. R2 is *seen* surfaces, and that was the
    wrong population to calibrate against. On the unseen paraphrases of cut B
    it vetoed 161 additional legitimate target operations, taking over-veto
    from 224 of 560 to 385 of 560. Coverage of a few collisions is not worth
    refusing a quarter more of what the person actually asks for, so it is
    gone; the collisions it uniquely caught are curated below instead.

    That leaves a second problem the curated rules cannot see: what they do not
    cover at all. 60 of the 158 catalogue operations reach no rule, and a
    request outside the catalogue walked straight through the gap. On the
    veto-reach V1 population "Barre las hojas del sendero" -- sweeping leaves
    off a path -- executed ``filesystem.sandbox.append.named`` and said nothing.
    The deterministic recogniser correctly declined it; the gate returned None
    because no rule names that operation, so nothing removed the authority the
    model had taken.

    The floor below closes that for the family that leaked, by generalising the
    condition the covered filesystem rules already impose rather than by adding
    another hand-written entry: **an operation that acts on a file must name
    something in the filesystem.** It is one-sided like every rule here -- it
    can only remove authority -- and it applies solely where no specific rule
    spoke.
    """

    if operation_identity_is_a_near_miss(text, operation):
        # A neighbouring substitute is not a missed paraphrase. The identity
        # verifier may revive the latter; it must not revive the former.
        return False
    verdict = _curated_domain_is_grounded(text, operation, application_names)
    if (
        verdict is False
        and operation == "audio.volume"
        and previous_user_text
        and _contextual_output_level_target(text, previous_user_text, available_operations)
    ):
        return True
    if verdict is not None:
        return verdict
    return _uncovered_family_floor(_fold(text), operation)


def _completed_missing_volume_level_request(
    text: str, previous_user_text: str | None, available_operations: Iterable[str],
) -> str | None:
    """Attach a numeric answer only to a unique, incomplete local-level request.

    Both surfaces are user-authored reference data. The ordinary resolver still
    checks the resulting request, including every current denial and effect.
    An assistant question or a completed earlier action cannot supply this target.
    """
    if not previous_user_text:
        return None
    clauses = _request_clauses(_strip_request_envelope(_fold(text)))
    if not clauses or re.fullmatch(
        r"(?:(?:a|al|to|at)\s+)?(?:100|\d{1,2})\s*"
        r"(?:%|por ciento|percent)?[\s,.!?]*",
        clauses[0],
    ) is None:
        return None
    prior = resolve_explicit_clarification_intent(previous_user_text, available_operations)
    if prior is None or prior.operations != ("audio.volume",) or prior.missing_fields != ("level",):
        return None
    return f"{previous_user_text.strip()}\n{text}"


_MSG_DICTATION_SEPARATOR = re.compile(
    r"\s*(?::|\b(?:que\s+diga|que\s+dice|diciendo(?:le)?|dici[eé]ndole|saying|that\s+says|que|that)\b)",
    re.IGNORECASE,
)


def _completed_missing_message_channel_request(
    text: str, previous_user_text: str | None, available_operations: Iterable[str],
) -> str | None:
    """MSGCLAR «mandale al grupo Musica: prueba 1 …» → «¿por WhatsApp o por
    Discord?» → «por WhatsApp»: the answered client completes the previous
    message request whose only missing field was the channel. The completed
    request is the person's own words with «por <client>» before the dictated
    text, and the ordinary draft reader still has to accept it."""

    if not previous_user_text:
        return None
    answer = _strip_request_envelope(_fold(text)).strip()
    found = re.fullmatch(
        r"[¿?¡!\s]*(?:(?:por|en|via|on|in|through|by|usando|using|con|with)\s+)?"
        r"(?:(?:el|la|the)\s+)?(?:(?:app|aplicacion|application)\s+(?:de\s+|of\s+)?)?"
        r"(?P<ch>whatsapp|wsp|discord)"
        r"(?:\s+(?:por\s+favor|please|mejor|nomas))?[\s.!?]*",
        answer,
    )
    if found is None:
        return None
    prior = resolve_explicit_clarification_intent(previous_user_text, available_operations)
    if prior is None or prior.operations != ("message.send",) or prior.missing_fields != ("channel",):
        return None
    channel = "whatsapp" if found.group("ch") in {"whatsapp", "wsp"} else "discord"
    previous = _strip_request_envelope(previous_user_text.strip()).strip()
    separator = _MSG_DICTATION_SEPARATOR.search(previous)
    if separator is None:
        return None
    joiner = " on " if _has(
        _fold(previous), r"^[^\w]*(?:send|write|text|message|tell|ask|let)\b",
    ) else " por "
    rest = previous[separator.start():]
    completed = previous[:separator.start()].rstrip() + joiner + channel + (" " if rest.startswith(":") else "") + rest
    return completed if message_draft_request(completed) is not None else None


_MSG_VERB = r"(?:m[aá]nd[aá](?:le|me|les)?|env[ií]a(?:le|me|les)?|envi[aá](?:le|me|les)?|escrib[ií](?:le|me)?|escr[ií]be(?:le|me)?|send|write|text|message)"
_MSG_OBJECT = r"(?:(?:un|una|el|a|an|the)\s+)?(?:mensaje|message|texto|text)"
_MSG_OBJECT_CHANNEL = r"(?:(?:un|una|el|a|an|the)\s+)?(?P<och>whatsapp|wsp|discord)(?:\s+(?:mensaje|message))?"
_MSG_CHANNEL = r"(?P<ch>whatsapp|wsp|discord)"
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


def client_channel_request(text: str) -> tuple[str, str] | None:
    """DISCORD1839 «ve a Cotele en Discord», «Go to Cotele in Discord», «Andá al canal
    Cotele en Discord»: the client and the place named by a go-to order scoped to a
    messaging client; the channel is located and the person asked before joining."""

    folded = _strip_request_envelope(_fold(text)).strip()
    found = re.fullmatch(
        r"[¿?¡!\s]*(?:(?:por\s+favor|please)[,]?\s+)?"
        r"(?:(?:en|in|on)\s+(?P<client_a>" + _NAVIGATION_CLIENT + r")[,]?\s+)?"
        r"(?:ve|anda|andate|entra|entrale|metete|navega|llevame|go|navigate|switch|cambia|cambiate|take\s+me)\s+"
        r"(?:a(?:l)?|to|hacia|into)\s+(?:(?:el|la|the)\s+)?(?:(?:canal|channel|chat|sala|room)\s+(?:de\s+(?:voz|texto)\s+)?(?:de\s+)?)?"
        r"(?P<place>\S.{0,60}?)"
        r"(?:\s+(?:en|in|on|de|del|of)\s+(?:el\s+)?(?P<client_b>" + _NAVIGATION_CLIENT + r"))?"
        r"(?:\s+(?:por\s+favor|please))?[\s.!?]*",
        folded,
    )
    if found is None:
        return None
    client = found.group("client_a") or found.group("client_b")
    place = found.group("place").strip(" \"'«»")
    if client is None or not place or _has(place, r"https?://|\b(?:[a-z0-9-]+\.)+[a-z]{2,63}\b"):
        return None
    raw = _strip_request_envelope(text).strip()
    start = _fold(raw).find(place)
    literal = raw[start:start + len(place)] if start >= 0 and len(_fold(raw)) == len(raw) else place
    return client, literal.strip(" \"'«».!?")


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
        channel = (groups.get("ch") or groups.get("och") or "").casefold()
        channel = "whatsapp" if channel in {"whatsapp", "wsp"} else channel
        recipient = re.sub(r"^(?:el\s+grupo|la\s+|el\s+|the\s+group|the\s+)\s*", "", (groups.get("rec") or "").strip(), flags=re.IGNORECASE).strip(" .")
        # MSGCLAR «que diga: prueba 2, todo OK»: the dictation colon after the
        # separator is punctuation, never part of the text.
        body = (groups.get("body") or "").strip().lstrip(":").strip()
        body = re.sub(
            r"^(?:que\s+diga\s+|que\s+dice\s+|diciendo(?:le)?\s+(?:que\s+)?|dici[eé]ndole\s+(?:que\s+)?|saying\s+|that\s+says\s+|que\s+|that\s+)",
            "", body, flags=re.IGNORECASE,
        ).strip()
        body = body.rstrip(" .!?") if len(body) > 1 else body
        if channel not in {"whatsapp", "discord"} or not recipient or not body:
            continue
        if re.search(r"\b(?:whatsapp|wsp|discord)\b", _fold(recipient)) or _fold(recipient) in {"mensaje", "message"}:
            continue
        if len(recipient.encode("utf-8")) > 512 or len(body.encode("utf-8")) > 16_384:
            continue
        return channel, recipient, body
    return None


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


def _completed_missing_music_request(
    text: str, previous_user_text: str | None, available_operations: Iterable[str],
) -> str | None:
    """MUSIC1571 «pon música» → «¿qué música?» → «lofi»: attach the person's
    answer to the incomplete music request as the music named, so it resolves
    like «pon música de lofi». Only after a request the resolver itself reads
    as a music clarification, and only for a short content answer (no request
    head, no question); the answer keeps its own words."""

    if not previous_user_text:
        return None
    prior = resolve_explicit_clarification_intent(previous_user_text, available_operations)
    if prior is None or prior.operations != ("media.play.query",) or prior.missing_fields != ("query",):
        return None
    answer = text.strip().strip("\"'“”«»").strip()
    folded = _strip_request_envelope(_fold(answer))
    words = folded.split()
    if (
        not folded
        or len(words) > 8
        or "?" in answer
        or _head_is(_request_head(folded), _COVERAGE_ACTION_HEAD)
        or _negative_action_forms(folded)
        or re.fullmatch(r"(?:no|nada|ninguna|none|nothing|cancela|cancelar|cancel|olvidalo|dejalo)\b.*", folded)
    ):
        return None
    answer = re.sub(r"^(?:algo\s+de|un\s+poco\s+de|some|something\s+like)\s+", "", answer, flags=re.IGNORECASE).strip(" .!")
    if not answer:
        return None
    browser_music = _named_browser_music_request(previous_user_text)
    if browser_music is not None and browser_music[1] is None:
        # MUSIC1827 «abrí chrome y poné música» → «¿qué música?» → «rock»: the
        # answer names the music, played from YouTube in that browser.
        label = {"opera_gx": "opera gx"}.get(browser_music[0], browser_music[0])
        return f"pon música de {answer} en {label}"
    if _has(_fold(previous_user_text), r"\bspotify\b"):
        return f"pon música de {answer} en spotify"
    if _has(_fold(previous_user_text), r"\bvideos?\b"):
        # VIDEO1717 «abre youtube y pon un video» → «¿qué video?» → «uno de
        # gatos»: the answer names the video, played from YouTube.
        answer = re.sub(r"^(?:(?:uno|una|one)\s+)?(?:de|of|sobre|about)\s+", "", answer, flags=re.IGNORECASE).strip(" .!") or answer
        return f"pon un video de {answer} en youtube"
    return f"pon música de {answer}"


def _contextual_output_level_target(
    text: str, previous_user_text: str, available_operations: Iterable[str],
) -> bool:
    """Ground a numeric pronoun target in the immediately preceding audio request.

    This only checks the domain of a proposed absolute-level operation. It does
    not choose the operation, extract its value or claim an observed level.
    Full-clause matching keeps another object or effect outside this inheritance.
    """
    folded = _strip_request_envelope(_fold(text))
    if re.fullmatch(
        r"(?:(?:pon|fija|ajusta|deja|establece)(?:lo|la)\s+(?:a|al)|"
        r"(?:set|put|leave|adjust)\s+it\s+(?:to|at))\s+"
        r"\d{1,3}\s*(?:%|por ciento|percent)?"
        r"(?:\s+(?:ahora|now|please|por favor))?[.!?]*",
        folded,
    ) is None:
        return False
    # A list of earlier targets is not a unique antecedent, even when the
    # audio recognizer can account for one part of that request.
    if _has(_fold(previous_user_text), r"\b(?:y|and|o|or)\b|;"):
        return False
    prior = resolve_explicit_effects(previous_user_text, available_operations)
    return (
        prior is not None
        and len(prior.operations) == 1
        and prior.operations[0] in {"audio.status", "audio.volume", "audio.volume.adjust"}
        and operation_domain_is_grounded(previous_user_text, prior.operations[0]) is True
    )


_FILESYSTEM_OBJECT_NOUN = (
    r"\b(?:archivos?|file|files|fichero|ficheros|carpetas?|folders?|"
    r"directorios?|directory|directories|ruta|rutas|path|paths|"
    r"documento|documentos|document|documents|sandbox|papelera|trash|"
    r"recycle|escritorio|desktop|descargas|downloads|imagenes|pictures|"
    r"copia|copias|backup|backups|respaldo|respaldos|"
    r"txt|csv|json|pdf|docx|xlsx|md|log)\b"
    r"|(?:^|\s)[a-z]:[\\/]|\.[a-z0-9]{2,4}\b"
)


# A weighted comparative veto was written here and measured and rejected. It
# weighed each term by how few operations the alias corpus attaches it to, and
# refused a proposal that carried no distinctive evidence when another operation
# carried some. On the eight V2 executions it reversed the inversion exactly --
# peripheral.list 1.48 against system.status 0.00, system.process.list 1.48
# against window.application.status 0.00 -- and stopped four of the seven wrong
# ones. Then it refused three of six plainly correct requests, among them
# "revisa el estado del audio" for ``audio.status`` and the note.create text of
# a physical mission that currently passes. Deriving a rule from the cases that
# failed and checking it only there is exactly the error R103 made; this is the
# third catalogue-derived gate to look free on its own evidence and break
# elsewhere. The finding is kept in the maintainability register, not as dead
# code here.
def _uncovered_family_floor(folded: str, operation: str) -> bool | None:
    """Require the object class for families no curated rule reaches.

    Only ``filesystem.`` is floored today, because that is where an unsolicited
    effect was actually observed. The remaining uncovered families are recorded
    as an open defect with their count rather than papered over here: adding
    rules for families no measurement has implicated would be the same
    hand-maintained treadmill this gate is already stuck on.
    """

    if operation.startswith("filesystem."):
        return _has(folded, _FILESYSTEM_OBJECT_NOUN)
    return None


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


def _curated_domain_is_grounded(
    text: str,
    operation: str,
    application_names: Iterable[str] | ApplicationCatalogIndex = (),
) -> bool | None:
    """Remove authority when a family names the wrong domain.

    One-sided: this never selects an operation.  A named computing domain
    (``bluetooth``, ``wifi``/``wireless``) is enough to keep the proposal;
    extra action-verb lists must not fail closed on a paraphrase that already
    names that domain.  ``False`` is for contradiction or an unnamed domain
    on a covered family.  ``None`` leaves uncovered catalogue operations
    untouched.
    """

    folded = _fold(text)
    if operation == "app.open":
        folded = _strip_request_envelope(folded)
        applications = build_application_catalog_index(application_names)
        return (
            _authenticated_application_target(folded, applications) is not None
            or _authenticated_application_desired_open(
                folded,
                applications,
            )
            is not None
            or bool(_open_application_spans(folded))
        )
    if operation == "task.delete":
        # "Bota los papers viejos al contenedor" reached task.delete. Throwing
        # paper away is not deleting a task, so the task domain has to be named.
        return _has(
            folded,
            r"\b(?:tarea|tareas|task|tasks|pendiente|pendientes|todo|to-?do)\b",
        )
    if operation.startswith("peripheral.") and operation != "peripheral.list":
        # "Vacuum the hallway carpet" reached peripheral.scan; a household
        # appliance is not a connected device inventory. peripheral.list keeps
        # its own stricter gate below -- a broad rule here would shadow it and
        # hand back authority that gate already removes.
        return _has(
            folded,
            r"\b(?:periferico|perifericos|peripheral|peripherals|"
            r"dispositivo|dispositivos|device|devices|"
            r"impresora|impresoras|printer|printers|"
            r"escaner|scanner|usb|hardware|accesorio|accesorios)\b",
        )
    if operation == "clipboard.paste":
        # Vocabulary grounding cannot separate this one: pasting a stamp onto an
        # envelope uses the operation's own verb. Ask what is being pasted
        # instead. The clipboard has to be named, or the thing pasted has to be
        # what was previously copied, or the target has to be a focused control.
        return _clipboard_paste_domain(folded)
    if operation == "window.move":
        # "Move the wardrobe towards the far window" names a window, but as the
        # destination. What moves has to be the window itself, so a destination
        # preposition between the verb and the window disqualifies it.
        return (
            re.search(
                r"\b(?:mueve|mover|muevele|desplaza|desplazar|reubica|move)\b"
                r"(?:(?!\b(?:hacia|towards?|junto\s+a|al\s+lado\s+de|"
                r"next\s+to|beside|near|cerca\s+de|frente\s+a|debajo\s+de|"
                r"under|below|behind|detras\s+de|pegado\s+a)\b)[\s\S])"
                r"{0,48}?\b(?:ventana|ventanas|window|windows)\b",
                folded,
                re.IGNORECASE,
            )
            is not None
        )
    if operation in {"system.recyclebin.empty", "system.recyclebin.restore"}:
        # "Envia la bicicleta vieja al reciclaje" was planned as emptying the
        # Windows Recycle Bin -- twice. Municipal recycling and the desktop bin
        # share a word in Spanish, and this operation is destructive and
        # irreversible, so the bin has to be named as the bin.
        return _has(
            folded,
            r"\bpapelera\b|\brecycle\s*bin\b|\brecycling\s*bin\b|"
            r"\btrash\b|\bbasura\s+de(?:l)?\s+(?:escritorio|windows|equipo|pc)\b",
        )
    if operation in {"app.close", "window.close"}:
        # "Cuelga el cuadro en la pared del pasillo" was planned as app.close.
        # Closing something on screen needs the screen named: an authenticated
        # application, or the literal window/program vocabulary.
        applications = build_application_catalog_index(application_names)
        return _authenticated_application_target(
            folded, applications
        ) is not None or _authenticated_application_close_target(
            folded, applications
        ) is not None or deictic_close_request(folded) or _has(
            folded,
            r"\b(?:aplicacion|aplicaciones|application|applications|app|apps|"
            r"programa|programas|program|programs|ventana|ventanas|"
            r"window|windows|pestana|pestanas|tab|tabs|proceso|process)\b",
        )
    if operation == "backup.list":
        return (
            _has(
                folded,
                r"\b(?:backup|backups|respaldo|respaldos|"
                r"copia|copias)(?:\s+de\s+seguridad)?\b",
            )
            and _has(
                folded,
                rf"\b(?:{_LIST}|inventario|inventory|disponibles?|available|"
                r"privad[oa]s?|private)\b",
            )
            and not _has(folded, r"\b(?:log|logs|registro|job|trabajo)\b")
        )
    if operation == "backup.create":
        return (
            _has(folded, r"\b(?:backup|respaldo|copia\s+de\s+seguridad)\b")
            and _has(folded, r"\b(?:archivo|file)\b")
            and not _has(
                folded,
                r"\b(?:pendrive|pen drive|usb|disco externo|external drive|"
                r"documentos|documents|carpeta|folder)\b",
            )
        )
    if operation == "bluetooth.radio.set":
        # Domain noun is the gate. Requiring a closed verb list vetoed
        # "apagame el bluetooth" because "apagame" is not "apaga". Opening
        # Bluetooth settings is a different effect and stays a contradiction.
        if not _has(folded, r"\bbluetooth\b"):
            return False
        if _has(
            folded,
            r"\b(?:configuracion|settings|entra|enter|abre|open)\b",
        ):
            return False
        return True
    if operation == "software.python.status":
        return _has(folded, r"\bpython\b")
    if operation == "software.python.package.status":
        return _python_package_request(folded) is not None
    if operation == "storage.removable.list":
        return _has(folded, r"\b(?:pendrive|pen|usb|externo|externa|external|removable|flash|stick)\b")
    if operation == "calculator.expression.evaluate":
        return calculator_expression_request(folded) is not None
    if operation == "display.status":
        return _has(folded, r"\b(?:resolucion|monitor(?:es)?|pantallas?|screens?|displays?|hz|hertz|hercios|frecuencia|refresh)\b")
    if operation == "bluetooth.radio.status":
        return _has(folded, r"\bbluetooth\b") and not _has(
            folded, r"\b(?:configuracion|settings|entra|enter|abre|open)\b"
        )
    if operation == "bluetooth.device.list":
        return (
            _has(folded, r"\bbluetooth\b")
            and _has(
                folded,
                r"\b(?:dispositivos?|devices?|equipos?|accesorios?|hardware|"
                r"detectad[oa]s?|detected|visibles?|visible|cercan[oa]s?|nearby|"
                r"lista|listar|list|enumera|enumerate|muestra|show|cuales|which)\b",
            )
            and not _has(
                folded,
                r"\b(?:ciudad|city|historia|story|imaginari[oa]|imaginary)\b",
            )
        )
    if operation == "input.pointer.control":
        # The pointer family was reachable without ever naming a pointer:
        # "consigue un ride hasta el centro" became input.pointer.control.
        return _has(
            folded,
            r"\b(?:puntero|pointer|cursor|raton|mouse|trackpad|touchpad)\b"
            r"|\b(?:clic|click|clickea|clickear|doble\s+clic|double\s+click|"
            r"arrastra|arrastrar|drag|"
            r"scroll|scrollea|scrollear|rueda)\b",
        )
    if operation == "input.visible.click":
        # Pointing verbs keep the coat-button false friend out. Navigate verbs
        # ("ve a", "go to") are the second clause of Open App → Click X and
        # only ground click, never pointer.control.
        if _visible_click_label(folded, allow_navigate=True) is not None:
            return True
        return _has(
            folded,
            r"\b(?:puntero|pointer|cursor|raton|mouse|trackpad|touchpad)\b"
            r"|\b(?:clic|click|clickea|clickear|doble\s+clic|double\s+click|"
            r"pulsa|presiona|press)\b",
        )
    if operation in {
        "input.key.press",
        "input.text.type",
        "input.keyboard.open",
        "input.keyboard.layout",
        "input.keyboard.status",
    }:
        return _has(
            folded,
            r"\b(?:teclado|keyboard|tecla|teclas|key|keys|"
            r"escribe|escribir|escribi|tipea|type|typing|teclea|teclear|"
            r"atajo|shortcut|combinacion|combination|presiona|press|"
            r"distribucion|layout|"
            r"dale\s+(?:enter|intro|return)|(?:press|hit|type)\s+enter)\b",
        )
    if operation in {"calendar.event.create", "calendar.event.list"}:
        names_calendar = _has(
            folded,
            r"\b(?:calendario|calendars?|agendas?|eventos?|events?|citas?|"
            r"appointments?|reunion|reuniones|meetings?)\b",
        )
        if not names_calendar or _has(
            folded,
            r"\b(?:email|e-mail|correo|mail|asunto|subject|escribele|"
            r"write to|send to)\b",
        ):
            return False
        # Creating and listing are opposite directions of one family. "Haz un
        # appointment con el doctor" was grounded for calendar.event.list, so
        # asking to make an appointment could execute a listing instead -- a
        # near-miss effect. Each direction now needs its own verb.
        creation = _has(
            folded,
            r"\b(?:crea|crear|agendar|agendame|programa|programar|"
            r"reserva|reservar|anota|anotar|haz|hazme|"
            r"make|create|schedule|book|set\s+up|add)\b"
            r"|\bagenda\s+(?:un|una|el|la|mi)\b",
        )
        reading = _has(
            folded,
            r"\b(?:que|cuales|cuando|cuantas|muestra|muestrame|dime|ver|"
            r"lista|listar|list|show|tell|revisa|consulta|tengo|hay|"
            r"what|which|when|how\s+many)\b",
        )
        if operation == "calendar.event.create":
            return creation
        return reading and not creation
    if operation in {"browser.navigate", "browser.navigate.named"}:
        if operation == "browser.navigate" and _symbolic_web_destination(text) is not None:
            return True
        if operation == "browser.navigate.named" and _named_browser_search(text) is not None:
            return True
        return _has(
            folded,
            r"\b(?:navegador|browser|web|website|sitio|site|pagina|page|"
            r"internet|google|wikipedia|youtube)\b|https?://|"
            r"\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}\b",
        ) and not _has(folded, r"\b(?:archivo|file|carpeta|folder)\b")
    if operation == "web.search":
        # A semantic selector may confuse local inspection verbs with a web
        # lookup (for example, "look through Downloads"). A direct search with
        # its own query need not repeat "internet", but cannot borrow a private
        # or local operand. This gate only retains a proposal, never selects it.
        direct_public_search = _direct_public_search_query(text) is not None
        return (
            _symbolic_web_destination(text) is not None
            or _location_recommendation_request(folded)
            or _public_route_lookup_request(folded)
            or _public_calendar_fact_lookup_request(folded)
            or _public_live_lookup_request(folded)
            or _public_commerce_lookup_request(folded)
            or (
                _has(
                    folded,
                    rf"\b(?:{_SEARCH}|consulta|consultar|investiga|investigar|"
                    r"investigate|look\s+on)\b",
                )
                and (
                    direct_public_search
                    or _has(
                        folded,
                        r"\b(?:web|internet|online|google|bing|public\s+api)\b",
                    )
                )
                and not _has(
                    folded,
                    r"\b(?:archivo|file|carpeta|folder|documentos?|documents?|"
                    r"descargas|downloads?|escritorio|desktop|notas?|notes?|"
                    r"tareas?|tasks?|recordatorios?|reminders?|aplicaciones?\s+"
                    r"instaladas?|installed\s+applications?|installed\s+apps?)\b",
                )
            )
        )
    if operation in {"game.install.prepare", "game.install.status"}:
        return _has(folded, r"\b(?:app\s*id|appid)\s*[:#-]?\s*\d{1,16}\b") or (
            _has(folded, r"\b\d{2,16}\b")
            and _has(
                folded,
                r"\b(?:steam|juego|game|instala|instalar|install|"
                r"descarga|download|progreso|progress|estado|status)\b",
            )
        )
    if operation == "filesystem.create.directory":
        # Desktop, Documents and Downloads are catalog roots since the owner's
        # decision of 2026-09-13 (point 2); pictures and drive letters are not.
        return _has(
            folded, r"\b(?:carpeta|folder|directorio|directory)\b"
        ) and not _has(
            folded,
            r"\b(?:imagenes|pictures|fotos|photos)\b|(?:^|\s)[a-z]:[\\/]",
        )
    if operation == "filesystem.path.ensure.absent":
        return (
            _has(folded, r"\b(?:archivo|file|ruta|path)\b")
            and not _has(folded, r"\b(?:carpeta|folder|directorio|directory)\b")
            and _has(
                folded,
                r"\b(?:borra|borrar|elimina|eliminar|delete|remove|"
                r"ausente|absent|no existe|does not exist|verifica|verify|check)\b",
            )
        )
    if operation == "filesystem.hash":
        if _has(folded, r"\bhash\b") and _has(folded, r"\b(?:archivo|file)\b"):
            return True
        return None
    if operation == "filesystem.list":
        return _has(
            folded,
            r"\b(?:archivos?|files?|carpetas?|folders?|directorios?|directories?|"
            r"entradas?|entries|sandbox)\b",
        ) and _has(
            folded,
            rf"\b(?:{_LIST}|enumera|enumerate|muestra|show|inventario|inventory|"
            r"contenido|contents?)\b",
        )
    if operation == "filesystem.write.text":
        # Known folders are catalog roots since 2026-09-13 (owner decision,
        # point 2); pictures and drive letters remain outside.
        return (
            _has(folded, r"\b(?:archivo|file|texto|text)\b")
            and _has(folded, r"\b(?:escribe|write|guarda|save|crea|create)\b")
            and not _has(
                folded,
                r"\b(?:imagenes|pictures|fotos|photos)\b|(?:^|\s)[a-z]:[\\/]",
            )
        )
    if operation == "game.catalog.list":
        return (
            _has(folded, r"\b(?:steam|juegos?|games?)\b")
            and _has(
                folded,
                r"\b(?:catalogo|catalog|biblioteca|library|lista|listar|list|"
                r"instalados|installed)\b",
            )
            and not _has(
                folded,
                r"\b(?:capturas?|screenshots?|tienda|store|shop|loja)\b",
            )
        )
    if operation == "game.install.status":
        return _has(folded, r"\b(?:appid|app id)\s+\d{1,16}\b") and _has(
            folded,
            r"\b(?:estado|status|instalacion|installation|instalad[oa]|installed)\b",
        )
    if operation == "game.launch":
        return _has(folded, rf"\b(?:{_OPEN}|lanza|launch|ejecuta|run)\b") and not _has(
            folded,
            r"\b(?:capturas?|screenshots?|tienda|store|shop|loja|"
            r"biblioteca|library)\b",
        )
    if operation == "audio.microphone.mute":
        return (
            _has(folded, r"\b(?:microfono|microphone|mic)\b")
            and _has(
                folded,
                r"\b(?:mutea|mutear|mute|silencia|silenciar|unmute|"
                r"reactiva|reactivar)\b",
            )
            and not _has(
                folded,
                r"\b(?:en|in|inside)\s+(?:discord|teams|zoom|skype|"
                r"whatsapp|una aplicacion|an app)\b",
            )
        )
    if operation == "email.latest.reply":
        return (
            _has(folded, r"\b(?:responde|responder|reply|answer)\b")
            and _has(folded, r"\b(?:ultimo|ultima|latest|recent)\b")
            and _has(folded, r"\b(?:correo|email|mail)\b")
        )
    if operation == "peripheral.list":
        return (
            (
                _has(
                    folded,
                    r"\b(?:perifericos?|peripherals?|impresoras?|printers?|"
                    r"escaneres?|scanners?|teclados?|keyboards?|mouse|mice|usb)\b",
                )
                or _has(folded, _CONNECTED_INVENTORY)
            )
            and _has(
                folded,
                rf"\b(?:{_LIST}|muestra|show|cuales|which|what|que|tengo)\b",
            )
            and not _has(folded, r"\b(?:predeterminad[oa]|default|establece|set)\b")
        )
    if operation in {"notification.cancel.at", "notification.cancel.latest"}:
        return (
            _has(folded, r"\b(?:alarma|alarm|recordatorio|reminder)\b")
            and _has(
                folded,
                r"\b(?:cancela|cancelar|cancel|quita|quitar|remove|remueve|"
                r"elimina|eliminar|delete|borra|borrar|get rid of)\b",
            )
            and (
                _latest_notification_selector(folded)
                if operation == "notification.cancel.latest"
                else _has(folded, _CLOCK_TIME_SELECTOR)
            )
        )
    if operation == "notification.list.due":
        return _has(
            folded,
            r"\b(?:recordatorios?|reminders?|notificaciones?|notifications?|"
            r"avisos?|alerts?)\b|\bexpired\s+notes?\b",
        ) and _has(
            folded,
            rf"\b(?:{_LIST}|vencid[oa]s?|due|overdue|pendientes?|pending|"
            r"dismissed)\b",
        )
    if operation == "note.list":
        return (
            _note_inventory_object(folded)
            and _has(
                folded,
                rf"\b(?:{_LIST}|indice|index|inventario|inventory|"
                r"completo|complete|privad[oa]s?|private|local)\b",
            )
            and not _has(
                folded,
                r"\b(?:expired|overdue|due|vencid[oa]s?|fuera\s+de\s+plazo)\b",
            )
        )
    if operation == "routine.phrase.create":
        return (
            _has(folded, r"\b(?:rutina|routine|frase|phrase|al oir|when you hear)\b")
            and _has(
                folded,
                r"\b(?:captura|screenshot|reproduce|play|pausa|pause|media)\b",
            )
            and not _has(
                folded, r"\b(?:habito|habit|marcalo|mark it|registre|registra)\b"
            )
        )
    if operation == "media.play.youtube":
        return (
            _has(folded, r"\byoutube\b")
            # MUSIC1553: the voseo and clitic forms («reproducí», «poné», «poneme»).
            and _has(folded, r"\b(?:reproduce|reproducir|reproduci|reproducime|play|pon|pone|poneme|ponme|poner)\b")
            and not _has(
                folded,
                r"\b(?:primer|primero|first|segundo|second|tercer|third|"
                r"resultado|result)\b",
            )
        )
    if operation == "ocr.read":
        return _has(
            folded,
            rf"\b(?:{_READ}|extrae|extraer|extract|run|turn|convert|convierte)\b",
        ) and _has(
            folded,
            r"\b(?:ocr|pantalla|screen|captura|screenshot|imagen|image|"
            r"texto|text|mensaje|message|writing|screenwriting|"
            r"characters?|caracteres?)\b",
        )
    if operation == "system.power":
        return _has(
            folded,
            r"\b(?:equipo|pc|compu|computador(?:a)?|computer|maquina|machine|"
            r"windows)\b",
        ) and not _has(
            folded,
            r"\b(?:telefono|movil|celular|phone|smartphone|tablet|iphone)\b",
        )
    if operation == "system.process.terminate.named":
        return _has(
            folded,
            r"\b(?:forzar|force|mata|matar|kill|termina|terminar|terminate|"
            r"cierra|cerrar|close)\b",
        ) and _has(
            folded,
            r"\b(?:proceso|process|aplicacion|application|app|programa|program)\b",
        )
    if operation == "task.create":
        return _has(
            folded,
            r"\b(?:tarea|task|to-do|todo|pendiente)\b",
        ) and _has(
            folded,
            r"\b(?:crea|crear|create|anade|agrega|agregame|add|nueva|new)\b",
        )
    if operation == "task.complete":
        return _has(folded, r"\b(?:tarea|task|to-do|todo)\b") and _has(
            folded,
            r"\b(?:completa|completar|complete|termina|terminada|terminado|"
            r"finish|finished|marca|mark)\b",
        )
    if operation == "reminder.delete":
        return _exact_local_reminder_title(folded) is not None
    if operation == "streaming.navigate":
        return (
            _has(
                folded,
                rf"\b(?:{_OPEN}|navega|navigate|reproduce|play|ver|watch)\b",
            )
            and _has(
                folded,
                r"\b(?:youtube|netflix|prime video|primevideo|streaming|"
                r"pelicula|movie|serie|show|video)\b|https?://",
            )
            and not _has(folded, r"\b(?:como|how)\b")
        )
    if operation == "streaming.play.named":
        return (
            _has(folded, r"\bnetflix\b")
            and _has(
                folded,
                r"\b(?:reproduce|play|pon|busca|find|encuentra|encuentras|"
                r"arranca|arrancala|start)\b",
            )
            and not _has(folded, r"\b(?:como|how|tutorial|ejemplo|example)\b")
        )
    if operation == "package.install.prepare":
        return (
            _spoken_package_id(folded) is not None
            and _has(
                folded,
                r"\b(?:prepara|preparado|prepare|resolve|instalacion|installation|"
                r"instalar|install|paquete|package|staged|tied|alista(?:lo|la)?)\b",
            )
            and not _has(folded, r"https?://|\b(?:juego|game|steam)\b")
        )
    if operation == "office.document.create":
        return (
            _has(
                folded,
                r"\b(?:documento|document|word|excel|hoja de calculo|"
                r"spreadsheet)\b",
            )
            and _has(
                folded,
                r"\b(?:crea|crear|creame|create|nuevo|new|blanco|blank)\b",
            )
            and not _has(
                folded,
                r"\b(?:powerpoint|presentacion|presentation|"
                r"diapositivas?|slides?)\b",
            )
            and not _has(
                folded,
                r"\b(?:convierte|convertir|convierteme|convert|pdf)\b",
            )
        )
    if operation == "media.seek.relative":
        return _has(
            folded,
            r"\b(?:adelanta|atrasa|retrocede|rewind|forward|jump|skip|seek)\b",
        ) and not _has(
            folded,
            r"\b(?:edita|editar|editame|edit|recorta|trim|corta|cut|"
            r"quita|quitar|quitale)\b",
        )
    if operation in {"game.install.cancel.active", "game.install.cancel"}:
        return (
            _has(folded, r"\b(?:steam|juego|game)\b")
            and (
                _has(
                    folded,
                    r"\b(?:cancela|cancelar|cancel|stop|detener|detene)\b",
                )
                or (
                    _has(folded, r"\bpara\b")
                    and _has(
                        folded,
                        r"\b(?:descarga|download|instalacion|install)\b",
                    )
                )
            )
            and not _has(folded, r"\b(?:torrent|series)\b")
        )
    if operation == "clipboard.write.text":
        return _has(folded, r"\b(?:portapapeles|clipboard)\b") and _has(
            folded,
            r"\b(?:copia|copiar|copy|escribe|write|pon|put|guarda|save|"
            r"reemplaza|replace|establece|set)\b",
        )
    if operation == "window.move":
        return (
            _has(folded, r"\b(?:mueve|mover|move|arrastra|drag)\b")
            and _has(folded, r"\b(?:ventana|window)\b")
            and not _has(folded, r"\b(?:archivo|file|carpeta|folder)\b")
        )
    if operation == "system.time":
        # A nominal clock/calendar query is still compatible with this domain.
        # The contextual policy selects the operation; this one-sided veto must
        # not require the person to repeat a verb in an elliptical follow-up.
        # A qualified date (an event, person or historical date) is not covered.
        return _nominal_datetime_query(folded) or any(
            _direct_current_time_request(clause)
            for clause in _request_clauses(folded)
        )
    if operation == "system.status":
        request = _strip_request_envelope(folded)
        # «y disco?», «Y espacio? cuánto espacio tengo»: a nominal machine
        # scope with no other verb is the same speech act as «y la fecha?»
        # for the clock (SYSTEM1175/001, /002). Only a scope word, optionally
        # preceded by y/and and an article, and optionally followed by the
        # how-much question on the same scope.
        nominal_scope = re.fullmatch(
            r"(?:(?:y|and)\s+)?(?:(?:el|la|mi|the|my)\s+)?"
            r"(?:disco|disk|espacio|space|bateria|battery|ram|memoria|memory|cpu|gpu)"
            r"[\s?!.]*(?:(?:cuanto|cuanta|how\s+much)\s+(?:espacio|space|ram|memoria|memory)"
            r"\s+(?:tengo|queda|hay|libre|do\s+i\s+have|is\s+left)[\s?!.]*)?",
            request,
        ) is not None
        return (nominal_scope or _is_direct_request(request)) and _system_status_domain(request)
    if operation in {"system.settings.adjust", "system.settings.status"}:
        return _has(
            folded,
            r"\b(?:brillo|brightness|luz\s+de\s+la\s+pantalla|"
            r"screen\s+(?:light|brightness)|how\s+bright)\b",
        )
    if operation == "system.settings.set":
        return _has(
            folded,
            r"\b(?:brillo|brightness|luz nocturna|night light|"
            r"no molestar|do not disturb|dnd)\b",
        )
    if operation == "system.process.list":
        return _process_list_domain(folded)
    if operation == "network.status":
        return _network_status_domain(folded)
    if operation in {
        "wifi.connect.named",
        "wifi.disconnect",
        "wifi.ensure.connected",
        "wifi.profile.list",
        "wifi.radio.set",
        "wifi.radio.status",
        "wifi.scan",
        "wifi.status",
    }:
        wifi_domain = _has(
            folded,
            r"\b(?:wi[\s-]?fi|red\s+inalambrica|wireless)\b",
        )
        if operation == "wifi.scan":
            # «qué redes hay» names the domain through «redes» alone.
            return _wifi_scan_question(folded)
        if operation == "wifi.radio.set":
            return wifi_domain and wifi_radio_set_request(folded) is not None
        if operation == "wifi.radio.status":
            return wifi_domain
        if not wifi_domain:
            return False
        if operation == "wifi.disconnect":
            # "drop the wireless connection" names the domain and the
            # disconnect; a closed verb list that omitted "drop" was the
            # whitelist-absence defect. Domain named is enough here.
            return True
        if operation == "wifi.profile.list":
            return _has(folded, r"\b(?:perfiles?|profiles?)\b") and _has(
                folded,
                rf"\b(?:{_LIST}|guardad[oa]s?|saved)\b",
            )
        if operation == "wifi.status":
            # «decime si el wifi está prendido» and «qué onda con el wifi» ask
            # for the same reading as «estado del wifi»; without these words the
            # gate withdrew wifi.status and the person got a confirmation
            # question instead of the observation (NETWORK1161/003, /004).
            return _has(
                folded,
                r"\b(?:estado|status|conectad[oa]|connected|como|how|which|cual|"
                r"pegad[oa]|a\s+que|prendid[oa]|encendid[oa]|apagad[oa]|activ[oa]|"
                r"onda|on|off|working)\b",
            )
        return _has(
            folded,
            r"\b(?:conecta|conectar|conectame|conectate|connect|cambia|change|enciende|turn\s+on)\b",
        )
    if operation == "memory.status":
        return _has(
            folded,
            r"\b(?:memoria|memory|recuerdos?)\b.{0,40}"
            r"\b(?:local|locales|baxy|asistente|assistant)\b|"
            r"\b(?:baxy|asistente|assistant|local|tus)\b.{0,40}"
            r"\b(?:memoria|memory|recuerdos?)\b",
        ) and not _has(
            folded,
            r"\b(?:ram|uso|usage|libre|free|sistema|system)\b",
        )
    if operation == "audio.mute":
        return _audio_mute_domain(folded)
    if operation in {
        "audio.status",
        "audio.volume",
        "audio.volume.adjust",
    }:
        return _volume_domain(folded)
    if operation == "notification.schedule":
        return _has(
            folded,
            (
                r"\b(?:notificacion(?:es)?|notifications?|avisa(?:me)?|"
                r"avisame|notify|recuerda(?:me)?|recuerdame|remind|"
                r"recordatorios?|reminders?|alarmas?|alarms?|timers?|"
                r"temporizadores?|despiertame|despertame|levantame|"
                r"wake\s+me(?:\s+up)?)\b"
            ),
        ) or _count_down_request(folded)
    if operation == "network.ip.list":
        # Without a rule the proposal was vetoed into a confirmation
        # (NETWORK1161/006-008). An IP is named as such.
        return _ip_list_request(folded) or _has(
            folded, r"\b(?:ip|ips|direccion(?:es)?\s+ip|ip\s+address(?:es)?)\b"
        )
    if operation == "reminder.resolve.exact":
        return _nominal_reminder_lookup_title(folded) is not None
    if operation in {"message.recipient.resolve", "message.send"}:
        # A bare "manda"/"send" grounded this family, so any errand that shares
        # the verb -- a parcel, a bouquet, a box -- could be answered by sending
        # a chat message instead. Excluding physical nouns one by one never
        # terminates: "package" was blocked and "ramo de rosas" walked straight
        # through. Require a positive message signal instead, which is a closed
        # set: a channel, a message noun, a speech act, or a verb carrying the
        # content to be said.
        names_a_message = _has(
            folded,
            r"\b(?:mensaje|mensajes|message|messages|texto|text|"
            r"whatsapp|wsp|discord|telegram|signal|sms|"
            r"correo|email|e-mail|mail|chat)\b",
        )
        speech_act = _has(
            folded,
            r"\b(?:dile|decile|diles|digale|tell|escribele|escribeles|"
            r"write\s+to|responde|respondele|reply|avisale|avisales)\b",
        )
        carries_spoken_content = _has(
            folded,
            r"\b(?:manda|mandale|mandales|envia|enviale|enviales|send)\b"
            r"[^.!?]{0,80}\bque\b",
        )
        # A document can legitimately be sent to a person: "envia el informe a
        # Lucas" is a message with an attachment, not an errand. Digital
        # artifacts stay a closed set, unlike physical goods.
        sends_a_digital_artifact = _has(
            folded,
            r"\b(?:informe|informes|reporte|reportes|report|reports|"
            r"documento|documentos|document|documents|archivo|archivos|"
            r"file|files|pdf|foto|fotos|photo|photos|imagen|imagenes|image|"
            r"images|captura|screenshot|enlace|enlaces|link|links|"
            r"resumen|resumenes|summary|nota|notas|note|notes)\b",
        )
        return (
            names_a_message
            or speech_act
            or carries_spoken_content
            or sends_a_digital_artifact
        )
    if operation == "routine.list":
        return _has(
            folded,
            r"\b(?:rutinas?|routines?|automations?|automatizaciones?|"
            r"secuencias?\s+automaticas?|automatic\s+sequences?)\b",
        ) and _has(
            folded,
            rf"\b(?:{_LIST}|enumera|enumerate|muestra|show|inventario|inventory|"
            r"guardad[oa]s?|saved|stored|disponibles?|available|"
            r"configurad[oa]s?|configured|repeat|repetir|habitual)\b",
        )
    if operation == "system.application.crash.diagnose":
        return _has(
            folded,
            r"\b(?:fallos?|errores?|bloqueos?|cierres?\s+inesperados?|"
            r"crash(?:es|ed|ing)?|failures?|faults?|application\s+errors?|"
            r"eventos?\s+de\s+error|error\s+events?)\b",
        ) and _has(
            folded,
            r"\b(?:aplicaciones?|applications?|apps?|programas?|programs?|"
            r"windows|registro\s+de\s+eventos|event\s+log)\b",
        )
    if operation.startswith("capture."):
        return (
            _has(
                folded,
                (
                    r"\b(?:captura de pantalla|captura (?:de )?(?:la )?ventana|"
                    r"captura de (?:toda )?la pantalla|"
                    r"captura (?:solamente |solo )?(?:de )?(?:la )?ventana|"
                    r"capture (?:only )?(?:the )?(?:active )?window|"
                    r"captura (?:de )?(?:el )?escritorio|capture (?:the )?desktop|"
                    r"pantallazo|screenshot|screen capture|window capture)\b"
                ),
            )
            or (
                _has(
                    folded,
                    r"\bsnapchat\b.{0,48}\bhow\s+desktop\s+looks\b",
                )
            )
            or (
                _has(folded, r"\bsabe\s+en\s+imagen\b")
                and _has(folded, r"\b(?:display|screen|pantalla|escritorio)\b")
            )
            or (_has(folded, r"\b(?:captura|capture)\b") and _has(folded, r"\bocr\b"))
        )
    if operation in {"browser.page.read", "browser.control"}:
        return _browser_page_domain(folded)
    if operation == "filesystem.folder.open":
        return _has(
            folded,
            r"\b(?:carpeta|folder|directorio|directory|escritorio|desktop|"
            r"documentos|documents|descargas|downloads|imagenes|pictures|"
            r"fotos|photos)\b",
        ) and not _has(folded, r"\b(?:archivo|file)\b")
    if operation == "filesystem.move":
        return (
            _has(folded, r"\b(?:mueve|mover|move|arrastra|drag)\b")
            and _has(folded, r"\b(?:archivo|file|carpeta|folder|ruta|path)\b")
            and not _has(folded, r"\b(?:ventana|window)\b")
        )
    if operation == "filesystem.file.open.latest":
        return _has(
            folded,
            r"\b(?:archivo|file)\b",
        ) and _has(
            folded,
            r"\b(?:reciente|latest|last|ultimo|ultima|newest)\b",
        )
    if operation == "filesystem.known.duplicates":
        return _has(
            folded,
            r"\b(?:archivos?|files?|documentos?|documents?|descargas|downloads?)\b",
        ) and _has(folded, _DUPLICATE_FILES)
    if operation == "filesystem.known.search":
        return (
            not _has(
                folded,
                r"\b(?:instala|instalar|install|installation|alista(?:lo|la)?|"
                r"prepare|prepara|preparado|ready|staged|tied)\b",
            )
            and not _has(folded, _DUPLICATE_FILES)
            and _has(
                folded,
                rf"\b(?:{_SEARCH}|locate|ubica|ubicar|find)\b|"
                r"\ba\s+ver\s+si\s+fin\b",
            )
            and _has(
                folded,
                r"\b(?:archivos?|files?|documentos?|documents?|descargas|downloads?|"
                r"imagenes?|pictures?|fotos?|photos?|carpetas?|folders?)\b",
            )
        )
    if operation == "filesystem.search":
        return (
            _has(
                folded,
                rf"\b(?:{_SEARCH}|locate|ubica|ubicar|find)\b",
            )
            and _has(
                folded,
                r"\b(?:archivos?|files?|documentos?|documents?|descargas|downloads?|"
                r"imagenes?|pictures?|fotos?|photos?|carpetas?|folders?|"
                r"escritorio|desktop|disco|drive|ruta|path)\b",
            )
            and not _has(
                folded,
                r"\b(?:web|website|internet|online|google|bing|public\s+api)\b",
            )
        )
    if operation == "task.search":
        return _has(folded, r"\b(?:tareas?|tasks?|to-?dos?)\b") and _has(
            folded,
            rf"\b(?:{_SEARCH}|find|locate|ubica|ubicar|muestra|show)\b",
        )
    if operation == "notification.diagnose":
        return _has(
            folded,
            r"\b(?:alarmas?|alarms?|notificaciones?|notifications?|"
            r"recordatorios?|reminders?|avisos?|alerts?)\b",
        ) and _has(
            folded,
            r"\b(?:diagnostica|diagnose|comprueba|check|revisa|review|"
            r"esta|estan|is|are|hay|there)\b",
        )
    if operation == "clipboard.copy":
        return _clipboard_copy_domain(folded)
    if operation == "clipboard.read.text":
        return (
            _has(folded, r"\b(?:portapapeles|clipboard)\b")
            or _has(
                folded,
                r"\b(?:texto|text)\b.{0,32}\b(?:list[oa]\s+para\s+pegar|"
                r"ready\s+(?:para|to)\s+(?:be\s+)?paste[d]?)\b",
            )
            or _has(
                folded,
                r"\btext\s+fragment\b.{0,40}\b(?:copied|capid)\b",
            )
            or _has(
                folded,
                r"^(?:what\s+did\s+i\s+copy|last\s+(?:thing\s+)?(?:i\s+)?copied|"
                r"que\s+(?:fue\s+lo\s+que\s+)?(?:copie|copié)\s+"
                r"(?:ultimo|ayer|recien|last))\b",
            )
        )
    if operation == "email.latest.read":
        return _latest_email_domain(folded)
    if operation == "media.status":
        return (
            _has(folded, r"\b(?:musica|music|cancion|song|media|multimedia)\b")
            and _has(
                folded,
                r"\b(?:sonando|playing|reproduciendo|playback|estado|status|"
                r"actual|current|sesion|session)\b",
            )
            or _has(
                folded,
                r"\b(?:que|what)\b.{0,40}\b(?:reproduciendo|playing)\b|"
                r"\bwhat(?:'s|\s+is)\s+playing\b",
            )
            or (
                _has(folded, r"\b(?:titulo|title|artista|artist|pista|track)\b")
                and _has(folded, r"\b(?:sonando|reproduciendo|playing)\b")
            )
        ) and not _has(
            folded,
            r"\b(?:netflix|youtube|spotify)\b|"
            r"\b(?:en|inside)\s+(?:mi|my)\s+(?:cabeza|mente|head|mind)\b",
        )
    if operation in {"media.play.exact", "media.play.query"}:
        return _media_play_domain(folded)
    if operation == "vision.describe":
        return (
            _has(
                folded,
                r"\b(?:pantalla|screen|captura|screenshot|imagen|image|"
                r"foto|photo|visual|escena|scene)\b",
            )
            and _has(
                folded,
                r"\b(?:describe|describeme|describe it|mira|look|"
                r"que hay|what is|what's|que se ve|que aparece|"
                r"what appears|ves|visible)\b",
            )
            and not _has(
                folded,
                r"\b(?:configuracion|settings|activa|activar|enable|"
                r"graba|grabar|record|recording|camara|camera)\b",
            )
        )
    if operation == "window.minimize.all":
        return minimize_all_request(folded)
    if operation == "window.close.all":
        return close_all_request(folded)
    if operation == "document.pdf.read":
        return _pdf_summary_request(folded) is not None
    if operation == "audio.app.volume.adjust":
        return app_volume_request(folded, application_names) is not None
    if operation == "window.snap":
        return _authenticated_application_snap_target(folded, application_names) is not None
    if operation in {
        "window.active",
        "window.focus",
        "window.maximize",
        "window.minimize",
        "window.move",
        "window.resize",
        "window.restore",
    }:
        return _window_domain(folded) or (operation == "window.active" and deictic_close_request(folded))
    if operation == "window.resolve":
        return (
            _authenticated_application_snap_target(folded, application_names) is not None
            or _authenticated_application_close_target(folded, application_names) is not None
            or _authenticated_application_focus_target(folded, application_names) is not None
            or conditional_open_pause_app(folded, application_names) is not None
            or window_inventory_arguments(folded) is not None or _window_domain(folded)
            or _has(folded, r"\b(?:aplicacion|application|proceso|process)\b")
        )
    return None


def confident_non_target_language(text: str) -> str | None:
    """Identify only high-precision Portuguese, French, or Italian cues.

    BAXY's accepted natural-language surface is Spanish, English, and their
    ordinary code-switching. This is intentionally an abstaining detector:
    shared Romance words never suffice, and named entities do not count.
    """

    folded = _fold(text).strip(" ?!.,")
    if _has(
        folded,
        # ``bota`` is ordinary Latin American Spanish -- "bota las boxes viejas
        # al recycling" is spanglish, not Portuguese -- so it only counts with a
        # Portuguese article behind it. A shared Romance word never suffices.
        r"\b(?:pra|cento|tela|loja|faz|mexer|tudo|aberto|regista|fiz|hoje)\b|"
        r"\bbota\s+[oa]\b|\bconecta\s+no\b|"
        r"\bfecha\s+tudo\b|\bde\s+novo\b|\barea\s+de\s+trabalho\b",
    ):
        return "pt"
    # «abre a calculadora» (owner review H0497): a Spanish request with a
    # dropped «l», not Portuguese, when the article is followed by a known
    # application name shared by both surfaces. «abre o bloco de notas» still
    # reads as Portuguese because ``bloco`` is not in that vocabulary.
    if _has(folded, r"\b(?:abre|minimiza)\s+[oa]\b") and not _has(
        folded,
        rf"\b(?:abre|minimiza)\s+[oa]\s+{_KNOWN_APPLICATION}\b",
    ):
        return "pt"
    if _has(
        folded,
        r"\b(?:augmente|fenetre|affiche|autres)\b|\bpour\s+cent\b|"
        r"\bpar\s+dessus\b",
    ):
        return "fr"
    if _has(
        folded,
        r"\b(?:apri|scrivi|salvala|finestra|spesa)\b|"
        r"\bblocco\s+note\b|\bfai\s+partire\b",
    ):
        return "it"
    return None


def effect_request_is_authoritative(text: str) -> bool:
    """Return whether text can authorize a present-tense computer effect."""

    folded = _fold(text)
    return (
        confident_non_target_language(text) is None
        and not explicit_non_action_frame(text)
        and _is_direct_request(folded)
        and not _is_past_or_hypothetical_state(folded)
        and not _is_meta_or_tool_denial(folded)
        and not _has_contradictory_correction(folded)
        and not _future_request_announcement(folded)
    )


def _future_request_announcement(folded: str) -> bool:
    """«Si mañana necesito X, te pediré que cierres…» announces a request to come.

    Nothing is asked now: a conditional opening followed by a first-person
    promise to ask later is conversation, not an effect and not an unsupported
    deferral (CLOSE1219-1223 boundary answered «no puedo cerrar ventanas»).
    """

    return _has(
        folded,
        r"^[¿?¡!\s]*(?:si|if|cuando|when|en\s+caso\s+de\s+que)\b.{0,160}"
        r"\b(?:te\s+(?:lo\s+)?(?:pedire|pediria|voy\s+a\s+pedir|dire|diria|avisare|avisaria)|"
        r"i(?:'ll|\s+will|\s+would|\s+might)\s+(?:ask|tell|let)\s+you)\b",
    )


def unsupported_effect_demonstration_request(text: str) -> bool:
    """Recognize a requested demonstration without granting effect authority."""

    return _has(
        _fold(text),
        r"^(?:antes de seguir\s+)?quiero ver como\b.{0,160}"
        r"\b(?:pones|abres|reproduces|usas|haces)\b",
    )


# The two frame word classes are generated from cognate groups instead of
# hand-listed, and this is the third design of them because the first two kept
# losing a word at a time. R23 carried Spanish ``indicacion`` with no entry at
# all and a whole Spanish cell fell to 23,5 %. R26 then carried English
# ``petition`` while Spanish ``peticion`` was already present, and 18 of its 20
# failures were that single word. Patching a noun per seal is a treadmill, so
# the class is stated as **pairs**: a noun cannot enter on one side of the
# language border without its counterpart on the other, and a test compares
# this module against the C# parser so the two borders cannot drift.
#
# ``tarea``/``task``/``recado``/``nota``/``recordatorio`` are deliberately NOT
# instruction nouns even though they read like ones. They name catalog objects,
# and "crea una tarea en el equipo: comprar pan" would be stripped down to
# "comprar pan", destroying the very request it was meant to unwrap.
INSTRUCTION_NOUN_COGNATES: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (("orden", "ordenes"), ("order", "orders")),
    (("instruccion", "instrucciones"), ("instruction", "instructions")),
    (("indicacion", "indicaciones"), ("direction", "directions")),
    (("directriz", "directrices"), ("directive", "directives")),
    (("consigna", "consignas"), ("command", "commands")),
    (("mandato", "mandatos"), ("mandate", "mandates")),
    (("encargo", "encargos"), ("errand", "errands")),
    (("encomienda", "encomiendas"), ("assignment", "assignments")),
    (("solicitud", "solicitudes"), ("request", "requests")),
    (("peticion", "peticiones"), ("petition", "petitions")),
    (("pedido", "pedidos"), ("order", "orders")),
    (("disposicion", "disposiciones"), ("provision", "provisions")),
)
# An English member may repeat one another pair already contributes -- several
# Spanish words for a computer share one English word. What the structure
# forbids is a group with an empty side, which is how ``petition`` went missing.
MACHINE_NOUN_COGNATES: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (("equipo", "equipos"), ("machine", "machines")),
    (("maquina", "maquinas"), ("machine", "machines")),
    (("computador", "computadores"), ("computer", "computers")),
    (("computadora", "computadoras"), ("computer", "computers")),
    # Peninsular Spanish. Leaving it out meant the frame was never stripped for
    # those speakers at all.
    (("ordenador", "ordenadores"), ("computer", "computers")),
    (("portatil", "portatiles"), ("laptop", "laptops")),
    (("pc", "pcs"), ("pc", "pcs")),
)


def _noun_alternation(
    cognates: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...],
) -> str:
    """Flatten cognate groups into one regex alternation, longest first."""

    words = sorted(
        {word for group in cognates for side in group for word in side},
        key=lambda value: (-len(value), value),
    )
    return "|".join(words)


_INSTRUCTION_NOUNS = _noun_alternation(INSTRUCTION_NOUN_COGNATES)
_MACHINE_NOUNS = _noun_alternation(MACHINE_NOUN_COGNATES)


# A frame that explicitly *denies* an instruction -- "esto no es una directriz
# para la computadora, dime nomas: ..." -- is the mirror of the instruction
# frame, and it must stay in place on the authority path: removing it there is
# exactly how an explicit request for no action would become an action.
#
# But it also displaces the content act from the front of the sentence, and the
# patterns below are anchored to ``^``. R25 lost five turns that way: the body
# asked to rewrite or translate a sentence that happened to *quote* an order,
# the anchor missed because the frame sat in front of it, and the turn drew a
# clarification instead of an answer. Removing the frame here is one-sided --
# it can only ever move a turn toward conversation, never toward an effect --
# because a denial of instruction is evidence for conversation.
#
# It reads its two noun classes from the same cognate groups as the positive
# frame, so the mirror can never fall out of step with what it mirrors.
_EXPLICIT_NO_ACTION_INSTRUCTION_FRAME = (
    r"^(?:baxy\s*[,;:]?\s*)?"
    r"(?=[^:]{0,110}\b(?:no|not|sin|without|s[oó]lo|solo|only|nada|"
    r"ning[uú]n|ninguna|ninguno|tampoco|nunca|jam[aá]s|neither|none|never)\b)"
    rf"(?=[^:]{{0,110}}\b(?:{_INSTRUCTION_NOUNS})\b)"
    rf"(?=[^:]{{0,110}}\b(?:{_MACHINE_NOUNS})\b)"
    r"[^:]{1,110}:\s*"
)


def _strip_explicit_no_action_frame(folded: str) -> str:
    """Remove a frame that denies an instruction, for content recognition only.

    Never call this on the authority path. It is safe here and nowhere else,
    because dropping a denial can only make a turn look *more* like
    conversation, and the content-act patterns it feeds are narrow: a request
    that survives the frame -- "no es una orden para el pc, dime nomas: envia
    el correo a Ana" -- still matches none of them.
    """

    return re.sub(_EXPLICIT_NO_ACTION_INSTRUCTION_FRAME, "", folded).strip()


def conversation_only_content_request(text: str) -> bool:
    """Recognize self-contained content work with no external effect.

    These forms ask the model to reason or draft inside the conversation.  A
    quoted imperative (for example, ``send the report``) remains content and
    never becomes authority to perform that imperative.  The patterns are
    anchored to explicit content acts so merely mentioning a catalog domain
    such as Wi-Fi, Steam, a window, or the clipboard cannot close a turn.
    """

    folded = _strip_explicit_no_action_frame(
        _strip_request_envelope(_fold(text)).strip()
    )
    return _has(
        folded,
        r"^(?:please\s+)?(?:write|draft) me (?:an?|un) (?:email|mail|correo) "
        r"(?:that|saying|about)\b|"
        r"^(?:por\s+favor\s+)?redactame\s+(?:un\s+)?(?:correo|email|mail)\b|"
        r"^(?:reescribe|reformula|refrasea|redacta|rewrite|rephrase)\b.{0,160}"
        r"\b(?:frase|oracion|sentence|phrase|texto|text)\b|"
        r"^(?:calcula|calculate|work\s+out)\b.{1,160}$|"
        r"^(?:dame|give\s+me|write|draft)\b.{0,96}"
        r"\b(?:receta|recipe)\b|"
        r"^dame\s+a\s+currir\s+ese\s+pi\s+para\b.{1,96}$|"
        r"^(?:inventa|crea|escribe|make\s+up|write)\b.{0,96}"
        r"\b(?:adivinanza|riddle|poema|poem|cuento|story)\b|"
        r"^(?:escribe|write)\b.{0,64}\b(?:lista|checklist)\b.{0,64}"
        r"\b(?:teorica|theoretical)\b|"
        r"^(?:escribe|write)\b.{0,64}\b(?:teorica|theoretical)\b.{0,64}"
        r"\b(?:lista|checklist)\b|"
        r"^(?:simula|role[- ]?play)\b.{0,128}\b(?:conversacion|conversation)\b"
        r".{0,96}\b(?:no\s+envies\s+nada|send\s+nothing)\b|"
        r"^(?:compara|comparar|compare)\b"
        r"(?![^\n]{0,192}\b(?:archivo|archivos|file|files|carpeta|folder|"
        r"documento|document|ruta|path)\b).{1,192}$|"
        r"^(?:\S+\s+){0,3}(?:story|cuento|historia)\b.{0,96}"
        r"\b(?:imaginari[oa]|imaginary)\b.{0,64}$|"
        r"^(?:compara|compare)\b.{0,160}"
        r"\b(?:en\s+teoria|in\s+theory|en\s+general|in\s+general|"
        r"sin\s+(?:consultar|revisar)\s+mis\s+datos|"
        r"without\s+(?:checking|consulting)\s+my\s+data|"
        r"sin\s+(?:check|checking)\s+my\s+data)\b|"
        r"^(?:traduce|translate)\b.{0,192}"
        r"\b(?:al|a|into)\s+(?:italiano|italian|ingles|english|espanol|spanish)\b|"
        r"^(?:pon|put)\s+into\s+(?:english|ingles|spanish|espanol|italian|italiano)"
        r"\b.{0,160}\b(?:frase|phrase|sentence)\b|"
        r"^(?:pon|put)\b.{0,32}\b(?:ingles|english)\b.{0,48}"
        r"\b(?:frase|phrase|sentence)\b.{1,128}$",
    )


_VISUAL_CONTENT_REQUEST = re.compile(
    r"^[\s¿?¡!]*(?:(?:oye|che|baxy)\s*,?\s+)?"
    r"(?:(?:tienes|tenes|tendras|tendrias|hay|tenis|do\s+you\s+have|got|have\s+you\s+got|"
    r"(?:me\s+)?(?:mandas|manda|mandame|mandame|envias|envia|enviame|pasas|pasa|pasame|muestras|muestra|muestrame|mostras|mostrame|das|da|dame|tiras|tirame)|"
    r"(?:can|could)\s+you\s+(?:send|show|give)(?:\s+me)?|send(?:\s+me)?|show(?:\s+me)?|give(?:\s+me)?)\s+"
    r"(?:(?:un|una|unos|unas|algun|alguna|algunos|algunas|el|la|los|las|a|an|any|some|the|me)\s+)*"
    r"(?:\w+\s+){0,2}?(?:meme|memes|imagen|imagenes|foto|fotos|gif|gifs|sticker|stickers|dibujo|dibujos|picture|pictures|image|images|photo|photos)\b"
    r".{0,40}$)"
)


_REASSURANCE_STATEMENT = re.compile(
    r"^[\s¿?¡!]*(?:(?:no|nunca)\s+(?:te|se)\s+preocup\w*|tranqui(?:lo|la|los|las)?\b|no\s+pasa\s+nada|"
    r"(?:don'?\s?t|dont|do\s+not)\s+worry|no\s+worries|it'?\s?s\s+(?:ok|okay|fine|alright)|esta\s+bien\s+si\b|todo\s+bien\s+si\b)"
)


def reassurance_statement(text: str) -> bool:
    """CONVERSATION1343 H0059 «NO te preocupes si se abrio steam»: a reassurance, not a request."""

    return _REASSURANCE_STATEMENT.match(_strip_request_envelope(_fold(text)).strip()) is not None


_FIRST_PERSON_PREFERENCE = re.compile(
    r"(?:me\s+(?:gusta|gustan|encanta|encantan|fascina|fascinan)|"
    r"prefiero|adoro|amo|odio|detesto|no\s+me\s+gusta|no\s+me\s+gustan|"
    r"i\s+(?:like|love|prefer|hate|enjoy|dislike))\s+"
    r"(?P<thing>(?!(?:que|si|cuando|porque)\b)[a-z][a-z0-9 '\-]{1,80})[\s.!?]*",
    re.IGNORECASE,
)
_PREFERENCE_REQUEST_HEAD = re.compile(
    r"\b(?:que|abre|abri|abris|pone|pon|poneme|pongas|abras|busca|buscame|cierra|"
    r"lanza|inicia|reproduce|manda|envia|escribe|crea|guarda|recuerda|recorda|"
    r"open|play|search|send|close|save|remember|remind)\b"
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
# KNOWLEDGE1505: the engine returns the public page of a bare, well-known name
# (its Wikipedia article or an encyclopedic page first); the names below are
# subjects verified against the engine's relevance rule on 2026-09-15, never
# replies. Many other common names returned unrelated pages that day.
_CURIOSITY_TOPICS_ES = (
    "Colibrí", "Luna", "Saturno", "Antártida", "Ornitorrinco", "Amazonas", "Pingüino", "Delfín",
    "Miel", "Chocolate", "Arcoíris", "Jirafa", "Koala", "Coliseo", "Titanic", "Neptuno", "Ballena",
    "Girasol", "Urano", "Plutón", "Abeja", "Mariposa", "Tortuga", "Cactus", "Microscopio", "Tsunami",
)
_CURIOSITY_TOPICS_EN = (
    "Moon", "Whale", "Jupiter", "Tsunami", "Titanic", "Koala", "Chocolate", "Cactus",
)


def curiosity_request(text: str) -> bool:
    """KNOWLEDGE1505 «decime una curiosidad», «contame algo», «estoy aburrido»: a curiosity with no topic."""

    return _CURIOSITY_REQUEST.match(_strip_request_envelope(_fold(text)).strip()) is not None


def curiosity_topic(text: str) -> str | None:
    """The public subject BAXY looks up for a curiosity request, or None.

    The topic is drawn at random from a list of well-known subjects in the
    language of the request; the answer is whatever the public page states."""

    if not curiosity_request(text):
        return None
    folded = _strip_request_envelope(_fold(text)).strip()
    english = re.match(r"^(?:baxy\s*[,:]?\s*)?(?:tell|give|i)\b", folded, re.IGNORECASE) is not None
    # The pick is stable for one request within the same hour, so every
    # reading of the turn (planning, verification) names the same subject.
    seed = hashlib.sha256(f"{folded}|{int(time.time() // 3600)}".encode("utf-8")).hexdigest()
    return random.Random(seed).choice(_CURIOSITY_TOPICS_EN if english else _CURIOSITY_TOPICS_ES)


def first_person_preference(text: str) -> str | None:
    """MEMORY1501/1503 H0174 «Me gusta tomar café.»: the thing a first-person taste names, or None.

    A taste or preference with nothing asked is a statement to acknowledge, not an order
    (MEMORY1245 asked where to go for coffee). No request verb, no «que» clause and no
    catalog head may follow the preference."""

    match = _FIRST_PERSON_PREFERENCE.fullmatch(_strip_request_envelope(_fold(text)))
    if match is None:
        return None
    thing = match.group("thing").strip()
    if _PREFERENCE_REQUEST_HEAD.search(thing) is not None:
        return None
    return thing


_VISUAL_CONTENT_NOUN = re.compile(
    r"\b(?P<noun>meme|memes|imagen|imagenes|foto|fotos|gif|gifs|sticker|stickers|dibujo|dibujos|picture|pictures|image|images|photo|photos)\b"
)


def visual_content_noun(text: str) -> str:
    """The visual noun asked for («meme», «foto»), for the boundary reply."""

    match = _VISUAL_CONTENT_NOUN.search(_fold(text))
    return match.group("noun") if match is not None else ""


def visual_content_request(text: str) -> bool:
    """CONVERSATION1150 H0069 «Tienes algun meme?»: memes and images cannot be shown here.

    A request to have, send or show visual content is answered as an honest
    boundary of this PC, never with a promised meme.
    """

    return _VISUAL_CONTENT_REQUEST.match(_strip_request_envelope(_fold(text)).strip()) is not None


def unsupported_live_machine_query(text: str) -> bool:
    """Recognize a live-machine question outside the observed status schema."""

    folded = _fold(text)
    return _has(
        folded,
        r"\b(?:hay algo mas que|que (?:otra cosa|proceso)|what else|which process)"
        r"\b.{0,100}\b(?:use|usa|uses|using|utilice|utiliza)\b.{0,40}\bgpu\b",
    )


def known_unsupported_effect_request(
    text: str,
    available_operations: Iterable[str],
) -> bool:
    """Close known missing variants only while no matching operation exists."""

    folded = _fold(text)
    available = frozenset(available_operations)
    contracts = (
        (
            _has(folded, r"\b(?:arrastra|drag)\b")
            and _has(folded, r"\b(?:archivo|file|carpeta|folder)\b")
            and _has(folded, r"\b(?:ventana|window)\b"),
            {"input.drag.drop", "filesystem.drag.drop"},
        ),
        (
            _has(folded, r"\b(?:habito|habit)\b")
            and _has(
                folded,
                r"\b(?:arma|armar|crea|crear|create|marca|marcar|mark|registra|register)\b",
            ),
            {"routine.habit.create", "routine.habit.mark"},
        ),
        (
            _has(folded, rf"\b{_OPEN}\b")
            and _has(folded, r"\b(?:archivo|file)\b")
            and not _has(folded, r"\b(?:ultimo|ultima|latest|reciente|newest)\b"),
            {"filesystem.file.open.named"},
        ),
        (
            _has(folded, r"\b(?:incognito|privad[ao]|private)\b")
            and _has(folded, r"\b(?:ventana|window|navegador|browser)\b"),
            {"browser.window.private.open"},
        ),
        (
            _has(folded, rf"\b{_OPEN}\b")
            and _has(folded, r"\b(?:configuracion|settings)\b")
            and _has(folded, r"\b(?:pantalla|display|screen)\b"),
            {"system.settings.display.open"},
        ),
        (
            _has(folded, r"\b(?:impresora|printer)\b")
            and _has(folded, r"\b(?:predeterminad[ao]|default)\b")
            and _has(folded, r"\b(?:pon|poner|establece|set|make)\b"),
            {"peripheral.default.set"},
        ),
        (
            _has(
                folded,
                r"^(?:get\s+me|i\s+(?:want|need)\s+to\s+get)\b",
            )
            and _has(
                folded,
                r"\b(?:american\s+express|visa|mastercard|credit\s+card|"
                r"debit\s+card|tarjeta|bizum|cash|efectivo)\b",
            )
            and not _has(folded, r"\b(?:game|juego|steam)\b"),
            {"commerce.product.purchase"},
        ),
        (
            # LIMITS1683 H0621 «multiplicá 6 por 7 en la calc», H0705 «Suma 2 más 2
            # en la Calculadora»: one control per confirmed click; no operation
            # evaluates an expression in the Calculator.
            _has(folded, r"\b(?:multiplica|multiplicar|multiplicame|suma|sumar|sumame|resta|restar|restame|divide|dividir|divideme|calcula|calcular|calculame|multiply|add|subtract|divide|calculate|compute)\b")
            and _has(folded, r"\b(?:calc|calculadora|calculator)\b"),
            {"calculator.expression.evaluate"},
        ),
        (
            # LIMITS1683 H0559 «Abre Steam y luego navega por la gui hasta
            # biblioteca», H0432 «Abre Epic Games y navega hasta la biblioteca»
            # were a known limit; since UI1731 the client's interface is walked
            # with input.visible.click (UIA, then OCR on the foreground window),
            # so this contract is inert while that operation exists.
            _has(folded, r"\b(?:navega|navegar|navegame|navigate)\b")
            and _has(folded, r"\b(?:steam|epic(?:\s+games)?|battle\.net|origin|uplay|gog|ubisoft\s+connect)\b")
            and _has(folded, r"\b(?:gui|interfaz|interface|biblioteca|library|tienda|store|menu|menus)\b"),
            {"input.visible.click"},
        ),
        (
            # LIMITS1683 H0302 «qué redes wifi hay»: saved profiles and the current
            # state are read; no operation scans the networks around the PC.
            _has(folded, r"\b(?:que|cuales|what|which)\s+redes(?:\s+(?:wifi|wi\s*fi|inalambricas))?\s+(?:hay|disponibles|cerca|detectas|ves|encontras)\b"
                         r"|\b(?:escanea|escanear|scan)\b.{0,24}\b(?:wifi|redes|networks)\b"
                         r"|\b(?:what|which)\s+(?:wifi\s+)?networks\s+(?:are\s+(?:there|available|nearby|around)|can\s+you\s+see|do\s+you\s+see)\b"),
            {"wifi.scan"},
        ),
        (
            # LIMITS1683 H0077 «descarga la imagen de portada de wikipedia.org y
            # guardala en el escritorio»: the browser navigates; no operation
            # downloads a file from the web.
            _has(folded, r"\b(?:descarga|descargar|descargame|baja|bajar|bajame|download)\b")
            and _has(folded, r"\b(?:imagen|imagenes|foto|fotos|image|images|picture|pictures|photo|photos|archivo|archivos|file|files|video|videos|pdf)\b")
            and not _has(folded, r"\b(?:steam|epic|juego|game)\b"),
            {"browser.download.file"},
        ),
        (
            # LIMITS1681 H0175 «en Discord apretá enter», H0566 «apretá enviar en
            # WhatsApp»: a control inside a messaging client is never pressed
            # by the product (the visible click works on its own windows).
            _has(folded, r"^[¿?¡!\s]*(?:(?:en|in|on)\s+(?:discord|whatsapp|teams|telegram|slack|skype|zoom|signal|messenger)[,]?\s+)?(?:apreta|apretale|pulsa|pulsale|presiona|presionale|dale\s+a|toca|clickea|click|press|hit)\s+"
                         r"(?:(?:la|el|the)\s+)?(?:tecla\s+|boton\s+(?:de\s+)?|key\s+|button\s+)?(?:enter|intro|return|enviar|send|escape|esc|espacio|space|tab)\b")
            and (_has(folded, r"^[¿?¡!\s]*(?:en|in|on)\s+(?:discord|whatsapp|teams|telegram|slack|skype|zoom|signal|messenger)\b") or _has(folded, r"\b(?:en|in|on)\s+(?:discord|whatsapp|teams|telegram|slack|skype|zoom|signal|messenger)[\s.!?]*$")),
            {"client.control.press"},
        ),
        (
            # LIMITS1681 H0107 «poneme el modo avión»: the radios are switched
            # one by one; no operation toggles airplane mode.
            _has(folded, r"\b(?:modo\s+avion|airplane\s+mode|flight\s+mode)\b")
            and _has(folded, r"\b(?:pon|pone|poneme|poner|activa|activame|activar|prende|prendeme|enciende|apaga|desactiva|quita|saca|turn\s+on|turn\s+off|enable|disable|switch|put|set)\b"),
            {"network.airplane.mode"},
        ),
        (
            # LIMITS1677 H0048 «ejecuta pytest», H0245 «ejecuta ls»: no operation
            # runs a shell command or a program by command line.
            _has(folded, r"^[¿?¡!\s]*(?:(?:por\s+favor|please)\s*[,;:]?\s*)?(?:ejecuta|ejecutame|corre|correme|run|execute|lanza|launch)\s+"
                         r"(?:(?:el|the|este|this|un|a)\s+)?(?:comando\s+|command\s+)?"
                         r"(?:pytest|ls|dir|cd|git|npm|npx|pip|pip3|python|python3|node|dotnet|cargo|make|cmd|powershell|bash|sh|"
                         r"\S+\.(?:py|sh|bat|ps1|cmd|exe\s+/)|comando|command)\b")
            and not _has(folded, r"\b(?:juego|game|steam|app|aplicacion|application|programa|program)\b"),
            {"shell.command.run"},
        ),
        (
            # LIMITS1677 H0635 «Puedes ver tu propio código y analizar si hay
            # alguna falla»: BAXY has no reading of its own source.
            _has(folded, r"\b(?:tu|tus|your)\s+(?:propio\s+|own\s+)?(?:codigo|code|fuente|source\s+code|programacion)\b")
            and _has(folded, r"\b(?:ver|leer|analizar|analiza|revisar|revisa|mirar|mira|examinar|examina|see|read|review|analy[sz]e|look|inspect|check)\b"),
            {"self.source.read"},
        ),
        (
            # LIMITS1677 H0444 «cerrá todas las pestañas de chrome»: since
            # BROWSER1841 «cerrá todas las pestañas» closes every open tab in the
            # product's own browser (browser.control close_all); a single-tab or
            # partial close still has no operation and stays a plain limit.
            _has(folded, r"\b(?:cierra|cerra|cerrar|cerrame|cierrame|close)\b")
            and _has(folded, r"\b(?:pestanas?|tabs?)\b")
            and browser_close_all_tabs_arguments(text) is None,
            {"browser.tab.close"},
        ),
        (
            # LIMITS1677 H0238/H0529 «minimizá todas las ventanas», H0658
            # «minimizá todo»: windows are minimized one at a time, never all.
            _has(folded, r"\b(?:minimiza|minimizar|minimizame|minimise|minimize)\b")
            and _has(folded, r"\b(?:todo|todas(?:\s+las)?(?:\s+ventanas)?|all(?:\s+(?:the|my))?(?:\s+windows)?|everything)\b")
            and not _has(folded, r"\b(?:pestanas?|tabs?|menos|except|excepto)\b"),
            {"window.minimize.all"},
        ),
        (
            # LIMITS1677 H0467 «cerrame todo», H0484 «cerrá todas las ventanas»
            # were a known limit; since CLOSEALL1733 (owner 2026-09-16: close
            # everything except Visual Studio Code) window.close.all exists and
            # this contract is inert.
            _has(folded, r"\b(?:cierra|cerra|cerrar|cerrame|cierrame|close)\s+(?:me\s+)?(?:todo|todas\s+las\s+ventanas|todas\s+las\s+apps|todas\s+las\s+aplicaciones|all\s+(?:the\s+|my\s+)?(?:windows|apps|applications)|everything)\b")
            and not _has(folded, r"\b(?:pestanas?|tabs?|menos|except|excepto|de\s+\w+$)\b"),
            {"window.close.all"},
        ),
        (
            # LIMITS1677 H0652 «subí el volumen de spotify»: the volume readers
            # act on the system endpoint; no operation sets one application's
            # volume.
            _has(folded, r"\b(?:volumen|volume)\s+(?:de|del|of)\s+(?:(?:la|el|the)\s+)?(?:app\s+)?(?:spotify|chrome|discord|youtube|steam|zoom|teams|vlc|firefox|opera|edge|whatsapp)\b"
                         r"|\b(?:spotify|chrome|discord|youtube|steam|zoom|teams|vlc|firefox|opera|edge|whatsapp)(?:\'s)?\s+volume\b"),
            {"audio.app.volume.adjust"},
        ),
        (
            # AGENDA1669 H0666 «resumime informe.pdf»: the text reader opens text
            # files; no operation reads or summarises a PDF.
            _has(folded, r"\b(?:resumi|resumime|resumeme|resume|resumir|resumen|summari[sz]e|summary|sum\s+up)\b")
            and _has(folded, r"\.pdf\b|\bpdfs?\b"),
            {"document.pdf.read"},
        ),
        (
            # LIMITS1665 H0459 «cambiá el fondo de pantalla a azul»: no operation
            # sets the desktop wallpaper.
            _has(folded, r"\b(?:fondo\s+de\s+(?:pantalla|escritorio)|wallpaper|papel\s+tapiz|desktop\s+background)\b")
            and _has(folded, r"\b(?:cambia|cambiar|cambiame|pon|pone|poneme|poner|establece|coloca|usa|change|set|put|use|make)\b"),
            {"desktop.wallpaper.set"},
        ),
        (
            # LIMITS1665 H0188 «Haz un powerpoint hablando de amor de 6
            # diapositivas»: no operation creates a slide deck.
            _has(folded, r"\b(?:powerpoint|power\s+point|presentacion(?:es)?|diapositivas?|slides?|slideshow|slide\s+deck)\b")
            and _has(folded, r"\b(?:haz|hace|haceme|hazme|crea|creame|crear|arma|armame|armar|genera|generame|generar|prepara|preparame|make|create|build|prepare|put\s+together)\b"),
            {"document.presentation.create"},
        ),
        (
            # LIMITS1665 H0306 «agregá a Juan a mis contactos», H0138 «guardá el
            # contacto de Lucía …»: no operation keeps an address book (the
            # owner ruled a phone number is not something to store on the PC).
            (
                _has(folded, r"\b(?:contactos?|contacts?|agenda\s+telefonica|address\s+book|libreta\s+de\s+direcciones)\b")
                and _has(folded, r"\b(?:agrega|agregar|agregame|anade|anadir|guarda|guardar|guardame|agenda|agendar|agendame|mete|meter|suma|sumar|add|save|store|put)\b")
            )
            or _has(folded, r"\b(?:agenda|agendame|guarda|guardame|anota|anotame|save|add)\s+(?:a\s+)?\w+\s+(?:con\s+el|with\s+the)\s+(?:numero|number|telefono|phone)\b"),
            {"contacts.add"},
        ),
        (
            # UI1659 H0290/H0636 «ve a Cotele en Discord» was a known limit; since
            # UI1735 the client is opened and the channel label clicked on its
            # interface (input.visible.click), so this contract is inert.
            client_navigation_target(folded) is not None,
            {"input.visible.click"},
        ),
    )
    return any(
        matched and not supported & available for matched, supported in contracts
    )


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


def resolve_explicit_clarification(
    text: str,
    available_operations: Iterable[str],
) -> str | None:
    """Return the single certain operation of an incomplete effect, if any."""

    intent = resolve_explicit_clarification_intent(text, available_operations)
    return (
        intent.operation if intent is not None and len(intent.operations) == 1 else None
    )


def _time_only_reminder_request(folded: str) -> bool:
    direct_clock = _has(
        folded,
        r"\b(?:recordatorio|reminder)\s+(?:para|for)\s+"
        r"(?:(?:las?|at)\s+)?(?:[0-9]|one|two|three|four|five|six|"
        r"seven|eight|nine|ten|eleven|twelve|una?|dos|tres|cuatro|"
        r"cinco|seis|siete|ocho|nueve|diez|once|doce)\b",
    )
    dated_clock = _has(
        folded,
        (
            r"\b(?:recordatorio|reminder)\s+(?:para|for)\s+"
            r"(?:hoy|today|manana|tomorrow|esta noche|tonight)"
            r"(?:\s+(?:a las?|at)\s+(?:las\s+)?"
            r"(?:[0-2]?\d|one|two|three|four|five|six|seven|eight|nine|"
            r"ten|eleven|twelve|una?|dos|tres|cuatro|cinco|seis|siete|"
            r"ocho|nueve|diez|once|doce)(?::[0-5]\d)?"
            r"\s*(?:a\.?\s*m\.?|p\.?\s*m\.?)?)?"
            r"[\s.!?]*$"
        ),
    )
    return direct_clock or dated_clock


_TEMPORAL_NUMBER_WORDS = {
    "one": 1,
    "un": 1,
    "una": 1,
    "uno": 1,
    "two": 2,
    "dos": 2,
    "three": 3,
    "tres": 3,
    "four": 4,
    "cuatro": 4,
    "five": 5,
    "cinco": 5,
    "six": 6,
    "seis": 6,
    "seven": 7,
    "siete": 7,
    "eight": 8,
    "ocho": 8,
    "nine": 9,
    "nueve": 9,
    "ten": 10,
    "diez": 10,
    "eleven": 11,
    "once": 11,
    "twelve": 12,
    "doce": 12,
    "fifteen": 15,
    "quince": 15,
    "twenty": 20,
    "veinte": 20,
    "thirty": 30,
    "treinta": 30,
    "forty five": 45,
    "cuarenta y cinco": 45,
    "sixty": 60,
    "sesenta": 60,
}
_TEMPORAL_NUMBER_PATTERN = (
    r"(?:[0-9]{1,3}|forty five|cuarenta y cinco|fifteen|quince|twenty|"
    r"veinte|thirty|treinta|sixty|sesenta|one|un|una|uno|two|dos|three|"
    r"tres|four|cuatro|five|cinco|six|seis|seven|siete|eight|ocho|nine|"
    r"nueve|ten|diez|eleven|once|twelve|doce)"
)
# One relative duration as people type it: «10 minutos», «2min», «2 h»,
# «media hora», «half an hour». Shared by every temporal reader so a compact
# form cannot pass one reader and fail the next (TIME1138, TIME1187).
_RELATIVE_DURATION_UNIT = r"(?:minutos?|minutes?|mins?|min|horas?|hours?|hrs?|h|dias?|days?)"
_RELATIVE_DURATION_PATTERN = (
    rf"(?:{_TEMPORAL_NUMBER_PATTERN}\s*{_RELATIVE_DURATION_UNIT}|media\s+hora|half\s+an?\s+hour)"
)
# «Dentro de doce minutos, recordame …» / «En 10 minutos avisame …»: the
# duration leads and the scheduling head follows. The preface is part of the
# same request, not a clause of its own (TIME1189/011).
_LEADING_DURATION_PREFACE = re.compile(
    rf"^[¿?¡!\s]*(?:en|in|dentro\s+de|within)\s+{_RELATIVE_DURATION_PATTERN},?\s+"
    r"(?=(?:recuerdame|recuerdamelo|recordame|recordamelo|avisame|remind\s+me|"
    r"pon|poner|ponme|pone|poneme|pongame|programa|programame|schedule|set|"
    r"despiertame|despertame|levantame|wake\s+me)\b)"
)


def _without_leading_duration_preface(folded: str) -> str:
    """Read a scheduling request after its leading duration preface."""

    return _LEADING_DURATION_PREFACE.sub("", folded, count=1)


# «contá 10 minutos», «count down 4 minutes»: the count head names a timer only
# when a duration follows it at once, so «cuenta» (account) never qualifies.
_COUNT_DOWN_REQUEST = re.compile(
    rf"^[¿?¡!\s]*(?:conta|cuenta|contame|cuentame|count(?:\s+down)?)\s+{_RELATIVE_DURATION_PATTERN}\b"
)


def _count_down_request(folded: str) -> bool:
    """Recognize a bare countdown request that names its duration first."""

    return _COUNT_DOWN_REQUEST.match(_strip_request_envelope(folded)) is not None


# «cuál es mi ip», «what's my ip address», «decime qué dirección IP tiene esta
# compu»: the machine's own address, read from the catalog (NETWORK1161/1201).
_IP_LIST_REQUEST = re.compile(
    r"^[¿?¡!\s]*(?:(?:decime|dime|mostrame|muestrame|show\s+me|tell\s+me)\s+)?"
    r"(?:(?:cual|which|what)(?:\s+es|'s|s|\s+is)?\s+)?"
    r"(?:mi|my|la|the|tu|your)\s+(?:direccion\s+)?ip(?:\s+address)?"
    r"(?:\s+(?:actual|current|local|de\s+(?:esta|este)\s+(?:compu|computadora|equipo|pc|maquina)|of\s+this\s+(?:pc|computer|machine)))?"
    r"[\s?!.]*$"
    r"|^[¿?¡!\s]*(?:(?:decime|dime|show\s+me|tell\s+me)\s+)?(?:que|what)\s+(?:direccion\s+)?ip(?:\s+address)?\s+"
    r"(?:tengo|tiene\s+(?:esta|este|la|el)\s+(?:compu|computadora|equipo|pc|maquina)|do\s+i\s+have|does\s+this\s+(?:pc|computer|machine)\s+have)"
    r"[\s?!.]*$"
)


def _ip_list_request(folded: str) -> bool:
    """Recognize a request for this machine's own IP address."""

    return _IP_LIST_REQUEST.match(_strip_request_envelope(folded)) is not None


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
_FILE_CREATION_REQUEST = re.compile(
    r"^[¿?¡!\s]*(?:cre[aá]|crear|cre[aá]me|create|guard[aá]|guardar|escrib[eí]|escribir|write|save)(?:me)?\s+"
    r"(?:(?:un|una|a|the|el)\s+)?(?:archivo|fichero|file)(?:\s+(?:de\s+texto|txt|text))?"
    rf"(?:\s+(?:en|on|in|dentro\s+de|inside)\s+(?:(?:el|la|mi|my|the)\s+)?(?P<folder_a>{_KNOWN_FOLDER_WORDS}))?"
    r"\s+(?:llamad[oa]|named|called|con\s+(?:el\s+)?nombre)\s+(?P<name>\"[^\"]+\"|'[^']+'|\S+)"
    rf"(?:\s+(?:en|on|in|dentro\s+de|inside)\s+(?:(?:el|la|mi|my|the)\s+)?(?P<folder_b>{_KNOWN_FOLDER_WORDS}))?"
    r"\s+(?:que\s+diga|que\s+contenga|con\s+(?:el\s+)?(?:texto|contenido)|with\s+(?:the\s+)?(?:text|content)|containing|that\s+says|saying)\s+"
    r"(?P<content>.+?)\s*$",
    re.IGNORECASE,
)
_DIRECTORY_CREATION_REQUEST = re.compile(
    r"^[¿?¡!\s]*(?:cre[aá]|crear|cre[aá]me|create|haz|hac[eé]|hazme|make)(?:me)?\s+"
    r"(?:(?:una|un|a|the)\s+)?(?:carpeta|directorio|folder|directory)"
    rf"(?:\s+(?:en|on|in|dentro\s+de|inside)\s+(?:(?:el|la|mi|my|the)\s+)?(?P<folder_a>{_KNOWN_FOLDER_WORDS}))?"
    r"\s+(?:llamad[oa]|named|called|con\s+(?:el\s+)?nombre)\s+(?P<name>\"[^\"]+\"|'[^']+'|\S+?)"
    rf"(?:\s+(?:en|on|in|dentro\s+de|inside)\s+(?:(?:el|la|mi|my|the)\s+)?(?P<folder_b>{_KNOWN_FOLDER_WORDS}))?"
    r"[\s.!?]*$",
    re.IGNORECASE,
)


# «borra el archivo hola.txt del escritorio», «borrá el archivo viejo.txt»,
# «delete old.txt from the desktop»: one named file, optionally in one known
# folder, goes to the product's recoverable private trash
# (filesystem.known.trash.named). A bare name must look like a file (an
# extension) unless the request says «archivo/file», so «borra el mensaje»
# and folders stay outside; a folder deletion has no operation.
_FILE_TRASH_REQUEST = re.compile(
    r"^[¿?¡!\s]*(?:borr[aá]|borrar|borr[aá]me|elimin[aá]|eliminar|elimin[aá]me|"
    r"delete|remove|"
    r"(?:mand[aá]|manda|envi[aá]|envia|tir[aá]|tira)(?:me)?\s+a\s+la\s+papelera)(?:me)?\s+"
    r"(?:(?:el|la|the)\s+)?(?P<noun>(?:archivo|fichero|file|carpeta|folder|directorio|directory)\s+)?"
    r"(?:(?:llamad[oa]|named|called)\s+)?"
    r"(?P<name>\"[^\"]+\"|'[^']+'|[^\s\"']+)"
    rf"(?:\s+(?:del|de\s+la|de|from|in|en|on)\s+(?:(?:el|la|mi|my|the)\s+)?(?P<folder>{_KNOWN_FOLDER_WORDS}))?"
    r"(?:\s*,?\s+(?:por\s+favor|please|porfa))?[\s.!?]*$",
    re.IGNORECASE,
)


# PDF1689 H0666 «resumime informe.pdf», «hazme un resumen de informe.pdf»,
# «summarize report.pdf»: one named PDF in the known folders is read for its
# text (document.pdf.read) and the reply presents it; a bare name must be
# a .pdf file or the request must say «pdf».
_PDF_SUMMARY_REQUEST = re.compile(
    r"^[¿?¡!\s]*(?:(?:por\s+favor|please|porfa)\s*[,;:]?\s*)?"
    r"(?:(?:hac[eé]|hace|hazme|haceme|hac[eé]me|arm[aá]|arm[aá]me|dame|make|give\s+me|write|escrib[ií])(?:me)?\s+"
    r"(?:(?:un|una|el|a|the)\s+)?(?:resumen|summary)\s+(?:de|del|of)(?:\s+(?:el|la|the))?"
    r"|(?:resum[ií]|resumime|resum[ií]me|resumeme|resumir|resume|summari[sz]e|sum\s+up)(?:me)?"
    r"(?:\s+(?:el|la|the))?)\s+"
    r"(?P<noun>(?:archivo|fichero|file|documento|document|pdf)\s+)?"
    r"(?:(?:llamad[oa]|named|called)\s+)?"
    r"(?P<name>\"[^\"]+\"|'[^']+'|[^\s\"']+)"
    rf"(?:\s+(?:del|de\s+la|de|from|in|en|on)\s+(?:(?:el|la|mi|my|the)\s+)?(?P<folder>{_KNOWN_FOLDER_WORDS}))?"
    r"(?:\s*,?\s+(?:por\s+favor|please|porfa))?[\s.!?]*$",
    re.IGNORECASE,
)


def _pdf_summary_request(text: str) -> re.Match[str] | None:
    """Match one summary or reading request of a named PDF in the known folders."""

    found = _PDF_SUMMARY_REQUEST.match(text.strip())
    if found is None:
        return None
    name = found.group("name").strip("\"'").rstrip(".!?,")
    if not name or name.lower() in {"todo", "esto", "eso", "this", "that", "it", "pagina", "página", "page"}:
        return None
    if re.fullmatch(r"[^\\/:*?\"<>|]+\.pdf", name, re.IGNORECASE) is None:
        noun = found.group("noun")
        if noun is None or noun.strip().lower() != "pdf" or "." in name:
            return None
    return found


def _file_trash_request(text: str) -> re.Match[str] | None:
    """Match one literal deletion of a named file (or, FILES1603 H0327 «Borra la
    carpeta CarterTest del escritorio», a named folder) in the person's known folders."""

    found = _FILE_TRASH_REQUEST.match(text.strip())
    if found is None:
        return None
    name = found.group("name").strip("\"'").rstrip(".!?,")
    if not name or name.lower() in {"todo", "todos", "everything", "all", "eso", "esto", "it", "that", "this"}:
        return None
    looks_like_file = re.fullmatch(r"[^\\/:*?\"<>|]+\.[a-z0-9]{1,8}", name, re.IGNORECASE) is not None
    if not looks_like_file and found.group("noun") is None:
        return None
    return found


# FILES1705 H0334 «crea un archivo de texto con los 5 procesos que mas memoria
# usan»: a text file whose content is a process listing read from this
# machine — system.process.list (limit, sort) then filesystem.write.text
# with the listing projected deterministically from the verified result.
_PROCESS_REPORT_FILE_REQUEST = re.compile(
    r"^[¿?¡!\s]*(?:crea|crear|creame|genera|generame|generar|guarda|guardame|guardar|"
    r"escribe|escribime|escribir|arma|armame|make|create|save|write|generate)(?:me)?\s+"
    r"(?:(?:un|una|a|el|the)\s+)?(?:(?:text|txt)\s+)?(?:archivo|fichero|file)(?:\s+(?:de\s+texto|txt|text))?"
    r"(?:\s+(?:llamad[oa]|named|called)\s+(?P<name>[^\s\"']+))?\s+"
    r"(?:con|que\s+(?:tenga|liste|contenga|muestre)|with|listing|containing|of)\s+"
    r"(?P<desc>(?:(?:los|las|the|mis|my)\s+)?(?:(?P<n>\d{1,2})\s+)?(?:procesos|processes)\s+"
    r"(?:que\s+mas\s+(?P<res_a>memoria|cpu|procesador|ram)\s+(?:usan|consumen|ocupan|gastan)|"
    r"que\s+(?:usan|consumen|ocupan|gastan)\s+mas\s+(?P<res_b>memoria|cpu|procesador|ram)|"
    r"(?:that\s+)?(?:use|using|consume|consuming)\s+(?:the\s+)?most\s+(?P<res_c>memory|cpu|ram)|"
    r"with\s+(?:the\s+)?(?:highest|most)\s+(?P<res_d>memory|cpu|ram)(?:\s+usage)?))"
    r"(?:\s*,?\s+(?:por\s+favor|please))?[\s.!?]*$",
    re.IGNORECASE,
)


def process_report_file_request(folded: str) -> dict[str, object] | None:
    """Read one request for a text file listing the top processes by memory or CPU."""

    found = _PROCESS_REPORT_FILE_REQUEST.match(_strip_request_envelope(folded).strip())
    if found is None:
        return None
    resource = next(
        (found.group(key) for key in ("res_a", "res_b", "res_c", "res_d") if found.group(key)),
        "",
    ).lower()
    sort = "cpu" if resource in {"cpu", "procesador"} else "memory"
    report: dict[str, object] = {"sort": sort, "resource_word": resource}
    if found.group("n"):
        limit = int(found.group("n"))
        if not 1 <= limit <= 50:
            return None
        report["limit"] = limit
    if found.group("name"):
        report["name"] = found.group("name")
    # The file header repeats the request's own description of the listing
    # («los 5 procesos que mas memoria usan»), so every header token is evidence.
    report["description"] = " ".join(found.group("desc").split())
    return report


def _file_creation_request(text: str) -> re.Match[str] | None:
    """Match one literal file creation with a name and its content."""

    return _FILE_CREATION_REQUEST.match(text.strip())


def _directory_creation_request(text: str) -> re.Match[str] | None:
    """Match one literal folder creation with a name."""

    return _DIRECTORY_CREATION_REQUEST.match(text.strip())


def _reminder_has_actionable_due(folded: str) -> bool:
    """Require a literal instant or duration, not merely a calendar day."""

    return bool(
        _has(folded, _CLOCK_TIME_SELECTOR)
        or _has(
            folded,
            r"\b(?:(?:en|in|dentro de|within)\s+)?"
            rf"{_RELATIVE_DURATION_PATTERN}"
            r"(?:\s+(?:from now|desde ahora))?\b",
        )
        or _has(folded, r"\b\d{4}-\d{2}-\d{2}t\d{2}:\d{2}(?::\d{2})?\S*\b")
    )


def _incomplete_scheduled_request(
    text: str, available: frozenset[str]
) -> ClarificationIntent | None:
    """Clarify a literal partial time without authorizing a scheduled effect."""

    folded = _strip_request_envelope(_fold(text))
    # Keep scope checks on the whole request before reading a temporal preface.
    # Quoted payloads and multi-clause requests remain with the existing paths.
    if (
        explicit_non_action_frame(text)
        or _is_meta_or_tool_denial(folded)
        or _is_past_or_hypothetical_state(folded)
        or _has_contradictory_correction(folded)
        or _has(folded, r'["“”«»;]|\b(?:no|nunca|jamas|never|not|without|sin|if|si)\b')
    ):
        return None
    clock = re.search(_CLOCK_TIME_SELECTOR, folded)
    # The numeric vocabulary is shared with the existing spoken-number reader.
    number = r"(?:\d{1,2}|" + "|".join(
        word for word, value in {**_ENGLISH_SMALL_NUMBERS, **_SPANISH_SMALL_NUMBERS}.items()
        if 0 <= value <= 23
    ) + r")"
    if clock is None:
        clock = re.search(
            rf"\b(?:for|para)\s+(?:las?\s+)?{number}\b"
            r"(?!\s+(?:minutes?|minutos?|hours?|horas?|days?|dias?)\b)", folded,
        )
    # «Dentro de doce minutos, recordame …»: the preface may carry its own
    # preposition before the bounded selector (TIME1189/011).
    temporal = re.match(
        rf"^(?:(?:en|in|dentro\s+de|within)\s+)?(?:{_CLOCK_TIME_SELECTOR}|{_BOUNDED_TEMPORAL_SELECTOR})",
        folded,
    )
    body = folded
    if temporal is not None and temporal.end() < len(folded):
        body = _strip_request_envelope(folded[temporal.end():].lstrip(" ,:"))
    if len(_request_clauses(body)) != 1:
        return None
    desire = _EXPLICIT_DESIRE_REQUEST.match(body)
    if desire is not None:
        body = desire.group("body")
    nominal_desire = re.fullmatch(
        r"(?:me\s+vendria\s+bien|i\s+could\s+use)\s+(?P<body>.+)", body
    )
    if nominal_desire is not None:
        body = nominal_desire.group("body")
    # These are scheduling speech acts, not matches anywhere in arbitrary prose.
    noun_request = re.match(
        rf"^(?:{_SCHEDULING_VERB}|fija)\s+(?:(?:un|una|el|la|an?|the)\s+)?"
        r"(?P<noun>alarma|alarm|timer|temporizador|recordatorio|reminder)\b(?P<tail>.*)$",
        body,
    )
    if noun_request is None and (desire is not None or nominal_desire is not None):
        noun_request = re.match(
            r"^(?:(?:un|una|an?|the)\s+)?"
            r"(?P<noun>alarma|alarm|timer|temporizador|recordatorio|reminder)\b(?P<tail>.*)$",
            body,
        )
    wake = re.match(r"^(?:wake\s+me(?:\s+up)?|get\s+me\s+up|desp(?:ierta|erta)me|levantame)\b", body)
    reminder = re.match(r"^(?:recuerdame|recordame|avisame|remind\s+me)\s+(?P<title>.+)$", body)
    if reminder is None and desire is not None:
        reminder = re.match(r"^(?:recuerdes|recuerde|avises|avise)\s+(?P<title>.+)$", body)
    alarm = wake is not None or (
        noun_request is not None and noun_request.group("noun") in {"alarma", "alarm", "timer", "temporizador"}
    )
    title = reminder.group("title") if reminder is not None else ""
    if noun_request is not None and noun_request.group("noun") in {"recordatorio", "reminder"}:
        payload = re.search(r"\b(?:about|to|de|que)\s+(?P<title>\S.+)", noun_request.group("tail"))
        title = payload.group("title") if payload is not None else ""
    if title:
        content = re.sub(rf"(?:{_CLOCK_TIME_SELECTOR}|{_BOUNDED_TEMPORAL_SELECTOR})", " ", title)
        # The duration's own preposition («en 30 minutos», «in ten minutes»)
        # is not content either (TIME1195).
        content = re.sub(
            r"\b(?:at|for|para|a|las?|on|next|el|la|proximo|proxima|en|in|dentro|de|within)\b",
            " ",
            content,
        )
        if not re.search(r"[a-z]", content):
            title = ""
    # Only explicitly retained content uses this branch. Time-only reminders
    # retain the existing title clarification below; no AGENDA1024 WIP is merged.
    if (
        not alarm
        and not title
        and reminder is not None
        and "reminder.create" in available
        and _reminder_has_actionable_due(folded)
    ):
        # «avisame en 30 minutos»: the moment is given, the content is not.
        # Without this the effect path asked the model for arguments, which
        # re-asked the delay or invented the content (TIME1195/000, /006).
        return ClarificationIntent(("reminder.create",), ("what_to_remind_or_notify_about",))
    if not alarm and not title:
        return None
    operation = "notification.schedule" if alarm else "reminder.create"
    if operation not in available:
        return None
    if clock is not None:
        literal_clock = clock.group(0)
        digits = re.search(r"\b(\d{1,2})\b", literal_clock)
        hour_value = int(digits.group(1)) if digits else None
        has_period = _has(
            literal_clock,
            r"\b(?:a\.?\s*m\.?|p\.?\s*m\.?)\b|\b(?:de\s+la|in\s+the)\s+\w+\b",
        )
        if hour_value is not None and (
            hour_value > 23 or (has_period and not 1 <= hour_value <= 12)
        ):
            # «a las 99», «13 pm»: no part of day can make that hour exist, so
            # asking morning/afternoon would be unfaithful (TIME1195 probe).
            return ClarificationIntent((operation,), ("valid_hour_0_to_23",))
        complete_clock = _has(
            literal_clock,
            r"\b\d{1,2}:\d{2}\b|\b(?:a\.?\s*m\.?|p\.?\s*m\.?)\b|"
            r"\b(?:de\s+la|in\s+the)\s+\w+\b|\b(?:0|1[3-9]|2[0-3])\b",
        )
        complete_clock = complete_clock or any(
            (value == 0 or 12 < value <= 23) and _has(literal_clock, rf"\b{word}\b")
            for word, value in {**_ENGLISH_SMALL_NUMBERS, **_SPANISH_SMALL_NUMBERS}.items()
        )
        if not complete_clock:
            return ClarificationIntent((operation,), ("am_pm_or_part_of_day_for_supplied_hour",))
        return None
    if not _reminder_has_actionable_due(folded):
        return ClarificationIntent((operation,), ("alarm_time" if alarm else "due_time",))
    return None


def _multiple_alarm_schedule_intent(
    folded: str,
    available: frozenset[str],
) -> EffectIntent | None:
    """Expand one explicit plural alarm request into its literal clock effects."""

    if "notification.schedule" not in available or _has(
        folded,
        r"\b(?:recurrente|recurrentes|repeating|recurring|cada|every)\b",
    ):
        return None
    clock_token = (
        r"(?:[0-9]{1,2}|one|two|three|four|five|six|seven|eight|nine|"
        r"ten|eleven|twelve|una?|dos|tres|cuatro|cinco|seis|siete|"
        r"ocho|nueve|diez|once|doce)(?::[0-5][0-9])?"
    )
    request = re.match(
        (
            r"^[^\w]*(?:record|create|set|schedule|crea|crear|programa|"
            r"programar|pon|ponme)\s+(?:(?:the|las?)\s+)?"
            r"(?:alarms|alarmas)\s+(?:(?:for|at|a|para)\s+(?:las?\s+)?)?"
            rf"(?P<clocks>{clock_token}(?:\s*(?:,|and|y)\s*{clock_token})+)\s*"
            r"(?P<period>a\.?\s*m\.?|p\.?\s*m\.?|de la manana|"
            r"de la tarde|de la noche|in the morning|in the afternoon|"
            r"in the evening)[\s.!?]*$"
        ),
        folded,
        re.IGNORECASE,
    )
    if request is None:
        return None
    clocks = tuple(
        token.strip()
        for token in re.split(r"\s*(?:,|and|y)\s*", request.group("clocks"))
        if token.strip()
    )
    if not 2 <= len(clocks) <= 8 or len(set(clocks)) != len(clocks):
        return None
    for clock in clocks:
        hour_text = clock.split(":", 1)[0]
        if hour_text.isdigit() and not 1 <= int(hour_text) <= 12:
            return None
    period = request.group("period")
    noun = "alarma a las" if _has(folded, r"\balarmas\b") else "alarm at"
    evidence = tuple(f"{noun} {clock} {period}" for clock in clocks)
    return EffectIntent(
        tuple("notification.schedule" for _ in clocks),
        evidence,
    )


_TASK_DATE_ONLY = re.compile(
    r"^(?:crea|creame|crear|agrega|agregame|anade|anadime|add|create|make|haz|hazme|pon|ponme|poneme|nueva|new)\s+"
    r"(?:(?:una|la|a|the)\s+)?(?:tarea|task|to-do|todo|pendiente)(?:\s+(?:nueva|new))?"
    r"(?:\s+(?:para|for|el|la|on|por|by|due|hasta|until)\s+(?:(?:el|la|este|esta|next|this|el\s+proximo|la\s+proxima)\s+)?"
    r"(?:lunes|martes|miercoles|jueves|viernes|sabado|domingo|monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
    r"manana|tomorrow|hoy|today|pasado\s+manana|semana|week|mes|month|fin\s+de\s+semana|weekend)"
    r"(?:\s+(?:que\s+viene|proxim[oa]))?"
    r"(?:\s+(?:a\s+las?|at)\s+\d{1,2}(?::\d{2})?\s*(?:am|pm|h|hs)?)?)?"
    r"[\s.!?]*$"
)


def _task_without_title(folded: str) -> bool:
    """«crea una tarea para el viernes»: a creation with at most a date, no content."""

    return _TASK_DATE_ONLY.match(_strip_request_envelope(folded).strip(" ¿?¡!.,")) is not None


def _current_directory_file_count(folded: str) -> bool:
    """FILES1437 «dime cuántos archivos .py hay en el directorio actual»: a
    file count over «the current directory», which BAXY does not have."""

    return (
        _has(folded, r"\b(?:cuantos|cuantas|how many|count|cuenta|conta|contame|cuentame)\b")
        and _has(folded, r"\b(?:archivos?|ficheros?|files?)\b")
        and _has(
            folded,
            r"\b(?:directorio|carpeta|folder|directory)\s+(?:actual|current|de trabajo|en (?:el|la) que estoy)\b"
            r"|\b(?:current|working|present)\s+(?:directory|folder)\b|\bcwd\b",
        )
        and not _has(folded, r"\b(?:escritorio|desktop|descargas|downloads|documentos|documents)\b")
    )


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


def resolve_explicit_clarification_intent(
    text: str,
    available_operations: Iterable[str],
    application_names: Iterable[str] | ApplicationCatalogIndex = (),
) -> ClarificationIntent | None:
    """Preserve the operation identity of a recognized incomplete effect."""

    if explicit_non_action_frame(text):
        return None
    folded = _strip_request_envelope(_strip_request_envelope(_fold(text)))
    # MUSIC1571 H0656 «no me molesta, poné música»: the idiom accepts, it does
    # not negate the order that follows.
    folded = re.sub(r"^no\s+me\s+molesta\s*[,;:]?\s+(?=\S)", "", folded, count=1)
    available = frozenset(available_operations)
    alias_plan = exact_catalog_operation_plan(folded)
    if alias_plan is not None and set(alias_plan) <= available:
        # A reviewed full-utterance alias already proves a complete operation
        # identity.  Do not let a looser incomplete-request heuristic pre-empt
        # it; the caller still applies catalogue authority and policy gates.
        return None
    if _is_meta_or_tool_denial(folded):
        return None
    if _literal_note_payload_request(folded):
        # The subordinate text is note content, not a message recipient/body.
        return None
    if known_unsupported_effect_request(text, available):
        # LIMITS1677 «subí el volumen de spotify»: a known effect with no
        # operation has no field to clarify; the limit answers it.
        return None
    if "filesystem.known.search" in available and _current_directory_file_count(folded):
        # FILES1437 «dime cuántos archivos .py hay en el directorio actual»: BAXY
        # has no working directory; the count needs the person's folder.
        return ClarificationIntent(("filesystem.known.search",), ("folder",))
    if "audio.microphone.mute" in available and app_scoped_microphone_mute(folded) is not None:
        # UI1653 H0232 «silencia mi microfono en discord», H0128 «en Discord
        # apretá silenciar»: BAXY operates the Windows capture endpoint, not
        # the mute control of a voice client; it asks whether to mute the
        # system microphone (the client would stop receiving it) instead of
        # muting it unasked or pretending to press the client button.
        return ClarificationIntent(("audio.microphone.mute",), ("system_microphone_confirmation",))
    if "input.text.type" in available and re.fullmatch(
        # UI1645 H0265 «escribe en el diálogo el de ChadGBT»: a typing order
        # that names where to write and not what; the text is missing.
        r"[¿?¡!\s]*(?:escribe|escribi|escribime|tipea|tipeame|teclea|type|write)\s+"
        r"(?:en|in|into|on)\s+(?:(?:el|la|los|las|the)\s+)?"
        r"(?:dialogo|chat|campo|cuadro|casilla|buscador|barra|caja|input|box|field|dialog|prompt)\b"
        r"(?:\s+box)?(?:\s+(?:de\s+(?:texto|busqueda|chat)|of\s+\w+))?(?:\s+(?:el|la|the)\s+de\s+\S+|\s+(?:de|of)\s+\S+)?[\s.!?]*",
        folded,
    ) is not None and not re.search(r"[\"'«»“”]", folded):
        return ClarificationIntent(("input.text.type",), ("text",))
    if "input.visible.click" in available:
        # UI1639 H0344 «hace click en el boton rojo»: controls are found by
        # their visible text, never by colour; the label is still missing.
        click_label = _visible_click_label(folded)
        if click_label is not None and re.fullmatch(
            r"(?:(?:de\s+)?color\s+)?(?:rojo|roja|verde|azul|amarillo|amarilla|naranja|gris|negro|negra|blanco|blanca|"
            r"violeta|morado|morada|rosa|rosado|celeste|red|green|blue|yellow|orange|grey|gray|black|white|purple|pink)",
            click_label,
        ):
            return ClarificationIntent(("input.visible.click",), ("label",))
    hourly_dynamic_notification = (
        re.fullmatch(
            r"(?:get|send|give)\s+(?:me\s+)?(?:an?\s+)?hourly\s+"
            r"notifications?\s+(?:on|about|for)\s+\S.+[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    if "notification.schedule" in available and hourly_dynamic_notification:
        return ClarificationIntent(
            ("notification.schedule",),
            ("live_lookup_or_static_reminder", "first_notification_time"),
        )
    dynamic_public_notification = (
        _has(
            folded,
            r"\b(?:set|create|programa|configura)\b.{0,48}"
            r"\b(?:notifications?|notificaciones?|alerts?|avisos?)\b",
        )
        and _has(
            folded,
            r"\b(?:weather|clima|disasters?|desastres?|news|noticias|"
            r"stocks?|acciones)\b",
        )
        and not _has(folded, _CLOCK_TIME_SELECTOR)
    )
    if "notification.schedule" in available and dynamic_public_notification:
        return ClarificationIntent(
            ("notification.schedule",),
            ("live_monitoring_source", "notification_condition"),
        )
    incomplete_recurring_reminder = (
        _has(folded, r"\b(?:every|cada)\b")
        and _has(folded, r"\b(?:reminder|recordatorio)\b")
        and _has(folded, r"\b(?:set|create|crea|pon|programa)\b")
        and re.search(r"\b(?:for|para)\s*[.!?]*$", folded) is not None
    )
    if "reminder.create" in available and incomplete_recurring_reminder:
        return ClarificationIntent(
            ("reminder.create",),
            ("reminder_title", "recurrence_time"),
        )
    deictic_song_replay = (
        re.fullmatch(
            r"(?:quiero|i\s+want\s+to)\s+(?:reproducir|play)\s+"
            r"(?:esta|esa|this|that|the)\s+(?:cancion|song|track)\s+"
            r"(?:de\s+nuevo|otra\s+vez|again)[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    if "media.play.query" in available and deictic_song_replay:
        return ClarificationIntent(
            ("media.play.query",),
            ("song_title_or_current_media_context",),
        )
    categorized_application_request = (
        re.fullmatch(
            r"(?:muestra|muestrame|ensena|ensename|show|show\s+me|list|lista)\s+"
            r"(?:(?:las|los|the|some)\s+)?(?:apps?|aplicaciones?)\s+"
            r"(?:de|para|for)\s+\S.{0,120}[\s.!?]*|"
            r"(?:show|show\s+me|list)\s+(?:(?:the|some)\s+)?"
            r"\S.{0,80}\s+(?:apps?|applications?)[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    if "app.installed" in available and categorized_application_request:
        return ClarificationIntent(
            ("app.installed",),
            ("specific_application_name",),
        )
    providerless_order_delivery = (
        re.fullmatch(
            r"(?:sabe|sabes|dime|indica|tell\s+me|show\s+me|what|when|cual|cuando)\b"
            r".{0,96}\b(?:entrega\s+estimada|estimated\s+delivery|delivery\s+estimate|"
            r"fecha\s+de\s+entrega|delivery\s+date)\b.{0,96}"
            r"\b(?:mi|my|the)\s+(?:pedido|order)\b[\s.!?]*|"
            r"(?:sabe|sabes|dime|indica|tell\s+me|show\s+me|what|when|cual|cuando)\b"
            r".{0,96}\b(?:mi|my|the)\s+(?:pedido|order)\b.{0,96}"
            r"\b(?:entrega\s+estimada|estimated\s+delivery|delivery\s+estimate|"
            r"fecha\s+de\s+entrega|delivery\s+date)\b[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    if "web.search" in available and providerless_order_delivery:
        return ClarificationIntent(
            ("web.search",),
            ("merchant_or_tracking_reference",),
        )
    vague_calendar_intent = (
        re.fullmatch(
            r"(?:necesito|quiero|i\s+need\s+to|i\s+want\s+to)\s+"
            r"(?:hacer|do)\s+(?:algo|something)\s+"
            r"(?:hoy|today|manana|tomorrow)[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    if "calendar.event.create" in available and vague_calendar_intent:
        return ClarificationIntent(
            ("calendar.event.create",),
            ("event_title", "start_time", "end_time_or_duration"),
        )
    unspecified_meeting_reschedule = (
        re.fullmatch(
            r"(?:(?:can|could|would)\s+you\s+)?(?:reschedule|reprograma|reagenda)\s+"
            r"(?:(?:my|mi|the|la)\s+)?(?:meeting|reunion)[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    if "calendar.event.create" in available and unspecified_meeting_reschedule:
        return ClarificationIntent(
            ("calendar.event.create",),
            ("existing_event_identity", "new_start_time", "new_end_time"),
        )
    generic_calendar_event = (
        re.fullmatch(
            r"(?:add|create|make|agrega|crea)\s+(?:(?:an?|un)\s+)?event[oa]?\s+"
            r"(?:to|in|en|al)\s+(?:(?:the|el|la)\s+)?calendar(?:\s+app)?[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    if "calendar.event.create" in available and generic_calendar_event:
        return ClarificationIntent(
            ("calendar.event.create",),
            ("event_title", "start_time", "end_time"),
        )
    yearly_reminder_without_time = (
        _has(folded, r"\b(?:cada\s+ano|every\s+year|yearly|anualmente)\b")
        and _has(folded, r"\b(?:recuerdame|acuerdame|remind\s+me)\b")
        and not _has(folded, _CLOCK_TIME_SELECTOR)
    )
    if "reminder.create" in available and yearly_reminder_without_time:
        return ClarificationIntent(
            ("reminder.create",),
            ("one_time_or_yearly", "year_and_time"),
        )
    dated_notification_without_time = (
        _has(folded, r"\b(?:notificacion|notification)\b")
        and _has(folded, _CALENDAR_MONTH_TOKEN)
        and not _has(folded, _CLOCK_TIME_SELECTOR)
    )
    if "notification.schedule" in available and dated_notification_without_time:
        return ClarificationIntent(
            ("notification.schedule",),
            ("year_and_time",),
        )
    named_resume_without_provider = (
        re.fullmatch(
            r"(?:retoma|reanuda|resume)\s+\S.{0,160}"
            r"\b(?:por\s+donde|where)\b.{0,96}"
            r"\b(?:pare|stopped|left\s+off)\b.{0,80}[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    if (
        "media.control" in available
        and named_resume_without_provider
        and not _resume_existing_media(folded)
    ):
        return ClarificationIntent(
            ("media.control",),
            ("source_app",),
        )
    shared_note_read = (
        re.fullmatch(
            r"(?:lee|leeme|read)(?:\s+me)?\s+"
            r"(?:(?:los|las|the)\s+)?(?:post-?its?|notas?|notes?)\b.{0,120}"
            r"\b(?:compartid[oa]s?|shared)\b.{0,96}[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    if "note.search" in available and shared_note_read:
        return ClarificationIntent(
            ("note.search",),
            ("shared_note_source",),
        )
    providerless_store_request = re.fullmatch(
        r"(?:get|bring|order)\s+(?:me\s+)?"
        r"(?P<item>[a-z0-9][a-z0-9 ,.&'-]{1,160}?)\s+from\s+"
        r"(?:(?:uh+|um+|er+|eh+)\s+from\s+)?"
        r"(?P<store>[a-z0-9][a-z0-9 .'-]{1,80})[\s.!?]*",
        folded,
        re.IGNORECASE,
    )
    if "web.search" in available and providerless_store_request is not None:
        if not _has(
            folded,
            r"\b(?:calendar|calendario|commitments?|compromisos?|tasks?|tareas?|"
            r"notes?|notas?|files?|archivos?|reminders?|recordatorios?)\b",
        ):
            return ClarificationIntent(
                ("web.search",),
                ("product_lookup_or_purchase",),
            )
    dynamic_market_alert = (
        _has(folded, r"\b(?:avisame|notificame|alert\s+me|notify\s+me)\b")
        and _has(folded, r"\b(?:acciones|stocks?|shares?)\b")
        and _has(
            folded,
            r"\b(?:suben|bajan|subir|bajar|rise|fall|go\s+up|go\s+down)\b",
        )
    )
    if "notification.schedule" in available and dynamic_market_alert:
        return ClarificationIntent(
            ("notification.schedule",),
            ("company", "live_monitoring_source"),
        )
    corrected_private_note_time = (
        re.fullmatch(
            r"(?:let(?:'|\s+u2019)?s|vamos\s+a)\s+"
            r"(?:create|make|crear|hacer)\s+(?:(?:a|una?)\s+)?(?:new\s+|nueva?\s+)?"
            r"(?:private|privada?)\s+(?:note|nota)\b.{0,160}"
            r"\b(?:at|a\s+las?)\s+\S.{0,32}\b(?:actually|en\s+realidad|"
            r"mejor)\b.{0,48}[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    if "note.create" in available and corrected_private_note_time:
        return ClarificationIntent(
            ("note.create",),
            ("time_as_note_content_or_reminder",),
        )
    generic_game_discovery = (
        re.fullmatch(
            r"(?:quiero|quisiera|me\s+gustaria|i\s+want|i(?:'d|\s+would)\s+like)"
            r"\s+(?:probar\s+con|try|jugar(?:\s+a)?|play)\s+"
            r"(?:(?:algun|un|some|a)\s+)?(?:juego|game)\b\S?.{0,220}"
            r"[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    corrected_room_game = (
        _has(folded, r"\b(?:juego|game)\b")
        and _has(folded, r"\b(?:salon|living\s+room)\b")
        and _has(folded, r"\b(?:habitacion|bedroom)\b")
        and _has(folded, r"\b(?:no|mejor|actually|instead)\b")
    )
    room_scoped_game_request = (
        re.fullmatch(
            r"(?:in\s+(?:(?:the|my)\s+)?(?:living\s+room|bedroom)\s*[,;:]?\s*"
            r"(?:play|launch|start)|"
            r"(?:en|para)\s+(?:(?:el|la|mi)\s+)?(?:salon|habitacion)\s*[,;:]?\s*"
            r"(?:pon|inicia|lanza|juega))\s+\S.{0,160}[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    if "game.launch" in available and room_scoped_game_request:
        return ClarificationIntent(
            ("game.launch",),
            ("local_pc_or_supported_device",),
        )
    if "game.launch" in available and corrected_room_game:
        return ClarificationIntent(
            ("game.launch",),
            ("game_title", "target_device"),
        )
    if "game.launch" in available and generic_game_discovery:
        return ClarificationIntent(("game.launch",), ("game_title",))
    topic_free_recipe_search = (
        re.fullmatch(
            r"(?:muestra|ensena|show)(?:\s+me|me)?\s+"
            r"(?:(?:las|unas|some|the)\s+)?(?:recetas|recipes)"
            r"[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    if "web.search" in available and topic_free_recipe_search:
        return ClarificationIntent(("web.search",), ("recipe_topic",))
    next_available_meeting = (
        re.fullmatch(
            r"(?:set|schedule|create|agenda|programa|crea)\s+"
            r"(?:(?:a|una?)\s+)?(?:meeting|reunion)\b.{0,200}"
            r"\b(?:next|proximo)\s+available\s+(?:meeting\s+)?day\b"
            r"[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    if "calendar.event.create" in available and next_available_meeting:
        return ClarificationIntent(
            ("calendar.event.create",),
            ("start_time", "end_time_or_duration"),
        )
    bare_radio = (
        re.fullmatch(
            r"(?:radio)(?:\s+(?:por\s+favor|please))?[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    if "media.play.query" in available and bare_radio:
        return ClarificationIntent(("media.play.query",), ("station_or_genre",))
    incomplete_shared_note = (
        re.fullmatch(
            r"(?:quiero|necesito|i\s+want)\s+(?:escribir|crear|hacer|write|create|make)\s+"
            r"(?:(?:una?|a)\s+)?(?:nota|note)\s+(?:compartida|shared)\b"
            r".{0,120}\b(?:hasta|until)\b.{0,48}[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    referential_note_read = (
        re.fullmatch(
            r"(?:(?:(?:me|puedes|podrias|can\s+you|could\s+you)\s+)*"
            r"(?:lees|lee|leer|read)\s+(?:(?:me|to\s+me)\s+)?|"
            r"let\s+me\s+(?:see|view)\s+)"
            r"(?:esta|esa|this|that)\s+(?:nota|note)[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    corrected_note_without_reminder = (
        _has(folded, r"\b(?:nota|note)\b")
        and _has(folded, r"\b(?:recordatorio|reminder)\b")
        and _has(
            folded,
            r"\b(?:mejor|better)\b.{0,32}\b(?:no\s+(?:incluyas?|include)|"
            r"without|sin)\b",
        )
    )
    if "note.create" in available and (
        incomplete_shared_note or corrected_note_without_reminder
    ):
        return ClarificationIntent(("note.create",), ("note_content",))
    if "note.read" in available and referential_note_read:
        return ClarificationIntent(("note.read",), ("note_identity_or_context",))
    channel_free_conveyance = _has(
        folded,
        r"^(?:hazle\s+(?:saber|llegar)\s+a|cuentale\s+a|dile\s+a)\s+"
        r"[a-z0-9][a-z0-9 ._-]{0,80}?\s+"
        r"(?:que|el\s+mensaje|the\s+message)\s+\S.+$|"
        r"^dile\s+a\s+[a-z0-9._-]{1,80}\s+\S.+$|"
        r"^let\s+[a-z0-9][a-z0-9 ._-]{0,80}?\s+know\s+\S.+$|"
        r"^send\s+[a-z0-9][a-z0-9 ._-]{0,80}?\s+the\s+note\s+\S.+$|"
        r"^get\s+(?:the\s+)?(?:update|note|message)\s+\S.+\s+to\s+"
        r"[a-z0-9][a-z0-9 ._-]{0,80}$|"
        r"^pasale\s+a\s+[a-z0-9][a-z0-9 ._-]{0,80}?\s+"
        r"(?:el\s+)?(?:aviso|update)\s+\S.+$|"
        r"^manda\s+a\s+[a-z0-9][a-z0-9 ._-]{0,80}?\s+que\s+\S.+$|"
        r"^get\s+word\s+to\s+[a-z0-9][a-z0-9 ._-]{0,80}?\s+that\s+\S.+$|"
        r"^pass\s+[a-z0-9][a-z0-9 ._-]{0,80}?\s+(?:the\s+)?update\s+\S.+$|"
        r"^send\s+(?!them\b)[a-z0-9][a-z0-9 ._-]{0,80}?\s+that\s+\S.+$|"
        r"^hazle\s+know\s+a\s+[a-z0-9][a-z0-9 ._-]{0,80}?\s+que\s+\S.+$|"
        r"^send\s+a\s+[a-z0-9][a-z0-9 ._-]{0,80}?\s+el\s+update\s+que\s+\S.+$|"
        r"^hazel\s+sabera\s+a\s+[a-z0-9][a-z0-9 ._-]{0,80}?\s+que\s+\S.+$|"
        r"^hustle\s+no\s+a\s+[a-z0-9][a-z0-9 ._-]{0,80}?\s+que\s+\S.+$",
    )
    if (
        "message.send" in available
        and channel_free_conveyance
        and not _has(folded, r"\b(?:whatsapp|wsp|discord)\b")
    ):
        return ClarificationIntent(("message.send",), ("channel",))
    # MESSAGING1363: a reply with content but no addressee and no antecedent
    # («contestale que sí», «respondele que llego en 10») names nobody to
    # answer; the recipient is what is missing, not the channel.
    reply_head = (
        r"(?:contestale|contestales|respondele|respondeles|contesta|responde|"
        r"reply|answer)"
    )
    reply_without_addressee = _has(
        folded, rf"^[^\w]*{reply_head}\s+(?:que|that)\s+\S"
    ) and not _has(folded, rf"^[^\w]*{reply_head}\s+(?:a|to)\s+")
    if "message.send" in available and reply_without_addressee:
        return ClarificationIntent(("message.send",), ("recipient",))
    # MESSAGING1363: an addressee and a channel with nothing to say
    # («escribile por whatsapp a Pedro», «mandale un whatsapp a Ana»).
    addressed_without_content = _has(
        folded,
        (
            r"^[^\w]*(?:escrib[ei]le|escrib[ei]les|mandale|mandales|enviale|"
            r"enviales|hablale|escrib[ei]|manda|envia|write|send|message|text)\s+"
            # The addressee is one or two bare tokens: «mandale hola a Lucas
            # por whatsapp» carries its content and is not this shape.
            r"(?:(?:por|en|via|on)\s+(?:whatsapp|wsp|discord)\s+(?:a|to)\s+"
            r"[a-z0-9][a-z0-9._-]{0,40}(?:\s+[a-z0-9][a-z0-9._-]{0,40})?|"
            r"(?:(?:a|to)\s+)?[a-z0-9][a-z0-9._-]{0,40}\s+(?:por|en|via|on)\s+"
            r"(?:whatsapp|wsp|discord)|"
            r"(?:un|una|a)\s+(?:whatsapp|wsp|discord)\s+(?:a|to)\s+"
            r"[a-z0-9][a-z0-9._-]{0,40}(?:\s+[a-z0-9][a-z0-9._-]{0,40})?)[\s.!?]*$"
        ),
    ) and not _has(folded, r"\b(?:que|that|diciendo|saying)\b|[:\"«»“”]")
    if "message.send" in available and addressed_without_content:
        return ClarificationIntent(("message.send",), ("message_text",))
    corrected_browser = (
        "browser.navigate.named" in available
        and _has(folded, r"\b(?:youtube|video)\b")
        and _has(folded, r"\b(?:pero|but)\b.{0,100}\b(?:opera|browser)\b")
        and _has(folded, r"\b(?:queria|wanted|meant)\b")
        and not _has(folded, r"https?://\S+")
    )
    if corrected_browser:
        return ClarificationIntent(
            ("browser.navigate.named",),
            ("destination_url",),
        )
    # Share the speech-act head so supplied recipient/content stay present.
    message_speech_act = (
        r"(?:dile|decile|mandale|enviale|avisale|escrib[ei]le|respondele)"
    )
    incomplete_message_shape = _has(
        folded,
        (
            r"^[^\w]*(?:envia|enviar|manda|mandar|send)\b.{0,160}"
            r"\b(?:texto|text|mensaje|message)\b|"
            r"^[^\w]*ask\s+[a-z0-9][a-z0-9 ._-]{0,80}?\s+"
            r"(?:if|whether|what|when)\b|"
            r"^[^\w]*message\s+[a-z0-9][a-z0-9 ._-]{0,80}?\s+"
            r"(?:and\s+tell|and\s+say|that|saying)\b|"
            r"^[^\w]*tell\s+[a-z0-9][a-z0-9 _-]{0,80}?\s+that\b|"
            rf"^[^\w]*{message_speech_act}\s+(?:a\s+)?"
            r"[a-z0-9][a-z0-9 ._-]{0,80}?\s+(?:que|el\s+texto|el\s+mensaje)\b|"
            # MSGCLAR «mandale al grupo Musica: prueba 1 …»: a dictation colon
            # after the addressee carries the text.
            rf"^[^\w]*{message_speech_act}\s+(?:a\s+|al\s+(?:grupo\s+)?|para\s+)?"
            r"[a-z0-9][a-z0-9 ._-]{0,80}?\s*:\s*\S|"
            r"^[^\w]*let\s+[a-z0-9][a-z0-9 ._-]{0,80}?\s+know\s+that\b|"
            r"^[^\w]*write\s+[a-z0-9][a-z0-9 ._-]{0,80}?\s+"
            r"(?:that|the\s+message)\b|"
            r"^[^\w]*preguntale\s+a\s+[a-z0-9][a-z0-9 ._-]{0,80}?\s+"
            r"(?:si|que|a que)\b"
        ),
    )
    if incomplete_message_shape and _has(
        folded,
        r"^ask\s+on\s+the\s+what\s+bluetooth\s+radio\s+can\s+see\b",
    ):
        incomplete_message_shape = False
    if (
        incomplete_message_shape
        and _latest_email_domain(folded)
        and not _has(folded, r"\b(?:whatsapp|wsp|discord)\b")
    ):
        # ``Tell me ... the email that just arrived`` is a live mailbox read,
        # not an incomplete instruction to contact a person named by the
        # greedy ``tell ... that`` messaging surface.
        incomplete_message_shape = False
    desired_volume = _EXPLICIT_DESIRE_REQUEST.match(folded)
    relative_spoken_volume = (
        re.fullmatch(
            r"(?:(?:speak|talk)\s+(?:softer|quieter|louder)|"
            r"turn\s+(?:(?:the\s+)?volume\s+(?:up|down)|"
            r"(?:up|down)\s+(?:the\s+)?volume)|"
            r"(?:raise|lower|increase|decrease)\s+(?:the\s+)?volume)"
            r"(?:\s+please)?[.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
        or (
            desired_volume is not None
            and re.fullmatch(
                r"se\s+(?:oiga|oyera|escuche|escuchara)\s+"
                r"(?:mas\s+(?:fuerte|alto|bajo)|menos\s+fuerte)\s+"
                rf"(?:el|mi)\s+{_LOCAL_VOLUME_DEVICE}"
                r"(?:\s*,?\s*por favor)?[.!?]*",
                desired_volume.group("body"),
            ) is not None
        )
    )
    telegraphic_calendar_invite = (
        re.fullmatch(
            (
                r"(?:calendar\s+)?event\s+(?:send\s+)?invite\s+"
                r"[a-z0-9][a-z0-9 ._-]{0,96}[\s?!.]*"
            ),
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    incomplete_schedule = _incomplete_scheduled_request(text, available)
    if incomplete_schedule is not None:
        return incomplete_schedule
    if (
        not _is_direct_request(folded)
        and not _alarm_turn_off_request(folded)
        and not incomplete_message_shape
        and not relative_spoken_volume
        and not telegraphic_calendar_invite
        # BRIGHT1283: «estoy cansado subí el brillo», «subime el brillo» carry
        # a preamble or a clitic the direct-request heads do not list.
        and not brightness_relative_without_amount(folded)
    ):
        return None
    corrected_generic_game_request = (
        re.fullmatch(
            (
                r"(?:quiero|quisiera|me\s+gustaria)\s+jugar\s+"
                r"(?:a\s+)?(?:algun|un)\s+juego\s+[^.;!?]{1,80}?\s*[,;]?\s*"
                r"(?:quiero\s+decir|o\s+sea|mejor)\s+[^.;!?]{1,80}"
                r"[\s.!?]*"
            ),
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    if "game.launch" in available and corrected_generic_game_request:
        return ClarificationIntent(("game.launch",), ("game_title",))
    corrected_incomplete_note = (
        re.fullmatch(
            (
                r"(?:can\s+you\s+)?(?:make|create)\s+(?:a\s+)?new\s+"
                r"shared\s*[,;]?\s*(?:no|sorry)\s*[,;]?\s*personal\s+note"
                r"[\s.!?]*"
            ),
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    if "note.create" in available and corrected_incomplete_note:
        return ClarificationIntent(("note.create",), ("note_content",))
    if (
        "ocr.read" in available
        and _has(folded, r"\bocr\b")
        and _has(folded, rf"\b{_READ}\b|\bleela\b|\bleelo\b")
        and not (
            _has(
                folded,
                r"\b(?:captura(?: de pantalla)?|pantallazo|screenshot|screen capture)\b",
            )
            and _has(
                folded,
                r"\b(?:haz|hacer|toma|tomar|crea|capture|take)\b",
            )
        )
    ):
        return ClarificationIntent(
            ("ocr.read",),
            ("image_or_new_screenshot",),
        )
    if (
        "calendar.event.list" in available
        and _has(folded, r"\b(?:calendario|calendar|eventos?|events?)\b")
        and _has(folded, rf"\b{_LIST}\b|\b(?:proximos?|upcoming)\b")
        and not _has(
            folded,
            r"\b(?:desde|from)\b.+\b(?:hasta|to)\b|"
            r"\b\d{4}-\d{2}-\d{2}(?=$|[t\s,;.!?])|"
            r"\b(?:hoy|today|manana|tomorrow|esta semana|this week|"
            r"la proxima semana|next week|este mes|this month)\b",
        )
        and not (
            (
                catalog_read := _strict_catalog_request(
                    folded,
                    available,
                    build_application_catalog_index(()),
                )
            )
            is not None
            and len(catalog_read.operations) >= 2
        )
    ):
        return ClarificationIntent(
            ("calendar.event.list",),
            ("date_range",),
        )
    if (
        "message.send" in available
        and _head_is(
            _request_head(folded),
            r"(?:envia|enviar|enviales|manda|mandar|mandales|send)",
        )
        and _has(
            folded,
            r"\b(?:mandales|enviales|send them)\b|"
            r"\b(?:ese|esa|that)\s+(?:mensaje|message)\b",
        )
    ):
        return ClarificationIntent(
            ("message.send",),
            ("recipient", "message_text"),
        )
    if "message.send" in available and incomplete_message_shape and message_draft_request(text) is None:
        # MSGCLAR «mandale al grupo Musica: prueba 1 de WhatsApp, ya funciona
        # de nuevo»: a client named inside the dictated text is part of the
        # message, not the channel; the channel counts in the instruction
        # before the dictation or as a trailing «por whatsapp».
        instruction_part = re.split(
            r":|\bque\s+diga\b|\bque\s+dice\b|\bdiciendo\b|\bsaying\b|\bthat\s+says\b",
            folded,
            maxsplit=1,
        )[0]
        supported_channel = _has(
            instruction_part,
            r"\b(?:whatsapp|wsp|discord)\b",
        ) or _has(
            folded,
            r"\b(?:por|en|via|on|in|through|by)\s+(?:whatsapp|wsp|discord)[\s.!?]*$",
        )
        literal_recipient = _has(
            folded,
            (
                r"^[^\w]*ask\s+[a-z0-9][a-z0-9 ._-]{0,80}?\s+"
                r"(?:if|whether|what|when)\b|"
                r"^[^\w]*message\s+[a-z0-9][a-z0-9 ._-]{0,80}?\s+"
                r"(?:and\s+tell|and\s+say|that|saying)\b|"
                r"^[^\w]*tell\s+[a-z0-9][a-z0-9 _-]{0,80}?\s+that\b|"
                rf"^[^\w]*{message_speech_act}\s+"
                r"(?:a\s+)?"
                r"[a-z0-9][a-z0-9 ._-]{0,80}?\s+(?:que|el\s+texto|el\s+mensaje)\b|"
                rf"^[^\w]*{message_speech_act}\s+(?:a\s+|al\s+(?:grupo\s+)?|para\s+)?"
                r"[a-z0-9][a-z0-9 ._-]{0,80}?\s*:\s*\S|"
                r"^[^\w]*let\s+[a-z0-9][a-z0-9 ._-]{0,80}?\s+know\s+that\b|"
                r"^[^\w]*write\s+[a-z0-9][a-z0-9 ._-]{0,80}?\s+"
                r"(?:that|the\s+message)\b|"
                r"^[^\w]*preguntale\s+a\s+[a-z0-9]"
                r"[a-z0-9 ._-]{0,80}?\s+(?:si|que|a que)\b|"
                r"\b(?:mensaje|message)\s+(?:a|to)\s+[a-z0-9]"
                r"[a-z0-9 ._-]{0,80}?\s+(?:para|to)\b|"
                r"\b(?:envia|manda|send)\s+"
                r"(?!(?:este|esta|this|that|the|a|an)\b)[a-z0-9]"
                r"[a-z0-9 ._-]{0,80}?\s+(?:el\s+|the\s+)?"
                r"(?:whatsapp\s+)?(?:mensaje|message)\b"
            ),
        ) and not _has(
            folded,
            r"\b(?:a|to)\s+(?:ellos|ellas|les|them)\b",
        )
        literal_payload = _has(
            folded,
            (
                r"\b(?:mensaje|message)\s*:\s*\S|"
                r"^[^\w]*ask\s+.+?\s+(?:if|whether|what|when)\s+\S|"
                r"^[^\w]*message\s+.+?\s+(?:and\s+tell|and\s+say|that|saying)\s+\S|"
                r"^[^\w]*tell\s+[^.;!?]{1,80}?\s+that\s+\S|"
                rf"^[^\w]*{message_speech_act}\s+"
                r"(?:a\s+)?"
                r".+?\s+(?:que|el\s+texto|el\s+mensaje)\s+\S|"
                rf"^[^\w]*{message_speech_act}\s+.+?:\s*\S|"
                r"^[^\w]*let\s+.+?\s+know\s+that\s+\S|"
                r"^[^\w]*write\s+.+?\s+(?:that|the\s+message)\s+\S|"
                r"^[^\w]*preguntale\s+a\s+.+?\s+(?:si|que|a que)\s+\S|"
                r"\b(?:para|to)\s+(?:decirle|tell)\b.+\S|"
                r"\b(?:mensaje|message)\s+[Â«\"'â€˜â€œ]?[a-z0-9].+|"
                r"\b(?:mensaje|message)\s+[^\w\s]\s*[a-z0-9].+"
            ),
        )
        missing_fields = tuple(
            field
            for field, present in (
                ("channel", supported_channel),
                ("recipient", literal_recipient),
                ("message_text", literal_payload),
            )
            if not present
        )
        if missing_fields:
            return ClarificationIntent(("message.send",), missing_fields)
    incomplete_calendar_clause = any(
        _head_is(
            _request_head(clause),
            r"(?:crea|crear|añade|añadir|anade|anadir|agrega|agregar|"
            r"haz|hacer|create|make|add|set|agenda|agendar|agendame|"
            r"programa|programar|schedule)",
        )
        and not _head_is(
            _request_head(clause),
            r"(?:anota|anotar|note\s+down)",
        )
        and _has(clause, r"\b(?:reunion|meeting|evento|event)\b")
        and not _has(clause, r"\b(?:recordatorio|reminder)\b")
        and not _has(
            folded,
            r"\b(?:avisame|recuerdame|recordame|remind\s+me)\b",
        )
        and _has(clause, _BOUNDED_TEMPORAL_SELECTOR)
        and not _has(
            clause,
            r"\b(?:de|desde|from)\b.+\b(?:a|hasta|to)\b",
        )
        for clause in _request_clauses(folded)
    )
    if "calendar.event.create" in available and incomplete_calendar_clause:
        return ClarificationIntent(
            ("calendar.event.create",),
            ("end_time_or_duration",),
        )
    telegraphic_calendar_invite = (
        re.fullmatch(
            (
                r"(?:calendar\s+)?event\s+(?:send\s+)?invite\s+"
                r"[a-z0-9][a-z0-9 ._-]{0,96}[\s?!.]*"
            ),
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    if "calendar.event.create" in available and telegraphic_calendar_invite:
        return ClarificationIntent(
            ("calendar.event.create",),
            ("event_title", "event_time"),
        )
    if (
        "app.open" in available
        and _head_is(_request_head(folded), _OPEN)
        and (
            # A generic app object is missing an identity, not a capability.
            # Consume the whole request so a named target or added instruction
            # stays with its ordinary argument/domain handling.
            re.fullmatch(
                rf"[¿?¡!\s]*{_OPEN}\s+(?:(?:un|una|a|an|el|la|the)\s+)?"
                r"(?:aplicacion|application|app|programa|program)"
                r"(?:\s*[,;]?\s*(?:por\s+favor|please))?[\s.!?]*",
                folded,
            )
            is not None
            or _has(
                folded,
                r"\b(?:navegador\s+por\s+defecto|default\s+browser|"
                r"(?:la\s+|the\s+)?ventana|window)\b",
            )
        )
        and not _has(folded, _KNOWN_APPLICATION)
        and not _has(folded, r"\b(?:incognito|incognita|privada|private)\b")
    ):
        return ClarificationIntent(("app.open",), ("application",))
    if (
        {"backup.create", "filesystem.write.text"} <= available
        and _has(folded, r"\b(?:backup|respaldo|copia\s+de\s+seguridad)\b")
        and _has(
            folded,
            r"\b(?:edita|editar|cambia|cambiar|modifica|modify|edit|change)\b",
        )
    ):
        return ClarificationIntent(
            ("backup.create", "filesystem.write.text"),
            ("target_file", "replacement_content"),
        )
    if (
        "bluetooth.device.pair" in available
        and _head_is(_request_head(folded), r"(?:conecta|conectar|connect)")
        and _has(folded, r"\bbluetooth\b")
        and not _has(
            folded,
            r"\b(?:dispositivo|device|auriculares?|headphones?)\s+\S",
        )
    ):
        return ClarificationIntent(("bluetooth.device.pair",), ("device",))
    if (
        "clipboard.write.text" in available
        and _head_is(_request_head(folded), r"(?:copia|copiar|copiame|copy)")
        and _has(folded, r"\b(?:portapapeles|clipboard)\b")
        and _has(folded, r"\b(?:este|esta|this)\s+(?:texto|text)\b")
    ):
        return ClarificationIntent(("clipboard.write.text",), ("text",))
    if (
        {
            "filesystem.known.search",
            "filesystem.read.text",
            "filesystem.write.text",
        }
        <= available
        and _head_is(_request_head(folded), r"(?:convierte|convert|transforma)")
        and _has(folded, r"\b(?:archivo\s+nuevo|new\s+file)\b")
    ):
        return ClarificationIntent(
            (
                "filesystem.known.search",
                "filesystem.read.text",
                "filesystem.write.text",
            ),
            (
                "source_file",
                "destination_file",
            ),
        )
    # MUSIC1571: «poneme una canción», «ponme musika», «tengo hambre poné
    # música», «no me molesta, poné música» are the same incomplete request:
    # a song or music with nothing named; a spoken preface before the order
    # («tengo hambre», «no me molesta,») is envelope here.
    music_folded = re.sub(
        r"^(?:(?:tengo\s+(?:hambre|sueno|frio|calor)|no\s+me\s+molesta|bueno|dale|che|ya)\s*[,;:]?\s+)+",
        "",
        folded,
        count=1,
    )
    incomplete_media_clause = any(
        # MUSIC1767 «tocá una canción en Spotify», «tocame algo»: the same bare request.
        _head_is(_request_head(clause), r"(?:pon|pone|poneme|ponme|reproduce|reproduci|reproducime|play|toca|tocame|toque)")
        # VIDEO1717 «abre youtube y pon un video»: a bare video is as
        # incomplete as a bare song.
        and _has(clause, r"\b(?:musica|music|musika|cancion|canciones|song|songs|tema|temas|track|tracks|algo|something|videos?)\b")
        and _desired_music_query(clause) is None
        # A video that is already named («un video de lofi en youtube») or a
        # title on a streaming service («The Office en Prime Video») is not bare.
        and youtube_play_query(clause) is None
        and not _has(clause, r"\bvideos?\s+(?:de|sobre|of|about)\s+\S")
        and not _has(clause, r"\b(?:en|on)\s+(?:netflix|disney|prime|hbo|max|crunchyroll|star|paramount|twitch|hulu|peacock|apple)\b")
        for clause in _request_clauses(music_folded)
    )
    browser_music = _named_browser_music_request(text)
    if (
        "media.play.query" in available
        and "browser.navigate.named" in available
        and browser_music is not None
        and browser_music[1] is None
    ):
        # MUSIC1827 «abrí chrome y poné música»: which music is asked first;
        # the answer opens YouTube's results in that browser.
        return ClarificationIntent(("media.play.query",), ("query",))
    if (
        "media.play.query" in available
        and incomplete_media_clause
        and (
            _head_is(
                _request_head(music_folded),
                r"(?:pon|pone|poneme|ponme|reproduce|play|toca|tocame|toque)",
            )
            or (_head_is(_request_head(music_folded), _OPEN) and _has(music_folded, r"\b(?:spotify|youtube)\b"))
        )
    ):
        return ClarificationIntent(("media.play.query",), ("query",))
    if (
        "audio.volume" in available
        and re.fullmatch(
            rf"{_SET_VOLUME_VERB}\s+(?:(?:el|the)\s+)?(?:volumen|volume)"
            r"(?:\s+(?:(?:al?|del?)\s+(?:sistema|equipo|pc|computador(?:a)?|ordenador)|"
            r"(?:of|on)\s+(?:the|my)\s+(?:system|computer|pc)))?"
            r"(?:\s+(?:a|al|en|to|at))?"
            r"(?:\s*,?\s*(?:please|por favor))?[.!?]*",
            folded,
        ) is not None
    ):
        # The same setting head with no target level is incomplete, not a
        # request to observe the previous level. Preserve the known operation
        # before the native selector can repeat an earlier status request.
        # A trailing value preposition still supplies no level. Full matching
        # preserves supplied values, other targets and subsequent clauses.
        return ClarificationIntent(("audio.volume",), ("level",))
    if "audio.app.volume.adjust" in available:
        app_volume = app_volume_request(text, application_names)
        if app_volume is not None and app_volume[2] is None:
            # AUDIO1787 «subí el volumen de spotify»: the application volume
            # keeps its direction and asks how much (owner rule on H0027).
            return ClarificationIntent(("audio.app.volume.adjust",), ("amount",))
    if (
        "audio.volume.adjust" in available
        and (
            _head_is(
                _request_head(folded),
                rf"(?:{_VOLUME_UP_VERB}|{_VOLUME_DOWN_VERB})",
            )
            and _has(folded, r"\b(?:volumen|volume)\b")
            or relative_spoken_volume
            or _bare_music_volume_request(folded)
        )
        and not _has(folded, r"\b(?:100|[0-9]{1,2})\b")
        and _literal_percentage_word_value(folded) is None
        and _literal_volume_adjustment(folded) is None
    ):
        if (
            "system.settings.adjust" in available
            and _has(
                folded,
                rf"\b(?:{_BRIGHTNESS_UP_VERB}|{_BRIGHTNESS_DOWN_VERB})\b[^,;]{{0,24}}"
                rf"\b{_BRIGHTNESS_OBJECT}\b",
            )
            and _literal_brightness_adjustment(folded) is None
        ):
            # AUDIO1461 «subí el volumen y bajá el brillo»: both amounts are
            # missing; the question must name both adjustments (H0027).
            return ClarificationIntent(("audio.volume.adjust", "system.settings.adjust"), ("amount",))
        return ClarificationIntent(("audio.volume.adjust",), ("amount",))
    if (
        "system.settings.adjust" in available
        and brightness_relative_without_amount(folded)
        and _literal_brightness_adjustment(folded) is None
    ):
        # BRIGHT1283: «subí el brillo» keeps its direction and asks how much,
        # the same owner rule as the volume (H0027); no default step.
        return ClarificationIntent(("system.settings.adjust",), ("amount",))
    if (
        {"memory.recall", "clipboard.write.text"} <= available
        and _head_is(_request_head(folded), r"(?:copy|copia|copiame)")
        and _has(folded, r"\b(?:my|mi)\s+(?:email|correo)\s+(?:address|electronico)\b")
        and _has(folded, r"\b(?:clipboard|portapapeles)\b")
    ):
        return ClarificationIntent(
            ("memory.recall", "clipboard.write.text"),
            ("stored_email_address",),
        )
    if (
        "office.document.create" in available
        and _has(folded, r"\b(?:powerpoint|presentacion|presentation)\b")
        and _has(folded, r"\b(?:crea|crear|haz|hacer|make|create)\b")
        and not _has(folded, r"\b(?:sobre|about|titulad[oa]|called|named)\b")
        and not _has(folded, r"\b(?:diapositivas?|slides?)\b|\b\d+\b")
    ):
        return ClarificationIntent(
            ("office.document.create",),
            ("topic_or_content",),
        )
    if (
        "reminder.create" in available
        and _has(folded, r"\b(?:recordatorio|reminder)\b")
        and _head_is(
            _request_head(folded),
            r"(?:pon|ponme|pone|crea|crear|set|create)",
        )
    ):
        if not _reminder_has_actionable_due(folded):
            return ClarificationIntent(("reminder.create",), ("due_time",))
        if _time_only_reminder_request(folded):
            return ClarificationIntent(("reminder.create",), ("title",))
    if "task.create" in available and _task_without_title(folded):
        # AGENDA1021/TIME1199 H0043 «crea una tarea para el viernes»: only a
        # date was given; the title is asked, never invented.
        return ClarificationIntent(("task.create",), ("title",))
    alarm_turn_off = _alarm_turn_off_request(folded)
    unnamed_cancellation = (
        (
            _head_is(
                _request_head(folded),
                r"(?:delete|remove|cancel|erase|elimina|eliminar|borra|borrar|"
                r"quita|quitar|cancela|cancelar|"
                # AGENDA1337 «cancelame la alarma»: the clitic forms are the
                # same unnamed cancellation.
                r"cancelame|cancelamela|cancelala|borrame|borrala|quitame|quitala|"
                r"eliminame|eliminala)",
            )
            or alarm_turn_off
        )
        and not _has(folded, _CLOCK_TIME_SELECTOR)
        and not _latest_notification_selector(folded)
        and _exact_local_reminder_title(folded) is None
    )
    if (
        unnamed_cancellation
        and "reminder.delete" in available
        and _has(folded, r"\b(?:reminder|recordatorio)\b")
        and not _has(folded, r"\b(?:reminders|recordatorios)\b")
    ):
        return ClarificationIntent(("reminder.delete",), ("reminder_title",))
    if (
        unnamed_cancellation
        and "notification.cancel.at" in available
        and _has(folded, r"\b(?:alarm|alarma)\b")
        and not _has(folded, r"\b(?:alarms|alarmas)\b")
    ):
        # AGENDA1021 H0011 «cancelá la alarma»: the owner rules that the
        # product asks which alarm (unless it already knows a single one);
        # naming the missing field as a time made it ask when to cancel.
        return ClarificationIntent(("notification.cancel.at",), ("which_alarm",))
    if (
        "window.move" in available
        and _head_is(
            _request_head(folded),
            r"(?:arrastra|arrastrar|mueve|mover|drag|move)",
        )
        and _has(folded, r"\b(?:ventana|window)\b")
        and not _has(folded, r"\b(?:activa|active|actual|current|de\s+\S+)\b")
        and not _has(folded, r"\b(?:archivo|file|carpeta|folder)\b")
    ):
        return ClarificationIntent(("window.move",), ("window",))
    return None


def _fold(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    without_marks = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    return " ".join(without_marks.split())


def _match(text: str, pattern: str) -> re.Match[str] | None:
    return re.search(pattern, text, re.IGNORECASE)


def _has(text: str, pattern: str) -> bool:
    return _match(text, pattern) is not None


def _entity_key(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", _fold(value)))


def build_game_catalog_index(
    entries: Iterable[tuple[str, str, str]] | GameCatalogIndex,
) -> GameCatalogIndex:
    """Validate and normalize a bounded Core-authenticated game snapshot."""

    if isinstance(entries, GameCatalogIndex):
        return entries
    retained: list[tuple[str, str, str, str]] = []
    identities: set[tuple[str, str]] = set()
    provider_names: set[tuple[str, str]] = set()
    for entry in entries:
        if (
            not isinstance(entry, (tuple, list))
            or len(entry) != 3
            or not all(isinstance(value, str) for value in entry)
        ):
            raise ValueError("invalid game catalog entry")
        provider, app_id, name = entry
        if len(retained) >= MAX_GAME_CATALOG_ENTRIES:
            raise ValueError("game catalog entry limit exceeded")
        if provider not in {"steam", "epic"}:
            raise ValueError("invalid game catalog provider")
        if (
            not app_id
            or len(app_id) > 16
            or re.fullmatch(r"[A-Za-z0-9._-]+", app_id) is None
        ):
            raise ValueError("invalid game catalog app id")
        display_name = name
        key = _entity_key(display_name)
        identity = (provider, app_id)
        provider_name = (provider, key)
        if (
            not display_name.strip()
            or "\ufffd" in display_name
            or any(
                unicodedata.category(character) == "Cc"
                or character.isspace()
                and character != " "
                for character in display_name
            )
            or not key
            or len(display_name.encode("utf-8")) > 512
            or identity in identities
            or provider_name in provider_names
        ):
            raise ValueError("ambiguous game catalog entry")
        identities.add(identity)
        provider_names.add(provider_name)
        retained.append((key, provider, app_id, display_name))
    retained.sort(key=lambda item: (item[0], item[1], item[2]))
    return GameCatalogIndex(tuple(retained))


def _authenticated_game_target(
    text: str,
    game_catalog: GameCatalogIndex,
) -> tuple[str, str, str] | None:
    """Resolve one exact or numeric-edition-prefix installed game title."""

    request = _match(
        text,
        (
            r"^[¿?¡!\s]*(?:(?:por favor|please)\s*[,;:]?\s*|"
            r"(?:puedes|podrias|can you|could you|would you)\s+)?"
            rf"(?:(?:vamos\s+a\s+)?(?:juega|jugar|juguemos|play)|"
            rf"(?:{_OPEN}|lanza|launch|ejecuta|run))\b\s+"
            r"(?:(?:al|el|the)\s+)?(?:(?:juego|game)\s+)?"
            r"(?P<title>.+?)"
            r"(?:\s+(?:modo|mode)\s+(?:multijugador|multiplayer))?"
            r"(?:\s+(?:desde|en|from|on)\s+steam)?[\s?!.]*$"
        ),
    )
    if request is None or _is_negated_match(text, request):
        return None
    target_key = _entity_key(request.group("title"))
    if not target_key:
        return None
    exact = [entry for entry in game_catalog.entries if entry[0] == target_key]
    candidates = exact or [
        entry
        for entry in game_catalog.entries
        if entry[0].startswith(target_key + " ")
        and re.fullmatch(r"\d+", entry[0][len(target_key) + 1 :]) is not None
    ]
    identities = {(entry[1], entry[2]) for entry in candidates}
    if len(identities) != 1:
        return None
    selected = candidates[0]
    return selected[1], selected[2], selected[3]


def _corrected_game_launch_title(text: str) -> str | None:
    """Extract the final positive game title from one explicit self-correction."""

    corrected = re.fullmatch(
        (
            r"[¿?¡!\s]*(?:quitar|quita|remove|delete|uninstall)\b[^.;!?]{0,64}"
            r"\b(?:quiero\s+decir|i\s+mean|meant|mejor)\b\s*[,;:]?\s*"
            r"(?:poner|pon|play|launch|lanza|abrir|abre)\s+"
            r"(?:(?:el|the)\s+)?(?:(?:juego|game)\s+)?"
            r"(?P<title>[^.;!?]{1,120})[\s.!?]*"
        ),
        _fold(text),
        re.IGNORECASE,
    )
    if corrected is None:
        return None
    title = corrected.group("title").strip()
    return title if title else None


def resolve_game_catalog_app_id(
    text: str,
    game_catalog: Iterable[tuple[str, str, str]] | GameCatalogIndex,
) -> str | None:
    """Return one authenticated local AppID for a request or exact title."""

    index = build_game_catalog_index(game_catalog)
    request_target = _authenticated_game_target(_fold(text), index)
    if request_target is not None:
        return request_target[1]
    key = _entity_key(text)
    matches = [entry for entry in index.entries if entry[0] == key]
    identities = {(entry[1], entry[2]) for entry in matches}
    return matches[0][2] if len(identities) == 1 else None


def _application_name_key(value: str) -> str:
    """Normalize case/spacing while preserving an app name's punctuation."""

    return _fold(value)


def build_application_catalog_index(
    application_names: Iterable[str] | ApplicationCatalogIndex,
) -> ApplicationCatalogIndex:
    """Normalize and compile an authenticated catalog exactly once."""

    if isinstance(application_names, ApplicationCatalogIndex):
        return application_names
    retained: list[tuple[str, str]] = []
    seen: set[str] = set()
    for name in application_names:
        if not isinstance(name, str):
            continue
        key = _application_name_key(name)
        if not key or key in seen:
            continue
        if len(retained) >= MAX_APPLICATION_CATALOG_ENTRIES:
            raise ValueError("application catalog exceeds entry limit")
        seen.add(key)
        retained.append((name, key))
    retained.sort(key=lambda item: (-len(item[1]), item[1]))
    escaped_names = tuple(re.escape(key) for _, key in retained)
    pattern_chars = sum(len(name) + 1 for name in escaped_names)
    if pattern_chars > MAX_APPLICATION_CATALOG_PATTERN_CHARS:
        raise ValueError("application catalog exceeds pattern limit")
    occurrence_pattern = (
        re.compile(
            (r"(?<![a-z0-9])(?P<target>" + "|".join(escaped_names) + r")(?![a-z0-9])"),
            re.IGNORECASE,
        )
        if escaped_names
        else None
    )
    return ApplicationCatalogIndex(
        entries=tuple(retained),
        keys=frozenset(seen),
        entity_identities=tuple((_entity_key(name), key) for name, key in retained),
        occurrence_pattern=occurrence_pattern,
    )


_APPLICATION_TRAILING_REQUEST = re.compile(
    r"\s*[,;:]?\s+(?:por favor|please|para mi|for me|ahora|now|"
    r"dale|porfa|porfi|porfis|pls|plz)$",
    re.IGNORECASE,
)


def _edit_distance(left: str, right: str) -> int:
    """Levenshtein distance with adjacent transpositions counted once."""

    previous = list(range(len(right) + 1))
    rows = [previous]
    for i, a in enumerate(left, 1):
        current = [i]
        for j, b in enumerate(right, 1):
            cost = 0 if a == b else 1
            value = min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + cost)
            if i > 1 and j > 1 and a == right[j - 2] and left[i - 2] == b:
                value = min(value, rows[i - 2][j - 2] + 1)
            current.append(value)
        rows.append(current)
        previous = current
    return previous[-1]


def near_catalog_application_candidates(
    text: str,
    application_names: Iterable[str] | ApplicationCatalogIndex,
) -> tuple[str, ...]:
    """APPS1495 «abres team», «Abre stea,», «Sí, abre Ste.», «abre Steel.»: the
    catalog names (at most two) that a plain open order almost names — a
    prefix of three or more letters, or one or two edits away — when the
    target itself matches no catalog entry. Empty for anything else: an
    authenticated target, a target with more than two words, a negation,
    a deferred request, or no near miss."""

    catalog = build_application_catalog_index(application_names)
    folded = _strip_request_envelope(_fold(text))
    if not folded or _has(folded, r"\b(?:no|nunca|jamas|never|don't|do\s+not)\b|\b(?:si|if|cuando|when)\b.{0,20}\b(?:termine|acabe|finish)\b"):
        return ()
    folded = re.sub(r"^(?:si|ok|dale|bueno|y|and)\s*[,.]?\s*(?:quema\s*,?\s*)?", "", folded, count=1).strip()
    if _authenticated_application_target(folded, catalog) is not None:
        return ()
    if resolve_application_catalog_app_id(folded, catalog) is not None:
        # An alias the catalog resolver already authenticates («abrime el
        # chrome» → Google Chrome) is an opening, not a near miss.
        return ()
    request = _application_open_request(folded)
    if request is None or request.group("desire") is not None:
        return ()
    target = request.group("target").strip(" ¿?¡!,:;.-")
    target = re.sub(r"\s*,?\s*(?:por\s+favor|porfa|please|pls)$", "", target).strip(" ,.")
    target = re.sub(r"^(?:el|la|los|las|the|a|an)\s+", "", target)
    key = _application_name_key(target)
    if not key or len(key) < 3 or len(key.split()) > 2 or not re.fullmatch(r"[a-z0-9 .+-]+", key):
        return ()
    if key in catalog.keys:
        return ()
    scored: list[tuple[int, str]] = []
    for name, entry_key in catalog.entries:
        tokens = [entry_key] + entry_key.split()
        best = None
        for token in tokens:
            if len(token) < 3:
                continue
            if token.startswith(key) and len(key) >= 3:
                score = 0
            else:
                distance = _edit_distance(key, token)
                limit = 1 if len(key) <= 4 else 2
                if distance > limit:
                    continue
                score = distance
            best = score if best is None else min(best, score)
        if best is not None:
            scored.append((best, name))
    scored.sort(key=lambda item: (item[0], item[1]))
    if not scored:
        return ()
    # A short garbled target («team», «ste») may stand for two names one edit
    # apart (Teams/Steam); a longer one keeps only its closest names.
    best = scored[0][0]
    tolerance = 1 if len(key) <= 4 else 0
    names = []
    for score, name in scored:
        if score <= best + tolerance and name not in names:
            names.append(name)
    return tuple(names[:2])


_NEAR_GAME_ORDER = re.compile(
    r"^[\s¡!¿?]*(?:abre|abri|abrime|abris|lanza|lanzame|inicia|iniciame|pone|pon|poneme|juga|jugar\s+a|jugar|"
    r"ve\s+a|anda\s+a|andate\s+a|entra\s+a|vamos\s+a|open|launch|play|go\s+to|start)\s+"
    r"(?:(?:el|la|los|las|the|a|al)\s+)?(?P<target>[a-z0-9][a-z0-9 .'+-]{1,40}?)[\s.!?,]*$"
)


def near_catalog_game_candidates(
    text: str,
    games: Iterable[tuple[str, str, str]] | GameCatalogIndex,
) -> tuple[str, ...]:
    """GAMES1533 «Ve a Mad de Rivals.»: the installed game names (at most two)
    that an open, launch or go-to order almost names — a word of five or more
    letters shared with the title, or the whole target one or two edits away —
    when the target matches no game exactly. Empty for anything else."""

    index = build_game_catalog_index(games)
    if not index.entries:
        return ()
    folded = _strip_request_envelope(_fold(text))
    if not folded or _has(folded, r"\b(?:no|nunca|jamas|never|don't|do\s+not)\b|\b(?:si|if|cuando|when)\b.{0,20}\b(?:termine|acabe|finish)\b"):
        return ()
    folded = re.sub(r"^(?:si|ok|dale|bueno|y|and)\s*[,.]?\s*(?:quema\s*,?\s*)?", "", folded, count=1).strip()
    request = _NEAR_GAME_ORDER.match(folded)
    if request is None:
        return ()
    target = request.group("target").strip(" ¿?¡!,:;.-")
    target = re.sub(r"\s*,?\s*(?:por\s+favor|porfa|please|pls)$", "", target).strip(" ,.")
    key = _entity_key(target)
    if not key or len(key) < 3 or len(key.split()) > 3:
        return ()
    if key in {"eso", "esto", "aquello", "ese", "esa", "este", "esta", "algo", "todo", "that", "this", "it"}:
        # «abrí eso» is a deictic, never a near miss of a short title (DSX).
        return ()
    if any(entry[0] == key for entry in index.entries):
        return ()
    target_tokens = {token for token in key.split() if len(token) >= 5}
    scored: list[tuple[int, str]] = []
    for normalized, _provider, _app_id, display in index.entries:
        name_tokens = set(normalized.split())
        if target_tokens & name_tokens:
            score = 0
        else:
            if len(key) < 5:
                continue
            distance = _edit_distance(key, normalized)
            if distance > 2:
                continue
            score = distance
        scored.append((score, display))
    scored.sort(key=lambda item: (item[0], item[1]))
    names: list[str] = []
    for score, name in scored:
        if score <= scored[0][0] and name not in names:
            names.append(name)
    return tuple(names[:2])


def _application_target_forms(
    raw_target: str,
) -> tuple[tuple[str, int], ...]:
    """Return bounded exact-name candidates before stripping request wrappers."""

    punctuation_forms: list[str] = []
    candidate = raw_target.strip()
    if candidate:
        punctuation_forms.append(candidate)
    for _ in range(8):
        compact = candidate.rstrip()
        if not compact or compact[-1] not in "?!.":
            break
        candidate = compact[:-1].rstrip()
        if candidate and candidate not in punctuation_forms:
            punctuation_forms.append(candidate)
    without_punctuation = raw_target.rstrip(" ?!.")
    if without_punctuation and without_punctuation not in punctuation_forms:
        punctuation_forms.append(without_punctuation)

    execution_hint = re.compile(
        r"\s+(?:(?:con\s+)?maximo\s+\d+\s+intentos?|[0-2])$",
        re.IGNORECASE,
    )
    wrapper = re.compile(
        (
            r"^(?:(?:el|la|los|las|un|una|the|a|an)\s+)?"
            r"(?:(?:aplicacion|application|app|programa|program)\s+)?"
        ),
        re.IGNORECASE,
    )
    forms: list[tuple[str, int]] = []
    for punctuation_form in punctuation_forms:
        bases = [punctuation_form]
        without_trailing = _APPLICATION_TRAILING_REQUEST.sub("", punctuation_form).rstrip()
        if without_trailing and without_trailing != punctuation_form:
            bases.append(without_trailing)
        without_execution_hint = execution_hint.sub("", punctuation_form).rstrip()
        if (
            without_execution_hint
            and without_execution_hint != punctuation_form
            and without_execution_hint not in bases
        ):
            bases.append(without_execution_hint)
        for base in bases:
            if (base, 0) not in forms:
                forms.append((base, 0))
            wrapped = wrapper.match(base)
            if wrapped is None or wrapped.end() <= 0:
                continue
            unwrapped = base[wrapped.end() :].strip()
            if unwrapped and (unwrapped, wrapped.end()) not in forms:
                forms.append((unwrapped, wrapped.end()))
    return tuple(forms)


_CATALOG_NAME_ALIASES: tuple[tuple[frozenset[str], tuple[str, ...]], ...] = (
    (frozenset({"calc", "calculator", "calculadora"}), ("calculadora", "calculator")),
    (frozenset({"notepad", "bloc de notas", "app de notas", "coso de notas",
                "editor de texto"}), ("bloc de notas", "notepad")),
    (frozenset({"explorador", "explorador de archivos", "explorador de windows",
                "file explorer", "files explorer", "explorer", "windows explorer"}),
     ("explorador de archivos", "file explorer")),
    # UI1731 «Abre Epic Games y navega hasta la biblioteca»: the Start catalog
    # names the client «Epic Games Launcher»; people say «Epic Games» or «Epic».
    (frozenset({"epic", "epic games", "epic launcher", "epic games launcher", "launcher de epic"}),
     ("epic games launcher",)),
    # UI1735 «en Opera hacé clic en …»: the Start catalog names the browser
    # «Navegador Opera GX»; people say «Opera» or «Opera GX».
    (frozenset({"opera", "opera gx", "navegador opera", "navegador opera gx", "opera browser"}),
     ("navegador opera gx", "opera gx", "opera")),
)


def _catalog_alias_key(target_key: str, keys: frozenset[str]) -> str | None:
    """Map a bilingual alias to the one catalog key it names, if installed."""

    if target_key in keys:
        return target_key
    for aliases, catalog_names in _CATALOG_NAME_ALIASES:
        if target_key in aliases:
            for name in catalog_names:
                if name in keys:
                    return name
    return None


def _indexed_authenticated_application_target(
    text: str,
    catalog: ApplicationCatalogIndex,
    *,
    installed_query: bool,
) -> tuple[int, str] | None:
    """Resolve one anchored target with bounded parsing and indexed lookup."""

    polite = (
        r"(?:(?:por favor|please)\s*[,;:]?\s*|"
        r"(?:puedes|podrias|can you|could you|would you)\s+)?"
    )
    trailing = (
        r"(?:\s*[,;:]?\s+(?:por favor|please|para mi|for me|ahora|now|"
        r"dale|porfa|porfi|porfis|pls|plz))?"
        r"[\s?!.]*$"
    )
    if installed_query:
        patterns = (
            (
                r"^[¿?¡!\s]*(?:esta|estan|is|are)\s+"
                r"(?:instalad[oa]s?|installed)\s+"
                r"(?P<target>.+)$"
            ),
            (
                r"^[¿?¡!\s]*(?:esta|estan|is|are)\s+"
                r"(?P<target>.+)\s+"
                rf"(?:instalad[oa]s?|installed){trailing}"
            ),
        )
    else:
        patterns = (
            (
                rf"^[¿?¡!\s]*{polite}(?:me\s+)?{_OPEN}\b\s+"
                r"(?P<target>.+)$"
            ),
        )
    matches: list[tuple[int, str]] = []
    for pattern in patterns:
        request = _match(text, pattern)
        if request is None or _is_negated_match(text, request):
            continue
        for target, offset in _application_target_forms(
            request.group("target"),
        ):
            target_key = _catalog_alias_key(_application_name_key(target), catalog.keys)
            if target_key is not None:
                matches.append((request.start("target") + offset, target_key))
    if not matches:
        return None if installed_query else _repeated_application_target(text, catalog)
    return min(
        matches,
        key=lambda item: (-len(item[1]), item[1], item[0]),
    )


def _authenticated_application_target(
    text: str,
    application_names: Iterable[str] | ApplicationCatalogIndex,
    *,
    installed_query: bool = False,
) -> tuple[int, str] | None:
    """Match an anchored app request against the OS-authenticated catalog."""

    return _indexed_authenticated_application_target(
        text,
        build_application_catalog_index(application_names),
        installed_query=installed_query,
    )


def _application_desire_is_positive(folded: str) -> bool:
    """Keep the existing desired-open exclusions on the complete request."""

    return not (
        _is_negative_effect_clause(folded)
        or _is_meta_or_tool_denial(folded)
        or _has_contradictory_correction(folded)
        or _has_unsupported_deferred_effect(folded)
        or _is_past_or_hypothetical_state(folded)
        or _has(
            folded,
            r"\b(?:on|en)\s+(?:my|mi|the|el|la)?\s*"
            r"(?:phone|telefono|movil|celular|tablet|ipad|iphone|console|consola)\b",
        )
    )


def _application_open_request(text: str) -> re.Match[str] | None:
    """Extract an ordinary or positive desired opening without resolving identity."""

    request = _match(
        text,
        (
            r"^[¿?¡!\s]*(?:(?:(?:por favor|please)\s*[,;:]?\s*|"
            r"(?:puedes|podrias|can you|could you|would you)\s+)?"
            rf"(?:me\s+)?{_OPEN}\b|"
            r"(?P<desire>(?:(?:i|we)\s+(?:need|want)\s+(?:you\s+)?to|"
            r"(?:i|we)\s+would\s+like\s+(?:you\s+)?to)\s+"
            r"(?:open|start|launch)|"
            r"(?:necesito|quiero|quisiera)\s+que\s+"
            r"(?:abras|abran|inicies|inicien|lances|lancen)))\s+"
            r"(?P<target>.+)$"
        ),
    )
    if request is not None and request.group("desire") is not None:
        if not _application_desire_is_positive(text):
            return None
    return request


def resolve_application_catalog_app_id(
    text: str,
    application_names: Iterable[str] | ApplicationCatalogIndex,
) -> str | None:
    """Resolve one conservative provider input from the authenticated snapshot."""

    catalog = build_application_catalog_index(application_names)
    folded = _strip_request_envelope(_fold(text))
    target = _authenticated_application_target(folded, catalog)
    if target is None:
        target = _authenticated_application_desired_open(folded, catalog)
    if target is not None:
        matches = [entry for entry in catalog.entries if entry[1] == target[1]]
        return matches[0][0] if len(matches) == 1 else None

    request = _application_open_request(folded)
    raw_target = request.group("target") if request is not None else folded
    forms = _application_target_forms(raw_target)
    if request is not None and request.group("desire") is not None:
        occurrence = catalog.occurrence_pattern
        if occurrence is not None and len(list(occurrence.finditer(folded))) > 1:
            return None
        # Alias resolution must retain the desired-open suffix boundary too.
        forms = tuple(
            (form, offset)
            for form, offset in forms
            if raw_target[offset + len(form) :].strip(" ¿?¡!,:;.-")
            in {"", "por favor", "porfa", "please", "dale", "pls"}
        )
    keys = tuple(
        dict.fromkeys(
            _application_name_key(form)
            for form, _ in forms
            if _application_name_key(form)
        )
    )
    if not keys:
        return None

    notepad_aliases = {
        "app de notas",
        "bloc de notas",
        "coso de notas",
        "editor de texto",
        "notepad",
    }
    calculator_aliases = {"calc", "calculadora", "calculator"}
    settings_aliases = {
        "configuracion",
        "configuracion de windows",
        "configuraciones de windows",
        "windows settings",
    }
    catalog_keys = {key for _, key in catalog.entries}
    for key in keys:
        if key in notepad_aliases and catalog_keys & {"bloc de notas", "notepad"}:
            return "windows.notepad"
        if key in calculator_aliases and catalog_keys & {"calculadora", "calculator"}:
            return "windows.calculator"
        alias_key = _catalog_alias_key(key, frozenset(catalog_keys))
        if alias_key is not None and alias_key != key:
            matches = [name for name, candidate_key in catalog.entries if candidate_key == alias_key]
            if len(matches) == 1:
                return matches[0]
        if key in settings_aliases:
            matches = [
                name
                for name, candidate_key in catalog.entries
                if candidate_key in {"configuracion", "windows settings"}
            ]
            if len(matches) == 1:
                return matches[0]

    for key in keys:
        exact = [
            name for name, candidate_key in catalog.entries if candidate_key == key
        ]
        if len(exact) == 1:
            return exact[0]
        query_tokens = set(_entity_key(key).split())
        if not query_tokens:
            continue
        ranked: list[tuple[int, str]] = []
        for name, _ in catalog.entries:
            candidate_tokens = set(_entity_key(name).split())
            if query_tokens <= candidate_tokens:
                score = 90 - min(6, len(candidate_tokens) - len(query_tokens))
                ranked.append((score, name))
        ranked.sort(key=lambda item: (-item[0], _application_name_key(item[1])))
        if not ranked:
            continue
        if len(ranked) > 1 and ranked[0][0] - ranked[1][0] < 8:
            continue
        return ranked[0][1]
    return None


def _authenticated_application_close_target(
    text: str,
    application_names: Iterable[str] | ApplicationCatalogIndex,
) -> tuple[int, str] | None:
    """Recognize one complete close request over an exact authenticated name.

    This supplies intent/domain evidence only: process/window identity still
    comes from window.resolve and the existing exact confirmation contract.
    """
    if (
        not effect_request_is_authoritative(text)
        or _has_unsupported_deferred_effect(_fold(text))
        or _other_device_effect_scope(_fold(text))
    ):
        return None
    # «necesito que cierres whatsapp», «podés cerrar la calculadora?»,
    # «cerrame el paint»: the desire/ability preface and the clitic still
    # ask for one close. The envelope already removes «puedes/could you».
    request = _match(
        _strip_request_envelope(_fold(text)),
        r"^[¿?¡!\s]*(?:(?:necesito|quiero|queria|quisiera|podes|podrias|podria|me\s+(?:podes|podrias|podria))\s+(?:que\s+)?)?"
        r"(?:cierra|cierres|cerra|cerrar|cerrame|close)\s+(?P<target>.+)$",
    )
    if request is None:
        return None
    catalog = build_application_catalog_index(application_names)
    raw_target = request.group("target")
    matches: list[tuple[int, str]] = []
    for target, offset in _close_target_forms(raw_target):
        # Do not inherit open's execution-count hints for a work-loss effect.
        # Only punctuation, the window wrapper's own tail («… window», «… app»)
        # and the existing bounded courtesy are removable.
        suffix = raw_target[offset + len(target):].strip(" ,;:.!?")
        suffix = re.sub(r"^(?:window|app|application)\b", "", suffix).strip(" ,;:.!?")
        if suffix and _APPLICATION_TRAILING_REQUEST.fullmatch(" " + suffix) is None \
                and _CLOSE_TRAILING_COURTESY.fullmatch(" " + suffix) is None:
            continue
        key = _authenticated_close_key(target, catalog)
        if key is not None:
            matches.append((request.start("target") + offset, key))
    identities = {key for _, key in matches}
    if len(identities) != 1:
        return None
    return min(matches, key=lambda item: item[0])


_CLOSE_WINDOW_WRAPPER = re.compile(
    r"^(?:(?:la|el|the)\s+)?(?:ventana|window|app|aplicacion|programa|application|program)\s+(?:de|del|of)\s+(?P<name>.+)$"
    r"|^(?:the\s+)?(?P<name_before>.+?)\s+(?:window|app|application)$",
    re.IGNORECASE,
)
_CLOSE_TRAILING_COURTESY = re.compile(r"\s*[,;:]?\s+(?:pls|plis|porfa|porfis|for me|para mi)$", re.IGNORECASE)


def _close_target_forms(raw_target: str) -> tuple[tuple[str, int], ...]:
    """Bounded close-target forms: the open forms plus «la ventana de X» / «the X window».

    Offsets index the original target so trailing-courtesy checks stay exact.
    """
    forms = list(_application_target_forms(raw_target))
    stripped = raw_target.rstrip(" ?!.")
    courtesy = _CLOSE_TRAILING_COURTESY.search(stripped)
    if courtesy is not None:
        core = stripped[:courtesy.start()]
        forms.extend((form, offset) for form, offset in _application_target_forms(core))
    for form, offset in list(forms):
        wrapped = _CLOSE_WINDOW_WRAPPER.fullmatch(form)
        if wrapped is None:
            continue
        name = wrapped.group("name") or wrapped.group("name_before")
        start = wrapped.start("name") if wrapped.group("name") else wrapped.start("name_before")
        forms.extend((inner, offset + start + inner_offset) for inner, inner_offset in _application_target_forms(name))
    return tuple(dict.fromkeys(forms))


def _authenticated_close_key(target: str, catalog: ApplicationCatalogIndex) -> str | None:
    """Resolve one target form to an exact catalog key, through the shared alias resolver.

    «chrome» → Google Chrome and «notepad» → Bloc de notas reuse the same
    identity resolver the presence reader trusts; anything ambiguous or
    outside the authenticated snapshot stays None.
    """
    key = _application_name_key(target)
    if key in catalog.keys:
        return key
    resolved = resolve_application_catalog_app_id(target, catalog)
    if resolved is None:
        return None
    builtin = {"windows.notepad": ("bloc de notas", "notepad"),
               "windows.calculator": ("calculadora", "calculator")}
    candidates = [name for name, candidate in catalog.entries
                  if candidate == _application_name_key(resolved) or candidate in builtin.get(resolved, ())]
    keys = {_application_name_key(name) for name in candidates}
    return next(iter(keys)) if len(keys) == 1 else None


_DEICTIC_CLOSE_REQUEST = re.compile(
    r"^[¿?¡!\s]*(?:"
    r"(?:cierra|cerra|cerrar|cerrame|cierrame|close)\s+"
    r"(?:"
    r"(?:(?:la|the|esta|this|esa|that)\s+)?(?:ventana|window)\s+(?:activa|active|actual|current)|"
    r"(?:the\s+)?(?:active|current|foreground|front)\s+window|"
    r"(?:esta|this|esa|that)\s+(?:ventana|window)|"
    r"(?:la\s+)?ventana\s+(?:que\s+(?:esta|tengo)\s+)?(?:en\s+)?(?:primer\s+plano|adelante|al\s+frente)|"
    r"(?:the\s+)?window\s+(?:in\s+front|in\s+the\s+foreground|on\s+top)|"
    r"esto|eso|this|that|it"
    r")|"
    r"cierrala|cierralo|cerrala|cerralo|close\s+it"
    r")[\s?!.]*$",
    re.IGNORECASE,
)


_DEICTIC_WINDOW_MUTATION = re.compile(
    r"^[¿?¡!\s]*(?:maximiza|maximizar|maximize|minimiza|minimizar|minimize|"
    r"restaura|restaurar|restore)(?:me|la|lo)?\s+"
    r"(?:"
    r"(?:(?:la|the|esta|this|esa|that)\s+)?(?:ventana|window)"
    r"(?:\s+(?:activa|active|actual|current))?|"
    r"(?:the\s+)?(?:active|current|foreground|front)\s+window|"
    r"(?:la\s+)?ventana\s+(?:que\s+(?:esta|tengo)\s+)?(?:en\s+)?"
    r"(?:primer\s+plano|adelante|al\s+frente)|"
    r"(?:the\s+)?window\s+(?:in\s+front|in\s+the\s+foreground|on\s+top)"
    r")[\s?!.]*$",
    re.IGNORECASE,
)


def deictic_window_mutation(folded: str) -> bool:
    """«maximizá esta ventana», «minimize the window»: change the window in front.

    A maximize/minimize/restore whose only referent is «la ventana», «esta
    ventana» or the foreground window binds window.active, never a window
    inventory from which some other window could be chosen. A named window
    («la ventana de Chrome») keeps its named resolution.
    """

    return _DEICTIC_WINDOW_MUTATION.match(folded) is not None


def deictic_close_request(folded: str) -> bool:
    """«cerrá esta ventana», «cerrala», «close the active window»: close what is in front.

    The referent is the foreground window, which window.active observes and
    the reviewed confirmation names before anything closes. A referent from
    earlier dialogue («la que te mencioné antes») is not deictic here.
    """

    return _DEICTIC_CLOSE_REQUEST.match(folded) is not None


_FOCUS_HEAD_ONLY = r"(?:enfoca|enfocame|enfocar|focus|switch\s+to|cambia\s+a|cambiame\s+a)"
_FOCUS_HEAD_WITH_TAIL = (
    r"(?:trae|traeme|traer|pone|poneme|pon|ponme|poner|lleva|llevame|llevar|"
    r"activa|activame|mostra|mostrame|muestra|muestrame|bring|show|put)"
)
_FOCUS_TAIL = (
    r"(?:al\s+frente|adelante|al\s+primer\s+plano|en\s+primer\s+plano|"
    r"to\s+the\s+front|forward|in\s+front|up\s+front)"
)


def _authenticated_application_focus_target(
    text: str,
    application_names: Iterable[str] | ApplicationCatalogIndex,
) -> tuple[int, str] | None:
    """Recognize one request to bring an authenticated application to the front.

    WINDOWS1385 «traé chrome al frente», «enfocá chrome», «bring Chrome to
    the front»: a focus-only head, or a carry/put head with the front tail,
    over one exact catalog identity. Window identity still comes from
    window.resolve; an absent window ends there truthfully.
    """
    if (
        not effect_request_is_authoritative(text)
        or _has_unsupported_deferred_effect(_fold(text))
        or _other_device_effect_scope(_fold(text))
    ):
        return None
    folded = _strip_request_envelope(_fold(text))
    request = _match(
        folded,
        rf"^[¿?¡!\s]*(?:(?:necesito|quiero|queria|quisiera|podes|podrias|podria|me\s+(?:podes|podrias|podria))\s+(?:que\s+)?)?"
        rf"(?:{_FOCUS_HEAD_ONLY}\s+(?:(?:me|a)\s+)?(?P<target_a>.+?)(?:\s+{_FOCUS_TAIL})?"
        rf"|{_FOCUS_HEAD_WITH_TAIL}\s+(?:(?:me|a)\s+)?(?P<target_b>.+?)\s+{_FOCUS_TAIL})[\s.!?]*$",
    )
    if request is None:
        return None
    group = "target_a" if request.group("target_a") is not None else "target_b"
    raw_target = request.group(group)
    catalog = build_application_catalog_index(application_names)
    matches: list[tuple[int, str]] = []
    for target, offset in _close_target_forms(raw_target):
        suffix = raw_target[offset + len(target):].strip(" ,;:.!?")
        suffix = re.sub(r"^(?:window|app|application)\b", "", suffix).strip(" ,;:.!?")
        if suffix and _APPLICATION_TRAILING_REQUEST.fullmatch(" " + suffix) is None \
                and _CLOSE_TRAILING_COURTESY.fullmatch(" " + suffix) is None:
            continue
        key = _authenticated_close_key(target, catalog)
        if key is not None:
            matches.append((request.start(group) + offset, key))
    identities = {key for _, key in matches}
    if len(identities) != 1:
        return None
    return min(matches, key=lambda item: item[0])


def resolve_application_focus_name(
    text: str,
    application_names: Iterable[str] | ApplicationCatalogIndex,
) -> str | None:
    """Preserve an authenticated focus target as a catalog display name."""
    catalog = build_application_catalog_index(application_names)
    target = _authenticated_application_focus_target(text, catalog)
    if target is None:
        return None
    names = {name for name, key in catalog.entries if key == target[1]}
    return next(iter(names)) if len(names) == 1 else None


_MINIMIZE_HEAD = r"(?:minimiza|minimizame|minimizar|minimise|minimize|minimisa|minimisame)"


def _authenticated_application_minimize_target(
    text: str,
    application_names: Iterable[str] | ApplicationCatalogIndex,
) -> tuple[int, str] | None:
    """Recognize one request to minimize an authenticated application by name.

    WINDOWS1695 H0697 «Minimisa ópera.»: a minimize head (the colloquial
    «minimisa» spelling included) over one exact catalog identity, with no
    «ventana» noun; window.resolve (the prerequisite) binds the window and an
    absent one ends there truthfully. «minimizá todo» stays with the desktop
    reader; a deictic «esta ventana» stays with window.active.
    """
    if (
        not effect_request_is_authoritative(text)
        or _has_unsupported_deferred_effect(_fold(text))
        or _other_device_effect_scope(_fold(text))
    ):
        return None
    folded = _strip_request_envelope(_fold(text))
    request = _match(
        folded,
        rf"^[¿?¡!\s]*(?:(?:necesito|quiero|queria|quisiera|podes|podrias|podria|me\s+(?:podes|podrias|podria))\s+(?:que\s+)?)?"
        rf"{_MINIMIZE_HEAD}\s+(?:(?:me|a)\s+)?(?P<target>.+?)[\s.!?]*$",
    )
    if request is None:
        return None
    raw_target = request.group("target")
    if _has(raw_target, r"\b(?:ventana|ventanas|window|windows|todo|todas|everything|all)\b"):
        return None
    catalog = build_application_catalog_index(application_names)
    matches: list[tuple[int, str]] = []
    for target, offset in _close_target_forms(raw_target):
        suffix = raw_target[offset + len(target):].strip(" ,;:.!?")
        suffix = re.sub(r"^(?:window|app|application)\b", "", suffix).strip(" ,;:.!?")
        if suffix and _APPLICATION_TRAILING_REQUEST.fullmatch(" " + suffix) is None                 and _CLOSE_TRAILING_COURTESY.fullmatch(" " + suffix) is None:
            continue
        key = _authenticated_close_key(target, catalog)
        if key is not None:
            matches.append((request.start("target") + offset, key))
    identities = {key for _, key in matches}
    if len(identities) != 1:
        return None
    return min(matches, key=lambda item: item[0])


def resolve_application_minimize_name(
    text: str,
    application_names: Iterable[str] | ApplicationCatalogIndex,
) -> str | None:
    """Preserve an authenticated minimize target as a catalog display name."""
    catalog = build_application_catalog_index(application_names)
    target = _authenticated_application_minimize_target(text, catalog)
    if target is None:
        return None
    names = {name for name, key in catalog.entries if key == target[1]}
    return next(iter(names)) if len(names) == 1 else None


_SNAP_HEAD = (
    r"(?:pon|pone|poneme|poner|ponla|ponlo|mueve|mover|moveme|muevela|muevelo|lleva|llevame|llevar|"
    r"coloca|colocame|colocar|acomoda|acomodame|acomodar|arrastra|arrastrame|arrastrar|"
    r"put|move|snap|dock|place|drag)"
)
_SNAP_SIDE = (
    r"(?P<side>(?:a|hacia|en|para)\s+(?:la\s+)?(?:mitad\s+)?(?:izquierda|derecha)(?:\s+de\s+la\s+pantalla)?|"
    r"(?:on|to|at)\s+the\s+(?:left|right)(?:\s+(?:side|half))?(?:\s+of\s+the\s+screen)?|"
    r"(?:left|right))"
)


def _authenticated_application_snap_target(
    text: str,
    application_names: Iterable[str] | ApplicationCatalogIndex,
) -> tuple[int, str, str] | None:
    """Recognize one request to dock an authenticated application on a side.

    ARRANGE1781 H0268 «poné chrome a la izquierda»: a placing head over one
    exact catalog identity followed by a side («a la izquierda/derecha»,
    «to the left/right»); window.resolve binds the window and window.snap
    docks it on that half of its monitor. «la ventana de chrome» names the
    same window; «esta ventana» stays with window.active.
    """
    if (
        not effect_request_is_authoritative(text)
        or _has_unsupported_deferred_effect(_fold(text))
        or _other_device_effect_scope(_fold(text))
    ):
        return None
    folded = _strip_request_envelope(_fold(text))
    request = _match(
        folded,
        rf"^[¿?¡!\s]*(?:(?:necesito|quiero|queria|quisiera|podes|podrias|podria|me\s+(?:podes|podrias|podria))\s+(?:que\s+)?)?"
        rf"{_SNAP_HEAD}\s+(?:(?:me|a)\s+)?(?P<target>.+?)\s+{_SNAP_SIDE}[\s.!?]*$",
    )
    if request is None:
        return None
    raw_target = request.group("target")
    if _has(raw_target, r"\b(?:esta|this|esa|that|todo|todas|everything|all|activa|active|actual|current)\b"):
        return None
    side = "left" if _has(request.group("side"), r"\b(?:izquierda|left)\b") else "right"
    catalog = build_application_catalog_index(application_names)
    matches: list[tuple[int, str]] = []
    for target, offset in _close_target_forms(raw_target):
        key = _authenticated_close_key(target, catalog)
        if key is not None:
            matches.append((request.start("target") + offset, key))
    identities = {key for _, key in matches}
    if len(identities) != 1:
        return None
    offset, key = min(matches, key=lambda item: item[0])
    return (offset, key, side)


def resolve_application_snap(
    text: str,
    application_names: Iterable[str] | ApplicationCatalogIndex,
) -> tuple[str, str] | None:
    """The authenticated snap target as (catalog display name, side)."""
    catalog = build_application_catalog_index(application_names)
    target = _authenticated_application_snap_target(text, catalog)
    if target is None:
        return None
    names = {name for name, key in catalog.entries if key == target[1]}
    return (next(iter(names)), target[2]) if len(names) == 1 else None


def resolve_application_snap_name(
    text: str,
    application_names: Iterable[str] | ApplicationCatalogIndex,
) -> str | None:
    """Preserve an authenticated snap target as a catalog display name."""
    resolved = resolve_application_snap(text, application_names)
    return resolved[0] if resolved is not None else None


def resolve_application_close_name(
    text: str,
    application_names: Iterable[str] | ApplicationCatalogIndex,
) -> str | None:
    """Preserve an authenticated close target as a catalog display name."""
    catalog = build_application_catalog_index(application_names)
    target = _authenticated_application_close_target(text, catalog)
    if target is None:
        return None
    names = {name for name, key in catalog.entries if key == target[1]}
    return next(iter(names)) if len(names) == 1 else None


def _repeated_application_target(
    text: str,
    catalog: ApplicationCatalogIndex,
) -> tuple[int, str] | None:
    """Resolve a uniform whole-target repetition through one catalog identity."""

    folded = _strip_request_envelope(_fold(text))
    if len(folded) > 16_384 or not _application_desire_is_positive(folded):
        return None
    request = _application_open_request(folded)
    if (
        request is None
        or _is_negated_match(folded, request)
        or len(_request_clauses(folded)) != 1
    ):
        return None
    matches: set[tuple[int, str]] = set()
    for target, offset in _application_target_forms(request.group("target")):
        repeated = re.fullmatch(r"(?P<unit>.+?)(?:\s+(?P=unit))+", target)
        if repeated is None:
            continue
        unit = repeated.group("unit")
        tokens = set(unit.split())
        identities = [
            (name, key) for name, key in catalog.entries
            if tokens and tokens <= set(key.split())
        ]
        if len(identities) != 1:
            continue
        name, key = identities[0]
        # Exact complete tokens and unique membership constrain the existing
        # resolver; no similarity winner, alias or first-token guess is added.
        resolved = resolve_application_catalog_app_id(unit, catalog)
        if resolved is not None and resolved == resolve_application_catalog_app_id(name, catalog):
            matches.add((request.start("target") + offset, key))
    if len({key for _, key in matches}) != 1:
        return None
    return min(matches)


def resolve_application_window_status_name(
    text: str,
    application_names: Iterable[str] | ApplicationCatalogIndex,
) -> str | None:
    """Resolve a named visible-window question against the app snapshot.

    A foreground snapshot cannot establish absence of other windows. Conversely,
    visible windows do not establish background process liveness. Keep this read
    bounded to presence/count questions about one authenticated application; the
    model still owns other formulations and unresolved application identities.
    """
    catalog = build_application_catalog_index(application_names)
    folded = _strip_request_envelope(_fold(text)).strip(" ¿?¡!.")
    folded = _strip_request_envelope(folded).strip(" ¿?¡!.")
    if _other_device_effect_scope(folded):
        return None
    folded = re.sub(r"\s+(?:por favor|please|ahora|now)$", "", folded)
    # «está corriendo spotify», «tengo discord abierto» (WINDOWS1207): running
    # and «tengo … abierto» are presence questions about one application.
    state = r"(?:abiert[oa]|cerrad[oa]|open|closed|corriendo|running|ejecutandose|activ[oa])"
    inquiry = (
        r"(?:(?:comprueba|revisa|verifica|confirma|averigua|dime)\s+si|"
        r"(?:check|verify|confirm|see|find out|tell me)\s+(?:if|whether))\s+"
    )
    patterns = (
        rf"(?:esta|is)\s+(?P<target>.+?)\s+{state}",
        rf"esta\s+{state}\s+(?P<target>.+?)",
        rf"tengo\s+(?:(?:el|la|a)\s+)?(?P<target>.+?)\s+{state}",
        rf"do\s+i\s+have\s+(?P<target>.+?)\s+{state}",
        rf"{inquiry}(?P<target>.+?)\s+(?:esta|is)\s+{state}",
        rf"{inquiry}esta\s+{state}\s+(?P<target>.+?)",
        r"hay\s+(?:(?:alguna|una)\s+)?ventana\s+de\s+"
        r"(?P<target>.+?)\s+abierta",
        r"are\s+(?:any\s+)?windows\s+of\s+(?P<target>.+?)\s+open",
        r"how\s+many\s+windows\s+of\s+(?P<target>.+?)\s+are\s+open",
        r"how\s+many\s+(?P<target>.+?)\s+windows\s+are\s+open",
        r"cuantas\s+ventanas\s+de\s+(?P<target>.+?)\s+estan\s+abiertas",
    )
    for pattern in patterns:
        match = re.fullmatch(pattern, folded)
        if match is None:
            continue
        target = match.group("target")
        # Reuse the catalog's identity resolver, never a vocabulary of app
        # names. Its aliases are also understood by the status provider.
        # Whole-target forms prevent an extra clause becoming part of a name.
        for form, _ in _application_target_forms(target):
            key = _application_name_key(form)
            exact = [name for name, candidate in catalog.entries if candidate == key]
            if len(exact) == 1:
                return exact[0]
        return resolve_application_catalog_app_id(target, catalog)
    return None


def resolve_application_window_followup_name(
    text: str,
    previous_requests: Iterable[str],
    application_names: Iterable[str] | ApplicationCatalogIndex,
) -> str | None:
    """Resolve one bounded read reference from user questions, never answers.

    A new or unresolved subject ends the chain. Previous commands cannot
    authorize an elliptical read, and assistant assertions cannot establish
    the application's identity or its current state.
    """
    catalog = build_application_catalog_index(application_names)

    def followup(request: str, previous: str | None) -> str | None:
        if previous is None:
            return None
        folded = _strip_request_envelope(_fold(request)).strip(" ¿?¡!.")
        folded = re.sub(r"\s+(?:por favor|please|ahora|now)$", "", folded)
        named = re.fullmatch(
            r"(?:y|and|what\s+about|how\s+about|que\s+hay\s+de)\s+(.+)", folded,
        )
        if named is not None:
            # Reuse the same whole-target catalog resolution as a full query.
            return resolve_application_window_status_name(
                f"is {named.group(1)} open", catalog,
            )
        entity = r"(?:es[ae]|est[ae])\s+(?:aplicacion|app|programa)"
        state = r"(?:abiert[oa]|cerrad[oa])"
        if re.fullmatch(
            rf"(?:is\s+(?:it|(?:this|that)\s+(?:app|application|program))\s+"
            rf"(?:still\s+)?(?:open|closed)|"
            rf"esta\s+(?:{entity}\s+{state}|{state}\s+{entity})|"
            rf"{entity}\s+tiene\s+(?:alguna|una)\s+ventana\s+abierta)",
            folded,
        ):
            return previous
        return None

    reference: str | None = None
    for request in previous_requests:
        reference = (
            resolve_application_window_status_name(request, catalog)
            or followup(request, reference)
        )
    return followup(text, reference)


def unresolved_application_open_name(
    text: str,
    application_names: Iterable[str] | ApplicationCatalogIndex,
    *,
    proper_name: bool = False,
) -> str | None:
    """Bind a literal app name for a presence read, never an opening fallback.

    ``proper_name`` also admits a capitalized bare name (APPS1549); the caller
    must first rule out games, near catalog names and public sites.
    """

    folded = _fold(text)
    if not folded or len(folded) > 16_384:
        return None
    # APPS1671 H0322 «quiero editar una foto en photoshop»: wanting to work in
    # a known program names the program; when the verified catalog does not
    # hold it, the presence read answers by its absence. Only the use-to-do
    # frame, only known software, never a catalog application (that stays a
    # real opening request for the other readers).
    use = re.fullmatch(
        r"[¿?¡!\s]*(?:(?:por\s+favor|please)\s*[,;:]?\s*)?"
        r"(?:quiero|querria|necesito|me\s+gustaria|tengo\s+que|i\s+want\s+to|i\s+need\s+to|i\'?d\s+like\s+to)\s+"
        r"(?:editar|retocar|usar|trabajar|edit|retouch|use|work)\s+(?:.{0,60}?\s+)?"
        rf"(?:en|con|in|with|on)\s+(?:(?:el|la|the)\s+)?(?P<name>{_KNOWN_SOFTWARE})"
        r"(?:\s*,?\s*(?:por\s+favor|please))?[\s.!?]*",
        folded,
    )
    if (
        use is not None
        and not proper_name
        and resolve_application_catalog_app_id(text, application_names) is None
        and resolve_application_catalog_app_id("abre " + use.group("name"), application_names) is None
    ):
        name_words = len(use.group("name").split())
        trimmed = _APPLICATION_TRAILING_REQUEST.sub("", text.rstrip(" ?!.")).rstrip()
        raw_name = " ".join(trimmed.split()[-name_words:])
        return _bounded_application_literal(raw_name)
    source = folded
    request = (
        _application_open_request(folded)
        if _application_desire_is_positive(folded) else None
    )
    if request is None:
        # «no, mejor abrí firefox»: a rectification or courtesy envelope precedes
        # the opening; the envelope grammar is the shared one, and the desire is
        # read on the request it wraps.
        stripped = _strip_request_envelope(folded)
        if stripped != folded and _application_desire_is_positive(stripped):
            source = stripped
            request = _application_open_request(stripped)
    if request is None or _is_negated_match(source, request):
        return None
    # An explicit application noun establishes the domain without guessing
    # whether an unfamiliar bare name denotes an app, file, site or game.
    wrapper = _match(
        request.group("target"),
        r"^(?:(?:el|la|un|una|the|a|an)\s+)?"
        r"(?:aplicacion|application|app|programa|program)\s+",
    )
    # Folding proves grammar only. Recover the original tokens for the read
    # so the provider receives the person's name, including case and accents.
    target_words = len(request.group("target").split())
    raw_target = " ".join(text.split()[-target_words:])
    if wrapper is None and build_application_catalog_index(application_names).entries:
        # A bare name is enough when it is software people open by name and a
        # verified catalog is present to prove it absent; «abrí la puerta»
        # stays outside because ``puerta`` is not.
        wrapper = _match(
            request.group("target"),
            rf"^(?:(?:el|la|the)\s+)?(?={_KNOWN_SOFTWARE}"
            r"(?:\s*[,;:]?\s+(?:por favor|please|para mi|for me|ahora|now|"
            r"dale|porfa|porfi|porfis|pls|plz))?[\s?!.]*$)",
        )
    if proper_name and wrapper is None and build_application_catalog_index(application_names).entries:
        # APPS1549 «abre Saint Rose.»: a proper name (every word capitalized,
        # no article, at most four words) after an open head is a name the
        # person expects on this PC; the verified catalog can prove it absent
        # and the reply can name it. Lowercase common nouns still abstain.
        proper = _APPLICATION_TRAILING_REQUEST.sub("", raw_target.rstrip(" ?!.")).rstrip()
        words = proper.split()
        if (
            1 <= len(words) <= 4
            and all(word[:1].isupper() and word[1:] == word[1:].lower() and word.isalpha() for word in words)
            and not _has(_fold(proper), r"^(?:el|la|los|las|un|una|the|a|an)\b")
        ):
            wrapper = _match(request.group("target"), r"^(?=\S)")
    if (
        wrapper is None
        or resolve_application_catalog_app_id(text, application_names) is not None
    ):
        return None
    raw_name = " ".join(raw_target.split()[len(wrapper.group().split()):])
    # The explicit application wrapper was consumed above. Strip only its
    # request suffix, never another article or program word inside the name.
    raw_name = _APPLICATION_TRAILING_REQUEST.sub("", raw_name.rstrip(" ?!.")).rstrip()
    name = _bounded_application_literal(raw_name)
    # Courtesy is a request envelope, not a separate effect clause.
    if name is None or len(_request_clauses(_strip_request_envelope(folded))) != 1:
        return None
    return name


def resolve_application_installed_name(
    text: str,
    application_names: Iterable[str] | ApplicationCatalogIndex,
) -> str | None:
    """Ground one explicit installed-application observation.

    Unlike ``app.open``, the read-only provider can truthfully answer that an
    arbitrary literal name is absent from the verified Start catalog.  The
    operation therefore must not require the queried name to already be in
    that same catalog.  We still accept an out-of-catalog literal only inside
    a tightly anchored observation request; free mentions and declarative
    sentences continue to abstain.
    """

    opening_name = unresolved_application_open_name(text, application_names)
    if opening_name is not None:
        return opening_name
    # APPS1549: the resolver admits a proper name behind a plain open verb only
    # after ruling out games, near names and public sites; the argument bound
    # here is that same name, exactly as the person wrote it.
    opening_name = unresolved_application_open_name(
        text, application_names, proper_name=True,
    )
    if opening_name is not None:
        return opening_name
    catalog = build_application_catalog_index(application_names)
    folded = _strip_request_envelope(_fold(text)).strip().rstrip(".?!").strip()
    if not folded:
        return None

    candidate: str | None = None
    patterns = (
        (
            r"(?:^|[,;]\s*|\b(?:y|and|then|luego|despues)\s+)"
            r"(?:comprueba|verifica|confirma|revisa|inspecciona|check|"
            r"verify|confirm|review|inspect)\s+"
            r"(?!(?:si|if|whether)\b)"
            r"(?:(?:el|la|the)\s+)?"
            r"(?P<target>[a-z0-9][a-z0-9 ._+@-]{0,100}?)\s+"
            r"(?:installation|instalacion|instalad[oa]|installed)"
            r"(?=$|[,;]|\s+(?:y|and|then|luego|despues)\b)"
        ),
        (
            r"^consulta\s+(?:el\s+)?software\s+local\s+para\s+saber\s+si\s+"
            r"(?:esta\s+)?(?P<target>.+)$"
        ),
        (
            r"^(?:comprueba|revisa|check)\s+(?:en|in)\s+(?:el\s+|the\s+)?"
            r"(?:menu\s+inicio|start\s+menu)\s+(?:la\s+presencia\s+de|for)\s+"
            r"(?P<target>.+)$"
        ),
        (
            r"^look\s+through\s+(?:the\s+)?local\s+software\s+inventory\s+"
            r"for\s+(?P<target>.+)$"
        ),
        (
            r"^find\s+out\s+whether\s+(?P<target>.+?)\s+exists\s+among\s+"
            r"(?:the\s+)?start\s+menu\s+apps?$"
        ),
        (
            r"^(?:chequea|checkea|comprueba)\s+si\s+(?P<target>.+?)\s+"
            r"figura\s+en\s+(?:el\s+)?software\s+de\s+(?:este\s+)?pc$"
        ),
        (
            r"^(?:verifica|verificar|confirma|confirmar|comprueba|comprobar|"
            r"averigua|averiguar|checkea|chequea|fijate|fijese|mira|revisa|"
            r"check|verify|confirm|see|find\s+out|dime|tell\s+me)\s+"
            r"(?:si|if|whether)\s+"
            r"(?:(?:tengo|tienes|tiene|tenemos|i\s+have|we\s+have)\s+)?"
            r"(?P<target>.+?)\s+"
            r"(?:(?:figura|aparece)\s+(?:entre|en)\s+(?:las\s+)?"
            r"(?:aplicaciones|apps)\s+(?:instaladas|de\s+(?:este|mi|el)\s+"
            r"(?:equipo|pc|ordenador|computador))|"
            r"(?:exists|appears|is\s+listed)\s+(?:among|in)\s+(?:the\s+)?"
            r"(?:installed\s+(?:apps|applications)|(?:apps|applications)\s+"
            r"on\s+(?:this|my|the)\s+(?:pc|computer|machine))|"
            r"(?:esta|is)\s+(?:disponible\s+como\s+(?:programa\s+)?"
            r"instalad[oa]|present\s+in\s+(?:my\s+|the\s+)?installed\s+"
            r"apps?|instalad[oa]|installed)|instalad[oa]|installed)"
            r"(?:\s+(?:aqui|here|en\s+(?:este|mi|el)\s+(?:equipo|pc)|"
            r"on\s+(?:this|my|the)\s+computer|localmente|locally))?$"
        ),
        (
            r"^(?:inspect|inspecciona|revisa|review|check)\s+"
            r"(?:(?:the|las?)\s+)?(?:installed\s+(?:applications?|apps?|"
            r"programs?)|aplicaciones?\s+instaladas?|programas?\s+instalados?)"
            r"\s+(?:for|por|para)\s+(?P<target>.+)$"
        ),
        (
            r"^(?:inspect|inspecciona|revisa|review|check)\s+(?:en\s+|in\s+)?"
            r"(?:(?:the|las?)\s+)?(?:installed\s+(?:applications?|apps?|"
            r"programs?)|aplicaciones?\s+instaladas?|programas?\s+instalados?)"
            r"\s+(?:si\s+aparece|if\s+(?:it\s+)?shows\s+up|for)\s+"
            r"(?P<target>.+)$"
        ),
        (
            r"^(?:inspect|inspecciona|revisa|review|check)\s+"
            r"(?:(?:the|el)\s+)?(?:start\s+(?:app|application)\s+inventory|"
            r"inventario\s+de\s+aplicaciones\s+(?:de\s+)?inicio)\s+"
            r"(?:for|por|para)\s+(?P<target>.+)$"
        ),
    )
    for pattern in patterns:
        request = _match(folded, pattern)
        if request is not None and not _is_negated_match(folded, request):
            candidate = request.group("target")
            break

    # Exact catalog evidence is produced by the authenticated entity
    # recognizer for ordinary state questions and repeated app lists.
    if candidate is None:
        exact = [name for name, key in catalog.entries if key == folded]
        if len(exact) == 1:
            return exact[0]
        if folded in {"windows.calculator", "windows.notepad"}:
            return folded
        return None

    forms = _application_target_forms(candidate)
    keys = tuple(
        dict.fromkeys(
            _application_name_key(form)
            for form, _ in forms
            if _application_name_key(form)
        )
    )
    if not keys:
        return None

    catalog_keys = {key for _, key in catalog.entries}
    for key in keys:
        exact = [
            name for name, candidate_key in catalog.entries if candidate_key == key
        ]
        if len(exact) == 1:
            return exact[0]
        if key in {"calc", "calculadora", "calculator"} and catalog_keys & {
            "calculadora",
            "calculator",
        }:
            return "windows.calculator"
        if key in {
            "app de notas",
            "bloc de notas",
            "editor de texto",
            "notepad",
        } and catalog_keys & {"bloc de notas", "notepad"}:
            return "windows.notepad"

    return _bounded_application_literal(forms[-1][0])


def _bounded_application_literal(candidate: str) -> str | None:
    """Keep literal presence queries bounded without asserting membership."""

    # A pronoun without catalog identity is not an application-name query.
    # Keep it unresolved rather than asking the provider about a literal "it".
    if _has(
        _fold(candidate),
        r"^(?:(?:esta|esa|aquella|this|that)\s+"
        r"(?:app|aplicacion|application|programa|program)|"
        r"esto|eso|esta|esa|aquella|it|this|that|them|esas|aquellas)$",
    ):
        return None
    # A relative clause or its subject still needs an antecedent; it is not
    # an unfamiliar literal identifier that a catalog can prove absent.
    if _has(
        _fold(candidate),
        r"^(?:(?:el|la|lo|los|las|the)\s+)?"
        r"(?:que|cual|cuales|quien|which|that|who|you|i|we|he|she|they)\b",
    ):
        return None

    # The provider's schema accepts at most 256 UTF-8 bytes and independently
    # verifies both presence and absence.  Reject clause syntax, control
    # characters and generic nouns so only one bounded literal reaches it.
    literal = candidate.strip(" \t\r\n\"'“”")
    if (
        not literal
        or len(literal.encode("utf-8")) > 256
        or any(ord(character) < 32 for character in literal)
        or _has(literal, r"(?:[;,]|\b(?:y|and|then|luego|despues)\b)")
        or _has(
            literal,
            r"^(?:app|application|aplicacion|program|programa|software|"
            r"installed\s+apps?|aplicaciones?\s+instaladas?)$",
        )
    ):
        return None
    return literal


def _authenticated_application_list(
    text: str,
    application_names: Iterable[str] | ApplicationCatalogIndex,
    *,
    installed_query: bool = False,
) -> tuple[tuple[int, str], ...]:
    """Recognize an exact coordinated list of authenticated app names."""

    occurrence_pattern = build_application_catalog_index(
        application_names,
    ).occurrence_pattern
    spans = (
        [
            (found.start(), found.end(), found.group("target"))
            for found in occurrence_pattern.finditer(text)
        ]
        if occurrence_pattern is not None
        else []
    )
    if len(spans) < 2:
        return ()
    connector = (
        r"\s*(?:"
        r",\s*(?:(?:y|and)(?:\s+(?:luego|despues|then|afterwards))?)?"
        r"|(?:y|and)(?:\s+(?:luego|despues|then|afterwards))?"
        r")\s*"
        r"(?:(?:el|la|los|las|the)\s+)?"
        r"(?:(?:aplicacion|application|app|programa|program)\s+)?"
    )
    if any(
        re.fullmatch(
            connector,
            text[prior[1] : later[0]],
            re.IGNORECASE,
        )
        is None
        for prior, later in zip(spans, spans[1:])
    ):
        return ()
    prefix = text[: spans[0][0]]
    suffix = text[spans[-1][1] :]
    if installed_query:
        prefix_first = _has(
            prefix,
            (
                r"^[¿?¡!\s]*(?:esta|estan|is|are)\s+"
                r"(?:instalad[oa]s?|installed)\s+"
                r"(?:(?:el|la|los|las|the)\s+)?$"
            ),
        ) and _has(suffix, r"^[\s?!.]*$")
        suffix_last = _has(
            prefix,
            r"^[¿?¡!\s]*(?:esta|estan|is|are)\s+$",
        ) and _has(
            suffix,
            r"^\s+(?:instalad[oa]s?|installed)[\s?!.]*$",
        )
        valid = prefix_first or suffix_last
    else:
        valid = _has(
            prefix,
            (
                r"^[¿?¡!\s]*(?:(?:por favor|please)\s*[,;:]?\s*|"
                r"(?:puedes|podrias|can you|could you|would you)\s+)?"
                rf"{_OPEN}\b\s+(?:(?:el|la|the)\s+)?"
                r"(?:(?:aplicacion|application|app|programa|program)\s+)?$"
            ),
        ) and _has(
            suffix,
            (
                r"^(?:\s+(?:por favor|please|para mi|for me|ahora|now))?"
                r"[\s?!.]*$"
            ),
        )
    if not valid:
        return ()
    return tuple((start, key) for start, _, key in spans)


def _authenticated_application_request(
    text: str,
    application_names: Iterable[str] | ApplicationCatalogIndex,
) -> tuple[str, tuple[tuple[int, str], ...]] | None:
    """Recognize a whole exact app request before inspecting words in names."""

    names = build_application_catalog_index(application_names)
    bare_target = _application_name_key(text.rstrip(" ?!."))
    if bare_target in names.keys:
        return "app.open", ((0, bare_target),)
    for installed_query, operation in (
        (False, "app.open"),
        (True, "app.installed"),
    ):
        target = _authenticated_application_target(
            text,
            names,
            installed_query=installed_query,
        )
        if target is not None:
            return operation, (target,)
        targets = _authenticated_application_list(
            text,
            names,
            installed_query=installed_query,
        )
        if targets:
            return operation, targets
    return None


def _authenticated_application_desired_open(
    text: str,
    application_names: Iterable[str] | ApplicationCatalogIndex,
) -> tuple[int, str] | None:
    """Resolve an exact installed app inside a literal desired-open clause."""

    folded = _fold(text)
    catalog = build_application_catalog_index(application_names)
    occurrence = catalog.occurrence_pattern
    if occurrence is None or not _application_desire_is_positive(folded):
        return None
    found = list(occurrence.finditer(folded))
    if len(found) != 1:
        return None
    target = found[0]
    prefix = folded[: target.start()].strip(" ¿?¡!,:;.-")
    suffix = folded[target.end() :].strip(" ¿?¡!,:;.-")
    request = _application_open_request(folded[: target.end()])
    leading_desire = (
        request is not None
        and request.group("desire") is not None
        and any(
            _application_name_key(form)
            == _application_name_key(target.group("target"))
            for form, _ in _application_target_forms(request.group("target"))
        )
        # Courtesy is outside identity; every other suffix stays opaque.
        and (not suffix or _has(suffix, r"^(?:por favor|porfa|please)$"))
    )
    desired_running = (
        _has(prefix, r"^(?:get|keep)$") and _has(suffix, r"^(?:open|running|started)$")
    ) or (
        not prefix
        and _has(
            suffix,
            r"^(?:needs?|has)\s+to\s+be\s+(?:open|running|started)$|"
            r"^(?:tiene|necesita)\s+que\s+estar\s+"
            r"(?:abiert[oa]|funcionando|iniciad[oa])$",
        )
    )
    if not (leading_desire or desired_running):
        return None
    return target.start(), _application_name_key(target.group("target"))


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


# Cortesía y vocativo que preceden a la petición real. Llamar al asistente por
# su nombre no cambia el acto de habla ni concede autoridad; solo desplaza la
# cabeza del pedido.
# La petición real puede reabrir con puntuación invertida después de la
# envoltura: «Hola, ¿qué hora es?». Consumirla aquí es lo mismo que ya hace el
# `[¿?¡!\s]*` del principio de la cadena.
_PREFIX_GAP = r"\s*[¿¡]?\s*"
_DISCOURSE_CLAUSE = (
    r"(?:"
    r"(?:cuando\s+(?:puedas|tengas\s+(?:(?:un|algo\s+de)\s+)?"
    r"(?:momento|rato|minuto)|te\s+(?:quede|venga)\s+bien)|"
    r"when\s+(?:you\s+(?:can|have\s+(?:a\s+)?(?:moment|minute|mean\s+it)|"
    r"get\s+(?:a\s+)?chance)|it\s+is\s+convenient))|"
    r"(?:(?:una\s+)?(?:(?:peque[nñ]a|breve|r[aá]pida|simple)\s+)?"
    r"(?:petici[oó]n|solicitud|consulta|pregunta)"
    r"(?:\s+(?:peque[nñ]a|breve|r[aá]pida|simple))?|"
    r"(?:(?:one|a)\s+)?(?:quick|small|brief|simple)\s+"
    r"(?:request|question)|(?:one|a)\s+(?:request|question))|"
    r"(?:a\s+prop[oó]sito|tengo\s+una\s+pregunta|i\s+was\s+wondering|"
    r"one\s+thing)|"
    r"(?:escucha|mira|listen|look)"
    r")"
)
_LOCAL_TASK_FRAME = (
    r"(?:"
    r"esta\s+vez\s+necesito\s+una\s+acci[oó]n\s+concreta\s+en\s+este\s+equipo|"
    r"enc[aá]rgate\s+en\s+el\s+computador\s+de\s+esto|"
    r"on\s+this\s+computer\s*,\s*carry\s+out\s+this\s+specific\s+request|"
    r"i\s+need\s+this\s+done\s+locally\s+on\s+the\s+pc|"
    r"haz\s+this\s+concrete\s+action\s+en\s+este\s+computador|"
    r"on\s+this\s+pc\s*,\s*enc[aá]rgate\s+de\s+esto|"
    r"(?:atiende\s+este\s+pedido|take\s+care\s+of\s+this\s+request|"
    r"handle\s+este\s+pedido)|"
    r"te\s+(?:dejo|doy|paso)\s+(?:una\s+)?"
    r"(?:instrucci[oó]n|indicaci[oó]n|tarea|petici[oó]n)"
    r"(?:\s+(?:concreta|espec[ií]fica|puntual))?"
    r"(?:\s+para\s+(?:(?:este|el)\s+)?(?:computador|equipo|pc))?|"
    r"necesito\s+que\s+(?:hagas|realices|atiendas)\s+"
    r"(?:lo\s+siguiente|esto)(?:\s+ahora)?|"
    r"here(?:['’]s|\s+is)\s+(?:(?:one|a)\s+)?"
    r"(?:(?:concrete|specific)\s+)?(?:instruction|request|task)"
    r"(?:\s+for\s+(?:(?:this|the)\s+)?(?:computer|pc))?|"
    r"please\s+(?:handle|do)\s+(?:the\s+following|this)"
    r"(?:\s+on\s+(?:(?:this|the)\s+)?(?:pc|computer))?(?:\s+now)?|"
    r"necesito\s+(?:this|esta)\s+(?:exact\s+)?(?:thing|cosa)"
    r"(?:\s+on\s+(?:(?:this|the)\s+)?(?:pc|computer))?|"
    r"(?:atiende|handle|haz|do)\s+(?:esto|this)"
    r")"
)
# A frame that only announces "what follows is an instruction for this machine"
# carries no operation of its own. Cut B wrapped every request in one --
# "Esto si es una orden para el equipo: ...", "Carry out this PC request: ..." --
# and 417 of its rows resolved correctly the moment the wrapper was removed, so
# failing to strip it looked exactly like a failure to generalise.
#
# The rule is written by shape rather than by listing the wrappers a corpus
# happened to use: before the colon there must be both an instruction noun and
# a machine noun, and no negation. The negation guard matters more than it
# looks -- "esto es solo una conversacion y no una orden para el pc" contains
# both nouns, and stripping it would turn an explicit no-action request into an
# action one.
# The word classes are generated from cognate groups instead of hand-listed,
# and this is the third design of them because the first two kept losing a word
# at a time. R23 carried ``indicacion`` with no Spanish counterpart in the list
# and a whole Spanish cell fell to 23,5 %. R26 then carried English
# ``petition`` while Spanish ``peticion`` was already present, and 18 of its 20
# failures were that one word. Patching a noun per seal is a treadmill, so the
# class is now stated as **pairs**: a noun cannot enter on one side of the
# language border without its counterpart on the other, and
# ``test_the_two_borders_share_one_instruction_lexicon`` fails if the C# parser
# and this module ever drift apart.
#
# ``tarea``/``task``/``recado``/``nota``/``recordatorio`` are deliberately NOT
# instruction nouns even though they read like ones. They name catalog objects,
# and "crea una tarea en el equipo: comprar pan" would be stripped down to
# "comprar pan", destroying the very request it was meant to unwrap.
_COMPUTER_INSTRUCTION_FRAME = (
    r"(?:baxy\s*[,;:]?\s*)?"
    r"(?![^:]{0,90}\b(?:no|not|sin|without|s[oó]lo|solo|only|nada|"
    r"ning[uú]n|ninguna|ningunos|ningunas|ninguno|tampoco|nunca|jam[aá]s|"
    r"neither|none|never)\b[^:]{0,90}:)"
    r"(?:"
    # Names the thing as an instruction and names the machine it is for.
    rf"(?=[^:]{{0,90}}\b(?:{_INSTRUCTION_NOUNS})\b)"
    rf"(?=[^:]{{0,90}}\b(?:{_MACHINE_NOUNS})\b)"
    r"|"
    # Or points at the machine imperatively without naming the noun:
    # "Haz this on the computer: ...".
    r"(?=[^:]{0,90}\b(?:haz|hacer|realiza|realizar|ejecuta|ejecutar|atiende|"
    r"atender|resuelve|resolver|enc[aá]rgate|oc[uú]pate|do|carry\s+out|"
    r"handle|perform|run|execute|attend\s+to|take\s+care\s+of)\b"
    r"[^:]{0,40}\b(?:this|esto|eso|est[ae]|lo\s+siguiente|the\s+following)\b"
    r"[^:]{0,20}\b(?:on|en|para)\b[^:]{0,20}"
    rf"\b(?:{_MACHINE_NOUNS})\b)"
    r")"
    r"[^:]{1,90}:\s*"
)
_LOCAL_SCOPE_COURTESY_FRAME = (
    r"for\s+(?:(?:this|este)\s+)?(?:computer|computador|pc|equipo)"
    r"(?:\s+(?:right\s+now|ahora))?\s*,\s*(?:please|por\s+favor)\s+"
)
_EXPLICIT_NON_ACTION_FRAME = (
    r"(?:"
    r"sin\s+pedir\s+ning[uú]n\s+cambio\s+en\s+el\s+computador\s*,?\s*"
    r"quiero\s+preguntarte|"
    r"s[oó]lo\s+conversemos\s*;\s*no\s+hagas\s+nada\s+en\s+este\s+equipo|"
    r"let['’]?s\s+only\s+discuss\s+this\s*;\s*"
    r"do\s+not\s+change\s+anything\s+on\s+the\s+computer|"
    r"this\s+is\s+conversation\s+only\s*,?\s*"
    r"with\s+no\s+pc\s+action\s+requested|"
    r"solo\s+let['’]?s\s+talk\s*;\s*no\s+hagas\s+any\s+pc\s+action|"
    r"conversation\s+only\s*,?\s*sin\s+cambiar\s+nada\s+en\s+este\s+equipo|"
    r"(?:quiero|quisiera)\s+(?:preguntarte|consultarte)\s+"
    r"(?:algo|una\s+cosa)\s+sin\s+(?:pedir|solicitar)\s+"
    r"(?:una\s+)?acci[oó]n|"
    r"tengo\s+una\s+(?:duda|pregunta)(?:\s+(?:breve|r[aá]pida|peque[nñ]a))?"
    r"\s*,?\s*(?:s[oó]lo|solamente)\s+para\s+(?:conversar|charlar)|"
    r"just\s+(?:a\s+)?(?:(?:quick|brief|small)\s+)?(?:thought|question)"
    r"\s*,?\s*with\s+no\s+(?:(?:computer|pc)\s+)?action|"
    r"i\s+have\s+(?:a\s+)?(?:(?:short|quick|brief|small)\s+)?"
    r"(?:question|thought)\s*,?\s*just\s+to\s+(?:chat|talk)|"
    r"tengo\s+una\s+(?:quick|brief|short)\s+(?:question|duda)"
    r"\s*,?\s*sin\s+(?:(?:computer|pc)\s+)?(?:action|acci[oó]n)|"
    r"just\s+para\s+(?:conversar|charlar)\s*,?\s*"
    r"(?:una\s+)?(?:duda|question)(?:\s+(?:breve|quick|short))?"
    r")"
)
_REQUEST_PREFIX = (
    # A delimited present-time frame leaves the following request intact.
    # Future/past times and quoted content are not request wrappers.
    r"(?:(?:(?:ahora(?:\s+mismo)?|en\s+este\s+momento|actualmente|"
    r"(?:right\s+)?now|at\s+(?:this|the)\s+moment|currently)\s*[,;:]\s*|"
    # «son las tres abrí la calculadora»: a stated clock time frames an
    # immediate opening (owner review H0724); it never becomes a schedule and
    # only an opening verb may follow it.
    r"(?:son|es)\s+las?\s+(?:\d{1,2}(?:[:.]\d{2})?|una|dos|tres|cuatro|cinco|"
    r"seis|siete|ocho|nueve|diez|once|doce)"
    r"(?:\s+(?:y|menos)\s+(?:cuarto|media|\d{1,2}))?"
    r"(?:\s+de\s+la\s+(?:manana|tarde|noche))?\s*[,;:.]?\s+"
    r"(?=(?:abre|abri|abris|abrime|avri|open)\b)|"
    # «es tarde bajá el volumen»: lateness is the reason, the request follows.
    r"(?:ya\s+)?es\s+(?:muy\s+)?(?:tarde|temprano|de\s+noche)\s*[,;:.]?\s+"
    r"(?=(?:baja|bajar|bajalo|bajala|sube|subir|subi|suvi|subelo|subela|pone|pon)\b)))?"
    # A language directive changes presentation, not the following speech act.
    # Require its separator; quoted content and unclosed clauses stay literal.
    r"(?:(?:(?:responde|contesta)\s+en|(?:answer|reply|respond)\s+in)\s+"
    r"(?:espa[nñ]ol|ingl[eé]s|spanish|english|spanglish)\s*:\s*|"
    # Prefer the longest, most specific local-task frames before the generic
    # courtesy token below; otherwise ``Please handle ...`` would lose only
    # ``Please`` and leave the rest of the wrapper as apparent request text.
    rf"(?:{_LOCAL_TASK_FRAME}\s*[,;:.!?\-\u2013\u2014]+{_PREFIX_GAP}|"
    rf"{_COMPUTER_INSTRUCTION_FRAME}|"
    rf"{_LOCAL_SCOPE_COURTESY_FRAME}|"
    rf"(?:por favor|porfa|please)\s*[,;:.!?]?{_PREFIX_GAP}|"
    rf"(?:una\s+(?:pequena\s+)?cuestion|i\s+small\s+question)"
    rf"\s*[,;:.!?\-\u2013\u2014]+{_PREFIX_GAP}|"
    # ASR may remove every pause from a stacked spoken envelope. Three
    # consecutive discourse markers still form an unambiguous preface.
    r"(?:oye\s+)?a\s+ver\s+(?:una\s+)?solicitud\s+rapida\s+|"
    # Conversational wrappers remain non-semantic only when punctuation
    # closes them.  This admits natural vocatives such as ``Baxy, hazme un
    # favor: ...`` without turning a literal ``hazme un favor que...`` into a
    # request for the trailing words.
    rf"(?:hazme\s+un\s+favor|one\s+thing|una\s+cosa(?:\s+please)?)"
    rf"\s*[,;:.!?\-\u2013\u2014]+{_PREFIX_GAP}|"
    r"(?:puedes|podes|podrias|podria|me\s+(?:puedes|podes|podrias|podria)|can you|could you|would you)\s+|"
    # Speech discourse markers require punctuation so literal content stays intact.
    rf"(?:a ver|antes que nada|che|oye|oiga|listen|dale)\s*[,;:.!?\-\u2013\u2014]{_PREFIX_GAP}|"
    rf"(?:por curiosidad|una duda|just curious|a question)"
    rf"\s*[,;:.!?\-\u2013\u2014]+{_PREFIX_GAP}|"
    rf"{_DISCOURSE_CLAUSE}\s*[,;:.!?\-\u2013\u2014]+{_PREFIX_GAP}|"
    # Un saludo suelto tampoco cambia el acto de habla: sólo desplaza la cabeza
    # del pedido, igual que el vocativo de abajo. Se exige el separador
    # explícito para que «hola mundo» o «escribe hola» sigan intactos.
    r"(?:buenos dias|buenas tardes|buenas noches|buenas|hola|"
    rf"good morning|good afternoon|good evening|hello|hi|hey)\s*[,;:.!?]{_PREFIX_GAP}|"
    r"(?:(?:che|oye|oiga|hey|ey|ok|okay|hola|hello|hi|escucha|listen|"
    r"a ver)\s+)?"
    rf"baxy\s*[,;:.!?\-\u2013\u2014]?{_PREFIX_GAP})?)"
)
# The shared prefix is large; compile it once for the repeated head reads.
_EXPLICIT_DESIRE_REQUEST = re.compile(
    rf"^[¿?¡!\s]*{_REQUEST_PREFIX}"
    r"(?:(?:i|we)\s+(?:need|want|would\s+like)\s+(?:you\s+)?to|"
    r"i['’]?d\s+like\s+to|(?:yo\s+)?(?:quiero|quisiera|necesito)"
    r"(?:\s+que)?)\s+(?:(?:lo|la|me)\s+)?"
    r"(?P<body>(?P<head>[a-z]+)\b.*)$",
    re.IGNORECASE,
)

# Una cola de cierre social no cambia el acto de habla: sólo anuncia que el
# pedido terminó. La gramática es acotada y simétrica con la del parser privado
# de memoria en `Baxy.App`; ambas fronteras deben quitar exactamente la misma
# familia o el mismo turno se entiende distinto según por dónde entre. Se exige
# el separador `,`/`;` para que un texto literal como «mi tarea termina hoy»
# siga intacto, y las variantes acentuadas se aceptan porque esta función se
# llama tanto sobre texto plegado como sobre texto crudo.
_TRAILING_SOCIAL_CLOSURE = re.compile(
    r"\s*[,;]\s*(?:(?:por favor|porfa|please|gracias|thanks|thank you)\s*,?\s*)?"
    r"(?:"
    r"eso es todo|nada m[aá]s|"
    r"that(?:'s| is) (?:all|the whole request)|nothing else|"
    # «con esto concluye la tarea», «con eso termina mi solicitud por ahora»
    r"con (?:eso|esto) (?:termina|finaliza|concluye) (?:mi|la) "
    r"(?:solicitud|petici[oó]n|pedido|tarea)(?: por ahora)?|"
    # «mi petición finaliza aquí», «la solicitud queda completada por ahora»
    r"(?:mi|la) (?:solicitud|petici[oó]n|pedido|tarea) "
    r"(?:termina|finaliza|concluye|queda (?:completa|completada))"
    r"(?: (?:aqu[ií]|por ahora))?|"
    # «that completes my request», «this concludes the task»
    r"(?:that|this) (?:completes|finishes|ends|concludes) (?:my|the) "
    r"(?:request|task)(?: for now)?|"
    # «my request is now complete», «con eso, my task has been finished for now»
    r"(?:con (?:eso|esto), )?(?:my|the) (?:request|task) "
    r"(?:is|is now|has been) (?:complete|completed|finished|done)(?: for now)?"
    r")\s*[.!?]*$",
    re.IGNORECASE,
)


# SYSTEM1545 H0076 «Dime que version de Windows tengo y cuanta RAM tiene este
# PC. Usa Python.»: a trailing sentence that names the means (Python, a script,
# the terminal) is not a second request. The owner does not want the assistant
# to program as a capability; the readable request before it is answered from
# the product's own readings and the means is declined, never followed.
_TRAILING_MEANS_DIRECTIVE = re.compile(
    r"\s*[.,;:]\s*(?:"
    r"(?:us[aá]|usando|utiliz[aá]|utilizando|emple[aá]|empleando|hazlo con|"
    r"hacelo con|con|mediante|a trav[eé]s de|use|using|with|by using|via)"
    r"\s+(?:el\s+|la\s+|un\s+|una\s+|a\s+|the\s+)?"
    r"(?P<means>python|powershell|bash|cmd|"
    r"script(?:\s+(?:de|en|of|in)\s+(?:python|powershell|bash))?|"
    r"c[oó]digo(?:\s+(?:de|en)\s+python)?|code|terminal|consola|console)"
    r")\s*[.!]*$",
    re.IGNORECASE,
)


def declined_means(text: str) -> str | None:
    """The means a trailing directive names (lowercase), or None.

    Only a directive that follows a request counts: «Usa Python.» alone is a
    request of its own and stays untouched.
    """

    found = _TRAILING_MEANS_DIRECTIVE.search(text)
    if found is None or found.start() == 0:
        return None
    return found.group("means").casefold()


def _strip_trailing_means_directive(text: str) -> str:
    found = _TRAILING_MEANS_DIRECTIVE.search(text)
    if found is None or found.start() == 0:
        return text
    return text[: found.start()].rstrip()


def _strip_trailing_social_closure(text: str) -> str:
    """Drop a trailing social closure without ever emptying the request.

    A turn made only of a closure keeps its own text: removing it would leave
    an empty body that the anchored matchers could reinterpret. This mirrors
    the bounded guard used by the private memory parser.
    """

    text = _strip_trailing_means_directive(text)
    found = _TRAILING_SOCIAL_CLOSURE.search(text)
    if found is None or found.start() == 0:
        return text
    return text[: found.start()].rstrip()


def _strip_request_envelope(text: str) -> str:
    """Remove bounded request prefaces without changing their action bodies.

    The wrapper grammar is deliberately the same one used by every anchored
    request matcher.  Centralizing it here makes ``Hola, ...`` and
    ``Hola baxy: ...`` invariant for every current and future catalog
    operation, while the mandatory greeting separator keeps literal content
    such as ``escribe hola`` untouched.  An unmatched request is returned
    byte-for-byte so this normalization can never manufacture authority.
    """

    current = _strip_trailing_social_closure(text).rstrip()
    for _ in range(6):
        # Agreement or an initial rectification can precede an explicit request.
        # Rectification requires a positive action head; agreement may also
        # precede a negative command. Retain the entire body so its prohibitions,
        # later corrections and narrative boundaries remain visible.
        found = _match(
            current,
            r"^[¿?¡!\s]*(?:(?:s[ií]|yes|ok(?:ay)?|perfecto|perfect)\s*[,;:.!]+\s*|"
            r"no\s*[,;:]\s*(?:mejor|en realidad|actually|on second thought)"
            rf"\s*[,;:]?\s+(?=(?:{_COVERAGE_ACTION_HEAD})\b)|"
            # APPS1535 «Y quema, abre Saint Rose.», «Y bueno, abre…»: a spoken
            # opener of a conjunction, one word and a comma before an order.
            r"(?:y|and)\s+(?!que\b|si\b|no\b)[a-z]{2,10}\s*,\s*"
            rf"(?=(?:{_COVERAGE_ACTION_HEAD})\b))"
            r"(?P<body>.+)$",
        )
        if found is not None and not (
            _head_is(_request_head(found.group("body")), _COVERAGE_ACTION_HEAD)
            or _negative_action_forms(found.group("body"))
        ):
            found = None
        if found is None:
            found = _match(
                current,
                rf"^[¿?¡!\s]*{_REQUEST_PREFIX}(?P<body>.+)$",
            )
        if found is None or found.start("body") == 0:
            break
        body = found.group("body")
        if body == current:
            break
        current = body
    return current


def explicit_non_action_body(text: str) -> str | None:
    """Return the body behind an explicit conversation-only boundary.

    Neutral vocatives may precede the boundary, but the boundary itself is not
    stripped as a request envelope.  A colon or equivalent sentence separator
    is mandatory, and the entire trailing body remains non-authoritative even
    if it contains imperative words.
    """

    framed = _strip_request_envelope(text).strip()
    found = _match(
        framed,
        rf"^[¿?¡!\s]*{_EXPLICIT_NON_ACTION_FRAME}"
        r"\s*[,;:.!?\-\u2013\u2014]+\s*[¿¡]?\s*(?P<body>\S.*)$",
    )
    return found.group("body") if found is not None else None


def explicit_non_action_frame(text: str) -> bool:
    """Recognize an explicit conversation-only boundary without granting effects."""

    return explicit_non_action_body(text) is not None


def _explicit_desire_request(text: str) -> re.Match[str] | None:
    # A need/desire introduces a request only when its next head is an
    # explicit effect verb. Inspect it before the literal first word so a
    # Spanish "quiero/necesito" cannot hide that verb. A denial, condition or
    # noun remains opaque; the frame never removes words from literal payloads.
    desired = _EXPLICIT_DESIRE_REQUEST.match(text)
    return (
        desired
        if desired is not None and _head_is(desired.group("head"), _COVERAGE_ACTION_HEAD)
        else None
    )


def _request_head(text: str) -> str:
    topic = _machine_status_topic(text)
    if topic is not None:
        text = topic.group("body")
    text = _negative_state_question_body(text) or text
    desired = _explicit_desire_request(text)
    if desired is not None:
        return desired.group("head")
    found = _match(
        text,
        rf"^[¿?¡!\s]*{_REQUEST_PREFIX}(?P<head>[a-z]+)",
    )
    if found is not None:
        head = found.group("head")
        if head not in {"i", "yo"}:
            return head
    # Preserve the original non-action heads (for example "write" in a note
    # request) for readers whose vocabulary is broader than clause boundaries.
    legacy_desire = _match(
        text,
        r"^[¿?¡!\s]*(?:i\s+(?:want|would\s+like)\s+to|"
        r"i['’]?d\s+like\s+to|yo\s+quiero|quiero|quisiera)\s+"
        r"(?P<head>[a-z]+)",
    )
    return legacy_desire.group("head") if legacy_desire is not None else ""


def _head_is(head: str, pattern: str) -> bool:
    return re.fullmatch(pattern, head, re.IGNORECASE) is not None


def _is_builtin_keyboard_request(text: str) -> bool:
    """Reserve the OSK phrase for its typed built-in operation."""

    return _head_is(_request_head(text), _OPEN) and _has(
        text,
        r"\b(?:teclado en pantalla|on[ -]screen keyboard)\b",
    )


def explicit_negative_constraint(text: str) -> bool:
    """Recognize a standalone prohibition for prose, never operation authority.

    Reuse the existing action-head vocabulary. Spanish negative imperatives
    use subjunctive endings rather than the affirmative command forms in that
    vocabulary. A negated statement or a compound request stays with the normal
    reader; neither a leading ``no`` nor a device noun proves a prohibition.
    """

    folded = _strip_request_envelope(_fold(text))
    # NEGATIVE1309 «mejor no abras la calculadora»: a softening adverb before
    # the prohibition does not change it.
    folded = re.sub(r"^(?:mejor|por ahora|ahora|hoy|por favor)\s+", "", folded, count=1)
    if any(mark in folded for mark in ("?", "¿")):
        return False
    if any(mark in folded for mark in (";", ",")):
        # «No cierres Chrome, lo estoy usando»: a justification or state after
        # the separator keeps the single prohibition (CLOSE1219-1225/010); any
        # other tail is a compound turn for the normal reader.
        head, tail = re.split(r"[,;]", folded, 1)
        if re.match(
            r"^\s*(?:(?:que\s+)?(?:lo|la|los|las|me|te)\s+)?"
            r"(?:estoy|estamos|esta|estan|sigo|seguimos|necesito|necesitamos|"
            r"i'?m|i\s+am|it'?s|we'?re|they'?re|porque|because|ya\s+que)\b",
            tail,
        ) is None:
            return False
        folded = head.strip()
    if re.search(r"\b(?:y|and|pero|but|sino)\b", folded):
        return False
    if len(_request_clauses(folded)) != 1:
        return False
    return bool(_negative_action_forms(folded))


def _negative_action_forms(folded: str) -> tuple[str, ...]:
    """Project a prohibited action for scope comparison, never execution."""

    found = re.match(
        r"^[¡!\s]*(?:(?P<es>no|nunca|jamas)\s+"
        r"(?:(?:me|lo|la|los|las|nos)\s+)?|(?:never|don't|dont|do\s+not)\s+)"
        r"(?P<verb>[a-z]+)\b",
        folded,
    )
    if found is None:
        return ()
    verb = found.group("verb")
    if found.group("es"):
        # SYSTEM1697 «No me digas la versión de Python.»: the irregular
        # subjunctive of decir projects to its request head.
        candidates = {"pongas": "pon", "hagas": "haz", "vayas": "ve", "digas": "dime"}
        heads = [candidates.get(verb, "")]
        for ending, replacement in (
            ("es", "a"), ("as", "e"), ("ces", "za"),
            ("ques", "ca"), ("gues", "ga"),
        ):
            if verb.endswith(ending):
                heads.append(verb[:-len(ending)] + replacement)
    else:
        heads = [verb]
    return tuple(
        head + folded[found.end():]
        for head in dict.fromkeys(heads)
        # SYSTEM1545 «No uses Python.»: forbidding a means (use, employ) is a
        # prohibition to acknowledge, although «usa» heads no request.
        # AUDIO1577 «No toques el volumen.»: forbidding to touch something is
        # the same prohibition as forbidding to change it.
        # KNOW1835 «No me contestes nada, solo estaba pensando en voz alta.»,
        # «Don't answer»: forbidding a reply is a prohibition to acknowledge.
        if re.fullmatch(_COVERAGE_ACTION_HEAD, head) or head in {"usa", "utiliza", "emplea", "use", "toca", "touch", "contesta", "habla", "answer", "reply", "talk", "speak", "say"}
    )


def _is_negative_effect_clause(text: str) -> bool:
    # A closed yes/no answer envelope is not an instruction negation.  Strip
    # only that leading envelope, then still fail closed if the actual clause
    # is negative (for example, ``yes or no: don't open Spotify``).
    text = re.sub(
        r"^[¿?¡!\s]*(?:yes\s+or\s+no|si\s+o\s+no)\b[\s,:;\-]*",
        "",
        text,
        count=1,
        flags=re.IGNORECASE,
    )
    # A negated state question asks for evidence; it does not prohibit the
    # observation. Imperatives (including questions such as "no cierres?")
    # and incomplete retractions keep the prohibition boundary below.
    if _negative_state_question_body(text) is not None:
        return False
    return _has(
        text,
        r"^[¿?¡!\s]*(?:no|nunca|jamas|never|don'?t|do\s+not|"
        r"(?:i|we)\s+(?:don'?t|do\s+not)|(?:yo|nosotros)\s+no)\b",
    )


def _negative_state_question_body(text: str) -> str | None:
    """Expose the state-query head while retaining the original request as data."""

    if "?" not in text and "¿" not in text:
        return None
    found = _match(text, r"^[¿?¡!\s]*no\s+(?=(?:esta|estan)\b)")
    return text[found.end():] if found is not None else None


def _is_social_clause(text: str) -> bool:
    return _has(
        text,
        (
            r"^[¿?¡!\s]*(?:gracias|thanks|thank you|por favor|please|"
            r"que tengas (?:un )?buen dia)\b|"
            # Vocativo suelto: llamar al asistente por su nombre no es una
            # cláusula pendiente, sólo abre la petición que viene después.
            r"^[¿?¡!\s]*(?:(?:che|oye|oiga|hey|ey|ok|okay|hola|escucha|"
            r"listen)\s+)?baxy[\s?!.,;:]*$|"
            # Un saludo o una despedida que ocupan la cláusula entera tampoco
            # dejan una petición pendiente. El anclaje final es lo que mantiene
            # «hola mundo» o «escribe hola» fuera de esta puerta.
            r"^[¿?¡!\s]*(?:buenos dias|buenas tardes|buenas noches|buenas|"
            r"hola|good morning|good afternoon|good evening|hello|hi|hey|"
            r"hasta luego|hasta pronto|hasta manana|nos vemos|adios|chau|"
            r"chao|goodbye|good bye|good night|bye|see you(?: later)?)"
            r"(?:\s+baxy)?[\s?!.,;:]*$"
        ),
    )


def _is_effect_receipt_clause(text: str) -> bool:
    """Accept requests for evidence already guaranteed by the operation contract."""

    return _has(
        text,
        (
            r"^[¿?¡!\s]*(?:dime|decime|tell me)\s+(?:si|whether)\s+"
            r"(?:pudiste|se pudo|lo verificaste|you could|it was)\s+"
            r"(?:verificar(?:lo)?|verified?)\b|"
            r"^[¿?¡!\s]*(?:guardalo|guardala|save it)\s+(?:y|and)\s+"
            r"(?:dime|tell me|show me)\s+(?:el\s+|the\s+)?"
            r"(?:path|ruta)\b"
        ),
    )


# Los alcances medibles del descriptor `system.status` del catálogo. Nombrar
# uno de ellos no inventa una operación: solo identifica el dominio físico que
# esa operación ya mide. El orden no importa; ninguno concede autoridad.
_GPU_MEMORY_TERMS = (
    r"\b(?:(?:video|graphics|gpu)\s+memory|"
    r"memoria\s+(?:grafica|de\s+video|de\s+(?:la\s+)?gpu))\b"
)

_MACHINE_STATUS_SCOPES: tuple[tuple[str, str], ...] = (
    (
        "battery",
        r"\b(?:bateria|baterias|battery|batteries)\b",
    ),
    (
        "gpu",
        r"\b(?:gpu|gpus|vram|nvidia-smi|graphics\s+card|video\s+card|"
        r"tarjeta\s+(?:grafica|de\s+video)|placa\s+de\s+video)\b|"
        + _GPU_MEMORY_TERMS,
    ),
    (
        "cpu",
        r"\b(?:cpu|procesador|processor|nucleos?|cores?)\b",
    ),
    (
        "disk",
        # «cuánto espacio queda en C» / «cuánto espacio tengo» name the disk
        # by its free space; without these forms the request had no scope and
        # no domain (SYSTEM1169 planning probe: H0146, H0219).
        r"\b(?:disco|disk|hard\s+drive|unidad\s+c|drive\s+c|"
        r"almacenamiento|storage)\b|"
        r"\b(?:cuanto|cuanta|how\s+much)\s+(?:espacio|space)\b|"
        r"\b(?:espacio|space)\s+(?:libre\s+|free\s+)?"
        r"(?:queda|quedan|left|disponible|available|en\s+(?:el\s+)?(?:disco|disk|c\b))",
    ),
    (
        "os",
        # «windows» a secas también nombra ventanas abiertas. Solo cuenta como
        # sistema operativo junto a una señal de identidad o versión.
        r"\b(?:sistema\s+operativo|operating\s+system)\b|"
        r"\bwindows\b(?=.{0,40}\b(?:version|versiones|build|edicion|edition|"
        r"tengo|tienes|tiene|have|has|running|corriendo|instalad[oa]s?|"
        r"installed|is this)\b)|"
        r"\b(?:version|versiones|build|edicion|edition|que|which|what|dime)\b"
        r".{0,40}\bwindows\b",
    ),
)
# «equipo», «sistema» o «máquina» sin calificar nombran este computador; con un
# calificador nombran otra cosa (equipo médico, sistema solar, máquina de
# coser). Solo la forma sin calificar concede dominio, igual que antes.
_UNQUALIFIED_MACHINE = (
    r"\b(?:equipo|sistema|system|computadora|notebook|laptop|maquina|"
    r"machine)\b"
    r"(?:\s+(?:actual|operativo|informatico|windows))?"
    r"(?:\s+(?:por favor|please|ahora|now))?"
    r"[\s?!.]*$|"
    r"\b(?:estado\s+del\s+sistema|system\s+status)\b"
    r"(?:\s+(?:por favor|please|ahora|now))?[\s?!.]*$"
)

# «memoria» es polisémica (memoria del equipo, memoria privada del asistente,
# memoria de un texto). Solo cuenta como alcance medible junto a una medida.
_MEMORY_SCOPE_MEASURE = (
    r"\b(?:uso|usa|usan|usando|use|usage|used|utilizada|ocupando|ocupada|"
    r"libre|libres|free|disponible|available|instalada|installed|total|"
    r"cuanta|cuanto|how\s+much|queda|quedan|left|tengo|tiene|have|has)\b"
)


# Palabras que anclan la evidencia de una lectura del equipo. Se derivan de la
# misma tabla de alcances para que ampliar un alcance no deje su evidencia sin
# cubrir.
_MACHINE_STATUS_EVIDENCE = "|".join(
    (
        *(pattern for _, pattern in _MACHINE_STATUS_SCOPES),
        r"\b(?:equipo|sistema|system|pc|computador|computadora|computer|"
        r"notebook|laptop|maquina|machine|ram|memoria|memory|espacio|"
        r"space)\b",
    )
)


# Combinaciones que el enum del catálogo mide en una sola lectura. Cualquier
# otra pareja de alcances necesita dos lecturas, así que el reconocedor se
# abstiene en vez de contestar sólo una mitad de la pregunta.
_COMBINED_MACHINE_SCOPES: tuple[frozenset[str], ...] = (
    frozenset({"cpu", "memory"}),
    frozenset({"os", "memory"}),
)


def _machine_status_scopes(text: str) -> frozenset[str]:
    """Name every closed `system.status` scope this request measures."""

    named = {scope for scope, pattern in _MACHINE_STATUS_SCOPES if _has(text, pattern)}
    # Qualified video memory names the GPU scope, not a second RAM reading.
    # Remove only that noun phrase: an independent RAM/system-memory request
    # must still survive so a combined request cannot silently lose a scope.
    memory_text = re.sub(_GPU_MEMORY_TERMS, " ", text)
    if _has(text, r"\bram\b") or (
        _has(memory_text, r"\b(?:memoria|memory)\b")
        and _has(text, _MEMORY_SCOPE_MEASURE)
    ):
        named.add("memory")
    return frozenset(named)


def _machine_status_scope(text: str) -> str | None:
    """Name one closed `system.status` scope this request measures, if any."""

    named = _machine_status_scopes(text)
    if not named:
        return None
    for scope, _ in _MACHINE_STATUS_SCOPES:
        if scope in named:
            return scope
    return "memory"


def _machine_status_scopes_are_one_reading(text: str) -> bool:
    """Reject a request whose scopes the catalog cannot measure at once."""

    named = _machine_status_scopes(text)
    if len(named) < 2:
        return True
    return any(named <= combined for combined in _COMBINED_MACHINE_SCOPES)


def _machine_status_is_the_whole_clause(text: str) -> bool:
    """Reject a clause that also asks for a reading of another family.

    «muestra la hora, mi IP y mi RAM» names three observations. When the
    clause splitter cannot separate them, answering only the machine status
    would silently drop the rest of the request, so the whole clause abstains
    and the model keeps the decision.
    """

    return not _has(
        text,
        (
            r"\b(?:hora|horas|time|fecha|date)\b|"
            r"\b(?:ip|direccion ip|ip address)\b|"
            r"\b(?:red|network|wi[\s-]?fi|internet|conexion|connection)\b|"
            r"\b(?:bluetooth|perifericos?|peripherals?)\b|"
            r"\b(?:cuentas?|usuarios?|accounts?|user(?:name)?s?)\b"
        ),
    )


def _is_past_or_hypothetical_state(text: str) -> bool:
    """Veto a state question that is not about the state right now.

    An observation reads the machine at this instant.  «cuánta batería tenía
    ayer» or «cuánta RAM tendría con 32 GB» ask about a state the providers
    cannot observe, so they belong to the conversation, not to a reading.
    """

    return _has(
        text,
        (
            r"\b(?:ayer|anteayer|anoche|yesterday|last\s+(?:night|week|month|"
            r"year)|la\s+semana\s+pasada|el\s+mes\s+pasado|el\s+ano\s+pasado|"
            r"recien|hace\s+(?:un|una|dos|tres|\d+)\s+"
            r"(?:minutos?|horas?|dias?|semanas?|meses?|anos?))\b|"
            r"\b(?:tenia|tenias|teniamos|tenian|habia|habian|estaba|estaban|"
            r"era|eran|fue|fueron|quedaba|quedaban|had|was|were|"
            r"used\s+to)\b|"
            r"\b(?:tendria|tendrias|seria|serian|tuviera|tuvieras|tuviese|"
            r"abriria|abririas|quedaria(?:s|mos|n)?|would(?!\s+you\b)|hipoteticamente|"
            r"hypothetically|supongamos|suponiendo|imagina|imagine)\b|"
            r"\bif\b.{0,64}\b(?:another|other)\s+(?:computer|device)\b|"
            r"\b(?:si|if)\b.{0,64}\b(?:otro|otra|another|other)\s+"
            r"(?:computador|computer|equipo|device)\b|"
            r"\b(?:que|what)\s+(?:ocurriria|pasaria|would\s+happen)\s+"
            r"(?:si|if)\b|"
            # Estado futuro: tampoco es una lectura de ahora.
            r"\b(?:usara|usaran|usaras|ocupara|ocuparan|tendra|tendran|"
            r"sera|seran|quedara|quedaran|necesitara|will|going\s+to)\b|"
            r"\bva\s+a\s+(?:usar|ocupar|necesitar|quedar|tener)\b"
        ),
    )


def _is_machine_knowledge_or_diagnosis(text: str) -> bool:
    """Separate measuring this machine from talking *about* hardware.

    ``system.status`` measures the current machine.  General hardware
    knowledge, purchase advice, prices, causal diagnosis, temperature,
    per-process attribution, monitoring over time, study material and the
    assistant's private memory are different requests: they must reach the
    model instead of gaining deterministic authority.
    """

    topic = _machine_status_topic(text)
    if topic is not None:
        # The Spanish relation in "respecto a CPU" is not the English
        # indefinite article in "a CPU". Keep its scope and complete request.
        text = text[topic.start("scope"):]
    return _has(
        text,
        (
            # definición, explicación y didáctica
            r"\b(?:que\s+es|que\s+son|what\s+is|what\s+are|what's|"
            r"explica(?:me|r)?|explain|para\s+que\s+sirve|"
            r"como\s+funciona(?:n)?)\b|"
            r"\bhow\s+(?:does|do)\b.{0,40}\bwork\b|"
            # consejo, comparación y compra
            r"\b(?:recomienda(?:s|me)?|recommend|conviene|mejor|peor|"
            r"better|best|worse|comprar|compro|buy|deberia|should|"
            r"necesita|necesitan|necesitas|necesito|need|needs)\b|"
            # precio
            r"\b(?:precio|precios|price|prices|cuesta|cuestan|cost|costs|"
            r"vale|valen|sale|salen|saliendo|cotiza|cotizame|quote)\b|"
            # causa y diagnóstico
            r"\b(?:por\s+que|porque|why|a\s+que\s+se\s+debe|causa|reason)\b|"
            # temperatura: fuera del enum medido por el catálogo
            r"\b(?:temperatura|temperature|temp|grados|celsius|"
            r"caliente|calientes|hot)\b|"
            # atribución por proceso o por agente: preguntar *quién* consume
            # un recurso no es medirlo, y el catálogo no atribuye consumo.
            r"\b(?:proceso|procesos|programa|programas|aplicacion|"
            r"aplicaciones|app|apps|process|processes|program|programs|"
            r"application|applications|quien|who|algo|alguien|something|"
            r"someone|anything|anyone)\b|"
            # El gerundio se acepta con tolerancia a errores de dictado
            # («usndo»): la forma progresiva basta para identificar la pregunta
            # por el agente, no por la cantidad.
            r"^[¿?¡!\s]*(?:que|what|cual|which)\s+(?:cosa\s+)?"
            r"(?:esta|estan|is|are)\s+(?:\w+\s+){0,2}\w*(?:ndo|ing)\b|"
            # Consumo o tamaño atribuido a un sujeto nombrado: preguntar
            # cuánto usa «parakeet» o cuánto pesa un juego no es medir el
            # equipo. Las continuaciones funcionales («estoy usando», «usa el
            # sistema») no cuentan como sujeto propio.
            r"(?<!in )(?<!the )(?<!of )"
            r"\b(?:usa|usan|use|uses|consume|consumen|ocupa|ocupan|pesa|"
            r"pesan|gasta|gastan)\s+"
            r"(?!(?:el|la|los|las|the|un|una|mi|mis|my|este|esta|estos|estas|"
            r"this|ahora|actualmente|de|del|en|mucho|poco|much|little|"
            r"right|now|left|free)\b)"
            r"[a-z0-9]+|"
            # Notas de configuración o de ejecución del modelo, no del equipo.
            r"\b(?:ctx|gguf|qat|swa|oom|kv|ngl|q4|q8|k_m|k_xl|mib|gib|"
            r"tokens?/s)\b|"
            # Temas de sesión de ingeniería: no son mediciones del equipo.
            r"\b(?:finetuning|fine-tuning|entrenamiento|training|benchmark|"
            r"checkpoint|dataset|prompt|inferencia|inference|epoch|epochs|"
            r"batch|deploy|release|refactor|commit)\b|"
            # Datos que `system.status` no mide.
            r"\b(?:hostname|dictation|dictado)\b|"
            r"\b(?:nombre|name)\s+(?:del|de la|of the)\s+"
            r"(?:pc|equipo|computador|computadora|computer|machine)\b|"
            r"\b(?:usuario actual|current user)\b|"
            # Preguntas sobre lo que BAXY hace por el equipo, no su estado.
            r"\b(?:cuidas|cuidar|cuidando|proteges|proteger|optimizas|"
            r"optimizar|mantienes|mantener|arreglas|arreglar|reparas|"
            r"reparar|mejoras|mejorar|limpias|limpiar|aceleras|acelerar)\b|"
            # observación sostenida en el tiempo, no una medición
            r"\b(?:mientras|while|durante|during|meanwhile)\b|"
            # otro equipo o pieza de hardware ajena
            r"\b(?:rtx|gtx|radeon|geforce|ryzen|4090|4080|4070|4060|"
            r"3090|3080|3070|3060)\b|"
            # Una familia de modelos de lenguaje nunca es hardware de este
            # equipo: preguntar por su consumo es conocimiento, no medición.
            r"\b(?:qwen|gemma|llama|mistral|mixtral|gpt|claude|deepseek|phi|"
            r"falcon|llm|modelo de lenguaje|language model)\b|"
            # "a la notebook" / "a mi laptop" uses the Spanish preposition,
            # not the indefinite article in "a small laptop".
            r"\b(?:un|una|an|otro|otra|another|"
            r"a(?!\s+(?:el|la|los|las|mi|mis|tu|tus|su|sus|"
            r"este|esta|estos|estas|ese|esa|esos|esas)\b))"
            r"\s+(?:\w+\s+){0,2}"
            r"(?:gpu|cpu|pc|notebook|laptop|equipo|computador|computadora|"
            r"juego|game|tarjeta|placa|maquina|machine)\b|"
            # An explicit other owner does not identify this machine, even
            # when its noun has a definite article ("la notebook de ...").
            r"\bde\s+otr[oa]\s+(?:persona|usuario|dueno|propietario)\b|"
            r"\b(?:someone|somebody)\s+else(?:'s)?\b|"
            # otro dispositivo con batería o consumo propio
            r"\b(?:auto|coche|carro|car|moto|bicicleta|bike|scooter|"
            r"celular|telefono|movil|phone|smartphone|tablet|ipad|"
            r"reloj|watch|audifonos|earbuds|control remoto|mando|remote|"
            r"linterna|flashlight|mouse|raton|drone|consola|console|"
            r"nintendo|playstation|xbox)\b|"
            # material de estudio o documentación
            r"\b(?:articulo|article|documento|document|paper|arquitectura|"
            r"architecture|manual|libro|book|clase|course|codigo|code)\b|"
            # memoria privada del asistente, no memoria del equipo
            r"\b(?:privada|private)\b|"
            r"\b(?:memoria|memory)\b.{0,30}"
            r"\b(?:personal|usuario|user|baxy|asistente|assistant|"
            r"tienes|tenes|guardas|guardaste|sabes|recuerdas|"
            r"de mi|sobre mi|about me)\b|"
            r"\b(?:personal|usuario|user|baxy|asistente|assistant)\b.{0,30}"
            r"\b(?:memoria|memory)\b"
        ),
    ) or _has(text, rf"\b{_KNOWN_APPLICATION}\b")


def _bare_note_inventory_request(text: str) -> bool:
    """Recognize a complete, verbless request for the person's own notes."""

    folded = _strip_request_envelope(_fold(text))
    return _note_inventory_object(folded) and re.fullmatch(
        r"[¿?¡!\s]*(?:(?:mis|my)\s+(?:notas|notes)(?:\s+(?:guardadas|saved))?|"
        r"(?:tengo|do\s+i\s+have)\s+(?:alguna|algunas|any)?\s*(?:notas?|notes?)"
        r"(?:\s+(?:guardadas?|saved))?)[\s.!?]*",
        folded,
        re.IGNORECASE,
    ) is not None


def _note_inventory_object(text: str) -> bool:
    """True when the person is listing notes, not asking for Notepad."""

    remainder = re.sub(_NOTEPAD_OBJECT, " ", text, flags=re.IGNORECASE)
    return bool(
        re.search(
            r"\b(?:notas?|notes?|apuntes?|anotaciones?|memos?)\b",
            remainder,
            re.IGNORECASE,
        )
    )


def _system_status_domain(text: str) -> bool:
    text = _strip_request_envelope(text)
    if _is_machine_knowledge_or_diagnosis(text) or _is_past_or_hypothetical_state(
        text,
    ):
        return False
    if _has(text, _CONNECTED_INVENTORY):
        return False
    if _has(
        text,
        r"\b(?:computador|computer|pc|ram|cpu)\b",
    ):
        return True
    if _has(text, r"\b(?:memoria|memory)\b") and _has(
        text,
        r"\b(?:uso|usan?|use|usage|utilizada|used|libre|free|disponible|available)\b",
    ):
        return True
    if _machine_status_scope(text) is not None:
        return True
    return _has(text, _UNQUALIFIED_MACHINE)


def _process_list_domain(text: str) -> bool:
    if _is_past_or_hypothetical_state(text) or _has(
        text, r"\b(?:explica(?:me|r)?|explain|como funciona(?:n)?|por que|why)\b|"
        r"\b(?:que es un|que son los|what is a|what are)\s+(?:proceso|process)",
    ):
        return False
    names_process = _has(
        text,
        r"\b(?:procesos?|process(?:es)?|task manager|administrador de tareas)\b|"
        r"\b(?:programas?|programs?|apps?|aplicacion(?:es)?)\b.{0,64}"
        r"\b(?:memoria|memory|cpu|ram|comiendo|eating)\b",
    )
    excluded = _has(
        text,
        (
            r"\b(?:biologic[oa]s?|biological|celular(?:es)?|cellular|"
            r"metabolic[oa]s?|metabolic|organismo|"
            r"ecosistema|contratacion|hiring|reclutamiento|recruitment|"
            r"empresa|business|negocio|seleccion de personal|fabricacion|"
            r"manufacturing|judicial(?:es)?|administrativ[oa]s?)\b"
        ),
    )
    computing = _has(
        text,
        (
            r"\b(?:sistema|system|computador|computer|pc|windows|"
            r"ejecucion|ejecutando|corriendo|funcionando|dando vueltas|running|activos?|active|"
            r"task manager|administrador de tareas|"
            r"cpu|ram|procesador|processor|memoria|memory|working set|consume|consumen|consuming|usan?|uses?|usage|"
            r"recursos|resources|por nombre|by name|observados?|observed|observar|ves ahora|"
            r"cuantos|cantidad|numero|how many|count)\b"
        ),
    )
    direct_inventory = re.fullmatch(
        r"(?:lista|listar|list|show|muestra|muestrame|mostrame|enumera|enumerate)\s+"
        r"(?:(?:los|the|active|activos?)\s+)?(?:procesos?|process(?:es)?)"
        r"[\s.!?]*", text, re.IGNORECASE,
    ) is not None
    return names_process and (computing or direct_inventory) and not excluded


def _direct_process_inventory_request(text: str) -> bool:
    return _process_list_domain(text) and _has(
        text, rf"^[¿?¡!\s]*{_REQUEST_PREFIX}(?:{_LIST}|mostrame|dime|dame|tell|"
        r"cuenta|count|ordena|sort|quiero|which|what|que|cual|cuales|cuantos|how)\b",
    )


def process_inventory_arguments(text: str) -> dict[str, object] | None:
    """Keep rank, metric and spoken page size bound to the process request."""
    text = _strip_request_envelope(_fold(text)).strip(" ¿?¡!.")
    if not _process_list_domain(text):
        return None
    sorts = {
        sort for sort, pattern in (
            ("cpu", r"\b(?:cpu|procesador|processor)\b"),
            ("memory", r"\b(?:ram|memoria|memory|working set)\b"),
            ("name", r"\b(?:por nombre|by name)\b"),
        ) if _has(text, pattern)
    }
    if len(sorts) > 1:
        return None
    result: dict[str, object] = {"sort": next(iter(sorts))} if sorts else {}
    number = r"(?:\d+|" + "|".join(
        re.escape(word) for word in sorted(_PERCENTAGE_WORD_VALUES, key=len, reverse=True)
    ) + r")"
    sizes = list(re.finditer(
        rf"\b(?:top|primeros|first|hasta|up\s+to)\s+(?P<rank>{number})\b|"
        rf"\b(?P<count>{number})\s+(?:(?:running|active|activos)\s+)?"
        r"(?:procesos?|process(?:es)?)\b", text,
    ))
    values = set()
    for match in sizes:
        raw = match.group("rank") or match.group("count")
        values.add(int(raw) if raw.isdecimal() else _PERCENTAGE_WORD_VALUES[raw])
    # A number outside a rank frame may be a PID, threshold or another action.
    remainder = text
    for match in reversed(sizes):
        remainder = remainder[:match.start()] + remainder[match.end():]
    if len(values) > 1 or _has(remainder, r"\d"):
        return None
    if values:
        value = next(iter(values))
        if not 1 <= value <= 50:
            return None
        result["limit"] = value
    elif _has(text, r"\b(?:que proceso|which process|what process)\b"):
        result["limit"] = 1
    return result


def _other_device_effect_scope(text: str) -> bool:
    """Reject effects explicitly scoped to a separate personal device."""

    return _has(
        text,
        (
            r"\b(?:en|on)\s+(?:(?:el|la|un|una|mi)\s+|"
            r"(?:(?:my|the|a)\s+)?(?:[a-z]+(?:'s)?\s+){0,2})?"
            r"(?:telefono|movil|celular|phone|smartphone|tablet|ipad|"
            r"iphone|reloj|watch|consola|console|xbox|playstation)\b|"
            r"\bfrom\s+(?:my|the|a)\s+(?:phone|smartphone|tablet)\b|"
            r"\b(?:into|to)\s+(?:my|the|a)\s+"
            r"(?:phone|smartphone|tablet|watch|console)\b|"
            r"\b(?:on|in)\s+another\s+(?:computer|device|pc)\b|"
            r"\ben\s+otro\s+(?:computador|equipo|pc|dispositivo)\b"
        ),
    )


def _local_internet_connection_query(text: str) -> bool:
    """A current local connection check is not a request for internet content."""
    machine_en = r"(?:this|the|my)\s+(?:computer|pc|machine)"
    machine_es = r"(?:este|el|mi)\s+(?:equipo|pc|computador(?:a)?|ordenador)"
    state_en = r"(?:connected\s+to\s+(?:the\s+)?internet|online)"
    state_es = r"conectad[oa]\s+a\s+internet"
    return re.fullmatch(
        rf"[¿?\s]*(?:"
        rf"(?:is\s+{machine_en}|am\s+i)\s+{state_en}|"
        rf"(?:check|verify)\s+(?:whether|if)\s+{machine_en}\s+is\s+{state_en}|"
        rf"esta\s+{machine_es}\s+{state_es}|"
        rf"(?:comprueba|revisa|verifica)\s+si\s+{machine_es}\s+esta\s+{state_es}"
        r")(?:\s+(?:right\s+now|now|ahora|actualmente))?[.!?\s]*",
        text,
        re.IGNORECASE,
    ) is not None


def _network_status_domain(text: str) -> bool:
    if _has(
        text,
        r"\b(?:wi[\s-]?fi|internet|conexion|connection)\b",
    ):
        return True
    if _has(
        text,
        r"\b(?:red|network)\s+(?:(?:de|of)\s+)?(?:neuronal|neural|"
        r"ferroviaria|rail|transporte|transport|social|electrica|electric)\b",
    ):
        return False
    return _has(
        text,
        r"\b(?:como\s+esta|how\s+is)\s+(?:la\s+red|the\s+network)\b|"
        r"\b(?:la\s+red|the\s+network|network)\b.{0,50}"
        r"\b(?:estado|status|salud|health|general|conectad[oa]|connected|"
        r"disponible|available|funciona|working)\b",
    )


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


def _volume_domain(text: str) -> bool:
    if _has_app_scoped_audio(text):
        return False
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
            "altavoz",
            "altavoces",
            "speaker",
            "speakers",
            "parlante",
            "parlantes",
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
            r"^(?:al?|en|esta|estan|actual|actualmente|ahora|ahorita|"
            r"quedo|puesto|configurado|tiene|tienes|tengo|hay|"
            r"to|at|by|up|down|level|is|are|now|currently|set|there|"
            r"\d{1,3}\s*(?:%|por ciento|percent|puntos?|points?)?|"
            rf"por favor|please|que\s+tenga\s+(?:ahora\s+)?(?:el\s+)?{_LOCAL_VOLUME_DEVICE})\b"
        ),
    )


# Verbos que ponen o quitan el silencio global. «apaga» y «activa» solo
# cuentan con un objeto de audio explícito, porque también gobiernan el equipo
# y otros dispositivos.
_UNMUTE_VERB = (
    r"(?:unmute|desmutea(?:me|lo|la)?|desmutear(?:lo|la)?|desmutees|"
    r"des(?:s)?ilenci(?:a(?:r(?:lo|la)?|me|lo|la)?|es))"
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
            r"(?:audio|sonido|sound|musica|music)\b|"
            rf"\b{_MUTE_VERB}\s+"
            r"(?:(?:el|la|los|las|the|mi|my)\s+)?"
            r"(?:(?:computador|computadora|computer|equipo|pc)\s+)?"
            r"(?:altavoz|altavoces|parlante|parlantes|speaker|speakers)\b|"
            # Un objeto total («todo»/«everything») también nombra el audio
            # global: el fixture canónico de argumentos usa exactamente
            # «mute everything please» para audio.mute.
            r"\b(?:silencia|silenciar|mutea|mutear|mute)\s+"
            r"(?:todo|everything)(?:\s+(?:please|por favor))?\b|"
            # Poner o quitar el estado de silencio, sin nombrar el verbo.
            r"\b(?:quita|quitar|saca|sacar|remove)\s+(?:el\s+)?"
            r"(?:silencio|mute|mudo)\b|"
            r"\b(?:pon|poner|ponle|deja|dejar|put|leave)\s+"
            r"(?:(?:el|la|the)\s+)?(?:\w+\s+){0,2}"
            r"(?:en|in|on)\s+(?:mudo|silencio|mute|silent)\b|"
            r"\bturn\s+(?:the\s+)?(?:audio|sound|volume)\s+back\s+on\b|"
            # Órdenes elípticas inequívocas: sólo existe un silencio global.
            rf"^[¿?¡!\s]*{_UNMUTE_VERB}"
            r"(?:\s+(?:it|please|pls|plz|por favor|porfa|todo|everything|el audio|"
            r"the audio))?[\s?!.]*$"
        ),
    )


_SET_VOLUME_VERB = (
    r"(?:pon(?:me|le|e|elo|ele|lo)?|poner|fija|ajusta|adjust|establece|set|"
    r"cambia|change|deja|dejame|leave)"
)
_VOLUME_UP_VERB = r"(?:sube(?:lo|la)?|subi|suvi|subir|aumenta|aumentar|incrementa|incrementar|increase|raise|up)"
_VOLUME_DOWN_VERB = r"(?:baja(?:lo|la)?|bajar|reduce|reducir|decrease|lower|down)"


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


def app_volume_request(
    text: str,
    application_names: Iterable[str] | ApplicationCatalogIndex,
) -> tuple[str, str, int | None] | None:
    """AUDIO1787 «subí el volumen de spotify»: (catalog display name, direction, amount or None).

    A relative volume verb whose object is one authenticated application's
    volume, in Spanish (volumen de X) or English (X's volume / turn up X
    volume); the amount is optional and, when absent, asked (owner rule on
    relative volume without a quantity). The system volume readers keep
    every request that names no application.
    """
    if (
        not effect_request_is_authoritative(text)
        or _other_device_effect_scope(_fold(text))
        or _is_negative_effect_clause(_fold(text))
    ):
        return None
    folded = _strip_request_envelope(_fold(text))
    if _has(folded, r"\b(?:o|or)\b") or len(_request_clauses(folded)) != 1:
        return None
    match = _APP_VOLUME_SPANISH.match(folded) or _APP_VOLUME_ENGLISH.match(folded) or _APP_VOLUME_ENGLISH_SPLIT.match(folded)
    if match is None:
        return None
    verb = match.group("verb")
    if re.fullmatch(rf"{_VOLUME_UP_VERB}|turn\s+up|raise|increase|bump\s+up|crank\s+up|up", verb):
        direction = "up"
    elif re.fullmatch(rf"{_VOLUME_DOWN_VERB}|turn\s+down|lower|decrease|down", verb):
        direction = "down"
    else:
        return None
    raw_app = match.group("app").strip(" ,;:")
    if _has(raw_app, r"\b(?:sistema|equipo|pc|computador(?:a)?|ordenador|system|computer|windows|todo|everything|musica|music)\b"):
        return None
    catalog = build_application_catalog_index(application_names)
    keys = {_authenticated_close_key(form, catalog) for form, _ in _application_target_forms(raw_app)}
    keys.discard(None)
    if len(keys) != 1:
        return None
    key = next(iter(keys))
    names = {name for name, entry_key in catalog.entries if entry_key == key}
    if len(names) != 1:
        return None
    raw_amount = match.group("amount") or match.group("amount2")
    amount = int(raw_amount) if raw_amount is not None else None
    if amount is not None and not 1 <= amount <= 100:
        return None
    return (next(iter(names)), direction, amount)


def _completed_missing_app_volume_request(
    text: str, previous_user_text: str | None, available_operations: Iterable[str],
    application_names: Iterable[str] | ApplicationCatalogIndex = (),
) -> str | None:
    """AUDIO1787 «subí el volumen de spotify» → «¿cuánto?» → «20»: the bare amount
    answer completes the application volume request as «… en 20»."""

    if not previous_user_text:
        return None
    answer = _strip_request_envelope(_fold(text)).strip()
    found = re.fullmatch(
        r"(?:(?:en|by|a|al|to|unos|unas|about)\s+)?(?P<amount>\d{1,3})\s*(?:%|por\s+ciento|percent|puntos?|points?)?[\s.!?]*",
        answer,
    )
    if found is None:
        return None
    prior = resolve_explicit_clarification_intent(previous_user_text, available_operations, application_names)
    if prior is None or prior.operations != ("audio.app.volume.adjust",) or prior.missing_fields != ("amount",):
        return None
    previous_folded = _strip_request_envelope(_fold(previous_user_text))
    joiner = " by " if (_APP_VOLUME_ENGLISH.match(previous_folded) or _APP_VOLUME_ENGLISH_SPLIT.match(previous_folded)) else " en "
    return previous_user_text.strip().rstrip(" .!?") + joiner + found.group("amount")

# Señales de que se pregunta por el nivel actual de audio, no por cambiarlo.
_AUDIO_LEVEL_CUE = (
    r"\b(?:en que|a que|cuanto|cuanta|estado|status|actual|current|"
    r"nivel|level|quedo|how much)\b|"
    r"\b(?:que|what|cual|which)\s+(?:volumen|volume)\b"
)

# Verbos de observación que, por sí solos, ya piden leer el audio.
_AUDIO_OBSERVATION_HEAD = (
    r"(?:dime|decime|dame|muestra|muestrame|mostrame|show|display|ver|"
    r"revisa|revisar|comprueba|chequea|checa|verifica|mira|fijate|check)"
)


def _indirect_audio_mute_state_query(text: str) -> bool:
    """An entire current-state question, with no conditional action tail."""
    target_es = r"(?:(?:el|mi)\s+)?(?:audio|sonido|volumen)"
    state_es = r"(?:silenciad[oa]|mutead[oa]|en\s+(?:silencio|mudo))"
    target_en = r"(?:(?:the|my)\s+)?(?:audio|sound|volume)"
    state_en = r"(?:muted|on\s+mute|silent)"
    return re.fullmatch(
        rf"[¿?¡!\s]*{_AUDIO_OBSERVATION_HEAD}\s+(?:si|if|whether)\s+"
        rf"(?:{target_es}\s+esta\s+{state_es}|"
        rf"esta\s+{state_es}\s+{target_es}|"
        rf"{target_en}\s+is\s+{state_en})"
        r"(?:\s+(?:ahora|actualmente|now|right\s+now))?[\s.!?]*",
        text,
        re.IGNORECASE,
    ) is not None


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


def explicit_window_title(text: str) -> str | None:
    """Copy one explicitly named window title; never infer a process or HWND."""
    matches = tuple(
        re.finditer(
            r"\b(?:ventana|window)\s+(?:titulada|titled|llamada|called|named|"
            r"(?:con|with)(?:\s+(?:el|the))?\s+(?:t[ií]tulo|title|nombre|name))\s+",
            text,
            re.IGNORECASE,
        )
    )
    if len(matches) != 1:
        return None
    title = text[matches[0].end() :].strip()
    if not title:
        return None
    quotes = {'"': '"', "'": "'", "«": "»", "“": "”", "‘": "’"}
    closing = quotes.get(title[0])
    if closing is not None:
        end = title.find(closing, 1)
        if end < 0 or title[end + 1 :].strip(" .!?"):
            return None
        title = title[1:end]
    return title if title.strip() and len(title) <= 260 and "\0" not in title else None


def has_named_window_target(text: str) -> bool:
    # The same literal relation serves recognition and argument grounding.
    # It supplies a query, never authority over an unobserved window.
    return explicit_window_title(text) is not None


def window_inventory_arguments(text: str) -> dict[str, object] | None:
    """Project an explicit global window inventory into the existing selector.

    Match the entire request so app/title qualifiers, physical windows, quoted
    orders and another requested action cannot silently widen into all windows.
    Filters and follow-up pages stay with their own argument/plan readers.
    """

    text = _strip_request_envelope(_fold(text)).strip(" ¿?¡!.")
    # «mostrame qué tengo abierto» asks for the same inventory without the
    # noun (WINDOWS1207).
    open_things = (
        r"(?:(?:lo\s+)?que\s+tengo\s+abierto|what\s+i\s+have\s+open|"
        r"what(?:'s|\s+is)\s+open|what\s+do\s+i\s+have\s+open)"
    )
    if not _has(text, rf"\b(?:ventanas?|windows?)\b|\b{open_things}\b"):
        return None
    number = r"(?:\d+|" + "|".join(
        re.escape(word) for word in sorted(_PERCENTAGE_WORD_VALUES, key=len, reverse=True)
    ) + r")"
    determiner = r"(?:(?:todas(?:\s+las)?|all(?:\s+the)?|las|mis|the|my)\s+)?"
    state = r"(?:abiertas|visibles|open|visible)"
    local = (
        r"(?:(?:de|del|en)\s+(?:(?:mi|el|este)\s+)?"
        r"(?:pc|equipo|computador(?:a)?|escritorio)|"
        r"(?:on|in|of)\s+(?:(?:my|the|this)\s+)?(?:pc|computer|desktop))"
    )
    noun = (
        rf"{determiner}(?:(?:primeras|first|hasta|up\s+to)\s+{number}\s+)?"
        rf"(?:{state}\s+)?(?:ventanas|windows)"
        rf"(?:\s+(?:{state}|{local}|(?:que\s+tengo|that\s+(?:i\s+have|are)|"
        rf"i\s+have|tengo|hay|estan|are)(?:\s+{state})?)){{0,3}}"
    )
    object_phrase = (
        rf"(?:(?:(?:el|la|los|the)\s+)?(?:titulos|titles|nombres|names|"
        rf"listado|lista|list|inventario|inventory)\s+(?:de|of)\s+)?{noun}"
    )
    read_head = (
        rf"(?:{_LIST}|{_MACHINE_STATUS_OBSERVATION_HEAD}|enumera|enumerate|"
        r"ensename|cuenta|count|tell\s+me|give\s+me|necesito|"
        r"quiero\s+ver|i\s+want\s+to\s+see|i\s+need\s+to\s+see|"
        r"fijate(?:\s+en)?|mira|mirame|chequea|checkea|revisa)"
    )
    # «ke ventanas tengo abiertas» (typo), «y cuántas ventanas?» (ellipsis),
    # «fijate qué ventanas tengo abiertas» (head + question): WINDOWS1207.
    question_head = (
        r"(?:(?:y|and)\s+)?(?:(?:dime|tell\s+me)\s+)?(?:que|ke|cuales|which|what|cuantas|how\s+many)"
        r"(?:\s+(?:son|are))?"
    )
    ending = r"(?:\s+(?:ahora|ahora\s+mismo|now|right\s+now))?(?:\s*[,;]?\s*(?:please|por\s+favor|porfa))?"
    # WINDOWS1315 H0419 «cuál es la ventana más grande»: a superlative over the
    # open windows is the same inventory read; the size comparison is made on
    # the observed geometry, never guessed.
    size_question = (
        r"(?:(?:dime|decime|tell\s+me)\s+)?(?:cual|que|which|what)\s+(?:es\s+|is\s+)?"
        r"(?:(?:de|of)\s+(?:(?:las|mis|the|my)\s+)?(?:ventanas|windows)(?:\s+(?:abiertas|open))?\s+(?:es\s+|is\s+)?)?"
        r"(?:(?:la|the)\s+)?(?:(?:ventana|window)\s+(?:es\s+|is\s+)?(?:(?:la|the)\s+)?)?"
        r"(?:mas\s+(?:grande|chica|pequena|ancha|alta)|"
        r"largest|biggest|smallest|widest|tallest)(?:\s+(?:ventana|window))?"
        r"(?:\s+(?:que\s+tengo\s+abierta|abierta|open|que\s+tengo|i\s+have\s+open))?"
    )
    if not re.fullmatch(
        rf"(?:(?:{read_head}\s+(?:{question_head}\s+)?|{question_head}\s+)(?:{object_phrase}|{open_things})|"
        rf"{object_phrase}\s*[,;]\s*(?:muestramelas|enumeralas|list\s+them|show\s+them)|"
        rf"{size_question})"
        rf"{ending}", text, re.IGNORECASE,
    ):
        return None
    result: dict[str, object] = {"process": "*", "byTitle": False}
    if re.fullmatch(rf"{size_question}{ending}", text, re.IGNORECASE):
        # WINDOWS1317: the comparison must see every observed window; ask for
        # the largest page the catalog allows (the App's default is 20).
        result["limit"] = 50
        return result
    limit = _match(text, rf"\b(?:primeras|first|hasta|up\s+to)\s+(?P<number>{number})\b")
    if limit is not None:
        raw = limit.group("number")
        value = int(raw) if raw.isdecimal() else _PERCENTAGE_WORD_VALUES[raw]
        if not 1 <= value <= 50:
            return None
        result["limit"] = value
    return result


def _window_domain(text: str) -> bool:
    if not _has(text, r"\b(?:ventana|window)\b"):
        return False
    if has_named_window_target(text):
        return True
    if _has(
        text,
        (
            r"\b(?:navegador|browser|aplicacion|application|programa|program|"
            r"spotify|opera|chrome|edge|firefox|notepad|bloc de notas|"
            r"calculadora|calculator)\b"
        ),
    ):
        return True
    if _has(
        text,
        (
            r"\b(?:ventana|window)\s+(?:activa|active|actual|current)\b"
            r"(?!\s+(?:de|del|of|para|for)\b)|"
            r"\b(?:ventana|window)\s+(?:esta|is)\s+(?:activa|active)\b"
            r"|\b(?:ventana|window)\s+(?:que\s+(?:esta|tengo)\s+)?(?:en\s+)?"
            r"primer\s+plano\b"
            r"|\bforeground\s+window\b"
        ),
    ):
        return True
    if _has(
        text,
        r"\b(?:esta|this)\s+(?:ventana|window)\b(?!\s+of\s+opportunity)",
    ):
        return True
    return _has(
        text,
        (
            r"\b(?:ventana|window)\b"
            r"(?=\s*(?:[\s?!.]*$|,?\s+(?:y luego|y despues|and then|then)\b))"
        ),
    )


def _clipboard_selection_domain(text: str) -> bool:
    return _has(text, r"\b(?:seleccion|selection)\b") and not _has(
        text,
        (
            r"\b(?:seleccion|selection)\s+(?:nacional|national|electoral|"
            r"deportiva|sports?|de|del|of)\b"
        ),
    )


def _clipboard_copy_domain(text: str) -> bool:
    """Recognize a literal local source copied into the OS clipboard."""

    return _clipboard_selection_domain(text) or (
        _has(text, r"\b(?:copia|copiar|copy)\b")
        and _has(
            text,
            r"\b(?:texto|text)\b.{0,100}\b(?:al|to the)\s+"
            r"(?:portapapeles|clipboard)\b",
        )
    )


def _clipboard_paste_domain(text: str) -> bool:
    """Recognize a paste of the OS clipboard rather than physical gluing.

    ``pegar`` means both "paste" and "glue", so the verb alone proved nothing:
    "pega la etiqueta en el frasco de mermelada" resolved to clipboard.paste
    and would have pasted into whatever had focus. The clipboard has to be
    named, or the pasted thing has to be what was copied, or the target has to
    be the focused control. Its sibling ``_clipboard_copy_domain`` already
    guarded copying this way; only pasting was left open.
    """

    return (
        _has(text, r"\bportapapeles\b|\bclipboard\b")
        or _has(
            text,
            r"\b(?:lo|el\s+texto|la\s+seleccion|what)\s+que\s+"
            r"(?:copie|copiaste|copiamos)\b"
            r"|\b(?:copie|copiaste|copiado|copiada|copied)\b",
        )
        or _has(
            text,
            r"\b(?:pegalo|pegala|paste\s+it)\b.{0,24}"
            r"\b(?:aca|aqui|ahi|here|there)\b|"
            r"\b(?:aca|aqui|ahi|here|there)\b.{0,16}\b(?:pegalo|pegala|paste)\b",
        )
        or _has(
            text,
            r"\b(?:campo|control|cuadro|casilla|field|box)\b"
            r".{0,24}\b(?:enfocad[oa]|activ[oa]|focused|active)\b"
            r"|\b(?:enfocad[oa]|focused)\b.{0,24}\b(?:campo|control|field)\b",
        )
        # A destination that belongs to the machine also settles the sense:
        # "pega esto en el bloc de notas" is a paste, "pega el patch en la
        # mochila" is not.
        or _has(
            text,
            rf"\b(?:en|into|in|on)\b.{{0,24}}\b(?:{_KNOWN_APPLICATION}|"
            r"documento|documentos|document|documents|nota|notas|note|notes|"
            r"archivo|archivos|file|files|chat|navegador|browser|correo|email|"
            r"terminal|consola|console|editor|celda|cell|formulario|form|"
            r"buscador|barra\s+de\s+direcciones|address\s+bar)\b",
        )
    )


def _latest_email_domain(text: str) -> bool:
    return (
        _has(
            text,
            r"\b(?:correos?|emails?|mails?|buzon|inbox|inbox\s+messages?)\b",
        )
        and _has(
            text,
            r"\b(?:reciente|latest|ultimo|ultima|newest|most\s+recent)\b|"
            r"\b(?:newly\s+arrived|just\s+arrived|just\s+received|"
            r"acaba\s+de\s+llegar|"
            r"recien\s+llego|nullier\s+i[dt]|era\s+(?:y|ive)\s+blast)\b",
        )
        and not _has(
            text,
            (
                r"\b(?:frase|phrase|palabras?|words?|texto|text)\b"
                r".{0,80}\b(?:correo|email|mail)\b"
            ),
        )
    )


def _spoken_package_id(text: str) -> str | None:
    """Recover exact common winget IDs after ASR removes their separator."""

    folded = _fold(text)
    aliases = (
        (r"\b(?:mozilla|mozzala)[\s.,-]+firefox\b", "Mozilla.Firefox"),
        (
            r"\bgithub[\s.,-]+github[\s.,-]*desktop\b",
            "GitHub.GitHubDesktop",
        ),
        (r"\bvlc\b", "VideoLAN.VLC"),
    )
    for pattern, package_id in aliases:
        if _has(folded, pattern):
            return package_id
    package = re.search(
        r"(?<![a-z0-9._-])(?P<id>[a-z0-9][a-z0-9_-]+"
        r"(?:\.[a-z0-9_-]+)+)(?![a-z0-9_-]|\.[a-z0-9_-])",
        text,
        re.IGNORECASE,
    )
    return package.group("id") if package is not None else None


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


def _spoken_radio_station_request(text: str) -> bool:
    """Recognize a named/dial radio request without treating every `pon` as media."""

    folded = _fold(text)
    return _head_is(
        _request_head(folded),
        r"(?:pon|ponme|pone|poneme|reproduce|reproducir|play|start|inicia|tune)",
    ) and _has(
        folded,
        r"(?:\bf\s*\.?\s*m\s*\.?\b|\ba\s*\.?\s*m\s*\.?\b|"
        r"\b(?:radio|station|emisora)\b)",
    )


def _desired_music_query(text: str) -> str | None:
    """Extract a bounded genre, artist or title query without choosing music.

    MUSIC1571: «pon algo de música» names nothing; a query that is only a
    music noun (with «algo de» in front) is not a query.
    """

    query = _desired_music_query_raw(text)
    if query is not None and re.fullmatch(
        r"(?:(?:algo|un\s+poco|something|some)\s+(?:de\s+|of\s+)?)?"
        r"(?:musica|music|musika|cancion(?:es)?|song(?:s)?|temas?|videos?)",
        _fold(query).strip(),
    ):
        return None
    return query


def _desired_music_query_raw(text: str) -> str | None:
    """Extract a bounded genre, artist or title query without choosing music."""

    folded = _strip_request_envelope(_fold(text))
    request = re.fullmatch(
        r"(?:(?:i\s+)?(?:need|want)|necesito|quiero)\s+"
        r"(?:(?:some|any|algo\s+de|un\s+poco\s+de)\s+)?"
        r"(?P<query>(?:rap|hip\s+hop|rock|pop|jazz|blues|reggae|"
        r"classical|clasica|metal|salsa|bachata|cumbia|reggaeton))"
        r"(?:\s+(?:music|musica))?[\s.!?]*",
        folded,
        re.IGNORECASE,
    )
    if request is not None:
        return request.group("query").strip()
    playlist = re.fullmatch(
        r"(?:enciende|inicia|pon|reproduce|start|play)\s+"
        r"(?:(?:la|the)\s+)?(?:lista\s+de\s+reproduccion|playlist)\b"
        r".{0,160}\b(?:musica\s+)?"
        r"(?P<query>rock|rap|hip\s+hop|pop|jazz|blues|reggae|clasica|"
        r"classical|metal|salsa|bachata|cumbia|reggaeton)\b"
        r".{0,48}[\s.!?]*",
        folded,
        re.IGNORECASE,
    )
    if playlist is not None:
        return playlist.group("query").strip()
    figurative = re.fullmatch(
        r"(?:comfort|soothe)\s+my\s+ears\s+with\s+"
        r"(?P<query>[a-z0-9][a-z0-9 .&'_-]{0,120})[\s.!?]*",
        folded,
        re.IGNORECASE,
    )
    if figurative is not None:
        return figurative.group("query").strip()
    named = re.fullmatch(
        (
            r"(?:quiero\s+que\s+me\s+pongas|i\s+want\s+you\s+to\s+play)\s+"
            r"(?P<query>\S(?:.{0,160}?\S)?)\s*[.!?]*"
        ),
        folded,
        re.IGNORECASE,
    )
    query = named.group("query").strip() if named is not None else _explicit_named_music_query(text)
    if query is None:
        return None
    if not 1 <= len(query.split()) <= 12 or _has(
        _fold(query),
        r"\b(?:alarma|alarm|temporizador|timer|volumen|volume|sonido|sound|"
        r"pantalla|screen|modo|mode|video|movie|pelicula|juego|game|"
        r"multijugador|multiplayer|with|against|conmigo|contra)\b",
    ):
        return None
    return query


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


def _explicit_named_music_query(text: str) -> str | None:
    """Keep the supplied artist/title of one current imperative verbatim."""

    named = re.fullmatch(
        r"(?:pon|ponme|poneme|pone|poné|reproduce|reproducir|reproduc[ií]|play|toca|tocá|tocame|tocáme|toque)\s+"
        r"(?:(?P<music>(?:(?:una?|la|las|the|a|some)\s+)?"
        r"(?:m[uú]sica|music|canci[oó]n(?:es)?|songs?|tracks?))\s+"
        r"(?:de|by|from)\s+)?"
        r"(?P<query>\S(?:.{0,160}?\S)?)\s*[.!?]*",
        _strip_request_envelope(text), re.IGNORECASE,
    )
    if named is None:
        return None
    folded = _fold(text)
    query = named.group("query").strip()
    if (
        named.group("music") is None
        and not _has(_fold(query), r"\S\s+(?:de|by)\s+\S")
        # MUSIC1749 «poné rock en spotify»: with the provider named, one word
        # (a genre, an artist) is the thing to play there; a generic noun
        # («música», «una canción») still asks what to play.
        and not (
            _has(_fold(query), r"\S\s+(?:en|on)\s+spotify\b")
            and not _has(
                re.sub(r"\s+(?:en|on)\s+spotify\b.*$", "", _fold(query)).strip(),
                r"^(?:(?:una?|la|el|los|las|algo\s+de|some|a|the)\s+)?"
                r"(?:m[uú]sica|music|canci[oó]n(?:es)?|songs?|temas?|tracks?|algo|something|"
                r"cualquier\s+cosa|anything|lo\s+que\s+sea)$",
            )
        )
        # VIDEO1715 «poné Tom and Jerry»: a proper title in the person's own
        # capitals (two capitalised words, connectors allowed) is the thing to
        # play; a single word or a known application name is not.
        and not _title_case_media_title(query)
    ) or (
        not effect_request_is_authoritative(text)
        or _has_unsupported_deferred_effect(folded)
        or len(_request_clauses(folded)) != 1
        or _other_device_effect_scope(folded)
        or _fold(query) in {"it", "them", "this", "that", "esto", "eso", "esa", "ese"}
        or _has(
            _fold(query),
            r"\b(?:archivo|file|carpeta|folder|pagina|page|fondo|wallpaper|"
            r"portapapeles|clipboard|contrasena|password)\b|"
            # VIDEO1715: a title on a named streaming service is that service's
            # session, never the local YouTube playback.
            r"\b(?:en|on)\s+(?:youtube|netflix|apple\s+music|apple\s+tv|disney|prime|hbo|max|"
            r"crunchyroll|star|paramount|twitch|hulu|peacock)\b",
        )
    ):
        return None
    # MUSIC1749: «pon michael jackson en spotify» names the provider, not the
    # music; the query is what precedes it.
    query = re.sub(r"\s*[,;:]?\s+(?:en|on)\s+spotify\b.*$", "", query, flags=re.IGNORECASE).strip(" ,;:.!?")
    return query or None


def _wake_alarm_request(text: str) -> bool:
    """Recognize a direct wake-up alarm with one explicit clock."""

    folded = _strip_request_envelope(_fold(text))
    return (
        re.fullmatch(
            r"(?:i\s+need\s+you\s+to\s+)?"
            r"(?:(?:wake|get)\s+me(?:\s+up)?|despiertame|despertame|levantame)\s+"
            r"(?:"
            rf"(?:in|en|dentro\s+de|within)\s+{_RELATIVE_DURATION_PATTERN}|"
            r"(?:at|a\s+las?|para\s+las?)\s+"
            r"(?:[0-2]?\d|one|two|three|four|five|six|seven|eight|nine|ten|"
            r"eleven|twelve|una?|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|"
            r"diez|once|doce)(?::[0-5]\d)?\s*"
            r"(?:a\.?\s*m\.?|p\.?\s*m\.?|de\s+la\s+manana|de\s+la\s+tarde|"
            r"de\s+la\s+noche|in\s+the\s+morning|in\s+the\s+afternoon|"
            r"in\s+the\s+evening)"
            r")[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )


def _direct_alarm_schedule_request(text: str) -> bool:
    """Read an alarm speech act, allowing its bounded time before the verb."""

    folded = _strip_request_envelope(_fold(text))
    if _wake_alarm_request(folded):
        return True
    if (
        _is_negative_effect_clause(folded)
        or _is_meta_or_tool_denial(folded)
        or _is_past_or_hypothetical_state(folded)
        or _has_contradictory_correction(folded)
        or _other_device_effect_scope(folded)
        or _has(folded, r'["“”«»;]|\b(?:if|si)\b')
    ):
        return False
    temporal = re.match(
        rf"^(?:(?:in|en|dentro de|within)\s+)?"
        rf"(?:{_CLOCK_TIME_SELECTOR}|{_BOUNDED_TEMPORAL_SELECTOR})\s*[, :]\s*",
        folded,
    )
    body = _strip_request_envelope(folded[temporal.end():]) if temporal else folded
    return (
        len(_request_clauses(body)) == 1
        and _has(body, r"\b(?:alarm|alarma)\b")
        and _has(
            body,
            rf"^(?:(?:please|por\s+favor)\s+)?"
            rf"(?:{_SCHEDULING_VERB}|new|nueva|ring|sound)\b|\bwake\s+up\s+alarm\b",
        )
        and _reminder_has_actionable_due(folded)
        and not _has(body, r"\b(?:check|comprueba|revisa|is\s+there|hay)\b")
    )


def _literal_memo_payload(text: str) -> str | None:
    """Return the payload of a compact ``create a memo to ...`` request."""

    folded = _strip_request_envelope(_fold(text))
    match = re.fullmatch(
        r"(?:create|make|add)\s+(?:a\s+)?memo\s+(?:to|that\s+says?)\s+"
        r"(?P<content>\S(?:.{0,480}?\S)?)[\s.!?]*",
        folded,
        re.IGNORECASE,
    )
    if match is not None:
        return match.group("content").strip()
    reversed_mixed_language = re.fullmatch(
        r"(?P<content>[a-z0-9][a-z0-9 ,&'-]{1,240}?)\s+"
        r"[^\x00-\x7f]{1,24}\s+memo\s+create\s+[^\x00-\x7f]{1,24}"
        r"[\s.!?]*",
        folded,
        re.IGNORECASE,
    )
    return (
        reversed_mixed_language.group("content").strip()
        if reversed_mixed_language is not None
        else None
    )


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
            r"\b(?:audio|media|musica|music|reproduccion|playback|cancion|song|pista|track)\b",
        )
        and not _has(folded, r"\b(?:grabacion|recording|microfono|microphone|mic)\b")
    )


def _media_play_domain(text: str) -> bool:
    if _underspecified_video_request(text):
        return False
    audio_setting = _has(
        text,
        (
            r"\b(?:volumen|volume|audio|sonido|sound)\b"
            r".{0,60}(?:\b\d{1,3}\b|%)"
        ),
    )
    explicit_spotify_context = _has(
        text,
        (
            rf"\b{_OPEN}\b\s+"
            r"(?:(?:el|la|the)\s+)?"
            r"(?:(?:aplicacion|application|app)\s+)?spotify\b"
        ),
    ) and _has(
        text,
        r"\b(?:reproduce|reproducir|play|pon|ponme)\b",
    )
    direct_query = (
        _head_is(_request_head(text), r"(?:reproduce|reproducir|play)")
        and _has(
            text,
            r"^[¿?¡!\s]*(?:(?:por favor|please)\s*[,;:]?\s*)?"
            r"(?:reproduce|reproducir|play|pon)\s+\S.+",
        )
        and not _has(text, r"\b(?:boton|button|video|pelicula|movie|archivo|file)\b")
    )
    live_music_query = re.match(
        r"^[^\w]*(?:(?:por favor|please)\s*[,;:]?\s*)?"
        r"(?:pon|ponme|pone|poneme)\s+(?P<query>.+?)\s+en\s+vivo"
        r"(?:\s+(?:por favor|please))?[\s.!?]*$",
        text,
    )
    if live_music_query is not None:
        query = live_music_query.group("query").strip()
        # "en vivo" is a strong music-performance cue only when the object is
        # not itself a live device, stream, setting, alarm, or display. This
        # keeps the recovery generic across artists without turning every
        # Spanish imperative headed by "pon" into Spotify authority.
        live_music_query = 1 <= len(query.split()) <= 12 and not _has(
            query,
            r"\b(?:camara|camera|television|tv|video|stream|transmision|"
            r"canal|channel|radio|alarma|alarm|temporizador|timer|"
            r"volumen|volume|sonido|sound|pantalla|screen|modo|mode|"
            r"ubicacion|location|gps|mapa|map|trafico|traffic)\b",
        )
    interactive_play = _has(
        text,
        (
            r"\b(?:play|juega|jugar|juguemos)\b.{0,80}"
            r"\b(?:with|against)\s+(?:me|us)\b|"
            r"\b(?:juega|jugar|juguemos)\b.{0,80}"
            r"\b(?:conmigo|con nosotros|contra mi|contra nosotros)\b"
        ),
    )
    return (
        (
            _has(text, r"\b(?:en|on)\s+spotify\b")
            or explicit_spotify_context
            or direct_query
            or _desired_music_query(text) is not None
            or _spoken_radio_station_request(text)
            or _bare_spoken_number_media_query(text) is not None
            or bool(live_music_query)
        )
        and not audio_setting
        and not interactive_play
    )


_OPEN_STATE_CONDITION = (
    r"^[¿?¡!\s]*(?:si|if)\s+(?:(?:tengo|esta|hay|i\s+have|there\s+is|is)\s+)?"
    r"(?:(?:el|la|the)\s+)?(?P<app>[a-z0-9][a-z0-9 .+-]{1,30}?)\s+"
    r"(?:(?:esta|is)\s+)?(?:abiert[oa]|open|running|corriendo|prendid[oa]|activ[oa])\s*,?\s*"
)


_MINIMIZE_ALL_REQUEST = re.compile(
    r"^[¿?¡!\s]*(?:(?:por\s+favor|please)\s*[,;:]?\s*)?"
    r"(?:minimiza|minimizame|minimizar|minimise|minimize)\s+(?:me\s+)?"
    r"(?:todas\s+(?:las\s+)?(?:ventanas|apps|aplicaciones)|todas|todo|"
    r"all(?:\s+(?:the|my|of\s+the))?(?:\s+(?:windows|apps|applications))?|everything)"
    r"(?:\s+(?:abiertas|open))?(?:\s*,?\s*(?:por\s+favor|please))?[\s.!?]*$"
)


_CLOSE_ALL_REQUEST = re.compile(
    r"^[¿?¡!\s]*(?:(?:por\s+favor|please)\s*[,;:]?\s*)?"
    r"(?:cierra|cerra|cerrar|cerrame|cierrame|close)\s+(?:me\s+)?"
    r"(?:todas\s+(?:las\s+)?(?:ventanas|apps|aplicaciones|cosas)|todo|todo\s+lo\s+que\s+(?:esta|tengo)\s+abierto|"
    r"all(?:\s+(?:the|my|of\s+the))?(?:\s+(?:windows|apps|applications))?|everything(?:\s+(?:that\s+is\s+)?open)?)"
    r"(?:\s+(?:abiertas|abierto|open))?(?:\s*,?\s*(?:por\s+favor|please))?[\s.!?]*$"
)


def close_all_request(folded: str) -> bool:
    """CLOSEALL1733 «cerrame todo», «cerrá todas las ventanas», «close everything»:
    one order over every desktop window (never a named one, never tabs)."""

    return _CLOSE_ALL_REQUEST.match(_strip_request_envelope(folded)) is not None


def minimize_all_request(folded: str) -> bool:
    """MINALL1687 «minimizá todas las ventanas», «minimizá todo»: one order
    over every desktop window, never a named one."""

    return _MINIMIZE_ALL_REQUEST.match(_strip_request_envelope(folded)) is not None


def conditional_open_pause_app(
    text: str,
    application_names: Iterable[str] | ApplicationCatalogIndex,
) -> str | None:
    """«si tengo spotify abierto pausalo»: the catalog display name of the
    application whose open window conditions a pause, else None."""

    folded = _strip_request_envelope(_fold(text))
    found = re.match(_OPEN_STATE_CONDITION + r"(?:pausalo|pausala|pausame|pausa|pausar|pause\s+it|pause)[\s.!?]*$", folded)
    if found is None:
        return None
    # The catalog resolver returns the display name the provider expects.
    return resolve_application_catalog_app_id("abre " + found.group("app"), application_names)


def _has_unsupported_deferred_effect(text: str) -> bool:
    """Veto immediate execution when the request actually asks for later."""

    # NETWORK1293 H0230 «decime si el wifi está prendido»: «decime si …» is an
    # indirect question, not a condition that defers the request. Read the
    # rest as the question itself; timing words after it still count.
    # APPS1613 H0275 «Abre Steam y dime si Fall Guys ya está instalado»: the
    # same indirect question after a conjunction or a clause boundary.
    text = re.sub(
        r"(^[¿?¡!\s]*|[,;.]\s*|\b(?:y|and|luego|then)\s+)"
        r"((?:decime|dime|contame|cuentame|tell\s+me|fijate|chequea|check)\s+)(?:si|if|whether)\b",
        r"\1\2",
        text,
        flags=re.IGNORECASE,
    )
    # Retaining a fact for a later question is not scheduling its write. Only
    # remove that subordinate purpose, leaving an earlier "tomorrow" or a
    # separate coordinated action visible to the existing timing check.
    deferred_scope = re.sub(
        rf"\b(?:recuerda|recuerdes|recordar|remember|recall)\b"
        rf"(?!\s+(?:to\s+)?(?:{_COVERAGE_ACTION_HEAD})\b)"
        rf"(?:(?!\b(?:y|and)\s+(?:(?:luego|despues|then)\s+)?"
        rf"(?:{_COVERAGE_ACTION_HEAD})\b)[^.!?;,]){{0,160}}?"
        r"(?P<purpose>\b(?:(?:para|for)\s+)?(?:"
        r"cuando\s+te\s+(?:lo\s+)?pregunte(?:\s+de\s+nuevo)?|"
        r"when\s+i\s+ask(?:\s+you)?(?:\s+again)?)\b)"
        r"(?=\s*(?:[.!?;,]|$))",
        lambda match: match.group(0)[:match.start("purpose") - match.start()] + " ",
        text,
        flags=re.IGNORECASE,
    )
    # Timing words inside a quoted message are payload, not scheduling for the
    # send operation itself: `send ... message “I arrive in ten minutes”` must
    # remain an immediate send. Timing outside the quote is deliberately kept,
    # so `send ... at seven` continues to fail closed until a scheduled-send
    # operation exists in the authenticated catalog.
    if _head_is(_request_head(text), r"(?:envia|enviar|manda|mandar|send)"):
        deferred_scope = re.sub(
            r"«[^»]*»|“[^”]*”|‘[^’]*’|\"[^\"]*\"|'[^']*'",
            " ",
            deferred_scope,
        )
    if _has(text, r"^[¿?¡!\s]*(?:crea|crear|create|make)\s+(?:una?\s+|a\s+)?(?:nota|note)\b"):
        # A quoted note body is data. Keep scheduling before its content
        # marker and conditional actions outside its closing quote visible.
        deferred_scope = re.sub(
            r'(\b(?:con\s+el\s+texto|with\s+the\s+text)\s+)'
            r'(?:"[^\"]*"|«[^»]*»|“[^”]*”)',
            r"\1 literal content",
            deferred_scope,
            flags=re.IGNORECASE,
        )
    # These phrases sequence a second explicit action; they do not defer the
    # mission to a later real-world event. Keep ``after that meeting`` and
    # other event-relative requests untouched and therefore fail-closed.
    deferred_scope = re.sub(
        rf"\b(?:after\s+(?:that|this)|despues\s+de\s+eso|tras\s+eso)\b"
        rf"(?=\s*[,;:]?[¿?¡!\s]*(?:{_COVERAGE_ACTION_HEAD}|"
        rf"{_SEQUENCE_NOMINAL_HEAD})\b)",
        " then ",
        deferred_scope,
        flags=re.IGNORECASE,
    )
    # A time expression after a literal note-content marker belongs to the
    # payload, not to the execution schedule. Inspect each clause separately so
    # an earlier request head cannot make a later note look deferred. A selector
    # before the marker (``create a note tomorrow that says ...``) remains
    # visible and therefore still fails closed.
    scoped_clauses = _request_clauses(deferred_scope)
    if any(_indirect_audio_mute_state_query(clause) for clause in scoped_clauses):
        # Only the subordinate question's marker is non-conditional. Preserve
        # every other clause so an actual "if ... then act" still vetoes now.
        deferred_scope = " . ".join(
            re.sub(r"\b(?:si|if)\b", "", clause, count=1, flags=re.IGNORECASE)
            if _indirect_audio_mute_state_query(clause) else clause
            for clause in scoped_clauses
        )
    if any(_literal_note_payload_request(clause) for clause in scoped_clauses):
        deferred_scope = " . ".join(
            "note literal payload" if _literal_note_payload_request(clause) else clause
            for clause in scoped_clauses
        )
    # This is an immediate ordering boundary inside the current mission, not
    # a request to wait for an external event. The complete phrase is removed;
    # ordinary ``before the meeting`` / ``antes de mañana`` remain deferred.
    deferred_scope = re.sub(
        r"\b(?:before\s+continuing|antes\s+de\s+continuar)\b",
        " ",
        deferred_scope,
        flags=re.IGNORECASE,
    )
    # MUSIC1675 H0421 «si tengo spotify abierto pausalo»: a condition on the
    # present state of an application (open now or not) is checked now by
    # the window read, not awaited; only future events stay deferred.
    deferred_scope = re.sub(_OPEN_STATE_CONDITION, " ", deferred_scope, count=1, flags=re.IGNORECASE)
    hard_deferred = _has(
        deferred_scope,
        (
            r"\b(?:manana|tomorrow|mas tarde|later|"
            r"cuando(?!\s+(?:es|son|fue|sera|seran)\b)|"
            r"when(?!\s+(?:is|are|was|were|will|do|does|did|can|could|should)\b)|"
            r"hasta que|until|esta noche|tonight|mediodia|noon|"
            r"medianoche|midnight|una vez que|once|upon)\b|"
            r"\b(?:dentro de|en)\s+(?:una?|dos|tres|\d+)\s+"
            r"(?:minutos?|minutes?|horas?|hours?|dias?|days?)\b|"
            r"\bin\s+(?:an?|one|two|three|\d+)\s+"
            r"(?:minutes?|hours?|days?)\b|"
            r"\b(?:tras|despues de|antes de|after|before)\s+"
            r"(?:el|la|los|las|the|una?|an?)?\s*[a-z0-9]+\b|"
            r"\b(?:si|if)\s+.{1,120}\b|"
            r"\b(?:al|upon)\s+(?:terminar|finalizar|acabar|finish(?:ing)?)\b|"
            r"\b(?:lunes|martes|miercoles|jueves|viernes|sabado|domingo|"
            r"monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b|"
            r"\b(?:el|on)?\s*\d{1,2}\s+(?:de\s+)?"
            r"(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|"
            r"septiembre|octubre|noviembre|diciembre|january|february|"
            r"march|april|may|june|july|august|september|october|"
            r"november|december)\b|"
            r"\b(?:january|february|march|april|may|june|july|august|"
            r"september|october|november|december)\s+\d{1,2}\b|"
            r"\ba las?\s+\d{1,2}(?::\d{2})?\b|"
            r"\bat\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?\b"
        ),
    )
    terminal_deferred = (
        _has(
            deferred_scope,
            r"\b(?:luego|despues|afterwards)[\s?!.]*$",
        )
        and len(list(re.finditer(rf"\b{_COVERAGE_ACTION_HEAD}\b", deferred_scope))) < 2
    )
    deferred = hard_deferred or terminal_deferred
    if not deferred:
        return False
    head = _request_head(text)
    if _has(
        text,
        r"\b(?:y|and)\s+(?:dime|tell me)\s+(?:si|whether)\s+"
        r"(?:pudiste|se pudo|lo verificaste|you could|it was)\s+"
        r"(?:verificar(?:lo)?|verified?)\b",
    ):
        return False
    if _has(
        text,
        r"\b(?:escribe|escribi|type)\b.{0,160}"
        r"\b(?:manana|tomorrow|esta noche|tonight|lunes|martes|miercoles|"
        r"jueves|viernes|sabado|domingo|monday|tuesday|wednesday|thursday|"
        r"friday|saturday|sunday)\b",
    ):
        return False
    if _literal_note_payload_request(text):
        return False
    if _has(
        text,
        r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
    ) and _has(
        text,
        r"\b(?:see\s+if|check\s+(?:if|whether)|mira\s+si|comprueba\s+si)\b"
        r".{0,48}\b(?:answers?|responde|contest|reach|alcanza|ping)\b",
    ):
        return False
    # Diferir un efecto no es lo mismo que no poder diferirlo. El catálogo tiene
    # `notification.schedule`, `reminder.create` y `calendar.event.create`: para
    # esos actos el «más tarde» ES la operación, no un obstáculo. Esta salida ya
    # existía, pero nombraba tan pocas formas que `ponme una alarma a las 7` o
    # `agenda una reunión el viernes` caían del lado no soportado. Se exigen
    # las DOS señales —verbo de programar y sustantivo programable— para que
    # `pon música mañana`, que no nombra ninguna, siga vetado.
    scheduling_request = (
        (_head_is(head, _SCHEDULING_VERB) and _has(text, _SCHEDULING_NOUN))
        or _head_is(head, _SCHEDULING_BY_ITSELF)
        or _has(
            text,
            rf"\b{_SCHEDULING_BY_ITSELF}\b",
        )
        or _bounded_calendar_list_query(text)
    )
    return not scheduling_request


def _literal_note_payload_request(text: str) -> bool:
    """Recognize a positive note request whose subordinate text is literal data."""

    text = _strip_request_envelope(_fold(text))
    desired = _explicit_desire_request(text)
    if desired is not None:
        text = desired.group("body")
    return _has(
        text,
        r"^[¿?¡!\s]*(?:"
        r"(?:anota|anotar|anotame|note\s+down|write\s+down|"
        r"deja(?:r)?\s+anotad[oa])\s*(?:que\b|that\b|:)"
        r"|(?:crea|crear|create|make|haz|hacer|guarda(?:me)?|guardar|save|"
        r"toma(?:me)?|take)\s+"
        r"(?:(?:una?|a)\s+)?(?:nota|note)\s*"
        r"(?:(?:que\s+diga|that\s+says?|saying)\s*:?|:)"
        r"|(?:nota\s+nueva|nueva\s+nota|new\s+note)\s*:"
        r")\s*\S.+$",
    )


_CALENDAR_MONTH_TOKEN = (
    r"(?:january|february|march|april|may|june|july|august|september|"
    r"october|november|december|enero|febrero|marzo|abril|mayo|junio|"
    r"julio|agosto|septiembre|octubre|noviembre|diciembre)"
)


def _absolute_calendar_range_parts(
    text: str,
) -> tuple[str, str, str, str] | None:
    """Return the two literal month/day endpoints of one bounded range."""

    folded = _fold(text)
    match = re.search(
        rf"\b(?:timeframe\s+of|between|from|entre|desde)\s+"
        rf"(?P<start_month>{_CALENDAR_MONTH_TOKEN})\s+"
        rf"(?P<start_day>{_PERCENTAGE_WORD_PATTERN}|\d{{1,2}})\s+"
        rf"(?:and|to|through|y|a|hasta)\s+"
        rf"(?P<end_month>{_CALENDAR_MONTH_TOKEN})\s+"
        rf"(?P<end_day>{_PERCENTAGE_WORD_PATTERN}|\d{{1,2}})\b",
        folded,
        re.IGNORECASE,
    )
    if match is None:
        return None
    return (
        match.group("start_month"),
        match.group("start_day"),
        match.group("end_month"),
        match.group("end_day"),
    )


def _bounded_calendar_list_query(text: str) -> bool:
    """Recognize a read-only calendar question with one bounded time scope."""

    folded = _fold(text)
    absolute_range = _absolute_calendar_range_parts(folded)
    if not _has(folded, _BOUNDED_TEMPORAL_SELECTOR) and absolute_range is None:
        return False
    head = _request_head(folded)
    calendar_domain = _has(
        folded,
        r"\b(?:calendario|calendar|evento|eventos|event|events|"
        r"reunion|reuniones|meeting|meetings|cita|citas|"
        r"appointment|appointments)\b",
    )
    if calendar_domain and (
        _head_is(head, _LIST)
        or _head_is(
            head,
            r"(?:cuando|when|revisa|revisar|review|check|consulta|consultar)",
        )
    ):
        return True
    if (
        absolute_range is not None
        and calendar_domain
        and _has(
            folded,
            r"\b(?:what|which)\s+(?:meetings|events|appointments)\s+"
            r"(?:occurred|happened|took\s+place)\b",
        )
    ):
        return True
    if _head_is(head, r"(?:eventos|events)"):
        return True
    return _has(
        folded,
        (
            r"^[^\w]*(?:what is going on|que (?:sucede|pasa)|"
            r"anything i should do|tengo algo que hacer|"
            r"hay algo que (?:hacer|tenga que hacer))\b"
        ),
    )


def _has_unresolved_shared_head_coordination(text: str) -> bool:
    """Detect coordinated objects that require different operation families."""

    head = _request_head(text)
    if _head_is(
        head,
        r"(?:pon|poner|fija|ajusta|establece|set|cambia)",
    ) and _volume_domain(text):
        return _has(
            text,
            (
                r"\b(?:y|and)\b\s+(?:(?:el|la|los|las|the)\s+)?"
                r"(?:brillo|brightness|microfono|microphone|camara|camera|"
                r"notificaciones?|notifications?|pantalla|screen)\b"
            ),
        )
    if _head_is(
        head,
        r"(?:silencia|silenciar|mute|unmute|reactiva|reactivar)",
    ) and _audio_mute_domain(text):
        return _has(
            text,
            (
                r"\b(?:y|and)\b\s+(?:[a-z]+\s+){0,2}"
                r"(?:notificaciones?|notifications?|microfono|microphone|"
                r"camara|camera|brillo|brightness|pantalla|screen)\b"
            ),
        )
    return False


def _coordinated_effect_domain_minimum(text: str) -> int | None:
    """Count effect-domain objects joined under one governing action head."""

    domain_patterns = {
        "note": r"\b(?:(?:mis?|my|una?|otra|another|las?|los?|the)\s+)?(?:notas?|notes?)\b",
        "task": r"\b(?:(?:mis?|my|una?|otra|another|las?|los?|the)\s+)?(?:tareas?|tasks?)\b",
        "reminder": r"\b(?:(?:mis?|my|un|una|los?|las?|the)\s+)?(?:recordatorios?|reminders?)\b",
        "routine": r"\b(?:(?:mis?|my|una?|las?|the)\s+)?(?:rutinas?|routines?)\b",
        "calendar": (
            r"\b(?:(?:un|una|mis?|my|los?|las?|the)\s+)?"
            r"(?:eventos?|events?)(?:\s+(?:del|de|of the)\s+"
            r"(?:calendario|calendar))?\b"
        ),
        "web": (
            r"\b(?:(?:en|on)\s+(?:(?:la|the)\s+)?)?"
            r"(?:web|internet)\b"
        ),
        "email": (
            r"\b(?:(?:mis?|my|el|the)\s+)?(?:correo|correos|email|emails|mail)"
            r"(?:\s+(?:mas\s+)?(?:reciente|recientes|latest))?\b"
        ),
        "process": (
            r"\b(?:procesos?|processes)(?:\s+(?:del|de|of the)\s+"
            r"(?:sistema|system))\b|\b(?:task manager|administrador de tareas)\b"
        ),
        "game": (
            r"\b(?:juegos?|games?)(?:\s+(?:de|del|on|of)\s+steam)\b|"
            r"\bsteam\s+games?\b"
        ),
        "bluetooth": r"\bbluetooth(?:\s+(?:devices?|dispositivos?))?\b",
        "peripheral": r"\b(?:perifericos?|peripherals?)\b",
        "wifi": r"\bwi[\s-]?fi\b",
        "audio": r"\b(?:audio|sonido|sound|musica|music|volumen|volume)\b",
        "brightness": r"\b(?:brillo|brightness)\b",
        "notification": r"\b(?:notificacion(?:es)?|notifications?)\b",
        "filesystem": (
            r"\b(?:(?:una?|mis?|my|los?|las?|the)\s+)?"
            r"(?:carpetas?|folders?|archivos?|files?|directorios?|directories|"
            r"descargas|downloads)\b"
        ),
        "document": r"\b(?:(?:un|una|the)\s+)?(?:documentos?|documents?)\b",
        "backup": r"\b(?:copias? de seguridad|backups?)\b",
        "memory": r"\b(?:memoria local|local memory|memory store)\b",
        "theme": r"\b(?:modo oscuro|dark mode|tema|theme)\b",
        "browser_page": r"\b(?:pagina|page|pestanas|tabs)\b",
        "clipboard": r"\b(?:portapapeles|clipboard|seleccion|selection)\b",
        "capture": r"\b(?:captura de pantalla|screenshot|screen capture)\b",
        "window": r"\b(?:ventana|window)\b",
    }
    spans: list[tuple[int, int, str]] = []
    for domain, pattern in domain_patterns.items():
        for found in re.finditer(pattern, text, re.IGNORECASE):
            spans.append((found.start(), found.end(), domain))
    spans.sort(key=lambda item: (item[0], -(item[1] - item[0])))
    deduplicated: list[tuple[int, int, str]] = []
    for span in spans:
        if any(span[0] >= prior[0] and span[1] <= prior[1] for prior in deduplicated):
            continue
        deduplicated.append(span)
    coordinated: set[tuple[int, int, str]] = set()
    for connector in re.finditer(r"\b(?:y|and)\b", text, re.IGNORECASE):
        if _has(
            text[connector.end() :],
            r"^\s*(?:luego|despues|then|finalmente|finally|afterwards)\b",
        ):
            # This connector introduces a new action head; it does not bind
            # another object to the prior action.
            continue
        left_candidates = [
            span
            for span in deduplicated
            if span[1] <= connector.start() and connector.start() - span[1] <= 160
        ]
        right_candidates = [
            span
            for span in deduplicated
            if span[0] >= connector.end() and span[0] - connector.end() <= 160
        ]
        if not left_candidates or not right_candidates:
            continue
        left = max(left_candidates, key=lambda item: item[1])
        right = min(right_candidates, key=lambda item: item[0])
        if left[2] == right[2]:
            continue
        coordinated.add(left)
        coordinated.add(right)
    return len(coordinated) if len(coordinated) >= 2 else None


def _has_multiple_installed_entities(text: str) -> bool:
    return (
        _has(text, r"\b(?:instalad[oa]s?|installed)\b")
        and _has(text, r"\b(?:en|on)\s+steam\b")
        and _has(text, r"\b(?:y|and)\b")
        and not _has(text, r"\b(?:juegos|games)\b")
    )


def _unresolved_explicit_cardinality(text: str) -> int | None:
    """Return a requested effect count that the argument binder cannot split."""

    words = {
        "dos": 2,
        "two": 2,
        "tres": 3,
        "three": 3,
        "cuatro": 4,
        "four": 4,
        "cinco": 5,
        "five": 5,
    }
    repeated = _match(
        text,
        (
            r"\b(?P<count>dos|two|tres|three|cuatro|four|cinco|five|[2-8])\s+"
            r"(?:notas?|notes?|tareas?|tasks?|recordatorios?|reminders?)\b|"
            r"\b(?P<times>dos|two|tres|three|cuatro|four|cinco|five|[2-8])\s+"
            r"(?:veces|times)\b|\b(?P<twice>twice)\b"
        ),
    )
    if repeated is not None:
        raw = (
            repeated.group("count")
            or repeated.group("times")
            or repeated.group("twice")
        )
        if raw in words:
            return words[raw]
        if raw == "twice":
            return 2
        return int(raw)
    repeated_domain = _match(
        text,
        (
            r"\b(?P<domain>nota|note|tarea|task|recordatorio|reminder)\b"
            r".{0,120}\b(?:y|and)\b\s+"
            r"(?:(?:una?|another|otra|otro|the)\s+)?"
            r"(?P=domain)s?\b"
        ),
    )
    return 2 if repeated_domain is not None else None


_ORDINAL_INDEX = {
    "primera": 1,
    "primero": 1,
    "first": 1,
    "segunda": 2,
    "segundo": 2,
    "second": 2,
    "tercera": 3,
    "tercero": 3,
    "third": 3,
    "cuarta": 4,
    "cuarto": 4,
    "fourth": 4,
    "quinta": 5,
    "quinto": 5,
    "fifth": 5,
    "sexta": 6,
    "sexto": 6,
    "sixth": 6,
    "septima": 7,
    "septimo": 7,
    "seventh": 7,
    "octava": 8,
    "octavo": 8,
    "eighth": 8,
}
_CARDINAL_NUMBER = {
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
}
_ORDINAL_WORD = "|".join(_ORDINAL_INDEX)


# The same note body can be introduced by a preposition or by a participle.
# ``Cedar containing north`` and ``Cedar con contenido norte`` name one note
# each; treating only the prepositional form as enumerable made an otherwise
# complete four-note mission collapse to a single create.
# Spanglish mixes the preposition and the noun freely, so ``con content`` and
# ``with contenido`` name a body just as ``con contenido`` does.
_NOTE_CONTENT_INTRODUCER = (
    r"(?:(?:con|with)\s+(?:contenido|content)|containing|conteniendo|"
    r"que\s+(?:contenga|diga))"
)


def _fully_enumerated_named_note_titles(text: str) -> tuple[str, ...]:
    """Extract a bounded ``title + content`` list without inventing labels."""

    head = _request_head(text)
    if not _head_is(head, _CREATE):
        return ()
    count_match = _match(
        text,
        r"\b(?P<count>dos|two|tres|three|cuatro|four|cinco|five|"
        r"seis|six|siete|seven|ocho|eight|[2-8])\s+"
        r"(?:(?:private|local|privadas?|locales?)\s+)?(?:notas|notes)\s*:\s*",
    )
    if count_match is None:
        return ()
    raw_count = count_match.group("count")
    count = _CARDINAL_NUMBER.get(
        raw_count, int(raw_count) if raw_count.isdigit() else 0
    )
    body = text[count_match.end() :]
    titles = tuple(
        " ".join(found.group("title").strip(" ,.;:").split())
        for found in re.finditer(
            # A serial comma keeps its conjunction: ``, and Birch`` must not
            # name a note ``and birch``.
            r"(?:^|,\s*(?:(?:y|and)\s+)?|\s+(?:y|and)\s+)"
            r"(?P<title>[a-z0-9][a-z0-9 _-]{0,79}?)\s+"
            rf"(?:{_NOTE_CONTENT_INTRODUCER})\s+\S",
            body,
            re.IGNORECASE,
        )
    )
    if (
        len(titles) != count
        or any(not title for title in titles)
        or len(set(titles)) != len(titles)
    ):
        return ()
    return titles


def _fully_enumerated_note_create_count(text: str) -> int | None:
    """Return an exact bounded count only for individually labelled notes."""

    head = _request_head(text)
    if not _head_is(head, _CREATE):
        return None
    count_match = _match(
        text,
        r"\b(?P<count>dos|two|tres|three|cuatro|four|cinco|five|"
        r"seis|six|siete|seven|ocho|eight|[2-8])\s+"
        r"(?:(?:private|local|privadas?|locales?)\s+)?(?:notas|notes)\b",
    )
    if count_match is None:
        return None
    raw_count = count_match.group("count")
    count = _CARDINAL_NUMBER.get(
        raw_count, int(raw_count) if raw_count.isdigit() else 0
    )
    labelled = [
        _ORDINAL_INDEX[found.group("ordinal")]
        for found in re.finditer(
            rf"\b(?:la|el|the)?\s*(?P<ordinal>{_ORDINAL_WORD})\s+"
            r"(?:titulad[oa]|llamad[oa]|titled|entitled|named|called)\b",
            text,
            re.IGNORECASE,
        )
    ]
    if labelled != list(range(1, count + 1)):
        named = _fully_enumerated_named_note_titles(text)
        if len(named) != count:
            return None
    return count


def _fully_enumerated_note_read_order(
    text: str,
    total_count: int | None = None,
) -> tuple[int, ...]:
    """Return an explicit, duplicate-free ordinal read order."""

    head = _request_head(text)
    if not _head_is(head, _READ):
        return ()
    ordered: list[int] = []
    for found in re.finditer(
        rf"\b(?:la|el|the)?\s*(?P<ordinal>{_ORDINAL_WORD}|middle|last)\s+"
        r"(?:nota|note)\b",
        text,
        re.IGNORECASE,
    ):
        word = found.group("ordinal")
        if word == "middle":
            if total_count is None or total_count < 3 or total_count % 2 == 0:
                return ()
            ordered.append((total_count + 1) // 2)
        elif word == "last":
            if total_count is None:
                return ()
            ordered.append(total_count)
        else:
            ordered.append(_ORDINAL_INDEX[word])
    if len(ordered) < 2 or len(set(ordered)) != len(ordered):
        return ()
    return tuple(ordered)


def _named_note_dependency_order(text: str) -> tuple[int, ...]:
    """Map a complete named read list to its unique named creation list."""

    clauses = _request_clauses(text)
    created: tuple[str, ...] = ()
    create_index = -1
    for index, clause in enumerate(clauses):
        titles = _fully_enumerated_named_note_titles(clause)
        if titles:
            if created:
                return ()
            created = titles
            create_index = index
    if not created or create_index + 1 >= len(clauses):
        return ()
    read_text = " y ".join(clauses[create_index + 1 :])
    if not _head_is(_request_head(read_text), _READ):
        return ()
    references = tuple(
        " ".join(found.group("title").strip(" ,.;:").split())
        for found in re.finditer(
            r"\b(?:la|the)?\s*(?:nota|note)\s+"
            r"(?P<title>[a-z0-9][a-z0-9 _-]{0,79}?)"
            r"(?=\s*(?:,|[.!?]|$|\b(?:y|and)\b))",
            read_text,
            re.IGNORECASE,
        )
    )
    if len(references) != len(created):
        return ()
    order: list[int] = []
    for reference in references:
        matches = [
            index
            for index, title in enumerate(created, 1)
            if title == reference or title.startswith(reference + " ")
        ]
        if len(matches) != 1:
            return ()
        order.append(matches[0])
    if set(order) != set(range(1, len(created) + 1)):
        return ()
    return tuple(order)


def _individually_authored_note_create_clauses(clauses: Iterable[str]) -> int:
    """Count clauses that each author exactly one note with its own body."""

    return sum(
        1
        for clause in clauses
        if _head_is(_request_head(clause), _CREATE)
        and _has(clause, r"\b(?:nota|note)s?\b")
        and _has(clause, rf"\b{_NOTE_CONTENT_INTRODUCER}\b")
    )


def _has_fully_enumerated_note_cardinality(
    clauses: Iterable[str],
    expected_count: int,
) -> bool:
    clauses = tuple(clauses)
    if any(
        _fully_enumerated_note_create_count(clause) == expected_count
        for clause in clauses
    ):
        return True
    # ``una nota Luna con content claro y otra nota Sol con content brillante``
    # states the same cardinality as one enumerated list of two, only spread
    # across two clauses that each carry their own title and body. Requiring a
    # single enumerating clause rejected a request that was fully authored, so
    # conserve the count when every note is individually written out.
    return _individually_authored_note_create_clauses(clauses) == expected_count


def enumerated_note_dependency_order(text: str) -> tuple[int, ...]:
    """Return a complete user-authored mapping from reads to created notes.

    The mapping is available only when one bounded creation list labels every
    note in ascending ordinal order and one later read list names every label
    exactly once. Partial, duplicate, or standalone ordinal references remain
    untrusted and return an empty tuple.
    """

    folded = _fold(text)
    clauses = _request_clauses(folded)
    named_order = _named_note_dependency_order(folded)
    if named_order:
        return named_order
    creates = tuple(
        (index, count)
        for index, clause in enumerate(clauses)
        if (count := _fully_enumerated_note_create_count(clause)) is not None
    )
    if len(creates) != 1:
        return ()
    create_index, count = creates[0]
    read_text = " y ".join(clauses[create_index + 1 :])
    order = _fully_enumerated_note_read_order(read_text, count)
    if len(order) != count or set(order) != set(range(1, count + 1)):
        return ()
    return order


def _is_meta_or_tool_denial(text: str) -> bool:
    """Decline lexical recognition of definitions as well as explicit constraints."""

    return _is_definition_question(text) or _is_explicit_meta_or_tool_denial(text)


def _is_definition_question(text: str) -> bool:
    """A syntactic hint for the recognizer, not an execution prohibition."""

    return (
        _has(
            text,
            r"^[Â¿?Â¡!\s]*(?:que\s+es|que\s+son|what\s+(?:is|are|es)|"
            r"para\s+que\s+sirve|explain\s+what)\b",
        )
        and not _has(
            text,
            r"\b(?:actual|actualmente|ahora|current|currently|right\s+now|"
            r"volumen|volume|hora|time|fecha|date|estado|status|"
            r"sonando|playing|usando|using)\b",
        )
        and not _has(text, r"^what\s+is\s+going\s+on\b")
        and not (_process_list_domain(text) and _has(text, r"\bobserved\b"))
    )


def _is_explicit_meta_or_tool_denial(text: str) -> bool:
    """Recognize explicit how-to, quotation and no-tool constraints."""

    topic = _machine_status_topic(text)
    request = topic.group("body") if topic is not None else text
    supported_live_status_question = (
        re.match(r"^[¿?¡!\s]*tell\s+me\s+how\b", request, re.IGNORECASE) is not None
        and (
            (
                _has(request, r"\b(?:doing|running|status|state|condition|configured)\b")
                and (
                    _has(text, r"\b(?:audio|sound|volume)\b")
                    or _system_status_domain(text)
                    or _network_status_domain(text)
                    or _has(
                        text,
                        r"\b(?:pc|computer|machine|equipo|computador)\b.{0,64}"
                        r"\b(?:doing|running|whole|overall)\b",
                    )
                )
            )
            or (
                _has(request, r"^[¿?¡!\s]*tell\s+me\s+how\s+(?:much|many)\b")
                and _has(
                    request,
                    r"\b(?:free|available|used|occupied|remaining|remains|left|"
                    r"installed|have|has|is|are)\b",
                )
                and _system_status_domain(text)
                and _machine_status_scopes_are_one_reading(text)
                and _machine_status_is_the_whole_clause(text)
            )
        )
    )
    return (
        (
            _has(
                text,
                (
                    r"\b(?:que significa|que quiere decir|what does .{0,80} mean|"
                    r"meaning of|como (?:hacer|hago|se hace|puedo|podria)|"
                    r"como\s+[a-z]+(?:ar|er|ir)\b|"
                    r"how (?:to|do i|can i)|explica(?:me)? como|"
                    r"tell me how|traduce|traducir|traduccion|"
                    r"translate|translation)\b"
                ),
            )
            and not supported_live_status_question
        )
        or _has(
            text,
            (
                r"\b(?:no uses?|sin usar|do not use|don'?t use|without using)\b"
                r".{0,40}\b(?:herramientas?|tools?|acciones?|actions?)\b|"
                r"\b(?:solo responde|just answer)\b.{0,40}\b"
                r"(?:no tools?|sin herramientas?)\b"
            ),
        )
        or (
            _has(
                text,
                (
                    r"\b(?:frase|comando|orden|sentence|command)\b|"
                    r"\b(?:por ejemplo|for example)\b"
                ),
            )
            and _has(
                text,
                rf"\b(?:{_OPEN}|silencia|mute|captura|screenshot|navega|navigate)\b",
            )
        )
    )


def _is_negated_match(text: str, found: re.Match[str]) -> bool:
    """Treat a nearby clause-local negation as a veto, never as an effect."""

    state_question = _negative_state_question_body(text)
    if state_question is not None:
        # Keep character offsets: the matched observation belongs to the
        # original evidence, and any later prohibition remains visible.
        text = " " * (len(text) - len(state_question)) + state_question
    prefix = text[max(0, found.start() - 80) : found.start()]
    boundary = max(
        prefix.rfind(","),
        prefix.rfind(";"),
        prefix.rfind("."),
        prefix.rfind("?"),
        prefix.rfind("!"),
        prefix.rfind(":"),
    )
    clause_prefix = prefix[boundary + 1 :]
    return _has(
        clause_prefix,
        (
            r"(?:\bno\b|\bnunca\b|\bjamas\b|\bnever\b|"
            r"\bdon'?t\b|\bdo\s+not\b|\bsin\b|\bwithout\b)"
            r"(?:\s+[a-z0-9_-]+){0,4}\s*$"
        ),
    )


def _append(
    matches: list[tuple[int, int, str]],
    text: str,
    operation: str,
    pattern: str,
    *,
    priority: int = 0,
) -> bool:
    for found in re.finditer(pattern, text, re.IGNORECASE):
        if _is_negated_match(text, found):
            continue
        matches.append((found.start(), priority, operation))
        return True
    return False


def _append_all(
    matches: list[tuple[int, int, str]],
    text: str,
    operation: str,
    pattern: str,
    *,
    priority: int = 0,
) -> int:
    """Append each distinct, non-negated verb/object occurrence in order."""

    count = 0
    for found in re.finditer(pattern, text, re.IGNORECASE):
        if _is_negated_match(text, found):
            continue
        matches.append((found.start(), priority, operation))
        count += 1
    return count


_KNOWN_APPLICATION = (
    r"(?:bloc de notas|notepad|calculadora|calculator|calc|opera gx|opera|spotify|"
    r"steam|discord|chrome|google chrome|word|microsoft word|edge|"
    r"microsoft edge|firefox|whatsapp|excel|powerpoint|vlc|"
    r"configuracion(?:es)?(?: de windows)?|windows settings)"
)
# Software people ask to open by name. Membership here never opens anything:
# it only lets an opening whose target is absent from the verified catalog be
# answered by a presence read («abrime el photoshop» → app.installed), instead
# of a model guess that denied the capability (APPS1231/007, /015) or asked for
# «the exact name» (/016).
_KNOWN_SOFTWARE = (
    rf"(?:{_KNOWN_APPLICATION}|photoshop|lightroom|illustrator|premiere(?:\s+pro)?|"
    r"after\s+effects|acrobat|brave|outlook|onenote|teams|zoom|skype|slack|telegram|"
    r"signal|notion|obsidian|obs(?:\s+studio)?|audacity|blender|gimp|inkscape|figma|"
    r"unity|unreal(?:\s+engine)?|godot|visual\s+studio(?:\s+code)?|vs\s*code|pycharm|"
    r"intellij|eclipse|android\s+studio|docker(?:\s+desktop)?|postman|github\s+desktop|"
    r"epic\s+games(?:\s+launcher)?|minecraft|roblox|fortnite|valorant|league\s+of\s+legends|"
    r"itunes|netflix|twitch|messenger|notepad\+\+|sublime(?:\s+text)?|winrar|7-?zip|"
    r"teamviewer|anydesk|virtualbox|vmware|wireshark|filezilla|putty|wordpad|paint|"
    r"camtasia|davinci\s+resolve|canva|dropbox|google\s+drive|onedrive|autocad|matlab|"
    r"rstudio|anaconda|jupyter|kodi|plex|handbrake|thunderbird|evernote|trello|origin|"
    r"battle\.net|ubisoft\s+connect|gog\s+galaxy)"
)
_NOTEPAD_OBJECT = r"\b(?:(?:bloc|app|coso)\s+de\s+notas|notepad)\b"
_DUPLICATE_FILES = r"\b(?:duplicad[oa]s?|repetid[oa]s?|duplicates?)\b"
_CONNECTED_INVENTORY = (
    r"\b(?:cosas?|things?|dispositivos?|devices?|perifericos?|peripherals?|"
    r"accesorios?|accessories)\b.{0,48}"
    r"\b(?:conectad[oa]s?|connected|enchufad[oa]s?|plugged|attached)\b|"
    r"\b(?:conectad[oa]s?|connected|enchufad[oa]s?|plugged|attached)\b.{0,40}"
    r"\b(?:al\s+equipo|a\s+(?:la\s+)?(?:maquina|computadora|pc)|"
    r"to\s+(?:the\s+)?(?:machine|computer|pc|equipment))\b"
)
_DEICTIC_DAY = (
    r"\b(?:ese\s+dia|esa\s+fecha|el\s+mismo\s+dia|"
    r"that\s+day|that\s+date|that\s+same\s+day)\b"
)
_OPEN = r"(?:abre|abres|abrir|abri|abris|abrime|avri|open|launch|lanza|inicia|start|ejecuta|arranca|arrancame)"
_MEDIA_RESUME_VERB = r"(?:reanuda|reanudar|resume|segui|seguir|sigue|continua|continuar|continue)"
_LIST = r"(?:lista|listar|listame|enumera|enumerar|muestra|muestrame|mostrame|mostra|dime|show|list|enumerate)"
_READ = r"(?:lee|leer|leeme|leela|leelo|leerla|leerlo|read|dime|muestra)"
_CREATE = (
    r"(?:crea|crear|anota|anotar|añade|añadir|anade|anadir|"
    r"agrega|agregar|agregame|guarda|guardame|guardar|haz|hacer|create|make|add|"
    r"toma|tomame|take)"
)
# Diferir un efecto no es lo mismo que no poder diferirlo. El catálogo tiene
# `notification.schedule`, `reminder.create` y `calendar.event.create`: para
# esos actos el «más tarde» ES la operación, no un obstáculo. Se exigen las DOS
# señales —verbo de programar y sustantivo programable— para que `pon música
# mañana`, que no nombra ninguna, siga fallando cerrado.
_SCHEDULING_NOUN = (
    r"\b(?:recordatorio|recordatorios|reminder|reminders|"
    r"evento|eventos|event|events|calendario|calendar|"
    r"tarea|tareas|task|tasks|rutina|rutinas|routine|routines|"
    r"alarma|alarmas|alarm|alarms|"
    r"temporizador|temporizadores|timer|timers|"
    r"aviso|avisos|reunion|reuniones|meeting|meetings|"
    r"cita|citas|appointment|appointments)\b"
)
_SCHEDULING_VERB = (
    rf"(?:{_CREATE}|programa|programar|programame|schedule|"
    r"pon|poner|ponme|pone|poneme|pongame|"
    r"agenda|agendar|agendame|avisa|set|start|inicia|arranca|empeza|empieza)"
)
# Un verbo que ya nombra el acto por sí solo, y la apertura nominal sin verbo
# que R3 aceptó como acto de habla, no necesitan repetir el sustantivo:
# «recuérdame comprar pan mañana», «alarma para mañana 8am».
_SCHEDULING_BY_ITSELF = (
    r"(?:recuerdame|recuerdamelo|recordame|recordamelo|avisame|despiertame|despertame|wake\s+me(?:\s+up)?|remind|"
    r"recordatorio|recordatorios|reminder|reminders|"
    r"alarma|alarmas|alarm|alarms|temporizador|temporizadores|timer|timers)"
)
_SEARCH = r"(?:busc[aá]|buscar|encuentra|search|find|look\s+up)"
# Verbs for catalog effects that this conservative recognizer does not
# necessarily classify itself.  They are used only as clause boundaries: if a
# compound request contains one of them and the following clause cannot be
# resolved, the whole deterministic path abstains instead of executing a
# recognized prefix and silently dropping the rest of the request.
_COVERAGE_ACTION_HEAD = (
    rf"(?:{_OPEN}|{_LIST}|{_READ}|{_CLOCK_READ_HEAD}|{_CREATE}|{_SEARCH}|{_SET_VOLUME_VERB}|"
    r"haz|toma|captura|take|capture|dejar|put|ring|sound|"
    rf"{_VOLUME_UP_VERB}|{_VOLUME_DOWN_VERB}|bajalo|subelo|"
    r"pone|arranca|cambiar|get rid|"
    rf"reduce|increment|decrease|silencia|silenciame|mute|{_UNMUTE_VERB}|mutea|mutear|"
    r"quita|quitar|saca|sacar|maximiza|minimiza|"
    r"sacale|"
    r"restaura|escribe|escribi|type|selecciona|select|copia|copiame|copy|"
    r"edita|edit|convierte|convert|transforma|arrastra|drag|make|navega|navegar|"
    r"navigate|ve|go|ir|anda|entra|entrar|recarga|recargar|reload|refresh|reproduce|reproducir|reproduzca|"
    rf"play|{_MEDIA_RESUME_VERB}|pausa|pausar|pause|deten|detener|stop|revisa|revisar|check|review|"
    r"consulta|consultar|comprueba|comprobar|checkea|averigua|averiguar|"
    r"investiga|investigar|research|"
    r"find\s+out|inspect|inspecciona|give|prepara|prepare|resolve|"
    r"envia|enviar|enviale|enviales|manda|mandar|mandale|mandales|"
    r"dile|decile|tell|send|"
    r"elimina|eliminar|borra|borrar|delete|"
    r"remove|apaga|apagar|shutdown|reinicia|reiniciar|restart|suspende|"
    r"suspender|sleep|cierra|cerra|cerrar|cerrame|cierrame|cierres|close|instala|instalar|install|"
    r"desinstala|desinstalar|uninstall|imprime|imprimir|print|escanea|"
    r"escanear|scan|conecta|conectar|connect|desconecta|disconnect|"
    r"empareja|emparejar|pair|renombra|renombrar|rename|mueve|mover|move|"
    r"guarda|guardar|save|descarga|descargar|download|comparte|share|"
    r"pega|pegar|paste|habilita|habilitar|enable|deshabilita|disable|"
    r"olvida|olvidar|forget|responde|responder|reply|programa|programar|"
    r"schedule|agenda|agendar|agendame|avisa|avisame|cancela|cancelar|cancel|"
    r"trancame|tranca|bloqueame|bloquea|lock|"
    r"diagnostica|diagnosticar|diagnose|"
    r"completa|completar|complete|reabre|reabrir|reopen|actualiza|"
    r"actualizar|update|describe|describir|redimensiona|redimensionar|"
    # WEB1539 «resumime esta página»: summarizing is an order head too.
    r"resumime|resumeme|resumi|resumir|resumelo|resumela|summarize|summarise|"
    r"resize|enfoca|enfocar|focus|presiona|presionar|press|clic|click|vacia|vaciar|"
    r"apreta|apretale|apretalo|apretala|apretar|aprieta|pulsa|pulsale|hace(?=\s+clic)|"
    r"empty|termina|terminar|terminate|verifica|verificar|verify|"
    r"recuerdame|recuerdamelo|recordame|recordamelo|remind|"
    r"activa|activar|enciende|encender|prende|prender|conectame|deactivate|"
    r"desactiva|desactivar|acepta|accept|"
    r"rechaza|reject|confirma|confirm|desbloquea|unlock|elije|elige|choose|"
    r"abrelo|abrela|cierralo|cierrala|maximizalo|maximizala|minimizalo|"
    r"minimizala|restauralo|restaurala|reactivalo|reactivala|silencialo|"
    r"silenciala|copialo|copiala|eliminalo|eliminala|borralo|borrala|"
    r"muevelo|muevela|redimensionalo|redimensionala|enfocalo|enfocala|"
    r"seleccionalo|seleccionala|pegalo|pegala|guardalo|guardala|"
    r"envialo|enviala|completalo|completala|reabrelo|reabrela|"
    r"actualizalo|actualizala|respondelo|respondela|cancelalo|cancelala|"
    r"a(?=\s+que)|cual|which|que\s+hora|what\s+time|"
    r"que hay|what(?:'s| is)|donde|where|hablame)"
)

_SEQUENCE_NOMINAL_HEAD = r"(?:alarma|alarm|recordatorio|reminder)"


def _has_contradictory_correction(
    text: str, available_operations: Iterable[str] = (),
) -> bool:
    """Reject an earlier effect when a later adversative clause revokes it."""

    # ``yes or no`` asks for a binary answer; its ``or`` is not an alternative
    # operation.  Keep inspecting the actual request so any later correction
    # or alternative still fails closed.
    text = re.sub(
        r"^[¿?¡!\s]*(?:yes\s+or\s+no|si\s+o\s+no)\b[\s,:;\-]*",
        "",
        text,
        count=1,
        flags=re.IGNORECASE,
    )
    # With the real catalog, the reader and conservation veto can prove that
    # a complete prohibition concerns a
    # different operation from every positive clause. Retractions without an
    # object and overlapping operations cannot be discharged this way.
    available = frozenset(available_operations)
    if available:
        clauses = _request_clauses(text)
        positives = tuple(c for c in clauses if not _is_negative_effect_clause(c))
        negatives = tuple(c for c in clauses if _is_negative_effect_clause(c))
        if positives and negatives:
            applications = build_application_catalog_index(())
            positive_intents = tuple(
                _resolve_explicit_effects_single(
                    c, available, application_names=applications,
                ) for c in positives
            )
            if all(intent is not None for intent in positive_intents):
                positive_operations = {
                    op for intent in positive_intents if intent is not None
                    for op in intent.operations
                }
                independent = True
                for clause in negatives:
                    forms = _negative_action_forms(clause)
                    intents = tuple(
                        _resolve_explicit_effects_single(
                            form, available, application_names=applications,
                        )
                        for form in forms
                    )
                    recognized = tuple(i for i in intents if i is not None)
                    if not recognized or any(
                        positive_operations.intersection(intent.operations)
                        for intent in recognized
                    ):
                        independent = False
                        break
                if independent:
                    text = "; ".join(positives)
    # Preserving the authored sequence is a positive mission constraint, not
    # a revocation of the requested effects. Remove only that bounded phrase;
    # any independent ``but do not ...`` clause remains visible below.
    text = re.sub(
        r"\b(?:sin\s+cambiar\s+(?:el\s+)?orden|"
        r"without\s+changing\s+(?:the\s+)?order|"
        r"keep\s+(?:the\s+)?(?:same\s+)?order)\b",
        "",
        text,
        flags=re.IGNORECASE,
    )
    return (
        _has(
            text,
            (
                r"\b(?:pero|but)\b.{0,160}"
                r"\b(?:no|nunca|jamas|never|don'?t|do\s+not)\b"
            ),
        )
        or _has(
            text,
            r",\s*no\s*,|\b(?:en vez de|instead of)\b",
        )
        or _has(
            text,
            (
                r"\b(?:evita|evitar|avoid|avoiding)\b.{0,120}"
                rf"\b(?:{_OPEN}|silencia|mute|captura|navega|navigate|"
                r"elimina|delete|envia|send)\b"
            ),
        )
        or _has(text, r"\b(?:o|or)\b")
        or _has(
            text,
            (
                r"\b(?:y|and)\b.{0,40}\b(?:no|nunca|jamas|never|"
                r"don'?t|do\s+not)\b|"
                r"\b(?:sin|without)\s+(?:reproducir|reproducirla|play|"
                r"abrir|open|cambiar|change|silenciar|mute|capturar|capture|"
                r"maximizar|maximize|copiar|copy)\b"
            ),
        )
        or _has(
            text,
            (
                r"(?:[,;.!?]|\b(?:pero|aunque|but|though)\b)\s*"
                r"(?:(?:mejor|en realidad|actually|on second thought)\s+)?"
                r"(?:no\b|don'?t\b|do\s+not\b|better\s+not\b)|"
                r"\b(?:mejor\s+no|en realidad\s+no|better\s+not|"
                r"actually\s+do\s+not|on second thought\s+do\s+not|"
                r"scratch that)\b|"
                r"(?:[,;.]|\b(?:pero|but)\b)\s*(?:mejor\s+)?"
                r"(?:ya no|ignora(?: eso|lo)?|"
                r"deja(?:lo)?(?=\s*(?:$|[,;.!?]))|me retracto|"
                r"me arrepenti|never mind|ignore that|i take that back|"
                r"drop it)\b"
            ),
        )
        or _has(
            text,
            (
                r"(?:--|[,;.!?]|\b(?:pero|but)\b)\s*"
                r"(?:(?:mejor|en realidad|actually|on second thought)\s*[,;:]?\s*)?"
                r"(?:do\s+neither|neither(?:\s+one|\s+of\s+them)?|"
                r"no\s+(?:hagas?|ejecutes?|realices?)\s+"
                r"(?:ningun[oa]|ninguna?\s+de\s+(?:las|los)\s+dos)|"
                r"ningun[oa]\s+de\s+(?:las|los)\s+dos)\b"
            ),
        )
    )


def _append_domain_actions(
    matches: list[tuple[int, int, str]],
    text: str,
    action_pattern: str,
    operation_by_domain: dict[str, str],
) -> int:
    """Bind an action to each explicitly coordinated local-data domain."""

    domain_patterns = {
        "note": r"\b(?:nota|notas|note|notes|memo|memos)\b",
        "task": r"\b(?:tarea|tareas|task|tasks|pendiente|pendientes)\b",
        "reminder": r"\b(?:recordatorio|recordatorios|reminder|reminders)\b",
        "routine": r"\b(?:rutina|rutinas|routine|routines)\b",
    }
    next_action = (
        rf"(?:{_CREATE}|{_SEARCH}|{_LIST}|{_READ}|{_OPEN}|"
        r"maximiza|minimiza|restaura|navigate|navega)"
    )
    boundary_pattern = (
        rf"[,;.!?]|\b(?:despues|luego|then|and then|y despues|y luego)\b|"
        rf"\by\s+(?={next_action}\b)"
    )
    appended = 0
    for action in re.finditer(rf"\b{action_pattern}\b", text, re.IGNORECASE):
        if _is_negated_match(text, action):
            continue
        suffix = text[action.end() :]
        boundary = re.search(boundary_pattern, suffix, re.IGNORECASE)
        fragment = suffix[: boundary.start()] if boundary is not None else suffix[:160]
        candidates: list[tuple[int, int, str]] = []
        for domain, noun_pattern in domain_patterns.items():
            if domain not in operation_by_domain:
                continue
            for noun in re.finditer(noun_pattern, fragment, re.IGNORECASE):
                candidates.append((noun.start(), noun.end(), domain))
        if not candidates:
            continue
        candidates.sort(key=lambda item: item[0])
        first_start, first_end, first_domain = candidates[0]
        selected = [(first_start, first_end, first_domain)]
        seen_domains = {first_domain}
        previous_end = first_end
        for start, end, domain in candidates[1:]:
            if domain in seen_domains:
                continue
            connector = fragment[previous_end:start]
            plain_coordination = _has(
                connector,
                (
                    r"^\s*(?:,\s*)?(?:y|and)\s+"
                    r"(?:(?:una?|an?|el|la|los|las|the|mis?|my)\s+)*$"
                ),
            )
            labeled_coordination = action_pattern == _CREATE and _has(
                connector,
                (
                    r"^\s+(?:llamad[oa]|titulad[oa]|named|called)\s+"
                    r"[^,;.!?]{1,80}\s+(?:y|and)\s+"
                    r"(?:(?:una?|an?|el|la|los|las|the|mis?|my)\s+)*$"
                ),
            )
            if not (plain_coordination or labeled_coordination):
                break
            selected.append((start, end, domain))
            seen_domains.add(domain)
            previous_end = end
        for index, (start, _, domain) in enumerate(selected):
            matches.append(
                (
                    action.start() if index == 0 else action.end() + start,
                    0,
                    operation_by_domain[domain],
                )
            )
            appended += 1
    return appended


def _review_local_data_effects(
    matches: list[tuple[int, int, str]],
    folded: str,
    head: str,
    *,
    context_note: bool,
) -> bool:
    """Append clause-local data effects and report explicit web-search intent."""

    if _head_is(head, r"(?:anota|anotar|anotame|apunta|apuntame|jot)") and not _has(
        folded, r"\b(?:nota|note)\b"
    ):
        _append(
            matches,
            folded,
            "note.create",
            r"\b(?:anota|anotar|anotame|apunta|apuntame|jot)\b",
        )
    if _head_is(head, r"(?:nota|nueva|new)") and _has(
        folded, r"^[¿?¡!\s]*(?:nota\s+nueva|nueva\s+nota|new\s+note)\s*:\s*\S"
    ):
        _append(
            matches,
            folded,
            "note.create",
            r"\b(?:nota\s+nueva|nueva\s+nota|new\s+note)\b",
        )
    if _head_is(head, r"(?:write|escribe|escribir)") and _has(
        folded, r"\b(?:nota|note)\b"
    ):
        _append(
            matches,
            folded,
            "note.create",
            r"\b(?:write|escribe|escribir)\b",
        )

    created_domains = (
        _append_domain_actions(
            matches,
            folded,
            _CREATE,
            {
                "note": "note.create",
                "task": "task.create",
                "reminder": "reminder.create",
            },
        )
        if _head_is(head, _CREATE)
        else 0
    )
    if created_domains:
        created_operations = [
            entry[2]
            for entry in matches
            if entry[2]
            in {
                "note.create",
                "task.create",
                "reminder.create",
            }
        ]
        if len(set(created_operations)) == 1:
            for another in re.finditer(
                r"(?:,|\by\b|\band\b)\s+(?:otra|otro|another)\b",
                folded,
                re.IGNORECASE,
            ):
                if _is_negated_match(folded, another):
                    continue
                matches.append((another.start(), 0, created_operations[0]))
    elif context_note:
        another_note = _match(
            folded,
            r"^(?:otra|otro|another)\b",
        )
        if another_note is not None:
            matches.append((another_note.start(), 0, "note.create"))

    web_search_requested = (
        _head_is(head, _SEARCH)
        and _has(
            folded,
            r"\b(?:en|on)\s+(?:la\s+|the\s+)?(?:web|internet)\b",
        )
        and _has(folded, rf"\b{_SEARCH}\b")
    )
    if not web_search_requested:
        if _head_is(head, _SEARCH):
            _append_domain_actions(
                matches,
                folded,
                _SEARCH,
                {
                    "note": "note.search",
                    "task": "task.search",
                },
            )
    if _head_is(head, _LIST):
        _append_domain_actions(
            matches,
            folded,
            _LIST,
            {
                "note": "note.list",
                "task": "task.list",
                "reminder": "reminder.list",
                "routine": "routine.list",
            },
        )
    if _head_is(head, _READ):
        _append_domain_actions(
            matches,
            folded,
            _READ,
            {"note": "note.read"},
        )
    if (
        context_note
        and _head_is(head, r"(?:leela|leelo|leerla|leerlo|read)")
        and _has(folded, r"\b(?:leela|leelo|leerla|leerlo|read it)\b")
        and not any(entry[2] == "note.read" for entry in matches)
    ):
        _append(
            matches,
            folded,
            "note.read",
            r"\b(?:leela|leelo|leerla|leerlo|read it)\b",
        )
    return web_search_requested


_CLOCK_TIME_SELECTOR = (
    r"\b(?:[01]?[0-9]|2[0-3]):[0-5][0-9]\b|"
    r"\b(?:a las?|para las?|at)\s+(?:las\s+)?"
    r"(?:\d{1,2}|una|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|"
    r"once|doce|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)"
    r"(?::[0-5][0-9])?\s*(?:a\.?\s*m\.?|p\.?\s*m\.?|"
    r"de la manana|de la tarde|de la noche|in the morning|"
    r"in the afternoon|in the evening)?(?=\s|$|[,;:.?!])|"
    r"\b(?:\d{1,2}|una|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|"
    r"once|doce|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)"
    r"(?::[0-5][0-9])?\s*(?:a\.?\s*m\.?|p\.?\s*m\.?|"
    r"de la manana|de la tarde|de la noche|in the morning|"
    r"in the afternoon|in the evening)(?=\s|$|[,;:.?!])"
)


_BOUNDED_TEMPORAL_SELECTOR = (
    r"\b(?:hoy|today|manana|tomorrow|esta noche|tonight|"
    r"despues del trabajo hoy|after work today|"
    r"ano nuevo|dia de ano nuevo|new year's day|new year day|"
    r"esta semana|this week|"
    r"la proxima semana|next week|este mes|this month|"
    r"lunes|martes|miercoles|jueves|viernes|sabado|domingo|"
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b|"
    r"\b\d{4}-\d{2}-\d{2}(?:t\S+)?\b|"
    r"\b(?:a las?|para las?|at|from|de|desde)\s+(?:las\s+)?"
    r"(?:\d{1,2}(?::\d{2})?|una|dos|tres|cuatro|cinco|seis|siete|ocho|"
    r"nueve|diez|once|doce|one|two|three|four|five|six|seven|eight|nine|"
    r"ten|eleven|twelve)(?:\s*(?:a\.?\s*m\.?|p\.?\s*m\.?))?\b|"
    rf"\b{_RELATIVE_DURATION_PATTERN}\b"
)


def _latest_notification_selector(text: str) -> bool:
    return _has(
        _fold(text),
        r"\b(?:latest|last|most recent|newest|ultima|ultimo|mas reciente|"
        r"recien (?:cread[ao]|programad[ao])|just (?:set|created|scheduled))\b",
    )


def _active_alarm_stop_request(text: str) -> bool:
    """Recognize only a standalone imperative to stop the active alarm."""

    return _has(
        _fold(text),
        r"^[^\w]*para\s+(?:(?:la|el)\s+)?alarma"
        r"(?:\s*[,;:]?\s+(?:por favor|please))?[\s,;:.!?]*$",
    )


def _alarm_turn_off_request(text: str) -> bool:
    """Recognize an alarm cancellation paraphrase even with a modal head."""

    folded = _fold(text)
    return _has(folded, r"\b(?:alarm|alarma)\b") and _has(
        folded,
        r"\b(?:turn(?:ed)?\s+of+|turn(?:ed)?\s+off|apaga|apagar|"
        r"deactivate|deactivates|desactiva|desactivar)\b",
    )


def _exact_local_reminder_title(text: str) -> str | None:
    """Return a bounded literal title only for one exact local reminder."""

    folded = _fold(text).strip()
    if _has(folded, r"\b(?:recordatorios|reminders)\b") or _has(
        folded, _CLOCK_TIME_SELECTOR
    ):
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
            r"(?:delete|remove|cancel|erase|eliminalo|borrarlo|quitarlo|"
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
            r"(?:se\s+(?:cancelo|cancelaron)|(?:was|were)\s+cancelled)\s+"
            r"(?:asi que|por lo que|so)\s+"
            r"(?:(?:este|el|this|the)\s+)?(?:recordatorio|reminder)\s+"
            r"(?:se\s+(?:tiene|debe)\s+que\s+|needs?\s+to\s+be\s+)?"
            r"(?:eliminar|borrar|cancelar|deleted|removed|cancelled)[\s.!?]*$"
        ),
    )
    for pattern in patterns:
        found = re.match(pattern, folded, re.IGNORECASE)
        if found is None:
            continue
        title = re.sub(
            r"(?:\s+please|\s+por favor)$",
            "",
            found.group("title").strip(" \t\r\n.,;:!?\"'"),
            flags=re.IGNORECASE,
        ).strip()
        if title and title not in {
            "a reminder",
            "el recordatorio",
            "it",
            "one",
            "please",
            "por favor",
            "that",
            "this",
        }:
            return title
    return None


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


def _review_calendar_message_and_direct_reminder_effects(
    matches: list[tuple[int, int, str]],
    folded: str,
    head: str,
) -> None:
    """Append complete scheduling and messaging requests with literal data."""

    calendar_domain = _has(
        folded,
        r"\b(?:calendario|calendar|evento|eventos|event|events|"
        r"reunion|reuniones|meeting|meetings|cita|citas|appointment|appointments)\b",
    )
    temporal = (
        _has(
            folded,
            _BOUNDED_TEMPORAL_SELECTOR,
        )
        or _absolute_calendar_range_parts(folded) is not None
    )
    if temporal and _bounded_calendar_list_query(folded):
        _append(
            matches,
            folded,
            "calendar.event.list",
            (
                rf"\b(?:{_LIST}|cuando|when|eventos|events)\b|"
                r"\bduring(?=\s+the\s+timeframe)\b|"
                r"\b(?:revisa|revisar|review|check|consulta|consultar)\b|"
                r"\b(?:what is going on|que (?:sucede|pasa)|"
                r"what\s+(?:meetings|events|appointments)\s+"
                r"(?:occurred|happened|took\s+place)|"
                r"anything i should do|tengo algo que hacer|"
                r"hay algo que (?:hacer|tenga que hacer))\b"
            ),
        )
    if (
        calendar_domain
        and temporal
        and _head_is(
            head,
            rf"(?:{_CREATE}|programa|programar|programame|schedule|"
            r"agenda|agendar|agendame)",
        )
        and (
            _has(
                folded,
                r"\b(?:llamad[oa]|titulad[oa]|called|named)\s+\S+",
            )
            or _has(folded, r"\b(?:reunion|meeting|evento|event)\b")
        )
        and _has(
            folded,
            r"\b(?:de|desde|from)\s+(?:las\s+)?(?:\d{1,2}|"
            r"una|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|once|doce|"
            r"one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)"
            r"(?:\s*(?:am|pm))?\s+(?:a|hasta|to)\s+(?:las\s+)?"
            r"(?:\d{1,2}|una|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|"
            r"diez|once|doce|one|two|three|four|five|six|seven|eight|nine|ten|"
            r"eleven|twelve)\b",
        )
    ):
        _append(
            matches,
            folded,
            "calendar.event.create",
            rf"\b(?:{_CREATE}|programa|programar|programame|schedule|"
            r"agenda|agendar|agendame)\b",
        )

    if (
        _head_is(
            head,
            r"(?:recuerdame|recuerdamelo|recordame|recordamelo|avisame|remind)",
        )
        and (temporal or _has(folded, _DEICTIC_DAY))
        and _has(
            folded,
            r"^[¿?¡!\s]*(?:recuerdame|recuerdamelo|recordame|recordamelo|"
            r"avisame|remind\s+me)\b.+",
        )
    ):
        _append(
            matches,
            folded,
            "reminder.create",
            r"\b(?:recuerdame|recuerdamelo|recordame|recordamelo|avisame|remind)\b",
        )

    if (
        temporal
        and not any(entry[2] == "reminder.create" for entry in matches)
        and re.match(
            # «Dentro de doce minutos, recordame …»: the duration leads and the
            # reminder head follows it (TIME1189/011).
            rf"^[¿?¡!\s]*(?:en|in|dentro\s+de|within)\s+{_RELATIVE_DURATION_PATTERN},?\s+"
            r"(?:recuerdame|recuerdamelo|recordame|recordamelo|avisame|remind\s+me)\b.+",
            folded,
        )
    ):
        _append(
            matches,
            folded,
            "reminder.create",
            r"\b(?:recuerdame|recuerdamelo|recordame|recordamelo|avisame|remind)\b",
        )

    if (
        temporal
        and _count_down_request(folded)
        and not any(entry[2] == "notification.schedule" for entry in matches)
    ):
        _append(
            matches,
            folded,
            "notification.schedule",
            r"\b(?:conta|cuenta|contame|cuentame|count)\b",
        )

    if (
        temporal
        and _head_is(
            head,
            r"(?:programa|programar|programame|schedule|pon|poner|ponme|pone|"
            r"poneme|pongame|set|arranca|inicia|start|alarma|alarm|"
            r"temporizador|timer)",
        )
        and _has(
            folded,
            r"\b(?:alarma|alarmas|alarm|alarms|temporizador|"
            r"temporizadores|timer|timers|aviso|avisos)\b",
        )
    ):
        _append(
            matches,
            folded,
            "notification.schedule",
            r"\b(?:programa|programar|programame|schedule|pon|poner|ponme|pone|"
            r"poneme|pongame|set|arranca|inicia|start|alarma|alarm|"
            r"temporizador|timer)\b",
        )

    if (
        temporal
        and _has(folded, r"\b(?:recordatorio|reminder)\b")
        and not any(entry[2] == "reminder.create" for entry in matches)
        and _head_is(
            head,
            r"(?:pon|ponme|pone|poneme|pongame|crea|crear|programa|programar|"
            r"set|schedule|recordatorio|reminder)",
        )
    ):
        _append(
            matches,
            folded,
            "reminder.create",
            r"\b(?:pon|ponme|pone|poneme|pongame|crea|crear|programa|programar|"
            r"set|schedule|recordatorio|reminder)\b",
        )

    cancel_notification = (
        (
            _head_is(
                head,
                r"(?:cancela|cancelar|cancel|quita|quitar|remove|remueve|"
                r"elimina|eliminar|delete|borra|borrar)",
            )
            or _has(folded, r"^get\s+rid\s+of\b")
        )
        and _has(folded, r"\b(?:alarma|alarm|recordatorio|reminder)\b")
        and not _has(
            folded,
            r"\b(?:alarmas|alarms|recordatorios|reminders)\b",
        )
    )
    exact_local_reminder_title = _exact_local_reminder_title(folded)
    exact_local_reminder_lookup = (
        (
            _head_is(
                head,
                r"(?:ver|ve|muestra|muestrame|ensena|show|see|view|find|busca)",
            )
            or _has(folded, r"^can i (?:see|view)\b")
        )
        and _has(folded, r"\b(?:recordatorio|reminder)\b")
        and _has(folded, r"\b(?:otra vez|de nuevo|nuevamente|again)\b")
        and _has(
            folded,
            r"\b(?:recordatorio|reminder)\s+(?:de|para|sobre|for|about)\s+\S",
        )
    )
    if exact_local_reminder_lookup:
        _append(
            matches,
            folded,
            "reminder.resolve.exact",
            r"\b(?:ver|ve|muestra|muestrame|ensena|show|see|view|find|busca)\b",
        )
    if exact_local_reminder_title is not None:
        _append(
            matches,
            folded,
            "reminder.delete",
            r"\b(?:cancela|cancelar|cancel|quita|quitar|remove|remueve|"
            r"elimina|eliminar|delete|borra|borrar|find|busca|encuentra)\b",
        )
    elif cancel_notification and (
        _has(folded, _CLOCK_TIME_SELECTOR) or _latest_notification_selector(folded)
    ):
        operation = (
            "notification.cancel.at"
            if _has(folded, _CLOCK_TIME_SELECTOR)
            else "notification.cancel.latest"
        )
        _append(
            matches,
            folded,
            operation,
            r"\b(?:cancela|cancelar|cancel|quita|quitar|remove|remueve|"
            r"elimina|eliminar|delete|borra|borrar|get rid of)\b",
        )

    send_head = _head_is(
        head,
        r"(?:envia|enviar|manda|mandar|dile|decile|tell|send)",
    )
    explicit_channel = _has(
        folded,
        r"\b(?:whatsapp|wsp|discord|signal|telegram)\b",
    )
    explicit_payload = _has(
        folded,
        r"\b(?:mensaje|message)\s+[«\"'‘“]?[a-z0-9].+",
    )
    explicit_recipient = _has(
        folded,
        r"\b(?:a|para|to)\s+[a-z0-9][a-z0-9 ._-]{0,80}\s+"
        r"(?:el\s+|the\s+)?(?:mensaje|message)\b|"
        r"\b(?:envia|manda|send)\s+[a-z0-9][a-z0-9 ._-]{0,80}\s+"
        r"(?:el\s+|the\s+)?(?:whatsapp\s+)?(?:mensaje|message)\b",
    ) and not _has(
        folded,
        r"\b(?:a|para|to)\s+(?:ellos|ellas|les|them)\b|"
        r"\b(?:send|envia|manda)\s+(?:them|les)\b",
    )
    tell_shape = _has(
        folded,
        r"^[¿?¡!\s]*(?:(?:dile|decile)\s+a\s+"
        r"[a-z0-9][a-z0-9 ._-]{0,80}?\s+"
        r"(?:(?:en|por)\s+(?:whatsapp|wsp|discord)\s+)?que|"
        r"tell\s+[a-z0-9][a-z0-9 ._-]{0,80}?\s+"
        r"(?:on\s+(?:whatsapp|discord)\s+)?that)\s+\S.+",
    ) and not _has(
        folded,
        r"^[¿?¡!\s]*(?:dile|decile)\s+a\s+(?:ellos|ellas|les)\b",
    )
    if (
        send_head
        and explicit_channel
        and ((explicit_payload and explicit_recipient) or tell_shape)
    ):
        _append(
            matches,
            folded,
            "message.send",
            r"\b(?:envia|enviar|manda|mandar|dile|decile|tell|send)\b",
        )


# «me queda…», «me alcanza…»: el clítico dativo abre una pregunta de estado
# solo con uno de estos verbos. «Me interesa…» o «me gustaría…» no lo son, así
# que el clítico nunca entra suelto en la lista de cabezas.
_DATIVE_STATE_OPENING = (
    r"me\s+(?:queda|quedan|quedaba|alcanza|alcanzan|sobra|sobran|falta|faltan|"
    r"dices|dice|decis|puedes decir|podrias decir)"
)

# «modelo» abre una pregunta de estado solo cuando el objeto es una pieza de
# este equipo. Suelto encabeza notas de configuración («Modelo FT Q4_K_M…»).
_HARDWARE_MODEL_OPENING = (
    r"(?:modelo|model)\s+(?:de\s+)?"
    r"(?:(?:mi|la|el|este|esta|my|the|this)\s+)?"
    r"(?:gpu|vram|tarjeta|placa|procesador|processor|cpu|video|"
    r"graphics|equipo|pc|computador|computadora|computer)"
)

# Aperturas de una pregunta de estado en ES/EN, incluidas las nominales
# («nivel de batería», «gpu usage») que no llevan verbo. Es solo una compuerta
# de acto de habla: cada reviewer sigue exigiendo su propio verbo y objeto, y
# ninguna de estas palabras selecciona por sí sola una operación.
_STATE_QUERY_HEAD = (
    r"(?:en que|en cuanto|a cuanto|a que|de cuanto|"
    r"cuanto|cuanta|cuantos|cuantas|cuan|"
    r"how\s+(?:much|many)|"
    r"queda|quedan|resta|hay|tengo|tiene|tienes|"
    rf"{_DATIVE_STATE_OPENING}|"
    r"am|do|does|have|has|"
    r"dame|decime|mostrame|display|ver|"
    r"chequea|checa|checar|verifica|verificar|fijate|mira|mirar|"
    r"bateria|battery|gpu|vram|cpu|procesador|processor|ram|memoria|memory|"
    r"disco|disk|storage|almacenamiento|espacio|space|windows|"
    r"uso|usage|nivel|level|porcentaje|percentage|percent|carga|"
    r"estado|status|version|free|current|overall|"
    rf"{_HARDWARE_MODEL_OPENING}|"
    r"audio|sonido|sound|volumen|volume)"
)

# Verbos de observación que, por sí solos, ya piden mirar el equipo.
_MACHINE_STATUS_OBSERVATION_HEAD = (
    r"(?:revisa|revisar|review|check|chequea|checar|checa|verifica|"
    r"verificar|comprueba|comprobar|fijate|mira|mirar|muestra|muestrame|"
    r"mostrame|show|display|dime|decime|dame|ver)"
)

# Cabezas que abren una observación del equipo. Se combinan siempre con un
# alcance medible y con el veto de conocimiento/diagnóstico.
_MACHINE_STATUS_HEAD = (
    rf"(?:{_MACHINE_STATUS_OBSERVATION_HEAD}|"
    r"como|how|que|what|which|cual|cuanto|cuanta|cuantos|cuantas|"
    r"queda|quedan|hay|tengo|tiene|tienes|"
    r"esta|estan|is|are|am|do|does|"
    r"bateria|battery|gpu|vram|cpu|procesador|processor|ram|memoria|memory|"
    r"disco|disk|storage|almacenamiento|espacio|space|windows|"
    r"uso|usage|nivel|level|porcentaje|percentage|percent|carga|"
    r"estado|status|version|free|current|overall)"
)

# El pedido debe preguntar por el estado o la dotación del alcance, no ordenar
# un cambio sobre él.
_MACHINE_STATUS_OBSERVATION = (
    r"\b(?:estado|status|salud|health|"
    r"uso|usage|usando|using|use|usa|usan|utilizada|used|"
    r"ocupad[oa]s?|ocupando|busy|llen[oa]s?|full|cargad[oa]s?|load|"
    r"nivel|niveles|level|levels|porcentaje|percent|percentage|"
    r"queda|quedan|resta|restante|remaining|left|alcanza|"
    r"libre|libres|free|disponible|disponibles|available|"
    r"carga|cargando|charging|charge|"
    r"cuanto|cuanta|cuantos|cuantas|cuan|how\s+much|how\s+many|"
    r"version|build|modelo|model|instalad[oa]s?|installed|total|"
    r"tiene|tienes|tengo|hay|have|has|"
    r"anda|andan|va|van|esta|estan|is|are|am|running|"
    r"actual|actuales|current|ahora|now|mismo|general|overall)\b"
)


def _machine_status_topic(text: str) -> re.Match[str] | None:
    """Locate a measured topic governing an observation, without rewriting it.

    This is only syntax. Domain, time, device, quotation, negation and whole
    request checks still decide authority. Do not call the envelope/head
    readers here: they consume this view and must not recurse into themselves.
    """

    if "," not in text and ";" not in text:
        return None
    scope = (
        rf"(?:(?:el|la|mi|este|esta|the|my|this)\s+)?"
        rf"(?:{_MACHINE_STATUS_EVIDENCE})(?:\s+c:?)?"
    )
    found = _match(
        text,
        rf"^[¿?¡!\s]*{_REQUEST_PREFIX}"
        r"(?:(?:de|del|sobre|respecto\s+a|en\s+cuanto\s+a|"
        r"con\s+respecto\s+a|about|regarding|as\s+for)\s+)?"
        rf"(?P<scope>{scope}(?:\s+(?:y|and)\s+{scope})?)"
        r"\s*(?P<separator>[,;])\s*"
        rf"(?P<body>[¿?¡!\s]*{_REQUEST_PREFIX}"
        rf"(?:{_MACHINE_STATUS_HEAD}|tell)\b.*)$",
    )
    if found is None or (
        not _has(found.group("body"), _MACHINE_STATUS_OBSERVATION)
        or _is_negative_effect_clause(found.group("body"))
    ):
        return None
    return found


_WIFI_STATE_QUESTION = re.compile(
    r"\bwi[\s-]?fi\s+(?:esta|is|anda)\s+(?:prendid[oa]|encendid[oa]|apagad[oa]|"
    r"activ[oa]|activad[oa]|desactivad[oa]|conectad[oa]|funcionando|on|off|"
    r"enabled|disabled|connected|working)\b|"
    r"\b(?:esta|is)\s+(?:prendid[oa]|encendid[oa]|apagad[oa]|activ[oa]|on|off|enabled)\s+"
    r"(?:el\s+|the\s+)?wi[\s-]?fi\b",
    re.IGNORECASE,
)


_BLUETOOTH_STATE_QUESTION = re.compile(
    r"^[¿?¡!\s]*(?:"
    # «tengo el bluetooth encendido», «¿tengo el bluetooth prendido?»
    r"(?:tengo|tenes|tienes|dejaste|deje|do\s+i\s+have)\s+(?:el\s+|the\s+)?bluetooth\s+"
    r"(?:prendid[oa]|encendid[oa]|apagad[oa]|activ[oa]|activad[oa]|desactivad[oa]|on|off|enabled|disabled)|"
    # «el bluetooth está prendido?», «bluetooth is on?»
    r"(?:el\s+|the\s+)?bluetooth\s+(?:esta|is|anda|queda|quedo)\s+"
    r"(?:prendid[oa]|encendid[oa]|apagad[oa]|activ[oa]|activad[oa]|desactivad[oa]|on|off|enabled|disabled)|"
    # «está encendido el bluetooth?», «is the bluetooth on?»
    r"(?:esta|is)\s+(?:prendid[oa]|encendid[oa]|apagad[oa]|activ[oa]|activad[oa]|on|off|enabled)\s+(?:el\s+|the\s+)?bluetooth|"
    # «y el bluetooth?», «and bluetooth?»: the state question with no antecedent.
    r"(?:y|and)\s+(?:el\s+|the\s+)?bluetooth"
    r")\b[\s?!.,]*$",
    re.IGNORECASE,
)


_DISPLAY_STATUS_QUESTION = re.compile(
    r"^[¿?¡!\s]*(?:"
    # «qué resolución tengo», «qué resolución de pantalla tengo», «cuál es la resolución de mi pantalla»
    r"(?:que|cual\s+es\s+la|what|what's|whats|dime\s+(?:que|la|cual)|decime\s+(?:que|la|cual))\s+resolucion(?:\s+(?:de|del)\s+(?:la\s+|mi\s+|el\s+|the\s+|my\s+)?(?:pantalla|monitor|screen|display))?(?:\s+(?:tengo|tiene|uso|estoy\s+usando|do\s+i\s+have|is|am\s+i\s+using))?|"
    # «cuántos monitores tengo», «how many monitors do i have»
    r"(?:cuantos|cuantas|how\s+many)\s+(?:monitores|pantallas|monitors|screens|displays)(?:\s+(?:tengo|hay|tiene|do\s+i\s+have|are\s+there|are\s+connected))?|"
    # «qué Hz tiene el monitor», «a cuántos Hz va la pantalla», «qué frecuencia de refresco tiene el monitor»
    r"(?:que|cuantos|a\s+cuantos|what|how\s+many)\s+(?:hz|hertz|hercios|frecuencia(?:\s+de\s+(?:refresco|actualizacion))?|refresh\s+rate)\s+(?:tiene|va|corre|tengo|has|is|does)?\s*(?:el\s+|la\s+|mi\s+|the\s+|my\s+)?(?:monitor|pantalla|screen|display)?(?:\s+(?:have|run\s+at|running\s+at))?"
    r")\b[\s?!.,]*$",
    re.IGNORECASE,
)


_PYTHON_STATUS_QUESTION = re.compile(
    r"^[¿?¡!\s]*(?:"
    # «dime la versión de Python instalada», «qué versión de python tengo», «cuál es la versión de python»
    r"(?:(?:dime|decime|di|tell\s+me|say)\s+(?:que|cual|la|the|which|what)\s+|"
    r"(?:que|cual\s+es\s+la|what|what's|whats|which)\s+)?"
    r"version\s+(?:de|del|of)\s+python(?:\s+(?:instalada|instalado|tengo|tienes|hay|esta\s+instalada|is\s+installed|do\s+i\s+have|installed))?"
    # «qué python tengo», «tengo python instalado», «is python installed», «python version»
    r"|(?:que|cual|what|which)\s+python(?:\s+version)?(?:\s+(?:tengo|hay|esta\s+instalado|is\s+installed|do\s+i\s+have))"
    r"|(?:tengo|hay|is)\s+python(?:\s+(?:instalado|installed))?"
    r"|(?:is\s+)?python\s+(?:version|installed)(?:\s+installed)?"
    r")\b[\s?!.,]*$",
    re.IGNORECASE,
)


_CALC_NUMBER = r"\d{1,12}(?:[.,]\d{1,6})?"
_CALC_MENTION = r"\b(?:calc|calcu|calculadora|calculator)\b"
_CALC_VERB_OPERATORS = (
    (r"(?:multiplic[aá]|multiplicame|multiplicar|multiply)", r"(?:por|x|×|\*|by|times)", "*"),
    (r"(?:sum[aá]|sumame|sumar|add)", r"(?:m[aá]s|mas|y|\+|and|plus|to)", "+"),
    (r"(?:rest[aá]|restame|restar|subtract)", r"(?:menos|-|minus|from)", "-"),
    (r"(?:divid[ií]|divideme|dividir|divide)", r"(?:entre|por|÷|/|by)", "/"),
)
_CALC_INFIX = {"por": "*", "x": "*", "×": "*", "*": "*", "mas": "+", "más": "+", "+": "+", "menos": "-", "-": "-", "entre": "/", "÷": "/", "/": "/", "times": "*", "plus": "+", "minus": "-"}


def calculator_expression_request(text: str) -> str | None:
    """UI1725 «multiplicá 6 por 7 en la calc», «Suma 2 más 2 en la Calculadora»,
    «cuánto es 6 por 7 en la calculadora»: the arithmetic the person wants typed
    into the open Calculator, as an expression over the person's own numbers;
    None without a Calculator mention or a readable binary operation."""

    folded = _strip_request_envelope(_fold(text)).strip()
    if not _has(folded, _CALC_MENTION) or _has(folded, r"\b(?:abre|abrir|abri|cierra|cerra|open|close)\b"):
        return None
    for verb, operator, symbol in _CALC_VERB_OPERATORS:
        found = re.search(
            rf"\b{verb}\s+(?P<a>{_CALC_NUMBER})\s*{operator}\s*(?P<b>{_CALC_NUMBER})\b",
            folded,
        )
        if found is not None:
            a, b = found.group("a"), found.group("b")
            if symbol == "-" and re.search(r"\bfrom\b", found.group(0)):
                a, b = b, a
            return f"{a}{symbol}{b}"
    infix = re.search(
        rf"(?P<a>{_CALC_NUMBER})\s*(?P<op>por|x|×|\*|mas|\+|menos|-|entre|÷|/|times|plus|minus)\s*(?P<b>{_CALC_NUMBER})\b",
        folded,
    )
    if infix is not None and (
        _head_is(_request_head(folded), r"(?:calcula|calculame|calcular|calculate|compute|cuanto|cuanto|resolve|resolvé|resolver)")
        or _has(folded, r"^[¿?¡!\s]*(?:cuanto|cuánto|what)\s+(?:es|is|da|sale)\b")
    ):
        return f"{infix.group('a')}{_CALC_INFIX[infix.group('op')]}{infix.group('b')}"
    return None


_PYTHON_PACKAGE_REQUEST = re.compile(
    r"^[¿?¡!\s]*(?:"
    # «instala requests con pip», «instalá numpy usando pip», «install pandas with pip»
    r"(?:instala(?:me|r|la|lo)?|install|agrega(?:me)?|anade|pone(?:me)?|pon|add)\s+(?:el\s+|la\s+|the\s+)?"
    r"(?:paquete\s+|package\s+|modulo\s+|module\s+|libreria\s+|library\s+)?(?P<a>[a-z0-9][a-z0-9._-]{0,60})"
    r"(?:\s+(?:de|of|for)\s+python)?\s+(?:con|via|usando|mediante|with|using|through)\s+pip\b"
    # «pip install requests»
    r"|pip3?\s+install\s+(?:-u\s+|--upgrade\s+)?(?P<b>[a-z0-9][a-z0-9._-]{0,60})\b"
    # «instala el paquete requests», «install the python module numpy»
    r"|(?:instala(?:me|r)?|install)\s+(?:el\s+|la\s+|the\s+)?(?:python\s+)?(?:paquete|package|modulo|module|libreria|library)\s+(?:de\s+python\s+)?(?P<c>[a-z0-9][a-z0-9._-]{0,60})\b"
    # «tengo requests instalado en python», «is numpy installed in python»
    r"|(?:tengo|esta|is|do\s+i\s+have)\s+(?:instalad[oa]\s+)?(?:el\s+|la\s+|the\s+)?(?:paquete\s+|package\s+|modulo\s+|module\s+)?(?P<d>[a-z0-9][a-z0-9._-]{0,60})\s+(?:instalad[oa]\s+|installed\s+)?(?:en|in|para|for)\s+python\b"
    r")",
)


_REMOVABLE_MEDIA = (
    r"(?:pendrive|pen\s+drive|pen|usb|memoria\s+usb|memoria\s+externa|disco\s+externo|disco\s+usb|"
    r"unidad\s+externa|unidad\s+usb|usb\s+stick|flash\s+drive|thumb\s+drive|external\s+(?:drive|disk)|"
    r"removable\s+(?:drive|disk)|memory\s+stick)"
)
_REMOVABLE_STORAGE_REQUEST = re.compile(
    r"^[¿?¡!\s]*(?:"
    # «hacé un backup de mis documentos a un pendrive», «copiá mis fotos al usb», «back up my documents to a USB stick»
    r"(?:hace(?:me)?|haz|hazme|make|do|copia(?:me)?|copy|guarda(?:me)?|save|pasa(?:me)?|move|mueve|respalda|back\s*up|backup|exporta|export)\b"
    r"[^.;]{0,80}?\b(?:a|al|en|hacia|to|onto|on|into)\s+(?:un|una|el|la|mi|mis|a|an|the|my)?\s*" + _REMOVABLE_MEDIA + r"s?\b"
    # «qué pendrives hay conectados», «hay algún usb conectado», «is there a flash drive connected»
    r"|(?:que|cuales|cuantos|hay|tengo|is\s+there|are\s+there|which|what|do\s+i\s+have)\b[^.;]{0,40}?\b" + _REMOVABLE_MEDIA + r"s?\b"
    r"[^.;]{0,40}?\b(?:conectad\w*|enchufad\w*|puest\w*|hay|tengo|connected|plugged|attached|available)\b"
    r")",
)


def _removable_storage_request(text: str) -> bool:
    """USB1823 «hace un backup de mis documentos a un pendrive», «qué pendrives hay
    conectados»: a storage.removable.list read of the removable drives connected
    now — nothing is copied; the copy itself is a separate confirmed step."""

    folded = _strip_request_envelope(_fold(text)).strip()
    return _REMOVABLE_STORAGE_REQUEST.match(folded) is not None and not _has(
        folded, r"\b(?:formatea|formatear|format|borra|borrar|elimina|delete|wipe|expulsa|eject|desconecta)\b"
    )


def _python_package_request(text: str) -> str | None:
    """PIP1817 «instala requests con pip»: the package named in an install-with-pip
    or is-it-installed request, answered by a software.python.package.status read
    (pip show in every registered Python) — never an install."""

    folded = _strip_request_envelope(_fold(text)).strip()
    match = _PYTHON_PACKAGE_REQUEST.match(folded)
    if match is None:
        return None
    name = next((value for value in match.groups() if value), None)
    if name is None or name in {"python", "pip", "pip3", "el", "la", "the", "un", "una", "a", "an"}:
        return None
    return name


def _python_status_question(text: str) -> bool:
    """SYSTEM1697 «dime la versión de Python instalada», «qué versión de python
    tengo», «is Python installed»: a software.python.status read of the registered
    installs — never an install, an update or a run."""

    folded = _strip_request_envelope(_fold(text)).strip()
    return (
        _PYTHON_STATUS_QUESTION.match(folded) is not None
        and not _has(folded, r"\b(?:instala|instalar|instalame|install|actualiza|actualizar|update|upgrade|desinstala|uninstall|ejecuta|ejecutar|run|corre|pip)\b")
    )


def _display_status_question(text: str) -> bool:
    """SYSTEM1459 «qué resolución tengo», «cuántos monitores tengo», «qué Hz tiene el
    monitor»: a display.status read of the attached monitors — never a change."""

    folded = _strip_request_envelope(_fold(text)).strip()
    return (
        _DISPLAY_STATUS_QUESTION.match(folded) is not None
        and not _has(folded, r"\b(?:cambia|cambiar|pone|poner|ajusta|ajustar|sube|baja|set|change|brillo|brightness)\b")
    )


def _bluetooth_state_question(text: str) -> bool:
    """NETWORK1457 «tengo el bluetooth encendido», «y el bluetooth?»: a
    bluetooth.radio.status read — the radio's state, never a device list."""

    folded = _strip_request_envelope(_fold(text)).strip()
    return (
        _BLUETOOTH_STATE_QUESTION.match(folded) is not None
        and not _has(folded, r"\b(?:dispositivo|device|auriculares?|headphones?|parlante|speaker)\b")
    )


_WIFI_SCAN_QUESTION = re.compile(
    r"(?:^|\b)(?:que|cuales|cuantas|what|which|how many)\s+(?:(?:wifi|wi[\s-]*fi|wireless)\s+)?(?:redes|networks)(?:\s+(?:wifi|wi[\s-]*fi|inalambricas|wireless))?\s+(?:are\s+)?(?:hay|existen|veo|ves|detectas|encontras|encuentras|alcanzas|disponibles|cerca|cercanas|around|nearby|available|there|can you see|do you see)\b"
    r"|\b(?:escanea|escaneame|escanear|scan|busca|buscame|buscar|search for|list|lista|listame|listar|mostrame|muestrame|show)\b.{0,24}\b(?:redes|networks)(?:\s+(?:wifi|wi[\s-]*fi|inalambricas|wireless))?\b"
    r"|\b(?:redes|networks)\s+(?:wifi|wi[\s-]*fi|inalambricas|wireless)\s+(?:disponibles|cercanas|visibles|available|nearby|visible|around)\b"
)


_WIFI_RADIO_SET_REQUEST = re.compile(
    r"^[¿?¡!\s]*(?:(?:por\s+favor|please)\s*[,;:]?\s*)?"
    r"(?P<verb>prende|prendeme|prender|encende|encendeme|encender|enciende|activa|activame|activar|turn\s+on|switch\s+on|enable|"
    r"apaga|apagame|apagar|desactiva|desactivame|desactivar|turn\s+off|switch\s+off|disable)\s+"
    r"(?:me\s+)?(?:el\s+|la\s+|the\s+)?(?:radio\s+)?(?:wifi|wi[\s-]*fi|wireless|red\s+inalambrica)"
    r"(?:\s+(?:del\s+|de\s+la\s+|of\s+the\s+)?(?:pc|computadora|compu|equipo|laptop|notebook|computer))?[\s.!?]*$"
)


_WIFI_OFF_OFFER = re.compile(
    r"(?:wifi|wi[\s-]*fi|radio|antena).{0,80}(?:apagad|off).{0,160}\?|(?:apagad|off).{0,80}(?:wifi|wi[\s-]*fi).{0,160}\?"
)
_ASSENT_TO_OFFER = re.compile(
    r"^[¿?¡!\s]*(?:si|sí|dale|ok|okey|okay|bueno|claro|obvio|por\s+favor|yes|yeah|yep|sure|please|go\s+ahead|do\s+it|hacelo|hazlo|prendelo|encendelo|enciendelo|prende|encende|turn\s+it\s+on)"
    r"(?:[,\s]+(?:si|sí|dale|por\s+favor|please|hacelo|hazlo|prendelo|encendelo|enciendelo|y\s+busca|y\s+escanea|and\s+scan|prende\s+el\s+wifi|encende\s+el\s+wifi|turn\s+it\s+on|turn\s+on\s+the\s+wifi))*[\s.!?]*$"
)
_ACCEPTED_WIFI_OFFER_EVIDENCE = "encender el wifi y buscar redes (oferta aceptada)"


def _accepted_wifi_offer_evidence(evidence: str) -> bool:
    return evidence == _ACCEPTED_WIFI_OFFER_EVIDENCE


def accepted_wifi_offer(
    text: str,
    history: object,
    available_operations: Iterable[str],
) -> EffectIntent | None:
    """NETWORK1737: the person asked which networks there are, the assistant said the
    Wi-Fi radio is off and offered to turn it on, and the person now assents
    → turn the radio on (confirmed) and scan. Nothing else reads an assent."""

    available = frozenset(available_operations)
    if not {"wifi.radio.set", "wifi.scan"} <= available or not isinstance(history, list):
        return None
    if _ASSENT_TO_OFFER.match(_strip_request_envelope(_fold(text)).strip()) is None:
        return None
    items = [item for item in history if isinstance(item, dict)]
    if items and items[-1].get("role") == "user" and items[-1].get("content") == text:
        items = items[:-1]
    assistant = next((str(item.get("content") or "") for item in reversed(items) if item.get("role") == "assistant"), "")
    previous = next((str(item.get("content") or "") for item in reversed(items) if item.get("role") == "user"), "")
    if not assistant or not previous:
        return None
    if _WIFI_OFF_OFFER.search(_fold(assistant)) is None or not _wifi_scan_question(previous):
        return None
    return EffectIntent(("wifi.radio.set", "wifi.scan"), (_ACCEPTED_WIFI_OFFER_EVIDENCE, _ACCEPTED_WIFI_OFFER_EVIDENCE))


def wifi_radio_set_request(text: str) -> bool | None:
    """NETWORK1737 «prendé el wifi», «apagá el wifi», «turn on the wifi»: the desired
    radio state, or None when the text is not that order."""

    folded = _strip_request_envelope(_fold(text)).strip()
    found = _WIFI_RADIO_SET_REQUEST.match(folded)
    if found is None:
        return None
    return not _has(found.group("verb"), r"^(?:apaga|apagame|apagar|desactiva|desactivame|desactivar|turn\s+off|switch\s+off|disable)$")


def _wifi_scan_question(text: str) -> bool:
    """NETWORK1729 «qué redes wifi hay», «escaneá las redes wifi», «what wifi networks
    are there»: a wifi.scan read of the networks the adapter sees — never a
    connection, a change of the radio, nor the saved-profile listing."""

    folded = _strip_request_envelope(_fold(text)).strip()
    return (
        _WIFI_SCAN_QUESTION.search(folded) is not None
        and _has(folded, r"\b(?:wifi|wi[\s-]*fi|inalambric\w*|wireless|redes|networks)\b")
        and not _has(folded, r"\b(?:conecta\w*|desconecta\w*|connect|apaga\w*|prende\w*|enciende\w*|turn|guardad\w*|saved|perfiles?|profiles?|olvida\w*|forget|borra\w*|delete)\b")
    )


def _wifi_state_question(text: str) -> bool:
    """«decime si el wifi está prendido», «¿el wifi está encendido?»: a wifi.status read."""

    return (
        _WIFI_STATE_QUESTION.search(text) is not None
        and not _has(
            text,
            r"\b(?:apaga\w*|prende\w*|enciende\w*|encende\w*|activa\w*|desactiva\w*|"
            r"conecta\w*|desconecta\w*|turn|enable|disable)\b",
        )
        # «… y apagalo»: a second action makes it a compound, not a bare read.
        and not _has(text, r"\b(?:y|and)\s+\w")
    )


def _is_direct_request(text: str) -> bool:
    """Require a request speech act before granting deterministic authority."""

    topic = _machine_status_topic(text)
    if topic is not None:
        text = topic.group("body")
    text = _negative_state_question_body(text) or text
    # MUSIC1675 «If Spotify is open, pause it.»: the present-state condition
    # frames the request; the speech act is the clause after it.
    conditioned = re.sub(_OPEN_STATE_CONDITION, "", text, count=1)
    if conditioned != text and conditioned.strip():
        text = conditioned
    # SCREEN1807: a leading statement of what is open on the screen frames the request.
    text = _without_screen_state_preface(text)
    # LIMITS1681 «en Discord apretá enter»: the client context frames the request.
    framed = re.sub(r"^[¿?¡!\s]*(?:en|in|on)\s+(?:discord|whatsapp|teams|telegram|slack|skype|zoom|signal|messenger)[,]?\s+", "", text, count=1)
    if framed != text and framed.strip():
        text = framed
    if (
        browser_back_arguments(text) is not None
        or browser_new_tab_arguments(text) is not None
        or browser_close_all_tabs_arguments(text) is not None
        or _direct_process_inventory_request(text)
        or _explicit_google_search_query(text) is not None
        or _resume_existing_media(text)
        or _media_transport_action(text)
        or _direct_alarm_schedule_request(text)
        # NETWORK1293: «¿el wifi está encendido?» is a read request without a
        # verb head; the state question itself is the speech act.
        or _wifi_state_question(text)
        or _wifi_scan_question(text)
        or _bluetooth_state_question(text)
        or _display_status_question(text)
        or _python_status_question(text)
        or _python_package_request(text) is not None
        or _removable_storage_request(text)
        or _research_question_query(text) is not None
        or message_draft_request(text) is not None
        or client_channel_request(text) is not None
    ):
        return True
    request_head = (
        rf"(?:{_OPEN}|{_LIST}|{_READ}|{_CREATE}|{_SEARCH}|{_MUTE_VERB}|"
        r"haz|hacer|hazme|haceme|hace|toma|tomar|fotografia|fotografiar|"
        r"snapshot|captura|capturar|retrata|retratar|take|capture|"
        r"genera|generar|generate|grab|reporta|report|enumera|enumerar|enumerate|"
        r"indica|indicate|detalla|detail|cuentame|describe|presenta|present|"
        # WEB1539 «resumime esta página»: summarizing is a request speech act.
        r"resumime|resumeme|resumi|resumir|resumelo|resumela|summarize|summarise|"
        r"ask(?=\s+(?:on\s+the\s+what\s+bluetooth\s+radio\s+can\s+see|"
        r"kick\s+check\b|capture\b))|"
        r"sabe(?=\s+en\s+imagen\b)|"
        r"as(?=\s+a\s+list\b)|"
        r"state|determina|determine|"
        r"necesito(?:\s+(?:saber|ver|escuchar))?|i\s+need(?:\s+to\s+know)?|"
        r"need\s+to\s+know|quiero(?:\s+ver)?|i\s+want(?:\s+to)?|"
        r"bring\s+up|establish|assess|evalua|evaluate|"
        r"recorre|reveal|revela|read\s+(?:out|back)|name|"
        r"senala|point\s+out|indaga|hunt\s+through|"
        r"senalame|echale\s+un\s+vistazo|have\s+a\s+look|look\s+at|"
        r"pull\s+up|pasame|sacame|tirame|take\s+stock|inventory|"
        r"quisiera|i\s+would\s+like|reune|gather|repasa|"
        r"pon\s+a\s+la\s+vista|bring\b.{0,48}\binto\s+view|"
        r"bring\s+me\s+up\s+to\s+date|dejame|armame|track\s+down|"
        r"a\s+ver\s+si|run\s+(?:this|a\s+quick)\s+check|"
        r"sin\s+omitir|without\s+skipping|"
        r"go\s+point\s+(?:by|por)\s+point|"
        r"conserva|preserve|registra|record|arma|put\s+together|build|"
        r"construye|construir|construct|stage|"
        r"identifica|identify|ensename|recitame|recite|guarda|save|"
        r"produce|assemble|retrieve|scan|explore|photograph|pasa|pass|"
        r"recupera|recuperar|recover|localiza|localizar|locate|encuentras|"
        r"investiga|investigar|investigate|research|build|get|"
        r"look\s+(?:through|across)|"
        r"find|rastrea|rastrear|explora|explorar|ubica|consult|"
        r"look(?=\s+on\s+(?:the\s+)?web\b)|"
        r"confirma|confirm|verify|see|"
        r"do(?=\s+i\s+have)|"
        r"resuelve|resolver|pon|pone|ponelo|ponlo|poner|ponle|fija|ajusta|adjust|"
        r"establece|set|deja|dejalo|dejala|dejar|put|leave|turn|"
        rf"{_VOLUME_UP_VERB}|{_VOLUME_DOWN_VERB}|bajalo|subelo|increment|"
        r"quita|quitar|saca|sacale|sacar|remove|get\s+rid\s+of|"
        r"pega|pegar|pegalo|pegala|paste|"
        r"trancame|tranca|bloqueame|bloquea|lock|"
        r"agendame|"
        r"para(?=\s+(?:lo\s+que\s+esta|la\s+descarga))|"
        r"scroll|scrollea|scrollear|"
        # NETWORK1293: radio verbs with clitics or voseo («apagame el
        # bluetooth», «encendé el bluetooth», «activá»).
        r"apaga|apagame|apagalo|enciende|encende|encendeme|encendelo|"
        r"prende|prendeme|prendelo|activa|activame|activalo|"
        r"desactiva|desactivame|desactivalo|"
        r"apuntame|apunta|jot|"
        r"dale(?=\s+(?:enter|intro|return))|"
        r"llevame|anda|andar|andate|"
        r"devuelvele|devuelve|devuelveme|"
        r"maximiza|maximizar|maximize|minimiza|minimizar|minimize|"
        # WINDOWS1695 «Minimisa ópera.»: the s-for-z spelling is the same order.
        r"minimisa|minimisame|"
        r"restaura|restaurar|restore|escribe|escribi|escribele|escribile|write|type|"
        r"selecciona|select|copia|copiame|copy|edita|edit|convierte|convert|"
        r"elige|elegir|choose|transforma|arrastra|drag|make|"
        r"navega|navegar|navigate|ve|go|clic|click|"
        # UI1273: «apretá el 5», «pulsá el 7», «presioná el nueve», «hacé clic en…».
        r"apreta|apretale|apretalo|apretala|apretar|aprieta|pulsa|pulsale|pulsalo|pulsala|"
        r"presiona|presionale|presionalo|presionala|press|hace(?=\s+clic)|"
        r"recarga|recargar|reload|refresh|reproduce|reproducir|reproduzca|play|tune|"
        # MUSIC1753: voseo and clitic play verbs («reproducí la sinfonía…»,
        # «tocá una canción en Spotify», «tocame algo»).
        r"reproduci|reproducime|reproducila|reproducilo|toca|tocame|tocala|tocalo|toque|"
        r"reanuda|reanudar|resume|pausa|pausar|pause|deten|detener|stop|revisa|revisar|check|review|"
        r"consulta|consultar|comprueba|comprobar|checkea|chequea|averigua|averiguar|"
        r"(?:fijate|fijese)(?=\s+si\b)|"
        r"find\s+out|inspect|inspecciona|give|prepara|prepare|resolve|"
        # WINDOWS1385 «traé chrome al frente», «enfocá chrome», «bring Chrome
        # to the front»: focus heads are request speech acts too.
        r"trae|traeme|traer|lleva|llevar|bring|enfoca|enfocame|enfocar|focus|"
        r"switch(?=\s+to\b)|"
        # SCREEN1417 «describime la pantalla», «describí lo que ves».
        r"describime|describeme|describi|describila|describilo|"
        r"cierra|cerra|cerrar|cerrame|cierrame|cierres|close|envia|enviar|enviale|enviales|"
        r"manda|mandar|mandale|mandales|"
        r"arma|armar|marca|marcar|graba|grabar|record|stage|"
        r"borra|borrar|elimina|eliminar|delete|"
        # AGENDA1339 «cancelame la alarma»: clitic cancellation heads are the
        # same speech act as «cancelá»/«cancel».
        r"cancelame|cancelamela|cancelala|borrame|borrala|quitame|quitala|"
        r"eliminame|eliminala|"
        r"cierralo|cierrala|cerrala|cerralo|close it|dile|decile|tell|send|message|"
        r"pausalo|pausala|pausame|pausa|pausar|pause|"
        r"programa|programar|programame|schedule|agenda|agendar|agendame|"
        r"ponme|pone|poneme|pongame|"
        r"activa|activar|desactiva|desactivar|enciende|encender|prende|prender|"
        r"apaga|apagar|arranca|inicia|start|conecta|conectar|conectame|conectate|connect|"
        # LIMITS1677 «Run pytest.», «Execute ls.»: a command run is a request speech act.
        r"run|execute|"
        # LIMITS1683: downloads, arithmetic and scans are request speech acts too.
        r"descarga|descargar|descargame|download|multiplica|multiplicame|suma|sumame|resta|restame|divide|divideme|calcula|calculame|multiply|subtract|calculate|compute|escanea|scan|"
        r"desconecta|disconnect|cambia|change|"
        r"cancela|cancelar|cancel|"
        rf"{_SCHEDULING_BY_ITSELF}|"
        rf"a(?=\s+que\b)|donde|where|hablame|que|cual|cuales|con\s+que|"
        r"el(?=\s+(?:equipo|computador|pc)\b.{0,96}\b(?:red|network)\b)|"
        rf"esta|estan|quedo|sigue|what|which|when|cuando|"
        rf"whether|si|is|are|name|time|current|local|hora|fecha|"
        rf"{_STATE_QUERY_HEAD})"
    )
    return _local_internet_connection_query(text) or _has(
        text,
        rf"^[¿?¡!\s]*{_REQUEST_PREFIX}"
        rf"(?:(?:primero|first)\s*[,;:]?[¿?¡!\s]+)?"
        # «me abrís la calculadora»: the dative clitic precedes a voseo opening.
        r"(?:me\s+(?=(?:abris|abres|abre|abri|abrime|avri)\b))?"
        # «en la calculadora apretá el 5»: the app context frames the request (UI1273).
        # UI1735 «en Opera hacé clic en …», «en Steam andá a la biblioteca»: any
        # application named as the frame (owner: general mechanisms).
        rf"(?:(?:{_VISIBLE_CLICK_APP_CONTEXT}|(?:en|in|on)\s+(?:la\s+|el\s+|the\s+)?[a-z0-9][a-z0-9 .+-]{{1,40}}?)\s*,?\s+)?"
        rf"{request_head}\b",
    )


_KNOWN_FOLDER_LISTING = (
    r"^[¿?¡!\s]*(?:(?:por favor|please)\s*[,;:]?\s*)?"
    r"(?:(?:lista|listame|list|enumera|enumerame|mostrame|muestrame|muestra|show me|show|"
    r"decime|dime|contame|cuentame|tell me)\s+(?:me\s+)?(?:que\s+|what\s+)?(?:los|las|the|mis|my|todos los|all the|all)?\s*"
    r"(?:archivos|ficheros|files|documentos|cosas|things)\s+(?:(?:que\s+)?(?:hay|tengo|are|is)\s+)?"
    r"(?:de|del|en|in|on|of|from)\s+|"
    r"(?:que|what)\s+(?:(?:archivos?|ficheros?|files?|cosas?|things?)\s+)?"
    r"(?:hay|tengo|is|is there|are|are there|do i have|i have)\s+(?:en|in|on)\s+)"
    r"(?:mi|el|la|my|the)?\s*(?:carpeta\s+(?:de\s+)?|folder\s+)?"
    r"(?P<folder>escritorio|desktop|descargas|downloads|documentos|documents)"
    r"(?:\s+(?:folder|carpeta))?[\s?!.]*$"
)
_KNOWN_FOLDER_ENUM = {
    "escritorio": "desktop", "desktop": "desktop",
    "descargas": "downloads", "downloads": "downloads",
    "documentos": "documents", "documents": "documents",
}


_KNOWN_FOLDER_WORDS = r"(?:escritorio|desktop|descargas|downloads|documentos|documents)"
_KNOWN_FOLDER_RECENT = (
    r"^[¿?¡!\s]*(?:(?:por favor|please)\s*[,;:]?\s*)?"
    r"(?:(?:cuenta|conta|count)\s+(?:los\s+|the\s+)?(?:archivos|ficheros|files)\s+(?:de|del|en|in|on|of)\s+"
    r"(?:mi|el|la|my|the)?\s*(?P<folder_a>" + _KNOWN_FOLDER_WORDS + r")\s+(?:y|and)\s+)?"
    r"(?:lista|listame|list|mostrame|muestrame|muestra|show me|show|dame|give me|decime|dime|tell me)\s+(?:me\s+)?"
    r"(?:los|las|the)?\s*(?P<n>[1-9]|1[0-9]|20)\s+(?:(?:archivos|ficheros|files|entradas|entries)\s+)?"
    r"(?:mas|most)\s+(?:recientes?|nuevos?|recent|newest)(?:\s+(?:archivos|ficheros|files|entradas|entries))?"
    r"(?:\s+(?:de|del|en|in|on|of)\s+(?:mi|el|la|my|the)?\s*(?P<folder_b>" + _KNOWN_FOLDER_WORDS + r"))?[\s?!.]*$"
)


def _known_folder_recent_listing(text: str) -> tuple[str, int] | None:
    """FILES1433 «cuenta los archivos en el escritorio y lista los 5 mas recientes»,
    «listá los 5 archivos más recientes del escritorio»: (folder enum, count)."""

    folded = _fold(text)
    match = re.match(_KNOWN_FOLDER_RECENT, folded)
    if match is None:
        return None
    folder = match.group("folder_a") or match.group("folder_b")
    if folder is None or (match.group("folder_a") and match.group("folder_b")
                          and match.group("folder_a") != match.group("folder_b")):
        return None
    enum = _KNOWN_FOLDER_ENUM.get(folder)
    return (enum, int(match.group("n"))) if enum else None


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


_AGENDA_LISTING = (
    r"^[¿?¡!\s]*(?:(?:por favor|please)\s*[,;:]?\s*)?"
    r"(?:(?:que|what)\s+(?:tengo|hay|do i have|have i got|is there|do i have got)|"
    r"(?:decime|dime|contame|cuentame|tell me|mostrame|muestrame|show me)\s+(?:que\s+(?:tengo|hay)|what\s+(?:i have|there is|is)))\s+"
    r"(?:(?:agendad[oa]s?|programad[oa]s?|planead[oa]s?|planificad[oa]s?|anotad[oa]s?|scheduled|planned|on\s+(?:my|the)\s+agenda|en\s+(?:la|mi)\s+agenda)"
    r"(?:\s+(?:para|for)\s+(?:hoy|manana|today|tomorrow|esta\s+semana|this\s+week))?"
    r"|(?:para|for)\s+(?:hoy|today)\s+(?:agendad[oa]s?|programad[oa]s?|scheduled|planned|en\s+(?:la|mi)\s+agenda))[\s?!.]*$"
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


def _known_folder_listing_request(text: str) -> str | None:
    """FILES1425 «lista los archivos del escritorio», «qué hay en Descargas»:
    the known-folder enum of a whole-folder listing request, else None."""

    folded = _fold(text)
    match = re.match(_KNOWN_FOLDER_LISTING, folded)
    if match is None:
        return None
    return _KNOWN_FOLDER_ENUM.get(match.group("folder"))


def _without_screen_state_preface(text: str) -> str:
    """SCREEN1807: «hay un diálogo de Steam abierto para instalar X, toca …» /
    «there is a Steam dialog open; take …»: the leading statement of what is
    open frames the request; the clause after it is the speech act."""

    stripped = re.sub(
        r"^[¿?¡!\s]*(?:hay|there\s+is|there's|tengo|i\s+have)\s+(?:un|una|unos|unas|el|la|a|an|the)\b"
        r"[^,.;]*?\b(?:abiert[oa]s?|open)\b[^,.;]*[,.;]\s*",
        "",
        text,
        count=1,
        flags=re.IGNORECASE,
    ).strip()
    return stripped or text


def _strict_catalog_request(
    text: str,
    available_operations: frozenset[str],
    application_names: Iterable[str] | ApplicationCatalogIndex,
) -> EffectIntent | None:
    """Resolve high-precision catalog reads and explicitly named contracts.

    Every branch requires a request speech act plus a domain-specific object.
    This complements the verb-oriented reviewer for ordinary state questions
    (``check whether ...``, ``consulta el estado ...``) without turning a
    domain noun by itself into effect authority.
    """

    # The public envelope can contain both a vocative and courtesy marker
    # (``Baxy, por favor: ...``).  The outer resolver removes one layer; peel
    # at most one remaining non-semantic layer for surface invariance.
    text = _strip_request_envelope(text).strip().rstrip(".!?").rstrip()
    text = _without_screen_state_preface(text)
    if "filesystem.known.list" in available_operations and (
        _known_folder_listing_request(text) is not None
        or _known_folder_recent_listing(text) is not None
    ):
        return EffectIntent(("filesystem.known.list",), (text,))
    if "notification.list" in available_operations and _notification_listing_request(text):
        return EffectIntent(("notification.list",), (text,))
    if "bluetooth.radio.status" in available_operations and _bluetooth_state_question(text):
        return EffectIntent(("bluetooth.radio.status",), (text,))
    if "display.status" in available_operations and _display_status_question(text):
        return EffectIntent(("display.status",), (text,))
    if "software.python.status" in available_operations and _python_status_question(text):
        return EffectIntent(("software.python.status",), (text,))
    if "wifi.scan" in available_operations and _wifi_scan_question(text):
        # NETWORK1729: the networks around the PC are read from the adapter.
        return EffectIntent(("wifi.scan",), (text,))
    if (
        "wifi.radio.set" in available_operations
        and wifi_radio_set_request(text) is not None
        and not _is_negative_effect_clause(_fold(text))
    ):
        # NETWORK1737 «prendé el wifi» / «apagá el wifi»: the radio state, confirmed.
        return EffectIntent(("wifi.radio.set",), (text,))
    if (
        "calculator.expression.evaluate" in available_operations
        and calculator_expression_request(text) is not None
        and not _is_negative_effect_clause(_fold(text))
    ):
        # UI1725: the arithmetic is typed into the open Calculator and its
        # display is read back.
        return EffectIntent(("calculator.expression.evaluate",), (text,))
    if window_inventory_arguments(text) is not None:
        return (
            EffectIntent(("window.resolve",), (text,))
            if "window.resolve" in available_operations else None
        )
    desired = _explicit_desire_request(text)
    if desired is not None:
        # A need for an explicit action is not a noun-only request to observe
        # the mentioned domain. Restrict this normalization to effect readers.
        text = desired.group("body")
    text = re.sub(
        r"^(?:primero|first)\s*[,;:]?\s+",
        "",
        text,
        count=1,
        flags=re.IGNORECASE,
    )

    benign_domain_alternative = _has(
        text,
        r"\b(?:pista|track)\s+(?:o|or)\s+(?:video|audio)\b",
    )
    channel_leading_message = _has(
        text,
        r"^(?:(?:por|en|on|via|through)\s+(?:whatsapp|discord)|"
        r"(?:have|ave|ab)\s+discord)\s*[,;:]?\s*"
        r"(?:manda|envia|send|dile|cuentale|avisa|avise|notifica|notify|"
        r"hazle\s+(?:llegar|saber)|"
        r"let\b.{0,48}\bknow|get\b.{0,80}\bto)\b",
    )
    bounded_status_question = _has(text, r"^(?:como|how|con\s+que|en\s+que)\b") and (
        _system_status_domain(text)
        or _network_status_domain(text)
        or _has(
            text,
            r"\b(?:wi[\s-]?fi|wireless\s+(?:connection|signal|link)|"
            r"vinculo\s+inalambrico|comunicacion\s+general|"
            r"communication\s+condition|network\s+access|"
            r"audio|sonido|sound|volume|volumen|"
            r"distribucion\s+de\s+teclas|key\s+arrangement|input\s+map)\b",
        )
    )
    bounded_routine_catalog_question = (
        _has(text, r"^(?:que|cuales?|what|which)\b")
        and _has(
            text,
            r"\b(?:rutinas?|routines?|automatizaciones?|automations?|"
            r"secuencias?\s+habituales?|habitual\s+sequences?)\b",
        )
        and _has(
            text,
            r"\b(?:baxy|guardad[oa]s?|saved|available|disponibles?|"
            r"repetir|repeat)\b|\bback\s+si\b",
        )
    )
    benign_referential_followup = _has(
        text,
        r"[?;]\s*(?:revisal[oa]s?|compruebalo|verificalo|leel[oa]s?|"
        r"check(?:\s+(?:it|them))?|verify(?:\s+it)?|read\s+them|"
        r"dame\s+(?:el\s+)?estado|give\s+me\s+(?:the\s+)?"
        r"(?:state|status))[\s.!?]*$",
    )
    explicit_catalog_composition = (
        _has(
            text,
            r"^(?:confirma|confirm|verify|build|construct|crea|create|stage|"
            r"alista|prepare)\b",
        )
        and _has(text, r"[,;]|\b(?:y|and|then|luego)\b")
        and sum(
            bool(_has(text, pattern))
            for pattern in (
                r"\b(?:installed|instalad[oa])\b",
                r"\b(?:juegos?|games?|game\s+catalog|catalogo\s+de\s+juegos)\b",
                r"\b(?:word|excel)\b",
                r"\b[a-z0-9][a-z0-9_+-]+(?:\.[a-z0-9_+-]+)+\b",
            )
        )
        >= 2
    )
    named_window_query = resolve_application_window_status_name(text, application_names)
    if (
        (
            not _is_direct_request(text)
            and not channel_leading_message
            and not bounded_status_question
            and not explicit_catalog_composition
            and named_window_query is None
            and not _literal_note_payload_request(text)
            and not _bare_note_inventory_request(text)
        )
        or _is_negative_effect_clause(text)
        or (_is_meta_or_tool_denial(text) and not bounded_routine_catalog_question)
        or (
            _has_contradictory_correction(text)
            and not benign_domain_alternative
            and not benign_referential_followup
        )
        or _other_device_effect_scope(text)
    ):
        return None
    # Names and bodies of local records are literal payload.  A title such as
    # ``Captura pantalla y extrae texto`` must never be reinterpreted as a
    # screenshot/OCR composition by the catalog-read grammar; the dedicated
    # write resolver below owns the complete record request.
    if _has(
        text,
        r"^(?:crea|crear|create|anota|anotar|note|agrega|agregar|add|guarda|save)\s+"
        r"(?:(?:un|una|a|an)\s+)?(?:nota|note|tarea|task|recordatorio|reminder)\b",
    ):
        return None
    deferred_effect = _has_unsupported_deferred_effect(text)

    def intent(*operations: str, evidence: tuple[str, ...] = ()) -> EffectIntent | None:
        if not operations or not set(operations) <= available_operations:
            return None
        return EffectIntent(operations, evidence or tuple(text for _ in operations))

    if not deferred_effect and _literal_note_payload_request(text):
        return intent("note.create")
    if named_window_query is not None:
        return intent("window.application.status")

    if _local_internet_connection_query(text):
        # The generic internet domain below means web content, not this local
        # observation. Match the whole clause so a second task is not dropped;
        # a missing catalog operation must not become an unrelated web search.
        return intent("network.status")

    if (
        not deferred_effect
        and _has(
            text,
            r"^(?:trancame|tranca|bloqueame|bloquea|lock)\b",
        )
        and _has(
            text,
            r"\b(?:equipo|pc|computador(?:a)?|computer|maquina|machine|windows)\b",
        )
    ):
        resolved = intent("system.power")
        if resolved is not None:
            return resolved

    package_id = _spoken_package_id(text)
    if (
        package_id is not None
        and not deferred_effect
        and not explicit_catalog_composition
        and _has(
            text,
            r"\b(?:prepara|preparado|prepare|stage|staged|resolve|resuelve|"
            r"ubica|locate|deja|leave|instalacion|installation|instalar|"
            r"install|listo|ready|tied|alista(?:lo|la)?)\b",
        )
        and not _has(text, r"https?://|\b(?:juego|game|steam)\b")
    ):
        resolved_package = intent(
            "package.install.prepare",
            evidence=(package_id,),
        )
        if resolved_package is not None:
            return resolved_package

    if _has(
        text,
        r"^(?:have|ave|ab)\s+discord\s+(?:notify|avise)\s+(?:a\s+)?"
        r"[a-z0-9][a-z0-9 ._-]{0,80}?\s+(?:that|que)\s+\S.+$",
    ):
        resolved_message = intent("message.recipient.resolve", "message.send")
        if resolved_message is not None:
            return resolved_message
    if _has(
        text,
        r"^ask\s+capture\b.{0,48}\bturn\s+screen\s*writing\s+into\s+"
        r"characters?\b",
    ):
        resolved_ocr = intent("capture.screenshot", "ocr.read")
        if resolved_ocr is not None:
            return resolved_ocr
    if _has(
        text,
        r"^a\s+ver\s+si\s+fin\b.{0,96}\bdownloads?\b",
    ):
        resolved_files = intent("filesystem.known.search")
        if resolved_files is not None:
            return resolved_files
    if _has(
        text,
        r"^(?:que|which)\s+habitual\s+sequences?\b.{0,72}"
        r"\bback\s+si\b.{0,32}\brepeat\b",
    ) or _has(
        text,
        r"^show\b.{0,32}\bsub\s*personal\s+o\s+the\s+machines\b",
    ):
        resolved_routine = intent("routine.list")
        if resolved_routine is not None:
            return resolved_routine

    request_observation = _has(
        text,
        r"^(?:comprueba|comprobar|checkea|chequea|averigua|averiguar|check|"
        r"ask(?=\s+(?:on\s+the\s+what\s+bluetooth\s+radio\s+can\s+see|"
        r"kick\s+check\b|capture\b))|"
        r"sabe(?=\s+en\s+imagen\b)|"
        r"as(?=\s+a\s+list\b)|find\s+out|"
        r"consulta|consultar|revisa|revisar|review|inspect|inspecciona|mira|"
        r"dime|decime|contame|fijate|dame|cuentame|tell|show|display|muestra|muestrame|ensename|"
        r"indica|indicate|detalla|detail|lista|listar|list|give|describe|"
        r"presenta|present|state|determina|"
        r"determine|identifica|identify|recitame|recite|"
        r"necesito(?:\s+(?:saber|ver|escuchar))?|i\s+need(?:\s+to\s+know)?|"
        r"need\s+to\s+know|bring\s+up|establish|assess|evalua|evaluate|"
        r"recorre|reveal|revela|read\s+(?:out|back)|name|"
        r"senala|point\s+out|indaga|hunt\s+through|"
        r"echale\s+un\s+vistazo|have\s+a\s+look|look\s+at|"
        r"sacame|pull\s+up|pasame|track\s+down|a\s+ver\s+si|"
        r"haz(?:me)?\s+(?:(?:este|un)\s+)?(?:chequeo|recuento|listado|inventario)|"
        r"take\s+stock|make\s+me\s+a\s+list|inventory|"
        r"quiero\s+(?:saber|ver|si(?=\s+el\s+complete\s+index\b)|see|"
        r"el\s+appointment\s+itinerary)|"
        r"quisiera\s+(?:el\s+itinerario|the\s+appointment\s+itinerary)|"
        r"i\s+want\s+to\s+(?:know|see)|"
        r"i\s+would\s+like\s+the\s+appointment\s+itinerary|"
        r"dejame|leave\s+me|guarda|save|reune|gather|repasa|"
        r"pon\s+a\s+la\s+vista|bring\s+(?:the\s+)?(?:saved\s+)?[^,;]{0,40}\s+into\s+view|"
        r"ponme\s+(?:al\s+dia|up\s+to\s+date)|bring\s+me\s+up\s+to\s+date|"
        r"run\s+(?:this|a\s+quick)\s+check|ubica|"
        r"senalame|quedo|sigue|"
        r"sin\s+omitir\s+ninguno\s*[,;:]?\s*revisa|"
        r"without\s+skipping\s+(?:any|ninguno)\s*[,;:]?\s*(?:inspect|revisa)|"
        r"ve\s+punto\s+por\s+punto|go\s+point\s+(?:by|por)\s+point|"
        r"que|cual|cuales|con\s+que|what|which|is|are|esta|estan|hay|quedo|sigue|"
        r"lee|read|abre|open|reporta|report|enumera|enumerate|recupera|recover|"
        r"retrieve|localiza|locate|investiga|investigate|research|confirma|"
        r"confirm|verify|see|look|find|scan|explore|rastrea|explora|consult|"
        r"haz(?:\s+un\s+chequeo)?)\b",
    ) or (
        _has(text, r"^(?:como|how|con\s+que|en\s+que)\b")
        and (
            _system_status_domain(text)
            or _network_status_domain(text)
            or _has(
                text,
                r"\b(?:wi[\s-]?fi|wireless\s+(?:connection|signal|link)|"
                r"vinculo\s+inalambrico|comunicacion\s+general|"
                r"communication\s+condition|network\s+access|"
                r"audio|sonido|sound|volume|volumen|"
                r"distribucion\s+de\s+teclas|key\s+arrangement|input\s+map)\b",
            )
        )
    )
    action_composition_head = _has(
        text,
        r"^(?:deja|leave|crea|create|construye|construct|captura|capture|"
        r"toma|take|retrata|conserva|preserve|"
        r"registra|record|arma|armame|put\s+together|build|stage|resolve|"
        r"resuelve|pon|put|find|encuentra)\b",
    ) or (
        _has(text, r"^(?:make|get|quiero(?:\s+ver)?|i\s+want(?:\s+to)?)\b")
        and _has(text, r"\b(?:word|excel|netflix|install|installation)\b")
    )

    # High-precision colloquial singletons.  These are semantic shapes, not
    # utterance literals: a request act and a closed catalog domain are both
    # required, while the negative/meta/other-device gates above still win.
    if request_observation and _has(
        text,
        r"\b(?:palabras?|words?)\b.{0,48}\b(?:list[oa]s?|ready)\b"
        r".{0,24}\b(?:pegar|paste)\b",
    ):
        resolved = intent("clipboard.read.text")
        if resolved is not None:
            return resolved
    if (_is_direct_request(text) or benign_referential_followup) and _has(
        text,
        r"\b(?:equipo|computer)\b.{0,72}\b(?:llegando|reaching)\b"
        r".{0,40}\b(?:red|network)\b",
    ):
        resolved = intent("network.status")
        if resolved is not None:
            return resolved
    if request_observation and _has(
        text,
        r"\b(?:notificacion(?:es)?|notifications?)\b.{0,48}"
        r"\b(?:vencid[oa]s?|expired|overdue)\b",
    ):
        resolved = intent("notification.list.due")
        if resolved is not None:
            return resolved
    if (
        (request_observation or action_composition_head)
        and _has(
            text,
            r"\b(?:word|excel)\b.{0,96}\b(?:se\s+llame|called|calle\s+de|named|"
            r"titulad[oa]|titled)\b",
        )
        and not _has(
            text,
            r"[,;]|\b(?:y|and)\s+(?:stage|alista|prepare|check|comprueba|"
            r"verifica|confirma)\b",
        )
    ):
        resolved = intent("office.document.create")
        if resolved is not None:
            return resolved
    if (
        action_composition_head
        and _has(
            text,
            r"\b(?:imagen|image)\b.{0,32}\b(?:pantalla|screen)\b|"
            r"\b(?:pantalla|screen)\b.{0,32}\b(?:imagen|image)\b",
        )
        and _has(
            text,
            r"\b(?:objetos?|objects?)\b.{0,48}\b(?:aparecen?|appear)\b",
        )
    ):
        resolved = intent("capture.screenshot", "vision.describe")
        if resolved is not None:
            return resolved
    if _is_direct_request(text) and _has(
        text,
        r"\b(?:aplicacion(?:es)?|applications?|apps?)\b.{0,64}"
        r"\b(?:recibiendo|receiving)\b.{0,32}\b(?:teclas|keystrokes)\b",
    ):
        resolved = intent("window.active")
        if resolved is not None:
            return resolved

    # Prefer an explicit installed-program inventory request over domain words
    # that may occur inside an authenticated application name (for example,
    # ``VLC media player``). This remains read-only and requires both an
    # observation head and a closed inventory phrase.
    installed_program_inventory = request_observation and _has(
        text,
        r"\b(?:programas?\s+locales?|local\s+programs?|installed\s+apps?|"
        r"programas?\b.{0,64}\b(?:presencia|installed)|"
        r"(?:installed\s+apps?|programas?)\b.{0,64}\b(?:aparece|shows?\s+up))\b",
    )
    if installed_program_inventory and not _has(
        text,
        r"\b(?:juego|game|steam|telefono|phone|tablet)\b",
    ):
        resolved = intent("app.installed", evidence=(text,))
        if resolved is not None:
            return resolved

    # Two explicit read domains may share one request head ("show X and Y").
    # Resolve only audited pairs and preserve the order in which the user names
    # them; an unrecognized third domain still falls through to fail-closed
    # compound conservation.
    if request_observation or action_composition_head:
        domain_patterns = (
            (
                "system.status",
                r"\b(?:sistema|system|estado\s+integral|integral\s+state|"
                r"overall\s+operating\s+condition|combined\s+operating\s+condition|"
                r"condicion\s+conjunta|condicion\s+del\s+equipo|"
                r"system\s+health|machine\s+health|salud\s+del\s+sistema|"
                r"estado\s+del\s+equipo|lectura\s+global)\b|"
                r"\b(?:maquina|machine)\b.{0,32}\b(?:conjunto|whole)\b|"
                r"\bwhole[- ]machine\b|"
                r"\bestado\s+general\b.{0,24}\b(?:pc|equipo|computador)\b|"
                r"\boverall\s+(?:status|state)\b.{0,24}\b(?:pc|computer)\b",
            ),
            (
                "network.status",
                r"\b(?:la\s+red|network|conectividad|connectivity|network\s+access|"
                r"acceso\s+(?:general\s+)?a\s+la\s+red|comunicacion\s+general|"
                r"communication\s+condition|red\s+general|"
                r"enlace\s+general\s+de\s+la\s+maquina)\b",
            ),
            (
                "task.list",
                r"\b(?:tareas?|tasks?|to-dos?|to\s+dos|unfinished\s+items?|"
                r"pendientes?|obligaciones?|obligations?|open\s+items?|open\s+tasks?|"
                r"unresolved\s+(?:to-dos?|to\s+dos)|quehaceres?|chores?|"
                r"chorsker\b.{0,32}\bmanopen|"
                r"items?\b.{0,40}\b(?:resolution|resolucion))\b",
            ),
            (
                "reminder.list",
                r"\b(?:recordatorios?|reminders?|scheduled\s+reminders?|"
                r"future\s+reminder\s+notices?|scheduled\b.{0,32}\bremember|"
                r"programad[oa]s?\b.{0,40}\brecordar|"
                r"things?\b.{0,56}\b(?:bring\s+back\s+to\s+mind|remember\s+later)|"
                r"cosas?\b.{0,72}\b(?:traerme\s+a\s+la\s+memoria|recordar\s+despues|"
                r"bring\s+back\b.{0,24}\b(?:tom\s+indlater|mindletter)))\b",
            ),
            (
                "notification.list.due",
                r"\b(?:alertas?|alerts?|notices?|avisos?|"
                r"notificaciones?|notifications?)\b.{0,64}"
                r"\b(?:overdue|due|past|paso|pasaron|pasada|plazo|crossed|"
                r"expired|fuera\s+de\s+plazo|venci(?:o|eron|d[oa]s?)|superaron)\b|"
                r"\b(?:overdue|past[- ]due|expired)\s+"
                r"(?:alerts?|notices?|notifications?|notes?)\b",
            ),
            (
                "note.list",
                r"\b(?:apuntes?|anotaciones?|memos?)\b|"
                r"(?<!bloc de )(?<!app de )(?<!coso de )\bnotas?\b|"
                r"\bnotes?\b",
            ),
            (
                "clipboard.read.text",
                r"\b(?:portapapeles|clipboard|listo\s+para\s+pegar|ready\s+to\s+paste|"
                r"waiting\s+to\s+be\s+pasted|preparad[oa]s?\s+para\s+pegar|"
                r"palabras?\s+almacenadas?\s+para\s+(?:el\s+)?proximo\s+pegado|"
                r"words?\s+stored\s+(?:(?:for|para)\s+)?(?:the\s+)?next\s+paste|"
                r"text\s+fragment\b.{0,40}\b(?:copied|capid))\b",
            ),
            ("bluetooth.device.list", r"\bbluetooth\b"),
            (
                "peripheral.list",
                r"\b(?:perifericos?|peripherals?|external\s+devices?|plugged\s+devices?|"
                r"external\s+hardware|hardware\s+externo|"
                r"dispositivos?\s+enchufados?\s+externamente|"
                r"physical\s+accessories|attached\s+accessories|accesorios?\s+fisicos?|"
                r"accesorios?\s+(?:estan\s+)?enchufados?|"
                r"plugged-in\s+accessories|accesorios?|accessories)\b",
            ),
            (
                "browser.tabs.list",
                r"\b(?:pestanas?|tabs?|paginas?\s+(?:abiertas?|cargadas?)|"
                r"pagis\s+abiertas?|"
                r"browser\s+pages?|paginas?\s+del\s+navegador|"
                r"paginas?\b.{0,24}\b(?:abiertas?|cargadas?)|"
                r"(?:open|loaded)\s+pages?|open\s+tab\s+set)\b",
            ),
            (
                "window.active",
                r"\b(?:ventana|window)\b.{0,48}\b(?:activ[oa]|active|foco|focus|"
                r"foreground|primer\s+plano|actual|current|frente|frontal|keystrokes|"
                r"por\s+encima\s+del\s+resto|above\s+the\s+rest)\b|"
                r"\b(?:active|focused|foreground|current|front)\s+window\b|"
                r"(?:^|[,;]\s*|\b(?:y|and)\s+)(?:ventana|window)"
                r"(?=\s*(?:[,;]|\by\b|\band\b|$))|"
                r"^(?:name|identify|show|muestra|consulta|identifica)\s+"
                r"(?:(?:the|la)\s+)?(?:window|ventana)(?=\s*(?:[,;]|$))|"
                r"\b(?:programa|program|application|app)\b.{0,48}"
                r"\b(?:teclas|keystrokes|typing\s+focus|foco\s+de\s+escritura)\b",
            ),
            (
                "input.keyboard.status",
                r"\b(?:key\s+(?:map|arrangement)|mapa\s+(?:de\s+entrada|de\s+teclas)|"
                r"key\s+layout|mapa\s+del\s+teclado|keyboard\s+(?:map|layout)|"
                r"distribucion\s+(?:de\s+entrada|de\s+teclas|del\s+teclado)|"
                r"input\s+(?:map|layout)|esquema\s+de\s+entrada|input\s+scheme|"
                r"(?:distribucion|layout|loud)\b.{0,40}\b(?:tecleando|typing))\b",
            ),
            (
                "email.latest.read",
                r"\b(?:ultimo|ultima|latest|newest|most\s+recent|"
                r"most\s+recently\s+received|mas\s+reciente)\b.{0,32}"
                r"\b(?:correo|email|mail|message|item|mailbox|buzon|inbox)\b|"
                r"\b(?:correo|email|mail|mailbox|buzon|inbox)\b.{0,32}"
                r"\b(?:ultimo|ultima|latest|newest|most\s+recent|mas\s+reciente|"
                r"mas\s+recientemente|recientemente\s+recibido|recently\s+received)\b|"
                r"\b(?:correo|email|mail|mailbox\s+item)\b.{0,40}"
                r"\b(?:entro|came\s+in|received)\b|"
                r"\b(?:newly\s+arrived\s+email|correo\s+recien\s+llegado|"
                r"(?:item|contenido|content)\b.{0,32}\b(?:recien|just)\s+received"
                r"\b.{0,24}\b(?:inbox|buzon)|"
                r"mensaje\b.{0,40}\bera\s+(?:y|ive)\s+blast\b.{0,32}"
                r"\bcorreo)\b",
            ),
            (
                "calendar.event.list",
                r"\b(?:calendario|calendar|agenda|citas?|appointments?|"
                r"compromisos?|commitments?)\b",
            ),
            (
                "audio.status",
                r"\b(?:audio|sonido|sound|volume|volumen|salida\s+sonora|"
                r"sound\s+(?:route|routing)|output\s+routing)\b",
            ),
            (
                "media.status",
                r"\b(?:media|multimedia|reproduccion|playing|playback|"
                r"sonando|"
                r"audiovisual\s+session|sesion\s+audiovisual|media\s+session|"
                r"(?:track|pista)\s+(?:or|o)\s+(?:video|audio))\b",
            ),
            (
                "wifi.status",
                r"\bwi[\s-]?fi\b|\b(?:wireless\s+(?:connection|connectivity|link|signal)|"
                r"vinculo\s+inalambrico|conexion\s+inalambrica|"
                r"conectividad\s+inalambrica|conexion\s+sin\s+cable)\b",
            ),
            ("web.search", r"\b(?:web|online|internet|en\s+linea)\b"),
            (
                "filesystem.known.duplicates",
                r"\b(?:duplicad[oa]s?|repetid[oa]s?|duplicates?)\b",
            ),
            (
                "filesystem.known.search",
                r"\b(?:documentos|documents|descargas|downloads)\b",
            ),
            (
                "app.installed",
                r"\b(?:software\s+(?:local|inventory|instalado)|"
                r"inventario\s+instalado|programas?\s+locales?|"
                r"installed\s+(?:applications?|apps?|programs?|software)|"
                r"(?:applications?|apps?|programs?|software)\s+installed|"
                r"local\s+(?:app|software)\s+inventory|"
                r"aplicaciones?\s+de\s+inicio|menu\s+inicio|start\s+menu\s+apps?|"
                r"software\s+del\s+equipo|"
                r"(?:whether|si)\b.{0,64}\b(?:instalad[oa]|installed))\b",
            ),
            (
                "game.catalog.list",
                r"\b(?:juegos?|games?|videojuegos?|"
                r"playable\s+(?:titles?|inventory)|titulos?\s+locales?|"
                r"titulos?\b.{0,40}\bbiblioteca|titles?\b.{0,40}\blibrary|"
                r"(?:steam|game)\s+(?:collection|library)|"
                r"(?:coleccion|biblioteca)\s+(?:local\s+)?(?:de\s+)?steam)\b",
            ),
            (
                "backup.list",
                r"\b(?:recovery\s+points?|puntos?\s+de\s+recuperacion|"
                r"recovery\s+copies|copias?\s+de\s+recuperacion|"
                r"restorable\s+copies|restore\s+(?:snapshots?|copies)|"
                r"recoverable\s+(?:snapshots?|backup\s+copies)|"
                r"instantaneas?\s+recuperables?|copias?\s+(?:locales\s+)?recuperables?|"
                r"respaldos?\b.{0,48}\b(?:volver\s+atras|roll\s+back)|"
                r"backups?\b.{0,48}\broll\s+back|respaldos?\s+privados?|"
                r"copias?\s+privadas?|private\s+copies|respaldos?|backups?)\b",
            ),
            (
                "routine.list",
                r"\b(?:rutinas?|routines?|automatic\s+sequences?|automatizaciones?|"
                r"habitual\s+workflows?|flujos?\s+habituales?|"
                r"automated\s+sequences?|secuencias?\s+automatizadas?|"
                r"secuencias?\s+habituales?|habitual\s+sequences?|personal\s+routines?|"
                r"sub\s*personal\s+(?:automations?|o\s+the\s+machines))\b",
            ),
            (
                "capture.screenshot",
                r"\bsnapshot\b|\bsnapchat\b.{0,48}\bhow\s+desktop\s+looks\b|"
                r"\bscreen\s+capture\b|\binstantanea\b.{0,48}"
                r"\b(?:escritorio|pantalla)\b|"
                r"\b(?:capture|captura)\b.{0,32}\b(?:screen|pantalla)\b|"
                r"\b(?:screen|desktop|monitor)\b.{0,52}"
                r"\b(?:image|picture|visual\s+state)\b|"
                r"\b(?:image|picture|imagen)\b.{0,64}"
                r"\b(?:screen|desktop|monitor|display|pantalla|escritorio)\b|"
                r"\b(?:conserva|preserve|registra|record)\b.{0,48}"
                r"\b(?:screen|desktop|monitor|pantalla|escritorio)\b|"
                r"\b(?:photograph|fotografia)\b.{0,40}"
                r"\b(?:screen|pantalla|monitor|desktop|escritorio)\b|"
                r"\b(?:screen|pantalla|monitor|desktop|escritorio)\b.{0,40}"
                r"\b(?:snapshot|photograph|fotografia)\b",
            ),
            (
                "vision.describe",
                r"\b(?:describe|explicame|explica|explain|interpreta|interpret)\b.{0,64}"
                r"\b(?:escena|scene|imagen|image|contenido|contents?|resulting|"
                r"what\s+it\s+contains|what\s+is\s+shown|what(?:'s|\s+is)\s+visible|"
                r"lo\s+que\s+contiene|que\s+muestra)\b|"
                r"\b(?:dime|tell\s+me)\b.{0,48}\b(?:que\s+aparece|what\s+appears)\b|"
                r"\b(?:objetos?|objects?)\b.{0,32}\b(?:aparecen?|appear)\b",
            ),
            (
                "ocr.read",
                r"\b(?:turn|convierte|conviertela|conviertelo|extract|extrae|"
                r"transcribe|reconoce|recognize)\b.{0,48}"
                r"\b(?:words?|palabras?|text|texto|lettering|letras|"
                r"writing|escritura)\b|"
                r"\b(?:read|lee)\s+(?:its|sus)\s+(?:text|lettering|letras)\b|"
                r"\b(?:run|ejecuta)\s+ocr\b|"
                r"\b(?:written|escrito|writing)\b.{0,40}\b(?:characters?|caracteres?)\b|"
                r"\b(?:texto|text)\s+(?:legible|readable)\b",
            ),
            ("office.document.create", r"\b(?:word|excel)\b"),
            (
                "package.install.prepare",
                r"\b(?:stage|alista|prepare|prepara|resolve|resuelve)\b.{0,40}"
                r"\b[a-z0-9][a-z0-9_+-]+\.[a-z0-9._+-]+"
                r"(?![a-z0-9._+-])|"
                r"\b[a-z0-9][a-z0-9_+-]+\.[a-z0-9._+-]+"
                r"(?![a-z0-9._+-]).{0,64}"
                r"\b(?:stage|staged|prepare|prepared|preparado|alista|install|"
                r"installation|instalar|instalarse|ready|listo)\b",
            ),
            ("streaming.play.named", r"\bnetflix\b"),
        )
        found_domains: list[tuple[int, str]] = []
        for operation, pattern in domain_patterns:
            found = _match(text, pattern)
            if found is not None:
                found_domains.append((found.start(), operation))
        found_domains = [
            item
            for item in found_domains
            if item[1] != "note.list" or _note_inventory_object(text)
        ]
        if any(
            operation == "filesystem.known.duplicates" for _, operation in found_domains
        ):
            found_domains = [
                item for item in found_domains if item[1] != "filesystem.known.search"
            ]
        installed_game_catalog = next(
            (
                index
                for index, (_, operation) in enumerate(found_domains)
                if operation == "game.catalog.list"
            ),
            None,
        )
        plural_installed_games = _has(
            text,
            r"\b(?:que|cuales|which|what)\s+(?:juegos?|games?|videojuegos?)\b|"
            r"\b(?:juegos|games|videojuegos)\b.{0,48}"
            r"\b(?:instalad[oa]s?|installed|biblioteca|library|catalogo|catalog)\b|"
            r"\b(?:instalad[oa]s?|installed)\b.{0,24}"
            r"\b(?:juegos|games|videojuegos)\b|"
            r"\b(?:game\s+catalog|catalogo\s+(?:local\s+)?de\s+juegos)\b",
        )
        if (
            installed_game_catalog is not None
            and _has(text, r"\b(?:instalad[oa]s?|installed)\b")
            and not plural_installed_games
        ):
            position, _ = found_domains[installed_game_catalog]
            installed_operation = (
                "app.installed"
                if _has(
                    text,
                    r"\bsteam\b.{0,40}\b(?:plataforma\s+de\s+juego|"
                    r"game|gaming\s+platform)\b",
                )
                else "game.installed.named"
            )
            found_domains[installed_game_catalog] = (
                position,
                installed_operation,
            )
        # A noun that is too broad on its own becomes unambiguous inside an
        # explicit catalog enumeration (``system, network, ...``).  Keep this
        # contextual instead of teaching the standalone resolver that a bare
        # ``machine`` or ``copies`` is always a live observation.
        if _has(text, r"[,;]"):
            enumerated_domain_patterns = (
                (
                    "system.status",
                    r"(?:^|[,;]\s*|\b(?:y|and)\s+)(?:sistema|system|maquina|machine|equipo|"
                    r"computador|computer|pc)(?=\s*(?:[,;]|\by\b|\band\b|$))",
                ),
                (
                    "network.status",
                    r"(?:^|[,;]\s*|\b(?:y|and)\s+)(?:red|network)"
                    r"(?=\s*(?:[,;]|\by\b|\band\b|$))",
                ),
                (
                    "input.keyboard.status",
                    r"(?:^|[,;]\s*|\b(?:y|and)\s+)(?:teclado|keyboard)"
                    r"(?=\s*(?:[,;]|\by\b|\band\b|$))",
                ),
                (
                    "backup.list",
                    r"(?:^|[,;]\s*|\b(?:y|and)\s+)(?:copias?|copies)"
                    r"(?=\s*(?:[,;]|\by\b|\band\b|$))",
                ),
                (
                    "email.latest.read",
                    r"^(?:read|lee)\s+(?:mail|correo|email)(?=\s*[,;])",
                ),
            )
            present_operations = {operation for _, operation in found_domains}
            for operation, pattern in enumerated_domain_patterns:
                if operation in present_operations:
                    continue
                found = _match(text, pattern)
                if found is not None:
                    found_domains.append((found.start(), operation))
                    present_operations.add(operation)
            leading_system = _match(
                text,
                r"^(?:report|reporta|show|muestra|consulta|inspect|revisa)\s+"
                r"(?:system|sistema|machine|maquina|equipo|computer|computador|pc)"
                r"(?=\s*[,;])",
            )
            if leading_system is not None and "system.status" not in present_operations:
                found_domains.append((leading_system.start(), "system.status"))
        named_installation = _match(
            text,
            r"(?:^|[,;]\s*|\b(?:y|and|then|luego|despues)\s+)"
            r"(?:comprueba|verifica|confirma|revisa|inspecciona|check|"
            r"verify|confirm|review|inspect)\s+"
            r"(?:(?:el|la|the)\s+)?"
            r"(?P<target>[a-z0-9][a-z0-9 ._+@-]{0,100}?)\s+"
            r"(?:installation|instalacion|instalad[oa]|installed)"
            r"(?=$|[,;]|\s+(?:y|and|then|luego|despues)\b)",
        )
        if named_installation is not None and not any(
            operation == "app.installed" for _, operation in found_domains
        ):
            found_domains.append((named_installation.start("target"), "app.installed"))
        installed_occurrence = (
            application_names.occurrence_pattern.search(text)
            if application_names.occurrence_pattern is not None
            else None
        )
        game_catalog_precedes_installed_app = (
            installed_occurrence is not None
            and any(
                operation == "game.catalog.list"
                and position < installed_occurrence.start()
                for position, operation in found_domains
            )
            and _has(
                text[: installed_occurrence.start()],
                r"\b(?:juegos?|games?|videojuegos?|playable\s+titles?)\b",
            )
        )
        if (
            installed_occurrence is not None
            and _has(
                text[installed_occurrence.start() :],
                r"^[a-z0-9 ._+-]{1,100}\binstallation\b",
            )
            and not game_catalog_precedes_installed_app
            and not any(operation == "app.installed" for _, operation in found_domains)
        ):
            found_domains.append((installed_occurrence.start(), "app.installed"))
        if (
            installed_occurrence is not None
            and any(operation == "app.installed" for _, operation in found_domains)
            and _has(
                installed_occurrence.group(0),
                r"\b(?:nota|notas|note|notes)\b",
            )
        ):
            found_domains = [item for item in found_domains if item[1] != "note.list"]
        if any(
            operation == "notification.list.due" for _, operation in found_domains
        ) and not _has(
            text,
            r"\b(?:tareas?|tasks?|to-dos?|to\s+dos|obligaciones?|obligations?|"
            r"unfinished\s+items?|open\s+items?|"
            r"(?:mis|los|las|my)\s+pendientes)\b",
        ):
            found_domains = [item for item in found_domains if item[1] != "task.list"]
        if any(
            operation == "notification.list.due" for _, operation in found_domains
        ) and not _has(text, r"\b(?:recordatorios?|reminders?)\b"):
            found_domains = [
                item for item in found_domains if item[1] != "reminder.list"
            ]
        if any(
            operation == "notification.list.due" for _, operation in found_domains
        ) and _has(
            text,
            r"\b(?:expired|overdue|due|vencid[oa]s?|fuera\s+de\s+plazo)\b",
        ):
            found_domains = [item for item in found_domains if item[1] != "note.list"]
        if (
            any(operation == "bluetooth.device.list" for _, operation in found_domains)
            and any(operation == "peripheral.list" for _, operation in found_domains)
            and not _has(
                text,
                r"\b(?:perifericos?|peripherals?)\b|"
                r"\b(?:accesorios?|accessories)\b.{0,32}"
                r"\b(?:conectad[oa]s?|attached|plugged|enchufad[oa]s?)\b|[,;]",
            )
        ):
            found_domains = [
                item for item in found_domains if item[1] != "peripheral.list"
            ]
        if any(
            operation == "reminder.list" for _, operation in found_domains
        ) and not _has(
            text,
            r"\b(?:tareas?|tasks?|to-dos?|to\s+dos|obligaciones?|obligations?|"
            r"unfinished\s+items?|open\s+items?|"
            r"(?:mis|los|las|my)\s+pendientes)\b|"
            r"(?:^|[,;]\s*|\b(?:y|and)\s+)pendientes"
            r"(?=\s*(?:(?:en\s+ese|in\s+that)\s+orden\s*)?"
            r"(?:[,;]|\by\b|\band\b|$))",
        ):
            found_domains = [item for item in found_domains if item[1] != "task.list"]
        if any(operation == "wifi.status" for _, operation in found_domains) and _has(
            text,
            r"\b(?:que|cuales|what|which)\s+redes\b|\bredes\s+(?:wifi\s+)?(?:hay|disponibles|cerca)\b|"
            r"\b(?:escanea|escanear|scan)\b|\bnetworks\s+(?:are\s+(?:there|available|nearby|around)|can\s+you\s+see)\b",
        ):
            # LIMITS1683 «qué redes wifi hay»: the networks around the PC are not
            # the state of its own Wi-Fi; that listing is a known limit.
            found_domains = [item for item in found_domains if item[1] != "wifi.status"]
        if any(
            operation == "wifi.status" for _, operation in found_domains
        ) and not _has(
            text,
            r"\b(?:la\s+red|the\s+network|overall\s+network|"
            r"network\s+access|"
            r"acceso\s+a\s+la\s+red|conectividad\s+general|"
            r"comunicacion\s+general|communication\s+condition)\b|"
            r"(?:^|[,;]\s*)(?:red|network)(?=\s*(?:[,;]|\by\b|\band\b|$))",
        ):
            found_domains = [
                item for item in found_domains if item[1] != "network.status"
            ]
        if any(
            operation == "input.keyboard.status" for _, operation in found_domains
        ) and not _has(
            text,
            r"\b(?:estado|status|salud|health|whole|overall|"
            r"condicion\s+(?:general|conjunta))\b.{0,48}\b(?:sistema|system)\b|"
            r"(?:^|[,;]\s*)(?:sistema|system)(?=\s*(?:[,;]|\by\b|\band\b|$))|"
            r"^(?:consulta|consult|show|muestra|report|reporta|inspect|revisa)\s+"
            r"(?:sistema|system)(?=\s*[,;])",
        ):
            found_domains = [
                item for item in found_domains if item[1] != "system.status"
            ]
        if any(operation == "audio.status" for _, operation in found_domains) and _has(
            text,
            r"\b(?:a la mitad|to half|bajito|bajalo|subelo)\b",
        ):
            found_domains = [
                (start, "audio.volume")
                if operation == "audio.status"
                else (start, operation)
                for start, operation in found_domains
            ]
        found_operation_set = frozenset(operation for _, operation in found_domains)
        unresolved_mail_collection = (
            request_observation
            and bool(found_domains)
            and "email.latest.read" not in found_operation_set
            and _has(
                text,
                r"\b(?:correos|emails|mails|mensajes\s+del\s+buzon|"
                r"mailbox\s+messages|inbox\s+messages)\b",
            )
        )
        if unresolved_mail_collection:
            return None
        action_signatures = {
            "capture.screenshot": (
                r"\b(?:conserva|preserve|registra|record|guarda|save|captura|"
                r"capture|toma|take|photograph|fotografia|retrata|deja|dejame|leave|"
                r"sabe(?=\s+en\s+imagen))\b"
            ),
            "vision.describe": (
                r"\b(?:describe|explica|explicame|explain|interpreta|interpret|"
                r"dime|tell|contarme|cuentame)\b"
            ),
            "ocr.read": (
                r"\b(?:extract|extrae|transcribe|reconoce|recognize|lee|read|"
                r"ocr|turn|convert|pasa|pasame|pull\s+out|saca|sacar|"
                r"convierte|conviertelo|conviertela|entregame)\b"
            ),
            "office.document.create": (
                r"\b(?:build|construct|make|create|crea|construye|arma|armame|"
                r"put\s+together|necesito)\b"
                r".{0,80}\b(?:word|excel)\b.{0,96}"
                r"\b(?:named|called|calle\s+de|llamad[oa]|denominad[oa]|se\s+llame|"
                r"titulad[oa]|titled)\b"
            ),
            "package.install.prepare": (
                r"\b(?:stage|staged|prepare|prepared|alista|preparad[oa]|deja|"
                r"leave|resolve|resuelve)\b.{0,120}"
                r"\b(?:install|installation|instalar|instalacion|ready|list[oa]|"
                r"[a-z0-9][a-z0-9_+-]+\.[a-z0-9._+-]+)\b|"
                r"\b[a-z0-9][a-z0-9_+-]+(?:\.[a-z0-9_+-]+)+"
                r"(?![a-z0-9._+-]).{0,80}"
                r"\b(?:stage|staged|prepare|prepared|preparado|alista|"
                r"install|installation|instalar|instalarse|ready|list[oa])\b"
            ),
            "streaming.play.named": (
                r"\b(?:pon|put|play|start|reproduce|ver|watch|find|encuentra|encuentras)\b"
                r".{0,120}\bnetflix\b|\bnetflix\b.{0,120}"
                r"\b(?:pon|put|play|start|reproduce|ver|watch)\b"
            ),
        }
        action_contracts_grounded = all(
            operation not in action_signatures
            or _has(text, action_signatures[operation])
            for operation in found_operation_set
        )
        explicit_coordination = _has(
            text,
            r"\b(?:y|e|and|despues|then|tambien|finally|por\s+ultimo)\b|"
            r"\b(?:junto\s+con|along\s+with)\b|[,;]",
        )
        action_operations = frozenset(action_signatures)
        starts_with_non_observation_action = _has(
            text,
            r"^(?:abre|open|launch|start|crea|crear|create|add|anade|agrega|"
            r"guarda|save|escribe|write|lee|read|pon|put|set|cambia|change)\b",
        ) and not (
            bool(found_operation_set & action_operations)
            or (
                bool({"email.latest.read", "clipboard.read.text"} & found_operation_set)
                and _has(text, r"^(?:abre|open|lee|read)\b")
                and not {"note.list", "app.installed", "game.catalog.list"}
                & found_operation_set
            )
        )
        semantic_domain_conflict = (
            (
                "system.status" in found_operation_set
                and (
                    _is_past_or_hypothetical_state(text)
                    or (
                        _is_machine_knowledge_or_diagnosis(text)
                        and not (
                            len(found_operation_set) >= 3
                            and _has(
                                text,
                                r"\b(?:configuracion\s+de\s+(?:sonido|audio)|"
                                r"sound\s+configuration)\b",
                            )
                        )
                    )
                )
            )
            or (
                "media.status" in found_operation_set
                and _has(
                    text,
                    r"\b(?:en|inside)\s+(?:mi|my)\s+"
                    r"(?:cabeza|mente|head|mind)\b",
                )
            )
            or _has(
                text,
                r"\b(?:equipo\s+(?:de\s+)?(?:futbol|medico|editorial)|"
                r"sistema\s+(?:solar|educativo|de\s+ecuaciones)|"
                r"red\s+(?:neuronal|ferroviaria|de\s+transporte)|"
                r"neural\s+network|rail(?:way)?\s+network|transport\s+network|"
                r"window\s+of\s+opportunity|ventana\s+(?:de\s+oportunidad|temporal)|"
                r"audio\s+device|dispositivo\s+de\s+audio|"
                r"volumen\s+de\s+(?:la\s+)?(?:enciclopedia|revista|libro)|"
                r"(?:from|on)\s+(?:my|the|another)\s+(?:phone|computer|device)|"
                r"en\s+(?:mi|el|otro)\s+(?:telefono|computador|equipo)|"
                r"another\s+(?:computer|device)|"
                r"(?:wi[\s-]?fi|wireless)\s+profiles?|perfiles?\s+wi[\s-]?fi|"
                r"procesos?\s+(?:activos?\s+)?del?\s+sistema|active\s+processes?|"
                r"(?:la\s+red|the\s+net)\s+(?:acerca|about)\b)",
            )
        )
        literal_read_conflict = _has(
            text,
            r"^(?:lee|read)\s+(?:(?:la|the)\s+)?(?:frase|words?)\b",
        )
        weak_single_domain = (
            len(found_domains) == 1
            and found_domains[0][1] == "backup.list"
            and not _has(
                text,
                r"\b(?:privad[oa]s?|private|local(?:es|ly)?|recoverable|"
                r"recuperables?|restore|recovery|restaurables?)\b",
            )
        )
        deferred_read_exempt = (
            "app.installed" in found_operation_set
            and _has(text, r"\b(?:si|if|whether)\b")
        ) or (
            found_operation_set == {"reminder.list"}
            and request_observation
            and _has(
                text,
                r"\b(?:recordar|remember|scheduled|programad[oa]s?|future|"
                r"futuros?|later|despues)\b",
            )
        )
        bounded_calendar_read = (
            request_observation
            and "calendar.event.list" in found_operation_set
            and not bool(found_operation_set & action_operations)
        )
        deferred_conflict = deferred_effect and not (
            deferred_read_exempt
            or bounded_calendar_read
            or (
                found_operation_set == {"streaming.play.named"}
                and _has(text, r"\bnetflix\b")
            )
        )
        generic_surface_safe = not (
            starts_with_non_observation_action
            or semantic_domain_conflict
            or literal_read_conflict
            or weak_single_domain
            or deferred_conflict
        )
        shared_minimum = _coordinated_effect_domain_minimum(text)
        shared_surface_complete = (
            shared_minimum is None or len(found_domains) >= shared_minimum
        )
        allowed_two_domain_compositions = {
            frozenset(("system.status", "network.status")),
            frozenset(("task.list", "reminder.list")),
            frozenset(("note.list", "clipboard.read.text")),
            frozenset(("bluetooth.device.list", "peripheral.list")),
            frozenset(("browser.tabs.list", "window.active")),
            frozenset(("email.latest.read", "calendar.event.list")),
            frozenset(("audio.status", "media.status")),
            frozenset(("wifi.status", "network.status")),
            frozenset(("web.search", "filesystem.known.search")),
            frozenset(("app.installed", "game.catalog.list")),
            frozenset(("system.status", "audio.status")),
            frozenset(("calendar.event.list", "task.list")),
            frozenset(("reminder.list", "notification.list.due")),
            frozenset(("app.installed", "peripheral.list")),
            frozenset(("browser.tabs.list", "clipboard.read.text")),
            frozenset(("game.catalog.list", "media.status")),
            frozenset(("bluetooth.device.list", "audio.status")),
            frozenset(("window.active", "input.keyboard.status")),
            frozenset(("email.latest.read", "task.list")),
            frozenset(("backup.list", "note.list")),
            frozenset(("routine.list", "reminder.list")),
            frozenset(("capture.screenshot", "clipboard.read.text")),
            frozenset(("package.install.prepare", "app.installed")),
            frozenset(("streaming.play.named", "audio.status")),
            frozenset(("wifi.status", "bluetooth.device.list")),
            frozenset(("office.document.create", "calendar.event.list")),
            frozenset(("capture.screenshot", "vision.describe")),
            frozenset(("capture.screenshot", "ocr.read")),
        }
        if (
            2 <= len(found_domains) <= 8
            and explicit_coordination
            and action_contracts_grounded
            and generic_surface_safe
            and shared_surface_complete
            and (
                len(found_domains) >= 3
                or found_operation_set in allowed_two_domain_compositions
            )
            and (request_observation or bool(found_operation_set & action_operations))
        ):
            ordered_operations = tuple(
                operation for _, operation in sorted(found_domains)
            )
            resolved = intent(*ordered_operations)
            if resolved is not None:
                return resolved
        if (
            len(found_domains) == 1
            and action_contracts_grounded
            and generic_surface_safe
            and (request_observation or found_domains[0][1] in action_operations)
        ):
            resolved = intent(found_domains[0][1])
            if resolved is not None:
                return resolved
        if len(found_domains) >= 2:
            return None

    if (
        bounded_status_question
        and _system_status_domain(text)
        and _machine_status_scopes_are_one_reading(text)
        and _machine_status_is_the_whole_clause(text)
    ):
        resolved = intent("system.status")
        if resolved is not None:
            return resolved

    if (
        request_observation
        and _has(
            text,
            r"\b(?:calendario|calendar|eventos?|events?|reuniones?|meetings?|"
            r"citas?|appointments?|agenda|actividades?\s+calendarizadas?|"
            r"scheduled\s+activities|compromisos?|commitments?)\b",
        )
        and _has(
            text,
            rf"{_BOUNDED_TEMPORAL_SELECTOR}|\b(?:esta\s+jornada|this\s+day)\b",
        )
    ):
        resolved = intent("calendar.event.list")
        if resolved is not None:
            return resolved

    if (
        request_observation
        and _has(text, r"\bbluetooth\b")
        and _has(
            text,
            r"\b(?:dispositivos?|devices?|equipos?|accesorios?|hardware|"
            r"detectad[oa]s?|detected|visibles?|visible|cercan[oa]s?|nearby|"
            r"reconoce|recognize|hallad[oa]s?|found)\b",
        )
        and not _has(
            text,
            r"\b(?:notas?|notes?|tareas?|tasks?|recordatorios?|reminders?)\b",
        )
    ):
        resolved = intent("bluetooth.device.list")
        if resolved is not None:
            return resolved

    if (
        request_observation
        and (
            _has(text, r"\b(?:pestanas?|tabs?)\b")
            or _has(
                text,
                r"\b(?:sitios?|sites?)\b.{0,40}\b(?:abiert[oa]s?|open)\b",
            )
            or _has(
                text,
                r"\b(?:paginas?|pages?)\s+(?:abiertas?|open)\b.{0,32}"
                r"\b(?:navegador|browser)\b",
            )
            or (
                _has(text, r"\b(?:navegador|browser)\b")
                and _has(text, r"\b(?:paginas?|pages?)\b")
                and _has(
                    text,
                    r"\b(?:abiertas?|open|actuales?|current|coleccion|collection)\b",
                )
            )
        )
        and _has(
            text,
            r"\b(?:navegador|browser|abiertas?|open|actuales?|current|"
            r"pestanas?|tabs?|sitios?|sites?)\b",
        )
    ):
        resolved = intent("browser.tabs.list")
        if resolved is not None:
            return resolved

    # A capture followed by OCR or visual description is one explicit
    # two-effect contract.  Detect it before the standalone screenshot branch.
    capture_domain = _has(
        text,
        r"\b(?:captura\s+de\s+pantalla|screenshot|screen\s+capture|pantallazo|"
        r"pantalla|screen|escritorio|desktop|monitor|display)\b",
    ) or (
        _has(text, r"\b(?:captura|capture)\b")
        and _has(
            text,
            r"\b(?:ocr|visible|aparece|appears|describe|ves|see)\b",
        )
    )
    capture_action = _has(
        text,
        r"^(?:haz|hacer|toma|tomar|take|captura|capture|retrata|genera|generate|"
        r"crea|crear|fotografia|fotografiar|photograph|snapshot|saca|grab|"
        r"create|guarda|save)\b",
    )
    if capture_domain and capture_action and not deferred_effect:
        if not _has(
            text,
            r"\b(?:nota|note|tarea|task|portapapeles|clipboard|pagina|page)\b",
        ) and _has(
            text,
            r"\b(?:ocr|lee|leer|leela|leelo|leerla|leerlo|read|"
            r"extrae|extraer|extract|transcribe|transcribir|reconoce|"
            r"recognize|convierte|conviertel[oa]|convert|turn|pasa|pasame|"
            r"pull\s+out|saca|sacar|entregame)\b"
            r".{0,80}\b(?:texto|text|ocr|visible|aparece|palabras?|words?|"
            r"writing|letras|lettering|caracteres?|characters?|readable|legible)\b|"
            r"\b(?:lee|read)\s+(?:sus|its)\s+(?:letras|lettering|text)\b|"
            r"\b(?:run|ejecuta)\s+ocr\b|"
            r"\b(?:leela|leelo|leerla|leerlo|read\s+it)\s+"
            r"(?:con|with)\s+ocr\b",
        ):
            resolved = intent("capture.screenshot", "ocr.read")
            if resolved is not None:
                return resolved
        if not _has(
            text,
            r"\b(?:nota|note|tarea|task|portapapeles|clipboard|pagina|page)\b",
        ) and _has(
            text,
            r"\b(?:describ\w*|decime|dime|contame|cuentame|tell\s+me)\s+"
            r"(?:lo\s+que\s+ves|que\s+ves|what\s+you\s+see|que\s+dice|what\s+it\s+says|"
            r"que\s+hay(?:\s+en\s+(?:la\s+)?pantal\w*)?|what\s+is\s+on\s+(?:the\s+)?screen)\b|"
            # SCREEN1807: «ve qué hay en pantalla», «para ver la pantalla»,
            # «identificá el botón» after a capture are the screen text read.
            r"\b(?:ve|mira|fijate|chequea|revisa|see|check|look)\s+(?:que|lo\s+que|what)\s+(?:hay|there\s+is)\b|"
            r"\b(?:para|to)\s+(?:ver|see)\s+(?:la\s+|the\s+)?(?:pantalla|screen)\b|"
            r"\b(?:identifica\w*|identify|ubica|localiza|find)\s+(?:el\s+|los\s+|the\s+)?(?:boton\w*|button\w*)\b",
        ) and not _has(
            text,
            r"\b(?:pantalla|screen)\s+(?:del|de mi|of my)\s+"
            r"(?:telefono|celular|movil|phone|smartphone|tablet|auto|car)\b",
        ):
            # SCREEN1485 «Toma un screenshot de la pantalla ahora mismo y
            # describeme lo que ves»: without a vision provider the truthful
            # description of the screen is its recognized text (SCREEN1417).
            resolved = intent("capture.screenshot", "ocr.read")
            if resolved is not None:
                return resolved
        if not _has(
            text,
            r"\b(?:nota|note|tarea|task|portapapeles|clipboard|pagina|page)\b",
        ) and _has(
            text,
            r"\b(?:describe|describir|interpreta|interpretar|interpret|"
            r"explica|explain|dime\s+que|tell\s+me\s+what|cuentame\s+que|"
            r"contarme\s+que)\b"
            r".{0,100}\b(?:ves|see|aparece|appears|visible|it|pantalla|screen|"
            r"escena|scene|shown|muestra|imagen|image|ella|representa|depicts|"
            r"contenido|contents?|objetos?|objects?)\b|"
            r"\b(?:objetos?|objects?)\b.{0,40}\b(?:aparecen?|appear)\b",
        ):
            resolved = intent("capture.screenshot", "vision.describe")
            if resolved is not None:
                return resolved
        if (
            not _has(
                text,
                r"^(?:crea|crear|create|make|build)\s+(?:(?:un|una|a|an)\s+)?"
                r"(?:nota|note|tarea|task|documento|document)\b",
            )
            and _has(
                text,
                r"\b(?:captura|screenshot|capture|pantallazo|grab|snapshot|"
                r"foto\s+digital|digital\s+(?:snapshot|photo)|imagen|image|"
                r"fotografia|photograph|instantanea|instant\s+picture)\b",
            )
            and _has(
                text,
                r"\b(?:pantalla|screen|escritorio|desktop|screenshot|monitor|display)\b",
            )
        ):
            resolved = intent("capture.screenshot")
            if resolved is not None:
                return resolved

    # An installed-app observation may name a catalog entry or ask for a
    # verified absence.  The latter is safe because the provider only reads
    # the Start inventory and reports whether the literal was found.
    installed_inventory_query = (
        _has(text, r"\b(?:instalad[oa]s?|installed)\b")
        and _has(
            text,
            r"\b(?:si|if|whether|comprueba|averigua|check|find\s+out|confirma|"
            r"verify|verifica|see|inspect|present|disponible|available)\b",
        )
    ) or _has(
        text,
        r"\b(?:start\s+(?:app|application)\s+inventory|"
        r"inventario\s+de\s+aplicaciones\s+(?:de\s+)?inicio|"
        r"software\s+local|local\s+software\s+inventory|"
        r"figura\s+en\s+(?:el\s+)?software|"
        r"(?:figura|aparece|exists|appears|listed)\s+(?:entre|en|among|in)\s+"
        r"(?:(?:las|the|installed)\s+)?(?:aplicaciones|apps|applications)\b|"
        r"menu\s+inicio|start\s+menu\s+apps?)\b",
    )
    generic_installed_inventory_query = request_observation and _has(
        text,
        r"\b(?:inventario\s+instalado|installed\s+apps?|"
        r"programas?\b.{0,64}\b(?:presencia|installed)|"
        r"(?:installed\s+apps?|programas?)\b.{0,64}\b(?:aparece|shows?\s+up)|"
        r"(?:whether|si)\b.{0,64}\b(?:instalad[oa]|installed))\b",
    )
    if generic_installed_inventory_query and not _has(
        text,
        r"\b(?:juego|game|steam|telefono|phone|tablet)\b",
    ):
        resolved = intent("app.installed", evidence=(text,))
        if resolved is not None:
            return resolved
    if installed_inventory_query and not _has(text, r"\b(?:juego|game)\b"):
        installed_name = resolve_application_installed_name(
            text,
            application_names,
        )
        if installed_name is not None:
            resolved = intent("app.installed", evidence=(text,))
            if resolved is not None:
                return resolved

    if (
        request_observation
        and _has(text, r"\b(?:audio|sonido|sound)\b")
        and _has(
            text,
            r"\b(?:estado|status|actual|current|present|configurad[oa]|configured|"
            r"configuracion|configuration|como|how|vigentes?|set|moment)\b",
        )
        and not _has(text, r"\b(?:microfono|microphone|app|aplicacion)\b|\d|%")
    ):
        resolved = intent("audio.status")
        if resolved is not None:
            return resolved

    if (
        request_observation
        and _has(
            text,
            r"\b(?:backup|backups|backup\s+snapshots?|respaldo|respaldos|"
            r"copias?\s+de\s+seguridad|copias?\s+privadas?|"
            r"puntos?\s+de\s+recuperacion|recovery\s+points?|"
            r"copias?\s+de\s+recuperacion|recovery\s+copies|"
            r"copias?\s+(?:locales\s+)?recuperables|"
            r"recoverable\s+(?:local\s+)?copies|restorable\s+copies)\b",
        )
        and _has(
            text,
            r"\b(?:lista|list|muestra|show|ensena|present|inventario|inventory|"
            r"snapshots?|disponibles?|available|privad[oa]s?|private|existen|"
            r"stored|guardad[oa]s?|kept|restorable|recuperables?|"
            r"roll\s+back|volver\s+atras|relacion)\b",
        )
        and not _has(text, r"\b(?:log|logs|registro|job|trabajo|work)\b")
    ):
        resolved = intent("backup.list")
        if resolved is not None:
            return resolved

    keyboard_state = (
        (
            _has(text, r"\b(?:teclado|keyboard|key\s+map|mapa\s+de\s+teclas)\b")
            and _has(
                text,
                r"\b(?:idioma|lenguaje|language|distribucion|layout|mapa|map)\b",
            )
            and _has(
                text,
                r"\b(?:actual|current|activ[oa]|active|seleccionad[oa]|selected|"
                r"estado|status|ahora|now|usa|usando|using|uso|use)\b",
            )
        )
        or (
            _has(text, r"\b(?:distribucion|layout)\b")
            and _has(text, r"\b(?:escribir|typing|input|entrada)\b")
            and _has(
                text,
                r"\b(?:actual|current|activ[oa]|active|ahora|now|usa|using|"
                r"estoy|i\s+am)\b",
            )
        )
        or (
            _has(text, r"\b(?:key\s+map|mapa\s+de\s+teclas|keyboard\s+map)\b")
            and _has(
                text,
                r"\b(?:estoy\s+escribiendo|i\s+am\s+typing|typing\s+with)\b",
            )
            and not _has(text, r"\b(?:manual|guide|guia|article|articulo)\b")
        )
    )
    if request_observation and keyboard_state:
        resolved = intent("input.keyboard.status")
        if resolved is not None:
            return resolved

    media_state = (
        _has(text, r"\b(?:que|what)\b.{0,40}\b(?:reproduciendo|playing)\b")
        or _has(text, r"\b(?:what(?:'s|\s+is)\s+playing)\b")
        or (
            _has(text, r"\b(?:media|multimedia|sesion\s+multimedia|media\s+session)\b")
            and _has(
                text,
                r"\b(?:estado|status|actual|current|active|activa|playing|"
                r"reproduciendo|reproduce|reproduccion|actualmente|currently)\b",
            )
        )
        or _has(text, r"\b(?:pista|track|video)\b.{0,40}\b(?:suena|playing)\b")
        or _has(
            text,
            r"\b(?:contenido\s+multimedia|media\s+content)\b.{0,48}"
            r"\b(?:corriendo|running|actual|current|now)\b",
        )
        or _has(
            text,
            r"\b(?:sesion\s+de\s+reproduccion|playback\s+session)\b",
        )
        or _has(
            text,
            r"\b(?:sesion|session)\b.{0,48}\b(?:sonando|playing|reproduciendo)\b",
        )
    )
    if (
        request_observation
        and media_state
        and not _has(text, r"\b(?:netflix|youtube|spotify|cabeza|mente|head|mind)\b")
    ):
        resolved = intent("media.status")
        if resolved is not None:
            return resolved

    private_memory = _has(
        text,
        r"\b(?:memoria|memory|recuerdos?)\b.{0,40}"
        r"\b(?:local|locales|baxy|asistente|assistant)\b|"
        r"\b(?:baxy|asistente|assistant|local|tus)\b.{0,40}"
        r"\b(?:memoria|memory|recuerdos?)\b",
    )
    if (
        request_observation
        and private_memory
        and _has(text, r"\b(?:estado|status|habilitad[oa]|enabled|como|how|local)\b")
        and not _has(text, r"\b(?:ram|uso|usage|libre|free|sistema|system)\b")
    ):
        resolved = intent("memory.status")
        if resolved is not None:
            return resolved

    if (
        request_observation
        and _has(
            text,
            r"\b(?:la\s+red|the\s+network|network|red|conectividad|connectivity)\b|"
            r"\b(?:conexion|connection|conectividad|connectivity)\b.{0,40}"
            r"\b(?:general|overall|equipo|computer|pc)\b|"
            r"\b(?:acceso|access)\b.{0,32}\b(?:red|network)\b",
        )
        and _has(
            text,
            r"\b(?:estado|state|status|condicion|condition|conectad[oa]|connected|"
            r"health|general|overall|conexion|connection|conectividad|connectivity|"
            r"funciona|funcionando|works?|working|anda|doing|acceso|access|"
            r"llegando|reaching)\b",
        )
        and not _has(
            text,
            r"\b(?:wi[\s-]?fi|inalambric[oa]|wireless)\b|"
            r"\b(?:neural|neuronal|social|ferroviari[oa]|rail|"
            r"transport|electrica?|electric)\b",
        )
    ):
        resolved = intent("network.status")
        if resolved is not None:
            return resolved

    if (
        request_observation
        and _has(text, r"\b(?:wi[\s-]?fi|inalambric[oa]|wireless)\b")
        and _has(
            text,
            r"\b(?:estado|state|status|actual|current|conectad[oa]|connected|health|"
            r"conexion|connection|conectividad|connectivity|enlace|link|activa|active|"
            r"condicion|condition|senal|signal|anda|doing|asociad[oa]|associated)\b",
        )
    ):
        resolved = intent("wifi.status")
        if resolved is not None:
            return resolved

    if (
        request_observation
        and not _has(text, r"\b(?:recordatorios?|reminders?)\b")
        and _has(
            text,
            r"\b(?:notificaciones?|notifications?|avisos?|alertas?|alerts?|notices?)\b",
        )
        and _has(
            text,
            r"\b(?:vencid[oa]s?|overdue|expired|due|pendientes?|pending|pasaron\s+su\s+hora|"
            r"not\s+been\s+dismissed|superaron\s+su\s+hora|gone\s+past\s+their\s+time|"
            r"plazo\s+se\s+cumplio|deadline\s+has\s+elapsed)\b",
        )
    ):
        resolved = intent("notification.list.due")
        if resolved is not None:
            return resolved

    latest_mail = _has(
        text,
        r"\b(?:ultimo|ultima|last|latest|newest|mas\s+nuevo|mas\s+nueva|"
        r"most\s+recent|recent|mas\s+recientemente)\b|"
        r"\b(?:acaba\s+de\s+llegar|just\s+arrived|recien\s+recibido|"
        r"just\s+received)\b|"
        r"\b(?:llego|arrived)\b.{0,32}\b(?:ultimo|last|recently)\b",
    )
    mail_domain = _has(
        text,
        r"\b(?:correo|email|mail|mailbox|buzon|inbox|inbox\s+message|"
        r"bandeja\s+de\s+entrada)\b",
    )
    if (
        request_observation
        and latest_mail
        and mail_domain
        and not _has(
            text,
            r"\b(?:telefono|phone|smartphone|tablet|reloj|watch)\b",
        )
        and _has(
            text,
            r"\b(?:mensaje|message|item|mailbox|buzon|inbox|arrived|llego|llegar)\b|"
            r"\b(?:mi|my)\b.{0,32}\b(?:correo|email|mail)\b",
        )
    ):
        resolved = intent("email.latest.read")
        if resolved is not None:
            return resolved

    if (
        request_observation
        and _has(
            text,
            r"\b(?:perifericos?|peripherals?|hardware\s+periferico|peripheral\s+hardware|"
            r"usb\s+hardware|"
            r"dispositivos?\s+usb|usb\s+devices?|accesorios?\s+usb|usb\s+accessories|"
            r"dispositivos?\s+externos?|external\s+devices?|"
            r"accesorios?\s+enchufados?|plugged-in\s+accessories|"
            r"accesorios?\b.{0,56}\b(?:reconoce|enchufad[oa]s?|conectad[oa]s?)|"
            r"accessories\b.{0,64}\b(?:recognizes?|attached|plugged|connected))\b|"
            rf"{_CONNECTED_INVENTORY}",
        )
        and _has(
            text,
            r"\b(?:lista|list|muestra|show|enumera|enumerate|revisa|inspect|"
            r"conectad[oa]s?|connected|enchufad[oa]s?|plugged|attached)\b",
        )
        and not _has(
            text,
            r"\b(?:telefono|phone|smartphone|tablet|router|auto|car)\b",
        )
    ):
        resolved = intent("peripheral.list")
        if resolved is not None:
            return resolved

    if _bare_note_inventory_request(text):
        resolved = intent("note.list")
        if resolved is not None:
            return resolved

    if (
        request_observation
        and _note_inventory_object(text)
        and _has(
            text,
            r"\b(?:lista|list|enumera|enumerate|muestra|show|display|revisa|inspect|"
            r"inventario|inventory|indice|index|guardad[oa]s?|saved|stored|"
            r"conservo|keep|local(?:es|ly)?|privad[oa]s?|private)\b",
        )
        and not _has(text, r"\b(?:tareas?|tasks?|recordatorios?|reminders?)\b")
    ):
        resolved = intent("note.list")
        if resolved is not None:
            return resolved

    if (
        request_observation
        and _has(
            text,
            r"\b(?:recordatorios?|reminders?)\b|"
            r"\b(?:cosas?|things?)\b.{0,64}\b(?:recordar|remember|"
            r"bring\s+back\s+to\s+mind)\b|"
            r"\blo\s+que\b.{0,64}\bagendad[oa]\b.{0,32}\brecordar\b|"
            r"\b(?:todo\s+lo\s+que|everything)\b.{0,64}"
            r"\b(?:debo\s+recordar|due\s+to\s+remember|remember\s+later)\b|"
            r"\b(?:avisos?|notices?)\b.{0,32}\b(?:programad[oa]s?|scheduled)\b",
        )
        and _has(
            text,
            r"\b(?:lista|list|enumera|enumerate|muestra|show|display|revisa|inspect|"
            r"inventario|inventory|agendad[oa]s?|scheduled|pendientes?|pending|"
            r"outstanding|programad[oa]s?|things?|cosas?|later|adelante)\b",
        )
    ):
        resolved = intent("reminder.list")
        if resolved is not None:
            return resolved

    if (
        request_observation
        and _has(
            text,
            r"\b(?:rutinas?|routines?|automations?|"
            r"automatizaciones?(?:\s+(?:rutinarias?|habituales?))?|"
            r"habitual\s+automations?|secuencias?\s+automaticas?|automatic\s+sequences?)\b",
        )
        and _has(
            text,
            r"\b(?:lista|list|enumera|enumerate|muestra|show|display|revisa|inspect|"
            r"inventario|inventory|guardad[oa]s?|saved|stored|disponibles?|available|"
            r"configurad[oa]s?|configured|habituales?|habitual)\b",
        )
        and not _has(text, r"\b(?:articulo|article|sitio|website|manual|guide)\b")
    ):
        resolved = intent("routine.list")
        if resolved is not None:
            return resolved

    if (
        request_observation
        and _has(
            text,
            r"\b(?:tareas?|tasks?|to-dos?|to\s+dos|asuntos?|items?)\b",
        )
        and _has(
            text,
            r"\b(?:lista|list|enumera|enumerate|muestra|show|display|revisa|inspect|"
            r"inventario|inventory|abiertas?|open|pendientes?|pending|not\s+closed|"
            r"sin\s+cerrar|sin\s+completar|unfinished|incomplet[oa]s?|"
            r"siguen\s+abiertos?|still\s+open|remain\s+unfinished)\b",
        )
        and not _has(text, r"\b(?:notas?|notes?|recordatorios?|reminders?)\b")
    ):
        resolved = intent("task.list")
        if resolved is not None:
            return resolved

    if request_observation and _has(
        text,
        r"\b(?:pendientes?|to-dos?|to\s+dos)\b.{0,48}"
        r"\b(?:permanecen\s+abiertos?|remain\s+open|still\s+open)\b",
    ):
        resolved = intent("task.list")
        if resolved is not None:
            return resolved

    if (
        request_observation
        and _has(
            text,
            r"\b(?:inventario|inventory)\s+(?:de|of)\s+"
            r"(?:pendientes?|open\s+(?:to-dos?|to\s+dos))\b",
        )
        and _has(text, r"\b(?:abiertos?|open|pendientes?|pending)\b")
    ):
        resolved = intent("task.list")
        if resolved is not None:
            return resolved

    if request_observation and _has(
        text,
        r"\b(?:todo\s+lo\s+que\s+tengo|everything\s+i\s+have)\b.{0,32}"
        r"\b(?:pendiente|pending|open)\b",
    ):
        resolved = intent("task.list")
        if resolved is not None:
            return resolved

    if (
        request_observation
        and (
            _has(text, r"\b(?:portapapeles|clipboard)\b")
            or _has(
                text,
                r"\b(?:texto|text|textual)\b.{0,40}\b(?:copiad[oa]|copied)\b",
            )
            or _has(
                text, r"\b(?:listo\s+para\s+pegar|ready\s+to\s+(?:be\s+)?paste[d]?)\b"
            )
        )
        and not _has(text, r"\b(?:copia|copy)\b.{0,40}\b(?:al|to)\b")
    ):
        resolved = intent("clipboard.read.text")
        if resolved is not None:
            return resolved

    if (
        request_observation
        and (
            _has(text, r"\bsteam\b")
            or _has(
                text,
                r"\b(?:juegos?|games?|videojuegos?)\b.{0,48}"
                r"\b(?:catalogo|catalog|disponibles?|available)\s*(?:local(?:mente|ly)?)?\b",
            )
        )
        and _has(
            text,
            r"\b(?:catalogo|catalog|juegos?|games?|videojuegos?|biblioteca|library|"
            r"titulos?|titles?|playable)\b",
        )
        and not _has(
            text,
            r"\b(?:tienda|store|capturas?|screenshots?|notas?|notes?|"
            r"tareas?|tasks?|recordatorios?|reminders?)\b",
        )
        and (
            not _has(text, r"\b(?:instalad[oa]s?|installed)\b")
            or _has(
                text,
                r"\b(?:que|cuales|which|what)\s+(?:juegos?|games?)\b|"
                r"\b(?:juegos?|games?)\b.{0,24}\b(?:instalad[oa]s?|installed)\b",
            )
        )
    ):
        resolved = intent("game.catalog.list")
        if resolved is not None:
            return resolved

    if (
        (
            request_observation
            or _has(
                text,
                r"^(?:busca|buscar|encuentra|find|search|localiza|locate|"
                r"hay|there\s+are)\b",
            )
        )
        and _has(
            text,
            r"\b(?:archivos?|files?|documentos?|documents?|descargas|downloads?)\b",
        )
        and _has(text, _DUPLICATE_FILES)
        and not _has(text, r"\b(?:web|internet|online|google|bing)\b")
    ):
        resolved = intent("filesystem.known.duplicates")
        if resolved is not None:
            return resolved

    if (
        _has(
            text,
            r"^(?:busca|buscar|encuentra|find|search|localiza|locate|"
            r"a\s+ver\s+si\s+(?:encuentras?|find)|track\s+down|"
            r"revisa\s+(?:documentos|descargas)|look\s+through|scan|explore|"
            r"rastrea|explora)\b",
        )
        and _has(
            text,
            r"\b(?:documentos?|documents?|descargas|downloads?|escritorio|desktop|"
            r"imagenes|pictures)\b",
        )
        and not _has(text, _DUPLICATE_FILES)
        and not _has(text, r"\b(?:web|internet|online|google|bing)\b")
    ):
        resolved = intent("filesystem.known.search")
        if resolved is not None:
            return resolved

    if (
        _has(
            text,
            r"^(?:busca|buscar|search|look\s+up|haz\s+una\s+busqueda)\b",
        )
        and _has(text, r"\b(?:web|internet|online)\b")
        and not _has(
            text,
            r"\b(?:archivo|file|carpeta|folder|notas?|notes?|tareas?|tasks?|"
            r"recordatorios?|reminders?)\b",
        )
    ):
        resolved = intent("web.search")
        if resolved is not None:
            return resolved

    if (
        request_observation
        and _has(
            text,
            r"^(?:consulta|consultar|consult|investiga|investigar|investigate|"
            r"research|look\s+on|averigua)\b",
        )
        and _has(
            text,
            r"\b(?:web|internet|online|google|bing|public\s+api)\b|"
            r"\b(?:la\s+red|the\s+net)\b\s+(?:acerca|about)\b",
        )
        and not _has(
            text,
            r"\b(?:archivo|file|carpeta|folder|documentos?|documents?|"
            r"descargas|downloads?|escritorio|desktop|notas?|notes?|tareas?|tasks?|"
            r"recordatorios?|reminders?)\b",
        )
    ):
        resolved = intent("web.search")
        if resolved is not None:
            return resolved

    if (
        request_observation
        and _has(
            text,
            r"\b(?:ventana|window|aplicacion|application|programa|program)\b",
        )
        and _has(
            text,
            r"\b(?:activa|active|primer\s+plano|foreground|actual|current|foco|focus|"
            r"focused|al\s+frente|in\s+front|delante|in\s+front\s+of|"
            r"recibe\s+el\s+teclado|recibiendo\s+mis\s+teclas|"
            r"receiving\s+(?:keyboard\s+focus|my\s+keystrokes|keyboard\s+input))\b",
        )
        and not _has(text, r"\b(?:oportunidad|opportunity|temporal|timeframe)\b")
    ):
        resolved = intent("window.active")
        if resolved is not None:
            return resolved

    if (
        request_observation
        and _has(
            text,
            r"\b(?:sistema|system|equipo|computer|computador|computadora|pc|"
            r"maquina|machine)\b",
        )
        and _has(
            text,
            r"\b(?:estado|state|status|condicion|condition|salud|health|resumen|"
            r"summary|como|how|anda|doing|overall|integral|conjunto|whole|"
            r"operating)\b",
        )
        and not _has(
            text,
            r"\b(?:comprar|buy|purchase|precio|price|might|would|podria|"
            r"otro|otra|another)\b",
        )
    ):
        resolved = intent("system.status")
        if resolved is not None:
            return resolved

    package_id = _spoken_package_id(text)
    if (
        package_id is not None
        and not deferred_effect
        and _has(
            text,
            r"\b(?:prepara|prepare|stage|resolve|resuelve|ubica|locate|deja|leave|"
            r"instalacion|installation|instalar|install|listo|ready|staged|tied|"
            r"alista(?:lo|la)?)\b",
        )
        and not _has(text, r"https?://|\b(?:juego|game|steam)\b")
    ):
        resolved = intent(
            "package.install.prepare",
            evidence=(package_id,),
        )
        if resolved is not None:
            return resolved

    office = re.search(
        r"^(?:crea|crear|create|construye|construir|construct|genera|generar|"
        r"generate|prepara|prepare|make|necesito|i\s+need|"
        r"build|produce|arma|armame|assemble)\s+"
        r"(?:(?:un|una|a|an)\s+)?"
        r"(?P<kind>documento\s+de\s+word|documento\s+word|archivo\s+word|"
        r"word(?:\s+(?:document|doc|file))?|planilla\s+excel|hoja\s+de\s+excel|"
        r"hoja\s+excel|archivo\s+excel|libro\s+excel|excel\s+(?:workbook|file|sheet))\s+"
        r"(?:llamad[oa]|denominad[oa]|named|called|titulad[oa]|titled|"
        r"con\s+el\s+nombre)\s+"
        r"(?P<title>.+)$",
        text,
        re.IGNORECASE,
    )
    if office is not None:
        resolved = intent("office.document.create")
        if resolved is not None:
            return resolved

    channel_conveyance = _has(
        text,
        r"^(?:(?:por|en|via)\s+(?:whatsapp|discord)\s+"
        r"(?:hazle\s+(?:llegar|saber)|cuentale|dile|avisa|notifica)\s+a\s+"
        r"[a-z0-9][a-z0-9 ._-]{0,80}?\s+"
        r"(?:que|el\s+mensaje|the\s+message)\s+\S.+|"
        r"(?:por|en|via)\s+(?:whatsapp|discord)\s+dile\s+a\s+"
        r"[a-z0-9._-]{1,80}\s+\S.+|"
        r"(?:through|on|via|por|en)\s+(?:whatsapp|discord)\s+"
        r"let\s+[a-z0-9][a-z0-9 ._-]{0,80}?\s+know\s+\S.+|"
        r"(?:through|on|via)\s+(?:whatsapp|discord)\s+"
        r"get\s+(?:the\s+)?(?:note|message|update)\s+\S.+\s+to\s+"
        r"[a-z0-9][a-z0-9 ._-]{0,80})$",
    )
    message_shape = (
        channel_conveyance
        or _has(
            text,
            r"^(?:(?:por|en|on|via|through)\s+(?:whatsapp|discord)\s*[,;:]?\s*"
            r"(?:manda|envia|send|avisa|notifica|notify)(?:le)?\s+(?:a\s+)?"
            r"[a-z0-9][a-z0-9 ._-]{0,80}?\s+"
            r"(?:el\s+|the\s+)?(?:texto|mensaje|message)\s+\S.+|"
            r"(?:manda|envia|send)(?:le)?\s+(?:a\s+)?[a-z0-9][a-z0-9 ._-]{0,80}?\s+"
            r"(?:(?:on|por|en)\s+(?:whatsapp|discord)\s+)?(?:el\s+|the\s+)?"
            r"(?:mensaje|message)\s+\S.+|"
            r"(?:dile|tell|mandale|enviale)\s+(?:a\s+)?"
            r"[a-z0-9][a-z0-9 ._-]{0,80}?\s+"
            r"(?:(?:on|por|en)\s+(?:whatsapp|discord)\s+)?(?:que|that)\s+\S.+|"
            r"(?:manda|envia|send)\s+(?:en|por|on|via)\s+(?:whatsapp|discord)\s+"
            r"(?:a\s+|to\s+)?[a-z0-9][a-z0-9 ._-]{0,80}?\s+(?:que|that)\s+\S.+|"
            r"message\s+[a-z0-9][a-z0-9 ._-]{0,80}?\s+"
            r"(?:on\s+)?(?:whatsapp|discord)\s+(?:that|saying)\s+\S.+|"
            r"(?:escribele|write\s+to)\s+(?:a\s+)?[a-z0-9][a-z0-9 ._-]{0,80}?\s+"
            r"(?:en|on)\s+(?:whatsapp|discord)\s+(?:que|that)\s+\S.+|"
            r"(?:pasa|pass)\s+(?:a\s+)?[a-z0-9][a-z0-9 ._-]{0,80}?\s+"
            r"(?:el\s+|the\s+)?(?:mensaje|message)\s+\S.+\s+"
            r"(?:por|through|via)\s+(?:whatsapp|discord)|"
            r"(?:escribele|escribe|pasa)\s+(?:en|por|via)\s+"
            r"(?:whatsapp|discord)\s+(?:a\s+)?[a-z0-9][a-z0-9 ._-]{0,80}?\s+"
            r"(?:que|el\s+texto|el\s+mensaje)\s+\S.+|"
            r"escribele\s+(?:en|por|on|via)\s+(?:whatsapp|discord)\s+a\s+"
            r"[a-z0-9][a-z0-9 ._-]{0,80}?\s*[,;:.!?]+\s*\S.+|"
            r"write\s+to\s+[a-z0-9][a-z0-9 ._-]{0,80}?\s+on\s+"
            r"(?:whatsapp|discord)\s*[,;:.!?]+\s*\S.+|"
            r"(?:que\s+)?discord\s+(?:le\s+)?(?:avise|notify)\s+a?\s*"
            r"[a-z0-9][a-z0-9 ._-]{0,80}?\s+(?:que|that)\s+\S.+|"
            r"(?:have|ave|ab)\s+discord\s+(?:notify|avise)\s+(?:a\s+)?"
            r"[a-z0-9][a-z0-9 ._-]{0,80}?\s+(?:that|que)\s+\S.+|"
            r"escribe\s+a\s+[a-z0-9][a-z0-9 ._-]{0,80}?\s+via\s+"
            r"(?:whatsapp|discord)\s+que\s+\S.+)$",
        )
        and _has(text, r"\b(?:whatsapp|discord)\b")
        and not _has(
            text,
            r"^(?:manda|envia|send|dile|tell)\s+(?:a\s+)?"
            r"(?:ellos|ellas|les|them)\b",
        )
    )
    if message_shape:
        resolved = intent("message.recipient.resolve", "message.send")
        if resolved is not None:
            return resolved

    netflix_weekday_title = _has(
        text,
        r"^(?:reproduce|play|pon|pone|put\s+on|busca|find|inicia|start|encuentra|encuentras|"
        r"localiza|locate)\s+wednesday\s+(?:en|in|on|desde|from|through|"
        r"usando|using)\s+netflix\b",
    )
    if (
        (not deferred_effect or netflix_weekday_title)
        and _has(text, r"\bnetflix\b")
        and _has(
            text,
            r"^(?:reproduce|play|pon|pone|put\s+on|busca|find|inicia|start|encuentra|encuentras|"
            r"localiza|locate)\b",
        )
        and _has(
            text,
            r"\b(?:en|in|on|desde|from|through|usando|using)\s+netflix\b",
        )
    ):
        resolved = intent("streaming.play.named")
        if resolved is not None:
            return resolved

    return None


def _finalize_effect_matches(
    folded: str,
    matches: list[tuple[int, int, str]],
    available: frozenset[str],
) -> EffectIntent | None:
    dominant_local_operations = {
        "note.create",
        "note.list",
        "note.read",
        "note.search",
        "task.create",
        "task.list",
        "task.search",
        "reminder.create",
        "reminder.list",
        "routine.list",
    }
    if any(entry[2] == "input.text.type" for entry in matches):
        matches = [entry for entry in matches if entry[2] == "input.text.type"]
    elif any(entry[2] in dominant_local_operations for entry in matches):
        matches = [entry for entry in matches if entry[2] in dominant_local_operations]
    # Navigation/play operations already open their named application.  An
    # explicit preceding "open" is a setup phrase, not a second observable
    # effect, unless no richer operation was recognized.
    operation_names = {entry[2] for entry in matches}
    if "app.open" in operation_names:
        filtered: list[tuple[int, int, str]] = []
        for entry in matches:
            if entry[2] != "app.open":
                filtered.append(entry)
                continue
            application = _match(
                folded[entry[0] :],
                rf"^\b{_OPEN}\b(?:\s+(?:el|la|the))?\s+(?P<app>{_KNOWN_APPLICATION})\b",
            )
            app_name = application.group("app") if application is not None else ""
            is_browser = _has(
                app_name,
                r"\b(?:opera|chrome|google chrome|edge|microsoft edge|firefox)\b",
            )
            is_spotify = app_name == "spotify"
            consumed_by_richer_effect = (
                is_browser and "browser.navigate.named" in operation_names
            ) or (
                is_spotify
                and (
                    "media.play.exact" in operation_names
                    or "media.play.query" in operation_names
                )
            )
            if not consumed_by_richer_effect:
                filtered.append(entry)
        matches = filtered

    matches.sort(key=lambda entry: (entry[0], entry[1]))
    retained = [entry for entry in matches if entry[2] in available]
    if not retained or len(retained) > 8:
        return None
    operations = tuple(entry[2] for entry in retained)
    evidence: list[str] = []
    for index, (position, _, _) in enumerate(retained):
        next_position = next(
            (later[0] for later in retained[index + 1 :] if later[0] > position),
            len(folded),
        )
        fragment = folded[position:next_position].strip(" ,;:-")
        fragment = re.sub(
            r"\b(?:y|and|then|luego|despues)\s*$",
            "",
            fragment,
            flags=re.IGNORECASE,
        ).strip(" ,;:-")
        # Google query construction consumes this evidence as data. Retain the
        # complete bounded clause so a plan cannot silently search a prefix.
        evidence.append(
            fragment if _explicit_google_search_query(fragment) is not None
            else fragment[:240] or "efecto solicitado"
        )
    return EffectIntent(operations, tuple(evidence))


def _review_system_and_network_effects(
    matches: list[tuple[int, int, str]],
    folded: str,
    head: str,
) -> None:
    """Append read-only system, network, and nearby-device effects."""

    if _direct_current_time_request(folded):
        _append(matches, folded, "system.time", r"\b(?:hora|time|fecha|date)\b")
    process_domain = _process_list_domain(folded)
    if _direct_process_inventory_request(folded):
        _append(
            matches,
            folded,
            "system.process.list",
            r"^",
        )
    if (
        not any(entry[2] == "system.process.list" for entry in matches)
        and process_domain
        and _has(folded, r"\b(?:programas?|programs?|apps?|aplicaciones?)\b")
        and _has(
            folded,
            r"\b(?:memoria|memory|cpu|ram|comiendo|eating)\b",
        )
        and not _has(folded, r"\b(?:instalad[oa]s?|installed)\b")
    ):
        _append(
            matches,
            folded,
            "system.process.list",
            r"^",
        )
    if (
        not any(entry[2] == "system.process.list" for entry in matches)
        and (
            _head_is(head, rf"(?:{_MACHINE_STATUS_HEAD}|tell)")
            or _has(
                folded,
                rf"^[¿?¡!\s]*(?:{_DATIVE_STATE_OPENING}|"
                rf"{_HARDWARE_MODEL_OPENING})\b",
            )
        )
        and _system_status_domain(folded)
        and _machine_status_scopes_are_one_reading(folded)
        and _machine_status_is_the_whole_clause(folded)
        # «el volumen del sistema» nombra el equipo solo como poseedor del
        # audio: esa lectura pertenece a audio.status, no a system.status.
        and not _volume_domain(folded)
        and (
            _has(folded, r"\b(?:como|health)\b")
            or _has(folded, _MACHINE_STATUS_OBSERVATION)
            or _head_is(head, _MACHINE_STATUS_OBSERVATION_HEAD)
        )
    ):
        _append(
            matches,
            folded,
            "system.status",
            # Identity/usage can precede the hardware noun. Retain the whole
            # request for the existing scope extractor, not just its noun.
            r"^",
        )

    if _head_is(head, r"(?:haz|hacer|ejecuta|run|ping)") and _has(
        folded,
        r"\b(?:haz|hacer|ejecuta|run)\s+(?:un\s+)?ping\b|\bping\s+(?:a|to)\b",
    ):
        _append(
            matches,
            folded,
            "network.ping",
            r"\b(?:haz|hacer|ejecuta|run|ping)\b",
        )
    elif (
        _head_is(head, r"(?:see|check|ping|haz|hacer|ejecuta|run)")
        and _has(folded, r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
        and _has(
            folded,
            r"\b(?:answers?|responde|contest|ping|alcanza|reach)\b",
        )
        and not _has(
            folded,
            r"\b(?:en|on)\s+(?:la\s+|the\s+)?(?:web|internet)\b",
        )
    ):
        _append(
            matches,
            folded,
            "network.ping",
            r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
        )
    elif (
        _head_is(head, r"(?:como|how|muestra|show|dime|que|what)")
        and _network_status_domain(folded)
        and _has(folded, r"\b(?:como|estado|status|health)\b")
    ):
        _append(matches, folded, "network.status", r"\bred\b|\bnetwork\b")
    if (
        _head_is(head, r"(?:lista|listar|muestra|muestrame|show|list)")
        and _has(folded, r"\bbluetooth\b")
        and _has(folded, rf"\b{_LIST}\b")
    ):
        _append(
            matches,
            folded,
            "bluetooth.device.list",
            r"\bbluetooth\b",
        )
    bluetooth_radio_verb = (
        r"(?:activa(?:me|lo)?|activar|desactiva(?:me|lo)?|desactivar|enciende(?:me|lo)?|"
        # NETWORK1293: voseo «encendé el bluetooth» folds to «encende».
        r"encende(?:me|lo)?|encender|prende(?:me|lo)?|"
        r"prender|apaga(?:me|lo)?|apagar|enable|disable|turn)"
    )
    if (
        _head_is(head, bluetooth_radio_verb)
        and _has(folded, r"\bbluetooth\b")
        and _has(folded, rf"\b{bluetooth_radio_verb}\b")
        and not _has(folded, r"\b(?:dispositivo|device|auriculares?|headphones?)\b")
        and not _has(
            folded,
            r"\b(?:del|de mi|on my|of my)\s+"
            r"(?:auto|car|telefono|celular|movil|phone|smartphone|tablet)\b",
        )
    ):
        _append(
            matches,
            folded,
            "bluetooth.radio.set",
            rf"\b{bluetooth_radio_verb}\b",
        )
    if (
        _head_is(head, r"(?:lista|listar|muestra|muestrame|show|list)")
        and _has(folded, r"\b(?:perifericos?|peripherals?)\b")
        and _has(folded, rf"\b{_LIST}\b|\bconectad")
    ):
        _append(
            matches,
            folded,
            "peripheral.list",
            r"\b(?:perifericos?|peripherals?)\b",
        )
    if _has(folded, r"\bwi[\s-]?fi\b") and not _has(
        folded,
        r"\b(?:del|de mi|on my|of my)\s+"
        r"(?:router|telefono|celular|movil|phone|smartphone|tablet|auto|car)\b",
    ):
        if (
            _has(folded, r"\b(?:perfiles?|profiles?)\b")
            and _has(folded, rf"\b{_LIST}\b|\bguardad")
            and _head_is(
                head,
                r"(?:lista|listar|muestra|muestrame|show|list)",
            )
        ):
            _append(matches, folded, "wifi.profile.list", r"\bwi[\s-]?fi\b")
        elif _head_is(
            head,
            r"(?:a|como|how|muestra|show|dime|que|what)",
        ) and _has(
            folded,
            r"\b(?:como|estado|status|health|conectad[oa]|connected)\b",
        ):
            _append(matches, folded, "wifi.status", r"\bwi[\s-]?fi\b")
        elif _wifi_state_question(folded):
            # NETWORK1293 H0230 «decime si el wifi está prendido», «¿el wifi
            # está encendido?»: a state question is the read, not an effect.
            _append(matches, folded, "wifi.status", r"\bwi[\s-]?fi\b")
        elif _head_is(head, r"(?:apaga|apagar|desconecta|disconnect)") and _has(
            folded, r"\b(?:apaga|apagar|desconecta|disconnect)\b"
        ):
            _append(
                matches,
                folded,
                "wifi.disconnect",
                r"\b(?:apaga|apagar|desconecta|disconnect)\b",
            )
        elif _head_is(
            head,
            # NETWORK1721 «conectate al wifi de casa»: the voseo reflexive is
            # the same order, and «al» is «a» + «el».
            r"(?:conecta|conectar|conectame|conectate|cambia|change|connect)",
        ) and _has(
            folded,
            r"\b(?:conecta|conectar|conectame|conectate|cambia|change|connect)\b",
        ):
            named_profile = _has(
                folded,
                r"\b(?:cambia|change)\s+(?:el\s+|la\s+)?wi[\s-]?fi\s+"
                r"(?:a|to)\s+\S|"
                r"\b(?:conecta|conectame|conectate|connect)\s+(?:a|al|to)\s+"
                r"(?:la\s+|the\s+)?(?:red\s+|network\s+)?wi[\s-]?fi\s+"
                r"(?:de|llamad[oa]|named|called)\s+\S|"
                r"\bconnect\s+to\s+(?:the\s+)?wi[\s-]?fi\s+network\s+"
                r"(?:named|called)\s+\S",
            )
            _append(
                matches,
                folded,
                "wifi.connect.named" if named_profile else "wifi.ensure.connected",
                r"\b(?:conecta|conectar|conectame|conectate|cambia|change|connect)\b",
            )


def _review_audio_effects(
    matches: list[tuple[int, int, str]],
    folded: str,
    head: str,
    *,
    context_audio: bool,
) -> bool:
    """Append audio effects and report whether the clause targets volume."""

    # A preceding audio clause is enough to interpret a numeric continuation
    # ("... y luego al 12%"), but only when this clause starts with the value.
    # Broader inheritance turns years and genre names such as "dance de los
    # 80" into literal volume authority.
    elliptical_audio_level = context_audio and _has(
        folded,
        r"^(?:al?|to)?\s*\d{1,3}\s*(?:%|por ciento|percent)?\b",
    )
    elliptical_audio_status = (
        context_audio
        and _head_is(
            head,
            r"(?:en|a|cuanto|cuanta|dime|decime|muestra|show|what|que|how)",
        )
        and _has(
            folded,
            r"\b(?:cuanto|cuanta|how much|nivel|level|quedo|estado|status)\b",
        )
    )
    audio_level = (
        _volume_domain(folded) or elliptical_audio_level or elliptical_audio_status
    )
    if (
        _head_is(head, _MUTE_VERB)
        and _has(folded, r"\b(?:microfono|microphone|mic)\b")
        and _has(folded, rf"\b{_MUTE_VERB}\b")
        and not _has(
            folded,
            r"\b(?:llamada|call|aplicacion|application|app|discord|teams|"
            r"zoom|skype|whatsapp)\b",
        )
    ):
        _append(
            matches,
            folded,
            "audio.microphone.mute",
            rf"\b{_MUTE_VERB}\b",
        )
    if audio_level:
        literal_level = _literal_percentage_word_value(folded)
        literal_adjustment = _literal_volume_adjustment(folded)
        if literal_level is not None and _head_is(
            head, rf"(?:{_SET_VOLUME_VERB}|{_VOLUME_UP_VERB}|{_VOLUME_DOWN_VERB})",
        ):
            _append(matches, folded, "audio.volume", rf"\b{_VOLUME_OBJECT}\b")
        elif (
            _head_is(head, rf"(?:{_VOLUME_UP_VERB}|{_VOLUME_DOWN_VERB})")
            and _has(
                folded,
                rf"\b{_VOLUME_OBJECT}\s+(?:a(?:l)?|to|at)\s*(?:100|[0-9]{{1,2}})(?![0-9])",
            )
        ):
            # «baja el volumen a 30»: the direction only states where the level
            # is coming from; the target is absolute (AUDIO1239, H0254).
            _append(matches, folded, "audio.volume", rf"\b{_VOLUME_OBJECT}\b")
        elif literal_adjustment is not None:
            _append(matches, folded, "audio.volume.adjust", rf"\b{_VOLUME_OBJECT}\b")
        elif _has(
            folded,
            r"\b(?:bajalo|bajala|subelo|subela)\b",
        ):
            _append(
                matches,
                folded,
                "audio.volume.adjust",
                r"\b(?:bajalo|bajala|subelo|subela)\b",
            )
        elif (
            _head_is(
                head,
                r"(?:sube|subir|baja|bajar|bajalo|subelo|aumenta|reduce|"
                r"increment|decrease)",
            )
            and _has(
                folded,
                r"\b(?:sube|subir|baja|bajar|bajalo|subelo|aumenta|reduce|"
                r"increment|decrease)\b",
            )
            and _has(
                folded,
                r"\b(?:puntos?|points?|en|by|por ciento|percent)\b|%",
            )
        ):
            _append(
                matches,
                folded,
                "audio.volume.adjust",
                r"\b(?:sube|subir|baja|bajar|aumenta|reduce|increment|decrease)\b",
            )
        elif (
            _head_is(head, _SET_VOLUME_VERB)
            and _has(folded, rf"\b{_SET_VOLUME_VERB}\b")
            and (
                _has(folded, r"(?:\b\d{1,3}\b|\bpor ciento\b|%)")
                or _literal_percentage_word_value(folded) is not None
            )
        ):
            _append(
                matches,
                folded,
                "audio.volume",
                rf"\b{_SET_VOLUME_VERB}\b",
            )
        elif context_audio and _has(
            folded,
            r"^(?:al?|to)?\s*\d{1,3}\s*(?:%|por ciento|percent)?\b",
        ):
            _append(
                matches,
                folded,
                "audio.volume",
                r"\d{1,3}",
            )
        already_set_volume = any(
            entry[2] in {"audio.volume", "audio.volume.adjust"} for entry in matches
        )
        level_query = (
            not already_set_volume
            and (
                (
                    _head_is(
                        head,
                        r"(?:en|a|cuanto|cuanta|estado|status|actual|current|"
                        r"nivel|level|volumen|volume|dime|decime|muestra|"
                        r"muestrame|mostrame|show|ver|what|que|cual|which|how)",
                    )
                    and _has(folded, _AUDIO_LEVEL_CUE)
                )
                # «muéstrame el volumen», «ver el volumen del sistema»: el verbo de
                # observación ya pide la lectura, sin palabra de medida.
                or (
                    _head_is(head, _AUDIO_OBSERVATION_HEAD)
                    and _has(folded, r"\b(?:volumen|volume)\b")
                )
            )
            and (
                not _has(
                    folded,
                    r"\b(?:pon|poner|fija|ajusta|adjust|establece|set|cambia|change|"
                    r"sube|subir|baja|bajar|bajalo|subelo|aumenta|reduce)\b",
                )
                or _has(folded, r"\b(?:luego|despues|then|after|quedo)\b")
            )
            and not _is_past_or_hypothetical_state(folded)
        )
        if level_query:
            _append(
                matches,
                folded,
                "audio.status",
                rf"{_AUDIO_LEVEL_CUE}|\b(?:volumen|volume|audio|sonido|sound)\b",
                priority=1,
            )
        elif _is_audio_mute_state_query(folded, head):
            _append(
                matches,
                folded,
                "audio.status",
                (
                    r"\b(?:silenciad[oa]s?|mutead[oa]s?|muted|mudo|"
                    r"silencio|mute)\b|"
                    r"\b(?:audio|sonido|sound|volumen|volume)\b"
                ),
                priority=1,
            )
    if (
        _head_is(
            head,
            rf"(?:{_MUTE_VERB}|quita|quitar|saca|sacar|remove|"
            r"pon|pone|ponlo|ponelo|poner|ponle|deja|dejalo|dejar|put|leave|turn)",
        )
        and (
            _audio_mute_domain(folded)
            # «ponelo en mute», «dejalo en mute»: the pronoun with the mute
            # predicate names the global audio (AUDIO1239, H0189).
            or _has(
                folded,
                r"^[¿?¡!\s]*(?:pon(?:e|lo|elo|le|eme)?|ponlo|deja(?:lo)?|"
                r"leave\s+it|put\s+it|turn\s+it)\s+(?:en|in|on)\s+"
                r"(?:mute|mudo|silencio|silent)[\s?!.]*$",
            )
            or (
                context_audio
                and _has(
                    folded,
                    r"^(?:reactiva(?:lo|la)?|unmute(?: it)?|quita(?:r)? el silencio)[\s?!.]*$",
                )
            )
        )
        and _has(
            folded,
            rf"\b{_MUTE_VERB}\b|"
            r"\b(?:quita|quitar|saca|sacar|remove)\s+(?:el\s+)?"
            r"(?:silencio|mute|mudo)\b|"
            r"\b(?:en|in|on)\s+(?:mudo|silencio|mute|silent)\b|"
            r"\bback\s+on\b",
        )
    ):
        _append(
            matches,
            folded,
            "audio.mute",
            rf"\b{_MUTE_VERB}\b|"
            r"\b(?:quita|quitar|saca|sacar|remove)\b|"
            r"\b(?:pon|poner|ponle|deja|dejar|put|leave|turn)\b",
        )
        reversal = _match(
            folded,
            (
                r"\b(?:y|and)\b\s+(?:reactiva(?:lo|la)?|reactivar|unmute|"
                r"quita(?:r)?\s+(?:el\s+)?silencio)\b"
            ),
        )
        if reversal is not None:
            matches.append((reversal.start(), 0, "audio.mute"))
    return audio_level


_ENGLISH_SMALL_NUMBERS = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
}
_ENGLISH_TENS = {
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}
_SPANISH_SMALL_NUMBERS = {
    "cero": 0,
    "uno": 1,
    "un": 1,
    "dos": 2,
    "tres": 3,
    "cuatro": 4,
    "cinco": 5,
    "seis": 6,
    "siete": 7,
    "ocho": 8,
    "nueve": 9,
    "diez": 10,
    "once": 11,
    "doce": 12,
    "trece": 13,
    "catorce": 14,
    "quince": 15,
    "dieciseis": 16,
    "diecisiete": 17,
    "dieciocho": 18,
    "diecinueve": 19,
    "veinte": 20,
    "veintiuno": 21,
    "veintidos": 22,
    "veintitres": 23,
    "veinticuatro": 24,
    "veinticinco": 25,
    "veintiseis": 26,
    "veintisiete": 27,
    "veintiocho": 28,
    "veintinueve": 29,
}
_SPANISH_TENS = {
    "treinta": 30,
    "cuarenta": 40,
    "cincuenta": 50,
    "sesenta": 60,
    "setenta": 70,
    "ochenta": 80,
    "noventa": 90,
}


def _percentage_word_values() -> dict[str, int]:
    values = dict(_ENGLISH_SMALL_NUMBERS)
    values.update(_SPANISH_SMALL_NUMBERS)
    for word, base in _ENGLISH_TENS.items():
        values[word] = base
        values.update(
            {
                f"{word} {unit}": base + value
                for unit, value in _ENGLISH_SMALL_NUMBERS.items()
                if 1 <= value <= 9
            }
        )
    for word, base in _SPANISH_TENS.items():
        values[word] = base
        values.update(
            {
                f"{word} y {unit}": base + value
                for unit, value in _SPANISH_SMALL_NUMBERS.items()
                if 1 <= value <= 9 and unit != "un"
            }
        )
    values["one hundred"] = 100
    values["cien"] = 100
    return values


_PERCENTAGE_WORD_VALUES = _percentage_word_values()
_PERCENTAGE_WORD_PATTERN = (
    "(?:"
    + "|".join(
        re.escape(value)
        for value in sorted(_PERCENTAGE_WORD_VALUES, key=len, reverse=True)
    )
    + ")"
)


def _literal_percentage_word_value(text: str) -> int | None:
    """Read one bounded ES/EN word-valued literal beside the volume domain."""

    text = _strip_request_envelope(_fold(text))
    if (
        not _volume_domain(text)
        or _is_negative_effect_clause(text)
        or _is_meta_or_tool_denial(text)
        or _has_contradictory_correction(text)
        or _has_unsupported_deferred_effect(text)
        or _has(text, r"\d|\b(?:o|or)\b")
        or _literal_volume_adjustment(text) is not None
    ):
        return None
    value = rf"(?P<level>{_PERCENTAGE_WORD_PATTERN}|mitad|half|maximo|maximum)"
    patterns = (
        rf"\b{_VOLUME_OBJECT}\s+(?:justo\s+|exactly\s+)?"
        rf"(?:a(?:l)?|en|to|at)\s*(?:la\s+|the\s+)?{value}"
        rf"(?:\s*(?:%|por\s+ciento|percent))?\b",
        # The numeric antecedent and its reference must be in this same
        # authored sentence; an absent prior level cannot be manufactured.
        rf"\b{value}\s+percent\s+is\s+enough\s*:\s*"
        rf"{_SET_VOLUME_VERB}\s+(?:the\s+)?(?:{_LOCAL_VOLUME_DEVICE}\s+)?"
        r"volume\s+(?:there|to\s+that\s+level)[.!?]*$",
    )
    matches = [found for pattern in patterns for found in re.finditer(pattern, text)]
    if len(matches) != 1:
        return None
    level = matches[0].group("level").casefold()
    if level in {"mitad", "half"}:
        return 50
    if level in {"maximo", "maximum"}:
        return 100
    return _PERCENTAGE_WORD_VALUES.get(level)


def _literal_volume_adjustment(text: str) -> dict[str, object] | None:
    """Bind a relative quantity to its authored direction and audio object."""

    text = _strip_request_envelope(_fold(text))
    if (
        not _volume_domain(text)
        or _is_negative_effect_clause(text)
        or _is_meta_or_tool_denial(text)
        or _has_contradictory_correction(text)
        or _has_unsupported_deferred_effect(text)
        or _has(text, r"\b(?:o|or)\b")
    ):
        return None
    up = _has(text, rf"\b{_VOLUME_UP_VERB}\b")
    down = _has(text, rf"\b{_VOLUME_DOWN_VERB}\b")
    if up == down:
        return None
    direction = rf"(?:{_VOLUME_UP_VERB}|{_VOLUME_DOWN_VERB})"
    amount = rf"(?P<amount>\d{{1,3}}|{_PERCENTAGE_WORD_PATTERN})(?![a-z0-9])"
    unit = r"(?:puntos?|(?:percentage\s+)?points?|por\s+ciento|percent|%)"
    patterns = (
        rf"\b{direction}\s+(?:en\s+|by\s+)?{amount}\s+{unit}"
        rf"\s+(?:(?:el|la|the)\s+)?{_VOLUME_OBJECT}\b",
        rf"\b{direction}\s+(?:(?:el|la|the)\s+)?{_VOLUME_OBJECT}"
        rf"\s+(?:en|by)\s+{amount}(?:\s*{unit})?",
    )
    matches = [found for pattern in patterns for found in re.finditer(pattern, text)]
    if len(matches) != 1:
        return None
    raw = matches[0].group("amount")
    value = int(raw) if raw.isdigit() else _PERCENTAGE_WORD_VALUES.get(raw)
    # Retain the former single-number boundary, including an out-of-range
    # number elsewhere in the fragment; do not choose among competing values.
    digits = re.findall(r"\d+", text)
    if value is None or not 1 <= value <= 100 or digits != ([raw] if raw.isdigit() else []):
        return None
    return {"amount": value, "direction": "up" if up else "down"}


# BRIGHT1283: no brightness literal had a deterministic reader, so «qué brillo
# tengo» became a clarification, «subí el brillo» asked for the direction it
# already carried and «turn the brightness down» denied the capability. The
# readers below mirror the volume grammar: a status question, a relative
# adjustment with an authored amount, and a relative request without amount
# that keeps its direction and asks how much (owner rule on H0027).
_BRIGHTNESS_SCREEN = (
    r"(?:\s+(?:de\s+(?:la\s+|mi\s+)?|del\s+|of\s+(?:the\s+|my\s+)?)"
    r"(?:pantalla|monitor|screen|display))?"
)
_BRIGHTNESS_OBJECT = (
    rf"(?:(?:nivel\s+de\s+)?(?:brillo|brightness){_BRIGHTNESS_SCREEN}"
    rf"(?:\s+actual)?{_BRIGHTNESS_SCREEN})"
)
_BRIGHTNESS_UP_VERB = (
    r"(?:sube(?:me|lo|la)?|subi(?:me|lo|la)?|subir|aumenta(?:me|lo|la)?|aumentar|"
    r"incrementa|incrementar|increase|raise|brighten)"
)
_BRIGHTNESS_DOWN_VERB = (
    r"(?:baja(?:me|lo|la)?|bajar|reduce(?:me|lo|la)?|reducir|disminui(?:me|lo|la)?|"
    r"disminuye|disminuir|decrease|lower|dim)"
)
_BRIGHTNESS_ABSOLUTE = (
    r"\b(?:a|al|to|at|hasta)\s*(?:100|[0-9]{1,2})\b|"
    r"\b(?:al\s+|to\s+(?:the\s+)?)?(?:maximo|minimo|max|min|tope|full|maximum|minimum)\b"
)
_BRIGHTNESS_ENGLISH_TURN = r"\bturn\s+(?:the\s+|my\s+)?(?:screen\s+)?brightness\s+(?P<dir>up|down)\b"
_BRIGHTNESS_RELATIVE_WORDS = (
    r"\b(?:un\s+(?:poco|toque|poquito|cacho|pelin)|bastante|mucho|algo|"
    r"a\s+little|a\s+bit|slightly)\b"
)


def brightness_status_request(text: str) -> bool:
    """«qué brillo tengo», «mostrame el brillo», «what's the brightness»: read it."""

    folded = _strip_request_envelope(_fold(text)).strip(" ¿?¡!.,")
    if re.search(r"\d", folded) or _is_past_or_hypothetical_state(folded):
        return False
    obj = _BRIGHTNESS_OBJECT
    return re.fullmatch(
        rf"(?:(?:y|and)\s+)?(?:"
        rf"(?:que|cual|cuanto|cuanta|como)\s+(?:es\s+|esta\s+|tengo\s+(?:de\s+)?)?"
        rf"(?:el\s+|mi\s+)?{obj}(?:\s+(?:tengo|hay|tiene|esta|puesto|ahora))*|"
        rf"(?:a|en)\s+(?:cuanto|que|que\s+nivel)\s+(?:esta|tengo|tiene)\s+(?:el\s+|mi\s+)?{obj}|"
        rf"(?:dime|decime|mostrame|muestrame|muestra|mostra|ver|quiero\s+ver|"
        rf"show(?:\s+me)?|tell\s+me|check|revisa|chequea|fijate)\s+"
        rf"(?:el\s+|mi\s+|the\s+|my\s+)?(?:nivel\s+(?:actual\s+)?de\s+)?{obj}|"
        rf"what(?:'s|\s+is)\s+(?:the\s+|my\s+)?(?:current\s+)?{obj}(?:\s+(?:level|at|now|set\s+to))*|"
        rf"how\s+bright\s+is\s+(?:the\s+|my\s+)?(?:screen|display|monitor)|"
        # BRIGHT1319 H0674 «tengo el brillo al máximo»: a claim about the
        # present level is answered by reading it, never by agreeing.
        rf"(?:tengo|esta|tiene|is)\s+(?:el\s+|mi\s+|the\s+|my\s+)?{obj}\s+"
        rf"(?:(?:al|a|en\s+el|at|on)\s+(?:maximo|minimo|max|min|tope|full|maximum|minimum)|a\s+tope|alto|bajo|high|low)"
        rf"(?:\s+(?:ahora|now))?|"
        rf"(?:el\s+|mi\s+)?{obj}\s+(?:esta|lo\s+tengo)\s+(?:al|a|en\s+el)\s+(?:maximo|minimo|max|min|tope)"
        rf")(?:\s*,?\s*(?:por\s+favor|please|no|verdad|cierto|right))?",
        folded,
    ) is not None


def _literal_brightness_adjustment(text: str) -> dict[str, object] | None:
    """Bind a relative quantity to its authored direction and the brightness object."""

    folded = _strip_request_envelope(_fold(text))
    if (
        _is_negative_effect_clause(folded)
        or _is_meta_or_tool_denial(folded)
        or _has_contradictory_correction(folded)
        or _has(folded, r"\b(?:o|or)\b")
        or re.search(_BRIGHTNESS_ABSOLUTE, folded) is not None
        # «un toque», «un poco»: a relative word is not a quantity («un» is
        # not one point); the request asks how much instead.
        or re.search(_BRIGHTNESS_RELATIVE_WORDS, folded) is not None
    ):
        return None
    english = re.search(_BRIGHTNESS_ENGLISH_TURN, folded)
    up = _has(folded, rf"\b{_BRIGHTNESS_UP_VERB}\b") or (english is not None and english.group("dir") == "up")
    down = _has(folded, rf"\b{_BRIGHTNESS_DOWN_VERB}\b") or (english is not None and english.group("dir") == "down")
    if up == down:
        return None
    direction = rf"(?:{_BRIGHTNESS_UP_VERB}|{_BRIGHTNESS_DOWN_VERB})"
    amount = rf"(?P<amount>\d{{1,3}}|{_PERCENTAGE_WORD_PATTERN})(?![a-z0-9])"
    unit = r"(?:puntos?|(?:percentage\s+)?points?|por\s+ciento|percent|%)"
    obj = _BRIGHTNESS_OBJECT
    patterns = (
        rf"\b{direction}\s+(?:(?:un|a)\s+)?{amount}\s*{unit}?\s+(?:(?:el|la|the)\s+)?{obj}\b",
        rf"\b{direction}\s+(?:(?:el|la|the|my|mi)\s+)?{obj}\s+(?:(?:en|by|un|a)\s+)?{amount}(?:\s*{unit})?",
        rf"{_BRIGHTNESS_ENGLISH_TURN}\s+(?:by\s+)?{amount}(?:\s*{unit})?",
    )
    matches = [found for pattern in patterns for found in re.finditer(pattern, folded)]
    if len(matches) != 1:
        return None
    raw = matches[0].group("amount")
    value = int(raw) if raw.isdigit() else _PERCENTAGE_WORD_VALUES.get(raw)
    digits = re.findall(r"\d+", folded)
    if value is None or not 1 <= value <= 100 or digits != ([raw] if raw.isdigit() else []):
        return None
    return {"amount": value, "direction": "up" if up else "down"}


def brightness_relative_without_amount(text: str) -> bool:
    """«subí el brillo», «bajame el brillo un toque», «turn the brightness down»: ask how much."""

    folded = _strip_request_envelope(_fold(text))
    if (
        _is_negative_effect_clause(folded)
        or _is_meta_or_tool_denial(folded)
        or _has_contradictory_correction(folded)
        or _is_past_or_hypothetical_state(folded)
        or re.search(r"\d", folded) is not None
        or _literal_percentage_word_value(folded) is not None
        or re.search(_BRIGHTNESS_ABSOLUTE, folded) is not None
        or len(_request_clauses(folded)) != 1
        or _has(folded, r"\b(?:y|and)\s+(?:abre|open|crea|create|apaga|silencia|pon|cierra|close)\b")
    ):
        return False
    return (
        re.search(
            rf"\b(?:{_BRIGHTNESS_UP_VERB}|{_BRIGHTNESS_DOWN_VERB})\s+(?:{_BRIGHTNESS_RELATIVE_WORDS}\s+)?"
            rf"(?:(?:el|la|the|my|mi)\s+)?{_BRIGHTNESS_OBJECT}\b",
            folded,
        ) is not None
        or re.search(_BRIGHTNESS_ENGLISH_TURN, folded) is not None
        or re.search(r"\b(?:brighten|dim)\s+(?:the\s+|my\s+)?(?:screen|display)\b", folded) is not None
    )


_BRIGHTNESS_SET_VERB = (
    r"(?:pon(?:me|le|e|elo|ele|lo)?|poner|fija(?:me|lo)?|ajusta(?:me|lo)?|adjust|"
    r"establece|set|cambia(?:me|lo)?|change|deja(?:me|lo)?|leave|"
    rf"{_BRIGHTNESS_UP_VERB}|{_BRIGHTNESS_DOWN_VERB}|turn)"
)
_BRIGHTNESS_EXTREME_VALUES = {
    "maximo": 100, "max": 100, "tope": 100, "full": 100, "maximum": 100, "the max": 100,
    "minimo": 0, "min": 0, "minimum": 0,
}


_CLIPBOARD_WRITE_HEAD = (
    r"(?:copia|copiar|copiame|copy|pon|pone|poneme|ponme|ponelo|ponlo|put|"
    r"escribe|escribi|escribime|write|guarda|guardame|save|deja|dejame|leave|"
    r"mete|meteme|carga|cargame|load)"
)
_CLIPBOARD_QUOTED = re.compile(r'"([^"\n]+)"|“([^”\n]+)”|«([^»\n]+)»|‘([^’\n]+)’')


def literal_clipboard_write_text(text: str) -> str | None:
    """Return the literal a person asked to put on the OS clipboard, or None.

    «Copia a mi portapapeles "Hola"», «copiá esto al portapapeles: hola mundo»,
    «Copy "hello" to my clipboard»: the head is a copy/put verb, the clipboard
    is named and the literal is either quoted or introduced by a colon after
    the clipboard noun. The literal keeps its case and accents. Nothing is
    inferred when no literal is given («copiá este texto al portapapeles» stays
    a clarification) or when the clause is a prohibition.
    """

    collapsed = " ".join(text.split())
    folded = _strip_request_envelope(_fold(collapsed))
    if not _has(folded, r"\b(?:portapapeles|clipboard)\b"):
        return None
    if not _head_is(_request_head(folded), _CLIPBOARD_WRITE_HEAD):
        return None
    if _is_negative_effect_clause(folded):
        return None
    quoted = [
        group
        for found in _CLIPBOARD_QUOTED.finditer(collapsed)
        for group in found.groups()
        if group
    ]
    if len(quoted) > 1:
        return None
    if quoted:
        literal = quoted[0].strip()
        return literal or None
    colon = re.search(
        r"\b(?:portapapeles|clipboard)\b[^:]*:\s*(?P<literal>.+)$",
        collapsed,
        re.IGNORECASE,
    )
    if colon is None:
        return None
    literal = colon.group("literal").strip()
    if literal.endswith(".") and literal.count(".") == 1:
        # The sentence's own full stop is not part of a dictated fragment.
        literal = literal[:-1].rstrip()
    return literal or None


def _literal_brightness_level(text: str) -> int | None:
    """«poné el brillo al 80», «pon el brillo al 80%», «subí el brillo al máximo»: an absolute level."""

    folded = _strip_request_envelope(_fold(text))
    if (
        _is_negative_effect_clause(folded)
        or _is_meta_or_tool_denial(folded)
        or _has_contradictory_correction(folded)
        or _is_past_or_hypothetical_state(folded)
        or _has(folded, r"\b(?:o|or)\b")
        or len(_request_clauses(folded)) != 1
    ):
        return None
    obj = _BRIGHTNESS_OBJECT
    numeric = re.search(
        rf"\b{_BRIGHTNESS_SET_VERB}\s+(?:(?:el|la|the|my|mi)\s+)?{obj}\s+"
        r"(?:a|al|en|to|at|hasta)\s*(?:el\s+|the\s+)?(?P<level>100|[0-9]{1,2})"
        r"(?![0-9])(?:\s*(?:%|por\s+ciento|percent))?",
        folded,
    )
    extreme = re.search(
        rf"\b{_BRIGHTNESS_SET_VERB}\s+(?:(?:el|la|the|my|mi)\s+)?{obj}\s+"
        r"(?:a|al|to|at|hasta)\s+(?:el\s+|the\s+)?(?P<word>maximo|max|tope|full|maximum|minimo|min|minimum)\b",
        folded,
    )
    digits = re.findall(r"\d+", folded)
    if numeric is not None and extreme is None:
        raw = numeric.group("level")
        return int(raw) if digits == [raw] else None
    if extreme is not None and numeric is None and not digits:
        return _BRIGHTNESS_EXTREME_VALUES.get(extreme.group("word"))
    return None


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


def _review_installed_catalog_effects(
    matches: list[tuple[int, int, str]],
    folded: str,
    *,
    application_names: Iterable[str],
) -> None:
    """Append authenticated installed-application and game-catalog effects."""

    game_list_query = _has(
        folded,
        r"\b(?:juegos|games)\b",
    ) and (
        _has(folded, rf"\b{_LIST}\b")
        or (
            _has(folded, r"\b(?:instalad[oa]s?|installed)\b")
            and _has(folded, r"\b(?:en|on)\s+steam\b")
        )
    )
    installed_query = _has(folded, r"\b(?:instalad[oa]s?|installed)\b")
    authenticated_installed = _authenticated_application_target(
        folded,
        application_names,
        installed_query=True,
    )
    authenticated_installed_list = _authenticated_application_list(
        folded,
        application_names,
        installed_query=True,
    )
    installed_application = (
        installed_query
        and not game_list_query
        and (
            authenticated_installed is not None
            or _has(
                folded,
                (
                    rf"^[¿?¡!\s]*(?:esta|estan|is|are)?\s*"
                    rf"(?:instalad[oa]s?|installed)\s*"
                    rf"(?:el|la|los|las|the)?\s*{_KNOWN_APPLICATION}"
                    rf"(?:\s+como\b.{{1,80}})?"
                    rf"(?:\s+(?:por favor|please|ahora|now))?[\s?!.]*$"
                ),
            )
            or _has(
                folded,
                (
                    rf"^[¿?¡!\s]*(?:is|are|esta|estan)\s+(?:el|la|the)?\s*"
                    rf"{_KNOWN_APPLICATION}\s+(?:even\s+)?"
                    rf"(?:instalad[oa]s?|installed)"
                    rf"(?:\s+(?:here|aqui|en este\s+(?:equipo|pc)|"
                    rf"on this machine))?"
                    rf"(?:\s+(?:por favor|please|ahora|now))?[\s?!.]*$"
                ),
            )
        )
    )
    installed_game = (
        installed_query
        and not installed_application
        and (
            _has(folded, r"\b(?:juego|game)\b")
            or _has(folded, r"\b(?:en|on)\s+steam\b")
        )
        and not game_list_query
    )
    if authenticated_installed_list:
        matches.extend(
            (position, 0, "app.installed")
            for position, _ in authenticated_installed_list
        )
    elif game_list_query:
        _append(
            matches,
            folded,
            "game.catalog.list",
            r"\b(?:juegos|games)\b",
        )
    elif installed_game:
        _append(
            matches,
            folded,
            "game.installed.named",
            r"\b(?:instalad[oa]s?|installed)\b",
        )
    elif installed_application:
        _append(
            matches,
            folded,
            "app.installed",
            r"\b(?:instalad[oa]s?|installed)\b",
        )
    elif (
        _has(
            folded,
            r"^(?:do\s+i\s+have|tengo|is\s+there)\b",
        )
        and _has(folded, rf"\b{_KNOWN_APPLICATION}\b")
        and _has(
            folded,
            r"\b(?:on this machine|en\s+(?:esta|este)\s+"
            r"(?:maquina|equipo|pc|computador)|aqui|here)\b",
        )
        and not _has(folded, r"\b(?:juego|game)\b")
    ):
        _append(
            matches,
            folded,
            "app.installed",
            rf"\b{_KNOWN_APPLICATION}\b",
        )


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


def _review_file_and_game_effects(
    matches: list[tuple[int, int, str]],
    folded: str,
    head: str,
) -> None:
    """Append closed file-discovery and explicitly Steam-scoped game effects."""

    if (
        _head_is(head, _OPEN)
        and _has(folded, r"\b(?:archivo|file)\b")
        and _has(
            folded,
            r"\b(?:ultimo|ultima|mas reciente|latest|most recent|last)\b",
        )
        and _has(
            folded,
            r"\b(?:descargas|downloads?|escritorio|desktop|documentos?|"
            r"documents?|imagenes|pictures|descargue|downloaded)\b",
        )
    ):
        _append(
            matches,
            folded,
            "filesystem.file.open.latest",
            rf"\b{_OPEN}\b",
        )
    if _has(folded, r"\bhash\b") and _has(folded, r"\b(?:archivo|file)\b"):
        _append(matches, folded, "filesystem.hash", r"\bhash\b")
    if (
        _head_is(head, r"(?:que|cuales|what|which)")
        and _has(folded, r"\b(?:archivos?|files?)\b")
        and _has(folded, r"\b(?:carpeta|folder|directorio|directory)\b")
        and not _has(folded, r"\b(?:busca|buscar|search|find|hash)\b")
    ):
        _append(
            matches,
            folded,
            "filesystem.list",
            r"\b(?:archivos?|files?)\b",
        )
    if _literal_known_file_search(folded) is not None or (
        _head_is(head, _SEARCH)
        and _has(folded, r"\b(?:archivos?|files?)\b")
        and _has(
            folded,
            r"\b(?:contengan?|contiene|containing|contain|llamad[oa]s?|named)\b",
        )
        and not _has(
            folded,
            r"\b(?:google|bing|web|internet|online)\b",
        )
    ):
        _append(
            matches,
            folded,
            "filesystem.known.search",
            rf"\b{_SEARCH}\b",
        )
    if (
        _head_is(head, _OPEN)
        and _has(folded, r"\b(?:biblioteca|library)\b")
        and _has(folded, r"\bsteam\b")
    ):
        _append(
            matches,
            folded,
            "game.catalog.list",
            rf"\b{_OPEN}\b",
        )
    if (
        _head_is(head, rf"(?:{_OPEN}|lanza|launch|ejecuta|run)")
        and _has(folded, r"\b(?:desde|en|on|from)\s+steam\b")
        and _has(
            folded,
            rf"^[¿?¡!\s]*(?:{_OPEN}|lanza|launch|ejecuta|run)\b\s+\S.+",
        )
    ):
        _append(
            matches,
            folded,
            "game.launch",
            rf"\b(?:{_OPEN}|lanza|launch|ejecuta|run)\b",
        )


def _review_application_and_window_effects(
    matches: list[tuple[int, int, str]],
    folded: str,
    head: str,
    *,
    application_names: Iterable[str],
    context_open_application: bool,
    context_window_active: bool,
) -> None:
    """Append authenticated application and foreground-window effects."""

    authenticated_open_list = _authenticated_application_list(
        folded,
        application_names,
    )
    opened_application_spans = (
        () if authenticated_open_list else _open_application_spans(folded)
    )
    authenticated_open = (
        None
        if opened_application_spans
        else _authenticated_application_target(
            folded,
            application_names,
        )
    )
    if _is_builtin_keyboard_request(folded):
        authenticated_open_list = ()
        opened_application_spans = ()
        authenticated_open = None
    explicit_open_count = len(opened_application_spans)
    if authenticated_open_list:
        matches.extend(
            (position, 0, "app.open") for position, _ in authenticated_open_list
        )
    elif explicit_open_count:
        matches.extend(
            (position, 0, "app.open") for position, _ in opened_application_spans
        )
    elif authenticated_open is not None:
        matches.append((authenticated_open[0], 0, "app.open"))
    elif (
        _head_is(head, _OPEN)
        and not _has(folded, _KNOWN_APPLICATION)
        and not _has(
            folded,
            r"\b(?:ventana|window|archivo|file|pagina|page|sitio|site)\b",
        )
    ):
        _append(
            matches,
            folded,
            "app.open",
            rf"\b{_OPEN}\s+(?:(?:el|un|the|a)\s+)?(?:navegador|browser)\b",
        )
    elif context_open_application:
        continued_application = _match(
            folded,
            rf"^(?:el|la|the)?\s*(?P<app>{_KNOWN_APPLICATION})[\s?!.]*$",
        )
        if continued_application is not None:
            matches.append((continued_application.start("app"), 0, "app.open"))

    if (
        _head_is(head, r"(?:cierra|cerra|cerrar|cerrame|cierrame|cierres|close|cierralo|cierrala|cerrala|cerralo)")
        and (
            has_named_window_target(folded)
            or _authenticated_application_close_target(folded, application_names) is not None
            or (
                _has(folded, r"\b(?:cierra|cerra|cerrar|close)\b")
                and _has(
                    folded,
                    rf"^[¿?¡!\s]*(?:cierra|cerra|cerrar|close)\s+"
                    rf"(?:(?:la|the)\s+)?(?:(?:ventana|window)\s+(?:de|of)\s+)?"
                    rf"(?:{_KNOWN_APPLICATION})"
                    r"(?:\s+(?:ventana|window|aplicacion|application|app))?"
                    r"[\s?!.]*$|"
                    r"^[¿?¡!\s]*(?:cierra|cerra|cerrar|close)\s+"
                    r"(?:(?:la|the)\s+)?(?:aplicacion|application|app|programa|program)\s+"
                    r"[a-z0-9][a-z0-9 ._+-]{0,100}[\s?!.]*$",
                )
            )
            or _has(
                folded,
                r"^[¿?¡!\s]*(?:cierra|cerra|cerrar|close)\s+"
                r"(?:(?:la|the)\s+)?(?:"
                r"(?:ventana|window)\s+(?:activa|active|actual|current)|"
                r"(?:active|current)\s+window"
                r")[\s?!.]*$",
            )
            or deictic_close_request(folded)
            or (
                context_open_application
                and _has(
                    folded,
                    r"^(?:cierralo|cierrala|close it)[\s?!.]*$",
                )
            )
        )
        and not _has(
            folded, r"\b(?:forzar|force|kill|termina el proceso|terminate process)\b"
        )
    ):
        _append(
            matches,
            folded,
            "app.close",
            r"\b(?:cierra|cerra|cerrar|cerrame|cierrame|cierres|close|cierralo|cierrala|cerrala|cerralo)\b",
        )

    for pattern, operation in (
        (r"\b(?:maximiza|maximizar|maximize)\b", "window.maximize"),
        (r"\b(?:minimiza|minimizar|minimize)\b", "window.minimize"),
        (r"\b(?:restaura|restaurar|restore)\b", "window.restore"),
    ):
        if (
            _head_is(
                head,
                r"(?:maximiza|maximizar|maximize|minimiza|minimizar|minimize|"
                r"restaura|restaurar|restore)",
            )
            and _has(folded, pattern)
            and (
                _window_domain(folded)
                or (
                    context_window_active
                    and _has(
                        folded,
                        r"^(?:maximiza|maximizar|maximize|minimiza|minimizar|"
                        r"minimize|restaura|restaurar|restore)[\s?!.]*$",
                    )
                )
            )
        ):
            _append_all(matches, folded, operation, pattern)
    if not any(
        entry[2] in {"window.maximize", "window.minimize", "window.restore"}
        for entry in matches
    ) and _has(folded, r"\b(?:ventana|window)\b"):
        if _has(
            folded,
            r"\b(?:hazme|make|pon)\b.{0,24}\bgrande\b.{0,24}"
            r"\b(?:ventana|window)\b|"
            r"\b(?:hazme|make|pon)\b.{0,24}\b(?:ventana|window)\b.{0,24}"
            r"\bgrande\b",
        ):
            _append(
                matches,
                folded,
                "window.maximize",
                r"\b(?:grande|maximize)\b",
            )
        elif _has(
            folded,
            r"\b(?:taskbar|barra\s+de\s+tareas)\b",
        ) and _has(
            folded,
            r"\b(?:abajo|down|send|manda|minimiza|minimize)\b",
        ):
            _append(
                matches,
                folded,
                "window.minimize",
                r"\b(?:taskbar|barra\s+de\s+tareas)\b",
            )
        elif _has(
            folded,
            r"\b(?:tamano|size)\s+normal\b|"
            r"\b(?:tamano|size)\s+(?:original|usual|regular)\b",
        ):
            _append(
                matches,
                folded,
                "window.restore",
                r"\b(?:tamano|size)\b",
            )
    window_mutations = [
        entry
        for entry in matches
        if entry[2]
        in {
            "window.maximize",
            "window.minimize",
            "window.restore",
        }
    ]
    if window_mutations and (
        _has(
            folded,
            r"\b(?:activa|active|actual|current)\b",
        )
        or deictic_window_mutation(folded)
        or context_window_active
    ):
        matches.append(
            (min(entry[0] for entry in window_mutations), -1, "window.active")
        )
    elif (
        not window_mutations
        and _window_domain(folded)
        and _has(folded, r"\b(?:activa|active|actual|current)\b")
        and _has(folded, r"\b(?:que|cual|what|dime)\b")
    ):
        _append(matches, folded, "window.active", r"\b(?:ventana|window)\b")


def _review_input_and_capture_effects(
    matches: list[tuple[int, int, str]],
    folded: str,
    head: str,
    *,
    context_capture: bool,
    context_open_application: bool,
) -> None:
    """Append keyboard, clipboard, screenshot, and OCR effects."""

    if _head_is(head, r"(?:dale|press|hit)") and _has(
        folded,
        r"\b(?:dale|press|hit)\s+(?:enter|intro|return)\b",
    ):
        _append(
            matches,
            folded,
            "input.key.press",
            r"\b(?:enter|intro|return)\b",
        )
    if (
        _head_is(head, r"(?:escribe|escribir|escribi|type)")
        and _has(folded, r"\b(?:escribe|escribir|escribi|type)\b")
        and (
            _has(folded, r"\b(?:literalmente|literally)\b")
            or context_open_application
            or _has(
                folded,
                r"\b(?:en|into|in)\s+(?:la\s+|the\s+)?"
                r"(?:busqueda|search|campo|field|cuadro|box|control)\b",
            )
            or _has(
                folded,
                r"\b(?:type|escribe|escribi)\s+\S.{0,80}\b(?:for\s+me|por\s+mi)\b",
            )
        )
    ):
        _append(
            matches,
            folded,
            "input.text.type",
            r"\b(?:escribe|escribir|escribi|type)\b",
        )
    if _head_is(head, r"(?:selecciona|seleccionar|select)") and _has(
        folded, r"\b(?:selecciona|seleccionar|select)\s+(?:todo|all)\b"
    ):
        _append(
            matches,
            folded,
            "input.select.all",
            r"\b(?:selecciona|seleccionar|select)\b",
        )
    if (
        _head_is(head, _OPEN)
        and _has(folded, r"\b(?:teclado en pantalla|on[ -]screen keyboard)\b")
        and _has(folded, rf"\b{_OPEN}\b")
    ):
        _append(
            matches,
            folded,
            "input.keyboard.open",
            r"\b(?:teclado en pantalla|on[ -]screen keyboard)\b",
        )
    if (
        _head_is(head, _READ)
        and _has(folded, r"\b(?:portapapeles|clipboard)\b")
        and _has(folded, rf"\b{_READ}\b")
    ):
        _append(
            matches,
            folded,
            "clipboard.read.text",
            r"\b(?:portapapeles|clipboard)\b",
        )
    if _has(folded, r"\b(?:portapapeles|clipboard)\b") and _has(
        folded,
        r"^(?:que hay|que tengo|what(?:'s| is)(?: there)?|dime que hay)\b",
    ):
        _append(
            matches,
            folded,
            "clipboard.read.text",
            r"\b(?:portapapeles|clipboard)\b",
        )
    if _has(
        folded,
        r"^(?:what\s+did\s+i\s+copy(?:\s+last)?|"
        r"last\s+(?:thing\s+)?(?:i\s+)?copied|"
        r"que\s+(?:fue\s+lo\s+que\s+)?(?:copie|copié)\s+"
        r"(?:ultimo|ayer|recien|last))\b",
    ):
        _append(
            matches,
            folded,
            "clipboard.read.text",
            r"\b(?:copy|copied|copie|copié)\b",
        )
    if (
        _head_is(head, r"(?:pega|pegar|pegalo|pegala|paste)")
        and _has(folded, r"\b(?:pega|pegar|pegalo|pegala|paste)\b")
        and _clipboard_paste_domain(folded)
    ):
        paste = _match(folded, r"\b(?:pega|pegar|pegalo|pegala|paste)\b")
        if paste is not None and _has(
            folded,
            rf"\b(?:en|into)\b.{{0,80}}\b(?:archivo\s+nuevo|new\s+file)\b"
            rf".{{0,80}}\b(?:{_KNOWN_APPLICATION})\b",
        ):
            matches.append((paste.start(), -1, "app.open"))
        _append(
            matches,
            folded,
            "clipboard.paste",
            r"\b(?:pega|pegar|pegalo|pegala|paste)\b",
        )
    if _head_is(head, r"(?:copia|copiar|copy)") and _clipboard_copy_domain(folded):
        _append(matches, folded, "clipboard.copy", r"\b(?:copia|copy)\b")
    active_window_capture = (
        _head_is(head, r"(?:captura|capture|toma|tomar|take)")
        and _has(folded, r"\b(?:captura|capture|toma|tomar|take)\b")
        and _has(
            folded,
            r"\b(?:ventana\s+(?:activa|actual)|active\s+window|current\s+window)\b",
        )
    )
    if active_window_capture:
        _append(
            matches,
            folded,
            "capture.active.window",
            r"\b(?:captura|capture|toma|tomar|take)\b",
        )
    capture_object = _has(
        folded,
        r"\b(?:captura de (?:toda )?la pantalla|captura de pantalla|"
        r"foto de captura|pantallazo|screenshot|screen capture)\b",
    ) or (_has(folded, r"\b(?:captura|capture)\b") and _has(folded, r"\bocr\b"))
    capture_requested = (
        capture_object
        and _has(
            folded,
            (
                r"^[¿?¡!\s]*(?:(?:por favor|please)\s*[,;:]?\s*|"
                r"(?:puedes|podrias|can you|could you|would you)\s+)?"
                r"(?:haz|hacer|toma|tomar|saca|sacale|crea|capture|take)\s+"
                r"(?:(?:una|un|a|the)\s+)?"
                r"(?:foto de captura|captura|pantallazo|screenshot|screen capture)\b"
            ),
        )
        and not active_window_capture
    )
    if capture_requested:
        _append(
            matches,
            folded,
            "capture.screenshot",
            r"\b(?:foto de captura|captura|pantallazo|screenshot|screen capture)\b",
        )
        if _has(
            folded,
            r"\b(?:que\s+se\s+ve|what(?:'s| is)\s+visible|"
            r"describe(?:me)?|describe it|que hay en la imagen)\b",
        ) and not _has(folded, r"\blo que ves\b|\bque ves\b|\bwhat you see\b"):
            # SCREEN1485: «describeme lo que ves» after a capture is the
            # screen-content reading below, not an image description.
            _append(
                matches,
                folded,
                "vision.describe",
                r"\b(?:que\s+se\s+ve|what(?:'s| is)\s+visible|"
                r"describe(?:me)?|describe it|que hay en la imagen)\b",
                priority=1,
            )
    # SCREEN1417 «leé la pantalla», «qué hay en la pantalla», «describime la
    # pantalla», «qué ves en mi pantalla»: without a vision provider the truthful
    # reading of a screen is its recognized text, which the composer frames as
    # what it can read. The phone/car exclusion below still applies.
    bare_screen_read = (
        _head_is(head, _READ)
        and _has(folded, r"^[¿?¡!\s]*(?:por favor\s*[,:]?\s*)?(?:lee|leer|leeme|read)\s+(?:me\s+)?(?:la|mi|the|my)\s+(?:pantalla|screen)[\s?!.]*$")
    )
    screen_content_question = _has(
        folded,
        r"^[¿?¡!\s]*(?:(?:decime|dime|contame|cuentame|tell me)\s+)?"
        r"(?:que|what)\s+(?:hay|se ve|aparece|ves|estas viendo|is|is there|do you see|are you seeing|can you see)"
        r"(?:\s+(?:ahora|now))?\s+(?:en|on)\s+(?:mi|la|tu|my|the)\s+(?:pantalla|screen)[\s?!.]*$|"
        r"^[¿?¡!\s]*(?:describe|describi|describime|describeme|describi?la|describila)\s+"
        r"(?:(?:mi|la|my|the)\s+(?:pantalla|screen)|lo que ves(?:\s+(?:en|on)\s+(?:mi|la|my|the)\s+(?:pantalla|screen))?|"
        r"what you see(?:\s+on\s+(?:my|the)\s+screen)?)[\s?!.]*$|"
        # SCREEN1485 «Toma un screenshot de la pantalla ahora mismo y describeme
        # lo que ves»: a capture order followed by the description of what is
        # seen is the same screen-content reading.
        r"^[¿?¡!\s]*(?:toma|tomame|saca|sacame|hace|haceme|haz|hazme|take|capture)\s+(?:(?:un|una|a)\s+)?"
        r"(?:screenshot|screen\s*shot|screen\s+capture|captura(?:\s+de\s+pantalla)?|pantallazo)"
        r"(?:\s+(?:de|of)\s+(?:la|mi|the|my)\s+(?:pantalla|screen))?(?:\s+(?:ahora(?:\s+mismo)?|now|right\s+now))?"
        r"\s*(?:,\s*|\s+(?:y|and)\s+)(?:describe|describi|describime|describeme|decime|dime|contame|cuentame|tell\s+me)\s+"
        r"(?:lo\s+que\s+ves|que\s+ves|que\s+hay|what\s+you\s+see|what(?:'s|\s+is)\s+(?:there|on\s+it))"
        r"(?:\s+(?:en|on)\s+(?:mi|la|my|the)\s+(?:pantalla|screen))?[\s?!.]*$",
    )
    implicit_screen_read = (
        (
            _head_is(head, _READ)
            and _has(folded, r"\b(?:pantalla|screen)\b")
            and _has(
                folded,
                r"\b(?:mensaje|message|error|texto|text|lo que|what)\b",
            )
        )
        or bare_screen_read
        or screen_content_question
    ) and (
        not _has(
            folded,
            r"\b(?:como|how)\s+(?:puedo|podria|can i|could i|to)\b",
        )
        and not _has(
            folded,
            r"\b(?:pantalla|screen)\s+(?:del|de mi|of my)\s+"
            r"(?:telefono|celular|movil|phone|smartphone|tablet|auto|car)\b",
        )
    )
    if implicit_screen_read:
        if not any(operation == "capture.screenshot" for _, _, operation in matches):
            # SCREEN1485: an explicit capture order («Toma un screenshot … y
            # describeme lo que ves») already appended the capture above.
            _append(
                matches,
                folded,
                "capture.screenshot",
                rf"\b{_READ}\b|\b(?:que|what|describ\w*)\b",
            )
        _append(
            matches,
            folded,
            "ocr.read",
            r"\b(?:pantalla|screen)\b|\blo que ves\b|\bwhat you see\b",
            priority=1,
        )
    if context_capture and _has(
        folded,
        r"^(?:describe|describelo|describela)"
        r"(?:\s+(?:it|that|the|same|esto|eso|esa|la|misma))?"
        r"(?:\s+(?:scene|image|capture|escena|imagen|captura|vista))?"
        r"[\s?!.]*$",
    ):
        _append(
            matches,
            folded,
            "vision.describe",
            r"\b(?:describe|describelo|describela)\b",
        )
    contextual_capture_read = (
        context_capture
        and _head_is(head, _READ)
        and _has(folded, r"\b(?:text|texto|words?|palabras?)\b")
        and _has(
            folded,
            r"\b(?:image|imagen|capture|captura|screenshot|screen|pantalla)\b",
        )
        and _has(
            folded,
            r"\b(?:that|same|the|esa|misma|la|from|de|en)\b",
        )
    )
    if contextual_capture_read:
        _append(matches, folded, "ocr.read", rf"\b{_READ}\b", priority=1)
    ocr_requested = (
        _head_is(head, _READ)
        and _has(
            folded,
            rf"^[¿?¡!\s]*(?:(?:por favor|please)\s*[,;:]?\s*|"
            rf"(?:puedes|podrias|can you|could you|would you)\s+)?"
            rf"{_READ}\b.{{0,80}}\bocr\b",
        )
        and not _has(
            folded,
            r"\b(?:nota|note|tarea|task|portapapeles|clipboard|pagina|page)\b",
        )
    ) or (
        capture_requested
        and _has(
            folded,
            r"\b(?:y|and)\s+(?:leela|leelo|leerla|leerlo|read it)\s+"
            r"(?:con|with)\s+ocr\b",
        )
    )
    if ocr_requested and (capture_requested or context_capture):
        _append(matches, folded, "ocr.read", r"\bocr\b", priority=1)


def _location_recommendation_request(text: str) -> bool:
    """Recognize a standalone request for public place recommendations."""

    return _has(
        text,
        r"^[^\w]*(?:lugares?|sitios?)\s+(?:para|a\s+donde)\s+"
        r"(?:ir|salir|comer|visitar)\b.+|"
        r"^[^\w]*(?:places?|restaurants?|things?)\s+to\s+"
        r"(?:go|visit|eat|do)\b.+",
    )


def _symbolic_web_destination(text: str) -> str | None:
    """Preserve a public site operand without manufacturing its URL."""

    request = _strip_request_envelope(text)
    desired = _explicit_desire_request(request)
    if desired is not None:
        request = request[desired.start("body"):]
    found = re.fullmatch(
        r"[¿?¡!\s]*(?:(?:ve|and[aá]|entra|entr[aá]|entrar|ir|navega|navegar|"
        r"llevame|llévame)\s+a(?:l)?\s+|(?:go|navigate)\s+to\s+|"
        r"take\s+me\s+to\s+|(?:abre|abr[ií]|abrir|open)\s+"
        # WEB1477 H0082 «Abre la p?gina oficial de OpenAI»: a corrupted
        # character inside «página» is a transcription glitch, not another word.
        r"(?=(?:(?:la|el|the|a)\s+)?(?:p[aá?]gina|page|sitio|site|website|portal)\b))"
        r"(?P<target>\S.+?)[\s.!?]*",
        request, re.IGNORECASE,
    )
    if found is None:
        return None
    folded = _fold(text)
    if (
        explicit_non_action_frame(text)
        or _is_meta_or_tool_denial(folded)
        or _is_past_or_hypothetical_state(folded)
        or _has_unsupported_deferred_effect(folded)
        or _has_contradictory_correction(folded)
        or len(_request_clauses(folded)) != 1
        or _named_browser(folded) is not None
        or client_navigation_target(folded) is not None
        or _has(folded, r"https?://|\b(?:[a-z0-9-]+\.)+[a-z]{2,63}\b")
        or _has(folded, r"\b(?:archivos?|files?|carpetas?|folders?|documentos?|"
                r"documents?|descargas|downloads?|escritorio|desktop|notas?|notes?|"
                r"tareas?|tasks?|recordatorios?|reminders?|ventanas?|windows?|"
                r"aplicaciones?|applications?|apps?)\b")
    ):
        return None
    # Courtesy and the site-role noun are syntax around the public name, not
    # required result terms. Keep all authority/privacy checks on original text.
    operand = re.sub(
        r",\s*(?:por\s+favor|please)[\s.!?]*$", "", found.group("target"),
        count=1, flags=re.IGNORECASE,
    ).strip()
    target = re.sub(
        r"^(?:(?:la|el|the|a)\s+)?(?:(?:p[aá?]gina|page|sitio|site)"
        r"(?:\s+web)?|website)"
        r"(?:\s+(?:oficial|official|principal|main|home))?\s+(?:(?:de|of)\s+)?",
        "", operand, count=1, flags=re.IGNORECASE,
    ).strip()
    possessive = re.fullmatch(
        r"(?P<name>\S.+?)(?:['’]s|['’])\s+"
        r"(?:(?:official|main|home)\s+)?(?:website|site|web\s+site|page)",
        target, re.IGNORECASE,
    )
    if possessive is not None:
        target = possessive.group("name")
    target = _bounded_application_literal(target)
    if target is None or _has(
        _fold(target),
        r"^(?:(?:la|el|the|a|esta|esa|this|that)\s+)?"
        r"(?:pagina|page|sitio|site|website|portal|alli|ahi|there|it)$",
    ):
        return None
    # Reuse public-query privacy and single-clause guards on the literal operand.
    return _direct_public_search_query("busca " + target)


def _direct_public_search_query(text: str) -> str | None:
    """Read one authoritative public query, preserving its original spelling."""

    match = re.fullmatch(
        rf"[¿?¡!\s]*{_REQUEST_PREFIX}{_SEARCH}(?:\s+for)?\s+"
        r"(?P<query>\S.*)",
        _strip_request_envelope(text),
        re.IGNORECASE,
    )
    if match is None:
        return None
    query = match.group("query").strip(" \t.,;:!?\"'“”«»")
    folded = _fold(text)
    if (
        not query
        or _has(_fold(query), r"^(?:for|en|on)[.!?]*$")
        or not effect_request_is_authoritative(text)
        or len(_request_clauses(folded)) != 1
        or _has(
            folded,
            r"\b(?:mi|mis|my|our|nuestros?|nuestras?|tus?|your|"
            r"privad[oa]s?|private|local(?:es|ly)?|portapapeles|clipboard|"
            r"contrasenas?|passwords?|correos?|emails?|mensajes?|messages?)\b|"
            r"\b[a-z]:[\\/]|\\\\",
        )
    ):
        return None
    return query


def _named_browser_search(text: str) -> tuple[str, str] | None:
    """Bind a public query and browser within one complete current request."""

    folded = _fold(text)
    if (
        len(text) > 16_384
        or explicit_non_action_frame(text)
        or _is_past_or_hypothetical_state(folded)
        or _has_unsupported_deferred_effect(folded)
        or _is_meta_or_tool_denial(folded)
        or _has_contradictory_correction(folded)
        or _has(folded, r"\b(?:archivo|file|carpeta|folder|documentos?|documents?|"
                r"descargas|downloads?|escritorio|desktop|notas?|notes?|"
                r"tareas?|tasks?|recordatorios?|reminders?|aplicaciones?\s+"
                r"instaladas?|installed\s+applications?|installed\s+apps?)\b")
    ):
        return None
    clauses = _request_clauses(_strip_request_envelope(text))
    if not 1 <= len(clauses) <= 2:
        return None
    query = _direct_public_search_query(clauses[-1])
    if query is None:
        return None
    scope = _named_browser_match(query)
    browser = _named_browser(query)
    if scope is not None:
        if scope.end() != len(query):
            return None
        query = query[:scope.start()].strip()
    if len(clauses) == 2:
        opening = _application_open_request(_fold(clauses[0]))
        if opening is not None and effect_request_is_authoritative(clauses[0]):
            opening_target = "in " + opening.group("target").rstrip(".!?")
            opened_scope = _named_browser_match(opening_target)
            opened = _named_browser(opening_target)
            if (
                opened_scope is None
                or opened_scope.start() != 0
                or opened_scope.end() != len(opening_target)
                or (browser is not None and browser != opened)
            ):
                return None
            browser = opened
        else:
            # Only a literal nominal desire immediately before this search
            # supplies its pronoun's antecedent; no history or model guess.
            antecedent = re.fullmatch(
                r"(?:i\s+(?:need|want)|necesito|quiero)\s+(?P<query>.+)",
                clauses[0].strip(), re.IGNORECASE,
            )
            if antecedent is None or _fold(query) not in {"it", "them", "that", "eso", "esto"}:
                return None
            query = antecedent.group("query").strip()
            if (
                _has(_fold(query), rf"^(?:to\s+)?(?:{_COVERAGE_ACTION_HEAD})\b")
                or _direct_public_search_query("search for " + query) is None
            ):
                return None
    if (
        browser not in NAMED_CDP_BROWSERS
        or not query
        or _fold(query) in {"it", "them", "that", "eso", "esto"}
        or len(query.encode("utf-8")) > 512
        or any(ord(character) < 32 for character in query)
        or _explicit_google_search_query("search " + query) is not None
    ):
        return None
    return browser, query


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


def _explicit_google_search_query(text: str) -> str | None:
    """Read an explicit Google search without folding its literal query."""

    prefix = rf"[¿?¡!\s]*{_REQUEST_PREFIX}"
    search = rf"(?:search(?:\s+for)?|{_SEARCH}|buscá)\s+"
    for body in (
        search + r"(?P<query>.+?)\s+(?:en|on)\s+google[.!?]*",
        search + r"(?:en|on)\s+google\s+(?P<query>.+)",
        rf"(?:en|on)\s+google\s*,\s*{_REQUEST_PREFIX}"
        + search + r"(?P<query>.+)",
    ):
        match = re.fullmatch(prefix + body, text.strip(), re.IGNORECASE)
        if match is None:
            continue
        query = match.group("query").strip()
        if (
            query
            and len(query.encode("utf-8")) <= 512
            and not any(ord(character) < 32 for character in query)
        ):
            return query
    return None


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


def _review_media_and_email_effects(
    matches: list[tuple[int, int, str]],
    folded: str,
    head: str,
    *,
    audio_level: bool,
    context_spotify: bool,
) -> None:
    """Append Spotify/media controls and read-only email effects."""

    spotify_target = _has(folded, r"\b(?:en|on)\s+spotify\b")
    spotify = spotify_target or context_spotify
    change_current_artist = _has(
        folded,
        r"^[^\w]*(?:(?:por favor|please)\s*[,;:]?\s*)?"
        r"(?:cambia|cambiar|change|switch)\s+"
        r"(?:(?:el|la|the|current|actual)\s+)?(?:artista|artist)"
        r"(?:\s*[,;:]?\s*(?:por favor|please))?[\s.!?]*$",
    )
    media_transport = _media_transport_action(folded)
    audio_media_setting = _has(
        folded,
        (
            r"\b(?:volumen|volume|audio|sonido|sound)\b"
            r".{0,60}(?:\b\d{1,3}\b|%)"
        ),
    )
    resume_existing_media = _resume_existing_media(folded)
    exact_play = (
        spotify
        and not audio_media_setting
        and _has(
            folded,
            r"\b(?:exactamente|exactly|exact|exacta)\b",
        )
        and _head_is(
            head,
            r"(?:reproduce|reproducir|play|pon)",
        )
        and _has(folded, r"\b(?:reproduce|reproducir|play|pon)\b")
    )
    if _explicit_named_music_query(folded) is not None and _desired_music_query(folded) is not None:
        # MUSIC1559: music named without a provider («pon música de daft punk»)
        # plays from YouTube in the local player; «en Spotify» keeps Spotify.
        _append(
            matches, folded, "media.play.query" if spotify else "media.play.youtube",
            r"\b(?:pon|ponme|poneme|pone|reproduce|reproducir|reproduci|play|toca|tocame|toque)\b",
        )
    elif _desired_music_query(folded) is not None:
        _append(
            matches,
            folded,
            "media.play.query",
            r"\b(?:need|want|necesito|quiero)\b",
        )
    elif _spoken_radio_station_request(folded):
        _append(
            matches,
            folded,
            "media.play.query",
            r"\b(?:pon|ponme|pone|poneme|reproduce|reproducir|play|start|inicia|tune)\b",
        )
    elif _bare_spoken_number_media_query(folded) is not None:
        _append(
            matches,
            folded,
            "media.play.query",
            r"\b(?:pon|ponme|pone|poneme|reproduce|reproducir|play)\b",
        )
    elif exact_play:
        _append(
            matches,
            folded,
            "media.play.exact",
            r"\b(?:reproduce|reproducir|play|pon)\b",
        )
    elif (
        (
            _head_is(
                head,
                rf"(?:{_SEARCH}|reproduce|reproducir|reproduzca|play|pon|ponme)",
            )
            and not (_head_is(head, r"(?:pon|poner|ponme)") and audio_level)
            and not audio_media_setting
            and not resume_existing_media
            and spotify_target
            and _has(
                folded,
                rf"\b{_SEARCH}\b|"
                r"\b(?:reproduce|reproducir|reproduzca|play|pon|ponme)\b",
            )
        )
        or (
            _head_is(head, r"(?:reproduce|reproducir|reproduzca|play|pon)")
            and context_spotify
            and not resume_existing_media
            and _has(folded, r"\b(?:reproduce|reproducir|play|pon)\b")
        )
        or (
            _head_is(head, r"(?:reproduce|reproducir|reproduzca|play|pon)")
            and _media_play_domain(folded)
            and not resume_existing_media
            and not media_transport
            and not _has(folded, r"\byoutube\b")
            and _has(
                folded,
                r"^[¿?¡!\s]*(?:(?:por favor|please)\s*[,;:]?\s*)?"
                r"(?:reproduce|reproducir|reproduzca|play|pon)\s+\S.+",
            )
        )
    ):
        _append(
            matches,
            folded,
            "media.play.query",
            rf"\b{_SEARCH}\b|\b(?:reproduce|reproducir|play|pon)\b",
        )
    if (
        _head_is(head, r"(?:reproduce|reproducir|reproduzca|play|pon)")
        and _has(folded, r"\byoutube\b")
        and not _has(
            folded,
            r"\b(?:primer|primero|first|segundo|second|tercer|third|"
            r"resultado|result)\b",
        )
        and not resume_existing_media
        and not media_transport
        and _has(folded, r"\b(?:reproduce|reproducir|play|pon)\b")
    ):
        _append(
            matches,
            folded,
            "media.play.youtube",
            r"\b(?:reproduce|reproducir|play|pon)\b",
        )
    if (
        media_transport
        or change_current_artist
        or resume_existing_media
        or (
            _head_is(
                head,
                r"(?:pausa|pausar|pause|deten|detener|stop|siguiente|next|anterior|previous|"
                r"reanuda|reanudar|resume|reproduce|reproducir|reproduzca|play)",
            )
            and _has(
                folded,
                r"\b(?:pausa|pausar|pause|deten|detener|stop|siguiente|next|anterior|previous|"
                r"reanuda|reanudar|resume|reproduce|reproducir|reproduzca|play)\b",
            )
            and (
                spotify
                or _has(
                    folded,
                    r"\b(?:audio|media|musica|music|reproduccion|playback)\b",
                )
                or exact_play
            )
            and not _has(
                folded,
                r"\b(?:grabacion|recording|microfono|microphone|mic)\b",
            )
            and (
                not _head_is(
                    head,
                    r"(?:reanuda|reanudar|resume|reproduce|reproducir|reproduzca|play)",
                )
                or resume_existing_media
            )
        )
    ):
        _append(
            matches,
            folded,
            "media.control",
            (
                r"\b(?:siguiente|next|anterior|previous|viene|sigue|antes|forward|back|deten(?:e|er)?|para|parar|stop)\b"
                if media_transport
                else r"\b(?:cambia|cambiar|change|switch)\b"
                if change_current_artist
                else rf"\b(?:{_MEDIA_RESUME_VERB}|reproduce|reproducir|reproduzca|play)\b"
                if resume_existing_media
                else r"\b(?:pausa|pausar|pause|deten|detener|stop|siguiente|next|anterior|previous|"
                r"reanuda|reanudar|resume|reproduce|reproducir|reproduzca|play)\b"
            ),
            priority=1,
        )
    if (
        not any(entry[2] == "media.control" for entry in matches)
        and (
            _head_is(head, r"(?:para|pausa|pausar|pause|deten|detener|stop)")
            or (
                _head_is(head, r"(?:deja|dejar)")
                and _has(folded, r"\b(?:deja|dejar)\s+en\s+pausa\b")
            )
        )
        and _has(
            folded,
            r"\b(?:sonando|playing|reproduciendo|cancion|song|pista|track|"
            r"lo\s+que\s+esta\s+sonando)\b",
        )
        and not _has(
            folded,
            r"\b(?:alarma|alarm|grabacion|recording|microfono|microphone|mic)\b",
        )
    ):
        _append(
            matches,
            folded,
            "media.control",
            r"\b(?:deja\s+en\s+pausa|dejar\s+en\s+pausa|"
            r"para|pausa|pausar|pause|deten|detener|stop)\b",
        )
    if (
        not any(entry[2] == "media.control" for entry in matches)
        and _head_is(head, r"(?:pasa|pasar|skip|siguiente|next)")
        and _has(
            folded,
            r"\b(?:siguiente|next|anterior|previous)\b",
        )
        and _has(
            folded,
            r"\b(?:cancion|song|pista|track|musica|music|tema)\b",
        )
    ):
        _append(
            matches,
            folded,
            "media.control",
            r"\b(?:pasa|pasar|skip|siguiente|next)\b",
        )
    if (
        _head_is(head, r"(?:que|what|cual|which|dime|show|muestra)")
        and _has(folded, r"\b(?:musica|music|cancion|song)\b")
        and not _has(
            folded,
            r"\b(?:en|inside)\s+(?:mi|my)\s+(?:cabeza|mente|head|mind)\b",
        )
        and _has(folded, r"\b(?:sonando|playing|reproduciendo)\b")
    ):
        _append(matches, folded, "media.status", r"\b(?:musica|music|cancion|song)\b")
    if (
        _head_is(head, _READ)
        and _latest_email_domain(folded)
        and _has(folded, rf"\b{_READ}\b")
    ):
        _append(
            matches,
            folded,
            "email.latest.read",
            r"\b(?:correo|email|mail)\b",
        )


def _resolve_explicit_effects_single(
    text: str,
    available_operations: Iterable[str],
    *,
    context_browser: str | None = None,
    context_spotify: bool = False,
    context_open_application: bool = False,
    context_capture: bool = False,
    context_note: bool = False,
    context_audio: bool = False,
    context_machine: bool = False,
    context_window_active: bool = False,
    application_names: Iterable[str] = (),
) -> EffectIntent | None:
    """Resolve effects inside one request clause with bounded prior context."""

    folded = _fold(text)
    desired = _explicit_desire_request(folded)
    if desired is not None:
        # This clause is now being read for effects. Keep the original need
        # frame visible to the earlier conversation/clarification readers;
        # only anchored operation matchers consume the explicit action body.
        folded = desired.group("body")
    available = frozenset(available_operations)
    authenticated_request = _authenticated_application_request(
        folded,
        application_names,
    )
    if authenticated_request is not None and not _is_builtin_keyboard_request(folded):
        operation, targets = authenticated_request
        if operation not in available or len(targets) > 8:
            return None
        return EffectIntent(
            tuple(operation for _ in targets),
            tuple(target for _, target in targets),
        )
    desired_open = _authenticated_application_desired_open(
        folded,
        application_names,
    )
    if desired_open is not None and "app.open" in available:
        return EffectIntent(("app.open",), (desired_open[1],))
    in_application = _click_in_application(folded, application_names)
    if in_application is not None and {"app.open", "input.visible.click"} <= available:
        # UI1735 «en <app> hacé clic en X», «ve a X en <app>» (owner: general
        # mechanisms): the application is opened or brought to the front
        # (app.open reuses a running window) and the visible label is clicked
        # on it; any Start-catalog application, any label.
        application, clause = in_application
        clause_click = _visible_click_intent(clause, available, allow_navigate=True)
        if clause_click is not None:
            return EffectIntent(("app.open", "input.visible.click"), (application, clause_click.evidence[0]))
    visible_click = _visible_click_intent(
        folded,
        available,
        allow_navigate=context_open_application,
    )
    if visible_click is not None:
        return visible_click
    strict_request = _strict_catalog_request(
        folded,
        available,
        application_names,
    )
    if strict_request is not None:
        return strict_request
    if (
        not folded
        or len(folded) > 16_384
        or _is_meta_or_tool_denial(folded)
        or _has_contradictory_correction(folded)
        or (
            _has_unsupported_deferred_effect(folded)
            and not _location_recommendation_request(folded)
        )
        or not (
            _is_direct_request(_without_leading_duration_preface(folded))
            or _count_down_request(folded)
            or _bounded_calendar_list_query(folded)
            or _location_recommendation_request(folded)
            or (
                _has(folded, r"^can i (?:see|view)\b")
                and _has(folded, r"\b(?:reminder|recordatorio)\b")
                and _has(folded, r"\b(?:again|otra vez|de nuevo)\b")
            )
            or (
                context_audio
                and (
                    _has(
                        folded,
                        r"^(?:al?|to)?\s*\d{1,3}\s*(?:%|por ciento|percent)?\b",
                    )
                    or _has(
                        folded,
                        r"^(?:reactiva(?:lo|la)?|unmute(?: it)?|quita(?:r)? el silencio)[\s?!.]*$",
                    )
                )
            )
            or (
                context_open_application
                and _has(
                    folded,
                    rf"^(?:el|la|the)?\s*{_KNOWN_APPLICATION}[\s?!.]*$",
                )
            )
            or (
                context_note
                and _has(
                    folded,
                    r"^(?:otra|otro|another)\b",
                )
            )
            or (
                context_capture
                and _has(
                    folded,
                    r"^(?:describe|describelo|describela|describe it)[\s?!.]*$",
                )
            )
        )
    ):
        return None

    matches: list[tuple[int, int, str]] = []
    head = _request_head(folded)

    _review_system_and_network_effects(matches, folded, head)
    if (
        context_machine
        and "system.process.list" in available
        and not any(operation == "system.process.list" for _, _, operation in matches)
        and _head_is(head, r"(?:lista|listar|muestra|muestrame|show|list)")
        and _has(folded, r"\b(?:procesos?|processes)\b")
        and not _has(
            folded,
            r"\b(?:biologic[oa]s?|biological|celular(?:es)?|cellular|"
            r"metabolic[oa]s?|metabolic|contratacion|hiring|reclutamiento|"
            r"recruitment|empresa|business|negocio|fabricacion|manufacturing)\b",
        )
    ):
        _append(
            matches,
            folded,
            "system.process.list",
            r"\b(?:procesos?|processes)\b",
        )

    audio_level = _review_audio_effects(
        matches,
        folded,
        head,
        context_audio=context_audio,
    )

    _review_installed_catalog_effects(
        matches,
        folded,
        application_names=application_names,
    )
    _review_file_and_game_effects(matches, folded, head)
    _review_application_and_window_effects(
        matches,
        folded,
        head,
        application_names=application_names,
        context_open_application=context_open_application,
        context_window_active=context_window_active,
    )

    _review_input_and_capture_effects(
        matches,
        folded,
        head,
        context_capture=context_capture,
        context_open_application=context_open_application,
    )

    # Bind local-data verbs to the closest following domain noun. This avoids
    # turning incidental words ("a note about my tasks") into extra effects.
    web_search_requested = _review_local_data_effects(
        matches,
        folded,
        head,
        context_note=context_note,
    )
    _review_calendar_message_and_direct_reminder_effects(
        matches,
        folded,
        head,
    )
    _review_web_and_browser_effects(
        matches,
        folded,
        head,
        context_browser=context_browser,
        web_search_requested=web_search_requested,
    )

    _review_media_and_email_effects(
        matches,
        folded,
        head,
        audio_level=audio_level,
        context_spotify=context_spotify,
    )

    return _finalize_effect_matches(folded, matches, available)


def _request_clauses(text: str) -> tuple[str, ...]:
    if _literal_note_payload_request(text):
        # Actions mentioned after the content marker remain stored text.
        return (text.strip(),)
    if window_inventory_arguments(text) is not None:
        # A complete inventory topic plus "list them" is one request. The
        # closed reader rejects extra actions before preserving this span.
        return (text.strip(),)
    if _LEADING_DURATION_PREFACE.match(_fold(text)) is not None and len(
        _request_clauses(_without_leading_duration_preface(_fold(text)))
    ) == 1:
        # A leading duration belongs to the scheduling request that follows it.
        return (text.strip(),)
    action_after_clause = _COVERAGE_ACTION_HEAD
    # Ordinal discourse markers describe the order of the first real action;
    # they are not standalone clauses.  Only strip them when a known effect
    # head follows, so literal content beginning with "primero" remains data.
    text = re.sub(
        rf"^[¿?¡!\s]*(?:primero|first)\s*[,;:][¿?¡!\s]*"
        rf"(?=(?:{action_after_clause}|{_SEQUENCE_NOMINAL_HEAD})\b)",
        "",
        text,
        count=1,
        flags=re.IGNORECASE,
    )
    elliptical_head = (
        rf"(?:{_KNOWN_APPLICATION}|otra|otro|another|"
        r"(?:al?|to)?\s*\d{1,3})"
    )
    next_action_head = rf"(?=[¿?¡!\s]*(?:{action_after_clause})\b)"
    next_nominal_head = rf"(?=[¿?¡!\s]*{_SEQUENCE_NOMINAL_HEAD}\b)"
    # Keep the pre-existing single-read boundary for the combined scopes that
    # system.status already measures together (CPU/RAM and OS/RAM). Only add
    # the new quantity-question boundary when it cannot use that same read.
    quantity_question_head = (
        ""
        if _machine_status_scopes(text) in _COMBINED_MACHINE_SCOPES
        and _machine_status_is_the_whole_clause(text)
        else r"|cuant[oa]s?|how\s+(?:much|many)"
    )
    next_effect_head = (
        rf"(?=[¿?¡!\s]*(?!(?:reproducela|reproducelo|play it|"
        rf"leerla con ocr|leerlo con ocr|read it with ocr)\b)"
        rf"(?:{action_after_clause}|{elliptical_head}|"
        rf"{_SEQUENCE_NOMINAL_HEAD}|como\s+esta|how\s+is|"
        rf"what\s+time|que\s+hora|is|are|was|were|esta|estan|estaba|estaban|"
        rf"si|if|whether{quantity_question_head})\b)"
    )
    separator = re.compile(
        (
            r"\s*[,;.!?]\s*(?=(?:no|nunca|jamas|never|don't|do\s+not)\b)|"
            rf"\s*(?:(?:[.;!?]+|[,;]\s*(?:y|and)?)\s*{next_action_head}|"
            rf";\s*{next_nominal_head}|"
            r"(?:[,;]\s*)?\b(?:y despues|y luego|and then|"
            r"despues\s+de\s+eso|tras\s+eso|"
            r"despues(?!\s+(?:de|del)\b)|luego|"
            r"then|afterwards|after\s+(?:that|this))\b\s*[,;:]?\s*|"
            rf"(?:[,;]\s*)?\b(?:(?:y|and)\s+)?(?:finalmente|finally)\b"
            rf"\s*[,;:]?\s*"
            rf"{next_effect_head}|"
            r"\b(?:y|and|pero|but)\b\s*(?=[¿?¡!\s]*(?:no|nunca|jamas|never|"
            r"don'?t|do\s+not)\b)|"
            r"\b(?:y|and)\b\s*(?=[¿?¡!\s]*(?:gracias|thanks|thank you|"
            r"por favor|please|que tengas (?:un )?buen dia)\b)|"
            rf"\b(?:pero|but)\b\s*{next_action_head}|"
            rf"(?:[,;]\s*)?\b(?:y|and)\b\s*{next_effect_head})\s*"
        ),
        re.IGNORECASE,
    )
    # A conjunction inside quoted payload is not a boundary between requests.
    # Mask only for locating separators; slice the original so literal content
    # and evidence survive unchanged. Word boundaries keep don't/it's from
    # opening a single-quoted payload.
    boundary_text = re.sub(
        r'«[^»]*»|“[^”]*”|‘[^’]*’|"[^\"]*"|(?<!\w)\'[^\']*\'(?!\w)',
        lambda match: "x" * len(match.group(0)),
        text,
    )
    parts = []
    start = 0
    for boundary in separator.finditer(boundary_text):
        if (
            _explicit_google_search_query(text[start:]) is not None
            and re.fullmatch(
                rf"[¿?¡!\s]*{_REQUEST_PREFIX}(?:en|on)\s+google",
                boundary_text[start:boundary.start()].strip(),
                re.IGNORECASE,
            )
        ):
            # The Google topic belongs to its following imperative. Later
            # action separators still delimit independent effects normally.
            continue
        topic = _machine_status_topic(boundary_text[start:])
        if topic is not None and (
            boundary.start() <= start + topic.start("separator") < boundary.end()
        ):
            # The topic belongs to this request; the next actual action still
            # forms its own clause. Slice original text, including quoted data.
            continue
        parts.append(text[start:boundary.start()])
        start = boundary.end()
    parts.append(text[start:])
    clauses = tuple(
        clause
        for clause in (part.strip() for part in parts)
        if clause and re.search(r"\w", clause, re.UNICODE) is not None
    )
    return _normalize_dependent_clauses(clauses)


# A dependent clause borrows its head from the clause that governs it. A
# sequencing verb (``termina con ...``) carries no operation of its own, an
# elided object (``otra nota Sol ...``) reuses the previous verb, and a bare
# ordinal (``read la segunda``) reuses the previous object noun. Leaving these
# unresolved made the compound conservation veto abstain from whole missions
# that were in fact fully expressible, so the normalization is deliberately
# narrow: every pattern is anchored at the start of a clause, and a clause that
# matches nothing is returned byte-for-byte.
_SEQUENCING_CLAUSE_HEAD = re.compile(
    r"^(?:(?:y|and)\s+)?"
    r"(?:(?:termina|finaliza|concluye)\s+"
    r"(?:con|reportando|revisando|mostrando|listando)"
    r"|(?:finish|end|conclude)\s+"
    r"(?:with|by\s+(?:checking|reporting|showing|listing|reading)))"
    r"\s+",
    re.IGNORECASE,
)
_ELLIPTICAL_OBJECT_CLAUSE = re.compile(
    r"^(?:(?:y|and)\s+)?(?:otra|otro|another|one\s+more|una\s+mas|uno\s+mas)\s+\w",
    re.IGNORECASE,
)
_BARE_ORDINAL_CLAUSE = re.compile(
    r"^(?:(?:y|and)\s+)?(?:lee|leer|lea|read)\s+(?:la|el|the)\s+"
    r"(?:primer[ao]?|segund[ao]|tercer[ao]?|cuart[ao]|quint[ao]|ultim[ao]|"
    r"first|second|third|fourth|fifth|last)[\s.!?]*$",
    re.IGNORECASE,
)
# The determiner and the noun are not always adjacent. "crea una nota **local**
# titulada A ... y otra titulada B" and its English twin "create a **local**
# note titled A and another titled B" name the same two notes as the bare form,
# but the modifier hid the governing noun, so the elliptical second clause was
# rebuilt as "create another titled B" with no object at all and the pair was
# counted as one. The modifiers are listed rather than left open: an arbitrary
# word between determiner and noun would let an unrelated phrase govern the
# ellipsis.
_NOUN_SCOPE_MODIFIER = (
    r"(?:local|locales|privad[ao]|privad[ao]s|private|personal|personales|"
    r"nuev[ao]|nuev[ao]s|new|rapid[ao]|quick|corta|corto|short)"
)
_CLAUSE_OBJECT_NOUN = re.compile(
    r"^(?:(?:y|and)\s+)?\S+\s+(?:una?|el|la|an?|the|otra|otro|another)\s+"
    rf"(?:{_NOUN_SCOPE_MODIFIER}\s+){{0,2}}"
    r"(?P<noun>notas?|notes?|recordatorios?|reminders?|alarmas?|alarms?|"
    r"tareas?|tasks?)\b",
    re.IGNORECASE,
)
_ORDINAL_NOTE_ITEM = (
    r"(?:(?:la|el|the)\s+)?"
    r"(?:primer[ao]?|segund[ao]|tercer[ao]?|cuart[ao]|quint[ao]|ultim[ao]|"
    r"first|second|third|fourth|fifth|last)"
    r"(?:\s+(?:nota|note))?"
)
_ORDINAL_READ_SEQUENCER = r"(?:luego|despues|then|finally|por\s+ultimo|lastly)"
# "read the second note and finally the first note" enumerates two reads and was
# resolving to one, which is a conservation loss: the request named four
# operations and three came back. Splitting follows the same rule the
# coordinated status clause already sets -- only when the clause is nothing but
# coordinated ordinal notes, so no segment the recognizer cannot ground is ever
# severed from one it can.
_PURE_COORDINATED_ORDINAL_READ_CLAUSE = re.compile(
    r"^(?:(?:y|and)\s+)?"
    r"(?:lee|leer|lea|read)\s+"
    rf"{_ORDINAL_NOTE_ITEM}"
    rf"(?:\s*,\s*(?:{_ORDINAL_READ_SEQUENCER}\s+)?{_ORDINAL_NOTE_ITEM})*"
    rf"\s+(?:y|and)\s+(?:{_ORDINAL_READ_SEQUENCER}\s+)?{_ORDINAL_NOTE_ITEM}"
    r"[\s.!?]*$",
    re.IGNORECASE,
)
_COORDINATED_ORDINAL_READ_TAIL = re.compile(
    rf"\s+(?:y|and)\s+(?:{_ORDINAL_READ_SEQUENCER}\s+)?(?={_ORDINAL_NOTE_ITEM}\b)",
    re.IGNORECASE,
)
_STATUS_DOMAIN_NOMINAL = (
    r"(?:audio|network|red|system|sistema|wifi|bluetooth|bateria|battery|"
    r"disco|disk|memoria|memory|cpu|gpu|sonido|sound)"
)
_STATUS_NOMINAL_ITEM = (
    rf"(?:(?:el|la|los|las|the)\s+)?(?:{_STATUS_DOMAIN_NOMINAL}"
    rf"(?:\s+(?:status|state|estado|usage))?|(?:estado|uso)\s+(?:del?|de\s+la)\s+"
    rf"{_STATUS_DOMAIN_NOMINAL}|hora|fecha|time|date|volumen|volume)"
)
_COORDINATED_STATUS_TAIL = re.compile(
    rf"\s*(?:,\s*(?:(?:y|and)\s+)?|\b(?:y|and)\s+)(?={_STATUS_NOMINAL_ITEM}\b)",
    re.IGNORECASE,
)
# Splitting a coordination is only safe when the whole clause is nothing but
# coordinated status nominals. Otherwise a segment the recognizer cannot
# ground -- ``show system status, network status, brew coffee and sound
# status`` -- would be severed from the part that does resolve, and the
# request would silently execute a recognizable subset instead of failing
# closed. Conservation outranks coverage here.
_PURE_COORDINATED_STATUS_CLAUSE = re.compile(
    r"^(?:(?:y|and)\s+)?"
    r"(?:(?:revisa|revisar|check|comprueba|comprobar|reporta|report|muestra|"
    r"show|dime|tell\s+me|consulta|lee|read|dame|give\s+me)\s+)?"
    rf"{_STATUS_NOMINAL_ITEM}"
    rf"(?:\s*,\s*{_STATUS_NOMINAL_ITEM})*"
    rf"\s*,?\s+(?:y|and)\s+{_STATUS_NOMINAL_ITEM}[\s.!?]*$",
    re.IGNORECASE,
)


def _clause_leading_verb(clause: str) -> str | None:
    found = re.match(
        rf"^(?:(?:y|and)\s+)?(?P<verb>{_COVERAGE_ACTION_HEAD})\b",
        clause,
        re.IGNORECASE,
    )
    return found.group("verb") if found is not None else None


def _strip_clause_conjunction(clause: str) -> str:
    return re.sub(r"^(?:y|and)\s+", "", clause, count=1, flags=re.IGNORECASE)


def _normalize_dependent_clauses(clauses: tuple[str, ...]) -> tuple[str, ...]:
    """Give dependent clauses back the head their governing clause supplied."""

    normalized: list[str] = []
    governing_verb: str | None = None
    governing_noun: str | None = None
    for clause in clauses:
        current = clause
        sequencing = _SEQUENCING_CLAUSE_HEAD.match(current)
        if governing_verb and _indirect_audio_mute_state_query(f"{governing_verb} {current}"):
            current = f"{governing_verb} {current}"
        elif sequencing is not None:
            remainder = current[sequencing.end() :].lstrip()
            if remainder:
                # ``revisa`` is already an accepted observation head, so the
                # residual noun phrase reaches the same recognizers a directly
                # phrased report would.
                current = f"revisa {remainder}"
        elif _ELLIPTICAL_OBJECT_CLAUSE.match(current) is not None and governing_verb:
            body = _strip_clause_conjunction(current)
            if governing_noun is not None and not _has(
                body,
                rf"\b{governing_noun}s?\b",
            ):
                # ``otra B`` after ``una nota A`` is another note, not a bare
                # label. Restore the elided noun so the clause carries the same
                # object its governing clause named.
                body = re.sub(
                    r"^(otra|otro|another|one\s+more|una\s+mas|uno\s+mas)\s+",
                    rf"\1 {governing_noun} ",
                    body,
                    count=1,
                    flags=re.IGNORECASE,
                )
            current = f"{governing_verb} {body}"
        elif _BARE_ORDINAL_CLAUSE.match(current) is not None and governing_noun:
            current = f"{current.rstrip(' .!?')} {governing_noun}"

        verb = _clause_leading_verb(current)
        if verb is None and _head_is(_request_head(current), _AUDIO_OBSERVATION_HEAD):
            verb = _request_head(current)
        if verb is not None:
            governing_verb = verb
        noun = _CLAUSE_OBJECT_NOUN.match(current)
        if noun is not None:
            governing_noun = noun.group("noun")

        if _PURE_COORDINATED_STATUS_CLAUSE.match(current) is not None:
            pieces = _COORDINATED_STATUS_TAIL.split(current)
        elif _PURE_COORDINATED_ORDINAL_READ_CLAUSE.match(current) is not None:
            pieces = _COORDINATED_ORDINAL_READ_TAIL.split(current)
        else:
            pieces = [current]
        if len(pieces) > 1:
            head_verb = _clause_leading_verb(pieces[0])
            normalized.append(pieces[0].strip())
            for tail in pieces[1:]:
                tail = tail.strip()
                normalized.append(f"{head_verb} {tail}" if head_verb else tail)
        else:
            normalized.append(current)
    return tuple(normalized)


_STRICT_COMPOSITION_SEGMENT_SEPARATOR = re.compile(
    r"\s*(?:[,;]+|\b(?:y\s+despues|y\s+luego|and\s+then|"
    r"despues\s+de\s+eso|por\s+ultimo|after\s+(?:that|this)|afterwards|"
    r"junto\s+con|along\s+with|finally|finalmente|then|luego|despues|"
    r"tambien|y|and)\b)\s*",
    re.IGNORECASE,
)


_STRICT_COMPOSITION_NOMINAL_OPERATIONS = (
    (
        "system.status",
        r"(?:system|sistema|machine|maquina|equipo|computer|computador|pc)",
    ),
    ("network.status", r"(?:red|network)"),
    ("backup.list", r"(?:copias?|copies|backups?|respaldos?)"),
    ("email.latest.read", r"(?:correo|email|mail)"),
    ("input.keyboard.status", r"(?:teclado|keyboard)"),
)


def _strict_composition_nominal_operation(segment: str) -> str | None:
    if _nominal_datetime_query(segment):
        return "system.time"
    observation_head = (
        r"(?:(?:reporta?|show|muestra|consulta|lee|read|enumera|list|"
        r"give|dame|revisa|revisar|check|comprueba|comprobar|"
        r"inspecciona|inspect)\s+)?"
    )
    for operation, nominal in _STRICT_COMPOSITION_NOMINAL_OPERATIONS:
        if (
            re.fullmatch(
                rf"[Â¿?Â¡!\s]*{observation_head}(?:(?:el|la|the)\s+)?"
                rf"{nominal}(?:\s+(?:status|state|estado))?[\s.!?]*",
                segment,
                re.IGNORECASE,
            )
            is not None
        ):
            return operation
    return None


def _strict_composition_segments_are_grounded(
    text: str,
    expected: EffectIntent,
    available: frozenset[str],
    applications: ApplicationCatalogIndex,
) -> bool:
    """Prove every coordinated segment belongs to the strict operation list."""

    segments = tuple(
        segment
        for segment in (
            part.strip() for part in _STRICT_COMPOSITION_SEGMENT_SEPARATOR.split(text)
        )
        if segment and re.search(r"\w", segment, re.UNICODE) is not None
    )
    if not 2 <= len(segments) <= 8:
        return False
    operations: list[str] = []
    for segment in segments:
        if (
            re.fullmatch(
                r"(?:exactamente|exactly)\s+(?:en|in)\s+(?:ese|that)\s+"
                r"(?:orden|order)[\s.!?]*",
                segment,
                re.IGNORECASE,
            )
            is not None
        ):
            continue
        resolved = _strict_catalog_request(segment, available, applications)
        if resolved is None:
            # A shared observation head can govern later nominal segments:
            # ``show system status, network access and sound routing``.
            resolved = _strict_catalog_request(
                "show " + segment,
                available,
                applications,
            )
        if resolved is None:
            nominal_operation = _strict_composition_nominal_operation(segment)
            if nominal_operation is None:
                return False
            operations.append(nominal_operation)
        else:
            operations.extend(resolved.operations)
        if len(operations) > 8:
            return False
    return tuple(operations) == expected.operations


def _open_application_spans(text: str) -> tuple[tuple[int, str], ...]:
    request = _match(
        text,
        (
            r"^[¿?¡!\s]*(?:(?:por favor|please)\s*[,;:]?\s*|"
            r"(?:puedes|podrias|can you|could you|would you)\s+)?"
            rf"(?:{_OPEN}|necesito|quiero|i\s+need|i\s+want)\b(?:\s+(?:el|la|the|un|una|a))?\s+"
            rf"(?:(?:aplicacion|application|app|programa|program)\s+)?"
            rf"(?P<body>{_KNOWN_APPLICATION}"
            rf"(?:\s*,\s*(?:el|la|the)?\s*{_KNOWN_APPLICATION})*)"
            r"(?:,?\s+(?:por favor|please|ahora|now))?[\s?!.]*$"
        ),
    )
    if request is None or _is_negated_match(text, request):
        return ()
    body = request.group("body")
    base = request.start("body")
    applications: list[tuple[int, str]] = []
    for found in re.finditer(_KNOWN_APPLICATION, body, re.IGNORECASE):
        app = found.group(0).casefold()
        app = {
            "opera gx": "opera_gx",
            "google chrome": "chrome",
            "microsoft edge": "edge",
        }.get(app, app)
        applications.append((base + found.start(), app))
    return tuple(applications)


_STEAM_LIBRARY_VERB = (
    r"(?:descarga|descargar|descargame|descargate|baja|bajar|bajame|bajate|"
    r"instala|instalar|instalame|instalate|instalaes|install|download|"
    r"desinstala|desinstalar|desinstalame|desinstalate|uninstall|remove|"
    # INSTALL1625 H0083 «lanzá Mortal Kombat en Steam»: launching a game the
    # library does not hold is answered by the same read.
    r"lanza|lanzar|lanzame|launch|run|juega|jugar|play|start|abre|abrir|abrime|open)"
)
_STEAM_LIBRARY_REQUEST = re.compile(
    r"[¿?¡!\s]*(?:(?:necesito|quiero|quisiera|podes|podrias|puedes|podria|can\s+you|could\s+you|please)\s+(?:que\s+)?)?"
    rf"(?:me\s+)?{_STEAM_LIBRARY_VERB}\s+(?:(?:el|la|the)\s+)?(?:(?:juego|game)\s+)?"
    r"(?P<title>[a-z0-9][a-z0-9 .:'&+-]{0,80}?)"
    # INSTALL1625 H0387/H0721 «… en Teams»: the owner's transcriptions write
    # Steam as «Teams» (H0386/H0522); a game platform, never the meeting app.
    r"\s+(?:en|de|desde|por|from|on|in|via|through)\s+(?:steam|seam|stim|estim|teams|team)"
    r"(?:\s+(?:por\s+favor|please|ahora|now))?[\s.!?]*"
)


def steam_library_title(text: str) -> str | None:
    """The game named by a Steam download/install/uninstall request.

    INSTALL1617 H0482 «Descarga Worms Rumble en Steam», H0049 «… en seam»,
    H0118 «Descarga doom eternal de steam», H0643 «Necesito que instalaes worms
    rumble en steam»: one verb, one title, Steam named after it. The title is
    returned with the person's own spelling and case; instructions after the
    request (AppIDs, URLs, a second sentence) keep the request out of this
    reader. Negations and meta talk abstain.
    """

    folded = _strip_request_envelope(_fold(text)).strip()
    if _is_negative_effect_clause(folded) or _is_meta_or_tool_denial(folded):
        return None
    match = _STEAM_LIBRARY_REQUEST.fullmatch(folded.rstrip(".!?").strip())
    if match is None:
        # INSTALL1627 H0396/H0456: the request is followed by instructions
        # about the same install (an AppID, a steam:// URL, the store page);
        # the first sentence is the request, the rest names no other effect.
        head, separator, rest = folded.partition(". ")
        if separator and _has(rest, r"\bapp\s*id\b|steam://|store\.steampowered\.com") and not _has(
            rest, r"\b(?:luego|despues|then|y\s+(?:abre|lanza|abri|ejecuta|open|launch|run)|cierra|close)\b",
        ):
            match = _STEAM_LIBRARY_REQUEST.fullmatch(head.rstrip(".!?").strip())
        if match is None:
            # INSTALL1633 H0608 «lanzá Mortal Kombat»: a launch of a bare name
            # with no platform; games are launched from Steam here, so the
            # library read answers when no installed game or catalog entry
            # claims the name (the caller checks those before reading).
            match = re.fullmatch(
                r"[¿?¡!\s]*(?:(?:necesito|quiero|quisiera|podes|podrias|puedes|can\s+you|could\s+you|please)\s+(?:que\s+)?)?"
                r"(?:me\s+)?(?:lanza|lanzame|lanzar|launch|juega|juga|jugar|jugame|jugemos)\s+"
                r"(?:(?:el|la|the|a|al)\s+)?(?:(?:juego|game)\s+)?"
                r"(?P<title>[a-z0-9][a-z0-9'&+-]*(?:\s+[a-z0-9][a-z0-9'&+-]*){0,3})"
                r"(?:[\s,]+(?:por\s+favor|please|ahora|now))?",
                folded.rstrip(".!?").strip(),
            )
            if match is not None and _has(
                match.group("title"),
                r"^(?:todo|todos|todas|eso|esto|aquello|algo|nada|lo|la|el|ese|esa|este|esta|los|las|un|una|mi|mis|"
                r"it|this|that|them|my|the|something|anything|un\s+juego|a\s+game|algun\s+juego|any\s+game)$",
            ):
                match = None
        if match is None:
            return None
    title = match.group("title").strip(" .")
    if not title or _has(title, r"^(?:el|la|the|un|una|a|an|juego|game|algo|something)$"):
        return None
    raw = str(text)
    folded_raw = _fold(raw)
    if len(folded_raw) == len(raw):
        position = folded_raw.find(title)
        if position >= 0:
            return raw[position:position + len(title)]
    return title


_CATALOG_INSTALL_VERB = (
    r"(?:instala|instalar|instalame|instalate|install|descarga|descargar|descargame|download|baja|bajar|bajame|"
    r"desinstala|desinstalar|desinstalame|desinstalate|uninstall)"
)


def installed_catalog_application_name(
    text: str,
    application_names: Iterable[str] | ApplicationCatalogIndex,
) -> str | None:
    """The Start-catalog application an install or uninstall request names.

    INSTALL1625 H0651 «instala Spotify», H0574 «desinstalá Spotify», H0089
    «desinstalá Discord»: the product installs nothing by name and uninstalls
    nothing; the truthful turn reads whether the application is present and
    says so. Only an authenticated catalog name qualifies; anything else stays
    with the model.
    """

    folded = _strip_request_envelope(_fold(text)).strip().rstrip(".!?").strip()
    if _is_negative_effect_clause(folded) or _is_meta_or_tool_denial(folded):
        return None
    match = re.fullmatch(
        rf"[¿?¡!\s]*(?:(?:necesito|quiero|quisiera|podes|podrias|puedes|can\s+you|could\s+you|please)\s+(?:que\s+)?)?"
        rf"(?:me\s+)?{_CATALOG_INSTALL_VERB}\s+(?:(?:el|la|the|a)\s+)?(?:(?:app|aplicacion|programa|application)\s+)?"
        r"(?P<name>[a-z0-9][a-z0-9 .+'&-]{0,60}?)"
        r"(?:[\s,]+(?:por\s+favor|please|ahora|now|de\s+nuevo|again))?",
        folded,
    )
    if match is None:
        return None
    name = match.group("name").strip()
    if not name:
        return None
    catalog_name = resolve_application_catalog_app_id("abre " + name, application_names)
    if catalog_name is not None:
        return catalog_name
    # INSTALL1629 «instala Photoshop»: known software absent from the catalog
    # is answered by the same presence read, with the name as the person
    # wrote it (the read proves absence; nothing is installed).
    known = re.fullmatch(_KNOWN_SOFTWARE, name) is not None
    # INSTALL1631 H0620 «Desinstala Worms Rumble»: uninstalling a name the
    # catalog does not hold is answered by the same presence read (nothing
    # can be removed that is not present); a plain name of one to four words.
    uninstall = _has(folded, r"^[¿?¡!\s]*(?:(?:necesito|quiero|quisiera|podes|podrias|puedes|can\s+you|could\s+you|please)\s+(?:que\s+)?)?(?:me\s+)?(?:desinstal|uninstall)")
    plain_name = re.fullmatch(r"[a-z0-9][a-z0-9'+-]*(?:\s+[a-z0-9][a-z0-9'+-]*){0,3}", name) is not None and not _has(
        name,
        r"^(?:(?:todo|todos|todas|eso|esto|aquello|algo|nada|lo|la|el|ese|esa|este|esta|los|las|"
        r"un|una|mi|mis|tu|tus|everything|all|it|this|that|them|my|the)\b.*|"
        r".*\b(?:programas?|aplicaciones?|apps?|juegos?|cosas?|archivos?|programs?|applications?|games?|files?))$",
    )
    if known or (uninstall and plain_name):
        raw = str(text)
        folded_raw = _fold(raw)
        position = folded_raw.find(name) if len(folded_raw) == len(raw) else -1
        return raw[position:position + len(name)] if position >= 0 else name
    return None


def installed_game_title(text: str) -> str | None:
    """Read the game named by an installed question («dime si X ya está instalado»).

    APPS1613 H0275: the clause is the person's folded surface; the title is
    everything between the question head and the installed predicate, without
    the article, «el juego» or «ya».  Free mentions and other shapes abstain.
    """

    folded = _strip_request_envelope(_fold(text)).strip().rstrip(".?!").strip()
    match = re.fullmatch(
        r"(?:[¿?¡!\s]*(?:y|and|luego|then)\s+)?"
        r"(?:decime|dime|contame|cuentame|tell\s+me|fijate|chequea|check|"
        r"comprueba|verifica|revisa|verify|confirm|confirma)\s+"
        r"(?:si|if|whether)\s+"
        r"(?:tengo\s+(?:instalado\s+)?|i\s+have\s+(?:installed\s+)?)?"
        r"(?:(?:el|la|the)\s+)?(?:(?:juego|game)\s+)?"
        r"(?P<title>[a-z0-9][a-z0-9 .:'&+-]{0,80}?)"
        r"(?:\s+(?:ya|already|esta|is)){0,2}"
        r"\s+(?:instalad[oa]|installed)"
        r"(?:\s+(?:en|on)\s+(?:steam|epic(?:\s+games)?))?",
        folded,
    )
    if match is None:
        return None
    title = match.group("title").strip()
    if not title or _has(title, r"^(?:el|la|the|un|una|a|an|ya|already|esta|is)$"):
        return None
    return title


def installed_game_provider(text: str) -> str:
    """The manifest family the installed question names; ``any`` otherwise."""

    folded = _fold(text)
    if _has(folded, r"\bsteam\b"):
        return "steam"
    if _has(folded, r"\bepic\b"):
        return "epic"
    return "any"


def _opened_applications(text: str) -> tuple[str, ...]:
    applications = [application for _, application in _open_application_spans(text)]
    return tuple(applications)


# WEB1739: the browsers browser.navigate.named can drive over CDP (Chromium family). Firefox is
# recognised as a name but has no CDP endpoint, so it never becomes a named navigation.
NAMED_CDP_BROWSERS = frozenset({"opera", "opera_gx", "chrome", "edge", "brave"})


def _named_browser_match(text: str) -> re.Match[str] | None:
    browser = r"(?:opera gx|opera|google chrome|chrome|microsoft edge|edge|brave|firefox)"
    return _match(
        text,
        (
            rf"^[¿?¡!\s]*(?:navega|navegar|navigate|ve|go)\s+"
            rf"(?P<leading>{browser})\b|"
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


def _dependent_web_navigation_intent(
    text: str,
    available_operations: frozenset[str],
    application_names: ApplicationCatalogIndex,
) -> EffectIntent | None:
    """Resolve an explicit site search followed by navigation to its result."""

    request = _match(
        text,
        (
            rf"^[¿?¡!\s]*{_REQUEST_PREFIX}{_OPEN}\b\s+"
            r"(?P<destination>wikipedia|(?:la\s+|the\s+)?(?:pagina|page|"
            r"sitio|site|website)\s+[^,;.!?]{1,100})\s+"
            r"(?:y|and)\s+(?:luego\s+|then\s+)?"
            rf"{_SEARCH}\b\s+(?P<query>\S.+?)[\s?!.]*$"
        ),
    )
    if request is None or _is_negated_match(text, request):
        return None
    if not {"web.search", "browser.navigate"} <= available_operations:
        return None
    first_clause = f"abre {request.group('destination')}"
    if _authenticated_application_target(
        first_clause, application_names
    ) is not None or _open_application_spans(first_clause):
        return None
    evidence = request.group(0).strip(" ,;:-")[:240]
    return EffectIntent(
        ("web.search", "browser.navigate"),
        (evidence, evidence),
    )


_VISIBLE_CLICK_POINTING = (
    r"(?:haz\s+clic(?:\s+en)?|hace\s+clic(?:k)?(?:\s+en)?|clic(?:k)?\s+en"
    r"|click(?:ea|ear)?(?:\s+(?:on|it))?"
    r"|apreta(?:le|lo|la)?(?:\s+en)?|apretar|aprieta(?:\s+en)?"
    r"|pulsa(?:lo|la|le)?|presiona(?:lo|la|le)?|press(?:\s+it)?)"
)
# «en la calculadora apretá el 5» / «apretá el 5 en la calculadora»: the app
# names where the control lives; the label is the control alone (UI1273).
_VISIBLE_CLICK_APP_CONTEXT = (
    r"(?:en|in|on)\s+(?:la|el|the)\s+(?:calculadora|calc|calculator|app|"
    r"aplicacion|application|ventana|window|pantalla|screen)"
)
_VISIBLE_CLICK_NAVIGATE = (
    # UI1731 «Abre Steam y luego navega por la gui hasta biblioteca», «Abre Epic
    # Games y navega hasta la biblioteca»: walking the open client's interface
    # to a named section is a verified click on that visible label.
    r"(?:ve\s+a|vete\s+a|anda\s+a|andate\s+a|entra\s+(?:a|en)|metete\s+en|go\s+to|go\s+into|"
    r"navega(?:\s+por\s+(?:la\s+|el\s+|los\s+)?(?:gui|interfaz|interface|menu|menus|pantalla|ventana|app|aplicacion))?\s+(?:a|hacia|hasta)|"
    r"navigate(?:\s+(?:through|via)\s+the\s+(?:gui|interface|menus?))?\s+to)"
)
_VISIBLE_CLICK_CONTROL_NOUN = (
    r"(?:boton|button|control|enlace|link|pestana|tab|seccion|section)"
)
_VISIBLE_CLICK_WEB_DESTINATION = re.compile(
    r"wikipedia|https?://|www\.|\.com\b|\.org\b|\.net\b|\.io\b",
    re.IGNORECASE,
)


def _visible_click_label(
    text: str,
    *,
    allow_navigate: bool = False,
) -> str | None:
    """Extract the unique visible-control label, or nothing.

    Navigate heads (``ve a`` / ``go to``) are click only after an app is
    already open. Bare web destinations stay with the browser family.
    """

    head = _VISIBLE_CLICK_POINTING
    if allow_navigate:
        head = rf"(?:{head}|{_VISIBLE_CLICK_NAVIGATE})"
    text = re.sub(
        rf"^([¿?¡!\s]*){_VISIBLE_CLICK_APP_CONTEXT}\s+", r"\1", _fold(text), count=1,
    )
    text = re.sub(rf"\s+{_VISIBLE_CLICK_APP_CONTEXT}(?=[\s?!.]*$)", "", text, count=1)
    request = _match(
        text,
        (
            rf"^[¿?¡!\s]*{_REQUEST_PREFIX}{head}\s+"
            r"(?:(?:el|la|los|las|the)\s+)?"
            rf"(?:{_VISIBLE_CLICK_CONTROL_NOUN}\s+)?"
            r"(?P<label>[^,;.!?]{1,80}?)"
            rf"(?:\s+{_VISIBLE_CLICK_CONTROL_NOUN})?"
            r"[\s?!.]*$"
        ),
    )
    if request is None or _is_negated_match(text, request):
        return None
    label = request.group("label").strip(" \t\"'`")
    label = re.sub(
        r"^(?:el|la|los|las|the)\s+",
        "",
        label,
        flags=re.IGNORECASE,
    ).strip()
    if (
        not label
        or len(label.split()) > 6
        or _VISIBLE_CLICK_WEB_DESTINATION.search(label) is not None
        # «pulsá la tecla enter» / «presioná enter» are key presses, not
        # visible controls (UI1273).
        or re.search(r"\b(?:tecla|teclas|key|keys|teclado|keyboard)\b", label, re.IGNORECASE) is not None
        or re.fullmatch(
            r"(?:enter|intro|return|escape|esc|tab|espacio|space|supr|delete|backspace|retroceso|"
            r"ctrl|control|alt|shift|win|windows|inicio|home|fin|end)",
            label,
            re.IGNORECASE,
        ) is not None
    ):
        return None
    return label[:80]


def _click_in_application(
    folded: str,
    application_names: Iterable[str] | ApplicationCatalogIndex,
) -> tuple[str, str] | None:
    """UI1735: a click or navigation order framed by «en/in/on <catalog app>»
    at either end of the clause → (catalog key, clause without the frame).
    Generic frames («en la calculadora», «en la app») keep the UI1273 path."""

    catalog = build_application_catalog_index(application_names)
    occurrence = catalog.occurrence_pattern
    if occurrence is None:
        return None
    text = folded.strip()
    for pattern in (
        r"^[¿?¡!\s]*(?:(?:por\s+favor|please)\s*[,;:]?\s*)?(?:en|in|on)\s+(?:la\s+|el\s+|the\s+)?(?P<app>.+?)\s*[,;:]?\s+(?P<clause>(?:ve|vete|anda|andate|entra|metete|navega|apreta|pulsa|presiona|hace|haz|toca|clickea|clica|go|navigate|click|press|tap|open)\b.+)$",
        r"^(?P<clause>.+?)\s+(?:en|in|on)\s+(?:la\s+|el\s+|the\s+)?(?P<app>[a-z0-9][a-z0-9 .+-]{1,40}?)[\s?!.]*$",
    ):
        found = re.match(pattern, text)
        if found is None:
            continue
        candidate = found.group("app").strip(" ,.;:!?")
        hit = occurrence.fullmatch(candidate)
        # A catalog name as written, or a bilingual alias of one («Opera» for
        # «Navegador Opera GX», «Epic Games» for «Epic Games Launcher»).
        key = _catalog_alias_key(
            _application_name_key(hit.group("target") if hit is not None else candidate),
            catalog.keys,
        )
        if key is None:
            continue
        clause = found.group("clause").strip(" ,;:")
        if not clause:
            continue
        if _MESSAGING_CLIENT_KEY.search(key) is not None and not _has(
            clause, r"^(?:ve|vete|anda|andate|entra|metete|go|navigate|navega)\b"
        ):
            # LIMITS1681 «apretá enviar en WhatsApp», «en Discord apretá enter»,
            # and the microphone reading of «en Discord apretá silenciar» stay as
            # they are: inside a messaging client only going to a chat or a
            # channel is a click on its interface; pressing its controls is not.
            return None
        return key, clause
    return None


_MESSAGING_CLIENT_KEY = re.compile(
    r"\b(?:discord|whatsapp|telegram|teams|slack|skype|zoom|signal|messenger)\b"
)


def _visible_click_intent(
    text: str,
    available_operations: frozenset[str],
    *,
    allow_navigate: bool = False,
) -> EffectIntent | None:
    """Resolve find-and-activate as one grounded visible-control effect."""

    if "input.visible.click" not in available_operations:
        return None
    request = _match(
        text,
        (
            rf"^[¿?¡!\s]*{_REQUEST_PREFIX}{_SEARCH}\b\s+"
            r"(?:(?:(?:el|la|the)\s+)?(?:boton|button|control|enlace|link)\b"
            r"[^,;.!?]{1,120}|(?:(?:el|la|the)\s+)?[^,;.!?]{1,100}\s+"
            r"(?:boton|button|control|enlace|link))\s+\b(?:y|and)\b\s+"
            r"(?:presionalo|presionala|pulsa(?:lo|la)?|haz\s+clic|"
            r"click(?:\s+it)?|press(?:\s+it)?)[\s?!.]*$"
        ),
    )
    if request is not None and not _is_negated_match(text, request):
        evidence = request.group(0).strip(" ,;:-")[:240]
        return EffectIntent(("input.visible.click",), (evidence,))
    if _visible_click_label(text, allow_navigate=allow_navigate) is None:
        return None
    if _has(_fold(text), r"\b(?:en|in|on)\s+(?:discord|whatsapp|teams|telegram|slack|skype|zoom|signal|messenger)\b") and _has(
        _fold(text), r"\b(?:enviar|envia|send|submit|mandar|manda|publicar|post)\b"
    ):
        # LIMITS1681 «apretá enviar en WhatsApp»: a send control inside a
        # messaging client is a known limit (never a real message). Going to
        # a channel or a chat («ve a Cotele en Discord») is navigation of the
        # client's interface (UI1735) and stays a click.
        return None
    evidence = text.strip(" ,;:-")[:240]
    return EffectIntent(("input.visible.click",), (evidence,))


def _wifi_email_intent(
    text: str,
    available_operations: frozenset[str],
) -> EffectIntent | None:
    """Resolve Wi-Fi availability followed by reading the latest email."""

    required = {"wifi.ensure.connected", "email.latest.read"}
    if not required <= available_operations:
        return None
    request = _match(
        text,
        (
            r"^[¿?¡!\s]*(?:conecta|conectar|connect)\s+"
            r"(?:(?:el|the)\s+)?wi[\s-]?fi\b[^.;!?]{0,80}"
            r"\b(?:abre|open)\s+(?:(?:el|the)\s+)?(?:correo|email|mail)\b"
            r"[^.;!?]{0,80}\b(?:lee|leeme|read)\b[^.;!?]{0,80}"
            r"\b(?:ultimo|ultima|latest|most recent)\b"
            r"(?:\s+(?:mensaje|message|correo|email|mail))?"
            r"(?:\s+(?:por favor|please))?[\s?!.]*$"
        ),
    )
    if request is None or _is_negated_match(text, request):
        return None
    evidence = request.group(0).strip(" ,;:-")[:240]
    return EffectIntent(
        ("wifi.ensure.connected", "email.latest.read"),
        (evidence, evidence),
    )


def _new_notepad_paste_intent(
    text: str,
    available: frozenset[str],
    application_names: ApplicationCatalogIndex,
) -> EffectIntent | None:
    """Open a verified blank Notepad target before pasting the clipboard."""

    if not {"app.open", "clipboard.paste"} <= available:
        return None
    request = _match(
        text,
        (
            r"^[ż?Ą!\s]*(?:pega|pegar|paste)\s+"
            r"(?:(?:el|the)\s+)?(?:texto|text)"
            r"(?:\s+(?:del|from the)\s+(?:portapapeles|clipboard))?\s+"
            r"(?:en|into)\s+(?:(?:un|una|a)\s+)?"
            r"(?:archivo|file|documento|document)\s+"
            r"(?:nuevo|nueva|new)\s+(?:de|en|of|in)\s+"
            r"(?P<application>notepad|bloc de notas)[\s?!.]*$"
        ),
    )
    if request is None or _is_negated_match(text, request):
        return None
    application = request.group("application")
    if resolve_application_catalog_app_id(application, application_names) is None:
        return None
    evidence = request.group(0).strip(" ,;:-")[:240]
    return EffectIntent(
        ("app.open", "clipboard.paste"),
        (application, evidence),
    )


def _office_document_roundtrip_intent(
    text: str,
    available: frozenset[str],
) -> EffectIntent | None:
    """Create one named Office document and read its verified identity."""

    if not {"office.document.create", "office.document.read"} <= available:
        return None
    request = _match(
        text,
        (
            r"^[¿?¡!\s]*(?:crea|crear|create|make)\s+"
            r"(?:(?:un|una|a)\s+)?"
            r"(?:(?:documento|document)\s+)?"
            r"(?:word|excel|documento|document|hoja de calculo|spreadsheet)\b"
            r".{0,80}\b(?:llamad[oa]|named|called)\b\s+"
            r"[^,;.!?]{1,120}?\s+(?:y|and)\s+"
            r"(?:lee|leer|read)\s+"
            r"(?:(?:ese|este|el|that|this|the)\s+)?"
            r"(?:mismo|same)\s+(?:documento|document)\b"
            r"(?:\s+(?:que\s+acabas\s+de\s+crear|you\s+just\s+created))?"
            r"[\s?!.]*$"
        ),
    )
    if request is None or _is_negated_match(text, request):
        return None
    evidence = request.group(0).strip(" ,;:-")[:240]
    return EffectIntent(
        ("office.document.create", "office.document.read"),
        (evidence, evidence),
    )


def _steam_install_status_intent(
    text: str,
    available: frozenset[str],
) -> EffectIntent | None:
    """Read installation status only for one literal Steam AppID."""

    if "game.install.status" not in available:
        return None
    request = _match(
        text,
        (
            r"^[¿?¡!\s]*(?:comprueba|comprobar|verifica|verificar|consulta|"
            r"check|verify|show|read)\b\s+"
            r"(?:(?:el|the)\s+)?"
            r"(?:estado|status)\s+(?:de\s+|of\s+)?"
            r"(?:la\s+|the\s+)?(?:instalacion|installation)\s+"
            r"(?:del?|of\s+the)\s+(?:appid|app id)\s+\d{1,16}[\s?!.]*$"
        ),
    )
    if request is None or _is_negated_match(text, request):
        return None
    return EffectIntent(
        ("game.install.status",),
        (request.group(0).strip(" ,;:-")[:240],),
    )


def _steam_install_cancel_active_intent(
    text: str,
    available: frozenset[str],
) -> EffectIntent | None:
    """Stop the download Steam is already running, not a torrent or a listing."""

    if "game.install.cancel.active" not in available:
        return None
    if _has(text, r"\b(?:torrent|series|pelicula|movie)\b"):
        return None
    request = _match(
        text,
        (
            r"^[¿?¡!\s]*(?:para|cancela|cancelar|cancel|stop|detene|"
            r"detener)\b.{0,96}\b(?:descarga|download|instalacion|install)"
            r"\b.{0,96}\bsteam\b.{0,48}$"
        ),
    )
    if request is None or _is_negated_match(text, request):
        return None
    return EffectIntent(
        ("game.install.cancel.active",),
        (request.group(0).strip(" ,;:-")[:240],),
    )


def _pointer_scroll_intent(
    text: str,
    available: frozenset[str],
) -> EffectIntent | None:
    """A spoken scroll is pointer motion, not a page read."""

    if "input.pointer.control" not in available:
        return None
    request = _match(
        text,
        (
            r"^[¿?¡!\s]*(?:scroll|scrollea|scrollear)\b"
            r".{0,48}\b(?:down|up|abajo|arriba|a\s+bit|un\s+poco)\b[\s?!.]*$"
        ),
    )
    if request is None or _is_negated_match(text, request):
        return None
    return EffectIntent(
        ("input.pointer.control",),
        (request.group(0).strip(" ,;:-")[:240],),
    )


def _steam_catalog_list_intent(
    text: str,
    available: frozenset[str],
) -> EffectIntent | None:
    """List the authenticated local Steam catalog from an explicit clause."""

    if "game.catalog.list" not in available:
        return None
    request = _match(
        text,
        (
            # GAMES1531 H0274 «Ver la biblioteca de Steam»: seeing or being shown
            # the library is the same read-only listing of the local manifests.
            r"^[¿?¡!\s]*(?:(?:primero|first)\s+)?"
            r"(?:enumera|enumerar|enumerate|lista|listar|list|muestra|show|"
            r"ver|mirar|mostrame|muestrame|ensename|dame|quiero\s+ver|see|view)\b"
            r"(?P<scope>[^.;!?]{0,100})"
            r"\b(?:catalogo|catalog|biblioteca|library)\b"
            r"[^.;!?]{0,80}\bsteam\b[\s?!.]*$"
        ),
    )
    if request is None or _is_negated_match(text, request):
        return None
    if _has(
        request.group("scope"),
        rf"\b(?:y|and)\s+(?:{_COVERAGE_ACTION_HEAD})\b",
    ):
        return None
    return EffectIntent(
        ("game.catalog.list",),
        (request.group(0).strip(" ,;:-")[:240],),
    )


def _resolve_clause_local_special_effects(
    clause: str,
    available: frozenset[str],
    applications: ApplicationCatalogIndex,
    games: GameCatalogIndex,
) -> EffectIntent | None:
    """Resolve bounded handlers that normally own one complete request."""

    if "browser.navigate" in available and _installed_browser_search_query(clause) is not None:
        # WEB1455 «Abre un navegador que tengas instalado y busca …»: the two
        # clauses are one reviewed navigation to the public search page.
        return EffectIntent(("browser.navigate",), (clause.strip(),))
    if "browser.navigate" in available and _youtube_search_query(clause) is not None:
        # WEB1481 «buscá videos de gatos en youtube»: one reviewed navigation
        # to YouTube's results page with the person's query.
        return EffectIntent(("browser.navigate",), (clause.strip(),))
    multiple_alarms = _multiple_alarm_schedule_intent(clause, available)
    if multiple_alarms is not None:
        return multiple_alarms
    game_target = _authenticated_game_target(clause, games)
    if game_target is not None and "game.launch" in available:
        return EffectIntent(("game.launch",), (game_target[2],))
    authenticated_request = _authenticated_application_request(
        clause,
        applications,
    )
    if authenticated_request is not None and not _is_builtin_keyboard_request(clause):
        operation, targets = authenticated_request
        if operation in available and len(targets) <= 8:
            return EffectIntent(
                tuple(operation for _ in targets),
                tuple(target for _, target in targets),
            )
    visible_click = _visible_click_intent(clause, available)
    if visible_click is not None:
        return visible_click
    if "notification.dismiss" in available and _active_alarm_stop_request(clause):
        return EffectIntent(("notification.dismiss",), (clause,))
    nominal_reminder = _nominal_reminder_lookup_title(clause)
    if nominal_reminder is not None and "reminder.resolve.exact" in available:
        return EffectIntent(("reminder.resolve.exact",), (clause,))
    if "web.search" in available and _location_recommendation_request(clause):
        return EffectIntent(("web.search",), (clause,))
    if "web.search" in available and _public_route_lookup_request(clause):
        return EffectIntent(("web.search",), (clause,))
    if "web.search" in available and _public_calendar_fact_lookup_request(clause):
        return EffectIntent(("web.search",), (clause,))
    notepad_paste = _new_notepad_paste_intent(
        clause,
        available,
        applications,
    )
    if notepad_paste is not None:
        return notepad_paste
    office_roundtrip = _office_document_roundtrip_intent(clause, available)
    if office_roundtrip is not None:
        return office_roundtrip
    steam_catalog = _steam_catalog_list_intent(clause, available)
    if steam_catalog is not None:
        return steam_catalog
    steam_status = _steam_install_status_intent(clause, available)
    if steam_status is not None:
        return steam_status
    steam_cancel = _steam_install_cancel_active_intent(clause, available)
    if steam_cancel is not None:
        return steam_cancel
    pointer_scroll = _pointer_scroll_intent(clause, available)
    if pointer_scroll is not None:
        return pointer_scroll
    if (
        "reminder.delete" in available
        and _exact_local_reminder_title(clause) is not None
    ):
        return EffectIntent(("reminder.delete",), (clause,))
    wifi_email = _wifi_email_intent(clause, available)
    if wifi_email is not None:
        return wifi_email
    return _dependent_web_navigation_intent(
        clause,
        available,
        applications,
    )


def _catalog_report_clauses(text: str) -> tuple[str, ...] | None:
    """Extract explicit noun clauses without assigning any operation."""

    report = _match(
        text,
        (
            r"^(?:(?:hazme\s+este|haz\s+este|hace\s+este)\s+"
            r"(?:chequeo|check)\s+(?:por|in)\s+"
            r"(?:partes|parts)(?:\s*[,;:.!?]+\s*|\s+)|"
            r"run\s+this\s+check\s+in\s+parts(?:\s*[,;:.!?]+\s*|\s+)|"
            r"necesito\s+(?:(?:un\s+parte\s+conjunto)|"
            r"(?:a\s+(?:combined|campaign)\s+report))"
            r"\s+(?:de|del)\s+|"
            r"i\s+need\s+a\s+combined\s+report\s+covering\s+|"
            r"(?:sin\s+omitir\s+ninguno|without\s+skipping\s+(?:any|ninguno))"
            r"\s*[,;:.!?]*\s*(?:revisa|inspect)\s+(?:en|in)\s+"
            r"(?:(?:este|this)\s+)?(?:orden|order)"
            r"(?:\s*[,;:.!?]+\s*|\s+)|"
            r"(?:ve|go)\s+(?:punto|point)\s+(?:por|by|for)\s+"
            r"(?:punto|point)\s+(?:(?:con|through|with)\s+)?)"
            r"(?P<body>.+)$"
        ),
    )
    if report is None:
        return None
    body = re.sub(
        r"(?:[,;:.!?]+\s*|\s+)(?:devolviendo|returning)\s+"
        r"(?:cada|each)\s+(?:resultado|result)\s+"
        r"(?:por\s+separado|separately)[\s.!?]*$",
        "",
        report.group("body"),
        flags=re.IGNORECASE,
    )
    return tuple(
        clause.strip(" \t\r\n,;:.!?")
        for clause in re.split(
            r"\s*(?:"
            r";\s*(?:(?:despues|then)(?:\s+check)?\b\s*[,;:.!?]*)?|"
            r"\b(?:despues|then)(?:\s+check)?\b\s*[,;:.!?]*"
            r")\s*",
            body,
            flags=re.IGNORECASE,
        )
        if clause.strip()
    )


def compound_retrieval_clauses(text: str) -> tuple[str, ...]:
    """Split an apparent sequence for advisory per-clause retrieval only.

    This deliberately grants no intent or operation authority. Speech
    recognizers routinely remove punctuation around ``después``/``then`` or
    leave a standalone ``check`` fragment; the strict effect grammar must keep
    rejecting those ambiguous forms, while retrieval may still offer each
    clause's authenticated family to the constrained model.
    """

    folded = _strip_request_envelope(_fold(re.sub(r"[\r\n]+", " . ", str(text))))
    strict = _catalog_report_clauses(folded)
    if strict is not None and 2 <= len(strict) <= 8:
        return strict
    parts = re.split(
        r"\s*(?:[.;!?]+\s*)?(?:\b(?:y\s+despues|and\s+then|"
        r"despues(?!\s+(?:de|del)\b)|then|afterwards)\b)"
        r"\s*[,;:.!?]*\s*(?:check\b\s*[,;:.!?]*\s*)?",
        folded,
        flags=re.IGNORECASE,
    )
    clauses: list[str] = []
    for part in parts:
        clause = re.sub(
            r"^check\b\s*[,;:.!?]*\s*",
            "",
            part.strip(" \t\r\n,;:.!?"),
            flags=re.IGNORECASE,
        )
        clause = re.sub(
            r"[,;:.!?]*\s*(?:devolviendo|returning)\s+"
            r"(?:cada|each)\s+(?:resultado|result)\s+"
            r"(?:por\s+separado|separately)[\s.!?]*$",
            "",
            clause,
            flags=re.IGNORECASE,
        ).strip(" \t\r\n,;:.!?")
        if clause and re.search(r"\w", clause, re.UNICODE):
            clauses.append(clause)
    return tuple(clauses) if 2 <= len(clauses) <= 8 else ()


def compound_retrieval_operation_hints(
    text: str,
    available_operations: Iterable[str],
    application_names: Iterable[str] | ApplicationCatalogIndex = (),
) -> tuple[str, ...]:
    """Return clause-local catalog candidates without granting intent authority."""

    available = tuple(available_operations)
    authenticated_applications = build_application_catalog_index(
        application_names,
    )
    hints: list[str] = []
    for clause in compound_retrieval_clauses(text):
        result = _resolve_explicit_effects_single(
            f"check {clause}",
            available,
            application_names=authenticated_applications,
        )
        if result is not None and len(result.operations) == 1:
            hints.append(result.operations[0])
            continue
        if "clipboard.read.text" in available and _has(
            clause,
            r"\b(?:texto|text)\b.{0,32}\b(?:list[oa]\s+para\s+pegar|"
            r"ready\s+(?:para|to)\s+paste)\b",
        ):
            hints.append("clipboard.read.text")
    return tuple(dict.fromkeys(hints))


def _catalog_report_composition(
    text: str,
    available: frozenset[str],
) -> EffectIntent | None:
    """Resolve an explicit, bounded catalog report without a model decode.

    Natural report requests often put the speech act only in the first clause
    and name the remaining read domains as noun phrases.  The ordinary clause
    resolver intentionally refuses those fragments in isolation.  This small
    grammar restores compositionality while remaining fail-closed: it requires
    a report wrapper, two to eight explicitly separated clauses, exactly one
    authenticated operation per clause, and zero negative/meta/device scope.

    Speech recognizers do not reliably preserve colons or semicolons.  Accept
    sentence punctuation after the authenticated wrapper and explicit
    ``then``/``despues`` boundaries as equivalent separators.  The domain
    matcher and uniqueness checks below remain unchanged, so punctuation alone
    can never manufacture an operation.
    """

    wrapper_negation = _is_negative_effect_clause(text) and not _has(
        text,
        r"^(?:sin\s+omitir\s+ninguno|without\s+skipping\s+(?:any|ninguno))\b",
    )
    if wrapper_negation or _other_device_effect_scope(text):
        return None
    clauses = _catalog_report_clauses(text)
    if clauses is None:
        return None
    if not 2 <= len(clauses) <= 8 or any(
        _is_negative_effect_clause(clause) for clause in clauses
    ):
        return None

    domains = (
        (
            "system.status",
            r"\b(?:salud\s+global|overall\s+(?:system\s+)?health|"
            r"over\s+(?:all\s+the\s+alt|or\s+layout)\s+del\s+sistema)\b",
        ),
        (
            "network.status",
            r"\b(?:acceso\s+general\s+a\s+la\s+red|general\s+(?:network\s+)?access)\b",
        ),
        (
            "wifi.status",
            r"\bwi[\s-]?fi\b.{0,32}\b(?:senal|signal|enlace|link)\b|"
            r"\b(?:senal|signal|enlace|link)\b.{0,32}\bwi[\s-]?fi\b",
        ),
        (
            "audio.status",
            r"\b(?:volumen|volume)\b.{0,32}\b(?:audio|output|salida)\b|"
            r"\baudio\s+(?:volume|output)\b",
        ),
        (
            "media.status",
            r"\b(?:lo\s+que\s+se\s+esta\s+reproduciendo|"
            r"what\s+is\s+(?:currently\s+)?playing|"
            r"what\s+is\s+(?:playing|plain)\s+ahora)\b",
        ),
        ("window.active", r"\b(?:ventana|window)\b.{0,32}\b(?:foco|focus)\b"),
        (
            "browser.tabs.list",
            r"\b(?:paginas?\s+abiertas?\s+del\s+navegador|"
            r"(?:open\s+pages|pages?\s+abiertas?)\s+(?:del|of\s+the)\s+browser|"
            r"(?:the\s+)?browsers?(?:'s)?\s+open\s+pages)\b",
        ),
        (
            "clipboard.read.text",
            r"\b(?:texto|text)\b.{0,32}\b(?:list[oa]\s+para\s+pegar|"
            r"ready\s+(?:para|to)\s+paste)\b|"
            r"\bcontext\s+ready\s+(?:para|to)\s+paste\b",
        ),
        (
            "input.keyboard.status",
            r"\b(?:distribucion\s+del\s+teclado|"
            r"keyboard\s+input\s+(?:layout|loud))\b",
        ),
        (
            "peripheral.list",
            r"\b(?:accesorios?\s+fisicos?\s+conectados?|"
            r"physical\s+accessories\s+(?:conectados?|attached)|"
            r"attached\s+physical\s+accessories)\b",
        ),
        (
            "bluetooth.device.list",
            r"\b(?:equipos?|devices?)\b.{0,32}\bbluetooth\b|"
            r"\bbluetooth\b.{0,32}\b(?:equipos?|devices?)\b",
        ),
        (
            "task.list",
            r"\b(?:tareas?|tasks?)\b.{0,32}\b(?:abiertas?|open|remain)\b|"
            r"\btask\s+screen\s+man\s+open\b",
        ),
        (
            "note.list",
            r"\b(?:(?:indice|index)\b.{0,24}\b(?:notas?|notes?)|"
            r"private[- ]note\s+index)\b",
        ),
        (
            "reminder.list",
            r"\b(?:recordatorios?|reminders?)\b.{0,32}"
            r"\b(?:programad[oa]s?|scheduled|still|todavia)\b",
        ),
        (
            "routine.list",
            r"\b(?:rutinas?|routines?)\b.{0,32}\b(?:guardad[oa]s?|saved|personal)\b|"
            r"\bsaved\s+personal\s+routines?\b|"
            r"\bsub\s*personal\s+routines?\b",
        ),
        (
            "backup.list",
            r"\b(?:copias?\s+recuperables?|recoverable\s+backup\s+copies)\b",
        ),
        (
            "game.catalog.list",
            r"\b(?:juegos?|games?|gammes)\b.{0,32}\b(?:catalogo|catalog)\b",
        ),
        (
            "calendar.event.list",
            r"\b(?:citas?\s+de\s+hoy|today(?:'s)?\s+appointments?)\b",
        ),
        (
            "email.latest.read",
            r"\b(?:contenido|content)\b.{0,40}\b(?:correo|email)\b.{0,32}"
            r"\b(?:recien\s+llegado|newly\s+arrived)\b|"
            r"\b(?:contenido|content)\b.{0,40}\b(?:recien\s+llegado|"
            r"newly\s+arrived)\b.{0,24}\b(?:correo|email)\b|"
            r"\b(?:correo|email)\b.{0,40}\b(?:recien\s+llegado|newly\s+arrived)\b|"
            r"\bnewly\s+arrived\s+emails?(?:'s)?\s+contents?\b|"
            r"\b(?:content|contenido)\b.{0,40}\bnullier\s+i[dt]\b"
            r".{0,24}\b(?:mails?|emails?|correos?)\b|"
            r"\b(?:content|contenido)\b.{0,40}\bnullier\b.{0,24}"
            r"\b(?:mails?|emails?|correos?)\b",
        ),
        (
            "notification.list.due",
            r"\b(?:avisos?\s+vencidos?|overdue\s+(?:notices?|avisos?)|"
            r"over\s*do\s+avisos?)\b",
        ),
        (
            "app.installed",
            r"\b(?:(?:si|sea)\s+\S.{0,48}\s+(?:figura\s+)?instalad[oa]|"
            r"(?:whether|si)\s+\S.{0,48}\s+is\s+installed)\b",
        ),
        (
            "filesystem.known.search",
            r"\b(?:archivos?|files?)\b.{0,64}\b(?:documentos|documents)\b",
        ),
    )
    operations: list[str] = []
    evidence: list[str] = []
    for clause in clauses:
        matches = [
            operation
            for operation, pattern in domains
            if operation in available and _has(clause, pattern)
        ]
        if len(matches) != 1:
            return None
        operations.append(matches[0])
        evidence.append(clause[:240])
    if len(set(operations)) != len(operations):
        return None
    return EffectIntent(tuple(operations), tuple(evidence))


_BOUNDED_STATUS_SEQUENCE_DOMAINS = (
    ("system.status", r"\b(?:estado\s+del\s+sistema|system\s+status)\b"),
    ("audio.status", r"\b(?:estado\s+del\s+audio|audio\s+status)\b"),
    ("network.status", r"\b(?:estado\s+de\s+la\s+red|network\s+status)\b"),
    (
        "input.keyboard.status",
        r"\b(?:estado\s+del\s+teclado|keyboard\s+status)\b",
    ),
    ("input.mouse.status", r"\b(?:estado\s+del\s+raton|mouse\s+status)\b"),
    (
        "bluetooth.radio.status",
        r"\b(?:estado\s+de\s+la\s+radio\s+bluetooth|"
        r"bluetooth\s+radio\s+status)\b",
    ),
    (
        "peripheral.list",
        r"\b(?:perifericos\s+conectados|connected\s+peripherals|"
        r"attached\s+peripherals)\b",
    ),
    (
        "bluetooth.device.list",
        r"\b(?:dispositivos\s+bluetooth\s+visibles|"
        r"visible\s+bluetooth\s+devices|bluetooth\s+devices\s+visible)\b",
    ),
)


_DATED_MACHINE_REPORT = re.compile(
    r"^[¿?¡!\s]*(?:muestra|muestrame|mostra|mostrame|dime|decime|dame|"
    r"show(?:\s+me)?|tell\s+me|give\s+me)\s+(?:(?:la|el|the)\s+)?"
    r"(?P<clock>(?:fecha|date)(?:\s+(?:y|and)\s+(?:(?:la\s+|the\s+)?hora|time))?"
    r"(?:\s+(?:actual(?:es)?|current|de\s+hoy|del\s+sistema|of\s+the\s+system|system))*)"
    r"\s+(?:y|and)\s+(?P<machine>.+?)[\s.!?]*$",
    re.IGNORECASE,
)


def _dated_machine_report(text: str) -> EffectIntent | None:
    """«Muestra la fecha actual y el uso de RAM del sistema»: clock, then status.

    A show/tell head, the date (optionally with the time) and one measurable
    machine scope joined by «y/and» is a read-only plan: system.time first,
    then system.status of the scope the existing readers ground (RAM, disk…).
    The bounded sequence above needs two ordering markers; this shape has
    none. Prohibitions, hypotheticals and other devices stay out.
    """

    if (
        _is_meta_or_tool_denial(text)
        or _is_negative_effect_clause(text)
        or _other_device_effect_scope(text)
    ):
        return None
    found = _DATED_MACHINE_REPORT.match(text)
    if found is None:
        return None
    machine = found.group("machine")
    if (
        not _system_status_domain(machine)
        or not _machine_status_scopes(machine)
        or not _machine_status_scopes_are_one_reading(machine)
        or len(_request_clauses(text)) > 2
    ):
        return None
    return EffectIntent(("system.time", "system.status"), (found.group("clock"), machine))


def _bounded_status_sequence_intent(
    text: str,
    available: frozenset[str],
) -> EffectIntent | None:
    """Resolve an explicitly ordered, read-only multi-domain report."""

    if (
        _is_meta_or_tool_denial(text)
        or _is_negative_effect_clause(text)
        or _other_device_effect_scope(text)
        or not _has(
            text,
            r"\b(?:revisa|reporta?|check|comprueba|dime|show|muestra)\b",
        )
    ):
        return None
    sequence_markers = re.findall(
        r"\b(?:primero|first|despues|then|finalmente|finally)\b",
        text,
        re.IGNORECASE,
    )
    if len(sequence_markers) < 2:
        return None
    matches: list[tuple[int, str, str]] = []
    for operation, pattern in _BOUNDED_STATUS_SEQUENCE_DOMAINS:
        found = re.search(pattern, text, re.IGNORECASE)
        if found is not None:
            matches.append((found.start(), operation, found.group(0)))
    matches.sort()
    operations = tuple(operation for _, operation, _ in matches)
    if (
        not 2 <= len(operations) <= 8
        or len(set(operations)) != len(operations)
        or not set(operations) <= available
    ):
        return None
    # This shortcut reports only the status domains it recognized. If the
    # request carries more clauses than domains, at least one clause -- a note
    # to create, a message to send -- would be dropped without a trace, and the
    # mission would run as a silent subset of what was asked. Fail the shortcut
    # and let the clause resolver account for every clause instead.
    if len(_request_clauses(text)) > len(operations):
        return None
    return EffectIntent(
        operations,
        tuple(evidence[:240] for _, _, evidence in matches),
    )


# WINDOWS1537 H0263 «cambiá a la otra ventana», H0392 «enfocá la mejor»: a
# window named only by «la otra», «la mejor», «la siguiente» with nothing
# before it; the honest turn asks which. Shared with __main__'s input kinds
# and with the deferred clause reader below.
INDETERMINATE_WINDOW_CLAUSE = re.compile(
    r"[\s¡!¿?]*(?:"
    r"(?:cambia|cambiame|pasa|pasame|anda|andate|ve|salta|volve|vuelve|switch|go|jump|move)"
    r"(?:\s+(?:a|to))?\s+(?:la|the)\s+(?:otra|other|next|siguiente|anterior|previous|ultima|last|mejor|best)"
    r"(?:\s+(?:ventana|window|pestana|tab))?|"
    r"(?:enfoca|enfocame|foca|activa|activame|trae|traeme|pone|poneme|lleva|llevame|focus|bring|put)"
    r"\s+(?:la|the)\s+(?:otra|other|mejor|best|siguiente|next|anterior|previous|ultima|last|"
    r"mas\s+grande|biggest|largest|mas\s+chica|smallest|mas\s+importante|principal|main)"
    r"(?:\s+(?:ventana|window))?(?:\s+(?:al\s+frente|adelante|to\s+the\s+front|forward))?"
    r")[\s.!?¿¡]*"
)

# Reads a turn may run before asking about the other clause.
_DEFERRED_READ_OPERATIONS = frozenset({"system.time", "window.resolve"})


@dataclass(frozen=True, slots=True)
class DeferredClarification:
    """A read the turn runs now, and the kind of question its final must end with."""

    read_text: str
    kind: str
    clause: str


def _deferred_clause_kind(clause: str, available: frozenset[str]) -> str | None:
    folded = _strip_request_envelope(_fold(clause)).strip()
    if not folded:
        return None
    if INDETERMINATE_WINDOW_CLAUSE.fullmatch(folded) is not None:
        return "indeterminate_window"
    asked = resolve_explicit_clarification_intent(clause, available)
    if (
        asked is not None
        and asked.operations in {("audio.volume.adjust",), ("audio.app.volume.adjust",)}
        and asked.missing_fields == ("amount",)
    ):
        return "volume_amount"
    return None


def deferred_clarification_split(
    text: str,
    available_operations: Iterable[str],
    application_names: Iterable[str] | ApplicationCatalogIndex = (),
    game_catalog: Iterable[tuple[str, str, str]] | GameCatalogIndex = (),
) -> DeferredClarification | None:
    """AUDIO858 H0067 «subí el volumen y decime qué fecha es», H0527 «listá las
    ventanas y enfocá la mejor»: two clauses joined by «y», one a read the turn
    can do (the date, the window listing) and the other a request that needs
    a question before any effect (the amount, which window). The turn asked
    the amount and dropped the date, or listed nothing. The read runs and the
    final ends with that one question; nothing is guessed for the other clause."""

    if explicit_non_action_frame(text):
        return None
    parts = re.split(r"\s*(?:,\s*)?(?<![\w])(?:y|e|and)(?![\w])\s+", text.strip(), maxsplit=1)
    if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
        return None
    available = frozenset(available_operations)
    for read, other in ((parts[0], parts[1]), (parts[1], parts[0])):
        kind = _deferred_clause_kind(other, available)
        if kind is None:
            continue
        if _deferred_clause_kind(read, available) is not None:
            return None
        intent = resolve_explicit_effects(read, available, application_names, game_catalog)
        if (
            intent is None
            or len(intent.operations) != 1
            or intent.operations[0] not in _DEFERRED_READ_OPERATIONS
        ):
            continue
        return DeferredClarification(read.strip(), kind, other.strip())
    return None


def resolve_explicit_effects(
    text: str,
    available_operations: Iterable[str],
    application_names: Iterable[str] | ApplicationCatalogIndex = (),
    game_catalog: Iterable[tuple[str, str, str]] | GameCatalogIndex = (),
    *,
    previous_user_text: str | None = None,
) -> EffectIntent | None:
    """Resolve a bounded sequence of clause-local, closed-catalog effects."""

    if explicit_non_action_frame(text):
        return None
    folded = _strip_request_envelope(_fold(re.sub(r"[\r\n]+", " . ", text)))
    available = frozenset(available_operations)
    if (
        "filesystem.known.list" in available
        and _known_folder_recent_listing(folded.strip().rstrip(".!?")) is not None
    ):
        # FILES1433 «cuenta los archivos en el escritorio y lista los 5 mas
        # recientes»: the literal count bounds the listing; it is not a note
        # cardinality and the conjunction is one read, not two effects.
        return EffectIntent(("filesystem.known.list",), (folded,))
    deferred = deferred_clarification_split(text, available, application_names, game_catalog)
    if deferred is not None:
        # The read clause resolves alone; the other clause is asked in the final.
        return resolve_explicit_effects(
            deferred.read_text, available, application_names, game_catalog,
        )
    completed_level_request = _completed_missing_volume_level_request(
        text, previous_user_text, available,
    )
    if completed_level_request is not None:
        return resolve_explicit_effects(
            completed_level_request, available, application_names, game_catalog,
        )
    completed_message_request = _completed_missing_message_channel_request(
        text, previous_user_text, available,
    )
    if completed_message_request is not None:
        # MSGCLAR: the answered client completes the previous message request.
        return resolve_explicit_effects(
            completed_message_request, available, application_names, game_catalog,
        )
    # AUDIO1789: the shell may resume a pending objective as «<request>
    # <trusted clarification prefix> <answer>»; the two halves are read as
    # the previous request and its answer.
    if previous_user_text is None and "aclaracion confiable del usuario:" in _fold(text):
        prior, _, answer = _fold(text).partition("aclaracion confiable del usuario:")
        if prior.strip() and answer.strip():
            return resolve_explicit_effects(
                answer.strip(), available, application_names, game_catalog,
                previous_user_text=prior.strip(),
            )
    completed_app_volume_request = _completed_missing_app_volume_request(
        text, previous_user_text, available, application_names,
    )
    if completed_app_volume_request is not None:
        return resolve_explicit_effects(
            completed_app_volume_request, available, application_names, game_catalog,
        )
    completed_music_request = _completed_missing_music_request(
        text, previous_user_text, available,
    )
    if completed_music_request is not None:
        return resolve_explicit_effects(
            completed_music_request, available, application_names, game_catalog,
        )
    contextual_read = (
        "system.time" if _nominal_datetime_query(folded) else
        "window.active" if re.fullmatch(
            r"(?:(?:y|and)\s+)?(?:(?:ahora(?:\s+mismo)?|(?:right\s+)?now)\s+)?"
            r"(?:cual|which(?:\s+one)?)\s+(?:(?:esta|is)\s+(?:activa|active)|"
            r"(?:tiene|has)\s+(?:el\s+)?(?:foco|focus))"
            r"(?:\s+(?:ahora(?:\s+mismo)?|(?:right\s+)?now))?",
            folded.strip(" ¿?¡!."),
        ) else None
    )
    if previous_user_text and contextual_read in available:
        # Inherit only the immediately preceding, independently resolved read
        # request. The assistant's prose cannot authorize a read or manufacture
        # a referent; another topic or an absent antecedent stays unresolved.
        previous = resolve_explicit_effects(
            previous_user_text, available, application_names, game_catalog,
        )
        if previous is not None and previous.operations == (contextual_read,):
            return EffectIntent((contextual_read,), (folded,))
    authenticated_applications = build_application_catalog_index(
        application_names,
    )
    authenticated_games = build_game_catalog_index(game_catalog)
    browser_music = _named_browser_music_request(text)
    if "browser.navigate.named" in available and browser_music is not None and browser_music[1] is None:
        # MUSIC1827 «open Edge and play some music»: which music is asked first
        # (clarification), not an open-and-play mission with «some music».
        return None
    channel_request = client_channel_request(text)
    if "client.channel.locate" in available and channel_request is not None and channel_request[0] == "discord":
        # DISCORD1839: the channel is located and the person asked before any join.
        return EffectIntent(("client.channel.locate",), (text,))
    if "message.send.test" in available and message_draft_request(text) is not None:
        # MSG §6 (owner decision 2026-09-17): a messaging request is sent for real,
        # but the destination is forced to the owner's own test channel; the final
        # says the truth about where it went.
        return EffectIntent(("message.send.test",), (text,))
    if "message.draft" in available and message_draft_request(text) is not None:
        # MSG1837: the message is left written in the named client, never sent.
        return EffectIntent(("message.draft",), (text,))
    if "web.search" in available and _research_question_query(text) is not None:
        # WEB1831: a research order carrying a question is the public search
        # for that question, in the person's words.
        return EffectIntent(("web.search",), (text,))
    if "storage.removable.list" in available and _removable_storage_request(text):
        # USB1823: a backup or copy to a pendrive first reads which removable
        # drives are connected; nothing is copied.
        return EffectIntent(("storage.removable.list",), (text,))
    if "software.python.package.status" in available and _python_package_request(text) is not None:
        # PIP1817: installing a Python package with pip is answered by whether
        # it is already installed in the registered Pythons; nothing is installed.
        return EffectIntent(("software.python.package.status",), (text,))
    if (
        "game.entitlement.named" in available
        and steam_library_title(text) is not None
        # INSTALL1625: a game the local catalog holds is launched, not read.
        and _authenticated_game_target(folded, authenticated_games) is None
        # INSTALL1633: a near miss of an installed game or catalog application,
        # or a catalog application itself, keeps its own path (clarifier, open).
        and not near_catalog_game_candidates(text, authenticated_games)
        and not near_catalog_application_candidates(text, authenticated_applications)
        and resolve_application_catalog_app_id(text, authenticated_applications) is None
    ):
        # INSTALL1617: a Steam download, install or uninstall of a named game
        # first reads whether the title is in the person's library and on disk;
        # the install effect itself needs an entitlement and a confirmation,
        # and most such requests name games the library does not hold.
        return EffectIntent(("game.entitlement.named",), (text,))
    if (
        "app.installed" in available
        and installed_catalog_application_name(text, authenticated_applications) is not None
    ):
        # INSTALL1625: installing or uninstalling a catalog application is
        # answered by its presence; nothing is installed or removed.
        return EffectIntent(("app.installed",), (text,))
    if "browser.control" in available and browser_new_tab_arguments(text) is not None:
        # BROWSER1493 «abrí una pestaña nueva»: one new blank tab in the
        # product's browser, verified by its presence.
        return EffectIntent(("browser.control",), (text,))
    if "browser.control" in available and browser_close_all_tabs_arguments(text) is not None:
        # BROWSER1841 «cerrá todas las pestañas»: close every open tab in the
        # product's own browser, verified by their absence.
        return EffectIntent(("browser.control",), (text,))
    if "browser.control" in available and browser_back_arguments(text) is not None:
        # A complete history request is not a destination to search.
        return EffectIntent(("browser.control",), (text,))
    if (
        "window.minimize.all" in available
        and minimize_all_request(folded)
        and not _is_negative_effect_clause(folded)
    ):
        # MINALL1687: every desktop window minimized and verified iconic.
        return EffectIntent(("window.minimize.all",), (text,))
    if (
        "window.close.all" in available
        and close_all_request(folded)
        and not _is_negative_effect_clause(folded)
    ):
        # CLOSEALL1733: every desktop window asked to close, except the editor.
        return EffectIntent(("window.close.all",), (text,))
    if (
        {"window.resolve", "media.control"} <= available
        and conditional_open_pause_app(text, authenticated_applications) is not None
        and not _is_negative_effect_clause(folded)
    ):
        # MUSIC1675 «si tengo spotify abierto pausalo»: the window read decides
        # the condition; an absent window ends the mission truthfully, a
        # present one pauses that application's session.
        return EffectIntent(("window.resolve", "media.control"), (text, text))
    if (
        "window.snap" in available
        and resolve_application_snap(text, authenticated_applications) is not None
        and not _is_negative_effect_clause(folded)
        and not _is_meta_or_tool_denial(folded)
    ):
        # ARRANGE1781 «poné chrome a la izquierda»: docking an authenticated
        # application on one half of the screen is window.snap; window.resolve
        # (its prerequisite) binds the window.
        return EffectIntent(("window.snap",), (folded,))
    if (
        "window.minimize" in available
        and resolve_application_minimize_name(text, authenticated_applications) is not None
        and not _is_negative_effect_clause(folded)
        and not _is_meta_or_tool_denial(folded)
    ):
        # WINDOWS1695 «Minimisa ópera.»: minimizing an authenticated application
        # by name is window.minimize; window.resolve binds its window.
        return EffectIntent(("window.minimize",), (folded,))
    if (
        "window.focus" in available
        and resolve_application_focus_name(text, authenticated_applications) is not None
        and not _is_negative_effect_clause(folded)
        and not _is_meta_or_tool_denial(folded)
    ):
        # WINDOWS1385: bringing an authenticated application to the front is
        # window.focus; window.resolve (its prerequisite) binds the window.
        return EffectIntent(("window.focus",), (folded,))
    destination = _symbolic_web_destination(text)
    if (
        destination is not None
        and {"web.search", "browser.navigate"} <= available
        and _authenticated_application_request(folded, authenticated_applications) is None
        and resolve_application_catalog_app_id(destination, authenticated_applications) is None
    ):
        # Resolve the destination through the existing verified search dependency.
        return EffectIntent(("web.search", "browser.navigate"), (text, text))
    if (
        "app.open" in available
        and _repeated_application_target(text, authenticated_applications) is not None
    ):
        return EffectIntent(("app.open",), (text,))
    browser_music = _named_browser_music_request(text)
    if "browser.navigate.named" in available and browser_music is not None and browser_music[1] is not None:
        # MUSIC1827 «pon música de rock en chrome»: YouTube's results page for
        # the person's words, in the named browser, after the root review.
        return EffectIntent(("browser.navigate.named",), (text,))
    if "browser.navigate.named" in available and _named_browser_search(text) is not None:
        return EffectIntent(("browser.navigate.named",), (text,))
    if (
        "app.installed" in available
        and unresolved_application_open_name(text, authenticated_applications) is not None
    ):
        # Identity is still pending. Read once under the original opening
        # objective; no app.open step or plan is inferred from this result.
        return EffectIntent(("app.installed",), (text,))
    if (
        "app.installed" in available
        and resolve_game_catalog_app_id(text, authenticated_games) is None
        and not near_catalog_application_candidates(text, authenticated_applications)
        and not near_catalog_game_candidates(text, authenticated_games)
        and not _has(folded, rf"\b{_NAMED_PUBLIC_SITE}\b")
        and _symbolic_web_destination(text) is None
        # Only the plain open verbs: «lanzá X» or «ejecutá X» name a game or a
        # program run, not a Start-catalog presence to prove.
        and _has(folded, r"^[¿?¡!\s]*(?:(?:por favor|please)\s*[,;:]?\s*)?(?:me\s+)?(?:abre|abri|abris|abrime|abrir|open)\b")
        and unresolved_application_open_name(
            text, authenticated_applications, proper_name=True,
        ) is not None
    ):
        # APPS1549 «Y quema, abre Saint Rose.»: a proper name that no catalog,
        # near name or public site claims is read once as an application
        # presence; the verified absence lets the reply name it truthfully.
        return EffectIntent(("app.installed",), (text,))
    alias_plan = exact_catalog_operation_plan(folded)
    if alias_plan is not None and set(alias_plan) <= available:
        return EffectIntent(alias_plan, tuple(folded for _ in alias_plan))
    if (
        {"system.process.list", "filesystem.write.text"} <= available
        and process_report_file_request(folded) is not None
        and not _is_negative_effect_clause(folded)
        and not _is_meta_or_tool_denial(folded)
    ):
        # FILES1705: the listing is read first; the file carries what was read.
        return EffectIntent(("system.process.list", "filesystem.write.text"), (folded, folded))
    if "filesystem.write.text" in available and _file_creation_request(folded) is not None:
        # A named file with literal content is a write, not a note.
        return EffectIntent(("filesystem.write.text",), (folded,))
    if (
        "document.pdf.read" in available
        and _pdf_summary_request(folded) is not None
        and not _is_negative_effect_clause(folded)
        and not _is_meta_or_tool_denial(folded)
    ):
        # PDF1689: the named PDF is read once for its text; the reply presents it.
        return EffectIntent(("document.pdf.read",), (folded,))
    if (
        "filesystem.known.trash.named" in available
        and _file_trash_request(folded) is not None
        and not _is_negative_effect_clause(folded)
        and not _is_meta_or_tool_denial(folded)
        and not _has_contradictory_correction(folded)
    ):
        # A named file deletion is the recoverable trash of that one file.
        return EffectIntent(("filesystem.known.trash.named",), (folded,))
    if (
        "system.settings.status" in available
        and brightness_status_request(folded)
        and not _is_negative_effect_clause(folded)
        and not _is_meta_or_tool_denial(folded)
    ):
        # BRIGHT1283: the brightness question is a read of the monitor value.
        return EffectIntent(("system.settings.status",), (folded,))
    if (
        "system.settings.adjust" in available
        and _literal_brightness_adjustment(folded) is not None
        and not _is_negative_effect_clause(folded)
        and not _is_meta_or_tool_denial(folded)
        and not _has_contradictory_correction(folded)
    ):
        return EffectIntent(("system.settings.adjust",), (folded,))
    if (
        "system.settings.set" in available
        and _literal_brightness_level(folded) is not None
    ):
        # BRIGHT1287: an absolute brightness level is the sensitive set (confirmation).
        return EffectIntent(("system.settings.set",), (folded,))
    if (
        "clipboard.write.text" in available
        and literal_clipboard_write_text(text) is not None
        and not _is_meta_or_tool_denial(folded)
        and not _has_contradictory_correction(folded)
    ):
        # CLIPBOARD1359: a quoted or colon-introduced literal for the clipboard
        # is the sensitive write (confirmation). The raw text is the evidence so
        # the literal keeps its case and accents.
        return EffectIntent(("clipboard.write.text",), (text,))
    if (
        "filesystem.create.directory" in available
        and _directory_creation_request(folded) is not None
    ):
        return EffectIntent(("filesystem.create.directory",), (folded,))
    clauses = _request_clauses(folded)
    explicit_cardinality = _unresolved_explicit_cardinality(folded)
    if not folded or len(folded) > 16_384:
        return None
    note_dependency_order = enumerated_note_dependency_order(folded)
    if note_dependency_order and {"note.create", "note.read"} <= available:
        note_count = len(note_dependency_order)
        operations = ("note.create",) * note_count + ("note.read",) * note_count
        return EffectIntent(operations, tuple(folded for _ in operations))
    dated_report = _dated_machine_report(folded)
    if dated_report is not None and {"system.time", "system.status"} <= available:
        # SYSTEM1367: «muestra la fecha actual y el uso de RAM del sistema»
        # is one clock read and then one status read of the named scope.
        return dated_report
    status_sequence = _bounded_status_sequence_intent(folded, available)
    if status_sequence is not None:
        return status_sequence
    if _underspecified_video_request(folded):
        return None
    alarm_status_request = (
        re.fullmatch(
            r"(?:(?:(?:please\s+)?tell\s+me|show\s+me|muestra|dime)\s+"
            r"(?:what|which|que|cuales)?\s*(?:alarms?|alarmas?)\s+"
            r"(?:are\s+on|are\s+active|estan\s+activas?|hay)|"
            r"(?:is\s+there|hay)\s+(?:(?:an?|una?)\s+)?(?:alarm|alarma)\s+"
            r"(?:for|at|para|a\s+las?)\s+\S.{0,48}|"
            r"(?:check|comprueba|revisa)\s+(?:if|si)\s+"
            r"(?:(?:an?|una?)\s+)?(?:alarm|alarma)\s+"
            r"(?:is\s+set|esta\s+puesta|esta\s+programada)\s+"
            r"(?:for|at|para|a\s+las?)\s+\S.{0,48})[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    if "notification.diagnose" in available and alarm_status_request:
        return EffectIntent(("notification.diagnose",), (folded,))
    if "notification.schedule" in available and _direct_alarm_schedule_request(folded):
        return EffectIntent(("notification.schedule",), (folded,))
    direct_named_website = (
        re.fullmatch(
            r"(?:go|take\s+me|navigate|open|ve|llevame|navega)\s+"
            r"(?:to\s+|a\s+)?(?:(?:the|el|la)\s+)?"
            r"(?:washington\s+post|new\s+york\s+times|bbc|cnn)\s+"
            r"(?:website|site|web|sitio|pagina)[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    if "browser.navigate" in available and direct_named_website:
        return EffectIntent(("browser.navigate",), (folded,))
    persistent_mute = (
        re.fullmatch(
            r"(?:de\s+ahora\s+en\s+adelante|from\s+now\s+on)\s+"
            r"(?:en\s+)?(?:mudo|mute|silent|silencio)[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    if "audio.mute" in available and persistent_mute:
        return EffectIntent(("audio.mute",), (folded,))
    if "note.search" in available and _stored_note_search_query(folded) is not None:
        return EffectIntent(("note.search",), (folded,))
    if "system.time" in available and _direct_current_time_request(folded):
        return EffectIntent(("system.time",), (folded,))
    if "calendar.event.list" in available and _relative_calendar_read_request(folded):
        return EffectIntent(("calendar.event.list",), (folded,))
    if "media.play.query" in available and (
        _direct_media_discovery_or_play_request(folded)
        # VIDEO1715: the readers fold the text themselves; the raw text keeps
        # the capitals that mark a proper title («poné Tom and Jerry»).
        or _desired_music_query(text) is not None
    ):
        evidence = text if _explicit_named_music_query(text) is not None else folded
        if (
            "media.play.youtube" in available
            and not _has(folded, r"\bspotify\b")
            and _explicit_named_music_query(text) is not None
        ):
            # MUSIC1559: no provider named → the local YouTube playback.
            return EffectIntent(("media.play.youtube",), (evidence,))
        return EffectIntent(("media.play.query",), (evidence,))
    if "web.search" in available and _public_live_lookup_request(folded):
        # WEB1445: the evidence keeps the person's accents («mañana»); the
        # engine answers the literal phrase and not its folded form.
        return EffectIntent(("web.search",), (text.strip(),))
    if {
        "message.recipient.resolve",
        "message.send",
        "task.list",
    } <= available and _has(
        folded,
        r"^por\s+whatsapp\s+(?:avisa|notifica|dile)\s+a\s+[^,;:.!?]{1,80}\s+"
        r"que\s+[^;:.!?]{1,240}\s+y\s+(?:luego|despues)\s+"
        r"(?:muestra|lista|ensena)me\s+(?:mis|las)\s+tareas?\s+abiertas?"
        r"[\s.!?]*$",
    ):
        # The message grammar deliberately consumes free-form body text.  Keep
        # the following task lookup outside that body only for this explicit,
        # bounded two-step construction.
        return EffectIntent(
            ("message.recipient.resolve", "message.send", "task.list"),
            (folded[:240], folded[:240], folded[:240]),
        )
    message_collection = _match(
        folded,
        r"^(?:dile|avisale|avisa|notifica(?:le)?)\s+a\s+[^,;:.!?]{1,80}\s+"
        r"por\s+whatsapp\s+que\s+[^;:.!?]{1,240}\s+y\s+"
        r"(?:luego|despues)\s+"
        r"(?:muestrame|listame|ensename|muestra|lista|ensena)\s+"
        r"(?:mis|las)\s+(?P<collection>tareas?\s+abiertas?|notas?)"
        r"[\s.!?]*$",
    )
    message_collection_operation = (
        "note.list"
        if message_collection is not None
        and _has(message_collection.group("collection"), r"\bnotas?\b")
        else "task.list"
    )
    if (
        message_collection is not None
        and {
            "message.recipient.resolve",
            "message.send",
            message_collection_operation,
        }
        <= available
    ):
        return EffectIntent(
            (
                "message.recipient.resolve",
                "message.send",
                message_collection_operation,
            ),
            (folded[:240], folded[:240], folded[:240]),
        )
    message_reminders = _match(
        folded,
        r"^(?:send|envia|manda|dile|avisa|notifica)\s+"
        r"[^,;:.!?]{1,80}\s+(?:on|por|en)\s+whatsapp\s+"
        r"(?:que|that)\s+\S.{1,240}?\s+"
        r"(?:y\s+then|and\s+then|y\s+luego|y\s+despues)\s+"
        r"(?:show|list|muestra|lista)(?:me)?\s+"
        r"(?:(?:my|mis|the|los|las)\s+)?"
        r"(?:(?:scheduled|programad[oa]s?)\s+)?"
        r"(?:reminders?|recordatorios?)\b[\s.!?]*$",
    )
    if (
        message_reminders is not None
        and {
            "message.recipient.resolve",
            "message.send",
            "reminder.list",
        }
        <= available
    ):
        return EffectIntent(
            ("message.recipient.resolve", "message.send", "reminder.list"),
            (folded[:240], folded[:240], folded[:240]),
        )
    collection_capture = _match(
        folded,
        r"^(?:list|show|muestra|lista)\b.{0,48}\b"
        r"(?P<collection>open\s+tasks?|tareas?\s+abiertas?|notes?|notas?)"
        r"\b\s*,?\s*(?:(?:and|y)\s+)?"
        r"(?:(?:then|despues)\s+)?"
        r"(?:capture|captura)\b.{0,32}\b"
        r"(?:screen|pantalla|view|vista|result|resultado)\b"
        r".{0,48}\b(?:and|y)\s+(?:read|lee|extract|extrae)\b"
        r".{0,32}\b(?:text|texto)\b"
        r".{0,48}\b(?:capture|captura)\b[\s.!?]*$",
    )
    collection_operation = (
        "note.list"
        if collection_capture is not None
        and _has(collection_capture.group("collection"), r"\b(?:notes?|notas?)\b")
        else "task.list"
    )
    if (
        collection_capture is not None
        and {
            collection_operation,
            "capture.screenshot",
            "ocr.read",
        }
        <= available
    ):
        return EffectIntent(
            (collection_operation, "capture.screenshot", "ocr.read"),
            (folded[:240], folded[:240], folded[:240]),
        )
    collection_capture_vision = _match(
        folded,
        r"^(?:list|show|muestra|lista)\b.{0,48}\b"
        r"(?P<collection>open\s+tasks?|tareas?\s+abiertas?|notes?|notas?)"
        r"\b\s*,?\s*(?:(?:and|y)\s+)?"
        r"(?:(?:then|despues)\s+)?"
        r"(?:capture|captura)\b.{0,32}\b"
        r"(?:screen|pantalla|view|vista|result|resultado)\b"
        r".{0,48}\b(?:and|y)\s+describe\b.{0,48}\b"
        r"(?:image|imagen|what\s+appears|lo\s+que\s+aparece)\b"
        r"[\s.!?]*$",
    )
    collection_vision_operation = (
        "note.list"
        if collection_capture_vision is not None
        and _has(
            collection_capture_vision.group("collection"),
            r"\b(?:notes?|notas?)\b",
        )
        else "task.list"
    )
    if (
        collection_capture_vision is not None
        and {
            collection_vision_operation,
            "capture.screenshot",
            "vision.describe",
        }
        <= available
    ):
        return EffectIntent(
            (
                collection_vision_operation,
                "capture.screenshot",
                "vision.describe",
            ),
            (folded[:240], folded[:240], folded[:240]),
        )
    if {
        "capture.screenshot",
        "vision.describe",
    } <= available and _has(
        folded,
        r"^(?:obten|toma|take|get|capture|captura)\b.{0,48}\b"
        r"(?:capture|captura|screenshot|image|imagen)\b.{0,48}\b"
        r"(?:screen|pantalla)\b.{0,64}\b(?:and|y)\s+describe\b"
        r".{0,64}\b(?:same|misma|esa\s+misma|that\s+same)\s+"
        r"(?:capture|captura|image|imagen)\b[\s.!?]*$",
    ):
        return EffectIntent(
            ("capture.screenshot", "vision.describe"),
            (folded[:240], folded[:240]),
        )
    if {
        "capture.screenshot",
        "ocr.read",
    } <= available and _has(
        folded,
        r"^(?:(?:obten|toma|take|get)\b.{0,40}\b"
        r"(?:captura|screenshot|snapshot)\b.{0,96}\b(?:usa|use)\b"
        r".{0,48}\b(?:imagen|image|captura|capture)\b.{0,96}\b"
        r"(?:transcribe|transcribir|read|extract)\b.{0,48}\b"
        r"(?:letras?|texto|text|words?)\b(?:\s+visibles?)?|"
        r"(?:(?:(?:take|toma|get|obten)\s+(?:(?:a|una?)\s+)?)?"
        r"(?:screen\s+capture|captura\b.{0,32}\b(?:screen|pantalla)|"
        r"capture\b.{0,32}\b(?:screen|pantalla)))\b.{0,64}\b"
        r"(?:and|y)\s+(?:read|lee|transcribe|extract|extrae)\b.{0,48}\b"
        r"(?:visible\s+words?|palabras?\s+visibles?)\b.{0,64}\b"
        r"(?:image|imagen)\b)[\s.!?]*$",
    ):
        return EffectIntent(
            ("capture.screenshot", "ocr.read"),
            (folded[:240], folded[:240]),
        )
    if {
        "capture.screenshot",
        "vision.describe",
        "ocr.read",
    } <= available and _has(
        folded,
        r"^(?:(?:take|toma|get|obten)\s+(?:(?:a|the|una?)\s+)?)?"
        r"(?:capture|captura|screenshot)\b"
        r"(?:.{0,48}\b(?:desktop|screen|escritorio|pantalla)\b)?.{0,80}\b"
        r"describe\b.{0,48}\b(?:scene|escena|image|imagen)\b.{0,80}\b"
        r"(?:and|y)\s+(?:transcribe|read|extract|lee)\b.{0,48}\b"
        r"(?:text|texto|words?|palabras?)\b.{0,64}\b"
        r"(?:same|misma|exact|esa)\b.{0,24}\b"
        r"(?:image|imagen|capture|captura)\b[\s.!?]*$",
    ):
        return EffectIntent(
            ("capture.screenshot", "vision.describe", "ocr.read"),
            (folded[:240],) * 3,
        )
    if {
        "calendar.event.list",
        "capture.screenshot",
        "vision.describe",
        "clipboard.read.text",
    } <= available and _has(
        folded,
        r"^(?:display|show|muestra|ensena(?:me)?)\b.{0,48}\b"
        r"(?:calendar|calendario|(?:today|tomorrow)(?:'s)?\s+"
        r"(?:appointments?|events?)|(?:citas?|eventos?)\s+(?:de\s+)?"
        r"(?:hoy|manana))\b.{0,64}\b"
        r"(?:screenshot|capture|captura)\b.{0,64}\b"
        r"describe\b.{0,64}\b(?:view|vista|image|imagen|"
        r"lo\s+que\s+aparece|what\s+appears)\b.{0,64}\b"
        r"(?:read|lee)\b(?:(?:.{0,32}\b(?:clipboard|portapapeles)\b"
        r".{0,24}\b(?:text|texto)\b)|(?:.{0,32}\b(?:text|texto)\b"
        r".{0,32}\b(?:clipboard|portapapeles)\b))[\s.!?]*$",
    ):
        return EffectIntent(
            (
                "calendar.event.list",
                "capture.screenshot",
                "vision.describe",
                "clipboard.read.text",
            ),
            (folded[:240],) * 4,
        )
    catalog_report = _catalog_report_composition(folded, available)
    if catalog_report is not None:
        return catalog_report
    report_clauses = _catalog_report_clauses(folded)
    if report_clauses is not None and len(report_clauses) >= 2:
        # The wrapper proves this is one multi-domain report. If any spoken
        # clause cannot be grounded to exactly one operation, falling through
        # would silently execute only the recognizable subset.
        return None
    spoken_report_markers = len(
        re.findall(
            r"\b(?:despues|then)(?:\s+check)?\b",
            folded,
            flags=re.IGNORECASE,
        )
    )
    spoken_report_minimum = (
        spoken_report_markers + 1
        if spoken_report_markers >= 2
        and _has(folded, r"\b(?:por\s+separado|separately)\b")
        else None
    )
    strict_request = _strict_catalog_request(
        folded,
        available,
        authenticated_applications,
    )
    if (
        strict_request is not None
        and spoken_report_minimum is not None
        and len(strict_request.operations) < spoken_report_minimum
    ):
        return None
    if (
        strict_request is not None
        and "task.list" in available
        and "task.list" not in strict_request.operations
        and _has(
            folded,
            r"\b(?:y\s+luego|y\s+despues|and\s+then)\s+"
            r"(?:lista|listar|muestra|show|list)\w*\b.{0,32}"
            r"\b(?:tareas?|tasks?)\b",
        )
    ):
        return None
    strict_capture_pipeline = (
        strict_request is not None
        and strict_request.operations
        in {
            ("capture.screenshot", "ocr.read"),
            ("capture.screenshot", "vision.describe"),
        }
    )
    strict_streaming_pipeline = (
        strict_request is not None
        and strict_request.operations == ("streaming.play.named",)
        and _has(
            folded,
            r"(?:\b(?:y|and)\b|[;,])\s+(?:ponla|ponlo|reproducela|reproducelo|"
            r"put\s+it(?:\s+on)?|start\s+it|"
            r"start\s+the\s+(?:show|movie|title|series))"
            r"(?:\s+(?:from|on|through)\s+netflix)?"
            r"[\s.!?]*$",
        )
    )
    strict_package_pipeline = (
        strict_request is not None
        and strict_request.operations == ("package.install.prepare",)
        and _has(
            folded,
            r"(?<![a-z0-9._-])[a-z0-9][a-z0-9_-]+"
            r"(?:\.[a-z0-9_-]+)+(?![a-z0-9_-]|\.[a-z0-9_-])",
        )
        and not _has(
            folded,
            r"\b(?:juego|game|steam|nota|note|tarea|task|mensaje|message)\b",
        )
    )
    strict_email_pipeline = (
        strict_request is not None
        and strict_request.operations == ("email.latest.read",)
        and _has(
            folded,
            r"^(?:abre|open)\b.{0,24}\b(?:lee|read)\b",
        )
    )
    strict_message_pipeline = (
        strict_request is not None
        and strict_request.operations == ("message.recipient.resolve", "message.send")
    )
    strict_media_alternative = (
        strict_request is not None
        and strict_request.operations == ("media.status",)
        and _has(
            folded,
            r"\b(?:pista|track)\s+(?:o|or)\s+(?:video|audio)\b",
        )
    )
    strict_audited_composition = (
        strict_request is not None
        and 2 <= len(strict_request.operations) <= 8
        and _strict_composition_segments_are_grounded(
            folded,
            strict_request,
            available,
            authenticated_applications,
        )
    )
    strict_referential_followup = (
        strict_request is not None
        and len(strict_request.operations) == 1
        and _has(
            folded,
            r"[?;]\s*(?:revisal[oa]s?|compruebalo|verificalo|leel[oa]s?|"
            r"check(?:\s+(?:it|them))?|verify(?:\s+it)?|read\s+them|"
            r"dame\s+(?:el\s+)?estado|give\s+me\s+(?:the\s+)?"
            r"(?:state|status))[\s.!?]*$",
        )
    )
    strict_single_domain_attributes = (
        strict_request is not None
        and len(strict_request.operations) == 1
        and _has(
            folded,
            r"\b(?:por\s+donde\s+y\s+a\s+que\s+nivel|"
            r"volume\s+and\s+output\s+routing|"
            r"(?:link|enlace)\s+(?:and|y)\s+(?:signal|senal)|"
            r"(?:signal|senal)\s+(?:and|y)\s+(?:link|enlace))\b",
        )
    )
    strict_single_domain_confirmation = (
        strict_request is not None
        and strict_request.operations == ("app.installed",)
        and _has(
            folded,
            r"\b(?:programas?|programs?)\b.{0,64}\b(?:y|and)\s+"
            r"(?:confirma|confirm)\b.{0,48}\b(?:presencia|presence)\b",
        )
    )
    if strict_request is not None and (
        (
            len(clauses) == 1
            and (
                len(strict_request.operations) == 1
                or strict_request.operations
                == ("message.recipient.resolve", "message.send")
            )
        )
        or strict_capture_pipeline
        or strict_streaming_pipeline
        or strict_package_pipeline
        or strict_email_pipeline
        or strict_message_pipeline
        or strict_media_alternative
        or strict_audited_composition
        or strict_referential_followup
        or strict_single_domain_attributes
        or strict_single_domain_confirmation
    ):
        return strict_request
    if (
        strict_request is not None
        and len(strict_request.operations) >= 2
        and len(clauses) == 1
    ):
        # Do not let the generic clause loop re-admit a strict multi-operation
        # candidate whose coordinated segments were not all accounted for.
        return None
    if "notification.schedule" in available and _wake_alarm_request(folded):
        return EffectIntent(("notification.schedule",), (folded,))
    if "network.ip.list" in available and _ip_list_request(folded):
        return EffectIntent(("network.ip.list",), (folded,))
    steam_cancel = _steam_install_cancel_active_intent(folded, available)
    if steam_cancel is not None:
        return steam_cancel
    pointer_scroll = _pointer_scroll_intent(folded, available)
    if pointer_scroll is not None:
        return pointer_scroll
    if (
        "media.play.query" in available
        and re.fullmatch(
            r"(?:comfort|soothe)\s+my\s+ears\s+with\s+\S.{0,120}[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    ):
        return EffectIntent(("media.play.query",), (folded,))
    if "note.create" in available and _literal_memo_payload(folded) is not None:
        return EffectIntent(("note.create",), (folded,))
    if "note.search" in available and _historical_note_search_request(folded):
        return EffectIntent(("note.search",), (folded,))
    if "reminder.create" in available and _time_only_reminder_request(folded):
        return None
    multiple_alarms = _multiple_alarm_schedule_intent(folded, available)
    if multiple_alarms is not None:
        return multiple_alarms
    corrected_game_title = _corrected_game_launch_title(folded)
    if corrected_game_title is not None and "game.launch" in available:
        corrected_game = _authenticated_game_target(
            "lanza " + corrected_game_title,
            authenticated_games,
        )
        if corrected_game is not None:
            return EffectIntent(("game.launch",), (corrected_game[2],))
    game_target = _authenticated_game_target(folded, authenticated_games)
    if game_target is not None and "game.launch" in available:
        _, _, display_name = game_target
        return EffectIntent(("game.launch",), (display_name,))
    authenticated_request = _authenticated_application_request(
        folded,
        authenticated_applications,
    )
    if authenticated_request is not None and not _is_builtin_keyboard_request(folded):
        operation, targets = authenticated_request
        if operation not in available or len(targets) > 8:
            return None
        return EffectIntent(
            tuple(operation for _ in targets),
            tuple(target for _, target in targets),
        )
    if (
        len(clauses) == 1
        and "web.search" in available
        and (
            _public_live_lookup_request(folded)
            or _public_route_lookup_request(folded)
            or _public_calendar_fact_lookup_request(folded)
        )
    ):
        # Weather and news are live feeds, not stable model knowledge. Their
        # literal domain closes the read request without relying on a semantic
        # family guess; Core still validates and verifies the public lookup.
        # WEB1445: the evidence keeps the person's accents («mañana»); the
        # engine answers the literal phrase and not its folded form.
        return EffectIntent(("web.search",), (text.strip(),))
    if "web.search" in available and _public_product_correction_lookup_request(folded):
        # The correction replaces the nominal query; it is not a second
        # physical effect. Keep this read-only and let Core verify the lookup.
        return EffectIntent(("web.search",), (folded,))
    if "web.search" in available and _public_commerce_lookup_request(folded):
        return EffectIntent(("web.search",), (folded,))
    shared_domain_minimum = _coordinated_effect_domain_minimum(folded)
    if _has_unresolved_shared_head_coordination(folded):
        shared_domain_minimum = max(2, shared_domain_minimum or 0)
    if (
        _is_meta_or_tool_denial(folded)
        or _has_contradictory_correction(folded, available)
        or _other_device_effect_scope(folded)
        or (
            _has_unsupported_deferred_effect(folded)
            and not _location_recommendation_request(folded)
        )
        or _has_multiple_installed_entities(folded)
        or (
            explicit_cardinality is not None
            and not _has_fully_enumerated_note_cardinality(
                clauses,
                explicit_cardinality,
            )
        )
        or (
            not _is_direct_request(_without_leading_duration_preface(folded))
            and not _count_down_request(folded)
            # A conjunction does not make independently explicit questions
            # implicit. The clause resolver below must still account for all
            # of them; this never grants a recognized subset authority.
            and not (
                len(clauses) > 1
                and all(_is_direct_request(clause) for clause in clauses)
            )
            and not _bounded_calendar_list_query(folded)
            and not _location_recommendation_request(folded)
            and _nominal_reminder_lookup_title(folded) is None
            and _exact_local_reminder_title(folded) is None
            and not _literal_note_payload_request(folded)
            and not _bare_note_inventory_request(folded)
            and not (
                _has(folded, r"^can i (?:see|view)\b")
                and _has(folded, r"\b(?:reminder|recordatorio)\b")
                and _has(folded, r"\b(?:again|otra vez|de nuevo)\b")
            )
            and not _active_alarm_stop_request(folded)
            and not any(
                _authenticated_application_desired_open(
                    clause,
                    authenticated_applications,
                )
                is not None
                for clause in clauses
            )
        )
    ):
        return None
    if (
        len(clauses) == 1
        and "system.power" in available
        and _has(
            folded,
            r"^(?:apaga|apagame|shutdown|shut\s+down)\b",
        )
        and _has(
            folded,
            r"\b(?:equipo|pc|compu|computador(?:a)?|computer|maquina|"
            r"machine|windows)\b",
        )
        and not _has(
            folded,
            r"\b(?:telefono|movil|celular|phone|smartphone|tablet|iphone)\b",
        )
    ):
        return EffectIntent(("system.power",), (folded,))
    if "audio.app.volume.adjust" in available:
        app_volume = app_volume_request(text, authenticated_applications)
        if app_volume is not None and app_volume[2] is not None:
            # AUDIO1787 «subí el volumen de spotify en 20»: the application
            # volume with its authored amount is one verified adjustment.
            return EffectIntent(("audio.app.volume.adjust",), (folded,))
    if (
        len(clauses) <= 2
        and "audio.volume.adjust" in available
        and _volume_domain(folded)
        and _has(folded, r"\b(?:bajalo|bajala|subelo|subela)\b")
        and not _has(
            folded,
            r"\b(?:y|and)\s+(?:abre|open|crea|create|apaga|silencia)\b",
        )
    ):
        return EffectIntent(("audio.volume.adjust",), (folded,))
    if (
        len(clauses) == 1
        and "audio.volume" in available
        and _volume_domain(folded)
        and _has(folded, r"\ba la mitad\b|\bto half\b")
    ):
        return EffectIntent(("audio.volume",), (folded,))
    visible_click = _visible_click_intent(folded, available)
    if visible_click is not None:
        return visible_click
    if "notification.dismiss" in available and _active_alarm_stop_request(folded):
        return EffectIntent(("notification.dismiss",), (folded,))
    nominal_reminder = _nominal_reminder_lookup_title(folded)
    if nominal_reminder is not None and "reminder.resolve.exact" in available:
        return EffectIntent(("reminder.resolve.exact",), (folded,))
    if "web.search" in available and _location_recommendation_request(folded):
        # Temporal phrases such as "después de la medianoche" are query
        # constraints, not composition separators. Preserve the complete
        # request before the generic clause splitter sees "después".
        return EffectIntent(("web.search",), (folded,))
    notepad_paste = _new_notepad_paste_intent(
        folded,
        available,
        authenticated_applications,
    )
    if notepad_paste is not None:
        return notepad_paste
    if (
        "reminder.delete" in available
        and _exact_local_reminder_title(folded) is not None
    ):
        return EffectIntent(("reminder.delete",), (folded,))
    wifi_email = _wifi_email_intent(folded, available)
    if wifi_email is not None:
        return wifi_email
    authenticated_list = _authenticated_application_list(
        folded,
        authenticated_applications,
    ) or _authenticated_application_list(
        folded,
        authenticated_applications,
        installed_query=True,
    )
    if authenticated_list:
        direct_applications = _resolve_explicit_effects_single(
            folded,
            available,
            application_names=authenticated_applications,
        )
        if (
            direct_applications is not None
            and len(direct_applications.operations) == len(authenticated_list)
            and all(
                operation in {"app.open", "app.installed"}
                for operation in direct_applications.operations
            )
        ):
            return direct_applications

    records: list[dict[str, str | None]] = []
    context_browser: str | None = None
    context_spotify = False
    context_steam = False
    context_open_application = False
    context_capture = False
    context_note = False
    context_audio = False
    context_machine = False
    enumerated_note_create_count = 0
    context_window_active = _has(
        folded,
        r"\b(?:ventana|window)\b",
    ) and _has(
        folded,
        r"\b(?:activa|active|actual|current)\b",
    )
    clause_index = 0
    while clause_index < len(clauses):
        clause = clauses[clause_index]
        consumed_clauses = 1
        local_browser = _named_browser(clause)
        authenticated_opened = _authenticated_application_list(
            clause,
            authenticated_applications,
        )
        if not authenticated_opened:
            authenticated_target = _authenticated_application_target(
                clause,
                authenticated_applications,
            )
            authenticated_opened = (
                (authenticated_target,) if authenticated_target is not None else ()
            )
        result = None
        # Some closed handlers represent one semantic effect group using
        # several coordinated action heads (for example, connect Wi-Fi, open
        # mail, and read the latest message).  The generic splitter separates
        # those heads so independent effects can compose.  Reassemble only the
        # shortest prefix that a bounded handler can account for, leaving any
        # following clause available to the rest of the mission.
        maximum_group_size = min(4, len(clauses) - clause_index)
        for group_size in range(1, maximum_group_size + 1):
            grouped_clause = " y ".join(
                clauses[clause_index : clause_index + group_size]
            )
            result = _resolve_clause_local_special_effects(
                grouped_clause,
                available,
                authenticated_applications,
                authenticated_games,
            )
            if result is not None:
                clause = grouped_clause
                consumed_clauses = group_size
                local_browser = _named_browser(clause)
                break
        if result is None:
            result = _resolve_explicit_effects_single(
                clause,
                available,
                context_browser=context_browser,
                context_spotify=context_spotify,
                context_open_application=context_open_application,
                context_capture=context_capture,
                context_note=context_note,
                context_audio=context_audio,
                context_machine=context_machine,
                context_window_active=context_window_active,
                application_names=authenticated_applications,
            )
        if result is None and len(clauses) > 1:
            # Inside a compound request a shared observation head governs a
            # later bare domain nominal: ``revisa el teclado, ... y el estado
            # de la red``. The strict composition verifier already treats this
            # mapping as authoritative, so the resolver must agree with it or
            # the conservation veto abstains from a request the product can in
            # fact ground. The table stays closed to authenticated operations.
            nominal_operation = _strict_composition_nominal_operation(clause)
            if nominal_operation is not None and nominal_operation in available:
                result = EffectIntent((nominal_operation,), (clause,))
        if (
            result is None
            and "note.read" in available
            and enumerated_note_create_count > 0
        ):
            read_order = _fully_enumerated_note_read_order(clause)
            if read_order and all(
                index <= enumerated_note_create_count for index in read_order
            ):
                result = EffectIntent(
                    tuple("note.read" for _ in read_order),
                    tuple(clause for _ in read_order),
                )
        if (
            result is not None
            and result.operations == ("app.installed",)
            and context_steam
            and "game.installed.named" in available
            and not (
                authenticated_applications.occurrence_pattern is not None
                and authenticated_applications.occurrence_pattern.search(clause)
            )
            and installed_game_title(clause) is not None
        ):
            # APPS1613 H0275 «Abre Steam y dime si Fall Guys ya está
            # instalado»: after Steam was opened in this request, an installed
            # question about a name absent from the Start catalog asks the
            # Steam/Epic manifests, not the Start catalog.
            result = EffectIntent(("game.installed.named",), (clause,))
        if result is None:
            if (
                _is_negative_effect_clause(clause)
                or _is_social_clause(clause)
                or _is_effect_receipt_clause(clause)
                or (
                    context_capture
                    and _has(
                        clause,
                        r"^(?:guardalo|guardala|save it|"
                        r"(?:dime|tell me|show me)\s+(?:el\s+|the\s+)?"
                        r"(?:path|ruta))[\s?!.]*$",
                    )
                )
            ):
                clause_index += consumed_clauses
                continue
            return None

        if result.operations == ("note.create",):
            local_count = _fully_enumerated_note_create_count(clause)
            if local_count is not None:
                result = EffectIntent(
                    tuple("note.create" for _ in range(local_count)),
                    tuple(clause for _ in range(local_count)),
                )
                enumerated_note_create_count = local_count
        elif result.operations == ("note.read",) and enumerated_note_create_count > 0:
            read_order = _fully_enumerated_note_read_order(clause)
            if read_order:
                if any(index > enumerated_note_create_count for index in read_order):
                    return None
                result = EffectIntent(
                    tuple("note.read" for _ in read_order),
                    tuple(clause for _ in read_order),
                )

        if "browser.navigate.named" in result.operations:
            target_browser = local_browser or context_browser
            if target_browser is not None:
                for index in range(len(records) - 1, -1, -1):
                    if (
                        records[index]["operation"] == "app.open"
                        and records[index]["application"] == target_browser
                    ):
                        del records[index]
                        break
        if any(
            operation in {"media.play.exact", "media.play.query"}
            for operation in result.operations
        ):
            for index in range(len(records) - 1, -1, -1):
                if (
                    records[index]["operation"] == "app.open"
                    and records[index]["application"] == "spotify"
                ):
                    del records[index]
                    break

        opened_in_clause = _opened_applications(clause) or tuple(
            name for _, name in authenticated_opened
        )
        opened = iter(opened_in_clause)
        for operation, evidence in zip(
            result.operations,
            result.evidence,
            strict=True,
        ):
            if (
                operation == "window.active"
                and any(record["operation"] == "window.active" for record in records)
                and any(
                    candidate
                    in {
                        "window.maximize",
                        "window.minimize",
                        "window.restore",
                    }
                    for candidate in result.operations
                )
            ):
                continue
            application = next(opened, None) if operation == "app.open" else None
            records.append(
                {
                    "operation": operation,
                    "evidence": evidence,
                    "application": application,
                }
            )

        continued_application = _has(
            clause,
            rf"^(?:el|la|the)?\s*{_KNOWN_APPLICATION}[\s?!.]*$",
        )
        context_open_application = bool(opened_in_clause) or (
            context_open_application
            and continued_application
            and "app.open" in result.operations
        )
        if opened_in_clause:
            latest = opened_in_clause[-1]
            context_browser = (
                latest if latest in {"opera", "opera_gx", "chrome", "edge", "firefox"} else None
            )
            context_spotify = latest == "spotify"
            context_steam = latest == "steam"
        elif "browser.navigate.named" in result.operations:
            context_browser = local_browser or context_browser
        elif any(
            operation in {"media.play.exact", "media.play.query"}
            for operation in result.operations
        ):
            context_spotify = True
        context_capture = context_capture or ("capture.screenshot" in result.operations)
        context_note = context_note or ("note.create" in result.operations)
        context_audio = context_audio or any(
            operation.startswith("audio.") for operation in result.operations
        )
        context_machine = context_machine or any(
            operation in {"system.status", "system.process.list"}
            for operation in result.operations
        )
        clause_index += consumed_clauses

    if (
        not records
        or len(records) > 8
        or (shared_domain_minimum is not None and len(records) < shared_domain_minimum)
    ):
        return None
    operations = tuple(str(record["operation"]) for record in records)
    if spoken_report_minimum is not None and len(operations) < spoken_report_minimum:
        # Even if ASR corrupts the report wrapper, repeated sequence markers
        # plus an explicit separate-result tail preserve its cardinality. A
        # shorter operation list would execute only a recognizable subset.
        return None
    if (
        "task.list" in available
        and "task.list" not in operations
        and _has(
            folded,
            r"\b(?:y\s+luego|y\s+despues|and\s+then)\s+"
            r"(?:lista|listar|muestra|show|list)\w*\b.{0,32}"
            r"\b(?:tareas?|tasks?)\b",
        )
    ):
        # A free-form message body must not absorb an explicit following task
        # lookup when the recipient transcription is uncertain.
        return None
    return EffectIntent(
        operations,
        tuple(str(record["evidence"]) for record in records),
    )


def unresolved_compound_contract(
    text: str,
    available_operations: Iterable[str],
    application_names: Iterable[str] | ApplicationCatalogIndex = (),
    game_catalog: Iterable[tuple[str, str, str]] | GameCatalogIndex = (),
    *,
    resolved_intent: EffectIntent | None | object = (_EXPLICIT_EFFECTS_NOT_RESOLVED),
    previous_user_text: str | None = None,
) -> CompoundEffectContract | None:
    """Describe a compound whose positive clauses are not all recognized.

    This is a conservation veto, not a classifier.  If the compositional
    resolver covers the whole request there is no unresolved contract.  For
    an incomplete compound, recognized clause sequences and their true
    cardinality are retained while every unresolved positive action adds at
    least one effect.  The caller must fail closed because the unresolved
    operation identity cannot be proved by this operation-only recognizer.
    """

    available = tuple(available_operations)
    if deferred_clarification_split(text, available, application_names, game_catalog) is not None:
        # The read clause is the whole effect of the turn; the other clause
        # becomes the final's question, not an unresolved positive action.
        return None
    completed_level_request = _completed_missing_volume_level_request(
        text, previous_user_text, available,
    )
    if completed_level_request is not None:
        return unresolved_compound_contract(
            completed_level_request, available, application_names, game_catalog,
            resolved_intent=resolved_intent,
        )
    folded = _strip_request_envelope(_fold(re.sub(r"[\r\n]+", " . ", text)))
    clauses = _request_clauses(folded)
    authenticated_applications = build_application_catalog_index(
        application_names,
    )
    authenticated_request = _authenticated_application_request(
        folded,
        authenticated_applications,
    )
    if authenticated_request is not None:
        operation, targets = authenticated_request
        if len(targets) <= 8 and operation in available:
            return None
        operations = tuple(operation for _ in targets)
        return CompoundEffectContract(
            max(1, len(operations)),
            ((operations,) if operations else ()),
        )
    if authenticated_applications and _authenticated_application_identity_conflict(
        folded,
        authenticated_applications,
    ):
        return CompoundEffectContract(1, ())
    if (
        isinstance(resolved_intent, EffectIntent)
        and resolved_intent.operations == ("reminder.delete",)
        and _exact_local_reminder_title(folded) is not None
    ):
        # A subject-level negative such as ``no necesito comida para perro``
        # is the reason for the following explicit deletion, not a negation of
        # it.  This exemption is available only after the closed reminder
        # grammar extracted one exact title; ordinary ``no borres`` requests
        # still fail closed below.
        return None
    benign_media_alternative = (
        isinstance(resolved_intent, EffectIntent)
        and resolved_intent.operations == ("media.status",)
        and _has(
            folded,
            r"\b(?:pista|track)\s+(?:o|or)\s+(?:video|audio)\b",
        )
    )
    benign_asr_catalog_report = (
        isinstance(resolved_intent, EffectIntent)
        and 2 <= len(resolved_intent.operations) <= 8
        and _catalog_report_clauses(folded) is not None
        and _has(folded, r"\bover\s+or\s+layout\s+del\s+sistema\b")
    )
    benign_exhaustive_report = (
        isinstance(resolved_intent, EffectIntent)
        and 2 <= len(resolved_intent.operations) <= 8
        and _has(
            folded,
            r"^(?:sin\s+omitir\s+ninguno|without\s+skipping\s+(?:any|ninguno))"
            r"\s*,?\s*(?:revisa|inspect)\s+(?:en|in)\s+"
            r"(?:(?:este|this)\s+)?(?:orden|order)\s*:\s*",
        )
    )
    benign_trash_prepare_without_commit = (
        isinstance(resolved_intent, EffectIntent)
        and resolved_intent.operations == ("filesystem.trash.prepare",)
        and exact_catalog_operation_plan(folded) == ("filesystem.trash.prepare",)
    )
    benign_routine_catalog_question = (
        isinstance(resolved_intent, EffectIntent)
        and resolved_intent.operations == ("routine.list",)
        and _has(
            folded,
            r"^which\s+habitual\s+sequences\s+does\s+bax[yi]\s+know\s+how\s+to\s+repeat[\s.!?]*$",
        )
    )
    benign_product_correction = (
        isinstance(resolved_intent, EffectIntent)
        and resolved_intent.operations == ("web.search",)
        and _public_product_correction_lookup_request(folded)
    )
    benign_live_lookup = (
        isinstance(resolved_intent, EffectIntent)
        and resolved_intent.operations == ("web.search",)
        and _public_live_lookup_request(folded)
    )
    benign_game_correction = (
        isinstance(resolved_intent, EffectIntent)
        and resolved_intent.operations == ("game.launch",)
        and _corrected_game_launch_title(folded) is not None
    )
    if (
        (
            _is_negative_effect_clause(folded)
            or any(_is_negative_effect_clause(clause) for clause in clauses)
        )
        # A negative clause is not a global ban on an independent positive
        # clause. The full semantic request still carries its constraints;
        # conservation below counts positive effects, not negative statements.
        # Standalone negatives, explicit tool denial, corrections and device
        # restrictions retain their separate fail-closed contracts.
        and len(clauses) < 2
        and not benign_exhaustive_report
        and not benign_trash_prepare_without_commit
        or (
            _has_contradictory_correction(folded, available)
            and not benign_media_alternative
            and not benign_asr_catalog_report
            and not benign_product_correction
            and not benign_live_lookup
            and not benign_game_correction
            and not benign_trash_prepare_without_commit
        )
        # A "what is" envelope can ask for a personal observation. Leaving
        # it to semantic selection is not a missing clause or a no-tool order.
        or (
            _is_explicit_meta_or_tool_denial(folded)
            and not benign_routine_catalog_question
        )
        or _other_device_effect_scope(folded)
    ):
        return CompoundEffectContract(1, ())
    if resolved_intent is _EXPLICIT_EFFECTS_NOT_RESOLVED:
        resolved = resolve_explicit_effects(
            folded,
            available,
            authenticated_applications,
            game_catalog,
        )
    elif resolved_intent is None or isinstance(resolved_intent, EffectIntent):
        resolved = resolved_intent
    else:
        raise TypeError("resolved intent has an invalid type")
    incomplete_exhaustive_report_tail = (
        isinstance(resolved, EffectIntent)
        and len(resolved.operations) >= 2
        and _has(
            folded,
            r"^(?:sin\s+omitir\s+ninguno|"
            r"without\s+skipping\s+(?:any|ninguno))\b",
        )
        and _has(
            folded,
            r"\b(?:resultado\s+por\s+separado|result\s+separately)[\s.!?]*$",
        )
        and not _has(
            folded,
            r"\b(?:devolviendo\s+cada\s+resultado\s+por\s+separado|"
            r"returning\s+each\s+result\s+separately)[\s.!?]*$",
        )
    )
    if incomplete_exhaustive_report_tail:
        # The user explicitly forbade omissions, but the ASR tail itself is
        # missing the return verb/determiner. Treat the apparently complete
        # subset as a truncated utterance and ask again instead of executing.
        return CompoundEffectContract(1, ())
    if resolved is not None:
        return None
    deferred_effect = _has_unsupported_deferred_effect(folded)
    shared_head_minimum = _coordinated_effect_domain_minimum(folded)
    if _has_unresolved_shared_head_coordination(folded):
        shared_head_minimum = max(2, shared_head_minimum or 0)
    multiple_installed_entities = _has_multiple_installed_entities(folded)
    explicit_cardinality = _unresolved_explicit_cardinality(folded)
    if (
        deferred_effect
        or shared_head_minimum is not None
        or multiple_installed_entities
        or explicit_cardinality is not None
    ):
        recognized = _resolve_explicit_effects_single(
            folded,
            available,
            application_names=authenticated_applications,
        )
        recognized_operations = recognized.operations if recognized is not None else ()
        return CompoundEffectContract(
            (
                max(1, len(recognized_operations))
                if deferred_effect
                else max(
                    explicit_cardinality or shared_head_minimum or 2,
                    len(recognized_operations) + 1,
                )
            ),
            ((recognized_operations,) if recognized_operations else ()),
        )
    if len(clauses) < 2:
        return None
    minimum_effects = 0
    unresolved_positive_clauses = 0
    required_sequences: list[tuple[str, ...]] = []
    clause_requirements: list[tuple[str, tuple[str, ...]]] = []
    for clause in clauses:
        result = _resolve_explicit_effects_single(
            clause,
            available,
            application_names=authenticated_applications,
        )
        if result is not None:
            minimum_effects += len(result.operations)
            required_sequences.append(result.operations)
            clause_requirements.append((clause, result.operations))
            continue
        if not _is_negative_effect_clause(clause) and not _is_social_clause(clause):
            minimum_effects += 1
            unresolved_positive_clauses += 1
            clause_requirements.append((clause, ()))
    if unresolved_positive_clauses == 0 or minimum_effects == 0:
        return None
    return CompoundEffectContract(
        minimum_effects,
        tuple(required_sequences),
        tuple(clause_requirements),
    )
