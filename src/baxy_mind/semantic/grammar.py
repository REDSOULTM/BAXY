"""Shared grammar of requests: envelope, clauses, heads and negation. Moved from effect_intent (Fase 3.5).
"""

from __future__ import annotations

import re
from .normalize import fold


_CLOCK_READ_HEAD = (
    r"(?:dime|decime|decir(?:me)?|muestra(?:me)?|mostra(?:r)?(?:me)?|"
    r"ensena(?:r)?(?:me)?|pasa(?:r)?(?:me)?|dame|dar(?:me)?|"
    r"indica(?:r)?(?:me)?|consulta(?:r)?|comprueba|comprobar|revisa(?:r)?|"
    r"tell\s+me|show(?:\s+me)?|give\s+me|check)"
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


_fold = fold  # the single normalization (semantic.normalize)


def _match(text: str, pattern: str) -> re.Match[str] | None:
    return re.search(pattern, text, re.IGNORECASE)


def _has(text: str, pattern: str) -> bool:
    return _match(text, pattern) is not None


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
    # Fase 3.5: «volvé a prender el micrófono» — repeating is aspect, not the
    # action; the request is the infinitive, as after «¿podés …?».
    r"(?:vuelve|volve|volver|vuelvas|vuelva)\s+a\s+(?=[a-z]+(?:ar|er|ir)(?:me|te|se|lo|la|los|las|le|les)?\b)|"
    # Speech discourse markers require punctuation so literal content stays intact.
    rf"(?:a ver|antes que nada|che|oye|oiga|listen|dale)\s*[,;:.!?\-\u2013\u2014]{_PREFIX_GAP}|"
    rf"(?:por curiosidad|una duda|just curious|a question)"
    rf"\s*[,;:.!?\-\u2013\u2014]+{_PREFIX_GAP}|"
    rf"{_DISCOURSE_CLAUSE}\s*[,;:.!?\-\u2013\u2014]+{_PREFIX_GAP}|"
    # Un saludo suelto tampoco cambia el acto de habla: sólo desplaza la cabeza
    # del pedido, igual que el vocativo de abajo. Se exige el separador
    # explícito para que «hola mundo» o «escribe hola» sigan intactos.
    # The raw text keeps its accents («Buenos días,»): the greeting is matched
    # with or without them so every reader sees the same stripped request.
    r"(?:buenos d[ií]as|buenas tardes|buenas noches|buenas|hola|"
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
    r"(?:\s*[.,;:]\s*(?:"
    r"(?:us[aá]|usando|utiliz[aá]|utilizando|emple[aá]|empleando|hazlo con|"
    r"hacelo con|con|mediante|a trav[eé]s de|use|using|with|by using|via)"
    r"\s+(?:el\s+|la\s+|un\s+|una\s+|a\s+|the\s+)?"
    r"(?P<means>python|powershell|bash|cmd|"
    r"script(?:\s+(?:de|en|of|in)\s+(?:python|powershell|bash))?|"
    r"c[oó]digo(?:\s+(?:de|en)\s+python)?|code|terminal|consola|console)"
    r")"
    # H0463 «Busca el App ID de Doom Eternal en Steam usando la API publica»:
    # a public API is a means the product does not call (owner: pending
    # capability); with or without a comma, the directive is declined the
    # same way as a language and the search runs on the request before it.
    r"|(?:\s*[.,;:]\s*|\s+)(?:usando|utilizando|mediante|a trav[eé]s de|"
    r"using|through|via|with|by\s+using)\s+(?:la\s+|el\s+|the\s+|its\s+|su\s+)?"
    r"(?P<api>(?:steam\s+(?:web\s+)?)?api(?:\s+(?:p[uú]blica|publica|public))?"
    r"(?:\s+(?:de|of)\s+steam)?|public\s+(?:steam\s+)?(?:web\s+)?api|steam\s+(?:web\s+)?api)"
    r")\s*[.!]*$",
    re.IGNORECASE,
)


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
            # Fase 3.5 (owner 2026-09-21, turn 222 «ahora súbelo a 100»): a time
            # or sequence adverb without a comma before an order is not part of
            # the order; only an action head may follow it.
            found = _match(
                current,
                r"^[¿?¡!\s]*(?:y\s+|pues\s+)?(?:ahora|luego|despues|entonces|ya)(?:\s+mismo)?\s+(?P<body>.+)$",
            )
            if found is not None and not _head_is(_request_head(found.group("body")), _COVERAGE_ACTION_HEAD):
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


_ENCLITIC_TAIL = re.compile(r"(?:(?:me|te|se|nos)?(?:los|las|lo|la|les|le)|me|te|nos)$")


