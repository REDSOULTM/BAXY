"""Lectura única del pedido: idioma, saludo y petición real.

Antes de esta pieza el idioma visible se decidía dos veces en Python
(`llm._message_response_language`, `__main__._explicit_response_language`) y
otra vez en C# (`UserMessagePolicy.IsEnglishGreetingRequest`), con tres
lexicones distintos. «Good afternoon» salía español en Python e inglés en C#:
el compositor recibía `greeting=hola` y su siguiente validador lo vetaba.

Aquí vive el contrato: una lectura por turno, con precedencia explícita
(traducción → idioma pedido → evidencia del texto → idioma de la conversación
→ español por defecto) y una separación de saludo y petición que nunca borra
lo que la persona pidió. `RequestReading.to_payload()` es la representación que
cruza la frontera hacia el shell; nadie la reinterpreta después.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata

LANGUAGES = ("es", "en", "mixed")

GREETING_NONE = "none"
GREETING_ONLY = "only"
GREETING_LEADING = "leading"

INTENT_KNOWLEDGE = "knowledge"
INTENT_CAPABILITY = "capability"
INTENT_IDENTITY = "identity"
INTENT_REFUSE = "refuse"
INTENT_TRANSLATION = "translation"
INTENT_AMBIGUOUS_ACTION = "ambiguous_action"
INTENT_CONTINUE_CONSTRAINT = "continue_constraint"
INTENT_NEGATIVE_CONSTRAINT = "negative_constraint"

_SPANISH_ORTHOGRAPHY = re.compile(r"[ñáéíóúü¿¡]", re.IGNORECASE)
_ENGLISH_CONTRACTION = re.compile(
    r"\b(?:can|could|would|should|do|does|did|is|are|was|were|will|ai|"
    r"have|has|had|must|might|i|you|we|they|he|she|it|that|there|what|"
    r"who|let|don|won)['’](?:t|s|m|re|ll|ve|d)\b",
    re.IGNORECASE,
)

# Palabras funcionales y verbos frecuentes. No se listan nombres propios ni
# términos compartidos por los dos idiomas: un token ambiguo no es evidencia.
_ES_WORDS = frozenset(
    """
    abras abre abrir abierta abierto actual ademas al algo alguna alguno alli ambos ante
    antes aquello aqui asi aunque ayer borra buenas buenos busca cada
    cancelar cerrada cerrado cierra cierre como con confirmar continuar contra crea cual cuales cuando cuanto cuenta
    cuentame de dejar del desde dias dice dices dime donde dos durante el
    ella ellas ellos encontrar encuentra entendi entiendo entonces era explica explicame
    eres esa ese eso escrita escrito esta estan este esto estoy fue gracias guardada guardado hace hacer
    haces hacia han hasta haz hola hora horas hoy igual incluso la las
    lee lista listo lo los luego manana mas mi mientras mis misma mismo
    modo mostrar mucha mucho muestra muy nada navega ninguna ninguno
    noches nos nota notas nuestra nuestro nunca ocupas otra otro para pero
    poco podia pon por porque procesos pude puede pueden puedes que quien
    quiere quieres quita reactiva reproduce sabes se segun ser si sido
    siempre siendo sigue silencia sobre sois somos son soy su sube sus
    tambien tanto tardes tarea tareas terminada terminado tiene tienen tienes toda todas todo
    todos trabajo tras tus un una unas uno unos usted ustedes vamos varias
    varios vez volumen vosotros voy y
    """.split()
)

_EN_WORDS = frozenset(
    """
    about above across after again against all along already also although
    always am among an and another any anything are around as ask asked at
    be because been before being below beside between both build but buy
    by bye call can cancel cannot close computer confirm continue could couple create currently
    delete details did does doing done down during each either else email
    enough even ever every everything explain few find first for from get give
    going good goodbye got great hard have having hear hello her here hers
    hey hi him his how however i if in into is isn it its just keep kind
    know later launch let letter like line list listen little look lose
    made make many maybe mine more most much music must my navigate near
    need never new next nothing now of off often on once one only open
    opened or order other our out over own pause phone play please process
    processes read really right said say search see select send sentence
    set should show since so some something soon sound speak speakers
    still stop such take talk tell temperature than thank thanks that the
    their them then there these they thing think this those though three
    through time to today together tomorrow too turn two under understand
    unmute until up upon us used very want was way we well were what
    whatever when where whether which while who why will window with
    within without would write wrote yes yesterday yet you your yours
    summarize summarise summary minimize maximize
    """.split()
)

_ES_PHRASES = (
    "buenos dias",
    "buenas tardes",
    "buenas noches",
    "que tal",
    "muchas gracias",
    "mil gracias",
    "por favor",
    "hasta luego",
    "nos vemos",
    "como estas",
    "me llamo",
    "te llamas",
    "se llama",
)

_EN_PHRASES = (
    "good morning",
    "good afternoon",
    "good evening",
    "good night",
    "hi there",
    "how are you",
    "see you",
    "thank you",
    "thanks a lot",
    "no problem",
)

_GREETING_HEAD = re.compile(
    r"^(?:buenos dias|buenas tardes|buenas noches|buenas|buenos|hola|"
    r"good morning|good afternoon|good evening|good night|"
    r"hi there|hello|hey|hi)"
    r"(?![a-z])",
)

# «Un saludo corto» pide un saludo: es la petición entera, no un encabezado.
_GREETING_REQUESTS = frozenset(
    {
        "just say hi",
        "say hi",
        "say hello",
        "solo un hola",
        "un saludo",
        "un saludo corto",
        "solo un saludo",
        "saludo corto",
        "saludame",
    }
)

# Vocativos y muletillas que acompañan a un saludo sin añadir petición.
_GREETING_FILLERS = (
    "a todos",
    "again",
    "amigo",
    "baxy",
    "compa",
    "de nuevo",
    "otra vez",
    "there",
    "tio",
)

_TRANSLATION_TOKENS = ("traduce", "traduceme", "traducir", "translate ")
_TO_SPANISH = ("al espanol", "to spanish", "en espanol", "in spanish")
_TO_ENGLISH = ("al ingles", "to english", "en ingles", "in english")

_KNOWLEDGE_TOKENS = (
    "que es ", "que es un", "explicame", "explica ", "explain ", "define ",
    "definicion de", "what is ", "what are ", "why ", "por que ",
    "te ocupas", "what do you do", "what can you do", "que puedes hacer",
    "que sabes hacer", "able to do", "echar una mano", "what will you",
    "what do you refuse", "que rechazas", "never do", "cannot do", "no haces",
    "who are you", "quien eres", "who is speaking", "quien habla",
    "introduce yourself", "presentate", "describe yourself", "describete",
    "traduce", "translate ",
    # IDENTITY1323 H0373 «cómo funciona esto»: how this works asks what the
    # assistant does, not a definition of a mechanism.
    "como funciona esto", "como funcionas", "como funciona baxy",
    "como funciona este asistente", "how does this work", "how do you work",
)

# «Qué puedes hacer» pide capacidades; «qué no haces» pide el límite. Estaban
# en el mismo cajón, así que una pregunta por los límites recibía la lista de
# capacidades y el modelo la negaba entera (panel-opus-2/017 y /030).
_CAPABILITY_TOKENS = (
    "te ocupas", "what do you do", "what can you do", "que puedes hacer",
    "que sabes hacer", "able to do", "echar una mano", "what are you able",
    "como funciona esto", "como funcionas", "como funciona baxy",
    "como funciona este asistente", "how does this work", "how do you work",
)

_IDENTITY_TOKENS = (
    "who are you", "quien eres", "quien sos", "who is speaking", "quien habla",
    "quien esta hablando", "introduce yourself", "presentate",
    "describe yourself", "describete",
)
# IDENTITY1323 H0012 «to quien chuta eres.»: one or two words between «quién»
# and «eres/sos» (an expletive, «te crees que») do not change the question.
_IDENTITY_EXPLETIVE = re.compile(
    r"\bquien\s+(?:\w+\s+){1,2}(?:eres|sos|eri|es\s+usted)\b|"
    r"\bwho\s+(?:the\s+\w+\s+|on\s+earth\s+)are\s+you\b"
)

_REFUSE_TOKENS = (
    "what will you", "what do you refuse", "que rechazas", "never do",
    "cannot do", "que no haces", "what don't you", "what dont you",
    "what do you not", "que no puedes hacer",
)

# Una pregunta por lo que hace o no hace el producto se reconocía por frases
# enteras, y bastaba decirlo de otra manera para salirse de la lista:
# «cuáles son tus límites aquí», «qué te niegas a hacer», «what do you handle
# on this PC» no estaban y se contestaron con una aclaración construida con
# vocabulario del planificador (panel-opus-13/038, /046, /052, /058).
#
# Lo que comparten no es la frase sino la forma: preguntan por quien contesta
# —segunda persona— y por lo que hace, o por el borde de lo que hace. Se lee
# componiendo tres vocabularios cerrados en vez de enumerando frases.
_SECOND_PERSON = re.compile(
    r"\b(?:tu|tus|te|ti|contigo|eres|sos|vos|estas|haces|puedes|podes|sabes|sueles|"
    r"you|your|yours|yourself)\b"
)
_DOING = re.compile(
    r"\b(?:hacer|haces|hace|hacen|puedes|podes|podrias|sabes|ofreces|ocupas|"
    r"manejas|gestionas|sirves|ayudas|do|does|doing|can|handle|handles|"
    r"manage|able|offer|help|capable)\b"
)
_LIMIT = re.compile(
    r"\b(?:niegas|negarse|rechazas|limite|limites|limitacion|"
    r"limitaciones|restriccion|restricciones|refuse|refuses|"
    r"limit|limits|limitation|limitations|restriction|restrictions)\b"
)
_NEGATED_DOING = re.compile(
    r"\b(?:no|nunca|jamas|never|not|cannot|cant|wont)\s+"
    r"(?:(?:me|te|le|nos|os|les|suelo|sueles|suele|suelen)\s+)*"
    + _DOING.pattern
)

_CAPABILITY_OVERRIDE_TOKENS = (
    "que puedes hacer", "que sabes hacer", "what can you do",
    "what do you do", "able to do",
)

_AMBIGUOUS_ACTION_TOKENS = (
    "abreme eso", "abre eso", "cierra aquello", "open that", "close that",
    "hazlo", "do it", "do that", "haz eso", "open it", "close it",
)

# Seguir hablando se pide de muchas maneras: «keep going», «keep chatting»,
# «keep talking», «sigue charlando», «continúa». La lista de frases enteras se
# quedaba corta —«keep talking without launching anything» se contestó con una
# pregunta sobre Lima (limites-14/009)— así que se lee el verbo de continuar.
# Sólo cuenta junto a una restricción, así que un «keep» suelto no arrastra.
_CONTINUE = re.compile(
    r"\b(?:keep|keeps|continue|continues|carry\s+on|go\s+on|"
    r"sigue|sigues|seguir|siga|continua|continuar|continue)\b"
)
_CONSTRAINT_TOKENS = ("without apps", "without opening", "sin abrir",
                      "sin lanzar", "without launching")
_NEGATIVE_TOKENS = ("no abras", "don't open", "dont open", "don't launch",
                    "dont launch", "no lances", "sin lanzar")

_ASK_TRIM = " .,!?¿¡…-–—"
_LEADING_SEPARATORS = " ,;:.-–—"


def fold(text: str) -> str:
    """Minúsculas sin diacríticos, con los espacios colapsados."""

    decomposed = unicodedata.normalize("NFKD", (text or "").casefold())
    stripped = "".join(
        character
        for character in decomposed
        if not unicodedata.combining(character)
    )
    return " ".join(stripped.split())


def _contains_any(folded: str, tokens: tuple[str, ...]) -> bool:
    return any(fold(token) in folded for token in tokens)


@dataclass(frozen=True)
class RequestReading:
    """Lectura del pedido. Una por turno; se transporta, no se recalcula."""

    text: str
    language: str
    greeting: str
    ask: str
    intents: frozenset[str]
    evidence: tuple[int, int]

    @property
    def greets(self) -> bool:
        return self.greeting != GREETING_NONE

    @property
    def greeting_only(self) -> bool:
        return self.greeting == GREETING_ONLY

    def has(self, intent: str) -> bool:
        return intent in self.intents

    def to_payload(self) -> dict[str, object]:
        return {
            "language": self.language,
            "greeting": self.greeting,
            "ask": self.ask,
            "intents": sorted(self.intents),
        }

    @staticmethod
    def from_payload(payload: object) -> "RequestReading | None":
        """Reconstruye la lectura emitida aguas arriba, sin reinterpretarla."""

        if not isinstance(payload, dict):
            return None
        language = payload.get("language")
        greeting = payload.get("greeting")
        if language not in LANGUAGES:
            return None
        if greeting not in (GREETING_NONE, GREETING_ONLY, GREETING_LEADING):
            return None
        raw_intents = payload.get("intents")
        intents = frozenset(
            str(item)
            for item in (raw_intents if isinstance(raw_intents, list) else [])
        )
        ask = str(payload.get("ask") or "")
        return RequestReading(
            text=str(payload.get("text") or ask),
            language=str(language),
            greeting=str(greeting),
            ask=ask,
            intents=intents,
            evidence=(0, 0),
        )


def _explicit_language(folded: str) -> str | None:
    """Traducción y idioma pedido mandan sobre la evidencia del texto."""

    if _contains_any(folded, _TRANSLATION_TOKENS) or _contains_any(
        folded,
        ("responde en ", "contesta en ", "answer in ", "reply in ",
         "respond in "),
    ):
        if _contains_any(folded, ("en spanglish", "in spanglish", "to spanglish",
                                  "a spanglish", "al spanglish")):
            return "mixed"
        if _contains_any(folded, _TO_SPANISH):
            return "es"
        if _contains_any(folded, _TO_ENGLISH):
            return "en"
    return None


def _language_evidence(text: str, folded: str) -> tuple[int, int]:
    tokens = set(re.findall(r"[a-z]+", folded))
    spanish = len(tokens & _ES_WORDS)
    english = len(tokens & _EN_WORDS)
    spanish += 2 * sum(
        1 for phrase in _ES_PHRASES if re.search(rf"\b{re.escape(phrase)}\b", folded)
    )
    english += 2 * sum(
        1 for phrase in _EN_PHRASES if re.search(rf"\b{re.escape(phrase)}\b", folded)
    )
    if _SPANISH_ORTHOGRAPHY.search(text or ""):
        spanish += 2
    if _ENGLISH_CONTRACTION.search(text or ""):
        english += 2
    return spanish, english


def _select_language(
    spanish: int,
    english: int,
    conversation_language: str | None,
) -> str:
    if not spanish and not english:
        if conversation_language in LANGUAGES:
            return conversation_language
        return "es"
    if not spanish:
        return "en"
    if not english:
        return "es"
    weak, strong = (
        (spanish, english) if spanish <= english else (english, spanish)
    )
    if weak * 3 >= strong:
        return "mixed"
    return "es" if spanish > english else "en"


def _strip_fillers(remainder: str) -> str:
    changed = True
    while changed and remainder:
        changed = False
        for filler in _GREETING_FILLERS:
            if remainder.strip(_ASK_TRIM) == filler:
                return ""
            if remainder.startswith(filler + " "):
                remainder = remainder[len(filler) + 1:].lstrip(
                    _LEADING_SEPARATORS
                )
                changed = True
                break
    return remainder


def _original_tail(text: str, folded_remainder: str) -> str:
    """Devuelve el tramo original del resto: conserva signos y mayúsculas."""

    head = (text or "").strip()
    for start in range(len(head)):
        if fold(head[start:]).strip(_ASK_TRIM) == folded_remainder:
            return head[start:].lstrip(_LEADING_SEPARATORS).rstrip()
    return folded_remainder


def _read_greeting(text: str, folded: str) -> tuple[str, str]:
    """Separa el saludo de la petición sin perder el texto original."""

    bare = folded.strip(_ASK_TRIM)
    if bare in _GREETING_REQUESTS:
        return GREETING_ONLY, ""
    match = _GREETING_HEAD.match(bare)
    if match is None:
        return GREETING_NONE, (text or "").strip()
    remainder = bare
    while match is not None:
        remainder = _strip_fillers(
            remainder[match.end():].lstrip(_LEADING_SEPARATORS)
        ).strip(_ASK_TRIM)
        # «Hola, buenas» encadena dos saludos; sigue siendo sólo un saludo.
        match = _GREETING_HEAD.match(remainder)
    if not remainder:
        return GREETING_ONLY, ""
    return GREETING_LEADING, _original_tail(text, remainder)


def _read_intents(ask: str) -> frozenset[str]:
    folded = fold(ask)
    intents: set[str] = set()
    if not folded:
        return frozenset(intents)
    if _contains_any(folded, _KNOWLEDGE_TOKENS) or _IDENTITY_EXPLETIVE.search(folded):
        intents.add(INTENT_KNOWLEDGE)
    continue_constraint = _CONTINUE.search(folded) is not None and _contains_any(
        folded, _CONSTRAINT_TOKENS
    )
    if continue_constraint:
        intents.add(INTENT_CONTINUE_CONSTRAINT)
    elif _contains_any(folded, _NEGATIVE_TOKENS):
        intents.add(INTENT_NEGATIVE_CONSTRAINT)
    # Pregunta por quien contesta y por lo que hace: capacidad si no marca un
    # borde, límite si lo marca. La forma manda sobre la frase exacta.
    about_you = (
        _INTERROGATIVE.search(folded) is not None
        and _SECOND_PERSON.search(folded) is not None
        and (_DOING.search(folded) is not None or _LIMIT.search(folded) is not None)
        and not continue_constraint
        and not _contains_any(folded, _NEGATIVE_TOKENS)
    )
    # «Qué puedes hacer y qué no haces» pide capacidades: el override que ya
    # gobernaba las frases enteras gobierna también la forma.
    marks_a_limit = (
        about_you
        # A negated person/reference ("no tú") says nothing about capability.
        # Bind negation to the activity; explicit limit nouns still stand alone.
        and (_LIMIT.search(folded) is not None or _NEGATED_DOING.search(folded) is not None)
        and not _contains_any(folded, _CAPABILITY_OVERRIDE_TOKENS)
    )
    if not continue_constraint and (
        _contains_any(folded, _CAPABILITY_TOKENS)
        or (about_you and not marks_a_limit)
    ):
        intents.add(INTENT_CAPABILITY)
    if _contains_any(folded, _IDENTITY_TOKENS) or _IDENTITY_EXPLETIVE.search(folded):
        intents.add(INTENT_IDENTITY)
    if (
        _contains_any(folded, _REFUSE_TOKENS)
        and not _contains_any(folded, _CAPABILITY_OVERRIDE_TOKENS)
    ) or marks_a_limit:
        intents.add(INTENT_REFUSE)
    if _contains_any(folded, _TRANSLATION_TOKENS):
        intents.add(INTENT_TRANSLATION)
    # cien-36 096 «ábreme eso porfa»: only the two formal politeness phrases
    # were stripped here, so the colloquial one left the request out of the
    # ambiguous-action reading and the turn answered that it could not
    # understand, where «ábreme eso» asks what to open.
    _POLITENESS = r"(?:por favor|please|porfa|porfis?|plis|pls|plz)"
    bare_request = re.sub(
        rf"^{_POLITENESS}\s*,?\s+|\s*,?\s*{_POLITENESS}$",
        "",
        folded.strip(_ASK_TRIM),
    )
    if bare_request in _AMBIGUOUS_ACTION_TOKENS:
        intents.add(INTENT_AMBIGUOUS_ACTION)
    return frozenset(intents)


def read_request(
    text: str,
    conversation_language: str | None = None,
) -> RequestReading:
    """Lee el pedido una vez: idioma, saludo, petición e intenciones."""

    raw = text or ""
    folded = fold(raw)
    greeting, ask = _read_greeting(raw, folded)
    spanish, english = _language_evidence(raw, folded)
    language = _explicit_language(folded)
    if language is None:
        language = _select_language(spanish, english, conversation_language)
    return RequestReading(
        text=raw,
        language=language,
        greeting=greeting,
        ask=ask,
        intents=_read_intents(ask if greeting == GREETING_LEADING else raw),
        evidence=(spanish, english),
    )


def response_language(
    text: str,
    conversation_language: str | None = None,
) -> str:
    """Idioma visible del turno. Único punto de decisión determinista."""

    return read_request(text, conversation_language).language


def spoken_language(text: str) -> str:
    """Voice of already composed text; quoted language requests are not instructions."""
    spanish, english = _language_evidence(text, fold(text))
    return "en" if english > spanish else "es"


# --- Seguimiento elíptico --------------------------------------------------
#
# «¿por qué importa?» no dice de qué habla: su tema está en el turno anterior.
# La mente lo resolvía pidiéndole al modelo que parafraseara su propia
# respuesta previa, y eso producía dos defectos medidos (`seguimiento-1..3`):
# la paráfrasis salía en abstracto («porque entender por qué es importante
# ayuda a decidir») y a veces el tema anterior se colaba en una pregunta nueva
# que sí traía el suyo («explain what a VPN is» → «¿Para qué sirve un proxy?»).
#
# Aquí la elipsis se trata como lo que es: una lectura del pedido. Se reconoce
# que la pregunta no nombra su tema y se recupera el tema de las palabras de la
# persona, no de la respuesta del asistente. Quien contesta sigue siendo la
# ruta de conocimiento, que ya responde bien cuando la pregunta está completa.

# Armazón de una pregunta: interrogativos, cópulas, artículos, pronombres y
# los verbos genéricos con los que se pregunta por la causa o la utilidad de
# algo. Una pregunta hecha sólo de armazón no tiene tema propio.
_FRAME_VERBS = frozenset(
    """
    importa importan importaba interesa interesan sirve sirven sirvio
    usa usan usaria usarian usamos usarse usaba necesita necesitan necesito
    conviene convienen hace hacen funciona funcionan aplica aplican vale
    matter matters mattered use uses used using need needs needed
    work works help helps apply applies
    """.split()
)
_FRAME_WORDS = frozenset(
    """
    a al ante con de del desde en entre hacia hasta para por segun sin sobre
    tras y e o u ni pero mas menos ya tambien tampoco entonces asi bien
    que quien quienes cual cuales como cuando donde cuanto cuanta cuantos
    el la lo los las le les un una unos unas
    este esta esto estos estas ese esa eso esos esas aquel aquella aquello
    me te se nos os mi tu su sus yo tuyo mio nuestro
    es son era eran fue fueron sea sean esta estan estaba sigue siguen siendo
    hay haber tener tiene tienen no si muy tan mucho poco algo nada
    util utiles importante importantes ventaja ventajas
    and or but so then still also too very much just
    a an the this that these those it its they them their
    i you we he she my your our
    what which who whom whose why how when where
    is are was were be been being do does did done has have had
    for to of in on at with about from by as
    should would could can may might will shall
    good useful important
    """.split()
) | _FRAME_VERBS

# Un clítico («lo», «la») va pegado o delante de un verbo; un artículo va
# delante de un sustantivo. Sólo el primero es anafórico.
_CLITIC_ON_INFINITIVE = re.compile(
    r"\b\w{2,}(?:ar|er|ir|ando|iendo)(?:me|te|se|nos|lo|la|le|los|las|les)\b"
)
_PROCLITIC = re.compile(r"\b(?:lo|la|le|los|las|les)\s+(\w+)")
_DEMONSTRATIVE = re.compile(r"\b(?:eso|esto|ello|aquello|it|that|this)\b\s*(\w+)?")


def _refers_back(folded: str) -> bool:
    """«eso» solo es anáfora si no lleva su sustantivo detrás.

    «what are your limits on this PC» se contestó con la definición de máscara
    de subred del turno anterior (panel-opus-13/051): «this» ahí es el
    determinante de «PC», no un referente al turno anterior. Un determinante va
    seguido de su sustantivo, y un sustantivo nunca es armazón.
    """

    for match in _DEMONSTRATIVE.finditer(folded):
        siguiente = match.group(1)
        if siguiente is None or siguiente in _FRAME_WORDS:
            return True
    return False
_INTERROGATIVE = re.compile(
    r"\b(?:que|cual|cuales|como|cuando|donde|cuanto|cuanta|cuantos|cuantas|"
    r"quien|quienes|what|which|how|when|where|why|who|whom|whose)\b"
)
_LEADING_CONNECTOR = re.compile(
    r"^(?:y|e|and|pero|but|ok|vale|bueno|entonces|so|then|oye|hey)\s+"
)

_TOPIC_FRAMES = (
    re.compile(r"\bqu[eé] (?:es|son)\b\s+(.+)", re.IGNORECASE),
    re.compile(r"\bwhat(?:'s| is| are)\b\s+(.+)", re.IGNORECASE),
    re.compile(r"\bexpl[ií]ca(?:me)?\b\s+(.+)", re.IGNORECASE),
    re.compile(r"\bexplain\b\s+(?:what\s+)?(.+?)(?:\s+is\b|\s+are\b|$)", re.IGNORECASE),
    re.compile(r"\bdefine\b\s+(.+)", re.IGNORECASE),
    re.compile(r"\bh[aá]blame de\b\s+(.+)", re.IGNORECASE),
)
_TOPIC_TAIL = re.compile(
    r"[,;]?\s*(?:(?:en|in)\s+)?(?:una?\s+frase|one\s+sentence|dos\s+frases|"
    r"two\s+sentences|brevemente|briefly|corto|short|por\s+favor|please)\b.*$|"
    r"[,;]?\s*(?:(?:pero|but)\s+)?(?:(?:en|in)\s+)?(?:"
    r"sin\s+tecnicismos|without\s+jargon|simple\s+terms|plain\s+language|"
    r"simple|sencillo)[.!?\s]*$",
    re.IGNORECASE,
)
_TOPIC_LEAD = re.compile(
    r"^(?:qu[eé]\s+(?:es|son)\s+)?(?:un|una|unos|unas|el|la|los|las|"
    r"an|a|the)\s+",
    re.IGNORECASE,
)


def is_elliptical_followup(text: str) -> bool:
    """¿La pregunta deja su tema en el turno anterior?

    Hacen falta las dos cosas: que pregunte —lleva un interrogativo— y que no
    nombre su tema, por armazón o por anáfora. Sin lo primero, «still there?»
    heredaría el tema anterior aunque pregunte por quien contesta, y «ábreme
    eso» o «close that» —que son encargos deícticos, no seguimientos— también.
    """

    ask = read_request(text).ask
    folded = _LEADING_CONNECTOR.sub("", fold(ask)).strip(_ASK_TRIM)
    if not folded:
        return False
    words = folded.split()
    if not words or len(words) > 12:
        return False
    if _INTERROGATIVE.search(folded) is None:
        return False
    if all(word in _FRAME_WORDS for word in words):
        return True
    proclitic = _PROCLITIC.search(folded)
    return (
        _CLITIC_ON_INFINITIVE.search(folded) is not None
        or _refers_back(folded)
        or (proclitic is not None and proclitic.group(1) in _FRAME_VERBS)
    )


def request_topic(text: str) -> str | None:
    """El tema que la persona nombró, tal y como lo nombró."""

    ask = read_request(text).ask.strip(_ASK_TRIM)
    for frame in _TOPIC_FRAMES:
        match = frame.search(ask)
        if match is None:
            continue
        topic = _TOPIC_TAIL.sub("", match.group(1)).strip(_ASK_TRIM)
        topic = _TOPIC_LEAD.sub("", topic).strip(_ASK_TRIM)
        if topic and len(topic.split()) <= 8 and fold(topic) not in _FRAME_WORDS:
            return topic
    return None


def starts_new_definition_topic(text: str, prior_texts: list[str]) -> bool:
    """Recognize a new, explicitly named simple definition topic.

    Keep context for references, multiword descriptions and previously mentioned
    subjects. This conservative boundary reuses topic extraction; it does not
    classify actions or erase conversation state.
    """
    topic = request_topic(text)
    if topic is None or is_elliptical_followup(text):
        return False
    normalized = fold(topic)
    if len(normalized.split()) != 1 or normalized in _FRAME_WORDS:
        return False
    return not any(
        re.search(r"(?<!\w)" + re.escape(normalized) + r"(?!\w)", fold(previous))
        for previous in prior_texts
    )


def followup_topic(text: str, prior_user_texts: object) -> str | None:
    """Tema de un seguimiento elíptico, leído del último pedido con tema.

    Devuelve ``None`` cuando la pregunta trae su propio tema: ahí anclar en el
    turno anterior es justamente el error que arrastraba el tema viejo.
    """

    if not is_elliptical_followup(text):
        return None
    if not isinstance(prior_user_texts, (list, tuple)):
        return None
    for previous in reversed(list(prior_user_texts)):
        candidate = str(previous or "")
        if not candidate.strip() or is_elliptical_followup(candidate):
            continue
        topic = request_topic(candidate)
        if topic is not None:
            return topic
    return None