def _head_forms(head: str) -> tuple[str, ...]:
    """The forms a verb head is recognized by (Fase 3.5, one rule instead of one entry per form).

    The head as written; without the object clitics fused to it («cerralo» → «cerra», «devolvele» →
    «devolve», «llamame» → «llama»); and a voseo imperative as its infinitive («cerra» → «cerrar»,
    «prende» → «prender», «subi» → «subir»). Short heads keep only themselves, so «ve» never becomes
    «ver» and «dale» never «da».
    """

    forms = [head]
    if len(head) >= 5:
        stripped = _ENCLITIC_TAIL.sub("", head)
        if stripped != head and len(stripped) >= 3:
            forms.append(stripped)
    for form in tuple(forms):
        if len(form) >= 4 and form[-1] in "aei":
            forms.append(form + "r")
    return tuple(forms)


def _head_is(head: str, pattern: str) -> bool:
    return any(re.fullmatch(pattern, form, re.IGNORECASE) is not None for form in _head_forms(head))


def _negative_action_forms(folded: str) -> tuple[str, ...]:
    """Project a prohibited action for scope comparison, never execution."""

    found = re.match(
        r"^[¡!\s]*(?:(?P<es>no|nunca|jamas)\s+"
        # THEN2003 «No le pongas nada.»: the dative clitic (le/les) sits before the verb too.
        r"(?:(?:me|te|le|les|lo|la|los|las|nos)\s+)?|(?:never|don't|dont|do\s+not)\s+)"
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


# Verbos que ponen o quitan el silencio global. «apaga» y «activa» solo
# cuentan con un objeto de audio explícito, porque también gobiernan el equipo
# y otros dispositivos.
_UNMUTE_VERB = (
    r"(?:unmute|desmutea(?:me|lo|la)?|desmutear(?:lo|la)?|desmutees|"
    r"des(?:s)?ilenci(?:a(?:r(?:lo|la)?|me|lo|la)?|es))"
)


_SET_VOLUME_VERB = (
    r"(?:pon(?:me|le|e|elo|ele|lo)?|poner|fija|ajusta|adjust|establece|set|"
    r"cambia|change|deja|dejame|leave)"
)


_VOLUME_UP_VERB = r"(?:sube(?:lo|la|le)?|subi(?:le)?|suvi|subir(?:le)?|aumenta(?:le)?|aumentar|incrementa|incrementar|increase|raise|up)"


_VOLUME_DOWN_VERB = r"(?:baja(?:lo|la|le)?|bajar(?:le)?|reduce|reducir|decrease|lower|down)"


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


_KNOWN_APPLICATION = (
    r"(?:bloc de notas|notepad|calculadora|calculator|calc|opera gx|opera|spotify|"
    r"steam|discord|chrome|google chrome|word|microsoft word|edge|"
    r"microsoft edge|firefox|whatsapp|excel|powerpoint|vlc|"
    r"configuracion(?:es)?(?: de windows)?|windows settings)"
)


_CONNECTED_INVENTORY = (
    r"\b(?:cosas?|things?|dispositivos?|devices?|perifericos?|peripherals?|"
    r"accesorios?|accessories)\b.{0,48}"
    r"\b(?:conectad[oa]s?|connected|enchufad[oa]s?|plugged|attached)\b|"
    r"\b(?:conectad[oa]s?|connected|enchufad[oa]s?|plugged|attached)\b.{0,40}"
    r"\b(?:al\s+equipo|a\s+(?:la\s+)?(?:maquina|computadora|pc)|"
    r"to\s+(?:the\s+)?(?:machine|computer|pc|equipment))\b"
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


# SEARCH2005 «dale, buscame recetas de pizza»: the clitic forms head a search too.
_SEARCH = r"(?:busc[aá](?:me|melo|mela|mel[oa]s)?|buscar|encuentra|search|find|look\s+up)"


# Verbs for catalog effects that this conservative recognizer does not
# necessarily classify itself.  They are used only as clause boundaries: if a
# compound request contains one of them and the following clause cannot be
# resolved, the whole deterministic path abstains instead of executing a
# recognized prefix and silently dropping the rest of the request.
_COVERAGE_ACTION_HEAD = (
    rf"(?:{_OPEN}|{_LIST}|{_READ}|{_CLOCK_READ_HEAD}|{_CREATE}|{_SEARCH}|{_SET_VOLUME_VERB}|"
    # «sound the alarm» is an order; «volume and sound output» is a noun.
    r"haz|toma|captura|take|capture|dejar|put|ring|sound(?=\s+(?:the|an?|la|una)\s+alarm)|"
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
    r"remove|apaga|apagar|shutdown|shut\s+down|turn\s+off|power\s+off|reinicia|reiniciar|restart|reboot|suspende|"
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
